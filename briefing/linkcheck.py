#!/usr/bin/env python3
"""Zero-broken internal link check for the briefing board (session arena/198cf31e).

Walks every local href in briefing/*.html and asserts the target exists (file or id anchor).
External http(s) links are counted and listed, never fetched.
Exit 0 = no broken internal link.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HREF = re.compile(r'href="([^"]+)"')
ID = re.compile(r'\bid="([^"]+)"')


def main() -> int:
    pages = sorted(HERE.glob("*.html"))
    ids = {p: set(ID.findall(p.read_text())) for p in pages}
    names = {p.name for p in pages} | {"style.css"}
    broken, internal, external = [], 0, 0

    for p in pages:
        for href in HREF.findall(p.read_text()):
            if href.startswith(("http://", "https://")):
                external += 1
                continue
            if href.startswith("mailto:") or href.startswith("tel:"):
                continue
            internal += 1
            file_part, _, frag = href.partition("#")
            target = file_part or p.name
            if target not in names:
                broken.append(f"{p.name}: missing target '{target}' (href={href})")
                continue
            if frag and frag not in ids.get(HERE / target, set()):
                broken.append(f"{p.name}: missing anchor '#{frag}' in {target}")

    print(f"pages: {len(pages)}  internal links: {internal}  external links: {external}")
    if broken:
        print(f"{len(broken)} BROKEN LINK(S):")
        for b in broken:
            print("  -", b)
        return 1
    print("0 broken links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
