#!/usr/bin/env python3
"""Build the owner's two unlisted personal pages and their calendars.

Owner request (2026-10-05), verbatim intent:
  * "One called good_hubby"   - reminders for Chloe events / special days
  * "Another called sports"   - upcoming events and where to watch
  * "Make a nice calender where i can see all coming up and where to watch"
  * "I want these emailed/whatever to me. Whatever is free."
  * "Build all as-is, unlisted only. I dont mind anyone can see things."
  * "Dont add any more." (exactly the 16 events supplied)

Outputs (site root, next to index.html, so the address is short):
    sports.html        sports.ics
    good_hubby.html    good_hubby.ics

They live at the ROOT, not in a subfolder, because the owner asked for exactly
that: "Having to click personal is annoying. Should of been set up jsut like
cute and 2026.html". The generator data stays under personal/data/.

These two pages are NOT part of the delivered professional portfolio. They are
an owner utility that happens to share the origin, so the site's page-level
tooling treats them as an explicitly excluded class: `tests/verify_site.py`
defines PERSONAL_PAGES and `html_pages()` leaves them out, which is what keeps
the sitemap, the shared navigation, the ambient-bot fact pools and the
per-page accessibility sweeps scoped to the actual site. Adding a third one
means adding it to PERSONAL_PAGES.

UNLISTED, NOT PRIVATE. These pages are served publicly from a public repo.
"Unlisted" means nothing links to them; anyone with the URL can read them, and
the files are readable in the repository itself. The owner was told this
explicitly and accepted it. The pages therefore carry `noindex, nofollow` and
robots.txt disallows them, which keeps them out of search results - it does
not make them secret, and the pages say so in their own footer.

Nothing here is invented: every date and holiday in the two JSON inputs carries
a `source` field, and channel numbers are deliberately null because no official
source could be verified for them.

Usage:
    python3 scripts/build_personal.py           # write pages + calendars
    python3 scripts/build_personal.py --check   # verify outputs are current
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

DATA = "personal/data"
OUT = "."

SITE = "https://matthewmbowyer.github.io/UoEOMScDataScience"

# SuperSport is the only confirmed carrier for the owner's list; the other two
# are offered as owner-named alternatives rather than asserted per event.
WATCH_NOTE = ("SuperSport is the confirmed DStv carrier for this list. Red Bull TV and F1 TV "
              "are included because you named them - check the guide for live coverage.")


def load(name: str) -> dict:
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def prune_events(events: list[dict], as_of: dt.date) -> tuple[list[dict], list[dict]]:
    """Split events into (kept, pruned) by end date relative to `as_of`.

    Deterministic and pure: the same (events, as_of) always yields the same
    split, so a rebuild is reproducible. An event is pruned once its `end` date
    has strictly passed — an event running today is kept. The source list in
    personal/data/sports.json is never modified; only the generated page and
    .ics drop the expired entries.
    """
    kept, pruned = [], []
    for e in sorted(events, key=lambda x: (x["start"], x["name"])):
        (kept if d(e["end"]) >= as_of else pruned).append(e)
    return kept, pruned


def _prune_as_of(data: dict) -> dt.date:
    """The deterministic reference date used for pruning when none is given."""
    ref = (data.get("pruning") or {}).get("as_of")
    if ref:
        try:
            return dt.date.fromisoformat(ref)
        except ValueError:
            pass
    return dt.date.today()


def nice(s: str) -> str:
    dt_ = d(s)
    return f"{dt_.day} {dt_.strftime('%b %Y')}"


def span(ev: dict) -> str:
    a, b = ev["start"], ev["end"]
    if a == b:
        return nice(a)
    da, db = d(a), d(b)
    if (da.year, da.month) == (db.year, db.month):
        return f"{da.day}-{db.day} {da.strftime('%b %Y')}"
    return f"{nice(a)} - {nice(b)}"


def days_word(n: int) -> str:
    return f"{n:,}".replace(",", " ")


# ---------------------------------------------------------------------------
# Shared chrome. Deliberately matches the owner's own 2026.html dark theme, so
# the two new pages sit alongside Cute.html/2026.html rather than looking like a
# different site bolted on.
# ---------------------------------------------------------------------------

CSS = """
:root{
  --bg:#070A12; --card:#0D1222; --card2:#0B1020; --text:#E9EEFF; --muted:#A9B2D6;
  --line:rgba(255,255,255,.08); --accent:#7c5cff; --accent2:#22d3ee;
  --good:#28d17c; --warn:#f7c948; --radius:18px;
  --shadow:0 14px 40px rgba(0,0,0,.45);
}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;
  font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
  background:
    radial-gradient(1000px 500px at 10% -10%, rgba(124,92,255,.30), transparent 55%),
    radial-gradient(900px 450px at 110% 10%, rgba(34,211,238,.20), transparent 55%),
    var(--bg);
  color:var(--text);
  line-height:1.55;
}
a{color:var(--accent2);text-decoration:none}
a:hover,a:focus-visible{text-decoration:underline}
.wrap{max-width:1100px;margin:0 auto;padding:22px 16px 48px}
header.top{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;justify-content:space-between;margin-bottom:6px}
h1{font-size:clamp(1.5rem,3.4vw,2rem);margin:0;letter-spacing:-.02em}
.sub{color:var(--muted);margin:6px 0 0;font-size:.95rem}
nav.links{display:flex;gap:10px;flex-wrap:wrap}
nav.links a{
  border:1px solid var(--line);border-radius:999px;padding:7px 14px;font-size:.86rem;
  color:var(--text);background:rgba(255,255,255,.03)
}
nav.links a[aria-current=page]{border-color:var(--accent);background:rgba(124,92,255,.16)}
.card{
  background:linear-gradient(180deg,var(--card),var(--card2));
  border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);
  padding:20px;margin:18px 0
}
h2{font-size:1.1rem;margin:0 0 4px;letter-spacing:-.01em}
h3{font-size:.95rem;margin:0}
.muted{color:var(--muted)}
.small{font-size:.84rem}
.next{display:flex;flex-wrap:wrap;gap:22px;align-items:center;justify-content:space-between}
.next .big{font-size:clamp(1.6rem,5vw,2.4rem);font-weight:700;letter-spacing:-.02em;line-height:1.1}
.count{display:flex;gap:18px;flex-wrap:wrap}
.count div{text-align:center;min-width:64px}
.count b{display:block;font-size:1.5rem;letter-spacing:-.02em}
.count span{font-size:.72rem;text-transform:uppercase;letter-spacing:.09em;color:var(--muted)}
.month{margin:22px 0 6px;font-size:.78rem;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}
ul.events{list-style:none;margin:0;padding:0;display:grid;gap:10px}
ul.events li{
  display:grid;grid-template-columns:104px 1fr auto;gap:14px;align-items:center;
  border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:rgba(255,255,255,.02)
}
ul.events li.past{opacity:.5}
ul.events .when{font-variant-numeric:tabular-nums;font-size:.86rem;color:var(--muted)}
ul.events .who{font-weight:600}
ul.events .meta{font-size:.8rem;color:var(--muted);margin-top:2px}
.tag{
  display:inline-block;font-size:.72rem;padding:3px 9px;border-radius:999px;
  border:1px solid var(--line);color:var(--muted);white-space:nowrap
}
.tag.live{border-color:rgba(40,209,124,.5);color:var(--good)}
.tag.soon{border-color:rgba(247,201,72,.5);color:var(--warn)}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.milestone{border:1px solid var(--line);border-radius:14px;padding:16px;background:rgba(255,255,255,.02)}
.milestone .num{font-size:1.9rem;font-weight:700;letter-spacing:-.02em;line-height:1.1}
.milestone .lbl{font-size:.8rem;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);margin-bottom:8px}
/* Row kind, so a long "coming up" list can be scanned at a glance. */
.chip{
  display:inline-block;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;
  color:var(--muted);border:1px solid var(--line);border-radius:999px;
  padding:1px 8px;margin-right:2px;vertical-align:1px
}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line)}
th{font-size:.74rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:600}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
footer.bot{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:.82rem}
.flag{
  border-left:3px solid var(--warn);background:rgba(247,201,72,.07);
  border-radius:0 12px 12px 0;padding:12px 16px;margin:16px 0;font-size:.88rem
}
@media (max-width:620px){
  ul.events li{grid-template-columns:1fr;gap:6px}
  .count{width:100%;justify-content:space-between}
}
"""

# Countdown + relative-day logic runs in the browser so the pages never go
# stale: the same file shows "in 3 days" today and "today" tomorrow.
JS = """
(function(){
  var now = new Date();
  var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  function startOf(s){ var p = s.split('-'); return new Date(+p[0], +p[1]-1, +p[2]); }
  function dayDiff(a,b){ return Math.round((b-a)/86400000); }
  function plural(n,w){ return n + ' ' + w + (n===1?'':'s'); }

  // "days until" / "days since" labels
  document.querySelectorAll('[data-until]').forEach(function(el){
    var target = startOf(el.getAttribute('data-until'));
    var diff = dayDiff(today, target);
    el.textContent = diff === 0 ? 'today' : (diff > 0 ? 'in ' + plural(diff,'day') : plural(-diff,'day') + ' ago');
  });
  // Next birthday. Month/day only, so no age is computed: the owner gave the
  // day, not a birth year, and an invented year would show a wrong age.
  document.querySelectorAll('[data-bday]').forEach(function(el){
    var p = el.getAttribute('data-bday').split('-');
    var m = +p[0], dd = +p[1];
    var when = new Date(today.getFullYear(), m-1, dd);
    if (when < today) { when = new Date(today.getFullYear()+1, m-1, dd); }
    var diff = dayDiff(today, when);
    var out = el.querySelector('[data-bday-next]');
    if (out) {
      out.textContent = diff === 0 ? 'today'
        : (diff === 1 ? 'tomorrow' : 'in ' + plural(diff,'day'));
    }
  });

  document.querySelectorAll('[data-since]').forEach(function(el){
    var from = startOf(el.getAttribute('data-since'));
    var diff = dayDiff(from, today);
    var years = today.getFullYear() - from.getFullYear();
    var anniv = new Date(from.getFullYear()+years, from.getMonth(), from.getDate());
    if (anniv < today) { years += 1; anniv = new Date(from.getFullYear()+years, from.getMonth(), from.getDate()); }
    el.querySelector('[data-days]').textContent = plural(diff,'day');
    el.querySelector('[data-years]').textContent = plural(years,'year');
    var toAnniv = dayDiff(today, anniv);
    el.querySelector('[data-next]').textContent =
      toAnniv === 0 ? 'today' : (toAnniv === 1 ? 'tomorrow' : 'in ' + plural(toAnniv,'day'));
  });

  // Live "next up" countdown card
  var box = document.getElementById('next-up');
  if (box) {
    var rows = [].slice.call(document.querySelectorAll('[data-start]'));
    var upcoming = rows.filter(function(r){ return startOf(r.getAttribute('data-start')) >= today; })
                       .sort(function(a,b){ return startOf(a.getAttribute('data-start')) - startOf(b.getAttribute('data-start')); });
    if (upcoming.length) {
      var ev = upcoming[0], t = startOf(ev.getAttribute('data-start'));
      var diff = dayDiff(today, t);
      box.querySelector('[data-name]').textContent = ev.getAttribute('data-name');
      box.querySelector('[data-when]').textContent = ev.getAttribute('data-when');
      box.querySelector('[data-watch]').textContent = ev.getAttribute('data-watch');
      box.querySelector('[data-count]').textContent =
        diff === 0 ? 'Today' : (diff === 1 ? 'Tomorrow' : plural(diff,'day'));
      box.querySelector('[data-count-label]').textContent = diff === 0 ? '' : 'until it starts';
    } else {
      box.querySelector('[data-name]').textContent = 'Nothing left on the list';
      box.querySelector('[data-count]').textContent = '-';
    }
  }

  // Highlight rows that are live / imminent, using the real clock
  document.querySelectorAll('[data-start][data-end]').forEach(function(r){
    var s = startOf(r.getAttribute('data-start')), e = startOf(r.getAttribute('data-end'));
    var tag = r.querySelector('.tag');
    if (!tag) return;
    if (today >= s && today <= e) { tag.textContent = 'On now'; tag.className = 'tag live'; }
    else if (dayDiff(today, s) <= 7 && dayDiff(today, s) >= 0) { tag.textContent = 'This week'; tag.className = 'tag soon'; }
  });
})();
"""


def page(title: str, heading: str, sub: str, body: str, active: str,
         as_of: str | None = None) -> str:
    body_attr = f' data-as-of="{as_of}"' if as_of else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<meta name="robots" content="noindex, nofollow" />
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body{body_attr}>
<div class="wrap">
<header class="top">
  <div>
    <h1>{html.escape(heading)}</h1>
    <p class="sub">{sub}</p>
  </div>
  <nav class="links" aria-label="Personal pages">
    <a href="sports.html"{' aria-current="page"' if active == "sports" else ''}>Sports</a>
    <a href="good_hubby.html"{' aria-current="page"' if active == "hubby" else ''}>Good Hubby</a>
  </nav>
</header>
{body}
<footer class="bot">
  <p><strong>Unlisted, not private.</strong> Nothing on the main site links here, and this page asks
  search engines not to index it - but it is served from a public repository, so anyone who has the
  address can read it. Keep that in mind before adding anything you would not want read.</p>
  <p>Dates come from the list you supplied and from the cited sources in
  <code>personal/data/</code>. Nothing here is invented; anything unverified is marked as such.</p>
</footer>
</div>
<script>{JS}</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# sports.html
# ---------------------------------------------------------------------------

def build_sports(data: dict, today: dt.date | None = None) -> str:
    """Render sports.html from the supplied events, pruning expired ones.

    `today` defaults to the stored `prune_as_of` reference date (falling back to
    the real date), so a rebuild is reproducible and `--check` is stable. Tests
    pass a frozen clock. The 16-event source list is untouched — only the
    generated page and .ics drop events whose end date has passed.
    """
    today = today or _prune_as_of(data)
    events, pruned = prune_events(data["events"], today)
    b = data["broadcasters"]

    next_box = """
