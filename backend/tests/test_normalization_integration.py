import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from traceback import extract_tb
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
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuditEvent
from app.common.database import make_engine
from app.imports.jobs import execute_import
from app.imports.jobs import job_id as import_job_id
from app.imports.models import ImportBatch, RawRecord
from app.main import create_app
from app.normalization.jobs import enqueue, execute_run, job_id, recover_runs
from app.normalization.models import AnalysisRun, EntityValue
from app.normalization.profiles import catalog
from tests.test_auth import ORIGIN, isolated_environment
from tests.test_auth import password as password
from tests.test_auth import role_tokens as role_tokens
from tests.test_imports import upload
from tests.test_policy import canonical_matrix

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FK_TEST_INTEGRATION") != "1", reason="integration services opt-in"
    ),
]
DATA = Path(__file__).resolve().parents[2] / "tests/data/normalization"
PROFILE = next(profile for profile in catalog().values() if profile.code == "synthetic-material")


@pytest.fixture(scope="module")
def auth_env(tmp_path_factory):
    environment = isolated_environment()
    base = next(environment)
    settings = base.model_copy(
        update={
            "import_storage_root": tmp_path_factory.mktemp("normalized-originals"),
            "import_queue_name": "normalization-test-" + uuid4().hex,
        }
    )
    yield settings
    engine = make_engine(settings)
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    queue = Queue(settings.import_queue_name, connection=redis)
    with Session(engine) as session:
        identifiers = [job_id(value) for value in session.scalars(select(AnalysisRun.id))]
        identifiers += [import_job_id(value) for value in session.scalars(select(ImportBatch.id))]
    for registry in [queue.finished_job_registry, queue.failed_job_registry]:
        identifiers += registry.get_job_ids()
    for identifier in set(identifiers):
        job = Job.fetch_many([identifier], connection=redis)[0]
        if job:
            job.delete()
    queue.delete(delete_jobs=True)
    redis.close()
    engine.dispose()
    try:
        next(environment)
    except StopIteration:
        pass


@pytest.fixture
def client(auth_env, role_tokens):
    with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as value:
        value.cookies.set(COOKIE_NAME, role_tokens["ADMIN"])
        yield value


def imported(client, settings, name="material.csv", payload=None):
    source = client.post(
        "/api/v1/sources",
        headers=ORIGIN,
        json={
            "code": uuid4().hex,
            "name": "Synthetic normalization",
            "source_type": "ONE_C" if name == "onec.xml" else "FILE",
        },
    ).json()
    response = upload(
        client, source["id"], name, (DATA / name).read_bytes() if payload is None else payload
    )
    assert response.status_code == 201, response.text
    identifier = response.json()["id"]
    execute_import(UUID(identifier), settings)
    assert client.get("/api/v1/imports/" + identifier).json()["status"] == "COMPLETED"
    return identifier


def start(client, batch):
    response = client.post(
        "/api/v1/analysis",
        headers=ORIGIN,
        json={"import_batch_ids": [batch], "template_id": str(PROFILE.id)},
    )
    assert response.status_code in {200, 201}, response.text
    return response.json()


def outputs(client, identifier):
    return client.get(f"/api/v1/analysis/{identifier}/records?limit=100").json()


