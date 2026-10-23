"""Pure validation of canonical human outcomes against frozen Conflict values."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.common.errors import ApiError
from app.decisions.schemas import CreateDecision
from app.decisions.validation import correction_policy, resolve_value


def body(**changes):
    return CreateDecision.model_validate(
        {
            "context_version": "a" * 64,
            "idempotency_key": str(uuid4()),
            "decision_type": "DEFERRED",
            "reason": "Данных недостаточно для выбора; проверим оригинал.",
            "confirmed": True,
            **changes,
        }
    )


def sides(kind="quantity", unit="kg"):
    return [
        {
            "source_id": str(uuid4()),
            "presence": "PRESENT",
            "value": {
                "value_id": str(uuid4()),
                "kind": kind,
                "unit": unit,
                "quality_status": "VALID",
                "normalized_value": value,
            },
        }
        for value in ["12.5", "12.4"]
    ]


@pytest.mark.parametrize("index", [0, 1])
def test_selects_only_the_frozen_value_and_source(index):
    snapshot = sides()
    side = snapshot[index]
    result = resolve_value(
        body(
            decision_type="SELECT_VALUE",
            selected_source_id=side["source_id"],
            selected_value_id=side["value"]["value_id"],
        ),
        snapshot,
    )
    assert result["selected_value"] == side["value"]["normalized_value"]
    assert str(result["selected_source_id"]) == side["source_id"]
    assert result["unit"] == "kg"
    assert snapshot[index]["value"]["normalized_value"] == result["selected_value"]


@pytest.mark.parametrize(
    "quality,presence,value",
    [
        ("UNKNOWN", "PRESENT", "12.5"),
        ("INVALID", "INVALID_OR_UNKNOWN", "bad"),
        ("VALID", "MISSING", None),
        ("VALID", "PRESENT", None),
    ],
)
def test_unknown_invalid_and_missing_values_are_not_asserted_as_truth(quality, presence, value):
    snapshot = sides()
    side = snapshot[0]
    side["presence"] = presence
    side["value"].update(quality_status=quality, normalized_value=value)
    with pytest.raises(ApiError) as failure:
        resolve_value(
            body(
                decision_type="SELECT_VALUE",
                selected_source_id=side["source_id"],
                selected_value_id=side["value"]["value_id"],
            ),
            snapshot,
        )
    assert failure.value.code == "INVALID_SOURCE_VALUE"


def test_cross_source_and_foreign_value_references_are_rejected():
    snapshot = sides()
    for selected in [snapshot[1]["value"]["value_id"], str(uuid4())]:
        with pytest.raises(ApiError):
            resolve_value(
                body(
                    decision_type="SELECT_VALUE",
                    selected_source_id=snapshot[0]["source_id"],
                    selected_value_id=selected,
                ),
                snapshot,
            )


@pytest.mark.parametrize(
    "kind,unit,raw,expected",
    [
        ("quantity", "kg", "12,500", "12.5"),
        ("decimal", None, "-15.000", "-15"),
        ("date", None, "2024-02-29", "2024-02-29"),
        (
            "string",
            None,
            "  е\u0308лка <script>alert(1)</script>  ",
            "ёлка <script>alert(1)</script>",
        ),
    ],
)
def test_corrected_values_keep_input_and_explicit_canonical_trace(kind, unit, raw, expected):
    snapshot = sides(kind, unit)
    result = resolve_value(
        body(decision_type="ENTER_VALUE", corrected_value=raw, corrected_unit=unit), snapshot
    )
    assert result["selected_value"] == expected
    assert result["corrected_input"] == raw
    assert result["conversion_trace"]["rounding"] == "NONE"
    assert result["selected_source_id"] is None
    assert snapshot[0]["value"]["normalized_value"] == "12.5"


@pytest.mark.parametrize(
    "kind,unit,raw,submitted_unit",
    [
        ("quantity", "kg", "12", "g"),
        ("decimal", None, "NaN", None),
        ("decimal", None, "1,234.5", None),
        ("decimal", None, "1e999", None),
        ("decimal", None, "1.0000000000000000001", None),
        ("date", None, "2023-02-29", None),
        ("date", None, "20261023", None),
        ("date", None, "2026-10-23T00:00:00Z", None),
        ("string", None, "x\x00y", None),
        ("string", None, " ", None),
    ],
)
def test_malformed_and_ambiguous_corrections_fail_closed(kind, unit, raw, submitted_unit):
    with pytest.raises(ApiError):
        resolve_value(
            body(decision_type="ENTER_VALUE", corrected_value=raw, corrected_unit=submitted_unit),
            sides(kind, unit),
        )


def test_conflicting_kind_unit_or_unknown_kind_cannot_enable_correction():
    snapshot = sides()
    snapshot[1]["value"]["kind"] = "string"
    assert not correction_policy(snapshot)["allowed"]
    snapshot = sides()
    snapshot[1]["value"]["unit"] = "g"
    assert not correction_policy(snapshot)["allowed"]
    assert not correction_policy(sides("code-execution", None))["allowed"]


@pytest.mark.parametrize("outcome", ["INSUFFICIENT_DATA", "DEFERRED"])
def test_unresolved_outcomes_never_install_a_value(outcome):
    result = resolve_value(body(decision_type=outcome), sides())
    assert result["selected_value"] is None and result["unit"] is None
    with pytest.raises(ApiError):
        resolve_value(body(decision_type=outcome, corrected_value="fake truth"), sides())


@pytest.mark.parametrize(
    "changes",
    [
        {"reason": " \t\n"},
        {"reason": "bad\x00comment"},
        {"reason": "x" * 2001},
        {"confirmed": False},
        {"confirmed": 1},
        {"user_id": str(uuid4())},
        {"status": "ACTIVE"},
        {"selected_value": "spoofed value"},
        {"decision_type": "ACCEPT_RECOMMENDATION"},
        {"decision_type": "FALSE_POSITIVE"},
    ],
)
def test_human_confirmation_and_server_owned_fields(changes):
    with pytest.raises(ValidationError):
        body(**changes)
