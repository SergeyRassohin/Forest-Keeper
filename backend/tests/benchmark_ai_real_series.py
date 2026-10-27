"""Twenty actual Registry/Qwen vertical observations, not a semantic benchmark.

Reuses the independently reviewed genuine-model test without provider/output mocks.
Each invocation owns a fresh disposable schema; reports/logs remain separate, including
failures. Run after main backfill to serialize access to the single embedding slot.
"""

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from tests.benchmark_ai_capacity import write_json

TARGET = (
    "tests/test_ai_real_integration.py::"
    "test_real_imports_precedents_qwen_retrieval_and_grounded_llm_leave_decision_to_human"
)


def run():
    if os.getenv("FK_TEST_INTEGRATION") != "1" or os.getenv("FK_AI_TEST_REAL") != "1":
        raise SystemExit("Explicit isolated actual-model series opt-in required")
    root = Path(os.environ["FK_AI_SERIES_ROOT"])
    root.mkdir(exist_ok=False)
    report = root / "series.json"
    rows = []
    result = {
        "kind": "actual-qwen-developer-vertical-timing-series-not-gold",
        "planned_observations": 20,
        "passed": False,
        "started_at": datetime.now(UTC).isoformat(),
        "series_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "vertical_test_sha256": hashlib.sha256(
            Path("tests/test_ai_real_integration.py").read_bytes()
        ).hexdigest(),
        "cache_limitation": "Persistent processes; no OS cache flush; first/later calls separate.",
        "model_load": "Runs after the 10k backfill; separate HTTPS core load may overlap LLM.",
        "transport": (
            "ASGI/real PG/Redis/RQ and actual private model RPC; "
            "separate HTTPS core load is not included here."
        ),
        "semantic_quality_evaluated": False,
        "production_accepted": False,
        "observations": rows,
    }
    write_json(report, result, exclusive=True)
    try:
        for number in range(1, 21):
            folder = root / ("attempt-" + str(number).zfill(2))
            folder.mkdir()
            env = os.environ.copy()
            env["PYTEST_ADDOPTS"] = ""
            env["FK_AI_REAL_REPORT_DIR"] = str(folder)
            row = {"attempt": number, "passed": False, "started_at": datetime.now(UTC).isoformat()}
            rows.append(row)
            write_json(report, result)
            print(json.dumps({"attempt": number, "phase": "started"}), flush=True)
            since = time.monotonic()
            try:
                with (folder / "private-test.log").open("x") as log:
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "pytest",
                            TARGET,
                            "-q",
                            "-x",
                            "--tb=short",
                            "--show-capture=no",
                            "-p",
                            "no:cacheprovider",
                            "-o",
                            "markers=integration: Requires owned PostgreSQL/Redis",
                        ],
                        env=env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=600,
                        check=False,
                    )
                row["returncode"] = completed.returncode
                if (folder / "stage9-real-vertical.json").exists():
                    row["actual_model_report"] = json.loads(
                        (folder / "stage9-real-vertical.json").read_text()
                    )
                raw = row.get("actual_model_report", {})
                row["passed"] = completed.returncode == 0 and raw.get("passed") is True
            except Exception as error:
                # No credentials, full SQL parameters, raw source, prompt or exception body.
                row["error_code"] = type(error).__name__[:64]
            row["elapsed_seconds"] = round(time.monotonic() - since, 4)
            row["ended_at"] = datetime.now(UTC).isoformat()
            write_json(report, result)
            print(
                json.dumps(
                    {
                        "attempt": number,
                        "passed": row["passed"],
                        "elapsed_seconds": row["elapsed_seconds"],
                    }
                ),
                flush=True,
            )
            if not row["passed"]:
                # Diagnose a real failure before sending another heavy inference request.
                break
    finally:
        times = [
            r["actual_model_report"]["llm_job_seconds"]
            for r in rows
            if "llm_job_seconds" in r.get("actual_model_report", {})
        ]
        result["completed_observations"] = sum("ended_at" in r for r in rows)
        result["failures"] = sum(not r["passed"] for r in rows)
        result["llm_observations_with_timing"] = len(times)
        if times:
            result["llm_p50_seconds"] = sorted(times)[math.ceil(0.5 * len(times)) - 1]
            result["llm_p95_seconds"] = sorted(times)[math.ceil(0.95 * len(times)) - 1]
            result["llm_max_seconds"] = max(times)
            result["first_llm_seconds"] = times[0]
        result["passed"] = (
            len(rows) == 20
            and result["completed_observations"] == 20
            and result["failures"] == 0
            and len(times) == 20
        )
        result["ended_at"] = datetime.now(UTC).isoformat()
        write_json(report, result)
    if not result["passed"]:
        raise SystemExit(
            "Actual timing series failed/incomplete; evidence retained without target changes"
        )


if __name__ == "__main__":
    run()