<section class="card next" id="next-up">
  <div>
    <div class="lbl muted small" style="text-transform:uppercase;letter-spacing:.09em">Next up</div>
    <div class="big" data-name>&nbsp;</div>
    <div class="muted" data-when></div>
    <div class="muted small" data-watch></div>
  </div>
  <div class="count">
    <div><b data-count>&nbsp;</b><span data-count-label></span></div>
  </div>
</section>
"""

    by_month: dict[str, list[dict]] = {}
    for ev in events:
        by_month.setdefault(d(ev["start"]).strftime("%B %Y"), []).append(ev)

    rows = []
    for month, evs in by_month.items():
        rows.append(f'<div class="month">{html.escape(month)}</div>')
        rows.append('<ul class="events">')
        for ev in evs:
            ch = ev.get("channel")
            watch = b[ev["broadcaster"]]["name"]
            if ch:
                watch += f' ch {ch}'
            desc = html.escape(ev.get("description", ""))
            meta = f'{html.escape(ev["series"])} &middot; {html.escape(ev["sport"])}'
            link = (f'<a href="{html.escape(ev["supersport_section"])}" target="_blank" '
                    f'rel="noopener noreferrer">{html.escape(watch)}</a>')
            rows.append(
                f'<li data-start="{ev["start"]}" data-end="{ev["end"]}" '
                f'data-name="{html.escape(ev["name"])}" data-when="{html.escape(span(ev))}" '
                f'data-watch="{html.escape(watch)}">'
                f'<span class="when">{html.escape(span(ev))}</span>'
                f'<span><span class="who">{html.escape(ev["name"])}</span>'
                f'<span class="meta">{meta}<br />'
                f'<span class="desc">{desc}</span><br />Watch: {link}</span></span>'
                f'<span class="tag">Scheduled</span></li>'
            )
        rows.append('</ul>')

    guides = ", ".join(
        f'<a href="{html.escape(v.get("guide") or v.get("url",""))}" target="_blank" '
        f'rel="noopener noreferrer">{html.escape(v["name"])}</a>'
        for v in b.values()
    )

    # Machine-readable preference profile, surfaced as a human table too.
    pref = data.get("preferences", {})
    pref_rows = "".join(
        f'<tr><td>{html.escape(s["sport"])}</td>'
        f'<td class="num">{s["event_count"]}</td>'
        f'<td>{html.escape(", ".join(s["series"]))}</td></tr>'
        for s in pref.get("sports", [])
    )

    pruned_note = ""
    if pruned:
        names = ", ".join(html.escape(p["name"]) for p in pruned)
        pruned_note = (f'<p class="small muted">Pruned as already finished before this build: '
                       f'{names}.</p>')

    body = f"""
{next_box}
<section class="card">
  <h2>The list</h2>
  <p class="muted small">Exactly the {len(events)} events you gave me that are still to come - nothing added.
  Times are your local timezone, {html.escape(data["timezone_label"])}. The countdown and the "on now"
  labels are worked out by your browser when the page loads, so this stays correct without me editing it.
  {('Events whose end date has passed are pruned on each build (' + str(len(pruned)) + ' dropped here).')
   if pruned else 'Nothing has been pruned yet.'}</p>
  <div class="flag">
    <strong>Channel numbers are blank on purpose.</strong> I could not confirm a channel number for these
    from an official source, and guessing one would send you to the wrong channel. Each row links to the
    relevant SuperSport section and the TV guide instead, where the number is shown live.
    If you tell me the numbers, I will put them in.
  </div>
  {''.join(rows)}
  {pruned_note}
