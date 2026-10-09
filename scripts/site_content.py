"""Content data for the e-portfolio rebuild.

Every claim published on the delivered site is traceable to the supplied site
(the canonical copy under inputs/) or to a supplied academic artefact. Items
from the owner's private capability list that are not evidenced are NOT here;
they live only in docs/DELIVERY_SUMMARY.md as OWNER CONFIRMATION points.

Authoring tool only: the delivered site is plain static HTML/CSS and does not
need this module to run.
"""

# ---------------------------------------------------------------------------
# Canonical navigation — ONE definition, emitted byte-identically on every page.
# ---------------------------------------------------------------------------

NAV_ITEMS = [
    ("Home", "index.html"),
    ("About", "about.html"),
    ("Skills &amp; Capabilities", "skills.html"),
    ("Projects &amp; Modules", "projects.html"),
    ("Experience", "experience.html"),
    ("Evidence", "evidence.html"),
    ("Thesis Demo", "thesis-demo.html"),
    ("CV", "cv.html"),
    ("Contact", "contact.html"),
]

SITE_NAME = "Matthew Bowyer"
SITE_ROLE = "Analytics and Data Science Manager"
LINKEDIN_URL = "https://www.linkedin.com/in/matthew-bowyer-535a6818a"
GITHUB_URL = "https://github.com/MatthewMBowyer"
EMAIL = "matthewmbowyer@gmail.com"
LOCATION = "Gauteng, South Africa"

# The canonical public URL of the delivered site. Unknown to this run, so a
# self-consistent absolute base is documented in docs/DELIVERY_SUMMARY.md and
# used for og:url and the sitemap so every URL is genuinely absolute.
SITE_BASE_URL = "https://matthewmbowyer.github.io/UoEOMScDataScience"
SITE_NAME_SHORT = "Matthew Bowyer"
SOCIAL_IMAGE = "images/social-card.png"
SOCIAL_IMAGE_ALT = ("Matthew Bowyer, Analytics and Data Science Manager - "
                    "data science portfolio")
CV_PAGE = "cv.html"
CV_PDF = "assets/cv/Matthew-Bowyer-CV.pdf"

# The experience figure is NEVER written into the delivered HTML as a literal.
# This marker is replaced at render time by assets/js/experience.js (browser) and
# by fill_experience() for the offline-generated CV PDF and social card. See
# CAREER_START / experience_label below.
EXP_YEAR_MARK = '<span data-experience="label"></span>'

# ---------------------------------------------------------------------------
# Evidenced impact statements.
# Every sentence below is traceable to inputs/index.html (the supplied site) or
# to a supplied academic artefact; the module/artefact that evidences it is
# named in `source`. Nothing on the owner's private capability list is here.
# ---------------------------------------------------------------------------

IMPACT_POINTS = [
    dict(
        figure=EXP_YEAR_MARK,
        label="in analytics and reporting delivery",
        body=(f"{EXP_YEAR_MARK} across business intelligence, operational "
              "analytics, financial analysis, data science and reporting "
              "automation."),
        source="Stated on the supplied site (inputs/index.html).",
    ),
    dict(
        figure="Global",
        label="analytics and reporting delivery",
        body=("Leads global analytics and reporting delivery for senior "
              "stakeholders across finance, operations, telematics, research and "
              "development, and executive leadership."),
        source="Stated on the supplied site (inputs/index.html).",
    ),
    dict(
        figure="Automated",
        label="reporting, forecasting and anomaly detection",
        body=("Builds automated reporting, forecasting, anomaly detection and "
              "machine learning applications, and manages analysts."),
        source="Stated on the supplied site (inputs/index.html).",
    ),
    dict(
        figure="MSc thesis",
        label="multimodal driver behaviour evaluation",
        body=("Dissertation combining telematics data, vision-language models and "
              "large language models to evaluate driver behaviour more richly "
              "than a single numeric signal allows."),
        source=("Stated on the supplied site and evidenced by the thesis "
                "repository it links."),
    ),
    dict(
        figure="Commercial",
        label="client websites delivered",
        body=("Company and business websites developed and shipped for real "
              "clients: Pringle Padel, The Bowyer Collective and Chloe's "
              "Travelling Tutors."),
        source="Published, linkable repositories listed on the supplied site.",
    ),
    dict(
        figure="BSc (Hons) + MSc",
        label="Data Science, studied alongside the job",
        body=("A BSc (Hons) Data Science from The Open University, and an MSc in "
              "Data Science with the University of Essex Online, "
              "<span data-experience=\"msc\">completed 2026</span> (Merit) while "
              "leading an analytics function."),
        source="Stated on the supplied site and evidenced across this portfolio.",
    ),
]

