#!/usr/bin/env python3
"""Convert the two photographic PNG module covers to JPEG.

Photographic content stored as PNG is the main remaining weight on the site.
Re-encoding to JPEG with the same pixel dimensions is visually
indistinguishable at the display size and cuts the transfer substantially.

Writes output/evidence/cover_conversion.csv and prints the mapping so the
builder's COVER_BY_MODULE table can be updated.
"""
from __future__ import annotations

import csv
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

TARGETS = [
    ("images/Machine_Learning.png", "images/Machine_Learning.jpg"),
    ("images/Research Methods and Professional Practice e port.png",
     "images/Research Methods and Professional Practice e port.jpg"),
]


def main() -> int:
    rows = []
    for src, dst in TARGETS:
        if not os.path.exists(src):
            print(f"SKIP (absent): {src}")
            continue
        before = os.path.getsize(src)
        with Image.open(src) as im:
            im.load()
            size = im.size
            im.convert("RGB").save(dst, "JPEG", quality=80, optimize=True,
                                   progressive=True)
        after = os.path.getsize(dst)
        rows.append({
            "from": src, "to": dst,
            "before_bytes": before, "after_bytes": after,
            "before_mb": round(before / 1048576, 2),
            "after_mb": round(after / 1048576, 2),
            "reduction_pct": round(100 * (before - after) / before, 1),
            "px": f"{size[0]}x{size[1]}",
            "reason": "photographic content stored as PNG; re-encoded to JPEG at the same pixel dimensions",
        })
        print(f"{src} -> {dst}  {rows[-1]['before_mb']} -> {rows[-1]['after_mb']} MB")

    os.makedirs("output/evidence", exist_ok=True)
    with open("output/evidence/cover_conversion.csv", "w", newline="",
              encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
