"""Re-evaluate real, prepared Stage 4 capacity history with the current Conflict Engine.

The caller owns the disposable auth_test schema. Source facts are reused read-only;
new users, sessions and execution/output facts belong to this probe. Hold DDL read
locks while running so an originating benchmark can safely wait to clean its schema.
"""

import argparse
import json
import math
import os
import platform
import re
import resource
import secrets
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis import Redis
from rq import Queue
from rq.job import Job
from sqlalchemy import delete, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.config import Settings
from app.common.database import make_engine
from app.conflicts.jobs import execute_conflict
from app.conflicts.models import Conflict, ConflictOutput
from app.main import create_app
from app.matching.models import MatchingRun
from app.normalization.models import EntityValue


def run(schema, matching_id, count):
    if os.getenv("FK_TEST_INTEGRATION") != "1" or not re.fullmatch(
        r"auth_test_[a-f0-9]{32}", schema
    ):
        raise SystemExit("Explicit disposable test schema and FK_TEST_INTEGRATION=1 required")
    base = Settings()
    url = (
        make_url(base.database_url.get_secret_value())
        .update_query_dict({"options": "-csearch_path=" + schema})
        .render_as_string(hide_password=False)
    )
    settings = base.model_copy(
        update={
            "database_url": SecretStr(url),
            "import_queue_name": "conflict-retest-" + uuid4().hex,
        }
    )
    engine = make_engine(settings)
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    queue = Queue(settings.import_queue_name, connection=redis)
    user_ids = []
    with engine.connect() as guard:
        tables = inspect(guard).get_table_names(schema=schema)
        preparer = engine.dialect.identifier_preparer
        qualified = ",".join(
            preparer.quote_schema(schema) + "." + preparer.quote(table) for table in tables
        )
        guard.execute(text("LOCK TABLE " + qualified + " IN ACCESS SHARE MODE"))
        try:
            tokens = []
            with Session(engine) as session:
                matching = session.get(MatchingRun, matching_id)
                assert matching and matching.status == "COMPLETED"
                assert (
                    matching.records_processed == count
                    and matching.status_counts["MATCHED"] == count
                )
                assert len(matching.input_analysis_ids) == 2
                assert all(
                    item["records"] == count for item in matching.input_context["normalization"]
                )
                password_hash = hash_password(secrets.token_urlsafe(24))
                for index in range(10):
                    user = User(
                        login="retest_" + uuid4().hex,
                        full_name="Synthetic capacity retest",
                        password_hash=password_hash,
                        roles=[UserRole(role_code="DATA_OWNER" if index == 0 else "VIEWER")],
                    )
                    session.add(user)
                    session.flush()
                    user_ids.append(user.id)
                    token = secrets.token_urlsafe(32)
                    tokens.append(token)
                    session.add(
                        AuthSession(
                            token_hash=token_digest(token),
                            user_id=user.id,
                            created_at=datetime.now(UTC),
                            expires_at=datetime.now(UTC) + timedelta(hours=2),
                        )
                    )
                session.commit()
            started = time.monotonic()
            with TestClient(
                create_app(settings=settings), base_url="https://localhost:8443"
            ) as client:
                client.cookies.set(COOKIE_NAME, tokens[0])
                response = client.post(
                    "/api/v1/conflict-runs",
                    headers={"Origin": "https://localhost:8443"},
                    json={"matching_run_id": str(matching_id)},
                )
                assert response.status_code == 201, response.text
                identifier = UUID(response.json()["id"])
                execute_conflict(identifier, settings)
                result = client.get("/api/v1/conflict-runs/" + str(identifier)).json()
                seconds = time.monotonic() - started
                assert result["status"] == "COMPLETED", result
                assert result["records_processed"] == count
                assert result["attributes_evaluated"] == count * 30
                assert result["conflicts_generated"] == count // 10 + count // 20
                with Session(engine) as session:
                    actual = set(
                        session.execute(
                            select(
                                EntityValue.normalized_value,
                                Conflict.attribute_code,
                                Conflict.conflict_type,
                            )
                            .join(Conflict, Conflict.entity_id == EntityValue.entity_id)
                            .join(ConflictOutput, ConflictOutput.conflict_id == Conflict.id)
                            .where(
                                ConflictOutput.run_id == identifier,
                                EntityValue.attribute_code == "id",
                            )
                        ).all()
                    )
                    expected = {
                        (f"{i:08}", "attribute_29", "VALUE_MISMATCH") for i in range(0, count, 10)
                    }
                    expected |= {
                        (f"{i:08}", "attribute_28", "MISSING") for i in range(0, count, 20)
                    }
                    assert actual == expected
                    example = session.scalar(
                        select(ConflictOutput.conflict_id)
                        .where(ConflictOutput.run_id == identifier)
                        .limit(1)
                    )
                paths = [
                    "/api/v1/conflicts/" + str(example),
                    "/api/v1/conflicts?limit=50&matching_run_id=" + str(matching_id),
                ]

                def read(token):
                    timings = []
                    with TestClient(
                        create_app(settings=settings), base_url="https://localhost:8443"
                    ) as reader:
                        reader.cookies.set(COOKIE_NAME, token)
                        for index in range(10):
                            before = time.monotonic()
                            assert reader.get(paths[index % 2]).status_code == 200
                            timings.append(time.monotonic() - before)
                    return timings

                with ThreadPoolExecutor(10) as pool:
                    timings = sorted(value for batch in pool.map(read, tokens) for value in batch)
                p95 = timings[math.ceil(len(timings) * 0.95) - 1]
                assert p95 <= 1
                return {
                    "commit": subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], text=True
                    ).strip(),
                    "environment": {
                        "python": platform.python_version(),
                        "os": platform.platform(),
                        "execution": (
                            "host Python; current engine on existing real "
                            "Import/Normalization/Matching history; "
                            "separate technical execution; DDL guard"
                        ),
                    },
                    "records_per_dataset": count,
                    "source_datasets": 2,
                    "attributes_per_record": 30,
                    "matching_run_id": str(matching_id),
                    "reused_stage2_4_history": True,
                    "matched_identities_processed": result["records_processed"],
                    "attributes_evaluated": result["attributes_evaluated"],
                    "conflicts_generated": result["conflicts_generated"],
                    "type_breakdown": result["status_counts"],
                    "true_conflicts": len(actual & expected),
                    "false_conflicts": len(actual - expected),
                    "missed_conflicts": len(expected - actual),
                    "conflict_seconds": round(seconds, 3),
                    "metadata_sessions": 10,
                    "metadata_p95_seconds": round(p95, 4),
                    "process_peak_rss_mib": round(
                        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
                    ),
                    "passed": True,
                }
        finally:
            ids = queue.get_job_ids()
            for registry in [queue.finished_job_registry, queue.failed_job_registry]:
                ids += registry.get_job_ids()
            for identifier in set(ids):
                job = Job.fetch_many([identifier], connection=redis)[0]
                if job:
                    job.delete()
            queue.delete(delete_jobs=True)
            redis.close()
            with Session(engine) as session:
                session.execute(delete(User).where(User.id.in_(user_ids)))
                session.commit()
            guard.rollback()
            engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--matching-run", type=UUID, required=True)
    parser.add_argument("--records", type=int, choices=[100, 1000, 10000, 100000], required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.schema, args.matching_run, args.records), indent=2))