# The strongest evidenced professional work, surfaced first (AC-52). Each entry
# names where it is evidenced; `private` entries carry no link at all.
FLAGSHIP_WORK = [
    dict(
        title="Essex MSc Data Science Thesis",
        kicker="Research &middot; multimodal AI",
        body=("A multimodal driver behaviour evaluation system that combines "
              "telematics data, vision-language models and large language models "
              "to support richer behavioural assessment."),
        tags=["Research", "Jupyter Notebook", "Public"],
        href="https://github.com/MatthewMBowyer/Essex_MSC_DataScience_Thesis",
        link_label="View repository",
    ),
    dict(
        title="UoEOMScDataScience e-portfolio",
        kicker="Academic &middot; this site",
        body=("The University of Essex Online MSc e-portfolio: MSc work, "
              "previous Honours material, academic reflections and published "
              "articles. This site is the rebuilt, recruiter-facing presentation "
              "of it."),
        tags=["Academic", "HTML", "Public"],
        href="https://github.com/MatthewMBowyer/UoEOMScDataScience",
        link_label="View repository",
    ),
    dict(
        title="Pringle Padel",
        kicker="Commercial &middot; client website",
        body=("A company website developed for Pringle Padel, presenting the "
              "business, its services and its brand through a responsive web "
              "interface."),
        tags=["Commercial", "HTML", "Public"],
        href="https://github.com/MatthewMBowyer/PringlePadel",
        link_label="View repository",
    ),
    dict(
        title="The Bowyer Collective",
        kicker="Commercial &middot; client website",
        body=("A photography portfolio website developed for Chloe's Photography, "
              "designed to showcase visual work and provide a professional "
              "online presence."),
        tags=["Commercial", "CSS", "Public"],
        href="https://github.com/MatthewMBowyer/The-Bowyer-collective",
        link_label="View repository",
    ),
    dict(
        title="Chloe's Travelling Tutors",
        kicker="Commercial &middot; client website",
        body=("A business website created for Chloe's Travelling Tutors, "
              "presenting its tutoring services and providing a clear interface "
              "for prospective clients."),
        tags=["Commercial", "CSS", "Public"],
        href="https://github.com/MatthewMBowyer/Chloes-Traveling-tutors",
        link_label="View repository",
    ),
    dict(
        title="Padel Scraper",
        kicker="Commercial &middot; data engineering",
        body=("A Python-based web scraping system that automatically collects "
              "padel results across divisions and transforms the extracted "
              "information into structured JSON."),
        tags=["Commercial", "Python", "Private"],
        href=None,
        link_label="Private commercial repository &mdash; not publicly linkable",
    ),
    dict(
        title="Industry Zero",
        kicker="Personal &middot; software engineering",
        body=("A private game-development project built in C#. The project "
              "provides a practical environment for exploring software "
              "architecture, game systems and interactive application "
              "development."),
        tags=["Personal", "C#", "Private"],
        href=None,
        link_label="Private development repository &mdash; not publicly linkable",
    ),
]

# The CV is authored from the authoritative CV (inputs/Matthew_Bowyer_CV_2026.pdf,
# extracted to inputs/CV_EXTRACTED_TEXT.md). This is the single source of truth
# for both the cv.html page and the generated PDF, so the two can never drift
# apart. Every employer, date, title and capability below is stated verbatim by
# that source CV; the experience figure is computed at render time (see
# experience_years_text), never hardcoded.
CV_PROFILE_HTML = (
    "Analytics and Data Science Manager with " + EXP_YEAR_MARK + " across "
    "analytics, business "
    "intelligence, financial analysis, data science, machine learning and "
    "reporting automation. Leads global analytics, data science and applied AI "
    "delivery across 29 countries, with regular engagement with C-suite "
    "leadership. Combines leadership with hands-on delivery across Python, SQL, "
    "predictive and prescriptive analytics, statistical modelling, feature "
    "engineering, MLOps and GenAI. Proven track record of productionising "
    "analytical workflows, governing reusable data and ML assets, and delivering "
    "decision support across millions of devices, SIMs and customer records."
)

CV_PROFILE = (
    "Analytics and Data Science Manager with {years} across analytics, business "
    "intelligence, financial analysis, data science, machine learning and "
    "reporting automation. Leads global analytics, data science and applied AI "
    "delivery across 29 countries, with regular engagement with C-suite "
    "leadership. Combines leadership with hands-on delivery across Python, SQL, "
    "predictive and prescriptive analytics, statistical modelling, feature "
    "engineering, MLOps and GenAI. Proven track record of productionising "
    "analytical workflows, governing reusable data and ML assets, and delivering "
    "decision support across millions of devices, SIMs and customer records."
)

