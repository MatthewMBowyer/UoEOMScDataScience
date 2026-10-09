#!/usr/bin/env python3
"""Authoring tool that emits the rebuilt e-portfolio pages.

The delivered site is plain static HTML/CSS/JS; this script exists so the shared
navigation, the page chrome and the module-page improvements are emitted
byte-identically everywhere instead of being copy-pasted per page.

Run from the project root:

    python3 scripts/build_site.py            # build every page
    python3 scripts/build_site.py --check    # verify the tree is already built
"""
from __future__ import annotations

import argparse
import functools
import os
import re
import sys
import urllib.parse

from lxml import html as LH

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)

import site_content as C  # noqa: E402
import pages_extra as PX  # noqa: E402
import pages_evidence as PE  # noqa: E402

flagship_cards = PX.flagship_cards
impact_list = PX.impact_list

STYLESHEETS = ["assets/css/main.css", "assets/css/portfolio.css"]

# The owner's unlisted personal pages. They sit at the site root for short
# addresses, but they are not delivered pages: no shared nav, no ambient-bot
# facts, and they must stay out of the sitemap (AC-P5). Keep in step with
# tests/verify_site.py::PERSONAL_PAGES.
PERSONAL_PAGES = ("sports.html", "good_hubby.html")

FOOTER_FETCH = """                <script>
                        document.addEventListener("DOMContentLoaded", function () {
                                var slot = document.getElementById("footer-placeholder");
                                if (!slot) { return; }
                                fetch("footer.html")
                                        .then(function (r) {
                                                if (!r.ok) { throw new Error("footer HTTP " + r.status); }
                                                return r.text();
                                        })
                                        .then(function (html) { slot.innerHTML = html; })
                                        .catch(function (err) {
                                                console.error(err);
                                                slot.innerHTML =
                                                        '<footer class="site-footer"><div class="wrap">' +
                                                        '<p>&copy; Matthew Bowyer. All rights reserved. ' +
                                                        'Design: HTML5 UP.</p></div></footer>';
                                        });
                        });
                </script>"""

SCRIPTS = """                <script src="assets/js/jquery.min.js"></script>
                <script src="assets/js/jquery.dropotron.min.js"></script>
                <script src="assets/js/browser.min.js"></script>
                <script src="assets/js/breakpoints.min.js"></script>
                <script src="assets/js/util.js"></script>
                <script src="assets/js/experience.js"></script>
                <script src="assets/js/main.js"></script>"""

# The template builds #titleBar/#navPanel from jQuery at runtime, so the
# hamburger the reader taps is an empty <a> with no accessible name. Label it
# and expose the expanded state. Runs after main.js (jQuery ready), and never
# creates the elements - it only annotates them, so it is inert if main.js has
# not run.
NAV_A11Y = """                <script>
                        jQuery(function ($) {
                                var toggle = document.querySelector('#titleBar .toggle');
                                var panel = document.getElementById('navPanel');
                                if (!toggle) { return; }
                                toggle.setAttribute('role', 'button');
                                toggle.setAttribute('aria-label', 'Open navigation menu');
                                toggle.setAttribute('aria-expanded', 'false');
                                if (panel) { toggle.setAttribute('aria-controls', 'navPanel'); }
                                var sync = function () {
                                        var open = document.body.classList.contains('navPanel-visible');
                                        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
                                        toggle.setAttribute('aria-label',
                                                open ? 'Close navigation menu' : 'Open navigation menu');
                                };
                                toggle.addEventListener('click', function () {
                                        setTimeout(sync, 0);
                                });
                                sync();
                        });
                </script>"""

CONTACT_FORM_SCRIPT = """                <script>
                        document.addEventListener("DOMContentLoaded", function () {
                                var form = document.getElementById("enquiry-form");
                                if (!form) { return; }
                                form.addEventListener("submit", function (ev) {
                                        ev.preventDefault();
                                        var val = function (id) {
                                                var el = document.getElementById(id);
                                                return el && el.value ? el.value.trim() : "";
                                        };
                                        var body = "Name: " + val("cf-name") +
                                                "\\nEmail: " + val("cf-email") +
                                                "\\nOrganisation: " + (val("cf-organisation") || "not given") +
                                                "\\n\\nMessage:\\n" + val("cf-message");
                                        var status = document.getElementById("cf-status");
                                        if (status) {
                                                status.textContent =
                                                        "Opening your email client with this message. Nothing has been sent yet.";
                                        }
                                        window.location.href =
                                                "mailto:matthewmbowyer@gmail.com" +
                                                "?subject=" + encodeURIComponent("Enquiry from your portfolio") +
                                                "&body=" + encodeURIComponent(body);
                                });
                        });
                </script>"""


