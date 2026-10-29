"""Standalone isolated runtime. Never imported by the public backend application."""

import asyncio
import http.client
import importlib
import importlib.metadata
import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Protocol

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.ai import baseline
from app.ai.artifacts import verify_component
from app.ai.contracts import (
    AIError,
    EmbeddingRequest,
    Explanation,
    Facts,
    GeneratedClauses,
    ModelInfo,
    embedding_text,
    explanation_schema,
    llm_input,
    validate_explanation,
)
from app.ai.identity import expected_model_info as model_info
from app.ai.transport import service_key, vectors_from_response


class RuntimeEngine(Protocol):
    info: ModelInfo

    def embed(self, request: EmbeddingRequest) -> list[list[float]]: ...

    def explain(self, facts: Facts) -> Explanation: ...

    def ready(self) -> bool: ...


class EmbeddingEngine:
    def __init__(self, root: Path, lock: Path):
        verify_component(root, lock, "embedding")
        expected = baseline.component_versions("embedding")
        if any(importlib.metadata.version(name) != value for name, value in expected.items()):
            raise AIError("AI_RUNTIME_VERSION_MISMATCH")
        # ML dependencies belong to ai/uv.lock, never the public backend environment.
        torch = importlib.import_module("torch")
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        transformers = importlib.import_module("sentence_transformers")
        self.model: Any = transformers.SentenceTransformer(
            str(root / "embedding"),
            device="cpu",
            local_files_only=True,
            trust_remote_code=False,
            model_kwargs={"dtype": "float32", "use_safetensors": True},
        )
        if self.model.get_embedding_dimension() != baseline.DIMENSIONS:
            raise AIError("AI_INVALID_EMBEDDING")
        self.info = model_info("embedding")

    def embed(self, request: EmbeddingRequest) -> list[list[float]]:
        texts = [embedding_text(context, request.purpose) for context in request.contexts]
        total_tokens = 0
        for text in texts:
            tokens = self.model.tokenizer(text, truncation=False)["input_ids"]
            total_tokens += len(tokens)
            if total_tokens > baseline.INPUT_TOKENS:
                raise AIError("AI_INPUT_TOO_LARGE")
        result: list[list[float]] = self.model.encode(
            texts,
            batch_size=min(8, len(texts)),
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
            precision="float32",
        ).tolist()
        return result

    def explain(self, facts: Facts) -> Explanation:
        raise AIError("AI_COMPONENT_UNAVAILABLE")

    def ready(self) -> bool:
        return True


def native_request(path: str, payload: dict[str, Any], deadline: float) -> dict[str, Any]:
    """Native llama server is loopback-only in the same isolated LLM container."""
    if path not in {"/apply-template", "/tokenize", "/v1/chat/completions"}:
        raise AIError("AI_INVALID_REQUEST")
    connection = http.client.HTTPConnection(
        "127.0.0.1", 19003, timeout=max(0.001, deadline - time.monotonic())
    )
    try:
        connection.request(
            "POST", path, json.dumps(payload).encode(), {"Content-Type": "application/json"}
        )
        sock = connection.sock
        if sock is not None:
            sock.settimeout(max(0.001, deadline - time.monotonic()))
        response = connection.getresponse()
        parts, size = [], 0
        while size <= baseline.OUTPUT_BYTES:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AIError("AI_TIMEOUT")
            if sock is not None:
                sock.settimeout(remaining)
            chunk = response.read1(min(65536, baseline.OUTPUT_BYTES + 1 - size))
            if not chunk:
                break
            parts.append(chunk)
            size += len(chunk)
        if response.status != 200 or size > baseline.OUTPUT_BYTES:
            raise AIError("AI_UNAVAILABLE")
        result = json.loads(b"".join(parts))
        if not isinstance(result, dict):
            raise AIError("AI_INVALID_RESPONSE")
        return result
    except AIError:
        raise
    except (OSError, ValueError, http.client.HTTPException):
        raise AIError("AI_UNAVAILABLE") from None
    finally:
        connection.close()


def llama_identity(root: Path) -> bool:
    connection = http.client.HTTPConnection("127.0.0.1", 19003, timeout=0.75)
    try:
        connection.request("GET", "/props")
        response = connection.getresponse()
        raw = response.read(65537)
        if response.status != 200 or len(raw) > 65536:
            return False
        props = json.loads(raw)
        return bool(
            Path(props["model_path"]).resolve() == (root / "llm" / "Qwen3-8B-Q4_K_M.gguf").resolve()
            and props["model_alias"] == baseline.LLM_MODEL + "@" + baseline.LLM_REVISION
            and props["default_generation_settings"]["n_ctx"] == baseline.CONTEXT_TOKENS
            and props["total_slots"] == 1
            and baseline.LLAMA_COMMIT[:9] in props["build_info"]
        )
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
        return False
    finally:
        connection.close()


