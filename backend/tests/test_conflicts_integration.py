import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.common.database import make_engine
from app.conflicts.jobs import execute_conflict
from app.conflicts.models import Conflict, ConflictRun
from app.main import create_app
from app.matching.jobs import execute_matching
from app.normalization.jobs import execute_run
from tests.test_auth import ORIGIN
from tests.test_auth import password as password
from tests.test_auth import role_tokens as role_tokens
from tests.test_matching_integration import auth_env as auth_env
from tests.test_matching_integration import candidates
from tests.test_matching_integration import start as matching_start
from tests.test_normalization_integration import imported
from tests.test_normalization_integration import start as normalization_start

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FK_TEST_INTEGRATION") != "1", reason="integration services opt-in"
    ),
]
DATA = Path(__file__).resolve().parents[2] / "tests/data/conflicts"


@pytest.fixture
def client(auth_env, role_tokens):
    with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as value:
        value.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
        yield value


def inputs(client, settings):
    ids = []
    for name, fixture in [("material.csv", "source-a.csv"), ("onec.xml", "source-b.xml")]:
        batch = imported(client, settings, name, (DATA / fixture).read_bytes())
        run = normalization_start(client, batch)
        execute_run(UUID(run["id"]), settings)
        ids.append(run["id"])
    run = matching_start(client, ids)
    execute_matching(UUID(run["id"]), settings)
    assert client.get("/api/v1/matching-runs/" + run["id"]).json()["status"] == "COMPLETED"
    return run


def start(client, matching):
    response = client.post(
        "/api/v1/conflict-runs", headers=ORIGIN, json={"matching_run_id": matching["id"]}
    )
    assert response.status_code in {200, 201}, response.text
    return response.json()


def rows(client, matching):
    response = client.get("/api/v1/conflicts?matching_run_id=" + matching["id"])
    assert response.status_code == 200, response.text
    return response.json()


def completed(client, run):
    value = client.get("/api/v1/conflict-runs/" + run["id"]).json()
    assert value["status"] == "COMPLETED", value
    return value


def test_real_path_no_false_conflicts_provenance_and_rerun(client, auth_env):
    matching = inputs(client, auth_env)
    before = [
        client.get("/api/v1/analysis/" + value + "/records").json()
        for value in matching["input_analysis_ids"]
    ]
    run = start(client, matching)
    assert start(client, matching)["id"] == run["id"]
    execute_conflict(UUID(run["id"]), auth_env)
    result = completed(client, run)
    records = rows(client, matching)
    assert len(records) == 2, records
    assert result["status_counts"] == {"VALUE_MISMATCH": 1, "MISSING": 1}
    for row in records:
        detail = client.get("/api/v1/conflicts/" + row["id"]).json()
        assert row["status"] == "OPEN" and row["severity"] == "LOW"
        assert "basis" not in row and "values_snapshot" not in row
        assert detail["human_decision"] == "NOT_TAKEN"
        assert detail["basis"]["authority"] == "NOT_DEFINED"
        assert detail["basis"]["identity_status"] == "MATCHED"
        assert len(detail["values_snapshot"]) == 2
        assert all(
            item["file_hash"] and item["source_position"] and item["value"]["value_id"]
            for item in detail["values_snapshot"]
        )
        assert {item["source_record_key"] for item in detail["values_snapshot"]} <= {"DIFF", "MISS"}
    assert [
        client.get("/api/v1/analysis/" + value + "/records").json()
        for value in matching["input_analysis_ids"]
    ] == before
    execute_conflict(UUID(run["id"]), auth_env)
    retry = start(client, matching)
    execute_conflict(UUID(retry["id"]), auth_env)
    assert rows(client, matching) == records
    assert completed(client, retry)["conflicts_generated"] == 2


def test_manual_duplicate_identities_and_frozen_inputs(client, auth_env):
    matching = inputs(client, auth_env)
    pending = candidates(client, matching, "POSSIBLE_MATCH")
    duplicate = []
    for candidate in pending:
        detail = client.get("/api/v1/match-candidates/" + candidate["id"]).json()
        if all(item["source_record_key"] == "DUP" for item in detail["records"]):
            duplicate.append(candidate)
    assert len(duplicate) == 2
    frozen = start(client, matching)
    for candidate in duplicate:
        response = client.post(
            "/api/v1/match-candidates/" + candidate["id"] + "/review",
            headers=ORIGIN,
            json={"status": "MATCHED", "reason": "Synthetic identity verified by human"},
        )
        assert response.status_code == 200, response.text
    execute_conflict(UUID(frozen["id"]), auth_env)
    assert completed(client, frozen)["conflicts_generated"] == 2
    new = start(client, matching)
    execute_conflict(UUID(new["id"]), auth_env)
    assert completed(client, new)["status_counts"]["DUPLICATE"] == 2
    duplicates = [item for item in rows(client, matching) if item["conflict_type"] == "DUPLICATE"]
    assert len(duplicates) == 2
    for item in duplicates:
        evidence = client.get("/api/v1/conflicts/" + item["id"]).json()["basis"]
        assert evidence["duplicate_identity_peers"]
        assert evidence["confirmed_by"]
        assert evidence["human_match_review"]["audit_event_id"]


