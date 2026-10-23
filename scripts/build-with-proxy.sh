#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
# Only the proxy hostname and resolved IP are emitted internally; never print its URL.
proxy_host=$(python - <<'PY'
import os
from urllib.parse import urlsplit
print(urlsplit(os.environ.get('HTTPS_PROXY', '')).hostname or '')
PY
)
if [[ -z "$proxy_host" ]]; then
  echo 'HTTPS_PROXY must be provided by the environment for this build adapter.' >&2
  exit 1
fi
proxy_ip=$(getent ahostsv4 "$proxy_host" | awk 'NR==1 {address=$1} END {print address}')
if [[ -z "$proxy_ip" ]]; then
  echo 'Cannot resolve the environment proxy.' >&2
  exit 1
fi
export FK_BUILD_PROXY_HOST_ENTRY="$proxy_host=$proxy_ip"
docker compose -f compose.yaml -f deploy/proxy-build.compose.yaml build \
  --build-arg HTTPS_PROXY --build-arg HTTP_PROXY --build-arg NO_PROXY "$@"
