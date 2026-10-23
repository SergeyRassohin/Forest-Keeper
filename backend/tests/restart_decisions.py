"""Explicitly isolated Stage6 HTTPS/restart proof; never removes volumes or business facts."""

import argparse
import hashlib
import json
import os
import secrets
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.config import Settings
from app.common.database import make_engine
from app.conflicts.models import Conflict
from app.decisions.models import Decision
from app.imports.models import ImportBatch, RawRecord
from app.matching.models import MatchCandidate
from app.normalization.models import EntityValue

ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--override", required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    if os.getenv("FK_TEST_INTEGRATION") != "1" or not args.project.startswith("fk-stage6"):
        raise SystemExit("Only an explicitly opted-in isolated fk-stage6 project is supported")
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
    settings = Settings()
    port = subprocess.check_output([*compose, "port", "postgres", "5432"], text=True).strip()
    assert make_url(settings.database_url.get_secret_value()).port == int(port.rsplit(":", 1)[1])
    assert args.base_url.startswith("https://localhost:")
    engine = make_engine(settings)
    context = ssl.create_default_context(cafile=str(ROOT / "deploy/local/tls/dev.crt"))
    tokens = [secrets.token_urlsafe(32) for _ in range(3)]
    user_ids = [uuid4() for _ in tokens]

    def command(*parts):
        subprocess.run([*compose, *parts], check=True, capture_output=True, text=True)

    def request(path, body=None, token=tokens[0], expected=200):
        headers = {"Cookie": COOKIE_NAME + "=" + token, "Origin": args.base_url}
        if body is not None:
            headers["Content-Type"] = "application/json"
        operation = urllib.request.Request(
            args.base_url + "/api/v1" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
        )
        try:
            response = urllib.request.urlopen(operation, context=context, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            assert response.status == expected, f"Unexpected HTTP status {response.status}"
            return json.load(response)

    def ready():
        for _ in range(45):
            try:
                if request("/health")["status"] == "ok":
                    return
            except (OSError, urllib.error.URLError, AssertionError):
                pass
            time.sleep(1)
        raise AssertionError("Stack readiness failed after restart")

    def begin(identifier):
        review = request(f"/conflicts/{identifier}/review-context")
        return request(
            f"/conflicts/{identifier}/review",
            {
                "context_version": review["context_version"],
                "supersedes_decision_id": review["current_decision"]["id"]
                if review["current_decision"]
                else None,
            },
        )

    def body(review, kind="SELECT_VALUE"):
        chosen = review["selectable_values"][0]
        return {
            "context_version": review["context_version"],
            "idempotency_key": str(uuid4()),
            "decision_type": kind,
            "reason": "Synthetic runtime evidence: reviewed by a person.",
            "confirmed": True,
            "supersedes_decision_id": review["current_decision"]["id"]
            if review["current_decision"]
            else None,
            **(
                {"selected_source_id": chosen["source_id"], "selected_value_id": chosen["value_id"]}
                if kind == "SELECT_VALUE"
                else {}
            ),
        }

    def snapshots(identifier):
        with Session(engine) as session:
            case = session.get(Conflict, UUID(identifier))
            raw_ids = {UUID(side["raw_record_id"]) for side in case.values_snapshot}
            entity_ids = {UUID(side["entity_id"]) for side in case.values_snapshot}
            raw = session.scalars(
                select(RawRecord).where(RawRecord.id.in_(raw_ids)).order_by(RawRecord.id)
            ).all()
            originals = session.scalars(
                select(ImportBatch)
                .where(ImportBatch.id.in_({r.import_batch_id for r in raw}))
                .order_by(ImportBatch.id)
            ).all()
            normalized = session.scalars(
                select(EntityValue)
                .where(EntityValue.entity_id.in_(entity_ids))
                .order_by(EntityValue.id)
            ).all()
            match = session.get(MatchCandidate, case.match_candidate_id)
            decisions = session.scalars(
                select(Decision)
                .where(Decision.conflict_id == case.id)
                .order_by(Decision.decided_at, Decision.id)
            ).all()

            def columns(rows, fields):
                return [[getattr(row, field) for field in fields] for row in rows]

            return {
                "raw": digest(columns(raw, ["id", "raw_payload", "source_position"])),
                "originals": digest(columns(originals, ["id", "file_hash", "storage_uri"])),
                "normalization": digest(
                    columns(normalized, ["id", "normalized_value", "normalization_rule"])
                ),
                "matching": digest([match.id, match.status, match.evidence, match.confirmed_by]),
                "evidence": digest([case.basis, case.values_snapshot]),
                "decisions": digest(
                    columns(decisions, [column.name for column in Decision.__table__.columns])
                ),
            }

    try:
        with Session(engine) as session:
            stored = hash_password(secrets.token_urlsafe(24))
            for index, token in enumerate(tokens):
                session.add(
                    User(
                        id=user_ids[index],
                        login="stage6_restart_" + uuid4().hex,
                        full_name="Synthetic restart reviewer",
                        data_domains=["*"],
                        password_hash=stored,
                        roles=[UserRole(role_code="REVIEWER")],
                    )
                )
                session.flush()
                session.add(
                    AuthSession(
                        token_hash=token_digest(token),
                        user_id=user_ids[index],
                        created_at=datetime.now(UTC),
                        expires_at=datetime.now(UTC) + timedelta(hours=2),
                    )
                )
            session.commit()
            identifier = str(
                session.scalar(
                    select(Conflict.id)
                    .where(Conflict.conflict_type == "VALUE_MISMATCH")
                    .order_by(Conflict.detected_at.desc())
                    .limit(1)
                )
            )
        assert identifier != "None", "Run real browser fixtures before this proof"
        source_before = snapshots(identifier)
        command("stop", "-t", "30", "worker")
        command("stop", "redis")
        # Authenticated review uses PostgreSQL only, even when readiness is degraded.
        assert request("/health", expected=503)["components"]["redis"] == "unavailable"
        first_request = body(begin(identifier))
        first = request(f"/conflicts/{identifier}/decisions", first_request, expected=201)
        second_request = body(begin(identifier), "DEFERRED")
        second = request(f"/conflicts/{identifier}/decisions", second_request, expected=201)
        command("start", "redis")
        ready()
        # Two real authenticated HTTPS submissions with one frozen context: only one wins.
        review = begin(identifier)
        competing = [body(review), body(review)]

        def race(index):
            headers = {
                "Cookie": COOKIE_NAME + "=" + tokens[index + 1],
                "Origin": args.base_url,
                "Content-Type": "application/json",
            }
            operation = urllib.request.Request(
                args.base_url + f"/api/v1/conflicts/{identifier}/decisions",
                data=json.dumps(competing[index]).encode(),
                headers=headers,
            )
            try:
                response = urllib.request.urlopen(operation, context=context, timeout=10)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.status

        with ThreadPoolExecutor(2) as pool:
            statuses = sorted(pool.map(race, range(2)))
        assert statuses == [201, 409], statuses
        history_before = request(f"/conflicts/{identifier}/decisions")
        cards_before = {row["id"]: request("/decisions/" + row["id"]) for row in history_before}
        before = snapshots(identifier)
        for key in ["raw", "originals", "normalization", "matching", "evidence"]:
            assert before[key] == source_before[key], key
        engine.dispose()
        command("restart", "postgres", "redis", "backend", "frontend")
        command("up", "--no-build", "-d", "--wait", "--wait-timeout", "180")
        ready()
        after = snapshots(identifier)
        assert after == before
        assert request(f"/conflicts/{identifier}/decisions") == history_before
        assert {key: request("/decisions/" + key) for key in cards_before} == cards_before
        replay = request(f"/conflicts/{identifier}/decisions", first_request)
        assert replay["decision_id"] == first["decision_id"]
        assert replay["decision"]["status"] == "SUPERSEDED"
        assert (
            request(f"/conflicts/{identifier}/decisions", second_request)["decision_id"]
            == second["decision_id"]
        )
        print(
            json.dumps(
                {
                    "passed": True,
                    "source_commit": subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                    ).strip(),
                    "project": args.project,
                    "conflict_id": identifier,
                    "first_decision_id": first["decision_id"],
                    "superseding_decision_id": second["decision_id"],
                    "history_rows": len(history_before),
                    "concurrent_http_statuses": statuses,
                    "review_while_redis_stopped": True,
                    "exact_idempotent_replay_after_restart": True,
                    "same_https_history_and_cards": True,
                    "before": before,
                    "after": after,
                },
                indent=2,
            )
        )
    finally:
        # Preserve business facts and volumes. Restore only this isolated stack's services.
        command("up", "--no-build", "-d", "--wait", "--wait-timeout", "180")
        with Session(engine) as session:
            for user in session.scalars(select(User).where(User.id.in_(user_ids))):
                user.status = "DISABLED"
            for auth in session.scalars(
                select(AuthSession).where(AuthSession.user_id.in_(user_ids))
            ):
                auth.revoked_at = datetime.now(UTC)
            session.commit()
        engine.dispose()


if __name__ == "__main__":
    run()
