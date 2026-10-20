from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.worker_health import MAX_HEARTBEAT_AGE_SECONDS, WORKER_TTL_SECONDS, worker_healthy


@pytest.mark.parametrize(
    "state,age,registered,expected",
    [
        (b"idle", 0, True, True),
        (b"busy", 30, True, True),
        (b"idle", WORKER_TTL_SECONDS - 15, True, True),
        (b"idle", MAX_HEARTBEAT_AGE_SECONDS + 1, True, False),
        (b"idle", -60, True, False),
        (b"started", 0, True, False),
        (b"suspended", 0, True, False),
        (b"stopped", 0, True, False),
        (b"idle", 0, False, False),
    ],
)
def test_registration_state_and_realistic_idle_heartbeat(state, age, registered, expected):
    now = datetime.now(UTC)
    redis = MagicMock()
    pipeline = redis.pipeline.return_value.__enter__.return_value
    pipeline.execute.return_value = [
        {
            b"state": state,
            b"last_heartbeat": (now - timedelta(seconds=age)).isoformat().encode(),
            b"queues": b"forest-keeper",
        },
        registered,
    ]
    assert worker_healthy(redis, "this-container", now) is expected
    pipeline.hgetall.assert_called_once_with("rq:worker:this-container")
    pipeline.sismember.assert_called_once_with("rq:workers", "rq:worker:this-container")


@pytest.mark.parametrize(
    "data",
    [{}, {b"state": b"idle"}, {b"state": b"idle", b"queues": b"q", b"last_heartbeat": b"bad"}],
)
def test_incomplete_or_malformed_worker_is_not_ready(data):
    redis = MagicMock()
    redis.pipeline.return_value.__enter__.return_value.execute.return_value = [data, True]
    assert not worker_healthy(redis, "this-container")


def test_redis_failure_does_not_emit_connection_details(capsys):
    redis = MagicMock()
    redis.pipeline.side_effect = RuntimeError("private-connection-marker")
    assert not worker_healthy(redis, "this-container")
    assert "private-connection-marker" not in str(capsys.readouterr())
