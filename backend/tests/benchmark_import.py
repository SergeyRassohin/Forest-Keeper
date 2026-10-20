"""Opt-in isolated import capacity profile; never point at production services."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue, SimpleWorker
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.database import make_engine
from app.main import create_app
from tests.test_auth import isolated_environment


def run(count: int) -> dict:
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Development-only: set FK_TEST_INTEGRATION=1 after loading local .env")
    from datetime import UTC, datetime, timedelta

    environment = isolated_environment()
    base = next(environment)
    with tempfile.TemporaryDirectory(prefix="fk-capacity-") as directory:
        queue_name = "capacity-" + uuid4().hex
        settings = base.model_copy(
            update={
                "import_storage_root": Path(directory) / "originals",
                "import_queue_name": queue_name,
            }
        )
        engine = make_engine(settings)
        connection = Redis.from_url(settings.redis_url.get_secret_value())
        tokens = []
        try:
            with Session(engine) as session:
                hashed = hash_password(secrets.token_urlsafe(24))
                for index in range(10):
                    user = User(
                        login=f"capacity_{index}",
                        full_name="Synthetic",
                        password_hash=hashed,
                        roles=[UserRole(role_code="DATA_OWNER")],
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
                headers = {"Origin": "https://localhost:8443"}
                batch_ids = []
                datasets = []
                previous = {
                    key: os.environ.get(key)
                    for key in ("FK_DATABASE_URL", "FK_REDIS_URL", "FK_IMPORT_STORAGE_ROOT")
                }
                os.environ.update(
                    FK_DATABASE_URL=settings.database_url.get_secret_value(),
                    FK_REDIS_URL=settings.redis_url.get_secret_value(),
                    FK_IMPORT_STORAGE_ROOT=str(settings.import_storage_root),
                )
                try:
                    for seed in [41, 42]:
                        file = Path(directory) / f"source-{seed}.csv"
                        generator = (
                            Path(__file__).resolve().parents[2] / "scripts/generate-import-data.py"
                        )
                        subprocess.run(
                            [
                                sys.executable,
                                str(generator),
                                str(file),
                                "--count",
                                str(count),
                                "--seed",
                                str(seed),
                            ],
                            check=True,
                        )
                        source = client.post(
                            "/api/v1/sources",
                            headers=headers,
                            json={
                                "name": f"Synthetic {seed}",
                                "code": f"source_{seed}",
                                "source_type": "FILE",
                            },
                        ).json()
                        start = time.monotonic()
                        with file.open("rb") as stream:
                            response = client.post(
                                "/api/v1/imports",
                                headers=headers,
                                data={"source_id": source["id"]},
                                files={"file": (file.name, stream)},
                            )
                        assert response.status_code == 201
                        batch_id = response.json()["id"]
                        batch_ids.append(batch_id)
                        SimpleWorker(
                            [Queue(queue_name, connection=connection)], connection=connection
                        ).work(burst=True, logging_level="ERROR")
                        detail = client.get("/api/v1/imports/" + batch_id).json()
                        assert detail["status"] == "COMPLETED" and detail["records_loaded"] == count
                        raw = client.get("/api/v1/imports/" + batch_id + "/records?limit=1").json()[
                            0
                        ]
                        assert len(raw["raw_payload"]) == 30
                        datasets.append(
                            {
                                "records": count,
                                "attributes": 30,
                                "bytes": file.stat().st_size,
                                "upload_worker_seconds": round(time.monotonic() - start, 3),
                            }
                        )

                    def read_metadata(token):
                        times = []
                        with TestClient(
                            create_app(settings=settings), base_url="https://localhost:8443"
                        ) as other:
                            other.cookies.set(COOKIE_NAME, token)
                            for _ in range(10):
                                start = time.monotonic()
                                result = other.get("/api/v1/imports/" + batch_ids[0])
                                assert result.status_code == 200
                                times.append(time.monotonic() - start)
                        return times

                    with ThreadPoolExecutor(10) as pool:
                        timings = sorted(
                            time for result in pool.map(read_metadata, tokens) for time in result
                        )
                    p95 = timings[94]
                    assert p95 <= 1.0, f"metadata p95 {p95:.3f}s exceeds baseline"
                    return {
                        "datasets": datasets,
                        "sessions": 10,
                        "requests": 100,
                        "metadata_p95_seconds": round(p95, 4),
                        "passed": True,
                    }
                finally:
                    for key, value in previous.items():
                        if value is None:
                            os.environ.pop(key, None)
                        else:
                            os.environ[key] = value
        finally:
            queue = Queue(queue_name, connection=connection)
            # Only this private queue's jobs/results belong to this profile.
            for registry in [queue.finished_job_registry, queue.failed_job_registry]:
                for identifier in registry.get_job_ids():
                    from rq.job import Job

                    Job.fetch(identifier, connection=connection).delete()
            queue.delete(delete_jobs=True)
            connection.close()
            engine.dispose()
            try:
                next(environment)
            except StopIteration:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, choices=[100, 1000, 10000, 100000], default=100000)
    args = parser.parse_args()
    print(json.dumps(run(args.records), ensure_ascii=False, indent=2))
