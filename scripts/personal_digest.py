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
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_personal import (d, load, resolve_moving, nice,  # noqa: E402
                            next_checkin_dates, write_research_snapshot)
import follow_research as FR  # noqa: E402


def _github_token() -> str:
    """A token for the run-time quota lookup: the env var, else the gh CLI.

    Actions sets GITHUB_TOKEN; a run on the owner's PC does not. Without one the
    digest said it "could not be determined" about his own repository, which is
    the one number item 8 exists to show. `gh auth token` is the CLI's own
    credential, so nothing new is stored here.
    """
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True,
                             text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _repo_slug() -> str:
    """`owner/name` for the run-time quota lookup, from CI or from git.

    Actions sets GITHUB_REPOSITORY; a run on the owner's PC does not, and the
    digest then said "could not be determined" about its own repository. The
    git remote says the same thing, so it is used as the fallback.
    """
    slug = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if slug:
        return slug
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"github\.com[/:]([^/]+/[^/\s]+?)(?:\.git)?$", url)
    return m.group(1) if m else ""


def collect(sports: dict, hubby: dict, today: dt.date, horizon: dt.date):
    """Upcoming sports events and special days inside the window."""
    watch = sports["broadcasters"]

    # The reminders list is the first thing the owner reads, so it has to obey
    # the same follow rules as the research layer. It did not: a switched-off
    # sport and a deliberately removed series still appeared at the top of the
    # email ("World Rally Championship - Saudi Arabia" sat under "on now" after
    # WRC was removed), which made removal look broken.
    cfg = FR.load_follow()
    muted = FR.muted_sports(cfg)
    removed_ser = FR.removed_series(cfg)

    events = []
    for e in sorted(sports["events"], key=lambda x: x["start"]):
        if e.get("sport") in muted or FR.is_removed_series(e, removed_ser):
            continue
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


def render(sports: dict, hubby: dict, today: dt.date, days: int,
           research: dict | None = None) -> str:
    """The plain-text digest. `research` is optional so the tests can render
    without touching the network; pass None and the block is simply absent."""
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

    # Research: news on what you follow, fixtures, and the tennis top-5 results.
    # Built before this call and passed in, so rendering stays pure and testable.
    if research:
        block = FR.render_text(research)
        if block.strip():
            out.append(block.rstrip())
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
    out.append(TOOL_POINTER_TEXT)
    out.append("Sent by the personal reminder job. Sources for every date are in")
    out.append("personal/data/. To stop these, disable the 'personal-digest' workflow.")
    return "\n".join(out)


