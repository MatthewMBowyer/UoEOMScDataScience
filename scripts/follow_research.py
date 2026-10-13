#!/usr/bin/env python3
"""Research what the owner follows: news, fixtures, and tennis top-5 results.

Owner request (2026-10-12), verbatim intent:
  * "Improve daily message ... to do more research"
  * "UEFA CHAMOPIONS LEAGEU - Search"
  * "i.e. whatever i am following i get news on"
  * "For tennis, only give me results of top 5."
  * "Make sure we follow any tennis the top 5 are in."
  * "Maybe find a way i can easily add or remove people/teams from sports."
  * "I.e. UEFA i only want specific teams"

WHO is followed lives in `personal/data/follow.json` - one file, edited by hand
or with `scripts/follow_edit.py`. Nothing is followed that the owner did not
name; the lists are allowed to be empty and stay empty.

Sources, all free and keyless:
  * News      - Google News RSS (`news.google.com/rss/search`), one query per
                followed item. It is an aggregator, so the headline and the
                publisher are both carried through verbatim.
  * Fixtures  - ESPN's public site API, which publishes the same schedule the
                ESPN site shows. Used for the football competitions and for the
                tennis tours.
  * Rankings  - the same ESPN API. The tennis top N is read LIVE from the
                rankings rather than hardcoded, so "top 5" means the top 5 on
                the day the email is built, not a list frozen in 2026.

Two hard rules from the project, applied here without exception:

1. **Nothing is invented.** Every line printed carries the source it came from.
   If a fetch fails, the section says it failed; it does not guess and it does
   not silently omit.
2. **Never block the email.** Research is best-effort. Any failure - no network,
   a 404, a changed response shape - degrades to a printed note and the digest
   still goes out. A reminder that arrives without the news beats one that does
   not arrive. `total_budget_seconds` caps the whole step.

Rendering is a pure function of (follow config, fetched data, today), so the
tests pin it with a frozen clock and a fake fetcher, and no test touches the
network.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "personal", "data")

UA = "Mozilla/5.0 (compatible; personal-digest/1.0)"
NEWS_URL = "https://news.google.com/rss/search"
ESPN = "https://site.web.api.espn.com/apis/site/v2/sports"

# ESPN's competition ids. A followed competition names one of these, so adding a
# competition is a data edit, not a code change.
LEAGUES = {
    "uefa.champions": "UEFA Champions League",
    "uefa.europa": "UEFA Europa League",
    "eng.1": "English Premier League",
    "esp.1": "Spanish LaLiga",
    "ita.1": "Italian Serie A",
    "ger.1": "German Bundesliga",
    "fra.1": "French Ligue 1",
    "rsa.1": "South African Premiership",
    "usa.1": "Major League Soccer",
}


class Fetcher:
    """Small, honest HTTP client: a deadline, a timeout, and no retries.

    Retries are deliberately absent. The digest has a fixed send time and a
    source that is down is down; spending the budget on a second attempt costs
    the sections that would otherwise have worked.
    """

    def __init__(self, timeout: float = 12.0, budget: float = 90.0):
        self.timeout = timeout
        self.deadline = dt.datetime.now() + dt.timedelta(seconds=budget)
        self.failures: list[str] = []

    def remaining(self) -> float:
        return (self.deadline - dt.datetime.now()).total_seconds()

    def get(self, url: str) -> bytes | None:
        """Fetch, or record why not. Never raises."""
        left = self.remaining()
        if left <= 0:
            self.failures.append("time budget exhausted")
            return None
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=min(self.timeout, left)) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001 - every failure degrades to a note
            self.failures.append(f"{type(exc).__name__} on {urllib.parse.urlparse(url).netloc}")
            return None

    def json(self, url: str) -> dict | None:
        raw = self.get(url)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            self.failures.append(f"unparseable JSON from {urllib.parse.urlparse(url).netloc}")
            return None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_follow(path: str | None = None) -> dict:
    """The follow list. A missing file is an empty follow list, not an error."""
    p = path or os.path.join(DATA, "follow.json")
    if not os.path.exists(p):
        return {"news": [], "competitions": [], "tennis": {"enabled": False}, "settings": {}}
    with open(p, encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg.setdefault("news", [])
    cfg.setdefault("competitions", [])
    cfg.setdefault("tennis", {"enabled": False})
    cfg.setdefault("settings", {})
    return cfg


def settings(cfg: dict, weekly: bool = False) -> dict:
    s = cfg.get("settings", {})
    age = s.get("weekly_news_max_age_days" if weekly else "news_max_age_days", 3)
    return {
        "news_per_follow": int(s.get("news_per_follow", 3)),
        "news_max_age_days": int(age),
        "timeout": float(s.get("request_timeout_seconds", 12)),
        "budget": float(s.get("total_budget_seconds", 90)),
    }


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def _parse_rfc822(s: str) -> dt.datetime | None:
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            parsed = dt.datetime.strptime(s.strip(), fmt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


def news_for(query: str, f: Fetcher, max_age_days: int, limit: int) -> list[dict]:
    """Headlines for one followed item, newest first, within the age window.

    Google News puts the publisher in a `<source>` element and, when the
    headline is a cluster, appends " - Publisher" to the title too. The
    publisher is kept as a separate field so the digest can attribute it
    honestly rather than leaving a suffix in the middle of a sentence.
    """
    url = f"{NEWS_URL}?q={urllib.parse.quote(query)}&hl=en-ZA&gl=ZA&ceid=ZA:en"
    raw = f.get(url)
    if raw is None:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        f.failures.append("unparseable news feed")
        return []

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=max_age_days)
    out = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        when = _parse_rfc822(item.findtext("pubDate") or "")
        if when is None or when < cutoff:
            continue
        publisher = (item.findtext("source") or "").strip()
        if not publisher and " - " in title:
            title, _, publisher = title.rpartition(" - ")
        # Google News appends " - Publisher" to a clustered headline AND fills
        # <source>. Without this the publisher prints twice.
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(f" - {publisher}")]
        out.append({
            "title": title.strip(),
            "publisher": publisher.strip(),
            "when": when,
            "link": (item.findtext("link") or "").strip(),
        })
        if len(out) >= limit:
            break
    return out


def research_news(cfg: dict, f: Fetcher, s: dict) -> dict:
    """One entry per followed item. An item with no recent news says so."""
    items = []
    for entry in cfg.get("news", []):
        query = entry.get("query") or entry.get("label")
        if not query:
            continue
        items.append({
            "label": entry.get("label", query),
            "sport": entry.get("sport", ""),
            "stories": news_for(query, f, s["news_max_age_days"], s["news_per_follow"]),
        })
    return {"items": items}


# ---------------------------------------------------------------------------
# Football competitions
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    """Loose team-name match, so 'Bayern Munich' finds 'Bayern München'.

    Accents and punctuation are stripped and a few of the common English/
    local spelling splits are folded, because the owner types the English name
    and the feed may carry the local one. Anything still unmatched stays
    unmatched - a wrong match would attribute a fixture to the wrong team,
    which is worse than no fixture.
    """
    n = name.lower()
    for a, b in (("ü", "u"), ("ö", "o"), ("ä", "a"), ("é", "e"), ("è", "e"),
                 ("á", "a"), ("í", "i"), ("ó", "o"), ("ç", "c"), ("ñ", "n"),
                 ("&", "and")):
        n = n.replace(a, b)
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    for long_form, short in (
        ("munchen", "munich"), ("bayern munich", "bayern"),
        ("manchester city", "man city"), ("manchester united", "man united"),
        ("internazionale", "inter"), ("atletico madrid", "atletico"),
        ("paris saint germain", "psg"), ("paris st germain", "psg"),
    ):
        if n == long_form or n.startswith(long_form):
            n = n.replace(long_form, short, 1)
    return n


def _fixture_rows(events: list[dict]) -> list[dict]:
    """Flatten ESPN's soccer scoreboard into one row per match."""
    rows = []
    for ev in events:
        comps = ev.get("competitions") or []
        if not comps:
            continue
        c = comps[0]
        status = (c.get("status") or {}).get("type") or {}
        teams = []
        for t in c.get("competitors", []):
            team = t.get("team") or {}
            teams.append({
                "name": team.get("displayName") or team.get("name") or "?",
                "home": t.get("homeAway") == "home",
                "score": t.get("score"),
                "winner": t.get("winner"),
            })
        when = ev.get("date") or ""
        rows.append({
            "when": when,
            "state": status.get("state", "pre"),
            "detail": status.get("shortDetail") or status.get("description") or "",
            "teams": teams,
            "venue": (c.get("venue") or {}).get("fullName", ""),
            "link": (c.get("links") or [{}])[0].get("href", ""),
        })
    return rows


