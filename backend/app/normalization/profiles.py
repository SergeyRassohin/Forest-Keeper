import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ENGINE_VERSION = "fk-normalization/1"


class FieldRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    attribute_code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    path: list[str | dict[str, str]] = Field(min_length=1, max_length=12)
    kind: Literal["string", "decimal", "quantity", "date"]
    required: bool = False
    case: Literal["keep", "upper", "lower", "casefold"] = "keep"
    trim: bool = True
    collapse_whitespace: bool = True
    unit: str | None = Field(default=None, max_length=32)
    unit_aliases: dict[str, str] = Field(default_factory=dict)
    date_formats: list[Literal["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"]] = []
    allow_midnight_datetime: bool = False

    @model_validator(mode="after")
    def bounded_configuration(self) -> "FieldRule":
        for segment in self.path:
            if isinstance(segment, str):
                if not segment or len(segment) > 200 or "\x00" in segment:
                    raise ValueError("Invalid mapping path")
            elif set(segment) != {"tag"} or not 0 < len(segment["tag"]) <= 200:
                raise ValueError("Only literal child-tag selectors are supported")
        if self.kind == "date" and not self.date_formats:
            raise ValueError("Date formats must be explicit")
        if self.kind == "quantity":
            if not self.unit or not self.unit_aliases or len(self.unit_aliases) > 32:
                raise ValueError("Quantity requires a canonical unit and explicit aliases")
            # Factors are bounded decimal constants, not executable expressions.
            import re

            if any(
                not re.fullmatch(r"[a-zа-я]{1,16}", alias)
                or not re.fullmatch(r"(?:[1-9][0-9]{0,5}|0)\.[0-9]{1,6}|[1-9][0-9]{0,5}", factor)
                or Decimal(factor) == 0
                for alias, factor in self.unit_aliases.items()
            ):
                raise ValueError("Invalid unit alias/factor")
        return self


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    formats: list[Literal["CSV", "XLSX", "XML"]] = Field(min_length=1, max_length=3)
    source_types: list[Literal["FILE", "ONE_C"]] = Field(min_length=1, max_length=2)
    object_types: list[str] = Field(min_length=1, max_length=16)
    fields: list[FieldRule] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique_attributes(self) -> "Binding":
        if len({field.attribute_code for field in self.fields}) != len(self.fields):
            raise ValueError("Duplicate canonical attribute")
        return self


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    code: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    version: str = Field(min_length=1, max_length=32)
    engine_version: Literal["fk-normalization/1"]
    synthetic: bool
    domain: str = Field(min_length=1, max_length=100)
    entity_type: str = Field(min_length=1, max_length=100)
    display_attribute: str = Field(max_length=64)
    bindings: list[Binding] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def no_ambiguous_binding(self) -> "Profile":
        combinations = [
            (fmt, source, obj)
            for binding in self.bindings
            for fmt in binding.formats
            for source in binding.source_types
            for obj in binding.object_types
        ]
        if len(combinations) != len(set(combinations)):
            raise ValueError("Ambiguous binding")
        return self

    def snapshot(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.snapshot(), sort_keys=True, ensure_ascii=True).encode()
        ).hexdigest()

    def binding(self, file_format: str, source_type: str, object_type: str) -> Binding | None:
        return next(
            (
                binding
                for binding in self.bindings
                if file_format in binding.formats
                and source_type in binding.source_types
                and object_type in binding.object_types
            ),
            None,
        )


def catalog() -> dict[UUID, Profile]:
    profiles = [
        Profile.model_validate_json(path.read_text())
        for path in sorted(Path(__file__).with_name("profiles").glob("*.json"))
    ]
    if len({profile.id for profile in profiles}) != len(profiles):
        raise ValueError("Duplicate profile ID")
    return {profile.id: profile for profile in profiles}
