import json
import random
from collections import Counter
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import pytest
from pydantic import ValidationError

from app.matching.engine import (
    BlockIndex,
    Observation,
    Record,
    candidates_for,
    evaluate,
    fuzzy,
    ordered_pair,
    pair_id,
)
from app.matching.models import MatchStatus
from app.matching.profiles import MatchingProfile, catalog
from app.normalization.normalize import normalize
from app.normalization.profiles import catalog as normalization_catalog

DATA = Path(__file__).resolve().parents[2] / "tests/data/matching"
PROFILE = next(profile for profile in catalog().values() if profile.code == "synthetic-material")
NORMALIZATION = next(
    profile for profile in normalization_catalog().values() if profile.code == "synthetic-material"
)
NAMESPACE = UUID("e5f9bf0b-d098-5c73-875e-5562024303fb")


def record(values, label, source=1):
    raw_id = uuid5(NAMESPACE, label)
    entity_id = uuid5(raw_id, "normalization")
    rules = NORMALIZATION.bindings[0].fields
    observations = {}
    for rule in rules:
        result = normalize(values.get(rule.path[0]), rule)
        observations[rule.attribute_code] = Observation(
            result.value, result.quality, result.unit, str(uuid5(entity_id, rule.attribute_code))
        )
    return Record(raw_id, entity_id, UUID(int=source), observations)


def gold_records():
    rows = json.loads((DATA / "records.json").read_text())
    return [
        {value.raw_id: value for row in rows[side] if (value := record(row, row["extra"], source))}
        for side, source in [("left", 1), ("right", 2)]
    ]


def assessment(left, right, profile=PROFILE):
    return evaluate(
        left,
        right,
        profile,
        [],
        BlockIndex({left.raw_id: left}, profile),
        BlockIndex({right.raw_id: right}, profile),
    )


def test_unordered_pair_identity_and_self_rejection():
    a, b, run = uuid4(), uuid4(), uuid4()
    assert pair_id(run, a, b) == pair_id(run, b, a)
    assert ordered_pair(a, b) == tuple(sorted([a, b]))
    assert pair_id(uuid4(), a, b) != pair_id(run, a, b)
    with pytest.raises(ValueError):
        ordered_pair(a, a)


@pytest.mark.parametrize("quality", ["INVALID", "UNKNOWN", "WARNING"])
def test_untrusted_identifier_never_auto_matches(quality):
    a = record({"id": "X", "name": "Болт"}, "a")
    b = record({"id": "X", "name": "Болт"}, "b", 2)
    a.values["code"] = Observation("X", quality, None, "value")
    assert assessment(a, b)[1] == MatchStatus.POSSIBLE_MATCH


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_empty_identity_is_not_exact(value):
    a = record({"id": value, "name": "Болт"}, "a")
    b = record({"id": value, "name": "Болт"}, "b", 2)
    assert assessment(a, b)[1] == MatchStatus.POSSIBLE_MATCH


def test_explicit_composite_identity_and_strong_negative():
    a = record({"id": "X", "name": "Болт М8", "mass": "12,5 кг"}, "a")
    b = record({"id": "X", "name": "  Болт   М8 ", "mass": "12500 г"}, "b", 2)
    confidence, status, evidence = assessment(a, b)
    assert status == MatchStatus.MATCHED and confidence == Decimal(".95")
    assert evidence["signals"][2]["score"] == "1"
    b.values["code"] = Observation("Y", "VALID", None, "value")
    assert assessment(a, b)[1] == MatchStatus.NOT_MATCHED
    b.values["code"] = Observation("X", "VALID", None, "value")
    b.values["name"] = Observation("БОЛТ М10", "VALID", None, "value")
    assert assessment(a, b)[1] == MatchStatus.POSSIBLE_MATCH


def test_conflicting_identity_signal_is_ambiguous():
    profile = PROFILE.model_copy(update={"identity_rules": [["name"]]})
    a = record({"id": "X", "name": "Болт"}, "a")
    b = record({"id": "Y", "name": "Болт"}, "b", 2)
    assert assessment(a, b, profile)[1] == MatchStatus.POSSIBLE_MATCH
    assert assessment(a, b, profile)[2]["reason"] == "CONFLICTING_STRONG_SIGNALS"


