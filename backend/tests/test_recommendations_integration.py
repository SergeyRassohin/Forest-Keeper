"""Actual persisted evidence, human confirmation and fail-closed/scoped boundaries."""

import os
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import AuditEvent, User
from app.main import create_app
from tests.recommendation_fixtures import Cases
from tests.test_auth import ORIGIN
from tests.test_auth import password as password
from tests.test_auth import role_tokens as _base_tokens
from tests.test_decisions_integration import begin, context, save, selection
from tests.test_matching_integration import auth_env as _base_environment
from tests.test_similarity_integration import enabled, index, similar

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("FK_TEST_INTEGRATION") != "1", reason="owned schema opt-in"),
]


@pytest.fixture
def auth_env(tmp_path_factory):
    yield from _base_environment.__wrapped__(tmp_path_factory)


@pytest.fixture
def role_tokens(auth_env, password):
    return _base_tokens.__wrapped__(auth_env, password)


@pytest.fixture
def client(auth_env, role_tokens):
    settings = enabled(auth_env).model_copy(update={"recommendation_enabled": True})
    with TestClient(create_app(settings=settings), base_url="https://localhost:8443") as value:
        value.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
        yield value


def recommendation(client, identifier, expected=200):
    response = client.get(f"/api/v1/conflicts/{identifier}/recommendation")
    assert response.status_code == expected, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def business_hash(session):
    tables = (
        "sources",
        "import_batches",
        "raw_records",
        "analysis_runs",
        "canonical_entities",
        "entity_values",
        "matching_runs",
        "match_candidates",
        "conflicts",
        "decisions",
    )
    # The names are a fixed fixture-owned list, not application/client input.
    existing = set(
        session.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()"))
    )
    return {
        table: session.scalar(
            text(
                "SELECT md5(coalesce(string_agg(to_jsonb(t)::text, '' "
                "ORDER BY to_jsonb(t)::text), '')) "
                'FROM "' + table + '" t'
            )
        )
        for table in tables
        if table in existing
    }


def test_five_real_independent_cases_recommend_current_value_and_audit_without_business_writes(
    client,
):
    cases = Cases(client)
    query = cases.prepared()
    with Session(client.app.state.engine) as session:
        before = business_hash(session)
    result = recommendation(client, query)
    assert result["status"] == "RECOMMENDED", result
    assert result["recommended_source_id"] == cases.sources[0]["source_id"]
    current = context(client, query)
    selected = next(
        v for v in current["selectable_values"] if v["source_id"] == result["recommended_source_id"]
    )
    assert result["recommended_value_id"] == selected["value_id"]
    assert result["recommended_value"]["value"] == selected["value"]
    assert (
        result["confidence"] == 5 and result["confidence_unit"] == "INDEPENDENT_PROVENANCE_GROUPS"
    )
    assert set(result["supporting_decision_ids"]) == {d["decision_id"] for d in cases.decisions}
    assert result["quality_provenance"] == "DEMONSTRATION_ONLY"
    assert result["authority_reference"] == "NOT_DEFINED" and result["rules_used"] == []
    repeated = recommendation(client, query)
    assert repeated == result
    with Session(client.app.state.engine) as session:
        assert business_hash(session) == before
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "RECOMMENDATION_EVALUATED")
            )
            == 1
        )
        event = session.get(AuditEvent, UUID(result["audit_reference"]))
        assert "Проверен исходный документ" not in str(event.payload)
        assert len(event.payload["basis"]["evidence"]) == 5