# ---------------------------------------------------------------------------
# Shared chrome
# ---------------------------------------------------------------------------

def nav_html() -> str:
    items = "\n".join(
        f'                                                <li><a href="{href}">{label}</a></li>'
        for label, href in C.NAV_ITEMS
    )
    return f'''                                <nav id="nav" aria-label="Primary">
                                        <ul>
{items}
                                        </ul>
                                </nav>'''


def recruiter_cta_row() -> str:
    """The four recruiter essentials, in the header, on EVERY page (AC-53).

    Download CV, Contact, LinkedIn and Evidence are each one click away from any
    delivered page because this block is part of the shared header.
    """
    return f'''                        <div class="wrap">
                                <ul class="header-cta" aria-label="Recruiter essentials">
                                        <li><a class="button button--sm" href="{C.CV_PDF}" download>Download CV</a></li>
                                        <li><a class="button button--sm alt" href="contact.html">Contact</a></li>
                                        <li><a class="button button--sm alt" href="{C.LINKEDIN_URL}" target="_blank" rel="noopener noreferrer">LinkedIn</a></li>
                                        <li><a class="button button--sm alt" href="evidence.html">Evidence</a></li>
                                </ul>
                        </div>'''


def site_header() -> str:
    return f'''                        <header class="site-header">
                                <div class="wrap">
                                        <a class="brand" href="index.html">
                                                <span class="brand-name">{C.SITE_NAME}</span>
                                                <span class="brand-role">{C.SITE_ROLE}</span>
                                        </a>
{nav_html()}
                                </div>
{recruiter_cta_row()}
                        </header>'''


def og_url(page_name: str) -> str:
    return f"{C.SITE_BASE_URL}/" + urllib.parse.quote(page_name)


def social_meta(page_name: str, title: str, description: str) -> str:
    """Open Graph + Twitter card tags, emitted on EVERY page (AC-47/AC-48).

    og:image and twitter:image point at the one same-origin share image, and
    og:url is the absolute URL of the page itself, so nothing here can 404 or
    resolve relatively.
    """
    image = f"{C.SITE_BASE_URL}/{C.SOCIAL_IMAGE}"
    url = og_url(page_name)
    def esc(v: str) -> str:
        return (v.replace("&", "&amp;").replace('"', "&quot;")
                .replace("<", "&lt;").replace(">", "&gt;"))
    t, d = esc(title), esc(description)
    return f'''                <meta property="og:type" content="website" />
                <meta property="og:site_name" content="{C.SITE_NAME_SHORT}" />
                <meta property="og:title" content="{t}" />
                <meta property="og:description" content="{d}" />
                <meta property="og:url" content="{esc(url)}" />
                <meta property="og:image" content="{esc(image)}" />
                <meta property="og:image:alt" content="{esc(C.SOCIAL_IMAGE_ALT)}" />
                <meta property="og:locale" content="en_GB" />
                <meta name="twitter:card" content="summary_large_image" />
                <meta name="twitter:title" content="{t}" />
                <meta name="twitter:description" content="{d}" />
                <meta name="twitter:image" content="{esc(image)}" />
                <meta name="twitter:image:alt" content="{esc(C.SOCIAL_IMAGE_ALT)}" />'''


def head_html(title: str, description: str, page_name: str,
              keywords: str | None = None) -> str:
    links = "\n".join(
        f'                <link rel="stylesheet" href="{s}" />' for s in STYLESHEETS
    )
    kw = f'\n                <meta name="keywords" content="{keywords}" />' if keywords else ""
    return f'''        <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>{title}</title>
                <meta name="description" content="{description}" />{kw}
                <link rel="canonical" href="{og_url(page_name)}" />
                <link rel="icon" href="images/favicon.png" type="image/png" />
                <link rel="shortcut icon" href="favicon.ico" />
{links}
{social_meta(page_name, title, description)}
        </head>'''


