"""Page builders for the new professional pages: footer, About, Skills,
Projects/Modules, Evidence and Contact.

Imported by scripts/build_site.py, which supplies the shared page chrome.
"""
from __future__ import annotations

import html
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import site_content as C  # noqa: E402


def footer_fragment(page_fn) -> str:
    nav = "\n".join(
        f'                                        <li><a href="{href}">{label}</a></li>'
        for label, href in C.NAV_ITEMS
    )
    return f'''<!-- footer.html — shared footer fragment, fetched into #footer-placeholder by every page.
     Retains the HTML5 UP credit, as required by the Dopetrope template's CCA 3.0 licence. -->
<footer class="site-footer">
        <div class="wrap">
                <ul class="footer-cta" aria-label="Recruiter essentials">
                        <li><a class="button button--sm" href="{C.CV_PDF}" download>Download CV</a></li>
                        <li><a class="button button--sm alt" href="contact.html">Contact</a></li>
                        <li><a class="button button--sm alt" href="{C.LINKEDIN_URL}" target="_blank" rel="noopener noreferrer">LinkedIn</a></li>
                        <li><a class="button button--sm alt" href="evidence.html">Evidence</a></li>
                </ul>
                <div class="footer-grid">
                        <section>
                                <h2>Matthew Bowyer</h2>
                                <p>{C.SITE_ROLE}. {C.fill_experience(C.POSITIONING_PLAIN)}</p>
                                <p><a href="{C.CV_PAGE}">Full CV &rarr;</a></p>
                        </section>
                        <section>
                                <h2>Site</h2>
                                <ul class="footer-links">
{nav}
                                </ul>
                        </section>
                        <section>
                                <h2>Contact</h2>
                                <ul class="footer-links">
                                        <li><a href="mailto:{C.EMAIL}">{C.EMAIL}</a></li>
                                        <li><a href="{C.LINKEDIN_URL}" target="_blank" rel="noopener noreferrer">LinkedIn</a></li>
                                        <li><a href="{C.GITHUB_URL}" target="_blank" rel="noopener noreferrer">GitHub</a></li>
                                        <li>{C.LOCATION}</li>
                                </ul>
                        </section>
                </div>
                <div id="copyright">
                        <ul class="links">
                                <li>&copy; Matthew Bowyer. All rights reserved.</li>
                                <li>Design: <a href="http://html5up.net" target="_blank" rel="noopener noreferrer">HTML5 UP</a></li>
                        </ul>
                </div>
        </div>
</footer>
'''


