"""Real source→Conflict→human decision, atomic history and authorization boundaries."""

import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuditEvent, User
from app.common.database import make_engine
from app.conflicts.jobs import execute_conflict
from app.decisions.models import Decision
from app.main import create_app
from tests.test_auth import ORIGIN
from tests.test_auth import password as password
from tests.test_auth import role_tokens as role_tokens
from tests.test_conflicts_integration import inputs, rows
from tests.test_conflicts_integration import start as start_conflicts
from tests.test_matching_integration import auth_env as auth_env

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FK_TEST_INTEGRATION") != "1", reason="isolated database integration opt-in"
    ),
]


@pytest.fixture
def client(auth_env, role_tokens):
    with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as value:
        value.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
        yield value


def real_case(client, settings):
    matching = inputs(client, settings)
    run = start_conflicts(client, matching)
    execute_conflict(UUID(run["id"]), settings)
    case = next(row for row in rows(client, matching) if row["conflict_type"] == "VALUE_MISMATCH")
    return case["id"]


def context(client, identifier):
    response = client.get(f"/api/v1/conflicts/{identifier}/review-context")
    assert response.status_code == 200, response.text
    return response.json()


def begin(client, identifier, previous=None):
    old = context(client, identifier)
    response = client.post(
        f"/api/v1/conflicts/{identifier}/review",
        headers=ORIGIN,
        json={"context_version": old["context_version"], "supersedes_decision_id": previous},
    )
    assert response.status_code == 200, response.text
    return response.json()


def selection(review, index=0):
    value = review["selectable_values"][index]
    return {
        "context_version": review["context_version"],
        "idempotency_key": str(uuid4()),
        "decision_type": "SELECT_VALUE",
        "selected_source_id": value["source_id"],
        "selected_value_id": value["value_id"],
        "reason": "Проверен исходный документ и единица массы.",
        "supersedes_decision_id": review["current_decision"]["id"]
        if review["current_decision"]
        else None,
        "confirmed": True,
    }


def save(client, identifier, body, expected=201):
    response = client.post(f"/api/v1/conflicts/{identifier}/decisions", headers=ORIGIN, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def test_real_decision_receipt_history_idempotency_and_source_preservation(client, auth_env):
    identifier = real_case(client, auth_env)
    original = client.get(f"/api/v1/conflicts/{identifier}").json()
    before = context(client, identifier)
    assert before["conflict_status"] == "OPEN"
    assert client.get(f"/api/v1/conflicts/{identifier}").json()["status"] == "OPEN"
    review = begin(client, identifier)
    assert review["conflict_status"] == "IN_REVIEW"
    request = selection(review)
    result = save(client, identifier, request)
    assert result["conflict_status"] == "RESOLVED" and not result["source_systems_changed"]
    assert result["decision"]["selected_value"] == review["selectable_values"][0]["value"]
    retry = save(client, identifier, request, expected=200)
    assert retry["decision_id"] == result["decision_id"]
    assert (
        client.get(f"/api/v1/decisions/{result['decision_id']}").json()["reason"]
        == request["reason"]
    )
    assert (
        client.get(f"/api/v1/conflicts/{identifier}/decisions").json()[0]["id"]
        == result["decision_id"]
    )
    after = client.get(f"/api/v1/conflicts/{identifier}").json()
    assert after["status"] == "RESOLVED"
    assert (
        after["values_snapshot"] == original["values_snapshot"]
        and after["basis"] == original["basis"]
    )
    save(client, identifier, {**request, "reason": "Изменённый запрос тем же ключом"}, expected=409)
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(Decision)
                    .where(Decision.conflict_id == UUID(identifier))
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.object_id == UUID(identifier),
                        AuditEvent.event_type == "DECISION_CREATED",
                    )
                )
                == 1
            )
    finally:
        engine.dispose()


def test_superseding_preserves_both_facts_and_explicit_lifecycle(client, auth_env):
    identifier = real_case(client, auth_env)
    first = save(client, identifier, selection(begin(client, identifier)))
    old = client.get(f"/api/v1/decisions/{first['decision_id']}").json()
    correction = begin(client, identifier, first["decision_id"])
    second = save(
        client,
        identifier,
        {
            "context_version": correction["context_version"],
            "idempotency_key": str(uuid4()),
            "decision_type": "ENTER_VALUE",
            "corrected_value": "13,250",
            "corrected_unit": "kg",
            "supersedes_decision_id": first["decision_id"],
            "reason": "Повторная проверка документа: масса уточнена человеком.",
            "confirmed": True,
        },
    )
    assert second["decision"]["selected_value"] == "13.25"
    assert second["decision"]["supersedes_decision_id"] == first["decision_id"]
    historical = client.get(f"/api/v1/decisions/{first['decision_id']}").json()
    assert (
        historical["status"] == "SUPERSEDED"
        and historical["superseded_by"] == second["decision_id"]
    )
    for field in ["selected_value", "reason", "user_id", "decided_at", "context_snapshot"]:
        assert historical[field] == old[field]
    history = client.get(f"/api/v1/conflicts/{identifier}/decisions").json()
    assert [row["status"] for row in history] == ["SUPERSEDED", "ACTIVE"]
    assert (
        client.patch(
            f"/api/v1/decisions/{first['decision_id']}", headers=ORIGIN, json={}
        ).status_code
        == 405
    )
    assert (
        client.delete(f"/api/v1/decisions/{first['decision_id']}", headers=ORIGIN).status_code
        == 405
    )


