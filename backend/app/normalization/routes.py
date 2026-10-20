import hashlib
import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from app.auth.dependencies import Cache, Config, Db, require_permission
from app.auth.models import User
from app.common.errors import ApiError
from app.imports.models import ImportBatch, RawRecord, SourceSystem
from app.normalization.jobs import audit, enqueue, recover_runs
from app.normalization.models import (
    AnalysisRecord,
    AnalysisRun,
    AnalysisStatus,
    CanonicalEntity,
    EntityValue,
)
from app.normalization.profiles import Profile, catalog

router = APIRouter(prefix="/api/v1/analysis", tags=["normalization"])
Reader = Annotated[User, Depends(require_permission("analysis.view"))]
Runner = Annotated[User, Depends(require_permission("analysis.run"))]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1_000_000)]


class StartAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    import_batch_ids: list[UUID] = Field(min_length=1, max_length=20)
    template_id: UUID


class AnalysisView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    analysis_id: UUID = Field(validation_alias="id")
    status: AnalysisStatus
    import_batch_ids: list[str]
    template_id: UUID
    mapping_hash: str
    mapping_snapshot: dict[str, Any]
    actor_id: UUID
    records_processed: int
    values_processed: int
    quality_counts: dict[str, int]
    created_at: datetime
    completed_at: datetime | None
    error_text: str | None


def run_or_404(session: Db, identifier: UUID) -> AnalysisRun:
    run = session.get(AnalysisRun, identifier)
    if run is None:
        raise ApiError(404, "ANALYSIS_NOT_FOUND", "Запуск нормализации не найден")
    return run


@router.get("/profiles")
def profiles(actor: Reader) -> list[dict[str, Any]]:
    return [
        {
            "id": str(profile.id),
            "code": profile.code,
            "version": profile.version,
            "engine_version": profile.engine_version,
            "synthetic": profile.synthetic,
            "mapping_hash": profile.digest(),
        }
        for profile in catalog().values()
    ]


@router.post("", response_model=AnalysisView, status_code=201)
def start(
    body: StartAnalysis,
    response: Response,
    session: Db,
    actor: Runner,
    settings: Config,
    redis: Cache,
) -> AnalysisRun:
    profile = catalog().get(body.template_id)
    if profile is None:
        raise ApiError(422, "PROFILE_NOT_FOUND", "Профиль нормализации не найден")
    identifiers = sorted(set(body.import_batch_ids))
    batches = session.scalars(select(ImportBatch).where(ImportBatch.id.in_(identifiers))).all()
    if len(batches) != len(identifiers):
        raise ApiError(404, "IMPORT_NOT_FOUND", "Пакет импорта не найден")
    if any(batch.status not in {"COMPLETED", "COMPLETED_WITH_ERRORS"} for batch in batches):
        raise ApiError(409, "IMPORT_NOT_READY", "Дождитесь успешного завершения импорта")
    try:
        recover_runs(settings, redis)
    except Exception:
        raise ApiError(503, "QUEUE_UNAVAILABLE", "Очередь временно недоступна") from None
    scope = [str(value) for value in identifiers]
    digest = profile.digest()
    key = int.from_bytes(
        hashlib.sha256(json.dumps([scope, digest]).encode()).digest()[:8], "big", signed=True
    )
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    existing = session.scalar(
        select(AnalysisRun)
        .where(
            AnalysisRun.import_batch_ids == scope,
            AnalysisRun.mapping_hash == digest,
            AnalysisRun.status.in_(
                [AnalysisStatus.NEW, AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING]
            ),
        )
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        session.commit()
        response.status_code = 200
        return existing
    run = AnalysisRun(
        import_batch_ids=scope,
        template_id=profile.id,
        mapping_hash=digest,
        mapping_snapshot=profile.snapshot(),
        actor_id=actor.id,
    )
    session.add(run)
    session.flush()
    audit(session, run, "CREATED")
    session.commit()
    enqueue(run.id, session, settings, redis)
    session.refresh(run)
    return run


@router.get("", response_model=list[AnalysisView])
def runs(
    session: Db,
    actor: Reader,
    import_batch_id: UUID | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[AnalysisRun]:
    query = select(AnalysisRun)
    if import_batch_id is not None:
        query = query.where(AnalysisRun.import_batch_ids.contains([str(import_batch_id)]))
    return list(
        session.scalars(
            query.order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.get("/{analysis_id}", response_model=AnalysisView)
def detail(analysis_id: UUID, session: Db, actor: Reader) -> AnalysisRun:
    return run_or_404(session, analysis_id)


@router.get("/{analysis_id}/records")
def records(
    analysis_id: UUID, session: Db, actor: Reader, limit: Limit = 50, offset: Offset = 0
) -> list[dict[str, Any]]:
    run = run_or_404(session, analysis_id)
    profile = Profile.model_validate(run.mapping_snapshot)
    rows = session.execute(
        select(AnalysisRecord, RawRecord, ImportBatch, SourceSystem, CanonicalEntity)
        .select_from(AnalysisRecord)
        .join(RawRecord, RawRecord.id == AnalysisRecord.raw_record_id)
        .join(ImportBatch, ImportBatch.id == RawRecord.import_batch_id)
        .join(SourceSystem, SourceSystem.id == ImportBatch.source_system_id)
        .outerjoin(CanonicalEntity, CanonicalEntity.id == AnalysisRecord.entity_id)
        .where(AnalysisRecord.analysis_id == analysis_id)
        .order_by(AnalysisRecord.raw_record_id)
        .offset(offset)
        .limit(limit)
    ).all()
    entity_ids = [link.entity_id for link, *_ in rows if link.entity_id]
    by_entity: dict[UUID, list[dict[str, Any]]] = {}
    for value in session.scalars(
        select(EntityValue)
        .where(EntityValue.entity_id.in_(entity_ids))
        .order_by(EntityValue.attribute_code)
    ):
        by_entity.setdefault(value.entity_id, []).append(
            {
                "id": value.id,
                "attribute_code": value.attribute_code,
                "raw_record_id": value.raw_record_id,
                "raw_value": value.raw_value,
                "normalized_value": value.normalized_value,
                "unit": value.unit,
                "quality_status": value.quality_status,
                "normalization_rule": value.normalization_rule,
            }
        )
    result = []
    for link, raw, batch, source, entity in rows:
        binding = profile.binding(batch.format, source.source_type, raw.source_object_type)
        definitions = (
            {field.attribute_code: field.model_dump(mode="json") for field in binding.fields}
            if binding
            else {}
        )
        result.append(
            {
                "raw_record_id": raw.id,
                "source_record_key": raw.source_record_key,
                "source_position": raw.source_position,
                "raw_payload": raw.raw_payload,
                "source": {"id": source.id, "name": source.name, "code": source.code},
                "import_batch": {
                    "id": batch.id,
                    "original_filename": batch.original_filename,
                    "file_hash": batch.file_hash,
                },
                "entity": {
                    "id": entity.id,
                    "domain": entity.domain,
                    "entity_type": entity.entity_type,
                    "display_name": entity.display_name,
                    "status": entity.status,
                }
                if entity
                else None,
                "values": [
                    {**value, "rule_definition": definitions[value["attribute_code"]]}
                    for value in by_entity.get(link.entity_id, [])
                ]
                if link.entity_id
                else [],
                "mapping_details": link.details,
            }
        )
    return result
