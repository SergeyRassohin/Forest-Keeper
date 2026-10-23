"""Pure context/provider boundaries; no production semantic-quality claim."""

from copy import deepcopy

import pytest

from app.common.config import Settings
from app.decisions.service import digest
from app.similarity.context import COMPATIBILITY, context, explain
from app.similarity.provider import (
    DIMENSIONS,
    REVISIONS,
    ProviderError,
    TestProvider,
    permitted,
    validate_vector,
)
from app.similarity.service import configuration


def snapshot():
    return {
        "conflict": {
            "attribute_code": "mass",
            "conflict_type": "VALUE_MISMATCH",
            "basis": {},
            "values_snapshot": [
                {
                    "source_id": "source",
                    "presence": "PRESENT",
                    "value": {
                        "kind": "quantity",
                        "unit": "kg",
                        "normalized_value": "12.5",
                        "quality_status": "VALID",
                    },
                }
            ],
        },
        "subject": {"domain": "materials", "entity_type": "Material", "display_name": "Steel Bolt"},
        "matching": {
            "profile_snapshot": {"synthetic": True, "version": "1"},
            "profile_hash": "hash",
        },
        "normalization_origins": [],
    }


def test_context_hash_ignores_transient_identity_order_and_raw_secrets():
    a = snapshot()
    a["conflict"]["id"] = "transient-id"
    a["conflict"]["values_snapshot"][0]["raw_payload"] = "secret"
    b = deepcopy(a)
    b["conflict"]["id"] = "different"
    b["conflict"]["values_snapshot"][0]["raw_payload"] = "other"
    assert context(a) == context(b)
    assert "secret" not in str(context(a))
    assert "SOURCE_TYPE_UNKNOWN" in context(a)["known_unknowns"]


@pytest.mark.parametrize("unit,kind", [("?", "quantity"), (None, "quantity"), ("kg", "UNKNOWN")])
def test_ambiguous_or_unknown_structure_rejected(unit, kind):
    data = snapshot()
    data["conflict"]["values_snapshot"][0]["value"].update(unit=unit, kind=kind)
    with pytest.raises(ProviderError):
        context(data)


@pytest.mark.parametrize(
    "value",
    [[0.0] * 1024, [1.0] * 1023, [float("nan")] * 1024, [float("inf")] * 1024, [1e308] * 1024],
)
def test_malformed_vectors_fail_closed(value):
    with pytest.raises(ProviderError):
        validate_vector(value)


def test_reproducible_pinned_version_and_unrelated_case_below_threshold():
    features = context(snapshot())
    provider = TestProvider(REVISIONS["test-v1"])
    vector = provider.embed(features)
    assert len(vector) == DIMENSIONS
    assert provider.embed(features) == vector
    other = {**features, "subject": "unrelated ceramic pipe"}
    assert (
        sum(a * b for a, b in zip(vector, provider.embed(other), strict=True))
        < configuration()["threshold"]
    )
    assert TestProvider(REVISIONS["test-v2"]).embed(features) != vector
    assert digest(configuration()) != digest(configuration("test-v2"))
    with pytest.raises(ProviderError):
        provider.embed({**features, "synthetic": False})


@pytest.mark.parametrize(
    "mode,allow,expected",
    [
        ("production", True, False),
        ("test", False, False),
        ("development", True, True),
        ("test", True, True),
    ],
)
def test_test_provider_requires_both_environment_and_explicit_optin(mode, allow, expected):
    settings = Settings(
        database_url="postgresql://unused",
        redis_url="redis://unused",
        deployment_mode=mode,
        similarity_provider="test",
        similarity_allow_test_provider=allow,
    )
    assert permitted(settings) is expected


@pytest.mark.parametrize("field", COMPATIBILITY)
def test_explainability_distinguishes_incompatible_fields(field):
    features = context(snapshot())
    matched, mismatched = explain(features, {**features, field: "different"})
    assert field in mismatched and field not in matched


def test_hostile_unicode_is_bounded_and_normalized():
    data = snapshot()
    data["subject"]["display_name"] = "A\u0301 STEEL"
    assert context(data)["subject"] == "á steel"
    data["subject"]["display_name"] = "x" * 257
    with pytest.raises(ProviderError):
        context(data)
