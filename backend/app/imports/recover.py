"""Reconcile imports after an interrupted worker/queue publication."""

from redis import Redis

from app.common.config import Settings
from app.imports.jobs import recover_imports


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    connection = Redis.from_url(settings.redis_url.get_secret_value(), socket_timeout=5)
    try:
        count = recover_imports(settings, connection)
        print(f"Imports reconciled: {count}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
