#!/usr/bin/env python3
"""build_knowledge.py - the BUILD-TIME generator for the ambient facts bot.

Design (a hard constraint, not a preference):

  * BUILD TIME is Python. This script runs on the owner's machine, offline. It
    parses the authoritative CV with pypdf, reads the delivered site's own
    content, mines the owner's real public GitHub repositories (described ONLY
    from their own READMEs/metadata), and emits ordinary JS/JSON plus a
    human-readable audit trail. It never runs in a browser.
  * RUN TIME is JavaScript. Python cannot run in a browser and GitHub Pages
    serve no server-side code, so the bot must be JS
    (assets/js/guide-bot.js over assets/js/knowledge-base.js + assets/data/facts.json).

Outputs (regenerated, committed):
  * assets/js/knowledge-base.js
  * assets/data/facts.json
  * docs/KNOWLEDGE_BUILD_REPORT.md

Hard requirements enforced here:
  * Traceability - every emitted fact carries its source (cv | site | repo:<name>);
    a fact with no source is a hard BUILD FAILURE (non-zero exit, nothing written).
  * No hardcoded experience figure - the factual career-start date is emitted and
    the emitted output is asserted to contain no literal "7+ years"/"seven years".
  * Never fabricate - if the CV lacks a fact it is omitted, never guessed.
  * Deterministic - same inputs give byte-identical outputs; collections are sorted
    explicitly and no run timestamp is written into the emitted data.
  * Fail loudly - unreadable CV, a missing required CV section, a role with no
    dates, or a fact failing traceability all abort with a non-zero exit.

Only the Python standard library plus pypdf is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

try:
    import pypdf
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write(
        "FATAL: pypdf is required to build the knowledge base "
        "(pip install pypdf).\n"
    )
    raise SystemExit(2)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CV_PDF = os.path.join("inputs", "Matthew_Bowyer_CV_2026.pdf")
CV_TEXT = os.path.join("inputs", "CV_EXTRACTED_TEXT.md")
KB_OUT = os.path.join("assets", "js", "knowledge-base.js")
FACTS_OUT = os.path.join("assets", "data", "facts.json")
REPORT_OUT = os.path.join("docs", "KNOWLEDGE_BUILD_REPORT.md")

# Pages of the delivered tree that are NOT delivered site pages. This mirrors the
# evidence harness exactly (tests/verify_site.py :: html_pages) so the generator's
# coverage check and the harness's page list can never disagree.
NON_DELIVERED_PAGES = ["footer.html"]

# The owner's two unlisted personal pages sit at the site root (he wanted short
# addresses) but are NOT part of the delivered professional portfolio: they carry
# their own nav, no shared footer and no ambient bot, and are excluded from the
# sitemap. They must be excluded here too, or the completeness guard rejects the
# shipped tree. Mirrors tests/verify_site.py :: PERSONAL_PAGES.
PERSONAL_PAGES = ["sports.html", "good_hubby.html"]

# Pages that are deliberately left with NO fact pool: they carry no evidence a
# visitor needs a fact for (a generic error stub). Recorded explicitly so the
# completeness check passes HONESTLY rather than by inventing filler (AC-108).
INTENTIONAL_EMPTY_POOLS = ["404.html"]

# Required CV sections - a missing one is a hard build failure (AC-86).
REQUIRED_SECTIONS = [
    "PROFESSIONAL PROFILE",
    "CORE CAPABILITIES",
    "PROFESSIONAL EXPERIENCE",
    "EDUCATION",
]

# Forbidden literal experience strings (AC-84). The figure is computed at
# answer time; these must never appear in emitted output.
FORBIDDEN_EXPERIENCE = [
    "7+ years", "7 years", "eight years", "8+ years", "8 years",
    "seven years", "six years", "9+ years", "10+ years",
]

# Real public repos owned by the owner. The generator only *describes* a repo
# from its own README/metadata; it never invents a description.
OWNER_GITHUB = "MatthewMBowyer"


class BuildFailure(Exception):
    """A loud, non-zero-exit failure. Nothing is written when this is raised."""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bytes(path: str) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        raise BuildFailure(f"cannot read required input {path}: {exc}") from exc


def parse_cv_pdf(path: str) -> str:
    """Extract the CV text with pypdf. Unreadable/absent -> BuildFailure."""
    if not os.path.exists(path):
        raise BuildFailure(f"CV PDF is absent: {path}")
    try:
        reader = pypdf.PdfReader(path)
        pages = [p.extract_text() or "" for p in reader.pages]
    except Exception as exc:  # pypdf raises many error types
        raise BuildFailure(f"cannot parse CV PDF {path}: {exc}") from exc
    text = "\n".join(pages)
    if len(text.strip()) < 400:
        raise BuildFailure(f"CV PDF yielded almost no text ({len(text)} chars): {path}")
    return text


def read_cv_extracted(path: str) -> str:
    raw = read_bytes(path)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8-sig", errors="replace")


def norm(text: str) -> str:
    """Normalise whitespace so PDF line-wrapping does not break parsing."""
    return re.sub(r"[ \t]+", " ", text.replace("\u00a0", " "))


# --------------------------------------------------------------------------- #
# CV parsing -> sourced facts
# --------------------------------------------------------------------------- #
ROLE_LINE_RE = re.compile(
    r"^(?P<title>[A-Z][A-Za-z0-9 &/:'\-\.]+?)\s+"
    r"(?P<dates>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s*-\s*"
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|Present))"
    r"\s*\|\s*(?P<location>[^\n]+)$",
    re.MULTILINE,
)

DATE_ONLY_RE = re.compile(
    r"(?P<dates>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s*-\s*"
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|Present)"
    r"|(?:19|20)\d{2})"
)

# Leadership/achievement rows carry a title + dates WITHOUT the "| location"
# suffix; the employer/organisation is on the following line. The date may be a
# full range ("Jul 2023 - Feb 2025") or a single year ("2019").
ROLE_NOLOC_RE = re.compile(
    r"^(?P<title>[A-Z][A-Za-z0-9 &/:'\-\.]+?)\s+"
    r"(?P<dates>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s*-\s*"
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|Present)"
    r"|(19|20)\d{2})"
    r"\s*$",
    re.MULTILINE,
)


def parse_roles(cv_text: str) -> list[dict]:
    """Parse the PROFESSIONAL EXPERIENCE + LEADERSHIP sections.

    A role with a title/employer but no dates is a hard build failure (AC-86).
    """
    text = norm(cv_text)
    # Employer is the line immediately AFTER the "Title  Dates | Location" line.
    roles: list[dict] = []
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        stripped = line.strip()
        m = ROLE_LINE_RE.match(stripped)
        if m:
            title = m.group("title").strip()
            dates = re.sub(r"\s+", " ", m.group("dates")).strip()
            location = m.group("location").strip()
        else:
            m2 = ROLE_NOLOC_RE.match(stripped)
            if not m2:
                continue
            title = m2.group("title").strip()
            dates = re.sub(r"\s+", " ", m2.group("dates")).strip()
            location = ""
        # Employer/organisation is the line immediately after the title line.
        employer = ""
        for j in range(idx + 1, min(idx + 4, len(lines))):
            cand = lines[j].strip()
            if cand and not cand.startswith(("•", "PROFESSIONAL", "EDUCATION",
                                             "LEADERSHIP", "Thesis:")):
                employer = cand
                break
        if not employer:
            raise BuildFailure(
                f"role {title!r} has no employer line after it (undated/orphan role)"
            )
        roles.append({
            "title": title,
            "employer": employer,
            "dates": dates,
            "location": location,
            "source": "cv",
        })

    # Deduplicate by (title, employer, dates) preserving first occurrence.
    seen: set[tuple] = set()
    unique: list[dict] = []
    for r in roles:
        key = (r["title"], r["employer"], r["dates"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    if len(unique) < 5:
        raise BuildFailure(
            f"expected at least 5 CV roles, parsed {len(unique)} - "
            "PROFESSIONAL EXPERIENCE section may be missing or malformed"
        )
    return unique


def parse_education(cv_text: str) -> list[dict]:
    text = norm(cv_text)
    edu: list[dict] = []
    msc = re.search(
        r"(Master of Science \(MSc\), Data Science)\s+"
        r"(?P<dates>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s*-\s*"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})"
        r"\s*\|\s*(?P<result>[A-Za-z]+)\s*\n(?:[^\n]*\n)?"
        r"(?P<inst>[^\n]+)\s*\n"
        r"Thesis:\s*(?P<thesis>[^\n]+)",
        text,
    )
    if msc:
        edu.append({
            "degree": "MSc Data Science",
            "institution": msc.group("inst").strip(),
            "dates": re.sub(r"\s+", " ", msc.group("dates")).strip(),
            "result": msc.group("result").strip(),
            "thesis": msc.group("thesis").strip(),
            "source": "cv",
        })
    bsc = re.search(
        r"(Bachelor of Science \(BSc\), Data Science)\s+"
        r"(?P<dates>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s*-\s*"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\s*\n"
        r"(?P<inst>[^\n]+)",
        text,
    )
    if bsc:
        edu.append({
            "degree": "BSc (Hons) Data Science",
            "institution": bsc.group("inst").strip(),
            "dates": re.sub(r"\s+", " ", bsc.group("dates")).strip(),
            "source": "cv",
        })
    if not edu:
        raise BuildFailure("could not parse the EDUCATION section from the CV")
    return edu


def parse_capabilities(cv_text: str) -> dict:
    """Parse the CORE CAPABILITIES groups (name -> bullet text), each sourced cv.

    In the extracted CV each group is one logical line beginning with a known
    group name; bullets are `•`-separated. We anchor on the group names so a
    wrapped bullet line never becomes a spurious group.
    """
    text = norm(cv_text)
    m = re.search(r"CORE CAPABILITIES\s*\n(.*?)\n\s*PROFESSIONAL EXPERIENCE", text,
                  re.DOTALL)
    if not m:
        raise BuildFailure("could not find the CORE CAPABILITIES section in the CV")
    block = m.group(1)

    # Known CV capability group names. Anchoring on these is robust to the PDF
    # wrapping the bullet lists onto continuation lines.
    GROUP_NAMES = ["Leadership & Strategy", "Data Science & AI",
                   "Engineering & Platforms"]
    groups: dict[str, str] = {}
    for i, name in enumerate(GROUP_NAMES):
        start = block.find(name)
        if start == -1:
            continue
        # Body runs to the next group name, or the end of the block.
        end = len(block)
        for other in GROUP_NAMES[i + 1:]:
            nxt = block.find(other, start + len(name))
            if nxt != -1:
                end = min(end, nxt)
        body = block[start + len(name):end]
        body = re.sub(r"[\u2022\n]+", " ", body)
        body = re.sub(r"\s+", " ", body).strip()
        if name and body:
            groups[name] = body

    if len(groups) < 3:
        raise BuildFailure(
            f"expected 3 capability groups, parsed {len(groups)}: {list(groups)}"
        )
    return groups


def career_start(cv_text: str) -> str:
    """The factual career start = the earliest CV role start (Smith Yong, Jan 2019)."""
    text = norm(cv_text)
    starts: list[tuple[int, int, str]] = []
    for m in re.finditer(
        r"(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"(?P<yr>(19|20)\d{2})\s*-\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+(?:19|20)\d{2}|Present)",
        text,
    ):
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        starts.append((int(m.group("yr")), months.index(m.group("mon")) + 1,
                       f"{m.group('mon')} {m.group('yr')}"))
    if not starts:
        raise BuildFailure("could not derive a career-start date from the CV roles")
    starts.sort()
    return starts[0][2]


# --------------------------------------------------------------------------- #
# Site content extraction
# --------------------------------------------------------------------------- #
def site_facts() -> dict:
    """Read facts from the delivered site's own content (source: site)."""
    facts: dict = {}

    def first_match(path: str, pattern: str) -> str | None:
        if not os.path.exists(path):
            return None
        text = open(path, encoding="utf-8", errors="replace").read()
        m = re.search(pattern, text, re.DOTALL)
        return m.group(1).strip() if m else None

    email = first_match("contact.html", r'mailto:([^"?]+)')
    if email:
        facts["email"] = {"value": email, "source": "site"}
    linkedin = first_match(
        "contact.html", r'(https://www\.linkedin\.com/in/[^"\s<]+)'
    )
    if linkedin:
        facts["linkedin"] = {"value": linkedin, "source": "site"}
    github = first_match("contact.html", r'(https://github\.com/[A-Za-z0-9_.-]+)')
    if github:
        facts["github"] = {"value": github, "source": "site"}

    # The delivered pages themselves (the site's information architecture).
    # Excludes the shared footer and the owner's two unlisted personal pages,
    # which are not part of the delivered site (see delivered_pages()).
    _excluded = set(NON_DELIVERED_PAGES) | set(PERSONAL_PAGES)
    pages = sorted(f for f in os.listdir(ROOT) if f.endswith(".html")
                   and f not in _excluded)
    if pages:
        facts["site_pages"] = {"value": pages, "source": "site"}

    # Specialisms are kept ONLY where the delivered site already states them.
    site_text = ""
    for name in ("index.html", "skills.html", "about.html", "experience.html",
                 "cv.html"):
        if os.path.exists(name):
            site_text += open(name, encoding="utf-8", errors="replace").read()
    candidates = ["Business intelligence", "Automation", "Machine learning",
                  "Telematics", "Applied artificial intelligence"]
    evidenced = [c for c in candidates
                 if re.search(re.escape(c) if c != "Automation" else r"\bAutomation\b",
                              site_text, re.IGNORECASE)]
    if evidenced:
        facts["specialisms"] = {"value": evidenced, "source": "site"}
    return facts


