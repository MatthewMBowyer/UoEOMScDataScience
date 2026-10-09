#!/usr/bin/env python3
"""Print the owner's personal reminder digest as plain text.

Used by `.github/workflows/personal-digest.yml`, which runs it once a day and
emails the output. Also runnable by hand:

    python3 scripts/personal_digest.py
    python3 scripts/personal_digest.py --days 14      # wider window
    python3 scripts/personal_digest.py --today 2026-10-05   # frozen clock (tests)

Why a script and not the page: a static site cannot send email, and the owner
asked for reminders to arrive rather than to be looked up. GitHub Actions is
free for this, so the site stays static and the nagging happens outside it.

Every date comes from `personal/data/*.json`, which records a source for each
one. Nothing is invented here, and anything unverified stays blank.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_personal import d, load, resolve_moving, nice, next_checkin_dates  # noqa: E402


def collect(sports: dict, hubby: dict, today: dt.date, horizon: dt.date):
    """Upcoming sports events and special days inside the window."""
    watch = sports["broadcasters"]

    events = []
    for e in sorted(sports["events"], key=lambda x: x["start"]):
        start, end = d(e["start"]), d(e["end"])
        # Include anything still running, plus anything starting in the window.
        if end < today or start > horizon:
            continue
        events.append((start, end, e, watch[e["broadcaster"]]["name"]))

    days = []
    for h in hubby["fixed_holidays"]:
        for year in (today.year, today.year + 1):
            try:
                when = dt.date(year, h["month"], h["day"])
            except ValueError:
                continue
            if today <= when <= horizon:
                days.append((when, h["name"], h["note"]))
                break
    for b in hubby.get("birthdays", []):
        for year in (today.year, today.year + 1):
            try:
                when = dt.date(year, b["month"], b["day"])
            except ValueError:
                continue
            if today <= when <= horizon:
                days.append((when, b["name"], b["note"]))
                break
    for h in hubby["moving_holidays"]:
        for year in (today.year, today.year + 1):
            when = resolve_moving(h, year)
            if when and today <= when <= horizon:
                days.append((when, h["name"], h["note"]))
                break

    milestones = []
    for m in hubby["milestones"]:
        start = d(m["date"])
        years = today.year - start.year
        anniv = dt.date(start.year + years, start.month, start.day)
        if anniv < today:
            years += 1
            anniv = dt.date(start.year + years, start.month, start.day)
        if today <= anniv <= horizon:
            milestones.append((anniv, m["label"], years))

    return events, sorted(days), sorted(milestones)


def render(sports: dict, hubby: dict, today: dt.date, days: int) -> str:
    horizon = today + dt.timedelta(days=days)
    events, holidays, milestones = collect(sports, hubby, today, horizon)
    tz = hubby["timezone_label"]

    out = [
        f"Your reminders - {today.strftime('%A')} {today.day} {today.strftime('%B %Y')}",
        f"Next {days} days ({tz})",
        "",
    ]

    out.append("SPORT")
    if events:
        for start, end, e, watch in events:
            when = nice(e["start"]) if e["start"] == e["end"] else f"{nice(e['start'])} - {nice(e['end'])}"
            status = "on now" if start <= today <= end else f"in {(start - today).days}d"
            out.append(f"  {when:<28} {e['name']}  [{status}]")
            out.append(f"  {'':<28} {e['series']} | watch: {watch} | {e['supersport_section']}")
        out.append("")
        out.append("  Channel numbers are not shown: none could be verified. Use the TV guide:")
        out.append(f"  {sports['broadcasters']['supersport']['guide']}")
    else:
        out.append("  Nothing in this window.")
    out.append("")

    out.append("SPECIAL DAYS")
    if milestones:
        for when, label, years in milestones:
            out.append(f"  {nice(when.isoformat()):<28} {label} - {years} years  << anniversary")
    for when, name, note in holidays:
        out.append(f"  {nice(when.isoformat()):<28} {name} ({note})")
    if not milestones and not holidays:
        out.append("  Nothing in this window.")
    out.append("")

    # Event-anchored check-in reminders: the next one inside the window, if any.
    ck = hubby.get("checkins")
    if ck:
        out.append(ck["name"].upper())
        checkins = [w for w in next_checkin_dates(today, ck["anchor"]["day_of_month"], n=4)
                    if today <= w <= horizon]
        if checkins:
            prompt = ck["prompts"][0]["text"]
            for when in checkins:
                out.append(f"  {nice(when.isoformat()):<28} {prompt}")
        else:
            out.append("  Nothing in this window.")
        out.append("")

    out.append("--")
    out.append("Sent by the personal reminder job. Sources for every date are in")
    out.append("personal/data/. To stop these, disable the 'personal-digest' workflow.")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10, help="how far ahead to look")
    ap.add_argument("--today", help="freeze the clock (YYYY-MM-DD), for tests")
    ap.add_argument("--subject", action="store_true", help="print the email subject only")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    sports = load("sports.json")
    hubby = load("good_hubby.json")

    if args.subject:
        events, holidays, _ = collect(sports, hubby, today, today + dt.timedelta(days=args.days))
        n = len(events) + len(holidays)
        print(f"Reminders: {n} thing{'s' if n != 1 else ''} in the next {args.days} days")
        return 0

    print(render(sports, hubby, today, args.days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
