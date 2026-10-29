"""Human-review outlines only: no inference, scoring, approved labels or production policy."""

import csv
import hashlib
import json
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "docs/testing/data/stage9-quality-candidates-v0.1"
FAMILIES = [
    ("fasteners", "Болт стальной М8×30", "0.0125", "0.0124"),
    ("steel-profile", "Профиль стальной", "12.5", "12.4"),
    ("cement", "Мешок цемента", "25", "24.8"),
    ("power-cable", "Бухта силового кабеля", "42", "41.8"),
    ("polymer-pipe", "Труба полипропиленовая", "2.5", "2.4"),
    ("lumber", "Брус деревянный", "12.5", "12.3"),
    ("ceramic", "Кирпич керамический", "3.6", "3.5"),
    ("bitumen", "Рулон битумной кровли", "23", "22.7"),
    ("rubber", "Прокладка резиновая", "0.125", "0.124"),
    ("glass", "Панель из стекла", "14", "13.9"),
    ("oil", "Канистра смазочного масла", "18", "17.8"),
    ("mineral-wool", "Упаковка минеральной ваты", "7.5", "7.3"),
    ("coating", "Банка защитного покрытия", "10", "9.8"),
    ("abrasive", "Упаковка абразивных листов", "0.5", "0.48"),
    ("copper", "Лист медный", "28", "27.8"),
    ("aluminium", "Заготовка алюминиевая", "5.4", "5.3"),
    ("composite", "Панель композитная", "6", "5.9"),
    ("battery", "Аккумуляторный блок", "12", "11.9"),
    ("actuator", "Электромеханический привод", "4", "3.9"),
    ("packaging", "Комплект картонной упаковки", "2", "1.9"),
]
SCENARIOS = [
    ("same-family", "Совместимые случаи того же семейства", "related"),
    ("name-variant", "Вариант наименования и сокращение: эксперт подтверждает смысл", "related"),
    ("normalized-unit", "Граммы и килограммы нормализованы вkg", "related"),
    ("wrong-attribute", "История о цене вместо массы", "none"),
    ("wrong-unit", "Исторические метры несовместимы с массой вkg", "none"),
    ("out-of-scope", "История вне actor domain; даже количество скрыто", "none"),
    ("ambiguous-family", "Похожее описание другого назначения: нужен эксперт", "unknown"),
    ("contradictory", "Совместимая история с разными исходами3/2: demo воздерживается", "related"),
    (
        "untrusted-instruction",
        "Указание в комментарии источника не является инструкцией",
        "related",
    ),
    ("no-history", "Доступных совместимых прошлых случаев нет", "none"),
]


def main():
    if DEST.exists():
        raise SystemExit("Never overwrite human review or historical proposal versions")
    DEST.mkdir(parents=True)
    cases = []
    for index, (family, subject, a, b) in enumerate(FAMILIES):
        for mode, scenario, relevance in SCENARIOS:
            identifier = f"q{len(cases) + 1:03}"
            history = [f"{identifier}-history-{i}" for i in range(1, 6)]
            cases.append(
                {
                    "candidate_id": identifier,
                    "family_cluster": family,
                    "split_proposal": "DEVELOPMENT"
                    if index < 5
                    else "EVALUATION_CANDIDATE_NOT_SEALED",
                    "subject": subject,
                    "mode": mode,
                    "scenario": scenario,
                    "domain": "materials",
                    "attribute_code": "mass",
                    "canonical_unit": "kg",
                    "file_value": a,
                    "onec_value": b,
                    "history_candidate_ids": [] if mode == "no-history" else history,
                    "proposed_relevant_ids": history
                    if relevance == "related"
                    else []
                    if relevance == "none"
                    else None,
                    "human_relevant_ids": None,
                    "human_label_status": "PENDING",
                    "human_approval_reference": None,
                    "provenance": "Invented outline, not customer data or persisted Registry IDs",
                }
            )
    assert len(cases) == len({row["candidate_id"] for row in cases}) == 200
    proposal = {
        "version": DEST.name,
        "status": "PROPOSAL_NOT_GOLD",
        "scoring_allowed": False,
        "human_labels_approved": False,
        "thresholds_approved": False,
        "production_accepted": False,
        "cases": cases,
    }
    raw = (json.dumps(proposal, ensure_ascii=False, indent=2) + "\n").encode()
    (DEST / "candidates.json").write_bytes(raw)
    with (DEST / "human-review.csv").open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.writer(out, delimiter=";")
        writer.writerow(
            [
                "ID",
                "Семейство",
                "Предложение разбиения",
                "Материал",
                "Сценарий",
                "Файл kg",
                "1С kg",
                "Предлагаемые IDs (НЕ gold)",
                "Человеческие релевантные IDs",
                "Ссылка на утверждение",
            ]
        )
        for row in cases:
            proposed = row["proposed_relevant_ids"]
            writer.writerow(
                [
                    row["candidate_id"],
                    row["family_cluster"],
                    row["split_proposal"],
                    row["subject"],
                    row["scenario"],
                    row["file_value"],
                    row["onec_value"],
                    "ТРЕБУЕТ РЕШЕНИЯ" if proposed is None else ", ".join(proposed),
                    "",
                    "",
                ]
            )
    manifest = {
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "cases": 200,
        "human_approved": False,
        "metrics_measured": False,
        "precision_returned_target_proposal": 0.95,
        "recall_target_proposal": 0.90,
        "no_match_false_positive_target_proposal": 0,
        "harmful_recommendation_target_proposal": 0,
    }
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Prepared200 human-review outlines; no gold labels, scores or activation.")


if __name__ == "__main__":
    main()
