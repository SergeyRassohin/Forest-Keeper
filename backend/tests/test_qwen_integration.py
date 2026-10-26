"""Opt-in ACTUAL pinned Qwen vectors with real independent import/Decision histories."""

import os
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue, SimpleWorker
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.common.database import make_engine
from app.main import create_app
from app.similarity.jobs import recover_indexes
from app.similarity.models import DecisionEmbedding, IndexRun
from app.similarity.provider import QwenProvider, inference_queue
from app.similarity.service import start_run
from tests.recommendation_fixtures import Cases
from tests.test_auth import password as password
from tests.test_auth import role_tokens as role_tokens
from tests.test_matching_integration import auth_env as auth_env

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FK_TEST_INTEGRATION") != "1" or os.getenv("FK_AI_TEST_REAL") != "1",
        reason="Actual verified local Qwen service is an explicit separate acceptance profile",
    ),
]


def test_real_qwen_backfill_query_and_scoped_lookup_preserve_manual_history(auth_env, role_tokens):
    from pathlib import Path

    settings = auth_env.model_copy(
        update={
            "deployment_mode": "test",
            "similarity_provider": "qwen-demo",
            "similarity_allow_qwen_demo": True,
            "ai_embedding_endpoint": os.environ["FK_AI_TEST_EMBEDDING_ENDPOINT"],
            "ai_service_key_file": Path(os.environ["FK_AI_TEST_KEY_FILE"]),
        }
    )
    engine = make_engine(settings)
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    queue = Queue(inference_queue(settings), connection=redis)
    try:
        with TestClient(create_app(settings=settings), base_url="https://localhost:8443") as client:
            client.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
            cases = Cases(client)
            precedent = cases.confirm(cases.case())
            current = cases.case()
            original = client.get("/api/v1/decisions/" + precedent["decision_id"]).json()
            with Session(engine) as session:
                run = start_run(session, settings, "qwen-demo-v1", activate=True, batch_size=8)
                session.commit()
                run_id = run.id
                version_id = run.version_id
            original_embed = QwenProvider.embed_many
            observed_batches = []

            def observed(provider, features, *, purpose="document"):
                assert engine.pool.checkedout() == 0
                from app.similarity.jobs import lock_key

                with Session(engine) as probe:
                    schema = probe.scalar(text("SELECT current_schema()"))
                    assert probe.scalar(
                        text("SELECT pg_try_advisory_xact_lock(:key)"),
                        {
                            "key": lock_key(version_id, schema),
                        },
                    )
                observed_batches.append(len(features))
                return original_embed(provider, features, purpose=purpose)

            for _ in range(2):
                recover_indexes(settings, redis)
                with (
                    patch("app.similarity.jobs.Settings", return_value=settings),
                    patch("app.ai.indexing.make_engine", return_value=engine),
                    patch.object(QwenProvider, "embed_many", new=observed),
                ):
                    SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
            assert observed_batches == [1]
            with Session(engine) as session:
                assert session.get(IndexRun, run_id).status == "COMPLETED"
                vector = session.scalar(select(DecisionEmbedding))
                assert vector is not None and len(vector.embedding) == 1024
                assert vector.decision_id == UUID(precedent["decision_id"])
            url = f"/api/v1/conflicts/{current}/similar-decisions"
            import_queue = Queue(settings.import_queue_name, connection=redis)
            before = import_queue.count
            pending = client.get(url)
            assert pending.status_code == 200 and pending.json()["state"] == "INDEXING"
            assert import_queue.count == before and queue.count == 1
            with patch("app.similarity.jobs.Settings", return_value=settings):
                SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
            with patch.object(
                QwenProvider, "embed", side_effect=AssertionError("Inference in GET")
            ):
                response = client.get(url)
            assert response.status_code == 200
            result = response.json()
            assert result["state"] == "READY", result
            assert result["embedding_model"]["provider"] == "qwen-local-demo"
            assert precedent["decision_id"] in [item["decision_id"] for item in result["results"]]
            assert client.get("/api/v1/decisions/" + precedent["decision_id"]).json() == original
    finally:
        for identifier in [
            *queue.get_job_ids(),
            *queue.finished_job_registry.get_job_ids(),
            *queue.failed_job_registry.get_job_ids(),
        ]:
            from rq.job import Job

            job = Job.fetch_many([identifier], connection=redis)[0]
            if job is not None:
                job.delete()
        queue.delete(delete_jobs=True)
        redis.close()
        engine.dispose()