def page(title: str, description: str, body: str, keywords: str | None = None,
         extra_scripts: str = "", page_name: str = "index.html") -> str:
    scripts = SCRIPTS + "\n" + NAV_A11Y + (
        "\n" + extra_scripts if extra_scripts else "")
    return f'''<!DOCTYPE HTML>
<!--
        Dopetrope by HTML5 UP
        html5up.net | @ajlkn
        Free for personal and commercial use under the CCA 3.0 license (html5up.net/license)
-->
<html lang="en">
{head_html(title, description, page_name, keywords)}
        <body class="is-preload">
                <a class="skip-link" href="#main-content">Skip to main content</a>
                <div id="page-wrapper">
{site_header()}
                        <main id="main-content" class="site-main">
{body}
                        </main>
                        <div id="footer-placeholder"></div>
                </div>
{scripts}
{FOOTER_FETCH}
        </body>
</html>
'''


def wrap(content: str) -> str:
    return f'                                <div class="wrap">\n{content}\n                                </div>'


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------

def build_home() -> str:
    chips = "\n".join(
        f'                                                                        <li>{s}</li>'
        for s in C.PRIMARY_SKILLS
    )
    specialisms = "; ".join(s.lower() for s in C.SPECIALISMS[:-1])
    specialisms += f"; and {C.SPECIALISMS[-1].lower()}"

    quick = []
    for href, title, desc in [
        ("projects.html", "All projects &amp; modules", "Research, commercial and academic work, strongest first, plus every module from both degrees as a scannable card-based body of work."),
        ("Masters.html", "MSc Data Science", "The University of Essex Online MSc I completed in 2026 (Merit), module by module."),
        ("Honours.html", "BSc (Hons) Data Science", "The Open University degree that built my statistics, maths and computing foundation."),
        ("evidence.html", "Evidence &amp; artefacts", "The real reports, literature reviews, presentations and worksheets produced across the programme."),
        ("skills.html", "Skills &amp; capabilities", "Technical capability grouped honestly, with a pointer to where each skill is evidenced."),
        ("about.html", "About", "Background, career trajectory, what I studied and why, and what I am looking for."),
    ]:
        quick.append(f'''                                                        <li class="card">
                                                                <div class="card-body">
                                                                        <h3><a href="{href}">{title}</a></h3>
                                                                        <p>{desc}</p>
                                                                        <a class="card-link" href="{href}">Open &rarr;</a>
                                                                </div>
                                                        </li>''')

    body = f'''                                <section class="hero" aria-labelledby="hero-title">
                                        <div class="wrap">
                                                <div class="hero-inner">
                                                        <div class="hero-copy">
                                                                <p class="hero-eyebrow">Analytics &middot; Data Science &middot; Applied AI</p>
                                                                <h1 id="hero-title"><span class="hero-name">{C.SITE_NAME}</span><span class="hero-outcome">turns operational data into decisions leaders act on</span></h1>
                                                                <p class="hero-role">{C.SITE_ROLE}</p>
                                                                <p class="hero-lede">{C.fill_experience(C.POSITIONING)}</p>
                                                                <ul class="skill-chips">
{chips}
                                                                </ul>
                                                                <ul class="cta-row">
                                                                        <li><a class="button" href="projects.html">View Projects</a></li>
                                                                        <li><a class="button" href="{C.CV_PDF}" download>Download CV</a></li>
                                                                        <li><a class="button alt" href="contact.html">Contact</a></li>
                                                                        <li><a class="button alt" href="{C.LINKEDIN_URL}" target="_blank" rel="noopener noreferrer">LinkedIn</a></li>
                                                                </ul>
                                                        </div>
                                                        <div class="hero-side">
                                                                <figure class="hero-media">
                                                                        <img src="images/banner.jpg" width="1792" height="1024" alt="Matthew Bowyer's data science work banner: a photograph used on the original portfolio" />
                                                                </figure>
                                                                <p class="hero-eyebrow">What I do</p>
                                                                <p class="hero-lede">I specialise in {specialisms}.</p>
                                                                <p class="hero-lede">I hold an MSc in Data Science from the University of Essex Online (completed 2026, Merit). My thesis is <em>A Multimodal Driver Behaviour Evaluation System: Combining Telematics, VLMs and LLMs</em>.</p>
                                                        </div>
                                                </div>
                                        </div>
                                </section>
{wrap(f"""                                        <section class="section" aria-labelledby="home-impact">
                                                <div class="section-head">
                                                        <p class="eyebrow">Impact</p>
                                                        <h2 id="home-impact">Analytics that has to deliver</h2>
                                                        <p>Every statement below is evidenced by the supplied site or by a supplied academic artefact. Nothing is quantified that the evidence does not support.</p>
                                                </div>
                                                <ul class="impact-grid">
{impact_list()}
                                                </ul>
                                                <p><a class="button" href="cv.html">See the full CV</a> <a class="button alt" href="{C.CV_PDF}" download>Download CV (PDF)</a></p>
                                        </section>""")}
{wrap(f"""                                        <section class="section" aria-labelledby="home-work">
                                                <div class="section-head">
                                                        <p class="eyebrow">Selected work</p>
                                                        <h2 id="home-work">Strongest evidenced work, first</h2>
                                                        <p>Research, commercial and academic projects the supplied site publishes, ordered with the highest-value work first.</p>
                                                </div>
                                                <ul class="card-grid">
{flagship_cards()}
                                                </ul>
                                                <p><a class="button" href="projects.html">View Projects &amp; Modules</a></p>
                                        </section>""")}
{wrap(f"""                                        <section class="section" aria-labelledby="home-explore">
                                                <div class="section-head">
                                                        <p class="eyebrow">Portfolio</p>
                                                        <h2 id="home-explore">A body of academic work, presented properly</h2>
                                                        <p>Eighteen taught modules and two programme pages. Each module has its own page &mdash; learning outcomes, reflection, and the artefacts produced along the way.</p>
                                                </div>
                                                <ul class="card-grid">
{chr(10).join(quick)}
                                                </ul>
                                        </section>""")}'''
    return page(
        title="Matthew Bowyer | Analytics and Data Science Manager",
        description=(
            "Matthew Bowyer is an Analytics and Data Science Manager working "
            "across business intelligence, operational analytics, financial "
            "analysis, data science and reporting automation. MSc Data Science "
            "portfolio, CV, projects and evidence."
        ),
        keywords=(
            "Matthew Bowyer, Analytics and Data Science Manager, Data Science, "
            "Machine Learning, Artificial Intelligence, Business Intelligence, "
            "Automation, Telematics, Python, SQL, Tableau"
        ),
        body=body,
        page_name="index.html",
    )


