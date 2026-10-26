"""Development-only loopback ingress to this project's internal Docker bridges.

Docker does not publish ports on an internal-only bridge. This fixed TCP relay keeps
all containers offline, preserves end-to-end TLS/cookie Origins and publishes no AI port.
Customer production ingress/firewall/installer acceptance remains separate.
"""

import argparse
import ipaddress
import json
import re
import select
import socket
import socketserver
import subprocess
import threading


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="forest-keeper")
    parser.add_argument("--https-port", type=int, default=8443)
    parser.add_argument(
        "--database-ports",
        action="store_true",
        help="Explicit local test/operator access",
    )
    parser.add_argument("--postgres-port", type=int, default=5432)
    parser.add_argument("--redis-port", type=int, default=6379)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", args.project):
        parser.error("Invalid Compose project name")
    if any(not 1024 <= p <= 65535 for p in (args.https_port, args.postgres_port, args.redis_port)):
        parser.error("Use unprivileged local ports")
    network = args.project + "_default"
    assert (
        subprocess.check_output(
            ["docker", "network", "inspect", "--format", "{{.Internal}}", network],
            text=True,
            timeout=10,
        ).strip()
        == "true"
    ), "Expected an internal-only application bridge"
    routes = [("frontend", args.https_port, 8443)]
    if args.database_ports:
        routes += [
            ("postgres", args.postgres_port, 5432),
            ("redis", args.redis_port, 6379),
        ]
    servers = []
    try:
        for service, listen_port, target_port in routes:
            raw = subprocess.check_output(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{json .NetworkSettings.Networks}}",
                    args.project + "-" + service + "-1",
                ],
                text=True,
                timeout=10,
            )
            address = json.loads(raw)[network]["IPAddress"]
            assert ipaddress.ip_address(address).is_private
            limit = threading.BoundedSemaphore(32)

            class Relay(socketserver.BaseRequestHandler):
                endpoint = (address, target_port)
                admission = limit

                def handle(self):
                    if not self.admission.acquire(blocking=False):
                        return
                    try:
                        with socket.create_connection(self.endpoint, timeout=3) as remote:
                            self.request.settimeout(5)
                            remote.settimeout(5)
                            peers = [self.request, remote]
                            while True:
                                ready, _, _ = select.select(peers, [], [], 60)
                                if not ready:
                                    break
                                for source in ready:
                                    chunk = source.recv(65536)
                                    if not chunk:
                                        return
                                    peers[1 if source is peers[0] else 0].sendall(chunk)
                    except (OSError, TimeoutError):
                        pass  # Fixed bounded failure, no payload/credential/error logging.
                    finally:
                        self.admission.release()

            class Server(socketserver.ThreadingTCPServer):
                allow_reuse_address = True
                daemon_threads = True

            server = Server(("127.0.0.1", listen_port), Relay)
            servers.append(server)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            print(f"Local {service} ingress ready on127.0.0.1:{listen_port}", flush=True)
        threading.Event().wait()
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
