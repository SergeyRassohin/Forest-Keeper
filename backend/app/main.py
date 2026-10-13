from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from redis import Redis

from app.common.config import Settings
from app.common.database import make_engine
from app.common.health import HealthChecker, HealthResponse


def create_app(settings: Settings | None = None, checker: HealthChecker | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if checker is not None:
            app.state.health_checker = checker
            yield
            return
        config = settings or Settings()  # type: ignore[call-arg]
        engine = make_engine(config)
        redis = Redis.from_url(
            config.redis_url.get_secret_value(),
            socket_connect_timeout=config.health_timeout_seconds,
            socket_timeout=config.health_timeout_seconds,
        )
        app.state.health_checker = HealthChecker(engine, redis, config.health_timeout_seconds)
        try:
            yield
        finally:
            redis.close()
            engine.dispose()

    app = FastAPI(title="Forest Keeper API", version="0.1.0", lifespan=lifespan)

    @app.get("/api/v1/health", response_model=HealthResponse)
    async def health(response: Response) -> HealthResponse:
        active_checker: HealthChecker = app.state.health_checker
        result = await active_checker.check()
        if result.status != "ok":
            response.status_code = 503
        response.headers["Cache-Control"] = "no-store"
        return result

    @app.get("/api/v1/version")
    def version() -> dict[str, str]:
        return {"name": "Forest Keeper", "version": "0.1.0", "stage": "foundation"}

    return app


app = create_app()
