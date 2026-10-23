"""Opt-in read capacity of synthetic queue rows carrying real frozen Conflict evidence.

This measures queue/context/registry reads, not full 100k import throughput or human SLA.
All generated rows live in a unique disposable schema; business create uses the actual API.
"""

import json
import math
import os
import resource
import secrets
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue
from rq.job import Job
from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.database import make_engine
from app.conflicts.models import Conflict
from app.main import create_app
from tests.test_auth import isolated_environment
from tests.test_decisions_integration import begin, real_case, save, selection


def run():
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Development-only opt-in required")
    environment = isolated_environment()
    base = next(environment)
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix="fk-decision-capacity-") as folder:
            settings = base.model_copy(
                update={
                    "import_storage_root": Path(folder),
                    "import_queue_name": "decision-capacity-" + uuid4().hex,
                }
            )
            engine = make_engine(settings)
            tokens = []
            with Session(engine) as session:
                password_hash = hash_password(secrets.token_urlsafe(24))
                for index in range(10):
                    user = User(
                        login=f"decision_capacity_{index}",
                        full_name="Synthetic reader",
                        data_domains=["*"],
                        password_hash=password_hash,
                        roles=[UserRole(role_code="DATA_OWNER" if index == 0 else "VIEWER")],
                    )
                    session.add(user)
                    session.flush()
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
            with TestClient(
                create_app(settings=settings), base_url="https://localhost:8443"
            ) as client:
                client.cookies.set(COOKIE_NAME, tokens[0])
                identifier = real_case(client, settings)
                with Session(engine) as session:
                    row = session.get(Conflict, UUID(identifier))
                    seed = {
                        column.name: getattr(row, column.name)
                        for column in Conflict.__table__.columns
                    }
                    initial = session.scalar(select(text("count(*)")).select_from(Conflict))
                request = selection(begin(client, identifier))
                started = time.monotonic()
                decision = save(client, identifier, request)
                create_seconds = time.monotonic() - started
                current = initial
                for count in [100, 1000, 10000, 100000]:
                    while current < count:
                        amount = min(count - current, 500)
                        with engine.begin() as connection:
                            connection.execute(
                                insert(Conflict), [{**seed, "id": uuid4()} for _ in range(amount)]
                            )
                        current += amount
                    endpoints = [
                        "/api/v1/conflicts?limit=50",
                        f"/api/v1/conflicts/{identifier}/review-context",
                        "/api/v1/decisions?limit=50",
                        f"/api/v1/decisions/{decision['decision_id']}",
                        f"/api/v1/conflicts/{identifier}/decisions?limit=50",
                    ]

                    def read(token, paths=endpoints):
                        samples = []
                        with TestClient(
                            create_app(settings=settings), base_url="https://localhost:8443"
                        ) as reader:
                            reader.cookies.set(COOKIE_NAME, token)
                            for index in range(15):
                                before = time.monotonic()
                                response = reader.get(paths[index % len(paths)])
                                assert response.status_code == 200, response.text
                                samples.append(
                                    (paths[index % len(paths)], time.monotonic() - before)
                                )
                        return samples

                    with ThreadPoolExecutor(10) as pool:
                        measurements = [
                            value for group in pool.map(read, tokens) for value in group
                        ]
                        samples = sorted(value[1] for value in measurements)
                    p95 = samples[math.ceil(len(samples) * 0.95) - 1]
                    assert p95 <= 1, p95
                    with engine.begin() as connection:
                        connection.execute(text("ANALYZE conflicts"))
                        plans = [
                            connection.execute(
                                text(
                                    "EXPLAIN SELECT id FROM conflicts "
                                    "ORDER BY detected_at DESC,id DESC LIMIT 50"
                                )
                            )
                            .scalars()
                            .all(),
                            connection.execute(
                                text(
                                    "EXPLAIN SELECT id FROM decisions "
                                    "ORDER BY decided_at DESC,id DESC LIMIT 50"
                                )
                            )
                            .scalars()
                            .all(),
                        ]
                    results.append(
                        {
                            "source_commit": subprocess.check_output(
                                ["git", "rev-parse", "HEAD"], text=True
                            ).strip(),
                            "queue_rows": count,
                            "decision_rows": 1,
                            "sessions": 10,
                            "requests": len(samples),
                            "p95_seconds": round(p95, 4),
                            "endpoint_p95_seconds": {
                                path: round(sorted(t for p, t in measurements if p == path)[28], 4)
                                for path in endpoints
                            },
                            "create_seconds_observed_no_sla": round(create_seconds, 4),
                            "plans": plans,
                            "process_peak_rss_mib": round(
                                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
                            ),
                            "passed": True,
                        }
                    )
                    print(json.dumps(results[-1]), flush=True)
            engine.dispose()
    finally:
        if "settings" in locals():
            redis = Redis.from_url(settings.redis_url.get_secret_value())
            queue = Queue(settings.import_queue_name, connection=redis)
            identifiers = queue.get_job_ids()
            for registry in [queue.finished_job_registry, queue.failed_job_registry]:
                identifiers += registry.get_job_ids()
            for identifier in set(identifiers):
                job = Job.fetch_many([identifier], connection=redis)[0]
                if job:
                    job.delete()
            queue.delete(delete_jobs=True)
            redis.close()
        try:
            next(environment)
        except StopIteration:
            pass
    return results


if __name__ == "__main__":
    run()
