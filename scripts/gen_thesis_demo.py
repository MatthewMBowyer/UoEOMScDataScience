#!/usr/bin/env python3
"""Generate thesis-demo.html — the offline, human-readable VLM thesis demo.

Grounded in the owner's PUBLIC thesis repository (read 2026-10-07):
  https://github.com/MatthewMBowyer/Essex_MSC_DataScience_Thesis
  "A Multimodal Driver behavior Evaluation System: Combining Telematics, VLMs
   and LLMs"

What is REAL and traceable to that repo:
  * the UBI-proxy scoring weights (notebook 3, "SCORING WEIGHTS" cell);
  * the telematics-only baseline score vs the telematics+VLM score comparison
    with score_delta / rank_base / rank_vlm / rank_delta / covered_ratio
    (Code and Resources/outputs/final_monthly_rankings_vlm.csv);
  * the VLM change types (confirmed / refined / new_context_added / contradicted
    / not_confirmed / no_vlm_signal) from event_change_audit.csv;
  * the output schema (column names) of the scored/features/ranking CSVs.

What is ILLUSTRATIVE and labelled as such:
  * the three worked scenarios (urban commute, motorway cruise, rural night) are
    representative examples with illustrative frame observations — they are not
    real client records and no model runs when the page is opened.

Fully static and OFFLINE: the data is embedded in assets/js/thesis-demo-data.js,
so the page makes no network request, needs no key and no backend.

Writes:
  - thesis-demo.html
  - assets/js/thesis-demo-data.js
  - output/evidence/vlm_demo_report.json
  - output/evidence/thesis_provenance.json
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

SITE = "https://matthewmbowyer.github.io/UoEOMScDataScience"
THESIS_TITLE = ("A Multimodal Driver Behaviour Evaluation System: Combining Telematics, "
                "VLMs and LLMs")
THESIS_REPO = "https://github.com/MatthewMBowyer/Essex_MSC_DataScience_Thesis"

# The one-sentence problem, before any diagram.
PROBLEM = ("A telematics box can see harsh braking and speeding, but it cannot see "
           "why — a driver who brakes hard to avoid a child looks identical to a "
           "driver who brakes hard because they were distracted. Adding the "
           "camera changes the verdict.")

# --- REAL method facts, traceable to the public repo -------------------------
# Scoring weights: notebook 3 "SCORING WEIGHTS — UBI PROXY SCORE" cell.
UBI_WEIGHTS = [
    ("Harsh manoeuvres (episode-based)", 0.20,
     "Cornering, braking, acceleration — the leading cause of fleet accidents"),
    ("Long speeding episodes (>1 event)", 0.18,
     "Sustained speeding suggests deliberate risk-taking"),
    ("Driver distraction (phone, seatbelt)", 0.13,
     "Phone use and seatbelt non-compliance raise injury severity"),
    ("Short speeding episodes (single event)", 0.12,
     "Isolated speed events — lower severity than sustained speeding"),
    ("Fatigue (eye closed, yawn, fatigue)", 0.12,
     "Fatigue-related crashes are disproportionately fatal"),
    ("Situational risk (headway, lane)", 0.10,
     "Forward-collision and lane-departure indicators"),
    ("Power violations", 0.10,
     "External battery disconnect — tampering or avoidance"),
    ("Camera obstruction", 0.05,
     "Monitoring integrity, not a direct driving behaviour"),
]

# VLM change types: notebook 3 audit + event_change_audit.csv vlm_change_type.
VLM_CHANGE_TYPES = [
    ("confirmed", "The VLM agreed with what the telematics flagged."),
    ("refined", "The VLM agreed AND found additional events — e.g. telematics "
                "said v_phone and the VLM also found SEATBELT_D_OFF."),
    ("new_context_added", "The VLM saw context the telematics had no event for."),
    ("contradicted", "The VLM evidence contradicted the flagged event."),
    ("not_confirmed", "The flagged event could not be confirmed from the camera."),
    ("no_vlm_signal", "No VLM signal was available for the clip."),
]

# Output schema (column names) of the public processed CSVs.
OUTPUT_SCHEMA = {
    "final_monthly_rankings_vlm.csv": [
        "vehicle_id", "window_start", "ubi_proxy_score_base", "ubi_proxy_score_vlm",
        "score_delta", "rank_base", "rank_vlm", "rank_delta",
        "vehicle_behaviour_class_base", "vehicle_behaviour_class_vlm",
        "covered_ratio", "covered_clips", "total_clips"],
    "event_change_audit.csv": [
        "clip", "vehicle_id", "terminal_event_id", "original_event_description",
        "vlm_events_for_pipeline", "vlm_change_type", "change_action",
        "change_reason", "removed_event", "added_event", "event_changed_flag"],
}

# --- REAL ranking rows (final_monthly_rankings_vlm.csv, 2026-01-01 window) ----
# Anonymised vehicle ids exactly as they appear in the public file. These are the
# thesis's own numbers, not invented ones.
REAL_RANKING_ROWS = [
    {"vehicle_id": "429570713", "base": 0.4143, "vlm": 0.3947, "delta": -0.0196,
     "rank_base": 166, "rank_vlm": 205, "rank_delta": -39, "covered_ratio": 1.0,
     "covered_clips": 2, "total_clips": 2},
    {"vehicle_id": "456979367", "base": 0.4756, "vlm": 0.5284, "delta": 0.0529,
     "rank_base": 124, "rank_vlm": 90, "rank_delta": 34, "covered_ratio": 0.083,
     "covered_clips": 1, "total_clips": 12},
    {"vehicle_id": "507451763", "base": 0.5691, "vlm": 0.5231, "delta": -0.046,
     "rank_base": 64, "rank_vlm": 94, "rank_delta": -30, "covered_ratio": 0.03,
     "covered_clips": 1, "total_clips": 33},
]

# --- ILLUSTRATIVE worked scenarios (representative; not real records) ---------
SCENARIOS = [
    {
        "id": "city-stopstart",
        "title": "Urban stop-start commute",
        "meta": "Representative example — dense traffic, frequent idling",
        "telematics": {
            "Harsh braking (per 100 km)": "11.4",
            "Harsh acceleration (per 100 km)": "8.9",
            "Average speed (km/h)": "24",
            "Idle fraction": "31%",
            "Cornering events (per 100 km)": "6.2",
        },
        "vlm": ("The dashcam frame shows a following distance of roughly one car length in "
                "a 40 km/h zone, a pedestrian near the kerb on the left and a wet road surface."),
        "llm": ("Repeated braking in heavy traffic with a short following distance and a "
                "pedestrian close to the carriageway points to a reactive driving pattern. The "
                "principal risk is rear-end collision under braking; a secondary risk is failing "
                "to see a crossing pedestrian in wet conditions."),
        "score_base": 62, "score_vlm": 68, "band": "Elevated",
        "delta_note": ("The camera added a pedestrian-near-kerb observation the telematics had "
                       "no event for, nudging the risk up."),
    },
    {
        "id": "highway-steady",
        "title": "Motorway steady cruise",
        "meta": "Representative example — light traffic, consistent speed",
        "telematics": {
            "Harsh braking (per 100 km)": "1.3",
            "Harsh acceleration (per 100 km)": "0.9",
            "Average speed (km/h)": "101",
            "Idle fraction": "4%",
            "Cornering events (per 100 km)": "0.4",
        },
        "vlm": ("The dashcam frame shows a long clear lane ahead, a following distance of "
                "roughly four car lengths, and dry road under daylight."),
        "llm": ("Smooth longitudinal control with a generous following distance and a clear "
                "lane indicates a low-risk motorway profile. The main residual exposure is "
                "speed-related rather than behavioural."),
        "score_base": 22, "score_vlm": 21, "band": "Low",
        "delta_note": ("The camera confirmed a clean profile and changed nothing material — a "
                       "confirmed change type."),
    },
    {
        "id": "rural-night",
        "title": "Rural road at night",
        "meta": "Representative example — unlit road, poor visibility",
        "telematics": {
            "Harsh braking (per 100 km)": "5.1",
            "Harsh acceleration (per 100 km)": "2.0",
            "Average speed (km/h)": "72",
            "Idle fraction": "2%",
            "Cornering events (per 100 km)": "3.8",
        },
        "vlm": ("The dashcam frame is low-light, showing a single unlit carriageway, no marked "
                "lane edges and a bend ahead without street lighting."),
        "llm": ("Moderate event rates on an unlit road with limited visibility raise the risk "
                "from an unforeseen obstacle or an unmarked bend. Night driving compounds the "
                "behavioural signal captured by the telematics."),
        "score_base": 50, "score_vlm": 54, "band": "Moderate",
        "delta_note": ("The camera confirmed the low-light conditions and added unmarked-bend "
                       "context, refining the risk upward."),
    },
]

# Four stages, each explained as the visitor reaches it.
STAGES = [
    ("telematics", "1. Telematics trace",
     "What went in: the raw event stream from the telematics box. What came out: "
     "counts of harsh manoeuvres, speeding and fatigue events, aggregated into "
     "episodes. What it changed: nothing yet — this is the telematics-only view, "
     "the 'base' score."),
    ("vlm", "2. VLM observation",
     "What went in: anonymised dashcam frames (faces blurred by an InsightFace step). "
     "What came out: a vision-language model's description of what is actually "
     "happening — following distance, pedestrians, lighting, road surface. What it "
     "changed: it can confirm, refine, contradict or add to the telematics events."),
    ("llm", "3. LLM risk narrative",
     "What went in: the combined telematics + VLM signal. What came out: a plain-"
     "language risk narrative. What it changed: it turns the numbers into a reason a "
     "fleet manager can act on."),
    ("score", "4. Risk score (base vs VLM)",
     "What went in: the same scoring weights, applied twice — once to telematics only "
     "(base) and once with the camera evidence folded in (VLM). What came out: two "
     "scores, their delta, and the driver's rank under each. What it changed: this "
     "comparison IS the thesis contribution — you can see the camera move a driver "
     "up or down the fleet ranking."),
]


def main() -> None:
    data = {
        "problem": PROBLEM,
        "thesis_title": THESIS_TITLE,
        "thesis_repo": THESIS_REPO,
        "weights": [{"label": w[0], "weight": w[1], "note": w[2]} for w in UBI_WEIGHTS],
        "change_types": [{"type": t[0], "note": t[1]} for t in VLM_CHANGE_TYPES],
        "output_schema": OUTPUT_SCHEMA,
        "ranking_rows": REAL_RANKING_ROWS,
        "scenarios": SCENARIOS,
        "stages": [{"id": s[0], "title": s[1], "help": s[2]} for s in STAGES],
    }
    data_js = ("window.THESIS_DEMO_DATA = "
               + json.dumps(data, indent=2, ensure_ascii=False) + ";\n")
    with open("assets/js/thesis-demo-data.js", "w", encoding="utf-8") as fh:
        fh.write(data_js)

    scenario_buttons = "\n".join(
        f'''\t\t\t\t\t\t\t<li><button type="button" class="demo-scenario" data-scenario="{s["id"]}" aria-pressed="false">
\t\t\t\t\t\t\t\t<span class="demo-scenario-title">{s["title"]}</span>
\t\t\t\t\t\t\t\t<span class="demo-scenario-meta">{s["meta"]}</span>
\t\t\t\t\t\t\t</button></li>''' for s in SCENARIOS)

    stage_items = "\n".join(
        f'''\t\t\t\t\t\t\t\t<li class="demo-stage" data-stage="{sid}">
\t\t\t\t\t\t\t\t\t<h3>{title}</h3>
\t\t\t\t\t\t\t\t\t<p class="demo-stage-help">{_esc(help_)}</p>
\t\t\t\t\t\t\t\t\t<p class="demo-stage-body demo-stage-placeholder">Select a scenario to reveal this stage.</p>
\t\t\t\t\t\t\t\t</li>''' for sid, title, help_ in STAGES)

    weights_rows = "\n".join(
        f'''\t\t\t\t\t\t\t\t<tr><th scope="row">{_esc(lbl)}</th>
\t\t\t\t\t\t\t\t\t<td class="num">{int(w*100)}%</td>
\t\t\t\t\t\t\t\t\t<td>{_esc(note)}</td></tr>'''
        for lbl, w, note in UBI_WEIGHTS)

    change_rows = "\n".join(
        f'''\t\t\t\t\t\t\t\t<tr><th scope="row"><code>{_esc(t)}</code></th>
\t\t\t\t\t\t\t\t\t<td>{_esc(note)}</td></tr>'''
        for t, note in VLM_CHANGE_TYPES)

    rank_rows = "\n".join(
        f'''\t\t\t\t\t\t\t\t<tr><th scope="row">{r["vehicle_id"]}</th>
\t\t\t\t\t\t\t\t\t<td class="num">{r["base"]:.4f}</td>
\t\t\t\t\t\t\t\t\t<td class="num">{r["vlm"]:.4f}</td>
\t\t\t\t\t\t\t\t\t<td class="num">{r["delta"]:+.4f}</td>
\t\t\t\t\t\t\t\t\t<td class="num">{r["rank_base"]}</td>
\t\t\t\t\t\t\t\t\t<td class="num">{r["rank_vlm"]}</td>
\t\t\t\t\t\t\t\t\t<td class="num">{r["rank_delta"]:+d}</td>
\t\t\t\t\t\t\t\t\t<td class="num">{r["covered_ratio"]*100:.1f}%</td></tr>'''
        for r in REAL_RANKING_ROWS)

    page = f'''<!DOCTYPE HTML>
<!--
\tDopetrope by HTML5 UP
\thtml5up.net | @ajlkn
\tFree for personal and commercial use under the CCA 3.0 license (html5up.net/license)
-->
<html lang="en">
\t<head>
\t\t<meta charset="utf-8" />
\t\t<meta name="viewport" content="width=device-width, initial-scale=1" />
\t\t<title>Thesis Demonstration | Multimodal Driver Behaviour (Telematics + VLM + LLM)</title>
\t\t<meta name="description" content="An offline, precomputed demonstration of Matthew Bowyer's MSc thesis method: a multimodal driver behaviour evaluation system combining telematics traces, vision-language models and large language models. Real scoring weights and a real base-vs-VLM ranking from the public thesis repository; representative scenarios; not live model output." />
\t\t<meta name="keywords" content="Matthew Bowyer, thesis, multimodal driver behaviour, telematics, VLM, LLM, data science" />
\t\t<link rel="canonical" href="{SITE}/thesis-demo.html" />
\t\t<link rel="icon" href="images/favicon.png" type="image/png" />
\t\t<link rel="shortcut icon" href="favicon.ico" />
\t\t<link rel="stylesheet" href="assets/css/main.css" />
\t\t<link rel="stylesheet" href="assets/css/portfolio.css" />
\t\t<meta property="og:type" content="website" />
\t\t<meta property="og:site_name" content="Matthew Bowyer" />
\t\t<meta property="og:title" content="Thesis Demonstration | Multimodal Driver Behaviour" />
\t\t<meta property="og:description" content="An offline, precomputed demonstration of a multimodal driver behaviour evaluation system: telematics + VLM + LLM, with the real base-vs-VLM ranking from the public thesis repository. Representative examples, not live model output." />
\t\t<meta property="og:url" content="{SITE}/thesis-demo.html" />
\t\t<meta property="og:image" content="{SITE}/images/social-card.png" />
\t\t<meta property="og:image:alt" content="Matthew Bowyer - multimodal driver behaviour thesis demonstration" />
\t\t<meta property="og:locale" content="en_GB" />
\t\t<meta name="twitter:card" content="summary_large_image" />
\t\t<meta name="twitter:title" content="Thesis Demonstration | Multimodal Driver Behaviour" />
\t\t<meta name="twitter:description" content="An offline, precomputed demonstration of a multimodal driver behaviour evaluation system: telematics + VLM + LLM. Representative examples, not live model output." />
\t\t<meta name="twitter:image" content="{SITE}/images/social-card.png" />
\t\t<meta name="twitter:image:alt" content="Matthew Bowyer - multimodal driver behaviour thesis demonstration" />
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
\t\t\t\t\t\t<p class="eyebrow">MSc thesis &middot; interactive demonstration</p>
\t\t\t\t\t\t<h1>Multimodal driver behaviour evaluation</h1>
\t\t\t\t\t\t<p class="thesis-problem" id="thesis-problem">{_esc(PROBLEM)}</p>
\t\t\t\t\t\t<p>That is the whole idea behind my MSc thesis, <em>&ldquo;{_esc(THESIS_TITLE)}&rdquo;</em>. The demonstration below walks through how the method works, then lets you run three representative scenarios stage by stage and see the telematics-only score compared with the score once the camera evidence is added. <a href="{THESIS_REPO}" target="_blank" rel="noopener noreferrer">The public thesis repository is here</a>.</p>
\t\t\t\t\t</section>

\t\t\t\t\t<section class="surface" aria-labelledby="demo-how">
\t\t\t\t\t\t<h2 id="demo-how">How the method works, stage by stage</h2>
\t\t\t\t\t\t<p>Each stage below says what went in, what came out, and what it changed about the verdict. Select a scenario further down to reveal the stages with that scenario&rsquo;s data.</p>
\t\t\t\t\t\t<ol class="demo-pipeline" id="demo-pipeline">
{stage_items}
\t\t\t\t\t\t</ol>
\t\t\t\t\t</section>

\t\t\t\t\t<section class="surface" aria-labelledby="demo-compare">
\t\t\t\t\t\t<h2 id="demo-compare">The point: the camera changes the ranking</h2>
\t\t\t\t\t\t<p>Every driver is scored twice with the <strong>same weights</strong> &mdash; once from telematics alone (<code>ubi_proxy_score_base</code>) and once with the camera evidence folded in (<code>ubi_proxy_score_vlm</code>). The difference between them is the thesis contribution. Here are three real rows from the public output file <code>final_monthly_rankings_vlm.csv</code> (January 2026 window):</p>
\t\t\t\t\t\t<div class="table-scroll">
\t\t\t\t\t\t<table class="thesis-table">
\t\t\t\t\t\t\t<caption>Real rows from the public thesis repository. Anonymised vehicle ids exactly as published.</caption>
\t\t\t\t\t\t\t<thead>
\t\t\t\t\t\t\t\t<tr><th scope="col">Vehicle</th><th scope="col">Score&nbsp;(base)</th><th scope="col">Score&nbsp;(VLM)</th><th scope="col">Score&nbsp;delta</th><th scope="col">Rank&nbsp;(base)</th><th scope="col">Rank&nbsp;(VLM)</th><th scope="col">Rank&nbsp;delta</th><th scope="col">Camera&nbsp;coverage</th></tr>
\t\t\t\t\t\t\t</thead>
\t\t\t\t\t\t\t<tbody>
{rank_rows}
\t\t\t\t\t\t\t</tbody>
\t\t\t\t\t\t</table>
\t\t\t\t\t\t</div>
\t\t\t\t\t\t<p class="muted small">Read the top row as: &ldquo;the camera moved this driver <strong>down 39 places</strong> in the fleet ranking.&rdquo; A positive delta means the camera found the driver <em>more</em> at risk than the telematics alone; a negative delta means it found them less at risk. <code>covered_ratio</code> is the share of that driver&rsquo;s clips the camera actually saw &mdash; the first row is fully covered, the others only partly, which is itself part of the story.</p>
\t\t\t\t\t</section>

\t\t\t\t\t<section class="surface" aria-labelledby="demo-weights">
\t\t\t\t\t\t<h2 id="demo-weights">The scoring weights (real, from the public repo)</h2>
\t\t\t\t\t\t<p>These are the actual UBI-proxy weights used in the thesis, taken from the &ldquo;SCORING WEIGHTS&rdquo; cell of notebook 3. They sum to 1.00.</p>
\t\t\t\t\t\t<div class="table-scroll">
\t\t\t\t\t\t<table class="thesis-table">
\t\t\t\t\t\t\t<thead><tr><th scope="col">Behaviour category</th><th scope="col">Weight</th><th scope="col">Why</th></tr></thead>
\t\t\t\t\t\t\t<tbody>
{weights_rows}
\t\t\t\t\t\t\t</tbody>
\t\t\t\t\t\t</table>
\t\t\t\t\t\t</div>
\t\t\t\t\t\t<p>The method also compares a telematics-only score against a telematics+VLM score and carries <code>score_delta</code>, <code>rank_base</code>, <code>rank_vlm</code>, <code>rank_delta</code> and <code>covered_ratio</code> &mdash; exactly the columns shown in the ranking table above.</p>
\t\t\t\t\t</section>

\t\t\t\t\t<section class="surface" aria-labelledby="demo-changes">
\t\t\t\t\t\t<h2 id="demo-changes">What the camera can change</h2>
\t\t\t\t\t\t<p>When the camera evidence is compared with the telematics events, each clip falls into one of these change types (from the thesis&rsquo;s own <code>event_change_audit.csv</code>):</p>
\t\t\t\t\t\t<div class="table-scroll">
\t\t\t\t\t\t<table class="thesis-table">
\t\t\t\t\t\t\t<thead><tr><th scope="col">Change type</th><th scope="col">What it means</th></tr></thead>
\t\t\t\t\t\t\t<tbody>
{change_rows}
\t\t\t\t\t\t\t</tbody>
\t\t\t\t\t\t</table>
\t\t\t\t\t\t</div>
\t\t\t\t\t</section>

\t\t\t\t\t<section class="surface" aria-labelledby="demo-scenarios">
\t\t\t\t\t\t<h2 id="demo-scenarios">Walk through a scenario</h2>
\t\t\t\t\t\t<p>Each scenario is a <strong>representative, precomputed example</strong> &mdash; not a real client record. Selecting one reveals the four stages above in order, with that scenario&rsquo;s data, and shows the base-vs-VLM score change at the end.</p>
\t\t\t\t\t\t<ul class="demo-scenario-picker" id="demo-scenarios-picker">
{scenario_buttons}
\t\t\t\t\t\t</ul>
\t\t\t\t\t</section>

\t\t\t\t\t<section class="callout">
\t\t\t\t\t\t<h2>What this is &mdash; and what it is not</h2>
\t\t\t\t\t\t<div class="demo-label" role="note">
\t\t\t\t\t\t\t<p><strong>What is real.</strong> The scoring weights, the change types and the ranking comparison are taken from my public thesis repository. The ranking rows shown are the thesis&rsquo;s own published numbers.</p>
\t\t\t\t\t\t\t<p><strong>What is illustrative.</strong> The three scenarios are representative examples. The frame observations are illustrative of what a vision-language model reports; they are not real client records.</p>
\t\t\t\t\t\t\t<p><strong>No live models.</strong> This page is a <em>precomputed demonstration</em>: no model runs when you interact with it, no data leaves your browser, and no API key or backend is used. Notebooks 1 and 2 of the thesis ship without stored outputs and need raw dashcam clips that are deliberately not public; notebooks 3 and 4 run from the processed outputs that are public. The real client data behind the underlying work is confidential and is not shown here.</p>
\t\t\t\t\t\t</div>
\t\t\t\t\t\t<p>For the research framing and the literature behind the method, see the <a href="evidence.html">Evidence</a> page and the <a href="projects.html">Projects &amp; Modules</a> index.</p>
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
\t\t<script src="assets/js/thesis-demo-data.js"></script>
\t\t<script src="assets/js/thesis-demo.js"></script>
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
\t\t\t\t\ttoggle.setAttribute('aria-label', open ? 'Close navigation menu' : 'Open navigation menu');
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
\t\t\t\t\t\tslot.innerHTML = '<footer class="site-footer"><div class="wrap"><p>&copy; Matthew Bowyer. All rights reserved. Design: HTML5 UP.</p></div></footer>';
\t\t\t\t\t}});
\t\t\t}});
\t\t</script>
\t</body>
</html>
'''
    with open("thesis-demo.html", "w", encoding="utf-8") as fh:
        fh.write(page)

    # --- provenance + report --------------------------------------------------
    provenance = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thesis_repo": THESIS_REPO,
        "thesis_title": THESIS_TITLE,
        "read_at": "2026-10-07",
        "sources": {
            "weights": {
                "file": "Code and Resources/3. Driver Analysis.ipynb",
                "sha256": "cfdef46dd47433b6a1be10313a6d452f96301400709a8aecf8b76b5d31a537eb",
                "locator": "notebook 3, 'CELL 18 — SCORING WEIGHTS & JUSTIFICATION' cell",
            },
            "ranking_rows": {
                "file": "Code and Resources/outputs/final_monthly_rankings_vlm.csv",
                "sha256": "ebd33db135bd46517434edad1a4e0f85336211aafe7e8bb71db076e1d628a934",
                "locator": "window_start 2026-01-01; rows 429570713 / 456979367 / 507451763",
            },
            "change_types": {
                "file": "Code and Resources/outputs/event_change_audit.csv",
                "sha256": "b75add6ee5e326ef3cc5f332d3673c40b179dbd9fb68c0fbca9f78df2260eaa4",
                "locator": "distinct vlm_change_type values",
            },
        },
        "real": ["scoring weights", "change types", "ranking comparison rows",
                 "output schema"],
        "illustrative": ["three worked scenarios", "frame observations",
                         "the composite base/vlm scenario scores"],
        "no_live_models": True,
    }
    with open("output/evidence/thesis_provenance.json", "w", encoding="utf-8") as fh:
        json.dump(provenance, fh, indent=2)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "page": "thesis-demo.html",
        "offline": True,
        "data_module": "assets/js/thesis-demo-data.js",
        "problem_lead": PROBLEM,
        "scenarios": [s["id"] for s in SCENARIOS],
        "pipeline_stages": [s[0] for s in STAGES],
        "weights": {lbl: w for lbl, w, _ in UBI_WEIGHTS},
        "weights_sum": round(sum(w for _, w, _ in UBI_WEIGHTS), 4),
        "change_types": [t for t, _ in VLM_CHANGE_TYPES],
        "real_ranking_rows": [r["vehicle_id"] for r in REAL_RANKING_ROWS],
        "honest_label_present": "precomputed demonstration" in page.lower(),
        "states_real_vs_illustrative": (
            "What is real." in page and "What is illustrative." in page
            and "No live models." in page),
        "ships_no_driver_imagery": True,
        "imagery_provenance": [
            {"asset": "images/banner.jpg", "provenance": "owner-supplied (original portfolio photograph)"},
            {"asset": "images/social-card.png", "provenance": "generated from the owner's own site assets"},
            {"asset": "assets/css/*, images/favicon.png", "provenance": "HTML5 UP Dopetrope template, CC BY 3.0"},
        ],
    }
    with open("output/evidence/vlm_demo_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("wrote thesis-demo.html; scenarios:", len(SCENARIOS),
          "weights_sum:", report["weights_sum"],
          "honest label:", report["honest_label_present"])


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


if __name__ == "__main__":
    main()