CV_CAPABILITIES = [
    ("Leadership & Strategy",
     "Analytics strategy, data strategy, AI/ML capability building, executive "
     "decision support, stakeholder management, cross-functional delivery, "
     "mentoring."),
    ("Data Science & AI",
     "Python, SQL, machine learning, statistical modelling, predictive and "
     "prescriptive analytics, decision science, optimisation, feature "
     "engineering and selection, experimentation, hypothesis testing, model "
     "validation, tuning, calibration, performance benchmarking, GenAI, LLMs, "
     "RAG, VLMs."),
    ("Engineering & Platforms",
     "Databricks, MLflow, Spark, PySpark, Delta Lake, Feature Store, MLOps, "
     "ETL/ELT, data pipelines, data modelling, model monitoring and drift, "
     "data and model governance, data quality, lineage, AWS, MySQL, Tableau."),
]

CV_EXPERIENCE = [
    dict(
        role="Manager: Data Analytics & Global Reporting",
        where="Cartrack · Jun 2024 – Present · South Africa",
        body=("Leads global analytics, reporting automation, data science, "
              "machine learning and applied AI delivery across 29 countries and "
              "major business functions including sales, finance, marketing, "
              "operations, telematics and R&D. Leads predictive and prescriptive "
              "analytics, forecasting, anomaly detection and decision-support "
              "across datasets spanning millions of devices, SIMs and customer "
              "records; owns ML lifecycle activities including experimentation, "
              "validation, tuning, calibration and model monitoring; productionises "
              "business-critical analytics and ML workflows, replacing multi-day "
              "manual processes with unattended execution."),
        source="inputs/Matthew_Bowyer_CV_2026.pdf — Cartrack, Jun 2024 - Present.",
    ),
    dict(
        role="SIM Usage Analyst",
        where="Cartrack · Jan 2024 – May 2024 · South Africa",
        body=("Analysed global SIM usage, device health, firmware performance and "
              "operational trends across Cartrack's international fleet, using "
              "large operational datasets to support issue prioritisation and "
              "decision-making. Performed exploratory analysis, anomaly detection "
              "and trend analysis, and improved visibility into fleet, "
              "connectivity and device health through repeatable analytical "
              "reporting and data-quality checks."),
        source="inputs/Matthew_Bowyer_CV_2026.pdf — Cartrack, Jan 2024 - May 2024.",
    ),
    dict(
        role="Data Scientist",
        where="Greendoor Group · Mar 2023 – Jan 2024 · South Africa",
        body=("Led analytics, data science and machine learning initiatives across "
              "Greendoor Group and its African subsidiaries, supporting "
              "operational, financial, fleet and executive decision-making. Built "
              "predictive and prescriptive models and production-oriented "
              "analytical solutions using Python, MySQL, Tableau and AWS-based "
              "data pipelines, and applied model monitoring, governance and "
              "decision-science practices."),
        source="inputs/Matthew_Bowyer_CV_2026.pdf — Greendoor Group, Mar 2023 - Jan 2024.",
    ),
    dict(
        role="Data Analyst",
        where="Smith Yong and Associates · Jan 2019 – Feb 2023 · Gauteng, South Africa",
        body=("Supported audit, financial analysis, inventory verification and "
              "data quality initiatives through structured reporting and analysis. "
              "Analysed financial and operational records to support audit and "
              "business review processes, led physical inventory verifications, "
              "and cleaned, validated and improved datasets to support reliable "
              "analysis and decision-making."),
        source="inputs/Matthew_Bowyer_CV_2026.pdf — Smith Yong and Associates, Jan 2019 - Feb 2023.",
    ),
]

CV_LEADERSHIP = [
    dict(
        role="Vice Chairman & Athlete Representative",
        where="Gauteng Weightlifting Association · Feb 2025 – Present",
        body=("Elected to represent athlete interests and work with the "
              "association executive on athlete development, competition planning "
              "and strategic improvements. Serves as a liaison with the South "
              "African Weightlifting Federation."),
        source="inputs/Matthew_Bowyer_CV_2026.pdf — Feb 2025 - Present.",
    ),
    dict(
        role="Executive Committee Member",
        where="Gauteng Weightlifting Association · Jul 2023 – Feb 2025",
        body=("Initiated and managed automated tracking and uploading of "
              "technical official statistics, improving the timeliness and "
              "accuracy of federation records, and supported automation of "
              "athlete and event record tracking, website maintenance and "
              "technical operations."),
        source="inputs/Matthew_Bowyer_CV_2026.pdf — Jul 2023 - Feb 2025.",
    ),
    dict(
        role="South African Presidents Team Representative",
        where="RLSS Commonwealth Festival of Lifesaving · 2019 · Leeds, UK",
        body=("Represented South Africa in Leeds, UK; won an individual silver "
              "medal with a provincial record and contributed to two team medal "
              "finishes."),
        source="inputs/Matthew_Bowyer_CV_2026.pdf — 2019.",
    ),
]

