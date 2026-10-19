import json
import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula
from redis import Redis
from rq import Queue, SimpleWorker
from rq.job import Job
from sqlalchemy import delete, func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuditEvent
from app.common.database import make_engine
from app.imports.jobs import enqueue_batch, execute_import, job_id, recover_imports
from app.imports.models import ImportBatch, ImportStatus, RawRecord, SourceSystem
from app.imports.parsers import parse_records
from app.imports.storage import LocalStorage, file_checksum
from app.main import create_app
from tests.test_auth import ORIGIN, isolated_environment
from tests.test_auth import password as password
from tests.test_auth import role_tokens as role_tokens
from tests.test_policy import canonical_matrix

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FK_TEST_INTEGRATION") != "1",
        reason="integration services opt-in",
    ),
]
DATA = Path(__file__).resolve().parents[2] / "tests/data/import"
MANIFEST = json.loads((DATA / "manifest.json").read_text())


@pytest.fixture(scope="module")
def auth_env(tmp_path_factory):
    environment = isolated_environment()
    base = next(environment)
    settings = base.model_copy(
        update={
            "import_storage_root": tmp_path_factory.mktemp("originals"),
            "import_queue_name": "test-import-" + uuid4().hex,
        }
    )
    yield settings
    connection = Redis.from_url(settings.redis_url.get_secret_value())
    engine = make_engine(settings)
    with Session(engine) as session:
        for batch_id in session.scalars(select(ImportBatch.id)):
            job = Job.fetch_many([job_id(batch_id)], connection=connection)[0]
            if job:
                job.delete()
    Queue(settings.import_queue_name, connection=connection).delete(delete_jobs=True)
    connection.close()
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


@pytest.fixture
def source(auth_env):
    engine = make_engine(auth_env)
    with Session(engine) as session:
        item = SourceSystem(name="Synthetic", code="source_" + uuid4().hex, source_type="FILE")
        session.add(item)
        session.commit()
        result = str(item.id)
    engine.dispose()
    return result


def upload(client, source, name="valid.csv", payload=None):
    return client.post(
        "/api/v1/imports",
        headers=ORIGIN,
        data={"source_id": source},
        files={"file": (name, (DATA / name).read_bytes() if payload is None else payload)},
    )


def current(client, batch_id):
    return client.get(f"/api/v1/imports/{batch_id}").json()


@pytest.mark.parametrize(
    "name", [name for name in MANIFEST if name not in {"duplicate.csv", "unsupported.txt"}]
)
def test_upload_worker_raw_and_error_summary(client, auth_env, source, name):
    expected = MANIFEST[name]
    engine = make_engine(auth_env)
    if name == "onec.xml":
        with Session(engine) as session:
            session.get(SourceSystem, UUID(source)).source_type = "ONE_C"
            session.commit()
    response = upload(client, source, name)
    assert response.status_code == 201, response.text
    batch_id = UUID(response.json()["id"])
    assert response.json()["status"] == "QUEUED"
    execute_import(batch_id, auth_env)
    result = current(client, batch_id)
    assert result["status"] == expected["status"]
    assert result["records_loaded"] == expected["records"]
    assert result["records_failed"] == expected["errors"]
    assert result["source_system_id"] == source and "storage_uri" not in result
    with Session(engine) as session:
        batch = session.get(ImportBatch, batch_id)
        stored = LocalStorage(auth_env.import_storage_root).path(batch.storage_uri)
        assert stored.read_bytes() == (DATA / name).read_bytes()
        assert file_checksum(stored) == result["file_hash"]
        ids = set(
            session.scalars(select(RawRecord.id).where(RawRecord.import_batch_id == batch_id))
        )
        events = session.scalars(select(AuditEvent).where(AuditEvent.object_id == batch_id)).all()
        expected_events = {
            "IMPORT_UPLOADED",
            "IMPORT_QUEUED",
            "IMPORT_PROCESSING",
            "IMPORT_" + result["status"],
        }
        assert expected_events <= {event.event_type for event in events}
        assert all(event.payload["source_system_id"] == source for event in events)
    execute_import(batch_id, auth_env)
    with Session(engine) as session:
        assert (
            set(session.scalars(select(RawRecord.id).where(RawRecord.import_batch_id == batch_id)))
            == ids
        )
    records = client.get(f"/api/v1/imports/{batch_id}/records").json()
    errors = client.get(f"/api/v1/imports/{batch_id}/errors").json()
    assert len(records) == expected["records"] and len(errors) == expected["errors"]
    if "first_position" in expected:
        assert any(
            row["source_position"].items() >= expected["first_position"].items() for row in records
        )
    engine.dispose()