def test_begin_review_refresh_acceptance_persists_provenance_and_original_idempotent_receipt(
    client,
):
    cases = Cases(client)
    query = cases.prepared()
    old = recommendation(client, query)
    review = begin(client, query)
    body = selection(review)
    body["recommendation_reference"] = old["audit_reference"]
    save(client, query, body, expected=409)
    fresh = recommendation(client, query)
    assert fresh["context_fingerprint"] != old["context_fingerprint"]
    position = next(
        i
        for i, value in enumerate(review["selectable_values"])
        if value["source_id"] == fresh["recommended_source_id"]
    )
    body = {**selection(review, position), "recommendation_reference": fresh["audit_reference"]}
    result = save(client, query, body)
    assert result["decision"]["context_snapshot"]["recommendation"]["relationship"] == "MATCHED"
    assert save(client, query, body, expected=200)["decision_id"] == result["decision_id"]
    assert recommendation(client, query)["reason_code"] == "CURRENT_CASE_NOT_ELIGIBLE"


@pytest.mark.parametrize("count", [0, 1, 4])
def test_insufficient_independent_history_is_first_class_abstention(client, count):
    cases = Cases(client)
    query = cases.prepared(count)
    result = recommendation(client, query)
    assert result["status"] == "ABSTAINED" and result["recommended_action"] is None
    assert result["confidence"] is None
    if count:
        assert result["reason_code"] == "INSUFFICIENT_INDEPENDENT_EVIDENCE"
        assert len(result["evidence"]) == count


def test_real_contradiction_vetoes_five_to_one_and_manual_override_still_works(client):
    cases = Cases(client)
    query = cases.prepared()
    opposed = cases.confirm(cases.case(), source=1)
    index(cases.settings)
    result = recommendation(client, query)
    assert result["reason_code"] == "CONTRADICTORY_PRECEDENTS", result
    assert opposed["decision_id"] in result["conflicting_evidence"]
    assert result["confidence"] is None and result["recommended_value_id"] is None
    assert save(client, query, selection(begin(client, query)))["conflict_status"] == "RESOLVED"


def test_real_reimports_same_files_with_new_matching_runs_are_not_independent(client):
    cases = Cases(client)
    first = cases.case(0)
    cases.confirm(first)
    # New matching execution of identical raw imports creates new Conflicts, not new evidence.
    for _ in range(4):
        case = cases.case(0)
        cases.confirm(case)
    query = cases.case(1)
    index(cases.settings)
    similar(client, query)
    result = recommendation(client, query)
    assert result["reason_code"] == "INSUFFICIENT_INDEPENDENT_EVIDENCE", result
    assert result["evidence_summary"]["independent_groups"] == 1


@pytest.mark.parametrize("role", ["VIEWER", "REVIEWER", "DATA_OWNER", "ADMIN", "NO_ROLES"])
def test_matrix_read_scope_revocation_and_opaque_missing_objects(client, role_tokens, role):
    cases = Cases(client)
    query = cases.case()
    client.cookies.set(COOKIE_NAME, role_tokens[role])
    recommendation(client, query, expected=403 if role == "NO_ROLES" else 200)
    if role == "NO_ROLES":
        return
    with Session(client.app.state.engine) as session:
        user = session.scalar(select(User).where(User.login == role.lower()))
        user.data_domains = []
        session.commit()
    denied = recommendation(client, query, expected=404)
    missing = recommendation(client, uuid4(), expected=404)
    assert denied == missing and "supporting_decision_ids" not in denied


@pytest.mark.parametrize("change", ["absent", "ambiguous", "wrong_type", "new_version"])
def test_source_correspondence_never_guesses_by_a_b_name_or_type(client, change):
    cases = Cases(client)
    query = cases.prepared()
    first = recommendation(client, query)
    mapping = deepcopy(cases.settings.recommendation_source_map)
    if change == "absent":
        cases.settings.recommendation_source_map = {}
    elif change == "ambiguous":
        mapping["sources"][1]["role"] = mapping["sources"][0]["role"]
        cases.settings.recommendation_source_map = mapping
    elif change == "wrong_type":
        mapping["sources"][0]["source_type"] = "ONE_C"
        cases.settings.recommendation_source_map = mapping
    else:
        mapping["version"] = "explicit-new-version"
        cases.settings.recommendation_source_map = mapping
    result = recommendation(client, query)
    if change == "new_version":
        assert result["context_fingerprint"] != first["context_fingerprint"]
    else:
        assert result["status"] == "ABSTAINED" and result["recommended_source_id"] is None