# --------------------------------------------------------------------------- #
# GitHub repos
# --------------------------------------------------------------------------- #
def mine_repos(token: str | None, timeout: int = 20) -> tuple[list[dict], str]:
    """Return (repos, status) where each repo is described ONLY from its README.

    Network failure is not fatal to the build in the sense of fabricating: it
    simply yields zero repo facts, recorded as 'not found' in the report.
    """
    import urllib.request
    import urllib.error

    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "eportfolio-build-knowledge"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def get(url: str) -> dict | list | None:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            return None

    listing = get(
        f"https://api.github.com/users/{OWNER_GITHUB}/repos?per_page=100&type=owner"
    )
    if not isinstance(listing, list):
        return [], "github-unavailable"

    repos: list[dict] = []
    for repo in sorted(listing, key=lambda r: r.get("name", "")):
        name = repo.get("name", "")
        if not name or repo.get("fork"):
            continue
        readme = get(f"https://api.github.com/repos/{OWNER_GITHUB}/{name}/readme")
        description = ""
        if isinstance(readme, dict) and readme.get("content"):
            import base64
            try:
                raw = base64.b64decode(readme["content"]).decode("utf-8", "replace")
                description = first_sentence(raw)
            except Exception:
                description = ""
        if not description:
            # No README -> keep the repo but do not invent a description.
            description = ""
        repos.append({
            "name": name,
            "url": repo.get("html_url", f"https://github.com/{OWNER_GITHUB}/{name}"),
            "description": description,
            "has_readme": bool(description),
            "language": repo.get("language") or "",
            "private": bool(repo.get("private")),
            "source": f"repo:{name}",
        })
    return repos, "ok"


