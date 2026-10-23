"""Versioned, bounded context from frozen evidence; no raw payload or chosen answer."""

import json
import unicodedata
from typing import Any

from app.decisions.models import Decision
from app.decisions.service import digest
from app.similarity.provider import SCHEMA, ProviderError


def normalized(value: Any, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ProviderError("INCOMPLETE_CONTEXT")
    return unicodedata.normalize("NFC", value).casefold().strip()


def context(snapshot: dict[str, Any], decision: Decision | None = None) -> dict[str, Any]:
    try:
        evidence = snapshot["conflict"]
        subject = snapshot["subject"]
        if decision is not None and (
            decision.evidence_hash != digest(evidence)
            or str(decision.conflict_id) != evidence["id"]
            or str(decision.entity_id) != evidence["entity_id"]
            or decision.domain != subject["domain"]
            or decision.entity_type != subject["entity_type"]
            or decision.attribute_code != evidence["attribute_code"]
        ):
            raise ProviderError("CORRUPT_EVIDENCE")
        values = evidence["values_snapshot"]
        kinds = {side["value"]["kind"] for side in values if side.get("value")}
        units = {side["value"].get("unit") for side in values if side.get("value")}
        if len(kinds) != 1 or len(units) != 1:
            raise ProviderError("INCOMPATIBLE_CONTEXT")
        kind, unit = next(iter(kinds)), next(iter(units))
        if kind not in {"quantity", "decimal", "string", "date"}:
            raise ProviderError("UNKNOWN_KIND")
        if kind == "quantity" and unit not in {"kg", "m", "mm", "cm", "g", "l", "ml"}:
            raise ProviderError("UNKNOWN_UNIT")
        if decision is not None and (
            decision.value_kind != kind or (decision.unit or "") != (unit or "")
        ):
            raise ProviderError("CORRUPT_EVIDENCE")
        observations = []
        sources = {s["source_id"]: s for s in snapshot.get("retrieval_sources", [])}
        for side in values:
            value = side.get("value") or {}
            source = sources.get(side["source_id"], {})
            observations.append(
                {
                    "value": normalized(value["normalized_value"])
                    if value.get("normalized_value") is not None
                    else None,
                    "presence": side["presence"],
                    "quality": value.get("quality_status", "UNKNOWN"),
                    "source_type": source.get("source_type", "UNKNOWN"),
                    "source_role": source.get("role", "NOT_DEFINED"),
                }
            )
        profile = snapshot["matching"]["profile_snapshot"]
        result = {
            "schema": SCHEMA,
            "domain": subject["domain"],
            "entity_type": subject["entity_type"],
            "business_key_class": "UNCONFIGURED",
            "subject": normalized(subject["display_name"], 256),
            "attribute_code": evidence["attribute_code"],
            "conflict_type": evidence["conflict_type"],
            "value_kind": kind,
            "unit": unit or "",
            "observations": sorted(observations, key=digest),
            "synthetic": profile.get("synthetic") is True,
            "matching": {
                "profile_version": profile["version"],
                "profile_hash": snapshot["matching"]["profile_hash"],
                "identity_status": evidence["basis"].get("identity_status", "UNKNOWN"),
            },
            "normalization": sorted(
                [
                    {k: x.get(k) for k in ("profile_version", "mapping_hash", "engine_version")}
                    for x in snapshot["normalization_origins"]
                ],
                key=digest,
            ),
            "authority": snapshot.get("authority", "NOT_DEFINED"),
            "forest_codex": snapshot.get("forest_codex", {"configured": False}),
            "known_unknowns": sorted(
                {x["presence"] for x in observations if x["presence"] != "PRESENT"}
                | {"SOURCE_ROLE_NOT_DEFINED", "AUTHORITY_NOT_DEFINED"}
                | (
                    {"SOURCE_TYPE_UNKNOWN"}
                    if any(x["source_type"] == "UNKNOWN" for x in observations)
                    else set()
                )
            ),
        }
        if len(json.dumps(result, ensure_ascii=False).encode()) > 32_768:
            raise ProviderError("CONTEXT_TOO_LARGE")
        return result
    except (KeyError, TypeError, ValueError, StopIteration):
        raise ProviderError("INCOMPLETE_CONTEXT") from None


COMPATIBILITY = ("domain", "entity_type", "attribute_code", "conflict_type", "value_kind", "unit")


def explain(query: dict[str, Any], past: dict[str, Any]) -> tuple[list[str], list[str]]:
    fields = (
        *COMPATIBILITY,
        "subject",
        "observations",
        "matching",
        "normalization",
        "authority",
        "forest_codex",
    )
    return (
        [key for key in fields if query[key] == past[key]],
        [key for key in fields if query[key] != past[key]],
    )