def competition_fixtures(entry: dict, f: Fetcher) -> dict:
    """The current matchweek for one competition, filtered to followed teams."""
    league = entry.get("league", "")
    label = entry.get("label") or LEAGUES.get(league, league)
    followed = [t for t in (entry.get("teams") or []) if str(t).strip()]
    out = {"label": label, "league": league, "followed": followed,
           "rows": [], "filtered": bool(followed), "error": ""}

    if league not in LEAGUES:
        out["error"] = f"unknown competition id '{league}' (see scripts/follow_research.py LEAGUES)"
        return out

    data = f.json(f"{ESPN}/soccer/{league}/scoreboard")
    if data is None:
        out["error"] = "could not be reached"
        return out

    rows = _fixture_rows(data.get("events") or [])
    if followed:
        wanted = {_norm(t) for t in followed}
        kept = []
        for r in rows:
            names = {_norm(t["name"]) for t in r["teams"]}
            # Substring both ways: "Bayern" in the list should find "Bayern Munich".
            if any(w == n or w in n or n in w for w in wanted for n in names):
                kept.append(r)
        rows = kept
    out["rows"] = rows
    return out


# ---------------------------------------------------------------------------
# Tennis
# ---------------------------------------------------------------------------

def tour_rankings(tour: str, f: Fetcher) -> list[dict]:
    """The live ranking list for one tour, in order. Empty on any failure."""
    data = f.json(f"{ESPN}/tennis/{tour}/rankings")
    if data is None:
        return []
    rankings = data.get("rankings") or []
    if not rankings:
        return []
    out = []
    for entry in rankings[0].get("ranks", []):
        athlete = entry.get("athlete") or {}
        name = athlete.get("displayName")
        if not name:
            continue
        flag = athlete.get("flag")
        country = ""
        if isinstance(flag, dict):
            country = flag.get("alt", "")
        elif isinstance(flag, str) and flag:
            # ESPN gives the flag as an image URL whose basename is the
            # three-letter country code: .../countries/500/kaz.png -> KAZ.
            country = os.path.splitext(os.path.basename(flag))[0].upper()
        out.append({
            "rank": entry.get("current"),
            "name": name,
            "country": country,
            "points": entry.get("points"),
        })
    return out