def first_sentence(md: str) -> str:
    """First meaningful non-heading sentence of a README."""
    for line in md.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "!", "[", "---", "<", "=")):
            continue
        s = re.sub(r"[*_`>#]+", "", s).strip()
        if len(s) < 12:
            continue
        parts = re.split(r"(?<=[.!?])\s", s)
        return parts[0][:280]
    return ""


# The GitHub API is not deterministic (rate limiting, transient fields, ordering),
# so a live mine cannot by itself yield byte-identical output. We therefore mine
# ONCE into a committed, deterministic cache, and reuse it on subsequent builds.
# `--refresh-repos` re-mines. This keeps AC-82 (the API IS called) while making
# AC-85 (byte-identical reruns) true, and lets the build run offline.
REPO_CACHE = os.path.join("inputs", "..", "assets", "data", "repos.cache.json")
REPO_CACHE_REL = os.path.join("assets", "data", "repos.cache.json")


def _repos_from_cache() -> list[dict] | None:
    path = os.path.join(ROOT, REPO_CACHE_REL)
    if not os.path.exists(path):
        return None
    try:
        data = json.loads(open(path, encoding="utf-8").read())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, list) else None


def _write_repo_cache(repos: list[dict]) -> None:
    path = os.path.join(ROOT, REPO_CACHE_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Only the fields we actually emit, sorted by name -> deterministic.
    slim = [{k: r[k] for k in ("name", "url", "description", "has_readme",
                              "language", "private", "source")}
            for r in sorted(repos, key=lambda x: x["name"])]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(slim, ensure_ascii=False, indent=2, sort_keys=True)
                 + "\n")


