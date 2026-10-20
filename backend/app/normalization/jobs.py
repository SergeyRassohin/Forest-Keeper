import hashlib
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from redis import Redis
from rq import Queue
from rq.job import Callback, Job
from sqlalchemy import exists, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent
from app.common.config import Settings
from app.common.database import make_engine
from app.imports.models import ImportBatch, RawRecord, SourceSystem
from app.normalization.models import (
    AnalysisRecord,
    AnalysisRun,
    AnalysisStatus,
    CanonicalEntity,
    EntityValue,
)
from app.normalization.pipeline import build_record
from app.normalization.profiles import Profile

TRANSITIONS = {
    AnalysisStatus.NEW: {AnalysisStatus.QUEUED},
    AnalysisStatus.QUEUED: {AnalysisStatus.PROCESSING, AnalysisStatus.FAILED},
    AnalysisStatus.PROCESSING: {AnalysisStatus.COMPLETED, AnalysisStatus.FAILED},
}


def lock_key(identifier: UUID) -> int:
    return int.from_bytes(
        hashlib.sha256(b"normalization:" + identifier.bytes).digest()[:8], "big", signed=True
    )


def job_id(identifier: UUID) -> str:
    return "normalize-" + identifier.hex


def audit(session: Session, run: AnalysisRun, event: str) -> None:
    session.add(
        AuditEvent(
            event_type="NORMALIZATION_" + event,
            user_id=run.actor_id,
            object_type="AnalysisRun",
            object_id=run.id,
            payload={
                "import_batch_ids": run.import_batch_ids,
                "mapping_hash": run.mapping_hash,
                "mapping_version": run.mapping_snapshot["version"],
                "engine_version": run.mapping_snapshot["engine_version"],
                "executor": "USER" if event == "CREATED" else "SYSTEM",
                "error_code": run.error_text if event == "FAILED" else None,
            },
        )
    )


def transition(session: Session, run: AnalysisRun, target: AnalysisStatus) -> None:
    if target not in TRANSITIONS.get(AnalysisStatus(run.status), set()):
        raise ValueError("Forbidden analysis transition")
    run.status = target
    if target in {AnalysisStatus.COMPLETED, AnalysisStatus.FAILED}:
        run.completed_at = datetime.now(UTC)
    audit(session, run, target)


def fail_run(identifier: UUID, settings: Settings) -> None:
    engine = make_engine(settings)
    try:
        with Session(engine) as session:
            if not session.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key(identifier)}
            ):
                return
            run = session.get(AnalysisRun, identifier, with_for_update=True)
            if run and run.status in {AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING}:
                run.error_text = "NORMALIZATION_INTERRUPTED"
                transition(session, run, AnalysisStatus.FAILED)
                session.commit()
    finally:
        engine.dispose()


def rq_failure(job: Job, connection: Redis, *args: Any, **kwargs: Any) -> None:
    fail_run(UUID(job.args[0]), Settings())  # type: ignore[call-arg]


def process_normalization(identifier: str) -> None:
    execute_run(UUID(identifier), Settings())  # type: ignore[call-arg]


def publish(identifier: UUID, settings: Settings, redis: Redis) -> None:
    try:
        Queue(settings.import_queue_name, connection=redis).enqueue(
            process_normalization,
            str(identifier),
            job_id=job_id(identifier),
            job_timeout=settings.import_job_timeout,
            on_failure=Callback(rq_failure, timeout=30),
            result_ttl=86400,
            failure_ttl=604800,
        )
    except Exception:
        fail_run(identifier, settings)


def enqueue(identifier: UUID, session: Session, settings: Settings, redis: Redis) -> None:
    if not session.scalar(
        text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key(identifier)}
    ):
        session.rollback()
        return
    run = session.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.id == identifier)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    ready = run is not None and run.status == AnalysisStatus.NEW
    if ready and run is not None:
        transition(session, run, AnalysisStatus.QUEUED)
    session.commit()
    if ready:
        publish(identifier, settings, redis)
    session.expire_all()