@pytest.mark.parametrize(
    "outcome,state", [("INSUFFICIENT_DATA", "INSUFFICIENT_DATA"), ("DEFERRED", "IN_REVIEW")]
)
def test_unresolved_decisions_never_resolve_a_conflict(client, auth_env, outcome, state):
    identifier = real_case(client, auth_env)
    review = begin(client, identifier)
    result = save(
        client,
        identifier,
        {
            "context_version": review["context_version"],
            "idempotency_key": str(uuid4()),
            "decision_type": outcome,
            "reason": "Сохранено явное объяснение отсутствующих данных.",
            "confirmed": True,
        },
    )
    assert result["conflict_status"] == state
    assert result["decision"]["selected_value"] is None
    assert context(client, identifier)["current_decision"]["id"] == result["decision_id"]


def test_stale_and_concurrent_reviewers_cannot_create_two_heads(client, auth_env, role_tokens):
    identifier = real_case(client, auth_env)
    review = begin(client, identifier)
    requests = [selection(review, index) for index in [0, 1]]

    def submit(value):
        with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as other:
            other.cookies.set(COOKIE_NAME, role_tokens["REVIEWER"])
            return other.post(
                f"/api/v1/conflicts/{identifier}/decisions", headers=ORIGIN, json=value
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, requests))
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert len(client.get(f"/api/v1/conflicts/{identifier}/decisions").json()) == 1
    assert (
        next(r for r in responses if r.status_code == 409).json()["error"]["code"]
        == "STALE_REVIEW_CONTEXT"
    )


def test_failure_rolls_back_decision_state_and_business_audit(client, auth_env):
    identifier = real_case(client, auth_env)
    request = selection(begin(client, identifier))
    with patch("app.decisions.service.audit", side_effect=SQLAlchemyError("synthetic failure")):
        save(client, identifier, request, expected=503)
    assert context(client, identifier)["current_decision"] is None
    assert client.get(f"/api/v1/conflicts/{identifier}").json()["status"] == "IN_REVIEW"
    assert client.get(f"/api/v1/conflicts/{identifier}/decisions").json() == []
    save(client, identifier, request)


def test_rbac_scope_and_immutable_database_guards(client, auth_env, role_tokens):
    identifier = real_case(client, auth_env)
    review = begin(client, identifier)
    request = selection(review)
    for role in ["VIEWER", "ADMIN", "NO_ROLES"]:
        client.cookies.set(COOKIE_NAME, role_tokens[role])
        save(client, identifier, request, expected=403)
    client.cookies.set(COOKIE_NAME, role_tokens["REVIEWER"])
    result = save(client, identifier, request)
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            reviewer = session.scalar(select(User).where(User.login == "reviewer"))
            user_id = reviewer.id
            reviewer.data_domains = ["another-domain"]
            session.commit()
        try:
            assert client.get(f"/api/v1/conflicts/{identifier}/review-context").status_code == 404
            assert client.get(f"/api/v1/conflicts/{identifier}").status_code == 404
            assert client.get(f"/api/v1/decisions/{result['decision_id']}").status_code == 404
            assert client.get(f"/api/v1/decisions?conflict_id={identifier}").json() == []
        finally:
            with Session(engine) as session:
                session.get(User, user_id).data_domains = ["*"]
                session.commit()
        for query in [
            "UPDATE decisions SET reason='rewrite' WHERE id=:id",
            "DELETE FROM decisions WHERE id=:id",
        ]:
            with pytest.raises(DBAPIError), engine.begin() as connection:
                connection.execute(text(query), {"id": UUID(result["decision_id"])})
    finally:
        engine.dispose()