def tennis_matches(tour: str, f: Fetcher) -> list[dict]:
    """Singles matches from every tournament in the current scoreboard window.

    The scoreboard returns the tournaments being played now and next, which is
    what "follow any tennis the top 5 are in" needs: the top-5 players are
    looked for across all of them, not just the one event the owner's own list
    happens to name.
    """
    data = f.json(f"{ESPN}/tennis/{tour}/scoreboard")
    if data is None:
        return []
    out = []
    for event in data.get("events") or []:
        tournament = event.get("name", "")
        for grouping in event.get("groupings") or []:
            slug = (grouping.get("grouping") or {}).get("slug", "")
            if slug not in ("mens-singles", "womens-singles"):
                continue
            for comp in grouping.get("competitions") or []:
                status = (comp.get("status") or {}).get("type") or {}
                players = []
                for t in comp.get("competitors", []):
                    athlete = t.get("athlete") or {}
                    if not athlete.get("displayName"):
                        continue
                    players.append({
                        "name": athlete["displayName"],
                        "winner": t.get("winner"),
                        "score": t.get("score"),
                    })
                if len(players) < 2:
                    continue
                out.append({
                    "tournament": tournament,
                    "when": comp.get("date") or "",
                    "state": status.get("state", "pre"),
                    "detail": status.get("description", ""),
                    "players": players,
                })
    return out


def _player_key(name: str) -> str:
    """Surname + first initial, so 'Carlos Alcaraz' matches 'C. Alcaraz'."""
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return ""
    surname = _norm(parts[-1])
    return f"{surname}|{_norm(parts[0])[:1]}" if len(parts) > 1 else surname


