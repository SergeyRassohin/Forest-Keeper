"""Fixed local transport, without redirects, public hosts or environment proxies."""

import http.client
import json
import math
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.ai import baseline
from app.ai.contracts import (
    AIError,
    EmbeddingResponse,
    Explanation,
    Facts,
    ModelInfo,
    validate_explanation,
)

HOSTS = {"127.0.0.1", "fk-ai-embedding", "fk-ai-llm"}
PORTS = {8091, 8092, 19001, 19002, 19003}
PATHS = {
    "/internal/ai/embed",
    "/internal/ai/explain",
    "/internal/ai/recommend",
    "/internal/ai/health",
    "/internal/ai/model-info",
}


def request_local(
    endpoint: str,
    key: bytes,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 120,
) -> dict[str, Any]:
    connection = None
    deadline = time.monotonic() + timeout
    try:
        address = urlsplit(endpoint)
        if (
            address.scheme != "http"
            or address.hostname not in HOSTS
            or address.port not in PORTS
            or address.username is not None
            or address.password is not None
            or address.path not in {"", "/"}
            or address.query
            or address.fragment
            or path not in PATHS
            or not 0 < timeout <= 120
            or len(key) < 32
            or len(key) > 256
            or not key.isascii()
        ):
            raise AIError("AI_TRANSPORT_CONFIGURATION_INVALID")
        body = (
            json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
            if payload is not None
            else None
        )
        if body is not None and len(body) > baseline.INPUT_BYTES:
            raise AIError("AI_INPUT_TOO_LARGE")
        connection = http.client.HTTPConnection(address.hostname, address.port, timeout=timeout)
        connection.request(
            "POST" if payload is not None else "GET",
            path,
            body,
            {"Content-Type": "application/json", "X-FK-AI-Key": key.decode("ascii")},
        )
        sock = connection.sock
        if sock is not None:
            sock.settimeout(max(0.001, deadline - time.monotonic()))
        response = connection.getresponse()
        parts = []
        size = 0
        while size <= baseline.OUTPUT_BYTES:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AIError("AI_UNAVAILABLE")
            if sock is not None:
                sock.settimeout(remaining)
            chunk = response.read1(min(65536, baseline.OUTPUT_BYTES + 1 - size))
            if not chunk:
                break
            parts.append(chunk)
            size += len(chunk)
        raw = b"".join(parts)
        if response.status != 200 or len(raw) > baseline.OUTPUT_BYTES:
            raise AIError("AI_UNAVAILABLE")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise AIError("AI_INVALID_RESPONSE")
        return result
    except AIError:
        raise
    except (OSError, ValueError, http.client.HTTPException):
        raise AIError("AI_UNAVAILABLE") from None
    finally:
        if connection is not None:
            connection.close()


def service_key(path: Path) -> bytes:
    try:
        if path.stat().st_size > 256 or not path.is_file() or path.is_symlink():
            raise AIError("AI_SERVICE_KEY_INVALID")
        value = path.read_bytes().strip()
        if not 32 <= len(value) <= 256 or not value.isascii() or any(x < 33 for x in value):
            raise AIError("AI_SERVICE_KEY_INVALID")
        return value
    except OSError:
        raise AIError("AI_SERVICE_KEY_UNAVAILABLE") from None


def verify_model_info(info: ModelInfo, component: str) -> None:
    model, revision, artifact = (
        (baseline.EMBEDDING_MODEL, baseline.EMBEDDING_REVISION, baseline.EMBEDDING_SHA256)
        if component == "embedding"
        else (baseline.LLM_MODEL, baseline.LLM_REVISION, baseline.LLM_SHA256)
    )
    if (
        info.component != component
        or info.model_id != model
        or info.revision != revision
        or info.artifact_sha256 != artifact
        or info.artifact_lock_sha256 != baseline.ARTIFACT_LOCK_SHA256
        or info.configured_context_tokens != baseline.CONTEXT_TOKENS
        or info.preprocessing_version != baseline.PREPROCESSING
        or info.runtime_versions != baseline.component_versions(component)
        or info.dimensions != (baseline.DIMENSIONS if component == "embedding" else None)
    ):
        raise AIError("AI_MODEL_IDENTITY_MISMATCH")


def vectors_from_response(raw: dict[str, Any], count: int) -> list[list[float]]:
    try:
        result = EmbeddingResponse.model_validate(raw)
        verify_model_info(result.model, "embedding")
        if len(result.vectors) != count:
            raise AIError("AI_INVALID_EMBEDDING")
        for vector in result.vectors:
            if (
                len(vector) != baseline.DIMENSIONS
                or any(not math.isfinite(x) for x in vector)
                or not 0.999 <= math.sqrt(sum(x * x for x in vector)) <= 1.001
            ):
                raise AIError("AI_INVALID_EMBEDDING")
        return result.vectors
    except (ValidationError, ValueError, OverflowError):
        raise AIError("AI_INVALID_EMBEDDING") from None


class LocalLLM:
    def __init__(self, endpoint: str, key_file: Path):
        self.endpoint, self.key_file = endpoint, key_file

    def explain(self, facts: Facts) -> Explanation:
        try:
            raw = request_local(
                self.endpoint,
                service_key(self.key_file),
                "/internal/ai/explain",
                facts.model_dump(mode="json"),
            )
            verify_model_info(ModelInfo.model_validate(raw["model"]), "llm")
            result = Explanation.model_validate(raw["explanation"])
            return validate_explanation(result, facts)
        except (KeyError, ValidationError):
            raise AIError("AI_INVALID_RESPONSE") from None
