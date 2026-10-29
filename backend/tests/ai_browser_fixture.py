"""Owned disposable actual-Qwen browser fixture; no production/customer schema or data."""

import json
import os
import re
import secrets
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue, SimpleWorker
from rq.job import Job
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.schema import DropSchema

from app.auth.dependencies import COOKIE_NAME
from app.common.database import make_engine
from app.conflicts.models import Conflict
from app.main import create_app
from app.similarity.jobs import recover_indexes
from app.similarity.models import IndexRun
from app.similarity.provider import inference_queue
from app.similarity.service import start_run
from tests.recommendation_fixtures import Cases
from tests.test_auth import isolated_environment, role_tokens

DESTINATION = Path(os.environ.get("FK_AI_BROWSER_FIXTURE", "/fixture/fixture.json"))


def prepare():
    if DESTINATION.exists():
        raise SystemExit("Owned AI browser fixture already exists")
    environment = isolated_environment(preserve_schema=True)
    base = next(environment)
    settings = base.model_copy(
        update={
            "deployment_mode": "test",
            "similarity_provider": "qwen-demo",
            "similarity_allow_qwen_demo": True,
            "recommendation_enabled": True,
            "ai_enabled": True,
            "import_queue_name": "stage9-ai-browser-" + uuid4().hex,
            "ai_service_key_file": Path(os.environ["FK_AI_TEST_KEY_FILE"]),
            "ai_embedding_endpoint": os.environ["FK_AI_TEST_EMBEDDING_ENDPOINT"],
            "ai_llm_endpoint": os.environ["FK_AI_TEST_LLM_ENDPOINT"],
            "import_storage_root": Path("/imports"),
        }
    )
    schema = settings.auth_rate_prefix.removesuffix(":")
    assert re.fullmatch(r"auth_test_[a-f0-9]{32}", schema)
    ownership = {
        "kind": "owned-stage9-synthetic-browser-fixture-v1",
        "schema": schema,
        "import_queue_name": settings.import_queue_name,
        "auth_rate_prefix": settings.auth_rate_prefix,
        "ready": False,
    }
    # Retain cleanup ownership even if later model/index preparation fails.
    fd = os.open(DESTINATION, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as out:
        json.dump(ownership, out)
    password = secrets.token_urlsafe(24)
    tokens = role_tokens.__wrapped__(settings, password)
    with TestClient(create_app(settings=settings), base_url="https://localhost:8443") as client:
        client.cookies.set(COOKIE_NAME, tokens["DATA_OWNER"])
        cases = Cases(client)
        for _ in range(5):
            cases.confirm(cases.case())
        current = cases.case()
        fallback = cases.case()
        with Session(client.app.state.engine) as session:
            schema = session.scalar(text("SELECT current_schema()"))
            from uuid import UUID

            matching = str(session.get(Conflict, UUID(current)).matching_run_id)
            fallback_matching = str(session.get(Conflict, UUID(fallback)).matching_run_id)
            run = start_run(session, settings, "qwen-demo-v1", activate=True, batch_size=8)
            session.commit()
            run_id = run.id
        with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
            queue = Queue(inference_queue(settings), connection=redis)
            for _ in range(2):
                recover_indexes(settings, redis)
                with patch("app.similarity.jobs.Settings", return_value=settings):
                    SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
        with Session(client.app.state.engine) as session:
            assert session.get(IndexRun, run_id).status == "COMPLETED"
        result = {
            **ownership,
            "ready": True,
            "schema": schema,
            "login": "data_owner",
            "password": password,
            "case_id": current,
            "matching_id": matching,
            "fallback_case_id": fallback,
            "fallback_matching_id": fallback_matching,
            "precedents": [item["decision_id"] for item in cases.decisions],
            "database_url": settings.database_url.get_secret_value(),
            "redis_url": settings.redis_url.get_secret_value(),
            "import_queue_name": settings.import_queue_name,
            "auth_rate_prefix": settings.auth_rate_prefix,
            "source_map": settings.recommendation_source_map,
        }
        temporary = DESTINATION.with_name("prepared-fixture.json")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(result, out)
        os.replace(temporary, DESTINATION)
    # Preserve this explicitly owned schema until its owner-run cleanup after browser testing.
    environment.close()
    print("Owned actual-Qwen browser fixture prepared; credentials not emitted.")


def cleanup():
    data = json.loads(DESTINATION.read_text())
    assert data["kind"] == "owned-stage9-synthetic-browser-fixture-v1"
    assert re.fullmatch(r"auth_test_[a-f0-9]{32}", data["schema"])
    assert re.fullmatch(r"stage9-ai-browser-[a-f0-9]{32}", data["import_queue_name"])
    assert data["auth_rate_prefix"] == data["schema"] + ":"
    from app.common.config import Settings

    settings = Settings()
    engine = make_engine(settings)
    try:
        with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
            for name in [
                data["import_queue_name"],
                data["import_queue_name"] + ":ai:embedding",
                data["import_queue_name"] + ":ai:llm",
            ]:
                queue = Queue(name, connection=redis)
                ids = [
                    *queue.get_job_ids(),
                    *queue.finished_job_registry.get_job_ids(),
                    *queue.failed_job_registry.get_job_ids(),
                ]
                for job in Job.fetch_many(list(set(ids)), connection=redis):
                    if job is not None:
                        job.delete()
                queue.delete(delete_jobs=True)
            for pattern in [data["import_queue_name"] + ":ai:*", data["auth_rate_prefix"] + "*"]:
                keys = list(redis.scan_iter(match=pattern))
                if keys:
                    redis.delete(*keys)
        with engine.begin() as connection:
            connection.execute(DropSchema(data["schema"], cascade=True))
        DESTINATION.unlink()
    finally:
        engine.dispose()
    print("Only the recorded owned browser fixture schema/queues were removed.")


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["prepare"]:
        prepare()
    elif sys.argv[1:] == ["cleanup"]:
        cleanup()
    else:
        raise SystemExit("Use prepare or cleanup")
