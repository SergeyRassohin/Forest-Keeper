"""Bounded immutable receipts; no raw payload, vectors or human reasons in audit."""

import json
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent, User
from app.common.basis_lock import Budget
from app.common.config import Settings
from app.common.errors import ApiError
from app.conflicts.models import Conflict
from app.decisions.schemas import CreateDecision
from app.decisions.service import digest
from app.recommendations.policy import POLICY
from app.recommendations.schemas import Outcome, RecommendationResult
from app.recommendations.service import Computed, evaluate


def receipt_time(stored: AuditEvent, actor_id: UUID, conflict_id: UUID) -> datetime:
    try:
        payload = stored.payload
        if not isinstance(payload, dict):
            raise ValueError("Invalid receipt payload")
        fingerprint = payload["context_fingerprint"]
        basis = payload["basis"]
        stamp = datetime.fromisoformat(str(payload["generated_at"]))
        if (
            stored.event_type != "RECOMMENDATION_EVALUATED"
            or stored.object_type != "Recommendation"
            or stored.user_id != actor_id
            or stored.object_id != conflict_id
            or not isinstance(basis, dict)
            or digest(basis) != fingerprint
            or basis.get("actor_id") != str(actor_id)
            or basis.get("conflict_id") != str(conflict_id)
            or stored.id != uuid5(NAMESPACE_URL, "forest-keeper:recommendation:" + str(fingerprint))
            or stamp.tzinfo is None
            or stamp.utcoffset() is None
        ):
            raise ValueError("Invalid receipt")
        return stamp
    except (KeyError, TypeError, ValueError):
        raise ApiError(
            503,
            "RECOMMENDATION_INTEGRITY_FAILURE",
            "Целостность основания рекомендации не подтверждена",
        ) from None


def record(
    session: Session, computed: Computed, actor_id: UUID, budget: Budget
) -> RecommendationResult:
    result = computed.result
    identifier = uuid5(NAMESPACE_URL, "forest-keeper:recommendation:" + result.context_fingerprint)
    payload = {
        "context_fingerprint": result.context_fingerprint,
        "basis": computed.basis,
        "generated_at": result.generated_at.isoformat(),
    }
    if (
        len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode())
        > POLICY["audit_max_bytes"]
    ):
        raise ApiError(
            503,
            "AUDIT_PAYLOAD_LIMIT",
            "Рекомендация недоступна: превышен размер проверяемых оснований",
        )
    budget.arm(session)
    session.execute(
        insert(AuditEvent)
        .values(
            id=identifier,
            event_type="RECOMMENDATION_EVALUATED",
            user_id=actor_id,
            object_type="Recommendation",
            object_id=result.conflict_id,
            payload=payload,
        )
        .on_conflict_do_nothing(index_elements=[AuditEvent.id])
    )
    budget.arm(session)
    stored = session.get(AuditEvent, identifier)
    if (
        stored is None
        or stored.user_id != actor_id
        or stored.object_id != result.conflict_id
        or not isinstance(stored.payload, dict)
        or stored.payload.get("context_fingerprint") != result.context_fingerprint
    ):
        raise ApiError(503, "AUDIT_UNAVAILABLE", "Не удалось сохранить основание рекомендации")
    generated = receipt_time(stored, actor_id, result.conflict_id)
    budget.prepare_commit(session)
    session.commit()
    return result.model_copy(update={"audit_reference": identifier, "generated_at": generated})


def validate_reference(
    session: Session,
    actor: User,
    case: Conflict,
    body: CreateDecision,
    settings: Settings,
    budget: Budget,
) -> dict[str, Any]:
    """Called only for a new submission under exclusive basis gate, after retry lookup."""
    stored = session.get(AuditEvent, body.recommendation_reference)
    if (
        stored is None
        or stored.event_type != "RECOMMENDATION_EVALUATED"
        or stored.user_id != actor.id
        or stored.object_id != case.id
    ):
        raise ApiError(
            409, "STALE_RECOMMENDATION", "Перечитайте рекомендацию или выберите ручное решение"
        )
    receipt_time(stored, actor.id, case.id)
    fresh = evaluate(session, actor, case, settings, budget)
    if (
        fresh.result.status != Outcome.RECOMMENDED
        or fresh.result.context_fingerprint != stored.payload.get("context_fingerprint")
    ):
        raise ApiError(
            409,
            "STALE_RECOMMENDATION",
            "Основания изменились. Обновите карточку и сделайте собственный выбор",
        )
    action = fresh.basis["result"]
    matched = (
        body.decision_type == "SELECT_VALUE"
        and str(body.selected_source_id) == action["source_id"]
        and str(body.selected_value_id) == action["value_id"]
    )
    return {
        "schema": "recommendation-receipt-v1",
        "audit_reference": str(stored.id),
        "context_fingerprint": fresh.result.context_fingerprint,
        "relationship": "MATCHED" if matched else "OVERRIDDEN",
        "policy_version": fresh.result.recommendation_policy_version,
        "retrieval_version": str(fresh.result.retrieval_version),
        "source_mapping_version": fresh.result.source_mapping_version,
        "supporting_decision_ids": [str(x) for x in fresh.result.supporting_decision_ids],
        "generated_at": stored.payload["generated_at"],
    }
