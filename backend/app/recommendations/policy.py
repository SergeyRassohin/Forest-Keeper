"""Owner-approved, versioned demonstration policy. No SQL/network or business writes."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.decisions.service import digest

POLICY: dict[str, Any] = json.loads(
    Path(__file__).with_name("policies").joinpath("demo-unanimous-v1.json").read_text()
)
POLICY_HASH = digest(POLICY)


@dataclass(frozen=True)
class Candidate:
    identifier: str
    correlation: frozenset[str]
    outcome: str
    role: str | None


def aggregate(current: frozenset[str], candidates: list[Candidate]) -> dict[str, Any]:
    """Build the whole graph including current before removing its component."""
    if len(candidates) > POLICY["maximum_precedents"]:
        return {"reason": "EVIDENCE_WINDOW_EXCEEDED", "groups": []}
    parents = list(range(len(candidates) + 1))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    nodes = [current, *[c.correlation for c in candidates]]
    for left in range(len(nodes)):
        for right in range(left):
            if nodes[left] & nodes[right]:
                parents[root(left)] = root(right)
    components: dict[int, list[Candidate]] = {}
    for index, candidate in enumerate(candidates, 1):
        components.setdefault(root(index), []).append(candidate)
    groups: list[dict[str, Any]] = [
        {
            "decision_ids": sorted(c.identifier for c in values),
            "correlated_with_current": component == root(0),
            "logical_roles": sorted({c.role for c in values if c.role is not None}),
        }
        for component, values in components.items()
    ]
    groups.sort(key=lambda group: group["decision_ids"])
    result: dict[str, Any] = {
        "reason": "INSUFFICIENT_INDEPENDENT_EVIDENCE",
        "groups": groups,
        "independent_groups": sum(not g["correlated_with_current"] for g in groups),
    }
    if not candidates:
        result["reason"] = "NO_COMPATIBLE_PRECEDENT"
        return result
    if any(c.outcome != "SELECT_VALUE" for c in candidates):
        result["reason"] = "UNSUPPORTED_HISTORICAL_ACTION"
        return result
    roles = {c.role for c in candidates}
    if None in roles:
        result["reason"] = "SOURCE_MAPPING_AMBIGUOUS"
    elif len(roles) != 1:
        result["reason"] = "CONTRADICTORY_PRECEDENTS"
    elif result["independent_groups"] >= POLICY["minimum_groups"]:
        result.update(reason="UNANIMOUS_INDEPENDENT_PRECEDENTS", role=next(iter(roles)))
    return result
