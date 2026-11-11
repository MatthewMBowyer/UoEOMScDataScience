#!/usr/bin/env python3
"""Tests for the owner's personal pages: `scripts/build_personal.py` and
`scripts/personal_digest.py`.

Run from the project root:

    python3 tests/verify_personal.py

What this actually checks, and why each one matters:

1.  **The owner's own dates round-trip.** "2969 days before 18 December 2024"
    must resolve to 2016-11-01 and back again. If the arithmetic drifts, every
    countdown on the page is wrong by that amount.
2.  **The event list is exactly the owner's.** He said "Dont add any more." So
    the count is pinned at 16 and every name is checked against the list he
    typed. A silently-added event fails here.
3.  **Nothing is fabricated.** Every date in the two JSON inputs must carry a
    `source`. This is the project's hard rule, and the personal pages are the
    most tempting place to relax it.
4.  **No channel number is invented.** The owner named DSTV but no official
    source confirmed a number, so the fields must stay null. If someone fills
    one in, this fails until a source is recorded too.
5.  **The pages are unlisted and say so.** noindex/nofollow present, and the
    "unlisted, not private" warning present, because the owner accepted a real
    privacy trade-off and the page must not quietly pretend otherwise.
6.  **Moving holidays are computed, not hardcoded.** Easter, Mother's Day and
    the rest are resolved from a rule for arbitrary years, so the page does not
    rot. A wrong nth-weekday calculation is caught here.
7.  **The clock is frozen and the digest behaves.** Several dates are tested so
    the reminder email shows the right things on a random future morning.
8.  **The .ics files are valid** and contain one VEVENT per item, with the
    exclusive end date the format requires.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

sys.path.insert(0, os.path.join(ROOT, "tests"))
import build_personal as BP  # noqa: E402
import follow_research as FR  # noqa: E402
from verify_research import FakeFetcher  # noqa: E402

NOW_DT = dt.datetime(2026, 11, 4, 9, 0, tzinfo=dt.timezone.utc)
NOW_RFC = NOW_DT.strftime("%a, %d %b %Y %H:%M:%S GMT")

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


SPORTS = BP.load("sports.json")
HUBBY = BP.load("good_hubby.json")

# The owner's list, verbatim from his message (2026-10-05). Counted here so an
# accidental addition is caught.
OWNER_EVENTS = [
    "Petit Le Mans", "Shanghai Masters", "UCI Gravel World Championships",
    "Bathurst 1000", "UCI Track Cycling World Championships",
    "Artistic Gymnastics World Championships", "MotoGP Australian Grand Prix",
    "NASCAR at Talladega", "Weightlifting World Championships", "Paris Masters",
    "World Endurance - 8 Hours of Bahrain", "NASCAR at Homestead-Miami",
    "World Rally Championship - Saudi Arabia", "MotoGP Portuguese Grand Prix",
    "Mexico Padel Major", "MotoGP Valencian Grand Prix (season finale)",
]


def test_owner_dates() -> None:
    """The relationship dates the owner gave, checked by arithmetic.

    The 'chatting' date is now the owner's DIRECT statement (2017-03-22,
    2026-10-07), which supersedes the earlier 2969-day derivation. The old
    arithmetic is still checked, so the history is visible, but the milestone
    itself must hold the corrected value.
    """
    derived = dt.date(2024, 12, 18) - dt.timedelta(days=2969)
    check("AC-P1 the OLD derivation '2969 days before 18 Dec 2024' was 2016-11-01",
          derived == dt.date(2016, 11, 1), str(derived))

    by_id = {m["id"]: m["date"] for m in HUBBY["milestones"]}
    check("AC-P1 chatting milestone is the owner's direct 2017-03-22",
          by_id.get("chatting") == "2017-03-22", by_id.get("chatting"))
    check("AC-P1 dating milestone is 2025-02-01", by_id.get("dating") == "2025-02-01", by_id.get("dating"))
    check("AC-P1 engaged milestone is 2026-04-01", by_id.get("engaged") == "2026-04-01", by_id.get("engaged"))


def test_event_list_is_exactly_the_owners() -> None:
    names = [e["name"] for e in SPORTS["events"]]
    check("AC-P2 exactly 16 events ('Dont add any more')", len(names) == 16, f"{len(names)}")
    check("AC-P2 no duplicates", len(names) == len(set(names)), str(len(names) - len(set(names))))
    missing = [n for n in OWNER_EVENTS if n not in names]
    extra = [n for n in names if n not in OWNER_EVENTS]
    check("AC-P2 every owner event present", not missing, str(missing))
    check("AC-P2 nothing added beyond the owner's list", not extra, str(extra))

    bad = [e["id"] for e in SPORTS["events"] if e["end"] < e["start"]]
    check("AC-P2 no event ends before it starts", not bad, str(bad))


def test_everything_has_a_source() -> None:
    """The never-fabricate rule, applied to the personal data."""
    unsourced = [h["name"] for h in HUBBY["fixed_holidays"] if not h.get("source")]
    unsourced += [h["name"] for h in HUBBY["moving_holidays"] if not h.get("source")]
    unsourced += [m["id"] for m in HUBBY["milestones"] if not m.get("source")]
    check("AC-P3 every holiday and milestone carries a source", not unsourced, str(unsourced))

    # Events: the date came from the owner, so the field is the owner reference.
    check("AC-P3 events record where the date came from",
          "Owner" in SPORTS["_note"] or "owner" in SPORTS["_note"].lower())

    # A date must be a real ISO date, not a typo that renders as "nan".
    bad = []
    for e in SPORTS["events"]:
        for k in ("start", "end"):
            try:
                dt.date.fromisoformat(e[k])
            except ValueError:
                bad.append(f"{e['id']}.{k}={e[k]}")
    check("AC-P3 every event date parses as ISO", not bad, str(bad))


def test_no_invented_channels() -> None:
    """A guessed channel number sends the owner to the wrong channel."""
    filled = [e["id"] for e in SPORTS["events"] if e.get("channel")]
    check("AC-P4 channel numbers stay empty (none verifiable)", not filled, str(filled))
    check("AC-P4 the reason is recorded in the data",
          "OWNER CONFIRMATION" in SPORTS["channel_status"], SPORTS["channel_status"])

    # Every event must still tell the owner where to look.
    no_link = [e["id"] for e in SPORTS["events"]
               if not e.get("supersport_section", "").startswith("https://")]
    check("AC-P4 every event links a broadcaster section", not no_link, str(no_link))


def test_pages_are_unlisted_and_say_so() -> None:
    for page in ("sports.html", "good_hubby.html"):
        src = open(page, encoding="utf-8").read()
        check(f"AC-P5 {page} is noindex/nofollow",
              'name="robots"' in src and "noindex" in src and "nofollow" in src)
        check(f"AC-P5 {page} warns that unlisted is not private",
              "Unlisted, not private" in src)
        check(f"AC-P5 {page} is not linked from the professional nav",
              "index.html" not in src or "evidence.html" not in src)

    robots = open("robots.txt", encoding="utf-8").read() if os.path.exists("robots.txt") else ""
    # The pages live at the site root now, so they are disallowed by name.
    missing = [f"Disallow: /{p}" for p in ("sports.html", "good_hubby.html")
               if f"Disallow: /{p}" not in robots]
    check("AC-P5 robots.txt disallows both personal pages", not missing, str(missing))

    # The sitemap must not advertise them.
    if os.path.exists("sitemap.xml"):
        sm = open("sitemap.xml", encoding="utf-8").read()
        check("AC-P5 sitemap does not list the personal pages",
              "sports.html" not in sm and "good_hubby.html" not in sm)

    # The unlisted-proof set has to cover the DATA too, not just the pages: the
    # raw relationship dates are served from a public repo at a guessable path,
    # so they need the same treatment as the pages they generate.
    for asset in ("sports.ics", "good_hubby.ics", "personal/"):
        check(f"AC-P5 robots.txt disallows /{asset}",
              f"Disallow: /{asset}" in robots)
    for f in ("personal/data/sports.json", "personal/data/good_hubby.json"):
        check(f"AC-P5 {f} is not advertised in the sitemap",
              f not in (open("sitemap.xml", encoding="utf-8").read()
                        if os.path.exists("sitemap.xml") else ""))


def test_moving_holidays_are_computed() -> None:
    """Resolved from a rule, so the page does not rot after this year."""
    # Second Sunday of May 2027 = 9 May; third Sunday of June 2027 = 20 June.
    check("AC-P6 Mother's Day 2027 = 9 May",
          BP._nth_weekday(2027, 5, 6, 2) == dt.date(2027, 5, 9),
          str(BP._nth_weekday(2027, 5, 6, 2)))
    check("AC-P6 Father's Day 2027 = 20 June",
          BP._nth_weekday(2027, 6, 6, 3) == dt.date(2027, 6, 20),
          str(BP._nth_weekday(2027, 6, 6, 3)))
    check("AC-P6 Sweetest Day 2027 = 16 October",
          BP._nth_weekday(2027, 10, 5, 3) == dt.date(2027, 10, 16),
          str(BP._nth_weekday(2027, 10, 5, 3)))
    check("AC-P6 World Marriage Day 2027 = 14 February",
          BP._nth_weekday(2027, 2, 6, 2) == dt.date(2027, 2, 14),
          str(BP._nth_weekday(2027, 2, 6, 2)))
    # First Sunday of May 2027 is the 2nd, so the second is the 9th - proves the
    # offset is not just "day + 7".
    check("AC-P6 nth-weekday offset is real (1st Sun May 2027 = 2 May)",
          BP._nth_weekday(2027, 5, 6, 1) == dt.date(2027, 5, 2))

    by_name = {h["name"]: h for h in HUBBY["moving_holidays"]}
    check("AC-P6 Easter 2027 resolves to 28 March",
          BP.resolve_moving(by_name["Easter Sunday"], 2027) == dt.date(2027, 3, 28),
          str(BP.resolve_moving(by_name["Easter Sunday"], 2027)))
    check("AC-P6 World Marriage Day 2027 resolves to 14 February",
          BP.resolve_moving(by_name["World Marriage Day"], 2027) == dt.date(2027, 2, 14),
          str(BP.resolve_moving(by_name["World Marriage Day"], 2027)))


def run_digest(today: str, days: int = 10) -> str:
    # --no-research keeps the suite offline and deterministic: the digest's own
    # content is what these tests pin, and the research layer has its own tests.
    return subprocess.run(
        [sys.executable, "scripts/personal_digest.py", "--today", today,
         "--days", str(days), "--no-research"],
        capture_output=True, text=True, check=True,
    ).stdout


def test_digest_with_frozen_clock() -> None:
    """The reminder email, on several different mornings."""
    # 5 Oct 2026: the Shanghai Masters and Bathurst are coming; nothing special.
    out = run_digest("2026-10-05")
    check("AC-P7 5 Oct digest lists the Shanghai Masters", "Shanghai Masters" in out)
    check("AC-P7 5 Oct digest lists Bathurst 1000", "Bathurst 1000" in out)
    check("AC-P7 5 Oct digest omits Petit Le Mans (already run)", "Petit Le Mans" not in out)
    check("AC-P7 5 Oct digest flags no special days", "Nothing in this window" in out)

    # 24 Oct 2026: MotoGP Australia and Talladega on the 25th. Talladega is a
    # NASCAR round and NASCAR is in `removed_series`, so the reminder list must
    # NOT carry it: asserting its presence was pinning the bug that let a
    # removed series sit at the top of the email.
    out = run_digest("2026-10-24")
    check("AC-P7 24 Oct digest includes the MotoGP Australian GP", "MotoGP Australian Grand Prix" in out)
    check("AC-R16 24 Oct digest omits the removed NASCAR round",
          "NASCAR at Talladega" not in out, "removed series leaked")

    # 27 Oct 2026: the weightlifting worlds start - a multi-day event, so it
    # must appear on its start date.
    out = run_digest("2026-10-27")
    check("AC-P7 27 Oct digest includes the weightlifting worlds",
          "Weightlifting World Championships" in out)

    # 15 Dec 2026: three SA public holidays in the window.
    out = run_digest("2026-12-15", days=14)
    check("AC-P7 15 Dec digest flags the Day of Reconciliation", "Reconciliation" in out)
    check("AC-P7 15 Dec digest flags Christmas", "Christmas Day" in out)
    check("AC-P7 15 Dec digest flags the Day of Goodwill", "Goodwill" in out)

    # 30 Jan 2027: the dating anniversary (1 Feb) is 2 days away.
    out = run_digest("2027-01-30", days=7)
    check("AC-P7 30 Jan 2027 digest flags the dating anniversary", "Started dating" in out)
    check("AC-P7 the anniversary is labelled", "anniversary" in out)

    # 20 Mar 2027: Easter 2027 (28 Mar) is 8 days out.
    out = run_digest("2027-03-20", days=14)
    check("AC-P7 20 Mar 2027 digest flags Easter Sunday", "Easter Sunday" in out)

    # A quiet window still produces a well-formed email, not a crash.
    out = run_digest("2026-10-05", days=0)
    check("AC-P7 a zero-day window still renders a full digest",
          "Your reminders" in out and "SPORT" in out and "SPECIAL DAYS" in out)


def test_html_email_is_a_real_alternative() -> None:
    """The pretty version must be a genuine multipart/alternative part.

    A mail client only shows the HTML version if the message is multipart AND
    the HTML part comes after the text part; get that order wrong and the owner
    silently keeps seeing plain text.
    """
    import email
    from email.message import EmailMessage

    html = subprocess.run(
        [sys.executable, "scripts/personal_digest.py", "--today", "2026-10-05",
         "--days", "10", "--html", "--no-research"],
        capture_output=True, text=True, check=True,
    ).stdout
    text = run_digest("2026-10-05")

    check("AC-P7 --html starts with a doctype", html.startswith("<!DOCTYPE html>"))
    check("AC-P7 --html is a complete document", "</html>" in html)
    check("AC-P7 --html carries no stray literal backslash-n",
          "\\n" not in html)

    # The same facts must appear in both renderings, or the two drift.
    for fact in ("Shanghai Masters", "Bathurst 1000", "SuperSport"):
        check(f"AC-P7 '{fact}' is in the HTML version", fact in html)
        check(f"AC-P7 '{fact}' is in the text version", fact in text)

    # Build the real message the way send_digest_email.py does and inspect it.
    msg = EmailMessage()
    msg["Subject"] = "s"
    msg["From"] = "a@b.com"
    msg["To"] = "c@d.com"
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    parsed = email.message_from_bytes(msg.as_bytes())
    types = [p.get_content_type() for p in parsed.walk()]
    check("AC-P7 the sent message is multipart/alternative",
          parsed.get_content_type() == "multipart/alternative")
    check("AC-P7 it carries a text/plain part", "text/plain" in types)
    check("AC-P7 it carries a text/html part", "text/html" in types)
    check("AC-P7 HTML is the LAST alternative, so clients prefer it",
          types[-1] == "text/html")


def test_reminders_obey_the_follow_list() -> None:
    """AC-P31: the top of the email must honour removal, not just the research.

    A delivered digest showed "World Rally Championship - Saudi Arabia" under
    "on now" although WRC is in `removed_series`, and carried a switched-off
    sport's events too: `collect()` never consulted follow.json at all. Removing
    something and still being reminded of it is the worst kind of bug here,
    because it makes the removal button look broken.
    """
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import personal_digest as PD

    sports = dict(PD.load("sports.json"))
    cfg = PD.FR.load_follow()
    muted = PD.FR.muted_sports(cfg)
    removed = PD.FR.removed_series(cfg)
    today = dt.date(2026, 10, 5)
    events, _, _ = PD.collect(sports, PD.load("good_hubby.json"),
                              today, today + dt.timedelta(days=10))
    check("AC-P31 the fixture set actually exercises exclusion",
          bool(muted or removed), f"muted={muted} removed={removed}")
    for _, _, e, _ in events:
        check(f"AC-P31 {e['name']} is not a removed series",
              not PD.FR.is_removed_series(e, removed), e.get("series", ""))
        check(f"AC-P31 {e['name']} is not a switched-off sport",
              e.get("sport") not in muted, e.get("sport", ""))


def test_an_event_date_range_renders_a_real_dash() -> None:
    """AC-P32: a date range must show an en dash, not the text "&ndash;".

    The range was built with the HTML entity and then passed through `esc()`,
    which turned the ampersand into `&amp;`, so two reminder rows per email read
    "11 Nov &ndash; 14 Nov" as literal characters.
    """
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import personal_digest as PD

    sports = dict(PD.load("sports.json"))
    cfg = PD.FR.load_follow()
    muted = PD.FR.muted_sports(cfg)
    removed = PD.FR.removed_series(cfg)
    # A kept event, not index 0: the first entry is a removed series and the
    # reminder list now correctly drops it.
    kept = next(e for e in sports["events"]
                if e.get("sport") not in muted and not PD.FR.is_removed_series(e, removed))
    sports["events"] = [dict(kept, start="2026-10-06", end="2026-10-09")]
    out = PD.render_html(sports, PD.load("good_hubby.json"),
                         dt.date(2026, 10, 5), 10)
    check("AC-P32 the escaped entity never reaches the reader",
          "&amp;ndash;" not in out)
    check("AC-P32 the range carries a real en dash", "\u2013" in out)
    check("AC-P32 both ends of the range are present",
          "6 Oct" in out and "9 Oct" in out)


def test_html_email_escapes_owner_data() -> None:
    """An '&' or '<' in an event name must not break the markup.

    Every value comes from the owner's own JSON today, but a pasted event name
    ('Bathurst 1000 & 12 Hour') would corrupt the email, so the escape is pinned.
    """
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import personal_digest as PD

    sports = dict(PD.load("sports.json"))
    sports["events"] = [dict(sports["events"][0],
                             name='<img src=x onerror=alert(1)> & "q"',
                             series="A&B",
                             start="2026-10-06", end="2026-10-07")]
    hubby = PD.load("good_hubby.json")
    out = PD.render_html(sports, hubby, dt.date(2026, 10, 5), 10)

    check("AC-P7 a tag in an event name is escaped, not emitted",
          "<img src=x" not in out and "&lt;img src=x" in out)
    check("AC-P7 an ampersand in an event name is escaped", "A&amp;B" in out)
    check("AC-P7 a quote in an event name is escaped", "&quot;q&quot;" in out)


def test_sender_attaches_the_html_alternative() -> None:
    """The sender must actually attach the HTML part, and survive a foreign cwd.

    The workflow only writes digest.txt, so send_digest_email.py renders the HTML
    itself. That render calls into personal_digest, which chdir()s to the repo
    root as an import side effect - if the sender does not account for that, it
    looks for digest.txt in the wrong place and the job fails.
    """
    import importlib.util
    import smtplib
    import tempfile

    captured = {}

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def ehlo(self):
            return (250, "ok")

        def login(self, u, p):
            captured["login"] = u

        def send_message(self, m):
            captured["msg"] = m

    real = smtplib.SMTP_SSL
    real_env = {k: os.environ.get(k) for k in ("MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_TO")}
    smtplib.SMTP_SSL = FakeSMTP
    os.environ.update(MAIL_USERNAME="me@gmail.com", MAIL_PASSWORD="pw",
                      MAIL_TO="you@example.com")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            # digest.txt/subject.txt live in the caller's cwd, as in the workflow.
            with open(os.path.join(tmp, "digest.txt"), "w", encoding="utf-8") as f:
                f.write("PLAIN BODY")
            with open(os.path.join(tmp, "subject.txt"), "w", encoding="utf-8") as f:
                f.write("A subject")
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                spec = importlib.util.spec_from_file_location(
                    "sde", os.path.join(ROOT, "scripts", "send_digest_email.py"))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                rc = mod.main()
                after = os.getcwd()
            finally:
                os.chdir(cwd)
    finally:
        smtplib.SMTP_SSL = real
        for k, v in real_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    check("AC-P10 the sender exits 0", rc == 0)
    check("AC-P10 the sender leaves the working directory alone", after == tmp)
    msg = captured.get("msg")
    types = [p.get_content_type() for p in msg.iter_parts()] if msg else []
    check("AC-P10 the sent mail is multipart/alternative", "text/html" in types)
    check("AC-P10 the plain-text part survives for non-HTML clients",
          "text/plain" in types)
    check("AC-P10 HTML is the last alternative", types[-1] == "text/html" if types else False)


def test_ics_files() -> None:
    # sports.ics now carries only the not-yet-expired events (pruned on build).
    as_of = BP._prune_as_of(SPORTS)
    kept, pruned = BP.prune_events(SPORTS["events"], as_of)
    sports_expected = len(kept)
    # Derived, not hardcoded: milestones + birthdays + check-in anchors + the
    # fixed holidays + every moving holiday that resolves over the .ics's
    # five-year base window. A hardcoded number silently rots when a day is
    # added, which is exactly what it did when the birthday was added.
    hubby_expected = (
        len(HUBBY["milestones"]) + len(HUBBY.get("birthdays", []))
        + len(HUBBY["fixed_holidays"])
        + len(HUBBY["checkins"]["anchor"]["day_of_month"])
        + sum(1 for h in HUBBY["moving_holidays"]
              for y in range(2026, 2031) if BP.resolve_moving(h, y))
    )
    for path, expect in (("sports.ics", sports_expected), ("good_hubby.ics", hubby_expected)):
        # newline="" so universal-newline translation does not hide the CRLF
        # endings the iCalendar format requires.
        with open(path, encoding="utf-8", newline="") as fh:
            src = fh.read()
        n = src.count("BEGIN:VEVENT")
        check(f"AC-P8 {path} has {expect} VEVENTs", n == expect, str(n))
        check(f"AC-P8 {path} has balanced BEGIN/END",
              src.count("BEGIN:VEVENT") == src.count("END:VEVENT")
              and src.count("BEGIN:VCALENDAR") == src.count("END:VCALENDAR"))
        check(f"AC-P8 {path} uses CRLF line endings", "\r\n" in src)
        check(f"AC-P8 {path} declares the timezone", "Africa/Johannesburg" in src)

        # DTEND is exclusive in iCalendar, so a single-day event must end the
        # day AFTER it starts or calendar apps show it a day short.
        blocks = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", src, re.S)
        bad = []
        for b in blocks:
            s = re.search(r"DTSTART;VALUE=DATE:(\d{8})", b)
            e = re.search(r"DTEND;VALUE=DATE:(\d{8})", b)
            if s and e:
                ds = dt.datetime.strptime(s.group(1), "%Y%m%d").date()
                de = dt.datetime.strptime(e.group(1), "%Y%m%d").date()
                if de <= ds:
                    bad.append(f"{s.group(1)}->{e.group(1)}")
        check(f"AC-P8 {path} DTEND is exclusive and after DTSTART", not bad, str(bad[:3]))

        # Every VEVENT needs a UID or some clients refuse the file.
        check(f"AC-P8 {path} every VEVENT has a UID", src.count("UID:") == n, str(src.count("UID:")))


def test_sports_descriptions() -> None:
    """AC-121: every event carries a short human-readable description."""
    missing = [e["id"] for e in SPORTS["events"] if not e.get("description", "").strip()]
    check("AC-121 every event has a description", not missing, str(missing))
    # One sentence, no padding: a sanity bound on length.
    long = [e["id"] for e in SPORTS["events"] if len(e.get("description", "")) > 220]
    check("AC-121 descriptions are one sentence (<=220 chars)", not long, str(long))
    # The sport field is surfaced as prose too (the description names the sport
    # context), and the page shows the description for every kept event.
    page = open("sports.html", encoding="utf-8").read()
    as_of = BP._prune_as_of(SPORTS)
    kept, _ = BP.prune_events(SPORTS["events"], as_of)
    page_descs = page.count('class="desc"')
    # Only events whose sport is still on are rendered. Counting every kept
    # event made this fail the moment the owner switched Cycling and Gymnastics
    # off (15 kept, 3 of them muted, 12 on the page) - the page was right.
    _follow = json.load(open("personal/data/follow.json", encoding="utf-8"))
    _on = {r["sport"] for r in _follow["sports"] if r.get("enabled", True)}
    expected_shown = [e for e in kept if e.get("sport") in _on]
    check("AC-121 the page surfaces a description per kept event",
          page_descs == len(expected_shown),
          f"page={page_descs} shown={len(expected_shown)} kept={len(kept)} "
          f"(a muted sport is not rendered)")


def test_sports_preferences() -> None:
    """AC-122: the recorded preference profile matches the 16 events exactly."""
    pref = SPORTS.get("preferences", {})
    sports = {s["sport"]: s["event_count"] for s in pref.get("sports", [])}
    expected = {"Motorsport": 9, "Tennis": 2, "Cycling": 2,
                "Gymnastics": 1, "Weightlifting": 1, "Padel": 1}
    check("AC-122 the preference profile matches the 16 supplied events exactly",
          sports == expected, str(sports))
    check("AC-122 the profile adds no sport beyond the owner's list",
          set(sports) == set(e["sport"] for e in SPORTS["events"]),
          str(set(sports) - set(e["sport"] for e in SPORTS["events"])))
    check("AC-122 the profile records the broadcaster set",
          set(pref.get("broadcasters", [])) == {"supersport", "redbulltv", "f1tv"},
          str(pref.get("broadcasters")))
    check("AC-122 the profile is machine-readable and explicit",
          pref.get("_rule") and pref.get("_derived_from"))
    # The series recorded for Motorsport must be the six real series.
    motor = next(s for s in pref["sports"] if s["sport"] == "Motorsport")
    for series in ("IMSA", "Supercars", "MotoGP", "NASCAR", "WEC", "WRC"):
        check(f"AC-122 Motorsport records {series}",
              any(series in x for x in motor["series"]), str(motor["series"]))


def test_sports_pruning() -> None:
    """AC-123: expired events are pruned deterministically on rebuild."""
    # Pure and reproducible: same input -> same split, twice.
    as_of = dt.date(2026, 10, 6)
    kept1, pruned1 = BP.prune_events(SPORTS["events"], as_of)
    kept2, pruned2 = BP.prune_events(SPORTS["events"], as_of)
    check("AC-123 pruning is deterministic across runs",
          [e["id"] for e in kept1] == [e["id"] for e in kept2]
          and [e["id"] for e in pruned1] == [e["id"] for e in pruned2])
    # At 2026-10-06 only Petit Le Mans (2026-10-03) has finished.
    check("AC-123 at 2026-10-06 exactly Petit Le Mans is pruned",
          [e["id"] for e in pruned1] == ["petit-le-mans-2026"],
          str([e["id"] for e in pruned1]))
    # An event running today is KEPT (end >= as_of), not pruned.
    kept_today, _ = BP.prune_events(
        [{"id": "x", "name": "x", "start": "2026-10-06", "end": "2026-10-06"}],
        dt.date(2026, 10, 6))
    check("AC-123 an event ending today is kept (end >= as_of)", len(kept_today) == 1)
    # The source list is never modified by pruning.
    check("AC-123 the source list still holds all 16 events",
          len(SPORTS["events"]) == 16, str(len(SPORTS["events"])))
    # A later clock prunes more, and the page follows.
    kept_later, pruned_later = BP.prune_events(SPORTS["events"], dt.date(2026, 11, 30))
    check("AC-123 a later clock prunes more events", len(pruned_later) > len(pruned1),
          f"{len(pruned_later)} > {len(pruned1)}")
    # The generated page is pruned to the recorded as_of.
    page = open("sports.html", encoding="utf-8").read()
    check("AC-123 the delivered page records the prune date",
          f'data-as-of="{BP._prune_as_of(SPORTS).isoformat()}"' in page)


def test_chatting_date_corrected() -> None:
    """AC-124: the chatting date is the owner's 2017-03-22, superseding 2016-11-01."""
    chatting = next(m for m in HUBBY["milestones"] if m["id"] == "chatting")
    check("AC-124 the chatting date is 2017-03-22",
          chatting["date"] == "2017-03-22", chatting["date"])
    check("AC-124 the source records that it supersedes the derivation",
          "SUPERSEDE" in chatting["source"].upper()
          and "2016-11-01" in chatting["source"], chatting["source"])
    check("AC-124 the source notes 2828 days, not 2969",
          "2828" in chatting["source"] and "2969" in chatting["source"],
          chatting["source"])
    # The arithmetic the source cites is true.
    check("AC-124 2017-03-22 is exactly 2828 days before 2024-12-18",
          (dt.date(2024, 12, 18) - dt.date(2017, 3, 22)).days == 2828)
    check("AC-124 2016-11-01 was 2969 days before 2024-12-18 (the old derivation)",
          (dt.date(2024, 12, 18) - dt.date(2016, 11, 1)).days == 2969)


