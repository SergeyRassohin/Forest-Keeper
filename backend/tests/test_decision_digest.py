"""Persisted canonical hashes must survive the frozen-JSON performance path."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

import pytest
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.decisions.service import digest, digest_frozen_json


class UnusualEnum(StrEnum):
    def __new__(cls, value):
        member = str.__new__(cls, "encoded-" + value)
        member._value_ = value
        return member

    VALUE = "actual"


class TypedEvidence(BaseModel):
    observed_at: datetime
    mass: Decimal


@pytest.mark.parametrize(
    "value",
    [
        {"unicode": "Масса 🌲", "values": [None, True, False, 0, 1.0, 1e-6, -1e20]},
        {"source": {"_sa_internal": "hidden", "kept": ["_sa_value", {"_sa": 7}]}},
        {"identifier": UUID("00000000-0000-0000-0000-000000000001")},
        {"date": datetime(2026, 10, 28, tzinfo=UTC), "mass": Decimal("12.50")},
        {"state": UnusualEnum.VALUE},
        {1: "integer key", 2: "another"},
        {"model": TypedEvidence(observed_at=datetime(2026, 10, 28), mass=Decimal("1.25"))},
        {"nested": [{"context": {"version": 1, "normalized": "12.500"}}] * 20},
    ],
)
def test_frozen_digest_preserves_original_persisted_hash_contract(value):
    # Independent pre-optimization formula is the compatibility oracle, including
    # normalization/filtering that direct json.dumps cannot apply to typed inputs.
    original = hashlib.sha256(
        json.dumps(
            jsonable_encoder(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    assert digest(value) == original
    assert digest_frozen_json(value) == original


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_values_do_not_acquire_acceptable_hashes(number):
    for function in (digest, digest_frozen_json):
        with pytest.raises(ValueError):
            function({"nested": [number]})


def test_deep_valid_json_retains_original_hash_when_guard_exhausts_stack():
    value = 0
    for _ in range(500):
        value = [value]
    assert digest_frozen_json(value) == digest(value)


def test_cycles_remain_errors_in_both_hash_paths():
    value = []
    value.append(value)
    for function in (digest, digest_frozen_json):
        with pytest.raises(RecursionError):
            function(value)