def test_real_rq_executes_import_job(client, auth_env, source, monkeypatch):
    batch_id = upload(client, source).json()["id"]
    monkeypatch.setenv("FK_DATABASE_URL", auth_env.database_url.get_secret_value())
    monkeypatch.setenv("FK_REDIS_URL", auth_env.redis_url.get_secret_value())
    monkeypatch.setenv("FK_IMPORT_STORAGE_ROOT", str(auth_env.import_storage_root))
    connection = Redis.from_url(auth_env.redis_url.get_secret_value())
    queue = Queue(auth_env.import_queue_name, connection=connection)
    own_queue = Queue(auth_env.import_queue_name + "-worker", connection=connection)
    job = Job.fetch(job_id(UUID(batch_id)), connection=connection)
    queue.remove(job.id)
    own_queue.enqueue_job(job)
    SimpleWorker([own_queue], connection=connection).work(burst=True, logging_level="WARNING")
    assert current(client, batch_id)["status"] == "COMPLETED"
    assert current(client, batch_id)["records_loaded"] == 2
    job.refresh()
    assert job.is_finished
    own_queue.delete(delete_jobs=True)
    connection.close()


def test_duplicate_upload_is_scoped_to_source(client, auth_env, source):
    first = upload(client, source).json()
    response = upload(client, source, "duplicate.csv")
    assert response.status_code == 200 and response.json()["duplicate"] is True
    assert response.json()["id"] == first["id"]
    assert response.json()["original_filename"] == "valid.csv"
    assert client.get("/api/v1/imports").headers["cache-control"] == "no-store"
    other = client.post(
        "/api/v1/sources",
        headers=ORIGIN,
        json={
            "name": "Other",
            "code": uuid4().hex,
            "source_type": "FILE",
        },
    ).json()
    assert upload(client, other["id"]).json()["id"] != first["id"]
    engine = make_engine(auth_env)
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ImportBatch)
                .where(ImportBatch.source_system_id == UUID(source))
            )
            == 1
        )
    engine.dispose()


@pytest.mark.parametrize(
    "name,status",
    [("../escape.csv", 422), ("x\\a.csv", 422), ("malware.xlsm", 415), ("bad.exe", 415)],
)
def test_unsafe_upload_name_or_format(client, source, auth_env, name, status):
    before = set(auth_env.import_storage_root.iterdir())
    assert upload(client, source, name, b"id\n1\n").status_code == status
    assert set(auth_env.import_storage_root.iterdir()) == before


def test_oversized_uploads_including_chunked(auth_env, source, role_tokens):
    settings = auth_env.model_copy(update={"import_max_bytes": 1024})
    with TestClient(create_app(settings=settings), base_url="https://localhost:8443") as client:
        client.cookies.set(COOKIE_NAME, role_tokens["ADMIN"])
        assert upload(client, source, payload=b"x" * 1025).status_code == 413
        response = client.post(
            "/api/v1/imports",
            headers={
                **ORIGIN,
                "Content-Type": "multipart/form-data; boundary=test",
            },
            content=iter([b"x" * 70000]),
        )
        assert response.status_code == 413


def test_raw_and_original_metadata_immutable(client, auth_env, source):
    batch_id = UUID(upload(client, source).json()["id"])
    execute_import(batch_id, auth_env)
    engine = make_engine(auth_env)
    with Session(engine) as session:
        record = session.scalar(select(RawRecord).where(RawRecord.import_batch_id == batch_id))
        record.raw_payload = {"changed": True}
        with pytest.raises(DBAPIError, match="append-only"):
            session.commit()
        session.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(delete(RawRecord).where(RawRecord.import_batch_id == batch_id))
        session.rollback()
        session.get(ImportBatch, batch_id).file_hash = "0" * 64
        with pytest.raises(DBAPIError, match="immutable"):
            session.commit()
        session.rollback()
    engine.dispose()


def test_queue_failure_and_retry_new_batch(client, auth_env, source):
    with patch("app.imports.jobs.Queue.enqueue", side_effect=ConnectionError("private internals")):
        response = upload(client, source)
    first = response.json()
    assert first["status"] == "FAILED" and "private" not in response.text
    response = client.post(f"/api/v1/imports/{first['id']}/retry", headers=ORIGIN)
    assert response.status_code == 201
    second = response.json()
    assert second["id"] != first["id"] and second["retry_of_id"] == first["id"]
    execute_import(UUID(second["id"]), auth_env)
    assert current(client, second["id"])["status"] == "COMPLETED"
    assert current(client, first["id"])["status"] == "FAILED"


