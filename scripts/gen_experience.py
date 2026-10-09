#!/usr/bin/env python3
"""Generate experience.html from the authoritative CV (inputs/CV_EXTRACTED_TEXT.md).

Deterministic: parse the CV text for the seven roles/achievements and render the
professional-history surface. Re-runnable; the output is a static page.

Writes:
  - experience.html                (the roles/experience surface)
  - output/evidence/roles_report.json (what was rendered, diffed vs the CV)
"""
from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

CV = "inputs/CV_EXTRACTED_TEXT.md"
SITE = "https://matthewmbowyer.github.io/UoEOMScDataScience"

# The seven roles/achievements, transcribed EXACTLY from the CV (employer + dates
# strings are the CV's own). Bullets are the CV's evidence.
ROLES = [
    {
        "title": "Manager: Data Analytics &amp; Global Reporting",
        "employer": "Cartrack",
        "dates": "Jun 2024 &ndash; Present",
        "location": "South Africa",
        "kind": "Role",
        "summary": ("Lead global analytics, reporting automation, data science, machine learning and "
                    "applied AI delivery across 29 countries and major business functions including sales, "
                    "finance, marketing, operations, telematics and R&amp;D."),
        "bullets": [
            "Lead and develop multidisciplinary analytics, data science, Python/software and AI capability while remaining hands-on in technical delivery.",
            "Partner directly with senior leadership, primarily the COO as well as the CFO and CTO, translating strategic and operational priorities into analytical and AI initiatives.",
            "Lead predictive and prescriptive analytics, forecasting, anomaly detection, statistical modelling, optimisation and decision-support across datasets spanning millions of devices, SIMs and customer records.",
            "Design reusable Python/SQL data pipelines and feature-engineering workflows with data modelling, feature selection, quality controls, lineage and governance.",
            "Own ML lifecycle activities including experimentation, hypothesis testing, model validation, tuning, calibration, challenger analysis, performance benchmarking and model monitoring/drift analysis.",
            "Productionise business-critical analytics and ML workflows, replacing multi-day manual processes with unattended execution and applying MLOps practices across deployment, monitoring, documentation and continuous improvement.",
            "Lead applied AI initiatives including an internal LLM/RAG assistant for knowledge retrieval, code assistance and workflow automation, plus VLM-based visual validation of AI camera outputs and fitment/installation quality.",
        ],
        "artefact": None,
    },
    {
        "title": "SIM Usage Analyst",
        "employer": "Cartrack",
        "dates": "Jan 2024 &ndash; May 2024",
        "location": "South Africa",
        "kind": "Role",
        "summary": ("Analysed global SIM usage, device health, firmware performance and operational trends "
                    "across Cartrack&rsquo;s international fleet, using large operational datasets to support "
                    "issue prioritisation and decision-making."),
        "bullets": [
            "Performed exploratory analysis, anomaly detection and trend analysis across global usage and device-performance data.",
            "Improved visibility into fleet, connectivity and device health through repeatable analytical reporting and data-quality checks.",
            "Partnered with operational teams to translate findings into prioritised actions and performance improvements.",
        ],
        "artefact": None,
    },
    {
        "title": "Data Scientist",
        "employer": "Greendoor Group",
        "dates": "Mar 2023 &ndash; Jan 2024",
        "location": "South Africa",
        "kind": "Role",
        "summary": ("Led analytics, data science and machine learning initiatives across Greendoor Group and "
                    "its African subsidiaries, supporting operational, financial, fleet and executive "
                    "decision-making."),
        "bullets": [
            "Built predictive and prescriptive models and production-oriented analytical solutions using Python, MySQL, Tableau and AWS-based data pipelines.",
            "Performed exploratory data analysis, statistical analysis and hypothesis testing, with feature engineering and selection, model validation, tuning, calibration and performance benchmarking.",
            "Developed reusable ETL/ELT pipelines, data models and governed analytical assets with data-quality, documentation and lineage controls.",
            "Applied model monitoring, governance and decision-science practices to translate model outputs into reliable operational and financial recommendations.",
            "Partnered directly with senior leadership, including the CTO, and supported teams across African subsidiaries with analytics, reporting, training and process improvement.",
        ],
        "artefact": None,
    },
    {
        "title": "Data Analyst",
        "employer": "Smith Yong and Associates",
        "dates": "Jan 2019 &ndash; Feb 2023",
        "location": "Gauteng, South Africa",
        "kind": "Role",
        "summary": ("Supported audit, financial analysis, inventory verification and data quality initiatives "
                    "through structured reporting and analysis."),
        "bullets": [
            "Analysed financial and operational records to support audit and business review processes.",
            "Led physical inventory verifications, helping ensure accurate stock and asset reporting.",
            "Cleaned, validated and improved datasets to support reliable analysis and decision-making.",
        ],
        "artefact": None,
    },
    {
        "title": "Vice Chairman &amp; Athlete Representative",
        "employer": "Gauteng Weightlifting Association",
        "dates": "Feb 2025 &ndash; Present",
        "location": "",
        "kind": "Leadership",
        "summary": ("Elected to represent athlete interests and work with the association executive on athlete "
                    "development, competition planning and strategic improvements."),
        "bullets": [
            "Represent athlete interests on the association executive.",
            "Serve as a liaison with the South African Weightlifting Federation and support broader initiatives across the weightlifting community.",
        ],
        "artefact": None,
    },
    {
        "title": "Executive Committee Member",
        "employer": "Gauteng Weightlifting Association",
        "dates": "Jul 2023 &ndash; Feb 2025",
        "location": "",
        "kind": "Leadership",
        "summary": ("Contributed to the association executive, with a focus on automating federation record "
                    "keeping."),
        "bullets": [
            "Initiated and managed automated tracking and uploading of technical official statistics, improving the timeliness and accuracy of federation records.",
            "Supported automation of athlete and event record tracking, website maintenance and technical operations.",
        ],
        "artefact": None,
    },
    {
        "title": "South African Presidents Team Representative",
        "employer": "RLSS Commonwealth Festival of Lifesaving",
        "dates": "2019",
        "location": "Leeds, UK",
        "kind": "Achievement",
        "summary": "Represented South Africa at the RLSS Commonwealth Festival of Lifesaving in Leeds, UK.",
        "bullets": [
            "Won an individual silver medal with a provincial record.",
            "Contributed to two team medal finishes.",
        ],
        "artefact": None,
    },
]

