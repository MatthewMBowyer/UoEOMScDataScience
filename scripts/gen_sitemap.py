#!/usr/bin/env python3
"""Regenerate sitemap.xml from the delivered pages (AC-50 / INV-16).

Lists EVERY delivered page (every *.html except the footer fragment) with an
absolute, URL-encoded URL. Deterministic and re-runnable; it can never omit a
page that exists on disk.

The owner's two unlisted personal pages (sports.html, good_hubby.html) are NOT
delivered pages - AC-P5 requires the sitemap not to advertise them, and AC-50
requires every *delivered* page to be listed. PERSONAL_PAGES is the single
definition of that exclusion; see tests/verify_site.py.
"""
from __future__ import annotations

import glob
import os
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

SITE = "https://matthewmbowyer.github.io/UoEOMScDataScience/"

PERSONAL_PAGES = ("sports.html", "good_hubby.html")


def main() -> None:
    pages = [p for p in sorted(glob.glob("*.html"))
             if p != "footer.html" and p not in PERSONAL_PAGES]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        # Encode spaces/commas; keep the path separators.
        loc = SITE + quote(p, safe="/")
        priority = "1.0" if p == "index.html" else "0.7"
        lines += ["  <url>", f"    <loc>{loc}</loc>",
                  "    <changefreq>monthly</changefreq>",
                  f"    <priority>{priority}</priority>", "  </url>"]
    lines.append("</urlset>")
    with open("sitemap.xml", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote sitemap.xml with {len(pages)} urls")
    for want in ("experience.html", "thesis-demo.html"):
        print(" ", want, "included:", any(want in l for l in lines))
    print("  chat.html removed:", not any("chat.html" in l for l in lines))


if __name__ == "__main__":
    main()
