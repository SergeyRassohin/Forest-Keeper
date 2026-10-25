"""Owned Stage 8 actual HTTPS, human confirmation, restart and fail-closed proof."""

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
from xml.sax.saxutils import escape

import httpx
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuthSession, User, UserRole
from app.auth.security import hash_password, token_digest
from app.common.config import Settings
from app.common.database import make_engine
from app.decisions.models import Decision
from app.decisions.service import digest
from app.matching.profiles import catalog
from app.similarity.jobs import execute_index
from app.similarity.models import IndexRun
from app.similarity.service import start_run

ROOT = Path(__file__).resolve().parents[2]


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--override", required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    if os.getenv("FK_TEST_INTEGRATION") != "1" or args.project != "fk-stage8":
        raise SystemExit("Only this task's owned fk-stage8 development project is supported")
    if args.base_url != "https://localhost:18449":
        raise SystemExit("Owned Stage 8 HTTPS address required")
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
    active_compose = list(compose)

    def command(*parts):
        result = subprocess.run([*active_compose, *parts], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("Owned runtime operation failed: " + parts[0])
        return result.stdout

    port = command("port", "postgres", "5432").strip()
    if make_url(settings.database_url.get_secret_value()).port != int(port.rsplit(":", 1)[1]):
        raise SystemExit("Database must belong to the selected owned project")
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
    prefix = "s8_runtime_" + identifier.hex[:12]
    sources, cases, decisions = [], [], []
    report = {
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "project": args.project,
    }
    override_path = Path("/tmp/fk-stage8-runtime-policy.json")

    def api(method, path, expected=200, **kwargs):
        response = client.request(method, path, **kwargs)
        assert response.status_code == expected, (method, path, response.status_code, response.text)
        return response.json()

    def wait(path, expected="COMPLETED", field="status", timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                response = client.get(path)
                if response.status_code == 200:
                    result = response.json()
                    if result.get(field) == expected:
                        return result
                    assert result.get("status") != "FAILED", "Background operation failed"
            except httpx.TransportError:
                pass
            time.sleep(0.5)
        raise AssertionError("Bounded readiness timeout: " + path)

    def case():
        key = prefix + "-" + str(len(cases))
        subject = (
            " ".join(["cohort" + identifier.hex[:16]] * 5) + " material bolt steel reference " + key
        )
        csv = f"id,name,mass,price,date\n{key},{subject},12.5 kg,10,2026-01-01\n".encode()
        xml = (
            f'<Выгрузка><Объект Тип="Справочник.Номенклатура" Ид="{escape(key)}">'
            f"<Наименование>{escape(subject)}</Наименование><Масса>12.4 kg</Масса>"
            "<Цена>10</Цена><Дата>2026-01-01</Дата></Объект></Выгрузка>"
        ).encode()
        profile = next(
            p for p in api("GET", "/analysis/profiles") if p["code"] == "synthetic-material"
        )
        analyses = []
        for source, name, content in zip(
            sources, ["material.csv", "onec.xml"], [csv, xml], strict=True
        ):
            batch = api(
                "POST",
                "/imports",
                expected=201,
                data={"source_id": source["source_id"]},
                files={
                    "file": (
                        name,
                        content,
                        "text/csv" if name.endswith("csv") else "application/xml",
                    )
                },
            )
            wait("/imports/" + batch["id"])
            analysis = api(
                "POST",
                "/analysis",
                expected=201,
                json={"import_batch_ids": [batch["id"]], "template_id": profile["id"]},
            )
            wait("/analysis/" + analysis["id"])
            analyses.append(analysis["id"])
        matching_profile = next(
            p for p in api("GET", "/matching-profiles") if p["code"] == "synthetic-material"
        )
        matching = api(
            "POST",
            "/matching-runs",
            expected=201,
            json={"analysis_run_ids": analyses, "profile_id": matching_profile["id"]},
        )
        wait("/matching-runs/" + matching["id"])
        conflicts = api(
            "POST", "/conflict-runs", expected=201, json={"matching_run_id": matching["id"]}
        )
        wait("/conflict-runs/" + conflicts["id"])
        found = api("GET", "/conflicts?matching_run_id=" + matching["id"])
        assert len(found) == 1 and found[0]["conflict_type"] == "VALUE_MISMATCH", found
        cases.append(found[0]["id"])
        return cases[-1]

    def begin(case_id):
        context = api("GET", f"/conflicts/{case_id}/review-context")
        return api(
            "POST",
            f"/conflicts/{case_id}/review",
            json={"context_version": context["context_version"]},
        )

    def body(context, reference=None):
        value = next(
            v for v in context["selectable_values"] if v["source_id"] == sources[0]["source_id"]
        )
        result = {
            "context_version": context["context_version"],
            "idempotency_key": str(uuid4()),
            "decision_type": "SELECT_VALUE",
            "selected_source_id": value["source_id"],
            "selected_value_id": value["value_id"],
            "confirmed": True,
            "reason": "Synthetic runtime acceptance: human confirms current source.",
        }
        if reference:
            result["recommendation_reference"] = reference
        return result

    def save(case_id, payload, expected=201):
        result = api("POST", f"/conflicts/{case_id}/decisions", expected=expected, json=payload)
        if expected == 201:
            decisions.append(result["decision_id"])
        return result

    def facts():
        with Session(engine) as session:
            return digest(
                [
                    [getattr(d, c.name) for c in Decision.__table__.columns]
                    for d in session.scalars(select(Decision).order_by(Decision.id))
                ]
            )

    def ready(case_id):
        wait(f"/conflicts/{case_id}/similar-decisions", "READY", "state")
        result = wait(f"/conflicts/{case_id}/recommendation", "RECOMMENDED")
        assert result["quality_provenance"] == "DEMONSTRATION_ONLY" and result["confidence"] >= 5
        return result

    try:
        with Session(engine) as session:
            session.add(
                User(
                    id=identifier,
                    login=prefix,
                    full_name="Stage 8 synthetic runtime operator",
                    data_domains=["*"],
                    password_hash=hash_password(secrets.token_urlsafe(24)),
                    roles=[UserRole(role_code="DATA_OWNER")],
                )
            )
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
        for source_type, role in [("FILE", "REGISTER_EXPORT"), ("ONE_C", "ACCOUNTING_EXPORT")]:
            source = api(
                "POST",
                "/sources",
                expected=201,
                json={
                    "code": prefix + "_" + source_type,
                    "name": "Synthetic runtime " + role,
                    "source_type": source_type,
                },
            )
            sources.append({"source_id": source["id"], "source_type": source_type, "role": role})
        profile = next(p for p in catalog().values() if p.code == "synthetic-material")
        mapping = {
            "version": prefix + "-v1",
            "approved": True,
            "approval_reference": "Owned synthetic operator assigns these exact source IDs.",
            "domain": "synthetic-material",
            "entity_type": "Material",
            "attribute_code": "mass",
            "matching_profile_hashes": [profile.digest()],
            "sources": sources,
        }
        flags = {
            "FK_DEPLOYMENT_MODE": "test",
            "FK_SIMILARITY_PROVIDER": "test",
            "FK_SIMILARITY_ALLOW_TEST_PROVIDER": "true",
            "FK_SIMILARITY_AUTOINDEX": "false",
            "FK_RECOMMENDATION_ENABLED": "true",
            "FK_RECOMMENDATION_SOURCE_MAP": json.dumps(mapping),
        }
        override_path.write_text(
            json.dumps(
                {
                    "services": {
                        service: {"environment": flags}
                        for service in ["backend", "worker", "migrate"]
                    }
                }
            )
        )
        override_path.chmod(0o600)
        command("stop", "frontend", "backend", "worker")
        active_compose = [*compose, "-f", str(override_path)]
        command("up", "--no-build", "-d", "--wait", "--wait-timeout", "180")
        settings = settings.model_copy(
            update={
                "deployment_mode": "test",
                "similarity_provider": "test",
                "similarity_allow_test_provider": True,
                "recommendation_enabled": True,
                "recommendation_source_map": mapping,
            }
        )
        for _ in range(5):
            first = case()
            save(first, body(begin(first)))
        query = case()
        command(
            "exec", "-T", "backend", "python", "-m", "app.similarity.cli", "start", "--activate"
        )
        ready(query)
        review = begin(query)
        recommendation = ready(query)
        assert set(recommendation["supporting_decision_ids"]) == set(decisions)
        checkpoint = facts()
        command("restart", "postgres", "redis", "backend", "worker", "frontend")
        wait("/health", "ok")
        restored = ready(query)
        assert restored == recommendation and facts() == checkpoint
        payload = body(review, restored["audit_reference"])
        receipt = save(query, payload)
        assert (
            receipt["decision"]["context_snapshot"]["recommendation"]["relationship"] == "MATCHED"
        )
        assert save(query, payload, expected=200)["decision_id"] == receipt["decision_id"]
        report.update(
            actual_https=True,
            five_independent_real_file_pairs=True,
            reference_survives_full_restart=True,
            human_confirmed_receipt=True,
            unchanged_history_after_restart=True,
        )

        next_case = case()
        old_version = restored["retrieval_version"]
        assert api("GET", f"/conflicts/{next_case}/recommendation")["status"] == "UNAVAILABLE"
        command("stop", "worker")
        with Session(engine) as session:
            run = start_run(session, settings, "test-v2", batch_size=1)
            run.status = "QUEUED"
            session.commit()
            run_id, version_id = run.id, run.version_id
        execute_index(run_id, settings, max_batches=1)
        with Session(engine) as session:
            assert session.get(IndexRun, run_id).processed == 1
            assert session.get(IndexRun, run_id).status == "PROCESSING"
        checkpoint = facts()
        command("restart", "postgres", "redis", "backend", "frontend")
        wait("/health", "ok")
        assert facts() == checkpoint
        command("start", "worker")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            with Session(engine) as session:
                if session.get(IndexRun, run_id).status == "COMPLETED":
                    break
            time.sleep(0.5)
        else:
            raise AssertionError("Durable partial index was not recovered")
        assert (
            api("GET", f"/conflicts/{next_case}/recommendation")["retrieval_version"] == old_version
        )
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
        begin_next = begin(next_case)
        next_rec = ready(next_case)
        assert next_rec["retrieval_version"] == str(version_id)
        assert receipt["decision_id"] in next_rec["supporting_decision_ids"]
        stale_payload = body(begin_next, next_rec["audit_reference"])
        # A previous version must first cover the newly confirmed history;
        # activating a genuinely incomplete version is correctly forbidden.
        with Session(engine) as session:
            previous = start_run(session, settings, "test-v1")
            previous.status = "QUEUED"
            session.commit()
            previous_id = previous.id
        execute_index(previous_id, settings)
        command(
            "exec",
            "-T",
            "backend",
            "python",
            "-m",
            "app.similarity.cli",
            "activate",
            "--version",
            old_version,
        )
        save(next_case, stale_payload, expected=409)
        save(next_case, body(begin_next))
        report.update(
            partial_checkpoint_recovered=True,
            explicit_activation=True,
            version_change_rejects_stale_reference=True,
            manual_save_after_stale=True,
        )

        final_case = case()
        command(
            "exec",
            "-T",
            "backend",
            "python",
            "-m",
            "app.similarity.cli",
            "start",
            "--revision",
            "test-v2",
            "--activate",
        )
        final = ready(final_case)
        checkpoint = facts()
        command("restart", "postgres", "redis", "backend", "worker", "frontend")
        wait("/health", "ok")
        assert ready(final_case) == final and facts() == checkpoint
        command("stop", "postgres")
        failed = client.get(f"/conflicts/{final_case}/recommendation")
        assert failed.status_code == 503 and "password" not in failed.text.lower()
        command("start", "postgres")
        wait("/health", "ok")
        assert ready(final_case) == final
        manual_payload = body(begin(final_case))
        command("stop", "redis")
        api("GET", f"/conflicts/{final_case}/recommendation", expected=503)
        assert save(query, payload, expected=200)["decision_id"] == receipt["decision_id"]
        save(final_case, manual_payload)
        command("start", "redis")
        report.update(
            postgres_failure_sanitized_recovery=True,
            redis_failure_manual_save=True,
            redis_failure_exact_reference_retry=True,
            second_restart_stable=True,
        )

        command("stop", "frontend", "backend", "worker")
        active_compose = list(compose)
        command("up", "--no-build", "-d", "--wait", "--wait-timeout", "180")
        unavailable_case = case()
        unavailable = api("GET", f"/conflicts/{unavailable_case}/recommendation")
        assert unavailable["status"] == "UNAVAILABLE" and unavailable["recommended_action"] is None
        save(unavailable_case, body(begin(unavailable_case)))
        assert api("GET", "/decisions/" + receipt["decision_id"])["id"] == receipt["decision_id"]
        report.update(
            default_configuration_fail_closed=True,
            provider_unavailable_manual_save=True,
            registry_independent=True,
            decisions=decisions,
            passed=True,
        )
        Path("/tmp/fk-stage8-runtime.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report), flush=True)
    finally:
        # Preserve synthetic business facts, files and volumes; restore default fail-closed config.
        try:
            command("start", "postgres", "redis")
            command("stop", "frontend", "backend", "worker")
            active_compose = list(compose)
            command("up", "--no-build", "-d", "--wait", "--wait-timeout", "180")
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
