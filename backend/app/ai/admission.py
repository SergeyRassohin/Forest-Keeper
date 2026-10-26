"""Atomic bounded RQ admission and expiring actor leases for optional local AI."""

import logging
import time
from typing import Any, cast
from uuid import uuid4

from redis import Redis
from redis.exceptions import WatchError
from rq import Queue, get_current_job
from rq.job import Job

from app.ai.contracts import AIError
from app.common.config import Settings

LEASE_SECONDS = 450
WAIT_SECONDS = 240


def prefix(settings: Settings) -> str:
    return settings.ai_queue_prefix or settings.import_queue_name + ":ai"


def enqueue_bounded(
    redis: Redis,
    settings: Settings,
    queue: Queue,
    function: Any,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    job_id: str,
    actor_id: str | None,
    description: str,
    request_record: dict[str, Any] | None = None,
) -> bool:
    """Reserve and enqueue in one transaction. Backfill leaves two slots for user work."""
    global_key = prefix(settings) + ":admission"
    actor_key = prefix(settings) + ":actor:" + actor_id if actor_id else None
    token = uuid4().hex
    job = queue.create_job(
        function,
        args=args,
        kwargs=kwargs,
        timeout=180,
        ttl=WAIT_SECONDS,
        result_ttl=900,
        failure_ttl=300,
        job_id=job_id,
        description=description,
        meta={
            "admission_token": token,
            "admission_actor_key": actor_key,
            **({"request_record": request_record} if request_record is not None else {}),
        },
    )
    watched = [global_key, job.key, *([actor_key] if actor_key else [])]
    for _ in range(3):
        try:
            with redis.pipeline() as pipe:
                pipe.watch(*watched)  # type: ignore[no-untyped-call]  # Sync Redis WATCH API.
                previous = None
                if pipe.exists(job.key):
                    previous = Job.fetch(job_id, connection=redis)
                    if previous.get_status(refresh=False) not in {
                        "finished",
                        "failed",
                        "stopped",
                        "canceled",
                    }:
                        return False
                now = time.time()
                if cast(int, pipe.zcount(global_key, now, "+inf")) >= (8 if actor_id else 6):
                    raise AIError("AI_QUEUE_FULL")
                if actor_key and pipe.exists(actor_key):
                    raise AIError("AI_ACTOR_BUSY")
                pipe.multi()
                if previous is not None:
                    previous.delete(pipeline=pipe)
                pipe.zremrangebyscore(global_key, "-inf", now)
                pipe.zadd(global_key, {token: now + LEASE_SECONDS})
                if actor_key:
                    pipe.set(actor_key, token, ex=LEASE_SECONDS)
                queue.enqueue_job(job, pipeline=pipe, at_front=actor_id is not None)
                pipe.execute()
                return True
        except WatchError:
            continue
    raise AIError("AI_QUEUE_BUSY")


def _release_current(settings: Settings) -> None:
    job = get_current_job()
    if job is None:
        return
    token = job.meta.get("admission_token")
    actor_key = job.meta.get("admission_actor_key")
    if not isinstance(token, str):
        return
    key = prefix(settings) + ":admission"
    if not isinstance(actor_key, str):
        job.connection.zrem(key, token)
        return
    # Never release a newer actor lease after a delayed/crashed job.
    job.connection.eval(
        "if redis.call('get',KEYS[2]) == ARGV[1] then redis.call('del',KEYS[2]) end; "
        "return redis.call('zrem',KEYS[1],ARGV[1])",
        2,
        key,
        actor_key,
        token,
    )


def release_current(settings: Settings) -> None:
    try:
        _release_current(settings)
    except Exception:
        # Leases expire if Redis is down; never log connection URLs/job input.
        logging.getLogger(__name__).warning("AI_ADMISSION_RELEASE_UNAVAILABLE")
