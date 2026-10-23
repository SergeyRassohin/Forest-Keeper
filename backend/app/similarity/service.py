"""Scope-first exact pgvector search, live eligibility and complete-coverage checks."""

from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Float, cast, exists, func, literal, literal_column, select
from sqlalchemy.orm import Session, aliased

from app.auth.models import AuditEvent, User
from app.common.config import Settings
from app.conflicts.models import Conflict
from app.decisions.models import Decision
from app.decisions.service import digest, historical_context
from app.similarity.context import COMPATIBILITY, context, explain
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
)


def configuration(revision: str = "test-v1") -> dict[str, Any]:
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
    if not 1 <= batch_size <= 500:
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
    successor = aliased(Decision)
    query = (
        select(Decision)
        .join(Conflict, Conflict.id == Decision.conflict_id)
        .where(
            Decision.decision_type.in_(["SELECT_VALUE", "ENTER_VALUE"]),
            Conflict.status == "RESOLVED",
            Conflict.current_decision_id == Decision.id,
            ~exists(select(successor.id).where(successor.supersedes_decision_id == Decision.id)),
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
    session: Session, actor: User, case: Conflict, settings: Settings, limit: int, offset: int
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
        if version.config != configuration(
            next(k for k, v in REVISIONS.items() if v == version.config["revision"])
        ):
            raise ProviderError("UNSUPPORTED_VERSION")
        features = context(historical_context(session, case))
        if not features["synthetic"]:
            raise ProviderError("SYNTHETIC_ONLY")
    except (ProviderError, StopIteration, KeyError, TypeError) as error:
        result["reason_code"] = (
            str(error) if isinstance(error, ProviderError) else "UNSUPPORTED_VERSION"
        )
        return result
    result["query_context_hash"] = digest(features)
    result["query_context"] = features
    query_cache = session.get(QueryEmbedding, (version.id, digest(features)))
    if query_cache is None:
        from app.similarity.jobs import request_query

        try:
            request_query(case.id, version.id, digest(features), settings)
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
    before = eligible(actor).where(Decision.conflict_id != case.id).subquery()
    pool = compatible_pool(actor, case, features)
    pool_ids = pool.with_only_columns(Decision.id).subquery()
    result["total_candidates_before_filter"] = session.scalar(
        select(func.count()).select_from(before)
    )
    result["total_after_filter"] = session.scalar(select(func.count()).select_from(pool_ids))
    result.update(
        state="NO_PRECEDENT", reason_code="NO_COMPATIBLE_PRECEDENT", total_above_threshold=0
    )
    if not result["total_candidates_before_filter"]:
        result["reason_code"] = (
            "NO_HISTORY" if "*" in (actor.data_domains or []) else "NO_ACCESSIBLE_PRECEDENT"
        )
        return result
    if not result["total_after_filter"]:
        return result
    # INDEXED checkpoint without vector is corruption, not successful empty coverage.
    uncovered = (
        pool.with_only_columns(Decision.id)
        .outerjoin(
            IndexItem, (IndexItem.version_id == version.id) & (IndexItem.decision_id == Decision.id)
        )
        .outerjoin(
            DecisionEmbedding,
            (DecisionEmbedding.version_id == version.id)
            & (DecisionEmbedding.decision_id == Decision.id),
        )
        .where(
            IndexItem.decision_id.is_(None)
            | ((IndexItem.reason == "INDEXED") & DecisionEmbedding.id.is_(None))
        )
    )
    if session.scalar(uncovered.limit(1)):
        result.update(state="INDEXING", reason_code="INDEX_NOT_READY", total_above_threshold=None)
        return result
    # Validate every scoped compatible artifact before thresholding: corrupt vectors
    # cannot disappear below threshold and masquerade as an honest empty result.
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
    invalid_vector = (
        select(DecisionEmbedding.id)
        .where(
            DecisionEmbedding.version_id == version.id,
            integrity_predicate,
            DecisionEmbedding.decision_id.in_(select(pool_ids.c.id)),
        )
        .limit(1)
    )
    # The partial integrity index is maintained on every insert/write, including a
    # deliberate test/admin corruption. It checks the whole scoped pool without
    # serializing and hashing 10k vectors again for each concurrent HTTP reader.
    invalid_features = (
        select(DecisionEmbedding.id)
        .where(
            DecisionEmbedding.version_id == version.id,
            DecisionEmbedding.decision_id.in_(select(pool_ids.c.id)),
            (DecisionEmbedding.domain != features["domain"])
            | (DecisionEmbedding.entity_type != features["entity_type"])
            | (DecisionEmbedding.attribute_code != features["attribute_code"])
            | (DecisionEmbedding.conflict_type != features["conflict_type"])
            | (DecisionEmbedding.value_kind != features["value_kind"])
            | (DecisionEmbedding.unit != features["unit"]),
        )
        .limit(1)
    )
    if session.scalar(invalid_vector) or session.scalar(invalid_features):
        result.update(state="UNAVAILABLE", reason_code="INDEX_INTEGRITY_FAILURE")
        return result
    distance = cast(
        DecisionEmbedding.embedding.op("OPERATOR(public.<=>)")(
            cast(literal(query_vector, type_=Vector()), Vector())
        ),
        Float,
    )
    ranked = (
        select(DecisionEmbedding, Decision, distance.label("distance"))
        .join(Decision, Decision.id == DecisionEmbedding.decision_id)
        .where(
            DecisionEmbedding.version_id == version.id,
            Decision.id.in_(select(pool_ids.c.id)),
            *[getattr(DecisionEmbedding, key) == features[key] for key in COMPATIBILITY],
        )
    )
    above = ranked.where(distance <= 1 - version.config["threshold"])
    result["total_above_threshold"] = session.scalar(
        select(func.count()).select_from(above.subquery())
    )
    for artifact, decision, dist in session.execute(
        above.order_by(distance, Decision.decided_at.desc(), Decision.id)
        .limit(limit)
        .offset(offset)
    ):
        try:
            past = context(decision.context_snapshot, decision)
            if (
                digest(past) != artifact.feature_hash
                or past != artifact.features
                or artifact.input_hash != digest(past)
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
