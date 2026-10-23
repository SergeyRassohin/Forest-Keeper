import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.auth.dependencies import Cache, Config, Db
from app.auth.models import User
from app.common.errors import ApiError
from app.decisions.routes import access, authenticated, record_rejection
from app.decisions.service import case_for
from app.similarity.service import retrieval

router = APIRouter(prefix="/api/v1", tags=["similarity"])


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=5, ge=1, le=20)
    offset: int = Field(default=0, ge=0, le=100)


def snapshot_actor(request: Request, session: Db, settings: Config) -> User:
    # Establish the snapshot before authentication and every later retrieval SELECT.
    session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
    session.execute(text("SET TRANSACTION READ ONLY"))
    session.execute(text("SET LOCAL statement_timeout = '750ms'"))
    return authenticated(request, session, settings)


SnapshotActor = Annotated[User, Depends(snapshot_actor)]


@router.get("/conflicts/{conflict_id}/similar-decisions")
def similar(
    conflict_id: UUID,
    request: Request,
    session: Db,
    settings: Config,
    actor: SnapshotActor,
    cache: Cache,
    query: Annotated[RetrievalQuery, Query()],
) -> dict[str, Any]:
    try:
        access(actor, "conflict.view", request, session)
        access(actor, "decision.view", request, session)
        try:
            key = (
                settings.auth_rate_prefix
                + "similarity:"
                + str(actor.id)
                + ":"
                + str(int(time.time() // 60))
            )
            with cache.pipeline() as pipeline:
                pipeline.incr(key)
                pipeline.expire(key, 120, nx=True)
                count, _ = pipeline.execute()
            if count > settings.similarity_reads_per_minute:
                raise ApiError(
                    429, "RETRIEVAL_RATE_LIMITED", "Слишком много запросов поиска. Повторите позже"
                )
        except RedisError:
            raise ApiError(503, "RETRIEVAL_UNAVAILABLE", "Поиск временно недоступен") from None
        return retrieval(
            session,
            actor,
            case_for(session, conflict_id, actor),
            settings,
            query.limit,
            query.offset,
        )
    except ApiError as error:
        session.rollback()
        record_rejection(request, "RETRIEVAL_ACCESS_DENIED", error.code, error.status)
        raise
    except SQLAlchemyError:
        session.rollback()
        raise ApiError(503, "RETRIEVAL_UNAVAILABLE", "Поиск временно недоступен") from None