def tennis_top_n(cfg: dict, f: Fetcher) -> dict:
    """Results and upcoming matches involving the live top N of each tour.

    The top N is read from the rankings on the day, never hardcoded, so this
    keeps working as the rankings change. A top-N player appears here for
    whichever tournament they are in.
    """
    t = cfg.get("tennis") or {}
    if not t.get("enabled"):
        return {"enabled": False, "tours": []}
    top_n = int(t.get("top_n", 5))
    max_matches = int(t.get("max_matches", 10))

    tours = []
    for tour in t.get("tours", ["atp", "wta"]):
        ranking = tour_rankings(tour, f)
        top = ranking[:top_n]
        keys = {_player_key(p["name"]) for p in top}
        by_key = {_player_key(p["name"]): p for p in top}

        results, upcoming = [], []
        matches = tennis_matches(tour, f)
        for m in matches:
            involved = [p for p in m["players"] if _player_key(p["name"]) in keys]
            if not involved:
                continue
            ranked = []
            for p in m["players"]:
                info = by_key.get(_player_key(p["name"]))
                ranked.append({**p, "rank": info["rank"] if info else None,
                               "country": info["country"] if info else ""})
            row = {**m, "players": ranked}
            (results if m["state"] == "post" else upcoming).append(row)

        results.sort(key=lambda r: r["when"], reverse=True)
        upcoming.sort(key=lambda r: r["when"])
        tours.append({
            "tour": tour.upper(),
            "top": top,
            "results": results[:max_matches],
            "upcoming": upcoming[:max_matches],
            "matches_scanned": len(matches),
        })
    return {"enabled": True, "top_n": top_n, "tours": tours}


# ---------------------------------------------------------------------------
# One call that does everything
# ---------------------------------------------------------------------------

def gather(cfg: dict, fetcher: Fetcher | None = None, weekly: bool = False) -> dict:
    s = settings(cfg, weekly=weekly)
    f = fetcher or Fetcher(timeout=s["timeout"], budget=s["budget"])

    news = research_news(cfg, f, s)
    comps = [competition_fixtures(e, f) for e in cfg.get("competitions", [])]
    tennis = tennis_top_n(cfg, f)

    # A source that failed is named. Silence would read as "nothing happened".
    notes = sorted(set(f.failures))
    return {
        "news": news,
        "competitions": comps,
        "tennis": tennis,
        "failures": notes,
        "as_of": dt.datetime.now(dt.timezone.utc),
    }


# ---------------------------------------------------------------------------
# Rendering - plain text
# ---------------------------------------------------------------------------

def _fmt_when(iso: str, tz_offset_hours: int = 2) -> str:
    """ESPN timestamps are UTC; the owner is SAST (UTC+2)."""
    if not iso:
        return ""
    try:
        when = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    when = when.astimezone(dt.timezone(dt.timedelta(hours=tz_offset_hours)))
    return when.strftime("%a %d %b %H:%M")


def _team_label(team: dict, state: str) -> str:
    """'Arsenal 2' for a played match, bare 'Arsenal' for one that has not kicked off.

    ESPN reports a not-yet-played match as 0-0, so printing the score
    unconditionally would claim every upcoming fixture is goalless.
    """
    score = team.get("score")
    if state == "pre" or score in (None, ""):
        return team["name"]
    return f"{team['name']} {score}"


def _match_order(row: dict) -> tuple[list[dict], str]:
    """(players in display order, separator). Winner first, ' beat '; else ' vs '.

    One definition shared by the text and HTML renderers, so the two cannot
    disagree about who won.
    """
    players = row["players"]
    winner = next((p for p in players if p.get("winner")), None)
    if winner and len(players) == 2:
        return [winner, next(p for p in players if p is not winner)], " beat "
    return players, " vs "


def _player_label(p: dict) -> str:
    return f"[{p['rank']}] {p['name']}" if p.get("rank") else p["name"]


def _score_line(row: dict) -> str:
    """'Felix Auger-Aliassime beat [4] Ben Shelton', or a plain pairing.

    A finished match has exactly one winner, so the winner is printed first. An
    unplayed match has neither, and is printed as a pairing rather than
    pretending to be a result.
    """
    players, sep = _match_order(row)
    return sep.join(_player_label(p) for p in players)