# ---------------------------------------------------------------------------
# Module pages (improved in place)
# ---------------------------------------------------------------------------

CONTENT_IMAGE_ALT = {
    "Unit 3 Linear Predictor.png": "Unit 3 chart from the Machine Learning module: a linear predictor fitted to the data",
    "Unit 3 Poly Predictor.png": "Unit 3 chart from the Machine Learning module: a polynomial predictor fitted to the data",
    "Unit 4 Linear Regression.png": "Unit 4 chart from the Machine Learning module: linear regression results with scikit-learn",
    "Unit 8 Costs vs iterations.png": "Unit 8 chart from the Machine Learning module: training cost plotted against iterations",
    "Machine Learning and Artificial Intelligence.jpg": "Illustration for the Machine Learning and Artificial Intelligence module",
    "realistic_scene_professional_working.jpg": "Illustration of professional working for the Deciphering Big Data module",
    "Research Methods and Professional Practice e port.png": "Illustration for the Research Methods and Professional Practice module",
    "Visualising data.png": "Illustration for the Visualising Data module",
    "The-data-professional.jpg": "Illustration for The Data Professional module",
    "Machine_Learning.png": "Illustration for the Machine Learning module",
}

# Covers that the template referenced as large PNGs, which the rebuild replaced
# with optimised JPEGs of the same pixels.
STALE_IMAGE_REMAP = {
    "images/Machine_Learning.png": "images/Machine_Learning.jpg",
    "images/Research Methods and Professional Practice e port.png":
        "images/Research Methods and Professional Practice e port.jpg",
}


