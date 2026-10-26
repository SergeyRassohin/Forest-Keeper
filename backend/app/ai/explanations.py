"""Ephemeral actor/session-bound explanation jobs; no business Decision writes."""

import time
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, ValidationError
from redis import Redis
from rq import get_current_job
from rq.job import Job
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.ai.admission import prefix, release_current
from app.ai.authorization import actor_case
from app.ai.contracts import (
    AIError,
    Digest,
    Explanation,
    Facts,
    ModelInfo,
    StrictModel,
    validate_explanation,
)
from app.ai.facts import collect
from app.ai.identity import expected_model_info
from app.ai.transport import LocalLLM, verify_model_info
from app.auth.models import AuditEvent
from app.common.basis_lock import Budget
from app.common.config import Settings
from app.common.database import make_engine
from app.decisions.service import digest


class StartRequest(StrictModel):
    request_id: UUID
    language: Literal["ru", "en"] = "ru"


class RequestRecord(StrictModel):
    handle: UUID
    actor_id: UUID
    session_hash: Digest
    conflict_id: UUID
    request_id: UUID
    language: Literal["ru", "en"]
    context_fingerprint: Digest
    model_hash: Digest
    expires_at: Annotated[float, Field(allow_inf_nan=False)]


class Stored(StrictModel):
    state: Literal["PROCESSING", "COMPLETED", "FAILED"]
    reason_code: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")] | None = None
    explanation: Explanation | None = None
    model: ModelInfo | None = None


def enabled(settings: Settings) -> bool:
    return settings.ai_enabled and settings.deployment_mode in {"development", "test"}


def handle_for(
    actor_id: UUID, session_hash: str, conflict_id: UUID, request_id: UUID, settings: Settings
) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "forest-keeper:ai:"
        + digest(
            [
                prefix(settings),
                str(actor_id),
                session_hash,
                str(conflict_id),
                str(request_id),
            ]
        ),
    )


def job_id(handle: UUID, settings: Settings) -> str:
    return "ai-explain-" + digest(prefix(settings))[:12] + "-" + handle.hex


def result_key(handle: UUID, settings: Settings) -> str:
    return prefix(settings) + ":explanation:" + handle.hex


def cancel_key(handle: UUID, settings: Settings) -> str:
    return prefix(settings) + ":cancel:" + handle.hex


def record_from(job: Job, handle: UUID, settings: Settings) -> RequestRecord:
    try:
        record = RequestRecord.model_validate(job.meta["request_record"])
        if (
            record.handle != handle
            or record.expires_at <= time.time()
            or (
                handle_for(
                    record.actor_id,
                    record.session_hash,
                    record.conflict_id,
                    record.request_id,
                    settings,
                )
                != handle
            )
        ):
            raise AIError("AI_REQUEST_UNAVAILABLE")
        return record
    except (ValidationError, KeyError):
        raise AIError("AI_REQUEST_UNAVAILABLE") from None


def snapshot(
    engine: Engine, settings: Settings, record: RequestRecord, budget: Budget | None = None
) -> Facts:
    with Session(engine) as session:
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        session.execute(text("SET TRANSACTION READ ONLY"))
        budget = budget or Budget()
        budget.arm(session)
        actor, case = actor_case(
            session, str(record.actor_id), record.session_hash, record.conflict_id
        )
        facts = collect(session, actor, case, settings, budget)
        if facts.context_fingerprint != record.context_fingerprint or (
            record.model_hash != digest(expected_model_info("llm").model_dump(mode="json"))
        ):
            raise AIError("AI_CONTEXT_STALE")
        return facts


def store(redis: Redis, settings: Settings, record: RequestRecord, result: Stored) -> None:
    raw = result.model_dump_json()
    if len(raw.encode()) > 65536:
        raise AIError("AI_OUTPUT_TOO_LARGE")
    remaining = max(1, int(record.expires_at - time.time()))
    redis.eval(
        "if redis.call('exists',KEYS[2]) == 0 then "
        "return redis.call('set',KEYS[1],ARGV[1],'EX',ARGV[2]) end; return 0",
        2,
        result_key(record.handle, settings),
        cancel_key(record.handle, settings),
        raw,
        remaining,
    )


def generate(handle_text: str) -> None:
    settings = Settings()  # type: ignore[call-arg]
    current_job = get_current_job()
    if current_job is None:
        return
    engine = make_engine(settings)
    record = None
    started = time.monotonic()
    redis = current_job.connection
    try:
        handle = UUID(handle_text)
        record = record_from(current_job, handle, settings)
        if not enabled(settings):
            raise AIError("AI_UNAVAILABLE")
        if redis.exists(cancel_key(handle, settings)):
            return
        facts = snapshot(engine, settings, record)
        store(redis, settings, record, Stored(state="PROCESSING"))
        # Both database snapshot/connection and all SQL locks have ended before inference.
        output = LocalLLM(settings.ai_llm_endpoint, settings.ai_service_key_file).explain(facts)
        if redis.exists(cancel_key(handle, settings)):
            return
        fresh = snapshot(engine, settings, record)
        validate_explanation(output, fresh)
        model = expected_model_info("llm")
        verify_model_info(
            model, "llm"
        )  # LocalLLM independently verified the identical returned identity.
        with Session(engine) as audit:
            audit.add(
                AuditEvent(
                    event_type="AI_EXPLANATION_EVALUATED",
                    object_type="AIExplanation",
                    object_id=handle,
                    user_id=record.actor_id,
                    payload={
                        "input_hash": facts.context_fingerprint,
                        "output_hash": digest(output.model_dump(mode="json")),
                        "model_hash": record.model_hash,
                        "model_revision": model.revision,
                        "prompt_version": model.prompt_version,
                        "prompt_hash": model.prompt_sha256,
                        "clauses": [item.code.value for item in output.clauses],
                        "cited_decisions": [
                            str(value) for item in output.clauses for value in item.decision_ids
                        ],
                        "duration_ms": int((time.monotonic() - started) * 1000),
                    },
                )
            )
            audit.commit()
        store(redis, settings, record, Stored(state="COMPLETED", explanation=output, model=model))
    except Exception as error:
        if record is not None:
            reason = str(error) if isinstance(error, AIError) else "EXPLANATION_UNAVAILABLE"
            try:
                store(redis, settings, record, Stored(state="FAILED", reason_code=reason))
            except Exception:
                # No prompt/SQL/connection error is emitted; expired jobs degrade on poll.
                return
    finally:
        engine.dispose()
        release_current(settings)


def read_stored(redis: Redis, settings: Settings, handle: UUID) -> Stored | None:
    raw = redis.get(result_key(handle, settings))
    if raw is None:
        return None
    try:
        if not isinstance(raw, (str, bytes)) or len(raw) > 65536:
            raise AIError("AI_RESULT_INVALID")
        return Stored.model_validate_json(raw)
    except (ValidationError, ValueError):
        raise AIError("AI_RESULT_INVALID") from None
