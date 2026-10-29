"""Bounded transactional checkpoints and restart recovery, independent of Decision save."""

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from redis import Redis
from rq import Queue
from rq.job import Job
from sqlalchemy import exists, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.ai.admission import enqueue_bounded, release_current
from app.ai.authorization import actor_case
from app.ai.contracts import AIError
from app.common.config import Settings
from app.common.database import make_engine
from app.conflicts.models import Conflict
from app.decisions.models import Decision
from app.decisions.service import digest, historical_context
from app.similarity.context import COMPATIBILITY, context
from app.similarity.models import (
    DecisionEmbedding,
    IndexItem,
    IndexRun,
    QueryEmbedding,
    RetrievalState,
    RetrievalVersion,
)
from app.similarity.provider import (
    ProviderError,
    inference_queue,
    permitted,
    provider,
    revision_name,
    validate_vector,
    vector_hash,
)
from app.similarity.service import audit, eligible, start_run


def missing(version: UUID) -> Any:
    return select(Decision).where(
        ~exists(
            select(IndexItem.decision_id).where(
                IndexItem.version_id == version, IndexItem.decision_id == Decision.id
            )
        )
    )


def lock_key(version: UUID, schema: str = "public") -> int:
    return int.from_bytes(
        hashlib.sha256(b"retrieval:" + schema.encode() + version.bytes).digest()[:8],
        "big",
        signed=True,
    )


def prepare_query(
    case_id: str,
    version_id: str,
    expected_hash: str,
    settings: Settings | None = None,
    *,
    actor_id: str | None = None,
    auth_session_hash: str | None = None,
) -> None:
    settings = settings or Settings()  # type: ignore[call-arg]
    engine = make_engine(settings)
    try:
        with Session(engine) as session:
            if settings.similarity_provider == "qwen-demo":
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                session.execute(text("SET TRANSACTION READ ONLY"))
            version = session.get(RetrievalVersion, UUID(version_id))
            case = session.get(Conflict, UUID(case_id))
            if (
                version is None
                or case is None
                or session.get(QueryEmbedding, (version.id, expected_hash)) is not None
            ):
                return
            features = context(historical_context(session, case, include_review=False))
            if digest(features) != expected_hash:
                return
            if settings.similarity_provider == "qwen-demo":
                actor_case(session, actor_id, auth_session_hash, case.id)
            revision = version.config["revision"]
        # No DB transaction/locks/pool slot are held across model inference.
        vector = validate_vector(provider(settings, revision).embed(features, purpose="query"))
        with Session(engine) as session:
            if settings.similarity_provider == "qwen-demo":
                _, current = actor_case(session, actor_id, auth_session_hash, UUID(case_id))
                fresh = context(historical_context(session, current, include_review=False))
                if digest(fresh) != expected_hash:
                    return
            session.execute(
                insert(QueryEmbedding)
                .values(
                    version_id=UUID(version_id),
                    context_hash=expected_hash,
                    features=features,
                    embedding=vector,
                    vector_hash=vector_hash(vector),
                )
                .on_conflict_do_nothing()
            )
            session.commit()
    except Exception:
        # RQ retains a sanitized FAILED state; GET distinguishes failure from indexing.
        raise ProviderError("QUERY_PREPARATION_FAILED") from None
    finally:
        engine.dispose()
        if settings.similarity_provider == "qwen-demo":
            release_current(settings)


