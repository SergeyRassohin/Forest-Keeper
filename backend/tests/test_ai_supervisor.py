"""Actual owned subprocess termination; no model weights or external services required."""

import signal
import sys
import time
from pathlib import Path

from app.ai import supervisor


def test_supervisor_terminates_stubborn_children_and_their_descendants(tmp_path):
    marker = tmp_path / "child"
    staged = str(marker) + ".tmp"
    script = (
        "import os,signal,time,pathlib; "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); child=os.fork(); "
        f"pathlib.Path({staged!r}).write_text(str(os.getpid())) if child==0 else None; "
        f"os.replace({staged!r},{str(marker)!r}) if child==0 else None; "
        "time.sleep(30)"
    )
    children = supervisor.Children()
    children.start([sys.executable, "-c", script])
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        descendant = int(marker.read_text())
        leader = children.processes[0]
        started = time.monotonic()
        children.stop(grace=0.1)
        assert time.monotonic() - started < 3
        assert leader.returncode == -signal.SIGKILL
        status = Path(f"/proc/{descendant}/stat")
        deadline = time.monotonic() + 0.5
        # SIGKILL delivery/reaping is asynchronous even after the leader has been reaped.
        while True:
            try:
                state = status.read_text().split()[2]
            except (FileNotFoundError, ProcessLookupError):
                break  # Reaped between lookup/open/read is successful termination.
            if state == "Z":
                break
            assert time.monotonic() < deadline, "Descendant survived the bounded group kill"
            time.sleep(0.005)
    finally:
        children.stop(grace=0.1)


def test_fault_marker_stops_actual_gateway_process_and_exits_nonzero(tmp_path, monkeypatch):
    fault = tmp_path / "fault"
    monkeypatch.setenv("FK_AI_COMPONENT", "embedding")
    monkeypatch.setenv("FK_AI_MODEL_ROOT", str(tmp_path))
    monkeypatch.setenv("FK_AI_ARTIFACT_LOCK", str(tmp_path / "unused-lock"))
    monkeypatch.setenv("FK_AI_FAULT_FILE", str(fault))
    monkeypatch.setattr(sys, "argv", ["supervisor"])
    monkeypatch.setattr(supervisor, "health", lambda: False)
    child_set = supervisor.Children()
    real_start = child_set.start

    def start_stub_runtime(argv):
        assert "app.ai.runtime:runtime_app" in argv
        real_start(
            [
                sys.executable,
                "-c",
                "import pathlib,signal,time; "
                "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                f"pathlib.Path({str(fault)!r}).touch(); time.sleep(30)",
            ]
        )

    monkeypatch.setattr(child_set, "start", start_stub_runtime)
    monkeypatch.setattr(supervisor, "Children", lambda: child_set)
    previous_term = signal.getsignal(signal.SIGTERM)
    previous_int = signal.getsignal(signal.SIGINT)
    try:
        started = time.monotonic()
        assert supervisor.main() == 1
        assert time.monotonic() - started < 8
        assert child_set.processes[0].returncode == -signal.SIGKILL
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        signal.signal(signal.SIGINT, previous_int)
        child_set.stop(grace=0.1)
        assert not any(process.poll() is None for process in child_set.processes)
