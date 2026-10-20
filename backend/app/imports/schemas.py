from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.imports.models import ImportBatch, ImportStatus, SourceStatus, SourceType
from app.imports.parsers import json_safe


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    source_type: SourceType
    authority_scope: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "authority_scope")
    @classmethod
    def representable(cls, value: Any) -> Any:
        if not json_safe(value):
            raise ValueError("Unrepresentable source metadata")
        return value


class SourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    authority_scope: dict[str, Any] | None = None

    @field_validator("name", "authority_scope")
    @classmethod
    def representable(cls, value: Any) -> Any:
        return SourceCreate.representable(value)


class SourceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    source_type: SourceType
    status: SourceStatus
    authority_scope: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ImportView(BaseModel):
    id: UUID
    import_batch_id: UUID
    source_system_id: UUID
    source_name: str
    original_filename: str
    file_name: str
    format: str
    file_hash: str
    status: ImportStatus
    uploaded_by: UUID
    uploaded_at: datetime
    records_total: int
    records_loaded: int
    records_failed: int
    error_text: str | None
    retry_of_id: UUID | None
    duplicate: bool = False

    @classmethod
    def of(cls, batch: ImportBatch, source_name: str, duplicate: bool = False) -> "ImportView":
        return cls(
            id=batch.id,
            import_batch_id=batch.id,
            source_system_id=batch.source_system_id,
            source_name=source_name,
            original_filename=batch.original_filename,
            file_name=batch.original_filename,
            format=batch.format,
            file_hash=batch.file_hash,
            status=ImportStatus(batch.status),
            uploaded_by=batch.uploaded_by,
            uploaded_at=batch.uploaded_at,
            records_total=batch.records_loaded + batch.records_failed,
            records_loaded=batch.records_loaded,
            records_failed=batch.records_failed,
            error_text=batch.error_text,
            retry_of_id=batch.retry_of_id,
            duplicate=duplicate,
        )


class RawView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    import_batch_id: UUID
    source_record_key: str | None
    source_object_type: str
    raw_payload: dict[str, Any]
    source_position: dict[str, Any]
    created_at: datetime


class ErrorView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_position: dict[str, Any]
    code: str
    message: str
