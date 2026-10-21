import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue, SimpleWorker
from rq.job import Job
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuditEvent
from app.common.database import make_engine
from app.main import create_app
from app.matching.jobs import enqueue, execute_matching, job_id, recover_runs
from app.matching.models import MatchCandidate, MatchingRun
from app.normalization.jobs import execute_run
from app.normalization.models import AnalysisRun, EntityValue
from tests.test_auth import ORIGIN, isolated_environment
from tests.test_auth import password as password
from tests.test_auth import role_tokens as role_tokens
from tests.test_matching import DATA, PROFILE
from tests.test_normalization_integration import imported
from tests.test_normalization_integration import start as normalize_start

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FK_TEST_INTEGRATION") != "1", reason="integration services opt-in"
    ),
]


@pytest.fixture(scope="module")
def auth_env(tmp_path_factory):
    environment = isolated_environment()
    base = next(environment)
    settings = base.model_copy(
        update={
            "import_storage_root": tmp_path_factory.mktemp("matching-originals"),
            "import_queue_name": "matching-test-" + uuid4().hex,
        }
    )
    yield settings
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    queue = Queue(settings.import_queue_name, connection=redis)
    identifiers = queue.get_job_ids()
    for registry in [queue.finished_job_registry, queue.failed_job_registry]:
        identifiers += registry.get_job_ids()
    for identifier in set(identifiers):
        job = Job.fetch_many([identifier], connection=redis)[0]
        if job:
            job.delete()
    queue.delete(delete_jobs=True)
    redis.close()
    try:
        next(environment)
    except StopIteration:
        pass


@pytest.fixture
def client(auth_env, role_tokens):
    with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as value:
        value.cookies.set(COOKIE_NAME, role_tokens["ADMIN"])
        yield value


def inputs(client, settings):
    identifiers = []
    for name, fixture in [("material.csv", "source-a.csv"), ("onec.xml", "source-b.xml")]:
        batch = imported(client, settings, name, (DATA / fixture).read_bytes())
        run = normalize_start(client, batch)
        execute_run(UUID(run["id"]), settings)
        assert client.get("/api/v1/analysis/" + run["id"]).json()["status"] == "COMPLETED"
        identifiers.append(run["id"])
    return identifiers


def start(client, identifiers, profile=PROFILE):
    response = client.post(
        "/api/v1/matching-runs",
        headers=ORIGIN,
        json={"analysis_run_ids": identifiers, "profile_id": str(profile.id)},
    )
    assert response.status_code in {200, 201}, response.text
    return response.json()


def candidates(client, run, status=None):
    result = []
    while True:
        response = client.get(
            "/api/v1/matching-runs/"
            + run["id"]
            + "/candidates?limit=100&offset="
            + str(len(result))
            + ("&status=" + status if status else "")
        )
        assert response.status_code == 200, response.text
        page = response.json()
        result.extend(page)
        if len(page) < 100:
            return result


def test_actual_import_normalization_matching_and_provenance(client, auth_env):
    ids = inputs(client, auth_env)
    before = [client.get("/api/v1/analysis/" + value + "/records").json() for value in ids]
    run = start(client, ids)
    assert start(client, list(reversed(ids)))["id"] == run["id"]
    execute_matching(UUID(run["id"]), auth_env)
    result = client.get("/api/v1/matching-runs/" + run["id"]).json()
    assert result["status"] == "COMPLETED", result
    assert all(
        result["status_counts"].get(status, 0) > 0
        for status in ["MATCHED", "POSSIBLE_MATCH", "NOT_MATCHED"]
    )
    for item in candidates(client, run):
        assert item["raw_record_a_id"] < item["raw_record_b_id"]
        detail = client.get("/api/v1/match-candidates/" + item["id"]).json()
        assert len(detail["records"]) == 2
        assert detail["records"][0]["source"]["id"] != detail["records"][1]["source"]["id"]
        assert all(
            record["file_hash"] and record["values"] and record["source_position"]
            for record in detail["records"]
        )
        assert detail["evidence"]["profile_hash"] == result["profile_hash"]
        assert detail["evidence"]["input_context"] == result["input_context"]
        assert detail["confirmed_by"] is None
    assert [client.get("/api/v1/analysis/" + value + "/records").json() for value in ids] == before
    assert client.get("/api/v1/conflicts").status_code == 404
    old = candidates(client, run)
    execute_matching(UUID(run["id"]), auth_env)
    assert candidates(client, run) == old
    second = start(client, ids)
    assert second["id"] != run["id"]
    execute_matching(UUID(second["id"]), auth_env)
    assert {row["id"] for row in candidates(client, second)}.isdisjoint({row["id"] for row in old})
    assert [
        (row["raw_record_a_id"], row["raw_record_b_id"], row["confidence"], row["status"])
        for row in sorted(
            candidates(client, second),
            key=lambda item: (item["raw_record_a_id"], item["raw_record_b_id"]),
        )
    ] == [
        (row["raw_record_a_id"], row["raw_record_b_id"], row["confidence"], row["status"])
        for row in sorted(old, key=lambda item: (item["raw_record_a_id"], item["raw_record_b_id"]))
    ]


