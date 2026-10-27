"""Owned-schema digest/canary checks around an operator-controlled actual DB/Redis restart."""

import json
import os
import re
import sys
from pathlib import Path

from pydantic import SecretStr
from redis import Redis
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.common.config import Settings
from app.common.database import make_engine

ROOT = Path(os.environ.get("FK_AI_REAL_REPORT_DIR", "/evidence"))
TABLES = (
    "source_systems",
    "import_batches",
    "raw_records",
    "analysis_runs",
    "canonical_entities",
    "entity_values",
    "matching_runs",
    "match_candidates",
    "conflicts",
    "decisions",
    "retrieval_versions",
    "decision_embeddings",
)


def main():
    data = json.loads(
        Path(os.environ.get("FK_AI_BROWSER_FIXTURE", "/fixture/fixture.json")).read_text()
    )
    assert data["kind"] == "owned-stage9-synthetic-browser-fixture-v1"
    assert re.fullmatch(r"auth_test_[a-f0-9]{32}", data["schema"])
    assert re.fullmatch(r"stage9-ai-browser-[a-f0-9]{32}", data["import_queue_name"])
    base = Settings()
    base_url = make_url(base.database_url.get_secret_value())
    fixture_url = make_url(data["database_url"])
    # An owned schema must stay on this operator-selected database, not merely
    # any database/port on the same host. Do not expose either URI in errors.
    assert all(
        getattr(base_url, field) == getattr(fixture_url, field)
        for field in ("drivername", "host", "port", "database", "username")
    )
    assert data["auth_rate_prefix"] == data["schema"] + ":"
    # Keep the existing typed secret wrapper; never print a URI or credential.
    settings = base.model_copy(update={"database_url": SecretStr(data["database_url"])})
    engine = make_engine(settings)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == data["schema"]
            snapshot = {
                name: {
                    "count": connection.scalar(text('SELECT count(*) FROM "' + name + '"')),
                    "digest": connection.scalar(
                        text(
                            "SELECT md5(coalesce(string_agg(to_jsonb(t)::text,'' "
                            "ORDER BY to_jsonb(t)::text),'')) FROM \"" + name + '" t'
                        )
                    ),
                }
                for name in TABLES
            }
            assert snapshot["decisions"]["count"] == 7
            dimensions = connection.scalar(
                text("SELECT min(public.vector_dims(embedding)) FROM decision_embeddings")
            )
            assert dimensions == 1024 and snapshot["decision_embeddings"]["count"] >= 5
        key = data["import_queue_name"] + ":restart-canary"
        with Redis.from_url(base.redis_url.get_secret_value()) as redis:
            if sys.argv[1:] == ["before"]:
                redis.set(key, "owned-stage9-restart-proof", ex=900)
                (ROOT / "stage9-restart-before.json").write_text(
                    json.dumps({"snapshot": snapshot, "dimensions": dimensions}, indent=2) + "\n"
                )
                print("Owned actual-vector/Decision snapshot and bounded Redis canary recorded.")
            elif sys.argv[1:] == ["after"]:
                before = json.loads((ROOT / "stage9-restart-before.json").read_text())
                assert snapshot == before["snapshot"]
                assert redis.get(key) == b"owned-stage9-restart-proof"
                result = {
                    "passed": True,
                    "decisions": 7,
                    "vector_dimensions": dimensions,
                    "actual_vectors_preserved": snapshot["decision_embeddings"]["count"],
                    "immutable_business_digests_preserved": True,
                    "redis_aof_canary_preserved": True,
                }
                (ROOT / "stage9-actual-db-redis-restart.json").write_text(
                    json.dumps(result, indent=2) + "\n"
                )
                redis.delete(key)
                print(
                    "Actual owned Qwen vectors, immutable Decisions and Redis restart canary PASS."
                )
            else:
                raise SystemExit("Use before or after")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