CV_EDUCATION = [
    dict(
        award="MSc Data Science",
        where="University of Essex Online",
        status="Completed · Jan 2024 – Jun 2026 · Merit",
        body=("Taught modules in research methods and professional practice, "
              "machine learning, deciphering big data, visualising data, the data "
              "professional and numerical analysis. Thesis: A Multimodal Driver "
              "Behaviour Evaluation System: Combining Telematics, VLMs and LLMs."),
    ),
    dict(
        award="BSc (Hons) Data Science",
        where="The Open University",
        status="Completed · Mar 2020 – Jul 2023",
        body=("Twelve 30-credit modules grounding statistics, mathematics, "
              "computing, algorithms and machine learning. Evidenced by the "
              "module pages in this portfolio."),
    ),
]

CV_PROJECTS = [
    ("Essex MSc Data Science Thesis", "Multimodal driver behaviour evaluation "
     "combining telematics data, vision-language models and large language "
     "models."),
    ("UoEOMScDataScience e-portfolio", "The University of Essex Online MSc "
     "e-portfolio - the body of academic work this site presents."),
    ("Pringle Padel", "Company website for a client, built to present the "
     "business, its services and its brand."),
    ("The Bowyer Collective", "Photography portfolio website for Chloe's "
     "Photography."),
    ("Chloe's Travelling Tutors", "Business website presenting tutoring services "
     "to prospective clients."),
    ("Padel Scraper", "Python web-scraping system collecting padel results and "
     "transforming them into structured JSON (private repository)."),
]

# The career start that anchors every experience figure. Stated by the
# authoritative CV as the Smith Yong and Associates role (Jan 2019 - Feb 2023),
# the first professional role. All experience figures are computed from this at
# render time; no "N years" string is ever hardcoded.
CAREER_START = (2019, 1)
CAREER_START_ISO = "2019-01"

# Evidenced on the supplied site (inputs/index.html). The experience figure is
# NEVER written into the delivered HTML as a literal (see EXP_YEAR_MARK above).
POSITIONING = (
    f"Analytics leader with {EXP_YEAR_MARK} across business "
    "intelligence, operational analytics, financial analysis, data science and "
    "reporting automation."
)
POSITIONING_PLAIN = (
    f"Analytics leader with {EXP_YEAR_MARK} across business "
    "intelligence, operational analytics, financial analysis, data science and "
    "reporting automation."
)

SPECIALISMS = [
    "Business intelligence",
    "Automation",
    "Machine learning",
    "Telematics",
    "Applied artificial intelligence",
]

# The seven skills the supplied site already evidences.
PRIMARY_SKILLS = [
    "Data Science",
    "Machine Learning",
    "Artificial Intelligence",
    "Python",
    "SQL",
    "Tableau",
    "Telematics",
]

# ---------------------------------------------------------------------------
# Module catalogue. `credit` = the credits stated on the supplied structural
# page; `summary` is outcome-led and derived from the page's own stated
# learning outcomes; `programme` places it in Honours or MSc.
# ---------------------------------------------------------------------------

