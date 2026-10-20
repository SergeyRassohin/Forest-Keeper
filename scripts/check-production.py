"""Disposable production-profile smoke; only synthetic secrets and own volumes."""

import argparse
import json
import os
import secrets
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-image", required=True)
    parser.add_argument("--frontend-image", required=True)
    args = parser.parse_args()
    project = "fk-prod-check-" + uuid4().hex
    with tempfile.TemporaryDirectory(prefix="fk-prod-check-") as directory:
        folder = Path(directory)
        password = secrets.token_hex(24)
        dsn = f"postgresql+psycopg://forest_keeper:{password}@postgres:5432/forest_keeper"
        # Docker Compose binds file secrets without remapping UID/mode. The test
        # files are readable by container UIDs; their host ancestor is private 0700.
        for name, value in [("postgres_password", password), ("fk_database_url", dsn)]:
            (folder / name).write_text(value)
            (folder / name).chmod(0o444)
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-sha256",
                "-nodes",
                "-days",
                "1",
                "-keyout",
                str(folder / "server.key"),
                "-out",
                str(folder / "server.crt"),
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost",
            ],
            check=True,
            capture_output=True,
        )
        (folder / "server.key").chmod(0o444)
        (folder / "server.crt").chmod(0o444)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        environment = {
            **os.environ,
            "FK_BACKEND_IMAGE": args.backend_image,
            "FK_FRONTEND_IMAGE": args.frontend_image,
            "FK_PROD_SECRETS_DIR": str(folder),
            "FK_HTTPS_PORT": str(port),
            "FK_BIND_ADDRESS": "127.0.0.1",
            "FK_ALLOWED_ORIGINS": json.dumps([f"https://localhost:{port}"]),
        }
        compose = ["docker", "compose", "-p", project, "-f", str(ROOT / "compose.production.yaml")]

        def run(command, *, check=True):
            result = subprocess.run(
                command, env=environment, cwd=ROOT, text=True, capture_output=True
            )
            if check and result.returncode:
                # Never propagate a command's arbitrary diagnostic with credentials.
                raise RuntimeError("Deployment check command failed: " + command[0])
            return result

        def execute(service, command, *, check=True):
            return run([*compose, "exec", "-T", service, *command], check=check)

        def probe(name):
            return execute(
                "backend", ["python", "-m", "app.worker_health", "--name", name], check=False
            )

        def wait_healthy(name):
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if probe(name).returncode == 0:
                    return
                time.sleep(0.5)
            raise RuntimeError("Worker did not become healthy")

        try:
            config = run([*compose, "config", "--format", "json"]).stdout
            assert password not in config and dsn not in config
            run([*compose, "up", "-d", "--wait", "--wait-timeout", "180"])
            context = ssl.create_default_context(cafile=str(folder / "server.crt"))
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(
                        f"https://localhost:{port}/api/v1/health", context=context, timeout=3
                    ) as response:
                        assert response.status == 200 and json.load(response)["status"] == "ok"
                    break
                except (OSError, urllib.error.URLError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.5)
            listing = run([*compose, "ps", "--format", "json"]).stdout.strip()
            try:
                identifiers = json.loads(listing)
            except json.JSONDecodeError:
                identifiers = [json.loads(line) for line in listing.splitlines()]
            # Compose emits either JSON lines or an array depending on version.
            if isinstance(identifiers, dict):
                identifiers = [identifiers]
            worker = next(item for item in identifiers if item["Service"] == "worker")
            inspected = json.loads(run(["docker", "inspect", worker["ID"]]).stdout)[0]
            name = inspected["Config"]["Hostname"]
            wait_healthy(name)
            for service in ["backend", "worker", "frontend", "postgres", "redis"]:
                identifier = run([*compose, "ps", "-q", service]).stdout.strip()
                info = json.loads(run(["docker", "inspect", identifier]).stdout)[0]
                assert password not in json.dumps(info["Config"]["Env"])
                assert dsn not in json.dumps(info["Config"]["Env"])
                host = info["HostConfig"]
                assert host["ReadonlyRootfs"] and host["Memory"] > 0 and host["NanoCpus"] > 0
                assert "ALL" in host["CapDrop"]
                assert execute(service, ["id", "-u"]).stdout.strip() != "0"
            assert (
                execute("backend", ["touch", "/app/should-not-write"], check=False).returncode != 0
            )
            execute("backend", ["touch", "/tmp/temporary-check"])
            execute(
                "backend",
                [
                    "python",
                    "-c",
                    """
import time
from redis import Redis
from rq import Queue
from app.common.config import Settings
r = Redis.from_url(Settings().redis_url.get_secret_value())
j = Queue('forest-keeper', connection=r).enqueue('operator.add', 2, 3)
try:
    end = time.monotonic() + 15
    while time.monotonic() < end:
        j.refresh()
        if j.is_finished or j.is_failed: break
        time.sleep(0.1)
    assert j.is_finished and j.return_value() == 5
finally:
    j.delete()
    r.close()
""",
                ],
            )
            # Freeze only our own synthetic worker. Age its technical heartbeat
            # rather than waiting 150 seconds; Docker must report unhealthy.
            run(["docker", "kill", "--signal=STOP", worker["ID"]])
            try:
                old = (datetime.now(UTC) - timedelta(seconds=151)).isoformat()
                execute("redis", ["redis-cli", "HSET", "rq:worker:" + name, "last_heartbeat", old])
                assert probe(name).returncode != 0
                end = time.monotonic() + 75
                while time.monotonic() < end:
                    info = json.loads(run(["docker", "inspect", worker["ID"]]).stdout)[0]
                    if info["State"]["Health"]["Status"] == "unhealthy":
                        break
                    time.sleep(1)
                else:
                    raise RuntimeError("Docker did not detect the stale worker")
            finally:
                run(["docker", "kill", "--signal=CONT", worker["ID"]], check=False)
            run([*compose, "stop", "-t", "10", "worker"])
            assert probe(name).returncode != 0
            run([*compose, "up", "-d", "--wait", "--wait-timeout", "60", "worker"])
            wait_healthy(name)
            # Persist only synthetic technical markers, then restart the services.
            execute(
                "postgres",
                [
                    "psql",
                    "-U",
                    "forest_keeper",
                    "-d",
                    "forest_keeper",
                    "-c",
                    "CREATE TABLE hardening_marker(value int); "
                    "INSERT INTO hardening_marker VALUES(42)",
                ],
            )
            execute("redis", ["redis-cli", "SET", "hardening:marker", "42"])
            run([*compose, "restart", "postgres", "redis", "backend", "worker"])
            run([*compose, "up", "-d", "--wait", "--wait-timeout", "180"])
            wait_healthy(name)
            assert (
                execute(
                    "postgres",
                    [
                        "psql",
                        "-U",
                        "forest_keeper",
                        "-d",
                        "forest_keeper",
                        "-Atc",
                        "SELECT value FROM hardening_marker",
                    ],
                ).stdout.strip()
                == "42"
            )
            assert execute("redis", ["redis-cli", "GET", "hardening:marker"]).stdout.strip() == "42"
            logs = run([*compose, "logs", "--no-color"]).stdout
            assert password not in logs and dsn not in logs
            print(
                "PASS: production config, HTTPS health, file secrets, non-root/read-only/resources"
            )
            print(
                "PASS: real RQ job; own worker healthy -> stale/unhealthy "
                "-> stopped -> restored healthy"
            )
            print(
                "PASS: PostgreSQL/Redis persistence after restart; "
                "no credential values in inspect/logs"
            )
        except Exception:
            logs = run([*compose, "logs", "--no-color", "--tail", "25"], check=False).stdout
            for value in [password, dsn]:
                logs = logs.replace(value, "REDACTED")
            print(logs)
            raise
        finally:
            run([*compose, "down", "--volumes", "--remove-orphans"], check=False)


if __name__ == "__main__":
    main()