def render_text(data: dict, today: dt.date | None = None) -> str:
    """The research block for the plain-text digest. Empty string if nothing."""
    out: list[str] = []

    items = [i for i in data["news"]["items"] if i["stories"]]
    if items:
        out.append("WHAT YOU FOLLOW")
        for item in items:
            head = item["label"] + (f"  ({item['sport']})" if item["sport"] else "")
            out.append(f"  {head}")
            for story in item["stories"]:
                who = f" - {story['publisher']}" if story["publisher"] else ""
                out.append(f"    * {story['title']}{who}")
                if story["link"]:
                    out.append(f"      {story['link']}")
        out.append("")

    comps = [c for c in data["competitions"] if c["rows"] or c["error"]]
    if comps:
        out.append("FIXTURES")
        for c in comps:
            if c["error"]:
                out.append(f"  {c['label']}: {c['error']}")
                continue
            scope = (", ".join(c["followed"]) if c["filtered"]
                     else "every team (no team filter set)")
            out.append(f"  {c['label']} - {scope}")
            for r in c["rows"]:
                teams = " vs ".join(_team_label(t, r["state"]) for t in r["teams"])
                state = "" if r["state"] == "pre" else f"  [{r['detail']}]"
                out.append(f"    {_fmt_when(r['when']):<18} {teams}{state}")
        out.append("")

    tennis = data["tennis"]
    if tennis.get("enabled"):
        for tour in tennis["tours"]:
            if not tour["top"]:
                continue
            names = ", ".join(f"{p['rank']}. {p['name']}" for p in tour["top"])
            out.append(f"TENNIS - {tour['tour']} TOP {tennis['top_n']}")
            out.append(f"  Currently: {names}")
            if tour["results"]:
                out.append("  Results:")
                for r in tour["results"]:
                    out.append(f"    {_fmt_when(r['when']):<18} {_score_line(r)}")
                    out.append(f"    {'':<18} {r['tournament']}")
            if tour["upcoming"]:
                out.append("  Coming up:")
                for r in tour["upcoming"]:
                    tag = "  [in progress]" if r["state"] == "in" else ""
                    out.append(f"    {_fmt_when(r['when']):<18} {_score_line(r)}{tag}")
                    out.append(f"    {'':<18} {r['tournament']}")
            if not tour["results"] and not tour["upcoming"]:
                out.append("  No top-5 match in the tournaments being played right now.")
            out.append("")

    if data["failures"]:
        out.append("  A source could not be reached this run: " + "; ".join(data["failures"]))
        out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Rendering - HTML email
# ---------------------------------------------------------------------------

