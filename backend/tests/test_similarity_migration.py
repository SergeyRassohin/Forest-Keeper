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
    pytest.mark.skipif(os.getenv("FK_TEST_INTEGRATION") != "1", reason="owned empty schema only"),
]


def test_empty_upgrade_downgrade_and_transactional_retry(bootstrap_env):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = make_engine(bootstrap_env)
    with patch.dict(os.environ, {"FK_DATABASE_URL": bootstrap_env.database_url.get_secret_value()}):
        command.downgrade(config, "0007_decisions")
        from alembic.operations import Operations

        original = Operations.execute

        def interrupt(self, sql, *args, **kwargs):
            result = original(self, sql, *args, **kwargs)
            if "CREATE TABLE decision_embeddings" in str(sql):
                raise RuntimeError("simulated interrupted migration")
            return result

        with patch.object(Operations, "execute", interrupt), pytest.raises(RuntimeError):
            command.upgrade(config, "head")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0007_decisions"
            )
            assert connection.scalar(text("SELECT to_regclass('decision_embeddings')")) is None
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        command.downgrade(config, "0007_decisions")
        command.upgrade(config, "head")
    engine.dispose()


def test_extension_in_wrong_schema_blocks_then_retry_succeeds(bootstrap_env):
    from uuid import uuid4

    from pydantic import SecretStr
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import DBAPIError

    database = "fk_stage7_vector_" + uuid4().hex
    admin = make_engine(bootstrap_env)
    url = (
        make_url(bootstrap_env.database_url.get_secret_value())
        .difference_update_query(["options"])
        .set(database=database)
        .render_as_string(hide_password=False)
    )
    settings = bootstrap_env.model_copy(update={"database_url": SecretStr(url)})
    target = None
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text('CREATE DATABASE "' + database + '"'))
        target = make_engine(settings)
        with patch.dict(os.environ, {"FK_DATABASE_URL": url}):
            command.upgrade(config, "0007_decisions")
            with target.begin() as connection:
                connection.execute(text("CREATE SCHEMA displaced_vector"))
                connection.execute(text("ALTER EXTENSION vector SET SCHEMA displaced_vector"))
            with pytest.raises(DBAPIError, match="Required public pgvector"):
                command.upgrade(config, "head")
            with target.begin() as connection:
                assert (
                    connection.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0007_decisions"
                )
                connection.execute(text("ALTER EXTENSION vector SET SCHEMA public"))
            command.upgrade(config, "head")
            command.upgrade(config, "head")
    finally:
        if target:
            target.dispose()
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text('DROP DATABASE IF EXISTS "' + database + '" WITH (FORCE)'))
        admin.dispose()


def test_stage7_upgrade_preserves_populated_stage2_to_6_history(bootstrap_env, tmp_path):
    import secrets
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from redis import Redis
    from rq import Queue
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.auth.dependencies import COOKIE_NAME
    from app.auth.models import AuthSession, User, UserRole
    from app.auth.security import hash_password, token_digest
    from app.decisions.models import Decision
    from app.main import create_app
    from tests.test_decisions_integration import begin, real_case, save, selection

    settings = bootstrap_env.model_copy(
        update={"import_storage_root": tmp_path, "import_queue_name": "s7-migration-" + uuid4().hex}
    )
    engine = make_engine(settings)
    token = secrets.token_urlsafe(32)
    try:
        with Session(engine) as session:
            user = User(
                login="s7_migration_" + uuid4().hex,
                full_name="Synthetic migration reviewer",
                data_domains=["*"],
                password_hash=hash_password(secrets.token_urlsafe(24)),
                roles=[UserRole(role_code="DATA_OWNER")],
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
            session.commit()
        with TestClient(create_app(settings=settings), base_url="https://localhost:8443") as client:
            client.cookies.set(COOKIE_NAME, token)
            case = real_case(client, settings)
            receipt = save(client, case, selection(begin(client, case)))
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            with patch.dict(
                os.environ, {"FK_DATABASE_URL": settings.database_url.get_secret_value()}
            ):
                # No vectors exist: only this owned schema's derived empty tables are removed.
                command.downgrade(config, "0007_decisions")

                def history():
                    with engine.connect() as connection:
                        names = connection.scalars(
                            text(
                                "SELECT tablename FROM pg_tables WHERE schemaname=current_schema() "
                                "AND tablename NOT LIKE 'retrieval_%' "
                                "AND tablename NOT IN ('decision_embeddings','alembic_version')"
                            )
                        ).all()
                        return {
                            name: connection.scalar(
                                text(
                                    "SELECT md5(coalesce(jsonb_agg(to_jsonb(t) "
                                    "ORDER BY to_jsonb(t)::text)::text,'[]')) FROM "
                                    + engine.dialect.identifier_preparer.quote(name)
                                    + " t"
                                )
                            )
                            for name in names
                        }

                before = history()
                command.upgrade(config, "head")
                command.upgrade(config, "head")
                assert history() == before
            detail = client.get("/api/v1/decisions/" + receipt["decision_id"])
            assert detail.status_code == 200 and detail.json()["reason"]
            assert client.get(f"/api/v1/conflicts/{case}").json()["status"] == "RESOLVED"
            with Session(engine) as session:
                assert len(session.scalars(select(Decision)).all()) == 1
    finally:
        with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
            Queue(settings.import_queue_name, connection=redis).delete(delete_jobs=True)
        engine.dispose()
