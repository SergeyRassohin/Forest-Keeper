"""Read-only, container-specific RQ readiness probe; never enqueue a job."""

import argparse
import socket
from datetime import UTC, datetime

from redis import Redis

from app.common.config import Settings

# RQ's idle BLPOP lasts worker_ttl - 15 seconds. The freshness limit must be
# longer than this legitimate idle interval, as well as busy monitor heartbeats.
WORKER_TTL_SECONDS = 120
MAX_HEARTBEAT_AGE_SECONDS = 150


def worker_identity() -> str:
    return socket.gethostname()


def worker_healthy(connection: Redis, name: str, now: datetime | None = None) -> bool:
    try:
        key = "rq:worker:" + name
        with connection.pipeline(transaction=False) as pipeline:
            pipeline.hgetall(key)
            pipeline.sismember("rq:workers", key)
            data, registered = pipeline.execute()
        if not registered or data.get(b"state") not in {b"idle", b"busy"}:
            return False
        if not data.get(b"queues"):
            return False
        heartbeat = datetime.fromisoformat(data[b"last_heartbeat"].decode("ascii"))
        if heartbeat.tzinfo is None:
            return False
        age = ((now or datetime.now(UTC)) - heartbeat).total_seconds()
        return -5 <= age <= MAX_HEARTBEAT_AGE_SECONDS
    except Exception:
        # Connection/parser errors can contain a Redis URL. Return status only.
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=worker_identity())
    args = parser.parse_args()
    healthy = False
    try:
        settings = Settings()  # type: ignore[call-arg]
        with Redis.from_url(
            settings.redis_url.get_secret_value(), socket_timeout=2, socket_connect_timeout=2
        ) as connection:
            healthy = worker_healthy(connection, args.name)
    except Exception:
        healthy = False
    print("worker healthy" if healthy else "worker unavailable")
    raise SystemExit(0 if healthy else 1)


if __name__ == "__main__":
    main()
