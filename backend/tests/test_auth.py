import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.auth.dependencies import cache, require_permission
from app.auth.models import AuditEvent, AuthSession, Role, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.config import Settings
from app.common.database import make_engine
from app.main import create_app
from tests.test_policy import canonical_matrix

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FK_TEST_INTEGRATION") != "1", reason="integration services opt-in"
    ),
]
ORIGIN = {"Origin": "https://localhost:8443"}
MATRIX = canonical_matrix()


def isolated_environment():
    base = Settings()
    engine = make_engine(base)
    schema = "auth_test_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    url = (
        make_url(base.database_url.get_secret_value())
        .update_query_dict({"options": "-csearch_path=" + schema})
        .render_as_string(hide_password=False)
    )
    settings = base.model_copy(
        update={
            "database_url": SecretStr(url),
            "auth_rate_prefix": schema + ":",
            "login_account_limit": 10000,
            "login_ip_limit": 10000,
        }
    )
    try:
        with patch.dict(os.environ, {"FK_DATABASE_URL": url}):
            command.upgrade(
                AlembicConfig(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head"
            )
        yield settings
    finally:
        redis = Redis.from_url(base.redis_url.get_secret_value())
        keys = list(redis.scan_iter(match=schema + ":*"))
        if keys:
            redis.delete(*keys)
        redis.close()
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


@pytest.fixture(scope="module")
def auth_env():
    yield from isolated_environment()


@pytest.fixture
def bootstrap_env():
    yield from isolated_environment()


@pytest.fixture
def client(auth_env):
    with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as value:
        yield value


@pytest.fixture(scope="module")
def password():
    return secrets.token_urlsafe(20)


@pytest.fixture(scope="module")
def role_tokens(auth_env, password):
    engine = make_engine(auth_env)
    stored = hash_password(password)
    result = {}
    try:
        with Session(engine) as session:
            for role in [*Role, "NO_ROLES"]:
                token = secrets.token_urlsafe(32)
                user = User(
                    login=str(role).lower(),
                    full_name=str(role),
                    password_hash=stored,
                    roles=[] if role == "NO_ROLES" else [UserRole(role_code=role)],
                )
                session.add(user)
                session.flush()
                session.add(
                    AuthSession(
                        token_hash=token_digest(token),
                        user_id=user.id,
                        created_at=datetime.now(UTC),
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                    )
                )
                result[str(role)] = token
            session.commit()
        return result
    finally:
        engine.dispose()


@pytest.fixture
def account(auth_env, password):
    engine = make_engine(auth_env)
    with Session(engine) as session:
        user = User(
            login="test_" + uuid4().hex,
            full_name="Test reviewer",
            password_hash=hash_password(password),
            roles=[UserRole(role_code="REVIEWER")],
        )
        session.add(user)
        session.commit()
        result = {"id": user.id, "login": user.login, "password": password}
    engine.dispose()
    return result


@pytest.mark.parametrize("permission", MATRIX)
@pytest.mark.parametrize("role", [*Role, "NO_ROLES"])
def test_each_permission_through_authenticated_backend(client, role_tokens, permission, role):
    def endpoint():
        return {"allowed": True}

    client.app.add_api_route(
        "/test/permission",
        endpoint,
        methods=["POST"],
        dependencies=[Depends(require_permission(permission))],
    )
    response = client.post(
        "/test/permission", headers={"Authorization": "Bearer " + role_tokens[str(role)]}
    )
    expected = 200 if role in MATRIX[permission] else 403
    assert response.status_code == expected


def enter(client, account):
    response = client.post(
        "/api/v1/auth/login",
        json={"login": account["login"].upper(), "password": account["password"]},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_login_cookie_token_storage_and_identity(client, account, auth_env):
    token = enter(client, account)
    assert client.get("/api/v1/auth/me").json()["roles"] == ["REVIEWER"]
    assert client.get("/api/v1/auth/me").headers["cache-control"] == "no-store"
    cookie = client.cookies.get("__Host-fk_session")
    assert cookie == token
    engine = make_engine(auth_env)
    with Session(engine) as session:
        assert session.get(AuthSession, token) is None
        assert session.get(AuthSession, token_digest(token)) is not None
        stored = session.get(User, account["id"]).password_hash
        assert stored.startswith("$argon2id$") and account["password"] not in stored
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.user_id == account["id"])
        ).all()
        assert any(event.event_type == "AUTH_LOGIN" for event in events)
        assert token not in str([event.payload for event in events])
        assert account["password"] not in str([event.payload for event in events])
    engine.dispose()


