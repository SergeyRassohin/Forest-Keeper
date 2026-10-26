"""Real Redis transaction races; this profile performs no model inference."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from redis import Redis
from rq import Queue
from rq.job import Job

from app.ai.admission import enqueue_bounded, prefix
from app.ai.contracts import AIError
from app.common.config import Settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("FK_TEST_INTEGRATION") != "1", reason="owned Redis opt-in"),
]


@pytest.fixture
def owned():
    namespace = "ai-admission-test-" + uuid4().hex
    settings = Settings().model_copy(update={"ai_queue_prefix": namespace})
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    queue = Queue(namespace + ":embedding", connection=redis)
    actors, jobs = [], []

    def enqueue(actor=None):
        actor = actor or uuid4().hex
        identifier = namespace + "-" + uuid4().hex
        actors.append(actor)
        jobs.append(identifier)
        try:
            return enqueue_bounded(
                redis,
                settings,
                queue,
                time.time,
                (),
                {},
                job_id=identifier,
                actor_id=actor,
                description="OWNED_ADMISSION_TEST",
            )
        except AIError:
            return False

    try:
        yield settings, redis, queue, enqueue
    finally:
        for job in Job.fetch_many(jobs, connection=redis):
            if job is not None:
                job.delete()
        queue.delete(delete_jobs=True)
        redis.delete(prefix(settings) + ":admission")
        for actor in set(actors):
            redis.delete(prefix(settings) + ":actor:" + actor)
        redis.close()


def test_concurrent_global_admission_never_exceeds_eight_or_leaves_partial_jobs(owned):
    settings, redis, queue, enqueue = owned
    with ThreadPoolExecutor(max_workers=20) as workers:
        results = list(workers.map(lambda _: enqueue(), range(20)))
    accepted = sum(results)
    assert 0 < accepted <= 8
    assert queue.count == accepted
    assert redis.zcard(prefix(settings) + ":admission") == accepted
    for _ in range(8 - accepted):
        assert enqueue()
    assert not enqueue()
    assert queue.count == 8


def test_two_simultaneous_requests_for_one_actor_admit_only_one(owned):
    settings, redis, queue, enqueue = owned
    actor = uuid4().hex
    with ThreadPoolExecutor(max_workers=10) as workers:
        results = list(workers.map(lambda _: enqueue(actor), range(10)))
    assert sum(results) == 1
    assert queue.count == redis.zcard(prefix(settings) + ":admission") == 1


def test_enqueue_failure_rolls_back_actor_lease_and_global_reservation(owned, monkeypatch):
    settings, redis, queue, enqueue = owned

    def fail(*args, **kwargs):
        raise RuntimeError("owned injected enqueue failure")

    monkeypatch.setattr(queue, "enqueue_job", fail)
    actor = uuid4().hex
    with pytest.raises(RuntimeError, match="owned injected"):
        enqueue(actor)
    assert not redis.exists(prefix(settings) + ":admission")
    assert not redis.exists(prefix(settings) + ":actor:" + actor)
    assert queue.count == 0
