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

# Audit the isolated AI lock without installing model runtimes into the backend/CI.
if [[ -f ai/uv.lock ]]; then
  ai_scan_dir=$(mktemp -d)
  trap 'rm -rf "$ai_scan_dir"' EXIT
  uv export --project ai --all-extras --frozen --no-hashes --no-dev --no-emit-project \
    --format requirements-txt > "$ai_scan_dir/locked.txt"
  # PyPI advisories identify upstream torch releases, not the vendor's +cpu local suffix.
  # This only normalizes advisory lookup; ai/uv.lock still pins the exact CPU distribution.
  python3 - "$ai_scan_dir" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
lines = (root / "locked.txt").read_text().splitlines()
lines = [line.replace("torch==2.14.1+cpu", "torch==2.14.1") for line in lines]
(root / "advisories.txt").write_text("\n".join(lines) + "\n")
PY
  (
    cd backend
    uv run --frozen pip-audit --requirement "$ai_scan_dir/advisories.txt" \
      --no-deps --disable-pip --format json --output "$ai_scan_dir/result.json" \
      --cache-dir "${TMPDIR:-/tmp}/forest-keeper-ai-pip-audit"
  )
  python3 - "$ai_scan_dir/result.json" <<'PY'
import json
import sys

items = json.load(open(sys.argv[1]))["dependencies"]
skipped = [item["name"] for item in items if item.get("skip_reason")]
if skipped:
    raise SystemExit("AI dependencies not audited: " + ", ".join(skipped))
if any(item.get("vulns") for item in items):
    raise SystemExit("AI dependency vulnerabilities found")
print(f"AI dependency lock: {len(items)} packages audited, no known vulnerabilities; "
      "torch CPU build uses upstream release advisory version")
PY
fi
