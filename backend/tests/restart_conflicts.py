"""Opt-in restart of the development Compose stack, preserving real browser-created facts."""

import hashlib
import json
import os
import secrets
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.config import Settings
from app.common.database import make_engine
from app.conflicts.models import Conflict
from app.imports.models import ImportBatch, RawRecord
from app.matching.models import MatchCandidate
from app.normalization.models import EntityValue

ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def run():
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Development Compose only: opt in with FK_TEST_INTEGRATION=1")
    engine = make_engine(Settings())
    token, user_id = secrets.token_urlsafe(32), uuid4()
    context = ssl.create_default_context(cafile=str(ROOT / "deploy/local/tls/dev.crt"))

    def get(path):
        request = urllib.request.Request(
            "https://localhost:8443/api/v1" + path, headers={"Cookie": COOKIE_NAME + "=" + token}
        )
        with urllib.request.urlopen(request, context=context, timeout=5) as response:
            assert response.status == 200
            return json.load(response)

    def snapshots():
        with Session(engine) as session:
            conflicts = session.scalars(select(Conflict).order_by(Conflict.id)).all()
            assert conflicts, "Run browser E2E before restart test"
            values = [
                (str(row.id), row.basis, row.values_snapshot, row.status, row.detected_at)
                for row in conflicts
            ]
            raw_ids = {item["raw_record_id"] for row in conflicts for item in row.values_snapshot}
            entity_ids = {item["entity_id"] for row in conflicts for item in row.values_snapshot}
            raw = session.scalars(
                select(RawRecord).where(RawRecord.id.in_(raw_ids)).order_by(RawRecord.id)
            ).all()
            originals = session.scalars(
                select(ImportBatch)
                .where(ImportBatch.id.in_({row.import_batch_id for row in raw}))
                .order_by(ImportBatch.id)
            ).all()
            normalized = session.scalars(
                select(EntityValue)
                .where(EntityValue.entity_id.in_(entity_ids))
                .order_by(EntityValue.id)
            ).all()
            matches = session.scalars(
                select(MatchCandidate)
                .where(MatchCandidate.id.in_({row.match_candidate_id for row in conflicts}))
                .order_by(MatchCandidate.id)
            ).all()

            def columns(rows, fields):
                return [[getattr(row, field) for field in fields] for row in rows]

            return {
                "conflict_ids": [str(row.id) for row in conflicts],
                "conflicts": digest(values),
                "raw": digest(columns(raw, ["id", "raw_payload", "source_position"])),
                "normalization": digest(
                    columns(normalized, ["id", "normalized_value", "normalization_rule"])
                ),
                "matching": digest(columns(matches, ["id", "status", "evidence", "confirmed_by"])),
                "originals": digest(columns(originals, ["id", "file_hash", "storage_uri"])),
            }

    try:
        with Session(engine) as session:
            session.add(
                User(
                    id=user_id,
                    login="restart_" + uuid4().hex,
                    full_name="Synthetic restart viewer",
                    password_hash=hash_password(secrets.token_urlsafe(24)),
                    roles=[UserRole(role_code="VIEWER")],
                )
            )
            session.flush()
            session.add(
                AuthSession(
                    token_hash=token_digest(token),
                    user_id=user_id,
                    created_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            session.commit()
        before = snapshots()
        cards_before = {
            identifier: get("/conflicts/" + identifier) for identifier in before["conflict_ids"]
        }
        engine.dispose()
        subprocess.run(
            ["docker", "compose", "restart", "postgres", "redis", "backend", "worker", "frontend"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        for _attempt in range(60):
            try:
                if get("/health")["status"] == "ok":
                    break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(1)
        else:
            raise AssertionError("Readiness failed after restart")
        after = snapshots()
        assert after == before
        cards_after = {
            identifier: get("/conflicts/" + identifier) for identifier in before["conflict_ids"]
        }
        assert cards_after == cards_before
        print(
            json.dumps(
                {
                    "passed": True,
                    "before": before,
                    "after": after,
                    "https_cards_identical": True,
                    "scope": (
                        "development Compose persistent volumes; "
                        "browser-created Conflict and Stage2-4 lineage"
                    ),
                },
                indent=2,
            )
        )
    finally:
        with Session(engine) as session:
            session.execute(delete(User).where(User.id == user_id))
            session.commit()
        engine.dispose()


if __name__ == "__main__":
    run()
