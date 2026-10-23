"""Real persisted import→review→pgvector path and security/recovery negatives."""

import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import COOKIE_NAME
from app.auth.models import User
from app.common.database import make_engine
from app.decisions.models import Decision
from app.main import create_app
from app.similarity.jobs import execute_index
from app.similarity.models import DecisionEmbedding, IndexItem, IndexRun
from app.similarity.service import start_run
from tests.test_auth import password as password
from tests.test_auth import role_tokens as role_tokens
from tests.test_decisions_integration import begin, context, real_case, save, selection
from tests.test_matching_integration import auth_env as auth_env

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("FK_TEST_INTEGRATION") != "1", reason="owned isolated DB opt-in"),
]


def enabled(settings):
    return settings.model_copy(
        update={
            "deployment_mode": "test",
            "similarity_provider": "test",
            "similarity_allow_test_provider": True,
        }
    )


@pytest.fixture
def client(auth_env, role_tokens):
    with TestClient(
        create_app(settings=enabled(auth_env)), base_url="https://localhost:8443"
    ) as value:
        value.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
        yield value


def index(settings, revision="test-v1", activate=True, batch_size=100, max_batches=None):
    settings = enabled(settings)
    engine = make_engine(settings)
    try:
        with Session(engine) as session:
            run = start_run(session, settings, revision, activate=activate, batch_size=batch_size)
            run.status = "QUEUED"
            session.commit()
            identifier = run.id
        execute_index(identifier, settings, max_batches=max_batches)
        return identifier
    finally:
        engine.dispose()


def similar(client, identifier, suffix=""):
    response = client.get(f"/api/v1/conflicts/{identifier}/similar-decisions{suffix}")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    if result["reason_code"] == "QUERY_CONTEXT_PENDING":
        from app.similarity.jobs import prepare_query

        prepare_query(
            identifier,
            result["retrieval_version"],
            result["query_context_hash"],
            client.app.state.settings,
        )
        return similar(client, identifier, suffix)
    return result


def test_real_path_new_case_finds_actual_decision_and_get_never_changes_facts(client, auth_env):
    first = real_case(client, auth_env)
    decision = save(client, first, selection(begin(client, first)))
    second = real_case(client, auth_env)
    assert similar(client, second)["state"] == "UNAVAILABLE"
    before = context(client, second)
    run_id = index(auth_env)
    result = similar(client, second)
    assert result["state"] == "READY", result
    assert decision["decision_id"] in [r["decision_id"] for r in result["results"]]
    found = next(r for r in result["results"] if r["decision_id"] == decision["decision_id"])
    assert found["similarity"] >= 0.85 and "unit" in found["matched_features"]
    assert found["actor"]["display_name"] and found["reason"]
    assert client.get(found["decision_url"]).status_code == 200
    assert context(client, second) == before
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            assert session.get(IndexRun, run_id).status == "COMPLETED"
            count = session.scalar(select(func.count()).select_from(DecisionEmbedding))
        index(auth_env)
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(DecisionEmbedding)) == count
    finally:
        engine.dispose()


def test_superseded_and_reopened_head_are_excluded_before_ranking(client, auth_env):
    first = real_case(client, auth_env)
    initial = save(client, first, selection(begin(client, first)))
    query = real_case(client, auth_env)
    index(auth_env)
    assert initial["decision_id"] in [r["decision_id"] for r in similar(client, query)["results"]]
    review = begin(client, first, initial["decision_id"])
    assert initial["decision_id"] not in [
        r["decision_id"] for r in similar(client, query)["results"]
    ]
    updated = save(client, first, selection(review))
    assert similar(client, query)["state"] == "INDEXING"
    index(auth_env)
    result = similar(client, query)
    assert updated["decision_id"] in [r["decision_id"] for r in result["results"]]
    assert initial["decision_id"] not in [r["decision_id"] for r in result["results"]]
    assert (
        client.get(f"/api/v1/decisions/{initial['decision_id']}").json()["status"] == "SUPERSEDED"
    )