def normalise_article(article, module_title: str) -> None:
    """Presentational normalisation only. No coursework wording is changed."""
    for el in article.iter():
        if el.get("style"):
            cleaned = re.sub(r"color\s*:\s*black\s*;?", "", el.get("style"), flags=re.I)
            cleaned = cleaned.strip().strip(";").strip()
            if cleaned:
                el.set("style", cleaned)
            else:
                del el.attrib["style"]
        if el.tag == "center":
            el.tag = "div"
            el.set("class", "center-block")

    for sec in article.xpath(".//section"):
        classes = set((sec.get("class") or "").split())
        classes.add("module-section")
        sec.set("class", " ".join(sorted(classes)))

    for a in article.xpath(".//a[contains(@class,'image')]"):
        images = a.xpath(".//img")
        if not images:
            continue
        figure = LH.Element("figure")
        figure.set("class", "module-figure")
        image = images[0]
        image.set("alt", f"Module cover image for the {module_title} module")
        for attr in ("height", "width"):
            image.attrib.pop(attr, None)
        figure.append(image)
        a.getparent().replace(a, figure)

    # The template's page cover still points at the pre-optimisation PNGs; the
    # delivered tree carries the optimised JPEG of each, so repoint it.
    for image in article.xpath(".//img"):
        src = (image.get("src") or "").replace("%20", " ")
        if src in STALE_IMAGE_REMAP:
            image.set("src", STALE_IMAGE_REMAP[src])

    for el in article.iter():
        # The article's own sections are h2, so the template's h4 sub-blocks
        # would skip a heading level below them. Same text, corrected level.
        if el.tag == "h4":
            el.tag = "h3"

    for image in article.xpath(".//img"):
        # Legacy fixed pixel dimensions fight the responsive layout; the CSS
        # controls display size and object-fit instead.
        for attr in ("height", "width"):
            image.attrib.pop(attr, None)
        if image.get("alt"):
            continue
        src = (image.get("src") or "").replace("%20", " ")
        base = os.path.basename(src)
        image.set("alt", CONTENT_IMAGE_ALT.get(
            base, f"Illustration from the {module_title} module: {base}"))


def artefact_block_for(src_path: str, module_title: str) -> str:
    arts = sorted(
        ((p, i) for p, i in C.ARTEFACTS.items() if i["module"] == src_path),
        key=lambda kv: kv[1]["title"],
    )
    if not arts:
        return ""
    items = "\n".join(
        f'''                                                                        <li>
                                                                                <a href="{path}" target="_blank" rel="noopener">{info["title"]}</a>
                                                                                <span class="artefact-kind">{info["kind"]}</span>
                                                                        </li>''' for path, info in arts
    )
    return f'''
                                                        <section class="artefact-block" aria-labelledby="artefacts-heading">
                                                                <h2 id="artefacts-heading">Artefacts from this module</h2>
                                                                <p>Downloadable work produced for {module_title}. Each file opens in a new tab.</p>
                                                                <ul class="artefact-list">
{items}
                                                                </ul>
                                                        </section>'''


def canonical_source(src_path: str) -> str:
    """Module/programme pages are rebuilt from the IMMUTABLE canonical copy in
    inputs/, so the build is idempotent and never re-transforms its own output."""
    return os.path.join(ROOT, "inputs", src_path)


def build_module(src_path: str) -> str:
    meta = C.MODULES[src_path]
    raw = open(canonical_source(src_path), encoding="utf-8", errors="replace").read()
    doc = LH.fromstring(raw)
    articles = doc.xpath("//article")
    article = articles[0] if articles else doc.xpath("//body")[0]
    module_title = meta["title"]
    normalise_article(article, module_title)

    inner = LH.tostring(article, encoding="unicode", pretty_print=False)
    inner = re.sub(r"\n\s*\n", "\n", inner)

    badges = f'<li><span class="badge badge--accent">{meta["programme"]}</span></li>'
    if meta["credit"]:
        badges += f'\n                                                                        <li><span class="badge">{meta["credit"]}</span></li>'

    body = wrap(f'''                                        <article class="module-page">
                                                <div class="section-head">
                                                        <p class="eyebrow">Module</p>
                                                        <h1>{module_title}</h1>
                                                        <ul class="card-meta module-meta">
                                                                        {badges}
                                                        </ul>
                                                </div>
{inner}
{artefact_block_for(src_path, module_title)}
                                        </article>''')

    programme_label = (
        "MSc Data Science (University of Essex Online)" if meta["programme"] == "MSc"
        else "BSc (Hons) Data Science (The Open University)"
    )
    return page(
        title=f"{module_title} | Matthew Bowyer, {meta['programme']} Data Science",
        description=(
            f"{module_title} - a module from Matthew Bowyer's {programme_label} "
            f"e-portfolio: learning outcomes, reflection and the artefacts produced "
            f"for the module."
        ),
        body=body,
        page_name=src_path,
    )


