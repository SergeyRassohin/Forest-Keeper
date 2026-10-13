#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
(
  cd backend
  uv run --frozen bandit -r app migrations
)
(
  cd frontend
  npm run security:sast
)