@pytest.mark.parametrize("role", ["VIEWER", "REVIEWER", "DATA_OWNER", "ADMIN"])
def test_read_permissions_are_matrix_based_and_scope_revocation_is_immediate(
    client, auth_env, role_tokens, role
):
    query = real_case(client, auth_env)
    index(auth_env)
    client.cookies.set(COOKIE_NAME, role_tokens[role])
    assert similar(client, query)["state"] == "READY"
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            user = session.scalar(select(User).where(User.login == role.lower()))
            user.data_domains = []
            session.commit()
        response = client.get(f"/api/v1/conflicts/{query}/similar-decisions")
        assert response.status_code == 404 and "results" not in response.json()
    finally:
        with Session(engine) as session:
            session.scalar(select(User).where(User.login == role.lower())).data_domains = ["*"]
            session.commit()
        engine.dispose()


@pytest.mark.parametrize(
    "query",
    [
        "limit=21",
        "limit=-1",
        "offset=101",
        "threshold=0",
        "limit=NaN",
        "embedding=[1,2]",
        "limit=1;DROP TABLE decisions",
    ],
)
def test_query_abuse_is_rejected_without_vector_input(client, auth_env, query):
    case = real_case(client, auth_env)
    assert client.get(f"/api/v1/conflicts/{case}/similar-decisions?{query}").status_code == 422


def test_checkpoint_restart_duplicate_delivery_and_dual_version_activation(client, auth_env):
    case = real_case(client, auth_env)
    save(client, case, selection(begin(client, case)))
    query = real_case(client, auth_env)
    engine = make_engine(auth_env)
    try:
        old = similar(client, query)["retrieval_version"]
        run = index(auth_env, "test-v2", activate=False, batch_size=1, max_batches=1)
        with Session(engine) as session:
            assert session.get(IndexRun, run).status == "PROCESSING"
            assert session.get(IndexRun, run).processed == 1
        assert similar(client, query)["retrieval_version"] == old
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda _: execute_index(run, enabled(auth_env)), range(2)))
        with Session(engine) as session:
            assert session.get(IndexRun, run).status == "COMPLETED"
            version = session.get(IndexRun, run).version_id
            from app.similarity.jobs import activate_version

            activate_version(session, version)
            session.commit()
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(DecisionEmbedding)
                    .where(DecisionEmbedding.version_id == version)
                )
                > 0
            )
            assert session.scalar(
                select(func.count()).select_from(IndexItem).where(IndexItem.version_id == version)
            ) == session.scalar(select(func.count()).select_from(Decision))
        assert similar(client, query)["retrieval_version"] != old
        assert similar(client, query)["state"] == "READY"
    finally:
        engine.dispose()


def test_optional_provider_failure_and_database_failure_do_not_mutate_registry(
    client, auth_env, role_tokens
):
    case = real_case(client, auth_env)
    with TestClient(create_app(settings=auth_env), base_url="https://localhost:8443") as production:
        production.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
        assert similar(production, case)["state"] == "UNAVAILABLE"
        assert production.get("/api/v1/decisions").status_code == 200
        assert context(production, case)["conflict_status"] == "OPEN"
    with patch(
        "app.similarity.routes.retrieval",
        side_effect=__import__("sqlalchemy").exc.SQLAlchemyError("sensitive payload"),
    ):
        response = client.get(f"/api/v1/conflicts/{case}/similar-decisions")
        assert response.status_code == 503 and "sensitive" not in response.text


def test_vector_db_dimension_and_immutability_guards(client, auth_env):
    from sqlalchemy.exc import DBAPIError

    index(auth_env)
    engine = make_engine(auth_env)
    try:
        for sql in [
            "UPDATE decision_embeddings SET input_hash='tampered'",
            "DELETE FROM decision_embeddings",
        ]:
            with pytest.raises(DBAPIError), engine.begin() as connection:
                connection.execute(text(sql))
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(text("SELECT '[NaN]'::public.vector(1024)"))
    finally:
        engine.dispose()


