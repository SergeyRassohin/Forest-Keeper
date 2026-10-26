"""Real auth/DB/RQ/Redis boundaries with an explicit model stub, never real-AI acceptance."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue, SimpleWorker
from rq.job import Job
from sqlalchemy.orm import Session

from app.ai.admission import prefix
from app.ai.contracts import Clause
from app.ai.explanations import result_key
from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User
from app.auth.security import token_digest
from app.main import create_app
from tests.recommendation_fixtures import Cases
from tests.test_auth import ORIGIN
from tests.test_auth import password as password
from tests.test_local_ai import grounded
from tests.test_recommendations_integration import auth_env as auth_env
from tests.test_recommendations_integration import business_hash
from tests.test_recommendations_integration import role_tokens as role_tokens
from tests.test_similarity_integration import enabled

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("FK_TEST_INTEGRATION") != "1", reason="owned integration opt-in"),
]


@pytest.fixture
def client(auth_env, role_tokens):
    settings = enabled(auth_env).model_copy(
        update={
            "recommendation_enabled": True,
            "ai_enabled": True,
        }
    )
    try:
        with TestClient(create_app(settings=settings), base_url="https://localhost:8443") as value:
            value.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
            yield value
    finally:
        assert settings.import_queue_name.startswith("matching-test-")
        with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
            queue = Queue(prefix(settings) + ":llm", connection=redis)
            ids = [
                *queue.get_job_ids(),
                *queue.finished_job_registry.get_job_ids(),
                *queue.failed_job_registry.get_job_ids(),
            ]
            for job in Job.fetch_many(list(set(ids)), connection=redis):
                if job is not None:
                    job.delete()
            queue.delete(delete_jobs=True)
            keys = list(redis.scan_iter(match=prefix(settings) + ":*"))
            if keys:
                redis.delete(*keys)


@pytest.fixture
def reviewer(client, role_tokens):
    with TestClient(
        create_app(settings=client.app.state.settings), base_url="https://localhost:8443"
    ) as value:
        value.cookies.set(COOKIE_NAME, role_tokens["REVIEWER"])
        yield value


def start(client, case, request_id=None, expected=202):
    response = client.post(
        f"/api/v1/conflicts/{case}/ai-explanation",
        headers=ORIGIN,
        json={"request_id": request_id or str(uuid4()), "language": "ru"},
    )
    assert response.status_code == expected, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def poll(client, case, handle):
    response = client.get(f"/api/v1/conflicts/{case}/ai-explanations/{handle}")
    assert response.status_code == 200, response.text
    return response.json()


def run_stub(client, implementation=grounded):
    settings = client.app.state.settings
    with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
        queue = Queue(prefix(settings) + ":llm", connection=redis)
        with (
            patch("app.ai.explanations.Settings", return_value=settings),
            patch("app.ai.explanations.LocalLLM.explain", side_effect=implementation) as generation,
        ):
            SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
            return generation.call_count


def test_explicit_job_idempotency_factual_projection_and_read_only_poll_preserve_business(client):
    cases = Cases(client)
    case = cases.prepared()
    with Session(client.app.state.engine) as session:
        before = business_hash(session)
    request = str(uuid4())
    first = start(client, case, request)
    assert start(client, case, request) == first
    handle = first["request_id"]
    assert poll(client, case, handle)["state"] == "QUEUED"
    captured = []

    def model_stub(facts):
        captured.append(facts)
        assert len(facts.precedents) == 5 and len(facts.comparison.values) == 2
        assert {v.normalized_value for v in facts.comparison.values} == {"12.4", "12.5"}
        assert "Проверен исходный документ" not in facts.model_dump_json()
        return grounded(facts)

    assert run_stub(client, model_stub) == 1
    result = poll(client, case, handle)
    assert result["state"] == "COMPLETED", result
    assert len(result["clauses"]) == 3
    assert any("12.5" in row["text"] and "12.4" in row["text"] for row in result["clauses"])
    assert result["model"]["production_accepted"] is False
    assert poll(client, case, handle) == result
    with Session(client.app.state.engine) as session:
        assert business_hash(session) == before


def test_foreign_actor_and_wrong_case_handles_are_opaque_and_ai_paths_not_internal(
    client, reviewer
):
    cases = Cases(client)
    case = cases.prepared()
    handle = start(client, case)["request_id"]
    known = reviewer.get(f"/api/v1/conflicts/{case}/ai-explanations/{handle}")
    unknown = reviewer.get(f"/api/v1/conflicts/{case}/ai-explanations/{uuid4()}")
    assert known.status_code == unknown.status_code == 404
    assert known.json() == unknown.json()
    assert client.get("/internal/ai/model-info").status_code == 404
    assert client.post("/internal/ai/explain", json={}).status_code == 404


def test_cancel_before_execution_never_invokes_model_and_cannot_deliver_output(client):
    cases = Cases(client)
    case = cases.prepared()
    handle = start(client, case)["request_id"]
    response = client.post(
        f"/api/v1/conflicts/{case}/ai-explanations/{handle}/cancel", headers=ORIGIN
    )
    assert response.status_code == 200
    assert run_stub(client) == 0
    assert poll(client, case, handle)["reason_code"] == "AI_CANCELLED"


def test_untrusted_model_citations_and_tampered_cache_are_not_delivered(client):
    cases = Cases(client)
    case = cases.prepared()
    handle = start(client, case)["request_id"]
    foreign = uuid4()

    def malicious(facts):
        output = grounded(facts)
        return output.model_copy(
            update={
                "clauses": [
                    output.clauses[0],
                    Clause(code="SUPPORT", decision_ids=[foreign]),
                    output.clauses[2],
                ]
            }
        )

    assert run_stub(client, malicious) == 1
    refused = poll(client, case, handle)
    assert refused["state"] == "FAILED" and str(foreign) not in str(refused)
    second = start(client, case)["request_id"]
    assert run_stub(client) == 1
    settings = client.app.state.settings
    with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
        redis.set(result_key(UUID(second), settings), '{"raw":"private-secret"}', ex=60)
    refused = poll(client, case, second)
    assert refused["state"] == "FAILED" and "private-secret" not in str(refused)


def test_stale_case_after_admission_does_not_call_model_or_return_ready_action(client):
    from tests.test_decisions_integration import begin

    cases = Cases(client)
    case = cases.prepared()
    handle = start(client, case)["request_id"]
    begin(client, case)
    assert run_stub(client) == 0
    assert poll(client, case, handle)["state"] == "FAILED"


def test_public_ai_json_limit_origin_overrides_and_disabled_mode_fail_closed(client):
    case = Cases(client).case()
    path = f"/api/v1/conflicts/{case}/ai-explanation"
    assert client.post(path, headers=ORIGIN, content=b"x" * 4097).status_code == 413
    assert (
        client.post(
            path, headers={"Origin": "https://evil.example"}, json={"request_id": str(uuid4())}
        ).status_code
        == 403
    )
    assert (
        client.post(
            path + "?threshold=0", headers=ORIGIN, json={"request_id": str(uuid4())}
        ).status_code
        == 422
    )
    client.app.state.settings.ai_enabled = False
    assert start(client, case, expected=503)["error"]["code"] == "AI_UNAVAILABLE"


def test_concurrent_request_id_cannot_bind_two_languages(client):
    from app.ai.admission import enqueue_bounded

    case = Cases(client).prepared()
    request = str(uuid4())
    barrier = Barrier(2)

    def concurrent_admission(*args, **kwargs):
        barrier.wait(timeout=5)
        return enqueue_bounded(*args, **kwargs)

    def send(language):
        return client.post(
            f"/api/v1/conflicts/{case}/ai-explanation",
            headers=ORIGIN,
            json={"request_id": request, "language": language},
        )

    with (
        patch("app.ai.routes.enqueue_bounded", side_effect=concurrent_admission),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        futures = [executor.submit(send, language) for language in ("ru", "en")]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(result.status_code for result in results) == [202, 409], [
        result.text for result in results
    ]
    rejected = next(result for result in results if result.status_code == 409)
    assert rejected.json()["error"]["code"] == "AI_REQUEST_ID_REUSED"


def test_scope_revoked_during_model_work_blocks_completion_and_delivery(client, role_tokens):
    case = Cases(client).prepared()
    handle = start(client, case)["request_id"]
    with Session(client.app.state.engine) as session:
        auth = session.get(AuthSession, token_digest(role_tokens["DATA_OWNER"]))
        actor_id = auth.user_id
        old_scope = list(session.get(User, actor_id).data_domains)

    def revoked_while_running(facts):
        with Session(client.app.state.engine) as session:
            session.get(User, actor_id).data_domains = []
            session.commit()
        return grounded(facts)

    try:
        assert run_stub(client, revoked_while_running) == 1
        response = client.get(f"/api/v1/conflicts/{case}/ai-explanations/{handle}")
        assert response.status_code == 404  # Existing scope policy deliberately hides the case.
        assert "clauses" not in response.json()
        unknown = client.get(f"/api/v1/conflicts/{uuid4()}/ai-explanations/{uuid4()}")
        assert response.json() == unknown.json()
    finally:
        with Session(client.app.state.engine) as session:
            session.get(User, actor_id).data_domains = old_scope
            session.commit()
    assert poll(client, case, handle)["state"] == "FAILED"


def test_completed_result_is_invalidated_by_case_head_and_model_identity_changes(
    client, monkeypatch
):
    from tests.test_decisions_integration import begin

    cases = Cases(client)
    case = cases.prepared()
    handle = start(client, case)["request_id"]
    assert run_stub(client) == 1
    assert poll(client, case, handle)["state"] == "COMPLETED"
    with monkeypatch.context() as patcher:
        patcher.setattr("app.ai.baseline.PROMPT_VERSION", "new-unaccepted-prompt")
        result = poll(client, case, handle)
        assert result["reason_code"] == "AI_CONTEXT_STALE" and "clauses" not in result
    begin(client, case)
    result = poll(client, case, handle)
    assert result["state"] == "FAILED" and "clauses" not in result


def test_same_actor_another_session_cannot_poll_or_cancel_an_existing_explanation(client, password):
    case = Cases(client).prepared()
    handle = start(client, case)["request_id"]
    with TestClient(
        create_app(settings=client.app.state.settings), base_url="https://localhost:8443"
    ) as another:
        login = another.post(
            "/api/v1/auth/login",
            headers=ORIGIN,
            json={"login": "data_owner", "password": password},
        )
        assert login.status_code == 200, login.text
        path = f"/api/v1/conflicts/{case}/ai-explanations/{handle}"
        assert another.get(path).status_code == 404
        assert another.post(path + "/cancel", headers=ORIGIN).status_code == 404
    assert run_stub(client) == 1
    assert poll(client, case, handle)["state"] == "COMPLETED"
