"""Physical rewrite of valid synthetic edge artifacts; not real-model quality evidence."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.decisions.models import Decision
from app.similarity.context import context, fingerprint
from app.similarity.models import DecisionEmbedding
from app.similarity.provider import vector_hash
from app.similarity.service import start_run
from tests.test_decisions_integration import begin, real_case, save, selection
from tests.test_similarity_integration import auth_env as auth_env
from tests.test_similarity_integration import client as client
from tests.test_similarity_integration import password as password
from tests.test_similarity_integration import role_tokens as role_tokens

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("FK_TEST_INTEGRATION") != "1", reason="owned schema only"),
]


def snapshot(engine):
    """Include every logical row, vector bytes, physical policy and protections."""
    with engine.connect() as db:
        names = db.scalars(
            text("SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY 1")
        ).all()
        rows = {
            name: db.scalar(
                text(
                    "SELECT md5(coalesce(string_agg(to_jsonb(t)::text,'' "
                    "ORDER BY to_jsonb(t)::text),'')) FROM "
                    + engine.dialect.identifier_preparer.quote(name)
                    + " t"
                )
            )
            for name in names
            if name != "alembic_version"
        }
        return {
            "rows": rows,
            "vectors": db.execute(
                text(
                    "SELECT id,encode(public.vector_send(embedding),'hex') "
                    "FROM decision_embeddings ORDER BY id"
                )
            ).all(),
            "indexes": db.execute(
                text(
                    "SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=current_schema() "
                    "AND tablename='decision_embeddings' ORDER BY indexname"
                )
            ).all(),
            "constraints": db.execute(
                text(
                    "SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conrelid='decision_embeddings'::regclass ORDER BY conname"
                )
            ).all(),
            "triggers": db.execute(
                text(
                    "SELECT tgname,tgenabled,pg_get_triggerdef(oid) FROM pg_trigger "
                    "WHERE tgrelid='decision_embeddings'::regclass ORDER BY tgname"
                )
            ).all(),
            "storage": db.scalar(
                text(
                    "SELECT attstorage FROM pg_attribute "
                    "WHERE attrelid='decision_embeddings'::regclass AND attname='embedding'"
                )
            ),
            "revision": db.scalar(text("SELECT version_num FROM alembic_version")),
        }


def assert_values_preserved(before, after):
    for key in ("rows", "vectors", "indexes", "constraints", "triggers"):
        assert after[key] == before[key], key


def assert_immutable(engine):
    for operation in (
        "UPDATE decision_embeddings SET embedding=embedding",
        "DELETE FROM decision_embeddings",
    ):
        with engine.begin() as db:
            with pytest.raises(DBAPIError, match="Retrieval artifact is immutable"):
                with db.begin_nested():
                    db.execute(text(operation))


def test_populated_inline_vector_upgrade_downgrade_and_interruption_preserve_all_facts(client):
    settings = client.app.state.settings
    # Real file/import/review Decisions, explicitly synthetic storage-edge vectors.
    edges = [[1.0, -0.0, 1e-45], [3.4028235e38, -1e-45, -0.0], [1e-7, -1e-7, 1.0]]
    for _ in edges:
        case = real_case(client, settings)
        save(client, case, selection(begin(client, case)))
    engine = client.app.state.engine
    with Session(engine) as db:
        run = start_run(db, settings, "test-v1", activate=False)
        db.flush()
        decisions = db.scalars(select(Decision).order_by(Decision.id)).all()
        assert len(decisions) == len(edges)
        for row, prefix in zip(decisions, edges, strict=True):
            features = context(row.context_snapshot, row)
            values = prefix + [0.0] * 1021
            hashed = fingerprint(features)
            db.add(
                DecisionEmbedding(
                    decision_id=row.id,
                    version_id=run.version_id,
                    embedding=values,
                    features=features,
                    feature_hash=hashed,
                    input_hash=hashed,
                    vector_hash=vector_hash(values),
                    dimensions=1024,
                    **{
                        key: features[key]
                        for key in (
                            "domain",
                            "entity_type",
                            "attribute_code",
                            "conflict_type",
                            "value_kind",
                            "unit",
                        )
                    },
                )
            )
        db.commit()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with patch.dict(os.environ, {"FK_DATABASE_URL": settings.database_url.get_secret_value()}):
        original = snapshot(engine)
        assert original["storage"] == "p" and original["revision"] == "0009_inline_vectors"
        assert_immutable(engine)
        command.downgrade(config, "0008_similarity")
        old = snapshot(engine)
        assert old["storage"] == "e" and old["revision"] == "0008_similarity"
        assert_values_preserved(original, old)
        execute = Operations.execute

        def interrupted(self, sql, *args, **kwargs):
            result = execute(self, sql, *args, **kwargs)
            if "ALTER TABLE decision_embeddings" in str(sql):
                raise RuntimeError("owned physical rewrite interrupted after DDL")
            return result

        with (
            patch.object(Operations, "execute", interrupted),
            pytest.raises(RuntimeError, match="rewrite interrupted"),
        ):
            command.upgrade(config, "head")
        assert snapshot(engine) == old
        assert_immutable(engine)
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        current = snapshot(engine)
        assert current["storage"] == "p" and current["revision"] == "0009_inline_vectors"
        assert_values_preserved(old, current)
        assert_immutable(engine)
        command.downgrade(config, "0008_similarity")
        assert snapshot(engine) == old
        assert_immutable(engine)
        command.upgrade(config, "head")
        assert_values_preserved(old, snapshot(engine))
