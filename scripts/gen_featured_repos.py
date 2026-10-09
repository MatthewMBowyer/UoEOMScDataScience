#!/usr/bin/env python3
"""Record per-card README/description provenance for the featured repositories (AC-74).

For each repository featured on the Projects surface it records:
  - the public URL and whether the repository is public or private,
  - the README fetch result (present/absent) and the README text on which the
    card's description is based, and
  - the repository's own public description (from the GitHub API), used only
    where the README is template boilerplate.

Private repositories must carry NO link. Writes
output/evidence/featured_repos_report.json.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

OWNER = "MatthewMBowyer"
# The repos featured on projects.html, and the card title used there.
FEATURED = [
    ("Essex_MSC_DataScience_Thesis", "Essex MSc Data Science Thesis"),
    ("UoEOMScDataScience", "UoEOMScDataScience e-portfolio"),
    ("PringlePadel", "Pringle Padel"),
    ("The-Bowyer-collective", "The Bowyer Collective"),
    ("Chloes-Traveling-tutors", "Chloe's Travelling Tutors"),
]


def get(url: str, accept: str | None = None):
    req = urllib.request.Request(url)
    if accept:
        req.add_header("Accept", accept)
    req.add_header("User-Agent", "eportfolio-provenance")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def main() -> None:
    pages = open("projects.html", encoding="utf-8").read()
    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "surface": "projects.html (Selected projects)",
           "repos": {}}

    for slug, card_title in FEATURED:
        url = f"https://github.com/{OWNER}/{slug}"
        api = f"https://api.github.com/repos/{OWNER}/{slug}"
        code, body = get(api)
        meta = json.loads(body) if code == 200 and body else {}
        is_private = bool(meta.get("private"))
        desc = meta.get("description") or ""

        rd_code, rd = get(f"https://api.github.com/repos/{OWNER}/{slug}/readme",
                          accept="application/vnd.github.raw")
        # Is the README real project documentation, or HTML5 UP template boilerplate?
        is_boilerplate = bool(re.search(r"html5up\.net|Free for personal and commercial use "
                                        r"under the CCA 3\.0 license", rd, re.I))
        readme_head = rd.strip().splitlines()[0] if rd.strip() else ""

        on_page = url in pages
        # A private repo must not be linked.
        link_ok = (not is_private and on_page) or (is_private and not on_page)

        out["repos"][slug] = {
            "card_title": card_title,
            "url": url,
            "public": not is_private,
            "repo_description": desc,
            "readme_present": rd_code == 200,
            "readme_is_template_boilerplate": is_boilerplate,
            "readme_first_line": readme_head,
            "provenance": (
                "README" if rd_code == 200 and not is_boilerplate
                else ("repo description field" if desc else
                      "repository title only (README is template boilerplate; no invented description)")),
            "linked_on_page": on_page,
            "link_ok": link_ok,
        }

    out["result"] = "PASS" if all(r["link_ok"] for r in out["repos"].values()) else "FAIL"
    os.makedirs("output/evidence", exist_ok=True)
    json.dump(out, open("output/evidence/featured_repos_report.json", "w", encoding="utf-8"),
              indent=2)
    for slug, r in out["repos"].items():
        print(f"{slug}: public={r['public']} readme={r['readme_present']} "
              f"boilerplate={r['readme_is_template_boilerplate']} linked={r['linked_on_page']} "
              f"link_ok={r['link_ok']} provenance={r['provenance']}")
    print("result:", out["result"])


if __name__ == "__main__":
    main()
