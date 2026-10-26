"""Container PID 1 owns its children and terminates actual timed-out model computation."""

import os
import signal
import subprocess  # nosec B404 - Own fixed executable argv, shell=False; no actor input.
import sys
import threading
import time
from pathlib import Path
from types import FrameType

from app.ai import baseline
from app.ai.artifacts import verify_component
from app.ai.contracts import AIError


class Children:
    """Only groups created by this supervisor may be signalled, never a configured PID."""

    def __init__(self) -> None:
        self.processes: list[subprocess.Popen[bytes]] = []

    def start(self, argv: list[str]) -> None:
        # Fixed deployment commands, no shell or actor-controlled executable/arguments.
        self.processes.append(subprocess.Popen(argv, start_new_session=True))  # nosec B603

    def failed(self) -> bool:
        return any(process.poll() is not None for process in self.processes)

    def stop(self, grace: float = 5) -> None:
        for process in reversed(self.processes):
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + grace
        for process in self.processes:
            try:
                process.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        # Also kill surviving descendants of a leader that has already exited.
        for process in reversed(self.processes):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)


def health() -> bool:
    from app.ai.transport import request_local, service_key

    component = os.environ.get("FK_AI_COMPONENT")
    if component not in {"embedding", "llm"}:
        return False
    port = 8091 if component == "embedding" else 8092
    try:
        result = request_local(
            f"http://127.0.0.1:{port}",
            service_key(Path(os.environ["FK_AI_KEY_FILE"])),
            "/internal/ai/health",
            timeout=1,
        )
        return result == {"status": "ok", "component": component}
    except (AIError, OSError, KeyError):
        return False


def main() -> int:
    if sys.argv[1:] == ["--health"]:
        return 0 if health() else 1
    if sys.argv[1:]:
        return 2
    stopped = threading.Event()

    def terminate(signum: int, frame: FrameType | None) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    children = Children()
    try:
        component = os.environ["FK_AI_COMPONENT"]
        if component not in {"embedding", "llm"}:
            raise AIError("AI_COMPONENT_UNAVAILABLE")
        root = Path(os.environ["FK_AI_MODEL_ROOT"])
        lock = Path(os.environ["FK_AI_ARTIFACT_LOCK"])
        fault = Path(os.environ["FK_AI_FAULT_FILE"])
        # A read-only image and private ephemeral /tmp prevent surviving stale markers.
        if fault.exists() or fault.is_symlink():
            raise AIError("AI_RUNTIME_CONFIGURATION_INVALID")
        if component == "llm":
            verify_component(root, lock, "llm")  # Before the native model loader too.
            children.start(
                [
                    "/app/native/llama-server",
                    "--model",
                    str(root / "llm/Qwen3-8B-Q4_K_M.gguf"),
                    "--alias",
                    baseline.LLM_MODEL + "@" + baseline.LLM_REVISION,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "19003",
                    "--ctx-size",
                    str(baseline.CONTEXT_TOKENS),
                    "--parallel",
                    "1",
                    "--threads",
                    "2",
                    "--threads-batch",
                    "2",
                    "--n-predict",
                    str(baseline.OUTPUT_TOKENS),
                    "--reasoning",
                    "off",
                    "--reasoning-budget",
                    "0",
                    "--chat-template-kwargs",
                    '{"enable_thinking":false}',
                    "--no-webui",
                    "--no-slots",
                    "--timeout",
                    "120",
                    "--log-disable",
                ]
            )
            from app.ai.runtime import llama_identity

            deadline = time.monotonic() + 180
            while not stopped.is_set() and not children.failed() and time.monotonic() < deadline:
                if llama_identity(root):
                    break
                stopped.wait(0.5)
            else:
                raise AIError("AI_NATIVE_STARTUP_UNAVAILABLE")
        port = "8091" if component == "embedding" else "8092"
        children.start(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.ai.runtime:runtime_app",
                "--factory",
                "--host",
                "0.0.0.0",  # nosec B104 - Keyed RPC on unpublished private container bridge only.
                "--port",
                port,
                "--no-access-log",
                "--timeout-graceful-shutdown",
                "2",
                "--limit-concurrency",
                "24",
            ]
        )
        # Enforce startup as well as runtime readiness. No model is required by core startup.
        startup_deadline = time.monotonic() + 180
        ready, failures = False, 0
        while not stopped.wait(0.5):
            if children.failed() or fault.exists():
                raise AIError("AI_RUNTIME_RESTART_REQUIRED")
            if health():
                ready, failures = True, 0
            elif ready:
                failures += 1
                if failures >= 4:
                    raise AIError("AI_RUNTIME_HEALTH_UNAVAILABLE")
            elif time.monotonic() >= startup_deadline:
                raise AIError("AI_RUNTIME_STARTUP_UNAVAILABLE")
        return 0
    except Exception:
        # Never emit exception details, environment, paths, requests or model output.
        print("AI_RUNTIME_STOPPED", file=sys.stderr, flush=True)
        return 1
    finally:
        children.stop()


if __name__ == "__main__":
    raise SystemExit(main())