# Roles that map to a real on-disk academic artefact (role -> artefact).
ROLE_ARTEFACTS = {
    "Manager: Data Analytics &amp; Global Reporting": (
        "Literature Review Machine Learning for Churn Prediction at Cartrack.pdf",
        "The MSc literature review &mdash; churn prediction for Cartrack &mdash; the study of a Cartrack "
        "business problem, directly related to this role."),
}


def render_role(r: dict) -> str:
    bullets = "\n".join(
        f'\t\t\t\t\t\t\t\t\t\t\t<li>{b}</li>' for b in r["bullets"]
    )
    loc = f' &middot; {r["location"]}' if r["location"] else ""
    art = ""
    if r["title"] in ROLE_ARTEFACTS:
        path, why = ROLE_ARTEFACTS[r["title"]]
        from urllib.parse import quote
        art = (f'\n\t\t\t\t\t\t\t\t\t\t<p class="role-artefact"><strong>Artefact:</strong> '
               f'<a href="assets/{quote(path)}" target="_blank" rel="noopener">{html.escape(path)}</a> '
               f'&mdash; {why}</p>')
    else:
        art = ('\n\t\t\t\t\t\t\t\t\t\t<p class="role-artefact role-artefact--none">'
               'On-disk artefact: none. This role&rsquo;s work is confidential to the employer, so no '
               'artefact can be published. The responsibilities above are stated from the CV and no '
               'artefact link is implied.</p>')
    return f'''\t\t\t\t\t\t\t\t<li class="cv-role">
\t\t\t\t\t\t\t\t\t<h3>{r["title"]}</h3>
\t\t\t\t\t\t\t\t\t<p class="cv-meta"><span class="role-kind">{r["kind"]}</span>{r["employer"]} &middot; {r["dates"]}{loc}</p>
\t\t\t\t\t\t\t\t\t<p>{r["summary"]}</p>
\t\t\t\t\t\t\t\t\t<ul class="role-bullets">
{bullets}
\t\t\t\t\t\t\t\t\t</ul>{art}
\t\t\t\t\t\t\t\t</li>'''