@pytest.mark.parametrize("index", [0, 1])
def test_each_frozen_source_is_selectable_and_registry_is_light(client, auth_env, index):
    identifier = real_case(client, auth_env)
    review = begin(client, identifier)
    result = save(client, identifier, selection(review, index))
    chosen = review["selectable_values"][index]
    assert result["decision"]["selected_source_id"] == chosen["source_id"]
    assert result["decision"]["selected_value_id"] == chosen["value_id"]
    listing = client.get(f"/api/v1/decisions?conflict_id={identifier}&status=ACTIVE").json()
    assert len(listing) == 1 and "context_snapshot" not in listing[0]
    assert "corrected_input" not in listing[0]
    assert client.get(f"/api/v1/decisions?conflict_id={identifier}&status=SUPERSEDED").json() == []
    assert client.get("/api/v1/decisions?date_from=2026-01-01T00:00:00").status_code == 422


@pytest.mark.parametrize("origin", [None, "null", "https://foreign.example"])
def test_review_requires_cookie_and_trusted_origin(client, auth_env, origin):
    identifier = real_case(client, auth_env)
    request = selection(begin(client, identifier))
    response = client.post(
        f"/api/v1/conflicts/{identifier}/decisions",
        headers={"Origin": origin} if origin else {},
        json=request,
    )
    assert response.status_code == 403
    assert client.get(f"/api/v1/conflicts/{identifier}/decisions").json() == []
    client.cookies.clear()
    save(client, identifier, request, expected=401)


@pytest.mark.parametrize(
    "field,value",
    [
        ("user_id", str(uuid4())),
        ("status", "ACTIVE"),
        ("confirmed", False),
        ("reason", "   "),
        ("reason", "x" * 2001),
        ("selected_source_id", str(uuid4())),
        ("selected_value_id", str(uuid4())),
        ("decision_type", "AUTO_ACCEPT"),
    ],
)
def test_untrusted_submission_never_changes_evidence(client, auth_env, field, value):
    identifier = real_case(client, auth_env)
    request = selection(begin(client, identifier))
    before = client.get(f"/api/v1/conflicts/{identifier}").json()
    response = client.post(
        f"/api/v1/conflicts/{identifier}/decisions",
        headers=ORIGIN,
        json={**request, field: value},
    )
    assert response.status_code in {409, 422}
    assert client.get(f"/api/v1/conflicts/{identifier}").json() == before
    assert client.get(f"/api/v1/conflicts/{identifier}/decisions").json() == []


def test_scope_revocation_between_context_and_submit_denies_even_retry(client, auth_env):
    identifier = real_case(client, auth_env)
    request = selection(begin(client, identifier))
    result = save(client, identifier, request)
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            actor = session.scalar(select(User).where(User.login == "data_owner"))
            actor_id = actor.id
            actor.data_domains = []
            session.commit()
        try:
            save(client, identifier, request, expected=404)
            assert client.get(f"/api/v1/decisions/{result['decision_id']}").status_code == 404
            assert client.get(f"/api/v1/conflicts/{identifier}/decisions").status_code == 404
            assert client.get(f"/api/v1/decisions?conflict_id={identifier}").json() == []
        finally:
            with Session(engine) as session:
                session.get(User, actor_id).data_domains = ["*"]
                session.commit()
        assert (
            save(client, identifier, request, expected=200)["decision_id"] == result["decision_id"]
        )
    finally:
        engine.dispose()


def test_concurrent_identical_retry_creates_one_decision(client, auth_env, role_tokens):
    identifier = real_case(client, auth_env)
    request = selection(begin(client, identifier))

    def submit(_):
        with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as other:
            other.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
            return other.post(
                f"/api/v1/conflicts/{identifier}/decisions", headers=ORIGIN, json=request
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sorted(row.status_code for row in results) == [200, 201]
    assert len({row.json()["decision_id"] for row in results}) == 1


def test_committed_but_lost_response_returns_same_receipt(client, auth_env):
    identifier = real_case(client, auth_env)
    request = selection(begin(client, identifier))
    with patch("app.decisions.service.receipt", side_effect=SQLAlchemyError("lost response")):
        save(client, identifier, request, expected=503)
    history = client.get(f"/api/v1/conflicts/{identifier}/decisions").json()
    assert len(history) == 1
    recovered = save(client, identifier, request, expected=200)
    assert recovered["decision_id"] == history[0]["id"]


def test_failure_after_decision_insert_rolls_back_all_business_effects(client, auth_env):
    from app.decisions.service import audit

    identifier = real_case(client, auth_env)
    request = selection(begin(client, identifier))

    def interrupted(session, actor_id, case_id, event, request_id, **metadata):
        if event == "CONFLICT_LIFECYCLE_CHANGED":
            raise SQLAlchemyError("synthetic failure after insert")
        return audit(session, actor_id, case_id, event, request_id, **metadata)

    with patch("app.decisions.service.audit", side_effect=interrupted):
        save(client, identifier, request, expected=503)
    assert client.get(f"/api/v1/conflicts/{identifier}/decisions").json() == []
    assert context(client, identifier)["conflict_status"] == "IN_REVIEW"
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.object_id == UUID(identifier),
                        AuditEvent.event_type == "DECISION_CREATED",
                    )
                )
                == 0
            )
    finally:
        engine.dispose()
    save(client, identifier, request)


