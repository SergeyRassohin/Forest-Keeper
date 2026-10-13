from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from redis import Redis
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User, UserStatus
from app.auth.policy import permits
from app.auth.security import token_digest
from app.common.config import Settings
from app.common.errors import ApiError

COOKIE_NAME = "__Host-fk_session"


def config(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def db(request: Request) -> Iterator[Session]:
    engine: Engine = request.app.state.engine
    with Session(engine) as session:
        yield session


def cache(request: Request) -> Redis:
    connection: Redis = request.app.state.redis
    return connection


Db = Annotated[Session, Depends(db)]
Config = Annotated[Settings, Depends(config)]
Cache = Annotated[Redis, Depends(cache)]


def check_origin(request: Request, settings: Settings, *, required: bool = False) -> None:
    origin = request.headers.get("origin")
    if (required and origin is None) or (
        origin is not None and origin not in settings.allowed_origins
    ):
        raise ApiError(403, "ORIGIN_NOT_ALLOWED", "Запрос с этого сайта запрещён")


def current_user(request: Request, session: Db, settings: Config) -> User:
    authorization = request.headers.get("authorization")
    token: str | None = None
    if authorization is not None:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value and len(value) <= 256:
            token = value
    else:
        token = request.cookies.get(COOKIE_NAME)
        if token and request.method not in {"GET", "HEAD", "OPTIONS"}:
            check_origin(request, settings, required=True)
    if not token or len(token) > 256:
        raise ApiError(401, "AUTH_REQUIRED", "Необходимо войти в систему")
    record = session.get(AuthSession, token_digest(token))
    now = datetime.now(UTC)
    if record is None or record.revoked_at is not None or record.expires_at <= now:
        raise ApiError(401, "SESSION_INVALID", "Сессия истекла. Войдите снова")
    user = session.get(User, record.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise ApiError(401, "SESSION_INVALID", "Сессия недействительна")
    request.state.auth_session = record
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_permission(permission: str) -> Callable[..., User]:
    def authorized(user: CurrentUser) -> User:
        if not permits(user, permission):
            raise ApiError(403, "PERMISSION_DENIED", "Недостаточно прав для этого действия")
        return user

    return authorized
