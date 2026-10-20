from redis import Redis

from app.common.config import Settings
from app.normalization.jobs import recover_runs


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    with Redis.from_url(settings.redis_url.get_secret_value()) as connection:
        print("Recovered normalization runs:", recover_runs(settings, connection))


if __name__ == "__main__":
    main()
