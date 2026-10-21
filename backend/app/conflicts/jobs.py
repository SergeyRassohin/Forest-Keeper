import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from redis import Redis
from rq import Queue
from rq.job import Callback, Job
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent
from app.common.config import Settings
from app.common.database import make_engine
from app.conflicts.engine import CONFIG_HASH
from app.conflicts.models import ConflictRun
from app.conflicts.pipeline import process_chunk
from app.normalization.jobs import TRANSITIONS
from app.normalization.models import AnalysisStatus


def lock_key(identifier: UUID) -> int:
    return int.from_bytes(
        hashlib.sha256(b"conflict:" + identifier.bytes).digest()[:8], "big", signed=True
    )


def job_id(identifier: UUID) -> str:
    return "conflict-" + identifier.hex


def audit(session: Session, run: ConflictRun, event: str) -> None:
    session.add(
        AuditEvent(
            event_type="CONFLICT_" + event,
            user_id=run.actor_id,
            object_type="ConflictRun",
            object_id=run.id,
            payload={
                "matching_run_id": str(run.matching_run_id),
                "profile_hash": run.profile_hash,
                "profile_version": run.profile_snapshot["version"],
                "engine_version": run.profile_snapshot["engine_version"],
                "severity": "LOW",
                "status": "OPEN",
                "executor": "USER" if event == "CREATED" else "SYSTEM",
                "conflicts_generated": run.conflicts_generated,
                "records_processed": run.records_processed,
                "attributes_evaluated": run.attributes_evaluated,
                "status_counts": run.status_counts,
                "error_code": run.error_text if event == "FAILED" else None,
            },
        )
    )

    logging.getLogger("forest_keeper.conflicts").warning(
        json.dumps(
            {
                "event": "CONFLICT_" + event,
                "run_id": str(run.id),
                "job_id": job_id(run.id),
                "matching_run_id": str(run.matching_run_id),
                "records_processed": run.records_processed,
                "conflicts_generated": run.conflicts_generated,
            }
        )
    )


def transition(session: Session, run: ConflictRun, target: AnalysisStatus) -> None:
    if target not in TRANSITIONS.get(AnalysisStatus(run.status), set()):
        raise ValueError("Forbidden conflict transition")
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
            run = session.get(ConflictRun, identifier, with_for_update=True)
            if run and run.status in {AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING}:
                run.error_text = "CONFLICT_INTERRUPTED"
                transition(session, run, AnalysisStatus.FAILED)
                session.commit()
    finally:
        engine.dispose()


def rq_failure(job: Job, connection: Redis, *args: Any, **kwargs: Any) -> None:
    fail_run(UUID(job.args[0]), Settings())  # type: ignore[call-arg]


def process_conflict(identifier: str) -> None:
    execute_conflict(UUID(identifier), Settings())  # type: ignore[call-arg]


def publish(identifier: UUID, settings: Settings, redis: Redis) -> None:
    try:
        Queue(settings.import_queue_name, connection=redis).enqueue(
            process_conflict,
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
        select(ConflictRun)
        .where(ConflictRun.id == identifier)
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


def execute_conflict(identifier: UUID, settings: Settings) -> None:
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
                    run = session.get(ConflictRun, identifier)
                    if run is None or run.status not in {
                        AnalysisStatus.QUEUED,
                        AnalysisStatus.PROCESSING,
                    }:
                        return
                    if run.status == AnalysisStatus.QUEUED:
                        transition(session, run, AnalysisStatus.PROCESSING)
                        session.commit()
                    if run.profile_hash != CONFIG_HASH:
                        raise ValueError("Unsupported conflict configuration")
                    while process_chunk(session, run):
                        session.commit()
                    transition(session, run, AnalysisStatus.COMPLETED)
                    session.commit()
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key(identifier)}
                )
                connection.commit()
    except Exception:
        # Raw values and DB parameters must never appear in error responses/logs.
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
                select(ConflictRun.id)
                .where(
                    ConflictRun.status.in_(
                        [AnalysisStatus.NEW, AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING]
                    ),
                    ConflictRun.updated_at < cutoff,
                )
                .limit(1000)
            ).all()
        for identifier in identifiers:
            with Session(engine) as session:
                if not session.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key(identifier)}
                ):
                    continue
                run = session.get(ConflictRun, identifier, with_for_update=True)
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
                        run.error_text = "CONFLICT_INTERRUPTED"
                        transition(session, run, AnalysisStatus.FAILED)
                        recovered += 1
                session.commit()
            if ready:
                publish(identifier, settings, redis)
    finally:
        engine.dispose()
    return recovered
