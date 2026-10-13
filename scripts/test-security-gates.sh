#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fixture_dir=$(mktemp -d)
trap 'rm -rf "$fixture_dir"' EXIT

# Temporary synthetic fixtures are never executed or added to the repository.
cat > "$fixture_dir/unsafe.py" <<'PY'
import subprocess
subprocess.run(user_input, shell=True)
PY
printf 'eval(userInput);\n' > "$fixture_dir/unsafe.ts"
python - "$fixture_dir" <<'PY'
import hashlib
import sys
from pathlib import Path

token = 'ghp_' + hashlib.sha256(b'forest-keeper-synthetic-security-gate').hexdigest()[:36]
(Path(sys.argv[1]) / 'synthetic-token.txt').write_text('token = "' + token + '"\n')
PY

expect_rejection() {
  local rule="$1"
  shift
  local exit_code=0
  "$@" > "$fixture_dir/output" 2>&1 || exit_code=$?
  if [[ "$exit_code" != 1 || "$(<"$fixture_dir/output")" != *"$rule"* ]]; then
    echo "Security gate did not reject the expected fixture: $rule (exit $exit_code)" >&2
    cat "$fixture_dir/output" >&2
    return 1
  fi
  echo "Security gate rejected fixture: $rule"
}

(
  cd backend
  expect_rejection B602 uv run --frozen bandit "$fixture_dir/unsafe.py"
)
(
  cd frontend
  expect_rejection security/detect-eval-with-expression ./node_modules/.bin/eslint \
    --stdin --stdin-filename src/security-gate-probe.ts \
    --config eslint.security.config.js --max-warnings 0 < "$fixture_dir/unsafe.ts"
)
scanner=ghcr.io/gitleaks/gitleaks@sha256:b5918eb91b8d2473cec722f066abb4352e4ffdc4ec9f4283ec143aba9ec9ebc4
expect_rejection github-pat docker run --rm --user "$(id -u):$(id -g)" \
  -v "$fixture_dir:/repo:ro" "$scanner" dir /repo --redact --no-banner --verbose
