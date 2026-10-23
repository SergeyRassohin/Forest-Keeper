"""Immutable facts. ACTIVE/SUPERSEDED is derived, never rewritten on a Decision."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Base


class DecisionType(StrEnum):
    SELECT_VALUE = "SELECT_VALUE"
    ENTER_VALUE = "ENTER_VALUE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DEFERRED = "DEFERRED"


class DecisionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(
            "decision_type IN ('SELECT_VALUE','ENTER_VALUE','INSUFFICIENT_DATA','DEFERRED')"
        ),
        CheckConstraint("supersedes_decision_id IS NULL OR supersedes_decision_id <> id"),
        CheckConstraint("char_length(reason) BETWEEN 1 AND 2000"),
        UniqueConstraint("conflict_id", "id", name="uq_decision_conflict_id"),
        UniqueConstraint("user_id", "conflict_id", "idempotency_key", name="uq_decision_retry"),
        UniqueConstraint("supersedes_decision_id", name="uq_decision_successor"),
        ForeignKeyConstraint(["conflict_id"], ["conflicts.id"]),
        ForeignKeyConstraint(
            ["conflict_id", "supersedes_decision_id"],
            ["decisions.conflict_id", "decisions.id"],
            name="fk_decision_predecessor",
        ),
        Index("ix_decision_created", "decided_at", "id"),
        Index("ix_decision_conflict_history", "conflict_id", "decided_at", "id"),
        Index("ix_decision_domain_created", "domain", "decided_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conflict_id: Mapped[UUID]
    entity_id: Mapped[UUID]
    domain: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    business_key: Mapped[str] = mapped_column(String(256))
    attribute_code: Mapped[str] = mapped_column(String(64))
    decision_type: Mapped[str] = mapped_column(String(32))
    selected_value: Mapped[Any] = mapped_column(JSONB(none_as_null=False), nullable=False)
    selected_source_id: Mapped[UUID | None]
    selected_value_id: Mapped[UUID | None]
    value_kind: Mapped[str | None] = mapped_column(String(32))
    unit: Mapped[str | None] = mapped_column(String(32))
    corrected_input: Mapped[Any] = mapped_column(JSONB(none_as_null=False), nullable=False)
    conversion_trace: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    # Historical actor survives administrative account removal, just like AuditEvent.
    user_id: Mapped[UUID]
    actor_roles: Mapped[list[str]] = mapped_column(JSONB)
    actor_display_name: Mapped[str] = mapped_column(String(200))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    evidence_hash: Mapped[str] = mapped_column(String(64))
    context_version: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[int] = mapped_column(default=1)
    idempotency_key: Mapped[UUID]
    request_hash: Mapped[str] = mapped_column(String(64))
    supersedes_decision_id: Mapped[UUID | None]
    audit_event_id: Mapped[UUID]
