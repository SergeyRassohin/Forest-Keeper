#!/usr/bin/env bash
# Export only the exact committed native source; never stage host binaries or weights.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
revision=620d2225cc436ab0b001e3200e590e3b286ef9ab
repository=${FK_LLAMA_SOURCE_REPOSITORY:-work/stage9-native-repository}
destination=work/stage9-native-src
if [[ -e "$destination" ]]; then
  echo 'Native source staging already exists. Use a fresh checkout or review it explicitly.' >&2
  exit 1
fi
if [[ ! -d "$repository/.git" ]]; then
  git -c http.version=HTTP/1.1 clone --no-checkout https://github.com/ggml-org/llama.cpp.git "$repository"
fi
git -C "$repository" cat-file -e "$revision^{commit}"
mkdir -p "$destination"
git -C "$repository" archive "$revision" | tar -x -C "$destination"
printf '%s\n' "$revision" > "$destination/FK_SOURCE_REVISION"
python3 - "$destination" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
files = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
         for path in sorted(root.rglob('*')) if path.is_file()}
(root / 'FK_SOURCE_SHA256.json').write_text(json.dumps(files, sort_keys=True) + '\n')
print('Pinned native source exported; no compiled artifacts or models staged.')
PY
