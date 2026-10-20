from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Base


class AnalysisStatus(StrEnum):
    NEW = "NEW"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint("status IN ('NEW','QUEUED','PROCESSING','COMPLETED','FAILED')"),
        Index("ix_analysis_created", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    status: Mapped[str] = mapped_column(String(16), default=AnalysisStatus.NEW)
    import_batch_ids: Mapped[list[str]] = mapped_column(JSONB)
    template_id: Mapped[UUID]
    mapping_hash: Mapped[str] = mapped_column(String(64))
    mapping_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    actor_id: Mapped[UUID]
    records_processed: Mapped[int] = mapped_column(default=0)
    values_processed: Mapped[int] = mapped_column(default=0)
    quality_counts: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    error_text: Mapped[str | None] = mapped_column(Text)


class CanonicalEntity(Base):
    __tablename__ = "canonical_entities"
    __table_args__ = (CheckConstraint("status IS NULL"),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(200))
    # Canonical docs define no lifecycle enum here. NULL reserves the field
    # without inventing an ACTIVE/MERGED/etc. business state for pre-match data.
    status: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EntityValue(Base):
    __tablename__ = "entity_values"
    __table_args__ = (
        CheckConstraint("quality_status IN ('VALID','WARNING','INVALID','UNKNOWN')"),
        Index("uq_entity_attribute", "entity_id", "attribute_code", unique=True),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    entity_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_entities.id"), index=True)
    attribute_code: Mapped[str] = mapped_column(String(64))
    raw_record_id: Mapped[UUID] = mapped_column(ForeignKey("raw_records.id"), index=True)
    raw_value: Mapped[Any] = mapped_column(JSONB(none_as_null=False), nullable=False)
    normalized_value: Mapped[Any] = mapped_column(JSONB(none_as_null=False), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    quality_status: Mapped[str] = mapped_column(String(16))
    normalization_rule: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisRecord(Base):
    """Technical run/output association, not a new domain business object."""

    __tablename__ = "analysis_records"
    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id"), primary_key=True)
    raw_record_id: Mapped[UUID] = mapped_column(ForeignKey("raw_records.id"), primary_key=True)
    entity_id: Mapped[UUID | None] = mapped_column(ForeignKey("canonical_entities.id"))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
