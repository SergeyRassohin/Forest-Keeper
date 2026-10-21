import hashlib
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from redis import Redis
from rq import Queue
from rq.job import Callback, Job
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent
from app.common.config import Settings
from app.common.database import make_engine
from app.matching.engine import BlockIndex, candidates_for, evaluate, ordered_pair, pair_id
from app.matching.models import MatchCandidate, MatchingPair, MatchingRun, MatchStatus
from app.matching.profiles import MatchingProfile
from app.matching.storage import load_records
from app.normalization.jobs import TRANSITIONS
from app.normalization.models import AnalysisStatus


def lock_key(identifier: UUID) -> int:
    return int.from_bytes(
        hashlib.sha256(b"matching:" + identifier.bytes).digest()[:8], "big", signed=True
    )


def job_id(identifier: UUID) -> str:
    return "matching-" + identifier.hex


def audit(session: Session, run: MatchingRun, event: str) -> None:
    session.add(
        AuditEvent(
            event_type="MATCHING_" + event,
            user_id=run.actor_id,
            object_type="MatchingRun",
            object_id=run.id,
            payload={
                "input_analysis_ids": run.input_analysis_ids,
                "profile_hash": run.profile_hash,
                "profile_version": run.profile_snapshot["version"],
                "engine_version": run.profile_snapshot["engine_version"],
                "threshold_decision": run.profile_snapshot["threshold_decision"],
                "executor": "USER" if event == "CREATED" else "SYSTEM",
                "candidates_generated": run.candidates_generated,
                "status_counts": run.status_counts,
                "error_code": run.error_text if event == "FAILED" else None,
            },
        )
    )


def transition(session: Session, run: MatchingRun, target: AnalysisStatus) -> None:
    if target not in TRANSITIONS.get(AnalysisStatus(run.status), set()):
        raise ValueError("Forbidden matching transition")
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
            run = session.get(MatchingRun, identifier, with_for_update=True)
            if run and run.status in {AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING}:
                run.error_text = "MATCHING_INTERRUPTED"
                transition(session, run, AnalysisStatus.FAILED)
                session.commit()
    finally:
        engine.dispose()


def rq_failure(job: Job, connection: Redis, *args: Any, **kwargs: Any) -> None:
    fail_run(UUID(job.args[0]), Settings())  # type: ignore[call-arg]


def process_matching(identifier: str) -> None:
    execute_matching(UUID(identifier), Settings())  # type: ignore[call-arg]


