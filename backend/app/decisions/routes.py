"""Cookie-authenticated human review and read-only Decision Registry endpoints."""

import logging
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, aliased, defer

from app.auth.dependencies import Config, Db, current_user
from app.auth.models import AuditEvent, User
from app.common.errors import ApiError
from app.decisions.models import Decision, DecisionStatus, DecisionType
from app.decisions.schemas import BeginReview, CreateDecision
from app.decisions.service import (
    begin_review,
    case_for,
    decision_view,
    require,
    review_context,
    save_decision,
    successor_id,
)

router = APIRouter(prefix="/api/v1", tags=["human-review", "decisions"])
logger = logging.getLogger(__name__)
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1_000_000)]


def record_rejection(request: Request, event: str, code: str, status: int) -> None:
    """A failed business transaction is rolled back before this independent sanitized audit."""
    identifier = request.path_params.get("conflict_id") or request.path_params.get("decision_id")
    try:
        object_id = UUID(str(identifier)) if identifier else None
    except ValueError:
        object_id = None
    request_id = getattr(request.state, "decision_request_id", uuid4())
    try:
        with Session(request.app.state.engine) as audit_session:
            audit_session.add(
                AuditEvent(
                    event_type=event,
                    user_id=getattr(request.state, "decision_actor_id", None),
                    object_type="DecisionReview",
                    object_id=object_id,
                    payload={
                        "request_id": str(request_id),
                        "reason_code": code,
                        "http_status": status,
                    },
                )
            )
            audit_session.commit()
    except SQLAlchemyError:
        # No raw input, selected/corrected values, credentials or database exception text.
        logger.warning("decision_audit_unavailable request_id=%s reason_code=%s", request_id, code)


def reject_invalid_request(request: Request) -> None:
    record_rejection(request, "DECISION_REQUEST_REJECTED", "INVALID_REQUEST", 422)


def authenticated(request: Request, session: Db, settings: Config) -> User:
    request.state.decision_request_id = uuid4()
    try:
        actor = current_user(request, session, settings)
    except ApiError as error:
        session.rollback()
        record_rejection(request, "DECISION_AUTHORIZATION_DENIED", error.code, error.status)
        raise
    except SQLAlchemyError:
        session.rollback()
        raise ApiError(503, "REVIEW_UNAVAILABLE", "Сервис решений временно недоступен") from None
    request.state.decision_actor_id = actor.id
    return actor


Actor = Annotated[User, Depends(authenticated)]


def access(actor: User, permission: str, request: Request, session: Session) -> None:
    try:
        require(actor, permission)
    except ApiError as error:
        session.rollback()
        record_rejection(request, "DECISION_AUTHORIZATION_DENIED", error.code, error.status)
        raise


def failed(request: Request, session: Session, error: Exception) -> ApiError:
    session.rollback()
    if isinstance(error, ApiError):
        code, status = error.code, error.status
        result = error
    else:
        code, status = "REVIEW_UNAVAILABLE", 503
        result = ApiError(status, code, "Сохранение не подтверждено. Повторите ту же отправку")
    event = "DECISION_AUTHORIZATION_DENIED" if status == 403 else "DECISION_REQUEST_REJECTED"
    record_rejection(request, event, code, status)
    return result


@router.get("/conflicts/{conflict_id}/review-context")
def context(conflict_id: UUID, request: Request, session: Db, actor: Actor) -> dict[str, Any]:
    access(actor, "conflict.view", request, session)
    access(actor, "decision.view", request, session)
    try:
        return review_context(session, case_for(session, conflict_id, actor), actor)
    except (ApiError, SQLAlchemyError) as error:
        raise failed(request, session, error) from None


@router.post("/conflicts/{conflict_id}/review")
def start(
    conflict_id: UUID,
    body: BeginReview,
    request: Request,
    response: Response,
    session: Db,
    actor: Actor,
) -> dict[str, Any]:
    access(actor, "conflict.review.start", request, session)
    try:
        result = begin_review(
            session,
            case_for(session, conflict_id, actor, lock=True),
            actor,
            body,
            request.state.decision_request_id,
        )
        response.headers["X-Request-ID"] = str(request.state.decision_request_id)
        return result
    except (ApiError, SQLAlchemyError) as error:
        raise failed(request, session, error) from None