def test_production_refuses_positive_synthetic_recommendation_even_with_flags(client):
    cases = Cases(client)
    query = cases.prepared()
    cases.settings.deployment_mode = "production"
    result = recommendation(client, query)
    assert result["status"] == "UNAVAILABLE" and result["confidence"] is None
    assert (
        result["supporting_decision_ids"] == [] and result["quality_provenance"] == "NOT_AVAILABLE"
    )
    assert save(client, query, selection(begin(client, query)))["conflict_status"] == "RESOLVED"


def test_missing_query_cache_never_runs_provider_or_enqueues_from_recommendation_get(client):
    from unittest.mock import patch

    cases = Cases(client)
    query = cases.case()
    index(cases.settings)
    with (
        patch("app.similarity.jobs.request_query", side_effect=AssertionError("no GET job")),
        patch(
            "app.similarity.provider.TestProvider.embed",
            side_effect=AssertionError("no HTTP embedding"),
        ),
    ):
        result = recommendation(client, query)
    assert result["reason_code"] == "QUERY_CONTEXT_PENDING"


@pytest.mark.parametrize(
    "query", ["threshold=0", "limit=100", "policy=approved", "confidence=1", "source_id=other"]
)
def test_client_cannot_override_policy_or_source_mapping(client, query):
    cases = Cases(client)
    identifier = cases.case()
    response = client.get(f"/api/v1/conflicts/{identifier}/recommendation?{query}")
    assert response.status_code == 422


def test_exact_committed_reference_retry_does_not_require_redis_or_new_evaluation(client):
    from unittest.mock import patch

    cases = Cases(client)
    query = cases.prepared()
    review = begin(client, query)
    rec = recommendation(client, query)
    position = next(
        i
        for i, value in enumerate(review["selectable_values"])
        if value["value_id"] == rec["recommended_value_id"]
    )
    body = {**selection(review, position), "recommendation_reference": rec["audit_reference"]}
    committed = save(client, query, body)
    with (
        patch("app.decisions.routes.read_budget", side_effect=AssertionError("no new search")),
        patch("app.recommendations.audit.evaluate", side_effect=AssertionError("no recompute")),
    ):
        assert save(client, query, body, expected=200)["decision_id"] == committed["decision_id"]


@pytest.mark.parametrize(
    "field", ["file_hash", "raw_record_id", "normalization_origins", "authority"]
)
def test_current_context_invalid_lineage_or_unconfigured_authority_fails_closed(client, field):
    from unittest.mock import patch

    from app.recommendations.service import historical_context

    cases = Cases(client)
    query = cases.prepared()

    def corrupted(*args, **kwargs):
        frozen = deepcopy(historical_context(*args, **kwargs))
        if field == "normalization_origins":
            frozen[field] = []
        elif field == "authority":
            frozen[field] = {"active": True, "source_id": "invented"}
        else:
            frozen["conflict"]["values_snapshot"][0][field] = (
                "f" * 64 if field == "file_hash" else str(uuid4())
            )
        return frozen

    with patch("app.recommendations.service.historical_context", side_effect=corrupted):
        result = recommendation(client, query)
    assert result["status"] != "RECOMMENDED"
    assert result["recommended_action"] is None and result["confidence"] is None


