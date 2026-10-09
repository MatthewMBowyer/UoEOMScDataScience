#!/usr/bin/env python3
"""Optimise the oversized images the delivered pages actually reference, and
record a before/after size report.

Canonical inputs under inputs/ are never modified; they are the untouched
"before" source. Only the delivered copies are re-encoded in place, so a
delivered image that is smaller than its input is one this script optimised.
Re-running is idempotent: an already-optimised image is reported from the input
baseline, never re-encoded from an already-reduced copy.

    python3 scripts/optimise_images.py
"""
from __future__ import annotations

import csv
import glob
import os
import sys
import urllib.parse

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# Displayed at most ~420 CSS px wide (card media / module figure); 1100 px gives
# headroom for 2x displays without shipping a 1536 px source.
MAX_W = 1100
# The requirement says "over 1 MB", i.e. 1,000,000 bytes. Using 1024*1024 left
# two 1879x1879 covers of ~1.02 MB unoptimised while three same-size siblings
# were resized; this is the decimal threshold the request actually states.
THRESHOLD = 1_000_000


def referenced_images() -> set[str]:
    from lxml import html as LH

    refs = set()
    for page in glob.glob("*.html"):
        doc = LH.fromstring(open(page, encoding="utf-8", errors="replace").read())
        for src in doc.xpath("//img/@src"):
            refs.add(urllib.parse.unquote(src))
    return refs


def optimise_in_place(rel: str) -> None:
    with Image.open(rel) as im:
        im.load()
        fmt = (im.format or "PNG").upper()
        w, h = im.size
        if w > MAX_W:
            new_h = round(h * MAX_W / w)
            im = im.resize((MAX_W, new_h), Image.LANCZOS)
        if fmt == "JPEG":
            im.convert("RGB").save(rel, "JPEG", quality=82, optimize=True,
                                   progressive=True)
        elif fmt == "PNG" and im.mode in ("RGBA", "LA", "P"):
            im.save(rel, "PNG", optimize=True)
        elif fmt == "PNG":
            im.convert("RGB").save(rel, "PNG", optimize=True)
        else:
            im.save(rel, optimize=True)


def main() -> int:
    refs = referenced_images()
    rows = []
    still_oversized = []

    for rel in sorted(refs):
        if not rel.startswith("images/") or not os.path.isfile(rel):
            continue
        before = os.path.getsize(rel)
        if before > THRESHOLD:
            optimise_in_place(rel)
            after = os.path.getsize(rel)
            baseline_bytes = before
        else:
            # Already at display weight; the untouched input is the "before".
            baseline = os.path.join("inputs", rel)
            if not os.path.isfile(baseline):
                continue
            baseline_bytes = os.path.getsize(baseline)
            after = before
            if baseline_bytes <= THRESHOLD:
                continue  # was never oversized, nothing to report

        if after > THRESHOLD:
            still_oversized.append(rel)

        with Image.open(rel) as im:
            w, h = im.size
        with Image.open(os.path.join("inputs", rel)) as im:
            bw, bh = im.size

        rows.append({
            "path": rel,
            "before_bytes": baseline_bytes,
            "after_bytes": after,
            "before_mb": round(baseline_bytes / 1048576, 2),
            "after_mb": round(after / 1048576, 2),
            "reduction_pct": round(100 * (baseline_bytes - after) / baseline_bytes, 1),
            "before_px": f"{bw}x{bh}",
            "after_px": f"{w}x{h}",
            "display_purpose": "module/programme card media (max ~420 CSS px wide)",
            "action": "resized to max 1100px wide and re-encoded",
        })

    with open("output/evidence/image_optimisation.csv", "w", newline="",
              encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else
                            ["path", "before_bytes", "after_bytes"])
        wr.writeheader()
        wr.writerows(rows)

    for r in rows:
        print(f"{r['path']:60s} {r['before_mb']:5.2f} -> {r['after_mb']:5.2f} MB "
              f"({r['reduction_pct']:4.1f}%)  {r['before_px']} -> {r['after_px']}")
    print(f"recorded {len(rows)} oversized referenced images")

    if still_oversized:
        print("STILL OVERSIZED (referenced):")
        for p in still_oversized:
            print("   ", p, round(os.path.getsize(p) / 1048576, 2), "MB")
        return 1
    print("no referenced image remains above 1 MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