def test_downgrade_with_vectors_refuses_without_losing_decision_history(client, auth_env):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.exc import DBAPIError

    index(auth_env)
    engine = make_engine(auth_env)
    with Session(engine) as session:
        before = session.scalar(select(func.count()).select_from(Decision))
        vectors = session.scalar(select(func.count()).select_from(DecisionEmbedding))
        assert vectors > 0
    with patch.dict(os.environ, {"FK_DATABASE_URL": auth_env.database_url.get_secret_value()}):
        with pytest.raises(DBAPIError, match="Preserve derived audit"):
            command.downgrade(Config("alembic.ini"), "0007_decisions")
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Decision)) == before
        assert session.scalar(select(func.count()).select_from(DecisionEmbedding)) == vectors
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == "0008_similarity"
    engine.dispose()


@pytest.mark.parametrize(
    "field,value",
    [
        ("domain", "foreign"),
        ("entity_type", "Other"),
        ("attribute_code", "other"),
        ("conflict_type", "MISSING"),
        ("value_kind", "string"),
        ("unit", "mm"),
    ],
)
def test_structural_incompatibility_is_filtered_in_sql(client, auth_env, field, value):
    from app.conflicts.models import Conflict
    from app.decisions.service import historical_context
    from app.similarity.context import context as build_context
    from app.similarity.service import compatible_pool

    case_id = real_case(client, auth_env)
    engine = make_engine(auth_env)
    with Session(engine) as session:
        case = session.get(Conflict, __import__("uuid").UUID(case_id))
        features = build_context(historical_context(session, case))
        features[field] = value
        actor = session.scalar(select(User).where(User.login == "data_owner"))
        assert (
            session.scalar(
                select(func.count()).select_from(compatible_pool(actor, case, features).subquery())
            )
            == 0
        )
    engine.dispose()


def test_unrelated_real_import_path_is_below_threshold(client, auth_env, tmp_path):
    from tests.test_conflicts_integration import DATA

    for file in ["source-a.csv", "source-b.xml"]:
        (tmp_path / file).write_text(
            (DATA / file).read_text().replace("Different Bolt", "Ceramic Plumbing Tube")
        )
    with patch("tests.test_conflicts_integration.DATA", tmp_path):
        query = real_case(client, auth_env)
    index(auth_env)
    result = similar(client, query)
    assert result["reason_code"] == "BELOW_THRESHOLD" and result["results"] == [], result


def test_snapshot_barrier_late_human_commit_never_produces_partial_ready_pool(
    client, auth_env, role_tokens
):
    from sqlalchemy import event

    query = real_case(client, auth_env)
    index(auth_env)
    baseline = similar(client, query)
    late = real_case(client, auth_env)
    body = selection(begin(client, late))
    committed = []

    def barrier(connection, cursor, statement, parameters, context, executemany):
        if (
            "ORDER BY" in statement
            and "decision_embeddings.embedding" in statement
            and not committed
        ):
            committed.append(True)
            with TestClient(
                create_app(settings=enabled(auth_env)), base_url="https://localhost:8443"
            ) as writer:
                writer.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
                saved = save(writer, late, body)
                committed.append(saved["decision_id"])

    event.listen(client.app.state.engine, "before_cursor_execute", barrier)
    try:
        result = similar(client, query)
    finally:
        event.remove(client.app.state.engine, "before_cursor_execute", barrier)
    assert len(committed) == 2
    assert (
        result["state"] == "READY"
        and result["total_after_filter"] == baseline["total_after_filter"]
    )
    assert committed[1] not in [r["decision_id"] for r in result["results"]]
    assert similar(client, query)["state"] == "INDEXING"