def test_cookie_attributes(client, account):
    response = client.post("/api/v1/auth/login", json=account_payload(account), headers=ORIGIN)
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    assert "path=/" in cookie and "domain=" not in cookie


def account_payload(account):
    return {"login": account["login"], "password": account["password"]}


def test_invalid_credentials_are_generic(client, account):
    body = account_payload(account)
    body["password"] = secrets.token_urlsafe(20)
    wrong = client.post("/api/v1/auth/login", json=body)
    body["login"] = uuid4().hex
    missing = client.post("/api/v1/auth/login", json=body)
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()


def test_unauthenticated_endpoints_and_forged_token(client):
    for path in ("/api/v1/auth/me", "/api/v1/dashboard", "/api/v1/users", "/api/v1/version"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer forged"}).status_code == 401
    assert client.post("/api/v1/users", json={}).status_code == 401


@pytest.mark.parametrize("status", ["BLOCKED", "DISABLED"])
def test_account_status_invalidates_login_and_existing_session(client, account, auth_env, status):
    enter(client, account)
    engine = make_engine(auth_env)
    with Session(engine) as session:
        session.get(User, account["id"]).status = status
        session.commit()
    engine.dispose()
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/login", json=account_payload(account)).status_code == 401


def test_logout_revokes_both_cookie_and_bearer(client, account):
    token = enter(client, account)
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code
        == 401
    )


def test_expired_session_is_rejected(client, account, auth_env):
    token = enter(client, account)
    engine = make_engine(auth_env)
    with Session(engine) as session:
        session.get(AuthSession, token_digest(token)).expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
        session.commit()
    engine.dispose()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_csrf_and_invalid_authorization_do_not_fall_back_to_cookie(client, account):
    enter(client, account)
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert (
        client.post("/api/v1/auth/logout", headers={"Origin": "https://evil.invalid"}).status_code
        == 403
    )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Basic invalid"}).status_code == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json=account_payload(account),
            headers={"Origin": "https://evil.invalid"},
        ).status_code
        == 403
    )


def test_admin_only_management_and_no_hash_leaks(client, role_tokens, password):
    for role in (Role.VIEWER, Role.REVIEWER, Role.DATA_OWNER):
        headers = {"Authorization": "Bearer " + role_tokens[role]}
        assert client.get("/api/v1/users", headers=headers).status_code == 403
        assert client.get("/api/v1/version", headers=headers).status_code == 403
    headers = {"Authorization": "Bearer " + role_tokens[Role.ADMIN]}
    response = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "login": "created_" + uuid4().hex,
            "full_name": "New reviewer",
            "password": password,
            "roles": ["REVIEWER", "REVIEWER"],
        },
    )
    assert response.status_code == 201
    assert response.json()["roles"] == ["REVIEWER"]
    assert "password" not in response.text
    assert "$argon2" not in client.get("/api/v1/users", headers=headers).text


def test_password_validation_never_echoes_input(client, role_tokens):
    password = secrets.token_urlsafe(150)
    response = client.post("/api/v1/auth/login", json={"login": "invalid", "password": password})
    assert response.status_code == 422 and password not in response.text
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": "Bearer " + role_tokens[Role.ADMIN]},
        json={
            "login": "invalid",
            "full_name": "Invalid",
            "password": password,
            "roles": ["SUPER_ADMIN"],
        },
    )
    assert response.status_code == 422 and password not in response.text