def test_worker_interrupted_chunk_survives_and_retry_is_new(client, auth_env, source):
    body = b"id,name\n" + b"".join(f"{n:04},value\n".encode() for n in range(600))
    batch_id = UUID(upload(client, source, payload=body).json()["id"])

    def interrupted(*args):
        for number, item in enumerate(parse_records(*args)):
            if number == 501:
                raise RuntimeError("worker interrupted")
            yield item

    with patch("app.imports.jobs.parse_records", interrupted):
        execute_import(batch_id, auth_env)
    assert current(client, batch_id)["status"] == "FAILED"
    assert current(client, batch_id)["records_loaded"] == 500
    new = client.post(f"/api/v1/imports/{batch_id}/retry", headers=ORIGIN).json()
    execute_import(UUID(new["id"]), auth_env)
    assert current(client, new["id"])["records_loaded"] == 600
    assert current(client, batch_id)["records_loaded"] == 500


def test_missing_job_recovery(client, auth_env, source):
    batch_id = UUID(upload(client, source).json()["id"])
    connection = Redis.from_url(auth_env.redis_url.get_secret_value())
    Job.fetch(job_id(batch_id), connection=connection).delete()
    engine = make_engine(auth_env)
    with Session(engine) as session:
        session.get(ImportBatch, batch_id).updated_at = datetime.now(UTC) - timedelta(minutes=5)
        session.commit()
    assert recover_imports(auth_env, connection) >= 1
    assert current(client, batch_id)["status"] == "FAILED"
    engine.dispose()
    connection.close()


OPERATIONS = [
    ("GET", "/sources", "source.view"),
    ("POST", "/sources", "source.manage"),
    ("GET", "/sources/{source}", "source.view"),
    ("PATCH", "/sources/{source}", "source.manage"),
    ("GET", "/imports", "import.view"),
    ("POST", "/imports", "import.create"),
    ("GET", "/imports/{batch}", "import.view"),
    ("GET", "/imports/{batch}/records", "import.view"),
    ("GET", "/imports/{batch}/errors", "import.view"),
    ("POST", "/imports/{batch}/retry", "import.retry"),
]


@pytest.mark.parametrize("role", ["VIEWER", "REVIEWER", "DATA_OWNER", "ADMIN", "NO_ROLES"])
@pytest.mark.parametrize("method,path,permission", OPERATIONS)
def test_source_import_routes_follow_xlsx(
    client, role_tokens, source, method, path, permission, role
):
    path = path.format(source=source, batch=uuid4())
    client.cookies.set(COOKIE_NAME, role_tokens[role])
    if path == "/imports" and method == "POST":
        response = upload(client, source)
    else:
        body = (
            {"name": "Synthetic", "code": uuid4().hex, "source_type": "FILE"}
            if method == "POST"
            else {"name": "Updated"}
        )
        response = client.request(
            method,
            "/api/v1" + path,
            headers=ORIGIN,
            **({"json": body} if method in {"POST", "PATCH"} else {}),
        )
    if role not in canonical_matrix()[permission]:
        assert response.status_code == 403
    else:
        assert response.status_code in {200, 201, 404}, response.text


@pytest.mark.parametrize(
    "name,payload,source_type",
    [
        ("invalid.csv", b"id,name\n1,Good\n2,Bad\x00value\n3,Good\n", "FILE"),
        (
            "invalid.xml",
            (
                '<Выгрузка><Объект Тип="Valid" Ид="1"/>'
                '<Объект Тип="' + "x" * 201 + '" Ид="2"/>'
                '<Объект Тип="Valid" Ид="3"/></Выгрузка>'
            ).encode(),
            "ONE_C",
        ),
    ],
)
def test_postgres_unsafe_record_is_partial_not_a_failed_chunk(
    client, auth_env, source, name, payload, source_type
):
    engine = make_engine(auth_env)
    with Session(engine) as session:
        session.get(SourceSystem, UUID(source)).source_type = source_type
        session.commit()
    batch_id = UUID(upload(client, source, name, payload).json()["id"])
    execute_import(batch_id, auth_env)
    result = current(client, batch_id)
    assert result["status"] == "COMPLETED_WITH_ERRORS"
    assert result["records_loaded"] == 2 and result["records_failed"] == 1
    assert client.get(f"/api/v1/imports/{batch_id}/errors").json()[0]["code"] == "INVALID_RAW_VALUE"
    engine.dispose()


