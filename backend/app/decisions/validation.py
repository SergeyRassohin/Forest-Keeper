"""Canonical corrections from frozen comparison metadata, never a source-data mutation."""

import unicodedata
from datetime import date
from typing import Any
from uuid import UUID

from app.common.errors import ApiError
from app.decisions.models import DecisionType
from app.decisions.schemas import CreateDecision
from app.normalization.normalize import bounded_decimal, decimal_text


def correction_policy(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = {side["value"]["kind"] for side in snapshots if side.get("value")}
    units = {side["value"].get("unit") for side in snapshots if side.get("value")}
    kind = next(iter(kinds)) if len(kinds) == 1 else None
    unit = next(iter(units)) if len(units) == 1 else None
    enabled = kind in {"string", "decimal", "quantity", "date"} and len(units) == 1
    if kind == "quantity" and not unit:
        enabled = False
    return {
        "allowed": enabled,
        "kind": kind,
        "unit": unit,
        "max_length": 4096,
        "numeric_precision": 38,
        "numeric_exponent": [-18, 18],
        "date_format": "YYYY-MM-DD",
        "business_range": None,
        "unit_policy": "frozen canonical unit only; no inferred conversion",
    }


def selectable(side: dict[str, Any]) -> bool:
    value = side.get("value")
    return bool(
        value
        and side.get("presence") == "PRESENT"
        and value.get("quality_status") == "VALID"
        and isinstance(value.get("normalized_value"), str)
        and len(value["normalized_value"]) <= 4096
        and value.get("kind") in {"string", "decimal", "quantity", "date"}
    )


def resolve_value(body: CreateDecision, snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    empty: dict[str, Any] = {
        "selected_value": None,
        "selected_source_id": None,
        "selected_value_id": None,
        "value_kind": None,
        "unit": None,
        "corrected_input": None,
        "conversion_trace": {},
    }
    if body.decision_type == DecisionType.SELECT_VALUE:
        if body.corrected_value is not None or body.corrected_unit is not None:
            raise ApiError(
                422, "UNEXPECTED_CORRECTION", "Для выбора источника не вводите другое значение"
            )
        for side in snapshots:
            value = side.get("value")
            if (
                value is not None
                and selectable(side)
                and str(body.selected_source_id) == side["source_id"]
                and str(body.selected_value_id) == value["value_id"]
            ):
                return {
                    **empty,
                    "selected_value": value["normalized_value"],
                    "selected_source_id": UUID(side["source_id"]),
                    "selected_value_id": UUID(value["value_id"]),
                    "value_kind": value["kind"],
                    "unit": value.get("unit"),
                }
        raise ApiError(422, "INVALID_SOURCE_VALUE", "Выберите допустимое значение этого конфликта")
    if body.selected_source_id is not None or body.selected_value_id is not None:
        raise ApiError(422, "UNEXPECTED_SOURCE", "Источник допустим только при выборе его значения")
    if body.decision_type != DecisionType.ENTER_VALUE:
        if body.corrected_value is not None or body.corrected_unit is not None:
            raise ApiError(422, "UNEXPECTED_VALUE", "Это решение не устанавливает значение")
        return empty
    policy = correction_policy(snapshots)
    raw = body.corrected_value
    if not policy["allowed"] or raw is None or not raw.strip():
        raise ApiError(
            422, "CORRECTION_UNAVAILABLE", "Для этого атрибута нельзя сохранить такое значение"
        )
    if body.corrected_unit != policy["unit"]:
        raise ApiError(
            422, "INVALID_UNIT", "Используйте единицу из сохранённого контекста конфликта"
        )
    if any(unicodedata.category(char) == "Cc" for char in raw):
        raise ApiError(422, "INVALID_VALUE", "Значение содержит недопустимые управляющие символы")
    kind = policy["kind"]
    text = unicodedata.normalize("NFC", raw).strip()
    if kind in {"quantity", "decimal"}:
        number = bounded_decimal(text)
        if number is None:
            raise ApiError(
                422, "INVALID_NUMBER", "Введите однозначное конечное число без округления"
            )
        canonical = decimal_text(number)
    elif kind == "date":
        try:
            canonical = date.fromisoformat(text).isoformat()
            if text != canonical:
                raise ValueError("Expected canonical ISO date")
        except ValueError:
            raise ApiError(
                422, "INVALID_DATE", "Введите существующую дату в формате ГГГГ-ММ-ДД"
            ) from None
    else:
        canonical = text
    return {
        **empty,
        "selected_value": canonical,
        "value_kind": kind,
        "unit": policy["unit"],
        "corrected_input": raw,
        "conversion_trace": {
            "operation": "HUMAN_CANONICAL_ENTRY",
            "unicode": "NFC",
            "trim": True,
            "decimal_separator": "comma-or-dot",
            "rounding": "NONE",
            "unit_conversion": "NONE",
        },
    }