COVER_BY_MODULE = {
    "Algorithms, data structure and computability.html": "images/Algorithms, data structure and computability.jpg",
    "Analysing data.html": "images/Analysing data.jpg",
    "Applied statistical modelling.html": "images/Applied statistical modelling.jpg",
    "Data Management and analysis.html": "images/Data Management and analysis.jpg",
    "Deciphering Big Data.html": "images/realistic_scene_professional_working.jpg",
    "Essential mathematics.html": "images/Essential mathematics.jpg",
    "Interactive design and user experience.html": "images/Interactive design and user experience.jpg",
    "Introduction to computers and technology 1.html": "images/Introduction to computers and technology 1.jpg",
    "Introduction to computers and technology 2.html": "images/Introduction to computers and technology 2.jpg",
    "Introduction to statistics.html": "images/Introduction to statistics.jpg",
    "Machine Learning and Artificial Intelligence.html": "images/Machine Learning and Artificial Intelligence.jpg",
    "Machine Learning.html": "images/Machine_Learning.jpg",
    "Mathematical methods.html": "images/Mathematical methods.jpg",
    "Numerical Analysis.html": "images/Numerical Analysis.jpg",
    "Practical modern statistics.html": "images/Practical modern statistics.jpg",
    "Research Methods and Professional Practice.html": "images/Research Methods and Professional Practice e port.jpg",
    "The Data Professional.html": "images/The-data-professional.jpg",
    "Visualising Data.html": "images/Visualising data.png",
}


def cover_for(path: str) -> str | None:
    return COVER_BY_MODULE.get(path)


def build_programme(src_path: str) -> str:
    meta = C.STRUCTURAL_PAGES[src_path]
    wanted = "MSc" if src_path == "Masters.html" else "BSc (Hons)"

    cards = []
    for path in C.MODULE_ORDER:
        m = C.MODULES[path]
        if m["programme"] != wanted:
            continue
        img = cover_for(path)
        media = (
            f'\n                                                                <a class="card-media" tabindex="-1" aria-hidden="true" href="{path}">'
            f'<img src="{img}" alt="" loading="lazy" /></a>' if img else ""
        )
        credit = (
            f'\n                                                                                <li><span class="badge">{m["credit"]}</span></li>'
            if m["credit"] else ""
        )
        cards.append(f'''                                                        <li class="card">{media}
                                                                <div class="card-body">
                                                                        <h3><a href="{path}">{m["title"]}</a></h3>
                                                                        <ul class="card-meta">
                                                                                <li><span class="badge badge--accent">{m["programme"]}</span></li>{credit}
                                                                        </ul>
                                                                        <p>{m["summary"]}</p>
                                                                        <a class="card-link" href="{path}">Open module &rarr;</a>
                                                                </div>
                                                        </li>''')

    if src_path == "Masters.html":
        extra = '''
                                        <section class="callout callout--note">
                                                <h2>MSc Computing Project</h2>
                                                <p>The MSc Computing Project provides a systematic method for planning, executing, writing and defending a dissertation on a selected research topic.</p>
                                                <p><strong>Completed 2026.</strong> MSc Data Science, University of Essex Online (Jan 2024 &ndash; Jun 2026), Merit. Thesis: <em>A Multimodal Driver Behaviour Evaluation System: Combining Telematics, VLMs and LLMs</em>. An interactive demonstration of the thesis concept is published on <a href="thesis-demo.html">the VLM thesis page</a> and the work is reachable from the <a href="evidence.html">Evidence</a> surface.</p>
                                        </section>'''
    else:
        extra = '''
                                        <section class="callout callout--note">
                                                <h2>About this programme</h2>
                                                <p>These twelve 30-credit modules made up my BSc (Hons) Data Science with The Open University. Each module page keeps the original learning outcomes and reflection, and links the artefacts produced for it.</p>
                                        </section>'''

    body = wrap(f'''                                        <section class="section-head">
                                                <p class="eyebrow">{meta["eyebrow"]}</p>
                                                <h1>{meta["title"]}</h1>
                                                <p>{meta["summary"]}</p>
                                        </section>
{extra}
                                        <section class="section" aria-labelledby="programme-modules">
                                                <h2 id="programme-modules" class="visually-hidden">Modules in this programme</h2>
                                                <ul class="card-grid">
{chr(10).join(cards)}
                                                </ul>
                                        </section>''')
    return page(
        title=f'{meta["title"]} | Matthew Bowyer',
        description=f'{meta["title"]} - {meta["summary"]}',
        body=body,
        page_name=src_path,
    )


