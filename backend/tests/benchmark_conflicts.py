"""Opt-in isolated Stage 5 acceptance profile, never run against production."""

import argparse
import csv
import json
import math
import os
import platform
import resource
import secrets
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue, SimpleWorker
from rq.job import Job
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, aliased

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.database import make_engine
from app.conflicts.models import Conflict
from app.main import create_app
from app.matching.models import MatchCandidate
from app.matching.profiles import catalog
from app.normalization.models import EntityValue
from app.normalization.profiles import catalog as normalization_catalog
from tests.test_auth import isolated_environment


def run(count, sources=2):
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Development-only: opt in with FK_TEST_INTEGRATION=1")
    environment = isolated_environment()
    base = next(environment)
    with tempfile.TemporaryDirectory(prefix="fk-matching-benchmark-") as directory:
        folder = Path(directory)
        settings = base.model_copy(
            update={
                "import_storage_root": folder / "originals",
                "import_queue_name": "match-capacity-" + uuid4().hex,
            }
        )
        engine = make_engine(settings)
        redis = Redis.from_url(settings.redis_url.get_secret_value())
        queue = Queue(settings.import_queue_name, connection=redis)
        try:
            tokens = []
            with Session(engine) as session:
                password_hash = hash_password(secrets.token_urlsafe(24))
                for index in range(10):
                    user = User(
                        login=f"capacity_{index}",
                        full_name="Synthetic benchmark",
                        password_hash=password_hash,
                        roles=[UserRole(role_code="DATA_OWNER" if index == 0 else "VIEWER")],
                    )
                    session.add(user)
                    session.flush()
                    token = secrets.token_urlsafe(32)
                    tokens.append(token)
                    session.add(
                        AuthSession(
                            token_hash=token_digest(token),
                            user_id=user.id,
                            created_at=datetime.now(UTC),
                            expires_at=datetime.now(UTC) + timedelta(hours=2),
                        )
                    )
                session.commit()
            with patch.dict(
                os.environ,
                {
                    "FK_DATABASE_URL": settings.database_url.get_secret_value(),
                    "FK_REDIS_URL": settings.redis_url.get_secret_value(),
                    "FK_IMPORT_STORAGE_ROOT": str(settings.import_storage_root),
                    "FK_IMPORT_QUEUE_NAME": settings.import_queue_name,
                },
            ):
                with TestClient(
                    create_app(settings=settings), base_url="https://localhost:8443"
                ) as client:
                    client.cookies.set(COOKIE_NAME, tokens[0])
                    headers = {"Origin": "https://localhost:8443"}
                    batches = []
                    sizes = []
                    started = time.monotonic()
                    for index in range(sources):
                        path = folder / f"capacity-{index}.csv"
                        subprocess.run(
                            [
                                sys.executable,
                                str(
                                    Path(__file__).resolve().parents[2]
                                    / "scripts/generate-import-data.py"
                                ),
                                str(path),
                                "--count",
                                str(count),
                                "--seed",
                                str(41),
                            ],
                            check=True,
                            capture_output=True,
                        )
                        if index == 1:
                            with path.open(newline="") as stream:
                                data = list(csv.reader(stream))
                            for row_index, row in enumerate(data[1:]):
                                if row_index % 10 == 0:
                                    row[29] = "explicit different value"
                                if row_index % 20 == 0:
                                    row[28] = ""
                            with path.open("w", newline="") as stream:
                                csv.writer(stream).writerows(data)
                        source = client.post(
                            "/api/v1/sources",
                            headers=headers,
                            json={
                                "name": f"Capacity {index}",
                                "code": f"capacity_{index}",
                                "source_type": "FILE",
                            },
                        ).json()
                        with path.open("rb") as stream:
                            response = client.post(
                                "/api/v1/imports",
                                headers=headers,
                                data={"source_id": source["id"]},
                                files={"file": (path.name, stream)},
                            )
                        assert response.status_code == 201
                        batches.append(response.json()["id"])
                        sizes.append(path.stat().st_size)
                    SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
                    for batch in batches:
                        assert (
                            client.get("/api/v1/imports/" + batch).json()["status"] == "COMPLETED"
                        )
                    import_seconds = time.monotonic() - started
                    normal_profile = next(
                        profile
                        for profile in normalization_catalog().values()
                        if profile.code == "synthetic-capacity"
                    )
                    started = time.monotonic()
                    normalized = []
                    for batch in batches:
                        response = client.post(
                            "/api/v1/analysis",
                            headers=headers,
                            json={
                                "import_batch_ids": [batch],
                                "template_id": str(normal_profile.id),
                            },
                        )
                        assert response.status_code == 201
                        normalized.append(response.json()["id"])
                    SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
                    for identifier in normalized:
                        detail = client.get("/api/v1/analysis/" + identifier).json()
                        assert (
                            detail["status"] == "COMPLETED"
                            and detail["values_processed"] == count * 30
                        )
                    normalization_seconds = time.monotonic() - started
                    profile = next(
                        profile
                        for profile in catalog().values()
                        if profile.code == "synthetic-capacity"
                    )
                    started = time.monotonic()
                    response = client.post(
                        "/api/v1/matching-runs",
                        headers=headers,
                        json={"analysis_run_ids": normalized, "profile_id": str(profile.id)},
                    )
                    assert response.status_code == 201, response.text
                    identifier = response.json()["id"]
                    SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
                    seconds = time.monotonic() - started
                    detail = client.get("/api/v1/matching-runs/" + identifier).json()
                    assert detail["status"] == "COMPLETED", detail["error_text"]
                    assert detail["records_processed"] == count
                    assert (
                        count
                        <= detail["candidates_generated"]
                        <= count * profile.max_candidates_per_record
                    )
                    assert detail["status_counts"].get("MATCHED") == count
                    with Session(engine) as session:
                        assert (
                            session.scalar(select(func.count()).select_from(MatchCandidate))
                            == detail["candidates_generated"]
                        )
                        a, b = aliased(EntityValue), aliased(EntityValue)
                        false_merges = session.scalar(
                            select(func.count())
                            .select_from(MatchCandidate)
                            .join(
                                a,
                                and_(
                                    a.raw_record_id == MatchCandidate.raw_record_a_id,
                                    a.attribute_code == "id",
                                ),
                            )
                            .join(
                                b,
                                and_(
                                    b.raw_record_id == MatchCandidate.raw_record_b_id,
                                    b.attribute_code == "id",
                                ),
                            )
                            .where(
                                MatchCandidate.status == "MATCHED",
                                a.normalized_value != b.normalized_value,
                            )
                        )
                        assert false_merges == 0

                    conflict_started = time.monotonic()
                    response = client.post(
                        "/api/v1/conflict-runs",
                        headers=headers,
                        json={"matching_run_id": identifier},
                    )
                    assert response.status_code == 201, response.text
                    conflict_run_id = response.json()["id"]
                    SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
                    conflict_seconds = time.monotonic() - conflict_started
                    conflict_run = client.get("/api/v1/conflict-runs/" + conflict_run_id).json()
                    assert conflict_run["status"] == "COMPLETED", conflict_run
                    expected = count // 10 + count // 20
                    assert conflict_run["records_processed"] == count
                    assert conflict_run["attributes_evaluated"] == count * 30
                    assert conflict_run["conflicts_generated"] == expected, conflict_run
                    with Session(engine) as session:
                        generated = session.scalar(select(func.count()).select_from(Conflict))
                        assert generated == expected
                        actual = set(
                            session.execute(
                                select(
                                    EntityValue.normalized_value,
                                    Conflict.attribute_code,
                                    Conflict.conflict_type,
                                )
                                .join(Conflict, Conflict.entity_id == EntityValue.entity_id)
                                .where(EntityValue.attribute_code == "id")
                            ).all()
                        )
                        oracle = {
                            (f"{i:08}", "attribute_29", "VALUE_MISMATCH")
                            for i in range(0, count, 10)
                        }
                        oracle |= {
                            (f"{i:08}", "attribute_28", "MISSING") for i in range(0, count, 20)
                        }
                        assert actual == oracle, {
                            "false": len(actual - oracle),
                            "missed": len(oracle - actual),
                        }
                        example = session.scalar(select(Conflict.id).limit(1))
                    cards = [
                        "/api/v1/conflicts/" + str(example),
                        "/api/v1/conflicts?limit=50&matching_run_id=" + identifier,
                    ]

                    def read(token):
                        timings = []
                        with TestClient(
                            create_app(settings=settings), base_url="https://localhost:8443"
                        ) as reader:
                            reader.cookies.set(COOKIE_NAME, token)
                            for _ in range(10):
                                before = time.monotonic()
                                assert reader.get(cards[_ % 2]).status_code == 200
                                timings.append(time.monotonic() - before)
                        return timings

                    with ThreadPoolExecutor(10) as pool:
                        times = sorted(
                            value for values in pool.map(read, tokens) for value in values
                        )
                    p95 = times[math.ceil(len(times) * 0.95) - 1]
                    assert p95 <= 1, f"conflict metadata/card p95 {p95:.4f} exceeds baseline"
                    return {
                        "source_datasets": sources,
                        "records_per_dataset": count,
                        "attributes_per_record": 30,
                        "bytes_per_dataset": sizes,
                        "import_seconds": round(import_seconds, 3),
                        "normalization_seconds": round(normalization_seconds, 3),
                        "matching_seconds": round(seconds, 3),
                        "conflict_seconds": round(conflict_seconds, 3),
                        "matched_identities_processed": conflict_run["records_processed"],
                        "attributes_evaluated": conflict_run["attributes_evaluated"],
                        "conflicts_generated": generated,
                        "expected_conflicts": expected,
                        "false_conflicts": 0,
                        "missed_conflicts": 0,
                        "conflict_types": conflict_run["status_counts"],
                        "records": count * sources,
                        "candidate_pairs_generated": detail["candidates_generated"],
                        "candidate_reduction_ratio": 1
                        - detail["candidates_generated"] / (count * count),
                        "status_counts": detail["status_counts"],
                        "false_merge_count": false_merges,
                        "records_per_second": round(count * sources / seconds, 2),
                        "coverage_diagnostics": detail["diagnostics"],
                        "normalization_values": count * sources * 30,
                        "metadata_endpoints": cards,
                        "metadata_sessions": 10,
                        "metadata_p95_seconds": round(p95, 4),
                        "process_peak_rss_mib": round(
                            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
                        ),
                        "passed": True,
                    }
        finally:
            identifiers = queue.get_job_ids()
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--records",
        nargs="+",
        choices=[100, 1000, 10000, 100000],
        type=int,
        default=[100, 1000, 10000, 100000],
    )
    parser.add_argument("--sources", choices=[2], type=int, default=2)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    evidence = {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()
        ),
        "environment": {
            "python": platform.python_version(),
            "os": platform.platform(),
            "execution": "host Python, isolated PostgreSQL schema/Redis queue; SimpleWorker",
        },
        "profiles": [],
    }
    for count in args.records:
        result = run(count, args.sources)
        evidence["profiles"].append(result)
        print(json.dumps({"profile": result}, ensure_ascii=False), flush=True)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
