"""Reject missing, changed or stale real UI screenshot evidence."""

import hashlib
import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GalleryMarkup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = set()
        self.stylesheets = set()
        self.inline_style = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "img":
            self.images.add(attributes.get("src"))
        if tag == "link" and attributes.get("rel") == "stylesheet":
            self.stylesheets.add(attributes.get("href"))
        if tag == "style" or "style" in attributes:
            self.inline_style = True


def main() -> None:
    folder = ROOT / "frontend/public/interface"
    data = json.loads((folder / "manifest.json").read_text())
    source_tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD:frontend/src"], cwd=ROOT, text=True
    ).strip()
    if data["source_tree"] != source_tree:
        raise SystemExit("UI gallery is stale: capture the current committed frontend source")
    if len(data["captures"]) < 16 or not data["accessibility"] or not data["responsive"]:
        raise SystemExit("Incomplete UI gallery")
    for item in data["captures"]:
        path = folder / item["file"]
        if path.parent != folder or path.suffix != ".png":
            raise SystemExit("Invalid gallery image path")
        raw = path.read_bytes()
        if (
            not raw.startswith(b"\x89PNG\r\n\x1a\n")
            or hashlib.sha256(raw).hexdigest() != item["sha256"]
        ):
            raise SystemExit("Changed or invalid screenshot: " + item["file"])
    for item in data["brand_assets"]:
        if (
            hashlib.sha256((ROOT / "frontend/public/brand" / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise SystemExit("Brand assets changed: capture the current UI")
    if any(item["violations"] for item in data["accessibility"]) or any(
        not item["passed"] for item in data["responsive"]
    ):
        raise SystemExit("Failed accessibility/responsive gallery gate")
    if not (folder / "index.html").exists():
        raise SystemExit("Missing public interface page")
    markup = GalleryMarkup()
    markup.feed((folder / "index.html").read_text())
    if markup.images != {item["file"] for item in data["captures"]}:
        raise SystemExit("Gallery page does not include the complete screenshot set")
    if markup.stylesheets != {"interface.css"} or markup.inline_style:
        raise SystemExit("Gallery must preserve the server's strict style CSP")
    if (folder / "interface.css").read_bytes() != (
        ROOT / "scripts/templates/interface.css"
    ).read_bytes():
        raise SystemExit("Missing or stale gallery stylesheet")
    print(
        f"PASS: {len(data['captures'])} real screenshots, WCAG checks; "
        f"{len(data['responsive'])} responsive checks; source tree matches"
    )


if __name__ == "__main__":
    main()
