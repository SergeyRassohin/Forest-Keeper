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
                    == "0007_decisions"
                )
    finally:
        engine.dispose()
