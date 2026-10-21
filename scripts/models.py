# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""Acquire the pinned model files; this does not start an AI service."""

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def catalog():
    manifest = yaml.safe_load((ROOT / "models/model-manifest.yaml").read_text())
    lock = json.loads((ROOT / "models/artifacts.lock.json").read_text())
    for component in ("llm", "embedding"):
        spec = manifest[component]
        pinned = lock[component]
        for key in ("repository", "revision"):
            if spec[key] != pinned[key]:
                raise ValueError(f"{component}: manifest/lock mismatch: {key}")
        if not re.fullmatch(r"[0-9a-f]{40}", spec["revision"]):
            raise ValueError("A full pinned revision is required")
        for file in pinned["files"]:
            path = Path(file["path"])
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe artifact path")
            if not re.fullmatch(r"[0-9a-f]{64}", file["sha256"]):
                raise ValueError("A locked SHA-256 is required")
        weight = spec.get("artifact", "model.safetensors")
        file = next(f for f in pinned["files"] if f["path"] == weight)
        if spec["verification"]["sha256"] != file["sha256"]:
            raise ValueError(f"{component}: weight checksum differs from manifest")
    return manifest, lock


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(path, file):
    return path.is_file() and path.stat().st_size == file["size"] and digest(path) == file["sha256"]


def request(url):
    if not url.startswith("https://huggingface.co/"):
        raise ValueError("Only the official Hugging Face HTTPS origin is supported")
    # HTTPS Hugging Face origin validated above.
    return urllib.request.urlopen(  # nosec B310
        urllib.request.Request(url, headers={"User-Agent": "Forest-Keeper-model-verifier/1"}),
        timeout=120,
    )


def download(path, file, url):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive partial file: concurrent downloads never share an output stream.
    partial = path.with_name(path.name + ".part")
    try:
        with partial.open("xb") as target, request(url) as response:
            count = 0
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > file["size"]:
                    raise ValueError("Download exceeds the pinned size")
                target.write(chunk)
        if not verify(partial, file):
            raise ValueError(f"Size/checksum mismatch: {file['path']}")
        partial.replace(path)
    except FileExistsError:
        raise ValueError(
            f"Partial file exists; inspect/remove before retrying: {partial}"
        ) from None
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def check_upstream(component, spec):
    url = f"https://huggingface.co/api/models/{spec['repository']}/revision/{spec['revision']}?blobs=true"
    with request(url) as response:
        data = json.load(response)
    if data["sha"] != spec["revision"] or data["id"] != spec["repository"]:
        raise ValueError(f"{component}: upstream identity mismatch")
    upstream = {f["rfilename"]: f for f in data["siblings"]}
    for file in spec["files"]:
        remote = upstream[file["path"]]
        if remote["size"] != file["size"]:
            raise ValueError(f"{component}/{file['path']}: upstream size mismatch")
        if "lfs" in remote:
            actual = remote["lfs"]["sha256"]
        else:
            url = f"https://huggingface.co/{spec['repository']}/resolve/{spec['revision']}/{file['path']}"
            with request(url) as response:
                actual = hashlib.sha256(response.read()).hexdigest()
        if actual != file["sha256"]:
            raise ValueError(f"{component}/{file['path']}: upstream checksum mismatch")
    print(
        f"UPSTREAM PASS {component}: {spec['repository']}@{spec['revision']}",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("info", "check-upstream", "download", "verify"))
    parser.add_argument("--directory", type=Path, default=ROOT / "models/downloads")
    args = parser.parse_args()
    manifest, lock = catalog()
    if args.action == "info":
        print(json.dumps({"manifest": manifest, "artifacts": lock}, indent=2))
        return
    for component in ("llm", "embedding"):
        spec = lock[component]
        if args.action == "check-upstream":
            check_upstream(component, spec)
            continue
        for file in spec["files"]:
            path = args.directory / component / file["path"]
            if path.is_symlink() or any(p.is_symlink() for p in path.parents):
                raise ValueError(f"Refusing symlink artifact path: {path}")
            if not verify(path, file):
                if args.action == "verify":
                    raise ValueError(f"Missing/corrupt artifact: {path}")
                print(
                    f"Downloading {component}/{file['path']} ({file['size']} bytes)",
                    flush=True,
                )
                url = f"https://huggingface.co/{spec['repository']}/resolve/{spec['revision']}/{file['path']}"
                download(path, file, url)
            print(f"SHA256 PASS {component}/{file['path']}", flush=True)
    if args.action in ("download", "verify"):
        print("Files verified. AI runtime/inference readiness is a separate acceptance gate.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