def test_provider_crash_rolls_back_batch_and_retry_keeps_prior_checkpoint(client, auth_env):
    from app.similarity.provider import ProviderError

    first = real_case(client, auth_env)
    save(client, first, selection(begin(client, first)))
    engine = make_engine(auth_env)
    with Session(engine) as session:
        before = session.scalar(select(func.count()).select_from(DecisionEmbedding))
    with patch(
        "app.similarity.provider.TestProvider.embed",
        side_effect=ProviderError("sensitive input must never be logged"),
    ):
        run_id = index(auth_env)
    with Session(engine) as session:
        run = session.get(IndexRun, run_id)
        assert run.status == "FAILED" and run.error_code == "INDEXING_FAILED"
        assert session.scalar(select(func.count()).select_from(DecisionEmbedding)) == before
    run_id = index(auth_env)
    with Session(engine) as session:
        assert session.get(IndexRun, run_id).status == "COMPLETED"
    engine.dispose()


def test_http_query_preparation_is_background_only_and_can_recover(client, auth_env):
    case_id = real_case(client, auth_env)
    # A fresh version has no cached query representation, even if its index is complete.
    index(auth_env, "test-v1")
    engine = make_engine(auth_env)
    from app.similarity.models import QueryEmbedding

    with Session(engine) as session:
        count_before = session.scalar(select(func.count()).select_from(QueryEmbedding))
    # Existing equal synthetic context may already be cached; use a distinct query name.
    from app.similarity.provider import TestProvider

    with patch.object(
        TestProvider, "embed", side_effect=AssertionError("embedding inside GET forbidden")
    ):
        response = client.get(f"/api/v1/conflicts/{case_id}/similar-decisions")
        assert response.status_code == 200 and response.json()["state"] in {"READY", "INDEXING"}
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(QueryEmbedding)) == count_before
    engine.dispose()


def test_limit_is_bounded_and_disabled_or_unprivileged_caller_cannot_read(
    client, auth_env, role_tokens
):
    case = real_case(client, auth_env)
    client.app.state.settings.similarity_reads_per_minute = 1
    client.app.state.settings.auth_rate_prefix += "rate-proof:"
    assert client.get(f"/api/v1/conflicts/{case}/similar-decisions").status_code == 200
    assert client.get(f"/api/v1/conflicts/{case}/similar-decisions").status_code == 429
    client.app.state.settings.similarity_reads_per_minute = 120
    client.cookies.set(COOKIE_NAME, role_tokens["NO_ROLES"])
    assert client.get(f"/api/v1/conflicts/{case}/similar-decisions").status_code == 403
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            actor = session.scalar(select(User).where(User.login == "viewer"))
            actor.status = "DISABLED"
            session.commit()
        client.cookies.set(COOKIE_NAME, role_tokens["VIEWER"])
        assert client.get(f"/api/v1/conflicts/{case}/similar-decisions").status_code == 401
    finally:
        with Session(engine) as session:
            session.scalar(select(User).where(User.login == "viewer")).status = "ACTIVE"
            session.commit()
        engine.dispose()


@pytest.mark.parametrize("outcome", ["DEFERRED", "INSUFFICIENT_DATA"])
def test_uncertain_outcomes_are_checkpointed_but_never_confirmed_precedents(
    client, auth_env, outcome
):
    case = real_case(client, auth_env)
    review = begin(client, case)
    result = save(
        client,
        case,
        {
            "context_version": review["context_version"],
            "idempotency_key": str(__import__("uuid").uuid4()),
            "decision_type": outcome,
            "reason": "Explicit uncertain test outcome",
            "confirmed": True,
        },
    )
    query = real_case(client, auth_env)
    index(auth_env)
    assert result["decision_id"] not in [
        r["decision_id"] for r in similar(client, query)["results"]
    ]
    engine = make_engine(auth_env)
    with Session(engine) as session:
        reasons = session.scalars(
            select(IndexItem.reason).where(
                IndexItem.decision_id == __import__("uuid").UUID(result["decision_id"])
            )
        ).all()
        assert reasons and set(reasons) == {"OUTCOME_OR_LIFECYCLE_EXCLUDED"}
    engine.dispose()