def test_concurrent_starts_and_deliveries(client, auth_env, role_tokens):
    ids = inputs(client, auth_env)

    def request(_):
        with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as other:
            other.cookies.set(COOKIE_NAME, role_tokens["ADMIN"])
            return start(other, ids)["id"]

    with ThreadPoolExecutor(5) as pool:
        identifiers = list(pool.map(request, range(5)))
    assert len(set(identifiers)) == 1
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(lambda _: execute_matching(UUID(identifiers[0]), auth_env), range(3)))
    run = {"id": identifiers[0]}
    rows = candidates(client, run)
    assert rows and len({row["id"] for row in rows}) == len(rows)
    assert client.get("/api/v1/matching-runs/" + run["id"]).json()["candidates_generated"] == len(
        rows
    )


@pytest.mark.parametrize("role", ["VIEWER", "REVIEWER", "DATA_OWNER", "ADMIN", "NO_ROLES"])
@pytest.mark.parametrize(
    "path",
    [
        "/matching-profiles",
        "/matching-runs",
        "/matching-runs/00000000-0000-0000-0000-000000000000",
        "/match-candidates/00000000-0000-0000-0000-000000000000",
    ],
)
def test_read_permissions(client, role_tokens, role, path):
    client.cookies.set(COOKIE_NAME, role_tokens[role])
    response = client.get("/api/v1" + path)
    assert response.status_code == (
        403 if role == "NO_ROLES" else 404 if "00000000" in path else 200
    )
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("role", ["VIEWER", "REVIEWER", "DATA_OWNER", "ADMIN", "NO_ROLES"])
def test_run_and_origin_permissions(client, role_tokens, role):
    client.cookies.set(COOKIE_NAME, role_tokens[role])
    payload = {"analysis_run_ids": [str(uuid4()), str(uuid4())], "profile_id": str(PROFILE.id)}
    response = client.post("/api/v1/matching-runs", headers=ORIGIN, json=payload)
    assert response.status_code == (403 if role in {"VIEWER", "NO_ROLES"} else 404)
    assert client.post("/api/v1/matching-runs", json=payload).status_code == 403


@pytest.mark.parametrize("role", ["VIEWER", "REVIEWER", "DATA_OWNER", "ADMIN", "NO_ROLES"])
@pytest.mark.parametrize("target", ["MATCHED", "NOT_MATCHED"])
def test_review_permissions_and_terminal_immutability(client, auth_env, role_tokens, role, target):
    ids = inputs(client, auth_env)
    run = start(client, ids)
    execute_matching(UUID(run["id"]), auth_env)
    item = candidates(client, run, "POSSIBLE_MATCH")[0]
    client.cookies.set(COOKIE_NAME, role_tokens[role])
    response = client.post(
        "/api/v1/match-candidates/" + item["id"] + "/review",
        headers=ORIGIN,
        json={"status": target, "reason": "synthetic explicit human check"},
    )
    if role not in {"REVIEWER", "DATA_OWNER"}:
        assert response.status_code == 403
        return
    assert response.status_code == 200 and response.json()["confirmed_by"]
    again = client.post(
        "/api/v1/match-candidates/" + item["id"] + "/review",
        headers=ORIGIN,
        json={
            "status": "NOT_MATCHED" if target == "MATCHED" else "MATCHED",
            "reason": "attempt to rewrite terminal",
        },
    )
    assert again.status_code == 409
    detail = client.get("/api/v1/match-candidates/" + item["id"]).json()
    assert detail["evidence"]["computed_status"] == "POSSIBLE_MATCH" and detail["status"] == target
    assert detail["manual_review"]["reason"] == "synthetic explicit human check"
    assert detail["manual_review"]["actor_id"] == response.json()["confirmed_by"]
    engine = make_engine(auth_env)
    with Session(engine) as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.object_id == UUID(item["id"]), AuditEvent.event_type == "MATCH_REVIEWED"
            )
        )
        assert event.user_id == UUID(response.json()["confirmed_by"])
        assert event.payload["reason"] == "synthetic explicit human check"
    engine.dispose()


