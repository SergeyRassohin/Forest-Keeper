from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import Cache, Config, Db
from app.common.basis_lock import Budget
from app.common.errors import ApiError
from app.common.retrieval_rate import read_budget
from app.decisions.routes import access, record_rejection
from app.decisions.service import case_for
from app.recommendations.audit import record
from app.recommendations.schemas import RecommendationResult
from app.recommendations.service import evaluate
from app.similarity.routes import SnapshotActor

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


class NoOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.get("/conflicts/{conflict_id}/recommendation", response_model=RecommendationResult)
def recommendation(
    conflict_id: UUID,
    request: Request,
    session: Db,
    settings: Config,
    actor: SnapshotActor,
    cache: Cache,
    query: Annotated[NoOverrides, Query()],
) -> RecommendationResult:
    budget: Budget = request.state.retrieval_budget
    try:
        for permission in ("conflict.view", "decision.view", "recommendation.view"):
            access(actor, permission, request, session)
        read_budget(cache, settings, actor)
        budget.arm(session)
        case = case_for(session, conflict_id, actor)
        computed = evaluate(session, actor, case, settings, budget)
        actor_id = actor.id
        session.rollback()  # End the coherent read-only snapshot before safe audit telemetry.
        with Session(request.app.state.engine) as audit_session:
            return record(audit_session, computed, actor_id, budget)
    except ApiError as error:
        session.rollback()
        record_rejection(request, "RECOMMENDATION_ACCESS_DENIED", error.code, error.status)
        raise
    except SQLAlchemyError:
        session.rollback()
        raise ApiError(
            503,
            "RECOMMENDATION_UNAVAILABLE",
            "Рекомендация временно недоступна. Ручное рассмотрение доступно отдельно",
        ) from None