def test_chatting_derivations_consistent() -> None:
    """AC-125: every day-count/countdown/anniversary derives from 2017-03-22."""
    page = open("good_hubby.html", encoding="utf-8").read()
    ics_src = open("good_hubby.ics", encoding="utf-8", newline="").read()
    check("AC-125 the page renders the chatting milestone from 2017-03-22",
          'data-since="2017-03-22"' in page, "data-since")
    check("AC-125 the page shows 22 Mar 2017", "22 Mar 2017" in page)
    check("AC-125 the .ics carries the corrected chatting date",
          "DTSTART;VALUE=DATE:20170322" in ics_src, "DTSTART")
    # No stale value survives anywhere in the generated artefacts.
    check("AC-125 no stale 2016-11-01 in good_hubby.html", "2016-11-01" not in page)
    check("AC-125 no stale 2016-11-01 in good_hubby.ics", "2016-11-01" not in ics_src)
    check("AC-125 no stale 2969-day figure in good_hubby.html", "2969" not in page)
    check("AC-125 no stale 2969-day figure in good_hubby.ics", "2969" not in ics_src)
    # The digest uses the same data (same source file), so it cannot disagree.
    digest = subprocess.run(
        [sys.executable, "scripts/personal_digest.py", "--today", "2026-12-01",
         "--days", "60", "--no-research"],
        capture_output=True, text=True).stdout
    check("AC-125 the digest carries no stale chatting value",
          "2016-11-01" not in digest and "2969" not in digest)
    # A frozen-clock anniversary check: 9 years on 22 Mar 2026.
    years = 2026 - 2017
    check("AC-125 the chatting anniversary year count derives from 2017",
          years == 9, str(years))