def test_recovery_defers_to_worker_lock_and_never_overwrites_completion(client, auth_env, source):
    from sqlalchemy import text

    from app.imports.jobs import batch_lock_key

    batch_id = UUID(upload(client, source).json()["id"])
    engine = make_engine(auth_env)
    with Session(engine) as session:
        session.get(ImportBatch, batch_id).updated_at = datetime.now(UTC) - timedelta(minutes=5)
        session.commit()
    connection = Redis.from_url(auth_env.redis_url.get_secret_value())
    with engine.connect() as worker_lock:
        worker_lock.execute(
            text("SELECT pg_advisory_lock(:key)"), {"key": batch_lock_key(batch_id)}
        )
        worker_lock.commit()
        assert recover_imports(auth_env, connection) == 0
        assert current(client, batch_id)["status"] == "QUEUED"
        worker_lock.execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": batch_lock_key(batch_id)}
        )
        worker_lock.commit()
    execute_import(batch_id, auth_env)
    assert recover_imports(auth_env, connection) == 0
    assert current(client, batch_id)["status"] == "COMPLETED"
    engine.dispose()
    connection.close()


def test_recovery_resumes_registration_crash_at_new(client, auth_env, source):
    # Simulate API death after file+NEW were committed, before queue publication.
    with patch("app.imports.routes.enqueue_batch"):
        batch_id = UUID(upload(client, source).json()["id"])
    engine = make_engine(auth_env)
    with Session(engine) as session:
        session.get(ImportBatch, batch_id).updated_at = datetime.now(UTC) - timedelta(minutes=5)
        session.commit()
    connection = Redis.from_url(auth_env.redis_url.get_secret_value())
    assert recover_imports(auth_env, connection) == 1
    assert current(client, batch_id)["status"] == "QUEUED"
    assert Job.fetch(job_id(batch_id), connection=connection)
    execute_import(batch_id, auth_env)
    assert current(client, batch_id)["status"] == "COMPLETED"
    engine.dispose()
    connection.close()


def test_concurrent_duplicates_only_register_one_original(client, auth_env, source, role_tokens):
    from concurrent.futures import ThreadPoolExecutor

    def upload_one(_):
        with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as value:
            value.cookies.set(COOKIE_NAME, role_tokens["ADMIN"])
            result = upload(value, source)
            return result.status_code, result.json()["id"]

    before = set(auth_env.import_storage_root.iterdir())
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(upload_one, range(4)))
    assert sorted(status for status, _ in results) == [200, 200, 200, 201]
    assert len({identifier for _, identifier in results}) == 1
    assert len(set(auth_env.import_storage_root.iterdir()) - before) == 1


def test_upload_origin_and_authorization_are_required(auth_env, source, role_tokens):
    with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as value:
        assert upload(value, source).status_code == 401
        value.cookies.set(COOKIE_NAME, role_tokens["ADMIN"])
        response = value.post(
            "/api/v1/imports",
            data={"source_id": source},
            files={"file": ("valid.csv", (DATA / "valid.csv").read_bytes())},
        )
        assert response.status_code == 403
        response = value.post(
            "/api/v1/imports",
            headers={**ORIGIN, "Authorization": "Bearer " + role_tokens["ADMIN"]},
            data={"source_id": source},
            files={"file": ("valid.csv", (DATA / "valid.csv").read_bytes())},
        )
        assert response.status_code == 401


def test_resuming_processing_keeps_previously_committed_raw_id(client, auth_env, source):
    from app.imports.service import transition

    batch_id = UUID(upload(client, source).json()["id"])
    first_id = uuid4()
    engine = make_engine(auth_env)
    with Session(engine) as session:
        transition(session, session.get(ImportBatch, batch_id), ImportStatus.PROCESSING)
        session.add(
            RawRecord(
                id=first_id,
                import_batch_id=batch_id,
                source_record_key="001",
                source_object_type="record",
                raw_payload={"id": "001", "name": "Болт, сталь", "price": "001.2300"},
                source_position={"line_start": 2, "line_end": 2},
                position_key="csv:1",
            )
        )
        session.commit()
    execute_import(batch_id, auth_env)
    assert current(client, batch_id)["records_loaded"] == 2
    with Session(engine) as session:
        assert session.get(RawRecord, first_id).raw_payload["price"] == "001.2300"
    engine.dispose()