def build_about(page, wrap) -> str:
    body = wrap('''                                        <section class="section-head">
                                                <p class="eyebrow">About</p>
                                                <h1>Matthew Bowyer</h1>
                                                <p>Analytics and Data Science Manager with <span data-experience="label"></span> across business intelligence, operational analytics, financial analysis, data science and reporting automation.</p>
                                                <ul class="cta-row">
                                                        <li><a class="button" href="cv.html">View CV</a></li>
                                                        <li><a class="button alt" href="assets/cv/Matthew-Bowyer-CV.pdf" download>Download CV</a></li>
                                                        <li><a class="button alt" href="contact.html">Contact</a></li>
                                                </ul>
                                        </section>

                                        <section class="surface">
                                                <h2>Background</h2>
                                                <p>I am an Analytics and Data Science Manager. My work sits where reporting, operational data and modelling meet: turning complex business requirements into analytical solutions that stakeholders can act on, and automating the manual work that gets in the way of them.</p>
                                                <p>That has meant leading global analytics and reporting delivery for senior stakeholders across finance, operations, telematics, research and development, and executive leadership; managing analysts; and building automated reporting, forecasting, anomaly detection and machine learning applications.</p>
                                                <p>My technical foundation is Python, SQL, Tableau, AWS and data pipeline development. Telematics and operational analytics are the domain I know best, because that is where I have spent most of my career: operational device data and the reporting built on top of it.</p>
                                        </section>

                                        <section class="surface">
                                                <h2>Career trajectory</h2>
                                                <p>I came into data science from analytics rather than the other way round. The early years were business intelligence and financial and operational reporting &mdash; learning what a business actually needs from its numbers, and how much of the value sits in the delivery mechanism rather than the model.</p>
                                                <p>That led into automation: reporting and workflow automation, and developing automated reporting. Forecasting, anomaly detection and machine learning followed naturally, because they were the next questions the business was already asking of data I already had.</p>
                                                <p>The formal underpinning came alongside the job. I completed a BSc (Hons) Data Science with The Open University, and an MSc in Data Science with the University of Essex Online (<span data-experience="msc">completed 2026</span>, Merit), while leading an analytics function. Doing both at once has been an education in prioritisation.</p>
                                        </section>

                                        <section class="surface">
                                                <h2>What I studied and why</h2>
                                                <p>I hold an MSc in Data Science with the University of Essex Online (<span data-experience="msc">completed 2026</span>, Merit). The taught modules are in this portfolio &mdash; research methods and professional practice, machine learning, deciphering big data, visualising data, the data professional and numerical analysis &mdash; on top of the earlier foundation in statistics, mathematics and computing.</p>
                                                <p>My thesis is <em>A Multimodal Driver Behaviour Evaluation System: Combining Telematics, VLMs and LLMs</em>: combining telematics data with vision-language and large language models to evaluate driver behaviour more richly than a single numeric signal allows. It is a direct extension of the work I do professionally, and an interactive demonstration of it is published on the <a href="thesis-demo.html">VLM thesis page</a>.</p>
                                        </section>

                                        <section class="surface">
                                                <h2>What I am looking for</h2>
                                                <p>I want to keep working where analytics has to deliver rather than just analyse: building and leading analytical teams, and putting machine learning and artificial intelligence into production where someone downstream depends on the result being correct.</p>
                                                <p>I am drawn to environments such as motorsport, where high-frequency data, engineering, operational strategy and human performance converge &mdash; and more broadly to telematics, sport and applied artificial intelligence, where I have most to offer.</p>
                                                <p>I am open to senior analytics and data science roles, and to consulting enquiries where an organisation needs a reporting and analytics function built, repaired or automated. The fastest way to reach me is email or LinkedIn.</p>
                                        </section>

                                        <section class="surface">
                                                <h2>What I have delivered</h2>
                                                <ul class="cap-list">
                                                        <li><span class="cap-name">Global analytics and reporting delivery</span><span class="cap-evidence">For senior stakeholders across finance, operations, telematics, research and development, and executive leadership.</span></li>
                                                        <li><span class="cap-name">Automated analytics in production</span><span class="cap-evidence">Automated reporting, forecasting, anomaly detection and machine learning applications.</span></li>
                                                        <li><span class="cap-name">Applied research</span><span class="cap-evidence">A multimodal driver behaviour evaluation system combining telematics data, vision-language models and large language models.</span></li>
                                                        <li><span class="cap-name">Commercial delivery</span><span class="cap-evidence">Company and business websites developed and shipped for real clients &mdash; see <a href="projects.html">Projects &amp; Modules</a>.</span></li>
                                                </ul>
                                                <p>Each of these traces to the supplied site or to a supplied academic artefact. Nothing on this page is asserted beyond that evidence.</p>
                                        </section>

                                        <section class="callout">
                                                <h2>Get in touch</h2>
                                                <p>Email <a href="mailto:matthewmbowyer@gmail.com">matthewmbowyer@gmail.com</a>, connect on <a href="https://www.linkedin.com/in/matthew-bowyer-535a6818a" target="_blank" rel="noopener noreferrer">LinkedIn</a>, or browse <a href="projects.html">Projects &amp; Modules</a> and <a href="evidence.html">Evidence</a>.</p>
                                        </section>''')
    return page(
        title="About Matthew Bowyer | Analytics and Data Science Manager",
        description=(
            "About Matthew Bowyer: background, career trajectory from business "
            "intelligence and automation into data science, his MSc Data Science "
            "at the University of Essex Online, and what he is looking for next."
        ),
        body=body,
        page_name="about.html",
    )


