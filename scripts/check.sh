#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 scripts/check-doc-links.py
python3 scripts/check-ui-gallery.py
bash -n scripts/capture-ui-gallery.sh
bash -n scripts/prepare-ai-native.sh scripts/prepare-ai-native-cache.sh scripts/build-ai-with-proxy.sh
uv run --with PyYAML==6.0.3 python -m unittest discover -s scripts -p test_models.py
(
  cd backend
  uv run --frozen ruff check .
  uv run --frozen ruff format --check .
  uv run --frozen ruff check ../scripts/check-production.py ../scripts/models.py ../scripts/check-doc-links.py ../scripts/test_models.py ../scripts/render-ui-gallery.py ../scripts/check-ui-gallery.py
  uv run --frozen ruff format --check ../scripts/check-production.py ../scripts/models.py ../scripts/check-doc-links.py ../scripts/test_models.py ../scripts/render-ui-gallery.py ../scripts/check-ui-gallery.py
  uv run --frozen ruff check ../scripts/check-ai-isolation.py ../scripts/check-ai-workers-isolation.py ../scripts/serve-ai-local.py
  uv run --frozen ruff format --check ../scripts/check-ai-isolation.py ../scripts/check-ai-workers-isolation.py ../scripts/serve-ai-local.py
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
