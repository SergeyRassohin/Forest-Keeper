"""Opt-in genuine Registry history → actual isolated Qwen vectors and local LLM.

Only Settings injection is patched for the isolated schema. Neither model/provider/output
is mocked. This legally synthetic development vertical is not human-gold evaluation.
"""

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue, SimpleWorker
from rq.job import Job
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.admission import prefix
from app.auth.dependencies import COOKIE_NAME
from app.decisions.models import Decision
from app.main import create_app
from app.similarity.jobs import recover_indexes
from app.similarity.models import DecisionEmbedding, IndexRun
from app.similarity.provider import inference_queue
from app.similarity.service import start_run
from tests.recommendation_fixtures import Cases
from tests.test_auth import ORIGIN
from tests.test_auth import password as password
from tests.test_auth import role_tokens as role_tokens
from tests.test_decisions_integration import begin, save, selection
from tests.test_matching_integration import auth_env as auth_env
from tests.test_recommendations_integration import business_hash

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FK_TEST_INTEGRATION") != "1" or os.getenv("FK_AI_TEST_REAL") != "1",
        reason="Separate actual isolated Qwen acceptance opt-in",
    ),
]


def drain(queue, settings, settings_path):
    with patch(settings_path, return_value=settings):
        SimpleWorker([queue], connection=queue.connection).work(burst=True, logging_level="ERROR")


def test_real_imports_precedents_qwen_retrieval_and_grounded_llm_leave_decision_to_human(
    auth_env, role_tokens
):
    settings = auth_env.model_copy(
        update={
            "deployment_mode": "test",
            "similarity_provider": "qwen-demo",
            "similarity_allow_qwen_demo": True,
            "recommendation_enabled": True,
            "ai_enabled": True,
            "ai_embedding_endpoint": os.environ["FK_AI_TEST_EMBEDDING_ENDPOINT"],
            "ai_llm_endpoint": os.environ["FK_AI_TEST_LLM_ENDPOINT"],
            "ai_service_key_file": Path(os.environ["FK_AI_TEST_KEY_FILE"]),
        }
    )
    report = {"kind": "legally-synthetic-development-vertical-not-gold", "passed": False}
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    embedding_queue = Queue(inference_queue(settings), connection=redis)
    llm_queue = Queue(prefix(settings) + ":llm", connection=redis)
    started = time.monotonic()
    try:
        with TestClient(create_app(settings=settings), base_url="https://localhost:8443") as client:
            client.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
            cases = Cases(client)
            for _ in range(5):
                cases.confirm(cases.case())
            current = cases.case()
            review = begin(client, current)
            with Session(client.app.state.engine) as session:
                run = start_run(session, settings, "qwen-demo-v1", activate=True, batch_size=8)
                session.commit()
                run_id, version_id = run.id, run.version_id
            phase = time.monotonic()
            # One bounded batch yields after its checkpoint; the next recovery pass
            # verifies coverage and completes/activates without repeating inference.
            for _ in range(2):
                recover_indexes(settings, redis)
                drain(embedding_queue, settings, "app.similarity.jobs.Settings")
            with Session(client.app.state.engine) as session:
                assert session.get(IndexRun, run_id).status == "COMPLETED"
                assert session.scalar(select(func.count()).select_from(DecisionEmbedding)) == 5
            report["backfill_seconds"] = round(time.monotonic() - phase, 4)
            path = f"/api/v1/conflicts/{current}"
            pending = client.get(path + "/similar-decisions")
            assert pending.status_code == 200 and pending.json()["state"] == "INDEXING"
            drain(embedding_queue, settings, "app.similarity.jobs.Settings")
            retrieval = client.get(path + "/similar-decisions").json()
            assert retrieval["state"] == "READY" and len(retrieval["results"]) == 5, retrieval
            assert retrieval["embedding_model"]["provider"] == "qwen-local-demo"
            recommendation = client.get(path + "/recommendation").json()
            assert recommendation["status"] == "RECOMMENDED", recommendation
            with Session(client.app.state.engine) as session:
                before = business_hash(session)
                count = session.scalar(select(func.count()).select_from(Decision))
            request = client.post(
                path + "/ai-explanation",
                headers=ORIGIN,
                json={"request_id": str(uuid4()), "language": "ru"},
            )
            assert request.status_code == 202, request.text
            handle = request.json()["request_id"]
            phase = time.monotonic()
            report["llm_started_at"] = datetime.now(UTC).isoformat()
            if folder := os.getenv("FK_AI_REAL_REPORT_DIR"):
                destination = Path(folder)
                destination.mkdir(parents=True, exist_ok=True)
                (destination / "llm-phase.json").write_text(
                    json.dumps(
                        {
                            "kind": "owned-actual-qwen-vertical-phase-not-quality",
                            "llm_started_at": report["llm_started_at"],
                        }
                    )
                    + "\n"
                )
            drain(llm_queue, settings, "app.ai.explanations.Settings")
            report["llm_finished_at"] = datetime.now(UTC).isoformat()
            if folder:
                (Path(folder) / "llm-phase.json").write_text(
                    json.dumps(
                        {
                            "kind": "owned-actual-qwen-vertical-phase-not-quality",
                            "llm_started_at": report["llm_started_at"],
                            "llm_finished_at": report["llm_finished_at"],
                        }
                    )
                    + "\n"
                )
            response = client.get(path + "/ai-explanations/" + handle)
            assert response.status_code == 200, response.text
            explanation = response.json()
            report["llm_job_seconds"] = round(time.monotonic() - phase, 4)
            report["explanation_state"] = explanation["state"]
            assert explanation["state"] == "COMPLETED", explanation
            assert explanation["model"]["production_accepted"] is False
            cited = {value for item in explanation["clauses"] for value in item["decision_ids"]}
            expected = {item["decision_id"] for item in cases.decisions}
            assert len(cited) == 1 and cited <= expected
            assert any(
                "12.5" in row["text"] and "12.4" in row["text"] for row in explanation["clauses"]
            )
            for identifier in cited:
                assert client.get("/api/v1/decisions/" + identifier).status_code == 200
            with Session(client.app.state.engine) as session:
                assert business_hash(session) == before
                assert session.scalar(select(func.count()).select_from(Decision)) == count
            # Explicit separate human confirmation; model text never supplies the write payload.
            chosen = next(
                i
                for i, v in enumerate(review["selectable_values"])
                if v["source_id"] == cases.sources[0]["source_id"]
            )
            saved = save(client, current, selection(review, chosen))
            assert UUID(saved["decision_id"])
            report.update(
                {
                    "passed": True,
                    "precedents": 5,
                    "actual_vectors": 5,
                    "retrieval_version": str(version_id),
                    "model": explanation["model"],
                    "support_citations_valid": True,
                    "ai_business_writes": 0,
                    "human_confirmation": True,
                    "production_accepted": False,
                }
            )
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - started, 4)
        if folder := os.getenv("FK_AI_REAL_REPORT_DIR"):
            destination = Path(folder)
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "stage9-real-vertical.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            )
        for queue in (embedding_queue, llm_queue):
            identifiers = [
                *queue.get_job_ids(),
                *queue.finished_job_registry.get_job_ids(),
                *queue.failed_job_registry.get_job_ids(),
            ]
            for job in Job.fetch_many(list(set(identifiers)), connection=redis):
                if job is not None:
                    job.delete()
            queue.delete(delete_jobs=True)
        keys = list(redis.scan_iter(match=prefix(settings) + ":*"))
        if keys:
            redis.delete(*keys)
        redis.close()
