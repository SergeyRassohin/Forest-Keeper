"""Resumable actual-Qwen capacity fixture, never customer data or a semantic Gold set.

Imports distinct synthetic records through the real pipeline and confirms fixture-only
Decisions through the normal API. It does not clone evidence or fabricate vectors.
Private ownership/tokens stay outside Git. Nothing is automatically deleted.
"""

import csv
import fcntl
import hashlib
import io
import json
import math
import os
import re
import secrets
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from unittest.mock import patch
from uuid import UUID, uuid4
from xml.sax.saxutils import escape

from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis import Redis
from rq import Queue, SimpleWorker
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.config import Settings
from app.common.database import make_engine
from app.conflicts.jobs import execute_conflict
from app.conflicts.models import Conflict
from app.decisions.models import Decision
from app.imports.jobs import execute_import
from app.main import create_app
from app.matching.jobs import execute_matching
from app.normalization.jobs import execute_run
from app.similarity.jobs import recover_indexes
from app.similarity.models import DecisionEmbedding, IndexRun, RetrievalVersion
from app.similarity.provider import inference_queue
from app.similarity.service import start_run
from tests.test_auth import ORIGIN, isolated_environment
from tests.test_conflicts_integration import start as conflict_start
from tests.test_decisions_integration import begin, save, selection
from tests.test_imports import upload
from tests.test_matching_integration import start as matching_start
from tests.test_normalization_integration import start as normalization_start

PRIVATE = Path(os.environ.get("FK_AI_CAPACITY_FIXTURE", "/private/fixture.json"))
REPORT = Path(os.environ.get("FK_AI_CAPACITY_REPORT", "/evidence/capacity.json"))
KIND = "owned-stage9-distinct-file-capacity-v1-not-gold"
FAMILIES = (
    "steel hex bolt",
    "stainless flat washer",
    "brass threaded nut",
    "aluminium angle",
    "copper electrical cable",
    "polyethylene pipe",
    "rubber sealing ring",
    "ceramic bearing",
    "cast iron valve",
    "galvanized bracket",
    "titanium connecting pin",
    "nylon gear wheel",
    "bronze sleeve",
    "carbon steel spring",
    "glass fibre panel",
    "polyurethane roller",
    "silicone gasket",
    "zinc plated screw",
    "steel mounting rail",
    "polypropylene fitting",
)


def write_json(path, value, *, exclusive=False, private=False):
    temporary = path.with_name(path.name + ".new." + uuid4().hex)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    fd = os.open(path if exclusive else temporary, flags, 0o600 if private else 0o644)
    with os.fdopen(fd, "w") as out:
        json.dump(value, out, indent=2, ensure_ascii=False)
        out.write("\n")
    if not exclusive:
        os.replace(temporary, path)


def load():
    value = json.loads(PRIVATE.read_text())
    assert value["kind"] == KIND
    assert re.fullmatch(r"auth_test_[a-f0-9]{32}", value["schema"])
    assert value["auth_rate_prefix"] == value["schema"] + ":"
    assert re.fullmatch(r"stage9-capacity-[a-f0-9]{32}", value["queue"])
    base = Settings()
    original, owned = (
        make_url(base.database_url.get_secret_value()),
        make_url(value["database_url"]),
    )
    assert all(
        getattr(original, name) == getattr(owned, name)
        for name in ("drivername", "host", "port", "database", "username")
    )
    settings = base.model_copy(
        update={
            "database_url": SecretStr(value["database_url"]),
            "auth_rate_prefix": value["auth_rate_prefix"],
            "import_queue_name": value["queue"],
            "import_storage_root": Path("/imports"),
            "similarity_reads_per_minute": 600,
            "similarity_autoindex": False,
            "recommendation_source_map": value.get("mapping", {}),
        }
    )
    engine = make_engine(settings)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_schema()")) == value["schema"]
    engine.dispose()
    return value, settings


