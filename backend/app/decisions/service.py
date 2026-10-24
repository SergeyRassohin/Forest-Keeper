"""Atomic human review. PostgreSQL is the authority; no Redis/AI/network dependency."""

import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent, User
from app.auth.policy import permits
from app.common.errors import ApiError
from app.conflicts.models import Conflict
from app.decisions.models import Decision, DecisionType
from app.decisions.schemas import BeginReview, CreateDecision
from app.decisions.validation import correction_policy, resolve_value, selectable
from app.imports.models import SourceSystem
from app.matching.models import MatchingRun
from app.normalization.models import AnalysisRun, CanonicalEntity


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            jsonable_encoder(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def require(actor: User, permission: str) -> None:
    if not permits(actor, permission):
        raise ApiError(403, "PERMISSION_DENIED", "Недостаточно прав для этого действия")


def domain_allowed(actor: User, domain: str) -> bool:
    return "*" in (actor.data_domains or []) or domain in (actor.data_domains or [])


def case_for(session: Session, identifier: UUID, actor: User, *, lock: bool = False) -> Conflict:
    query = select(Conflict).where(Conflict.id == identifier)
    if "*" not in (actor.data_domains or []):
        query = query.join(CanonicalEntity, CanonicalEntity.id == Conflict.entity_id).where(
            CanonicalEntity.domain.in_(actor.data_domains or [])
        )
    if lock:
        query = query.with_for_update(of=Conflict)
    case = session.scalar(query)
    if case is None:
        raise ApiError(404, "CONFLICT_NOT_FOUND", "Конфликт не найден или недоступен")
    return case


def frozen_evidence(case: Conflict) -> dict[str, Any]:
    return {
        key: jsonable_encoder(getattr(case, key))
        for key in [
            "id",
            "entity_id",
            "analysis_run_id",
            "matching_run_id",
            "match_candidate_id",
            "attribute_code",
            "conflict_type",
            "severity",
            "detected_at",
            "values_snapshot",
            "basis",
        ]
    }


def context_version(case: Conflict) -> str:
    return digest(
        {
            "evidence": digest(frozen_evidence(case)),
            "status": case.status,
            "version": case.review_version,
            "effective_decision": case.current_decision_id,
        }
    )


def audit(
    session: Session,
    actor_id: UUID | None,
    case_id: UUID,
    event: str,
    request_id: UUID,
    **metadata: Any,
) -> UUID:
    identifier = uuid4()
    session.add(
        AuditEvent(
            id=identifier,
            event_type=event,
            user_id=actor_id,
            object_type="Conflict",
            object_id=case_id,
            payload={"request_id": str(request_id), **jsonable_encoder(metadata)},
        )
    )
    return identifier


def decision_view(
    row: Decision, successor: UUID | None = None, *, detail: bool = False
) -> dict[str, Any]:
    result = {
        key: getattr(row, key)
        for key in [
            "id",
            "conflict_id",
            "entity_id",
            "domain",
            "entity_type",
            "business_key",
            "attribute_code",
            "decision_type",
            "selected_value",
            "selected_source_id",
            "selected_value_id",
            "value_kind",
            "unit",
            "reason",
            "user_id",
            "actor_roles",
            "actor_display_name",
            "decided_at",
            "supersedes_decision_id",
            "audit_event_id",
            "schema_version",
        ]
    }
    result.update(status="SUPERSEDED" if successor else "ACTIVE", superseded_by=successor)
    if detail:
        result.update(
            context_snapshot=row.context_snapshot,
            evidence_hash=row.evidence_hash,
            context_version=row.context_version,
            corrected_input=row.corrected_input,
            conversion_trace=row.conversion_trace,
            idempotency_key=row.idempotency_key,
            conflict_status_at_decision=outcome_state(row.decision_type),
        )
    return result


def successor_id(session: Session, row: Decision) -> UUID | None:
    return session.scalar(select(Decision.id).where(Decision.supersedes_decision_id == row.id))


def outcome_state(kind: str) -> str:
    return {
        "SELECT_VALUE": "RESOLVED",
        "ENTER_VALUE": "RESOLVED",
        "INSUFFICIENT_DATA": "INSUFFICIENT_DATA",
        "DEFERRED": "IN_REVIEW",
    }[kind]


def historical_context(
    session: Session, case: Conflict, *, include_review: bool = True
) -> dict[str, Any]:
    entity = session.get(CanonicalEntity, case.entity_id)
    matching = session.get(MatchingRun, case.matching_run_id)
    if entity is None or matching is None:
        raise ApiError(409, "EVIDENCE_UNAVAILABLE", "Исторический контекст недоступен")
    origins = []
    for origin in case.basis["normalization_context"]["normalization"]:
        run = session.get(AnalysisRun, UUID(origin["analysis_id"]))
        if run is None:
            raise ApiError(409, "EVIDENCE_UNAVAILABLE", "Исторический контекст недоступен")
        origins.append({**origin, "profile_version": run.mapping_snapshot["version"]})
    result = {
        "schema_version": 1,
        "conflict": frozen_evidence(case),
        "subject": {
            "domain": entity.domain,
            "entity_type": entity.entity_type,
            "display_name": entity.display_name,
        },
        "normalization_origins": origins,
        "retrieval_sources": [
            {
                "source_id": side["source_id"],
                "source_type": source.source_type if source else "UNKNOWN",
                "role": "NOT_DEFINED",
            }
            for side in case.values_snapshot
            for source in [session.get(SourceSystem, UUID(side["source_id"]))]
        ],
        "matching": {
            "run_id": str(matching.id),
            "profile_id": str(matching.profile_id),
            "profile_hash": matching.profile_hash,
            "profile_snapshot": matching.profile_snapshot,
            "input_context": matching.input_context,
        },
        "forest_codex": {"configured": False, "version": None},
        "authority": "NOT_DEFINED",
    }
    if include_review:
        result["review"] = {
            "status": case.status,
            "version": case.review_version,
            "context_version": context_version(case),
            "effective_decision_id": str(case.current_decision_id)
            if case.current_decision_id
            else None,
        }
    return result


def review_context(session: Session, case: Conflict, actor: User) -> dict[str, Any]:
    head = session.get(Decision, case.current_decision_id) if case.current_decision_id else None
    can_create = permits(actor, "decision.create") and permits(actor, "conflict.review.start")
    can_replace = head is None or permits(actor, "decision.supersede")
    actions = []
    policy = correction_policy(case.values_snapshot)
    if can_create and can_replace:
        if any(selectable(side) for side in case.values_snapshot):
            actions.append("SELECT_VALUE")
        if policy["allowed"]:
            actions.append("ENTER_VALUE")
        if permits(actor, "decision.insufficient_data"):
            actions.append("INSUFFICIENT_DATA")
        actions.append("DEFERRED")
    history_count = session.scalar(
        select(func.count()).select_from(Decision).where(Decision.conflict_id == case.id)
    )
    return {
        "conflict_id": case.id,
        "conflict_status": case.status,
        "review_version": case.review_version,
        "context_version": context_version(case),
        "evidence_hash": digest(frozen_evidence(case)),
        "evidence": historical_context(session, case),
        "allowed_actions": actions,
        "can_start_review": can_create and can_replace,
        "can_supersede": bool(head and can_create and permits(actor, "decision.supersede")),
        "current_decision": decision_view(head) if head else None,
        "history_count": history_count,
        "correction_policy": policy,
        "selectable_values": [
            {
                "source_id": side["source_id"],
                "source_name": side["source_name"],
                "side": "A" if index == 0 else "B",
                "value_id": side["value"]["value_id"],
                "value": side["value"]["normalized_value"],
                "unit": side["value"].get("unit"),
            }
            for index, side in enumerate(case.values_snapshot)
            if selectable(side)
        ],
        "known_unknowns": [
            {
                "source_id": side["source_id"],
                "presence": side.get("presence"),
                "quality": side["value"].get("quality_status") if side.get("value") else "UNKNOWN",
            }
            for side in case.values_snapshot
            if not selectable(side)
        ],
        "source_systems_changed": False,
    }


def check_version(case: Conflict, token: str) -> None:
    if token != context_version(case):
        raise ApiError(
            409,
            "STALE_REVIEW_CONTEXT",
            "Контекст изменился. Обновите карточку и проверьте принятое решение",
        )


def check_predecessor(case: Conflict, predecessor: UUID | None, actor: User) -> None:
    if case.current_decision_id != predecessor:
        raise ApiError(409, "DECISION_HEAD_CHANGED", "Уже есть другое решение. Перечитайте историю")
    if predecessor is not None:
        require(actor, "decision.supersede")


def begin_review(
    session: Session, case: Conflict, actor: User, body: BeginReview, request_id: UUID
) -> dict[str, Any]:
    require(actor, "conflict.review.start")
    check_version(case, body.context_version)
    check_predecessor(case, body.supersedes_decision_id, actor)
    if case.status != "IN_REVIEW":
        previous = case.status
        case.status = "IN_REVIEW"
        case.review_version += 1
        audit(
            session,
            actor.id,
            case.id,
            "CONFLICT_REVIEW_STARTED",
            request_id,
            previous_status=previous,
            status=case.status,
            version=case.review_version,
            supersedes_decision_id=body.supersedes_decision_id,
        )
        session.commit()
    return review_context(session, case, actor)


def save_decision(
    session: Session, case: Conflict, actor: User, body: CreateDecision, request_id: UUID
) -> tuple[dict[str, Any], bool]:
    require(actor, "decision.create")
    if body.decision_type == DecisionType.INSUFFICIENT_DATA:
        require(actor, "decision.insufficient_data")
    if body.supersedes_decision_id:
        require(actor, "decision.supersede")
    request_hash = digest(body.model_dump(mode="json"))
    existing = session.scalar(
        select(Decision).where(
            Decision.user_id == actor.id,
            Decision.conflict_id == case.id,
            Decision.idempotency_key == body.idempotency_key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise ApiError(
                409,
                "IDEMPOTENCY_KEY_REUSED",
                "Этот ключ отправки уже использован с другим содержимым",
            )
        return receipt(session, existing, case), False
    check_version(case, body.context_version)
    check_predecessor(case, body.supersedes_decision_id, actor)
    if case.status != "IN_REVIEW":
        raise ApiError(409, "REVIEW_NOT_STARTED", "Сначала начните рассмотрение этого конфликта")
    selected = resolve_value(body, case.values_snapshot)
    snapshot = historical_context(session, case)
    identifier = uuid4()
    evidence_hash = digest(frozen_evidence(case))
    audit(
        session,
        actor.id,
        case.id,
        "DECISION_CREATE_ATTEMPTED",
        request_id,
        decision_id=identifier,
        decision_type=body.decision_type,
        evidence_hash=evidence_hash,
    )
    event_id = audit(
        session,
        actor.id,
        case.id,
        "DECISION_CREATED",
        request_id,
        decision_id=identifier,
        decision_type=body.decision_type,
        evidence_hash=evidence_hash,
        context_version=body.context_version,
        schema_version=1,
    )
    # The Decision links an already persisted audit event in this same transaction.
    session.flush()
    row = Decision(
        id=identifier,
        conflict_id=case.id,
        entity_id=case.entity_id,
        domain=snapshot["subject"]["domain"],
        entity_type=snapshot["subject"]["entity_type"],
        business_key=str(
            case.values_snapshot[0].get("source_record_key") or snapshot["subject"]["display_name"]
        )[:256],
        attribute_code=case.attribute_code,
        decision_type=body.decision_type,
        **selected,
        reason=body.reason,
        user_id=actor.id,
        actor_roles=sorted(assignment.role_code for assignment in actor.roles),
        actor_display_name=actor.full_name,
        context_snapshot=snapshot,
        evidence_hash=evidence_hash,
        context_version=body.context_version,
        schema_version=1,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        supersedes_decision_id=body.supersedes_decision_id,
        audit_event_id=event_id,
    )
    session.add(row)
    session.flush()  # INSERT guard still sees IN_REVIEW and the previous effective head.
    case.current_decision_id = identifier
    case.status = outcome_state(body.decision_type)
    case.review_version += 1
    if body.supersedes_decision_id:
        audit(
            session,
            actor.id,
            case.id,
            "DECISION_SUPERSEDED",
            request_id,
            decision_id=body.supersedes_decision_id,
            superseded_by=identifier,
        )
    audit(
        session,
        actor.id,
        case.id,
        "CONFLICT_LIFECYCLE_CHANGED",
        request_id,
        previous_status="IN_REVIEW",
        status=case.status,
        decision_id=identifier,
        version=case.review_version,
    )
    session.commit()  # Decision, head, lifecycle and audit are one durable PostgreSQL transaction.
    return receipt(session, row, case), True


def receipt(session: Session, row: Decision, case: Conflict) -> dict[str, Any]:
    return {
        "decision_id": row.id,
        "conflict_id": case.id,
        "conflict_status": outcome_state(row.decision_type),
        "current_conflict_status": case.status,
        "current_decision_id": case.current_decision_id,
        "decision": decision_view(row, successor_id(session, row), detail=True),
        "source_systems_changed": False,
        "message": "Решение сохранено в Forest Keeper. Исходные системы не изменялись.",
    }
