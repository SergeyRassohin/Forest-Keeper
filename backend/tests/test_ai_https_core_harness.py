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
