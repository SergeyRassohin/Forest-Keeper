"""Contract/security tests only; real inference has a separate explicit acceptance profile."""

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai import baseline
from app.ai.artifacts import verify_component
from app.ai.contracts import (
    AIError,
    Clause,
    EmbeddingRequest,
    Explanation,
    Facts,
    embedding_text,
    semantic_context,
    validate_explanation,
)
from app.ai.runtime import create_runtime, model_info
from app.ai.transport import request_local, vectors_from_response

KEY = b"unit-service-capability-not-a-real-customer-secret"


def features():
    return {
        "domain": "materials",
        "entity_type": "material",
        "subject": "стальной болт",
        "attribute_code": "MASS",
        "conflict_type": "VALUE_MISMATCH",
        "value_kind": "quantity",
        "unit": "kg",
        "observations": [
            {
                "value": "12.4",
                "presence": "PRESENT",
                "quality": "VALID",
                "source_type": "FILE",
                "source_role": "NOT_DEFINED",
            }
        ],
        "reason": "private human rationale",
        "actor_name": "private actor name",
        "raw_payload": "private original record",
        "selected_value_id": str(uuid4()),
    }


def facts():
    return Facts(
        conflict_id=uuid4(),
        context_fingerprint="a" * 64,
        status="RECOMMENDED",
        reason_code="UNANIMOUS_INDEPENDENT_PRECEDENTS",
        action="SELECT_VALUE",
        supporting_decision_ids=[uuid4() for _ in range(5)],
        contradictory_decision_ids=[],
        source_ids=[uuid4(), uuid4()],
        value_ids=[uuid4(), uuid4()],
        independent_groups=5,
    )


def grounded(value):
    return Explanation(
        **{
            key: getattr(value, key)
            for key in ("conflict_id", "context_fingerprint", "status", "action", "reason_code")
        },
        clauses=[
            Clause(code="CURRENT_CONTEXT", decision_ids=[]),
            Clause(code="SUPPORT", decision_ids=value.supporting_decision_ids[:1]),
            Clause(code="LIMITATION", decision_ids=[]),
        ],
    )


def vector_response():
    return {
        "vectors": [[1.0, *([0.0] * 1023)]],
        "model": model_info("embedding").model_dump(mode="json"),
    }


def test_exact_manifest_lock_matches_runtime_constants():
    root = Path(__file__).resolve().parents[2]
    raw = (root / "models/artifacts.lock.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == baseline.ARTIFACT_LOCK_SHA256
    lock = json.loads(raw)
    assert lock["llm"]["repository"] == baseline.LLM_MODEL
    assert lock["llm"]["revision"] == baseline.LLM_REVISION
    assert lock["embedding"]["repository"] == baseline.EMBEDDING_MODEL
    assert lock["embedding"]["revision"] == baseline.EMBEDDING_REVISION
    assert len(lock["llm"]["files"]) + len(lock["embedding"]["files"]) == 14
    assert model_info("embedding").dimensions == 1024
    assert model_info("llm").configured_context_tokens == 32768
    assert not model_info("embedding").production_accepted


def test_model_input_minimizes_fields_and_query_has_distinct_versioned_instruction():
    context = semantic_context(features())
    document = embedding_text(context, "document")
    query = embedding_text(context, "query")
    for forbidden in ["private human", "private actor", "private original", "selected_value_id"]:
        assert forbidden not in document and forbidden not in query
    assert "стальной болт" in document
    assert not document.startswith("Instruct:")
    assert query == "Instruct: " + baseline.QUERY_INSTRUCTION + "\nQuery: " + document


@pytest.mark.parametrize("sensitive", ["password=demo", "name@example.com", "Bearer: demo"])
def test_sensitive_input_is_refused(sensitive):
    with pytest.raises(ValidationError):
        semantic_context({**features(), "subject": sensitive})


def test_factual_output_is_non_vacuous_and_no_generated_prose_is_accepted():
    value = facts()
    output = grounded(value)
    assert validate_explanation(output, value) is output
    with pytest.raises(ValidationError):
        Explanation.model_validate({**output.model_dump(), "prose": "trust me instead"})
    with pytest.raises(ValidationError):
        Explanation.model_validate({**output.model_dump(), "clauses": []})
    duplicate = output.model_copy(update={"clauses": [output.clauses[-1]] * 3})
    with pytest.raises(AIError, match="AI_INCOMPLETE_EXPLANATION"):
        validate_explanation(duplicate, value)


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("conflict_id", uuid4()),
        ("context_fingerprint", "b" * 64),
        ("reason_code", "NEW_UNSUPPORTED_REASON"),
        ("status", "ABSTAINED"),
        ("action", None),
    ],
)
def test_model_cannot_change_deterministic_facts(field, replacement):
    value = facts()
    with pytest.raises(AIError, match="AI_FACT_MISMATCH"):
        validate_explanation(grounded(value).model_copy(update={field: replacement}), value)


