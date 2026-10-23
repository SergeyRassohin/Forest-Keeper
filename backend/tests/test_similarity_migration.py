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
