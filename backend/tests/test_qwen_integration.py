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
from tests.test_recommendations_integration import auth_env as auth_env
from tests.test_recommendations_integration import role_tokens as role_tokens

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


def test_real_qwen_shadow_checkpoint_new_worker_cutover_and_test_space_rollback(
    auth_env, role_tokens
):
    from pathlib import Path

    from sqlalchemy import func

    from app.ai.admission import prefix
    from app.similarity.jobs import activate_version
    from app.similarity.models import RetrievalState
    from app.similarity.provider import ProviderError
    from tests.test_similarity_integration import enabled, index, similar

    legacy = enabled(auth_env)
    qwen = auth_env.model_copy(
        update={
            "deployment_mode": "test",
            "similarity_provider": "qwen-demo",
            "similarity_allow_qwen_demo": True,
            "ai_embedding_endpoint": os.environ["FK_AI_TEST_EMBEDDING_ENDPOINT"],
            "ai_service_key_file": Path(os.environ["FK_AI_TEST_KEY_FILE"]),
        }
    )
    redis = Redis.from_url(qwen.redis_url.get_secret_value())
    queue = Queue(inference_queue(qwen), connection=redis)
    engine = make_engine(qwen)
    try:
        with TestClient(create_app(settings=legacy), base_url="https://localhost:8443") as client:
            client.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
            cases = Cases(client)
            histories = [cases.confirm(cases.case()) for _ in range(2)]
            current = cases.case()
            original = {
                row["decision_id"]: client.get("/api/v1/decisions/" + row["decision_id"]).json()
                for row in histories
            }
            index(legacy)
            old = similar(client, current)
            assert old["state"] == "READY" and len(old["results"]) == 2
            old_id = UUID(old["retrieval_version"])
            with Session(engine) as session:
                run = start_run(session, qwen, "qwen-demo-v1", activate=False, batch_size=1)
                session.commit()
                run_id, version_id = run.id, run.version_id
            recover_indexes(qwen, redis)
            with patch("app.similarity.jobs.Settings", return_value=qwen):
                SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
            with Session(engine) as session:
                assert session.get(IndexRun, run_id).processed == 1
                assert session.get(RetrievalState, 1).active_version_id == old_id
                with pytest.raises(ProviderError, match="INDEX_NOT_READY"):
                    activate_version(session, version_id)
                session.rollback()
            assert similar(client, current)["retrieval_version"] == str(old_id)
            # The first worker has exited after one durable checkpoint. A new worker
            # resumes from anti-join coverage, without rerunning the old batch.
            for _ in range(2):
                recover_indexes(qwen, redis)
                with patch("app.similarity.jobs.Settings", return_value=qwen):
                    SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
            with Session(engine) as session:
                assert session.get(IndexRun, run_id).status == "COMPLETED"
                assert session.get(IndexRun, run_id).processed == 2
                assert session.get(RetrievalState, 1).active_version_id == old_id
                for identifier in (old_id, version_id):
                    assert (
                        session.scalar(
                            select(func.count())
                            .select_from(DecisionEmbedding)
                            .where(DecisionEmbedding.version_id == identifier)
                        )
                        == 2
                    )
        # API is quiesced before each explicit configuration/active-version switch.
        with Session(engine) as session:
            activate_version(session, version_id)
            session.commit()
        with TestClient(create_app(settings=qwen), base_url="https://localhost:8443") as client:
            client.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
            url = f"/api/v1/conflicts/{current}/similar-decisions"
            assert client.get(url).json()["state"] == "INDEXING"
            with patch("app.similarity.jobs.Settings", return_value=qwen):
                SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
            actual = client.get(url).json()
            assert actual["state"] == "READY" and len(actual["results"]) == 2, actual
            assert actual["retrieval_version"] == str(version_id)
            assert actual["embedding_model"]["provider"] == "qwen-local-demo"
            for identifier, before in original.items():
                assert client.get("/api/v1/decisions/" + identifier).json() == before
        with Session(engine) as session:
            activate_version(session, old_id)
            session.commit()
        with TestClient(create_app(settings=legacy), base_url="https://localhost:8443") as client:
            client.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
            rollback = similar(client, current)
            assert rollback["state"] == "READY" and rollback["retrieval_version"] == str(old_id)
            assert {row["decision_id"] for row in rollback["results"]} == set(original)
    finally:
        from rq.job import Job

        ids = [
            *queue.get_job_ids(),
            *queue.finished_job_registry.get_job_ids(),
            *queue.failed_job_registry.get_job_ids(),
        ]
        for job in Job.fetch_many(list(set(ids)), connection=redis):
            if job is not None:
                job.delete()
        queue.delete(delete_jobs=True)
        keys = list(redis.scan_iter(match=prefix(qwen) + ":*"))
        if keys:
            redis.delete(*keys)
        redis.close()
        engine.dispose()
