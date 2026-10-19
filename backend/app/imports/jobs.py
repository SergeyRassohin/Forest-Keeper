import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from redis import Redis
from rq import Queue
from rq.job import Callback, Job
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.config import Settings
from app.common.database import make_engine
from app.imports.models import ImportBatch, ImportErrorRecord, ImportStatus, RawRecord, SourceSystem
from app.imports.parsers import ParsedRecord, ParseFailure, parse_records
from app.imports.service import transition
from app.imports.storage import LocalStorage, file_checksum

logger = logging.getLogger("forest_keeper.imports")


def job_id(batch_id: UUID) -> str:
    return "import-" + batch_id.hex


def batch_lock_key(batch_id: UUID) -> int:
    return int.from_bytes(hashlib.sha256(batch_id.bytes).digest()[:8], "big", signed=True)


def log_event(event: str, batch_id: UUID) -> None:
    logger.warning(
        json.dumps(
            {
                "event": event,
                "import_batch_id": str(batch_id),
                "job_id": job_id(batch_id),
            }
        )
    )


def fail_batch(batch_id: UUID, message: str, settings: Settings) -> None:
    engine = make_engine(settings)
    try:
        with Session(engine) as session:
            if not session.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": batch_lock_key(batch_id)}
            ):
                return
            batch = session.scalar(
                select(ImportBatch)
                .where(
                    ImportBatch.id == batch_id,
                )
                .with_for_update()
            )
            if batch and batch.status in {ImportStatus.QUEUED, ImportStatus.PROCESSING}:
                batch.error_text = message
                transition(session, batch, ImportStatus.FAILED)
                session.commit()
                log_event("IMPORT_FAILED", batch_id)
    finally:
        engine.dispose()


def rq_failure(job: Job, connection: Redis, *args: Any, **kwargs: Any) -> None:
    # Callback also covers RQ timeouts/abandoned-job handling. Never log exception text.
    settings = Settings()  # type: ignore[call-arg]
    fail_batch(
        UUID(job.args[0]), "Фоновая обработка прервана. Создайте повторный импорт.", settings
    )


def enqueue_batch(batch_id: UUID, session: Session, redis: Redis, settings: Settings) -> None:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise ValueError("Import batch does not exist")
    transition(session, batch, ImportStatus.QUEUED)
    session.commit()
    publish_job(batch_id, redis, settings)
    session.expire_all()


def publish_job(batch_id: UUID, redis: Redis, settings: Settings) -> None:
    try:
        Queue(settings.import_queue_name, connection=redis).enqueue(
            process_import,
            str(batch_id),
            job_id=job_id(batch_id),
            job_timeout=settings.import_job_timeout,
            on_failure=Callback(rq_failure, timeout=30),
            result_ttl=86400,
            failure_ttl=604800,
        )
    except Exception:
        fail_batch(batch_id, "Не удалось поставить импорт в очередь. Повторите импорт.", settings)


def process_import(batch_id: str) -> None:
    execute_import(UUID(batch_id), Settings())  # type: ignore[call-arg]


def execute_import(batch_id: UUID, settings: Settings) -> None:
    engine = make_engine(settings)
    lock_key = batch_lock_key(batch_id)
    try:
        with engine.connect() as connection:
            acquired = connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": lock_key},
            )
            connection.commit()
            if not acquired:
                return
            try:
                with Session(bind=connection) as session:
                    batch = session.get(ImportBatch, batch_id)
                    if batch is None or batch.status not in {
                        ImportStatus.QUEUED,
                        ImportStatus.PROCESSING,
                    }:
                        return
                    if batch.status == ImportStatus.QUEUED:
                        transition(session, batch, ImportStatus.PROCESSING)
                        session.commit()
                    source = session.get(SourceSystem, batch.source_system_id)
                    if source is None:
                        raise ParseFailure("SOURCE_NOT_FOUND", "Источник не найден")
                    path = LocalStorage(settings.import_storage_root).path(batch.storage_uri)
                    if file_checksum(path) != batch.file_hash:
                        raise ParseFailure(
                            "CHECKSUM_MISMATCH", "Контрольная сумма оригинала изменена"
                        )
                    raw: list[dict[str, Any]] = []
                    errors: list[dict[str, Any]] = []
                    fatal: ParseFailure | None = None
                    try:
                        for item in parse_records(
                            path,
                            batch.format,
                            source.source_type,
                            settings.import_max_expanded_bytes,
                        ):
                            append_item(batch_id, item, raw, errors)
                            if len(raw) + len(errors) >= 500:
                                flush_items(session, batch, raw, errors)
                    except ParseFailure as error:
                        fatal = error
                        errors.append(
                            {
                                "id": uuid4(),
                                "import_batch_id": batch_id,
                                "source_position": {"file": True},
                                "position_key": "file",
                                "code": error.code,
                                "message": error.message,
                            }
                        )
                    flush_items(session, batch, raw, errors)
                    if fatal:
                        batch.error_text = fatal.message
                        target = ImportStatus.FAILED
                    elif batch.records_failed and not batch.records_loaded:
                        batch.error_text = "В файле нет записей, пригодных для импорта"
                        target = ImportStatus.FAILED
                    elif batch.records_failed:
                        target = ImportStatus.COMPLETED_WITH_ERRORS
                    else:
                        target = ImportStatus.COMPLETED
                    transition(session, batch, target)
                    session.commit()
                    log_event("IMPORT_" + target, batch_id)
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
                connection.commit()
    except Exception:
        # Rollback releases transaction state; preserve committed raw chunks and original.
        fail_batch(batch_id, "Не удалось обработать файл. Повторите импорт.", settings)
    finally:
        engine.dispose()