</section>

<section class="card">
  <h2>What you follow</h2>
  <p class="muted small">This is the sports profile recorded from your own list, so a future refresh knows
  what to look for without guessing. It adds nothing you have not shown an interest in.</p>
  <table>
    <tr><th>Sport</th><th>Events</th><th>Series</th></tr>
    {pref_rows}
  </table>
</section>

<section class="card">
  <h2>Where to watch</h2>
  <p class="muted small">{html.escape(WATCH_NOTE)}</p>
  <table>
    <tr><th>Source</th><th>What it is</th><th>Link</th></tr>
    <tr><td>SuperSport</td><td>Your DStv sport channels, and the live TV guide</td>
        <td><a href="https://supersport.com/tv-guide" target="_blank" rel="noopener noreferrer">TV guide</a></td></tr>
    <tr><td>Red Bull TV</td><td>Free streaming, no subscription</td>
        <td><a href="https://www.redbull.com/int-en/tv" target="_blank" rel="noopener noreferrer">redbull.com/tv</a></td></tr>
    <tr><td>F1 TV</td><td>Formula 1's own streaming service</td>
        <td><a href="https://f1tv.formula1.com/" target="_blank" rel="noopener noreferrer">f1tv.formula1.com</a></td></tr>
  </table>
  <p class="small muted" style="margin-top:12px">Guides: {guides}</p>