class LlamaEngine:
    def __init__(self, root: Path, lock: Path):
        verify_component(root, lock, "llm")
        self.root = root
        if not llama_identity(root):
            raise AIError("AI_MODEL_IDENTITY_MISMATCH")
        self.info = model_info("llm")

    def ready(self) -> bool:
        return llama_identity(self.root)

    def embed(self, request: EmbeddingRequest) -> list[list[float]]:
        raise AIError("AI_COMPONENT_UNAVAILABLE")

    def explain(self, facts: Facts) -> Explanation:
        deadline = time.monotonic() + 120
        if not self.ready():
            raise AIError("AI_MODEL_IDENTITY_MISMATCH")
        messages = [
            {"role": "system", "content": baseline.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(llm_input(facts), ensure_ascii=False)},
        ]
        template = native_request(
            "/apply-template",
            {"messages": messages, "chat_template_kwargs": {"enable_thinking": False}},
            deadline,
        )
        if not isinstance(template.get("prompt"), str):
            raise AIError("AI_INVALID_RESPONSE")
        tokenized = native_request(
            "/tokenize", {"content": template["prompt"], "add_special": False}, deadline
        )
        tokens = tokenized.get("tokens")
        if not isinstance(tokens, list) or len(tokens) > baseline.INPUT_TOKENS:
            raise AIError("AI_INPUT_TOO_LARGE")
        logging.getLogger(__name__).warning("AI_LLM_INPUT_TOKENS count=%d", len(tokens))
        result = native_request(
            "/v1/chat/completions",
            {
                "model": baseline.LLM_MODEL + "@" + baseline.LLM_REVISION,
                "messages": messages,
                "chat_template_kwargs": {"enable_thinking": False},
                "temperature": 0.2,
                "max_tokens": baseline.OUTPUT_TOKENS,
                "stream": False,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "GroundedExplanation",
                        "strict": True,
                        "schema": explanation_schema(facts),
                    },
                },
            },
            deadline,
        )
        try:
            choice = result["choices"][0]
            # Fixed metadata only; never log generated text, IDs, prompt or arbitrary native values.
            usage = result.get("usage", {})
            completion = usage.get("completion_tokens") if isinstance(usage, dict) else None
            if type(completion) is int and 0 <= completion <= baseline.OUTPUT_TOKENS:
                logging.getLogger(__name__).warning("AI_LLM_OUTPUT_TOKENS count=%d", completion)
            if choice.get("finish_reason") != "stop":
                raise AIError("AI_INCOMPLETE_EXPLANATION")
            generated = GeneratedClauses.model_validate_json(choice["message"]["content"])
            output = Explanation(
                **{
                    name: getattr(facts, name)
                    for name in (
                        "conflict_id",
                        "context_fingerprint",
                        "status",
                        "action",
                        "reason_code",
                    )
                },
                clauses=generated.clauses,
            )
            if not self.ready():
                raise AIError("AI_MODEL_IDENTITY_MISMATCH")
            return validate_explanation(output, facts)
        except (KeyError, IndexError, TypeError, ValidationError):
            raise AIError("AI_INVALID_RESPONSE") from None


