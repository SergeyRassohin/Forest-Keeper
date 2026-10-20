"""Synthetic matching quality and offline threshold sensitivity; no runtime calibration."""

import json
from collections import Counter
from decimal import Decimal
from uuid import uuid5

from app.matching.engine import BlockIndex, candidates_for, evaluate
from tests.test_matching import DATA, NAMESPACE, PROFILE, gold_records


def run():
    left, right = gold_records()
    gold = json.loads((DATA / "gold.json").read_text())
    truth = {
        (uuid5(NAMESPACE, row["a"]), uuid5(NAMESPACE, row["b"])): row["truth"]
        for row in gold["cases"]
    }
    li, ri = BlockIndex(left, PROFILE), BlockIndex(right, PROFILE)
    degrees = Counter()
    results = {}
    signals = Counter()
    for identifier in sorted(left):
        pairs, _ = candidates_for(left[identifier], right, li, ri, degrees, PROFILE)
        for other, blocks in pairs:
            score, status, evidence = evaluate(left[identifier], other, PROFILE, blocks, li, ri)
            results[(identifier, other.raw_id)] = (score, status, evidence)
            signals.update(
                item["algorithm"] for item in evidence["signals"] if item["score"] is not None
            )

    def metrics(predictions):
        tp = sum(
            status == "MATCHED" and truth.get(pair, "NOT_MATCH") == "MATCH"
            for pair, status in predictions.items()
        )
        fp = sum(
            status == "MATCHED" and truth.get(pair, "NOT_MATCH") == "NOT_MATCH"
            for pair, status in predictions.items()
        )
        unsafe = sum(
            status == "MATCHED" and truth.get(pair) == "REVIEW"
            for pair, status in predictions.items()
        )
        positive = sum(value == "MATCH" for value in truth.values())
        precision = tp / max(1, tp + fp + unsafe)
        recall = tp / max(1, positive)
        return {
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / max(1e-12, precision + recall),
            "false_merge_count": fp,
            "false_merge_rate": fp / max(1, tp + fp),
            "unsafe_auto_on_review": unsafe,
            "false_non_match_count": sum(
                status == "NOT_MATCHED" and truth.get(pair) == "MATCH"
                for pair, status in predictions.items()
            ),
            "missed_true_matches": sum(
                label == "MATCH" and pair not in predictions for pair, label in truth.items()
            ),
            "review_rate": sum(status == "POSSIBLE_MATCH" for status in predictions.values())
            / max(1, len(predictions)),
        }

    baseline = metrics({pair: value[1] for pair, value in results.items()})
    assert (
        baseline["false_merge_count"]
        == baseline["unsafe_auto_on_review"]
        == baseline["missed_true_matches"]
        == 0
    )
    sweeps = []
    for threshold in ["0.7", "0.8", "0.9", "0.95"]:
        predictions = {}
        for pair, (score, status, evidence) in results.items():
            predictions[pair] = (
                status
                if evidence["negative_keys"] or evidence["ambiguous_identity_rules"]
                else ("MATCHED" if score >= Decimal(threshold) else "POSSIBLE_MATCH")
            )
        sweeps.append(
            {
                "threshold": threshold,
                "offline_only": True,
                "strong_negative_and_ambiguity_blockers": True,
                **metrics(predictions),
            }
        )
    return {
        "scope": "synthetic benchmark, not customer Gold Reference; "
        "no production threshold selected",
        "profile_hash": PROFILE.digest(),
        "profile_version": PROFILE.version,
        "engine_version": PROFILE.engine_version,
        "left_records": len(left),
        "right_records": len(right),
        "candidates": len(results),
        "candidate_reduction_ratio": 1 - len(results) / (len(left) * len(right)),
        "signals_compared": dict(signals),
        "runtime_policy": PROFILE.threshold_policy,
        "metrics": baseline,
        "offline_threshold_sweeps": sweeps,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