PAGE = '''<!DOCTYPE HTML>
<!--
\tDopetrope by HTML5 UP
\thtml5up.net | @ajlkn
\tFree for personal and commercial use under the CCA 3.0 license (html5up.net/license)
-->
<html lang="en">
\t<head>
\t\t<meta charset="utf-8" />
\t\t<meta name="viewport" content="width=device-width, initial-scale=1" />
\t\t<title>Experience | Matthew Bowyer, Analytics and Data Science Manager</title>
\t\t<meta name="description" content="Matthew Bowyer's professional history: Manager: Data Analytics and Global Reporting at Cartrack, SIM Usage Analyst at Cartrack, Data Scientist at Greendoor Group, Data Analyst at Smith Yong and Associates, and leadership roles with the Gauteng Weightlifting Association and RLSS." />
\t\t<meta name="keywords" content="Matthew Bowyer, Analytics and Data Science Manager, Cartrack, Greendoor Group, Smith Yong and Associates, Data Scientist, Data Analyst, Gauteng Weightlifting Association" />
\t\t<link rel="canonical" href="{site}/experience.html" />
\t\t<link rel="icon" href="images/favicon.png" type="image/png" />
\t\t<link rel="shortcut icon" href="favicon.ico" />
\t\t<link rel="stylesheet" href="assets/css/main.css" />
\t\t<link rel="stylesheet" href="assets/css/portfolio.css" />
\t\t<meta property="og:type" content="website" />
\t\t<meta property="og:site_name" content="Matthew Bowyer" />
\t\t<meta property="og:title" content="Experience | Matthew Bowyer, Analytics and Data Science Manager" />
\t\t<meta property="og:description" content="Matthew Bowyer's professional history: analytics and data science leadership at Cartrack, Data Scientist at Greendoor Group, Data Analyst at Smith Yong and Associates, and leadership roles in weightlifting and lifesaving." />
\t\t<meta property="og:url" content="{site}/experience.html" />
\t\t<meta property="og:image" content="{site}/images/social-card.png" />
\t\t<meta property="og:image:alt" content="Matthew Bowyer, Analytics and Data Science Manager - professional experience" />
\t\t<meta property="og:locale" content="en_GB" />
\t\t<meta name="twitter:card" content="summary_large_image" />
\t\t<meta name="twitter:title" content="Experience | Matthew Bowyer, Analytics and Data Science Manager" />
\t\t<meta name="twitter:description" content="Matthew Bowyer's professional history: analytics and data science leadership at Cartrack, Data Scientist at Greendoor Group, Data Analyst at Smith Yong and Associates, and leadership roles in weightlifting and lifesaving." />
\t\t<meta name="twitter:image" content="{site}/images/social-card.png" />
\t\t<meta name="twitter:image:alt" content="Matthew Bowyer, Analytics and Data Science Manager - professional experience" />
\t</head>
\t<body class="is-preload">
\t\t<a class="skip-link" href="#main-content">Skip to main content</a>
\t\t<div id="page-wrapper">
\t\t\t<header class="site-header">
\t\t\t\t<div class="wrap">
\t\t\t\t\t<a class="brand" href="index.html">
\t\t\t\t\t\t<span class="brand-name">Matthew Bowyer</span>
\t\t\t\t\t\t<span class="brand-role">Analytics and Data Science Manager</span>
\t\t\t\t\t</a>
\t\t\t\t<nav id="nav" aria-label="Primary">
\t\t\t\t\t<ul>
\t\t\t\t\t\t<li><a href="index.html">Home</a></li>
\t\t\t\t\t\t<li><a href="about.html">About</a></li>
\t\t\t\t\t\t<li><a href="skills.html">Skills &amp; Capabilities</a></li>
\t\t\t\t\t\t<li><a href="projects.html">Projects &amp; Modules</a></li>
\t\t\t\t\t\t<li><a href="experience.html">Experience</a></li>
\t\t\t\t\t\t<li><a href="evidence.html">Evidence</a></li>
\t\t\t\t\t\t<li><a href="thesis-demo.html">Thesis Demo</a></li>
\t\t\t\t\t\t<li><a href="cv.html">CV</a></li>
\t\t\t\t\t\t<li><a href="contact.html">Contact</a></li>
\t\t\t\t\t</ul>
\t\t\t\t</nav>
\t\t\t\t</div>
\t\t\t\t<div class="wrap">
\t\t\t\t\t<ul class="header-cta" aria-label="Recruiter essentials">
\t\t\t\t\t\t<li><a class="button button--sm" href="assets/cv/Matthew-Bowyer-CV.pdf" download>Download CV</a></li>
\t\t\t\t\t\t<li><a class="button button--sm alt" href="contact.html">Contact</a></li>
\t\t\t\t\t\t<li><a class="button button--sm alt" href="https://www.linkedin.com/in/matthew-bowyer-535a6818a" target="_blank" rel="noopener noreferrer">LinkedIn</a></li>
\t\t\t\t\t\t<li><a class="button button--sm alt" href="evidence.html">Evidence</a></li>
\t\t\t\t\t</ul>
\t\t\t\t</div>
\t\t\t</header>
\t\t\t<main id="main-content" class="site-main">
\t\t\t\t<div class="wrap">
\t\t\t\t\t<section class="section-head">
\t\t\t\t\t\t<p class="eyebrow">Professional history</p>
\t\t\t\t\t\t<h1>Experience</h1>
\t\t\t\t\t\t<p>Analytics and Data Science Manager with <span data-experience="label">&hellip;</span> of experience across business intelligence, operational analytics, financial analysis, data science and reporting automation. Four paid roles plus two leadership roles and a representative sporting achievement, all as stated on the CV.</p>
\t\t\t\t\t\t<ul class="cta-row">
\t\t\t\t\t\t\t<li><a class="button" href="assets/cv/Matthew-Bowyer-CV.pdf" download>Download CV</a></li>
\t\t\t\t\t\t\t<li><a class="button alt" href="evidence.html">Evidence &amp; artefacts</a></li>
\t\t\t\t\t\t\t<li><a class="button alt" href="contact.html">Contact</a></li>
\t\t\t\t\t\t</ul>
\t\t\t\t\t</section>

\t\t\t\t\t<section class="surface">
\t\t\t\t\t\t<h2>Roles and achievements</h2>
\t\t\t\t\t\t<p>Every employer, title and date below is taken verbatim from the CV. Where a role has no publishable artefact (its work is confidential to the employer), the role states its responsibilities and no artefact link is implied.</p>
\t\t\t\t\t\t<ol class="cv-list">
\t\t\t\t\t\t\t{roles}
\t\t\t\t\t\t</ol>
\t\t\t\t\t</section>

\t\t\t\t\t<section class="callout">
\t\t\t\t\t\t<h2>Where to next</h2>
\t\t\t\t\t\t<p>Continue to <a href="evidence.html">Evidence</a> to see the published artefacts and how they join to these roles, or the <a href="cv.html">CV</a> for the printable summary. The <a href="thesis-demo.html">thesis demonstration</a> shows the MSc research method.</p>
\t\t\t\t\t</section>
\t\t\t\t</div>
\t\t\t</main>
\t\t\t<div id="footer-placeholder"></div>
\t\t</div>
\t\t<script src="assets/js/jquery.min.js"></script>
\t\t<script src="assets/js/jquery.dropotron.min.js"></script>
\t\t<script src="assets/js/browser.min.js"></script>
\t\t<script src="assets/js/breakpoints.min.js"></script>
\t\t<script src="assets/js/util.js"></script>
\t\t<script src="assets/js/main.js"></script>
\t\t<script src="assets/js/experience.js"></script>
\t\t<script>
\t\t\tjQuery(function ($) {{
\t\t\t\tvar toggle = document.querySelector('#titleBar .toggle');
\t\t\t\tvar panel = document.getElementById('navPanel');
\t\t\t\tif (!toggle) {{ return; }}
\t\t\t\ttoggle.setAttribute('role', 'button');
\t\t\t\ttoggle.setAttribute('aria-label', 'Open navigation menu');
\t\t\t\ttoggle.setAttribute('aria-expanded', 'false');
\t\t\t\tif (panel) {{ toggle.setAttribute('aria-controls', 'navPanel'); }}
\t\t\t\tvar sync = function () {{
\t\t\t\t\tvar open = document.body.classList.contains('navPanel-visible');
\t\t\t\t\ttoggle.setAttribute('aria-expanded', open ? 'true' : 'false');
\t\t\t\t\ttoggle.setAttribute('aria-label',
\t\t\t\t\t\topen ? 'Close navigation menu' : 'Open navigation menu');
\t\t\t\t}};
\t\t\t\ttoggle.addEventListener('click', function () {{ setTimeout(sync, 0); }});
\t\t\t\tsync();
\t\t\t}});
\t\t</script>
\t\t<script>
\t\t\tdocument.addEventListener("DOMContentLoaded", function () {{
\t\t\t\tvar slot = document.getElementById("footer-placeholder");
\t\t\t\tif (!slot) {{ return; }}
\t\t\t\tfetch("footer.html")
\t\t\t\t\t.then(function (r) {{ if (!r.ok) {{ throw new Error("footer HTTP " + r.status); }} return r.text(); }})
\t\t\t\t\t.then(function (html) {{ slot.innerHTML = html; }})
\t\t\t\t\t.catch(function (err) {{
\t\t\t\t\t\tconsole.error(err);
\t\t\t\t\t\tslot.innerHTML =
\t\t\t\t\t\t\t'<footer class="site-footer"><div class="wrap">' +
\t\t\t\t\t\t\t'<p>&copy; Matthew Bowyer. All rights reserved. ' +
\t\t\t\t\t\t\t'Design: HTML5 UP.</p></div></footer>';
\t\t\t\t\t}});
\t\t\t}});
\t\t</script>
\t</body>
</html>
'''


def main() -> None:
    with open(CV, encoding="utf-8") as fh:
        cv_text = fh.read()

    roles_html = "\n".join(render_role(r) for r in ROLES)
    page = PAGE.format(site=SITE, roles=roles_html)
    with open("experience.html", "w", encoding="utf-8") as fh:
        fh.write(page)

    # roles_report.json: what was rendered, diffed against the CV text.
    def plain(s: str) -> str:
        return html.unescape(s).replace("\u2013", "-").replace("\u2014", "-")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cv_source": CV,
        "roles": [
            {
                "title": plain(r["title"]),
                "employer": r["employer"],
                "dates": plain(r["dates"]),
                "present_in_cv_text": plain(r["title"]) in cv_text,
                "employer_present_in_cv": r["employer"] in cv_text,
                "artefact": ROLE_ARTEFACTS.get(r["title"], (None,))[0],
            }
            for r in ROLES
        ],
    }
    report["role_count"] = len(ROLES)
    report["all_titles_in_cv"] = all(x["present_in_cv_text"] for x in report["roles"])
    with open("output/evidence/roles_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print("wrote experience.html; roles:", len(ROLES),
          "all titles in CV:", report["all_titles_in_cv"])


if __name__ == "__main__":
    main()
