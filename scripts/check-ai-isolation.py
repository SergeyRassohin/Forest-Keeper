"""Operator-run negative connectivity checks inside the actual model containers.

No prompts, vectors, capability values, credentials or full Docker environments are emitted.
Run after --no-build --pull never startup; this does not certify signed distribution.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROBE = r"""
import http.client, json, os, socket, sys, threading
from pathlib import Path
from app.ai.transport import request_local, service_key, verify_model_info
from app.ai.contracts import ModelInfo
component, database_ip = sys.argv[1:]
port = 8091 if component == 'embedding' else 8092
info = ModelInfo.model_validate(request_local(
    f'http://127.0.0.1:{port}', service_key(Path(os.environ['FK_AI_KEY_FILE'])),
    '/internal/ai/model-info', timeout=2))
verify_model_info(info, component)
connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
connection.request('GET', '/internal/ai/health')
unauthorized = connection.getresponse().status
connection.close()
def denied(host, port):
    try:
        connection = socket.create_connection((host,port), timeout=1)
        connection.close()
        return False
    except OSError:
        return True
dns = []
def resolve():
    try:
        socket.getaddrinfo('example.com',443)
        dns.append(False)
    except OSError:
        dns.append(True)
thread = threading.Thread(target=resolve,daemon=True)
thread.start()
thread.join(3)
result = {
    'component': component, 'model':info.model_dump(mode='json'),
    'unauthenticated_denied':unauthorized in (401,403),
    'public_tcp_denied':denied('1.1.1.1',443),
    'database_tcp_denied':denied(database_ip,5432),
    'public_dns_denied':bool(dns and dns[0]),
    'dns_finished_within_seconds':3 if dns else None,
    'no_database_credentials':not any(k in os.environ for k in ('FK_DATABASE_URL','FK_REDIS_URL')),
    'no_outbound_proxy':not any(os.getenv(k) for k in (
        'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')),
    'offline_flags':all(os.getenv(k)=='1' for k in (
        'HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','DO_NOT_TRACK')),
}
print(json.dumps(result))
"""


def docker(*arguments: str, body: str | None = None) -> str:
    return subprocess.check_output(
        ["docker", *arguments], input=body, text=True, timeout=30
    ).strip()


def inspect(name: str, expression: str):
    return json.loads(docker("inspect", "--format", "{{json " + expression + "}}", name))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="fk-stage9")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", args.project):
        parser.error("Invalid Compose project name")
    report = {"passed": True, "components": []}
    for suffix in ("default", "ai_private"):
        assert json.loads(
            docker(
                "network",
                "inspect",
                "--format",
                "{{json .Internal}}",
                args.project + "_" + suffix,
            )
        ), "Outbound-capable network"
    database_ip = inspect(args.project + "-postgres-1", ".NetworkSettings.Networks")[
        args.project + "_default"
    ]["IPAddress"]
    for component in ("embedding", "llm"):
        container = args.project + "-fk-ai-" + component + "-1"
        config = inspect(container, ".HostConfig")
        networks = inspect(container, ".NetworkSettings.Networks")
        mounts = inspect(container, ".Mounts")
        private = (
            inspect(container, ".NetworkSettings.Ports") in ({}, None)
            and set(networks) == {args.project + "_ai_private"}
            and config["ReadonlyRootfs"]
            and config["CapDrop"] == ["ALL"]
            and config["Dns"] == ["127.0.0.1"]
            and "no-new-privileges:true" in config["SecurityOpt"]
            and inspect(container, ".Config.User") == "10001:10001"
            and all(not item["RW"] for item in mounts if item["Type"] == "bind")
            and {item["Destination"] for item in mounts if item["Type"] == "bind"}
            == {"/models/" + component, "/run/secrets/fk_ai_key"}
        )
        result = json.loads(
            docker(
                "exec",
                "-i",
                container,
                "python",
                "-",
                component,
                database_ip,
                body=PROBE,
            )
        )
        result["private_container_policy"] = private
        result["image"] = inspect(container, ".Image")
        checks = [
            "unauthenticated_denied",
            "public_tcp_denied",
            "database_tcp_denied",
            "public_dns_denied",
            "no_database_credentials",
            "no_outbound_proxy",
            "offline_flags",
            "private_container_policy",
        ]
        result["passed"] = all(result[key] for key in checks)
        report["components"].append(result)
        report["passed"] = report["passed"] and result["passed"]
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("AI isolation " + ("PASS" if report["passed"] else "FAILED"))
    if not report["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
