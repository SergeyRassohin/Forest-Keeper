import time
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.common.config import Settings
from app.common.health import HealthChecker
from app.main import create_app


@pytest.mark.parametrize("database,redis", [(True, True), (False, True), (True, False)])
def test_health_requires_all_dependencies(database: bool, redis: bool) -> None:
    checker = HealthChecker(Mock(), Mock(), 0.1)
    checker.database_ready = Mock(return_value=database)
    checker.redis_ready = Mock(return_value=redis)
    with TestClient(create_app(checker=checker)) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == (200 if database and redis else 503)
    assert response.json()["components"] == {
        "api": "ok",
        "database": "ok" if database else "unavailable",
        "redis": "ok" if redis else "unavailable",
    }
    assert response.headers["cache-control"] == "no-store"


def test_driver_error_does_not_leak_secrets() -> None:
    checker = HealthChecker(Mock(), Mock(), 0.1)
    checker.database_ready = Mock(side_effect=RuntimeError("postgres://secret-password"))
    checker.redis_ready = Mock(return_value=True)
    with TestClient(create_app(checker=checker)) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert "secret-password" not in response.text


def test_health_deadline_bounds_slow_dependencies() -> None:
    checker = HealthChecker(Mock(), Mock(), 0.02)
    checker.database_ready = Mock(side_effect=lambda: time.sleep(0.1))
    checker.redis_ready = Mock(return_value=True)
    with TestClient(create_app(checker=checker)) as client:
        started = time.monotonic()
        response = client.get("/api/v1/health")
        elapsed = time.monotonic() - started
    assert response.status_code == 503
    assert elapsed < 0.1


def test_required_settings_are_not_silently_defaulted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FK_DATABASE_URL", raising=False)
    monkeypatch.delenv("FK_REDIS_URL", raising=False)
    with pytest.raises(ValueError):
        Settings()  # type: ignore[call-arg]
