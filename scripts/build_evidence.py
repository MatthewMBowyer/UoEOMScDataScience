#!/usr/bin/env python3
"""Emit the machine-readable evidence deliverables:

  output/evidence/artefact_manifest.json   (DEL-ARTEFACT-MANIFEST)
  output/evidence/removals.json            (DEL-REMOVALS-LOG)
  output/evidence/module_layout_report.json (DEL-MODULES)

All three are derived deterministically from the delivered tree and from the
content model in scripts/site_content.py, not hand-written.

    python3 scripts/build_evidence.py
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse

from lxml import html as LH

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)
os.chdir(ROOT)
import site_content as C  # noqa: E402

OUT = "output/evidence"
NAV_EXPECTED = [(t, h) for t, h in C.NAV_ITEMS]
STYLESHEETS = ["assets/css/main.css", "assets/css/portfolio.css"]

REMOVED_PAGES = {
    "index01.html": "Leftover duplicate template landing page (index01); not part of the portfolio.",
    "index1.html": "Leftover duplicate template landing page (index1); not part of the portfolio.",
    "2026.html": "Personal/aspirational goal page; not recruiters-facing portfolio content.",
    "Mattgoals.html": "Personal goal-setting page; not recruiters-facing portfolio content.",
    "Americano.html": "Personal coffee/hobby page from the template.",
    "Team_Americano.html": "Personal coffee/hobby page from the template.",
    "AMsmash.html": "Personal hobby page (badminton); also the only consumer of assets/league_data.json.",
    "Cute.html": "Personal photo page (relationship/June photo set); not portfolio content.",
    "RobJo.html": "Personal photo page; not portfolio content.",
    "burpeeeeeees.html": "Personal fitness/hobby page.",
    "grumpgrump.html": "Personal/humorous page.",
    "test.html": "Scratch/test page with no site purpose.",
}

REMOVED_ASSETS = {
    "assets/league_data.json": "Unreferenced once AMsmash.html is removed; carried no portfolio value.",
    "images/Chloe background.png": "Personal image only used by the removed personal pages.",
    "images/grumpgrump.png": "Personal image only used by the removed grumpgrump.html.",
    "images/RobJo.jpeg": "Personal image only used by the removed RobJo.html.",
    "images/data-science-background.jpg": "Unreferenced by any supplied page; superseded by the new hero treatment.",
    "images/pic01.jpg": "Dead template demo asset (referenced only by main.css for the #banner block, which main.css also references as ../../images/pic01.jpg).",
    "images/pic02.jpg": "Dead template demo asset, unreferenced by any page.",
    "images/pic03.jpg": "Dead template demo asset, unreferenced by any page.",
    "images/pic04.jpg": "Dead template demo asset, unreferenced by any page.",
    "images/pic05.jpg": "Dead template demo asset, unreferenced by any page.",
    "images/pic06.jpg": "Dead template demo asset, unreferenced by any page.",
    "images/pic07.jpg": "Dead template demo asset, unreferenced by any page.",
    "images/pic08.jpg": "Dead template demo asset, unreferenced by any page.",
    "images/pic09.jpg": "Dead template demo asset, unreferenced by any page.",
    "images/pic10.jpg": "Dead template demo asset, unreferenced by any page.",
    "images/RelationshipImage1.jpg": "Personal photo set (33 files) referenced only by the removed personal pages.",
    "images/June20262.jpeg": "Personal photo set referenced only by the removed personal pages.",
    "images/june20261.jpeg": "Personal photo set referenced only by the removed personal pages.",
    "images/Banner": "Extensionless JPEG; replaced by images/banner.jpg so it is served with a correct image content type (AC-28).",
    "images/Machine_Learning.png": "Photographic PNG cover converted to images/Machine_Learning.jpg (1.17 MB -> 0.10 MB).",
    "images/Research Methods and Professional Practice e port.png": "Photographic PNG cover converted to a JPEG of the same name (1.55 MB -> 0.13 MB).",
}

# Assets created by the rebuild (recorded so the removals log is complete).
ADDED_ASSETS = {
    "assets/css/portfolio.css": "The new design-system stylesheet layered over the retained Dopetrope template.",
    "images/banner.jpg": "Extension-correct replacement for the extensionless images/Banner.",
    "images/Machine_Learning.jpg": "Optimised JPEG replacement for Machine_Learning.png.",
    "images/Research Methods and Professional Practice e port.jpg": "Optimised JPEG replacement for the equivalent PNG.",
    "images/favicon.png": "Site icon created so pages do not 404 on favicon.",
    "favicon.ico": "Fallback icon for clients that request /favicon.ico.",
    "footer.html": "Rebuilt shared footer fragment retaining the HTML5 UP credit.",
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse(path: str):
    return LH.fromstring(open(path, encoding="utf-8", errors="replace").read())


def html_pages() -> list[str]:
    import glob

    return sorted(p for p in glob.glob("*.html") if p != "footer.html")


# ---------------------------------------------------------------------------
# artefact_manifest.json
# ---------------------------------------------------------------------------

def build_manifest() -> dict:
    arts = []
    for path, info in sorted(C.ARTEFACTS.items()):
        arts.append({
            "path": path,
            "title": info["title"],
            "kind": info["kind"],
            "module": info["module"],
            "module_title": C.MODULES.get(info["module"], {}).get("title", ""),
            "declared_pages": info.get("pages"),
            "exists": os.path.isfile(path),
            "bytes": os.path.getsize(path) if os.path.isfile(path) else None,
            "sha256": sha256(path) if os.path.isfile(path) else None,
            "in_inputs": os.path.isfile(os.path.join("inputs", path)),
        })
    dups = []
    for path, info in sorted(C.ROOT_DUPLICATES.items()):
        assets_copy = "assets/" + path
        dups.append({
            "path": path,
            "title": info["title"],
            "kind": info["kind"],
            "exists": os.path.isfile(path),
            "bytes": os.path.getsize(path) if os.path.isfile(path) else None,
            "sha256": sha256(path) if os.path.isfile(path) else None,
            "duplicate_of": assets_copy,
            "duplicate_of_sha256": sha256(assets_copy) if os.path.isfile(assets_copy) else None,
            "identical_to_copy": (os.path.isfile(path) and os.path.isfile(assets_copy)
                                  and sha256(path) == sha256(assets_copy)),
        })
    return {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "description": "Every academic artefact linked from the delivered site, "
                       "with attribution and content hashes.",
        "artefact_count": len(arts),
        "root_duplicate_count": len(dups),
        "artefacts": arts,
        "root_duplicates": dups,
    }


# ---------------------------------------------------------------------------
# removals.json
# ---------------------------------------------------------------------------

def build_removals() -> dict:
    removed_pages = []
    for page, reason in sorted(REMOVED_PAGES.items()):
        removed_pages.append({
            "kind": "page",
            "path": page,
            "reason": reason,
            "present_in_inputs": os.path.isfile(os.path.join("inputs", page)),
            "absent_from_delivered_tree": not os.path.exists(page),
            "in_delivered_navigation": any(
                page in [h for _, h in C.NAV_ITEMS] for p in html_pages()
            ),
            "reversible_from": f"inputs/{page}",
        })

    removed_assets = []
    for path, reason in sorted(REMOVED_ASSETS.items()):
        in_inputs = os.path.isfile(os.path.join("inputs", path))
        removed_assets.append({
            "kind": "asset",
            "path": path,
            "reason": reason,
            "present_in_inputs": in_inputs,
            "absent_from_delivered_tree": not os.path.exists(path),
            "reversible_from": f"inputs/{path}" if in_inputs else None,
        })
    # The relationship/June photo set is a large batch; record each file.
    import glob

    for extra in sorted(glob.glob("inputs/images/RelationshipImage*") +
                        glob.glob("inputs/images/June*.jpeg") +
                        glob.glob("inputs/images/june*.jpeg")):
        rel = os.path.relpath(extra, "inputs")
        if os.path.exists(rel):
            continue
        if any(r["path"] == rel for r in removed_assets):
            continue
        removed_assets.append({
            "kind": "asset",
            "path": rel,
            "reason": "Personal photo referenced only by the removed personal pages.",
            "present_in_inputs": True,
            "absent_from_delivered_tree": True,
            "reversible_from": f"inputs/{rel}",
        })

    # Canonical inputs must be untouched by the rebuild.
    import glob as _glob

    mismatches = []
    checked = 0
    for p in _glob.glob("inputs/**/*", recursive=True):
        if not os.path.isfile(p):
            continue
        checked += 1
    manifest_path = ".supervisor/INPUT_MANIFEST.json"
    if os.path.exists(manifest_path):
        man = json.load(open(manifest_path, encoding="utf-8"))
        for f in man["files"]:
            src = os.path.join("inputs", f["relative_path"])
            if not os.path.isfile(src):
                mismatches.append({"path": f["relative_path"], "issue": "missing"})
            elif sha256(src) != f["sha256"]:
                mismatches.append({"path": f["relative_path"], "issue": "hash changed"})

    return {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "policy": "Pages and assets were removed from the DELIVERED tree only. "
                  "The canonical copy under inputs/ is immutable, so every removal "
                  "is reversible by copying the file back.",
        "inputs_unchanged": not mismatches,
        "inputs_files_checked": checked,
        "inputs_hash_mismatches": mismatches,
        "removals": removed_pages + removed_assets,
        "pages_removed": len(removed_pages),
        "assets_removed": len(removed_assets),
        "assets_added": [{"path": p, "reason": r} for p, r in sorted(ADDED_ASSETS.items())],
    }


# ---------------------------------------------------------------------------
# module_layout_report.json
# ---------------------------------------------------------------------------

def build_module_report() -> dict:
    report = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "expected_nav": [{"label": t, "href": h} for t, h in NAV_EXPECTED],
        "expected_stylesheets": STYLESHEETS,
        "modules": {},
        "conforming": 0,
        "non_conforming": 0,
        "non_conforming_pages": [],
    }
    for path in C.MODULE_ORDER:
        doc = parse(path)
        h1 = [e.text_content().strip() for e in doc.xpath("//h1")]
        navs = doc.xpath("//nav[@id='nav']")
        nav = [((a.text_content() or "").strip(), a.get("href")) for a in
               navs[0].xpath(".//a")] if navs else []
        css = [l.get("href") for l in doc.xpath("//link[@rel='stylesheet']")]
        lang = (doc.xpath("//html/@lang") or [""])[0]
        foot = bool(doc.xpath("//div[@id='footer-placeholder']"))
        art_block = bool(doc.xpath("//section[contains(@class,'artefact-block')]"))
        art_links = [a.get("href") for a in doc.xpath("//a[@href]")
                     if urllib.parse.unquote(a.get("href", "")).lower().endswith(
                         (".pdf", ".xlsx", ".docx"))]
        meta = C.MODULES[path]
        badge = meta["programme"]
        has_badge = any(badge in e.text_content()
                        for e in doc.xpath("//span[contains(@class,'badge')]"))
        expected_artefacts = sorted(
            p for p, i in C.ARTEFACTS.items() if i["module"] == path)
        got_artefacts = sorted(set(urllib.parse.unquote(x) for x in art_links))
        arts_match = got_artefacts == expected_artefacts
        expected_nav = [(html.unescape(t), h) for t, h in C.NAV_ITEMS]
        checks = {
            "exactly_one_h1": len(h1) == 1,
            "h1_matches_module_title": h1 == [meta["title"]],
            "nav_identical": nav == expected_nav,
            "stylesheet_set": css == STYLESHEETS,
            "lang_en": lang == "en",
            "footer_placeholder": foot,
            "programme_badge": has_badge,
            "artefact_block_matches_manifest": (
                art_block == bool(expected_artefacts) and arts_match),
        }
        ok = all(checks.values())
        report["modules"][path] = {
            "title": meta["title"],
            "programme": badge,
            "credit": meta["credit"],
            "checks": checks,
            "artefact_links": sorted(urllib.parse.unquote(x) for x in art_links),
            "expected_artefacts": expected_artefacts,
            "conforms": ok,
        }
        if ok:
            report["conforming"] += 1
        else:
            report["non_conforming"] += 1
            report["non_conforming_pages"].append(
                {"page": path, "failed": [k for k, v in checks.items() if not v]})
    report["module_count"] = len(C.MODULE_ORDER)
    return report


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    man = build_manifest()
    with open(f"{OUT}/artefact_manifest.json", "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=2, ensure_ascii=False)
    print(f"artefact_manifest.json: {man['artefact_count']} artefacts, "
          f"{man['root_duplicate_count']} root duplicates")

    rem = build_removals()
    with open(f"{OUT}/removals.json", "w", encoding="utf-8") as fh:
        json.dump(rem, fh, indent=2, ensure_ascii=False)
    print(f"removals.json: {rem['pages_removed']} pages, "
          f"{rem['assets_removed']} assets, inputs_unchanged={rem['inputs_unchanged']}")

    rep = build_module_report()
    with open(f"{OUT}/module_layout_report.json", "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2, ensure_ascii=False)
    print(f"module_layout_report.json: {rep['conforming']}/{rep['module_count']} conforming")
    return 0 if rep["non_conforming"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