def test_concurrency_duplicate_delivery_and_transaction_failure(client, auth_env, role_tokens):
    matching = inputs(client, auth_env)

    def request(_):
        with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as other:
            other.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
            return start(other, matching)["id"]

    with ThreadPoolExecutor(4) as pool:
        identifiers = list(pool.map(request, range(4)))
    assert len(set(identifiers)) == 1
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(lambda _: execute_conflict(UUID(identifiers[0]), auth_env), range(3)))
    assert len(rows(client, matching)) == 2
    retry = start(client, matching)
    with patch(
        "app.conflicts.jobs.process_chunk", side_effect=RuntimeError("do not expose raw data")
    ):
        execute_conflict(UUID(retry["id"]), auth_env)
    failed = client.get("/api/v1/conflict-runs/" + retry["id"]).json()
    assert failed["status"] == "FAILED" and failed["error_text"] == "CONFLICT_INTERRUPTED"
    next_run = start(client, matching)
    execute_conflict(UUID(next_run["id"]), auth_env)
    assert completed(client, next_run)["conflicts_generated"] == 2
    assert len(rows(client, matching)) == 2


@pytest.mark.parametrize("role", ["VIEWER", "REVIEWER", "DATA_OWNER", "ADMIN", "NO_ROLES"])
@pytest.mark.parametrize(
    "path",
    [
        "/conflicts",
        "/conflict-runs",
        "/conflicts/00000000-0000-0000-0000-000000000000",
        "/conflict-runs/00000000-0000-0000-0000-000000000000",
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
def test_start_permission_origin_no_business_actions(client, role_tokens, role):
    client.cookies.set(COOKIE_NAME, role_tokens[role])
    data = {"matching_run_id": str(uuid4())}
    response = client.post("/api/v1/conflict-runs", headers=ORIGIN, json=data)
    assert response.status_code == (403 if role in {"VIEWER", "NO_ROLES"} else 404)
    assert client.post("/api/v1/conflict-runs", json=data).status_code == 403
    assert (
        client.post(
            "/api/v1/conflicts/" + str(uuid4()) + "/decisions", headers=ORIGIN, json={}
        ).status_code
        == 404
    )


def test_guards_pagination_filters_and_fresh_app_persistence(client, auth_env, role_tokens):
    matching = inputs(client, auth_env)
    run = start(client, matching)
    execute_conflict(UUID(run["id"]), auth_env)
    record = rows(client, matching)[0]
    engine = make_engine(auth_env)
    try:
        for sql in [
            "UPDATE conflicts SET basis='{}' WHERE id=:id",
            "UPDATE conflicts SET status='RESOLVED' WHERE id=:id",
            "DELETE FROM conflicts WHERE id=:id",
        ]:
            with engine.connect() as connection:
                with pytest.raises(DBAPIError):
                    connection.execute(text(sql), {"id": UUID(record["id"])})
                connection.rollback()
        with Session(engine) as session:
            assert session.scalar(select(Conflict).where(Conflict.id == UUID(record["id"])))
            assert session.get(ConflictRun, UUID(run["id"])).status == "COMPLETED"
    finally:
        engine.dispose()
    detail = client.get("/api/v1/conflicts/" + record["id"]).json()
    source_id = detail["values_snapshot"][0]["source_id"]
    assert len(client.get("/api/v1/conflicts?source_id=" + source_id).json()) == 2
    with patch("app.conflicts.routes.CONFIG_HASH", "f" * 64):
        previous = client.get("/api/v1/conflicts/" + record["id"]).json()
        assert previous["based_on_previous_profile"] is True
        assert previous["basis"] == detail["basis"]
    client.cookies.clear()
    assert client.get("/api/v1/conflicts").status_code == 401
    assert client.get("/api/v1/conflicts/" + record["id"]).status_code == 401
    client.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])

    with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as other:
        other.cookies.set(COOKIE_NAME, role_tokens["VIEWER"])
        assert other.get("/api/v1/conflicts/" + record["id"]).json() == detail
    assert (
        len(
            client.get(
                "/api/v1/conflicts?matching_run_id=" + matching["id"] + "&conflict_type=MISSING"
            ).json()
        )
        == 1
    )
    assert (
        len(client.get("/api/v1/conflicts?matching_run_id=" + matching["id"] + "&limit=1").json())
        == 1
    )
    for query in [
        "limit=101",
        "offset=-1",
        "conflict_type=FORMAT",
        "severity=EXTREME",
        "status=ACCEPTED",
    ]:
        assert client.get("/api/v1/conflicts?" + query).status_code == 422