def test_foreign_citation_and_invented_claim_on_abstention_are_refused():
    value = facts()
    output = grounded(value)
    output = output.model_copy(
        update={
            "clauses": [
                output.clauses[0],
                Clause(code="SUPPORT", decision_ids=[uuid4()]),
                output.clauses[2],
            ]
        }
    )
    with pytest.raises(AIError, match="AI_INVALID_CITATION"):
        validate_explanation(output, value)
    value = value.model_copy(update={"status": "ABSTAINED", "action": None})
    with pytest.raises(AIError):
        validate_explanation(grounded(value), value)


@pytest.mark.parametrize("vector", [[0.0] * 1024, [float("nan")] * 1024, [1.0] * 1023])
def test_invalid_embeddings_are_refused(vector):
    raw = vector_response()
    raw["vectors"] = [vector]
    with pytest.raises(AIError, match="AI_INVALID_EMBEDDING"):
        vectors_from_response(raw, 1)


@pytest.mark.parametrize(
    "field,value",
    [("model_id", "some-other-model"), ("revision", "b" * 40), ("dimensions", 512)],
)
def test_wrong_model_identity_never_becomes_qwen_vector(field, value):
    raw = vector_response()
    raw["model"][field] = value
    with pytest.raises(AIError):
        vectors_from_response(raw, 1)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://api.openai.com",
        "http://example.com:8091",
        "http://169.254.169.254:8091",
        "http://127.0.0.1:5432",
        "http://user:pass@127.0.0.1:19001",
        "http://127.0.0.1:19001/path",
        "http://127.0.0.1:19001?redirect=external",
    ],
)
def test_transport_rejects_external_metadata_and_override_urls_before_network(
    endpoint, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("A forbidden address reached the HTTP client")

    monkeypatch.setattr("app.ai.transport.http.client.HTTPConnection", forbidden)
    with pytest.raises(AIError, match="AI_TRANSPORT_CONFIGURATION_INVALID"):
        request_local(endpoint, KEY, "/internal/ai/model-info")


class ContractOnlyEngine:
    """Explicit unit fake, never used by real-model acceptance/deployment."""

    def __init__(self):
        self.info = model_info("embedding")
        self.calls = 0
        self.fail = False

    def embed(self, request: EmbeddingRequest) -> list[list[float]]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("private provider request must not escape")
        return [[1.0, *([0.0] * 1023)] for _ in request.contexts]

    def explain(self, value: Facts) -> Explanation:
        return grounded(value)

    def ready(self) -> bool:
        return not self.fail


def test_private_runtime_admission_body_limit_errors_and_real_info_contract():
    engine = ContractOnlyEngine()
    with TestClient(create_runtime(engine, KEY)) as client:
        assert client.get("/internal/ai/model-info").status_code == 403
        client.headers["X-FK-AI-Key"] = KEY.decode()
        assert (
            client.get("/internal/ai/model-info").json()["revision"] == baseline.EMBEDDING_REVISION
        )
        response = client.post("/internal/ai/embed", content=b"private" * 5000)
        assert response.status_code == 413 and "private" not in response.text
        response = client.post("/internal/ai/embed", json={"private": "provider secret"})
        assert response.status_code == 422 and "secret" not in response.text
        assert engine.calls == 0
        payload = {"purpose": "query", "contexts": [semantic_context(features()).model_dump()]}
        response = client.post("/internal/ai/embed", json=payload)
        assert response.status_code == 200
        assert len(vectors_from_response(response.json(), 1)[0]) == 1024
        engine.fail = True
        response = client.post("/internal/ai/embed", json=payload)
        assert response.status_code == 503 and "private" not in response.text
        assert client.get("/internal/ai/health").status_code == 503


def test_artifact_lock_and_actual_byte_tampering_fail_closed(tmp_path, monkeypatch):
    root = tmp_path / "models"
    (root / "embedding").mkdir(parents=True)
    artifact = root / "embedding/model.safetensors"
    artifact.write_bytes(b"owned verification fixture")
    entry = {
        "path": "model.safetensors",
        "size": artifact.stat().st_size,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    }
    lock = tmp_path / "lock.json"
    lock.write_text(
        json.dumps(
            {
                "embedding": {
                    "repository": baseline.EMBEDDING_MODEL,
                    "revision": baseline.EMBEDDING_REVISION,
                    "files": [entry],
                }
            }
        )
    )
    with pytest.raises(AIError, match="AI_ARTIFACT_LOCK_MISMATCH"):
        verify_component(root, lock, "embedding")
    monkeypatch.setattr(
        baseline, "ARTIFACT_LOCK_SHA256", hashlib.sha256(lock.read_bytes()).hexdigest()
    )
    verify_component(root, lock, "embedding")
    extra = root / "embedding/adapter_config.json"
    extra.write_text('{"base_model_name_or_path":"unapproved"}')
    with pytest.raises(AIError, match="AI_ARTIFACT_UNEXPECTED_FILE"):
        verify_component(root, lock, "embedding")
    extra.unlink()
    artifact.write_bytes(b"tampered verification file")
    with pytest.raises(AIError, match="AI_ARTIFACT_MISMATCH"):
        verify_component(root, lock, "embedding")


def test_native_model_identity_is_rechecked_before_generation(monkeypatch):
    from app.ai.runtime import LlamaEngine

    engine = LlamaEngine.__new__(LlamaEngine)
    engine.root = Path("/tmp/not-used-for-model-load")
    engine.info = model_info("llm")
    monkeypatch.setattr("app.ai.runtime.llama_identity", lambda root: False)

    def forbidden(*args, **kwargs):
        pytest.fail("Inference ran after the pinned native model was replaced")

    monkeypatch.setattr("app.ai.runtime.native_request", forbidden)
    with pytest.raises(AIError, match="AI_MODEL_IDENTITY_MISMATCH"):
        engine.explain(facts())


def test_model_timeout_closes_admission_marks_supervisor_fault_and_keeps_output_unavailable(
    tmp_path,
):
    import time

    class Slow(ContractOnlyEngine):
        def embed(self, request):
            self.calls += 1
            time.sleep(0.2)
            return [[1.0, *([0.0] * 1023)]]

    engine = Slow()
    marker = tmp_path / "model-fault"
    with TestClient(create_runtime(engine, KEY, fault_file=marker, timeout_seconds=0.01)) as client:
        client.headers["X-FK-AI-Key"] = KEY.decode()
        body = {"purpose": "query", "contexts": [semantic_context(features()).model_dump()]}
        assert client.post("/internal/ai/embed", json=body).json()["reason_code"] == "AI_TIMEOUT"
        assert marker.exists()
        assert client.get("/internal/ai/health").status_code == 503
        assert client.get("/internal/ai/model-info").status_code == 503
        assert client.post("/internal/ai/embed", json=body).status_code == 503
        assert engine.calls == 1


def test_authenticated_slow_bodies_have_bounded_admission_and_cancel_releases_it():
    import asyncio

    from app.ai.runtime import PrivateBoundary

    async def scenario():
        started = 0
        sent = []

        async def downstream(scope, receive, send):
            sent.append({"type": "downstream"})

        async def slow():
            nonlocal started
            started += 1
            await asyncio.Event().wait()

        async def output(message):
            sent.append(message)

        boundary = PrivateBoundary(downstream, KEY)
        scope = {"type": "http", "headers": [(b"x-fk-ai-key", KEY)]}
        tasks = [asyncio.create_task(boundary(scope, slow, output)) for _ in range(8)]
        while started < 8:
            await asyncio.sleep(0)
        await boundary(scope, slow, output)
        assert any(item.get("status") == 429 for item in sent)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        async def valid():
            return {"type": "http.request", "body": b"", "more_body": False}

        await boundary(scope, valid, output)
        assert {"type": "downstream"} in sent

    asyncio.run(scenario())
