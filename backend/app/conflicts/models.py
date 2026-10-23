from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Base


class ConflictType(StrEnum):
    VALUE_MISMATCH = "VALUE_MISMATCH"
    MISSING = "MISSING"
    DUPLICATE = "DUPLICATE"
    RULE_VIOLATION = "RULE_VIOLATION"
    ANOMALY = "ANOMALY"


class ConflictStatus(StrEnum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConflictRun(Base):
    """Technical execution/checkpoint, using the canonical AnalysisRun lifecycle."""

    __tablename__ = "conflict_runs"
    __table_args__ = (
        CheckConstraint("status IN ('NEW','QUEUED','PROCESSING','COMPLETED','FAILED')"),
        Index("ix_conflict_runs_created", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    matching_run_id: Mapped[UUID] = mapped_column(ForeignKey("matching_runs.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="NEW")
    profile_hash: Mapped[str] = mapped_column(String(64))
    profile_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    actor_id: Mapped[UUID]
    records_processed: Mapped[int] = mapped_column(default=0)
    attributes_evaluated: Mapped[int] = mapped_column(default=0)
    conflicts_generated: Mapped[int] = mapped_column(default=0)
    status_counts: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    last_candidate_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_text: Mapped[str | None] = mapped_column(Text)


class Conflict(Base):
    __tablename__ = "conflicts"
    __table_args__ = (
        CheckConstraint(
            "conflict_type IN ('VALUE_MISMATCH','MISSING','DUPLICATE','RULE_VIOLATION','ANOMALY')"
        ),
        CheckConstraint("status IN ('OPEN','IN_REVIEW','RESOLVED','INSUFFICIENT_DATA')"),
        CheckConstraint("severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"),
        Index("ix_conflicts_created", "detected_at", "id"),
        Index("ix_conflicts_run_created", "matching_run_id", "detected_at", "id"),
        Index("ix_conflicts_filter", "conflict_type", "status", "severity"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    entity_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_entities.id"), index=True)
    analysis_run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id"))
    matching_run_id: Mapped[UUID] = mapped_column(ForeignKey("matching_runs.id"), index=True)
    match_candidate_id: Mapped[UUID] = mapped_column(ForeignKey("match_candidates.id"), index=True)
    attribute_code: Mapped[str] = mapped_column(String(64))
    conflict_type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default="OPEN")
    review_version: Mapped[int] = mapped_column(default=0)
    current_decision_id: Mapped[UUID | None]
    values_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    basis: Mapped[dict[str, Any]] = mapped_column(JSONB)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConflictOutput(Base):
    """Technical association lets reruns reuse immutable Conflict facts."""

    __tablename__ = "conflict_outputs"
    run_id: Mapped[UUID] = mapped_column(ForeignKey("conflict_runs.id"), primary_key=True)
    conflict_id: Mapped[UUID] = mapped_column(ForeignKey("conflicts.id"), primary_key=True)


class ConflictInput(Base):
    """Frozen eligible identity set; no mutable matching preview enters analysis."""

    __tablename__ = "conflict_inputs"
    run_id: Mapped[UUID] = mapped_column(ForeignKey("conflict_runs.id"), primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("match_candidates.id"), primary_key=True)
