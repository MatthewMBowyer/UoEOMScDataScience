#!/usr/bin/env python3
"""Single source of truth for the delivered site's shared navigation.

Rewrites the primary <nav id="nav"><ul>...</ul> block and the footer "Site"
link list on EVERY delivered page so the items and their order are identical
everywhere (INV-01 / AC-06 / AC-34 / AC-77), including the pages added by the
CV amendment.
"""
from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# (label, href) — the ONE navigation contract for the whole site.
NAV_ITEMS = [
    ("Home", "index.html"),
    ("About", "about.html"),
    ("Skills &amp; Capabilities", "skills.html"),
    ("Projects &amp; Modules", "projects.html"),
    ("Experience", "experience.html"),
    ("Evidence", "evidence.html"),
    ("Thesis Demo", "thesis-demo.html"),
    ("CV", "cv.html"),
    ("Contact", "contact.html"),
]

REFERENCE_PAGE = "experience.html"


def nav_block(indent: str = "\t\t\t\t\t") -> str:
    lines = [f'{indent}<ul>']
    for label, href in NAV_ITEMS:
        lines.append(f'{indent}\t<li><a href="{href}">{label}</a></li>')
    lines.append(f'{indent}</ul>')
    return "\n".join(lines)


def footer_site_block(indent: str = "\t\t\t\t\t\t") -> str:
    lines = ['<ul class="footer-links">']
    for label, href in NAV_ITEMS:
        lines.append(f'{indent}<li><a href="{href}">{label}</a></li>')
    lines.append(f'{indent}</ul>')
    return "\n".join(lines)


def rewrite_page(path: str) -> bool:
    with open(path, encoding="utf-8") as fh:
        s = fh.read()
    original = s

    # Primary nav: replace contents of <ul> inside <nav id="nav" ...>
    nav_re = re.compile(r'(<nav id="nav" aria-label="Primary">\s*)<ul>.*?</ul>', re.DOTALL)
    s = nav_re.sub(lambda m: m.group(1) + nav_block(), s)

    # Footer is a shared fragment; only footer.html carries the Site list.
    return s != original, s


def main() -> None:
    import glob
    changed = []
    pages = [p for p in sorted(glob.glob("*.html")) if p != "footer.html"]
    for name in pages:
        if not os.path.exists(name):
            continue
        changed_flag, new = rewrite_page(name)
        if changed_flag:
            with open(name, "w", encoding="utf-8") as fh:
                fh.write(new)
            changed.append(name)

    # footer.html Site list
    if os.path.exists("footer.html"):
        with open("footer.html", encoding="utf-8") as fh:
            f = fh.read()
        f2 = re.sub(r'<ul class="footer-links">.*?</ul>',
                    footer_site_block(), f, count=1, flags=re.DOTALL)
        if f2 != f:
            with open("footer.html", "w", encoding="utf-8") as fh:
                fh.write(f2)
            changed.append("footer.html(site-links)")

    print("nav rewritten on:", changed)


if __name__ == "__main__":
    main()
