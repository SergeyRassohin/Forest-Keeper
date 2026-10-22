"""Synthetic Stage 5 oracle over real CSV/XML import/normalization/matching/conflicts."""

import json
import os
import secrets
import subprocess
import tempfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue
from rq.job import Job
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.database import make_engine
from app.conflicts.jobs import execute_conflict
from app.main import create_app
from tests.test_auth import ORIGIN, isolated_environment
from tests.test_conflicts_integration import DATA, candidates, completed, inputs, rows, start


def run():
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Opt in to isolated development tests with FK_TEST_INTEGRATION=1")
    environment = isolated_environment()
    base = next(environment)
    with tempfile.TemporaryDirectory(prefix="conflict-quality-") as folder:
        settings = base.model_copy(
            update={
                "import_storage_root": Path(folder),
                "import_queue_name": "conflict-quality-" + uuid4().hex,
            }
        )
        engine = make_engine(settings)
        redis = Redis.from_url(settings.redis_url.get_secret_value())
        queue = Queue(settings.import_queue_name, connection=redis)
        try:
            token = secrets.token_urlsafe(32)
            with Session(engine) as session:
                user = User(
                    login="synthetic-reviewer",
                    full_name="Synthetic fixture operator",
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
            with TestClient(
                create_app(settings=settings), base_url="https://localhost:8443"
            ) as client:
                client.cookies.set(COOKIE_NAME, token)
                matching = inputs(client, settings)
                first = start(client, matching)
                execute_conflict(UUID(first["id"]), settings)
                labels = json.loads((DATA / "expected.json").read_text())
                assert completed(client, first)["status_counts"] == labels["automatic"]
                reviews = 0
                for candidate in candidates(client, matching, "POSSIBLE_MATCH"):
                    detail = client.get("/api/v1/match-candidates/" + candidate["id"]).json()
                    if all(item["source_record_key"] == "DUP" for item in detail["records"]):
                        response = client.post(
                            "/api/v1/match-candidates/" + candidate["id"] + "/review",
                            headers=ORIGIN,
                            json={
                                "status": "MATCHED",
                                "reason": "Explicit synthetic duplicate identity review",
                            },
                        )
                        assert response.status_code == 200
                        reviews += 1
                assert reviews == 2
                second = start(client, matching)
                execute_conflict(UUID(second["id"]), settings)
                assert (
                    completed(client, second)["status_counts"]
                    == labels["after_explicit_duplicate_identity_review"]
                )
                result = rows(client, matching)
                actual = []
                for row in result:
                    detail = client.get("/api/v1/conflicts/" + row["id"]).json()
                    keys = {item["source_record_key"] for item in detail["values_snapshot"]}
                    assert len(keys) == 1
                    actual.append((next(iter(keys)), row["attribute_code"], row["conflict_type"]))
                allowed = {tuple(case) for case in labels["cases"]}
                false = sum(case not in allowed for case in actual)
                true = sum(case in allowed for case in actual)
                missed = 4 - true
                assert false == missed == 0 and len(actual) == 4
                return {
                    "commit": subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], text=True
                    ).strip(),
                    "true_conflicts": true,
                    "false_conflicts": false,
                    "missed_conflicts": missed,
                    "precision": 1.0,
                    "recall": 1.0,
                    "type_breakdown": dict(Counter(row["conflict_type"] for row in result)),
                    "cases": actual,
                    "explicit_duplicate_identity_reviews": reviews,
                    "passed": True,
                    "scope": "authored synthetic fixture, not a production quality SLA",
                }
        finally:
            identifiers = queue.get_job_ids()
            for registry in [queue.finished_job_registry, queue.failed_job_registry]:
                identifiers += registry.get_job_ids()
            for identifier in set(identifiers):
                job = Job.fetch_many([identifier], connection=redis)[0]
                if job:
                    job.delete()
            queue.delete(delete_jobs=True)
            redis.close()
            engine.dispose()
            try:
                next(environment)
            except StopIteration:
                pass


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