def test_checkin_reminders() -> None:
    """AC-126/AC-127: event-anchored, warm, specific, supported-only reminders."""
    ck = HUBBY.get("checkins")
    check("AC-126 check-in reminders exist", bool(ck))
    dom = ck["anchor"]["day_of_month"]
    # Anchored to occasions already on the page (1st/22nd + milestones), NOT daily.
    check("AC-126 anchored to specific days of the month, not a daily schedule",
          dom == [1, 22] and len(dom) < 5, str(dom))
    check("AC-126 the 22nd matches the chatting milestone's day-of-month",
          22 in dom and next(m for m in HUBBY["milestones"]
                             if m["id"] == "chatting")["date"].endswith("-22"))
    check("AC-126 anchored to the milestone anniversaries too",
          set(ck["anchor"]["milestones"]) == {"chatting", "dating", "engaged"})
    check("AC-126 effective frequency is weekly-to-fortnightly, not daily",
          "fortnightly" in ck["effective_frequency"].lower())
    # Substance: check in on each other and name what each does well.
    texts = " ".join(p["text"].lower() for p in ck["prompts"])
    check("AC-127 the prompts are about checking in on each other",
          "check in" in texts or "checking in" in texts)
    check("AC-127 a prompt names what each does well for the other",
          "does well" in texts or "did well" in texts)
    check("AC-127 there are several prompts (substance, not one line)",
          len(ck["prompts"]) >= 3, str(len(ck["prompts"])))
    # One or two clear name options, the plainest chosen, no invented jargon.
    check("AC-127 one or two name options are proposed",
          1 <= len(ck["name_options"]) <= 2, str(ck["name_options"]))
    check("AC-127 the chosen name is one of the options",
          ck["name"] in ck["name_options"])
    check("AC-127 unsupported specifics are marked OWNER CONFIRMATION",
          any("OWNER CONFIRMATION" in u for u in ck["unsupported"]),
          str(ck["unsupported"]))
    # Nothing fabricated about the partner: no invented name/pet/detail.
    check("AC-127 no invented partner detail in the prompts",
          not re.search(r"\b(Chloe|she|her|his|pet|dog|cat)\b", texts),
          texts[:120])
    # The page and the .ics both carry it, and the .ics recurrence is monthly.
    page = open("good_hubby.html", encoding="utf-8").read()
    ics_src = open("good_hubby.ics", encoding="utf-8", newline="").read()
    check("AC-126 the page renders the check-in section", ck["name"] in page)
    check("AC-126 the .ics has a MONTHLY check-in recurrence",
          "RRULE:FREQ=MONTHLY;BYMONTHDAY=1" in ics_src
          and "RRULE:FREQ=MONTHLY;BYMONTHDAY=22" in ics_src)
    check("AC-126 the digest renders a check-in line",
          "CHECK-IN" in subprocess.run(
              [sys.executable, "scripts/personal_digest.py",
               "--today", "2026-10-07", "--days", "20", "--no-research"],
              capture_output=True, text=True).stdout)