@router.post("/conflicts/{conflict_id}/decisions", status_code=201)
def create(
    conflict_id: UUID,
    body: CreateDecision,
    request: Request,
    response: Response,
    session: Db,
    actor: Actor,
) -> dict[str, Any]:
    access(actor, "decision.create", request, session)
    try:
        result, created = save_decision(
            session,
            case_for(session, conflict_id, actor, lock=True),
            actor,
            body,
            request.state.decision_request_id,
        )
        response.status_code = 201 if created else 200
        response.headers["X-Request-ID"] = str(request.state.decision_request_id)
        return result
    except (ApiError, SQLAlchemyError) as error:
        raise failed(request, session, error) from None


@router.get("/decisions/{decision_id}")
def detail(decision_id: UUID, request: Request, session: Db, actor: Actor) -> dict[str, Any]:
    access(actor, "decision.view", request, session)
    query = select(Decision).where(Decision.id == decision_id)
    if "*" not in (actor.data_domains or []):
        query = query.where(Decision.domain.in_(actor.data_domains or []))
    row = session.scalar(query)
    if row is None:
        record_rejection(request, "DECISION_ACCESS_DENIED", "DECISION_NOT_FOUND", 404)
        raise ApiError(404, "DECISION_NOT_FOUND", "Решение не найдено или недоступно")
    return decision_view(row, successor_id(session, row), detail=True)


@router.get("/decisions")
def registry(
    request: Request,
    session: Db,
    actor: Actor,
    limit: Limit = 50,
    offset: Offset = 0,
    conflict_id: UUID | None = None,
    entity_id: UUID | None = None,
    attribute_code: str | None = Query(default=None, max_length=64),
    business_key: str | None = Query(default=None, max_length=256),
    user_id: UUID | None = None,
    decision_type: DecisionType | None = None,
    status: DecisionStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[dict[str, Any]]:
    access(actor, "decision.view", request, session)
    successor = aliased(Decision)
    query = (
        select(Decision, successor.id)
        .outerjoin(successor, successor.supersedes_decision_id == Decision.id)
        .options(
            defer(Decision.context_snapshot),
            defer(Decision.corrected_input),
            defer(Decision.conversion_trace),
        )
    )
    if "*" not in (actor.data_domains or []):
        query = query.where(Decision.domain.in_(actor.data_domains or []))
    for field, value in [
        (Decision.conflict_id, conflict_id),
        (Decision.entity_id, entity_id),
        (Decision.attribute_code, attribute_code),
        (Decision.user_id, user_id),
        (Decision.decision_type, decision_type),
        (Decision.business_key, business_key),
    ]:
        if value is not None:
            query = query.where(field == value)
    for instant in [date_from, date_to]:
        if instant is not None and instant.tzinfo is None:
            raise ApiError(422, "TIMEZONE_REQUIRED", "Укажите часовой пояс даты фильтра")
    if date_from and date_to and date_from > date_to:
        raise ApiError(422, "INVALID_DATE_RANGE", "Начальная дата позже конечной")
    if date_from:
        query = query.where(Decision.decided_at >= date_from)
    if date_to:
        query = query.where(Decision.decided_at <= date_to)
    if status:
        query = query.where(
            successor.id.is_(None) if status == DecisionStatus.ACTIVE else successor.id.is_not(None)
        )
    return [
        decision_view(row, child)
        for row, child in session.execute(
            query.order_by(Decision.decided_at.desc(), Decision.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/conflicts/{conflict_id}/decisions")
def history(
    conflict_id: UUID,
    request: Request,
    session: Db,
    actor: Actor,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[dict[str, Any]]:
    access(actor, "decision.view", request, session)
    access(actor, "conflict.view", request, session)
    case_for(session, conflict_id, actor)
    successor = aliased(Decision)
    query = (
        select(Decision, successor.id)
        .outerjoin(successor, successor.supersedes_decision_id == Decision.id)
        .options(
            defer(Decision.context_snapshot),
            defer(Decision.corrected_input),
            defer(Decision.conversion_trace),
        )
        .where(Decision.conflict_id == conflict_id)
        .order_by(Decision.decided_at, Decision.id)
    )
    return [
        decision_view(row, child)
        for row, child in session.execute(query.offset(offset).limit(limit))
    ]
