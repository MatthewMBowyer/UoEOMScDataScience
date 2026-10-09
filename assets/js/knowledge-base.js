/* knowledge-base.js - the site's grounded fact set.
 *
 * GENERATED FILE - do not edit by hand. Produced at BUILD TIME by
 * scripts/build_knowledge.py (Python, pypdf). Every fact below carries
 * its source (cv | site | repo:<name>). Regenerate with:
 *     python3 scripts/build_knowledge.py
 *
 * The experience figure is NEVER stored here as a literal - it is
 * composed at render time by assets/js/experience.js.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.PortfolioKB = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var FACTS = {
  "capabilities": {
    "Data Science & AI": "Python SQL Machine learning Statistical modelling Predictive & prescriptive analytics Decision science Optimisation Feature engineering & selection Experimentation Hypothesis testing Model validation Tuning Calibration Performance benchmarking GenAI LLMs RAG VLMs",
    "Engineering & Platforms": "Databricks MLflow Spark PySpark Delta Lake Feature Store MLOps ETL/ELT Data pipelines Data modelling Model monitoring & drift Data/model governance Data quality Lineage AWS MySQL Tableau",
    "Leadership & Strategy": "Analytics strategy Data strategy AI/ML capability building Executive decision support Stakeholder management Cross-functional delivery Mentoring"
  },
  "career_start": "Jan 2019",
  "education": [
    {
      "dates": "Jan 2024 - Jun 2026",
      "degree": "MSc Data Science",
      "institution": "University of Essex Online",
      "result": "Merit",
      "source": "cv",
      "thesis": "A Multimodal Driver Behaviour Evaluation System: Combining Telematics, VLMs and LLMs"
    },
    {
      "dates": "Mar 2020 - Jul 2023",
      "degree": "BSc (Hons) Data Science",
      "institution": "The Open University",
      "source": "cv"
    }
  ],
  "email": "matthewmbowyer@gmail.com",
  "github": "https://github.com/MatthewMBowyer",
  "linkedin": "https://www.linkedin.com/in/matthew-bowyer-535a6818a",
  "location": "Gauteng, South Africa",
  "name": "Matthew Bowyer",
  "projects": [
    {
      "description": "Multimodal driver behaviour evaluation combining telematics, VLMs and LLMs.",
      "name": "Essex MSc Data Science Thesis",
      "source": "cv"
    },
    {
      "description": "The University of Essex Online MSc e-portfolio this site presents.",
      "name": "UoEOMScDataScience e-portfolio",
      "source": "site"
    }
  ],
  "repos": [
    {
      "description": "",
      "has_readme": false,
      "language": "CSS",
      "name": "Chloes-Traveling-tutors",
      "private": false,
      "source": "repo:Chloes-Traveling-tutors",
      "url": "https://github.com/MatthewMBowyer/Chloes-Traveling-tutors"
    },
    {
      "description": "This repository contains the code for my MSc Data Science thesis:",
      "has_readme": true,
      "language": "Jupyter Notebook",
      "name": "Essex_MSC_DataScience_Thesis",
      "private": false,
      "source": "repo:Essex_MSC_DataScience_Thesis",
      "url": "https://github.com/MatthewMBowyer/Essex_MSC_DataScience_Thesis"
    },
    {
      "description": "A browser-only tutoring invoice app.",
      "has_readme": true,
      "language": "JavaScript",
      "name": "Invoice_app",
      "private": false,
      "source": "repo:Invoice_app",
      "url": "https://github.com/MatthewMBowyer/Invoice_app"
    },
    {
      "description": "Massively by HTML5 UP",
      "has_readme": true,
      "language": "HTML",
      "name": "PringlePadel",
      "private": false,
      "source": "repo:PringlePadel",
      "url": "https://github.com/MatthewMBowyer/PringlePadel"
    },
    {
      "description": "",
      "has_readme": false,
      "language": "CSS",
      "name": "The-Bowyer-collective",
      "private": false,
      "source": "repo:The-Bowyer-collective",
      "url": "https://github.com/MatthewMBowyer/The-Bowyer-collective"
    },
    {
      "description": "Dopetrope by HTML5 UP",
      "has_readme": true,
      "language": "HTML",
      "name": "UoEOMScDataScience",
      "private": false,
      "source": "repo:UoEOMScDataScience",
      "url": "https://github.com/MatthewMBowyer/UoEOMScDataScience"
    },
    {
      "description": "Include a 1280×640 image, course title in sentence case, and a concise description in emphasis.",
      "has_readme": true,
      "language": "",
      "name": "skills-github-pages",
      "private": false,
      "source": "repo:skills-github-pages",
      "url": "https://github.com/MatthewMBowyer/skills-github-pages"
    },
    {
      "description": "Include a 1280×640 image, course title in sentence case, and a concise description in emphasis.",
      "has_readme": true,
      "language": "",
      "name": "skills-introduction-to-github",
      "private": false,
      "source": "repo:skills-introduction-to-github",
      "url": "https://github.com/MatthewMBowyer/skills-introduction-to-github"
    }
  ],
  "role": "Analytics and Data Science Manager",
  "roles": [
    {
      "dates": "Jun 2024 - Present",
      "employer": "Cartrack",
      "location": "South Africa",
      "source": "cv",
      "title": "Manager: Data Analytics & Global Reporting"
    },
    {
      "dates": "Jan 2024 - May 2024",
      "employer": "Cartrack",
      "location": "South Africa",
      "source": "cv",
      "title": "SIM Usage Analyst"
    },
    {
      "dates": "Mar 2023 - Jan 2024",
      "employer": "Greendoor Group",
      "location": "South Africa",
      "source": "cv",
      "title": "Data Scientist"
    },
    {
      "dates": "Jan 2019 - Feb 2023",
      "employer": "Smith Yong and Associates",
      "location": "Gauteng, South Africa",
      "source": "cv",
      "title": "Data Analyst"
    },
    {
      "dates": "Feb 2025 - Present",
      "employer": "Gauteng Weightlifting Association",
      "location": "",
      "source": "cv",
      "title": "Vice Chairman & Athlete Representative"
    },
    {
      "dates": "Jul 2023 - Feb 2025",
      "employer": "Gauteng Weightlifting Association",
      "location": "",
      "source": "cv",
      "title": "Executive Committee Member"
    },
    {
      "dates": "2019",
      "employer": "RLSS Commonwealth Festival of Lifesaving",
      "location": "",
      "source": "cv",
      "title": "South African Presidents Team Representative"
    }
  ],
  "site_pages": [
    "404.html",
    "Algorithms, data structure and computability.html",
    "Analysing data.html",
    "Applied statistical modelling.html",
    "Data Management and analysis.html",
    "Deciphering Big Data.html",
    "Essential mathematics.html",
    "Honours.html",
    "Interactive design and user experience.html",
    "Introduction to computers and technology 1.html",
    "Introduction to computers and technology 2.html",
    "Introduction to statistics.html",
    "Machine Learning and Artificial Intelligence.html",
    "Machine Learning.html",
    "Masters.html",
    "Mathematical methods.html",
    "Numerical Analysis.html",
    "Practical modern statistics.html",
    "Research Methods and Professional Practice.html",
    "The Data Professional.html",
    "Visualising Data.html",
    "about.html",
    "contact.html",
    "cv.html",
    "evidence.html",
    "experience.html",
    "index.html",
    "projects.html",
    "skills.html",
    "thesis-demo.html"
  ],
  "specialisms": [
    "Business intelligence",
    "Automation",
    "Machine learning",
    "Telematics",
    "Applied artificial intelligence"
  ]
};

  // Per-fact provenance (every emitted fact has a source).
  var FACT_SOURCES = {
  "capabilities": "cv",
  "career_start": "cv",
  "education": "cv",
  "email": "site",
  "github": "site",
  "linkedin": "site",
  "location": "cv",
  "name": "cv",
  "projects": "cv+site",
  "repos": "github:MatthewMBowyer",
  "role": "cv",
  "roles": "cv",
  "site_pages": "site",
  "specialisms": "site"
};

  /* Fill {placeholders} in a fact from live facts at render time. The
     experience figure is resolved through experience.js by the bot. */
  function fill(template, ctx) {
    return template.replace(/\{(\w+)\}/g, function (_, key) {
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