def test_incomplete_frozen_context_is_skipped_with_reason_without_mutating_fact(client, auth_env):
    from app.decisions.service import digest
    from tests.similarity_fixtures import expand

    case = real_case(client, auth_env)
    saved = save(client, case, selection(begin(client, case)))
    engine = make_engine(auth_env)
    with Session(engine) as session:
        seed = session.get(Decision, __import__("uuid").UUID(saved["decision_id"]))
        corrupt = expand(session, seed, 1, lambda snapshot: snapshot.pop("normalization_origins"))[
            0
        ]
        before = digest(session.get(Decision, corrupt).context_snapshot)
    index(auth_env)
    with Session(engine) as session:
        assert (
            session.scalar(
                select(IndexItem.reason).where(IndexItem.decision_id == corrupt).limit(1)
            )
            == "INCOMPLETE_CONTEXT"
        )
        assert (
            session.scalar(
                select(DecisionEmbedding.id).where(DecisionEmbedding.decision_id == corrupt)
            )
            is None
        )
        assert digest(session.get(Decision, corrupt).context_snapshot) == before
    engine.dispose()


def test_hard_corruption_below_threshold_fails_closed_before_ranking(client, auth_env):
    from sqlalchemy import update

    from app.similarity.models import RetrievalState

    case = real_case(client, auth_env)
    index(auth_env)
    assert similar(client, case)["state"] == "READY"
    engine = make_engine(auth_env)
    try:
        with Session(engine) as session:
            # Deliberately simulate storage/admin corruption only in this owned disposable schema.
            assert session.scalar(text("SELECT current_schema()")).startswith("auth_test_")
            version = session.get(RetrievalState, 1).active_version_id
            artifact = session.scalar(
                select(DecisionEmbedding).where(DecisionEmbedding.version_id == version).limit(1)
            )
            identifier, original = artifact.id, artifact.embedding
            constraint = session.scalar(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid='decision_embeddings'::regclass "
                    "AND pg_get_constraintdef(oid) LIKE '%vector_hash%'"
                )
            )
        # Names come from this schema's catalog; quote using SQLAlchemy's dialect preparer.
        quoted = engine.dialect.identifier_preparer.quote(constraint)
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE decision_embeddings DISABLE TRIGGER retrieval_vector_immutable")
            )
            connection.execute(text("ALTER TABLE decision_embeddings DROP CONSTRAINT " + quoted))
            connection.execute(
                update(DecisionEmbedding)
                .where(DecisionEmbedding.id == identifier)
                .values(embedding=[1.0] + [0.0] * 1023)
            )
        assert similar(client, case)["reason_code"] == "INDEX_INTEGRITY_FAILURE"
    finally:
        if "identifier" in locals():
            with engine.begin() as connection:
                connection.execute(
                    update(DecisionEmbedding)
                    .where(DecisionEmbedding.id == identifier)
                    .values(embedding=original)
                )
                connection.execute(
                    text(
                        "ALTER TABLE decision_embeddings ADD CONSTRAINT "
                        + quoted
                        + " CHECK(vector_hash=encode(sha256(public.vector_send(embedding)),'hex'))"
                    )
                )
                connection.execute(
                    text(
                        "ALTER TABLE decision_embeddings ENABLE TRIGGER retrieval_vector_immutable"
                    )
                )
        engine.dispose()


def test_real_statement_timeout_is_local_and_registry_remains_readable(client, auth_env):
    import time

    case = real_case(client, auth_env)

    def slow(session, *args):
        session.execute(text("SELECT pg_sleep(1.5)"))

    started = time.monotonic()
    with patch("app.similarity.routes.retrieval", slow):
        response = client.get(f"/api/v1/conflicts/{case}/similar-decisions")
    assert response.status_code == 503 and time.monotonic() - started < 1.5
    assert client.get("/api/v1/decisions").status_code == 200
    assert client.get(f"/api/v1/conflicts/{case}/review-context").status_code == 200


