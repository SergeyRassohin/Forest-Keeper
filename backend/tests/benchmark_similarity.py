"""Opt-in >=10k actual Decision/vector capacity in an owned disposable schema."""

import json
import math
import os
import re
import resource
import secrets
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue
from rq.job import Job
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.database import make_engine
from app.decisions.models import Decision
from app.main import create_app
from app.similarity.models import DecisionEmbedding
from tests.similarity_fixtures import expand
from tests.test_auth import isolated_environment
from tests.test_decisions_integration import begin, real_case, save, selection
from tests.test_similarity_integration import enabled, index, similar


def percentile(values, fraction):
    return round(sorted(values)[math.ceil(len(values) * fraction) - 1], 6)


def run():
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Owned development schema opt-in required")
    keep_fixture = os.getenv("FK_KEEP_SIMILARITY_BENCH") == "1"
    environment = isolated_environment(preserve_schema=keep_fixture)
    base = next(environment)
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix="fk-similarity-capacity-") as folder:
            settings = enabled(base).model_copy(
                update={
                    "import_storage_root": Path(folder),
                    "import_queue_name": "similarity-capacity-" + uuid4().hex,
                    "similarity_reads_per_minute": 600,
                }
            )
            engine = make_engine(settings)
            tokens = [secrets.token_urlsafe(32) for _ in range(10)]
            with Session(engine) as session:
                password = hash_password(secrets.token_urlsafe(24))
                for n, token in enumerate(tokens):
                    user = User(
                        login="capacity_" + str(n),
                        full_name="Synthetic capacity reader",
                        data_domains=["*"],
                        password_hash=password,
                        roles=[UserRole(role_code="DATA_OWNER" if n == 0 else "VIEWER")],
                    )
                    session.add(user)
                    session.flush()
                    session.add(
                        AuthSession(
                            token_hash=token_digest(token),
                            user_id=user.id,
                            created_at=datetime.now(UTC),
                            expires_at=datetime.now(UTC) + timedelta(hours=2),
                        )
                    )
                session.commit()
            with TestClient(
                create_app(settings=settings), base_url="https://localhost:8443"
            ) as client:
                recorded = {}

                def capture_plan_input(
                    connection, cursor, statement, parameters, context, executemany
                ):
                    if (
                        statement.startswith("WITH ")
                        and "scored_precedents AS MATERIALIZED" in statement
                    ):
                        recorded.update(sql=statement, parameters=parameters)

                event.listen(client.app.state.engine, "before_cursor_execute", capture_plan_input)

                def phase(statement):
                    if "sha256" in statement:
                        return "integrity"
                    if "LEFT OUTER JOIN retrieval_items" in statement:
                        return "coverage"
                    if "OPERATOR(public.<=>)" in statement:
                        return "ranking"
                    return "metadata"

                def failed(context):
                    print(
                        json.dumps(
                            {
                                "sql_failure_phase": phase(context.statement or ""),
                                "sqlstate": getattr(context.original_exception, "sqlstate", None),
                            }
                        ),
                        flush=True,
                    )

                event.listen(client.app.state.engine, "handle_error", failed)
                client.cookies.set(COOKIE_NAME, tokens[0])
                first = real_case(client, settings)
                seed = save(client, first, selection(begin(client, first)))
                query = real_case(client, settings)
                if keep_fixture:
                    private = Path("/tmp/fk-stage7-capacity-debug.json")
                    with private.open("w") as output:
                        os.chmod(private, 0o600)
                        json.dump(
                            {
                                "database_url": settings.database_url.get_secret_value(),
                                "redis_url": settings.redis_url.get_secret_value(),
                                "query": query,
                                "tokens": tokens,
                                "queue": settings.import_queue_name,
                            },
                            output,
                        )
                    print(
                        "Owned persistent debug fixture: /tmp/fk-stage7-capacity-debug.json",
                        flush=True,
                    )
                for count in [100, 1000, 10000]:
                    with Session(engine) as session:
                        existing = session.scalar(select(func.count()).select_from(Decision))
                        new_rows = count - existing
                        seed_row = session.get(Decision, UUID(seed["decision_id"]))
                        while existing < count:
                            amount = min(count - existing, 250)
                            expand(session, seed_row, amount)
                            existing += amount
                    with engine.connect() as connection:
                        before_bytes = connection.scalar(
                            text("SELECT pg_total_relation_size('decision_embeddings')")
                        )
                    started = time.monotonic()
                    index(settings)
                    index_seconds = time.monotonic() - started
                    with engine.begin() as connection:
                        for table in [
                            "decisions",
                            "conflicts",
                            "decision_embeddings",
                            "retrieval_items",
                        ]:
                            connection.execute(text("ANALYZE " + table))
                    # First query prepares its vector in the background-test harness, then reads it.
                    cold_started = time.monotonic()
                    result = similar(client, query)
                    first_query_seconds = time.monotonic() - cold_started
                    assert result["state"] == "READY" and len(result["results"]) == 5
                    endpoint = f"/api/v1/conflicts/{query}/similar-decisions"
                    warm = []
                    for limit in [1, 5, 20]:
                        for _ in range(5):
                            started = time.monotonic()
                            response = client.get(endpoint + f"?limit={limit}")
                            assert (
                                response.status_code == 200 and response.json()["state"] == "READY"
                            ), response.text
                            warm.append((limit, time.monotonic() - started))

                    def read(token, endpoint=endpoint):
                        timings = []
                        for _ in range(5):
                            started = time.monotonic()
                            response = client.get(
                                endpoint, headers={"Cookie": COOKIE_NAME + "=" + token}
                            )
                            assert (
                                response.status_code == 200 and response.json()["state"] == "READY"
                            ), response.text
                            timings.append(time.monotonic() - started)
                        return timings

                    with ThreadPoolExecutor(10) as pool:
                        concurrent = [t for group in pool.map(read, tokens) for t in group]
                    assert percentile(concurrent, 0.95) <= 1, concurrent
                    with engine.begin() as connection:
                        connection.execute(text("ANALYZE decision_embeddings"))
                        connection.execute(text("ANALYZE decisions"))
                        connection.execute(text("ANALYZE conflicts"))
                        sizes = dict(
                            connection.execute(
                                text(
                                    "SELECT pg_total_relation_size('decision_embeddings') AS "
                                    "artifacts_bytes, "
                                    "pg_indexes_size('decision_embeddings') AS btree_index_bytes, "
                                    "pg_total_relation_size('decisions') AS decisions_bytes"
                                )
                            )
                            .mappings()
                            .one()
                        )
                        connection.execute(text("SET LOCAL enable_nestloop=off; SET LOCAL jit=off"))
                        plan = [
                            re.sub(
                                r"'\[[^]]+\]'::(?:public\.)?vector(?:\(\d+\))?",
                                "'[REDACTED_VECTOR]'::public.vector",
                                row,
                            )
                            for row in connection.exec_driver_sql(
                                "EXPLAIN (ANALYZE,BUFFERS) " + recorded["sql"],
                                recorded["parameters"],
                            ).scalars()
                        ]
                        integrity_plan = (
                            connection.execute(
                                text(
                                    "EXPLAIN SELECT decision_id FROM decision_embeddings "
                                    "WHERE version_id=:version AND (vector_hash IS DISTINCT FROM "
                                    "encode(sha256(public.vector_send(embedding)),'hex') "
                                    "OR feature_hash IS DISTINCT FROM input_hash "
                                    "OR dimensions<>1024)"
                                ),
                                {"version": UUID(result["retrieval_version"])},
                            )
                            .scalars()
                            .all()
                        )
                        actual = connection.scalar(
                            select(func.count()).select_from(DecisionEmbedding)
                        )
                    output = {
                        "source_commit": subprocess.check_output(
                            ["git", "rev-parse", "HEAD"], text=True
                        ).strip(),
                        "decision_rows": count,
                        "vector_rows": actual,
                        "indexing_new_rows": new_rows,
                        "index_seconds": round(index_seconds, 4),
                        "new_vectors_per_second": round(
                            new_rows / index_seconds,
                            2,
                        ),
                        "first_query_with_preparation_seconds": round(first_query_seconds, 4),
                        "cold_cache_limitation": (
                            "First API read after indexing; "
                            "OS/PostgreSQL cache not flushed on shared host."
                        ),
                        "warm_p50_seconds": percentile([t for _, t in warm], 0.5),
                        "warm_p95_seconds": percentile([t for _, t in warm], 0.95),
                        "top_n_p95_seconds": {
                            str(n): percentile([t for k, t in warm if k == n], 0.95)
                            for n in [1, 5, 20]
                        },
                        "sessions": 10,
                        "concurrent_requests": len(concurrent),
                        "concurrent_p50_seconds": percentile(concurrent, 0.5),
                        "concurrent_p95_seconds": percentile(concurrent, 0.95),
                        "artifact_growth_bytes": sizes["artifacts_bytes"] - before_bytes,
                        "process_peak_rss_mib": round(
                            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
                        ),
                        "sizes": sizes,
                        "filtered_exact_pgvector_plan": plan,
                        "partial_integrity_plan": integrity_plan,
                        "passed": True,
                    }
                    results.append(output)
                    print(json.dumps(output), flush=True)
            engine.dispose()
    finally:
        if "settings" in locals():
            with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
                queue = Queue(settings.import_queue_name, connection=redis)
                identifiers = queue.get_job_ids()
                for registry in [queue.finished_job_registry, queue.failed_job_registry]:
                    identifiers += registry.get_job_ids()
                for identifier in set(identifiers):
                    job = Job.fetch_many([identifier], connection=redis)[0]
                    if job:
                        job.delete()
                queue.delete(delete_jobs=True)
        try:
            next(environment)
        except StopIteration:
            pass
    return results


if __name__ == "__main__":
    run()