</section>

<section class="card">
  <h2>Put it in your calendar</h2>
  <p class="muted small">This is the free way to get reminded. Download the file, or subscribe to the URL
  and your phone will do the nagging - no server, no cost, and new events appear when the list changes.</p>
  <p><a href="sports.ics" download>Download sports.ics</a> &nbsp;&middot;&nbsp;
     <a href="sports.ics">Subscribe URL</a> (paste into Google/Apple Calendar &rarr; "From URL")</p>
</section>
"""
    return page("Sports calendar", "Sports calendar",
                f"{len(events)} events still to come, {html.escape(data['timezone_label'])}",
                body, "sports", as_of=today.isoformat())


# ---------------------------------------------------------------------------
# good_hubby.html
# ---------------------------------------------------------------------------

RULE_LABEL = {
    "second_sunday_may": "Second Sunday in May",
    "third_sunday_june": "Third Sunday in June",
    "third_saturday_october": "Third Saturday in October",
}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """nth `weekday` (Mon=0) of a month. n=2 -> second."""
    first = dt.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + dt.timedelta(days=offset + 7 * (n - 1))


def resolve_moving(h: dict, year: int) -> dt.date | None:
    rule = h["rule"]
    if "dates" in h and str(year) in h["dates"]:
        return d(h["dates"][str(year)])
    if rule == "second_sunday_may":
        return _nth_weekday(year, 5, 6, 2)
    if rule == "second_sunday_february":
        return _nth_weekday(year, 2, 6, 2)
    if rule == "third_sunday_june":
        return _nth_weekday(year, 6, 6, 3)
    if rule == "third_saturday_october":
        return _nth_weekday(year, 10, 5, 3)
    return None


def next_annual(month: int, day: int, today: dt.date) -> dt.date | None:
    """The next occurrence of a month/day on or after `today`, or None."""
    for year in (today.year, today.year + 1):
        try:
            when = dt.date(year, month, day)
        except ValueError:
            continue
        if when >= today:
            return when
    return None


def hubby_upcoming(data: dict, today: dt.date,
                   horizon_days: int = 365) -> list[dict]:
    """Everything worth planning for, in one sorted list.

    The owner asked for the "coming up" list to be a planning surface, not just
    a holiday list, so this gathers the birthdays, the milestone anniversaries
    and the check-in days alongside the cute days and the public holidays. Each
    entry keeps its own `source`, so nothing on the page is unsourced.
    """
    horizon = today + dt.timedelta(days=horizon_days)
    out: list[dict] = []

    def add(when, name, note, source, kind):
        if when and today <= when <= horizon:
            out.append({"when": when, "name": name, "note": note,
                        "source": source, "kind": kind})

    for h in data.get("fixed_holidays", []):
        add(next_annual(h["month"], h["day"], today), h["name"], h["note"],
            h.get("source", ""), h.get("kind", "Cute day"))
    for h in data.get("moving_holidays", []):
        when = next((w for w in (resolve_moving(h, y)
                                 for y in (today.year, today.year + 1)) if w), None)
        add(when, h["name"], h["note"], h.get("source", ""),
            h.get("kind", "Cute day"))
    for b in data.get("birthdays", []):
        add(next_annual(b["month"], b["day"], today), b["name"], b["note"],
            b.get("source_short", b.get("source", "")), "Birthday")
    for m in data.get("milestones", []):
        started = d(m["date"])
        when = next_annual(started.month, started.day, today)
        if when:
            years = when.year - started.year
            add(when, f"{m['label']} anniversary",
                f"{years} years since {nice(m['date'])}",
                m.get("source_short", m.get("source", "")), "Anniversary")
    ck = data.get("checkins")
    if ck:
        for when in next_checkin_dates(today, ck["anchor"]["day_of_month"], n=26):
            add(when, ck["name"], ck["_purpose"],
                "Owner-set anchor: 1st and 22nd of the month", "Check-in")

    out.sort(key=lambda e: (e["when"], e["name"]))
    return out


def next_checkin_dates(today: dt.date, days_of_month: list[int], n: int = 4) -> list[dt.date]:
    """The next `n` event-anchored check-in dates on/after `today`.

    Anchored to specific days of the month (not a daily schedule), so the
    effective cadence is roughly weekly-to-fortnightly rather than every day.
    """
    out: list[dt.date] = []
    year, month = today.year, today.month
    while len(out) < n:
        for dom in sorted(days_of_month):
            try:
                when = dt.date(year, month, dom)
            except ValueError:
                continue
            if when >= today:
                out.append(when)
                if len(out) >= n:
                    break
        month += 1
        if month > 12:
            month = 1
            year += 1
    return sorted(out)[:n]


def build_hubby(data: dict, today: dt.date) -> str:
    miles = sorted(data["milestones"], key=lambda m: m["date"])

    cards = []
    for m in miles:
        cards.append(
            f'<div class="milestone" data-since="{m["date"]}">'
            f'<div class="lbl">{html.escape(m["label"])}</div>'
            f'<div class="num" data-days>&nbsp;</div>'
            f'<div class="muted small">{html.escape(nice(m["date"]))} &middot; '
            f'<span data-years></span> together</div>'
            f'<div class="small" style="margin-top:8px">Next anniversary <span data-next></span></div>'
            f'</div>'
        )

    fixed = sorted(data["fixed_holidays"], key=lambda h: (h["month"], h["day"]))
    upcoming = hubby_upcoming(data, today)

    # The list is long once the check-ins are folded in, so the rows carry their
    # kind. The nearest few are marked so the page can be scanned for "what is
    # next" without reading every row.
    soon = {e["when"] for e in upcoming[:6]}
    rows = "".join(
        f'<tr data-kind="{html.escape(e["kind"])}">'
        f'<td class="num">{html.escape(nice(e["when"].isoformat()))}</td>'
        f'<td><span data-until="{e["when"].isoformat()}"></span></td>'
        f'<td><span class="chip">{html.escape(e["kind"])}</span> '
        f'<strong>{html.escape(e["name"])}</strong>'
        f'<br /><span class="muted small">{html.escape(e["note"])}</span>'
        f'<br /><span class="muted small">Source: {html.escape(e["source"])}</span></td></tr>'
        for e in upcoming
    )
    next_soon = [e for e in upcoming if e["when"] in soon]
    next_line = ""
    if next_soon:
        bits = ", ".join(
            f'{html.escape(e["name"])} ({html.escape(nice(e["when"].isoformat()))})'
            for e in next_soon[:3])
        next_line = (f'<p class="muted small">Next three: {bits}.</p>')

    # Her birthday. Month and day only: the owner gave the day, not a year, so
    # no age is computed and none is implied.
    bday_cards = "".join(
        f'<div class="milestone" data-bday="{b["month"]:02d}-{b["day"]:02d}">'
        f'<div class="lbl">{html.escape(b["name"])}</div>'
        f'<div class="num">{b["day"]} {dt.date(2000, b["month"], 1).strftime("%B")}</div>'
        f'<div class="muted small">{html.escape(b["note"])} &middot; '
        f'next <span data-bday-next></span></div>'
        f'<div class="muted small" style="margin-top:8px">Source: '
        f'{html.escape(b.get("source_short", b.get("source", "")))}</div>'
        f'</div>'
        for b in data.get("birthdays", [])
    )

    # Event-anchored "checking on each other" reminders. These attach to the 1st
    # and 22nd of the month (the 22nd is the chatting milestone's day-of-month)
    # plus the milestone anniversaries already on the page - not a daily schedule.
    ck = data.get("checkins", {})
    ck_rows = ""
    if ck:
        dates = next_checkin_dates(today, ck["anchor"]["day_of_month"], n=4)
        ck_rows = "".join(
            f'<tr><td class="num">{html.escape(nice(w.isoformat()))}</td>'
            f'<td>{html.escape(p["text"])}</td></tr>'
            for w, p in zip(dates, ck["prompts"])
        )

    checkin_section = ""
    if ck:
        checkin_section = f"""