def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def render_html(data: dict, ink: str, muted: str, line: str, accent: str,
                surface: str, soft: str) -> dict:
    """The research block as email-safe HTML, split into its three sections.

    Returns {"news": rows, "fixtures": rows, "tennis": rows} so the digest can
    wrap each in its own titled section, exactly as the text version does.
    Colours are passed in so this module stays independent of the digest's
    palette rather than duplicating it.
    """
    news_rows: list[str] = []
    fixture_rows: list[str] = []
    tennis_rows: list[str] = []
    note_rows: list[str] = []

    items = [i for i in data["news"]["items"] if i["stories"]]
    for item in items:
        news_rows.append(f'<div style="font-size:13px;font-weight:700;color:{ink};'
                         f'margin:0 0 4px">{esc(item["label"])}</div>')
        for story in item["stories"]:
            who = (f'<span style="color:{muted};font-size:12px"> &mdash; '
                   f'{esc(story["publisher"])}</span>') if story["publisher"] else ""
            link = (f'<a href="{esc(story["link"])}" style="color:{ink};'
                    f'text-decoration:none">{esc(story["title"])}</a>'
                    if story["link"] else esc(story["title"]))
            news_rows.append(f'<div style="font-size:13px;color:{ink};margin:0 0 6px;'
                             f'padding-left:10px;border-left:2px solid {line}">{link}{who}</div>')

    comps = [c for c in data["competitions"] if c["rows"] or c["error"]]
    for c in comps:
        if c["error"]:
            fixture_rows.append(f'<div style="font-size:13px;color:{muted};margin:0 0 6px">'
                                f'{esc(c["label"])}: {esc(c["error"])}</div>')
            continue
        scope = (", ".join(c["followed"]) if c["filtered"]
                 else "every team &mdash; no team filter set")
        fixture_rows.append(f'<div style="font-size:13px;font-weight:700;color:{ink};'
                            f'margin:0 0 4px">{esc(c["label"])}'
                            f'<span style="font-weight:400;color:{muted};font-size:12px">'
                            f' &middot; {esc(scope)}</span></div>')
        for r in c["rows"]:
            teams = " vs ".join(
                (f'{esc(t["name"])} <strong>{esc(t["score"])}</strong>'
                 if r["state"] != "pre" and t["score"] not in (None, "")
                 else esc(t["name"]))
                for t in r["teams"])
            badge = ("" if r["state"] == "pre" else
                     f'<span style="color:{muted};font-size:11px"> [{esc(r["detail"])}]</span>')
            fixture_rows.append(f'<div style="font-size:13px;color:{ink};margin:0 0 6px">'
                                f'<span style="color:{muted};font-size:12px">'
                                f'{esc(_fmt_when(r["when"]))}</span> &nbsp;{teams}{badge}</div>')

    tennis = data["tennis"]
    if tennis.get("enabled"):
        for tour in tennis["tours"]:
            if not tour["top"]:
                continue
            names = ", ".join(f'{p["rank"]}. {p["name"]}' for p in tour["top"])
            tennis_rows.append(f'<div style="font-size:13px;font-weight:700;color:{ink};'
                               f'margin:0 0 4px">{esc(tour["tour"])} top {tennis["top_n"]}'
                               f'<span style="font-weight:400;color:{muted};font-size:12px">'
                               f' &middot; currently {esc(names)}</span></div>')
            for heading, group in (("Results", tour["results"]), ("Coming up", tour["upcoming"])):
                if not group:
                    continue
                tennis_rows.append(f'<div style="font-size:12px;font-weight:700;color:{ink};'
                                   f'margin:8px 0 4px">{heading}</div>')
                for r in group:
                    order, sep = _match_order(r)
                    line_parts = []
                    for t in order:
                        tag = f'[{t["rank"]}] ' if t.get("rank") else ""
                        bold = "font-weight:700;" if t.get("winner") else ""
                        line_parts.append(f'<span style="{bold}">{esc(tag + t["name"])}</span>')
                    score = sep.join(line_parts)
                    tag = (f'<span style="color:{muted};font-size:11px"> [in progress]</span>'
                           if r["state"] == "in" else "")
                    tennis_rows.append(f'<div style="font-size:13px;color:{ink};margin:0 0 6px">'
                                       f'<span style="color:{muted};font-size:12px">'
                                       f'{esc(_fmt_when(r["when"]))}</span> &nbsp;{score}{tag}'
                                       f'<span style="color:{muted};font-size:12px"> &middot; '
                                       f'{esc(r["tournament"])}</span></div>')
            if not tour["results"] and not tour["upcoming"]:
                tennis_rows.append(f'<div style="font-size:13px;color:{muted};margin:0 0 6px">'
                                   f'No top-{tennis["top_n"]} match in the tournaments being '
                                   f'played right now.</div>')

    if data["failures"]:
        note_rows.append(f'<div style="font-size:12px;color:{muted};margin:10px 0 0">'
                         f'A source could not be reached this run: '
                         f'{esc("; ".join(data["failures"]))}</div>')

    return {
        "news": "".join(news_rows),
        "fixtures": "".join(fixture_rows),
        "tennis": "".join(tennis_rows) + "".join(note_rows),
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Research what the owner follows.")
    ap.add_argument("--html", action="store_true", help="print the HTML block")
    ap.add_argument("--weekly", action="store_true", help="widen the news window")
    ap.add_argument("--today", help="accepted for symmetry; research uses the live clock")
    args = ap.parse_args()

    cfg = load_follow()
    data = gather(cfg, weekly=args.weekly)
    if args.html:
        print(render_html(data, "#10161d", "#556274", "#e2e7ed", "#13567f", "#ffffff", "#e8f1f8"))
    else:
        print(render_text(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
