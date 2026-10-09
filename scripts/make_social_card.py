#!/usr/bin/env python3
"""Generate the same-origin Open Graph / Twitter share image.

A one-off offline authoring step (like make_cv_pdf.py); the delivered site only
serves the image. 1200x630 is the standard large-card size, so the card renders
in full without being cropped.

    python3 scripts/make_social_card.py   -> images/social-card.png
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "images", "social-card.png")

W, H = 1200, 630
INK = (16, 22, 29)
INK2 = (24, 34, 44)
ACCENT = (19, 86, 127)
ACCENT_LIGHT = (159, 196, 221)
WHITE = (255, 255, 255)
SOFT = (219, 228, 236)

FONT_DIRS = [
    "/usr/share/fonts/truetype/lato",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/noto",
]


def font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def main() -> None:
    import site_content as C
    exp = C.experience_label()
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)

    # Restrained diagonal accent field, matching the site's hero treatment.
    for i in range(H):
        t = i / H
        d.line([(0, i), (W, i)],
               fill=(int(INK2[0] + (INK[0] - INK2[0]) * t),
                     int(INK2[1] + (INK[1] - INK2[1]) * t),
                     int(INK2[2] + (INK[2] - INK2[2]) * t)))
    d.polygon([(0, H), (0, H - 230), (W, H - 60), (W, H)], fill=ACCENT)
    d.rectangle([0, 0, W, 8], fill=ACCENT)

    f_name = font(["Lato-Bold.ttf", "DejaVuSans-Bold.ttf"], 74)
    f_role = font(["Lato-Medium.ttf", "DejaVuSans.ttf"], 36)
    f_lede = font(["Lato-Regular.ttf", "DejaVuSans.ttf"], 27)
    f_small = font(["Lato-Regular.ttf", "DejaVuSans.ttf"], 22)

    x = 72
    d.text((x, 92), "MATTHEW BOWYER", font=f_small, fill=ACCENT_LIGHT)
    d.text((x, 132), "Matthew Bowyer", font=f_name, fill=WHITE)
    d.text((x, 228), "Analytics and Data Science Manager", font=f_role, fill=ACCENT_LIGHT)

    lines = [
        f"{exp} across business intelligence, operational",
        "analytics, financial analysis, data science and",
        "reporting automation.",
    ]
    y = 296
    for line in lines:
        d.text((x, y), line, font=f_lede, fill=SOFT)
        y += 38

    d.line([(x, 452), (x + 90, 452)], fill=WHITE, width=3)
    d.text((x, 470), "Data Science  \u00b7  Machine Learning  \u00b7  Applied AI",
           font=f_small, fill=WHITE)
    d.text((W - 72 - 330, 470), "MSc Data Science e-portfolio", font=f_small, fill=WHITE)

    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {os.path.relpath(OUT, ROOT)} "
          f"({os.path.getsize(OUT)} bytes, {img.width}x{img.height})")


if __name__ == "__main__":
    main()
