"""Check static-page links and required dashboard routes before deployment."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
REQUIRED_PAGES = (
    SITE / "index.html",
    SITE / "cs2" / "index.html",
    SITE / "lol" / "index.html",
    SITE / "sources" / "index.html",
)


def check_site(site_root: Path = SITE) -> list[str]:
    errors: list[str] = []
    for path in REQUIRED_PAGES:
        if not path.is_file():
            errors.append(f"Required page is missing: {path.relative_to(ROOT)}")
    if errors:
        return errors

    for html_path in sorted(site_root.rglob("*.html")):
        try:
            soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
        except OSError as exc:
            errors.append(f"Cannot read {html_path.relative_to(ROOT)}: {exc}")
            continue
        if soup.find("table") is None and html_path.parent.name in {"cs2", "lol"}:
            errors.append(f"Category page has no table: {html_path.relative_to(ROOT)}")
        if not soup.find("nav"):
            errors.append(f"Page has no navigation: {html_path.relative_to(ROOT)}")
        for node, attribute in [(node, "href") for node in soup.find_all(href=True)] + [(node, "src") for node in soup.find_all(src=True)]:
            value = str(node.get(attribute, "")).strip()
            if not value or value.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            parsed = urlparse(value)
            if parsed.scheme or parsed.netloc:
                continue
            target = (html_path.parent / parsed.path).resolve()
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                errors.append(f"Broken local {attribute} in {html_path.relative_to(ROOT)}: {value}")

    for html_path in site_root.rglob("*.html"):
        body = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser").body
        if not body or not body.get("data-snapshot"):
            errors.append(f"Page does not declare a snapshot data path: {html_path.relative_to(ROOT)}")

    app_script = site_root / "assets" / "app.js"
    if app_script.exists():
        code = app_script.read_text(encoding="utf-8")
        if "localhost" in code.casefold() or "127.0.0.1" in code:
            errors.append("Browser-facing code must not call localhost/127.0.0.1")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=SITE)
    args = parser.parse_args()
    errors = check_site(args.site)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Static site checks passed for {args.site}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
