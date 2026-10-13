#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
# Pinned official Gitleaks v8.24.2 image. Findings are always redacted.
scanner=ghcr.io/gitleaks/gitleaks@sha256:b5918eb91b8d2473cec722f066abb4352e4ffdc4ec9f4283ec143aba9ec9ebc4
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/repo:ro" "$scanner" \
  git /repo --log-opts=--all --redact --no-banner

# Also inspect current tracked contents before commit; never scan generated .env,
# private TLS keys, virtualenvs or node_modules from the development machine.
scan_dir=$(mktemp -d)
trap 'rm -rf "$scan_dir"' EXIT
git ls-files -z | tar --null --files-from=- -cf - | tar -xf - -C "$scan_dir"
docker run --rm --user "$(id -u):$(id -g)" -v "$scan_dir:/repo:ro" "$scanner" \
  dir /repo --redact --no-banner
