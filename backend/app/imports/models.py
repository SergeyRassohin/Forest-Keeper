from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Base


class SourceType(StrEnum):
    FILE = "FILE"
    ONE_C = "ONE_C"


class SourceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"


class ImportStatus(StrEnum):
    NEW = "NEW"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class SourceSystem(Base):
    __tablename__ = "source_systems"
    __table_args__ = (
        CheckConstraint("source_type IN ('FILE','ONE_C')"),
        CheckConstraint("status IN ('ACTIVE','DISABLED','ARCHIVED')"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(64), unique=True)
    source_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default=SourceStatus.ACTIVE)
    authority_scope: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint("format IN ('CSV','XLSX','XML')"),
        CheckConstraint(
            "status IN ('NEW','QUEUED','PROCESSING','COMPLETED','COMPLETED_WITH_ERRORS','FAILED')"
        ),
        Index(
            "uq_import_original_checksum",
            "source_system_id",
            "file_hash",
            unique=True,
            postgresql_where=text("retry_of_id IS NULL"),
        ),
        Index("ix_import_uploaded", "uploaded_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_system_id: Mapped[UUID] = mapped_column(ForeignKey("source_systems.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(8))
    file_hash: Mapped[str] = mapped_column(String(64))
    storage_uri: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default=ImportStatus.NEW)
    uploaded_by: Mapped[UUID]
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    error_text: Mapped[str | None] = mapped_column(Text)
    records_loaded: Mapped[int] = mapped_column(default=0)
    records_failed: Mapped[int] = mapped_column(default=0)
    retry_of_id: Mapped[UUID | None] = mapped_column(ForeignKey("import_batches.id"), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RawRecord(Base):
    __tablename__ = "raw_records"
    __table_args__ = (UniqueConstraint("import_batch_id", "position_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("import_batches.id"), index=True)
    source_record_key: Mapped[str | None] = mapped_column(Text)
    source_object_type: Mapped[str] = mapped_column(String(200))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_position: Mapped[dict[str, Any]] = mapped_column(JSONB)
    position_key: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportErrorRecord(Base):
    __tablename__ = "import_errors"
    __table_args__ = (UniqueConstraint("import_batch_id", "position_key", "code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("import_batches.id"), index=True)
    source_position: Mapped[dict[str, Any]] = mapped_column(JSONB)
    position_key: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(String(300))
