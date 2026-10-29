"""Expected identity is configuration, not a claim that a runtime is healthy."""

import hashlib
import json
from functools import lru_cache
from typing import Literal

from app.ai import baseline
from app.ai.contracts import EmbeddingRequest, EmbeddingResponse, Facts, GeneratedClauses, ModelInfo


def schema_hash(schema: dict[str, object]) -> str:
    raw = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


@lru_cache(maxsize=2)
def schema_identity(component: Literal["embedding", "llm"]) -> tuple[str, str]:
    # Schema classes are immutable release configuration, never actor/client overrides.
    embedding = component == "embedding"
    input_schema = EmbeddingRequest if embedding else Facts
    output_schema = EmbeddingResponse if embedding else GeneratedClauses
    return (
        schema_hash(input_schema.model_json_schema()),
        schema_hash(output_schema.model_json_schema()),
    )


def expected_model_info(component: Literal["embedding", "llm"]) -> ModelInfo:
    embedding = component == "embedding"
    input_hash, output_hash = schema_identity(component)
    return ModelInfo(
        component=component,
        model_id=baseline.EMBEDDING_MODEL if embedding else baseline.LLM_MODEL,
        revision=baseline.EMBEDDING_REVISION if embedding else baseline.LLM_REVISION,
        artifact_sha256=baseline.EMBEDDING_SHA256 if embedding else baseline.LLM_SHA256,
        artifact_lock_sha256=baseline.ARTIFACT_LOCK_SHA256,
        dimensions=baseline.DIMENSIONS if embedding else None,
        configured_context_tokens=baseline.CONTEXT_TOKENS,
        preprocessing_version=baseline.PREPROCESSING,
        prompt_version=None if embedding else baseline.PROMPT_VERSION,
        prompt_sha256=None if embedding else baseline.PROMPT_SHA256,
        instruction_sha256=baseline.INSTRUCTION_SHA256 if embedding else None,
        runtime_versions=baseline.component_versions(component),
        input_schema_sha256=input_hash,
        output_schema_sha256=output_hash,
    )
