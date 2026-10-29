"""Scope-first exact pgvector search, live eligibility and complete-coverage checks."""

from collections.abc import Iterable
from typing import Any
from typing import cast as typed_cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Float, Select, cast, exists, func, literal, literal_column, select, text
from sqlalchemy import case as sql_case
from sqlalchemy.orm import Session, defer

from app.ai import baseline
from app.ai.identity import expected_model_info
from app.auth.models import AuditEvent, User
from app.common.config import Settings
from app.conflicts.models import Conflict
from app.decisions.models import Decision
from app.decisions.service import digest, historical_context
from app.similarity.context import COMPATIBILITY, context, explain, fingerprint
from app.similarity.models import (
    DecisionEmbedding,
    IndexItem,
    IndexRun,
    QueryEmbedding,
    RetrievalState,
    RetrievalVersion,
    Vector,
)
from app.similarity.provider import (
    DIMENSIONS,
    MODEL,
    PREPROCESSING,
    REVISIONS,
    SCHEMA,
    THRESHOLD,
    ProviderError,
    permitted,
    provider,
    revision_name,
)


def configuration(revision: str = "test-v1") -> dict[str, Any]:
    if revision == "qwen-demo-v1":
        return {
            "provider": "qwen-local-demo",
            "model_id": baseline.EMBEDDING_MODEL,
            "revision": baseline.EMBEDDING_REVISION,
            "artifact_sha256": baseline.EMBEDDING_SHA256,
            "artifact_lock_sha256": baseline.ARTIFACT_LOCK_SHA256,
            "dimensions": DIMENSIONS,
            "input_schema": SCHEMA,
            "preprocessing": baseline.PREPROCESSING,
            "instruction_sha256": baseline.INSTRUCTION_SHA256,
            "input_schema_sha256": expected_model_info("embedding").input_schema_sha256,
            "output_schema_sha256": expected_model_info("embedding").output_schema_sha256,
            "runtime_versions": baseline.component_versions("embedding"),
            "eligibility": "resolved-effective-value-v1",
            "metric": "cosine",
            "threshold": THRESHOLD,
            "is_test": True,
            "quality_provenance": "LOCAL_QWEN_DEMO",
            "production_accepted": False,
            "default_limit": 5,
            "max_limit": 20,
        }
    if revision not in REVISIONS:
        raise ProviderError("UNSUPPORTED_VERSION")
    return {
        "provider": "deterministic-test",
        "model_id": MODEL,
        "revision": REVISIONS[revision],
        "dimensions": DIMENSIONS,
        "input_schema": SCHEMA,
        "preprocessing": PREPROCESSING,
        "eligibility": "resolved-effective-value-v1",
        "metric": "cosine",
        "threshold": THRESHOLD,
        "is_test": True,
        "default_limit": 5,
        "max_limit": 20,
    }


def audit(session: Session, identifier: UUID, event: str, **metadata: Any) -> None:
    session.add(
        AuditEvent(
            event_type="RETRIEVAL_" + event,
            object_type="RetrievalVersion",
            object_id=identifier,
            payload={"executor": "SERVER_OPERATOR", **metadata},
        )
    )


def start_run(
    session: Session,
    settings: Settings,
    revision: str = "test-v1",
    *,
    activate: bool = False,
    batch_size: int = 100,
) -> IndexRun:
    config = configuration(revision)
    provider(settings, config["revision"])
    maximum = 8 if revision == "qwen-demo-v1" else 500
    if not 1 <= batch_size <= maximum:
        raise ProviderError("INVALID_BATCH_SIZE")
    identifier = uuid5(NAMESPACE_URL, "forest-keeper:retrieval:" + digest(config))
    # Operator transactions serialize creation/retry; no duplicate version registration.
    session.execute(select(func.pg_advisory_xact_lock(7081201)))
    version = session.get(RetrievalVersion, identifier)
    if version is None:
        session.add(RetrievalVersion(id=identifier, config=config))
        session.flush()
        audit(session, identifier, "VERSION_REGISTERED", configuration_hash=digest(config))
    active = session.scalar(
        select(IndexRun).where(
            IndexRun.version_id == identifier, IndexRun.status.in_(["NEW", "QUEUED", "PROCESSING"])
        )
    )
    if active:
        return active
    run = IndexRun(version_id=identifier, activate=activate, batch_size=batch_size)
    session.add(run)
    session.flush()
    audit(session, identifier, "BACKFILL_CREATED", run_id=str(run.id))
    return run