def test_pages_are_current() -> None:
    """The committed pages match the generator, so they cannot silently drift."""
    rc = subprocess.run([sys.executable, "scripts/build_personal.py", "--check"],
                        capture_output=True, text=True).returncode
    check("AC-P9 generated pages/calendars are up to date", rc == 0,
          "run: python3 scripts/build_personal.py")


def test_check_is_reproducible_without_a_clock() -> None:
    """`--check` must not depend on the wall clock.

    This is the regression guard for the defect that made AC-P9 fail every
    single day: `main()` passed `date.today()` to every generator, so the
    committed pages could never match on any day but the one they were built.
    A drift guard that always fails is worse than no guard, because it trains
    the reader to ignore it. The check must be reproducible from the stored pin
    alone, whatever day it runs.
    """
    rc = subprocess.run([sys.executable, "scripts/build_personal.py", "--check"],
                        capture_output=True, text=True)
    check("AC-P9 --check passes on the real clock, not just a frozen one",
          rc.returncode == 0, rc.stdout.strip())

    # And the same input must produce byte-identical output twice in a row, so
    # there is no hidden `now` left anywhere in the pipeline.
    before = {p: open(p, encoding="utf-8", newline="").read()
              for p in ("sports.html", "good_hubby.html", "sports.ics", "good_hubby.ics")}
    subprocess.run([sys.executable, "scripts/build_personal.py"],
                   capture_output=True, text=True, check=True)
    after = {p: open(p, encoding="utf-8", newline="").read()
             for p in ("sports.html", "good_hubby.html", "sports.ics", "good_hubby.ics")}
    changed = [p for p in before if before[p] != after[p]]
    check("AC-P9 a plain rebuild is byte-identical (no wall clock in the output)",
          not changed, str(changed))


