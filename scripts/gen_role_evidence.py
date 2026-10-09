#!/usr/bin/env python3
"""Inject the professional-role evidence section into evidence.html (AC-60).

Keeps the existing academic-theme grouping and adds a professional dimension:
every one of the seven CV roles appears, with a real role -> artefact link where
an on-disk artefact exists, and an explicit artefact-less statement otherwise.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# (role title, employer, dates, artefact path or None, artefact rationale)
ROLE_EVIDENCE = [
    ("Manager: Data Analytics &amp; Global Reporting", "Cartrack", "Jun 2024 &ndash; Present",
     "Literature Review Machine Learning for Churn Prediction at Cartrack.pdf",
     "The MSc literature review studies churn prediction for Cartrack &mdash; the "
     "employer and business problem this role owns. This is the explicit role &rarr; artefact join."),
    ("SIM Usage Analyst", "Cartrack", "Jan 2024 &ndash; May 2024", None,
     "Confidential operational fleet data; no publishable artefact."),
    ("Data Scientist", "Greendoor Group", "Mar 2023 &ndash; Jan 2024", None,
     "Client and subsidiary work is confidential; no publishable artefact."),
    ("Data Analyst", "Smith Yong and Associates", "Jan 2019 &ndash; Feb 2023", None,
     "Audit and inventory engagements are confidential; no publishable artefact."),
    ("Vice Chairman &amp; Athlete Representative", "Gauteng Weightlifting Association",
     "Feb 2025 &ndash; Present", None,
     "Voluntary association role; no artefact on disk."),
    ("Executive Committee Member", "Gauteng Weightlifting Association",
     "Jul 2023 &ndash; Feb 2025", None,
     "Voluntary association role; no artefact on disk."),
    ("South African Presidents Team Representative",
     "RLSS Commonwealth Festival of Lifesaving", "2019", None,
     "Sporting achievement; no publishable artefact."),
]

MARKER_START = "<!-- ROLE-EVIDENCE-START -->"
MARKER_END = "<!-- ROLE-EVIDENCE-END -->"


def build_section() -> str:
    items = []
    for title, employer, dates, artefact, why in ROLE_EVIDENCE:
        if artefact:
            link = (f'<p class="role-artefact"><strong>Artefact:</strong> '
                    f'<a href="assets/{quote(artefact)}" target="_blank" rel="noopener">'
                    f'{artefact}</a> &mdash; {why}</p>')
        else:
            link = (f'<p class="role-artefact role-artefact--none">{why} The responsibilities for this '
                    f'role are stated on the <a href="experience.html">Experience</a> page with no '
                    f'artefact link implied.</p>')
        items.append(
            f'''\t\t\t\t\t\t\t<li class="role-evidence">
\t\t\t\t\t\t\t\t<h3>{title}</h3>
\t\t\t\t\t\t\t\t<p class="cv-meta">{employer} &middot; {dates}</p>
\t\t\t\t\t\t\t\t{link}
\t\t\t\t\t\t\t</li>''')
    return (MARKER_START + "\n"
            '\t\t\t\t\t<section class="artefact-group" aria-labelledby="professional-experience-evidence">\n'
            '\t\t\t\t\t\t<h2 id="professional-experience-evidence">Professional experience &mdash; roles and evidence</h2>\n'
            '\t\t\t\t\t\t<p>Alongside the academic artefacts, each of the roles on the '
            '<a href="experience.html">Experience</a> page appears here. Where a real on-disk artefact '
            'relates to a role it is linked explicitly (role &rarr; artefact); where the work is '
            'confidential to the employer the role is stated with no artefact link, and that is recorded '
            'in the delivery summary as artefact-less by necessity.</p>\n'
            '\t\t\t\t\t\t<ul class="role-evidence-list">\n'
            + "\n".join(items) + "\n"
            '\t\t\t\t\t\t</ul>\n'
            '\t\t\t\t\t</section>\n'
            + MARKER_END)


def main() -> None:
    with open("evidence.html", encoding="utf-8") as fh:
        s = fh.read()

    # Remove any previous injected block (idempotent re-run).
    if MARKER_START in s:
        start = s.index(MARKER_START)
        end = s.index(MARKER_END) + len(MARKER_END)
        s = s[:start] + s[end:]

    anchor = '<section class="artefact-group" aria-labelledby="research-project-design-literature-and-method">'
    if anchor not in s:
        raise SystemExit("anchor section not found in evidence.html")
    section = build_section() + "\n\n\t\t\t\t\t"
    s = s.replace(anchor, section + anchor, 1)

    with open("evidence.html", "w", encoding="utf-8") as fh:
        fh.write(s)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roles_logged": len(ROLE_EVIDENCE),
        "artefact_joined": [r[0] for r in ROLE_EVIDENCE if r[3]],
        "artefact_less": [r[0] for r in ROLE_EVIDENCE if not r[3]],
    }
    with open("output/evidence/role_evidence_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("evidence.html role section injected; roles:", len(ROLE_EVIDENCE),
          "joined:", report["artefact_joined"])


if __name__ == "__main__":
    main()