@pytest.mark.parametrize("field", ["basis", "generated_at"])
def test_corrupt_persisted_audit_receipt_is_sanitized_and_never_used(client, field):
    cases = Cases(client)
    query = cases.prepared()
    review = begin(client, query)
    rec = recommendation(client, query)
    with Session(client.app.state.engine) as session:
        event = session.get(AuditEvent, UUID(rec["audit_reference"]))
        payload = deepcopy(event.payload)
        payload[field] = {"corrupt": True} if field == "basis" else "not-a-date"
        # Deliberate storage corruption only in this disposable fixture schema.
        session.execute(text("ALTER TABLE audit_events DISABLE TRIGGER audit_append_only"))
        event.payload = payload
        session.flush()
        session.execute(text("ALTER TABLE audit_events ENABLE TRIGGER audit_append_only"))
        session.commit()
    failed = recommendation(client, query, expected=503)
    assert "not-a-date" not in str(failed) and "corrupt" not in str(failed)
    position = next(
        i
        for i, value in enumerate(review["selectable_values"])
        if value["value_id"] == rec["recommended_value_id"]
    )
    save(
        client,
        query,
        {**selection(review, position), "recommendation_reference": rec["audit_reference"]},
        expected=503,
    )
    assert context(client, query)["conflict_status"] == "IN_REVIEW"


def test_total_monotonic_budget_applies_to_every_statement_and_releases_gate(client):
    import time

    from sqlalchemy.exc import DBAPIError

    from app.common.basis_lock import Budget, basis_lock

    engine = client.app.state.engine
    started = time.monotonic()
    with Session(engine) as session:
        budget = Budget(deadline=started + 0.35)
        basis_lock(session, exclusive=True, budget=budget)
        session.execute(text("SELECT pg_sleep(0.20)"))
        with pytest.raises(DBAPIError):
            session.execute(text("SELECT pg_sleep(0.30)"))
        session.rollback()
    assert time.monotonic() - started < 0.65
    with Session(engine) as session:
        basis_lock(session)
        assert session.scalar(text("SELECT current_setting('statement_timeout')")) == "0"


def test_unseen_twenty_first_precedent_is_not_silently_ignored(client):
    cases = Cases(client)
    query = cases.prepared(21)
    result = recommendation(client, query)
    assert result["reason_code"] == "EVIDENCE_WINDOW_EXCEEDED", result
    assert result["supporting_decision_ids"] == [] and result["confidence"] is None


def test_manual_historical_correction_cannot_be_copied_to_another_case(client):
    cases = Cases(client)
    query = cases.prepared()
    cases.confirm(
        cases.case(),
        decision_type="ENTER_VALUE",
        selected_source_id=None,
        selected_value_id=None,
        corrected_value="12.6",
        corrected_unit="kg",
    )
    index(cases.settings)
    result = recommendation(client, query)
    assert result["reason_code"] == "UNSUPPORTED_HISTORICAL_ACTION", result
    assert result["recommended_value"] is None


def test_rate_budget_is_shared_with_existing_similarity_get(client):
    cases = Cases(client)
    query = cases.case()
    cases.settings.similarity_reads_per_minute = 2
    recommendation(client, query)
    assert client.get(f"/api/v1/conflicts/{query}/similar-decisions").status_code == 200
    recommendation(client, query, expected=429)


def test_two_real_reviewers_have_one_atomic_decision_and_one_stale_response(client, role_tokens):
    from concurrent.futures import ThreadPoolExecutor

    cases = Cases(client)
    query = cases.prepared()
    review = begin(client, query)
    owner_rec = recommendation(client, query)
    with TestClient(
        create_app(settings=cases.settings), base_url="https://localhost:8443"
    ) as other:
        other.cookies.set(COOKIE_NAME, role_tokens["REVIEWER"])
        reviewer_rec = recommendation(other, query)
        position = next(
            i
            for i, value in enumerate(review["selectable_values"])
            if value["value_id"] == owner_rec["recommended_value_id"]
        )
        owner = {
            **selection(review, position),
            "recommendation_reference": owner_rec["audit_reference"],
        }
        reviewer = {
            **selection(review, position),
            "recommendation_reference": reviewer_rec["audit_reference"],
        }

        def submit(pair):
            caller, payload = pair
            return caller.post(f"/api/v1/conflicts/{query}/decisions", headers=ORIGIN, json=payload)

        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(submit, [(client, owner), (other, reviewer)]))
        assert sorted(r.status_code for r in responses) == [201, 409], [r.text for r in responses]
    assert len(client.get(f"/api/v1/conflicts/{query}/decisions").json()) == 1