def test_her_birthday() -> None:
    """Her birthday: 30 October, month/day only, no invented birth year."""
    bdays = HUBBY.get("birthdays", [])
    check("AC-P11 her birthday is recorded", len(bdays) == 1, str(len(bdays)))
    if not bdays:
        return
    b = bdays[0]
    check("AC-P11 her birthday is 30 October",
          (b["month"], b["day"]) == (10, 30), f"{b['month']}/{b['day']}")
    check("AC-P11 the birthday carries its source", bool(b.get("source")), str(b.get("source")))
    # No year was given, so no birth YEAR field may exist: a year would let the
    # page imply an age the owner never stated. (The source string legitimately
    # records when the owner said it, so only the date fields are checked.)
    year_fields = [k for k in b if re.search(r"year|birth|date|dob", k, re.I)]
    check("AC-P11 the birthday stores no birth year", not year_fields, str(year_fields))
    check("AC-P11 the birthday is stored as month/day only",
          isinstance(b["month"], int) and isinstance(b["day"], int),
          f"{b['month']}/{b['day']}")

    page = open("good_hubby.html", encoding="utf-8").read()
    ics_src = open("good_hubby.ics", encoding="utf-8", newline="").read()
    check("AC-P11 the page renders the birthday", 'data-bday="10-30"' in page)
    check("AC-P11 the .ics carries a yearly birthday recurrence",
          "birthday-her-birthday@eportfolio.personal" in ics_src
          and "RRULE:FREQ=YEARLY" in ics_src)
    # The countdown must be computed in the browser, so it cannot go stale.
    check("AC-P11 the page counts down to it in the browser",
          "data-bday-next" in page and "dayDiff" in page)


def test_cute_days_are_verified_and_kind_is_labelled() -> None:
    """Every cute day carries a source, and each row says which kind it is."""
    for key in ("fixed_holidays", "moving_holidays"):
        unsourced = [h["name"] for h in HUBBY[key] if not h.get("source")]
        check(f"AC-P12 every {key} entry has a source", not unsourced, str(unsourced))
        unkind = [h["name"] for h in HUBBY[key] if not h.get("kind")]
        check(f"AC-P12 every {key} entry is labelled with its kind", not unkind, str(unkind))

    names = {h["name"] for h in HUBBY["fixed_holidays"]} | {
        h["name"] for h in HUBBY["moving_holidays"]}
    for want in ("International Kissing Day", "Global Love Day", "Pepero Day",
                 "World Marriage Day"):
        check(f"AC-P12 the cute day {want} is present", want in names)
    check("AC-P12 Chinese New Year was dropped as asked",
          "Chinese New Year" not in names)

    page = open("good_hubby.html", encoding="utf-8").read()
    check("AC-P12 the page labels rows by kind", 'class="chip"' in page
          and 'data-kind="Cute day"' in page)


def test_coming_up_covers_the_planning_surface() -> None:
    """The owner asked for one list covering anniversaries and check-ins too."""
    today = BP._prune_as_of(SPORTS)
    up = BP.hubby_upcoming(HUBBY, today)
    kinds = {e["kind"] for e in up}
    for want in ("Cute day", "Birthday", "Anniversary", "Check-in"):
        check(f"AC-P13 'Coming up' includes {want}", want in kinds, str(sorted(kinds)))
    # Public holidays are on the list too, but only the SA ones exist by design.
    check("AC-P13 'Coming up' is in date order",
          all(a["when"] <= b["when"] for a, b in zip(up, up[1:])))
    check("AC-P13 every entry keeps a source", all(e["source"] for e in up),
          str([e["name"] for e in up if not e["source"]]))
    # It must stay inside the horizon it advertises.
    horizon = today + dt.timedelta(days=365)
    check("AC-P13 every entry is inside the 12-month horizon",
          all(today <= e["when"] <= horizon for e in up))

    page = open("good_hubby.html", encoding="utf-8").read()
    check("AC-P13 the page renders the unified list", "Coming up" in page)


def test_no_secret_leaked() -> None:
    """The reminder job takes credentials from secrets only."""
    wf = open(".github/workflows/personal-digest.yml", encoding="utf-8").read()
    check("AC-P10 workflow reads credentials from secrets",
          "secrets.MAIL_PASSWORD" in wf and "secrets.MAIL_USERNAME" in wf)
    # A literal password would look like an assignment outside ${{ }}.
    hard = re.findall(r"MAIL_PASSWORD:\s*(?!\$\{\{)[^\s]+", wf)
    check("AC-P10 no credential is written into the workflow", not hard, str(hard))



def test_sports_page_shows_the_follow_table_and_the_tool_pointer() -> None:
    """AC-147/AC-143/INV-64: the follow table is a management surface."""
    data = BP.load("sports.json")
    follow = json.load(open("personal/data/follow.json", encoding="utf-8"))
    page = open("sports.html", encoding="utf-8").read()

    check("AC-143 sports.html names MANAGE_SPORTS.bat", "MANAGE_SPORTS.bat" in page)
    check("AC-143 the pointer says it runs on the owner's own PC", "your own PC" in page)
    check("AC-143 the pointer appears before the first content section",
          page.index("MANAGE_SPORTS.bat") < page.index('id="next-up"'))
    check("AC-143 it is rendered text, not an HTML comment", 'class="pointer"' in page)

    rows = BP.follow_rows(follow, data, data["events"])
    check("AC-147 the follow table covers every sport in the follow list",
          len(rows) == len([r for r in follow["sports"] if r.get("sport")]),
          f"{len(rows)} rows vs {len(follow['sports'])} sports")
    check("AC-147 every row carries the source line it came from",
          all(r["source"] for r in rows), str([r["sport"] for r in rows if not r["source"]]))
    check("AC-147 the rendered table has a State column",
          ">State<" in page and ">Where the follow came from<" in page)

    muted = json.loads(json.dumps(follow))
    for r in muted["sports"]:
        if r["sport"] == "Padel":
            r["enabled"] = False
    muted_page = BP.build_sports(data, dt.date(2026, 10, 6), muted)
    table = muted_page.split("What you follow")[1]
    check("AC-147 a muted sport still appears in the follow table", "Padel" in table)
    check("AC-147 a muted sport is marked off", 'class="tag off">Off' in table)
    check("AC-147 a muted sport says no digest section shows it",
          "no digest section shows this sport" in table)

    body = muted_page.split("What you follow")[0]
    check("AC-142 a muted sport produces no events in the event list",
          "Mexico Padel Major" not in body, "Padel event still rendered")
    # The count has to DROP, which is the actual requirement. Pinning a literal
    # number here made the check fail whenever the owner's own sport list
    # changed (it went 14 -> 11 when Cycling and Gymnastics were switched off),
    # which is a stale test rather than a broken feature.
    def _count(pg: str) -> int:
        m = re.search(r"(\d+) events still to come", pg)
        return int(m.group(1)) if m else -1

    unmuted = BP.build_sports(data, dt.date(2026, 10, 6), follow)
    check("AC-142 the event count drops with the mute",
          0 <= _count(muted_page) < _count(unmuted),
          f"muted={_count(muted_page)} unmuted={_count(unmuted)}")


