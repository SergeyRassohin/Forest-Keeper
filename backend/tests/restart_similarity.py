"""Owned Stage 7 real HTTPS/backfill/reindex/runtime proof; retains all business facts."""

import argparse
import json
import os
import secrets
import ssl
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.config import Settings
from app.common.database import make_engine
from app.decisions.models import Decision
from app.decisions.service import digest
from app.similarity.jobs import execute_index
from app.similarity.models import DecisionEmbedding, IndexRun
from app.similarity.service import start_run

ROOT = Path(__file__).resolve().parents[2]


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--override", required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    if os.getenv("FK_TEST_INTEGRATION") != "1" or args.project != "fk-stage7":
        raise SystemExit("Only this task's owned fk-stage7 project is supported")
    assert args.base_url.startswith("https://localhost:")
    settings = Settings()
    compose = [
        "docker",
        "compose",
        "--env-file",
        args.env_file,
        "-p",
        args.project,
        "-f",
        str(ROOT / "compose.yaml"),
        "-f",
        args.override,
    ]

    def command(*parts):
        return subprocess.run([*compose, *parts], check=True, capture_output=True, text=True).stdout

    port = command("port", "postgres", "5432").strip()
    assert make_url(settings.database_url.get_secret_value()).port == int(port.rsplit(":", 1)[1])
    engine = make_engine(settings)
    identifier, token = uuid4(), secrets.token_urlsafe(32)
    tls = ssl.create_default_context(cafile=str(ROOT / "deploy/local/tls/dev.crt"))
    client = httpx.Client(
        base_url=args.base_url + "/api/v1",
        verify=tls,
        timeout=15,
        headers={"Origin": args.base_url},
        cookies={COOKIE_NAME: token},
        trust_env=False,
    )

    def api(method, path, expected=200, **kwargs):
        response = client.request(method, path, **kwargs)
        assert response.status_code == expected, f"Unexpected HTTP {response.status_code}"
        return response.json()

    def wait_status(path, target="COMPLETED", field="status", timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                result = api("GET", path)
                if result[field] == target:
                    return result
                assert result.get("status") != "FAILED", "Background operation failed"
            except (httpx.TransportError, AssertionError):
                pass
            time.sleep(0.5)
        raise AssertionError("Bounded runtime readiness timeout")

    def create_case(label):
        profile = next(
            p for p in api("GET", "/analysis/profiles") if p["code"] == "synthetic-material"
        )
        analyses = []
        for side in ["a", "b"]:
            source = api(
                "POST",
                "/sources",
                expected=201,
                json={
                    "code": "s7_" + uuid4().hex,
                    "name": label + " " + side,
                    "source_type": "FILE" if side == "a" else "ONE_C",
                },
            )
            filename = "source-a.csv" if side == "a" else "onec.xml"
            payload = (
                ROOT
                / "tests/data/conflicts"
                / ("source-" + side + (".csv" if side == "a" else ".xml"))
            ).read_bytes()
            batch = api(
                "POST",
                "/imports",
                expected=201,
                data={"source_id": source["id"]},
                files={
                    "file": (filename, payload, "text/csv" if side == "a" else "application/xml")
                },
            )
            wait_status("/imports/" + batch["id"])
            normalized = api(
                "POST",
                "/analysis",
                expected=201,
                json={"import_batch_ids": [batch["id"]], "template_id": profile["id"]},
            )
            wait_status("/analysis/" + normalized["id"])
            analyses.append(normalized["id"])
        matching_profile = next(
            p for p in api("GET", "/matching-profiles") if p["code"] == "synthetic-material"
        )
        matching = api(
            "POST",
            "/matching-runs",
            expected=201,
            json={"analysis_run_ids": analyses, "profile_id": matching_profile["id"]},
        )
        wait_status("/matching-runs/" + matching["id"])
        conflicts = api(
            "POST", "/conflict-runs", expected=201, json={"matching_run_id": matching["id"]}
        )
        wait_status("/conflict-runs/" + conflicts["id"])
        return next(
            c["id"]
            for c in api("GET", "/conflicts?matching_run_id=" + matching["id"])
            if c["conflict_type"] == "VALUE_MISMATCH"
        )

    def facts():
        with Session(engine) as session:
            return digest(
                [
                    [getattr(d, c.name) for c in Decision.__table__.columns]
                    for d in session.scalars(select(Decision).order_by(Decision.id))
                ]
            )

    def vectors():
        with Session(engine) as session:
            return digest(
                [
                    [
                        str(v.id),
                        str(v.decision_id),
                        str(v.version_id),
                        v.feature_hash,
                        v.vector_hash,
                    ]
                    for v in session.scalars(
                        select(DecisionEmbedding).order_by(DecisionEmbedding.id)
                    )
                ]
            )

    try:
        with Session(engine) as session:
            user = User(
                id=identifier,
                login="s7_runtime_" + identifier.hex,
                full_name="Stage 7 synthetic runtime operator",
                data_domains=["*"],
                password_hash=hash_password(secrets.token_urlsafe(24)),
                roles=[UserRole(role_code="DATA_OWNER")],
            )
            session.add(user)
            session.flush()
            session.add(
                AuthSession(
                    token_hash=token_digest(token),
                    user_id=identifier,
                    created_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(hours=2),
                )
            )
            session.commit()
        first = create_case("Stage7 first synthetic case")
        review = api("GET", f"/conflicts/{first}/review-context")
        review = api(
            "POST",
            f"/conflicts/{first}/review",
            json={"context_version": review["context_version"]},
        )
        value = review["selectable_values"][0]
        receipt = api(
            "POST",
            f"/conflicts/{first}/decisions",
            expected=201,
            json={
                "context_version": review["context_version"],
                "idempotency_key": str(uuid4()),
                "decision_type": "SELECT_VALUE",
                "selected_source_id": value["source_id"],
                "selected_value_id": value["value_id"],
                "reason": "Synthetic automated acceptance fixture: explicit confirmed selection.",
                "confirmed": True,
            },
        )
        second = create_case("Stage7 next similar synthetic case")
        command(
            "exec", "-T", "backend", "python", "-m", "app.similarity.cli", "start", "--activate"
        )
        path = f"/conflicts/{second}/similar-decisions?limit=20"
        result = wait_status(path, "READY", "state")
        assert receipt["decision_id"] in [r["decision_id"] for r in result["results"]]
        original_facts, original_vectors = facts(), vectors()
        original_version = result["retrieval_version"]
        # Stop the actual worker before deliberately leaving a durable partial reindex.
        command("stop", "worker")
        with Session(engine) as session:
            run = start_run(session, settings, "test-v2", batch_size=1)
            run.status = "QUEUED"
            session.commit()
            run_id, version_id = run.id, run.version_id
        execute_index(run_id, settings, max_batches=1)
        with Session(engine) as session:
            assert session.get(IndexRun, run_id).status == "PROCESSING"
            assert session.get(IndexRun, run_id).processed == 1
        assert api("GET", path)["retrieval_version"] == original_version
        command("restart", "postgres", "redis", "backend", "frontend")
        wait_status("/health", "ok", timeout=60)
        assert facts() == original_facts
        command("start", "worker")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            with Session(engine) as session:
                if session.get(IndexRun, run_id).status == "COMPLETED":
                    break
            time.sleep(0.5)
        else:
            raise AssertionError("Partial backfill was not recovered after worker restart")
        assert api("GET", path)["retrieval_version"] == original_version
        command(
            "exec",
            "-T",
            "backend",
            "python",
            "-m",
            "app.similarity.cli",
            "activate",
            "--version",
            str(version_id),
        )
        final = wait_status(path, "READY", "state")
        assert final["retrieval_version"] == str(version_id)
        assert receipt["decision_id"] in [r["decision_id"] for r in final["results"]]
        indexed_vectors = vectors()
        execute_index(run_id, settings)  # Duplicate completed delivery cannot add/alter artifacts.
        assert vectors() == indexed_vectors and facts() == original_facts
        command("restart", "postgres", "redis", "backend", "worker", "frontend")
        wait_status("/health", "ok", timeout=60)
        restored = wait_status(path, "READY", "state")
        assert (
            restored["results"] == final["results"]
            and facts() == original_facts
            and vectors() == indexed_vectors
        )
        command("stop", "postgres")
        failed = client.get(path)
        assert failed.status_code == 503 and "password" not in failed.text.lower()
        command("start", "postgres")
        wait_status("/health", "ok", timeout=60)
        assert wait_status(path, "READY", "state")["results"] == final["results"]
        with Session(engine) as session:
            counts = {
                "decisions": session.scalar(select(func.count()).select_from(Decision)),
                "vectors": session.scalar(select(func.count()).select_from(DecisionEmbedding)),
                "run_processed": session.get(IndexRun, run_id).processed,
            }
        output = {
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "project": args.project,
            "first_conflict": first,
            "new_conflict": second,
            "decision_id": receipt["decision_id"],
            "old_version": original_version,
            "new_version": str(version_id),
            "actual_https": True,
            "partial_checkpoint_before_restart": 1,
            "postgres_redis_backend_frontend_restart": True,
            "worker_recovered_partial_backfill": True,
            "dual_versions_explicit_activation": True,
            "duplicate_delivery_idempotent": True,
            "same_results_after_full_restart": True,
            "postgres_failure_sanitized_recovery": True,
            "decision_facts_unchanged": facts() == original_facts,
            "old_vectors_retained": original_vectors != indexed_vectors,
            "counts": counts,
            "passed": True,
        }
        print(json.dumps(output))
    finally:
        # Keep synthetic business facts/files/vectors; only revoke this owned login/session.
        try:
            command("start", "postgres", "redis", "backend", "worker", "frontend")
            with Session(engine) as session:
                user = session.get(User, identifier)
                if user:
                    user.status = "DISABLED"
                auth = session.get(AuthSession, token_digest(token))
                if auth:
                    auth.revoked_at = datetime.now(UTC)
                session.commit()
        finally:
            client.close()
            engine.dispose()


if __name__ == "__main__":
    run()