def request_query(
    case_id: UUID,
    version_id: UUID,
    context_hash: str,
    settings: Settings,
    *,
    actor_id: str | None = None,
    auth_session_hash: str | None = None,
) -> None:
    with Redis.from_url(
        settings.redis_url.get_secret_value(), socket_connect_timeout=0.5, socket_timeout=0.5
    ) as redis:
        queue_name = inference_queue(settings)
        queue = Queue(queue_name, connection=redis)
        queue_namespace = hashlib.sha256(queue_name.encode()).hexdigest()[:12]
        job_id = "retrieval-query-" + queue_namespace + "-" + version_id.hex + "-" + context_hash
        job = Job.fetch_many([job_id], connection=redis)[0]
        if job and job.get_status(refresh=True) == "failed":
            ended = job.ended_at
            if (
                ended is None
                or (datetime.now(UTC) - ended.replace(tzinfo=UTC)).total_seconds() < 30
            ):
                raise ProviderError("QUERY_PREPARATION_FAILED")
        if job and job.get_status(refresh=True) in {"queued", "started", "deferred", "scheduled"}:
            return
        if job and settings.similarity_provider != "qwen-demo":
            job.delete()
        if settings.similarity_provider == "qwen-demo":
            if actor_id is None or auth_session_hash is None:
                raise ProviderError("AI_AUTHORIZATION_REQUIRED")
            try:
                enqueue_bounded(
                    redis,
                    settings,
                    queue,
                    prepare_query,
                    (str(case_id), str(version_id), context_hash),
                    {"actor_id": actor_id, "auth_session_hash": auth_session_hash},
                    job_id=job_id,
                    actor_id=actor_id,
                    description="QWEN_QUERY_PREPARATION",
                )
            except AIError as error:
                raise ProviderError(str(error)) from None
            return
        queue.enqueue(
            prepare_query,
            str(case_id),
            str(version_id),
            context_hash,
            job_id=job_id,
            job_timeout=30,
            result_ttl=60,
            failure_ttl=300,
        )


def activate_version(session: Session, identifier: UUID) -> None:
    from app.common.basis_lock import basis_lock

    basis_lock(session)
    state = session.get(RetrievalState, 1, with_for_update=True)
    if state is None or session.get(RetrievalVersion, identifier) is None:
        raise ProviderError("VERSION_NOT_FOUND")
    if session.scalar(missing(identifier).with_only_columns(Decision.id).limit(1)):
        raise ProviderError("INDEX_NOT_READY")
    state.active_version_id = identifier
    audit(session, identifier, "VERSION_ACTIVATED")


def process_index(identifier: str) -> None:
    settings = Settings()  # type: ignore[call-arg]
    try:
        execute_index(
            UUID(identifier),
            settings,
            max_batches=1 if settings.similarity_provider == "qwen-demo" else None,
        )
    finally:
        if settings.similarity_provider == "qwen-demo":
            release_current(settings)


def execute_index(identifier: UUID, settings: Settings, *, max_batches: int | None = None) -> None:
    """max_batches is a test/operator interruption boundary, not a successful completion."""
    if settings.similarity_provider == "qwen-demo":
        from app.ai.indexing import execute

        execute(identifier, settings, max_batches=max_batches)
        return
    engine = make_engine(settings)
    try:
        with engine.connect() as connection:
            with Session(bind=connection) as session:
                run = session.get(IndexRun, identifier)
                if run is None or run.status not in {"QUEUED", "PROCESSING"}:
                    return
                version_id = run.version_id
            key = lock_key(version_id, connection.scalar(text("SELECT current_schema()")))
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            connection.commit()
            if not acquired:
                return
            try:
                with Session(bind=connection) as session:
                    run = session.get(IndexRun, identifier)
                    if run is None or run.status not in {"QUEUED", "PROCESSING"}:
                        return
                    version = session.get(RetrievalVersion, run.version_id)
                    if version is None:
                        raise ProviderError("VERSION_NOT_FOUND")
                    embedder = provider(settings, version.config["revision"])
                    if run.status == "QUEUED":
                        run.status = "PROCESSING"
                        audit(session, run.version_id, "BACKFILL_STARTED", run_id=str(run.id))
                        session.commit()
                    batches = 0
                    while True:
                        rows = list(
                            session.scalars(
                                missing(run.version_id).order_by(Decision.id).limit(run.batch_size)
                            )
                        )
                        if not rows:
                            if run.activate:
                                activate_version(session, run.version_id)
                            run.status = "COMPLETED"
                            audit(
                                session,
                                run.version_id,
                                "BACKFILL_COMPLETED",
                                run_id=str(run.id),
                                processed=run.processed,
                                indexed=run.indexed,
                                skipped=run.skipped,
                            )
                            session.commit()
                            break
                        for decision in rows:
                            reason = "INDEXED"
                            live = session.scalar(
                                eligible()
                                .with_only_columns(Decision.id)
                                .where(Decision.id == decision.id)
                            )
                            if live is None:
                                reason = "OUTCOME_OR_LIFECYCLE_EXCLUDED"
                            else:
                                try:
                                    features = context(decision.context_snapshot, decision)
                                    if (
                                        settings.similarity_provider == "test"
                                        and features["synthetic"] is not True
                                    ):
                                        raise ProviderError("SYNTHETIC_ONLY")
                                except ProviderError as error:
                                    reason = str(error)
                                else:
                                    # Failed batch rolls back; earlier checkpoints survive.
                                    vector = validate_vector(embedder.embed(features))
                                    session.add(
                                        DecisionEmbedding(
                                            decision_id=decision.id,
                                            version_id=run.version_id,
                                            **{k: features[k] for k in COMPATIBILITY},
                                            embedding=vector,
                                            features=features,
                                            feature_hash=digest(features),
                                            input_hash=digest(features),
                                            vector_hash=vector_hash(vector),
                                        )
                                    )
                            session.add(
                                IndexItem(
                                    version_id=run.version_id,
                                    decision_id=decision.id,
                                    reason=reason,
                                )
                            )
                            run.processed += 1
                            run.indexed += reason == "INDEXED"
                            run.skipped += reason != "INDEXED"
                            run.last_decision_id = decision.id
                        session.commit()
                        batches += 1
                        if max_batches is not None and batches >= max_batches:
                            break
            except Exception:
                # Sanitized durable failure, no input/SQL/provider exception text in audit/logs.
                connection.rollback()
                with Session(bind=connection) as failed:
                    row = failed.get(IndexRun, identifier)
                    if row and row.status in {"QUEUED", "PROCESSING"}:
                        row.status = "FAILED"
                        row.error_code = "INDEXING_FAILED"
                        audit(
                            failed,
                            row.version_id,
                            "BACKFILL_FAILED",
                            run_id=str(row.id),
                            error_code=row.error_code,
                        )
                        failed.commit()
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                connection.commit()
    finally:
        engine.dispose()