def test_reopen_waits_for_atomic_reference_validation_and_commit(client, role_tokens):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event
    from unittest.mock import patch

    from app.decisions.routes import gated_actor
    from app.recommendations.audit import evaluate

    cases = Cases(client)
    query = cases.prepared()
    review = begin(client, query)
    rec = recommendation(client, query)
    position = next(
        i
        for i, value in enumerate(review["selectable_values"])
        if value["value_id"] == rec["recommended_value_id"]
    )
    payload = {**selection(review, position), "recommendation_reference": rec["audit_reference"]}
    past = cases.cases[0]
    old_review = context(client, past)
    evaluated, release, writer_entered = Event(), Event(), Event()

    def barrier(*args, **kwargs):
        result = evaluate(*args, **kwargs)
        evaluated.set()
        assert release.wait(1)
        return result

    def gated(request, *args, **kwargs):
        if str(request.path_params.get("conflict_id")) == past:
            writer_entered.set()
        return gated_actor(request, *args, **kwargs)

    with TestClient(
        create_app(settings=cases.settings), base_url="https://localhost:8443"
    ) as other:
        other.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
        with (
            patch("app.recommendations.audit.evaluate", side_effect=barrier),
            patch("app.decisions.routes.gated_actor", side_effect=gated),
            ThreadPoolExecutor(2) as pool,
        ):
            save_future = pool.submit(
                client.post, f"/api/v1/conflicts/{query}/decisions", headers=ORIGIN, json=payload
            )
            assert evaluated.wait(1)
            reopen = pool.submit(
                other.post,
                f"/api/v1/conflicts/{past}/review",
                headers=ORIGIN,
                json={
                    "context_version": old_review["context_version"],
                    "supersedes_decision_id": old_review["current_decision"]["id"],
                },
            )
            try:
                assert writer_entered.wait(0.5)
                with pytest.raises(TimeoutError):
                    reopen.result(timeout=0.1)
            finally:
                release.set()
            assert save_future.result().status_code == 201
            assert reopen.result().status_code == 200


def test_scope_revoked_after_preflight_is_rechecked_from_fresh_orm_under_gate(client, role_tokens):
    from unittest.mock import patch

    from app.decisions.routes import gated_actor

    cases = Cases(client)
    query = cases.prepared()
    review = begin(client, query)
    rec = recommendation(client, query)
    payload = {**selection(review), "recommendation_reference": rec["audit_reference"]}
    with Session(client.app.state.engine) as session:
        actor_id = str(session.scalar(select(User.id).where(User.login == "data_owner")))
    with TestClient(
        create_app(settings=cases.settings), base_url="https://localhost:8443"
    ) as admin:
        admin.cookies.set(COOKIE_NAME, role_tokens["ADMIN"])

        def revoke(*args, **kwargs):
            response = admin.put(
                f"/api/v1/users/{actor_id}/data-scope", headers=ORIGIN, json={"data_domains": []}
            )
            assert response.status_code == 200, response.text
            return gated_actor(*args, **kwargs)

        with patch("app.decisions.routes.gated_actor", side_effect=revoke):
            save(client, query, payload, expected=404)
    with Session(client.app.state.engine) as session:
        from app.decisions.models import Decision

        assert (
            session.scalar(
                select(func.count())
                .select_from(Decision)
                .where(Decision.conflict_id == UUID(query))
            )
            == 0
        )


def test_retrieval_activation_invalidates_reference_but_manual_save_remains_independent(client):
    cases = Cases(client)
    query = cases.prepared()
    review = begin(client, query)
    rec = recommendation(client, query)
    index(cases.settings, revision="test-v2")
    body = {**selection(review), "recommendation_reference": rec["audit_reference"]}
    save(client, query, body, expected=409)
    del body["recommendation_reference"]
    assert save(client, query, body)["conflict_status"] == "RESOLVED"
