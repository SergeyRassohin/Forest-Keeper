import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import (
    COOKIE_NAME,
    Cache,
    Config,
    CurrentUser,
    Db,
    check_origin,
    require_permission,
)
from app.auth.models import AuditEvent, AuthSession, User, UserRole
from app.auth.schemas import LoginRequest, LoginResponse, UserCreate, UserView
from app.auth.security import dummy_hash, hash_password, token_digest, verify_password
from app.common.errors import ApiError

router = APIRouter(prefix="/api/v1", tags=["authentication"])
_RATE_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""


def audit(session: Db, event: str, user_id: UUID | None, object_id: UUID | None = None) -> None:
    session.add(
        AuditEvent(
            event_type=event,
            user_id=user_id,
            object_type="User",
            object_id=object_id,
            payload={},
        )
    )


@router.post("/auth/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: Db,
    settings: Config,
    redis: Cache,
) -> LoginResponse:
    check_origin(request, settings)
    name = body.login.casefold()
    ip = request.client.host if request.client else "unknown"
    try:
        for scope, identity, limit in (
            ("account", name, settings.login_account_limit),
            ("ip", ip, settings.login_ip_limit),
        ):
            key = (
                settings.auth_rate_prefix
                + scope
                + ":"
                + hashlib.sha256(identity.encode()).hexdigest()
            )
            count = cast(int, redis.eval(_RATE_SCRIPT, 1, key, settings.login_window_seconds))
            if count > limit:
                raise ApiError(429, "LOGIN_RATE_LIMITED", "Слишком много попыток. Повторите позже")
    except RedisError as error:
        raise ApiError(503, "AUTH_UNAVAILABLE", "Вход временно недоступен") from error

    user = session.scalar(select(User).where(User.login == name))
    valid = verify_password(
        body.password.get_secret_value(), user.password_hash if user else dummy_hash
    )
    if not valid or user is None or user.status != "ACTIVE":
        audit(session, "AUTH_LOGIN_DENIED", user.id if user else None)
        session.commit()
        raise ApiError(401, "INVALID_CREDENTIALS", "Неверный логин или пароль")
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    session.add(
        AuthSession(
            token_hash=token_digest(token),
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(minutes=settings.session_minutes),
        )
    )
    audit(session, "AUTH_LOGIN", user.id, user.id)
    session.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        secure=True,
        httponly=True,
        samesite="strict",
        max_age=settings.session_minutes * 60,
        path="/",
    )
    return LoginResponse(access_token=token, user=UserView.of(user))


@router.get("/auth/me", response_model=UserView)
def me(user: CurrentUser) -> UserView:
    return UserView.of(user)


@router.post("/auth/logout", status_code=204, response_class=Response)
def logout(request: Request, response: Response, user: CurrentUser, session: Db) -> None:
    record: AuthSession = request.state.auth_session
    record.revoked_at = datetime.now(UTC)
    audit(session, "AUTH_LOGOUT", user.id, user.id)
    session.commit()
    response.delete_cookie(COOKIE_NAME, secure=True, httponly=True, samesite="strict", path="/")


@router.get("/users", response_model=list[UserView])
def users(
    session: Db, user: Annotated[User, Depends(require_permission("user.view"))]
) -> list[UserView]:
    return [
        UserView.of(item) for item in session.scalars(select(User).order_by(User.login).limit(100))
    ]


@router.post(
    "/users",
    response_model=UserView,
    status_code=201,
    dependencies=[Depends(require_permission("role.assign"))],
)
def create_user(
    body: UserCreate,
    request: Request,
    session: Db,
    actor: Annotated[User, Depends(require_permission("user.manage"))],
) -> UserView:
    record: AuthSession = request.state.auth_session
    if datetime.now(UTC) - record.created_at > timedelta(minutes=5):
        raise ApiError(403, "REAUTH_REQUIRED", "Для управления пользователями войдите повторно")
    user = User(
        login=body.login,
        full_name=body.full_name,
        job_title=body.job_title,
        password_hash=hash_password(body.password.get_secret_value()),
        roles=[UserRole(role_code=role) for role in sorted(set(body.roles))],
    )
    session.add(user)
    try:
        session.flush()
        audit(session, "USER_CREATED", actor.id, user.id)
        session.add(
            AuditEvent(
                event_type="ROLES_ASSIGNED",
                user_id=actor.id,
                object_type="User",
                object_id=user.id,
                payload={"roles": sorted(set(body.roles))},
            )
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApiError(409, "LOGIN_ALREADY_EXISTS", "Этот логин уже используется") from error
    return UserView.of(user)