def test_changed_original_never_completes(client, auth_env, source):
    batch_id = UUID(upload(client, source).json()["id"])
    engine = make_engine(auth_env)
    with Session(engine) as session:
        path = LocalStorage(auth_env.import_storage_root).path(
            session.get(ImportBatch, batch_id).storage_uri
        )
        path.chmod(0o600)
        path.write_bytes(b"id\nchanged\n")
    execute_import(batch_id, auth_env)
    assert current(client, batch_id)["status"] == "FAILED"
    assert current(client, batch_id)["records_loaded"] == 0
    engine.dispose()


def test_broken_multiline_csv_does_not_store_field_fragments(client, auth_env, source):
    payload = (
        'id,name\n1,Before\n2,"' + "x" * 1_000_001 + '\n3,phantom\ntail"\n4,After\n'
    ).encode()
    batch_id = UUID(upload(client, source, payload=payload).json()["id"])
    execute_import(batch_id, auth_env)
    result = current(client, batch_id)
    assert result["status"] == "FAILED"
    assert result["records_loaded"] == 1 and result["records_failed"] == 1
    raw = client.get(f"/api/v1/imports/{batch_id}/records").json()
    assert [item["raw_payload"] for item in raw] == [{"id": "1", "name": "Before"}]
    error = client.get(f"/api/v1/imports/{batch_id}/errors").json()[0]
    assert error["code"] == "INVALID_CSV_STRUCTURE"
    assert error["source_position"]["line_start"] == 3
    engine = make_engine(auth_env)
    with Session(engine) as session:
        original = session.get(ImportBatch, batch_id)
        assert (
            LocalStorage(auth_env.import_storage_root).path(original.storage_uri).read_bytes()
            == payload
        )
    engine.dispose()


@pytest.mark.parametrize("kind", ["duration", "array", "data_table"])
def test_typed_xlsx_finishes_and_preserves_all_records(client, auth_env, source, kind):
    value = {
        "duration": timedelta(hours=25, minutes=30),
        "array": ArrayFormula(ref="B3", text="=SUM(1,2)"),
        "data_table": DataTableFormula(ref="B3", r1="B2"),
    }[kind]
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["id", "value"])
    sheet.append(["001", "Before"])
    sheet.append(["002", value])
    sheet.append(["003", "After"])
    stream = BytesIO()
    workbook.save(stream)
    batch_id = UUID(upload(client, source, "typed.xlsx", stream.getvalue()).json()["id"])
    execute_import(batch_id, auth_env)
    result = current(client, batch_id)
    assert result["status"] == "COMPLETED"
    assert result["records_loaded"] == 3 and result["records_failed"] == 0
    rows = client.get(f"/api/v1/imports/{batch_id}/records").json()
    assert {item["source_record_key"] for item in rows} == {"001", "002", "003"}
    value = next(
        item["raw_payload"]["value"] for item in rows if item["source_record_key"] == "002"
    )
    if kind == "duration":
        assert value == {"excel_type": "timedelta", "days": 1, "seconds": 5400, "microseconds": 0}
    else:
        assert value["attributes"]["ref"] == "B3"
        if kind == "array":
            assert value["text"] == "=SUM(1,2)"


@pytest.mark.parametrize(
    "target", [status for status in ImportStatus if status != ImportStatus.NEW]
)
def test_delayed_enqueue_does_not_overwrite_fresh_state_or_republish(
    client, auth_env, source, target
):
    from app.imports.service import transition

    with patch("app.imports.routes.enqueue_batch"):
        batch_id = UUID(upload(client, source).json()["id"])
    engine = make_engine(auth_env)
    connection = Redis.from_url(auth_env.redis_url.get_secret_value())
    queue = Queue(auth_env.import_queue_name, connection=connection)
    try:
        with Session(engine) as delayed:
            cached = delayed.get(ImportBatch, batch_id)
            assert cached.status == ImportStatus.NEW
            with Session(engine) as other:
                batch = other.get(ImportBatch, batch_id)
                transition(other, batch, ImportStatus.QUEUED)
                if target != ImportStatus.QUEUED:
                    transition(other, batch, ImportStatus.PROCESSING)
                    if target != ImportStatus.PROCESSING:
                        transition(other, batch, target)
                other.commit()
                events = other.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.object_id == batch_id)
                )
            before = queue.count
            enqueue_batch(batch_id, delayed, connection, auth_env)
            assert cached.status == target
            assert queue.count == before
            assert Job.fetch_many([job_id(batch_id)], connection=connection)[0] is None
            assert (
                delayed.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.object_id == batch_id)
                )
                == events
            )
    finally:
        connection.close()
        engine.dispose()


