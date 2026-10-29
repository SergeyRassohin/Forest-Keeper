"""Versioned test and local-Qwen adapters; inference runs only in bounded AI jobs."""

import hashlib
import math
import re
import struct
from typing import Any, Literal, Protocol

from pydantic import ValidationError

from app.ai import baseline
from app.ai.admission import prefix
from app.ai.contracts import AIError, EmbeddingRequest, semantic_context
from app.ai.transport import request_local, service_key, vectors_from_response
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
    def embed(
        self, features: dict[str, Any], *, purpose: Literal["document", "query"] = "document"
    ) -> list[float]: ...


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
    return settings.deployment_mode in {"development", "test"} and (
        (settings.similarity_provider == "test" and settings.similarity_allow_test_provider)
        or (settings.similarity_provider == "qwen-demo" and settings.similarity_allow_qwen_demo)
    )


class TestProvider:
    """Synthetic fixtures only. Hash vectors do not establish semantic quality."""

    def __init__(self, revision: str):
        if revision not in REVISIONS.values():
            raise ProviderError("UNSUPPORTED_VERSION")
        self.revision = revision

    def embed(
        self, features: dict[str, Any], *, purpose: Literal["document", "query"] = "document"
    ) -> list[float]:
        if features.get("synthetic") is not True:
            raise ProviderError("SYNTHETIC_ONLY")
        vector = [0.0] * DIMENSIONS
        weighted = [(token, 4.0) for token in re.findall(r"\w+", features["subject"])]
        weighted += [("observation:" + digest(x), 1.0) for x in features["observations"]]
        for token, weight in weighted:
            hashed = hashlib.sha256((self.revision + ":" + token).encode()).digest()
            vector[int.from_bytes(hashed[:4], "big") % DIMENSIONS] += weight
        return validate_vector(vector)


class QwenProvider:
    """Real model in explicitly isolated development mode; no production acceptance."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def embed_many(
        self,
        features: list[dict[str, Any]],
        *,
        purpose: Literal["document", "query"] = "document",
    ) -> list[list[float]]:
        try:
            request = EmbeddingRequest(
                purpose=purpose, contexts=[semantic_context(item) for item in features]
            )
            raw = request_local(
                self.settings.ai_embedding_endpoint,
                service_key(self.settings.ai_service_key_file),
                "/internal/ai/embed",
                request.model_dump(mode="json"),
            )
            return [validate_vector(v) for v in vectors_from_response(raw, len(features))]
        except (AIError, ValidationError):
            raise ProviderError("QWEN_EMBEDDING_UNAVAILABLE") from None

    def embed(
        self, features: dict[str, Any], *, purpose: Literal["document", "query"] = "document"
    ) -> list[float]:
        return self.embed_many([features], purpose=purpose)[0]


def revision_name(revision: str) -> str:
    if revision == baseline.EMBEDDING_REVISION:
        return "qwen-demo-v1"
    for name, value in REVISIONS.items():
        if revision == value:
            return name
    raise ProviderError("UNSUPPORTED_VERSION")


def provider(settings: Settings, revision: str) -> EmbeddingProvider:
    if not permitted(settings):
        raise ProviderError("PROVIDER_UNAVAILABLE")
    if settings.similarity_provider == "test":
        return TestProvider(revision)
    if revision != baseline.EMBEDDING_REVISION:
        raise ProviderError("UNSUPPORTED_VERSION")
    return QwenProvider(settings)


def inference_queue(settings: Settings) -> str:
    return (
        prefix(settings) + ":embedding"
        if settings.similarity_provider == "qwen-demo"
        else settings.import_queue_name
    )