# ---------------------------------------------------------------------------
# Build driver
# ---------------------------------------------------------------------------

def write_sitemap() -> str:
    """A sitemap listing EVERY delivered page with its absolute URL (AC-50).

    The owner's unlisted personal pages live at the site root but are not
    delivered pages; AC-P5 requires them to stay out of the sitemap.
    """
    pages = sorted(
        p for p in os.listdir(ROOT)
        if p.endswith(".html") and p != "footer.html" and p not in PERSONAL_PAGES
    )
    urls = "\n".join(
        f"  <url>\n    <loc>{og_url(p)}</loc>\n    <changefreq>monthly</changefreq>\n"
        f"    <priority>{'1.0' if p == 'index.html' else '0.7'}</priority>\n  </url>"
        for p in pages
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n"
    )


ROBOTS_TXT = """# robots.txt — Matthew Bowyer's professional e-portfolio.
# Indexing is permitted: this is a public, recruiter-facing portfolio and the
# whole point is to be findable. Nothing here blanket-disallows crawling.
User-agent: *
Allow: /
Disallow: /docs/
Disallow: /output/
Disallow: /scripts/
Disallow: /tests/
Disallow: /work/
Disallow: /inputs/

# The owner's personal pages (sports calendar, reminders). Unlisted rather than
# private: the files are served from this public repo, so this only keeps them
# out of search results. They also carry a noindex meta tag of their own.
# They sit at the site root (the owner wanted short addresses), so they are
# named individually rather than by folder.
Disallow: /sports.html
Disallow: /good_hubby.html
Disallow: /sports.ics
Disallow: /good_hubby.ics

Sitemap: {base}/sitemap.xml
"""


def build_all() -> list[str]:
    written = []

    outputs = {
        "index.html": build_home(),
        "about.html": PX.build_about(page, wrap),
        "skills.html": PX.build_skills(page, wrap),
        "projects.html": PX.build_projects(
            page, wrap,
            {"order": C.MODULE_ORDER, "map": C.MODULES},
            C.STRUCTURAL_PAGES, cover_for,
        ),
        "evidence.html": PE.build_evidence(page, wrap),
        "cv.html": PX.build_cv(page, wrap),
    }
    outputs["contact.html"] = PE.build_contact(page, wrap).replace(
        FOOTER_FETCH, CONTACT_FORM_SCRIPT + "\n" + FOOTER_FETCH, 1)

    for src in C.MODULE_ORDER:
        outputs[src] = build_module(src)
    for src in C.STRUCTURAL_PAGES:
        outputs[src] = build_programme(src)

    for name, content in outputs.items():
        path = os.path.join(ROOT, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(name)

    with open(os.path.join(ROOT, "footer.html"), "w", encoding="utf-8") as fh:
        fh.write(PX.footer_fragment(page))
    written.append("footer.html")

    # robots.txt and sitemap.xml are static files written by the same authoring
    # step, so they can never fall out of sync with the delivered page set.
    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as fh:
        fh.write(ROBOTS_TXT.format(base=C.SITE_BASE_URL))
    written.append("robots.txt")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write(write_sitemap())
    written.append("sitemap.xml")

    return written


def expected_pages() -> list[str]:
    return (
        list(C.MODULES) + list(C.STRUCTURAL_PAGES)
        + ["index.html", "about.html", "skills.html", "projects.html",
           "evidence.html", "cv.html", "contact.html", "footer.html"]
    )


def check() -> int:
    missing = [n for n in expected_pages() if not os.path.exists(os.path.join(ROOT, n))]
    if missing:
        print("MISSING:", missing)
        return 1
    print(f"OK: all {len(expected_pages())} pages present")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        return check()
    written = build_all()
    print(f"wrote {len(written)} files")
    for name in written:
        print("  ", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