def publish(identifier: UUID, settings: Settings, redis: Redis) -> None:
    try:
        Queue(settings.import_queue_name, connection=redis).enqueue(
            process_matching,
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
        select(MatchingRun)
        .where(MatchingRun.id == identifier)
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


def execute_matching(identifier: UUID, settings: Settings) -> None:
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
                    run = session.get(MatchingRun, identifier)
                    if run is None or run.status not in {
                        AnalysisStatus.QUEUED,
                        AnalysisStatus.PROCESSING,
                    }:
                        return
                    if run.status == AnalysisStatus.QUEUED:
                        transition(session, run, AnalysisStatus.PROCESSING)
                        session.commit()
                    profile = MatchingProfile.model_validate(run.profile_snapshot)
                    if profile.digest() != run.profile_hash:
                        raise ValueError("Matching profile fingerprint mismatch")
                    left = load_records(session, UUID(run.input_analysis_ids[0]), profile)
                    right = load_records(session, UUID(run.input_analysis_ids[1]), profile)
                    left_index, right_index = BlockIndex(left, profile), BlockIndex(right, profile)
                    degrees = Counter(
                        dict(
                            session.execute(
                                select(MatchingPair.right_record_id, func.count())
                                .where(MatchingPair.run_id == identifier)
                                .group_by(MatchingPair.right_record_id)
                            ).all()
                        )
                    )
                    diagnostics = dict(run.diagnostics)
                    diagnostics.update(
                        left_records=len(left),
                        right_records=len(right),
                        full_cartesian_pairs=len(left) * len(right),
                        oversized_left_blocks=left_index.oversized_blocks,
                        oversized_right_blocks=right_index.oversized_blocks,
                    )
                    pending = [
                        value
                        for value in sorted(left)
                        if run.last_record_id is None or value > run.last_record_id
                    ]
                    for offset in range(0, len(pending), 100):
                        chunk = pending[offset : offset + 100]
                        output, links = [], []
                        targets: dict[MatchStatus, list[UUID]] = {
                            value: [] for value in MatchStatus
                        }
                        counts = Counter(run.status_counts)
                        for raw_id in chunk:
                            record = left[raw_id]
                            candidates, omitted = candidates_for(
                                record, right, left_index, right_index, degrees, profile
                            )
                            for key, count in omitted.items():
                                diagnostics[key] = diagnostics.get(key, 0) + count
                            if not candidates:
                                diagnostics["records_without_candidates"] = (
                                    diagnostics.get("records_without_candidates", 0) + 1
                                )
                            for other, blocks in candidates:
                                confidence, status, evidence = evaluate(
                                    record, other, profile, blocks, left_index, right_index
                                )
                                candidate_id = pair_id(identifier, raw_id, other.raw_id)
                                a, b = ordered_pair(raw_id, other.raw_id)
                                evidence.update(
                                    run_id=str(identifier), input_context=run.input_context
                                )
                                output.append(
                                    {
                                        "id": candidate_id,
                                        "raw_record_a_id": a,
                                        "raw_record_b_id": b,
                                        "confidence": confidence,
                                        "evidence": evidence,
                                        "status": MatchStatus.POSSIBLE_MATCH,
                                        "confirmed_by": None,
                                    }
                                )
                                links.append(
                                    {
                                        "run_id": identifier,
                                        "candidate_id": candidate_id,
                                        "left_record_id": raw_id,
                                        "right_record_id": other.raw_id,
                                    }
                                )
                                targets[status].append(candidate_id)
                                counts[status.value] += 1
                        if output:
                            session.execute(insert(MatchCandidate).on_conflict_do_nothing(), output)
                            for status in [MatchStatus.MATCHED, MatchStatus.NOT_MATCHED]:
                                if targets[status]:
                                    session.execute(
                                        update(MatchCandidate)
                                        .where(
                                            MatchCandidate.id.in_(targets[status]),
                                            MatchCandidate.status == MatchStatus.POSSIBLE_MATCH,
                                        )
                                        .values(status=status)
                                    )
                            session.execute(insert(MatchingPair).on_conflict_do_nothing(), links)
                        run.records_processed += len(chunk)
                        run.candidates_generated += len(output)
                        run.status_counts = dict(counts)
                        run.last_record_id = chunk[-1]
                        diagnostics["coverage_limited"] = bool(
                            diagnostics.get("oversized_block_hits", 0)
                            or diagnostics.get("pairs_omitted_cap", 0)
                        )
                        diagnostics["candidate_reduction_ratio"] = str(
                            1 - run.candidates_generated / max(1, len(left) * len(right))
                        )
                        run.diagnostics = dict(diagnostics)
                        session.commit()
                    if not pending:
                        run.diagnostics = diagnostics
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
                select(MatchingRun.id)
                .where(
                    MatchingRun.status.in_(
                        [AnalysisStatus.NEW, AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING]
                    ),
                    MatchingRun.updated_at < cutoff,
                )
                .limit(1000)
            ).all()
        for identifier in identifiers:
            with Session(engine) as session:
                if not session.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key(identifier)}
                ):
                    continue
                run = session.get(MatchingRun, identifier, with_for_update=True)
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
                        run.error_text = "MATCHING_INTERRUPTED"
                        transition(session, run, AnalysisStatus.FAILED)
                        recovered += 1
                session.commit()
            if ready:
                publish(identifier, settings, redis)
    finally:
        engine.dispose()
    return recovered
