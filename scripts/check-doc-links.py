"""Check repository documentation targets, optionally check public HTTP links."""

import argparse
import concurrent.futures
import datetime
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sources():
    return [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        *sorted((ROOT / "docs").rglob("*.md")),
        *sorted((ROOT / "models").glob("*.md")),
        *sorted((ROOT / "tests/data").rglob("README.md")),
    ]


def http_check(url):
    try:
        if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
            raise ValueError("Only HTTP(S) documentation links are permitted")
        # Stream a byte: follow redirects without fetching a model/archive in full.
        req = urllib.request.Request(url, headers={"User-Agent": "Forest-Keeper-link-check/1"})
        # Only HTTP(S) schemes are admitted above.
        with urllib.request.urlopen(req, timeout=30) as response:  # nosec B310
            response.read(1)
            # Signed CDN query strings are transient and are not part of the report.
            final = urllib.parse.urlsplit(response.url)
            return {
                "url": url,
                "status": response.status,
                "destination": urllib.parse.urlunsplit(final._replace(query="", fragment="")),
                "ok": response.status in (200, 206),
            }
    except (OSError, ValueError) as exc:
        return {"url": url, "ok": False, "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    missing, urls = [], set()
    for path in sources():
        content = path.read_text()
        for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", content):
            parts = urllib.parse.urlsplit(target)
            if parts.scheme or target.startswith("#"):
                continue
            local = (path.parent / urllib.parse.unquote(parts.path)).resolve()
            if not local.exists():
                missing.append({"source": str(path.relative_to(ROOT)), "target": target})
        # Historical reports keep their original external URLs. Local targets are
        # still checked, but historical network drift is not a current download gate.
        if "testing/reports" in str(path) or "sessions/" in str(path):
            continue
        for url in re.findall(r'https?://[^\s<>`"\)\]]+', content):
            url = url.rstrip(".,;")
            host = urllib.parse.urlsplit(url).hostname
            if (
                host
                and host not in ("localhost", "127.0.0.1")
                and "." in host
                and not host.endswith((".invalid", ".test", ".example", ".localhost"))
            ):
                urls.add(url)
    lock = json.loads((ROOT / "models/artifacts.lock.json").read_text())
    for component in ("llm", "embedding"):
        spec = lock[component]
        for file in spec["files"]:
            urls.add(
                f"https://huggingface.co/{spec['repository']}/resolve/{spec['revision']}/{file['path']}"
            )
    results = []
    if args.external:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(http_check, sorted(urls)))
    report = {
        "checked_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "scope": (
            "All local Markdown targets; active documentation and locked model URLs over HTTP. "
            "Fragments and reserved example hosts are not checked."
        ),
        "missing_local_targets": missing,
        "external": results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for item in missing:
        print(f"MISSING {item['source']}: {item['target']}")
    for item in results:
        print(
            f"{'PASS' if item['ok'] else 'FAIL'} {item['url']} "
            f"{item.get('status', item.get('error'))}"
        )
    print(
        f"Local missing: {len(missing)}; HTTP checked: {len(results)}; "
        f"HTTP failures: {sum(not r['ok'] for r in results)}"
    )
    return int(bool(missing) or any(not r["ok"] for r in results))


if __name__ == "__main__":
    sys.exit(main())
