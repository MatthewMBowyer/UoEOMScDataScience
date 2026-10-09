"""Extract the module summaries the site itself states, so projects/programme
cards reuse the owner's own wording rather than anything invented.

Writes output/evidence/site_module_summaries.json (derived; inputs/ is never modified).
"""
import glob
import json
import os
import re
import sys

from lxml import html as LH

ROOT = "/projects/conference-program/projects/eportfolio_rebuild"
os.chdir(ROOT)
OUT = "output/evidence/site_module_summaries.json"

out = {}
for src in ("Masters.html", "Honours.html"):
    doc = LH.fromstring(open(f"inputs/{src}", encoding="utf-8", errors="replace").read())
    for sec in doc.xpath("//section[@class='box' or contains(@class,'box')]"):
        a = sec.xpath(".//header//h3")
        p = sec.xpath(".//p[1]")
        href = sec.xpath(".//footer//a/@href")
        img = sec.xpath(".//img/@src")
        if not (a and p and href):
            continue
        title = re.sub(r"\s+", " ", a[0].text_content()).strip()
        text = re.sub(r"\s+", " ", p[0].text_content()).strip()
        target = href[0]
        if target == "#":
            continue
        if not target.endswith(".html"):
            continue
        out[target] = {
            "source_page": src,
            "title_on_page": title,
            "credits": bool(re.search(r"\(\s*30\s*Credits\s*\)", title, re.I)),
            "summary": text,
            "image": img[0] if img else None,
            "alt": (sec.xpath(".//img/@alt") or [""])[0],
        }

os.makedirs("output/evidence", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2, ensure_ascii=False)

print(f"extracted {len(out)} module summaries from the supplied programme pages -> {OUT}")
for k, v in sorted(out.items()):
    print(f"  {k:56s} credits={v['credits']} img={v['image']}")