CAPABILITY_GROUPS = [
    dict(
        heading="Languages &amp; Tools",
        summary="The tooling used day to day, evidenced on this site and in the artefacts.",
        items=[
            ("Python", "Programming throughout the MSc, including regression, clustering and neural-network work in <a href=\"Machine Learning.html\">Machine Learning</a>."),
            ("SQL", "Relational and NoSQL data management in <a href=\"Data Management and analysis.html\">Data Management and analysis</a>, plus a full logical database design project in <a href=\"Deciphering Big Data.html\">Deciphering Big Data</a>."),
            ("Tableau", "Dashboard work in the <a href=\"Visualising Data.html\">Visualising Data</a> module."),
            ("Google Colab", "Used for the collaborative discussion work in the <a href=\"Machine Learning.html\">Machine Learning</a> module."),
            ("Excel analysis tooling", "Analysis ToolPak worksheets for hypothesis testing and summary measures in <a href=\"Research Methods and Professional Practice.html\">Research Methods and Professional Practice</a>."),
        ],
    ),
    dict(
        heading="Data &amp; Analytics",
        summary="Turning data into a decision, with the statistical grounding to defend it.",
        items=[
            ("Data Science", "Stated on the supplied site and evidenced across every module in this portfolio."),
            ("Business intelligence", "Stated on the supplied site; reflected in the reporting and dashboard work across the programme."),
            ("Applied statistics", "Hypothesis testing, summary measures, linear and generalised linear models, time series and Bayesian methods in <a href=\"Practical modern statistics.html\">Practical modern statistics</a> and <a href=\"Applied statistical modelling.html\">Applied statistical modelling</a>."),
            ("Data wrangling", "Cleansing and normalisation of large, diverse datasets in <a href=\"Deciphering Big Data.html\">Deciphering Big Data</a>."),
            ("Data visualisation and reporting", "Dashboard design and delivery in <a href=\"Visualising Data.html\">Visualising Data</a> &mdash; see the <a href=\"assets/Unit 12 - Final Project.pdf\" target=\"_blank\" rel=\"noopener\">Unit 12 dashboard manual</a>."),
            ("Automation", "Stated on the supplied site as reporting automation; the same instinct runs through the programming and pipeline work in the MSc."),
        ],
    ),
    dict(
        heading="Machine Learning &amp; AI",
        summary="Building models, evaluating them honestly, and knowing their limits.",
        items=[
            ("Machine learning", "A full twelve-unit reflective module in <a href=\"Machine Learning.html\">Machine Learning</a>: exploratory analysis, regression, clustering with scikit-learn and neural networks."),
            ("Artificial intelligence", "Deep neural learning, convolutional and recurrent networks in <a href=\"Machine Learning and Artificial Intelligence.html\">Machine Learning and Artificial Intelligence</a>."),
            ("Neural networks", "Creating, training and evaluating neural networks &mdash; evidenced by the <a href=\"assets/Unit 11 Slide Final.pdf\" target=\"_blank\" rel=\"noopener\">Unit 11 CNN dashcam presentation</a>."),
            ("Applied AI in telematics", "The supplied site states telematics and applied artificial intelligence as specialisms; the Unit 11 project applies CNNs to dashcam footage."),
            ("Research and literature review", "A thirteen-page churn-prediction literature review and a full research proposal, in <a href=\"Research Methods and Professional Practice.html\">Research Methods and Professional Practice</a>."),
        ],
    ),
    dict(
        heading="Cloud &amp; Engineering",
        summary="Enough infrastructure knowledge to get analysis into production.",
        items=[
            ("Cloud technologies", "Computer hardware, cloud technologies and data processing in <a href=\"Introduction to computers and technology 2.html\">Introduction to computers and technology 2</a>."),
            ("Data pipelines and processing", "Designing and evaluating solutions for processing datasets in <a href=\"Deciphering Big Data.html\">Deciphering Big Data</a>."),
            ("Database design", "Logical database design and implementation for a ride-hailing company &mdash; see the <a href=\"assets/Unit 6 - Project Report Database Design for Ride-Hailing Company.pdf\" target=\"_blank\" rel=\"noopener\">Unit 6 project report</a>."),
            ("Numerical methods", "The mathematical and statistical methodology underpinning data science and AI in <a href=\"Numerical Analysis.html\">Numerical Analysis</a>."),
            ("Professional practice", "Research ethics, professional responsibility and collaborative working in <a href=\"Research Methods and Professional Practice.html\">Research Methods and Professional Practice</a>."),
        ],
    ),
]


