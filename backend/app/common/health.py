import asyncio
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel
from redis import Redis
from sqlalchemy import Engine, text

SCHEMA_REVISION = "0001_foundation"
ComponentStatus = Literal["ok", "unavailable"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    components: dict[str, ComponentStatus]


class HealthChecker:
    def __init__(self, engine: Engine, redis: Redis, timeout: float) -> None:
        self.engine = engine
        self.redis = redis
        self.timeout = timeout

    def database_ready(self) -> bool:
        with self.engine.begin() as connection:
            # Bound only this probe transaction; pooled connections and migrations
            # retain their normal database timeout policy after the transaction ends.
            connection.execute(text("SET LOCAL statement_timeout = '500ms'"))
            # A listening DB without the required migration/extension is not ready.
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            vector = connection.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            ).scalar()
            return revision == SCHEMA_REVISION and bool(vector)

    def redis_ready(self) -> bool:
        return bool(self.redis.ping())

    async def _probe(self, probe: Callable[[], bool]) -> ComponentStatus:
        try:
            result = await asyncio.wait_for(asyncio.to_thread(probe), timeout=self.timeout)
            return "ok" if result else "unavailable"
        except Exception:
            # Credentials, URLs and driver errors must not appear in the public response.
            return "unavailable"

    async def check(self) -> HealthResponse:
        database, redis = await asyncio.gather(
            self._probe(self.database_ready), self._probe(self.redis_ready)
        )
        return HealthResponse(
            status="ok" if database == redis == "ok" else "degraded",
            components={"api": "ok", "database": database, "redis": redis},
        )