@pytest.mark.parametrize("failure", ["exception", "hard_stop"])
def test_atomic_checkpoint_resume_and_partial_retry(client, auth_env, failure):
    payloads = [
        (
            "id,name,mass,price,date\n"
            + "".join(f"{i:06},Material{i:06},{mass} kg,1,2026-10-20\n" for i in range(101))
        ).encode()
        for mass in [1, 2]
    ]
    normalized = []
    for payload in payloads:
        batch = imported(client, auth_env, "material.csv", payload)
        analysis = normalization_start(client, batch)
        execute_run(UUID(analysis["id"]), auth_env)
        normalized.append(analysis["id"])
    matching = matching_start(client, normalized)
    execute_matching(UUID(matching["id"]), auth_env)
    run = start(client, matching)
    from app.conflicts.pipeline import process_chunk

    class HardStop(BaseException):
        pass

    calls = 0

    def interrupted(session, execution):
        nonlocal calls
        calls += 1
        result = process_chunk(session, execution)
        if calls == 2:
            if failure == "hard_stop":
                raise HardStop()
            raise RuntimeError("synthetic interruption")
        return result

    with patch("app.conflicts.jobs.process_chunk", side_effect=interrupted):
        if failure == "hard_stop":
            with pytest.raises(HardStop):
                execute_conflict(UUID(run["id"]), auth_env)
        else:
            execute_conflict(UUID(run["id"]), auth_env)
    partial = client.get("/api/v1/conflict-runs/" + run["id"]).json()
    assert partial["records_processed"] == partial["conflicts_generated"] == 100
    assert partial["status"] == ("PROCESSING" if failure == "hard_stop" else "FAILED")
    target = run if failure == "hard_stop" else start(client, matching)
    execute_conflict(UUID(target["id"]), auth_env)
    assert completed(client, target)["conflicts_generated"] == 101
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            records = session.scalars(
                select(Conflict).where(Conflict.matching_run_id == UUID(matching["id"]))
            ).all()
            assert len(records) == 101
    finally:
        engine.dispose()


def test_real_rq_delivery_and_stale_recovery(client, auth_env, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from redis import Redis
    from rq import Queue, SimpleWorker

    from app.conflicts.jobs import recover_runs

    matching = inputs(client, auth_env)
    monkeypatch.setenv("FK_DATABASE_URL", auth_env.database_url.get_secret_value())
    monkeypatch.setenv("FK_REDIS_URL", auth_env.redis_url.get_secret_value())
    monkeypatch.setenv("FK_IMPORT_STORAGE_ROOT", str(auth_env.import_storage_root))
    monkeypatch.setenv("FK_IMPORT_QUEUE_NAME", auth_env.import_queue_name)
    redis = Redis.from_url(auth_env.redis_url.get_secret_value())
    try:
        with patch("app.conflicts.routes.enqueue"):
            run = start(client, matching)
        assert recover_runs(auth_env, redis) == 0
        engine = make_engine(auth_env)
        with Session(engine) as session:
            execution = session.get(ConflictRun, UUID(run["id"]))
            execution.updated_at = datetime.now(UTC) - timedelta(seconds=120)
            session.commit()
        engine.dispose()
        assert recover_runs(auth_env, redis) == 1
        SimpleWorker([Queue(auth_env.import_queue_name, connection=redis)], connection=redis).work(
            burst=True, logging_level="ERROR"
        )
        assert completed(client, run)["conflicts_generated"] == 2
    finally:
        redis.close()


def test_migration_from_stage4_repeat_roundtrip_preserves_history(client, auth_env, monkeypatch):
    from alembic import command
    from alembic.config import Config as AlembicConfig
    from sqlalchemy import func

    from app.imports.models import RawRecord
    from app.matching.models import MatchCandidate
    from app.normalization.models import EntityValue

    matching = inputs(client, auth_env)
    engine = make_engine(auth_env)

    def history():
        with Session(engine) as session:
            return [
                session.scalar(select(func.count()).select_from(model))
                for model in [RawRecord, EntityValue, MatchCandidate]
            ]

    before = history()
    monkeypatch.setenv("FK_DATABASE_URL", auth_env.database_url.get_secret_value())
    config = AlembicConfig("alembic.ini")
    command.downgrade(config, "0005_matching")
    assert history() == before
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    assert history() == before
    run = start(client, matching)
    execute_conflict(UUID(run["id"]), auth_env)
    assert completed(client, run)["conflicts_generated"] == 2
    engine.dispose()


def test_absent_csv_schema_column_does_not_create_missing_conflict(client, auth_env):
    normal = []
    for payload in [
        b"id,name,price,date\nSCHEMA,Schema Bolt,1,2026-01-01\n",
        b"id,name,mass,price,date\nSCHEMA,Schema Bolt,1 kg,2,2026-01-01\n",
    ]:
        batch = imported(client, auth_env, "material.csv", payload)
        analysis = normalization_start(client, batch)
        execute_run(UUID(analysis["id"]), auth_env)
        normal.append(analysis["id"])
    matching = matching_start(client, normal)
    execute_matching(UUID(matching["id"]), auth_env)
    run = start(client, matching)
    execute_conflict(UUID(run["id"]), auth_env)
    result = completed(client, run)
    assert result["conflicts_generated"] == 1
    assert [(row["attribute_code"], row["conflict_type"]) for row in rows(client, matching)] == [
        ("price", "VALUE_MISMATCH")
    ]