def records(count):
    for number in range(count):
        family = number % len(FAMILIES)
        variant = number // len(FAMILIES)
        digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        # The first three characters are unique within this workload. A shared
        # synthetic prefix would exercise bounded fuzzy-block omission instead
        # of preparing the intended exact-identity retrieval capacity fixture.
        code = "".join(digits[number // power % 36] for power in (1296, 36, 1))
        key = code + "-FK-NFR"
        subject = f"{key} {FAMILIES[family]} size-{variant % 40 + 1} grade-{variant % 7 + 1}"
        # Distinct normalized comparisons as well as distinct source/entity/provenance.
        mass = 1000 + family * 500 + variant
        yield key, subject, f"{mass / 1000:.3f}", f"{(mass + 10) / 1000:.3f}"


def prepare(count):
    assert 20 <= count <= 10000
    if PRIVATE.exists():
        value, settings = load()
        assert value["target"] == count
    else:
        environment = isolated_environment(preserve_schema=True)
        settings = next(environment).model_copy(
            update={
                "import_queue_name": "stage9-capacity-" + uuid4().hex,
                "import_storage_root": Path("/imports"),
            }
        )
        value = {
            "kind": KIND,
            "schema": settings.auth_rate_prefix.removesuffix(":"),
            "auth_rate_prefix": settings.auth_rate_prefix,
            "database_url": settings.database_url.get_secret_value(),
            "queue": settings.import_queue_name,
            "target": count,
            "phase": "CREATED",
            "tokens": [secrets.token_urlsafe(32) for _ in range(10)],
        }
        write_json(PRIVATE, value, exclusive=True, private=True)
        environment.close()
        value, settings = load()
        engine = make_engine(settings)
        with Session(engine) as session:
            password = hash_password(secrets.token_urlsafe(32))
            for position, token in enumerate(value["tokens"]):
                user = User(
                    login=f"capacity_{position}",
                    full_name="Automated capacity fixture",
                    password_hash=password,
                    data_domains=["*"],
                    roles=[UserRole(role_code="DATA_OWNER" if position == 0 else "VIEWER")],
                )
                session.add(user)
                session.flush()
                session.add(
                    AuthSession(
                        token_hash=token_digest(token),
                        user_id=user.id,
                        created_at=datetime.now(UTC),
                        expires_at=datetime.now(UTC) + timedelta(hours=24),
                    )
                )
            session.commit()
        engine.dispose()
    with TestClient(create_app(settings=settings), base_url="https://localhost:8443") as client:
        client.cookies.set(COOKIE_NAME, value["tokens"][0])
        if value["phase"] == "CREATED":
            # Refuse an ambiguous partly imported fixture; do not silently add duplicate data.
            value["phase"] = "IMPORTING"
            write_json(PRIVATE, value, private=True)
            sources, analyses = [], []
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["id", "name", "mass", "price", "date"])
            xml = ["<Выгрузка>"]
            for key, subject, first, second in records(count + len(FAMILIES)):
                writer.writerow([key, subject, first + " kg", "10", "2026-01-01"])
                xml.append(
                    f'<Объект Тип="Справочник.Номенклатура" Ид="{key}">'
                    f"<Наименование>{escape(subject)}</Наименование><Масса>{second} kg</Масса>"
                    "<Цена>10</Цена><Дата>2026-01-01</Дата></Объект>"
                )
            xml.append("</Выгрузка>")
            for source_type, role, name, payload in [
                ("FILE", "REGISTER_EXPORT", "material.csv", buffer.getvalue().encode()),
                ("ONE_C", "ACCOUNTING_EXPORT", "onec.xml", "".join(xml).encode()),
            ]:
                response = client.post(
                    "/api/v1/sources",
                    headers=ORIGIN,
                    json={
                        "code": uuid4().hex,
                        "name": "Synthetic capacity " + role,
                        "source_type": source_type,
                    },
                )
                assert response.status_code == 201, response.status_code
                source_id = response.json()["id"]
                sources.append({"source_id": source_id, "source_type": source_type, "role": role})
                response = upload(client, source_id, name, payload)
                assert response.status_code == 201, response.status_code
                batch = response.json()["id"]
                execute_import(UUID(batch), settings)
                analysis = normalization_start(client, batch)
                execute_run(UUID(analysis["id"]), settings)
                analyses.append(analysis["id"])
            matching = matching_start(client, analyses)
            execute_matching(UUID(matching["id"]), settings)
            conflicts = conflict_start(client, matching)
            execute_conflict(UUID(conflicts["id"]), settings)
            engine = make_engine(settings)
            with Session(engine) as session:
                rows = list(session.scalars(select(Conflict).order_by(Conflict.id)))
                rows.sort(key=lambda row: row.values_snapshot[0]["source_record_key"])
                assert len(rows) == count + len(FAMILIES), len(rows)
                assert all(row.conflict_type == "VALUE_MISMATCH" for row in rows)
                value["history"] = [str(row.id) for row in rows[:count]]
                value["queries"] = [str(row.id) for row in rows[count:]]
            engine.dispose()
            card = client.get("/api/v1/conflicts/" + value["history"][0]).json()
            value["mapping"] = {
                "version": "owned-capacity-explicit-sources-v1",
                "approved": True,
                "approval_reference": "Explicit fixture source roles, not a customer policy.",
                "domain": "synthetic-material",
                "entity_type": "Material",
                "attribute_code": "mass",
                "matching_profile_hashes": [card["basis"]["matching_profile_hash"]],
                "sources": sources,
            }
            value["phase"] = "CONFIRMING"
            write_json(PRIVATE, value, private=True)
            settings.recommendation_source_map = value["mapping"]
        assert value["phase"] in {"CONFIRMING", "PREPARED"}, "Partial import retained for diagnosis"
        engine = make_engine(settings)
        with Session(engine) as session:
            saved = set(session.scalars(select(Decision.conflict_id)))
        for position, identifier in enumerate(value["history"]):
            if UUID(identifier) not in saved:
                review = begin(client, identifier)
                request = selection(review)
                request["reason"] = "AUTOMATED SYNTHETIC CAPACITY FIXTURE, not human Gold approval."
                save(client, identifier, request)
            if (position + 1) % 100 == 0:
                value["confirmed_checkpoint"] = position + 1
                write_json(PRIVATE, value, private=True)
                print(json.dumps({"phase": "confirming", "confirmed": position + 1}), flush=True)
                if shutil.disk_usage(PRIVATE.parent).free < 700 * 1024 * 1024:
                    raise SystemExit(
                        "Owned load preparation paused for disk headroom; progress retained"
                    )
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(Decision)) == count
        engine.dispose()
        value["phase"] = "PREPARED"
        write_json(PRIVATE, value, private=True)
        print(json.dumps({"phase": "prepared", "decisions": count, "gold": False}), flush=True)