def build_skills(page, wrap) -> str:
    groups = []
    for g in CAPABILITY_GROUPS:
        rows = "\n".join(
            f'''                                                                <li>
                                                                        <span class="cap-name">{name}</span>
                                                                        <span class="cap-evidence">{evidence}</span>
                                                                </li>''' for name, evidence in g["items"]
        )
        groups.append(f'''                                        <li class="cap-group">
                                                <h2>{g["heading"]}</h2>
                                                <p class="cap-summary">{g["summary"]}</p>
                                                <ul class="cap-list">
{rows}
                                                </ul>
                                        </li>''')

    body = wrap(f'''                                        <section class="section-head">
                                                <p class="eyebrow">Capabilities</p>
                                                <h1>Skills &amp; Capabilities</h1>
                                                <p>Technical and professional capability, grouped honestly. Every entry points at the module page or artefact on this site that evidences it &mdash; nothing here is claimed without a source.</p>
                                        </section>

                                        <section class="callout callout--note">
                                                <h2>How to read this page</h2>
                                                <p>These are the capabilities evidenced by the supplied site and by the academic artefacts in this portfolio. My professional context adds more than a coursework portfolio can show; I would rather discuss that in conversation than pad this page with claims the evidence here cannot support.</p>
                                        </section>

                                        <section class="section" aria-labelledby="capability-groups">
                                                <h2 id="capability-groups" class="visually-hidden">Capability groups</h2>
                                                <ul class="cap-grid">
{chr(10).join(groups)}
                                                </ul>
                                        </section>

                                        <section class="section">
                                                <div class="section-head">
                                                        <h2>Where this is evidenced</h2>
                                                        <p>Every capability above traces to the programme pages, module pages or downloadable artefacts below.</p>
                                                </div>
                                                <div class="two-col">
                                                        <div class="panel">
                                                                <h3>Programme</h3>
                                                                <ul>
                                                                        <li><a href="Masters.html">MSc Data Science &mdash; University of Essex Online</a></li>
                                                                        <li><a href="Honours.html">BSc (Hons) Data Science &mdash; The Open University</a></li>
                                                                </ul>
                                                        </div>
                                                        <div class="panel">
                                                                <h3>Artefacts</h3>
                                                                <p><a href="evidence.html">The Evidence surface</a> lists every report, literature review, presentation and worksheet produced across the programme, with attribution.</p>
                                                        </div>
                                                </div>
                                        </section>''')
    return page(
        title="Skills & Capabilities | Matthew Bowyer",
        description=(
            "Matthew Bowyer's technical and professional capabilities: languages "
            "and tools, data and analytics, machine learning and AI, cloud and "
            "engineering. Each capability links to the module or artefact that "
            "evidences it."
        ),
        body=body,
        page_name="skills.html",
    )


def flagship_cards() -> str:
    """The strongest evidenced work, surfaced first (AC-52)."""
    cards = []
    for w in C.FLAGSHIP_WORK:
        tags = "".join(
            f'<li><span class="badge">{html.escape(t)}</span></li>' for t in w["tags"]
        )
        if w["href"]:
            link = (f'<a class="card-link" href="{w["href"]}" '
                    f'target="_blank" rel="noopener noreferrer">{w["link_label"]} &rarr;</a>')
        else:
            link = (f'<p class="card-private">{w["link_label"]}. '
                    f'No public link is published, so there is no dead link here.</p>')
        cards.append(f'''                                                        <li class="card card--project">
                                                                <div class="card-body">
                                                                        <p class="eyebrow">{w["kicker"]}</p>
                                                                        <h3>{html.escape(w["title"])}</h3>
                                                                        <ul class="card-meta">{tags}</ul>
                                                                        <p>{w["body"]}</p>
                                                                        {link}
                                                                </div>
                                                        </li>''')
    return "\n".join(cards)


def impact_list() -> str:
    items = []
    for p in C.IMPACT_POINTS:
        items.append(f'''                                                        <li class="impact">
                                                                <p class="impact-figure">{C.fill_experience(p["figure"])}</p>
                                                                <p class="impact-label">{p["label"]}</p>
                                                                <p class="impact-body">{C.fill_experience(p["body"])}</p>
                                                        </li>''')
    return "\n".join(items)