def eligible(actor: User | None = None) -> Any:
    superseded = (
        select(Decision.supersedes_decision_id)
        .where(Decision.supersedes_decision_id.is_not(None))
        .correlate(None)
    )
    query = (
        select(Decision)
        .join(Conflict, Conflict.id == Decision.conflict_id)
        .where(
            Decision.decision_type.in_(["SELECT_VALUE", "ENTER_VALUE"]),
            Conflict.status == "RESOLVED",
            Conflict.current_decision_id == Decision.id,
            Decision.id.not_in(superseded),
        )
    )
    if actor is not None and "*" not in (actor.data_domains or []):
        query = query.where(Decision.domain.in_(actor.data_domains or []))
    return query


def compatible_pool(actor: User, case: Conflict, features: dict[str, Any]) -> Any:
    return eligible(actor).where(
        Decision.conflict_id != case.id,
        Decision.domain == features["domain"],
        Decision.entity_type == features["entity_type"],
        Decision.attribute_code == features["attribute_code"],
        Decision.value_kind == features["value_kind"],
        func.coalesce(Decision.unit, "") == features["unit"],
        Conflict.conflict_type == features["conflict_type"],
    )


def retrieval(
    session: Session,
    actor: User,
    case: Conflict,
    settings: Settings,
    limit: int,
    offset: int,
    *,
    prepare_query: bool = True,
    prepared_features: dict[str, Any] | None = None,
    actor_session_hash: str | None = None,
) -> dict[str, Any]:
    state = session.get(RetrievalState, 1)
    version = (
        session.get(RetrievalVersion, state.active_version_id)
        if state and state.active_version_id
        else None
    )
    result: dict[str, Any] = {
        "conflict_id": case.id,
        "state": "UNAVAILABLE",
        "reason_code": "PROVIDER_UNAVAILABLE",
        "query_context_version": SCHEMA,
        "query_context_hash": None,
        "retrieval_version": version.id if version else None,
        "embedding_model": version.config if version else None,
        "threshold": THRESHOLD,
        "total_candidates_before_filter": None,
        "total_after_filter": None,
        "total_above_threshold": None,
        "results": [],
        "insufficient_precedent": True,
        "limit": limit,
        "offset": offset,
        "known_limitations": [
            "Production provider is not accepted. Test vectors do not prove semantic quality.",
            "Exact canonical unit/attribute compatibility; no unit-family inference.",
            "Forest Codex and authoritative source are not configured.",
        ],
    }
    if not permitted(settings) or version is None:
        return result
    try:
        if version.config != configuration(revision_name(version.config["revision"])):
            raise ProviderError("UNSUPPORTED_VERSION")
        selected_provider = (
            "qwen-local-demo"
            if settings.similarity_provider == "qwen-demo"
            else "deterministic-test"
        )
        if version.config.get("provider") != selected_provider:
            raise ProviderError("UNSUPPORTED_VERSION")
        # Private same-snapshot reuse by RecommendationService; public routes
        # never accept feature/policy overrides and keep building their context.
        features = (
            prepared_features
            if prepared_features is not None
            else context(historical_context(session, case, include_review=False))
        )
        if settings.similarity_provider == "test" and not features["synthetic"]:
            raise ProviderError("SYNTHETIC_ONLY")
    except (ProviderError, StopIteration, KeyError, TypeError) as error:
        result["reason_code"] = (
            str(error) if isinstance(error, ProviderError) else "UNSUPPORTED_VERSION"
        )
        return result
    if settings.similarity_provider == "qwen-demo":
        result["known_limitations"][0] = (
            "Actual local Qwen vectors in development mode; production semantic quality "
            "is not accepted. Not interchangeable with synthetic-test vectors."
        )
    feature_hash = fingerprint(features)
    result["query_context_hash"] = feature_hash
    result["query_context"] = features
    query_cache = session.get(QueryEmbedding, (version.id, feature_hash))
    if query_cache is None:
        if not prepare_query:
            result.update(state="INDEXING", reason_code="QUERY_CONTEXT_PENDING")
            return result
        from app.similarity.jobs import request_query

        try:
            request_query(
                case.id,
                version.id,
                feature_hash,
                settings,
                actor_id=str(actor.id),
                auth_session_hash=actor_session_hash,
            )
        except ProviderError as error:
            result["reason_code"] = str(error)
            return result
        except Exception:
            result["reason_code"] = "QUERY_PREPARATION_UNAVAILABLE"
            return result
        result.update(state="INDEXING", reason_code="QUERY_CONTEXT_PENDING")
        return result
    from app.similarity.provider import vector_hash

    if (
        query_cache.features != features
        or vector_hash(query_cache.embedding) != query_cache.vector_hash
    ):
        result["reason_code"] = "QUERY_INTEGRITY_FAILURE"
        return result
    query_vector = query_cache.embedding
    # Materialize eligibility once. Counts, coverage, invariant checks and ranking
    # reuse this narrow set instead of repeatedly joining the immutable Registry.
    scoped = (
        eligible(actor)
        .where(Decision.conflict_id != case.id)
        .with_only_columns(
            Decision.id,
            Decision.decided_at,
            Decision.domain,
            Decision.entity_type,
            Decision.attribute_code,
            Conflict.conflict_type,
            Decision.value_kind,
            func.coalesce(Decision.unit, "").label("unit"),
        )
        .cte("scoped_precedents")
        .prefix_with("MATERIALIZED")
    )
    compatible = (
        select(scoped)
        .where(*[scoped.c[key] == features[key] for key in COMPATIBILITY])
        .cte("compatible_precedents")
        .prefix_with("MATERIALIZED")
    )
    integrity_predicate = (
        DecisionEmbedding.vector_hash.is_distinct_from(
            func.encode(
                func.sha256(func.public.vector_send(DecisionEmbedding.embedding)),
                literal_column("'hex'"),
            )
        )
        | DecisionEmbedding.feature_hash.is_distinct_from(DecisionEmbedding.input_hash)
        | (DecisionEmbedding.dimensions != literal_column("1024"))
    )
    corrupt_ids = (
        select(DecisionEmbedding.decision_id)
        .where(
            DecisionEmbedding.version_id == version.id,
            integrity_predicate,
        )
        .order_by(DecisionEmbedding.version_id, DecisionEmbedding.decision_id)
        .cte("corrupt_artifacts")
        .prefix_with("MATERIALIZED")
    )
    # Newly written heap pages can make the planner price an empty partial
    # integrity index as if it required thousands of heap fetches. Isolate this
    # exact scoped check and prefer its index, then restore ordinary planning
    # before ranking. Errors roll back these transaction-local settings.
    previous_seqscan = session.scalar(text("SELECT current_setting('enable_seqscan')"))
    session.execute(text("SET LOCAL enable_seqscan=off"))
    corrupt_vector = session.scalar(
        select(
            select(func.count())
            .select_from(corrupt_ids)
            .where(
                corrupt_ids.c.decision_id.in_(
                    compatible_pool(actor, case, features).with_only_columns(Decision.id)
                )
            )
            .scalar_subquery()
            > 0
        ).prefix_with("/* scoped_retrieval_integrity */")
    )
    session.execute(
        text("SELECT set_config('enable_seqscan', :value, true)"), {"value": previous_seqscan}
    )
    if not isinstance(corrupt_vector, bool):
        result["reason_code"] = "INDEX_INTEGRITY_FAILURE"
        return result
    distance = cast(
        DecisionEmbedding.embedding.op("OPERATOR(public.<=>)")(
            cast(literal(query_vector, type_=Vector()), Vector())
        ),
        Float,
    )
    # One metadata/vector join supplies both coverage and scores. Materialize only
    # narrow derived fields, never full historical JSON or the vectors themselves.
    prepared = (
        select(
            compatible.c.id.label("decision_id"),
            compatible.c.decided_at,
            DecisionEmbedding.id.label("artifact_id"),
            distance.label("distance"),
            sql_case(
                (DecisionEmbedding.id.is_not(None), False),
                else_=~exists(
                    select(IndexItem.decision_id)
                    .where(
                        IndexItem.version_id == version.id,
                        IndexItem.decision_id == compatible.c.id,
                        IndexItem.reason != "INDEXED",
                    )
                    .correlate(compatible)
                ),
            ).label("missing"),
            (
                (DecisionEmbedding.domain != features["domain"])
                | (DecisionEmbedding.entity_type != features["entity_type"])
                | (DecisionEmbedding.attribute_code != features["attribute_code"])
                | (DecisionEmbedding.conflict_type != features["conflict_type"])
                | (DecisionEmbedding.value_kind != features["value_kind"])
                | (DecisionEmbedding.unit != features["unit"])
            ).label("corrupt_features"),
        )
        .select_from(compatible)
        .outerjoin(
            DecisionEmbedding,
            (DecisionEmbedding.version_id == version.id)
            & (DecisionEmbedding.decision_id == compatible.c.id),
        )
        .cte("prepared_precedents")
        .prefix_with("MATERIALIZED")
    )
    aggregate = (
        select(
            func.count().label("after_count"),
            func.coalesce(func.bool_or(prepared.c.missing), False).label("missing"),
            func.coalesce(func.bool_or(prepared.c.corrupt_features), False).label(
                "corrupt_features"
            ),
        )
        .select_from(prepared)
        .subquery()
    )
    diagnostics = (
        select(
            select(func.count()).select_from(scoped).scalar_subquery().label("before_count"),
            aggregate.c.after_count,
            aggregate.c.missing,
            literal(corrupt_vector).label("corrupt_vector"),
            aggregate.c.corrupt_features,
        )
        .select_from(aggregate)
        .cte("retrieval_diagnostics")
        .prefix_with("MATERIALIZED")
    )
    scored = (
        select(
            prepared.c.artifact_id,
            prepared.c.decision_id,
            prepared.c.decided_at,
            prepared.c.distance,
        )
        .join(diagnostics, literal(True))
        .where(
            ~diagnostics.c.missing, ~diagnostics.c.corrupt_vector, ~diagnostics.c.corrupt_features
        )
        .cte("scored_precedents")
        .prefix_with("MATERIALIZED")
    )
    qualified = select(scored).where(scored.c.distance <= 1 - version.config["threshold"])
    total = select(func.count().label("count")).select_from(qualified.subquery()).subquery()
    page = (
        qualified.order_by(scored.c.distance, scored.c.decided_at.desc(), scored.c.decision_id)
        .limit(limit)
        .offset(offset)
        .cte("precedent_page")
        .prefix_with("MATERIALIZED")
    )
    query: Select[Any] = (
        select(DecisionEmbedding, Decision, page.c.distance, total.c.count, *diagnostics.c)
        .select_from(total)
        .join(diagnostics, literal(True))
        .outerjoin(page, literal(True))
        .outerjoin(DecisionEmbedding, DecisionEmbedding.id == page.c.artifact_id)
        .outerjoin(Decision, Decision.id == page.c.decision_id)
        .options(defer(DecisionEmbedding.embedding))
        .order_by(page.c.distance, page.c.decided_at.desc(), page.c.decision_id)
    )
    # Cross-table effective-head correlation is underestimated by PostgreSQL17.
    # Prefer hash joins for this set operation; avoid JIT startup on its tiny
    # singleton cross joins. A receipt check may reuse this transaction for a
    # Decision write, so scope the plan hints to the bounded ranking query itself.
    planner = session.execute(
        text("SELECT current_setting('enable_nestloop'), current_setting('jit')")
    ).one()
    session.execute(text("SET LOCAL enable_nestloop=off; SET LOCAL jit=off"))
    rows = typed_cast(
        Iterable[
            tuple[
                DecisionEmbedding | None,
                Decision | None,
                float | None,
                int,
                int,
                int,
                bool,
                bool,
                bool,
            ]
        ],
        session.execute(query).all(),
    )
    # Fetch before restoration. SQL errors abort the caller's transaction; its
    # required rollback restores SET LOCAL state, without issuing SQL after error.
    session.execute(
        text("SELECT set_config('enable_nestloop', :nested, true), set_config('jit', :jit, true)"),
        {"nested": planner[0], "jit": planner[1]},
    )
    for (
        artifact,
        decision,
        dist,
        above_count,
        before_count,
        after_count,
        missing,
        corrupt_vector,
        corrupt_features,
    ) in rows:
        result.update(
            total_candidates_before_filter=before_count,
            total_after_filter=after_count,
            total_above_threshold=above_count,
            state="NO_PRECEDENT",
            reason_code="NO_COMPATIBLE_PRECEDENT",
        )
        if not before_count:
            result["reason_code"] = (
                "NO_HISTORY" if "*" in (actor.data_domains or []) else "NO_ACCESSIBLE_PRECEDENT"
            )
            return result
        if not after_count:
            return result
        if missing:
            result.update(
                state="INDEXING", reason_code="INDEX_NOT_READY", total_above_threshold=None
            )
            return result
        if corrupt_vector or corrupt_features:
            result.update(
                state="UNAVAILABLE",
                reason_code="INDEX_INTEGRITY_FAILURE",
                total_above_threshold=None,
            )
            return result
        if artifact is None or decision is None or dist is None:
            continue
        try:
            past = context(decision.context_snapshot, decision)
            past_hash = fingerprint(past)
            if (
                past_hash != artifact.feature_hash
                or past != artifact.features
                or artifact.input_hash != past_hash
            ):
                raise ProviderError("INDEX_INTEGRITY_FAILURE")
        except ProviderError:
            result.update(state="UNAVAILABLE", reason_code="INDEX_INTEGRITY_FAILURE", results=[])
            return result
        matched, mismatched = explain(features, past)
        result["results"].append(
            {
                "decision_id": decision.id,
                "similarity": round(max(0, min(1, 1 - dist)), 6),
                "matched_features": matched,
                "mismatched_features": mismatched,
                "actor": {"id": decision.user_id, "display_name": decision.actor_display_name},
                "decided_at": decision.decided_at,
                "domain": decision.domain,
                "entity_type": decision.entity_type,
                "attribute_code": decision.attribute_code,
                "outcome": decision.decision_type,
                "selected_value": decision.selected_value,
                "unit": decision.unit,
                "conflict_id": decision.conflict_id,
                "reason": decision.reason,
                "decision_status": "ACTIVE",
                "decision_url": f"/api/v1/decisions/{decision.id}",
                "evidence_summary": past,
                "explanation": "Compatible structure; cosine score from versioned test features.",
            }
        )
    result.update(
        state="READY" if result["total_above_threshold"] else "NO_PRECEDENT",
        reason_code="MATCHES" if result["total_above_threshold"] else "BELOW_THRESHOLD",
        insufficient_precedent=not bool(result["total_above_threshold"]),
    )
    return result