def recover_indexes(settings: Settings, redis: Redis) -> None:
    if not permitted(settings):
        return
    engine = make_engine(settings)
    try:
        with Session(engine) as session:
            if settings.similarity_autoindex:
                state = session.get(RetrievalState, 1)
                version = (
                    session.get(RetrievalVersion, state.active_version_id)
                    if state and state.active_version_id
                    else None
                )
                selected_provider = (
                    "qwen-local-demo"
                    if settings.similarity_provider == "qwen-demo"
                    else "deterministic-test"
                )
                if (
                    version
                    and version.config.get("provider") == selected_provider
                    and session.scalar(missing(version.id).with_only_columns(Decision.id).limit(1))
                ):
                    try:
                        revision = revision_name(version.config["revision"])
                    except ProviderError:
                        revision = None
                    if revision:
                        start_run(
                            session,
                            settings,
                            revision,
                            batch_size=8 if settings.similarity_provider == "qwen-demo" else 100,
                        )
                        session.commit()
            queue = Queue(inference_queue(settings), connection=redis)
            for run in session.scalars(
                select(IndexRun).where(IndexRun.status.in_(["NEW", "QUEUED", "PROCESSING"]))
            ):
                version = session.get(RetrievalVersion, run.version_id)
                selected_provider = (
                    "qwen-local-demo"
                    if settings.similarity_provider == "qwen-demo"
                    else "deterministic-test"
                )
                if version is None or version.config.get("provider") != selected_provider:
                    continue
                if not session.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:key)"),
                    {
                        "key": lock_key(
                            run.version_id, session.scalar(text("SELECT current_schema()"))
                        )
                    },
                ):
                    session.rollback()
                    continue
                if run.status == "NEW":
                    run.status = "QUEUED"
                    audit(session, run.version_id, "BACKFILL_QUEUED", run_id=str(run.id))
                    session.commit()
                job_id = "retrieval-" + run.id.hex
                job = Job.fetch_many([job_id], connection=redis)[0]
                if job and job.get_status(refresh=True) in {
                    "queued",
                    "deferred",
                    "scheduled",
                }:
                    continue
                if job and settings.similarity_provider != "qwen-demo":
                    job.delete()
                if settings.similarity_provider == "qwen-demo":
                    try:
                        enqueue_bounded(
                            redis,
                            settings,
                            queue,
                            process_index,
                            (str(run.id),),
                            {},
                            job_id=job_id,
                            actor_id=None,
                            description="QWEN_BOUNDED_BACKFILL",
                        )
                    except AIError:
                        continue
                    session.commit()
                    continue
                queue.enqueue(
                    process_index,
                    str(run.id),
                    job_id=job_id,
                    job_timeout=settings.import_job_timeout,
                    result_ttl=86400,
                )
                session.commit()
    finally:
        engine.dispose()