def indexing():
    value, settings = load()
    assert value["phase"] in {"PREPARED", "INDEXING", "INDEXED"}
    engine = make_engine(settings)
    if "run_id" not in value:
        with Session(engine) as session:
            run = start_run(session, settings, "qwen-demo-v1", activate=True, batch_size=8)
            session.commit()
            value.update(run_id=str(run.id), version_id=str(run.version_id), phase="INDEXING")
        write_json(PRIVATE, value, private=True)
    result = (
        json.loads(REPORT.read_text())
        if REPORT.exists()
        else {
            "kind": KIND,
            "production_accepted": False,
            "semantic_quality_evaluated": False,
            "target": value["target"],
            "batch_job_seconds": [],
            "passed": False,
            "workload": (
                "20 material families, distinct genuine file rows and fixture API Decisions"
            ),
            "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "model_file_sha256": "0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd",
            "dimensions": 1024,
        }
    )
    with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
        queue = Queue(inference_queue(settings), connection=redis)
        while True:
            with Session(engine) as session:
                run = session.get(IndexRun, UUID(value["run_id"]))
                result.update(
                    processed=run.processed,
                    indexed=run.indexed,
                    status=run.status,
                    error_code=run.error_code,
                )
            write_json(REPORT, result)
            print(
                json.dumps({key: result[key] for key in ("processed", "indexed", "status")}),
                flush=True,
            )
            if run.status in {"COMPLETED", "FAILED"}:
                break
            recover_indexes(settings, redis)
            started = time.monotonic()
            # DI selects only this owned schema/queue. No model/provider/output is mocked.
            with patch("app.similarity.jobs.Settings", return_value=settings):
                worked = SimpleWorker([queue], connection=redis).work(
                    burst=True, max_jobs=1, logging_level="ERROR"
                )
            if not worked:
                raise SystemExit("Owned index queue stalled; preserved evidence is not a pass")
            result["batch_job_seconds"].append(round(time.monotonic() - started, 6))
    with Session(engine) as session:
        actual = session.scalar(select(func.count()).select_from(DecisionEmbedding))
        unique_inputs = session.scalar(
            select(func.count(func.distinct(DecisionEmbedding.input_hash)))
        )
        observed_config = session.get(RetrievalVersion, UUID(value["version_id"])).config
    engine.dispose()
    assert result["status"] == "COMPLETED" and actual == value["target"], result["status"]
    value["phase"] = "INDEXED"
    write_json(PRIVATE, value, private=True)
    result["actual_vectors"] = actual
    result["distinct_input_hashes"] = unique_inputs
    result["observed_model_configuration"] = observed_config
    result["retrieval_version"] = value["version_id"]
    result["index_benchmark_sha256"] = result["benchmark_sha256"]
    result["hardware_profile"] = json.loads(PRIVATE.with_name("hardware.json").read_text())
    assert unique_inputs == actual, "Capacity fixture must have distinct actual embedding inputs"
    write_json(REPORT, result)


