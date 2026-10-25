"""Owned synthetic capacity/latency proof; copied provenance is not independent evidence."""

import json
import math
import os
import re
import resource
import secrets
import subprocess
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.database import make_engine
from app.decisions.models import Decision
from app.main import create_app
from app.similarity.models import DecisionEmbedding
from tests.recommendation_fixtures import Cases
from tests.similarity_fixtures import expand
from tests.test_auth import isolated_environment
from tests.test_similarity_integration import enabled, index, similar


def percentile(values, fraction):
    return round(sorted(values)[math.ceil(len(values) * fraction) - 1], 6)


def run():
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Disposable owned schema opt-in required")
    environment = isolated_environment()
    base = next(environment)
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix="fk-recommendation-capacity-") as folder:
            settings = enabled(base).model_copy(
                update={
                    "recommendation_enabled": True,
                    "import_storage_root": Path(folder),
                    "import_queue_name": "recommendation-capacity-" + uuid4().hex,
                }
            )
            engine = make_engine(settings)
            tokens = [secrets.token_urlsafe(32) for _ in range(10)]
            with Session(engine) as session:
                password = hash_password(secrets.token_urlsafe(24))
                for n, token in enumerate(tokens):
                    user = User(
                        login="capacity_" + str(n),
                        full_name="Synthetic Stage 8 capacity reader",
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
                client.cookies.set(COOKIE_NAME, tokens[0])
                cases = Cases(client)
                query = cases.prepared()
                plans = {}

                def capture(connection, cursor, statement, parameters, context, executemany):
                    if (
                        statement.startswith("WITH ")
                        and "scored_precedents AS MATERIALIZED" in statement
                    ):
                        plans.update(sql=statement, parameters=parameters)

                event.listen(client.app.state.engine, "before_cursor_execute", capture)

                def measure(endpoint, field, expected):
                    def read(token):
                        observations = []
                        for _ in range(5):
                            started = time.monotonic()
                            response = client.get(
                                endpoint, headers={"Cookie": COOKIE_NAME + "=" + token}
                            )
                            seconds = time.monotonic() - started
                            assert response.status_code == 200, response.text
                            payload = response.json()
                            assert payload[field] == expected, payload
                            observations.append((seconds, payload.get("reason_code", expected)))
                        return observations

                    with ThreadPoolExecutor(10) as pool:
                        observations = [row for group in pool.map(read, tokens) for row in group]
                    times = [row[0] for row in observations]
                    p95 = percentile(times, 0.95)
                    assert p95 <= 1, {"endpoint": endpoint, "p95": p95}
                    return {
                        "requests": len(times),
                        "sessions": 10,
                        "p50_seconds": percentile(times, 0.5),
                        "p95_seconds": p95,
                        "max_seconds": round(max(times), 6),
                        "failures": 0,
                        "outcomes": dict(Counter(reason for _, reason in observations)),
                    }

                recommendation_endpoint = f"/api/v1/conflicts/{query}/recommendation"
                baseline_endpoint = f"/api/v1/conflicts/{query}/similar-decisions"
                positive = measure(recommendation_endpoint, "status", "RECOMMENDED")
                assert positive["outcomes"] == {"UNANIMOUS_INDEPENDENT_PRECEDENTS": 50}
                results.append({"decision_rows": 5, "independent_positive": positive})
                for count in [100, 1000, 10000]:
                    with Session(engine) as session:
                        existing = session.scalar(select(func.count()).select_from(Decision))
                        seed = session.get(Decision, UUID(cases.decisions[0]["decision_id"]))
                        while existing < count:
                            amount = min(count - existing, 250)
                            expand(session, seed, amount)
                            existing += amount
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
                    assert similar(client, query)["state"] == "READY"
                    baseline = measure(baseline_endpoint, "state", "READY")
                    recommendation = measure(recommendation_endpoint, "status", "ABSTAINED")
                    assert recommendation["outcomes"] == {"EVIDENCE_WINDOW_EXCEEDED": 50}
                    with engine.begin() as connection:
                        connection.execute(text("SET LOCAL enable_nestloop=off; SET LOCAL jit=off"))
                        plan = [
                            re.sub(
                                r"'\[[^]]+\]'::(?:public\.)?vector(?:\(\d+\))?",
                                "'[REDACTED_VECTOR]'::public.vector",
                                row,
                            )
                            for row in connection.exec_driver_sql(
                                "EXPLAIN (ANALYZE,BUFFERS) " + plans["sql"], plans["parameters"]
                            ).scalars()
                        ]
                        vectors = connection.scalar(
                            select(func.count()).select_from(DecisionEmbedding)
                        )
                    row = {
                        "decision_rows": count,
                        "vector_rows": vectors,
                        "index_seconds": round(index_seconds, 4),
                        "stage7_baseline": baseline,
                        "stage8_recommendation": recommendation,
                        "additional_p95_seconds": round(
                            recommendation["p95_seconds"] - baseline["p95_seconds"], 6
                        ),
                        "process_peak_rss_mib": round(
                            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
                        ),
                        "query_plan": plan,
                    }
                    results.append(row)
                    print(
                        json.dumps(
                            {key: value for key, value in row.items() if key != "query_plan"}
                        ),
                        flush=True,
                    )
            engine.dispose()
    finally:
        if "settings" in locals():
            with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
                Queue(settings.import_queue_name, connection=redis).delete(delete_jobs=True)
        try:
            next(environment)
        except StopIteration:
            pass
    report = {
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "scope": (
            "Owned disposable schema; real immutable Decision/vector rows, "
            "synthetic copied provenance."
        ),
        "limitations": [
            "100k not measured; replicated fixtures do not prove semantic quality or independence.",
            "Warm PostgreSQL/OS caches; no fully cold-cache claim.",
            "Pool >20 intentionally abstains; production provider remains disabled.",
            "In-process ASGI API, real PostgreSQL/Redis; HTTPS transport tested separately.",
            "RSS is Python process peak, not total server/container memory.",
        ],
        "results": results,
        "passed": True,
    }
    Path("/tmp/fk-stage8-performance.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    run()