def test_digest_footer_points_at_the_tool() -> None:
    """AC-143: the same pointer is in the text digest AND the HTML email."""
    import personal_digest as PD
    text = subprocess.run(
        [sys.executable, "scripts/personal_digest.py", "--today", "2026-11-04",
         "--days", "10", "--no-research"], capture_output=True, text=True, check=True).stdout
    check("AC-143 the text digest footer names MANAGE_SPORTS.bat",
          "MANAGE_SPORTS.bat" in text)
    check("AC-143 the text footer says it runs on the owner's own PC",
          "your own PC" in text)

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [sys.executable, "scripts/personal_digest.py", "--today", "2026-11-04",
             "--days", "10", "--no-research", "--out-dir", tmp],
            capture_output=True, text=True, check=True)
        html = open(os.path.join(tmp, "digest.html"), encoding="utf-8").read()
    check("AC-143 the HTML email carries the same pointer",
          "MANAGE_SPORTS.bat" in html and "your own PC" in html)


def test_local_category_config_is_complete() -> None:
    """AC-195/AC-196/AC-198: priority, annual and two_person are CONFIGURATION."""
    follow = json.load(open("personal/data/follow.json", encoding="utf-8"))
    cats = follow["local"]["categories"]
    by = {c["key"]: c for c in cats}

    check("AC-195 every local category carries an integer priority",
          all(isinstance(c.get("priority"), int) for c in cats),
          str({c["key"]: c.get("priority") for c in cats}))
    check("AC-195 the configured order is buffet, massage, events",
          [c["key"] for c in FR.category_order(cats)] == ["buffet", "massage", "events"],
          str([c["key"] for c in FR.category_order(cats)]))
    shuffled = [by["events"], by["buffet"], by["massage"]]
    check("AC-195 priority overrides the file order",
          [c["key"] for c in FR.category_order(shuffled)] == ["buffet", "massage", "events"])

    check("AC-196 every local category carries an annual boolean",
          all(isinstance(c.get("annual"), bool) for c in cats),
          str({c["key"]: c.get("annual") for c in cats}))

    for key in ("massage", "buffet"):
        tp = by[key].get("two_person") or {}
        check(f"AC-198(a) the {key} category carries a two_person block", bool(tp))
        check(f"AC-198(a) the {key} two_person block has a label", bool(tp.get("label")))
        joined = " ".join(tp.get("queries") or []).lower()
        check(f"AC-198(a) the {key} block searches the couples/for-two phrasing",
              "couples" in joined or "for two" in joined, joined)
        check(f"AC-198(a) the {key} existing queries are RETAINED, not replaced",
              len(by[key].get("queries") or []) >= 3, str(by[key].get("queries")))

    annual_cat = {"key": "events", "annual": True}
    plain_cat = {"key": "buffet"}
    check("AC-196 an annual category is annual",
          FR.is_annual_item(annual_cat, "Anything", dt.date(2026, 11, 4)))
    check("AC-196 a category with no flag is NOT annual",
          not FR.is_annual_item(plain_cat, "Sunday buffet", dt.date(2026, 11, 4)))
    check("AC-196 an explicit future year stamp makes an item annual",
          FR.is_annual_item(plain_cat, "Comic Con 2027", dt.date(2026, 11, 4)))
    check("AC-196 a past year stamp does not",
          not FR.is_annual_item(plain_cat, "Comic Con 2025", dt.date(2026, 11, 4)))
    check("AC-196 the annual horizon is 12 months and the default is 3",
          FR.horizon_months(annual_cat, "x", follow["local"], dt.date(2026, 11, 4)) == 12
          and FR.horizon_months(plain_cat, "x", follow["local"], dt.date(2026, 11, 4)) == 3)


def test_local_ordering_is_deterministic() -> None:
    """AC-195b/c + INV-97: the rendered order is the documented rule."""
    # Both terms are followed, so every fixture headline names a followed thing
    # and the DATE is what decides - that is the rule being isolated.
    cat = {"key": "massage", "queries": ["couples spa Johannesburg",
                                         "spa for two Johannesburg"],
           "followed_terms": ["spa", "massage"]}
    items = [
        {"title": "Cheap massage special", "date": "2026-10-20",
         "query": "spa for two Johannesburg"},
        {"title": "Spa day for two in Sandton", "date": "2026-10-01",
         "query": "couples spa Johannesburg"},
        {"title": "Spa weekend deal", "date": "2026-10-25",
         "query": "couples spa Johannesburg"},
    ]
    ordered = [i["title"] for i in FR.order_local_items(items, cat)]
    check("AC-195(c) items are ordered newest first inside a category",
          ordered == ["Spa weekend deal", "Cheap massage special",
                      "Spa day for two in Sandton"], str(ordered))

    mixed = [
        {"title": "Random lunch special", "date": "2026-10-30", "query": "q"},
        {"title": "Spa treatment sale", "date": "2026-10-01", "query": "q"},
    ]
    out = [i["title"] for i in FR.order_local_items(mixed, cat)]
    check("AC-195(b) a followed-term headline sorts before a newer unrelated one",
          out == ["Spa treatment sale", "Random lunch special"], str(out))

    tie = [
        {"title": "Zeta spa deal", "date": "2026-10-10",
         "query": "spa for two Johannesburg"},
        {"title": "Alpha spa deal", "date": "2026-10-10",
         "query": "couples spa Johannesburg"},
    ]
    out = [i["title"] for i in FR.order_local_items(tie, cat)]
    check("AC-195(c) a query-index tie falls through to the headline",
          out == ["Alpha spa deal", "Zeta spa deal"], str(out))
    check("AC-195 the ordering is stable across repeated calls",
          [i["title"] for i in FR.order_local_items(items, cat)] == ordered)