def append_item(
    batch_id: UUID,
    item: ParsedRecord,
    raw: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> None:
    common = {
        "id": uuid4(),
        "import_batch_id": batch_id,
        "source_position": item.position,
        "position_key": item.position_key,
    }
    if item.error_code:
        errors.append({**common, "code": item.error_code, "message": item.error_message})
    else:
        raw.append(
            {
                **common,
                "source_record_key": item.record_key,
                "source_object_type": item.object_type,
                "raw_payload": item.payload,
            }
        )


def flush_items(
    session: Session,
    batch: ImportBatch,
    raw: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> None:
    if raw:
        session.execute(insert(RawRecord).values(raw).on_conflict_do_nothing())
        raw.clear()
    if errors:
        session.execute(insert(ImportErrorRecord).values(errors).on_conflict_do_nothing())
        errors.clear()
    batch.records_loaded = (
        session.scalar(
            select(func.count())
            .select_from(RawRecord)
            .where(
                RawRecord.import_batch_id == batch.id,
            )
        )
        or 0
    )
    batch.records_failed = (
        session.scalar(
            select(func.count())
            .select_from(ImportErrorRecord)
            .where(
                ImportErrorRecord.import_batch_id == batch.id,
            )
        )
        or 0
    )
    session.commit()


def recover_imports(settings: Settings, redis: Redis) -> int:
    """Reconcile failed/missing RQ jobs after a crash without reusing terminal batches."""
    engine = make_engine(settings)
    recovered = 0
    try:
        cutoff = datetime.now(UTC) - timedelta(seconds=60)
        with Session(engine) as scan:
            ids = scan.scalars(
                select(ImportBatch.id).where(
                    ImportBatch.status.in_(
                        [
                            ImportStatus.NEW,
                            ImportStatus.QUEUED,
                            ImportStatus.PROCESSING,
                        ]
                    ),
                    ImportBatch.updated_at < cutoff,
                )
            ).all()
        for batch_id in ids:
            publish = False
            with Session(engine) as session:
                # Share the worker's lock and re-read the row: the scan may already be stale.
                if not session.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:key)"),
                    {"key": batch_lock_key(batch_id)},
                ):
                    continue
                batch = session.scalar(
                    select(ImportBatch)
                    .where(
                        ImportBatch.id == batch_id,
                    )
                    .with_for_update()
                )
                if batch is None or batch.updated_at >= cutoff:
                    continue
                if batch.status == ImportStatus.NEW:
                    transition(session, batch, ImportStatus.QUEUED)
                    publish = True
                    recovered += 1
                elif batch.status in {ImportStatus.QUEUED, ImportStatus.PROCESSING}:
                    job = Job.fetch_many([job_id(batch.id)], connection=redis)[0]
                    if job is None or job.get_status(refresh=True) in {
                        "failed",
                        "stopped",
                        "canceled",
                        "finished",
                    }:
                        batch.error_text = "Фоновая задача прервана. Создайте повторный импорт."
                        transition(session, batch, ImportStatus.FAILED)
                        recovered += 1
                session.commit()
            # The job must not start while this recovery still owns the worker lock.
            if publish:
                publish_job(batch_id, redis, settings)
    finally:
        engine.dispose()
    return recovered
