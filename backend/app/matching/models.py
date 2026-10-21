from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Base
from app.normalization.models import AnalysisStatus


class MatchStatus(StrEnum):
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    MATCHED = "MATCHED"
    NOT_MATCHED = "NOT_MATCHED"


class MatchingRun(Base):
    """Technical execution, reusing the canonical AnalysisRun lifecycle."""

    __tablename__ = "matching_runs"
    __table_args__ = (
        CheckConstraint("status IN ('NEW','QUEUED','PROCESSING','COMPLETED','FAILED')"),
        Index("ix_matching_created", "created_at", "id"),
        Index("ix_matching_profile", "profile_hash"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    status: Mapped[str] = mapped_column(String(16), default=AnalysisStatus.NEW)
    input_analysis_ids: Mapped[list[str]] = mapped_column(JSONB)
    profile_id: Mapped[UUID]
    profile_hash: Mapped[str] = mapped_column(String(64))
    profile_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    input_context: Mapped[dict[str, Any]] = mapped_column(JSONB)
    actor_id: Mapped[UUID]
    records_processed: Mapped[int] = mapped_column(default=0)
    candidates_generated: Mapped[int] = mapped_column(default=0)
    status_counts: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_record_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_text: Mapped[str | None] = mapped_column(Text)


class MatchCandidate(Base):
    __tablename__ = "match_candidates"
    __table_args__ = (
        CheckConstraint("raw_record_a_id < raw_record_b_id"),
        CheckConstraint("confidence >= 0 AND confidence <= 1"),
        CheckConstraint("status IN ('POSSIBLE_MATCH','MATCHED','NOT_MATCHED')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    raw_record_a_id: Mapped[UUID] = mapped_column(ForeignKey("raw_records.id"), index=True)
    raw_record_b_id: Mapped[UUID] = mapped_column(ForeignKey("raw_records.id"), index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default=MatchStatus.POSSIBLE_MATCH)
    confirmed_by: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MatchingPair(Base):
    """Technical run/ordered-input association; candidate itself uses an unordered raw pair."""

    __tablename__ = "matching_pairs"
    __table_args__ = (
        CheckConstraint("left_record_id <> right_record_id"),
        Index("uq_matching_pair", "run_id", "left_record_id", "right_record_id", unique=True),
        Index("ix_matching_right", "run_id", "right_record_id"),
    )
    run_id: Mapped[UUID] = mapped_column(ForeignKey("matching_runs.id"), primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("match_candidates.id"), primary_key=True)
    left_record_id: Mapped[UUID] = mapped_column(ForeignKey("raw_records.id"))
    right_record_id: Mapped[UUID] = mapped_column(ForeignKey("raw_records.id"))