def esc(s: str) -> str:
    """Escape for HTML. Every value here comes from the owner's own JSON, but an
    ampersand or angle bracket in an event name would still break the markup."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# Palette mirrors assets/css/portfolio.css so the email matches the site.
INK = "#10161d"
BODY = "#3d4a57"
MUTED = "#556274"
LINE = "#e2e7ed"
CANVAS = "#f4f6f9"
SURFACE = "#ffffff"
ACCENT = "#13567f"
ACCENT_SOFT = "#e8f1f8"
ACCENT_LINE = "#bcd6e8"

FONT = ('-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,'
        '"Helvetica Neue",Arial,sans-serif')


def _pill(text: str, bg: str, fg: str) -> str:
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:999px;'
            f'background:{bg};color:{fg};font-size:11px;font-weight:700;'
            f'letter-spacing:.03em;text-transform:uppercase;white-space:nowrap">'
            f'{esc(text)}</span>')


def _section(title: str, rows: str, empty: str) -> str:
    """One titled block. A table rather than a list: email clients are stuck in 2003.

    `title` is markup, not text - several callers pass &mdash; and &amp; - so it is
    deliberately NOT escaped here. Escaping it printed "Local &amp;mdash; ..." in
    the email.
    """
    return f"""
      <tr><td style="padding:26px 28px 0">
        <div style="font-size:11px;font-weight:700;letter-spacing:.11em;
                    text-transform:uppercase;color:{ACCENT};
                    border-bottom:1px solid {LINE};padding-bottom:8px">{title}</div>
      </td></tr>
      <tr><td style="padding:12px 28px 0">
        {rows if rows else f'<p style="margin:0;color:{MUTED};font-size:14px">{esc(empty)}</p>'}
      </td></tr>"""


def render_html(sports: dict, hubby: dict, today: dt.date, days: int,
                research: dict | None = None) -> str:
    """The same digest as `render()`, as an email-safe HTML alternative."""
    horizon = today + dt.timedelta(days=days)
    events, holidays, milestones = collect(sports, hubby, today, horizon)
    tz = hubby["timezone_label"]
    guide = sports["broadcasters"]["supersport"]["guide"]
    n = len(events) + len(holidays) + len(milestones)

    # Sport
    rows = []
    for start, end, e, watch in events:
        live = start <= today <= end
        # An en dash, as a real character. The entity form was escaped by
        # `esc()` below and reached the reader as the literal text "&ndash;".
        when = (nice(e["start"]) if e["start"] == e["end"]
                else f'{nice(e["start"])} \u2013 {nice(e["end"])}')
        status = ("on now" if live else f'{(start - today).days}d')
        rows.append(f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="border:1px solid {LINE};border-radius:10px;margin:0 0 8px;
                      background:{ACCENT_SOFT if live else SURFACE}">
          <tr><td style="padding:11px 13px">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="font-size:14px;font-weight:600;color:{INK}">{esc(e['name'])}</td>
                <td align="right" style="white-space:nowrap">
                  {_pill(status, ACCENT if live else "#eef1f5", SURFACE if live else MUTED)}
                </td>
              </tr>
            </table>
            <div style="font-size:12px;color:{MUTED};margin-top:3px">{esc(when)}</div>
            <div style="font-size:12px;color:{MUTED};margin-top:3px">
              {esc(e['series'])} &middot; watch {esc(watch)} &middot;
              <a href="{esc(e['supersport_section'])}" style="color:{ACCENT};
                 text-decoration:none">guide</a>
            </div>
          </td></tr>
        </table>""")
    if events:
        rows.append(f'<p style="margin:6px 0 0;font-size:11px;color:{MUTED}">'
                    f'Channel numbers are not shown: none could be verified. '
                    f'<a href="{esc(guide)}" style="color:{ACCENT}">Use the TV guide</a>.</p>')
    sport = _section("Sport", "".join(rows), "Nothing in this window.")

    # Research: news, fixtures and the tennis top-5. Three separate sections so
    # each can be scanned on its own, and so an empty one simply disappears.
    follow = ""
    if research:
        blocks = FR.render_html(research, INK, MUTED, LINE, ACCENT, SURFACE, ACCENT_SOFT)
        for key, title in (
            ("sports", "By sport"),
            ("news", "What you follow"),
            ("fixtures", "Fixtures"),
            ("standings", "Standings"),
            ("tennis", "Tennis"),
            ("suggestions", "Suggested next"),
            ("local", "Local &mdash; Wilgeheuwel &amp; Roodepoort"),
            ("prices", "Price watch &mdash; the parts you listed"),
            ("deals", "Deals &amp; Black Friday"),
            ("timing", "Run time"),
        ):
            if blocks.get(key):
                follow += _section(title, blocks[key], "")

    # Special days
    rows = []
    for when, label, years in milestones:
        rows.append(f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 7px">
          <tr>
            <td style="font-size:13px;color:{MUTED};white-space:nowrap;width:92px">{esc(nice(when.isoformat()))}</td>
            <td style="font-size:14px;color:{INK}">{esc(label)}
              {_pill(f"{years} years", ACCENT_SOFT, ACCENT)}</td>
          </tr>
        </table>""")
    for when, name, note in holidays:
        rows.append(f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 7px">
          <tr>
            <td style="font-size:13px;color:{MUTED};white-space:nowrap;width:92px">{esc(nice(when.isoformat()))}</td>
            <td style="font-size:14px;color:{INK}">{esc(name)}
              <span style="color:{MUTED};font-size:12px"> &mdash; {esc(note)}</span></td>
          </tr>
        </table>""")
    special = _section("Special days", "".join(rows), "Nothing in this window.")

    # Check-in
    ck = hubby.get("checkins")
    checkin = ""
    if ck:
        rows = []
        checkins = [w for w in next_checkin_dates(today, ck["anchor"]["day_of_month"], n=4)
                    if today <= w <= horizon]
        prompt = ck["prompts"][0]["text"]
        for when in checkins:
            rows.append(f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 7px">
          <tr>
            <td style="font-size:13px;color:{MUTED};white-space:nowrap;width:92px">{esc(nice(when.isoformat()))}</td>
            <td style="font-size:14px;color:{INK}">{esc(prompt)}</td>
          </tr>
        </table>""")
        checkin = _section(esc(ck["name"]), "".join(rows), "Nothing in this window.")

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your reminders</title></head>
<body style="margin:0;padding:0;background:{CANVAS}">
<!-- Preheader: the line clients show next to the subject. -->
<div style="display:none;font-size:1px;color:{CANVAS}">
  {n} thing{'s' if n != 1 else ''} in the next {days} days.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:{CANVAS};padding:22px 12px">
  <tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="max-width:600px;background:{SURFACE};border:1px solid {LINE};
                  border-radius:14px;font-family:{FONT};
                  -webkit-text-size-adjust:100%">
      <tr><td style="padding:22px 28px 20px;background:{ACCENT};
                     border-radius:13px 13px 0 0">
        <div style="font-size:19px;font-weight:700;color:{SURFACE}">Your reminders</div>
        <div style="font-size:13px;color:{ACCENT_LINE};margin-top:3px">
          {esc(f"{today.strftime('%A')} {today.day} {today.strftime('%B %Y')}")} &middot; next {days} days ({esc(tz)})</div>
        <div style="font-size:13px;color:{SURFACE};margin-top:12px">
          <strong>{n}</strong> thing{'s' if n != 1 else ''} coming up</div>
      </td></tr>
      {sport}
      {follow}
      {special}
      {checkin}
      <tr><td style="padding:26px 28px 24px">
        <div style="border-top:1px solid {LINE};padding-top:14px;
                    font-size:12px;color:{MUTED};line-height:1.5">
          <strong style="color:{INK}">Add or remove a sport:</strong> double-click
          <code style="font-size:11px">MANAGE_SPORTS.bat</code> in the project folder.
          It runs on your own PC - a numbered menu, no commands to type.<br><br>
          Sources for every date are in <code style="font-size:11px">personal/data/</code>.
          To see all of it at once:
          <a href="https://matthewmbowyer.github.io/UoEOMScDataScience/good_hubby.html"
             style="color:{ACCENT}">good_hubby.html</a> &middot;
          <a href="https://matthewmbowyer.github.io/UoEOMScDataScience/sports.html"
             style="color:{ACCENT}">sports.html</a>.<br>
          To stop these emails, disable the <code style="font-size:11px">personal-digest</code> workflow.
        </div>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def _sport_events(sports: dict) -> list[dict]:
    """The owner's events, flattened for the per-sport block and suggestions.

    `sports.json` stores events however the owner wrote them; the research layer
    only needs (sport, name, when), so the shape is normalised here rather than
    in two places.
    """
    out = []
    for e in sports.get("events") or []:
        name = e.get("name") or e.get("title") or ""
        if not name:
            continue
        start = e.get("start") or e.get("date") or ""
        out.append({
            "sport": e.get("sport", ""),
            "name": name,
            "when": start,
            # An event already running started BEFORE today but is still in the
            # window. Carrying the end date is what lets an ongoing championship
            # count as "on now" instead of vanishing on its second day.
            "end": e.get("end") or start,
            # Carried through so the per-sport block can say what the event IS
            # rather than only how many there are.
            "series": e.get("series") or "",
            "description": e.get("description") or "",
            "broadcaster": e.get("broadcaster") or "",
            "channel": e.get("channel") or "",
            "official": e.get("official") or "",
        })
    out.sort(key=lambda e: e["when"])
    return out


# AC-143: one unmissable line naming the tool and saying where it runs. Defined
# once so the text digest and the HTML email cannot drift apart.
TOOL_POINTER_TEXT = (
    "Add or remove a sport: double-click MANAGE_SPORTS.bat in the project folder. "
    "It runs on your own PC - a numbered menu, no commands to type."
)


def subject_line(sports: dict, hubby: dict, today: dt.date, days: int) -> str:
    """The email subject. Counts the calendar only, never the research fetches."""
    events, holidays, _ = collect(sports, hubby, today, today + dt.timedelta(days=days))
    n = len(events) + len(holidays)
    return f"Reminders: {n} thing{'s' if n != 1 else ''} in the next {days} days"


def build(days: int, today: dt.date, weekly: bool, research_enabled: bool = True) -> dict:
    """ONE gather, THREE parts: text, HTML and subject from the same research.

    Two independent renders could disagree about a fact while a heading-parity
    test still passed, so the workflow and the email both consume THIS dict.
    """
    started = time.monotonic()
    sports = load("sports.json")
    hubby = load("good_hubby.json")

    research = None
    if research_enabled:
        try:
            research = FR.gather(
                FR.load_follow(), weekly=weekly, today=today,
                sports_events=_sport_events(sports),
                window_days=days,
                elapsed=time.monotonic() - started,
                repo=_repo_slug(),
                token=_github_token(),
            )
        except Exception as exc:  # noqa: BLE001 - a reminder must still be sent
            print(f"NOTE: research unavailable ({type(exc).__name__}: {exc})", file=sys.stderr)

    return {
        "text": render(sports, hubby, today, days, research),
        "html": render_html(sports, hubby, today, days, research),
        "subject": subject_line(sports, hubby, today, days),
        "research": research,
    }


def write_parts(parts: dict, directory: str) -> list[str]:
    os.makedirs(directory, exist_ok=True)
    written = []
    for name, key in (("digest.txt", "text"), ("digest.html", "html"),
                      ("subject.txt", "subject")):
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(parts[key].rstrip() + "\n")
        written.append(path)
    # The static page renders the SAME gather, so it cannot drift from the email.
    # Written beside the other parts, never into the repo: `--out-dir` is used by
    # the tests and must not mutate the delivered tree.
    if parts.get("research"):
        written.append(write_research_snapshot(
            parts["research"], os.path.join(directory, "research.json")))
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10, help="how far ahead to look")
    ap.add_argument("--today", help="freeze the clock (YYYY-MM-DD), for tests")
    ap.add_argument("--subject", action="store_true", help="print the email subject only")
    ap.add_argument("--html", action="store_true", help="print the HTML email body instead of text")
    ap.add_argument("--out-dir",
                    help="write digest.txt, digest.html and subject.txt from ONE gather")
    ap.add_argument("--weekly", action="store_true",
                    help="widen the news window to a week (used by the weekly job)")
    ap.add_argument("--no-research", action="store_true",
                    help="skip the news/fixtures/tennis fetches (offline, fast)")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    parts = build(args.days, today, args.weekly, research_enabled=not args.no_research)

    if args.out_dir:
        for path in write_parts(parts, args.out_dir):
            print(f"wrote {path}")
        return 0

    if args.subject:
        print(parts["subject"])
        return 0
    if args.html:
        print(parts["html"])
        return 0
    print(parts["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
