import os

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue
from sqlalchemy import text

from app.common.config import Settings
from app.common.database import make_engine
from app.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FK_TEST_INTEGRATION") != "1", reason="integration services opt-in"
    ),
]


def test_real_health_and_vector_roundtrip() -> None:
    settings = Settings()  # type: ignore[call-arg]
    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    engine = make_engine(settings)
    try:
        with engine.connect() as connection:
            # Exercises the extension, not merely its catalog entry.
            distance = connection.execute(
                text("SELECT '[1,0,0]'::vector <=> '[1,0,0]'::vector")
            ).scalar_one()
            assert distance == 0
    finally:
        engine.dispose()


def test_rq_worker_executes_job() -> None:
    settings = Settings()  # type: ignore[call-arg]
    connection = Redis.from_url(settings.redis_url.get_secret_value())
    job = Queue("forest-keeper", connection=connection).enqueue("operator.add", 2, 3)
    try:
        # Only this unique smoke job is inspected and removed.
        import time

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            job.refresh()
            if job.is_finished or job.is_failed:
                break
            time.sleep(0.1)
        assert job.is_finished, job.get_status()
        assert job.return_value() == 5
    finally:
        job.delete()
        connection.close()
