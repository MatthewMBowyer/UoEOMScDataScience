"""Evidence and Contact page builders for the rebuilt e-portfolio."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import site_content as C  # noqa: E402

# Themed groupings for the Evidence surface. Each artefact is attributed to the
# module it was produced for and to what it demonstrates.
EVIDENCE_THEMES = [
    (
        "Research project &mdash; design, literature and method",
        "The research strand of Research Methods and Professional Practice: a full literature review, the plan and outline behind it, the data collection design, and the research proposal presented and transcribed.",
        [
            "assets/Literature Review Machine Learning for Churn Prediction at Cartrack.pdf",
            "assets/Literature Review Plan.pdf",
            "assets/Literature review outline.pdf",
            "assets/Literature review preperation.pdf",
            "assets/Data Collection Outline.pdf",
            "assets/Research Proposal Presentation Outline.pdf",
            "assets/Research Proposal Presentation Transcript.pdf",
            "assets/F1 Masters presentation.pdf",
        ],
    ),
    (
        "Machine learning &amp; AI projects",
        "Applied machine learning work: a collaborative discussion from the ML module, a fifteen-slide executive proposal to enhance AI dashcams with convolutional neural networks, its transcript, and a group business analysis report using k-nearest neighbours.",
        [
            "assets/Unit 1 - Colab discussion.pdf",
            "assets/Unit 1 - Colab discussion.docx",
            "assets/Unit 11 Slide Final.pdf",
            "assets/Unit 11 Transcript.pdf",
            "assets/Group TM3 - Business Analysis Report.pdf",
        ],
    ),
    (
        "Big data &amp; database engineering",
        "Data wrangling and database work from Deciphering Big Data, including a full logical database design and implementation for a ride-hailing company.",
        [
            "assets/Unit 1-3 Collaborative Discussion 1.pdf",
            "assets/Unit 6 - Project Report Database Design for Ride-Hailing Company.pdf",
            "assets/Unit 11 - Individual Project Executive Summary.pdf",
        ],
    ),
    (
        "Data visualisation &amp; dashboards",
        "Visualisation work from Visualising Data: a ticket-team dashboard manual, the dashboard design draft behind it, a programming exercise report, a website comparison and its summary post.",
        [
            "assets/Unit 12 - Final Project.pdf",
            "assets/Unit 9 - Dashboard Design Draft.pdf",
            "assets/Unit 8 - Report.pdf",
            "assets/Unit 2 - Collab Discussion.pdf",
            "assets/Unit 4 - Summary Post.pdf",
        ],
    ),
    (
        "Data science as a profession",
        "The Data Professional strand: an analytics report and end-of-module assignment on a national transport survey, plus two collaborative discussions on the data/AI/cloud convergence and on data protection.",
        [
            "assets/The data Prof - Data Analytics Report.pdf",
            "assets/The Data Prof - EOMA.pdf",
            "assets/Collab Disc 1.pdf",
            "assets/The Data Professional - Collaborative Discussion 2.pdf",
        ],
    ),
    (
        "Statistics &amp; professional practice worksheets",
        "The quantitative worksheets and the collaborative discussion from Research Methods and Professional Practice: hypothesis testing and summary measures in Excel, a charts worksheet, and an ethics discussion.",
        [
            "assets/e-Portfolio Activity Hypothesis Testing Worksheet.xlsx",
            "assets/e-Portfolio Activity Summary Measures Worksheet.xlsx",
            "assets/Charts Worksheet.xlsx",
            "assets/Collab discussion 1.pdf",
        ],
    ),
]


def build_evidence(page, wrap) -> str:
    groups = []
    total = 0
    for heading, intro, paths in EVIDENCE_THEMES:
        rows = []
        for path in paths:
            info = C.ARTEFACTS[path]
            total += 1
            rows.append(f'''                                                        <tr>
                                                                <td><a href="{path}" target="_blank" rel="noopener">{info["title"]}</a></td>
                                                                <td>{info["kind"]}</td>
                                                                <td><a href="{info["module"]}">{module_label(info["module"])}</a></td>
                                                                <td>{info["desc"]}</td>
                                                        </tr>''')
        groups.append(f'''                                        <section class="artefact-group" aria-labelledby="{slug(heading)}">
                                                <h2 id="{slug(heading)}">{heading}</h2>
                                                <p>{intro}</p>
                                                <table class="evidence-table">
                                                        <caption class="visually-hidden">{heading}</caption>
                                                        <thead>
                                                                <tr>
                                                                        <th scope="col">Artefact</th>
                                                                        <th scope="col">Type</th>
                                                                        <th scope="col">Module</th>
                                                                        <th scope="col">What it demonstrates</th>
                                                                </tr>
                                                        </thead>
                                                        <tbody>
{chr(10).join(rows)}
                                                        </tbody>
                                                </table>
                                        </section>''')

    dups = "\n".join(
        f'''                                                        <li>
                                                                <a href="{p}" target="_blank" rel="noopener">{info["title"]}</a>
                                                                <span class="artefact-kind">{info["kind"]}</span>
                                                                <span>{info["desc"]}</span>
                                                        </li>''' for p, info in C.ROOT_DUPLICATES.items()
    )

    body = wrap(f'''                                        <section class="section-head">
                                                <p class="eyebrow">Evidence</p>
                                                <h1>Evidence &amp; Artefacts</h1>
                                                <p>Every report, literature review, presentation and worksheet produced across my MSc and BSc modules &mdash; {total} artefacts, each attributed to the module it was written for and to what it demonstrates. Nothing here is a summary of the work; these are the work.</p>
                                        </section>

                                        <section class="callout">
                                                <h2>What you are looking at</h2>
                                                <p>These are the original academic artefacts. They are published unedited: the marks, feedback and rough edges are the point, because they show how the analysis was actually done rather than how it would be presented with hindsight.</p>
                                                <p>Academic work produced for assessment is retained as submitted. Presentation on this site has been rebuilt; the documents themselves have not been altered.</p>
                                        </section>

{chr(10).join(groups)}

                                        <section class="artefact-group" aria-labelledby="duplicate-copies">
                                                <h2 id="duplicate-copies">Additional copies at the site root</h2>
                                                <p>Three artefacts also exist as byte-identical copies at the root of this site, exactly as they are in the original repository. They are kept and linked here so that nothing in the supplied site is left unreachable.</p>
                                                <ul class="artefact-list">
{dups}
                                                </ul>
                                        </section>

                                        <section class="section">
                                                <div class="section-head">
                                                        <h2>How these artefacts map to modules</h2>
                                                        <p>Each artefact is also linked from the module page it was produced for, so it can be found either by theme here or by module in <a href="projects.html">Projects &amp; Modules</a>.</p>
                                                </div>
                                        </section>''')
    return page(
        title="Evidence & Artefacts | Matthew Bowyer",
        description=(
            "The academic artefacts behind Matthew Bowyer's MSc Data Science "
            "portfolio: literature review, research proposal, presentations, "
            "dashboards, database design reports and statistical worksheets."
        ),
        body=body,
        page_name="evidence.html",
    )


def module_label(path: str) -> str:
    if path in C.MODULES:
        return C.MODULES[path]["title"]
    if path in C.STRUCTURAL_PAGES:
        return C.STRUCTURAL_PAGES[path]["title"]
    return path


def slug(text: str) -> str:
    import re

    text = re.sub(r"&[a-z]+;", "", text)
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build_contact(page, wrap) -> str:
    body = wrap(f'''                                        <section class="section-head">
                                                <p class="eyebrow">Contact</p>
                                                <h1>Contact</h1>
                                                <p>Open to senior analytics and data science roles, and to consulting enquiries. Email is the fastest route; LinkedIn works too.</p>
                                        </section>

                                        <div class="contact-grid">
                                                <section class="surface">
                                                        <h2>Direct</h2>
                                                        <ul class="contact-list">
                                                                <li>
                                                                        <span class="contact-label">Email</span>
                                                                        <span><a href="mailto:{C.EMAIL}?subject=Enquiry%20from%20your%20portfolio">{C.EMAIL}</a></span>
                                                                </li>
                                                                <li>
                                                                        <span class="contact-label">LinkedIn</span>
                                                                        <span><a href="{C.LINKEDIN_URL}" target="_blank" rel="noopener noreferrer">{C.LINKEDIN_URL}</a></span>
                                                                </li>
                                                                <li>
                                                                        <span class="contact-label">GitHub</span>
                                                                        <span><a href="{C.GITHUB_URL}" target="_blank" rel="noopener noreferrer">{C.GITHUB_URL}</a></span>
                                                                </li>
                                                                <li>
                                                                        <span class="contact-label">Location</span>
                                                                        <span>{C.LOCATION}</span>
                                                                </li>
                                                        </ul>
                                                        <p><a class="button" href="mailto:{C.EMAIL}?subject=Enquiry%20from%20your%20portfolio">Email Matthew</a></p>
                                                </section>

                                                <section class="surface">
                                                        <h2>What to include</h2>
                                                        <p>If you are getting in touch about a role or a project, these help me reply usefully:</p>
                                                        <ul>
                                                                <li>The organisation and the team the role or project sits in.</li>
                                                                <li>The outcome you are trying to reach, and what is currently in the way.</li>
                                                                <li>Whether this is a permanent, contract or consulting engagement.</li>
                                                        </ul>
                                                        <p>I work from {C.LOCATION} and am comfortable working with distributed teams.</p>
                                                </section>
                                        </div>

                                        <section class="surface" id="contact-form">
                                                <h2>Message form</h2>
                                                <div class="callout callout--note">
                                                        <p><strong>This form does not send anything automatically.</strong> There is no backend on this site and no credentials to send mail, so nothing here is transmitted or stored &mdash; pressing the button below simply opens your own email client with the text you typed already filled in, addressed to <a href="mailto:{C.EMAIL}">{C.EMAIL}</a>. You can review the message before it is sent, and nothing is sent unless you send it yourself.</p>
                                                </div>
                                                <form class="contact-form" id="enquiry-form" novalidate>
                                                        <fieldset>
                                                                <legend>Write a message</legend>
                                                                <label for="cf-name">Your name</label>
                                                                <input type="text" id="cf-name" name="name" autocomplete="name" />

                                                                <label for="cf-email">Your email</label>
                                                                <input type="email" id="cf-email" name="email" autocomplete="email" />

                                                                <label for="cf-organisation">Organisation (optional)</label>
                                                                <input type="text" id="cf-organisation" name="organisation" autocomplete="organization" />

                                                                <label for="cf-message">Message</label>
                                                                <textarea id="cf-message" name="message"></textarea>

                                                                <p>
                                                                        <button type="submit" class="button">Open in my email client</button>
                                                                </p>
                                                                <p class="form-note" id="cf-status" role="status">
                                                                        Nothing is sent from this page. The button composes an email in your own client, addressed to {C.EMAIL}.
                                                                </p>
                                                        </fieldset>
                                                </form>
                                        </section>''')
    return page(
        title="Contact Matthew Bowyer | Analytics and Data Science Manager",
        description=(
            "Contact Matthew Bowyer, Analytics and Data Science Manager. Email "
            "matthewmbowyer@gmail.com, connect on LinkedIn, or use the "
            "mailto-composing message form."
        ),
        body=body,
        page_name="contact.html",
    )
