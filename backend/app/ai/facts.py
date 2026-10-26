"""Minimal authorized comparison/evidence, independently of generated prose."""

from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.contracts import (
    AIError,
    ClauseCode,
    ComparedValue,
    Comparison,
    Explanation,
    Facts,
    PrecedentFact,
    semantic_context,
    validate_explanation,
)
from app.ai.identity import expected_model_info
from app.auth.models import User
from app.common.basis_lock import Budget
from app.common.config import Settings
from app.conflicts.models import Conflict
from app.decisions.service import digest, historical_context
from app.recommendations.evidence import EvidenceError, validate_lineage
from app.recommendations.schemas import SourceMap
from app.recommendations.service import MESSAGES, evaluate
from app.similarity.context import context
from app.similarity.provider import ProviderError


def scalar_text(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise AIError("AI_INPUT_NOT_VERIFIED")


def collect(
    session: Session, actor: User, case: Conflict, settings: Settings, budget: Budget
) -> Facts:
    try:
        computed = evaluate(session, actor, case, settings, budget)
        result = computed.result
        snapshot = historical_context(session, case, include_review=False)
        budget.arm(session)
        validate_lineage(session, [snapshot])
        semantic = semantic_context(context(snapshot))
        roles = {}
        if result.source_mapping_version is not None:
            mapping = SourceMap.model_validate(settings.recommendation_source_map)
            roles = {str(item.source_id): item.role for item in mapping.sources}
        values = []
        for side in case.values_snapshot:
            value = side.get("value") or {}
            values.append(
                ComparedValue(
                    source_id=side["source_id"],
                    value_id=value.get("value_id"),
                    normalized_value=scalar_text(value.get("normalized_value")),
                    presence=side["presence"],
                    quality=value.get("quality_status", "UNKNOWN"),
                    logical_role=roles.get(side["source_id"], "NOT_DEFINED"),
                )
            )
        comparison = Comparison(
            **semantic.model_dump(exclude={"subject", "observations"}), values=values
        )
        precedents = [
            PrecedentFact.model_validate(
                {
                    "decision_id": item.decision_id,
                    "outcome": item.outcome,
                    "selected_value": scalar_text(item.selected_value),
                    "unit": item.unit or "",
                    "logical_role": item.logical_role,
                }
            )
            for item in result.evidence
        ]
        fingerprint = digest(
            {
                "recommendation": result.context_fingerprint,
                "model": expected_model_info("llm").model_dump(mode="json"),
                "source_map": settings.recommendation_source_map,
                "comparison": comparison.model_dump(mode="json"),
                "precedents": [item.model_dump(mode="json") for item in precedents],
            }
        )
        return Facts(
            conflict_id=case.id,
            context_fingerprint=fingerprint,
            status=result.status.value,
            reason_code=result.reason_code,
            action=result.recommended_action,
            supporting_decision_ids=result.supporting_decision_ids,
            contradictory_decision_ids=result.conflicting_evidence,
            source_ids=[item.source_id for item in values],
            value_ids=[item.value_id for item in values if item.value_id is not None],
            independent_groups=result.evidence_summary.get("independent_groups", 0),
            comparison=comparison,
            precedents=precedents,
        )
    except (EvidenceError, ProviderError, ValidationError, KeyError, TypeError, ValueError):
        raise AIError("AI_INPUT_NOT_VERIFIED") from None


def render(output: Explanation, facts: Facts, language: str = "ru") -> list[dict[str, Any]]:
    validate_explanation(output, facts)
    rows = {item.decision_id: item for item in facts.precedents}
    clauses = []
    for clause in output.clauses:
        example = rows[clause.decision_ids[0]] if clause.decision_ids else None
        if clause.code == ClauseCode.CURRENT_CONTEXT:
            values = "; ".join(
                (item.normalized_value or ("не определено" if language == "ru" else "unknown"))
                + (" " + facts.comparison.unit if facts.comparison.unit else "")
                for item in facts.comparison.values
            )
            text = (
                f"Сравниваются значения атрибута «{facts.comparison.attribute_code}»: {values}. "
                "Это нормализованные наблюдения, а не установленная истина."
                if language == "ru"
                else f"Current {facts.comparison.attribute_code} observations: {values}. "
                "Normalization does not establish truth."
            )
        elif clause.code == ClauseCode.SUPPORT and example is not None:
            text = (
                f"Детерминированная политика опирается на {facts.independent_groups} "
                f"независимых групп подтверждённых случаев. В приведённом примере выбрано "
                f"{example.selected_value} {example.unit}; логическая роль источника: "
                f"{example.logical_role}. Проверьте текущее значение самостоятельно."
                if language == "ru"
                else f"The deterministic policy uses {facts.independent_groups} "
                "independent groups. "
                f"The cited example selected {example.selected_value} {example.unit} "
                f"from logical source role {example.logical_role}. A human decides this case."
            )
        elif clause.code == ClauseCode.CONTRADICTION:
            text = (
                "В проверенном наборе прошлых решений есть противоречащие исходы. "
                "Политика воздерживается от выбора. Ссылка показывает один из случаев этого набора."
                if language == "ru"
                else "Verified precedents contain conflicting outcomes. The policy abstains. "
                "The link identifies one member of that evidence set."
            )
        elif clause.code == ClauseCode.ABSTENTION:
            text = (
                MESSAGES.get(facts.reason_code, "Проверенных оснований для готового действия нет.")
                if language == "ru"
                else "No verified basis permits a proposed action. Review the evidence manually."
            )
        else:
            text = (
                "Локальная AI-модель объясняет только переданные проверенные факты. "
                "Демонстрационный режим: промышленное качество не подтверждено. "
                "Окончательное решение принимает человек."
                if language == "ru"
                else "Local AI explains only the supplied verified facts. This is development "
                "mode, without accepted production semantic quality. A human makes the decision."
            )
        clauses.append(
            {
                "code": clause.code.value,
                "text": text,
                "decision_ids": [str(value) for value in clause.decision_ids],
            }
        )
    return clauses