def test_role_changes_take_effect_without_new_login(client, account, auth_env):
    enter(client, account)
    engine = make_engine(auth_env)
    with Session(engine) as session:
        session.execute(delete(UserRole).where(UserRole.user_id == account["id"]))
        session.commit()
    engine.dispose()
    response = client.get("/api/v1/auth/me")
    assert response.json()["permissions"] == []
    assert client.get("/api/v1/dashboard").status_code == 403


def test_login_rate_limit_is_enforced(auth_env, account):
    settings = auth_env.model_copy(
        update={
            "auth_rate_prefix": auth_env.auth_rate_prefix + "limit:",
            "login_account_limit": 2,
            "login_window_seconds": 73,
        }
    )
    with TestClient(create_app(settings=settings), base_url="https://localhost:8443") as client:
        body = {"login": account["login"], "password": "incorrect"}
        assert client.post("/api/v1/auth/login", json=body).status_code == 401
        assert client.post("/api/v1/auth/login", json=body).status_code == 401
        response = client.post("/api/v1/auth/login", json=body)
        assert response.status_code == 429
        assert response.headers["retry-after"] == "73"


def test_redis_failure_does_not_bypass_login_limit(client, account):
    class Unavailable:
        def eval(self, *args):
            raise RedisError("unavailable")

    client.app.dependency_overrides[cache] = lambda: Unavailable()
    assert client.post("/api/v1/auth/login", json=account_payload(account)).status_code == 503


def test_audit_cannot_be_rewritten(client, account, auth_env):
    enter(client, account)
    engine = make_engine(auth_env)
    with Session(engine) as session:
        event = session.scalar(select(AuditEvent).where(AuditEvent.user_id == account["id"]))
        event.payload = {"changed": True}
        with pytest.raises(DBAPIError, match="append-only"):
            session.commit()
        session.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(delete(AuditEvent).where(AuditEvent.user_id == account["id"]))
        session.rollback()
    engine.dispose()


def test_bootstrap_creates_only_initial_admin_and_refuses_reentry(bootstrap_env, password, capsys):
    from io import StringIO

    from app.auth.bootstrap import main

    argv = [
        "bootstrap",
        "--login",
        "initial_admin",
        "--full-name",
        "Initial administrator",
        "--password-stdin",
    ]
    with patch.dict(os.environ, {"FK_DATABASE_URL": bootstrap_env.database_url.get_secret_value()}):
        with patch("sys.argv", argv), patch("sys.stdin", StringIO(password + "\n")):
            main()
        with patch("sys.argv", argv), patch("sys.stdin", StringIO(password + "\n")):
            with pytest.raises(SystemExit) as error:
                main()
        assert error.value.code == 1
    assert password not in str(capsys.readouterr())
    engine = make_engine(bootstrap_env)
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.login == "initial_admin"))
        assert [role.role_code for role in user.roles] == ["ADMIN"]
    engine.dispose()


def test_stale_admin_session_requires_reauthentication(client, role_tokens, auth_env, password):
    token = role_tokens[Role.ADMIN]
    engine = make_engine(auth_env)
    with Session(engine) as session:
        record = session.get(AuthSession, token_digest(token))
        original = record.created_at
        record.created_at = datetime.now(UTC) - timedelta(minutes=6)
        session.commit()
    try:
        response = client.post(
            "/api/v1/users",
            headers={"Authorization": "Bearer " + token},
            json={
                "login": "denied_" + uuid4().hex,
                "full_name": "Denied",
                "password": password,
                "roles": ["VIEWER"],
            },
        )
        assert response.status_code == 403 and response.json()["error"]["code"] == "REAUTH_REQUIRED"
    finally:
        with Session(engine) as session:
            session.get(AuthSession, token_digest(token)).created_at = original
            session.commit()
        engine.dispose()