@pytest.mark.parametrize("text", ["Écrou M8", "E\u0301CROU M8", "  écrou  m8 "])
def test_unicode_case_whitespace_fuzzy_equivalence(text):
    assert fuzzy(text, "M8 écrou") == 1


def test_score_reproducible_from_evidence_and_no_runtime_threshold():
    a = record({"id": "X", "name": "Болт М8", "mass": "12.5 кг"}, "a")
    b = record({"id": "X", "name": "Болт МВ", "mass": "12500 г"}, "b", 2)
    confidence, status, evidence = assessment(a, b)
    expected = (
        sum(Decimal(s["weighted_contribution"]) for s in evidence["signals"])
        / Decimal(evidence["weight_sum"])
    ).quantize(Decimal(".000001"))
    assert confidence == expected and status == MatchStatus.POSSIBLE_MATCH
    assert evidence["auto_match_threshold"] is None
    assert assessment(a, b) == assessment(a, b)
    assert json.loads(json.dumps(evidence)) == evidence


def test_profile_snapshot_version_and_invalid_threshold_rejected():
    assert MatchingProfile.model_validate(PROFILE.snapshot()).digest() == PROFILE.digest()
    assert PROFILE.model_copy(update={"version": "2"}).digest() != PROFILE.digest()
    with pytest.raises(ValidationError):
        MatchingProfile.model_validate({**PROFILE.snapshot(), "auto_match_threshold": ".9"})
    with pytest.raises(ValidationError):
        MatchingProfile.model_validate(
            {**PROFILE.snapshot(), "identity_rules": [["secret_unknown"]]}
        )


def test_blocking_degree_caps_overflow_and_self_source_safety():
    left = {}
    right = {}
    for index in range(8):
        a = record({"id": str(index), "name": "Болт М8"}, f"a{index}")
        b = record({"id": str(index), "name": "Болт М8"}, f"b{index}", 2)
        left[a.raw_id] = a
        right[b.raw_id] = b
    profile = PROFILE.model_copy(update={"max_block_size": 3, "max_candidates_per_record": 2})
    li, ri = BlockIndex(left, profile), BlockIndex(right, profile)
    degrees = Counter()
    for a in left.values():
        pairs, diagnostics = candidates_for(a, right, li, ri, degrees, profile)
        assert len(pairs) <= 2 and diagnostics["oversized_block_hits"] > 0
        assert all(b.source_id != a.source_id for b, _ in pairs)
    assert max(degrees.values()) <= 2
    same = next(iter(left.values()))
    assert candidates_for(same, {same.raw_id: same}, li, li, Counter(), profile)[0] == []


def test_gold_hard_negatives_have_no_false_auto_merge():
    left, right = gold_records()
    li, ri = BlockIndex(left, PROFILE), BlockIndex(right, PROFILE)
    labels = json.loads((DATA / "gold.json").read_text())
    truth = {
        (uuid5(NAMESPACE, row["a"]), uuid5(NAMESPACE, row["b"])): row["truth"]
        for row in labels["cases"]
    }
    degrees = Counter()
    statuses = Counter()
    for a in sorted(left):
        pairs, _ = candidates_for(left[a], right, li, ri, degrees, PROFILE)
        for b, blocks in pairs:
            _, status, evidence = evaluate(left[a], b, PROFILE, blocks, li, ri)
            statuses[status] += 1
            if status == MatchStatus.MATCHED:
                assert truth.get((a, b.raw_id), "NOT_MATCH") == "MATCH", evidence
            if truth.get((a, b.raw_id)) == "REVIEW":
                assert status == MatchStatus.POSSIBLE_MATCH
    assert all(statuses[value] > 0 for value in MatchStatus)


def test_seeded_fuzzy_limits_and_precision():
    rng = random.Random(4113)
    for _ in range(100):
        text = "".join(chr(rng.randrange(0x110000)) for _ in range(rng.randrange(1, 64)))
        assert Decimal(0) <= fuzzy(text, text) <= Decimal(1)
    a = record({"id": "X", "name": "x" * 5000}, "a")
    b = record({"id": "X", "name": "x" * 5000}, "b", 2)
    assert assessment(a, b)[1] == MatchStatus.POSSIBLE_MATCH


def test_fuzzy_is_symmetric_even_for_ambiguous_alignment():
    assert fuzzy("tide", "diet") == fuzzy("diet", "tide")
