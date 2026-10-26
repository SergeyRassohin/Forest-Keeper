#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
repo_root=$PWD
env_file=${FK_ENV_FILE:-.env}
if [[ ! -f "$env_file" ]]; then
  echo 'Prepare a development environment file and build the frontend/backend images first.' >&2
  exit 1
fi
if [[ -e deploy/local/e2e.json ]]; then
  echo 'Another browser fixture exists. Finish its owner-run cleanup before capturing a gallery.' >&2
  exit 1
fi
if [[ -n "$(git status --porcelain -- frontend/src frontend/public/brand frontend/index.html frontend/vite.config.ts)" ]]; then
  echo 'Commit the frontend source/brand before capture so evidence has an exact source tree.' >&2
  exit 1
fi
npm --prefix frontend run build
set -a
source "$env_file"
set +a
export FK_TEST_INTEGRATION=1 FK_CAPTURE_UI=1
export FK_GALLERY_PORT=${FK_GALLERY_PORT:-18446}
if [[ ! "$FK_GALLERY_PORT" =~ ^[0-9]{4,5}$ ]] || (( FK_GALLERY_PORT > 65535 )); then
  echo 'FK_GALLERY_PORT must be a valid local high port.' >&2
  exit 1
fi
export FK_GALLERY_BACKEND_IMAGE=${FK_GALLERY_BACKEND_IMAGE:-forest-keeper-backend}
export FK_GALLERY_FRONTEND_IMAGE=${FK_GALLERY_FRONTEND_IMAGE:-forest-keeper-frontend}
export FK_GALLERY_FRONTEND_IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$FK_GALLERY_FRONTEND_IMAGE")
export FK_GALLERY_BACKEND_IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$FK_GALLERY_BACKEND_IMAGE")
fixture_root=$(mktemp -d /tmp/fk-ui-gallery-XXXXXXXX)
export FK_GALLERY_OUTPUT="$fixture_root/screenshots"
mkdir -p "$FK_GALLERY_OUTPUT"
project="fk-gallery-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:12])')"
override="$fixture_root/compose.yaml"
export FK_GALLERY_SOURCE_DECLARATION=$(cd backend && FK_TEST_INTEGRATION=1 uv run --frozen python -m tests.ui_gallery_accounts declaration)
python3 - "$override" <<'PY'
import json, os, sys
port=int(os.environ['FK_GALLERY_PORT'])
backend=os.environ['FK_GALLERY_BACKEND_IMAGE']
frontend=os.environ['FK_GALLERY_FRONTEND_IMAGE']
origin=json.dumps([f'https://localhost:{port}'])
with open(sys.argv[1], 'w') as out:
    out.write('services:\n')
    for service in ['backend', 'worker', 'migrate']:
        out.write(f'  {service}:\n    image: {json.dumps(backend)}\n    environment:\n      FK_ALLOWED_ORIGINS: {json.dumps(origin)}\n')
        # Only this unique disposable synthetic gallery project enables the test provider.
        out.write('      FK_DEPLOYMENT_MODE: test\n      FK_SIMILARITY_PROVIDER: test\n      FK_SIMILARITY_ALLOW_TEST_PROVIDER: "true"\n      FK_SIMILARITY_AUTOINDEX: "true"\n')
        out.write('      FK_RECOMMENDATION_ENABLED: "true"\n')
        out.write('      FK_RECOMMENDATION_SOURCE_MAP: '+json.dumps(os.environ['FK_GALLERY_SOURCE_DECLARATION'])+'\n')
        if service == 'backend': out.write('    ports: !override []\n')
    out.write(f'  frontend:\n    image: {json.dumps(frontend)}\n    ports: !override ["127.0.0.1:{port}:8443"]\n')
    out.write('  postgres:\n    ports: !override ["127.0.0.1::5432"]\n  redis:\n    ports: !override ["127.0.0.1::6379"]\n')
PY
compose=(docker compose --env-file "$env_file" -p "$project" -f compose.yaml -f "$override")
prepared=0
cleanup() {
  result=$?
  if [[ "$result" != 0 ]]; then
    "${compose[@]}" logs --no-color --tail 100 > "$fixture_root/runtime-failure.log" 2>&1 || true
  fi
  if [[ "$prepared" == 1 ]]; then
    (cd "$repo_root/backend" && uv run --frozen python -m tests.e2e_accounts cleanup) || result=1
  fi
  # Only the unique disposable project created by this script is removed.
  "${compose[@]}" down --volumes --remove-orphans > "$fixture_root/cleanup.log" 2>&1 || result=1
  if [[ "$result" != 0 ]]; then echo "Gallery failed; local diagnostics: $fixture_root" >&2; fi
  exit "$result"
}
trap cleanup EXIT
"${compose[@]}" up --no-build -d --wait --wait-timeout 180 > "$fixture_root/startup.log" 2>&1
export FK_GALLERY_POSTGRES_PORT=$("${compose[@]}" port postgres 5432 | awk -F: '{print $NF}')
export FK_GALLERY_REDIS_PORT=$("${compose[@]}" port redis 6379 | awk -F: '{print $NF}')
export FK_DATABASE_URL=$(python3 -c 'import os,urllib.parse; print("postgresql+psycopg://forest_keeper:"+urllib.parse.quote(os.environ["FK_POSTGRES_PASSWORD"],safe="")+"@127.0.0.1:"+os.environ["FK_GALLERY_POSTGRES_PORT"]+"/forest_keeper")')
export FK_REDIS_URL="redis://127.0.0.1:$FK_GALLERY_REDIS_PORT/0"
export FK_E2E_BASE_URL="https://localhost:$FK_GALLERY_PORT"
(cd backend && uv run --frozen python -m tests.e2e_accounts prepare)
prepared=1
(cd backend && uv run --frozen python -m tests.ui_gallery_accounts)
"${compose[@]}" exec -T backend python -m app.similarity.cli start --activate > "$fixture_root/index-start.log"
(cd frontend && npx playwright test --config playwright.gallery.config.ts)
python3 scripts/render-ui-gallery.py "$FK_GALLERY_OUTPUT"
mkdir -p frontend/public/interface
cp "$FK_GALLERY_OUTPUT/"*.png "$FK_GALLERY_OUTPUT/manifest.json" "$FK_GALLERY_OUTPUT/index.html" "$FK_GALLERY_OUTPUT/interface.css" frontend/public/interface/
python3 scripts/check-ui-gallery.py
printf 'PASS: real UI gallery: frontend/public/interface/index.html\n'
