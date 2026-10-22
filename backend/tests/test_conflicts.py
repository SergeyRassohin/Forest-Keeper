from copy import deepcopy
from uuid import uuid4

import pytest

from app.conflicts.engine import CONFIG, CONFIG_HASH, basis, compare, conflict_id, presence
from app.conflicts.models import ConflictStatus, ConflictType, Severity


def observation(value="12.5", kind="quantity", unit="kg", quality="VALID", state="present"):
    return {
        "normalized_value": value,
        "kind": kind,
        "unit": unit,
        "quality_status": quality,
        "normalization_rule": {"presence": state},
    }


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ("12.5", "12.4", ("VALUE_MISMATCH", "NORMALIZED_VALUES_DIFFER")),
        ("12.500", "12.5", None),
        ("0", "-0", None),
        ("12.5", "12.500001", ("VALUE_MISMATCH", "NORMALIZED_VALUES_DIFFER")),
        ("NaN", "12.5", None),
        ("Infinity", "12.5", None),
    ],
)
def test_typed_decimal_comparison(left, right, expected):
    assert compare(observation(left), observation(right)) == expected


@pytest.mark.parametrize("missing", ["missing", "null", "empty"])
def test_explicit_absence_has_distinct_evidence(missing):
    a, b = observation(), observation(None, quality="UNKNOWN", state=missing)
    assert compare(a, b) == ("MISSING", "SOURCE_VALUE_ABSENT")
    assert basis("SOURCE_VALUE_ABSENT", [a, b])["presence"] == ["PRESENT", missing.upper()]
    assert compare(b, a) == compare(a, b)


@pytest.mark.parametrize("state", ["INVALID", "UNKNOWN", "WARNING"])
def test_unknown_invalid_or_float_warning_never_becomes_missing_or_mismatch(state):
    assert compare(observation(), observation("garbage", quality=state)) is None
    assert presence(observation(quality=state)) == "INVALID_OR_UNKNOWN"


def test_unmapped_and_incompatible_units_or_types_do_not_imply_conflict():
    a = observation()
    assert compare(a, None) is None
    assert presence(None) == "SCHEMA_UNMAPPED"
    assert compare(a, observation("12500", unit="g")) is None
    assert compare(a, observation("12.4", kind="string")) is None
    assert compare(observation(None, state="missing"), observation(None, state="null")) is None


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("БОЛТ", "БОЛТ", None),
        ("<script>alert(1)</script>", "bolt", "VALUE_MISMATCH"),
        ("é", "e\u0301", "VALUE_MISMATCH"),
        ("x" * 4097, "y", None),
    ],
)
def test_string_comparison_uses_normalization_policy_without_guessing(a, b, expected):
    compared = compare(observation(a, "string", None), observation(b, "string", None))
    assert (compared[0] if compared else None) == expected


def test_config_identity_no_truth_and_disabled_generation():
    candidate = uuid4()
    original = observation()
    saved = deepcopy(original)
    result = basis("NORMALIZED_VALUES_DIFFER", [original, original])
    assert original == saved
    assert result["authority"] == "NOT_DEFINED"
    assert result["human_decision"] == "NOT_TAKEN"
    assert result["config_hash"] == CONFIG_HASH
    assert CONFIG["disabled_types"] == ["RULE_VIOLATION", "ANOMALY"]
    assert CONFIG["severity"] == "LOW"
    assert conflict_id(candidate, "mass", "VALUE_MISMATCH") == conflict_id(
        candidate, "mass", "VALUE_MISMATCH"
    )
    assert conflict_id(candidate, "mass", "VALUE_MISMATCH") != conflict_id(
        candidate, "price", "VALUE_MISMATCH"
    )
    assert set(ConflictType) == {
        "VALUE_MISMATCH",
        "MISSING",
        "DUPLICATE",
        "RULE_VIOLATION",
        "ANOMALY",
    }
    assert set(ConflictStatus) == {"OPEN", "IN_REVIEW", "RESOLVED", "INSUFFICIENT_DATA"}
    assert set(Severity) == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_missing_source_schema_is_not_an_empty_cell():
    missing = observation(None, quality="UNKNOWN", state="missing")
    missing["source_schema_contains_field"] = False
    assert presence(missing) == "SCHEMA_UNMAPPED"
    assert compare(observation(), missing) is None