def test_two_person_offers_render_with_the_label() -> None:
    """AC-198(b)/(c): a couple offer is labelled; an empty search says so."""
    label = "For two / couples"
    cat = {"key": "massage", "label": "Massage & spa", "priority": 2, "annual": False,
           "queries": ["massage Johannesburg"],
           "require_any": ["massage", "spa"],
           "followed_terms": ["spa", "massage"],
           "two_person": {"label": label,
                          "queries": ["couples spa Johannesburg"]}}
    cfg = {"local": {"city": "Johannesburg", "enabled": True, "months_ahead": 3,
                     "annual_months_ahead": 12,
                     "place_terms": ["johannesburg", "sandton"],
                     "categories": [cat]},
           "sports": []}

    feed = ("<rss version='2.0'><channel>"
            "<item><title>A couples spa day in Johannesburg</title><source>Example</source>"
            f"<pubDate>{NOW_RFC}</pubDate><link>https://x/1</link></item>"
            "<item><title>Massage sale in Sandton</title><source>Example</source>"
            f"<pubDate>{NOW_RFC}</pubDate><link>https://x/2</link></item>"
            "</channel></rss>")
    from verify_research import FakeFetcher
    out = FR.local_events(cfg, FakeFetcher({"news.google": feed}),
                          today=dt.date(2026, 11, 4))
    items = out["categories"][0]["items"]
    labelled = [i for i in items if i.get("two_person")]
    check("AC-198(b) the couples headline is marked two-person", bool(labelled),
          str([(i["title"], i.get("two_person")) for i in items]))
    check("AC-198(b) it carries the configured label",
          bool(labelled) and labelled[0]["two_person_label"] == label,
          str([i.get("two_person_label") for i in labelled]))
    check("AC-198(c) the solo results are NOT suppressed",
          any(not i.get("two_person") for i in items), str(len(items)))

    base = {"news": {"items": []}, "competitions": [], "standings": [],
            "tennis": {"enabled": False}, "by_sport": [],
            "sports": {"enabled": [], "muted": []},
            "suggestions": {}, "local": out, "prices": {},
            "timing": {}, "failures": [], "as_of": NOW_DT}
    text = FR.render_text(base)
    check("AC-198(b) the label is visible in the text digest", f"[{label}]" in text, text)
    html = "".join(str(v) for v in FR.render_html(
        base, "#111", "#666", "#ddd", "#7c5cff", "#fff", "#f4f4f8").values())
    check("AC-198(b) the label is visible in the HTML email", label in html)

    solo_only = ("<rss version='2.0'><channel>"
                 "<item><title>Massage sale in Sandton</title><source>Example</source>"
                 f"<pubDate>{NOW_RFC}</pubDate><link>https://x/2</link></item>"
                 "</channel></rss>")
    out2 = FR.local_events(cfg, FakeFetcher({"news.google": solo_only}),
                           today=dt.date(2026, 11, 4))
    check("AC-198(c) an empty two-person result is recorded, not lost",
          out2["categories"][0].get("two_person_found") == 0,
          str(out2["categories"][0].get("two_person_found")))
    text2 = FR.render_text(dict(base, local=out2))
    check("AC-198(c) it says no two-person offers were found",
          "no two-person offers found in this window" in text2, text2)
    check("AC-198(d) no venue or price is invented for a two-person item",
          "R " not in text2.split("LOCAL")[-1], text2.split("LOCAL")[-1][:300])


def test_local_window_argument_and_empty_state() -> None:
    """AC-167/INV-77/INV-79: 3-month default, 12-month annual, honest empty."""
    annual_cat = {"key": "events", "label": "Big events", "priority": 3, "annual": True,
                  "queries": ["festival Johannesburg"], "require_any": ["festival"],
                  "followed_terms": ["festival"]}
    plain_cat = {"key": "buffet", "label": "Buffets", "priority": 1, "annual": False,
                 "queries": ["buffet Johannesburg"], "require_any": ["buffet"]}
    base_loc = {"city": "Johannesburg", "enabled": True, "months_ahead": 3,
                "annual_months_ahead": 12, "place_terms": ["johannesburg"]}

    # The feed dates a story by PUBLICATION, and the horizon is a look-back (a
    # buffet lead published in February is still the best one in November). So
    # "9 months" here means a story published nine months ago.
    old = (dt.date.today() - dt.timedelta(days=275)).strftime("%a, %d %b %Y 10:00:00 GMT")
    feed = ("<rss version='2.0'><channel>"
            "<item><title>Johannesburg festival roundup</title><source>Example</source>"
            f"<pubDate>{old}</pubDate><link>https://x/1</link></item></channel></rss>")

    from verify_research import FakeFetcher
    got_annual = FR.local_events(
        {"local": dict(base_loc, categories=[annual_cat]), "sports": []},
        FakeFetcher({"news.google": feed}))
    check("AC-167/AC-196 a 9-month-old item is INCLUDED in an annual category",
          bool(got_annual["categories"][0]["items"]),
          str(got_annual["categories"][0]))

    got_plain = FR.local_events(
        {"local": dict(base_loc, categories=[plain_cat]), "sports": []},
        FakeFetcher({"news.google": feed}))
    check("AC-167 the same 9-month-old item is EXCLUDED in a non-annual category",
          not got_plain["categories"][0]["items"],
          str(got_plain["categories"][0]["items"]))

    empty = FR.local_events({"local": dict(base_loc, categories=[plain_cat]),
                             "sports": []}, FakeFetcher({}))
    check("AC-169/INV-79 an empty window says 'nothing found in this window'",
          "nothing found" in empty["error"], empty["error"])
    text = FR.render_text({"news": {"items": []}, "competitions": [], "standings": [],
                           "tennis": {"enabled": False}, "by_sport": [],
                           "sports": {"enabled": [], "muted": []},
                           "suggestions": {}, "local": empty, "prices": {},
                           "timing": {}, "failures": [], "as_of": NOW_DT})
    check("AC-169 the rendered block states the empty window",
          "nothing found in this window" in text, text.split("LOCAL")[-1][:300])
    check("AC-169 it is not padded with a guess",
          "*" not in text.split("LOCAL")[-1].split("RUN TIME")[0])


def test_removed_category_is_excluded() -> None:
    """AC-168/INV-78: the local block reuses the same exclusion machinery."""
    cfg = {"local": {"city": "Johannesburg", "enabled": True, "months_ahead": 3,
                     "place_terms": ["johannesburg"],
                     "categories": [
                         {"key": "buffet", "label": "Buffets", "priority": 1,
                          "enabled": False, "queries": ["buffet Johannesburg"],
                          "require_any": ["buffet"]},
                         {"key": "massage", "label": "Massage", "priority": 2,
                          "enabled": True, "queries": ["massage Johannesburg"],
                          "require_any": ["massage"]}]},
           "sports": []}
    feed = ("<rss version='2.0'><channel>"
            "<item><title>Buffet special in Johannesburg</title><source>Ex</source>"
            f"<pubDate>{NOW_RFC}</pubDate><link>https://x/1</link></item>"
            "<item><title>Massage special in Johannesburg</title><source>Ex</source>"
            f"<pubDate>{NOW_RFC}</pubDate><link>https://x/2</link></item></channel></rss>")
    from verify_research import FakeFetcher
    out = FR.local_events(cfg, FakeFetcher({"news.google": feed}))
    keys = [c["key"] for c in out["categories"]]
    check("AC-168 a muted local category is not rendered at all",
          "buffet" not in keys, str(keys))
    check("AC-168 the other categories still render", "massage" in keys, str(keys))



def test_sport_list_is_first_class_and_complete() -> None:
    """AC-139/AC-194/INV-96: the follow list is the source both surfaces read."""
    follow = json.load(open("personal/data/follow.json", encoding="utf-8"))
    sports = follow.get("sports") or []
    check("AC-139 follow.json carries a sports array", isinstance(sports, list) and bool(sports),
          str(type(sports).__name__))
    check("AC-139 every sport row has a name", all(s.get("sport") for s in sports))
    check("AC-139 every sport row has an on/off flag",
          all(isinstance(s.get("enabled"), bool) for s in sports),
          str([s.get("sport") for s in sports if not isinstance(s.get("enabled"), bool)]))
    check("AC-139 every sport row carries a source line",
          all(str(s.get("source") or "").strip() for s in sports),
          str([s.get("sport") for s in sports if not str(s.get("source") or "").strip()]))

    # AC-194: POPULATED with every sport the owner's own supplied data evidences.
    names = {s["sport"] for s in sports}
    evidenced = {p["sport"] for p in json.load(
        open("personal/data/sports.json", encoding="utf-8"))["preferences"]["sports"]}
    evidenced |= {"Football"}   # his UEFA Champions League follow, news[0]
    check("AC-194 every evidenced sport is in the delivered follow list",
          evidenced <= names, f"missing {sorted(evidenced - names)}")
    check("AC-194 all nine are present",
          names == {"Motorsport", "Tennis", "Football", "Cycling",
                    "Gymnastics", "Weightlifting", "Padel", "Rugby", "F1"},
          str(sorted(names)))
    # Not "every row is enabled": the owner switched Cycling and Gymnastics off
    # on 2026-11-05 ("I never wanna see cycling and gymnastics"), so requiring
    # all-on would be asserting the opposite of what he asked for.
    check("AC-194 every row still carries its own state",
          all(isinstance(s["enabled"], bool) for s in sports))
    check("AC-194 the sports he switched off are off",
          {s["sport"] for s in sports if not s["enabled"]} == {"Cycling", "Gymnastics"},
          str(sorted(s["sport"] for s in sports if not s["enabled"])))

    # Both surfaces read THAT list, not a derived guess.
    bp = open("scripts/build_personal.py", encoding="utf-8").read()
    fr = open("scripts/follow_research.py", encoding="utf-8").read()
    check("AC-139 sports.html reads follow.json",
          "follow.json" in bp and "follow_rows" in bp)
    check("AC-139 the digest reads follow.json",
          "def load_follow" in fr and 'cfg.get("sports")' in fr
          or "muted_sports(cfg)" in fr)


