import hashlib
import json
from collections import Counter
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from app.auth.dependencies import Cache, Config, Db, require_permission
from app.auth.models import AuditEvent, User
from app.common.errors import ApiError
from app.imports.models import ImportBatch, RawRecord, SourceSystem
from app.matching.jobs import audit, enqueue, recover_runs
from app.matching.models import MatchCandidate, MatchingPair, MatchingRun
from app.matching.profiles import catalog
from app.normalization.models import AnalysisRun, AnalysisStatus, EntityValue
from app.normalization.profiles import catalog as normalization_catalog

router = APIRouter(prefix="/api/v1", tags=["matching"])
Reader = Annotated[User, Depends(require_permission("match.view"))]
Runner = Annotated[User, Depends(require_permission("analysis.run"))]
Reviewer = Annotated[User, Depends(require_permission("match.review"))]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1_000_000)]


class StartMatching(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_run_ids: list[UUID] = Field(min_length=2, max_length=2)
    profile_id: UUID


class ReviewMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["MATCHED", "NOT_MATCHED"]
    reason: str = Field(min_length=1, max_length=1000)


def run_or_404(identifier: UUID, session: Db) -> MatchingRun:
    run = session.get(MatchingRun, identifier)
    if run is None:
        raise ApiError(404, "MATCHING_NOT_FOUND", "Запуск сопоставления не найден")
    return run


def view(run: MatchingRun) -> dict[str, Any]:
    current = catalog().get(run.profile_id)
    normalization = normalization_catalog()
    previous_inputs = any(
        (profile := normalization.get(UUID(item["profile_id"]))) is None
        or profile.digest() != item["mapping_hash"]
        for item in run.input_context["normalization"]
    )
    return {
        "id": run.id,
        "status": run.status,
        "input_analysis_ids": run.input_analysis_ids,
        "profile_id": run.profile_id,
        "profile_hash": run.profile_hash,
        "profile_snapshot": run.profile_snapshot,
        "input_context": run.input_context,
        "actor_id": run.actor_id,
        "records_processed": run.records_processed,
        "candidates_generated": run.candidates_generated,
        "status_counts": run.status_counts,
        "diagnostics": run.diagnostics,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
        "error_text": run.error_text,
        "based_on_previous_profile": current is None
        or current.digest() != run.profile_hash
        or previous_inputs,
        "gold_reference_configured": False,
    }


@router.get("/matching-profiles")
def profiles(actor: Reader) -> list[dict[str, Any]]:
    return [
        {
            "id": str(profile.id),
            "code": profile.code,
            "version": profile.version,
            "domain": profile.domain,
            "entity_type": profile.entity_type,
            "synthetic": profile.synthetic,
            "profile_hash": profile.digest(),
        }
        for profile in catalog().values()
    ]


@router.post("/matching-runs", status_code=201)
def start(
    body: StartMatching,
    response: Response,
    session: Db,
    actor: Runner,
    settings: Config,
    redis: Cache,
) -> dict[str, Any]:
    profile = catalog().get(body.profile_id)
    if profile is None:
        raise ApiError(422, "PROFILE_NOT_FOUND", "Профиль сопоставления не найден")
    identifiers = sorted(set(body.analysis_run_ids))
    if len(identifiers) != 2:
        raise ApiError(422, "TWO_INPUTS_REQUIRED", "Выберите два разных запуска нормализации")
    inputs = [session.get(AnalysisRun, identifier) for identifier in identifiers]
    if any(run is None for run in inputs):
        raise ApiError(404, "ANALYSIS_NOT_FOUND", "Запуск нормализации не найден")
    context = []
    batch_sets: list[set[UUID]] = []
    sources = []
    for input_run in inputs:
        if input_run is None:
            continue
        if input_run.status != AnalysisStatus.COMPLETED or not input_run.values_processed:
            raise ApiError(
                409, "NORMALIZATION_NOT_READY", "Выберите завершённую нормализацию с результатами"
            )
        if (
            input_run.mapping_snapshot["domain"] != profile.domain
            or input_run.mapping_snapshot["entity_type"] != profile.entity_type
        ):
            raise ApiError(
                422,
                "INCOMPATIBLE_DOMAIN",
                "Профиль не соответствует domain/entity type входных данных",
            )
        batch_ids = {UUID(value) for value in input_run.import_batch_ids}
        batch_sets.append(batch_ids)
        source_ids = set(
            session.scalars(
                select(ImportBatch.source_system_id).where(ImportBatch.id.in_(batch_ids))
            )
        )
        if len(source_ids) != 1:
            raise ApiError(
                422,
                "ONE_SOURCE_PER_INPUT",
                "Для каждого входа выберите нормализацию одного источника",
            )
        source = next(iter(source_ids))
        sources.append(source)
        context.append(
            {
                "analysis_id": str(input_run.id),
                "profile_id": str(input_run.template_id),
                "mapping_hash": input_run.mapping_hash,
                "engine_version": input_run.mapping_snapshot["engine_version"],
                "source_id": str(source),
                "records": input_run.records_processed,
            }
        )
    if batch_sets[0] & batch_sets[1] or (
        sources[0] == sources[1] and not profile.allow_same_source
    ):
        raise ApiError(
            422, "DISJOINT_SOURCES_REQUIRED", "Выберите непересекающиеся пакеты разных источников"
        )
    try:
        recover_runs(settings, redis)
    except Exception:
        raise ApiError(503, "QUEUE_UNAVAILABLE", "Очередь временно недоступна") from None
    scope = [str(value) for value in identifiers]
    digest = profile.digest()
    key = int.from_bytes(
        hashlib.sha256(b"matching-start:" + json.dumps([scope, digest]).encode()).digest()[:8],
        "big",
        signed=True,
    )
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    existing = session.scalar(
        select(MatchingRun)
        .where(
            MatchingRun.input_analysis_ids == scope,
            MatchingRun.profile_hash == digest,
            MatchingRun.status.in_(
                [AnalysisStatus.NEW, AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING]
            ),
        )
        .limit(1)
    )
    if existing:
        session.commit()
        response.status_code = 200
        return view(existing)
    run = MatchingRun(
        input_analysis_ids=scope,
        profile_id=profile.id,
        profile_hash=digest,
        profile_snapshot=profile.snapshot(),
        input_context={"normalization": context, "gold_reference_version": None},
        actor_id=actor.id,
    )
    session.add(run)
    session.flush()
    audit(session, run, "CREATED")
    session.commit()
    enqueue(run.id, session, settings, redis)
    session.refresh(run)
    return view(run)


@router.get("/matching-runs")
def runs(session: Db, actor: Reader, limit: Limit = 50, offset: Offset = 0) -> list[dict[str, Any]]:
    return [
        view(run)
        for run in session.scalars(
            select(MatchingRun)
            .order_by(MatchingRun.created_at.desc(), MatchingRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/matching-runs/{run_id}")
def detail(run_id: UUID, session: Db, actor: Reader) -> dict[str, Any]:
    return view(run_or_404(run_id, session))


def candidate_view(candidate: MatchCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "raw_record_a_id": candidate.raw_record_a_id,
        "raw_record_b_id": candidate.raw_record_b_id,
        "confidence": str(candidate.confidence),
        "status": candidate.status,
        "confirmed_by": candidate.confirmed_by,
        "created_at": candidate.created_at,
        "reason": candidate.evidence["reason"],
        "run_id": candidate.evidence["run_id"],
    }


@router.get("/matching-runs/{run_id}/candidates")
def candidates(
    run_id: UUID,
    session: Db,
    actor: Reader,
    status: Literal["MATCHED", "POSSIBLE_MATCH", "NOT_MATCHED"] | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[dict[str, Any]]:
    run_or_404(run_id, session)
    query = (
        select(MatchCandidate)
        .join(MatchingPair, MatchingPair.candidate_id == MatchCandidate.id)
        .where(MatchingPair.run_id == run_id)
    )
    if status:
        query = query.where(MatchCandidate.status == status)
    return [
        candidate_view(value)
        for value in session.scalars(query.order_by(MatchCandidate.id).offset(offset).limit(limit))
    ]


@router.get("/match-candidates/{candidate_id}")
def candidate_detail(candidate_id: UUID, session: Db, actor: Reader) -> dict[str, Any]:
    candidate = session.get(MatchCandidate, candidate_id)
    if candidate is None:
        raise ApiError(404, "MATCH_NOT_FOUND", "Кандидат не найден")
    result = candidate_view(candidate)
    result["evidence"] = candidate.evidence
    review_event = session.scalar(
        select(AuditEvent)
        .where(AuditEvent.object_id == candidate.id, AuditEvent.event_type == "MATCH_REVIEWED")
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(1)
    )
    result["manual_review"] = (
        {
            "audit_event_id": review_event.id,
            "actor_id": review_event.user_id,
            "reviewed_at": review_event.created_at,
            "from_status": review_event.payload["from"],
            "to_status": review_event.payload["to"],
            "reason": review_event.payload["reason"],
        }
        if review_event
        else None
    )

    records = []
    for item in candidate.evidence["inputs"]:
        raw, batch, source = session.execute(
            select(RawRecord, ImportBatch, SourceSystem)
            .select_from(RawRecord)
            .join(ImportBatch, ImportBatch.id == RawRecord.import_batch_id)
            .join(SourceSystem, SourceSystem.id == ImportBatch.source_system_id)
            .where(RawRecord.id == UUID(item["raw_record_id"]))
        ).one()
        values = session.scalars(
            select(EntityValue)
            .where(EntityValue.entity_id == UUID(item["entity_id"]))
            .order_by(EntityValue.attribute_code)
        ).all()
        records.append(
            {
                "raw_record_id": raw.id,
                "source": {"id": source.id, "name": source.name, "code": source.code},
                "import_batch_id": batch.id,
                "filename": batch.original_filename,
                "file_hash": batch.file_hash,
                "source_record_key": raw.source_record_key,
                "source_position": raw.source_position,
                "raw_payload": raw.raw_payload,
                "entity_id": item["entity_id"],
                "values": [
                    {
                        "attribute_code": value.attribute_code,
                        "raw_value": value.raw_value,
                        "normalized_value": value.normalized_value,
                        "unit": value.unit,
                        "quality_status": value.quality_status,
                        "normalization_rule": value.normalization_rule,
                    }
                    for value in values
                ],
            }
        )
    result["records"] = records
    result["run"] = view(run_or_404(UUID(candidate.evidence["run_id"]), session))
    return result


@router.post("/match-candidates/{candidate_id}/review")
def review(candidate_id: UUID, body: ReviewMatch, session: Db, actor: Reviewer) -> dict[str, Any]:
    link = session.scalar(select(MatchingPair).where(MatchingPair.candidate_id == candidate_id))
    if link is None:
        raise ApiError(404, "MATCH_NOT_FOUND", "Кандидат не найден")
    run = session.get(MatchingRun, link.run_id, with_for_update=True)
    if run is None or run.status != AnalysisStatus.COMPLETED:
        raise ApiError(409, "MATCHING_NOT_COMPLETED", "Дождитесь завершения сопоставления")
    candidate = session.scalar(
        select(MatchCandidate)
        .where(MatchCandidate.id == candidate_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if candidate is None or candidate.status != "POSSIBLE_MATCH":
        raise ApiError(409, "MATCH_TERMINAL", "Кандидат уже имеет окончательный статус")
    if not body.reason.strip():
        raise ApiError(422, "REASON_REQUIRED", "Укажите причину решения")
    candidate.status = body.status
    candidate.confirmed_by = actor.id
    counts = Counter(run.status_counts)
    counts["POSSIBLE_MATCH"] -= 1
    counts[body.status] += 1
    run.status_counts = dict(counts)
    session.add(
        AuditEvent(
            event_type="MATCH_REVIEWED",
            user_id=actor.id,
            object_type="MatchCandidate",
            object_id=candidate.id,
            payload={
                "run_id": str(run.id),
                "from": "POSSIBLE_MATCH",
                "to": body.status,
                "reason": body.reason,
                "profile_hash": run.profile_hash,
            },
        )
    )
    session.commit()
    return candidate_view(candidate)
