#!/usr/bin/env python3
"""Generate the REAL downloadable CV PDF for the rebuilt e-portfolio.

Run OFFLINE, as a one-off authoring step. The delivered site has no build step
and never runs this; it only serves the PDF this produces. The content comes
from scripts/site_content.py, the same single source of truth the cv.html page
uses, so the page and the PDF can never drift apart.

Every statement in the PDF traces to the supplied site (inputs/) or to a
supplied academic artefact. No employer, date, metric, award or credential is
invented, and nothing from the owner's private capability list is published.

    python3 scripts/make_cv_pdf.py
    -> assets/cv/Matthew-Bowyer-CV.pdf
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, KeepTogether,
                                PageTemplate, Paragraph, Spacer)

import site_content as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "cv")
OUT_PDF = os.path.join(OUT_DIR, "Matthew-Bowyer-CV.pdf")

INK = colors.HexColor("#10161d")
BODY = colors.HexColor("#2b3642")
MUTED = colors.HexColor("#667585")
ACCENT = colors.HexColor("#13567f")
LINE = colors.HexColor("#cbd3dc")


def styles() -> dict:
    ss = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "name", parent=ss["Normal"], fontName="Helvetica-Bold",
            fontSize=20, leading=23, textColor=INK, spaceAfter=1),
        "role": ParagraphStyle(
            "role", parent=ss["Normal"], fontName="Helvetica",
            fontSize=11.5, leading=14, textColor=ACCENT, spaceAfter=3),
        "contact": ParagraphStyle(
            "contact", parent=ss["Normal"], fontName="Helvetica",
            fontSize=8.6, leading=12, textColor=MUTED, spaceAfter=2),
        "h2": ParagraphStyle(
            "h2", parent=ss["Normal"], fontName="Helvetica-Bold",
            fontSize=10.5, leading=13, textColor=ACCENT,
            spaceBefore=9, spaceAfter=3),
        "body": ParagraphStyle(
            "body", parent=ss["Normal"], fontName="Helvetica",
            fontSize=9.4, leading=13.2, textColor=BODY, alignment=TA_JUSTIFY),
        "item": ParagraphStyle(
            "item", parent=ss["Normal"], fontName="Helvetica",
            fontSize=9.4, leading=13.2, textColor=BODY),
        "itemhead": ParagraphStyle(
            "itemhead", parent=ss["Normal"], fontName="Helvetica-Bold",
            fontSize=10, leading=13, textColor=INK, spaceBefore=5),
        "meta": ParagraphStyle(
            "meta", parent=ss["Normal"], fontName="Helvetica-Oblique",
            fontSize=8.4, leading=11, textColor=MUTED),
        "note": ParagraphStyle(
            "note", parent=ss["Normal"], fontName="Helvetica-Oblique",
            fontSize=7.8, leading=10.4, textColor=MUTED, spaceBefore=5),
    }


def deco(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(ACCENT)
    canvas.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, stroke=0, fill=1)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 12 * mm,
                      f"{C.SITE_NAME} — Curriculum Vitae")
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build() -> None:
    st = styles()
    os.makedirs(OUT_DIR, exist_ok=True)
    doc = BaseDocTemplate(
        OUT_PDF, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=15 * mm, bottomMargin=18 * mm,
        title=f"{C.SITE_NAME} — Curriculum Vitae",
        author=C.SITE_NAME,
        subject="Curriculum vitae — Analytics and Data Science Manager",
        creator="scripts/make_cv_pdf.py (offline authoring step)",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="cv", frames=[frame], onPage=deco)])

    f = []
    f.append(Paragraph(C.SITE_NAME, st["name"]))
    f.append(Paragraph(C.SITE_ROLE, st["role"]))
    f.append(Paragraph(
        f"{C.EMAIL} &nbsp;|&nbsp; {C.LOCATION} &nbsp;|&nbsp; "
        f"<link href='{C.LINKEDIN_URL}' color='#13567f'>{C.LINKEDIN_URL}</link> "
        f"&nbsp;|&nbsp; <link href='{C.GITHUB_URL}' color='#13567f'>{C.GITHUB_URL}</link>",
        st["contact"]))
    f.append(HRFlowable(width="100%", thickness=0.8, color=LINE,
                        spaceBefore=3, spaceAfter=1))

    f.append(Paragraph("Profile", st["h2"]))
    f.append(Paragraph(C.fill_experience(C.CV_PROFILE), st["body"]))

    f.append(Paragraph("Experience", st["h2"]))
    for e in C.CV_EXPERIENCE:
        f.append(KeepTogether([
            Paragraph(e["role"], st["itemhead"]),
            Paragraph(e["where"], st["meta"]),
            Paragraph(e["body"], st["body"]),
        ]))

    f.append(Paragraph("Leadership &amp; Additional Achievements", st["h2"]))
    for e in C.CV_LEADERSHIP:
        f.append(KeepTogether([
            Paragraph(e["role"], st["itemhead"]),
            Paragraph(e["where"], st["meta"]),
            Paragraph(e["body"], st["body"]),
        ]))

    f.append(Paragraph("Education", st["h2"]))
    for e in C.CV_EDUCATION:
        f.append(KeepTogether([
            Paragraph(e["award"], st["itemhead"]),
            Paragraph(f'{e["where"]} &middot; {e["status"]}', st["meta"]),
            Paragraph(e["body"], st["body"]),
        ]))

    f.append(Paragraph("Core Capabilities", st["h2"]))
    for name, body in C.CV_CAPABILITIES:
        f.append(Paragraph(f"<b>{name}.</b> {body}", st["item"]))

    f.append(Paragraph("Selected projects", st["h2"]))
    for title, desc in C.CV_PROJECTS:
        f.append(Paragraph(f"<b>{title}.</b> {desc}", st["item"]))

    f.append(Paragraph("Selected academic artefacts", st["h2"]))
    f.append(Paragraph(
        "The full academic body of work — module pages and the reports, "
        "literature reviews, presentations, dashboards and statistical "
        "worksheets produced across the programme — is published on the "
        "portfolio site this CV accompanies. Every artefact named below is "
        "reachable from that site's Evidence surface.", st["item"]))
    for t, d in [
        ("Literature review — machine learning for churn prediction in telematics",
         "A 13-page literature review produced for Research Methods and "
         "Professional Practice."),
        ("MSc Computing Project — multimodal driver behaviour evaluation",
         "Dissertation combining telematics data, vision-language models and "
         "large language models."),
        ("Unit 12 — Final Project",
         "A 20-page ticket-team dashboard manual produced for Visualising Data."),
        ("Unit 6 — Database design for a ride-hailing company",
         "A full logical database design and implementation report."),
    ]:
        f.append(Paragraph(f"<b>{t}.</b> {d}", st["item"]))

    f.append(HRFlowable(width="100%", thickness=0.6, color=LINE,
                        spaceBefore=10, spaceAfter=2))
    f.append(Paragraph(
        "Every statement in this CV traces to the supplied portfolio site, the "
        "supplied academic artefacts, or the LinkedIn profile linked above. No "
        "number, employer, date, metric or credential is asserted that those "
        "sources do not evidence.", st["note"]))

    doc.build(f)
    size = os.path.getsize(OUT_PDF)
    print(f"wrote {os.path.relpath(OUT_PDF, ROOT)} ({size} bytes)")


if __name__ == "__main__":
    build()
