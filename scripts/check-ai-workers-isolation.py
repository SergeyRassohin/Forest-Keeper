"""Read-only current-profile egress probes; no inference, payload, credential or mutation."""

import argparse
import json
import re
import subprocess
from pathlib import Path

PROBE = """import json,os,socket,threading

def denied(host,port):
    try:
        connection=socket.create_connection((host,port),timeout=1)
        connection.close()
        return False
    except OSError:
        return True
resolved=[]
def resolve():
    try:
        socket.getaddrinfo('example.com',443)
        resolved.append(False)
    except OSError:
        resolved.append(True)
thread=threading.Thread(target=resolve,daemon=True)
thread.start()
thread.join(3)
print(json.dumps({
    'public_tcp_denied':denied('1.1.1.1',443),
    'public_dns_denied':bool(resolved and resolved[0]),
    'dns_finished':bool(resolved),
    'no_proxy':not any(os.getenv(key) for key in (
        'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'))
}))
"""


def docker(*argv, body=None):
    return subprocess.check_output(["docker", *argv], input=body, text=True, timeout=20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", args.project):
        parser.error("Invalid project name")
    expected = sorted([args.project + "_ai_private", args.project + "_default"])
    internal = {}
    for name in expected:
        internal[name] = (
            json.loads(docker("network", "inspect", "--format", "{{json .Internal}}", name)) is True
        )
    report = {
        "internal_networks": internal,
        "components": {},
        "passed": all(internal.values()),
    }
    for service in ("backend", "ai-embedding-worker", "ai-llm-worker"):
        name = args.project + "-" + service + "-1"
        result = json.loads(docker("exec", "-i", name, "python", "-", body=PROBE))
        result["networks"] = sorted(
            json.loads(docker("inspect", "--format", "{{json .NetworkSettings.Networks}}", name))
        )
        result["image"] = json.loads(docker("inspect", "--format", "{{json .Image}}", name))
        result["passed"] = (
            all(
                result[key]
                for key in (
                    "public_tcp_denied",
                    "public_dns_denied",
                    "dns_finished",
                    "no_proxy",
                )
            )
            and result["networks"] == expected
            and all(internal.values())
        )
        report["components"][service] = result
        report["passed"] = report["passed"] and result["passed"]
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("AI worker/backend egress " + ("PASS" if report["passed"] else "FAILED"))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
