#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
proxy_host=$(python3 - <<'PY'
import os
from urllib.parse import urlsplit
print(urlsplit(os.environ.get('HTTPS_PROXY', '')).hostname or '')
PY
)
[[ -n "$proxy_host" ]] || { echo 'Inherited HTTPS proxy required.' >&2; exit 1; }
proxy_ip=$(getent ahostsv4 "$proxy_host" | awk 'NR==1 {address=$1} END {print address}')
[[ -n "$proxy_ip" ]] || { echo 'Cannot resolve the environment proxy.' >&2; exit 1; }
export FK_BUILD_PROXY_HOST_ENTRY="$proxy_host=$proxy_ip"
if [[ "$#" == 0 ]]; then set -- fk-ai-embedding fk-ai-llm; fi
docker compose --env-file "${FK_ENV_FILE:-.env}" -f compose.yaml \
  -f deploy/ai.compose.yaml -f deploy/ai-proxy-build.compose.yaml --profile ai build \
  --build-arg HTTPS_PROXY --build-arg HTTP_PROXY --build-arg NO_PROXY \
  "$@"
