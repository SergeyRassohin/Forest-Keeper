"""One actor budget shared by similarity and recommendations, never an extra quota."""

import time

from redis import Redis
from redis.exceptions import RedisError

from app.auth.models import User
from app.common.config import Settings
from app.common.errors import ApiError


def read_budget(cache: Redis, settings: Settings, actor: User) -> None:
    key = (
        settings.auth_rate_prefix
        + "similarity:"
        + str(actor.id)
        + ":"
        + str(int(time.time() // 60))
    )
    try:
        with cache.pipeline() as pipeline:
            pipeline.incr(key)
            pipeline.expire(key, 120, nx=True)
            count, _ = pipeline.execute()
        if count > min(120, settings.similarity_reads_per_minute):
            raise ApiError(429, "RETRIEVAL_RATE_LIMITED", "Слишком много запросов. Повторите позже")
    except RedisError:
        raise ApiError(503, "RETRIEVAL_UNAVAILABLE", "Поиск временно недоступен") from None