def build_cv(page, wrap) -> str:
    caps = "\n".join(
        f'''                                                                <li>
                                                                        <span class="cap-name">{name}</span>
                                                                        <span class="cap-evidence">{body}</span>
                                                                </li>''' for name, body in C.CV_CAPABILITIES
    )
    exp = "\n".join(
        f'''                                                        <li class="cv-role">
                                                                <h3>{e["role"]}</h3>
                                                                <p class="cv-meta">{e["where"]}</p>
                                                                <p>{e["body"]}</p>
                                                                <p class="cv-source">Evidence: {e["source"]}</p>
                                                        </li>''' for e in C.CV_EXPERIENCE
    )
    lead = "\n".join(
        f'''                                                        <li class="cv-role">
                                                                <h3>{e["role"]}</h3>
                                                                <p class="cv-meta">{e["where"]}</p>
                                                                <p>{e["body"]}</p>
                                                        </li>''' for e in C.CV_LEADERSHIP
    )
    edu = "\n".join(
        f'''                                                        <li class="cv-role">
                                                                <h3>{e["award"]}</h3>
                                                                <p class="cv-meta">{e["where"]} &middot; {e["status"]}</p>
                                                                <p>{e["body"]}</p>
                                                        </li>''' for e in C.CV_EDUCATION
    )
    proj = "\n".join(
        f'''                                                                <li>
                                                                        <span class="cap-name">{html.escape(t)}</span>
                                                                        <span class="cap-evidence">{d}</span>
                                                                </li>''' for t, d in C.CV_PROJECTS
    )
    body = wrap(f'''                                        <section class="section-head">
                                                <p class="eyebrow">Curriculum vitae</p>
                                                <h1>{C.SITE_NAME} &mdash; CV</h1>
                                                <p>{C.SITE_ROLE} with <span data-experience="label"></span> across business intelligence, operational analytics, financial analysis, data science and reporting automation.</p>
                                                <ul class="cta-row">
                                                        <li><a class="button" href="{C.CV_PDF}" download>Download CV (PDF)</a></li>
                                                        <li><a class="button alt" href="mailto:{C.EMAIL}?subject=Enquiry%20from%20your%20portfolio">Email Matthew</a></li>
                                                        <li><a class="button alt" href="{C.LINKEDIN_URL}" target="_blank" rel="noopener noreferrer">LinkedIn</a></li>
                                                        <li><a class="button alt" href="evidence.html">Evidence</a></li>
                                                </ul>
                                        </section>

                                        <section class="surface">
                                                <h2>Profile</h2>
                                                <p>{C.CV_PROFILE_HTML}</p>
                                        </section>

                                        <section class="surface">
                                                <h2>Experience</h2>
                                                <ul class="cv-list">
{exp}
                                                </ul>
                                        </section>

                                        <section class="surface">
                                                <h2>Leadership &amp; Additional Achievements</h2>
                                                <ul class="cv-list">
{lead}
                                                </ul>
                                        </section>

                                        <section class="surface">
                                                <h2>Education</h2>
                                                <ul class="cv-list">
{edu}
                                                </ul>
                                        </section>

                                        <section class="surface">
                                                <h2>Capabilities</h2>
                                                <ul class="cap-list">
{caps}
                                                </ul>
                                        </section>

                                        <section class="surface">
                                                <h2>Selected projects</h2>
                                                <ul class="cap-list">
{proj}
                                                </ul>
                                                <p>Full detail, including the academic modules and downloadable artefacts, is on the <a href="projects.html">Projects &amp; Modules</a> and <a href="evidence.html">Evidence</a> pages.</p>
                                        </section>

                                        <section class="surface">
                                                <h2>Contact</h2>
                                                <ul class="contact-list">
                                                        <li><span class="contact-label">Email</span><span><a href="mailto:{C.EMAIL}">{C.EMAIL}</a></span></li>
                                                        <li><span class="contact-label">LinkedIn</span><span><a href="{C.LINKEDIN_URL}" target="_blank" rel="noopener noreferrer">{C.LINKEDIN_URL}</a></span></li>
                                                        <li><span class="contact-label">GitHub</span><span><a href="{C.GITHUB_URL}" target="_blank" rel="noopener noreferrer">{C.GITHUB_URL}</a></span></li>
                                                        <li><span class="contact-label">Location</span><span>{C.LOCATION}</span></li>
                                                </ul>
                                        </section>

                                        <section class="callout">
                                                <h2>How to read this page</h2>
                                                <p>Every statement here traces to the supplied site, the supplied academic artefacts, or the LinkedIn profile already linked from this site. Nothing is inferred, and nothing is quantified that the evidence does not support.</p>
                                        </section>''')
    return page(
        title="CV | Matthew Bowyer, Analytics and Data Science Manager",
        description=(
            "Curriculum vitae for Matthew Bowyer, Analytics and Data Science "
            "Manager: analytics, business intelligence, operational analytics, "
            "financial analysis, data science and reporting automation, with a "
            "downloadable PDF."
        ),
        body=body,
        page_name="cv.html",
    )


