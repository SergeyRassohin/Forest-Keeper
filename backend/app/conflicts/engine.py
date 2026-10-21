"""Pure deterministic comparison. No source precedence or truth selection."""

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from app.normalization.normalize import bounded_decimal

CONFIG = json.loads((Path(__file__).parent / "profiles/default-v1.json").read_text())
CONFIG_HASH = hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode()).hexdigest()


def conflict_id(candidate_id: UUID, attribute: str, kind: str, dependencies: str = "") -> UUID:
    return uuid5(candidate_id, CONFIG_HASH + ":" + attribute + ":" + kind + ":" + dependencies)


def presence(value: dict[str, Any] | None) -> str:
    if value is None:
        return "SCHEMA_UNMAPPED"
    code = value["normalization_rule"].get("presence")
    if code in CONFIG["missing"]:
        return str(code).upper()
    if value["quality_status"] != "VALID" or value["normalized_value"] is None:
        return "INVALID_OR_UNKNOWN"
    return "PRESENT"


def compare(a: dict[str, Any] | None, b: dict[str, Any] | None) -> tuple[str, str] | None:
    states = [presence(a), presence(b)]
    # An unmapped schema, invalid number, or unknown unit is not evidence of absence.
    if "PRESENT" in states and any(s in {"MISSING", "NULL", "EMPTY"} for s in states):
        return "MISSING", "SOURCE_VALUE_ABSENT"
    if states != ["PRESENT", "PRESENT"] or a is None or b is None:
        return None
    if a["kind"] != b["kind"] or a["unit"] != b["unit"]:
        return None  # No conversion/semantic assumption beyond frozen normalization.
    left, right = a["normalized_value"], b["normalized_value"]
    if not isinstance(left, str) or not isinstance(right, str) or max(len(left), len(right)) > 4096:
        return None
    if a["kind"] in {"decimal", "quantity"}:
        x, y = bounded_decimal(left), bounded_decimal(right)
        if x is None or y is None:
            return None
        different = x != y  # Zero tolerance is explicit release configuration.
    else:
        different = left != right  # Normalization owns Unicode/case/date policy.
    return ("VALUE_MISMATCH", "NORMALIZED_VALUES_DIFFER") if different else None


def basis(reason: str, values: list[dict[str, Any] | None]) -> dict[str, Any]:
    return {
        "reason_code": reason,
        "basis_type": "CROSS_SOURCE_COMPARISON",
        "engine_version": CONFIG["engine_version"],
        "config_hash": CONFIG_HASH,
        "config_snapshot": CONFIG,
        "presence": [presence(value) for value in values],
        "authority": "NOT_DEFINED",
        "human_decision": "NOT_TAKEN",
    }