def test_restart_checkpoint_and_safe_error(client, auth_env):
    ids = inputs(client, auth_env)
    run = start(client, ids)
    from app.matching.engine import evaluate

    calls = 0

    def interrupted(*args):
        nonlocal calls
        calls += 1
        if calls > 3:
            raise RuntimeError("private-source-marker")
        return evaluate(*args)

    with patch("app.matching.jobs.evaluate", side_effect=interrupted):
        execute_matching(UUID(run["id"]), auth_env)
    detail = client.get("/api/v1/matching-runs/" + run["id"]).json()
    assert detail["status"] == "FAILED" and detail["error_text"] == "MATCHING_INTERRUPTED"
    assert "private-source-marker" not in str(detail)
    retry = start(client, ids)
    execute_matching(UUID(retry["id"]), auth_env)
    assert client.get("/api/v1/matching-runs/" + retry["id"]).json()["status"] == "COMPLETED"


def test_recovery_late_enqueue_and_profile_history(client, auth_env):
    ids = inputs(client, auth_env)
    run = start(client, ids)
    redis = Redis.from_url(auth_env.redis_url.get_secret_value())
    engine = make_engine(auth_env)
    try:
        Job.fetch(job_id(UUID(run["id"])), connection=redis).delete()
        with Session(engine) as session:
            value = session.get(MatchingRun, UUID(run["id"]))
            value.updated_at = datetime.now(UTC) - timedelta(minutes=2)
            session.commit()
        assert recover_runs(auth_env, redis) >= 1
        with Session(engine) as session:
            enqueue(UUID(run["id"]), session, auth_env, redis)
        assert client.get("/api/v1/matching-runs/" + run["id"]).json()["status"] == "FAILED"
        retry = start(client, ids)
        execute_matching(UUID(retry["id"]), auth_env)
        old = candidates(client, retry)
        changed = PROFILE.model_copy(update={"version": "2"})
        with patch("app.matching.routes.catalog", return_value={changed.id: changed}):
            assert client.get("/api/v1/matching-runs/" + retry["id"]).json()[
                "based_on_previous_profile"
            ]
            newer = start(client, ids, changed)
            execute_matching(UUID(newer["id"]), auth_env)
        assert newer["profile_hash"] != retry["profile_hash"] and candidates(client, retry) == old
    finally:
        engine.dispose()
        redis.close()


def test_real_rq_matching_delivery(client, auth_env, monkeypatch):
    monkeypatch.setenv("FK_DATABASE_URL", auth_env.database_url.get_secret_value())
    monkeypatch.setenv("FK_REDIS_URL", auth_env.redis_url.get_secret_value())
    monkeypatch.setenv("FK_IMPORT_QUEUE_NAME", auth_env.import_queue_name)
    ids = inputs(client, auth_env)
    run = start(client, ids)
    redis = Redis.from_url(auth_env.redis_url.get_secret_value())
    try:
        SimpleWorker([Queue(auth_env.import_queue_name, connection=redis)], connection=redis).work(
            burst=True, logging_level="ERROR"
        )
        assert client.get("/api/v1/matching-runs/" + run["id"]).json()["status"] == "COMPLETED"
    finally:
        redis.close()


def test_migration_roundtrip_preserves_stage2_and_stage3(client, auth_env, monkeypatch):
    ids = inputs(client, auth_env)
    engine = make_engine(auth_env)
    with Session(engine) as session:
        before = session.scalar(select(func.count()).select_from(EntityValue))
    monkeypatch.setenv("FK_DATABASE_URL", auth_env.database_url.get_secret_value())
    config = AlembicConfig("alembic.ini")
    command.downgrade(config, "0004_normalization")
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(EntityValue)) == before
        assert all(
            session.get(AnalysisRun, UUID(identifier)).status == "COMPLETED" for identifier in ids
        )
    engine.dispose()