def build_projects(page, wrap, modules, structural, cover_for) -> str:
    cards = []
    for path in modules["order"]:
        m = modules["map"][path]
        img = cover_for(path)
        media = (
            f'\n                                                                <a class="card-media" tabindex="-1" aria-hidden="true" href="{path}">'
            f'<img src="{img}" alt="" loading="lazy" /></a>' if img else ""
        )
        credit = f'\n                                                                                <li><span class="badge">{m["credit"]}</span></li>' if m["credit"] else ""
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

    structural_cards = []
    for path, meta in structural.items():
        logo = meta.get("logo")
        media = (
            f'\n                                                                <a class="card-media card-media--logo" href="{path}">'
            f'<img src="{logo}" alt="{meta.get("logo_alt", "")}" loading="lazy" /></a>'
            if logo else ""
        )
        structural_cards.append(f'''                                                        <li class="card">{media}
                                                                <div class="card-body">
                                                                        <h3><a href="{path}">{meta["title"]}</a></h3>
                                                                        <ul class="card-meta">
                                                                                <li><span class="badge badge--count">{meta["eyebrow"]}</span></li>
                                                                        </ul>
                                                                        <p>{meta["summary"]}</p>
                                                                        <a class="card-link" href="{path}">Open programme &rarr;</a>
                                                                </div>
                                                        </li>''')

    n_modules = len(modules["order"])
    body = wrap(f'''                                        <section class="section-head">
                                                <p class="eyebrow">Portfolio</p>
                                                <h1>Projects &amp; Modules</h1>
                                                <p>Research, commercial and academic work, strongest first &mdash; then {n_modules} taught modules across an MSc in Data Science (University of Essex Online) and a BSc (Hons) Data Science (The Open University). Each module card opens that module's own page: its learning outcomes, reflection and the artefacts produced for it.</p>
                                        </section>

                                        <section class="section" aria-labelledby="flagship">
                                                <div class="section-head">
                                                        <p class="eyebrow">Strongest first</p>
                                                        <h2 id="flagship">Selected projects</h2>
                                                        <p>Research, commercial and academic work the supplied site evidences, ordered with the highest-value work first.</p>
                                                </div>
                                                <ul class="card-grid">
{flagship_cards()}
                                                </ul>
                                        </section>

                                        <section class="section" aria-labelledby="programme-pages">
                                                <h2 id="programme-pages" class="visually-hidden">Programme pages</h2>
                                                <div class="section-head">
                                                        <p class="eyebrow">Academic</p>
                                                        <h2>Programmes</h2>
                                                </div>
                                                <ul class="card-grid">
{chr(10).join(structural_cards)}
                                                </ul>
                                        </section>

                                        <section class="section" aria-labelledby="module-list">
                                                <div class="section-head">
                                                        <p class="eyebrow">Body of work</p>
                                                        <h2 id="module-list">Modules</h2>
                                                        <p>Ordered by programme, then alphabetically. MSc Data Science modules first, then the BSc (Hons) Data Science foundation.</p>
                                                </div>
                                                <ul class="card-grid">
{chr(10).join(cards)}
                                                </ul>
                                        </section>

                                        <section class="section">
                                                <div class="section-head">
                                                        <h2>Artefacts</h2>
                                                        <p>The reports, literature reviews, presentations and worksheets produced across these modules are collected on the Evidence surface.</p>
                                                </div>
                                                <p><a class="button" href="evidence.html">View Evidence &amp; artefacts</a></p>
                                        </section>''')
    return page(
        title="Projects & Modules | Matthew Bowyer, MSc Data Science Portfolio",
        description=(
            "Matthew Bowyer's portfolio of work: the MSc Data Science thesis, "
            "commercial client websites and an academic e-portfolio, plus MSc and "
            "BSc (Hons) Data Science modules presented as a card-based body of "
            "work, each linking to its page and artefacts."
        ),
        body=body,
        page_name="projects.html",
    )
