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
