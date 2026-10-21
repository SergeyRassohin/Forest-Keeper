from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import literal, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import defer

from app.auth.dependencies import Cache, Config, Db, require_permission
from app.auth.models import User
from app.common.errors import ApiError
from app.conflicts.engine import CONFIG, CONFIG_HASH
from app.conflicts.jobs import audit, enqueue, recover_runs
from app.conflicts.models import (
    Conflict,
    ConflictInput,
    ConflictRun,
    ConflictStatus,
    ConflictType,
    Severity,
)
from app.matching.models import MatchCandidate, MatchingPair
from app.matching.routes import run_or_404
from app.matching.routes import view as matching_view

router = APIRouter(prefix="/api/v1", tags=["conflicts"])
Reader = Annotated[User, Depends(require_permission("conflict.view"))]
Runner = Annotated[User, Depends(require_permission("analysis.run"))]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1_000_000)]


class StartConflicts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matching_run_id: UUID


def run_view(run: ConflictRun) -> dict[str, Any]:
    return {
        key: getattr(run, key)
        for key in [
            "id",
            "matching_run_id",
            "status",
            "profile_hash",
            "profile_snapshot",
            "records_processed",
            "attributes_evaluated",
            "conflicts_generated",
            "status_counts",
            "created_at",
            "completed_at",
            "error_text",
        ]
    }


@router.post("/conflict-runs", status_code=201)
def start(
    body: StartConflicts,
    response: Response,
    session: Db,
    actor: Runner,
    settings: Config,
    redis: Cache,
) -> dict[str, Any]:
    matching = run_or_404(body.matching_run_id, session)
    if matching.status != "COMPLETED":
        raise ApiError(409, "MATCHING_NOT_COMPLETED", "Дождитесь завершения сопоставления")
    try:
        recover_runs(settings, redis)
    except Exception:
        raise ApiError(503, "QUEUE_UNAVAILABLE", "Очередь временно недоступна") from None
    # Serialize with matching review: a technical run freezes eligible MATCHED input IDs
    # at execution; final identities cannot be reverted under Stage 4 lifecycle.
    session.execute(
        text("SELECT id FROM matching_runs WHERE id=:id FOR UPDATE"), {"id": matching.id}
    )
    existing = session.scalar(
        select(ConflictRun)
        .where(
            ConflictRun.matching_run_id == matching.id,
            ConflictRun.profile_hash == CONFIG_HASH,
            ConflictRun.status.in_(["NEW", "QUEUED", "PROCESSING"]),
        )
        .limit(1)
    )
    if existing:
        response.status_code = 200
        return run_view(existing)
    run = ConflictRun(
        matching_run_id=matching.id,
        profile_hash=CONFIG_HASH,
        profile_snapshot=CONFIG,
        actor_id=actor.id,
    )
    session.add(run)
    session.flush()
    session.execute(
        insert(ConflictInput).from_select(
            ["run_id", "candidate_id"],
            select(literal(run.id), MatchCandidate.id)
            .join(MatchingPair, MatchingPair.candidate_id == MatchCandidate.id)
            .where(MatchingPair.run_id == matching.id, MatchCandidate.status == "MATCHED"),
        )
    )
    audit(session, run, "CREATED")
    session.commit()
    enqueue(run.id, session, settings, redis)
    session.refresh(run)
    return run_view(run)


@router.get("/conflict-runs")
def runs(session: Db, actor: Reader, limit: Limit = 50, offset: Offset = 0) -> list[dict[str, Any]]:
    return [
        run_view(run)
        for run in session.scalars(
            select(ConflictRun)
            .order_by(ConflictRun.created_at.desc(), ConflictRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/conflict-runs/{run_id}")
def run_detail(run_id: UUID, session: Db, actor: Reader) -> dict[str, Any]:
    run = session.get(ConflictRun, run_id)
    if run is None:
        raise ApiError(404, "CONFLICT_RUN_NOT_FOUND", "Запуск не найден")
    return run_view(run)


def summary(conflict: Conflict) -> dict[str, Any]:
    result = {
        key: getattr(conflict, key)
        for key in [
            "id",
            "entity_id",
            "analysis_run_id",
            "matching_run_id",
            "match_candidate_id",
            "attribute_code",
            "conflict_type",
            "severity",
            "status",
            "detected_at",
        ]
    }
    result["sources"] = [
        {key: value.get(key) for key in ["source_id", "source_name", "source_record_key"]}
        for value in conflict.values_snapshot
    ]
    return result


@router.get("/conflicts")
def conflicts(
    session: Db,
    actor: Reader,
    conflict_type: ConflictType | None = None,
    status: ConflictStatus | None = None,
    severity: Severity | None = None,
    matching_run_id: UUID | None = None,
    entity_id: UUID | None = None,
    source_id: UUID | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[dict[str, Any]]:
    query = select(Conflict).options(defer(Conflict.basis))
    if source_id:
        query = query.where(Conflict.values_snapshot.contains([{"source_id": str(source_id)}]))
    for field, value in [
        (Conflict.conflict_type, conflict_type),
        (Conflict.status, status),
        (Conflict.severity, severity),
        (Conflict.matching_run_id, matching_run_id),
        (Conflict.entity_id, entity_id),
    ]:
        if value is not None:
            query = query.where(field == value)
    return [
        summary(row)
        for row in session.scalars(
            query.order_by(Conflict.detected_at.desc(), Conflict.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/conflicts/{conflict_id}")
def detail(conflict_id: UUID, session: Db, actor: Reader) -> dict[str, Any]:
    conflict = session.get(Conflict, conflict_id)
    if conflict is None:
        raise ApiError(404, "CONFLICT_NOT_FOUND", "Конфликт не найден")
    matching = run_or_404(conflict.matching_run_id, session)
    return {
        **summary(conflict),
        "values_snapshot": conflict.values_snapshot,
        "basis": conflict.basis,
        "based_on_previous_profile": matching_view(matching)["based_on_previous_profile"]
        or conflict.basis["config_hash"] != CONFIG_HASH,
        "human_decision": "NOT_TAKEN",
        "forest_codex_configured": False,
    }
