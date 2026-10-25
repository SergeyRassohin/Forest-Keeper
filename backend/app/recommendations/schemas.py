from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Outcome(StrEnum):
    RECOMMENDED = "RECOMMENDED"
    ABSTAINED = "ABSTAINED"
    UNAVAILABLE = "UNAVAILABLE"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceBinding(StrictModel):
    source_id: UUID
    source_type: Literal["FILE", "ONE_C"]
    role: str = Field(pattern=r"^[A-Z][A-Z_]{0,63}$")


class SourceMap(StrictModel):
    version: str = Field(min_length=1, max_length=64)
    approved: Literal[True]
    approval_reference: str = Field(min_length=1, max_length=256)
    domain: str = Field(min_length=1, max_length=100)
    entity_type: str = Field(min_length=1, max_length=100)
    attribute_code: str = Field(min_length=1, max_length=64)
    matching_profile_hashes: list[str] = Field(min_length=1, max_length=10)
    sources: list[SourceBinding] = Field(min_length=2, max_length=42)

    @model_validator(mode="after")
    def unique_sources(self) -> "SourceMap":
        if len({s.source_id for s in self.sources}) != len(self.sources):
            raise ValueError("Ambiguous source identity")
        if any(
            len(h) != 64 or any(c not in "0123456789abcdef" for c in h)
            for h in self.matching_profile_hashes
        ):
            raise ValueError("Expected exact profile fingerprints")
        return self


class Evidence(StrictModel):
    decision_id: UUID
    conflict_id: UUID
    actor_id: UUID
    actor_display_name: str
    decided_at: datetime
    outcome: str
    selected_value: Any
    unit: str | None
    reason: str
    similarity: float = Field(ge=0, le=1, allow_inf_nan=False)
    logical_role: str | None = None
    context_summary: dict[str, Any]
    source_correspondence: list[dict[str, str]] = Field(default_factory=list)


class RecommendationResult(StrictModel):
    conflict_id: UUID
    status: Outcome = Outcome.ABSTAINED
    recommended_action: Literal["SELECT_VALUE"] | None = None
    recommended_source_id: UUID | None = None
    recommended_value_id: UUID | None = None
    recommended_value: dict[str, Any] | None = None
    confidence: int | None = Field(default=None, ge=5, le=20)
    confidence_unit: Literal["INDEPENDENT_PROVENANCE_GROUPS"] = "INDEPENDENT_PROVENANCE_GROUPS"
    confidence_label: str = "NOT_APPLICABLE"
    reason_code: str
    reasoning_summary: str
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list, max_length=20)
    conflicting_evidence: list[UUID] = Field(default_factory=list, max_length=20)
    supporting_decision_ids: list[UUID] = Field(default_factory=list, max_length=20)
    rules_used: list[str] = Field(default_factory=list)
    rules_status: Literal["NOT_CONFIGURED"] = "NOT_CONFIGURED"
    template_status: Literal["NOT_CONFIGURED"] = "NOT_CONFIGURED"
    authority_reference: Literal["NOT_DEFINED"] = "NOT_DEFINED"
    forest_codex: Literal["NOT_CONFIGURED"] = "NOT_CONFIGURED"
    quality_provenance: Literal["DEMONSTRATION_ONLY", "NOT_AVAILABLE"] = "NOT_AVAILABLE"
    retrieval_version: UUID | None = None
    embedding_model: dict[str, Any] | None = None
    recommendation_policy_version: str
    recommendation_policy_hash: str
    source_mapping_version: str | None = None
    context_fingerprint: str
    review_context_version: str
    generated_at: datetime
    audit_reference: UUID | None = None

    @model_validator(mode="after")
    def action_contract(self) -> "RecommendationResult":
        fields = (
            self.recommended_action,
            self.recommended_source_id,
            self.recommended_value_id,
            self.recommended_value,
            self.confidence,
        )
        if self.status == Outcome.RECOMMENDED:
            if any(value is None for value in fields) or not self.supporting_decision_ids:
                raise ValueError("A recommendation needs current references and actual support")
            if self.quality_provenance != "DEMONSTRATION_ONLY":
                raise ValueError("Production recommendation is not accepted")
        elif any(value is not None for value in fields) or self.supporting_decision_ids:
            raise ValueError("An abstention cannot contain a proposed action or confidence")
        return self
