"""Failed load observations must not inherit PASS or disappear from the report.

These are simulated HTTP failures of the measuring tool, not actual-model acceptance.
"""

import json
from threading import Lock
from unittest.mock import MagicMock

import pytest

from app.common.config import Settings
from app.similarity.service import configuration
from tests import benchmark_ai_capacity as bench


@pytest.mark.parametrize(
    ("fault", "during_warmup"),
    [
        ("transport", True),
        ("json", True),
        ("transport", False),
        ("json", False),
        ("http", False),
        ("version", False),
        ("count", False),
        ("list_type", False),
        ("list_foreign", False),
        ("list_duplicate", False),
        ("registry_type", False),
        ("registry_foreign", False),
        ("registry_duplicate", False),
        ("list_unhashable", False),
        ("registry_unhashable", False),
        ("retrieval_unhashable", False),
        ("recommendation", False),
        ("none", False),
        ("below", False),
    ],
)
def test_failures_are_preserved_and_clear_older_pass(tmp_path, monkeypatch, fault, during_warmup):
    report = tmp_path / "capacity.json"
    report.write_text(json.dumps({"passed": True, "measurements": [{"old": True}]}))
    value = {
        "phase": "INDEXED",
        "target": 20,
        "version_id": "owned-version",
        "tokens": ["synthetic-test-token-" + str(i) for i in range(10)],
        "queries": ["owned-query-" + str(i) for i in range(20)],
        "history": ["owned-history-" + str(i) for i in range(20)],
    }
    monkeypatch.setattr(bench, "REPORT", report)
    settings = Settings(
        database_url="postgresql+psycopg://localhost/owned", redis_url="redis://localhost/15"
    )
    monkeypatch.setattr(bench, "load", lambda: (value, settings))
    monkeypatch.setattr(bench, "make_engine", lambda _: MagicMock())
    monkeypatch.setattr(bench, "Session", MagicMock())
    monkeypatch.setattr(bench, "create_app", lambda **_: object())
    monkeypatch.setattr(bench, "Redis", MagicMock())
    monkeypatch.setattr(bench, "Queue", MagicMock())
    monkeypatch.setattr("tests.test_recommendations_integration.business_hash", lambda _: "stable")

    class Client:
        def __init__(self, *args, **kwargs):
            self.cookies = MagicMock()
            self.calls, self.injected = 0, False
            self.lock = Lock()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, endpoint, **kwargs):
            with self.lock:
                self.calls += 1
                inject = (
                    not self.injected
                    and (
                        endpoint.endswith("similar-decisions")
                        if not fault.startswith(("list_", "registry_"))
                        and fault != "recommendation"
                        else endpoint.startswith("/api/v1/conflicts?")
                        if fault.startswith("list_")
                        else endpoint.startswith("/api/v1/decisions?")
                        if fault.startswith("registry_")
                        else endpoint.endswith("recommendation")
                    )
                    and (
                        (during_warmup and self.calls == 1)
                        or (not during_warmup and self.calls > 20)
                    )
                )
                self.injected = self.injected or inject
            if inject and fault == "transport":
                raise ConnectionError("Private transport details must never enter the report")
            payload = (
                [{"id": identifier} for identifier in value["history"] + value["queries"]]
                if endpoint.startswith("/api/v1/conflicts?")
                else [
                    {"id": "decision-" + str(i), "conflict_id": identifier}
                    for i, identifier in enumerate(value["history"])
                ]
            )
            if endpoint.endswith("similar-decisions"):
                payload = {
                    "state": "READY",
                    "retrieval_version": value["version_id"],
                    "embedding_model": configuration("qwen-demo-v1"),
                    "total_candidates_before_filter": 20,
                    "total_after_filter": 20,
                    "reason_code": "MATCHES",
                    "total_above_threshold": 20,
                    "results": [
                        {"decision_id": "decision-" + str(i), "conflict_id": value["history"][i]}
                        for i in range(5)
                    ],
                }
                if fault == "below":
                    payload.update(
                        state="NO_PRECEDENT",
                        reason_code="BELOW_THRESHOLD",
                        total_above_threshold=0,
                        results=[],
                    )
                if inject and fault == "version":
                    payload["retrieval_version"] = "wrong-space"
                if inject and fault == "count":
                    payload["total_after_filter"] = 1
                if inject and fault == "retrieval_unhashable":
                    payload["results"][0]["conflict_id"] = []
            elif endpoint.endswith("recommendation"):
                payload = {
                    "status": "ABSTAINED",
                    "reason_code": "BELOW_THRESHOLD"
                    if fault == "below"
                    else "INSUFFICIENT_INDEPENDENT_EVIDENCE",
                }
                if inject and fault == "recommendation":
                    payload["reason_code"] = "WRONG_REASON"
            if inject and fault in {"list_type", "registry_type"}:
                payload = {}
            if inject and fault in {"list_foreign", "registry_foreign"}:
                payload[0] = {"id": "foreign"}
            if inject and fault in {"list_duplicate", "registry_duplicate"}:
                payload[0] = payload[1]
            if inject and fault in {"list_unhashable", "registry_unhashable"}:
                payload[0]["id" if fault.startswith("list_") else "conflict_id"] = []
            response = MagicMock(status_code=403 if inject and fault == "http" else 200)
            if inject and fault == "json":
                response.json.side_effect = ValueError("Untrusted response body")
            else:
                response.json.return_value = payload
            return response

    monkeypatch.setattr(bench, "TestClient", Client)
    if fault in {"none", "below"}:
        bench.measure()
        assert json.loads(report.read_text())["passed"] is True
        return
    with pytest.raises(AssertionError, match="NFR failed"):
        bench.measure()
    outcome = json.loads(report.read_text())
    assert outcome["passed"] is False
    assert "Private transport" not in report.read_text()
    assert "Untrusted response" not in report.read_text()
    if during_warmup:
        assert outcome["requests"] == 0 and outcome["warmup_failures"] == 1
    else:
        assert outcome["requests"] == 400 and outcome["invalid_responses"] == 1
        assert len(outcome["measurements"]) == 400
    history = list(tmp_path.glob("measurement-history-*.json"))
    assert len(history) == 1 and json.loads(history[0].read_text())["passed"] is True