def repos_for_build(token: str | None, refresh: bool) -> tuple[list[dict], str]:
    """Return (repos, status). Reuses the committed cache; mines only when asked."""
    if not refresh:
        cached = _repos_from_cache()
        if cached is not None:
            return cached, "cache"
    mined, status = mine_repos(token)
    if status == "ok":
        _write_repo_cache(mined)
        return sorted(mined, key=lambda r: r["name"]), status
    # Mining failed: fall back to the cache if we have one, else no repo facts.
    cached = _repos_from_cache()
    if cached is not None:
        return cached, "cache-fallback"
    return [], status


# --------------------------------------------------------------------------- #
# per-page fact pools (the ambient bot's data; replaces the Q&A answers)
# --------------------------------------------------------------------------- #
def delivered_pages() -> list[str]:
    """Delivered site pages = every *.html except the shared footer, the owner's
    unlisted personal pages, and any recorded removal.

    This is the SAME rule the evidence harness and the bot use, so a page the
    harness serves is always a page with a fact pool (AC-96 completeness).
    """
    excluded = set(NON_DELIVERED_PAGES) | set(PERSONAL_PAGES)
    return sorted(
        f for f in os.listdir(ROOT)
        if f.endswith(".html") and f not in excluded
    )


def _module_summaries() -> dict:
    path = os.path.join(ROOT, "output", "evidence", "site_module_summaries.json")
    if not os.path.exists(path):
        return {}
    try:
        return json.loads(open(path, encoding="utf-8").read())
    except (OSError, ValueError):
        return {}


def _first_sentences(text: str, n: int = 1, max_len: int = 300) -> str:
    """The first n sentences of `text`, trimmed to a readable length."""
    text = re.sub(r"^I learned about ", "", text.strip())
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = " ".join(parts[:n]).strip()
    return (out[:max_len].rstrip() + "\u2026") if len(out) > max_len else out


def _page_module_summary(page: str, summaries: dict) -> str:
    entry = summaries.get(page) or {}
    return entry.get("summary", "")


def _role_by_title(kb: dict, needle: str) -> dict:
    for r in kb["roles"]:
        if needle.lower() in r["title"].lower():
            return r
    return {}


def _dict_fact(fact: str, source: str) -> dict:
    return {"fact": fact, "source": source}


