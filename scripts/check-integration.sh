#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
env_file=${FK_ENV_FILE:-.env}
if [[ ! -f "$env_file" ]]; then
  echo 'Run scripts/dev-init.sh and docker compose up --build -d first.' >&2
  exit 1
fi
set -a
source "$env_file"
set +a
curl --fail --silent --show-error --retry 15 --retry-connrefused --retry-delay 1 \
  --cacert deploy/local/tls/dev.crt "${FK_E2E_BASE_URL:-https://localhost:8443}/api/v1/health"
(
  cd backend
  FK_TEST_INTEGRATION=1 uv run --frozen pytest -m integration
  uv run --frozen alembic current
)
(
  cd backend
  FK_TEST_INTEGRATION=1 uv run --frozen python -m tests.e2e_accounts prepare
)
cleanup() {
  (cd backend && FK_TEST_INTEGRATION=1 uv run --frozen python -m tests.e2e_accounts cleanup)
}
trap cleanup EXIT
(
  cd frontend
  npm run test:e2e
)