@pytest.mark.parametrize("name", ["material.csv", "material.xlsx", "generic.xml", "onec.xml"])
def test_import_mapping_normalization_provenance_and_raw_immutability(client, auth_env, name):
    batch = imported(client, auth_env, name)
    before = client.get(f"/api/v1/imports/{batch}/records").json()
    run = start(client, batch)
    assert run["status"] == "QUEUED"
    assert start(client, batch)["id"] == run["id"]
    execute_run(UUID(run["id"]), auth_env)
    result = client.get("/api/v1/analysis/" + run["id"]).json()
    assert result["status"] == "COMPLETED" and result["records_processed"] == 5
    assert result["values_processed"] == 25
    records = outputs(client, run["id"])
    expected = json.loads((DATA / "expected.json").read_text())
    ordered = sorted(
        records,
        key=lambda record: next(
            value["raw_value"] for value in record["values"] if value["attribute_code"] == "code"
        ),
    )
    for record_index, record in enumerate(ordered):
        by_attribute = {value["attribute_code"]: value for value in record["values"]}
        for attribute, columns in {
            "mass": ["raw_value", "normalized_value", "unit", "quality_status"],
            "price": ["raw_value", "normalized_value", "quality_status"],
            "name": ["raw_value", "normalized_value"],
            "dates": ["raw_value", "normalized_value", "quality_status"],
        }.items():
            if record_index < len(expected[attribute]):
                value = by_attribute["manufactured_on" if attribute == "dates" else attribute]
                assert [value[column] for column in columns] == expected[attribute][record_index]
    masses = []
    for record in records:
        values = {value["attribute_code"]: value for value in record["values"]}
        masses.append(
            (
                values["code"]["raw_value"],
                values["mass"]["normalized_value"],
                values["mass"]["quality_status"],
            )
        )
        assert record["source"]["name"] == "Synthetic normalization"
        assert record["import_batch"]["id"] == batch
        assert record["source_position"]
        assert record["entity"]["status"] is None
        assert record["entity"]["domain"] == "synthetic-material"
        assert all(value["raw_record_id"] == record["raw_record_id"] for value in record["values"])
        assert all(
            value["normalization_rule"]["mapping"] == result["mapping_hash"]
            for value in record["values"]
        )
        assert "extra" in record["mapping_details"]["unmapped_fields"]
    assert sorted(masses) == [
        ("001", "12.5", "VALID"),
        ("002", "12.5", "VALID"),
        ("003", "12.5", "VALID"),
        ("004", None, "UNKNOWN"),
        ("005", None, "INVALID"),
    ]
    assert client.get(f"/api/v1/imports/{batch}/records").json() == before
    execute_run(UUID(run["id"]), auth_env)
    assert outputs(client, run["id"]) == records
    second = start(client, batch)
    assert second["id"] != run["id"]
    execute_run(UUID(second["id"]), auth_env)
    assert outputs(client, second["id"]) == records
    engine = make_engine(auth_env)
    with Session(engine) as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.object_id == UUID(run["id"]))
        ).all()
        assert {event.event_type for event in events} == {
            "NORMALIZATION_CREATED",
            "NORMALIZATION_QUEUED",
            "NORMALIZATION_PROCESSING",
            "NORMALIZATION_COMPLETED",
        }
        assert all(
            "raw_payload" not in event.payload
            and event.payload["mapping_hash"] == run["mapping_hash"]
            for event in events
        )
        value = session.get(EntityValue, UUID(records[0]["values"][0]["id"]))
        value.normalized_value = "changed"
        with pytest.raises(DBAPIError, match="append-only"):
            session.commit()
        session.rollback()
        session.get(RawRecord, UUID(records[0]["raw_record_id"])).raw_payload = {"changed": True}
        with pytest.raises(DBAPIError, match="append-only"):
            session.commit()
    engine.dispose()


def test_different_raw_records_remain_different_entities(client, auth_env):
    batches = [imported(client, auth_env) for _ in range(2)]
    entity_ids = []
    for batch in batches:
        run = start(client, batch)
        execute_run(UUID(run["id"]), auth_env)
        entity_ids.append({record["entity"]["id"] for record in outputs(client, run["id"])})
    assert not entity_ids[0] & entity_ids[1]


def test_real_rq_execution_and_concurrent_delivery(client, auth_env, monkeypatch):
    batch = imported(client, auth_env)
    run = start(client, batch)
    monkeypatch.setenv("FK_DATABASE_URL", auth_env.database_url.get_secret_value())
    monkeypatch.setenv("FK_REDIS_URL", auth_env.redis_url.get_secret_value())
    redis = Redis.from_url(auth_env.redis_url.get_secret_value())
    try:
        SimpleWorker([Queue(auth_env.import_queue_name, connection=redis)], connection=redis).work(
            burst=True, logging_level="ERROR"
        )
        assert client.get("/api/v1/analysis/" + run["id"]).json()["status"] == "COMPLETED"
        second = start(client, batch)
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda _: execute_run(UUID(second["id"]), auth_env), range(2)))
        assert len(outputs(client, second["id"])) == 5
    finally:
        redis.close()