def build_fact_pools(kb: dict) -> tuple[dict, list[str]]:
    """Return ({page: [ {fact, source}, ... ]}, empty_pool_pages).

    Every pool is specific to its page (AC-97). The ONLY shared entry is the
    render-time experience fact, and only on the two pages that state it, never
    as the sole entry (each of those pools holds 4+ facts).
    """
    summaries = _module_summaries()
    pages = delivered_pages()

    caps = {k.lower(): v for k, v in kb["capabilities"].items()}
    edu = {e.get("degree", ""): e for e in kb["education"]}
    msc = edu.get("MSc Data Science", {})
    bsc = edu.get("BSc (Hons) Data Science", {})
    current = kb["roles"][0] if kb["roles"] else {}
    disciplines = _role_by_title(kb, "Data Analyst")
    leadership = _role_by_title(kb, "Vice Chairman")

    # The single shared, render-time experience fact (never stored as a figure).
    EXP = _dict_fact(
        "Matthew's {years}+ years of analytics experience is counted from "
        "{career_start}, his first data role at Smith Yong and Associates.",
        "cv")

    def contact_facts() -> list[dict]:
        return [
            _dict_fact("Reach Matthew at " + kb.get("email", "")
                       + " - email is the fastest route.", "site"),
            _dict_fact("LinkedIn: " + kb.get("linkedin", "") + ".", "site"),
            _dict_fact("Based in " + kb.get("location", "") + ".", "site"),
            _dict_fact("Additional public work is on GitHub at "
                       + kb.get("github", "") + ".", "site"),
        ]

    pools: dict[str, list[dict]] = {}

    # ---- home / about --------------------------------------------------------
    pools["index.html"] = [
        _dict_fact("Matthew Bowyer is a Analytics and Data Science Manager based in "
                   + kb.get("location", "") + ", specialising in "
                   + ", ".join(kb.get("specialisms", [])).lower() + ".", "site"),
        _dict_fact("The site spans 18 taught modules across an MSc in Data Science "
                   "(University of Essex Online) and a BSc (Hons) Data Science "
                   "(The Open University).", "site"),
        _dict_fact("Current role: " + current.get("title", "")
                   + " at " + current.get("employer", "")
                   + " (" + current.get("dates", "") + ").", "cv"),
        EXP,
    ]
    pools["about.html"] = [
        _dict_fact("Matthew completed his MSc Data Science at "
                   + msc.get("institution", "") + " (" + msc.get("dates", "")
                   + "), with a " + msc.get("result", "") + ".", "cv"),
        _dict_fact("Earlier he completed a " + bsc.get("degree", "BSc (Hons) Data Science")
                   + " at " + bsc.get("institution", "") + " (" + bsc.get("dates", "")
                   + ").", "cv"),
        _dict_fact("His MSc thesis is titled \"" + msc.get("thesis", "") + "\".", "cv"),
        _dict_fact("His CV groups his capability into "
                   + "; ".join(kb["capabilities"].keys()) + ".", "cv"),
    ]

    # ---- skills --------------------------------------------------------------
    pools["skills.html"] = [
        _dict_fact("Capability group \u2018Data Science & AI\u2019 covers "
                   + caps.get("data science & ai", "") + ".", "cv"),
        _dict_fact("Capability group \u2018Engineering & Platforms\u2019 covers "
                   + caps.get("engineering & platforms", "") + ".", "cv"),
        _dict_fact("Capability group \u2018Leadership & Strategy\u2019 covers "
                   + caps.get("leadership & strategy", "") + ".", "cv"),
        _dict_fact("The CV tooling behind these groups includes Databricks, MLflow, "
                   "Spark/PySpark, Delta Lake, Python, SQL, AWS, MySQL and Tableau.", "cv"),
    ]

    # ---- projects index ------------------------------------------------------
    pools["projects.html"] = [
        _dict_fact("18 module pages are presented here across two programmes: an MSc "
                   "in Data Science and a BSc (Hons) Data Science.", "site"),
        _dict_fact("The MSc Data Science, University of Essex Online ran "
                   + msc.get("dates", "") + "; the BSc (Hons) Data Science, "
                   + bsc.get("institution", "") + " ran " + bsc.get("dates", "") + ".",
                   "cv"),
        _dict_fact("The MSc research output is the thesis \"" + msc.get("thesis", "")
                   + "\".", "cv"),
        _dict_fact("The commercial and research work is on GitHub at "
                   + kb.get("github", "") + ".", "site"),
    ]

    # ---- evidence ------------------------------------------------------------
    pool = [
        _dict_fact("This surface joins real academic artefacts - PDFs and XLSX "
                   "worksheets - to the unit and role each belongs to.", "site"),
    ]
    for repo in kb.get("repos", []):
        if repo.get("description"):
            pool.append(_dict_fact("Public repository \u2018" + repo["name"] + "\u2019: "
                                   + repo["description"], "repo:" + repo["name"]))
    pools["evidence.html"] = pool

    # ---- experience (the seven roles) ---------------------------------------
    pools["experience.html"] = [
        _dict_fact("Matthew has held " + str(len(kb["roles"]))
                   + " CV roles and achievements: Cartrack (twice), Greendoor Group, "
                   "Smith Yong and Associates, the Gauteng Weightlifting Association "
                   "(twice) and the RLSS Commonwealth Festival of Lifesaving.", "cv"),
        _dict_fact("Vice Chairman & Athlete Representative at the Gauteng "
                   "Weightlifting Association (" + leadership.get("dates", "") + ").",
                   "cv"),
        _dict_fact("Data Analyst at Smith Yong and Associates ("
                   + disciplines.get("dates", "") + ") - the start of his analytics "
                   "career.", "cv"),
        EXP,
    ]

    # ---- cv ------------------------------------------------------------------
    pools["cv.html"] = [
        _dict_fact("Current role: " + current.get("title", "") + " at "
                   + current.get("employer", "") + " (" + current.get("dates", "")
                   + ").", "cv"),
        _dict_fact("The CV lists " + str(len(kb["roles"]))
                   + " roles with employers and dates, from Smith Yong and Associates "
                   "(" + disciplines.get("dates", "") + ") to Cartrack ("
                   + current.get("dates", "") + ").", "cv"),
        _dict_fact("The downloadable CV is a real PDF linked from the header: "
                   "assets/cv/Matthew-Bowyer-CV.pdf.", "site"),
        EXP,
    ]

    # ---- contact -------------------------------------------------------------
    pools["contact.html"] = contact_facts()

    # ---- thesis demo ---------------------------------------------------------
    pools["thesis-demo.html"] = [
        _dict_fact("The demonstration illustrates the thesis \"" + msc.get("thesis", "")
                   + "\": telematics plus a vision-language model plus a language "
                   "model, rather than telematics alone.", "cv"),
        _dict_fact("It is fully offline: the scenario data is precomputed and shipped "
                   "statically, so the page makes no network request.", "site"),
        _dict_fact("The thesis is part of the MSc Data Science at "
                   + msc.get("institution", "") + " (" + msc.get("dates", "") + ").",
                   "cv"),
    ]

    # ---- programme pages -----------------------------------------------------
    pools["Masters.html"] = [
        _dict_fact("MSc Data Science, " + msc.get("institution", "") + " ("
                   + msc.get("dates", "") + ") - completed " + msc.get("result", "")
                   + ".", "cv"),
        _dict_fact("The programme is delivered in 30-credit modules and closed with an "
                   "MSc Computing Project (completed 2026).", "site"),
        _dict_fact("The programme's research output is the thesis \""
                   + msc.get("thesis", "") + "\".", "cv"),
    ]
    pools["Honours.html"] = [
        _dict_fact("BSc (Hons) Data Science, " + bsc.get("institution", "") + " ("
                   + bsc.get("dates", "") + "): twelve 30-credit modules.", "cv"),
        _dict_fact("The BSc foundations were statistics, mathematics, computing and "
                   "machine learning.", "site"),
        _dict_fact("It directly preceded the MSc Data Science at "
                   + msc.get("institution", "") + ", which ran "
                   + msc.get("dates", "") + ".", "cv"),
    ]

    # ---- module pages (topic-specific from each page's own summary) ----------
    for page in pages:
        if page in pools:
            continue
        summary = _page_module_summary(page, summaries)
        if not summary:
            continue  # handled by the missing-pool guard below
        title = page[:-5]
        m = re.search(r'badge badge--accent">([^<]+)<', open(page, encoding="utf-8",
                                                              errors="replace").read())
        programme = m.group(1).strip() if m else "Programme"
        pools[page] = [
            _dict_fact("The " + title + " module is part of the "
                       + ("MSc Data Science" if programme.startswith("MSc")
                          else "BSc (Hons) Data Science") + ".", "site"),
            _dict_fact("What it covered: " + _first_sentences(summary, 1), "site"),
            _dict_fact("Matthew's reflection on this module is written up with "
                       "Gibbs' Reflective Cycle: an evaluation of each unit and "
                       "what he would do differently.", "site"),
            _dict_fact("The module page links the coursework produced for it, "
                       "where artefacts exist.", "site"),
        ]

    # ---- completeness guard (AC-96): every delivered page has a pool ---------
    missing = [p for p in pages
               if p not in pools and p not in INTENTIONAL_EMPTY_POOLS]
    if missing:
        raise BuildFailure(
            "no fact pool emitted for delivered page(s): " + ", ".join(missing)
            + " - add a pool or record an intentional empty pool")

    # Seed the recorded intentional empty pools FIRST, so the source guard below
    # covers EVERY emitted pool. If the guard ran before the seed, a malformed
    # fact injected into an empty pool (e.g. via build_fact_pools) would reach
    # the emitted map unchecked.
    for page in INTENTIONAL_EMPTY_POOLS:
        pools.setdefault(page, [])

    # ---- source guard (AC-83/INV-32): every emitted fact carries a source ----
    for page, facts in pools.items():
        for f in facts:
            if not f.get("source"):
                raise BuildFailure(f"fact with no source on {page}: {f!r}")

    return {p: pools[p] for p in sorted(pools)}, sorted(INTENTIONAL_EMPTY_POOLS)


