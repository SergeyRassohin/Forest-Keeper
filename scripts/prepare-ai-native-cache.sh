#!/usr/bin/env bash
# Optional local incremental build; byte-verify a prior source build, never execute copied files.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source_image=${1:-forest-keeper-ai-llm:stage9}
output=work/stage9-native-release
if [[ -e "$output" ]]; then
  echo 'Native cache staging exists; review it explicitly rather than overwriting.' >&2
  exit 1
fi
container="fk-native-export-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:12])')"
docker create --pull never --name "$container" --entrypoint /bin/true "$source_image" > /dev/null
trap 'docker rm "$container" > /dev/null' EXIT
mkdir -p work
docker cp "$container:/app/native" "$output"
python3 - "$output" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
lock = json.loads(pathlib.Path('ai/native-artifact.lock.json').read_text())
assert not root.is_symlink()
assert not any(path.is_symlink() for path in root.rglob('*'))
actual = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
          for path in root.rglob('*') if path.is_file()}
assert actual == lock['files'], 'Native build bytes differ from the reviewed local artifact lock'
assert (root/'FK_SOURCE_REVISION').read_text().strip() == lock['source_revision']
print('Verified local native build cache; no weights copied; no signature claim.')
PY