def test_delayed_upload_after_recovery_and_real_rq_completion_is_noop(
    client, auth_env, source, monkeypatch
):
    with patch("app.imports.routes.enqueue_batch"):
        batch_id = UUID(upload(client, source).json()["id"])
    monkeypatch.setenv("FK_DATABASE_URL", auth_env.database_url.get_secret_value())
    monkeypatch.setenv("FK_REDIS_URL", auth_env.redis_url.get_secret_value())
    monkeypatch.setenv("FK_IMPORT_STORAGE_ROOT", str(auth_env.import_storage_root))
    engine = make_engine(auth_env)
    connection = Redis.from_url(auth_env.redis_url.get_secret_value())
    queue = Queue(auth_env.import_queue_name, connection=connection)
    own_queue = Queue(auth_env.import_queue_name + "-delayed", connection=connection)
    try:
        with Session(engine) as delayed:
            cached = delayed.get(ImportBatch, batch_id)
            assert cached.status == "NEW"
            with Session(engine) as other:
                other.get(ImportBatch, batch_id).updated_at = datetime.now(UTC) - timedelta(
                    minutes=5
                )
                other.commit()
            assert recover_imports(auth_env, connection) >= 1
            job = Job.fetch(job_id(batch_id), connection=connection)
            queue.remove(job.id)
            own_queue.enqueue_job(job)
            SimpleWorker([own_queue], connection=connection).work(
                burst=True, logging_level="WARNING"
            )
            assert current(client, batch_id)["status"] == "COMPLETED"
            before = client.get(f"/api/v1/imports/{batch_id}/records").json()
            before_queue = queue.count
            assert cached.status == "NEW"  # Original request has not refreshed its ORM state.
            enqueue_batch(batch_id, delayed, connection, auth_env)
            job.refresh()
            assert job.is_finished and queue.count == before_queue
            assert current(client, batch_id)["status"] == "COMPLETED"
            assert client.get(f"/api/v1/imports/{batch_id}/records").json() == before
    finally:
        own_queue.delete(delete_jobs=True)
        connection.close()
        engine.dispose()


def test_initial_enqueue_defers_to_shared_worker_lock(client, auth_env, source):
    from sqlalchemy import text

    from app.imports.jobs import batch_lock_key

    with patch("app.imports.routes.enqueue_batch"):
        batch_id = UUID(upload(client, source).json()["id"])
    engine = make_engine(auth_env)
    connection = Redis.from_url(auth_env.redis_url.get_secret_value())
    try:
        with engine.begin() as locked, Session(engine) as session:
            locked.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": batch_lock_key(batch_id)}
            )
            enqueue_batch(batch_id, session, connection, auth_env)
            assert current(client, batch_id)["status"] == "NEW"
            assert Job.fetch_many([job_id(batch_id)], connection=connection)[0] is None
        with Session(engine) as session:
            enqueue_batch(batch_id, session, connection, auth_env)
        assert current(client, batch_id)["status"] == "QUEUED"
        assert Job.fetch(job_id(batch_id), connection=connection)
    finally:
        connection.close()
        engine.dispose()


def test_concurrent_initial_enqueue_publishes_only_once(client, auth_env, source):
    from concurrent.futures import ThreadPoolExecutor

    with patch("app.imports.routes.enqueue_batch"):
        batch_id = UUID(upload(client, source).json()["id"])
    engine = make_engine(auth_env)
    connection = Redis.from_url(auth_env.redis_url.get_secret_value())
    queue = Queue(auth_env.import_queue_name, connection=connection)
    try:
        before = queue.count

        def enqueue(_):
            with Session(engine) as session:
                enqueue_batch(batch_id, session, connection, auth_env)

        with ThreadPoolExecutor(2) as pool:
            list(pool.map(enqueue, range(2)))
        assert queue.count == before + 1
        with Session(engine) as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.object_id == batch_id, AuditEvent.event_type == "IMPORT_QUEUED"
                    )
                )
                == 1
            )
    finally:
        connection.close()
        engine.dispose()
