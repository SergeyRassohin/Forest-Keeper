"""Bounded AI input and output; generated free-form claims are never trusted."""

import json
import re
from enum import StrEnum
from typing import Annotated, Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, model_validator

from app.ai.baseline import INPUT_BYTES, QUERY_INSTRUCTION

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Revision = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
Short = Annotated[str, Field(max_length=64)]
Ids = Annotated[list[UUID], Field(max_length=20)]


class AIError(Exception):
    """Fixed sanitized reason only, never input or model response text."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Observation(StrictModel):
    value: Annotated[str, Field(max_length=512)] | None
    presence: Short
    quality: Short
    source_type: Short
    source_role: Short


class SemanticContext(StrictModel):
    domain: Short
    entity_type: Short
    subject: Annotated[str, Field(min_length=1, max_length=256)]
    attribute_code: Short
    conflict_type: Short
    value_kind: Literal["quantity", "decimal", "string", "date"]
    unit: Short
    observations: Annotated[list[Observation], Field(min_length=1, max_length=8)]

    @model_validator(mode="after")
    def minimize_sensitive_input(self) -> "SemanticContext":
        text = self.model_dump_json()
        # A denylist supplements field minimization; it is not a perfect PII detector.
        if re.search(
            r"(?i)(?:password|passwd|api[_ -]?key|secret|bearer)\s*[:=]"
            r"|[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b(?:ghp_|github_pat_|sk-)[A-Za-z0-9_]"
            r"|(?<!\w)\+\d[\d ()-]{8,}\d",
            text,
        ):
            raise ValueError("SENSITIVE_INPUT")
        return self


def semantic_context(features: dict[str, Any]) -> SemanticContext:
    """Explicit projection excludes reasons, selected outcome, raw payload and actor."""
    fields = SemanticContext.model_fields
    return SemanticContext.model_validate({k: features[k] for k in fields if k in features})


class EmbeddingRequest(StrictModel):
    purpose: Literal["document", "query"]
    contexts: Annotated[list[SemanticContext], Field(min_length=1, max_length=8)]


def embedding_text(context: SemanticContext, purpose: Literal["document", "query"]) -> str:
    data = json.dumps(context.model_dump(), ensure_ascii=False, sort_keys=True, allow_nan=False)
    if len(data.encode()) > INPUT_BYTES:
        raise AIError("AI_INPUT_TOO_LARGE")
    return "Instruct: " + QUERY_INSTRUCTION + "\nQuery: " + data if purpose == "query" else data


class ModelInfo(StrictModel):
    component: Literal["embedding", "llm"]
    model_id: str
    revision: Revision
    artifact_sha256: Digest
    artifact_lock_sha256: Digest
    dimensions: int | None
    configured_context_tokens: int
    preprocessing_version: str
    prompt_version: str | None
    prompt_sha256: Digest | None
    instruction_sha256: Digest | None
    runtime_versions: dict[str, str]
    input_schema_sha256: Digest
    output_schema_sha256: Digest
    quality_provenance: Literal["LOCAL_QWEN_DEMO"] = "LOCAL_QWEN_DEMO"
    production_accepted: Literal[False] = False


class EmbeddingResponse(StrictModel):
    vectors: Annotated[list[list[StrictFloat]], Field(min_length=1, max_length=8)]
    model: ModelInfo


class ComparedValue(StrictModel):
    source_id: UUID
    value_id: UUID | None
    normalized_value: Annotated[str, Field(max_length=512)] | None
    presence: Short
    quality: Short
    logical_role: Annotated[str, Field(pattern=r"^[A-Z][A-Z_]{0,63}$")]


class Comparison(StrictModel):
    domain: Short
    entity_type: Short
    attribute_code: Short
    conflict_type: Short
    value_kind: Literal["quantity", "decimal", "string", "date"]
    unit: Short
    values: Annotated[list[ComparedValue], Field(min_length=1, max_length=8)]


class PrecedentFact(StrictModel):
    decision_id: UUID
    outcome: Literal["SELECT_VALUE", "ENTER_VALUE"]
    selected_value: Annotated[str, Field(max_length=512)] | None
    unit: Short
    logical_role: Annotated[str, Field(pattern=r"^[A-Z][A-Z_]{0,63}$")] | None


class Facts(StrictModel):
    conflict_id: UUID
    context_fingerprint: Digest
    status: Literal["RECOMMENDED", "ABSTAINED", "UNAVAILABLE"]
    reason_code: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
    action: Literal["SELECT_VALUE"] | None
    supporting_decision_ids: Ids
    contradictory_decision_ids: Ids
    source_ids: Annotated[list[UUID], Field(max_length=8)]
    value_ids: Annotated[list[UUID], Field(max_length=8)]
    independent_groups: Annotated[int, Field(ge=0, le=20)]
    comparison: Comparison
    precedents: Annotated[list[PrecedentFact], Field(max_length=20)]

    @model_validator(mode="after")
    def consistent_action(self) -> "Facts":
        if (self.status == "RECOMMENDED") != (self.action == "SELECT_VALUE"):
            raise ValueError("INCONSISTENT_ACTION")
        if self.status == "RECOMMENDED" and (
            self.independent_groups < 5
            or len(self.supporting_decision_ids) < self.independent_groups
            or self.contradictory_decision_ids
        ):
            raise ValueError("INSUFFICIENT_EVIDENCE")
        support, contrary = self.supporting_decision_ids, self.contradictory_decision_ids
        if (
            len(set(support)) != len(support)
            or len(set(contrary)) != len(contrary)
            or (set(support) & set(contrary))
        ):
            raise ValueError("AMBIGUOUS_EVIDENCE")
        if contrary and (
            self.status != "ABSTAINED" or self.reason_code != "CONTRADICTORY_PRECEDENTS"
        ):
            raise ValueError("INCONSISTENT_CONTRADICTION")
        if self.status == "RECOMMENDED" and self.reason_code != "UNANIMOUS_INDEPENDENT_PRECEDENTS":
            raise ValueError("INCONSISTENT_REASON")
        ids = [item.decision_id for item in self.precedents]
        if len(ids) != len(set(ids)) or not (set(support) | set(contrary)).issubset(ids):
            raise ValueError("UNVERIFIED_EVIDENCE")
        if set(self.source_ids) != {item.source_id for item in self.comparison.values} or (
            set(self.value_ids)
            != {item.value_id for item in self.comparison.values if item.value_id is not None}
        ):
            raise ValueError("UNVERIFIED_CURRENT_REFERENCES")
        if len(self.source_ids) != len(set(self.source_ids)) or len(self.value_ids) != len(
            set(self.value_ids)
        ):
            raise ValueError("AMBIGUOUS_CURRENT_REFERENCES")
        # Reuse the minimized-value privacy checks; never send human names/reasons/raw.
        SemanticContext(
            **self.comparison.model_dump(exclude={"values"}),
            subject="Verified current comparison",
            observations=[
                Observation(
                    value=item.normalized_value,
                    presence=item.presence,
                    quality=item.quality,
                    source_type="NOT_INCLUDED",
                    source_role=item.logical_role,
                )
                for item in self.comparison.values
            ],
        )
        for item in self.precedents:
            SemanticContext(
                **self.comparison.model_dump(exclude={"values"}),
                subject="Verified precedent summary",
                observations=[
                    Observation(
                        value=item.selected_value,
                        presence="PRESENT",
                        quality="VERIFIED_SNAPSHOT",
                        source_type="NOT_INCLUDED",
                        source_role=item.logical_role or "NOT_DEFINED",
                    )
                ],
            )
        return self


def llm_input(facts: Facts) -> dict[str, Any]:
    """Versioned prompt projection; verified comparison/evidence remain, server IDs do not."""
    comparison = facts.comparison.model_dump(mode="json", exclude={"values"})
    comparison["values"] = [
        value.model_dump(mode="json", exclude={"source_id", "value_id"})
        for value in facts.comparison.values
    ]
    support, contrary = set(facts.supporting_decision_ids), set(facts.contradictory_decision_ids)
    return {
        "status": facts.status,
        "reason_code": facts.reason_code,
        "action": facts.action,
        "independent_groups": facts.independent_groups,
        "comparison": comparison,
        "supporting_precedents": [
            item.model_dump(mode="json") for item in facts.precedents if item.decision_id in support
        ],
        "contradictory_precedents": [
            item.model_dump(mode="json")
            for item in facts.precedents
            if item.decision_id in contrary
        ],
    }


class ClauseCode(StrEnum):
    CURRENT_CONTEXT = "CURRENT_CONTEXT"
    SUPPORT = "SUPPORT"
    CONTRADICTION = "CONTRADICTION"
    ABSTENTION = "ABSTENTION"
    LIMITATION = "LIMITATION"


class Clause(StrictModel):
    code: ClauseCode
    decision_ids: Annotated[list[UUID], Field(max_length=1)]


class GeneratedClauses(StrictModel):
    clauses: Annotated[list[Clause], Field(min_length=3, max_length=3)]


class Explanation(GeneratedClauses):
    conflict_id: UUID
    context_fingerprint: Digest
    status: Literal["RECOMMENDED", "ABSTAINED", "UNAVAILABLE"]
    action: Literal["SELECT_VALUE"] | None
    reason_code: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]


def explanation_schema(facts: Facts) -> dict[str, Any]:
    """Grammar constrains copying, while validation independently distrusts model output."""
    schema = GeneratedClauses.model_json_schema()
    evidence_code = (
        "SUPPORT"
        if facts.status == "RECOMMENDED"
        else "CONTRADICTION"
        if facts.contradictory_decision_ids
        else "ABSTENTION"
    )
    ids = [
        str(value)
        for value in (
            facts.supporting_decision_ids
            if facts.status == "RECOMMENDED"
            else facts.contradictory_decision_ids
        )
    ]
    variants = []
    for code in ("CURRENT_CONTEXT", evidence_code, "LIMITATION"):
        references: dict[str, Any] = {"type": "array", "maxItems": 0}
        if code in {"SUPPORT", "CONTRADICTION"}:
            references = {
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {"type": "string", "enum": ids},
            }
        variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["code", "decision_ids"],
                "properties": {"code": {"const": code}, "decision_ids": references},
            }
        )
    schema["properties"]["clauses"]["items"] = {"oneOf": variants}
    return schema


def validate_explanation(output: Explanation, facts: Facts) -> Explanation:
    if any(
        getattr(output, key) != getattr(facts, key)
        for key in ("conflict_id", "context_fingerprint", "status", "action", "reason_code")
    ):
        raise AIError("AI_FACT_MISMATCH")
    codes = [c.code for c in output.clauses]
    required = {ClauseCode.CURRENT_CONTEXT, ClauseCode.LIMITATION}
    required.add(
        ClauseCode.SUPPORT
        if facts.status == "RECOMMENDED"
        else ClauseCode.CONTRADICTION
        if facts.contradictory_decision_ids
        else ClauseCode.ABSTENTION
    )
    if len(codes) != len(set(codes)) or not required.issubset(codes):
        raise AIError("AI_INCOMPLETE_EXPLANATION")
    for clause in output.clauses:
        supplied = set(clause.decision_ids)
        if clause.code == ClauseCode.SUPPORT:
            if (
                facts.status != "RECOMMENDED"
                or not supplied
                or not supplied.issubset(facts.supporting_decision_ids)
            ):
                raise AIError("AI_INVALID_CITATION")
        elif clause.code == ClauseCode.CONTRADICTION:
            if (
                facts.status == "RECOMMENDED"
                or not supplied
                or not supplied.issubset(facts.contradictory_decision_ids)
            ):
                raise AIError("AI_INVALID_CITATION")
        elif supplied or (clause.code == ClauseCode.ABSTENTION and facts.status == "RECOMMENDED"):
            raise AIError("AI_FACT_MISMATCH")
    return output


class LLMProvider(Protocol):
    def explain(self, facts: Facts) -> Explanation: ...
