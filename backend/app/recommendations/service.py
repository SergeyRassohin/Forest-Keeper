"""One authorized snapshot, bounded existing retrieval and deterministic advisory output."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.basis_lock import Budget
from app.common.config import Settings
from app.conflicts.models import Conflict
from app.decisions.models import Decision
from app.decisions.service import context_version, digest, frozen_evidence, historical_context
from app.decisions.validation import selectable
from app.recommendations.evidence import EvidenceError, prepare, validate_lineage
from app.recommendations.policy import POLICY, POLICY_HASH, aggregate
from app.recommendations.schemas import Evidence, Outcome, RecommendationResult, SourceMap
from app.similarity.models import DecisionEmbedding
from app.similarity.provider import permitted
from app.similarity.service import compatible_pool, eligible, retrieval

MESSAGES = {
    "UNANIMOUS_INDEPENDENT_PRECEDENTS": (
        "В независимых похожих случаях люди выбирали соответствующий "
        "источник. Проверьте текущее значение и примите собственное "
        "решение."
    ),
    "INSUFFICIENT_INDEPENDENT_EVIDENCE": (
        "Недостаточно независимых оснований: требуется не менее пяти "
        "согласованных групп прошлых случаев."
    ),
    "CONTRADICTORY_PRECEDENTS": (
        "В прошлых решениях есть противоречие. Система воздерживается от "
        "выбора; рассмотрите основания самостоятельно."
    ),
    "SOURCE_MAPPING_NOT_CONFIGURED": "Соответствие исторических и текущих источников не назначено.",
    "SOURCE_MAPPING_AMBIGUOUS": (
        "Не удалось однозначно подтвердить соответствие источников. Выбор остаётся за человеком."
    ),
    "UNSUPPORTED_HISTORICAL_ACTION": (
        "История содержит вручную введённое значение. Переносить его в "
        "новый случай без проверенных правил нельзя."
    ),
    "EVIDENCE_WINDOW_EXCEEDED": (
        "Подходящих прецедентов больше двадцати. Полнота рассмотрения "
        "оснований для готового предложения не обеспечена."
    ),
    "CURRENT_CASE_NOT_ELIGIBLE": (
        "По этому случаю уже есть решение или идёт его пересмотр. Используйте ручное рассмотрение."
    ),
    "STALE_CONTEXT": (
        "Основания относятся к предыдущей конфигурации. Обновите оценку "
        "перед использованием предложения."
    ),
    "INDEX_NOT_READY": "Индекс прошлых решений ещё не готов. Ручное рассмотрение доступно.",
    "INDEX_COVERAGE_UNCERTAIN": (
        "Часть совместимой истории не представлена в индексе. "
        "Полнота оснований не подтверждена; рассмотрите случай вручную."
    ),
    "QUERY_CONTEXT_PENDING": (
        "Контекст поиска ещё подготавливается. Откройте похожие решения и повторите проверку."
    ),
    "NO_HISTORY": "Доступных прошлых решений пока нет. Обоснованной рекомендации нет.",
    "NO_ACCESSIBLE_PRECEDENT": "Доступных прецедентов нет. Обоснованной рекомендации нет.",
    "NO_COMPATIBLE_PRECEDENT": "Нет совместимых прошлых решений для этого конфликта.",
    "BELOW_THRESHOLD": "Найденная история недостаточно похожа. Обоснованной рекомендации нет.",
    "PROVIDER_UNAVAILABLE": (
        "Механизм поиска недоступен. Ручное рассмотрение и сохранённые решения доступны отдельно."
    ),
    "POLICY_NOT_APPROVED": "Политика рекомендаций не утверждена. Используйте ручное рассмотрение.",
    "CORRUPT_LINEAGE": "Целостность оснований не подтверждена. Готовая рекомендация недоступна.",
}


@dataclass
class Computed:
    result: RecommendationResult
    basis: dict[str, Any]


def evaluate(
    session: Session, actor: User, case: Conflict, settings: Settings, budget: Budget
) -> Computed:
    token = context_version(case)
    basis: dict[str, Any] = {
        "actor_id": str(actor.id),
        "conflict_id": str(case.id),
        "review_context_version": token,
        "actor_access_hash": digest(
            {
                "scope": sorted(actor.data_domains or []),
                "roles": sorted(r.role_code for r in actor.roles),
            }
        ),
        "policy": POLICY,
        "policy_hash": POLICY_HASH,
    }
    result = RecommendationResult(
        conflict_id=case.id,
        reason_code="PROVIDER_UNAVAILABLE",
        reasoning_summary=MESSAGES["PROVIDER_UNAVAILABLE"],
        recommendation_policy_version=POLICY["version"],
        recommendation_policy_hash=POLICY_HASH,
        context_fingerprint=digest(basis),
        review_context_version=token,
        generated_at=datetime.now(UTC),
        limitations=[
            "Рекомендация не является решением. Окончательный выбор делает человек.",
            "Промышленное семантическое качество поиска не подтверждено.",
            "Rules, CustomerTemplate и Forest Codex не настроены; авторитетный источник не задан.",
            (
                "Применяются только точные канонические типы/единицы; диапазоны и "
                "семейства не угадываются."
            ),
        ],
    )

    def finish(reason: str, state: Outcome = Outcome.ABSTAINED) -> Computed:
        budget.arm(session)
        result.status = state
        result.reason_code = reason
        result.reasoning_summary = MESSAGES.get(
            reason,
            (
                "Основания рекомендации недоступны или не подтверждены. Ручное "
                "рассмотрение доступно отдельно."
            ),
        )
        basis["result"] = {
            "status": state,
            "reason_code": reason,
            "action": result.recommended_action,
            "source_id": str(result.recommended_source_id)
            if result.recommended_source_id
            else None,
            "value_id": str(result.recommended_value_id) if result.recommended_value_id else None,
            "confidence": result.confidence,
            "summary": result.evidence_summary,
        }
        result.context_fingerprint = digest(basis)
        return Computed(RecommendationResult.model_validate(result.model_dump()), basis)

    if not settings.recommendation_enabled or not permitted(settings):
        return finish("PROVIDER_UNAVAILABLE", Outcome.UNAVAILABLE)
    if POLICY.get("approval", {}).get("status") != "APPROVED":
        return finish("POLICY_NOT_APPROVED")
    result.quality_provenance = "DEMONSTRATION_ONLY"
    result.limitations.insert(
        0, "Демонстрационный режим: тестовые векторы не доказывают правильность рекомендации."
    )
    if case.status not in {"OPEN", "IN_REVIEW"} or case.current_decision_id is not None:
        return finish("CURRENT_CASE_NOT_ELIGIBLE")
    budget.arm(session)
    try:
        snapshot = historical_context(session, case, include_review=False)
        basis["current_context_hash"] = digest(snapshot)
        if not settings.recommendation_source_map:
            return finish("SOURCE_MAPPING_NOT_CONFIGURED")
        mapping = SourceMap.model_validate(settings.recommendation_source_map)
        current = prepare(snapshot, mapping)
        validate_lineage(session, [snapshot])
    except ValidationError:
        return finish("SOURCE_MAPPING_AMBIGUOUS")
    except EvidenceError as error:
        return finish(str(error))
    result.source_mapping_version = mapping.version
    basis["source_mapping_hash"] = digest(mapping.model_dump(mode="json"))
    basis["source_mapping_version"] = mapping.version
    # No embedding calculation, job enqueue, internal HTTP or hidden pagination here.
    budget.arm(session)
    retrieved = retrieval(session, actor, case, settings, 20, 0, prepare_query=False)
    budget.arm(session)
    result.retrieval_version = retrieved["retrieval_version"]
    result.embedding_model = retrieved["embedding_model"]
    basis["retrieval"] = {
        "version": str(result.retrieval_version) if result.retrieval_version else None,
        "model": result.embedding_model,
        "query_hash": retrieved["query_context_hash"],
        "total_above_threshold": retrieved["total_above_threshold"],
    }
    if retrieved["state"] != "READY":
        return finish(
            retrieved["reason_code"],
            Outcome.UNAVAILABLE
            if retrieved["state"] in {"UNAVAILABLE", "INDEXING"}
            else Outcome.ABSTAINED,
        )
    # A known oversized pool already forbids an action; avoid additional
    # completeness work whose result cannot change that bounded abstention.
    if retrieved["total_above_threshold"] > POLICY["maximum_precedents"]:
        return finish("EVIDENCE_WINDOW_EXCEEDED")
    # Stage 7 permits explicit non-INDEXED checkpoints for retrieval. A ready
    # action needs stronger completeness: an unrepresented compatible outcome
    # might contradict the visible five. Check only scoped narrow metadata,
    # including skips, without loading unbounded historical JSON or changing
    # the public Stage 7 contract.
    unrepresented = compatible_pool(actor, case, current.features).where(
        ~exists(
            select(DecisionEmbedding.id).where(
                DecisionEmbedding.decision_id == Decision.id,
                DecisionEmbedding.version_id == result.retrieval_version,
            )
        )
    )
    if session.scalar(select(exists(unrepresented.with_only_columns(Decision.id)))):
        return finish("INDEX_COVERAGE_UNCERTAIN", Outcome.UNAVAILABLE)
    basis["complete_compatible_vector_coverage"] = True
    ids = [UUID(str(item["decision_id"])) for item in retrieved["results"]]
    records = cast(
        list[tuple[Decision, Conflict]],
        session.execute(eligible(actor).where(Decision.id.in_(ids)).add_columns(Conflict)).all(),
    )
    rows = {row.id: row for row, _ in records}
    if any(row.evidence_hash != digest(frozen_evidence(past_case)) for row, past_case in records):
        return finish("CORRUPT_LINEAGE", Outcome.UNAVAILABLE)
    try:
        validate_lineage(session, [row.context_snapshot for row in rows.values()])
    except EvidenceError:
        return finish("CORRUPT_LINEAGE", Outcome.UNAVAILABLE)
    if len(ids) != len(rows) or len(ids) != retrieved["total_above_threshold"]:
        return finish("CORRUPT_LINEAGE", Outcome.UNAVAILABLE)
    prepared, manifest = [], []
    used_sources = set(current.roles)
    try:
        for item in retrieved["results"]:
            row = rows[UUID(str(item["decision_id"]))]
            past = prepare(row.context_snapshot, mapping, row)
            prepared.append(past.candidate)
            used_sources.update(past.roles)
            correspondence = [
                {
                    "historical_source_id": source_id,
                    "logical_role": role,
                    "current_source_id": next(
                        key for key, value in current.roles.items() if value == role
                    ),
                }
                for source_id, role in sorted(past.roles.items())
            ]
            result.evidence.append(
                Evidence(
                    decision_id=row.id,
                    conflict_id=row.conflict_id,
                    actor_id=row.user_id,
                    actor_display_name=row.actor_display_name,
                    decided_at=row.decided_at,
                    outcome=row.decision_type,
                    selected_value=row.selected_value,
                    unit=row.unit,
                    reason=row.reason,
                    similarity=item["similarity"],
                    logical_role=past.candidate.role,
                    context_summary={
                        key: past.features[key]
                        for key in (
                            "domain",
                            "entity_type",
                            "subject",
                            "attribute_code",
                            "conflict_type",
                            "value_kind",
                            "unit",
                        )
                    },
                    source_correspondence=correspondence,
                )
            )
            manifest.append(
                {
                    "decision_id": str(row.id),
                    "context_hash": digest(row.context_snapshot),
                    "evidence_hash": row.evidence_hash,
                    "similarity": item["similarity"],
                    "outcome": row.decision_type,
                    "logical_role": past.candidate.role,
                }
            )
    except (EvidenceError, StopIteration) as error:
        result.evidence = []
        return finish(
            str(error) if isinstance(error, EvidenceError) else "SOURCE_MAPPING_AMBIGUOUS"
        )
    basis["evidence"] = manifest
    scoped_mapping = mapping.model_dump(mode="json")
    scoped_mapping["sources"] = [
        s for s in scoped_mapping["sources"] if s["source_id"] in used_sources
    ]
    basis["source_mapping"] = scoped_mapping
    # Bind the entire trusted declaration hash too: a configuration change is never silent.
    basis["source_mapping_hash"] = digest(mapping.model_dump(mode="json"))
    combined = aggregate(current.candidate.correlation, prepared)
    result.evidence_summary = {
        "evaluated_precedents": len(prepared),
        "independent_groups": combined.get("independent_groups", 0),
        "minimum_groups": POLICY["minimum_groups"],
        "groups": combined["groups"],
        "independence_quality": "CONSERVATIVE_DEMONSTRATION_GROUPING_NOT_INDUSTRIAL_PROOF",
    }
    reason = combined["reason"]
    if reason == "CONTRADICTORY_PRECEDENTS":
        result.conflicting_evidence = ids
    if reason != "UNANIMOUS_INDEPENDENT_PRECEDENTS":
        return finish(reason)
    targets = [
        side
        for side in case.values_snapshot
        if current.roles[side["source_id"]] == combined["role"] and selectable(side)
    ]
    if len(targets) != 1:
        return finish("SOURCE_MAPPING_AMBIGUOUS")
    target = targets[0]
    result.recommended_action = "SELECT_VALUE"
    result.recommended_source_id = UUID(target["source_id"])
    result.recommended_value_id = UUID(target["value"]["value_id"])
    result.recommended_value = {
        "kind": target["value"]["kind"],
        "value": target["value"]["normalized_value"],
        "unit": target["value"].get("unit"),
    }
    result.confidence = combined["independent_groups"]
    result.confidence_label = "SUFFICIENT_DEMONSTRATION_EVIDENCE"
    result.supporting_decision_ids = [
        UUID(identifier)
        for group in combined["groups"]
        if not group["correlated_with_current"]
        for identifier in group["decision_ids"]
    ]
    return finish(reason, Outcome.RECOMMENDED)