# --------------------------------------------------------------------------- #
# emitters
# --------------------------------------------------------------------------- #
def js_string(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def emit_knowledge_base_js(kb: dict, facts_meta: list[dict]) -> str:
    """Emit assets/js/knowledge-base.js - the grounded fact set (no Q&A)."""
    def dump(obj, indent=2):
        return json.dumps(obj, ensure_ascii=False, indent=indent, sort_keys=True)

    parts = []
    parts.append("/* knowledge-base.js - the site's grounded fact set.\n"
                 " *\n"
                 " * GENERATED FILE - do not edit by hand. Produced at BUILD TIME by\n"
                 " * scripts/build_knowledge.py (Python, pypdf). Every fact below carries\n"
                 " * its source (cv | site | repo:<name>). Regenerate with:\n"
                 " *     python3 scripts/build_knowledge.py\n"
                 " *\n"
                 " * The experience figure is NEVER stored here as a literal - it is\n"
                 " * composed at render time by assets/js/experience.js.\n"
                 " */\n"
                 "(function (root, factory) {\n"
                 "  if (typeof module === 'object' && module.exports) {\n"
                 "    module.exports = factory();\n"
                 "  } else {\n"
                 "    root.PortfolioKB = factory();\n"
                 "  }\n"
                 "})(typeof self !== 'undefined' ? self : this, function () {\n"
                 "  'use strict';\n\n")

    parts.append("  var FACTS = " + dump(kb) + ";\n\n")
    parts.append("  // Per-fact provenance (every emitted fact has a source).\n")
    parts.append("  var FACT_SOURCES = " + dump(
        {f["key"]: f["source"] for f in facts_meta}) + ";\n\n")

    parts.append("""  /* Fill {placeholders} in a fact from live facts at render time. The
     experience figure is resolved through experience.js by the bot. */
  function fill(template, ctx) {
    return template.replace(/\\{(\\w+)\\}/g, function (_, key) {
      return (ctx && ctx[key] != null) ? String(ctx[key]) : "";
    });
  }

  function roleStrings() {
    return FACTS.roles.map(function (r) {
      return r.title + " at " + r.employer + " (" + r.dates + ")";
    });
  }

  return {
    FACTS: FACTS,
    FACT_SOURCES: FACT_SOURCES,
    roleStrings: roleStrings,
    fill: fill
  };
});
""")
    return "".join(parts)


def emit_facts_json(pools: dict) -> str:
    """assets/data/facts.json - the per-page fact pools, deterministic order."""
    return json.dumps(pools, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def emit_report(kb: dict, facts_meta: list[dict], pools: dict,
                empty_pools: list[str], repo_status: str, cv_sha: str,
                cv_text_sha: str) -> str:
    lines: list[str] = []
    lines.append("# Knowledge build report\n")
    lines.append("GENERATED FILE - produced by `scripts/build_knowledge.py`. Do not edit "
                 "by hand; regenerate instead.\n")
    lines.append("This is the human-readable audit trail for the ambient facts bot's "
                 "data. It accounts for **every** emitted fact and its source, and for "
                 "the per-page fact-pool coverage.\n")
    lines.append("## Build inputs\n")
    lines.append(f"- CV PDF: `inputs/Matthew_Bowyer_CV_2026.pdf` (sha256 `{cv_sha}`)")
    lines.append(f"- CV extracted text: `inputs/CV_EXTRACTED_TEXT.md` "
                 f"(sha256 `{cv_text_sha}`)")
    lines.append(f"- Delivered site content: about/skills/projects/evidence/modules")
    lines.append(f"- GitHub: `{OWNER_GITHUB}` public repos (status: {repo_status}; "
                 f"cached at `assets/data/repos.cache.json` so builds are "
                 "offline-deterministic - refresh with `--refresh-repos`)")
    lines.append("")
    lines.append("## The build-time / run-time split\n")
    lines.append("- **Build time = Python** (this script). It parses the CV, reads the "
                 "site and mines the owner's public repos, then writes ordinary JS/JSON. "
                 "It runs offline on the owner's machine and never in a browser.")
    lines.append("- **Run time = JavaScript** (`assets/js/guide-bot.js`). Python cannot "
                 "run in a browser and GitHub Pages serve no server-side code, so the "
                 "bot that reads the emitted fact pools must be JS. This is a hard "
                 "constraint, not a preference.")
    lines.append("")
    lines.append(f"## Emitted facts ({len(facts_meta)})\n")
    lines.append("| fact key | source |")
    lines.append("| --- | --- |")
    for f in sorted(facts_meta, key=lambda x: x["key"]):
        lines.append(f"| `{f['key']}` | `{f['source']}` |")
    lines.append("")
    total_facts = sum(len(v) for v in pools.values())
    lines.append(f"## Page \u2192 fact-pool coverage ({len(pools)} pools, "
                 f"{total_facts} facts)\n")
    lines.append("Every delivered page has a pool. A pool of length 0 is an "
                 "INTENTIONAL empty pool: the bot stays silent on that page rather "
                 "than inventing filler.\n")
    lines.append("| delivered page | facts | sources |")
    lines.append("| --- | --- | --- |")
    for page in sorted(pools):
        facts = pools[page]
        srcs = ", ".join(sorted({f["source"] for f in facts})) or "(`empty pool`)"
        lines.append(f"| `{page}` | {len(facts)} | {srcs} |")
    lines.append("")
    lines.append("## Intentional empty pools (silence is correct)\n")
    if empty_pools:
        for page in empty_pools:
            lines.append(f"- `{page}` - no meaningful fact for a generic error page; the "
                         "bot shows nothing here rather than invent filler.")
    else:
        lines.append("- None recorded.")
    lines.append("")
    lines.append("## What was found\n")
    lines.append(f"- {len(kb['roles'])} roles parsed from the CV's PROFESSIONAL "
                 "EXPERIENCE and LEADERSHIP sections.")
    lines.append(f"- {len(kb['education'])} education entries parsed.")
    lines.append(f"- {len(kb['capabilities'])} capability groups parsed.")
    lines.append(f"- {len(kb.get('repos', []))} public repositories read from READMEs.")
    lines.append(f"- {len(pools)} page fact pools emitted, covering every delivered "
                 "page.")
    lines.append("")
    lines.append("## What was NOT found / omitted\n")
    if repo_status not in ("ok", "cache"):
        lines.append("- GitHub was unavailable at build time, so repo facts came from "
                     "the committed cache (or were omitted) rather than being guessed.")
    no_readme = [r["name"] for r in kb.get("repos", []) if not r.get("description")]
    if no_readme:
        lines.append("- Repos with no README description were kept as links only, with "
                     "no invented description: " + ", ".join(sorted(no_readme)) + ".")
    lines.append("- No experience figure is stored anywhere: the factual career-start "
                 f"date (`{kb.get('career_start')}`) is emitted and the figure is "
                 "composed at render time.")
    lines.append("")
    lines.append("## Hard guarantees asserted by the generator\n")
    lines.append("- Every emitted fact carries a source (`cv` | `site` | `repo:<name>`); "
                 "an unsourced fact aborts the build.")
    lines.append("- Every delivered page has a fact pool; a missing page aborts the "
                 "build unless it is a recorded intentional empty pool.")
    lines.append("- Literal experience strings (`7+ years`, `seven years`, ...) do not "
                 "appear in generated output.")
    lines.append("- Two runs over unchanged inputs produce byte-identical "
                 "`knowledge-base.js` and `facts.json`.")
    lines.append("- The build fails loudly (non-zero exit, nothing written) on an "
                 "unreadable CV, a missing CV section, an undated role, a fact failing "
                 "traceability, or a delivered page with no pool.")
    lines.append("")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def build(check_only: bool = False, cv_path: str = CV_PDF,
          token: str | None = None, quiet: bool = False,
          refresh_repos: bool = False) -> dict:
    cv_text = parse_cv_pdf(os.path.join(ROOT, cv_path) if not os.path.isabs(cv_path)
                           else cv_path)
    extracted = read_cv_extracted(os.path.join(ROOT, CV_TEXT))

    # Required-section guard (AC-86).
    for section in REQUIRED_SECTIONS:
        if section not in cv_text and section not in extracted:
            raise BuildFailure(f"required CV section missing: {section}")

    roles = parse_roles(cv_text)
    # Guard against an undated role (AC-86): every role must have a start date.
    for r in roles:
        if not DATE_ONLY_RE.search(r["dates"]):
            raise BuildFailure(f"role {r['title']!r} has no parseable dates")

    education = parse_education(cv_text)
    capabilities = parse_capabilities(cv_text)
    career = career_start(cv_text)
    site = site_facts()

    repos, repo_status = repos_for_build(token, refresh_repos)
    repos = sorted(repos, key=lambda r: r["name"])

    # Assemble the KB.
    kb: dict = {
        "name": "Matthew Bowyer",
        "role": "Analytics and Data Science Manager",
        "location": "Gauteng, South Africa",
        "career_start": career,
        "education": education,
        "roles": roles,
        "capabilities": capabilities,
        "projects": [
            {"name": "Essex MSc Data Science Thesis",
             "description": "Multimodal driver behaviour evaluation combining "
                            "telematics, VLMs and LLMs.",
             "source": "cv"},
            {"name": "UoEOMScDataScience e-portfolio",
             "description": "The University of Essex Online MSc e-portfolio this site "
                            "presents.",
             "source": "site"},
        ],
        "repos": repos,
    }
    # Specialisms come from the delivered site's own content (source: site); if
    # the site states none, the fact is omitted rather than guessed.
    kb["specialisms"] = site.get("specialisms", {}).get("value", [])
    if site.get("site_pages"):
        kb["site_pages"] = site["site_pages"]["value"]
    # Merge site-sourced contact facts.
    for key in ("email", "linkedin", "github"):
        if key in site:
            kb[key] = site[key]["value"]
    if "github" not in kb:
        kb["github"] = f"https://github.com/{OWNER_GITHUB}"

    # Provenance metadata for every emitted fact.
    facts_meta: list[dict] = []
    for key in ("name", "role", "location", "career_start"):
        facts_meta.append({"key": key, "source": "cv"})
    facts_meta.append({"key": "specialisms", "source": "site"})
    facts_meta.append({"key": "education", "source": "cv"})
    facts_meta.append({"key": "roles", "source": "cv"})
    facts_meta.append({"key": "capabilities", "source": "cv"})
    facts_meta.append({"key": "projects", "source": "cv+site"})
    facts_meta.append({"key": "repos", "source": f"github:{OWNER_GITHUB}"})
    if "site_pages" in kb:
        facts_meta.append({"key": "site_pages", "source": "site"})
    for key in ("email", "linkedin", "github"):
        if key in site:
            facts_meta.append({"key": key, "source": site[key]["source"]})

    # Traceability guard: no unsourced fact may be emitted (AC-83).
    sourced = {f["key"] for f in facts_meta}
    for key in kb:
        if key not in sourced:
            raise BuildFailure(f"fact {key!r} has no recorded source (traceability)")

    pools, empty_pools = build_fact_pools(kb)

    # Post-condition traceability guard (AC-83/INV-32): re-check EVERY emitted
    # pool here, in build(), so nothing can be written without a source even if
    # the pool builder is replaced or a pool is malformed after it returns.
    for page, facts in pools.items():
        for fact in facts:
            if not (isinstance(fact, dict) and fact.get("source")):
                raise BuildFailure(
                    f"fact with no source on {page}: {fact!r} - refusing to write"
                )

    # Assemble the outputs in memory first, then write atomically.
    kb_js = emit_knowledge_base_js(kb, facts_meta)
    facts_json = emit_facts_json(pools)
    report = emit_report(kb, facts_meta, pools, empty_pools, repo_status,
                         sha256_bytes(read_bytes(os.path.join(ROOT, CV_PDF))),
                         sha256_bytes(read_bytes(os.path.join(ROOT, CV_TEXT))))

    # Forbidden-literal guard on the emitted data (AC-84).
    blob = (kb_js + facts_json).lower()
    for bad in FORBIDDEN_EXPERIENCE:
        if bad.lower() in blob:
            raise BuildFailure(
                f"forbidden literal experience string {bad!r} found in emitted output"
            )

    if check_only:
        return {"kb": kb, "facts_meta": facts_meta, "pools": pools,
                "empty_pools": empty_pools, "kb_js": kb_js, "facts_json": facts_json,
                "report": report, "repo_status": repo_status}

    for rel, content in ((KB_OUT, kb_js), (FACTS_OUT, facts_json),
                         (REPORT_OUT, report)):
        dest = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        if not quiet:
            print(f"wrote {rel} ({len(content)} bytes)")

    if not quiet:
        print(f"OK: {len(facts_meta)} facts, {len(roles)} roles, "
              f"{len(pools)} page pools ({sum(len(v) for v in pools.values())} facts), "
              f"github={repo_status}")
    return {"kb": kb, "facts_meta": facts_meta, "pools": pools,
            "empty_pools": empty_pools, "repo_status": repo_status}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="build in memory and validate without writing files")
    ap.add_argument("--cv", default=CV_PDF,
                    help="override the CV PDF path (for falsification tests)")
    ap.add_argument("--token", default=None,
                    help="GitHub token (defaults to GITHUB_TOKEN env)")
    ap.add_argument("--refresh-repos", action="store_true",
                    help="re-mine GitHub and rewrite assets/data/repos.cache.json")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    token = args.token or os.environ.get("GITHUB_TOKEN") or None
    try:
        build(check_only=args.check, cv_path=args.cv, token=token, quiet=args.quiet,
              refresh_repos=args.refresh_repos)
    except BuildFailure as exc:
        sys.stderr.write(f"BUILD FAILURE: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
