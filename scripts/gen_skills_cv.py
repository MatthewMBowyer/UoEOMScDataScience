#!/usr/bin/env python3
"""Add the CV's capability groups to skills.html (AC-62).

Uses ONLY the CV's own group names and wording (Leadership & Strategy;
Data Science & AI; Engineering & Platforms), each tied to where it is evidenced.
Idempotent: re-running replaces the injected block.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

MARK_START = "<!-- CV-CAP-GROUPS-START -->"
MARK_END = "<!-- CV-CAP-GROUPS-END -->"

GROUPS = [
    ("Leadership &amp; Strategy",
     "Analytics strategy, data strategy, AI/ML capability building, executive decision support, "
     "stakeholder management, cross-functional delivery, mentoring.",
     "Evidenced by the Manager: Data Analytics &amp; Global Reporting role at Cartrack "
     "(<a href=\"experience.html\">Experience</a>)."),
    ("Data Science &amp; AI",
     "Python, SQL, machine learning, statistical modelling, predictive &amp; prescriptive analytics, "
     "decision science, optimisation, feature engineering &amp; selection, experimentation, hypothesis "
     "testing, model validation, tuning, calibration, performance benchmarking, GenAI, LLMs, RAG, VLMs.",
     "Evidenced across the Cartrack, Greendoor Group and Smith Yong roles, the MSc modules, and the "
     "<a href=\"thesis-demo.html\">thesis demonstration</a>."),
    ("Engineering &amp; Platforms",
     "Databricks, MLflow, Spark, PySpark, Delta Lake, Feature Store, MLOps, ETL/ELT, data pipelines, "
     "data modelling, model monitoring &amp; drift, data/model governance, data quality, lineage, AWS, "
     "MySQL, Tableau.",
     "Evidenced by the Engineering &amp; Platforms group on the CV and the data-engineering modules in "
     "this portfolio."),
]


def build() -> str:
    items = []
    for name, wlist, evid in GROUPS:
        items.append(
            f'''\t\t\t\t\t\t<li class="cap-group">
\t\t\t\t\t\t\t<h2>{name}</h2>
\t\t\t\t\t\t\t<p class="cap-summary">{wlist}</p>
\t\t\t\t\t\t\t<p class="cap-evidence">{evid}</p>
\t\t\t\t\t\t</li>''')
    return (MARK_START + "\n"
            '\t\t\t\t\t<section class="section" aria-labelledby="cv-capability-groups">\n'
            '\t\t\t\t\t\t<div class="section-head">\n'
            '\t\t\t\t\t\t\t<h2 id="cv-capability-groups">Capabilities from the current CV</h2>\n'
            '\t\t\t\t\t\t\t<p>The CV groups my capability into three areas. The wording below is the '
            'CV&rsquo;s own, each tied to where it is evidenced on this site or in the roles.</p>\n'
            '\t\t\t\t\t\t</div>\n'
            '\t\t\t\t\t\t<ul class="cap-grid">\n'
            + "\n".join(items) + "\n"
            '\t\t\t\t\t\t</ul>\n'
            '\t\t\t\t\t</section>\n'
            + MARK_END + "\n\n\t\t\t\t\t")


def main() -> None:
    with open("skills.html", encoding="utf-8") as fh:
        s = fh.read()

    if MARK_START in s:
        a = s.index(MARK_START)
        b = s.index(MARK_END) + len(MARK_END)
        # also drop trailing separator we added
        s = s[:a] + s[b:].lstrip("\n")
        # keep spacing tidy
        s = s.replace("\n\n\n\t\t\t\t\t<section class=\"section\">",
                      "\n\n\t\t\t\t\t<section class=\"section\">")

    anchor = '<section class="section">\n                                                <div class="section-head">\n                                                        <h2>Where this is evidenced</h2>'
    if anchor not in s:
        anchor = '<section class="section">'
        idx = s.index('Where this is evidenced')
        # find the enclosing section start before that text
        sec = s.rindex('<section class="section">', 0, idx)
        s = s[:sec] + build() + s[sec:]
    else:
        s = s.replace(anchor, build() + anchor, 1)

    with open("skills.html", "w", encoding="utf-8") as fh:
        fh.write(s)

    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "groups": ["Leadership & Strategy", "Data Science & AI", "Engineering & Platforms"]}
    with open("output/evidence/skills_cv_groups_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("skills.html CV capability groups injected")


if __name__ == "__main__":
    main()