def percentile(values, fraction):
    return round(sorted(values)[math.ceil(len(values) * fraction) - 1], 6)


def measure():
    from app.similarity.service import configuration
    from tests.test_recommendations_integration import business_hash

    value, settings = load()
    assert value["phase"] == "INDEXED"
    result = json.loads(REPORT.read_text())
    if "measurements" in result:
        write_json(
            REPORT.with_name("measurement-history-" + uuid4().hex + ".json"), result, exclusive=True
        )
    result.setdefault("index_benchmark_sha256", result.get("benchmark_sha256"))
    # A new attempt must never inherit an earlier successful measurement.
    for field in (
        "measurements",
        "p50_seconds",
        "p95_seconds",
        "max_seconds",
        "endpoint_p95_seconds",
        "passed",
        "measurement_error",
        "immutable_history_preserved",
    ):
        result.pop(field, None)
    result.update(
        passed=False,
        measurement_attempt=str(uuid4()),
        measurement_started_at=datetime.now(UTC).isoformat(),
        measurement_benchmark_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        transport="Warm ASGI TestClient + actual PostgreSQL/Redis, not HTTPS end-to-end",
        cache_profile="warm; no OS/PostgreSQL cache flush",
        concurrent_model_inference=False,
        provenance_limit=(
            "Two bulk files correlate this fixture; no independent-positive-path claim"
        ),
        sessions=10,
        planned_requests=400,
    )
    write_json(REPORT, result)
    measurements, warmup = [], []
    lock = Lock()
    expected_config = configuration("qwen-demo-v1")
    engine = make_engine(settings)
    before = None

    def safe_reason(payload):
        code = payload.get("reason_code") if isinstance(payload, dict) else None
        return code if isinstance(code, str) and re.fullmatch(r"[A-Z0-9_]{1,64}", code) else None

    def valid_retrieval(payload):
        return isinstance(payload, dict) and (
            payload.get("state") == "READY"
            and payload.get("retrieval_version") == value["version_id"]
            and payload.get("embedding_model") == expected_config
            and payload.get("total_candidates_before_filter") == value["target"]
            and payload.get("total_after_filter") == value["target"]
        )

    def observe(client, endpoint, token):
        started = time.monotonic()
        row = {
            "endpoint": endpoint.rsplit("/", 1)[-1],
            "status_code": None,
            "valid": False,
            "reason_code": None,
            "error_code": None,
        }
        payload = None
        try:
            response = client.get(
                endpoint, headers={"Cookie": COOKIE_NAME + "=" + token}, timeout=5
            )
            row["status_code"] = response.status_code
            try:
                payload = response.json()
            except ValueError:
                row["error_code"] = "INVALID_RESPONSE_JSON"
            row["valid"] = response.status_code == 200 and isinstance(payload, (dict, list))
            row["reason_code"] = safe_reason(payload)
            if endpoint.endswith("/similar-decisions"):
                row["valid"] = row["valid"] and valid_retrieval(payload)
            elif endpoint.endswith("/recommendation"):
                row["valid"] = (
                    row["valid"]
                    and isinstance(payload, dict)
                    and payload.get("status") in {"RECOMMENDED", "ABSTAINED"}
                )
                if value["target"] >= 100:
                    row["valid"] = (
                        row["valid"]
                        and payload.get("status") == "ABSTAINED"
                        and payload.get("reason_code") == "EVIDENCE_WINDOW_EXCEEDED"
                    )
        except Exception as error:
            # Fixed class name only; no URI, credentials, response body or exception text.
            row["error_code"] = type(error).__name__[:64]
        row["seconds"] = round(time.monotonic() - started, 6)
        return row, payload

    try:
        with Session(engine) as session:
            before = business_hash(session)
        with TestClient(create_app(settings=settings), base_url="https://localhost:8443") as client:
            client.cookies.set(COOKIE_NAME, value["tokens"][0])
            with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
                queue = Queue(inference_queue(settings), connection=redis)
                for identifier in value["queries"]:
                    endpoint = "/api/v1/conflicts/" + identifier + "/similar-decisions"
                    row, payload = observe(client, endpoint, value["tokens"][0])
                    if (
                        isinstance(payload, dict)
                        and payload.get("reason_code") == "QUERY_CONTEXT_PENDING"
                    ):
                        with patch("app.similarity.jobs.Settings", return_value=settings):
                            worked = SimpleWorker([queue], connection=redis).work(
                                burst=True, max_jobs=1, logging_level="ERROR"
                            )
                        if not worked:
                            raise RuntimeError("Warmup queue stalled")
                        row, payload = observe(client, endpoint, value["tokens"][0])
                    warmup.append(row)
                    if not row["valid"]:
                        raise RuntimeError("Warmup failed")

            def reader(item):
                position, token = item
                identifier = value["queries"][position]
                endpoints = [
                    "/api/v1/conflicts?limit=50",
                    "/api/v1/decisions?limit=50",
                    "/api/v1/conflicts/" + identifier + "/similar-decisions",
                    "/api/v1/conflicts/" + identifier + "/recommendation",
                ]
                for _ in range(10):
                    for endpoint in endpoints:
                        row, _ = observe(client, endpoint, token)
                        with lock:
                            measurements.append(row)

            with ThreadPoolExecutor(10) as pool:
                list(pool.map(reader, enumerate(value["tokens"])))
        with Session(engine) as session:
            result["immutable_history_preserved"] = business_hash(session) == before
    except Exception as error:
        result["measurement_error"] = type(error).__name__[:64]
    finally:
        engine.dispose()
        result.update(measurements=measurements, warmup=warmup, requests=len(measurements))
        times = [r["seconds"] for r in measurements]
        result["p50_seconds"] = percentile(times, 0.5) if times else None
        result["p95_seconds"] = percentile(times, 0.95) if times else None
        result["max_seconds"] = max(times) if times else None
        result["http_failures"] = sum(r["status_code"] != 200 for r in measurements)
        result["invalid_responses"] = sum(not r["valid"] for r in measurements)
        result["warmup_failures"] = sum(not r["valid"] for r in warmup)
        result["outcomes"] = dict(
            Counter(
                r["error_code"] or r["reason_code"] or "HTTP_" + str(r["status_code"])
                for r in measurements
            )
        )
        result["endpoint_p95_seconds"] = {
            endpoint: percentile(
                [r["seconds"] for r in measurements if r["endpoint"] == endpoint], 0.95
            )
            for endpoint in {r["endpoint"] for r in measurements}
        }
        result["passed"] = (
            len(measurements) == 400
            and len(warmup) == len(value["queries"])
            and all(r["valid"] for r in warmup)
            and "measurement_error" not in result
            and result.get("immutable_history_preserved") is True
            and result["invalid_responses"] == 0
            and all(elapsed <= 1 for elapsed in result["endpoint_p95_seconds"].values())
        )
        write_json(REPORT, result)
    assert result["passed"], "NFR failed; observations preserved without relaxing the target"


if __name__ == "__main__":
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Explicit owned fixture opt-in required")
    lock_fd = os.open(
        PRIVATE.with_name("runner.lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(lock_fd, "w"):
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if sys.argv[1:2] == ["prepare"] and len(sys.argv) == 3:
            prepare(int(sys.argv[2]))
        elif sys.argv[1:] == ["index"]:
            indexing()
        elif sys.argv[1:] == ["measure"]:
            measure()
        else:
            raise SystemExit("Use prepare <20..10000>, index, or measure")