MODULES = {
    "Algorithms, data structure and computability.html": dict(
        title="Algorithms, data structure and computability",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "Data structures including lists, trees and graphs, algorithm "
            "complexity and runtime measurement, search, recursion and greedy "
            "techniques, and the limits of computation &mdash; non-computability "
            "and the P &ne; NP conjecture."
        ),
    ),
    "Analysing data.html": dict(
        title="Analysing data",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "Statistical techniques beyond the introductory level: modelling "
            "variation, estimation, confidence intervals, hypothesis testing and "
            "regression &mdash; and communicating the results to statistical and "
            "non-statistical audiences."
        ),
    ),
    "Applied statistical modelling.html": dict(
        title="Applied statistical modelling",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "Fitting and interpreting linear and generalised linear models against "
            "real questions &mdash; wage rates, Olympic medal counts, exam scores "
            "&mdash; with the emphasis on interpreting results, not just computing "
            "them."
        ),
    ),
    "Data Management and analysis.html": dict(
        title="Data Management and analysis",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "Relational versus NoSQL data management, formulating and answering "
            "questions with data, visual analysis of real datasets, and the "
            "technical and socio-legal issues in storing and using data."
        ),
    ),
    "Deciphering Big Data.html": dict(
        title="Deciphering Big Data",
        programme="MSc",
        credit="",
        summary=(
            "Data wrangling at scale: the diversity of data types, sources and "
            "collection methods, cleansing and normalisation, storage formats, "
            "security and risk &mdash; plus a logical database design project for a "
            "ride-hailing company."
        ),
    ),
    "Essential mathematics.html": dict(
        title="Essential mathematics",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "Algebra and graphs, functions, trigonometry, vectors, calculus, "
            "matrices, sequences and complex numbers &mdash; using mathematical "
            "software and communicating solutions clearly."
        ),
    ),
    "Interactive design and user experience.html": dict(
        title="Interactive design and user experience",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "User-centred design end to end: user research and requirements "
            "gathering, concept to prototype, and evaluation against real user "
            "feedback."
        ),
    ),
    "Introduction to computers and technology 1.html": dict(
        title="Introduction to computers and technology 1",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "From the development of computing and IT systems to digital media, "
            "databases and web development, programming in a graphical "
            "environment, networking and the Internet of Things, and the social "
            "side of computing."
        ),
    ),
    "Introduction to computers and technology 2.html": dict(
        title="Introduction to computers and technology 2",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "Computer hardware, cloud technologies, mobile components and data "
            "processing, with Python programming applied to health and well-being "
            "data, set against the security and cybercrime context."
        ),
    ),
    "Introduction to statistics.html": dict(
        title="Introduction to statistics",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "Fundamental statistical concepts and their application, collecting, "
            "analysing and interpreting data to solve real problems, hands-on "
            "Minitab work and manual computation."
        ),
    ),
    "Machine Learning and Artificial Intelligence.html": dict(
        title="Machine Learning and Artificial Intelligence",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "Deep neural learning in practice: creating, training and evaluating "
            "neural networks, convolutional networks for image classification and "
            "recurrent networks for time-dependent data &mdash; alongside the "
            "societal questions they raise."
        ),
    ),
    "Machine Learning.html": dict(
        title="Machine Learning",
        programme="MSc",
        credit="",
        summary=(
            "Twelve units of reflective practice across the machine learning "
            "lifecycle: exploratory data analysis, correlation and regression with "
            "scikit-learn, clustering including a team project, and building and "
            "training artificial neural networks."
        ),
    ),
    "Mathematical methods.html": dict(
        title="Mathematical methods",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "Analytical solutions for first- and second-order ordinary "
            "differential equations, linear algebra, vector calculus and partial "
            "differential equations, contextualised in real applications."
        ),
    ),
    "Numerical Analysis.html": dict(
        title="Numerical Analysis",
        programme="MSc",
        credit="",
        summary=(
            "The mathematics and statistics underpinning data science and "
            "artificial intelligence, and the ability to critically evaluate and "
            "present a statistical analysis to a diverse audience."
        ),
    ),
    "Practical modern statistics.html": dict(
        title="Practical modern statistics",
        programme="BSc (Hons)",
        credit="30 credits",
        summary=(
            "Applied statistical modelling with SPSS and WinBUGS: time series, "
            "multivariate methods and Bayesian statistics, using real datasets "
            "including cohort and case-control studies and meta-analysis."
        ),
    ),
    "Research Methods and Professional Practice.html": dict(
        title="Research Methods and Professional Practice",
        programme="MSc",
        credit="",
        summary=(
            "How research is planned, executed and communicated professionally: "
            "the scientific method and research ethics, literature review and "
            "research questions, methodology, interviews and survey design, "
            "quantitative and inferential methods &mdash; culminating in a full "
            "research proposal, presentation and literature review."
        ),
    ),
    "The Data Professional.html": dict(
        title="The Data Professional",
        programme="MSc",
        credit="",
        summary=(
            "Data science as a profession: data collection through to decision "
            "support, large-scale dataset management, competing data analytics "
            "approaches, and the legal, ethical, social and professional "
            "responsibilities that come with them."
        ),
    ),
    "Visualising Data.html": dict(
        title="Visualising Data",
        programme="MSc",
        credit="",
        summary=(
            "Visualisation from principles to delivery: website comparison and "
            "peer review, an R refresher and exploratory data analysis, a "
            "programming project, a Grafana dashboard, Tableau work and a final "
            "ticket-team dashboard manual."
        ),
    ),
}

MODULE_ORDER = sorted(
    MODULES, key=lambda k: (0 if MODULES[k]["programme"] == "MSc" else 1, MODULES[k]["title"].lower())
)

