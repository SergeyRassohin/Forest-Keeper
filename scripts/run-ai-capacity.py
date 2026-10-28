"""Run an owned, resumable Stage9 fixture without Docker socket/model/repo secret mounts."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.getuid() == 0:
        raise SystemExit("Run the owned capacity helper as a non-root operator")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "index", "measure", "series"])
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--count", type=int, choices=[20, 100, 1000, 10000], default=10000)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", args.fixture):
        parser.error("Use a simple owned fixture label")
    base = ROOT / "work/stage9-capacity-private"
    if not (base / "base.env").is_file():
        raise SystemExit("Provide the private base.env with configured owned DB/Redis selectors")
    if args.phase == "series":
        capacity = json.loads((base / "actual-10k-v1/fixture.json").read_text())
        if capacity.get("phase") != "INDEXED" or capacity.get("target") != 10000:
            raise SystemExit("Finish the owned 10k backfill before a separate vertical series")
    for network in ("fk-stage9_default", "fk-stage9_ai_private"):
        info = json.loads(
            subprocess.check_output(
                ["docker", "network", "inspect", network, "--format", "{{json .}}"],
                text=True,
            )
        )
        if (
            not info.get("Internal")
            or info.get("Labels", {}).get("com.docker.compose.project") != "fk-stage9"
        ):
            raise SystemExit("The fixed owned development bridges must both be internal")
    fixture = base / args.fixture
    fixture.mkdir(mode=0o700, exist_ok=True)
    for name in ("imports", "evidence"):
        (fixture / name).mkdir(exist_ok=True)
    state_path = fixture / "fixture.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state.get("measurement_only") and args.phase != "measure":
            raise SystemExit("An adopted index profile permits measurement only")
    image = subprocess.check_output(
        ["docker", "inspect", "fk-stage9-backend-1", "--format", "{{.Image}}"],
        text=True,
    ).strip()
    hardware = {
        "host_cgroup_cpu_max": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "host_cgroup_memory_max": Path("/sys/fs/cgroup/memory.max").read_text().strip(),
        "runner_cpu_limit": 1,
        "runner_memory_bytes": 1073741824,
        "runner_base_image": image,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "application_source_sha256": {
            str(p.relative_to(ROOT / "backend/app")): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "backend/app").rglob("*.py"))
        },
        "model_containers": {},
    }
    for name in ("fk-ai-embedding", "fk-ai-llm", "postgres"):
        template = (
            '{"image":{{json .Image}},"nano_cpus":{{.HostConfig.NanoCpus}},'
            '"memory_bytes":{{.HostConfig.Memory}}}'
        )
        hardware["model_containers"][name] = json.loads(
            subprocess.check_output(
                ["docker", "inspect", "fk-stage9-" + name + "-1", "--format", template],
                text=True,
            )
        )
    hardware_path = fixture / "hardware.json"
    if hardware_path.exists():
        previous = json.loads(hardware_path.read_text())
        if {k: v for k, v in previous.items() if k != "source_commit"} != {
            k: v for k, v in hardware.items() if k != "source_commit"
        }:
            raise SystemExit("Fixture hardware/source profile changed; preserve it as a new run")
    else:
        with hardware_path.open("x") as out:
            json.dump(hardware, out, indent=2)
            out.write("\n")
    container = "fk-stage9-capacity-" + args.fixture + "-" + args.phase
    inspected = subprocess.run(
        [
            "docker",
            "container",
            "inspect",
            container,
            "--format",
            "{{json .Config.Labels}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspected.returncode == 0:
        labels = json.loads(inspected.stdout)
        if labels.get("com.forest-keeper.stage9-owned") != args.fixture:
            raise SystemExit("Existing container is not this owned capacity fixture")
        # Never silently restart an existing preparation or overlap an indexing driver.
        raise SystemExit("Container already exists; inspect its preserved status before resuming")
    command = [
        "docker",
        "create",
        "--name",
        container,
        "--label",
        "com.forest-keeper.stage9-owned=" + args.fixture,
        "--env-file",
        str(base / "base.env"),
        "--env",
        "FK_TEST_INTEGRATION=1",
        "--env",
        "PYTHONPATH=/test-dependencies:/repository/backend",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--network",
        "fk-stage9_default",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "128",
        "--memory",
        "1g",
        "--cpus",
        "1",
        "--dns",
        "127.0.0.1",
    ]
    mounts = [
        (ROOT / "backend/app", "/repository/backend/app", True),
        (ROOT / "backend/tests", "/repository/backend/tests", True),
        (ROOT / "backend/migrations", "/repository/backend/migrations", True),
        (ROOT / "backend/alembic.ini", "/repository/backend/alembic.ini", True),
        (ROOT / "docs/security", "/repository/docs/security", True),
        (ROOT / "tests/data", "/repository/tests/data", True),
        (
            ROOT / "models/artifacts.lock.json",
            "/repository/models/artifacts.lock.json",
            True,
        ),
        (
            ROOT / "backend/.venv/lib/python3.13/site-packages",
            "/test-dependencies",
            True,
        ),
        (Path("/tmp/fk-stage9-ai-service-key"), "/run/secrets/fk_ai_key", True),
        (fixture, "/private", False),
        (fixture / "imports", "/imports", False),
        (fixture / "evidence", "/evidence", False),
    ]
    for source, destination, readonly in mounts:
        if not source.exists() or source.is_symlink():
            raise SystemExit("Missing/unexpected symlink in fixed operator mount list")
        command += [
            "--mount",
            f"type=bind,src={source},dst={destination}" + (",readonly" if readonly else ""),
        ]
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        command += ["--env", name + "="]
    command += [
        "--env",
        "NO_PROXY=*",
        "--env",
        "no_proxy=*",
    ]
    if args.phase == "series":
        for name, value in {
            "FK_AI_TEST_REAL": "1",
            "FK_AI_TEST_EMBEDDING_ENDPOINT": "http://fk-ai-embedding:8091",
            "FK_AI_TEST_LLM_ENDPOINT": "http://fk-ai-llm:8092",
            "FK_AI_TEST_KEY_FILE": "/run/secrets/fk_ai_key",
            "FK_AI_SERIES_ROOT": "/evidence/llm-series",
        }.items():
            command += ["--env", name + "=" + value]
    command += [
        "--workdir",
        "/repository/backend",
        image,
        "python",
        "-m",
        "tests.benchmark_ai_real_series"
        if args.phase == "series"
        else "tests.benchmark_ai_capacity",
    ]
    if args.phase != "series":
        command.append(args.phase)
    if args.phase == "prepare":
        command.append(str(args.count))
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["docker", "network", "connect", "fk-stage9_ai_private", container], check=True)
    subprocess.run(["docker", "start", "--attach", container], check=True)
    exit_code = subprocess.check_output(
        ["docker", "inspect", container, "--format", "{{.State.ExitCode}}"], text=True
    ).strip()
    if exit_code != "0":
        raise SystemExit("Owned benchmark failed; its logs/data are preserved")


if __name__ == "__main__":
    main()