<section class="card">
  <h2>{html.escape(ck["name"])}</h2>
  <p class="muted small">{html.escape(ck["_purpose"])} They land on the 1st and the 22nd of
  the month - the 22nd is the day of the month you started chatting - plus the three
  anniversaries above. That works out at roughly {html.escape(ck["effective_frequency"].split("(")[0].strip())},
  rather than something that nags you every day.</p>
  <table>
    <tr><th>Date</th><th>What to do</th></tr>
    {ck_rows}
  </table>
  <p class="muted small" style="margin-top:12px">These are deliberately general. The name
  options were &ldquo;{html.escape('&rdquo; and &ldquo;'.join(ck["name_options"]))}&rdquo;; I went with
  &ldquo;{html.escape(ck["name"])}&rdquo; as the plainest. Tell me anything specific you would rather
  they say and I will put it in.</p>
</section>
"""

    bday_section = ""
    if bday_cards:
        bday_section = f"""
<section class="card">
  <h2>Birthdays</h2>
  {bday_cards}
</section>
"""

    body = f"""
<section class="card">
  <h2>Your days</h2>
  <p class="muted small">Counting runs in your browser from the dates you gave me, so it is always
  right - no edits needed as time passes.</p>
  <div class="grid">{''.join(cards)}</div>
</section>

