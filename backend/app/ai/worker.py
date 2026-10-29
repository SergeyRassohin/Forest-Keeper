"""Dedicated AI queues; neither model inference nor its recovery blocks import workers."""

import argparse
import logging

from redis import Redis
from rq import Queue, Worker

from app.ai.admission import prefix
from app.common.config import Settings
from app.similarity.jobs import recover_indexes
from app.similarity.provider import permitted
from app.worker_health import WORKER_TTL_SECONDS, worker_healthy, worker_identity


class AIWorker(Worker):
    @property
    def dequeue_timeout(self) -> int:
        return max(1, min(super().dequeue_timeout, self.maintenance_interval))

    def run_maintenance_tasks(self) -> None:
        super().run_maintenance_tasks()  # type: ignore[no-untyped-call]
        try:
            settings = Settings()  # type: ignore[call-arg]
            if self.name.endswith(":ai-embedding"):
                recover_indexes(settings, self.connection)
        except Exception:
            logging.getLogger(__name__).warning("AI_RECOVERY_UNAVAILABLE")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=["embedding", "llm"], required=True)
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()
    settings = Settings()  # type: ignore[call-arg]
    if settings.deployment_mode not in {"development", "test"}:
        parser.exit(2, "AI_PRODUCTION_ACTIVATION_NOT_ACCEPTED\n")
    if args.kind == "embedding" and not (
        permitted(settings) and settings.similarity_provider == "qwen-demo"
    ):
        parser.exit(2, "AI_PROVIDER_NOT_CONFIGURED\n")
    if args.kind == "llm" and not settings.ai_enabled:
        parser.exit(2, "AI_NOT_CONFIGURED\n")
    name = worker_identity() + ":ai-" + args.kind
    queue_name = prefix(settings) + ":" + args.kind
    with Redis.from_url(settings.redis_url.get_secret_value()) as connection:
        if args.health:
            healthy = worker_healthy(connection, name) and (
                connection.hget("rq:worker:" + name, "queues") == queue_name.encode()
            )
            print("AI worker healthy" if healthy else "AI worker unavailable")
            raise SystemExit(0 if healthy else 1)
        if args.kind == "embedding":
            recover_indexes(settings, connection)
        AIWorker(
            [Queue(queue_name, connection=connection)],
            connection=connection,
            name=name,
            worker_ttl=WORKER_TTL_SECONDS,
            maintenance_interval=30,
        ).work()


if __name__ == "__main__":
    main()
