#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
(
  cd backend
  uv run --frozen pip-audit --path .venv/lib/python3.13/site-packages \
    --skip-editable --cache-dir "${TMPDIR:-/tmp}/forest-keeper-pip-audit"
)
(
  cd frontend
  npm audit --audit-level=high
)
