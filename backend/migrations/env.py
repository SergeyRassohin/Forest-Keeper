from alembic import context

from app.common.config import Settings
from app.common.database import make_engine

if context.is_offline_mode():
    config = Settings()  # type: ignore[call-arg]
    context.configure(
        url=config.database_url.get_secret_value(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    config = Settings()  # type: ignore[call-arg]
    engine = make_engine(config)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