def test_db_rejects_new_final_decision_without_atomic_final_lifecycle(client, auth_env):
    from sqlalchemy import insert

    identifier = real_case(client, auth_env)
    first = save(client, identifier, selection(begin(client, identifier)))
    begin(client, identifier, first["decision_id"])
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            row = session.get(Decision, UUID(first["decision_id"]))
            cloned = {
                column.name: getattr(row, column.name) for column in Decision.__table__.columns
            }
        new_id = uuid4()
        cloned.update(
            id=new_id, idempotency_key=uuid4(), supersedes_decision_id=UUID(first["decision_id"])
        )
        with pytest.raises(DBAPIError, match="atomic lifecycle"), engine.begin() as connection:
            connection.execute(insert(Decision).values(**cloned))
            connection.execute(
                text(
                    "UPDATE conflicts SET current_decision_id=:head,"
                    "review_version=review_version+1 WHERE id=:id"
                ),
                {"head": new_id, "id": UUID(identifier)},
            )
        assert len(client.get(f"/api/v1/conflicts/{identifier}/decisions").json()) == 1
        for query in [
            "UPDATE conflicts SET values_snapshot='[]'::jsonb,"
            "review_version=review_version+1 WHERE id=:id",
            "UPDATE conflicts SET status='RESOLVED',current_decision_id=NULL,"
            "review_version=review_version+1 WHERE id=:id",
            "DELETE FROM conflicts WHERE id=:id",
        ]:
            with pytest.raises(DBAPIError), engine.begin() as connection:
                connection.execute(text(query), {"id": UUID(identifier)})
    finally:
        engine.dispose()


def test_history_blocks_destructive_migration_downgrade(client, auth_env):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config as AlembicConfig

    identifier = real_case(client, auth_env)
    result = save(client, identifier, selection(begin(client, identifier)))
    with patch.dict(os.environ, {"FK_DATABASE_URL": auth_env.database_url.get_secret_value()}):
        with pytest.raises(RuntimeError, match="Decision history exists"):
            command.downgrade(
                AlembicConfig(str(Path(__file__).resolve().parents[1] / "alembic.ini")),
                "0006_conflicts",
            )
    assert client.get(f"/api/v1/decisions/{result['decision_id']}").status_code == 200


def test_data_scope_assignment_is_explicit_privileged_and_audited(
    client, auth_env, role_tokens, password
):
    client.cookies.set(COOKIE_NAME, role_tokens["ADMIN"])
    created = client.post(
        "/api/v1/users",
        headers=ORIGIN,
        json={
            "login": "scope_" + uuid4().hex,
            "full_name": "Scope tester",
            "password": password,
            "roles": ["REVIEWER"],
        },
    )
    assert created.status_code == 201, created.text
    actor = created.json()
    assert actor["data_domains"] == []
    path = f"/api/v1/users/{actor['id']}/data-scope"
    assert (
        client.put(path, headers=ORIGIN, json={"data_domains": ["*", "other"]}).status_code == 422
    )
    granted = client.put(path, headers=ORIGIN, json={"data_domains": ["synthetic-material"]})
    assert granted.status_code == 200, granted.text
    assert granted.json()["data_domains"] == ["synthetic-material"]
    client.cookies.set(COOKIE_NAME, role_tokens["REVIEWER"])
    assert client.put(path, headers=ORIGIN, json={"data_domains": ["*"]}).status_code == 403
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            event = session.scalar(
                select(AuditEvent).where(
                    AuditEvent.object_id == UUID(actor["id"]),
                    AuditEvent.event_type == "DATA_SCOPE_ASSIGNED",
                )
            )
            assert event is not None
    finally:
        engine.dispose()


def test_role_revocation_between_context_and_submit_is_rechecked(client, auth_env):
    from app.auth.models import UserRole

    identifier = real_case(client, auth_env)
    request = selection(begin(client, identifier))
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            actor = session.scalar(select(User).where(User.login == "data_owner"))
            actor_id = actor.id
            actor.roles = []
            session.commit()
        try:
            save(client, identifier, request, expected=403)
        finally:
            with Session(engine) as session:
                session.get(User, actor_id).roles = [UserRole(role_code="DATA_OWNER")]
                session.commit()
        assert client.get(f"/api/v1/conflicts/{identifier}/decisions").json() == []
        save(client, identifier, request)
    finally:
        engine.dispose()
