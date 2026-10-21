import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Signal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    attribute_code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    algorithm: Literal["exact", "token_sort_ratio", "decimal_tolerance"]
    weight: str = Field(pattern=r"^(?:[1-9][0-9]{0,2}|0)(?:\.[0-9]{1,6})?$")
    tolerance: str = Field(default="0", pattern=r"^(?:[0-9]{1,6})(?:\.[0-9]{1,6})?$")
    unit: str | None = Field(default=None, max_length=32)


class MatchingProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    code: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    version: str = Field(min_length=1, max_length=32)
    engine_version: Literal["fk-matching/1"]
    synthetic: bool
    domain: str = Field(min_length=1, max_length=100)
    entity_type: str = Field(min_length=1, max_length=100)
    identity_rules: list[list[str]] = Field(min_length=1, max_length=4)
    strong_negative_keys: list[str] = Field(max_length=8)
    identifier_attribute: str
    name_attribute: str
    prefix_length: int = Field(default=3, ge=2, le=16)
    max_string_length: int = Field(default=256, ge=16, le=512)
    max_block_size: int = Field(default=32, ge=1, le=128)
    max_candidates_per_record: int = Field(default=16, ge=1, le=64)
    allow_same_source: bool = False
    signals: list[Signal] = Field(min_length=1, max_length=16)
    threshold_policy: Literal["EXACT_RULES_ONLY_NO_FUZZY_AUTO"]
    threshold_decision: Literal["OPEN"]
    auto_match_threshold: None = None
    review_threshold: None = None

    @model_validator(mode="after")
    def valid_rules(self) -> "MatchingProfile":
        attributes = {signal.attribute_code for signal in self.signals}
        if (
            len(attributes) != len(self.signals)
            or sum(Decimal(s.weight) for s in self.signals) <= 0
        ):
            raise ValueError("Signals require unique attributes and positive total weight")
        referenced = {self.identifier_attribute, self.name_attribute, *self.strong_negative_keys}
        for rule in self.identity_rules:
            if not rule or len(rule) > 8 or len(rule) != len(set(rule)):
                raise ValueError("Invalid identity rule")
            referenced.update(rule)
        if not referenced <= attributes:
            raise ValueError("All blocking/identity attributes must have declared signals")
        return self

    def snapshot(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.snapshot(), sort_keys=True).encode()).hexdigest()


def catalog() -> dict[UUID, MatchingProfile]:
    profiles = [
        MatchingProfile.model_validate_json(path.read_text())
        for path in sorted(Path(__file__).with_name("profiles").glob("*.json"))
    ]
    if len({profile.id for profile in profiles}) != len(profiles):
        raise ValueError("Duplicate matching profile ID")
    return {profile.id: profile for profile in profiles}
