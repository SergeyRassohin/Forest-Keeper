from redis import Redis
from rq import Queue, Worker

from app.common.config import Settings


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    connection = Redis.from_url(settings.redis_url.get_secret_value())
    try:
        Worker([Queue("forest-keeper", connection=connection)], connection=connection).work()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
