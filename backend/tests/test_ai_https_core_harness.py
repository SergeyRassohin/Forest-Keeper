"""Malformed successful HTTP responses cannot make the load instrument pass."""

from unittest.mock import MagicMock

import pytest

from tests.benchmark_ai_https_core import observe


@pytest.mark.parametrize("category", ["decision_detail", "review_context", "conflict_detail"])
@pytest.mark.parametrize("payload", [[], ["invalid"], 7, None, "incorrect"])
def test_malformed_http200_details_are_failed_observations(category, payload):
    client = MagicMock()
    client.get.return_value.status_code = 200
    client.get.return_value.json.return_value = payload
    row = observe(client, category, "/owned", "case", "decision", {"history"}, {"case"})
    assert row["valid"] is False
    assert row["status_code"] == 200
    assert row["seconds"] >= 0


@pytest.mark.parametrize("transport", [False, True])
def test_transport_and_non_json_failures_are_retained_without_private_text(transport):
    client = MagicMock()
    if transport:
        client.get.side_effect = ConnectionError("Private credential-bearing diagnostics")
    else:
        client.get.return_value.status_code = 200
        client.get.return_value.json.side_effect = ValueError("Untrusted response body")
    row = observe(client, "decision_detail", "/owned", "case", "decision", set(), set())
    assert row["valid"] is False
    assert row["error_code"] in {"ConnectionError", "ValueError"}
    assert "Private credential" not in str(row) and "Untrusted response" not in str(row)


@pytest.mark.parametrize("category", ["conflict_list", "registry_list"])
def test_wrong_scope_or_dataset_list_is_not_a_success(category):
    client = MagicMock()
    client.get.return_value.status_code = 200
    client.get.return_value.json.return_value = [{"id": "outside", "conflict_id": "outside"}] * 50
    row = observe(client, category, "/owned", "case", "decision", {"history"}, {"case"})
    assert row["valid"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "INDEXING"),
        ("state", "UNAVAILABLE"),
        ("retrieval_version", "wrong-space"),
        ("embedding_model", {"provider": "test"}),
        ("total_candidates_before_filter", 1),
        ("total_after_filter", 1),
    ],
)
def test_retrieval_wrong_provider_version_or_pool_cannot_pass(field, value):
    from app.similarity.service import configuration

    payload = {
        "state": "READY",
        "retrieval_version": "owned-qwen-version",
        "embedding_model": configuration("qwen-demo-v1"),
        "total_candidates_before_filter": 10000,
        "total_after_filter": 10000,
    }
    payload[field] = value
    client = MagicMock()
    client.get.return_value.status_code = 200
    client.get.return_value.json.return_value = payload
    row = observe(
        client,
        "similar_decisions",
        "/owned",
        "case",
        "decision",
        set(),
        set(),
        "owned-qwen-version",
        10000,
    )
    assert row["valid"] is False


def test_full_pool_recommendation_does_not_count_unavailable_or_positive_as_success():
    client = MagicMock()
    client.get.return_value.status_code = 200
    for payload in [
        {"status": "UNAVAILABLE"},
        {"status": "RECOMMENDED"},
        {"status": "ABSTAINED", "reason_code": "WRONG_REASON"},
    ]:
        client.get.return_value.json.return_value = payload
        row = observe(client, "recommendation", "/owned", "case", "decision", set(), set())
        assert row["valid"] is False