def test_versioned_profiles_preserve_old_results(client, auth_env):
    batch = imported(client, auth_env)
    first = start(client, batch)
    execute_run(UUID(first["id"]), auth_env)
    original = outputs(client, first["id"])
    snapshot = PROFILE.snapshot()
    snapshot["version"] = "2"
    snapshot["bindings"][0]["fields"][1]["case"] = "lower"
    changed = type(PROFILE).model_validate(snapshot)
    with patch("app.normalization.routes.catalog", return_value={changed.id: changed}):
        second = start(client, batch)
    execute_run(UUID(second["id"]), auth_env)
    assert second["mapping_hash"] != first["mapping_hash"]
    assert {r["entity"]["id"] for r in outputs(client, second["id"])}.isdisjoint(
        {r["entity"]["id"] for r in original}
    )
    assert outputs(client, first["id"]) == original
    assert (
        client.get("/api/v1/analysis/" + first["id"]).json()["mapping_snapshot"]["version"] == "1"
    )


@pytest.mark.parametrize("failure", ["failure", "crash"])
def test_partial_checkpoint_retry_or_resume(client, auth_env, failure):
    batch = imported(
        client,
        auth_env,
        payload=("id,name,mass\n" + "".join(f"{n},Name,12.5 kg\n" for n in range(101))).encode(),
    )
    run = start(client, batch)
    from app.normalization.pipeline import build_record

    calls = 0

    def interrupted(*args):
        nonlocal calls
        calls += 1
        if calls > 100:
            if failure == "crash":
                raise SystemExit("synthetic hard-stop")
            raise RuntimeError("private-source-and-path-marker")
        return build_record(*args)

    with patch("app.normalization.jobs.build_record", side_effect=interrupted):
        if failure == "crash":
            with pytest.raises(SystemExit):
                execute_run(UUID(run["id"]), auth_env)
        else:
            execute_run(UUID(run["id"]), auth_env)
    detail = client.get("/api/v1/analysis/" + run["id"]).json()
    assert detail["records_processed"] == 100 and detail["status"] == (
        "PROCESSING" if failure == "crash" else "FAILED"
    )
    assert "private-source-and-path-marker" not in str(detail)
    target = run if failure == "crash" else start(client, batch)
    execute_run(UUID(target["id"]), auth_env)
    assert client.get("/api/v1/analysis/" + target["id"]).json()["records_processed"] == 101
    engine = make_engine(auth_env)
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(EntityValue)
                .where(
                    EntityValue.raw_record_id.in_(
                        select(RawRecord.id).where(RawRecord.import_batch_id == UUID(batch))
                    )
                )
            )
            == 505
        )
    engine.dispose()


def test_missing_job_recovery_and_late_enqueue(client, auth_env):
    batch = imported(client, auth_env)
    run = start(client, batch)
    redis = Redis.from_url(auth_env.redis_url.get_secret_value())
    engine = make_engine(auth_env)
    try:
        Job.fetch(job_id(UUID(run["id"])), connection=redis).delete()
        with Session(engine) as session:
            record = session.get(AnalysisRun, UUID(run["id"]))
            record.updated_at = datetime.now(UTC) - timedelta(minutes=2)
            session.commit()
        assert recover_runs(auth_env, redis) >= 1
        assert client.get("/api/v1/analysis/" + run["id"]).json()["status"] == "FAILED"
        with Session(engine) as session:
            enqueue(UUID(run["id"]), session, auth_env, redis)
        assert client.get("/api/v1/analysis/" + run["id"]).json()["status"] == "FAILED"
    finally:
        engine.dispose()
        redis.close()


