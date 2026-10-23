"""Only human-submittable fields; actor, history, provenance and status are server owned."""

import unicodedata
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.decisions.models import DecisionType


class BeginReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    supersedes_decision_id: UUID | None = None


class CreateDecision(BeginReview):
    idempotency_key: UUID
    decision_type: DecisionType
    selected_source_id: UUID | None = None
    selected_value_id: UUID | None = None
    corrected_value: str | None = Field(default=None, max_length=4096)
    corrected_unit: str | None = Field(default=None, max_length=32)
    reason: str = Field(min_length=1, max_length=2000)
    confirmed: bool

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value: object) -> bool:
        if value is not True:
            raise ValueError("Explicit human confirmation is required")
        return True

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A human reason is required")
        if any(unicodedata.category(char) == "Cc" and char not in "\n\r\t" for char in value):
            raise ValueError("Unsupported control character")
        return value
