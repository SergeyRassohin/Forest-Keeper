"""Explicit cookie-authenticated optional AI requests; GET never runs inference."""

import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Query, Request
from redis.exceptions import RedisError
from rq import Queue
from rq.job import Job

from app.ai.admission import enqueue_bounded, prefix
from app.ai.contracts import AIError
from app.ai.explanations import (
    RequestRecord,
    StartRequest,
    cancel_key,
    enabled,
    generate,
    handle_for,
    job_id,
    read_stored,
    record_from,
    snapshot,
)
from app.ai.facts import collect, render
from app.ai.identity import expected_model_info
from app.ai.transport import verify_model_info
from app.auth.dependencies import Cache, Config, Db
from app.auth.models import User
from app.common.errors import ApiError
from app.common.retrieval_rate import read_budget
from app.conflicts.models import Conflict
from app.decisions.routes import access
from app.decisions.service import case_for, digest
from app.recommendations.routes import NoOverrides
from app.similarity.routes import SnapshotActor

router = APIRouter(prefix="/api/v1/conflicts", tags=["local-ai"])


def authorize(request: Request, session: Db, actor: User, conflict_id: UUID) -> Conflict:
    for permission in ("conflict.view", "decision.view", "recommendation.view"):
        access(actor, permission, request, session)
    return case_for(session, conflict_id, actor)


def owned_job(
    redis: Cache,
    settings: Config,
    handle: UUID,
    conflict_id: UUID,
    actor_id: UUID,
    session_hash: str,
) -> tuple[Job, RequestRecord]:
    job = Job.fetch_many([job_id(handle, settings)], connection=redis)[0]
    try:
        if job is None:
            raise AIError("AI_REQUEST_UNAVAILABLE")
        record = record_from(job, handle, settings)
        if (
            record.actor_id != actor_id
            or record.session_hash != session_hash
            or (record.conflict_id != conflict_id)
        ):
            raise AIError("AI_REQUEST_UNAVAILABLE")
        return job, record
    except AIError:
        raise ApiError(404, "NOT_FOUND", "Объяснение не найдено") from None


@router.post("/{conflict_id}/ai-explanation", status_code=202)
def start(
    conflict_id: UUID,
    body: StartRequest,
    request: Request,
    session: Db,
    settings: Config,
    actor: SnapshotActor,
    redis: Cache,
    query: Annotated[NoOverrides, Query()],
) -> dict[str, Any]:
    case = authorize(request, session, actor, conflict_id)
    if not enabled(settings):
        raise ApiError(
            503, "AI_UNAVAILABLE", "AI-объяснение недоступно. Ручное рассмотрение работает отдельно"
        )
    try:
        read_budget(redis, settings, actor)
        session_hash = request.state.auth_session.token_hash
        handle = handle_for(actor.id, session_hash, conflict_id, body.request_id, settings)
        existing = Job.fetch_many([job_id(handle, settings)], connection=redis)[0]
        if existing is not None:
            record = record_from(existing, handle, settings)
            if record.language != body.language:
                raise ApiError(
                    409,
                    "AI_REQUEST_ID_REUSED",
                    "Для другого запроса используйте новый идентификатор",
                )
            return {"request_id": str(handle)}
        facts = collect(session, actor, case, settings, request.state.retrieval_budget)
        actor_id = actor.id
        record = RequestRecord(
            handle=handle,
            actor_id=actor_id,
            session_hash=session_hash,
            conflict_id=conflict_id,
            request_id=body.request_id,
            language=body.language,
            context_fingerprint=facts.context_fingerprint,
            model_hash=digest(expected_model_info("llm").model_dump(mode="json")),
            expires_at=time.time() + 900,
        )
        session.rollback()
        enqueue_bounded(
            redis,
            settings,
            Queue(prefix(settings) + ":llm", connection=redis),
            generate,
            (str(handle),),
            {},
            job_id=job_id(handle, settings),
            actor_id=str(actor_id),
            description="LOCAL_AI_EXPLANATION",
            request_record=record.model_dump(mode="json"),
        )
        return {"request_id": str(handle)}
    except (AIError, RedisError):
        raise ApiError(
            503,
            "EXPLANATION_UNAVAILABLE",
            "Объяснение сейчас недоступно или очередь занята. Ручное рассмотрение доступно",
        ) from None


@router.get("/{conflict_id}/ai-explanations/{handle}")
def poll(
    conflict_id: UUID,
    handle: UUID,
    request: Request,
    session: Db,
    settings: Config,
    actor: SnapshotActor,
    redis: Cache,
    query: Annotated[NoOverrides, Query()],
) -> dict[str, Any]:
    authorize(request, session, actor, conflict_id)
    try:
        read_budget(redis, settings, actor)
        job, record = owned_job(
            redis, settings, handle, conflict_id, actor.id, request.state.auth_session.token_hash
        )
        failed = {
            "request_id": str(handle),
            "state": "FAILED",
            "reason_code": "EXPLANATION_UNAVAILABLE",
        }
        if not enabled(settings):
            return failed
        if redis.exists(cancel_key(handle, settings)):
            return {**failed, "reason_code": "AI_CANCELLED"}
        if record.model_hash != digest(expected_model_info("llm").model_dump(mode="json")):
            return {**failed, "reason_code": "AI_CONTEXT_STALE"}
        stored = read_stored(redis, settings, handle)
        if stored is not None and stored.state == "COMPLETED":
            if stored.explanation is None or stored.model is None:
                return failed
            verify_model_info(stored.model, "llm")
            session.rollback()
            facts = snapshot(
                request.app.state.engine, settings, record, request.state.retrieval_budget
            )
            return {
                "request_id": str(handle),
                "state": "COMPLETED",
                "reason_code": None,
                "context_fingerprint": facts.context_fingerprint,
                "clauses": render(stored.explanation, facts, record.language),
                "model": stored.model.model_dump(mode="json"),
            }
        if stored is not None and stored.state == "FAILED":
            return {**failed, "reason_code": stored.reason_code or "EXPLANATION_UNAVAILABLE"}
        status = job.get_status(refresh=True)
        if status in {"failed", "finished", "stopped", "canceled"}:
            return failed
        return {
            "request_id": str(handle),
            "state": "PROCESSING" if status == "started" else "QUEUED",
        }
    except (AIError, RedisError):
        return {
            "request_id": str(handle),
            "state": "FAILED",
            "reason_code": "EXPLANATION_UNAVAILABLE",
        }


@router.post("/{conflict_id}/ai-explanations/{handle}/cancel")
def cancel(
    conflict_id: UUID,
    handle: UUID,
    request: Request,
    session: Db,
    settings: Config,
    actor: SnapshotActor,
    redis: Cache,
    query: Annotated[NoOverrides, Query()],
    body: Annotated[NoOverrides | None, Body()] = None,
) -> dict[str, Any]:
    authorize(request, session, actor, conflict_id)
    try:
        read_budget(redis, settings, actor)
        _, record = owned_job(
            redis, settings, handle, conflict_id, actor.id, request.state.auth_session.token_hash
        )
        redis.set(
            cancel_key(handle, settings), "1", ex=max(1, int(record.expires_at - time.time()))
        )
        return {"request_id": str(handle), "state": "FAILED", "reason_code": "AI_CANCELLED"}
    except RedisError:
        raise ApiError(
            503, "EXPLANATION_UNAVAILABLE", "Не удалось подтвердить отмену ожидания"
        ) from None