def test_rq_recovery_coalesces_queued_delivery_and_finishes_real_backfill(client, auth_env):
    from uuid import uuid4

    from redis import Redis
    from rq import Queue, SimpleWorker

    from app.similarity.jobs import recover_indexes

    case = real_case(client, auth_env)
    save(client, case, selection(begin(client, case)))
    settings = enabled(auth_env).model_copy(
        update={"import_queue_name": "retrieval-recovery-" + uuid4().hex}
    )
    engine = make_engine(settings)
    with Session(engine) as session:
        run = start_run(session, settings)
        session.commit()
        identifier = run.id
    with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
        queue = Queue(settings.import_queue_name, connection=redis)
        try:
            recover_indexes(settings, redis)
            recover_indexes(settings, redis)
            assert len(queue.get_job_ids()) == 1
            with patch("app.similarity.jobs.Settings", return_value=settings):
                SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
            with Session(engine) as session:
                assert session.get(IndexRun, identifier).status == "COMPLETED"
        finally:
            for job_id in [
                *queue.get_job_ids(),
                *queue.finished_job_registry.get_job_ids(),
                *queue.failed_job_registry.get_job_ids(),
            ]:
                from rq.job import Job

                job = Job.fetch_many([job_id], connection=redis)[0]
                if job:
                    job.delete()
            queue.delete(delete_jobs=True)
    engine.dispose()


def test_query_provider_failure_is_unavailable_then_bounded_retry_recovers(
    client, auth_env, role_tokens, tmp_path
):
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from redis import Redis
    from rq import Queue, SimpleWorker
    from rq.job import Job

    from app.similarity.provider import ProviderError
    from tests.test_conflicts_integration import DATA

    for file in ["source-a.csv", "source-b.xml"]:
        (tmp_path / file).write_text(
            (DATA / file).read_text().replace("Different Bolt", "Distinct Query Failure Fixture")
        )
    with patch("tests.test_conflicts_integration.DATA", tmp_path):
        case = real_case(client, auth_env)
    index(auth_env)
    settings = enabled(auth_env).model_copy(
        update={"import_queue_name": "query-failure-" + uuid4().hex}
    )
    with (
        TestClient(create_app(settings=settings), base_url="https://localhost:8443") as reader,
        Redis.from_url(settings.redis_url.get_secret_value()) as redis,
    ):
        reader.cookies.set(COOKIE_NAME, role_tokens["DATA_OWNER"])
        queue = Queue(settings.import_queue_name, connection=redis)
        path = f"/api/v1/conflicts/{case}/similar-decisions"
        try:
            assert reader.get(path).json()["reason_code"] == "QUERY_CONTEXT_PENDING"
            job_id = queue.get_job_ids()[0]
            with (
                patch("app.similarity.jobs.Settings", return_value=settings),
                patch(
                    "app.similarity.provider.TestProvider.embed",
                    side_effect=ProviderError("sensitive provider payload"),
                ),
            ):
                SimpleWorker([queue], connection=redis).work(burst=True, logging_level="CRITICAL")
            failed = reader.get(path)
            assert failed.status_code == 200 and failed.json()["state"] == "UNAVAILABLE"
            assert failed.json()["reason_code"] == "QUERY_PREPARATION_FAILED"
            assert "sensitive" not in failed.text
            job = Job.fetch(job_id, connection=redis)
            assert "sensitive" not in (job.exc_info or "")
            job.ended_at = datetime.now(UTC) - timedelta(seconds=31)
            job.save()
            assert reader.get(path).json()["reason_code"] == "QUERY_CONTEXT_PENDING"
            with patch("app.similarity.jobs.Settings", return_value=settings):
                SimpleWorker([queue], connection=redis).work(burst=True, logging_level="ERROR")
            assert reader.get(path).json()["state"] == "NO_PRECEDENT"
            assert reader.get(f"/api/v1/conflicts/{case}/review-context").status_code == 200
        finally:
            job = Job.fetch_many([job_id], connection=redis)[0] if "job_id" in locals() else None
            if job:
                job.delete()
            queue.delete(delete_jobs=True)
