"""Transactional DDL recovery with an owned empty schema; no business history deletion."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.common.database import make_engine
from tests.test_auth import bootstrap_env as bootstrap_env

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("FK_TEST_INTEGRATION") != "1", reason="isolated DB opt-in"),
]


def test_interrupted_migration_rolls_back_and_repeats_safely(bootstrap_env):
    settings = bootstrap_env
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = make_engine(settings)
    try:
        with patch.dict(os.environ, {"FK_DATABASE_URL": settings.database_url.get_secret_value()}):
            command.downgrade(config, "0006_conflicts")
            with patch(
                "alembic.op.create_index",
                side_effect=RuntimeError("simulated migration interruption"),
            ):
                with pytest.raises(RuntimeError, match="migration interruption"):
                    command.upgrade(config, "head")
            with engine.begin() as connection:
                assert (
                    connection.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0006_conflicts"
                )
                assert connection.scalar(text("SELECT to_regclass('decisions')")) is None
                assert (
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM information_schema.columns "
                            "WHERE table_schema=current_schema() AND table_name='users' "
                            "AND column_name='data_domains'"
                        )
                    )
                    == 0
                )
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            with engine.begin() as connection:
                assert (
                    connection.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0008_similarity"
                )
    finally:
        engine.dispose()


def test_stage6_roundtrip_preserves_existing_open_conflict_and_legacy_access(
    bootstrap_env, tmp_path
):
    import secrets
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from redis import Redis
    from rq import Queue
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from app.auth.dependencies import COOKIE_NAME
    from app.auth.models import AuthSession, User, UserRole
    from app.auth.security import hash_password, token_digest
    from app.decisions.models import Decision
    from app.main import create_app
    from tests.test_decisions_integration import real_case

    settings = bootstrap_env.model_copy(
        update={"import_storage_root": tmp_path, "import_queue_name": "migration-" + uuid4().hex}
    )
    engine = make_engine(settings)
    token = secrets.token_urlsafe(32)
    user_id = uuid4()
    try:
        with Session(engine) as session:
            session.add(
                User(
                    id=user_id,
                    login="migration_" + uuid4().hex,
                    full_name="Migration reviewer",
                    data_domains=["*"],
                    password_hash=hash_password(secrets.token_urlsafe(24)),
                    roles=[UserRole(role_code="DATA_OWNER")],
                )
            )
            session.flush()
            session.add(
                AuthSession(
                    token_hash=token_digest(token),
                    user_id=user_id,
                    created_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            session.commit()
        with TestClient(create_app(settings=settings), base_url="https://localhost:8443") as client:
            client.cookies.set(COOKIE_NAME, token)
            identifier = real_case(client, settings)
            before = client.get(f"/api/v1/conflicts/{identifier}").json()
            assert before["status"] == "OPEN" and before["current_decision_id"] is None
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            with patch.dict(
                os.environ, {"FK_DATABASE_URL": settings.database_url.get_secret_value()}
            ):
                command.downgrade(config, "0006_conflicts")
                command.upgrade(config, "head")
                command.upgrade(config, "head")
            assert client.get(f"/api/v1/conflicts/{identifier}").json() == before
            with Session(engine) as session:
                assert session.get(User, user_id).data_domains == ["*"]
                assert session.scalar(select(func.count()).select_from(Decision)) == 0
    finally:
        redis = Redis.from_url(settings.redis_url.get_secret_value())
        Queue(settings.import_queue_name, connection=redis).delete(delete_jobs=True)
        redis.close()
        engine.dispose()
