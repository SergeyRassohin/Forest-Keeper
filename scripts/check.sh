#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
(
  cd backend
  uv run --frozen ruff check .
  uv run --frozen ruff format --check .
  uv run --frozen mypy app
  uv run --frozen pytest -m 'not integration'
)
(
  cd frontend
  npm run lint
  npm test
  npm run build
  npm run typecheck:e2e
)