def execute_run(identifier: UUID, settings: Settings) -> None:
    engine = make_engine(settings)
    try:
        with engine.connect() as connection:
            acquired = connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key(identifier)}
            )
            connection.commit()
            if not acquired:
                return
            try:
                with Session(bind=connection) as session:
                    run = session.get(AnalysisRun, identifier)
                    if run is None or run.status not in {
                        AnalysisStatus.QUEUED,
                        AnalysisStatus.PROCESSING,
                    }:
                        return
                    if run.status == AnalysisStatus.QUEUED:
                        transition(session, run, AnalysisStatus.PROCESSING)
                        session.commit()
                    profile = Profile.model_validate(run.mapping_snapshot)
                    if profile.digest() != run.mapping_hash:
                        raise ValueError("Mapping fingerprint mismatch")
                    batch_ids = [UUID(value) for value in run.import_batch_ids]
                    last_id = None
                    while True:
                        query = (
                            select(RawRecord, ImportBatch.format, SourceSystem.source_type)
                            .select_from(RawRecord)
                            .join(ImportBatch, ImportBatch.id == RawRecord.import_batch_id)
                            .join(SourceSystem, SourceSystem.id == ImportBatch.source_system_id)
                            .where(
                                RawRecord.import_batch_id.in_(batch_ids),
                                ~exists().where(
                                    AnalysisRecord.analysis_id == identifier,
                                    AnalysisRecord.raw_record_id == RawRecord.id,
                                ),
                            )
                            .order_by(RawRecord.id)
                            .limit(100)
                        )
                        if last_id is not None:
                            query = query.where(RawRecord.id > last_id)
                        rows = session.execute(query).all()
                        if not rows:
                            break
                        last_id = rows[-1][0].id
                        entities, values, links = [], [], []
                        counts = Counter(run.quality_counts)
                        for raw, fmt, source_type in rows:
                            entity, output, details = build_record(
                                raw, fmt, source_type, profile, run.mapping_hash
                            )
                            if entity:
                                entities.append(entity)
                            values.extend(output)
                            counts.update(item["quality_status"] for item in output)
                            links.append(
                                {
                                    "analysis_id": identifier,
                                    "raw_record_id": raw.id,
                                    "entity_id": entity["id"] if entity else None,
                                    "details": details,
                                }
                            )
                        if entities:
                            session.execute(
                                insert(CanonicalEntity).on_conflict_do_nothing(), entities
                            )
                        if values:
                            session.execute(insert(EntityValue).on_conflict_do_nothing(), values)
                        session.execute(insert(AnalysisRecord).on_conflict_do_nothing(), links)
                        run.records_processed += len(rows)
                        run.values_processed += len(values)
                        run.quality_counts = dict(counts)
                        session.commit()  # Outputs and progress are one atomic checkpoint.
                    transition(session, run, AnalysisStatus.COMPLETED)
                    session.commit()
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key(identifier)}
                )
                connection.commit()
    except Exception:
        # SQL/normalizer exceptions may contain raw input. Expose only a stable code.
        fail_run(identifier, settings)
    finally:
        engine.dispose()


def recover_runs(settings: Settings, redis: Redis) -> int:
    engine = make_engine(settings)
    recovered = 0
    try:
        cutoff = datetime.now(UTC) - timedelta(seconds=60)
        with Session(engine) as scan:
            identifiers = scan.scalars(
                select(AnalysisRun.id)
                .where(
                    AnalysisRun.status.in_(
                        [AnalysisStatus.NEW, AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING]
                    ),
                    AnalysisRun.updated_at < cutoff,
                )
                .limit(1000)
            ).all()
        for identifier in identifiers:
            with Session(engine) as session:
                if not session.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key(identifier)}
                ):
                    continue
                run = session.get(AnalysisRun, identifier, with_for_update=True)
                if run is None or run.updated_at >= cutoff:
                    continue
                ready = run.status == AnalysisStatus.NEW
                if ready:
                    transition(session, run, AnalysisStatus.QUEUED)
                    recovered += 1
                elif run.status in {AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING}:
                    job = Job.fetch_many([job_id(identifier)], connection=redis)[0]
                    if job is None or job.get_status(refresh=True) in {
                        "failed",
                        "stopped",
                        "canceled",
                        "finished",
                    }:
                        run.error_text = "NORMALIZATION_INTERRUPTED"
                        transition(session, run, AnalysisStatus.FAILED)
                        recovered += 1
                session.commit()
            if ready:
                publish(identifier, settings, redis)
    finally:
        engine.dispose()
    return recovered
