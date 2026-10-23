"""Bounded offline provider contract. No model runtime or network client."""

import hashlib
import math
import re
import struct
from typing import Any, Protocol

from app.common.config import Settings
from app.decisions.service import digest

DIMENSIONS = 1024
SCHEMA = "retrieval-context-v1"
PREPROCESSING = "nfc-semantic-sort-v1"
MODEL = "forest-keeper/deterministic-test-embedding"
REVISIONS = {name: hashlib.sha256(name.encode()).hexdigest() for name in ("test-v1", "test-v2")}
THRESHOLD = 0.85


class ProviderError(Exception):
    """Sanitized operational failure; never contains the embedding input."""


class EmbeddingProvider(Protocol):
    def embed(self, features: dict[str, Any]) -> list[float]: ...


def validate_vector(values: list[float]) -> list[float]:
    if len(values) != DIMENSIONS or any(not math.isfinite(x) for x in values):
        raise ProviderError("INVALID_EMBEDDING")
    norm = math.sqrt(sum(x * x for x in values))
    if not math.isfinite(norm) or norm < 1e-12:
        raise ProviderError("INVALID_EMBEDDING")
    return [struct.unpack("f", struct.pack("f", x / norm))[0] for x in values]


def vector_hash(values: list[float]) -> str:
    """Matches public.vector_send binary representation, including dimension header."""
    return hashlib.sha256(
        struct.pack(">hh", DIMENSIONS, 0) + struct.pack(">1024f", *values)
    ).hexdigest()


def permitted(settings: Settings) -> bool:
    return (
        settings.deployment_mode in {"development", "test"}
        and settings.similarity_provider == "test"
        and settings.similarity_allow_test_provider
    )


class TestProvider:
    """Synthetic fixtures only. Hash vectors do not establish semantic quality."""

    def __init__(self, revision: str):
        if revision not in REVISIONS.values():
            raise ProviderError("UNSUPPORTED_VERSION")
        self.revision = revision

    def embed(self, features: dict[str, Any]) -> list[float]:
        if features.get("synthetic") is not True:
            raise ProviderError("SYNTHETIC_ONLY")
        vector = [0.0] * DIMENSIONS
        weighted = [(token, 4.0) for token in re.findall(r"\w+", features["subject"])]
        weighted += [("observation:" + digest(x), 1.0) for x in features["observations"]]
        for token, weight in weighted:
            hashed = hashlib.sha256((self.revision + ":" + token).encode()).digest()
            vector[int.from_bytes(hashed[:4], "big") % DIMENSIONS] += weight
        return validate_vector(vector)


def provider(settings: Settings, revision: str) -> EmbeddingProvider:
    if not permitted(settings):
        raise ProviderError("PROVIDER_UNAVAILABLE")
    return TestProvider(revision)
