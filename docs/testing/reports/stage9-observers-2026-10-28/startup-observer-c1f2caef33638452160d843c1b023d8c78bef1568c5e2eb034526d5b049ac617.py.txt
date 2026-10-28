"""One known-idle owned LLM process restart with an archived exact observer source.

Run only after the main vector backfill. This measures coarse health-check readiness,
not OS/disk cold-cache latency or a production hardware guarantee.
"""

import hashlib
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from tests.benchmark_ai_capacity import write_json
from tests.benchmark_ai_https_core import FIXTURE

NAME = "fk-stage9-fk-ai-llm-1"


def main():
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Explicit owned-development restart opt-in required")
    fixture = json.loads((FIXTURE / "fixture.json").read_text())
    assert fixture["kind"] == "owned-stage9-distinct-file-capacity-v1-not-gold"
    assert fixture["phase"] == "INDEXED" and fixture["target"] == 10000
    label = subprocess.check_output(
        [
            "docker",
            "inspect",
            NAME,
            "--format",
            '{{index .Config.Labels "com.docker.compose.project"}}',
        ],
        text=True,
    ).strip()
    assert label == "fk-stage9"
    cpu = subprocess.check_output(
        ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}", NAME], text=True
    ).strip()
    if float(cpu.rstrip("%")) >= 10:
        raise SystemExit("The owned LLM is busy; do not interrupt inference")
    image = subprocess.check_output(
        ["docker", "inspect", NAME, "--format", "{{.Image}}"], text=True
    ).strip()
    source = Path(__file__).read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    source_path = FIXTURE / "evidence" / ("startup-observer-" + digest + ".py.txt")
    if source_path.exists():
        assert source_path.read_bytes() == source
    else:
        with source_path.open("xb") as out:
            out.write(source)
    report = FIXTURE / "evidence" / ("llm-startup-" + uuid4().hex + ".json")
    result = {
        "passed": False,
        "kind": "owned-llm-process-startup-not-os-cold-cache",
        "observer_sha256": digest,
        "observer_artifact": source_path.name,
        "model_image": image,
        "started_at": datetime.now(UTC).isoformat(),
        "os_cache_flushed": False,
        "production_accepted": False,
    }
    write_json(report, result, exclusive=True)
    began = time.monotonic()
    try:
        subprocess.run(
            ["docker", "restart", "--timeout", "10", NAME],
            check=True,
            stdout=subprocess.DEVNULL,
            timeout=30,
        )
        result["restart_command_seconds"] = round(time.monotonic() - began, 4)
        while time.monotonic() - began < 180:
            health = json.loads(
                subprocess.check_output(
                    ["docker", "inspect", NAME, "--format", "{{json .State.Health}}"], text=True
                )
            )
            if health["Status"] == "healthy":
                good = [
                    entry
                    for entry in health.get("Log", [])
                    if entry.get("ExitCode") == 0
                    and datetime.fromisoformat(entry["End"].replace("Z", "+00:00"))
                    > datetime.fromisoformat(result["started_at"])
                ]
                assert good
                result.update(
                    passed=True,
                    healthy_observed_at=datetime.now(UTC).isoformat(),
                    first_retained_successful_healthcheck_at=good[0]["End"],
                    restart_to_successful_healthcheck_seconds=round(
                        (
                            datetime.fromisoformat(good[0]["End"].replace("Z", "+00:00"))
                            - datetime.fromisoformat(result["started_at"])
                        ).total_seconds(),
                        4,
                    ),
                )
                break
            time.sleep(1)
        if not result["passed"]:
            result["error_code"] = "MODEL_NOT_READY_WITHIN_180_SECONDS"
    except Exception as error:
        result["error_code"] = type(error).__name__[:64]
    finally:
        write_json(report, result)
    print(json.dumps({"report": str(report.name), "passed": result["passed"]}))
    if not result["passed"]:
        raise SystemExit("Owned LLM readiness failed; preserve the observation")


if __name__ == "__main__":
    main()
