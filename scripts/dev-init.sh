#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
umask 077
mkdir -p deploy/local/tls
if [[ ! -e .env ]]; then
  password=$(openssl rand -hex 24)
  cat > .env <<EOF
# Generated local-development credentials. Never commit this file.
FK_POSTGRES_PASSWORD=$password
FK_DATABASE_URL=postgresql+psycopg://forest_keeper:$password@127.0.0.1:5432/forest_keeper
FK_REDIS_URL=redis://127.0.0.1:6379/0
EOF
fi
if [[ ! -e deploy/local/tls/dev.key && ! -e deploy/local/tls/dev.crt ]]; then
  openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 30 \
    -keyout deploy/local/tls/dev.key -out deploy/local/tls/dev.crt \
    -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1' 2>/dev/null
elif [[ ! -f deploy/local/tls/dev.key || ! -f deploy/local/tls/dev.crt ]]; then
  echo 'Incomplete TLS pair: restore both files before starting.' >&2
  exit 1
fi
echo 'Local configuration prepared. Existing files were preserved.'