def test_idle_worker_recovers_new_run_after_quick_restart(client, auth_env):
    from app.worker import ForestWorker

    batch = imported(client, auth_env)
    # Simulate the API stopping after its durable NEW commit, before publication.
    with patch("app.normalization.routes.enqueue"):
        run = start(client, batch)
    assert run["status"] == "NEW"
    redis = Redis.from_url(auth_env.redis_url.get_secret_value())
    engine = make_engine(auth_env)
    settings = auth_env.model_copy(update={"import_queue_name": "recovery-" + uuid4().hex})
    queue = Queue(settings.import_queue_name, connection=redis)
    worker = ForestWorker([queue], connection=redis, maintenance_interval=0)
    try:
        with patch("app.worker.Settings", return_value=settings):
            worker.run_maintenance_tasks()
            assert queue.count == 0  # Fresh work is intentionally protected for 60 seconds.
            with Session(engine) as session:
                record = session.get(AnalysisRun, UUID(run["id"]))
                record.updated_at = datetime.now(UTC) - timedelta(seconds=90)
                session.commit()
            # RQ's idle dequeue loop invokes maintenance again, without an API write.
            result = worker.dequeue_job_and_maintain_ttl(timeout=1, max_idle_time=2)
        assert result is not None and result[0].id == job_id(UUID(run["id"]))
        execute_run(UUID(run["id"]), auth_env)
        assert client.get("/api/v1/analysis/" + run["id"]).json()["status"] == "COMPLETED"
    finally:
        Job.fetch(job_id(UUID(run["id"])), connection=redis).delete()
        queue.delete(delete_jobs=True)
        worker.register_death()
        engine.dispose()
        redis.close()


def test_concurrent_start_requests_coalesce_one_active_run(client, auth_env, role_tokens):
    batch = imported(client, auth_env)
    recovery_errors = []

    def observe_recovery(*args, **kwargs):
        try:
            return recover_runs(*args, **kwargs)
        except Exception as error:
            # The public API deliberately sanitizes recovery failures. Retain only
            # diagnostic types/callsites here, never exception text, SQL or inputs.
            recovery_errors.append(
                {
                    "type": type(error).__name__,
                    "sqlstate": getattr(getattr(error, "orig", None), "sqlstate", None),
                    "frames": [
                        [Path(frame.filename).name, frame.name, frame.lineno]
                        for frame in extract_tb(error.__traceback__)
                        if "/app/" in frame.filename
                    ],
                }
            )
            raise

    def request(_):
        with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as other:
            other.cookies.set(COOKIE_NAME, role_tokens["ADMIN"])
            return start(other, batch)["id"]

    try:
        with (
            patch("app.normalization.routes.recover_runs", side_effect=observe_recovery),
            ThreadPoolExecutor(max_workers=6) as pool,
        ):
            identifiers = list(pool.map(request, range(6)))
    except Exception as error:
        error.add_note("Sanitized recovery diagnostics: " + json.dumps(recovery_errors))
        raise
    assert len(set(identifiers)) == 1
    execute_run(UUID(identifiers[0]), auth_env)
    assert client.get("/api/v1/analysis/" + identifiers[0]).json()["records_processed"] == 5


@pytest.mark.parametrize("role", ["VIEWER", "REVIEWER", "DATA_OWNER", "ADMIN", "NO_ROLES"])
@pytest.mark.parametrize(
    "path",
    [
        "",
        "/profiles",
        "/00000000-0000-0000-0000-000000000000",
        "/00000000-0000-0000-0000-000000000000/records",
    ],
)
def test_read_rbac(client, role_tokens, role, path):
    client.cookies.set(COOKIE_NAME, role_tokens[role])
    response = client.get("/api/v1/analysis" + path)
    assert response.status_code == (
        403 if role == "NO_ROLES" else 404 if path.startswith("/000") else 200
    )
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("role", ["VIEWER", "REVIEWER", "DATA_OWNER", "ADMIN", "NO_ROLES"])
def test_write_rbac_and_origin(client, role_tokens, role):
    client.cookies.set(COOKIE_NAME, role_tokens[role])
    body = {"import_batch_ids": [str(uuid4())], "template_id": str(PROFILE.id)}
    allowed = any(r.value == role for r in canonical_matrix()["analysis.run"])
    assert client.post("/api/v1/analysis", headers=ORIGIN, json=body).status_code == (
        404 if allowed else 403
    )
    assert client.post("/api/v1/analysis", json=body).status_code == 403


def test_migration_roundtrip_preserves_stage2_raw(client, auth_env):
    batch = imported(client, auth_env)
    before = client.get(f"/api/v1/imports/{batch}/records").json()
    configuration = AlembicConfig(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with patch.dict(os.environ, {"FK_DATABASE_URL": auth_env.database_url.get_secret_value()}):
        command.downgrade(configuration, "0003_imports")
        command.upgrade(configuration, "head")
        command.upgrade(configuration, "head")
    assert client.get(f"/api/v1/imports/{batch}/records").json() == before