{bday_section}

{checkin_section}

<section class="card">
  <h2>Coming up</h2>
  <p class="muted small">Everything worth planning for over the next 12 months - the cute days, the
  South African public holidays, her birthday, the milestone anniversaries and the check-in days - in
  one list, in date order. Every date carries its source. Days that move each year (Easter, World
  Marriage Day, Mother's Day, Father's Day, Sweetest Day) are worked out from their rule rather than
  written down, so this list does not rot.</p>
  {next_line}
  <table>
    <tr><th>Date</th><th>When</th><th>What</th></tr>
    {rows}
  </table>
</section>

<section class="card">
  <h2>Put it in your calendar</h2>
  <p class="muted small">Download or subscribe, same as the sports page. Subscribing means your phone
  reminds you - free, and no website to remember to check.</p>
  <p><a href="good_hubby.ics" download>Download good_hubby.ics</a> &nbsp;&middot;&nbsp;
     <a href="good_hubby.ics">Subscribe URL</a></p>
</section>
"""
    return page("Good Hubby", "Good Hubby",
                "Your special days, anniversaries and the cute holidays", body, "hubby")


# ---------------------------------------------------------------------------
# Calendars
# ---------------------------------------------------------------------------

def ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def ics(events: list[dict], calname: str) -> str:
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Matthew Bowyer//Personal//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_escape(calname)}",
        "X-WR-TIMEZONE:Africa/Johannesburg",
    ]
    # DTSTAMP is required by the format, but using "now" would rewrite the file
    # on every run and make `--check` permanently stale. Derive it from the
    # newest event instead: deterministic, still a valid timestamp, and the
    # file only changes when the content does.
    newest = max(d(e["end"]) for e in events)
    stamp = newest.strftime("%Y%m%dT000000Z")
    for e in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{ics_escape(e['uid'])}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d(e['start']).strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(d(e['end']) + dt.timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:{ics_escape(e['summary'])}",
            f"DESCRIPTION:{ics_escape(e['description'])}",
        ]
        if e.get("url"):
            lines.append(f"URL:{e['url']}")
        if e.get("rrule"):
            lines.append(f"RRULE:{e['rrule']}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def sports_ics(data: dict, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    kept, _pruned = prune_events(data["events"], today)
    b = data["broadcasters"]
    evs = []
    for e in kept:
        watch = b[e["broadcaster"]]["name"]
        if e.get("channel"):
            watch += f" ch {e['channel']}"
        evs.append({
            "uid": f"{e['id']}@eportfolio.personal",
            "start": e["start"], "end": e["end"],
            "summary": f"{e['name']} ({e['sport']})",
            "description": f"{e['series']}. Watch: {watch}. Guide: {b[e['broadcaster']]['guide']}",
            "url": b[e["broadcaster"]]["guide"],
        })
    return ics(evs, "Sports")


def hubby_ics(data: dict, today: dt.date) -> str:
    # Fixed base year with a yearly recurrence, rather than "this year": the
    # file then stays byte-identical across runs and across New Year, so the
    # committed copy cannot silently drift.
    base_year = 2026
    evs = []
    for m in data["milestones"]:
        evs.append({
            "uid": f"milestone-{m['id']}@eportfolio.personal",
            "start": m["date"], "end": m["date"],
            "summary": m["label"],
            # The .ics carries the concise source; the full supersede note lives
            # on the page and in the data file, so a derived artefact never
            # restates a superseded date.
            "description": f"{m['label']} - {m.get('source_short', m['source'])}",
            "rrule": "FREQ=YEARLY",
        })
    # Her birthday: month/day only, yearly recurrence. No birth year is invented,
    # so no age can be derived from this entry.
    for b in data.get("birthdays", []):
        start = dt.date(base_year, b["month"], b["day"]).isoformat()
        evs.append({
            "uid": f"birthday-{b['name'].lower().replace(' ', '-')}@eportfolio.personal",
            "start": start, "end": start,
            "summary": b["name"],
            "description": f"{b['note']} (Source: {b.get('source_short', b.get('source', ''))})",
            "rrule": "FREQ=YEARLY",
        })
    for h in data["fixed_holidays"]:
        start = dt.date(base_year, h["month"], h["day"]).isoformat()
        evs.append({
            "uid": f"holiday-{h['name'].lower().replace(' ', '-')}@eportfolio.personal",
            "start": start, "end": start,
            "summary": h["name"], "description": f"{h['note']} (Source: {h['source']})",
            "rrule": "FREQ=YEARLY",
        })
    # Moving holidays cannot be expressed as a simple RRULE, so they are listed
    # explicitly for the years whose dates are actually known. Years with no
    # verified date are skipped rather than guessed.
    for h in data["moving_holidays"]:
        for year in range(base_year, base_year + 5):
            when = resolve_moving(h, year)
            if when:
                evs.append({
                    "uid": f"moving-{h['name'].lower().replace(' ', '-')}-{year}@eportfolio.personal",
                    "start": when.isoformat(), "end": when.isoformat(),
                    "summary": h["name"],
                    "description": f"{h['note']} (Source: {h['source']})",
                })
    # Event-anchored check-ins: a monthly recurrence on the 1st and 22nd, so the
    # reminders land on the same occasions the page names, not daily.
    ck = data.get("checkins")
    if ck:
        for dom in sorted(ck["anchor"]["day_of_month"]):
            start = dt.date(base_year, 1, dom).isoformat()
            evs.append({
                "uid": f"checkin-{dom}@eportfolio.personal",
                "start": start, "end": start,
                "summary": f"{ck['name']} - {ck['prompts'][0]['text']}",
                "description": ck["_purpose"],
                "rrule": f"FREQ=MONTHLY;BYMONTHDAY={dom}",
            })
    return ics(evs, "Good Hubby")


# ---------------------------------------------------------------------------

def write(path: str, content: str, check: bool) -> bool:
    """Write, or in --check mode report whether the file is already current.

    Both read and write use newline="" so the CRLF endings the .ics format
    requires survive the round trip; without it Python's universal-newline
    translation makes every .ics look stale.
    """
    if check:
        if not os.path.exists(path):
            print(f"MISSING {path}")
            return False
        with open(path, encoding="utf-8", newline="") as fh:
            current = fh.read() == content
        print(f"{'OK   ' if current else 'STALE'} {path}")
        return current
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    print(f"wrote {path} ({len(content):,} bytes)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the outputs are current; non-zero if stale")
    ap.add_argument("--today", help="freeze the clock (YYYY-MM-DD), for tests")
    args = ap.parse_args()

    sports = load("sports.json")
    hubby = load("good_hubby.json")
    # ONE reference date for all four outputs. Without --today this is the
    # stored pin, so a plain rebuild and `--check` reproduce the committed
    # artefacts instead of drifting with the wall clock (the wall clock made
    # `--check` fail every day, which is what made it useless as a drift guard).
    # The governed monthly refresh passes an explicit --today to re-derive it.
    ref = dt.date.fromisoformat(args.today) if args.today else _prune_as_of(sports)

    ok = True
    ok &= write(os.path.join(OUT, "sports.html"),
                build_sports(sports, ref), args.check)
    ok &= write(os.path.join(OUT, "good_hubby.html"),
                build_hubby(hubby, ref), args.check)
    ok &= write(os.path.join(OUT, "sports.ics"),
                sports_ics(sports, ref), args.check)
    ok &= write(os.path.join(OUT, "good_hubby.ics"),
                hubby_ics(hubby, ref), args.check)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