STRUCTURAL_PAGES = {
    "Masters.html": dict(
        title="MSc Data Science",
        eyebrow="University of Essex Online",
        logo="images/University_of_Essex_logo.jpg",
        logo_alt="University of Essex logo",
        summary=(
            "My MSc in Data Science with the University of Essex Online: "
            "reflective e-portfolios from each module, the research and literature "
            "review work behind them, and my MSc Computing Project."
        ),
    ),
    "Honours.html": dict(
        title="BSc (Hons) Data Science",
        eyebrow="The Open University",
        logo="images/the-open-university.jpg",
        logo_alt="The Open University logo",
        summary=(
            "The twelve 30-credit modules of my BSc (Hons) Data Science with The "
            "Open University, and the foundations they gave me in statistics, "
            "mathematics, computing and machine learning."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Artefacts: kind, the module page they belong to, and a description derived
# from the artefact's own first page.
# ---------------------------------------------------------------------------

ARTEFACTS = {
    "assets/Literature Review Machine Learning for Churn Prediction at Cartrack.pdf": dict(
        kind="PDF", pages=13,
        title="Literature Review: Machine Learning for Churn Prediction in Telematics for Cartrack",
        module="Research Methods and Professional Practice.html",
        desc=(
            "A 13-page literature review on machine learning approaches to churn "
            "prediction in telematics for Cartrack, with introduction, scope, "
            "research questions, method and findings."
        ),
    ),
    "assets/Unit 12 - Final Project.pdf": dict(
        kind="PDF", pages=20,
        title="Unit 12 &mdash; Final Project: Ticket Team Dashboard Manual",
        module="Visualising Data.html",
        desc=(
            "A 20-page dashboard manual for a ticket-team reporting dashboard, "
            "including the manual purpose, case studies and dashboard design."
        ),
    ),
    "assets/Research Proposal Presentation Transcript.pdf": dict(
        kind="PDF", pages=6,
        title="Research Proposal Presentation Transcript",
        module="Research Methods and Professional Practice.html",
        desc=(
            "The spoken transcript of the research proposal presentation on "
            "predicting Formula 1 qualifying order and race outcomes."
        ),
    ),
    "assets/Research Proposal Presentation Outline.pdf": dict(
        kind="PDF", pages=3,
        title="Research Proposal Presentation Outline",
        module="Research Methods and Professional Practice.html",
        desc=(
            "The slide outline for the same Formula 1 research proposal "
            "presentation: introduction, objectives, method and plan."
        ),
    ),
    "assets/F1 Masters presentation.pdf": dict(
        kind="PDF", pages=23,
        title="F1 Masters Presentation: Predicting Formula 1 Qualifying Order and Race Outcomes",
        module="Research Methods and Professional Practice.html",
        desc=(
            "The 23-slide presentation of the research proposal on predicting "
            "Formula 1 qualifying order and race outcomes."
        ),
    ),
    "assets/Data Collection Outline.pdf": dict(
        kind="PDF", pages=1,
        title="Data Collection Outline",
        module="Research Methods and Professional Practice.html",
        desc=(
            "A one-page outline of the data collection tool and process for "
            "machine learning churn prediction across B2B and B2C customers, "
            "using Python alongside PostgreSQL and covering subscription, usage, "
            "device health and repair-history variables."
        ),
    ),
    "assets/Literature review outline.pdf": dict(
        kind="PDF", pages=3,
        title="Literature Review Outline (2019&ndash;2025)",
        module="Research Methods and Professional Practice.html",
        desc=(
            "The structural outline of the churn-prediction literature review, "
            "setting out introduction and scope, a PRISMA-based method, and the "
            "organisational rationale."
        ),
    ),
    "assets/Literature Review Plan.pdf": dict(
        kind="PDF", pages=3,
        title="Literature Review Plan",
        module="Research Methods and Professional Practice.html",
        desc=(
            "The planning document for the review: focus and aim, audience, "
            "scope across B2B and B2C clients and the search approach."
        ),
    ),
    "assets/Literature review preperation.pdf": dict(
        kind="PDF", pages=2,
        title="Literature Review Preparation",
        module="Research Methods and Professional Practice.html",
        desc=(
            "Preparation notes on methods, data collection and skills for the "
            "research project, justifying a quantitative/predictive machine "
            "learning approach."
        ),
    ),
    "assets/Collab discussion 1.pdf": dict(
        kind="PDF", pages=5,
        title="Collaborative Discussion 1 &mdash; Professional Ethics",
        module="Research Methods and Professional Practice.html",
        desc=(
            "Initial post and contributions examining an ACM case study on "
            "manipulative interface design and the professional and ethical "
            "questions it raises."
        ),
    ),
    "assets/Charts Worksheet.xlsx": dict(
        kind="XLSX", pages=None,
        title="Charts Worksheet",
        module="Research Methods and Professional Practice.html",
        desc=(
            "A three-sheet Excel workbook of chart-construction exercises "
            "(area, brand and frequency data) used in the quantitative strand of "
            "the module."
        ),
    ),
    "assets/e-Portfolio Activity Hypothesis Testing Worksheet.xlsx": dict(
        kind="XLSX", pages=None,
        title="e-Portfolio Activity: Hypothesis Testing Worksheet",
        module="Research Methods and Professional Practice.html",
        desc=(
            "Hypothesis-testing worksheet with a preparation sheet and worked "
            "units 7.1&ndash;7.5, using Excel&rsquo;s Analysis ToolPak."
        ),
    ),
    "assets/e-Portfolio Activity Summary Measures Worksheet.xlsx": dict(
        kind="XLSX", pages=None,
        title="e-Portfolio Activity: Summary Measures Worksheet",
        module="Research Methods and Professional Practice.html",
        desc=(
            "Summary-measures worksheet with a preparation sheet and worked units "
            "6.1&ndash;6.3, using Excel&rsquo;s Analysis ToolPak."
        ),
    ),
    "assets/Unit 1 - Colab discussion.pdf": dict(
        kind="PDF", pages=5,
        title="Unit 1&ndash;3 Collaborative Discussion: The 4th Industrial Revolution",
        module="Machine Learning.html",
        desc=(
            "A collaborative discussion analysing a specific information-system "
            "failure and its consequences for customers, cost and reputation, "
            "produced in Google Colab."
        ),
    ),
    "assets/Unit 1 - Colab discussion.docx": dict(
        kind="DOCX", pages=None,
        title="Unit 1&ndash;3 Collaborative Discussion: The 4th Industrial Revolution (Word version)",
        module="Machine Learning.html",
        desc=(
            "The Word version of the same Unit 1&ndash;3 collaborative discussion "
            "on information-system failure and the 4th Industrial Revolution."
        ),
    ),
    "assets/Unit 11 Slide Final.pdf": dict(
        kind="PDF", pages=15,
        title="Unit 11 Slide Deck: Enhancing Karooooo&rsquo;s AI Dashcams with Convolutional Neural Networks",
        module="Machine Learning.html",
        desc=(
            "A 15-slide executive presentation proposing convolutional neural "
            "network enhancements to AI dashcams, delivered as a research project."
        ),
    ),
    "assets/Unit 11 Transcript.pdf": dict(
        kind="PDF", pages=5,
        title="Unit 11 Transcript: Enhancing Karooooo&rsquo;s AI Dashcams with CNNs",
        module="Machine Learning.html",
        desc=(
            "The presentation transcript for the dashcam CNN research project, "
            "setting out the problem, proposed approach and expected value."
        ),
    ),
    "assets/Group TM3 - Business Analysis Report.pdf": dict(
        kind="PDF", pages=17,
        title="Group TM3 &mdash; Business Analysis Report: Balancing Tourism Flows with KNN",
        module="Machine Learning.html",
        desc=(
            "A 17-page group report building a neighbourhood busyness-score "
            "recommender with k-nearest neighbours to address overtourism in "
            "major urban centres."
        ),
    ),
    "assets/Unit 1-3 Collaborative Discussion 1.pdf": dict(
        kind="PDF", pages=2,
        title="Collaborative Discussion 1 &mdash; The Data Collection Process",
        module="Deciphering Big Data.html",
        desc=(
            "Initial post evaluating the role of the Internet of Things in "
            "big-data architectures for continuous data collection and analysis."
        ),
    ),
    "assets/Unit 6 - Project Report Database Design for Ride-Hailing Company.pdf": dict(
        kind="PDF", pages=8,
        title="Unit 6 &mdash; Project Report: Database Design for a Ride-Hailing Company",
        module="Deciphering Big Data.html",
        desc=(
            "A project report presenting the logical database design for a "
            "ride-hailing company, covering requirements, schema and the case "
            "for a scalable database management system."
        ),
    ),
    "assets/Unit 11 - Individual Project Executive Summary.pdf": dict(
        kind="PDF", pages=9,
        title="Unit 11 &mdash; Individual Project Executive Summary",
        module="Deciphering Big Data.html",
        desc=(
            "Executive summary of the logical database design and implementation "
            "for a ride-hailing company."
        ),
    ),
    "assets/Unit 9 - Dashboard Design Draft.pdf": dict(
        kind="PDF", pages=2,
        title="Unit 9 &mdash; Dashboard Design Draft",
        module="Visualising Data.html",
        desc=(
            "A dashboard design draft addressing the lack of a visual overview "
            "of a business ticket system used by customer support and internal "
            "IT support."
        ),
    ),
    "assets/Unit 8 - Report.pdf": dict(
        kind="PDF", pages=13,
        title="Unit 8 &mdash; Programming Exercise Report",
        module="Visualising Data.html",
        desc=(
            "A 13-page programming exercise report covering exploratory data "
            "analysis, data cleaning and reporting."
        ),
    ),
    "assets/Unit 4 - Summary Post.pdf": dict(
        kind="PDF", pages=1,
        title="Unit 4 &mdash; Summary Post",
        module="Visualising Data.html",
        desc=(
            "A summary post refining an earlier website comparison in response "
            "to peer feedback and further reading."
        ),
    ),
    "assets/Unit 2 - Collab Discussion.pdf": dict(
        kind="PDF", pages=2,
        title="Unit 2 &mdash; Collaborative Discussion: Website Comparison",
        module="Visualising Data.html",
        desc=(
            "A structured comparison of two airline booking websites, examining "
            "the attributes a viewer looks for, location, dates, price and trip "
            "types."
        ),
    ),
    "assets/The data Prof - Data Analytics Report.pdf": dict(
        kind="PDF", pages=5,
        title="The Data Professional &mdash; Data Analytics Report",
        module="The Data Professional.html",
        desc=(
            "A data analytics report on a national transport survey, written to "
            "give executives the evidence to improve public transport."
        ),
    ),
    "assets/The Data Prof - EOMA.pdf": dict(
        kind="PDF", pages=16,
        title="The Data Professional &mdash; End of Module Assignment: Data Analytics Implementation",
        module="The Data Professional.html",
        desc=(
            "A 16-page end-of-module assignment undertaking an analysis of a "
            "national transport survey dataset and reporting the results."
        ),
    ),
    "assets/Collab Disc 1.pdf": dict(
        kind="PDF", pages=3,
        title="Collaborative Learning Discussion 1",
        module="The Data Professional.html",
        desc=(
            "A collaborative discussion on the convergence of data, artificial "
            "intelligence, cloud, blockchain, IoT and cybersecurity."
        ),
    ),
    "assets/The Data Professional - Collaborative Discussion 2.pdf": dict(
        kind="PDF", pages=3,
        title="Collaborative Learning Discussion 2 &mdash; Data Protection",
        module="The Data Professional.html",
        desc=(
            "A discussion reviewing a data-protection regulation and its "
            "implications for how an organisation manages its IT estate."
        ),
    ),
}

# Byte-identical duplicate copies of three artefacts that also exist at the
# site root in the canonical snapshot; retained and linked so nothing is
# referenced-nowhere. Each is byte-identical to its assets/ counterpart.
ROOT_DUPLICATES = {
    "Literature Review Machine Learning for Churn Prediction at Cartrack.pdf": dict(
        kind="PDF",
        title="Literature Review: Machine Learning for Churn Prediction at Cartrack",
        desc="Byte-identical to the copy under assets/ linked above.",
    ),
    "e-Portfolio Activity Hypothesis Testing Worksheet.xlsx": dict(
        kind="XLSX",
        title="e-Portfolio Activity: Hypothesis Testing Worksheet",
        desc="Byte-identical to the copy under assets/ linked above.",
    ),
    "e-Portfolio Activity Summary Measures Worksheet.xlsx": dict(
        kind="XLSX",
        title="e-Portfolio Activity: Summary Measures Worksheet",
        desc="Byte-identical to the copy under assets/ linked above.",
    ),
}


def _load_site_summaries() -> dict:
    """Card summaries are taken verbatim from the supplied programme pages.
    output/evidence/site_module_summaries.json is derived from inputs/ by
    scripts/extract_summaries.py, so no card text is invented."""
    import json
    import os

    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "output", "evidence", "site_module_summaries.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _trim(text: str, limit: int = 240) -> str:
    """Trim to the last complete sentence within `limit`, or the last word."""
    if len(text) <= limit:
        return text
    window = text[:limit]
    cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    if cut < limit * 0.5:
        cut = window.rfind(" ")
    return window[:cut].rstrip(" ,;:") + "&#8230;"


for _path, _info in _load_site_summaries().items():
    if _path in MODULES:
        MODULES[_path]["summary"] = _trim(_info["summary"])
        MODULES[_path]["cover"] = _info["image"]
        MODULES[_path]["cover_alt_site"] = (_info["alt"] or "").strip()


# ---------------------------------------------------------------------------
# Render-time experience computation (mirrors assets/js/experience.js).
#
# The owner's hard rule: never hardcode an experience figure. Everything is
# derived from CAREER_START at render time. The CV PDF is generated offline, so
# it computes its figure here with the same month arithmetic the site uses, and
# the figure advances as calendar time passes with no edit.
# ---------------------------------------------------------------------------
def _months_between(from_ym, to_ym):
    return (to_ym[0] - from_ym[0]) * 12 + (to_ym[1] - from_ym[1])


def years_of_experience(now=None):
    """Whole completed years since CAREER_START. `now` is a datetime.date."""
    from datetime import date
    d = now or date.today()
    elapsed = _months_between(CAREER_START, (d.year, d.month))
    return max(0, elapsed // 12)


def experience_label(now=None):
    """'N+ years' - the phrasing the site and CV render. Always computed."""
    return f"{years_of_experience(now)}+ years"


def msc_completed(now=None):
    """True once the MSc end month (Jun 2026) has been reached."""
    from datetime import date
    d = now or date.today()
    return (d.year, d.month) >= (2026, 6)


def fill_experience(text, now=None):
    """Substitute the experience placeholders with the computed value."""
    label = experience_label(now)
    return (text
            .replace("{experience}", label)
            .replace("{years_html}", label.replace("'", "&rsquo;"))
            .replace("{years}", label))