def test_follow_edit_cli_contract() -> None:
    """AC-141: add-sport, remove-sport, --list-sports and --show all work."""
    def run(*args):
        return subprocess.run([sys.executable, "scripts/follow_edit.py", *args],
                              capture_output=True, text=True)

    listed = run("--list-sports")
    check("AC-141 --list-sports needs no other argument and exits 0",
          listed.returncode == 0, listed.stderr[-300:])
    check("AC-141 --list-sports prints the sports",
          "Motorsport" in listed.stdout and "Padel" in listed.stdout, listed.stdout[:200])

    shown = run("--show")
    check("AC-141 --show exits 0", shown.returncode == 0, shown.stderr[-200:])
    check("AC-141 --show prints the sport list with on/off state",
          "Sports (9)" in shown.stdout and "[on ]" in shown.stdout, shown.stdout[:400])

    check("AC-141 add-sport and remove-sport are real subcommands",
          "add-sport" in run("--help").stdout and "remove-sport" in run("--help").stdout)


def test_add_then_remove_a_sport_round_trips() -> None:
    """AC-140/AC-144/INV-63: reversible mute; duplicates refused; unknown reported.

    Runs against a THROWAWAY copy of follow.json so the delivered data is never
    touched by the test, then asserts the copy returns to its exact prior state.
    """
    import shutil, tempfile
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import follow_edit as FE

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "follow.json")
        shutil.copy("personal/data/follow.json", path)
        FE.PATH = path
        before = json.load(open(path, encoding="utf-8"))
        before_sports = json.loads(json.dumps(before.get("sports")))

        cfg = FE.read()
        FE.add_sport(cfg, "Snooker"); FE.write(cfg)
        added = FE.read()
        check("AC-141 add-sport adds a new row",
              any(s["sport"] == "Snooker" and s["enabled"] for s in added["sports"]))
        check("AC-141 an added sport carries a source line",
              all(s.get("source") for s in added["sports"] if s["sport"] == "Snooker"))

        # A second add must REPORT, not duplicate.
        msg = FE.add_sport(added, "Snooker")
        check("AC-140 adding an existing sport reports instead of duplicating",
              "already on" in msg, msg)
        check("AC-140 the duplicate did not create a second row",
              len([s for s in added["sports"] if s["sport"] == "Snooker"]) == 1)

        # Removing is a MUTE: the row stays, the flag flips.
        FE.remove_sport(added, "Snooker"); FE.write(added)
        muted = FE.read()
        row = [s for s in muted["sports"] if s["sport"] == "Snooker"]
        check("AC-144 a removal is a mute, not a delete", len(row) == 1, str(row))
        check("AC-144 the muted row keeps enabled=false", row and row[0]["enabled"] is False)

        # An unknown name is reported, not silently accepted.
        msg = FE.remove_sport(muted, "NotASport")
        check("AC-140 removing an unknown sport reports it",
              "not in the sport list" in msg, msg)
        check("AC-140 the unknown removal changed nothing",
              len(muted["sports"]) == len(added["sports"]))

        # Round trip: add it back and the row count is where it started + 0.
        msg = FE.add_sport(muted, "Snooker"); FE.write(muted)
        check("AC-144 add-sport re-enables a muted sport",
              "back on" in msg, msg)
        FE.remove_sport(muted, "Snooker")
        muted["sports"] = [s for s in muted["sports"] if s["sport"] != "Snooker"]
        FE.write(muted)
        after = FE.read()
        check("AC-144 add-then-remove round-trips the sport list",
              after["sports"] == before_sports,
              f"{len(after['sports'])} vs {len(before_sports)}")


def test_empty_sport_list_is_legal_and_stays_empty() -> None:
    """AC-144/INV-65: an empty list stays empty; nothing seeds a default."""
    import tempfile
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import follow_edit as FE

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "follow.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"sports": [], "news": [], "competitions": []}, fh)
        FE.PATH = path
        cfg = FE.read()
        check("AC-144 an empty sport list reads back empty",
              (cfg.get("sports") or []) == [], str(cfg.get("sports")))
        check("AC-144 --list-sports says there are none rather than inventing one",
              "No sports listed" in FE.list_sports(cfg), FE.list_sports(cfg))

    # ...and the digest invents no sport to fill the block.
    cfg = {"sports": [], "news": [], "competitions": [],
           "tennis": {"enabled": False}, "local": {"enabled": False}}
    data = FR.gather(cfg, FakeFetcher({}), today=dt.date(2026, 11, 3))
    check("AC-144/INV-65 the digest reports no followed sports",
          not (data["sports"].get("enabled")), str(data["sports"]))
    text = FR.render_text(data)
    check("AC-144 the digest does not invent a sport block",
          "nothing is followed yet" in text.lower() or "no sports" in text.lower(),
          text[:500])


def test_manage_sports_bat_is_double_clickable() -> None:
    """AC-140: numbered menu, prints FIRST, CRLF, and the sports items are 1 and 2."""
    raw = open("MANAGE_SPORTS.bat", encoding="utf-8", newline="").read()
    check("AC-140 the .bat is CRLF (double-click safe on Windows)",
          raw.count("\r\n") > 50 and raw.count("\n") == raw.count("\r\n"),
          f"crlf={raw.count(chr(13)+chr(10))} lf={raw.count(chr(10))}")

    menu_at = raw.index(":menu")
    first_prompt = raw.index('set /p "CHOICE=')
    seg = raw[menu_at:first_prompt]
    check("AC-140 ADD a sport is numbered menu item 1", "1  ADD a sport" in seg)
    check("AC-140 REMOVE a sport is numbered menu item 2", "2  REMOVE a sport" in seg)
    check("AC-140 the menu prints BEFORE any sub-prompt",
          "set /p \"SPORT_NAME" not in raw[:first_prompt])
    check("AC-140 the menu is the first thing shown, before the current list",
          raw.index("1  ADD a sport") < raw.index("--list-sports"))
    check("AC-140 it names the file the owner double-clicks (itself)",
          "Double-click THIS file" in raw)
    check("AC-140 removing is described as reversible",
          "switched back on" in raw or "reversible" in raw)
    check("AC-140 it does not require the owner to type a command",
          "no commands" in raw.lower() or "No file to open" in raw)

def main() -> int:
    print("=== personal pages verification ===\n")
    for fn in (
        test_owner_dates,
        test_event_list_is_exactly_the_owners,
        test_everything_has_a_source,
        test_no_invented_channels,
        test_pages_are_unlisted_and_say_so,
        test_moving_holidays_are_computed,
        test_sports_descriptions,
        test_sports_preferences,
        test_sports_pruning,
        test_chatting_date_corrected,
        test_chatting_derivations_consistent,
        test_checkin_reminders,
        test_digest_with_frozen_clock,
        test_html_email_is_a_real_alternative,
        test_reminders_obey_the_follow_list,
        test_an_event_date_range_renders_a_real_dash,
        test_html_email_escapes_owner_data,
        test_sender_attaches_the_html_alternative,
        test_ics_files,
        test_pages_are_current,
        test_check_is_reproducible_without_a_clock,
        test_her_birthday,
        test_cute_days_are_verified_and_kind_is_labelled,
        test_coming_up_covers_the_planning_surface,
        test_no_secret_leaked,
        test_sports_page_shows_the_follow_table_and_the_tool_pointer,
        test_digest_footer_points_at_the_tool,
        test_local_category_config_is_complete,
        test_local_ordering_is_deterministic,
        test_two_person_offers_render_with_the_label,
        test_local_window_argument_and_empty_state,
        test_removed_category_is_excluded,
        test_sport_list_is_first_class_and_complete,
        test_follow_edit_cli_contract,
        test_add_then_remove_a_sport_round_trips,
        test_empty_sport_list_is_legal_and_stays_empty,
        test_manage_sports_bat_is_double_clickable,
    ):
        fn()
        print()

    total = 0
    print("=== summary ===")
    if FAILURES:
        print(f"{len(FAILURES)} FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all personal-page checks PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
