"""Render the public, self-contained screenshot catalogue from real capture metadata."""

import html
import json
import sys
from pathlib import Path


def render(folder: Path) -> None:
    data = json.loads((folder / "manifest.json").read_text())
    cards = []
    for item in data["captures"]:
        file, title, description = (
            html.escape(item[key], quote=True) for key in ["file", "title", "description"]
        )
        cards.append(
            f'''<article><a href="{file}"><img loading="lazy" src="{file}"
alt="{title} — реальный экран Forest Keeper" width="1440"></a>
<div><span class="tag">Работает сейчас · демонстрационные данные</span>
<h2>{title}</h2>
<p>{description}</p>
<a href="{file}">Открыть полный экран ↗</a></div></article>'''
        )
    template = Path(__file__).with_name("templates") / "interface.html"
    page = template.read_text().replace("<!-- GALLERY -->", "\n".join(cards))
    (folder / "index.html").write_text(page)
    (folder / "interface.css").write_text(template.with_suffix(".css").read_text())


if __name__ == "__main__":
    render(Path(sys.argv[1]))