@pytest.mark.parametrize("failure", ["exception", "hard_stop"])
def test_atomic_100_record_checkpoint_and_resume(client, auth_env, failure):
    payload = (
        "id,name,mass,price,date\n"
        + "".join(f"{index:06},Material{index:06},1 kg,1,2026-10-20\n" for index in range(101))
    ).encode()
    ids = []
    for _ in range(2):
        batch = imported(client, auth_env, "material.csv", payload)
        normalized = normalize_start(client, batch)
        execute_run(UUID(normalized["id"]), auth_env)
        ids.append(normalized["id"])
    run = start(client, ids)
    from app.matching.engine import evaluate

    calls = 0

    def stop(*args):
        nonlocal calls
        calls += 1
        if calls > 100:
            if failure == "hard_stop":
                raise SystemExit("synthetic interruption")
            raise RuntimeError("private-marker")
        return evaluate(*args)

    with patch("app.matching.jobs.evaluate", side_effect=stop):
        if failure == "hard_stop":
            with pytest.raises(SystemExit):
                execute_matching(UUID(run["id"]), auth_env)
        else:
            execute_matching(UUID(run["id"]), auth_env)
    partial = client.get("/api/v1/matching-runs/" + run["id"]).json()
    assert partial["records_processed"] == partial["candidates_generated"] == 100
    assert partial["status"] == ("PROCESSING" if failure == "hard_stop" else "FAILED")
    retry = run if failure == "hard_stop" else start(client, ids)
    execute_matching(UUID(retry["id"]), auth_env)
    complete = client.get("/api/v1/matching-runs/" + retry["id"]).json()
    assert complete["status"] == "COMPLETED" and complete["candidates_generated"] == 101
    assert len(candidates(client, retry)) == 101


def test_idle_worker_recovers_fresh_then_stale_new_matching_run(client, auth_env):
    from app.worker import ForestWorker

    ids = inputs(client, auth_env)
    with patch("app.matching.routes.enqueue"):
        run = start(client, ids)
    assert run["status"] == "NEW"
    redis = Redis.from_url(auth_env.redis_url.get_secret_value())
    engine = make_engine(auth_env)
    settings = auth_env.model_copy(update={"import_queue_name": "match-recovery-" + uuid4().hex})
    queue = Queue(settings.import_queue_name, connection=redis)
    worker = ForestWorker([queue], connection=redis, maintenance_interval=0)
    try:
        with patch("app.worker.Settings", return_value=settings):
            worker.run_maintenance_tasks()
            assert queue.count == 0
            with Session(engine) as session:
                stored = session.get(MatchingRun, UUID(run["id"]))
                stored.updated_at = datetime.now(UTC) - timedelta(seconds=90)
                session.commit()
            result = worker.dequeue_job_and_maintain_ttl(timeout=1, max_idle_time=2)
        assert result and result[0].id == job_id(UUID(run["id"]))
        execute_matching(UUID(run["id"]), auth_env)
        assert client.get("/api/v1/matching-runs/" + run["id"]).json()["status"] == "COMPLETED"
    finally:
        Job.fetch(job_id(UUID(run["id"])), connection=redis).delete()
        queue.delete(delete_jobs=True)
        worker.register_death()
        engine.dispose()
        redis.close()


def test_matching_origin_and_evidence_cannot_be_rewritten(client, auth_env):
    from sqlalchemy.exc import DBAPIError

    ids = inputs(client, auth_env)
    run = start(client, ids)
    execute_matching(UUID(run["id"]), auth_env)
    item = candidates(client, run)[0]
    engine = make_engine(auth_env)
    try:
        for model, identifier, field, value in [
            (MatchingRun, run["id"], "profile_hash", "changed"),
            (MatchCandidate, item["id"], "evidence", {"changed": True}),
        ]:
            with pytest.raises(DBAPIError), Session(engine) as session:
                setattr(session.get(model, UUID(identifier)), field, value)
                session.commit()
    finally:
        engine.dispose()


def test_concurrent_reviews_have_one_terminal_transition(client, auth_env, role_tokens):
    ids = inputs(client, auth_env)
    run = start(client, ids)
    execute_matching(UUID(run["id"]), auth_env)
    item = candidates(client, run, "POSSIBLE_MATCH")[0]

    def submit(status):
        with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as other:
            other.cookies.set(COOKIE_NAME, role_tokens["REVIEWER"])
            return other.post(
                "/api/v1/match-candidates/" + item["id"] + "/review",
                headers=ORIGIN,
                json={"status": status, "reason": "synthetic concurrent review"},
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(submit, ["MATCHED", "NOT_MATCHED"]))
    assert sorted(outcomes) == [200, 409]
