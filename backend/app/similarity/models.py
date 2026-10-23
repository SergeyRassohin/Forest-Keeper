"""Versioned derived artifacts; the immutable Decision remains the source of truth."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.auth.models import Base


class Vector(UserDefinedType[list[float]]):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "public.vector(1024)"

    def bind_processor(self, dialect: Any) -> Any:
        return lambda value: "[" + ",".join(str(x) for x in value) + "]"

    def result_processor(self, dialect: Any, coltype: Any) -> Any:
        return lambda value: [float(x) for x in value.strip("[]").split(",")]


class RetrievalVersion(Base):
    __tablename__ = "retrieval_versions"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RetrievalState(Base):
    __tablename__ = "retrieval_state"
    __table_args__ = (CheckConstraint("id=1"),)
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    active_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("retrieval_versions.id"))


class DecisionEmbedding(Base):
    __tablename__ = "decision_embeddings"
    __table_args__ = (
        UniqueConstraint("version_id", "decision_id"),
        CheckConstraint("dimensions=1024"),
        CheckConstraint("public.vector_norm(embedding)>0"),
        Index(
            "ix_embedding_filters",
            "version_id",
            "domain",
            "entity_type",
            "attribute_code",
            "conflict_type",
            "value_kind",
            "unit",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id"))
    version_id: Mapped[UUID] = mapped_column(ForeignKey("retrieval_versions.id"))
    domain: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    attribute_code: Mapped[str] = mapped_column(String(64))
    conflict_type: Mapped[str] = mapped_column(String(32))
    value_kind: Mapped[str] = mapped_column(String(32))
    unit: Mapped[str] = mapped_column(String(32))
    dimensions: Mapped[int] = mapped_column(default=1024)
    embedding: Mapped[list[float]] = mapped_column(Vector())
    features: Mapped[dict[str, Any]] = mapped_column(JSONB)
    feature_hash: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    vector_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IndexItem(Base):
    __tablename__ = "retrieval_items"
    version_id: Mapped[UUID] = mapped_column(ForeignKey("retrieval_versions.id"), primary_key=True)
    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id"), primary_key=True)
    reason: Mapped[str] = mapped_column(String(64))


class QueryEmbedding(Base):
    __tablename__ = "retrieval_queries"
    version_id: Mapped[UUID] = mapped_column(ForeignKey("retrieval_versions.id"), primary_key=True)
    context_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB)
    embedding: Mapped[list[float]] = mapped_column(Vector())
    vector_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IndexRun(Base):
    __tablename__ = "retrieval_runs"
    __table_args__ = (
        CheckConstraint("status IN ('NEW','QUEUED','PROCESSING','COMPLETED','FAILED')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version_id: Mapped[UUID] = mapped_column(ForeignKey("retrieval_versions.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="NEW")
    processed: Mapped[int] = mapped_column(default=0)
    indexed: Mapped[int] = mapped_column(default=0)
    skipped: Mapped[int] = mapped_column(default=0)
    batch_size: Mapped[int] = mapped_column(default=100)
    last_decision_id: Mapped[UUID | None]
    activate: Mapped[bool] = mapped_column(default=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
