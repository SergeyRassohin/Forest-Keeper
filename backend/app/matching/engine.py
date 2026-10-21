import unicodedata
from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID, uuid5

from app.matching.models import MatchStatus
from app.matching.profiles import MatchingProfile
from app.normalization.normalize import bounded_decimal, decimal_text

SCALE = Decimal("0.000001")
BlockKey = tuple[str, ...]


@dataclass(frozen=True)
class Observation:
    value: str | None
    quality: str
    unit: str | None
    value_id: str


@dataclass
class Record:
    raw_id: UUID
    entity_id: UUID
    source_id: UUID
    values: dict[str, Observation]


def ordered_pair(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    if a == b:
        raise ValueError("Self-pairs are forbidden")
    first, second = sorted((a, b))
    return first, second


def pair_id(run_id: UUID, a: UUID, b: UUID) -> UUID:
    first, second = ordered_pair(a, b)
    return uuid5(run_id, first.hex + second.hex)


def usable(record: Record, attribute: str, profile: MatchingProfile) -> str | None:
    value = record.values.get(attribute)
    if (
        value is None
        or value.quality != "VALID"
        or not isinstance(value.value, str)
        or not value.value.strip()
        or len(value.value) > profile.max_string_length
    ):
        return None
    return value.value


def tokens(text: str) -> list[str]:
    return sorted(unicodedata.normalize("NFC", text).casefold().split())


def block_keys(record: Record, profile: MatchingProfile) -> list[BlockKey]:
    keys: list[BlockKey] = []
    for index, rule in enumerate(profile.identity_rules):
        values = [usable(record, attribute, profile) for attribute in rule]
        if all(value is not None for value in values):
            keys.append(("identity", str(index), *(str(value) for value in values)))
    identifier = usable(record, profile.identifier_attribute, profile)
    if identifier is not None:
        keys.append(("identifier", profile.identifier_attribute, identifier))
        keys.append(
            ("identifier_prefix", profile.identifier_attribute, identifier[: profile.prefix_length])
        )
    name = usable(record, profile.name_attribute, profile)
    if name is not None:
        words = tokens(name)
        canonical = " ".join(words)
        if canonical:
            keys.append(("name_prefix", profile.name_attribute, canonical[: profile.prefix_length]))
        for word in sorted(set(words))[:2]:
            keys.append(("name_token", profile.name_attribute, word[: profile.prefix_length]))
    return sorted(set(keys))


class BlockIndex:
    def __init__(self, records: dict[UUID, Record], profile: MatchingProfile):
        self.counts: Counter[BlockKey] = Counter()
        self.buckets: dict[BlockKey, list[UUID]] = {}
        for identifier in sorted(records):
            for key in block_keys(records[identifier], profile):
                self.counts[key] += 1
                bucket = self.buckets.setdefault(key, [])
                if len(bucket) <= profile.max_block_size:
                    bucket.append(identifier)
        self.oversized_blocks = sum(n > profile.max_block_size for n in self.counts.values())


def candidates_for(
    left: Record,
    right: dict[UUID, Record],
    left_index: BlockIndex,
    right_index: BlockIndex,
    degrees: Counter[UUID],
    profile: MatchingProfile,
) -> tuple[list[tuple[Record, list[BlockKey]]], dict[str, int]]:
    reasons: dict[UUID, list[BlockKey]] = {}
    skipped_blocks = 0
    for key in block_keys(left, profile):
        if max(left_index.counts[key], right_index.counts[key]) > profile.max_block_size:
            skipped_blocks += 1
            continue
        for identifier in right_index.buckets.get(key, []):
            record = right[identifier]
            if identifier != left.raw_id and (
                profile.allow_same_source or record.source_id != left.source_id
            ):
                reasons.setdefault(identifier, []).append(key)
    priority = {
        kind: index
        for index, kind in enumerate(
            ["identity", "identifier", "identifier_prefix", "name_prefix", "name_token"]
        )
    }
    result: list[tuple[Record, list[BlockKey]]] = []
    omitted = 0
    for identifier in sorted(
        reasons, key=lambda value: (min(priority[key[0]] for key in reasons[value]), value)
    ):
        if (
            len(result) >= profile.max_candidates_per_record
            or degrees[identifier] >= profile.max_candidates_per_record
        ):
            omitted += 1
            continue
        result.append((right[identifier], reasons[identifier]))
        degrees[identifier] += 1
    return result, {"oversized_block_hits": skipped_blocks, "pairs_omitted_cap": omitted}


def fuzzy(a: str, b: str) -> Decimal:
    first, second = sorted((" ".join(tokens(a)), " ".join(tokens(b))))
    if not first or not second:
        return Decimal(0)
    count = sum(
        block.size
        for block in SequenceMatcher(None, first, second, autojunk=False).get_matching_blocks()
    )
    return (Decimal(count * 2) / Decimal(len(first) + len(second))).quantize(
        SCALE, rounding=ROUND_HALF_EVEN
    )


def evaluate(
    left: Record,
    right: Record,
    profile: MatchingProfile,
    blocks: list[BlockKey],
    left_index: BlockIndex,
    right_index: BlockIndex,
) -> tuple[Decimal, MatchStatus, dict[str, Any]]:
    signals = []
    total = Decimal(0)
    weight_sum = sum((Decimal(signal.weight) for signal in profile.signals), Decimal(0))
    with localcontext() as context:
        context.prec = 48
        for definition in profile.signals:
            attribute = definition.attribute_code
            a, b = usable(left, attribute, profile), usable(right, attribute, profile)
            score: Decimal | None = None
            code = "MISSING_INVALID_OR_TOO_LONG"
            if a is not None and b is not None:
                if definition.algorithm == "exact":
                    score = Decimal(int(a == b))
                elif definition.algorithm == "token_sort_ratio":
                    score = fuzzy(a, b)
                else:
                    first, second = bounded_decimal(a), bounded_decimal(b)
                    units = [left.values[attribute].unit, right.values[attribute].unit]
                    if (
                        first is not None
                        and second is not None
                        and units == [definition.unit, definition.unit]
                    ):
                        score = Decimal(int(abs(first - second) <= Decimal(definition.tolerance)))
                code = "COMPARED" if score is not None else "TYPE_OR_UNIT_MISMATCH"
            weighted = (score or Decimal(0)) * Decimal(definition.weight)
            total += weighted
            signals.append(
                {
                    "attribute_code": attribute,
                    "algorithm": definition.algorithm,
                    "inputs": [a, b],
                    "value_ids": [
                        value.value_id if (value := record.values.get(attribute)) else None
                        for record in [left, right]
                    ],
                    "quality": [
                        value.quality if (value := record.values.get(attribute)) else "UNKNOWN"
                        for record in [left, right]
                    ],
                    "units": [
                        value.unit if (value := record.values.get(attribute)) else None
                        for record in [left, right]
                    ],
                    "score": decimal_text(score) if score is not None else None,
                    "weight": definition.weight,
                    "weighted_contribution": decimal_text(weighted),
                    "tolerance": definition.tolerance,
                    "canonical_unit": definition.unit,
                    "code": code,
                }
            )
        confidence = (total / weight_sum).quantize(SCALE, rounding=ROUND_HALF_EVEN)
    identities = []
    ambiguous = []
    for index, rule in enumerate(profile.identity_rules):
        identity_a = [usable(left, attribute, profile) for attribute in rule]
        identity_b = [usable(right, attribute, profile) for attribute in rule]
        if all(value is not None for value in identity_a) and identity_a == identity_b:
            key = ("identity", str(index), *(str(value) for value in identity_a))
            if left_index.counts[key] == right_index.counts[key] == 1:
                identities.append(index)
            else:
                ambiguous.append(index)
    negatives = [
        attribute
        for attribute in profile.strong_negative_keys
        if (a := usable(left, attribute, profile)) is not None
        and (b := usable(right, attribute, profile)) is not None
        and a != b
    ]
    if (identities or ambiguous) and negatives:
        status, reason = MatchStatus.POSSIBLE_MATCH, "CONFLICTING_STRONG_SIGNALS"
    elif negatives:
        status, reason = MatchStatus.NOT_MATCHED, "STRONG_KEY_DISAGREEMENT"
    elif identities and not ambiguous:
        status, reason = MatchStatus.MATCHED, "EXPLICIT_UNIQUE_IDENTITY_RULE"
    else:
        status, reason = (
            MatchStatus.POSSIBLE_MATCH,
            "AMBIGUOUS_IDENTITY" if ambiguous else "NO_APPROVED_FUZZY_THRESHOLD",
        )
    return (
        confidence,
        status,
        {
            "engine_version": profile.engine_version,
            "profile_hash": profile.digest(),
            "profile_version": profile.version,
            "threshold_policy": profile.threshold_policy,
            "threshold_decision": profile.threshold_decision,
            "auto_match_threshold": None,
            "review_threshold": None,
            "signals": signals,
            "weight_sum": decimal_text(weight_sum),
            "weighted_sum": decimal_text(total),
            "confidence": str(confidence),
            "blocking": [list(key) for key in blocks],
            "identity_rules_matched": identities,
            "ambiguous_identity_rules": ambiguous,
            "negative_keys": negatives,
            "initial_status": "POSSIBLE_MATCH",
            "computed_status": status.value,
            "reason": reason,
            "inputs": [
                {
                    "raw_record_id": str(record.raw_id),
                    "entity_id": str(record.entity_id),
                    "source_id": str(record.source_id),
                }
                for record in [left, right]
            ],
        },
    )
