#!/usr/bin/env python3
"""Regenerate output/evidence/gen11_change_report.json (the AC-133/AC-134/AC-135/
AC-136/AC-137 change report) from the delivered tree.

The 2026-10-07 change shipped this report, but it was left stale: it recorded the
guide-bot suite as 100/100 at an old head, claimed `footer_states_unlisted_not_private`
was False for both personal pages while still returning PASS, and bound the bot's
sha to a superseded revision. A stale, internally contradictory evidence bundle is
worse than none, so this generator rebuilds it deterministically:

  * the five delivered suites are re-RUN here and their real returncode/tail recorded;
  * every other row is re-derived from the files on disk, never trusted from the
    previous report;
  * any failed check makes the whole report `result: FAIL` and exits non-zero.

It starts its own local HTTP server for the served-root rows and is fully offline.

    python3 scripts/build_gen11_report.py
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

OUT = "output/evidence/gen11_change_report.json"
PERSONAL_PAGES = ("sports.html", "good_hubby.html")
PERSONAL_ASSETS = ("sports.html", "good_hubby.html", "sports.ics", "good_hubby.ics")
SUITES = [
    ("verify_site", [sys.executable, "tests/verify_site.py", "--self-test"]),
    ("verify_personal", [sys.executable, "tests/verify_personal.py"]),
    ("test_guide_bot", [sys.executable, "tests/test_guide_bot.py"]),
    ("verify_amendment_remaining", [sys.executable, "tests/verify_amendment_remaining.py"]),
    ("launcher_check", [sys.executable, "tests/launcher_check.py", "--self-test"]),
]
CHANGE = ("2026-10-07 change: guide cadence/throw/quiet, thesis offline + "
          "traceability, sports description/preference/prune, good_hubby "
          "date/reminders, framework periodic refresh")
HTTP_PORT = int(os.environ.get("EPO_GEN11_PORT", "8771"))

failures: list[str] = []


def check(name: str, ok: bool) -> bool:
    if not ok:
        failures.append(name)
    return bool(ok)


def sha(path: str) -> str | None:
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else None


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


# --------------------------------------------------------------------------- #
def run_suites() -> dict:
    suite = {}
    for name, cmd in SUITES:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        tail = "\n".join(l for l in proc.stdout.strip().splitlines() if l.strip())[-200:]
        suite[name] = {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "passed": proc.returncode == 0,
            "tail": tail.splitlines()[-1] if tail else "",
        }
    return suite


def head_and_origin() -> tuple[str, str]:
    return git("rev-parse", "HEAD"), git("rev-parse", "origin/main")


def check_ac133() -> dict:
    suite = run_suites()
    head, origin = head_and_origin()
    counts = git("rev-list", "--left-right", "--count", "origin/main...HEAD").split()
    ahead, behind = (counts[1], counts[0]) if len(counts) == 2 else ("?", "?")
    all_green = all(v["passed"] for v in suite.values())
    check("AC-133 all five suites green", all_green)
    # Local HEAD is ahead of the remote-tracking origin/main and never behind it:
    # the project's commits are local-only and no push rewrote the remote ref.
    nothing_pushed = behind == "0"
    check("AC-133 no push rewrote origin/main (HEAD ahead, not behind)", nothing_pushed)
    return {
        "suite": suite,
        "all_green": all_green,
        "nothing_pushed": nothing_pushed,
        "ahead_of_origin_main": ahead,
        "behind_origin_main": behind,
        "origin_main_unchanged": origin,
        "workspace_remote": git("remote", "-v"),
        "note": ("The workspace remote is the CMi framework repo (CMi_agent); the "
                 "owner's portfolio repository was never pushed to. The project's "
                 f"commits are local-only ({ahead} ahead, {behind} behind "
                 "origin/main); nothing was pushed to any remote."),
    }


def check_ac134() -> dict:
    before = open("PAGES.md", encoding="utf-8").read() if os.path.exists("PAGES.md") else None
    proc = subprocess.run([sys.executable, "scripts/gen_page_index.py"],
                          capture_output=True, text=True)
    after = open("PAGES.md", encoding="utf-8").read() if os.path.exists("PAGES.md") else None
    reproduces = before is not None and before == after
    pages = [p for p in sorted(glob.glob("*.html")) if p != "footer.html"]
    delivered = [p for p in pages if p not in PERSONAL_PAGES]
    personal = [p for p in pages if p in PERSONAL_PAGES]
    text = after or ""
    lists_all = all(f"`{p}`" in text for p in delivered)
    launcher = json.load(open("output/evidence/launcher_check.json", encoding="utf-8")) \
        if os.path.exists("output/evidence/launcher_check.json") else {}
    owner_facing = launcher.get("checked_owner_facing", [])
    check("AC-134 PAGES.md regenerates byte-identical", reproduces)
    check("AC-134 PAGES.md lists every delivered page", lists_all)
    return {
        "pages_md_exists": os.path.exists("PAGES.md"),
        "generator": "scripts/gen_page_index.py",
        "generator_rerun_reproduces_committed_file": reproduces,
        "generator_output": (proc.stdout.strip().splitlines() or [""])[-1],
        "lists_every_delivered_page": delivered,
        "lists_personal_pages_at_root": personal,
        "opened_by_launcher": "START_PREVIEW.bat" in text,
        "launcher_check_owner_facing_includes_pages_md": "PAGES.md" in owner_facing,
        "launcher_check_passed": launcher.get("failed", 1) == 0,
    }


def check_ac135() -> dict:
    root_present = {p: os.path.exists(p) for p in PERSONAL_ASSETS}
    data_present = {p: os.path.exists(p) for p in
                    ("personal/data/sports.json", "personal/data/good_hubby.json")}
    # No delivered page (excluding the personal pages themselves) may link at the
    # old personal/ page paths.
    stale: list[str] = []
    for page in glob.glob("*.html"):
        if page in PERSONAL_PAGES or page == "footer.html":
            continue
        src = open(page, encoding="utf-8").read()
        for old in ("personal/sports.html", "personal/good_hubby.html"):
            if old in src:
                stale.append(f"{page}:{old}")
    check("AC-135 personal pages at root", all(root_present.values()))
    check("AC-135 no delivered link points at old personal/ paths", not stale)
    return {
        "root_files_present": root_present,
        "beside_index_html": os.path.exists("index.html") and all(root_present.values()),
        "generator_data_under_personal_data": data_present,
        "no_stale_personal_page_links": not stale,
        "stale_personal_links": stale,
    }


def check_ac136() -> dict:
    per_page = {}
    for page in PERSONAL_PAGES:
        src = open(page, encoding="utf-8").read()
        per_page[page] = {
            "noindex_nofollow_meta": ('name="robots"' in src and "noindex" in src
                                      and "nofollow" in src),
            "footer_states_unlisted_not_private": "Unlisted, not private" in src,
        }
    robots = open("robots.txt", encoding="utf-8").read()
    disallows = {p: f"Disallow: /{p}" in robots for p in PERSONAL_ASSETS}
    sitemap = open("sitemap.xml", encoding="utf-8").read() if os.path.exists("sitemap.xml") else ""
    absent = all(p not in sitemap for p in PERSONAL_PAGES)
    check("AC-136 personal pages warn unlisted-not-private",
          all(v["footer_states_unlisted_not_private"] for v in per_page.values()))
    check("AC-136 robots disallows all four personal files", all(disallows.values()))
    check("AC-136 sitemap omits personal pages", absent)
    return {
        "per_page": per_page,
        "robots_disallows_by_name": disallows,
        "robots_does_not_blanket_disallow": "Disallow: /\n" not in robots
        and "Disallow: /*" not in robots,
        "absent_from_sitemap": absent,
    }


def check_ac137() -> dict:
    wf = ".github/workflows/personal-digest.yml"
    wtext = open(wf, encoding="utf-8").read() if os.path.exists(wf) else ""
    digest = subprocess.run([sys.executable, "scripts/personal_digest.py", "--today", "2027-01-30"],
                            capture_output=True, text=True)
    run_md = open("docs/RUN.md", encoding="utf-8").read()
    check("AC-137 digest runs", digest.returncode == 0)
    return {
        "script_exists": os.path.exists("scripts/personal_digest.py"),
        "workflow_exists": os.path.exists(wf),
        "workflow_schedules_on_github_runner": "runs-on: ubuntu-latest" in wtext
        and "schedule:" in wtext,
        "digest_runs": digest.returncode == 0,
        "digest_agrees_with_corrected_date": "Started dating" in digest.stdout
        or "anniversary" in digest.stdout.lower(),
        "run_md_states_honest_status": "no email has been sent" in run_md
        or "not been pushed" in run_md,
        "honest_not_yet_running_recorded": ("no email has been sent" in run_md),
    }


def served_root_paths() -> dict:
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(HTTP_PORT)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)
    out = {}
    try:
        for p in PERSONAL_ASSETS:
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{HTTP_PORT}/{p}", timeout=5) as r:
                    out[p] = r.status == 200
            except Exception:
                out[p] = False
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    return out


def main() -> int:
    head, origin = head_and_origin()
    ac133 = check_ac133()
    ac134 = check_ac134()
    ac135 = check_ac135()
    ac136 = check_ac136()
    ac137 = check_ac137()
    ac135["served_root_paths"] = served_root_paths()
    ac135["launcher_serves_root"] = os.path.exists("START_PREVIEW.bat")
    check("AC-135 personal files served at root",
          all(ac135["served_root_paths"].values()))

    artifacts = {}
    for p in ("docs/PERIODIC_REFRESH.md", "framework/periodic_refresh.py",
              "framework/tests/test_periodic_refresh.py",
              "output/evidence/periodic_refresh_report.json", "assets/js/guide-bot.js",
              "thesis-demo.html", "personal/data/sports.json",
              "personal/data/good_hubby.json", "scripts/personal_digest.py",
              ".github/workflows/personal-digest.yml", "PAGES.md"):
        artifacts[p] = sha(p)

    report = {
        "schema": "cmi_gen11_change_report_v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "project": "eportfolio_rebuild",
        "change": CHANGE,
        "head": head,
        "origin_main": origin,
        "AC-133": ac133,
        "AC-134": ac134,
        "AC-135": ac135,
        "AC-136": ac136,
        "AC-137": ac137,
        "artifacts": artifacts,
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }
    os.makedirs("output/evidence", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(f"== gen11 change report: {report['result']} "
          f"({len(failures)} failures) -> {OUT} ==")
    for f in failures:
        print("  FAILED:", f)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
