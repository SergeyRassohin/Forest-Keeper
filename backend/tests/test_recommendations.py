"""Adversarial golden policy cases; test similarity never becomes probability."""

from datetime import UTC, datetime
from itertools import permutations
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.decisions.schemas import CreateDecision
from app.decisions.service import digest
from app.recommendations.policy import POLICY, POLICY_HASH, Candidate, aggregate
from app.recommendations.schemas import RecommendationResult, SourceMap


def cases(count, role="ACCOUNTING_EXPORT"):
    return [
        Candidate(str(i), frozenset({"file:" + str(i)}), "SELECT_VALUE", role) for i in range(count)
    ]


@pytest.mark.parametrize("count", [0, 1, 4, 5, 20, 21])
def test_minimum_and_complete_window_boundary(count):
    result = aggregate(frozenset({"current"}), cases(count))
    assert (result["reason"] == "UNANIMOUS_INDEPENDENT_PRECEDENTS") is (5 <= count <= 20)
    if count == 21:
        assert result["reason"] == "EVIDENCE_WINDOW_EXCEEDED"


def test_five_correlated_clones_count_once():
    pool = [
        Candidate(str(i), frozenset({"same-file", str(i)}), "SELECT_VALUE", "ACCOUNTING_EXPORT")
        for i in range(5)
    ]
    result = aggregate(frozenset({"current"}), pool)
    assert result["independent_groups"] == 1
    assert result["reason"] == "INSUFFICIENT_INDEPENDENT_EVIDENCE"


def test_current_correlation_is_transitive_and_never_removed_before_graph_construction():
    pool = [
        Candidate("a", frozenset({"current-file", "bridge"}), "SELECT_VALUE", "X"),
        Candidate("b", frozenset({"bridge", "other"}), "SELECT_VALUE", "X"),
        *cases(4, "X"),
    ]
    result = aggregate(frozenset({"current-file"}), pool)
    assert result["independent_groups"] == 4
    assert result["reason"] == "INSUFFICIENT_INDEPENDENT_EVIDENCE"
    assert next(g for g in result["groups"] if "b" in g["decision_ids"])["correlated_with_current"]


@pytest.mark.parametrize("count", [1, 5, 19])
def test_any_contradiction_vetoes_a_majority(count):
    pool = [
        *cases(count),
        Candidate("opposed", frozenset({"other"}), "SELECT_VALUE", "REGISTER_EXPORT"),
    ]
    assert aggregate(frozenset({"current"}), pool)["reason"] == "CONTRADICTORY_PRECEDENTS"


def test_disagreement_inside_a_correlated_group_cannot_disappear_into_one_vote():
    pool = [
        *cases(5),
        Candidate("opposed", frozenset({"file:0"}), "SELECT_VALUE", "REGISTER_EXPORT"),
    ]
    assert aggregate(frozenset({"current"}), pool)["reason"] == "CONTRADICTORY_PRECEDENTS"


@pytest.mark.parametrize("outcome", ["ENTER_VALUE", "INSUFFICIENT_DATA", "DEFERRED"])
def test_manual_value_or_uncertain_outcome_never_becomes_a_source_majority(outcome):
    pool = [*cases(5), Candidate("other", frozenset({"other"}), outcome, None)]
    assert aggregate(frozenset({"current"}), pool)["reason"] == "UNSUPPORTED_HISTORICAL_ACTION"


def test_unknown_source_role_fails_closed():
    assert (
        aggregate(
            frozenset({"current"}),
            [*cases(5), Candidate("?", frozenset({"?"}), "SELECT_VALUE", None)],
        )["reason"]
        == "SOURCE_MAPPING_AMBIGUOUS"
    )


def test_group_partition_and_abstention_are_deterministic_under_ties_and_order_changes():
    pool = [*cases(2), Candidate("other", frozenset({"file:0"}), "SELECT_VALUE", "REGISTER_EXPORT")]
    expected = aggregate(frozenset({"current"}), pool)
    for order in permutations(pool):
        assert aggregate(frozenset({"current"}), list(order)) == expected


@pytest.mark.parametrize("status", ["ABSTAINED", "UNAVAILABLE"])
def test_abstention_schema_forbids_actions_and_numeric_confidence(status):
    values = dict(
        conflict_id=uuid4(),
        status=status,
        reason_code="PROVIDER_UNAVAILABLE",
        reasoning_summary="No evidence",
        recommendation_policy_version=POLICY["version"],
        recommendation_policy_hash=POLICY_HASH,
        context_fingerprint="a" * 64,
        review_context_version="b" * 64,
        generated_at=datetime.now(UTC),
    )
    assert RecommendationResult(**values).confidence is None
    for field, value in [
        ("confidence", 5),
        ("recommended_action", "SELECT_VALUE"),
        ("recommended_source_id", uuid4()),
    ]:
        with pytest.raises(ValidationError):
            RecommendationResult(**values, **{field: value})


def test_policy_is_owner_approved_and_exactly_versioned_not_probability():
    assert POLICY["approval"]["status"] == "APPROVED"
    assert POLICY["minimum_groups"] == 5 and POLICY["agreement"] == 1
    assert POLICY["maximum_disagreement"] == 0 and POLICY["maximum_precedents"] == 20
    assert POLICY["confidence_unit"] == "INDEPENDENT_PROVENANCE_GROUPS"
    assert POLICY_HASH != digest({**POLICY, "minimum_groups": 1})


def test_additive_reference_does_not_change_historical_manual_retry_payload_hash():
    old = dict(
        context_version="a" * 64,
        idempotency_key=str(uuid4()),
        decision_type="DEFERRED",
        reason="Human reason",
        confirmed=True,
        supersedes_decision_id=None,
        selected_source_id=None,
        selected_value_id=None,
        corrected_value=None,
        corrected_unit=None,
    )
    body = CreateDecision(**old)
    assert digest(body.model_dump(mode="json", exclude={"recommendation_reference"})) == digest(old)
    with pytest.raises(ValidationError):
        CreateDecision(**old, accepted=True)


def test_source_declaration_cannot_confuse_two_roles_for_the_same_source():
    source = str(uuid4())
    with pytest.raises(ValidationError):
        SourceMap(
            version="1",
            approved=True,
            approval_reference="Owner declaration",
            domain="domain",
            entity_type="Material",
            attribute_code="mass",
            matching_profile_hashes=["a" * 64],
            sources=[
                {"source_id": source, "source_type": "FILE", "role": "REGISTER_EXPORT"},
                {"source_id": source, "source_type": "ONE_C", "role": "ACCOUNTING_EXPORT"},
            ],
        )
