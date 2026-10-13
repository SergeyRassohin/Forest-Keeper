from sqlalchemy import Engine, create_engine

from app.common.config import Settings


def make_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 1, "options": "-c statement_timeout=500"},
    )