class PrivateBoundary:
    def __init__(self, app: ASGIApp, key: bytes):
        self.app, self.key = app, key
        self.pending = asyncio.BoundedSemaphore(8)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        supplied = headers.get(b"x-fk-ai-key", b"")
        if len(supplied) > 256 or not secrets.compare_digest(supplied, self.key):
            await JSONResponse({"reason_code": "AI_ACCESS_DENIED"}, status_code=403)(
                scope, receive, send
            )
            return
        try:
            await asyncio.wait_for(self.pending.acquire(), timeout=0.01)
        except TimeoutError:
            await JSONResponse({"reason_code": "AI_BUSY"}, status_code=429)(scope, receive, send)
            return
        parts, size = [], 0
        try:
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    size += len(chunk)
                    if size > baseline.INPUT_BYTES:
                        await JSONResponse(
                            {"reason_code": "AI_INPUT_TOO_LARGE"},
                            status_code=413,
                            headers={"Connection": "close"},
                        )(scope, receive, send)
                        return
                    parts.append(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await JSONResponse(
                {"reason_code": "AI_INPUT_TIMEOUT"},
                status_code=408,
                headers={"Connection": "close"},
            )(scope, receive, send)
            return
        finally:
            self.pending.release()
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": b"".join(parts), "more_body": False}

        await self.app(scope, bounded_receive, send)


def create_runtime(
    engine: RuntimeEngine,
    key: bytes,
    *,
    fault_file: Path | None = None,
    timeout_seconds: float = 118,
) -> FastAPI:
    if not 32 <= len(key) <= 256:
        raise AIError("AI_SERVICE_KEY_INVALID")
    if not 0 < timeout_seconds <= 118 or (fault_file is not None and fault_file.exists()):
        raise AIError("AI_RUNTIME_CONFIGURATION_INVALID")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(PrivateBoundary, key=key)
    admission = threading.BoundedSemaphore(1)
    faulted = threading.Event()

    def fault() -> None:
        faulted.set()
        if fault_file is not None:
            try:
                fd = os.open(
                    fault_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                os.close(fd)
            except OSError:
                logging.getLogger(__name__).warning("AI_SUPERVISOR_MARKER_UNAVAILABLE")

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Any, error: Any) -> JSONResponse:
        return JSONResponse({"reason_code": "AI_INVALID_REQUEST"}, status_code=422)

    @app.get("/internal/ai/health", response_model=None)
    def health() -> dict[str, str] | JSONResponse:
        if faulted.is_set() or not engine.ready():
            return JSONResponse({"reason_code": "AI_UNAVAILABLE"}, status_code=503)
        return {"status": "ok", "component": engine.info.component}

    @app.get("/internal/ai/model-info", response_model=None)
    def info() -> ModelInfo | JSONResponse:
        if faulted.is_set() or not engine.ready():
            return JSONResponse({"reason_code": "AI_UNAVAILABLE"}, status_code=503)
        return engine.info

    @app.post("/internal/ai/embed", response_model=None)
    async def embed(body: EmbeddingRequest) -> dict[str, Any] | JSONResponse:
        if faulted.is_set():
            return JSONResponse({"reason_code": "AI_UNAVAILABLE"}, status_code=503)
        if not admission.acquire(blocking=False):
            return JSONResponse({"reason_code": "AI_BUSY"}, status_code=429)
        try:
            vectors = await asyncio.wait_for(
                asyncio.to_thread(engine.embed, body), timeout=timeout_seconds
            )
            result = {"vectors": vectors, "model": engine.info.model_dump(mode="json")}
            vectors_from_response(result, len(body.contexts))
            return result
        except TimeoutError:
            fault()
            return JSONResponse({"reason_code": "AI_TIMEOUT"}, status_code=503)
        except asyncio.CancelledError:
            fault()  # to_thread is still running until the supervisor terminates this process.
            raise
        except Exception:
            return JSONResponse({"reason_code": "AI_UNAVAILABLE"}, status_code=503)
        finally:
            admission.release()

    @app.post("/internal/ai/recommend", response_model=None)
    @app.post("/internal/ai/explain", response_model=None)
    async def explain(body: Facts) -> dict[str, Any] | JSONResponse:
        if faulted.is_set():
            return JSONResponse({"reason_code": "EXPLANATION_UNAVAILABLE"}, status_code=503)
        if not admission.acquire(blocking=False):
            return JSONResponse({"reason_code": "AI_BUSY"}, status_code=429)
        try:
            generated = await asyncio.wait_for(
                asyncio.to_thread(engine.explain, body), timeout=timeout_seconds
            )
            output = validate_explanation(generated, body)
            return {
                "explanation": output.model_dump(mode="json"),
                "model": engine.info.model_dump(mode="json"),
            }
        except TimeoutError:
            fault()
            return JSONResponse({"reason_code": "AI_TIMEOUT"}, status_code=503)
        except asyncio.CancelledError:
            fault()
            raise
        except Exception:
            return JSONResponse({"reason_code": "EXPLANATION_UNAVAILABLE"}, status_code=503)
        finally:
            admission.release()

    return app


def runtime_app() -> FastAPI:
    # Deployment sets these before interpreter startup too; no auto-download fallback.
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
        os.environ[name] = "1"
    os.environ["DO_NOT_TRACK"] = "1"
    root = Path(os.environ["FK_AI_MODEL_ROOT"])
    lock = Path(os.environ["FK_AI_ARTIFACT_LOCK"])
    component = os.environ["FK_AI_COMPONENT"]
    engine: RuntimeEngine
    if component == "embedding":
        engine = EmbeddingEngine(root, lock)
    elif component == "llm":
        engine = LlamaEngine(root, lock)
    else:
        raise AIError("AI_COMPONENT_UNAVAILABLE")
    fault_path = os.environ.get("FK_AI_FAULT_FILE")
    return create_runtime(
        engine,
        service_key(Path(os.environ["FK_AI_KEY_FILE"])),
        fault_file=Path(fault_path) if fault_path else None,
    )
