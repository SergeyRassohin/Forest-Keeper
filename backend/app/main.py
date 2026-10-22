from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis import Redis

from app.auth.dependencies import require_permission
from app.auth.routes import router as auth_router
from app.common.config import Settings
from app.common.database import make_engine
from app.common.errors import ApiError
from app.common.health import HealthChecker, HealthResponse
from app.conflicts.routes import router as conflict_router
from app.imports.routes import router as import_router
from app.matching.routes import router as matching_router
from app.normalization.routes import router as normalization_router


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
        app.state.engine = engine
        app.state.redis = redis
        app.state.settings = config
        try:
            yield
        finally:
            redis.close()
            engine.dispose()

    app = FastAPI(title="Forest Keeper API", version="0.1.0", lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(import_router)
    app.include_router(normalization_router)
    app.include_router(matching_router)
    app.include_router(conflict_router)

    @app.exception_handler(ApiError)
    async def api_error(request: Request, error: ApiError) -> JSONResponse:
        headers = {"Cache-Control": "no-store"}
        if error.status == 429:
            headers["Retry-After"] = str(request.app.state.settings.login_window_seconds)
        return JSONResponse(error.body(), status_code=error.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Pydantic's default response can echo password/token input. Never expose it.
        return JSONResponse(
            ApiError(422, "INVALID_REQUEST", "Проверьте введённые данные").body(),
            status_code=422,
            headers={"Cache-Control": "no-store"},
        )

    @app.middleware("http")
    async def private_response(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith(
            (
                "/api/v1/auth",
                "/api/v1/users",
                "/api/v1/sources",
                "/api/v1/imports",
                "/api/v1/analysis",
                "/api/v1/matching",
                "/api/v1/conflict",
                "/api/v1/match-candidates",
            )
        ):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/v1/health", response_model=HealthResponse)
    async def health(response: Response) -> HealthResponse:
        active_checker: HealthChecker = app.state.health_checker
        result = await active_checker.check()
        if result.status != "ok":
            response.status_code = 503
        response.headers["Cache-Control"] = "no-store"
        return result

    @app.get(
        "/api/v1/dashboard",
        response_model=HealthResponse,
        dependencies=[Depends(require_permission("dashboard.view"))],
    )
    async def dashboard(response: Response) -> HealthResponse:
        return await health(response)

    @app.get("/api/v1/version", dependencies=[Depends(require_permission("update.view"))])
    def version() -> dict[str, str]:
        return {"name": "Forest Keeper", "version": "0.1.0", "stage": "conflicts"}

    return app


app = create_app()
