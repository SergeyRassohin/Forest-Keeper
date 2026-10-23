import logging

from redis import Redis
from rq import Queue, Worker

from app.common.config import Settings
from app.conflicts.jobs import recover_runs as recover_conflicts
from app.imports.jobs import recover_imports
from app.matching.jobs import recover_runs as recover_matching
from app.normalization.jobs import recover_runs
from app.similarity.jobs import recover_indexes
from app.worker_health import WORKER_TTL_SECONDS, worker_identity


class ForestWorker(Worker):
    def run_maintenance_tasks(self) -> None:
        super().run_maintenance_tasks()  # type: ignore[no-untyped-call]  # RQ's untyped hook.
        try:
            settings = Settings()  # type: ignore[call-arg]
            recover_runs(settings, self.connection)
            recover_matching(settings, self.connection)
            recover_conflicts(settings, self.connection)
            recover_indexes(settings, self.connection)
        except Exception:
            # Database failures can include credentials or raw input in their text.
            logging.getLogger(__name__).warning("BACKGROUND_RECOVERY_UNAVAILABLE")


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    connection = Redis.from_url(settings.redis_url.get_secret_value())
    try:
        recover_imports(settings, connection)
        recover_runs(settings, connection)
        recover_matching(settings, connection)
        recover_conflicts(settings, connection)
        recover_indexes(settings, connection)
        ForestWorker(
            [Queue(settings.import_queue_name, connection=connection)],
            connection=connection,
            name=worker_identity(),
            worker_ttl=WORKER_TTL_SECONDS,
            maintenance_interval=30,
        ).work()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
