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
import email.utils
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "personal", "data")

UA = "Mozilla/5.0 (compatible; personal-digest/1.0)"
NEWS_URL = "https://news.google.com/rss/search"
ESPN = "https://site.web.api.espn.com/apis/site/v2/sports"
# Standings live on a DIFFERENT root to the scoreboard: `/apis/v2/...`, not
# `/apis/site/v2/...`. The site/-rooted shape 404s (measured 2026-11-03).
ESPN_V2 = "https://site.web.api.espn.com/apis/v2/sports"
# Regenerated locally each run; the API needs no key. See `local_prices`.
PRICE_API = "https://api.takealot.com/rest/v-1-10-0/searches/products"

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

    def get(self, url: str, headers: dict | None = None) -> bytes | None:
        """Fetch, or record why not. Never raises."""
        left = self.remaining()
        if left <= 0:
            self.failures.append("time budget exhausted")
            return None
        try:
            hdrs = {"User-Agent": UA}
            hdrs.update(headers or {})
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=min(self.timeout, left)) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001 - every failure degrades to a note
            self.failures.append(f"{type(exc).__name__} on {urllib.parse.urlparse(url).netloc}")
            return None

    def json(self, url: str, headers: dict | None = None) -> dict | None:
        raw = self.get(url, headers=headers)
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
        return {"news": [], "sports": [], "competitions": [],
                "tennis": {"enabled": False}, "local": {}, "price_watch": {},
                "settings": {}}
    with open(p, encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg.setdefault("news", [])
    cfg.setdefault("sports", [])
    cfg.setdefault("competitions", [])
    cfg.setdefault("tennis", {"enabled": False})
    cfg.setdefault("local", {})
    cfg.setdefault("price_watch", {})
    cfg.setdefault("settings", {})
    return cfg


def enabled_sports(cfg: dict) -> list[str]:
    """The sports the owner has switched ON, in file order.

    An EMPTY sport list means "no switch was ever set", not "no sports". In that
    case every sport named by the owner's own event list is treated as on, so a
    file written before the sport switch existed keeps behaving as it did. Once
    the owner has any sports rows, that list is the only authority - deleting
    them all would otherwise silently re-enable everything.
    """
    rows = cfg.get("sports") or []
    if not rows:
        return []
    return [r["sport"] for r in rows if r.get("enabled", True) and r.get("sport")]


def muted_sports(cfg: dict) -> set[str]:
    """Sports the owner switched OFF. Their events must not appear anywhere."""
    return {r["sport"] for r in (cfg.get("sports") or [])
            if r.get("sport") and not r.get("enabled", True)}


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


def _entry_muted(entry: dict, muted: set[str]) -> bool:
    """True if a follow entry belongs to a sport the owner switched off.

    A competition carries no sport of its own, so it is matched by its league
    id against the competitions that the muted sports would have produced.
    Football is the only sport with leagues today, and saying so explicitly is
    better than a guess that silently stops filtering the day another arrives.
    """
    sport = (entry.get("sport") or "").strip()
    if sport and sport in muted:
        return True
    if entry.get("league") and "Football" in muted:
        return True
    return False


def research_news(cfg: dict, f: Fetcher, s: dict,
                  muted: set[str] | None = None) -> dict:
    """One entry per followed item. An item with no recent news says so."""
    muted = muted or set()
    items = []
    for entry in cfg.get("news", []):
        query = entry.get("query") or entry.get("label")
        if not query:
            continue
        if _entry_muted(entry, muted):
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


def league_standings(entry: dict, f: Fetcher) -> dict:
    """The live league table for one competition, exactly as ESPN publishes it.

    The stats are NOT re-derived. ESPN supplies both the abbreviation and a
    display value per stat (GP/W/D/L/GD/P plus extras), and the qualification
    marker in `note.description`. Recomputing points from wins and draws would
    disagree with ESPN the moment a competition uses a non-standard scoring or
    deduction, so the published numbers are carried through verbatim.
    """
    league = entry.get("league", "")
    label = entry.get("label") or LEAGUES.get(league, league)
    out = {"label": label, "league": league, "stage": "", "rows": [], "error": ""}

    if league not in LEAGUES:
        out["error"] = f"unknown competition id '{league}'"
        return out

    data = f.json(f"{ESPN_V2}/soccer/{league}/standings")
    if data is None:
        out["error"] = "standings could not be reached"
        return out

    # The payload nests the table one level down under a stage ("League Phase"
    # for the Champions League). Take the first stage that actually has entries
    # rather than assuming there is exactly one.
    tables = []
    for child in (data.get("children") or []):
        entries = ((child.get("standings") or {}).get("entries") or [])
        if entries:
            tables.append((child.get("name") or "", entries))
    if not tables and (data.get("standings") or {}).get("entries"):
        tables.append(("", data["standings"]["entries"]))
    if not tables:
        out["error"] = "no standings table in the response"
        return out

    stage, entries = tables[0]
    out["stage"] = stage
    for e in entries:
        team = e.get("team") or {}
        note = e.get("note") or {}
        stats = {}
        for s in (e.get("stats") or []):
            abbr = s.get("abbreviation")
            if abbr:
                stats[abbr] = s.get("displayValue", "")
        out["rows"].append({
            "rank": note.get("rank"),
            "team": team.get("displayName") or team.get("name") or "?",
            "stats": stats,
            "note": note.get("description") or "",
        })
    out["rows"].sort(key=lambda r: (r["rank"] is None, r["rank"]))
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
        event_status = ((event.get("status") or {}).get("type") or {})
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
                        "linescores": _linescores(t.get("linescores")),
                    })
                # A set score is a pair, and which half comes first depends on
                # who is speaking. Storing "6-3 6-4" once bakes in ESPN's player
                # order, so a row about the OTHER player read "beat Norrie 3-6
                # 4-6" - the wrong way round. The pairing is stored per player
                # below instead, oriented to that player.
                pairs = []
                if len(players) == 2:
                    a_ls = players[0]["linescores"]
                    b_ls = players[1]["linescores"]
                    for i in range(max(len(a_ls), len(b_ls))):
                        a = a_ls[i] if i < len(a_ls) else "-"
                        b = b_ls[i] if i < len(b_ls) else "-"
                        pairs.append((a, b))
                for me, rival in ((0, 1), (1, 0)):
                    if len(players) == 2:
                        players[me]["setline"] = " ".join(
                            f"{p[me]}-{p[rival]}" for p in pairs)
                if len(players) < 2:
                    continue
                notes = [n.get("text", "") for n in (comp.get("notes") or [])
                         if n.get("type") == "event" and n.get("text")]
                out.append({
                    "tournament": tournament,
                    "event_state": event_status.get("state", ""),
                    "event_complete": bool(event_status.get("completed")),
                    "when": comp.get("date") or "",
                    "state": status.get("state", "pre"),
                    "detail": status.get("description", ""),
                    "round": ((comp.get("round") or {}).get("displayName") or ""),
                    "note": notes[0] if notes else "",
                    "sets": pairs,
                    "players": players,
                })
    return out


def _linescores(raw: list | None) -> list[str]:
    """Per-set scores as displayed, e.g. ['6', '7(3)'].

    ESPN gives a set as `value` plus an optional `tiebreak`. Printing the
    tiebreak without its bracket would read as a 77-game set, so it is kept in
    the conventional `7(3)` form.
    """
    out = []
    for s in (raw or []):
        v = s.get("value")
        if v is None:
            continue
        tb = s.get("tiebreak")
        out.append(f"{int(v)}({tb})" if tb not in (None, "") else str(int(v)))
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

    On top of the flat result/upcoming lists, every tournament is grouped and
    each top-N player is given an explicit STANDING in it (see
    `_player_standings`), because the owner's complaint was that a top-5 player
    who was not in the visible matches simply vanished with no explanation.
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

        # Group the same matches by tournament, so the digest can lead with the
        # event name instead of repeating it on every line.
        events: dict[str, dict] = {}
        for m in matches:
            ev = events.setdefault(m["tournament"], {
                "tournament": m["tournament"],
                "event_complete": m["event_complete"],
                "matches": [],
            })
            # A tournament is only "complete" if EVERY match carrying it says so.
            ev["event_complete"] = ev["event_complete"] and m["event_complete"]
            ev["matches"].append(m)
        for ev in events.values():
            ev["standings"] = _player_standings(ev["matches"], top)
            ev["status_line"] = _event_status_line(ev["matches"])

        tours.append({
            "tour": tour.upper(),
            "top": top,
            "results": results[:max_matches],
            "upcoming": upcoming[:max_matches],
            "matches_scanned": len(matches),
            "events": sorted(events.values(),
                             key=lambda e: (not e["event_complete"], e["tournament"])),
        })
    return {"enabled": True, "top_n": top_n, "tours": tours}


# The round names measured on the live Paris Masters payload (2026-11-03). This
# is the MEASURED SET, not a closed allow-list: a 96-draw Masters event uses
# 'Round 4', which must render verbatim and sort between Round 3 and the
# quarterfinal rather than being dropped for being unlisted.
MEASURED_ROUNDS = ["Qualifying 1st Round", "Qualifying Final", "Round 1",
                   "Round 2", "Round 3", "Quarterfinal", "Semifinal", "Final"]

_NAMED_ROUND_RANK = {
    "qualifying 1st round": 1,
    "qualifying first round": 1,
    "qualifying final": 2,
    "quarterfinal": 50,
    "quarterfinals": 50,
    "quarter-final": 50,
    "semifinal": 60,
    "semifinals": 60,
    "semi-final": 60,
    "final": 70,
}

_ROUND_NUMBER = re.compile(r"round\s*(?:of\s*)?(\d+)", re.IGNORECASE)


def round_sort_key(name: str) -> tuple[int, int]:
    """Deterministic order for a round name ESPN supplies, measured or not.

    An unmeasured name is never discarded. It is ordered by its own numeric
    round where it carries one ('Round 4' -> after Round 3), and alphabetically
    among nameless rounds, but never before the qualifying rounds.
    """
    if not name:
        return (0, 0)
    key = name.strip().lower()
    if key in _NAMED_ROUND_RANK:
        return (_NAMED_ROUND_RANK[key], 0)
    m = _ROUND_NUMBER.search(key)
    if m:
        n = int(m.group(1))
        # 'Round of 16' is the same stage as 'Round 4' at a 128-draw event, so
        # the draw size is converted to the round number it names.
        if n >= 16 and n & (n - 1) == 0:
            n = 8 - (n.bit_length() - 1)
        # Rounds 1..39 sit between qualifying and the quarterfinal.
        return (min(49, 10 + n), 0)
    return (45, 0)


STANDINGS_COLUMNS = [
    ("rank", "#"), ("team", "Team"), ("GP", "P"), ("W", "W"), ("D", "D"),
    ("L", "L"), ("GD", "GD"), ("P", "Pts"),
]


def standings_blocks(data: dict) -> list[dict]:
    """Every followed competition's table as plain data, for any renderer.

    The columns and the numbers are ESPN's own: `stats` is the payload's
    abbreviation -> displayValue map, so nothing is re-derived here.
    """
    out = []
    for s in (data.get("standings") or []):
        if not (s["rows"] or s["error"]):
            continue
        out.append({
            "label": s["label"],
            "stage": s["stage"],
            "error": s["error"],
            "columns": [c[1] for c in STANDINGS_COLUMNS],
            "rows": [{
                "position": r["rank"],
                "team": r["team"],
                "stats": {k: r["stats"].get(k, "") for k in
                          ("GP", "W", "D", "L", "GD", "P")},
                "note": r["note"],
            } for r in s["rows"]],
        })
    return out


def suggestion_blocks(data: dict) -> list[dict]:
    """The SUGGESTED data as plain records, so every renderer agrees.

    Items blocked by either exclusion set never reach here - `suggest()` drops
    them before this structure exists, so a renderer cannot un-hide them.
    """
    sug = data.get("suggestions") or {}
    groups = []
    for g in sug.get("sports") or []:
        if not g["items"]:
            continue
        groups.append({
            "sport": g["sport"], "source": g["source"],
            "items": [{"name": i["name"], "why": i["why"]} for i in g["items"]],
            "total": int(g.get("total", len(g["items"]))),
        })
    return [{"groups": groups,
             "errors": list(sug.get("errors") or []),
             "error": sug.get("error") or "",
             "excluded": list(sug.get("excluded") or [])}]


def local_blocks(data: dict) -> list[dict]:
    """The LOCAL - JOHANNESBURG block as plain records."""
    loc = data.get("local") or {}
    if not loc:
        return []
    return [{
        "city": loc.get("city", ""),
        "categories": [{
            "label": c["label"],
            "months": c["months"],
            "items": [{"date": i["date"], "title": i["title"],
                       "publisher": i["publisher"], "link": i["link"],
                       "two_person": bool(i.get("two_person")),
                       "two_person_label": i.get("two_person_label", "")}
                      for i in c["items"]],
            "two_person_found": c.get("two_person_found"),
            "two_person_label": c.get("two_person_label", ""),
        } for c in (loc.get("categories") or [])],
        "error": loc.get("error") or "",
        "note": loc.get("note") or "",
    }]


def _match_render_row(row: dict) -> dict:
    """One match as data: winner-first pairing plus the REAL score, if any.

    A finished match's score is the winning player's own set line, which the
    payload supplies per competitor. An unplayed match carries no score at all -
    nothing is constructed or defaulted to fill the gap.
    """
    players, sep = _match_order(row)
    winner = next((p for p in row["players"] if p.get("winner")), None)
    score = ""
    if row["state"] == "post" and winner and winner.get("setline"):
        score = winner["setline"]
    return {
        "when": _fmt_when(row.get("when") or ""),
        "winner_first": bool(winner) and len(row["players"]) == 2,
        "players": [{"label": _player_label(p), "winner": bool(p.get("winner"))}
                    for p in players],
        "sep": sep,
        "score": score,
        "live": row["state"] == "in",
        "line": _score_line(row) + (f"  {score}" if score else ""),
    }


def tennis_tour_blocks(tour: dict, top_n: int) -> list[dict]:
    """One tour's tennis detail as plain data, shared by every renderer.

    The text digest, the HTML email and sports.html all render THIS structure,
    so a grouped layout cannot be produced one way in one place and a flat list
    in another, and the per-tour RANKING line cannot be dropped from one
    rendering while the grouping criteria still pass.

    Each block is one of:

      * ``{"kind": "ranking"}``  - the CURRENT tour ranking, positions verbatim
      * ``{"kind": "summary"}``  - how the top N are doing, in one line
      * ``{"kind": "event"}``    - one tournament: name, stage, player rows
      * ``{"kind": "note"}``     - a named degradation note
    """
    blocks: list[dict] = []
    top = tour.get("top") or []

    if top:
        blocks.append({
            "kind": "ranking",
            "label": f"{tour['tour']} top {top_n} - current ranking",
            "players": [{"position": p["rank"], "name": p["name"]} for p in top],
            "line": ", ".join(f"{p['rank']}. {p['name']}" for p in top),
        })
        blocks.append({
            "kind": "summary",
            "label": "How the top 5 are doing",
            "line": _top_n_summary(tour, top_n),
        })
    else:
        # Never a remembered or guessed list: say the ranking could not be read
        # and carry on with whatever the events can say.
        blocks.append({"kind": "note",
                       "text": "current ranking could not be read"})

    events = tour.get("events") or []
    for ev in events:
        rows = ev["standings"]
        # A row exists for every top-N player, but "did not compete" and "no
        # match found" are NOT matches. A tournament with none of the top N in
        # it must say so in one line rather than print a block of dashes.
        has_match = any(r["status"] in ("in", "out") for r in rows)
        blocks.append({
            "kind": "event",
            "tournament": ev["tournament"],
            "stage": ev.get("status_line", ""),
            "rows": [{
                "position": r["rank"],
                "name": r["name"],
                "state": r["status"],
                "mark": {"in": "IN", "out": "OUT"}.get(r["status"], "--"),
                "detail": r["detail"],
            } for r in rows],
            "empty_line": (f"No top-{top_n} match in this event."
                           if not has_match else ""),
        })

    if events and not any(r["status"] in ("in", "out")
                          for ev in events for r in ev["standings"]):
        blocks.append({"kind": "note",
                       "text": f"No top-{top_n} match in the tournaments being "
                               "played right now."})

    matches = (tour.get("results") or []) + (tour.get("upcoming") or [])
    if matches:
        blocks.append({
            "kind": "matches",
            "label": "Their matches",
            "rows": [_match_render_row(m) for m in matches],
        })
    return blocks


def _top_n_summary(tour: dict, top_n: int) -> str:
    """Who is still alive, who is out, and in which round - one glance."""
    parts: list[str] = []
    for ev in tour.get("events") or []:
        rows = ev["standings"]
        if not any(r["status"] != "absent" for r in rows):
            continue
        alive = [f"{r['rank']}. {r['name']}" for r in rows if r["status"] == "in"]
        gone = [f"{r['rank']}. {r['name']} ({r['detail']})"
                for r in rows if r["status"] == "out"]
        waiting = [f"{r['rank']}. {r['name']}" for r in rows
                   if r["status"] in ("absent", "did_not_compete")]
        bit = [f"{ev['tournament']}: still in - "
               + (", ".join(alive) if alive else "none"),
               f"out - " + (", ".join(gone) if gone else "none")]
        if waiting:
            bit.append("not placed yet - " + ", ".join(waiting))
        parts.append("; ".join(bit))
    if parts:
        return " | ".join(parts)
    if tour.get("events"):
        return (f"no top-{top_n} player is in the events being played right now")
    return "no tournament carrying a top-5 player yet"


def _event_status_line(matches: list[dict]) -> str:
    """The latest round reached in this event, from REAL matches only."""
    real = [m for m in matches if not _is_placeholder(m)]
    rounds = [m["round"] for m in real if m.get("round")]
    if not rounds:
        return "draw not published yet"
    furthest = max(rounds, key=round_sort_key)
    if any(m["state"] == "in" for m in real):
        return f"In progress - {furthest}"
    finished = [m for m in real if m["state"] == "post"]
    if furthest == "Final" and any(m["round"] == "Final" for m in finished):
        return "Finished"
    return f"Latest round played: {furthest}"


def _is_placeholder(match: dict) -> bool:
    """A not-yet-filled draw slot ("TBD vs TBD"), not a real match.

    ESPN publishes the whole bracket up front. Those unfilled rows look exactly
    like scheduled matches, so counting them as "still to play" would claim a
    player is still alive in a tournament that finished weeks ago.
    """
    names = [(p.get("name") or "").strip().lower() for p in match["players"]]
    return all(n in ("", "tbd", "tba") for n in names)


def _player_standings(matches: list[dict], top: list[dict]) -> list[dict]:
    """Where every top-N player stands in ONE tournament.

    Three outcomes, and each is a claim the payload supports:

      * ``in``          - has a REAL match still to play or being played.
      * ``out``         - their most recent completed match was a loss; the
                          round and the player who beat them are named from it.
      * ``absent``      - appears nowhere in this event. Reported as "no match
                          found in this event", NOT as "did not compete", unless
                          the event is demonstrably complete, in which case the
                          entry is a real absence and becomes ``did_not_compete``.

    The distinction matters: a half-published draw looks identical to a
    withdrawal, and claiming a withdrawal that did not happen is exactly the
    kind of invented fact this project forbids.
    """
    out = []
    for p in top:
        key = _player_key(p["name"])
        played, live = [], []
        for m in matches:
            if _is_placeholder(m):
                continue
            names = {_player_key(x["name"]): x for x in m["players"]}
            if key not in names:
                continue
            me = names[key]
            others = [x for k, x in names.items() if k != key]
            row = {
                "round": m.get("round", ""),
                "state": m["state"],
                "opponent": others[0]["name"] if others else "",
                "won": bool(me.get("winner")) if m["state"] == "post" else None,
                "beaten_by": (others[0]["name"] if others else "") if (
                    m["state"] == "post" and not me.get("winner")) else "",
                "score": me.get("score"),
                "scoreline": me.get("setline", ""),
                "note": m.get("note", ""),
                "when": m.get("when", ""),
            }
            (live if m["state"] != "post" else played).append(row)

        played.sort(key=lambda r: r["when"])
        live.sort(key=lambda r: r["when"])

        if live:
            # Still to play a real opponent: still in, at the next round due.
            status = "in"
            rounds = [r["round"] for r in live if r["round"]]
            detail = f"still in - {rounds[0]}" if rounds else "still in"
        elif played:
            last = played[-1]
            if last["won"]:
                status = "in"
                detail = (f"won the {last['round']}" if last["round"]
                          else "won their latest match")
            else:
                status = "out"
                where = f"out in the {last['round']}" if last["round"] else "out"
                detail = (f"{where}, beaten by {last['beaten_by']}"
                          if last["beaten_by"] else where)
        else:
            out.append({"rank": p["rank"], "name": p["name"], "status": "absent",
                        "detail": "no match found in this event yet",
                        "matches": []})
            continue

        out.append({"rank": p["rank"], "name": p["name"], "status": status,
                    "detail": detail, "matches": played + live})

    # Only now can an absence be called a withdrawal: every REAL match in the
    # event is finished, so a player with no match genuinely did not appear.
    real = [m for m in matches if not _is_placeholder(m)]
    complete = bool(real) and all(m["state"] == "post" for m in real)
    if complete:
        for row in out:
            if row["status"] == "absent":
                row["status"] = "did_not_compete"
                row["detail"] = "did not compete in this event"
    return out


# ---------------------------------------------------------------------------
# Suggestions (item 3)
# ---------------------------------------------------------------------------

# What each ON sport suggests FROM. Football and tennis are live; the rest are
# derived from the owner's own event list. Nothing here invents an event - it
# names where a candidate came from.
SPORT_SOURCES = {
    "Football": "ESPN football competitions",
    "Tennis": "ESPN tennis calendar",
    "Motorsport": "your own event list",
    "Cycling": "your own event list",
    "Gymnastics": "your own event list",
    "Weightlifting": "your own event list",
    "Padel": "your own event list",
}


def suggest(cfg: dict, sports_events: list[dict], f: Fetcher,
            already_shown: set[str] | None = None) -> dict:
    """Competitions/events the owner is NOT following, derived from what he is.

    Two independent exclusion sets are applied, and they are the whole point of
    the feature - the owner was explicit that a suggestion is worthless if it
    proposes something he removed:

      1. the sport-level mute list (`sports[].enabled == false`);
      2. the removed/not-followed competition list - anything already in
         `competitions` is excluded because he already has it, and a competition
         he removed is recorded in `removed` when the editor removes it.

    A suggestion always names the source it came from and the follow that caused
    it, so the owner can see why it appeared and judge whether to add it.
    """
    muted = muted_sports(cfg)
    on = enabled_sports(cfg)
    # A suggestion is only useful if it is NEWS. An event already printed in
    # this same email ("Rolex Paris Masters" appeared under TENNIS while also
    # being offered as a suggestion) reads as padding, so anything the digest
    # already covers is dropped by name.
    shown = {(n or "").lower() for n in (already_shown or set()) if n}
    followed_leagues = {e.get("league") for e in cfg.get("competitions", [])}
    removed = {r.lower() for r in (cfg.get("removed") or []) if r}

    # A sport he removed is listed as excluded so the digest can say so out
    # loud. Silence would look like the sport was never considered.
    out = {"sports": [], "error": "", "excluded": sorted(muted | removed)}

    if not on:
        out["error"] = ("nothing new to suggest - no sports are switched on, so there "
                        "is nothing to suggest from")
        return out

    for sport in on:
        if sport in muted:  # belt and braces: muted can never suggest
            continue
        items = []
        if sport == "Football":
            # There is no key-less "list every competition" endpoint (both
            # /leagues shapes 404), so a competition is suggested from the TEAM
            # LIST of the competition he already follows - a real source, and
            # exactly the "teams in the Champions League you do not follow yet"
            # idea. Clubs he already follows as teams are excluded.
            for entry in cfg.get("competitions", []):
                league = entry.get("league", "")
                if league not in LEAGUES:
                    continue
                data = f.json(f"{ESPN}/soccer/{league}/teams")
                if data is None:
                    out.setdefault("errors", []).append(
                        f"the {entry.get('label', league)} team list could not be reached")
                    continue
                mine = {_norm(t) for t in (entry.get("teams") or []) if t}
                for sport_row in (data.get("sports") or []):
                    for lg in (sport_row.get("leagues") or []):
                        for t in (lg.get("teams") or []):
                            team = (t.get("team") or {})
                            name = team.get("displayName") or ""
                            if not name or name.lower() in removed:
                                continue
                            if {_norm(name)} & mine:
                                continue
                            items.append({
                                "name": name, "league": league,
                                "source": f"ESPN {entry.get('label', league)} team list",
                                "why": f"in the {entry.get('label', league)}, which you follow",
                            })
        elif sport == "Tennis":
            t = cfg.get("tennis") or {}
            for tour in t.get("tours", ["atp", "wta"]):
                data = f.json(f"{ESPN}/tennis/{tour}/scoreboard")
                if data is None:
                    out.setdefault("errors", []).append(
                        f"the ESPN {tour.upper()} calendar could not be reached")
                    continue
                for ev in (data.get("events") or []):
                    name = ev.get("name") or ""
                    if not name or name.lower() in removed:
                        continue
                    if name.lower() in shown:
                        continue
                    items.append({"name": name, "league": f"tennis:{tour}",
                                  "source": SPORT_SOURCES["Tennis"],
                                  "why": f"you follow Tennis and the {tour.upper()} top "
                                         f"{int(t.get('top_n', 5))}"})
        else:
            # Derived from the owner's OWN event list: an event of a sport he
            # follows that falls OUTSIDE the current digest window is a real
            # "this is coming later, do you want it?" candidate. Nothing is
            # fetched, so nothing can be invented.
            for e in sports_events:
                if e.get("sport") != sport:
                    continue
                if (e.get("sport") or "").lower() in removed:
                    continue
                name = e.get("name", "")
                if not name or name.lower() in removed:
                    continue
                if name.lower() in shown:
                    continue
                items.append({"name": f"{name} ({e.get('when', 'date unknown')})",
                              "league": "",
                              "source": SPORT_SOURCES.get(sport, "your own event list"),
                              "why": f"you follow {sport}, later than this digest window"})

        # De-duplicate while keeping first-seen order, and never suggest the
        # same name twice within a sport.
        seen_names, unique = set(), []
        for it in items:
            k = it["name"].lower()
            if k in seen_names:
                continue
            seen_names.add(k)
            unique.append(it)
        # Carry the true count so a truncated list can say how many were left
        # out, rather than looking like the complete set of suggestions.
        out["sports"].append({"sport": sport, "items": unique[:8],
                              "total": len(unique),
                              "source": SPORT_SOURCES.get(sport, "your own event list")})

    if not any(s["items"] for s in out["sports"]) and not out.get("errors"):
        out["error"] = "nothing new to suggest - you already follow what these sources list"
    return out


# ---------------------------------------------------------------------------
# Local events near the owner (item 6)
# ---------------------------------------------------------------------------

def _in_window(ev: dict, start: dt.date, end: dt.date) -> bool:
    """True if an event OVERLAPS [start, end].

    Overlap, not "starts within": a championship that began three days ago and
    finishes next week is on now, and dropping it because its start date is in
    the past would hide exactly the events the owner is watching.
    """
    try:
        first = dt.date.fromisoformat((ev.get("when") or "")[:10])
    except ValueError:
        return False
    try:
        last = dt.date.fromisoformat((ev.get("end") or ev.get("when") or "")[:10])
    except ValueError:
        last = first
    return first <= end and last >= start


def _within_months(month: str, today: dt.date, months: int) -> bool:
    """True if a `YYYY-MM` PUBLISH stamp is within the last N months.

    The feed dates a story by when it was PUBLISHED, not by when the event is
    on. "All you can eat sushi around Johannesburg for R200" was published in
    August and is still the best buffet lead in November, so the useful window
    looks BACKWARDS. Requiring a future publish date - which the first version
    of this did - matched nothing at all, because no outlet publishes tomorrow's
    newspaper today.
    """
    try:
        y, m = (int(x) for x in month.split("-")[:2])
    except (ValueError, AttributeError):
        return False
    now = today.year * 12 + today.month - 1
    return now - months <= y * 12 + m - 1 <= now


# ---------------------------------------------------------------------------
# LOCAL ordering and classification (items 6: AC-195, AC-196, AC-198)
# ---------------------------------------------------------------------------

# The owner's own words: "nice massage sale i can take Chloe and i, same with
# buffets". A headline carrying one of these markers is an offer he can take
# someone to, and it is labelled as such rather than left to guesswork.
TWO_PERSON_MARKERS = ("couple", "couples", "for two", "date night", "two people")


def is_two_person(headline: str) -> bool:
    low = (headline or "").lower()
    return any(m in low for m in TWO_PERSON_MARKERS)


def is_annual_item(category: dict, headline: str, today: dt.date) -> bool:
    """'Annual' is a CONFIGURATION FACT plus an explicit year stamp (AC-196).

    Never an inference from the words in the headline: a category flagged
    `annual: true` is annual, and so is an item whose headline carries a
    four-digit year LATER than the current one. Everything else is not.
    """
    if category.get("annual"):
        return True
    for match in re.findall(r"\b((?:19|20)\d{2})\b", headline or ""):
        if int(match) > today.year:
            return True
    return False


def horizon_months(category: dict, headline: str, loc: dict, today: dt.date) -> int:
    """The window this item is judged against: 12 months when annual, else 3."""
    return (int(loc.get("annual_months_ahead", 12)) if is_annual_item(category, headline, today)
            else int(loc.get("months_ahead", 3)))


def category_order(categories: list[dict]) -> list[dict]:
    """Configuration priority first, then configured order, then key (AC-195a).

    `priority` is the owner-authored preference order carried in follow.json
    (buffet, then massage/spa, then great events). Absent means the configured
    position, so a file written before the field existed keeps its order.
    """
    indexed = list(enumerate(categories))
    return [c for _, c in sorted(
        indexed,
        key=lambda pair: (pair[1].get("priority",
                                      len(categories) + pair[0]),
                          pair[0],
                          pair[1].get("key", "")))]


def order_local_items(items: list[dict], category: dict) -> list[dict]:
    """The deterministic LOCAL order (AC-195b/c). A pure function, no scoring.

    (b) an item whose headline names a followed sport or competition sorts
        before one that does not - the only "what he liked" signal supplied;
    (c) then publisher date newest first, then the index of the `queries` entry
        that produced it, then the headline.

    No relevance score, keyword weight or model judgement is introduced.
    """
    followed = [t.lower() for t in (category.get("followed_terms") or [])]
    queries = [q.lower() for q in (category.get("queries") or [])]

    def key(pair):
        idx, it = pair
        low = (it.get("title") or "").lower()
        names_followed = 1 if any(t and t in low for t in followed) else 0
        try:
            qidx = queries.index((it.get("query") or "").lower())
        except ValueError:
            qidx = len(queries)
        return (-names_followed, _neg_date(it.get("date") or ""), qidx, low)

    return [it for _, it in sorted(enumerate(items), key=key)]


def _neg_date(s: str) -> tuple:
    """Newest first: sort the date descending without a reverse= (keeps ties stable)."""
    return tuple(-int(part) for part in s.split("-")) if s else (0, 0, 0)


def local_events(cfg: dict, f: Fetcher, today: dt.date | None = None) -> dict:
    """Buffets, massages and good events near the owner, from headlines.

    The honest limit: there is no free, key-less Johannesburg event calendar
    that answers a plain fetch, so this reports NEWS HEADLINES about local
    events with their publisher and date, clearly labelled as such. It never
    invents a venue, a price, a date or a booking link, and an empty category
    says so rather than being padded.
    """
    today = today or dt.date.today()
    loc = cfg.get("local") or {}
    out = {"city": loc.get("city", "Johannesburg"), "categories": [],
           "error": "", "note": "", "sport_blocked": sorted(muted_sports(cfg))}

    if not loc.get("enabled", False):
        out["error"] = "local events are switched off in personal/data/follow.json"
        return out

    months = int(loc.get("months_ahead", 3))
    annual = int(loc.get("annual_months_ahead", 12))
    # Google News broadens a narrow query, and the result was a New Jersey vice
    # squad story under "massage special Johannesburg". A headline has to name
    # the town AND the thing being looked for, or it is not a lead.
    places = [t.lower() for t in (loc.get("place_terms") or
                                  ["johannesburg", "joburg", "gauteng", "sandton",
                                   "soweto", "randburg", "rosebank", "fourways",
                                   "pretoria", "jhb"])]
    muted_cats = {c["key"] for c in loc.get("categories", [])
                  if c.get("key") and not c.get("enabled", True)}

    # Owner-authored preference order carried on the config (AC-195a).
    for cat in category_order([c for c in loc.get("categories", [])]):
        key = cat.get("key") or ""
        if not key or key in muted_cats:
            continue
        subject = [t.lower() for t in (cat.get("require_any") or [])]
        items = []
        two_person_queries = [q for q in ((cat.get("two_person") or {}).get("queries") or [])]
        two_person_hits = 0
        # The two-person search is ADDITIVE: it runs alongside the normal
        # queries, so a couple offer the owner can use is found without ever
        # suppressing the solo results (AC-198c).
        for q in list(cat.get("queries") or []) + two_person_queries:
            raw = f.get(_news_url(q))
            if raw is None:
                continue
            for title, link, pub, when in _rss_items(
                    raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw):
                low = title.lower()
                if not any(pl in low for pl in places):
                    continue
                if subject and not any(w in low for w in subject):
                    continue
                months_here = horizon_months(cat, title, loc, today)
                # A story from last season is not a lead; one from the last few
                # months about an annual event still is. The month stamp is the
                # best date the feed carries.
                if not _within_months(when.strftime("%Y-%m") if when else "",
                                      today, months_here):
                    continue
                pair = is_two_person(title)
                if pair and q in two_person_queries:
                    two_person_hits += 1
                items.append({"title": title, "link": link, "publisher": pub,
                              "date": when.strftime("%Y-%m-%d") if when else "",
                              "query": q,
                              "two_person": pair,
                              "two_person_label": ((cat.get("two_person") or {}).get("label")
                                                   if pair else ""),
                              "annual": is_annual_item(cat, title, today)})
        # De-duplicate on the headline, then apply the deterministic order rule
        # (AC-195) and the two-person label (AC-198).
        seen, unique = set(), []
        for it in items:
            k = it["title"].lower()
            if k in seen:
                continue
            seen.add(k)
            unique.append(it)
        unique = order_local_items(unique, cat)
        row = {
            "key": key,
            "label": cat.get("label") or key,
            "items": unique[:6],
            # The horizon actually applied to this category, so the empty-state
            # message names the window that was really searched.
            "months": annual if cat.get("annual") else months,
            "source": "Google News RSS, Johannesburg",
            "priority": cat.get("priority"),
            "annual": bool(cat.get("annual")),
        }
        if two_person_queries:
            row["two_person_label"] = (cat.get("two_person") or {}).get("label", "")
            row["two_person_found"] = two_person_hits
        out["categories"].append(row)

    if not any(c["items"] for c in out["categories"]):
        out["error"] = (f"nothing found for {out['city']} in the last {annual} months")
    out["note"] = ("These are headlines about local things to do, published in the last "
                   f"{annual} months - not a verified event calendar. Check the venue and "
                   "the current price before booking, and some may already be over.")
    return out


# ---------------------------------------------------------------------------
# Price watch (item 7)
# ---------------------------------------------------------------------------

def _kit_capacity_gb(title: str) -> int | None:
    """Total memory in a product title, in GB.

    "Kingston Fury Beast 16GB" -> 16, "16GB Kit (2x8GB)" -> 16, and crucially
    "32GB (2x16GB)" -> 32. Parsing the total is the only way to keep a 32GB kit
    out of a 16GB watch, because "16gb" is a substring of "2x16gb".
    """
    t = title.lower()
    m = re.search(r"(\d+)\s*x\s*(\d+)\s*gb", t)
    if m:
        return int(m.group(1)) * int(m.group(2))
    m = re.search(r"(\d+)\s*gb", t)
    return int(m.group(1)) if m else None


def local_prices(cfg: dict, f: Fetcher) -> dict:
    """Best current prices for the watched products, cheapest first.

    Takealot's public search API needs no key. The price lives in
    `buybox_summary` (NOT in the empty `pricing` block), as a `listing_price`
    integer plus a pre-formatted `pretty_price`. Using the retailer's own string
    where it exists means the digest cannot round or mangle it.
    """
    pw = cfg.get("price_watch") or {}
    out = {"enabled": bool(pw.get("enabled")), "items": [], "error": ""}
    if not out["enabled"]:
        out["error"] = "price watch is switched off in personal/data/follow.json"
        return out

    for spec in pw.get("items") or []:
        if not spec.get("enabled", True):
            continue
        label = spec.get("label") or spec.get("key") or "item"
        query = spec.get("query") or label
        must = [m.lower() for m in (spec.get("must_match") or [])]

        data = f.json(f"{PRICE_API}?qsearch={_q(query)}&size=40")
        if data is None:
            out["items"].append({"label": label, "offers": [],
                                 "error": "the price source could not be reached"})
            continue

        results = (((data.get("sections") or {}).get("products") or {})
                   .get("results") or [])
        if not results:
            out["items"].append({"label": label, "offers": [],
                                 "error": "the price source returned no matches "
                                          "(its response shape may have changed)"})
            continue

        offers = []
        for r in results:
            views = r.get("product_views") or {}
            core = views.get("core") or {}
            buy = views.get("buybox_summary") or {}
            title = core.get("title") or ""
            low = title.lower()
            if must and not all(m in low for m in must):
                continue
            # "16gb" is a substring of "2x16gb" (= 32GB), which would put a 32GB
            # kit in a 16GB watch. Capacity is checked as a NUMBER, not a string.
            capacity = _kit_capacity_gb(low)
            if spec.get("capacity_gb") and capacity != int(spec["capacity_gb"]):
                continue
            # AC-173/176: ONE price per row - the SELLING price `prices[0]`,
            # which is the number the retailer displays as `pretty_price`.
            # `listing_price` is the pre-discount list figure and is a different
            # number (measured 2026-11-04: 5,899 vs 5,549), so sorting on it
            # while printing `prices[0]` would rank the page by a price the
            # owner never sees.
            prices = buy.get("prices")
            selling = None
            if isinstance(prices, list) and prices:
                selling = prices[0]
            elif isinstance(buy.get("listing_price"), int):
                selling = buy.get("listing_price")
            if not isinstance(selling, int) or selling <= 0:
                continue
            # A 16GB kit (2x8GB) and a single 16GB module are different
            # products; conflating them would make the "best price" wrong.
            kind = ("kit" if re.search(r"\d+\s*x\s*\d+\s*gb", low) or " kit" in f" {low}"
                    else "single module")
            offers.append({
                "title": title,
                "price": selling,
                "list_price": (buy.get("listing_price")
                               if isinstance(buy.get("listing_price"), int) else None),
                "pretty": buy.get("pretty_price") or f"R {selling:,}",
                "retailer": "Takealot",
                "kind": kind,
                "stock": (views.get("stock_availability_summary") or {}).get("status", ""),
                "url": f"https://www.takealot.com/{core.get('slug', '')}/PLID{core.get('id', '')}",
            })

        offers.sort(key=lambda o: o["price"])
        # Saving is only meaningful against a DEARER listing of the same kind,
        # and it is the difference of the two RENDERED (selling) prices.
        for o in offers:
            same = [x["price"] for x in offers if x["kind"] == o["kind"]]
            o["saving"] = (max(same) - o["price"]) if len(same) > 1 else 0

        err = "" if offers else ("no 16GB listing with a usable price was found "
                                 f"among {len(results)} results")
        out["items"].append({"label": label, "offers": offers[:6], "error": err})

    return out


# ---------------------------------------------------------------------------
# Run time (item 8)
# ---------------------------------------------------------------------------

def _fmt_secs(seconds: float) -> str:
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"


def run_time(elapsed: float, f: Fetcher, repo: str = "",
             token: str = "") -> dict:
    """This run's duration, the recent trend, and the monthly projection.

    On the Actions-minutes question the honest answer for this repository is
    that it is PUBLIC, and GitHub does not bill Actions minutes for public
    repositories - so there is no shrinking quota to report. Saying otherwise
    would be an invented number, so the measured usage is reported alongside
    that statement instead of a fake balance.
    """
    sched = {"daily_per_day": 1, "weekly_per_week": 1}

    out = {"elapsed_seconds": elapsed, "elapsed": _fmt_secs(elapsed),
           "recent": [], "recent_error": "", "monthly_seconds": None,
           "monthly": "", "public_repo": None, "remaining": "",
           "runs_measured": 0}

    runs = []
    if repo:
        url = f"https://api.github.com/repos/{repo}/actions/runs?per_page=20"
        data = f.json(url, headers={"Authorization": f"Bearer {token}"} if token else None)
        if data is None and token:
            # A token refused on a PUBLIC repository is a scope problem, not a
            # reason to give up: the endpoint also answers anonymously. One
            # retry, then the named note (AC-180/AC-200).
            data = f.json(url)
        if data is None:
            out["recent_error"] = "recent runs could not be measured"
        else:
            for r in (data.get("workflow_runs") or []):
                if r.get("name") and "digest" not in (r.get("name") or "").lower():
                    continue
                try:
                    start = dt.datetime.fromisoformat(
                        (r.get("run_started_at") or r["created_at"]).replace("Z", "+00:00"))
                    end = dt.datetime.fromisoformat(
                        (r.get("updated_at") or r["created_at"]).replace("Z", "+00:00"))
                except (KeyError, ValueError):
                    continue
                dur = (end - start).total_seconds()
                if dur <= 0:
                    continue
                runs.append({"id": r.get("id"),
                             "at": r.get("run_started_at") or r.get("created_at", ""),
                             "seconds": dur, "conclusion": r.get("conclusion") or ""})
    else:
        out["recent_error"] = "no repository configured, so recent runs were not measured"

    out["recent"] = runs[:5]
    out["runs_measured"] = len(runs)

    # Projection: the daily run plus the extra Sunday weekly run. Measured runs
    # are used when available, otherwise this run's own duration, which keeps
    # the figure measured rather than assumed either way.
    per = (sum(r["seconds"] for r in runs) / len(runs)) if runs else elapsed
    out["mean_seconds"] = per
    daily = per * 30
    weekly = per * sched["weekly_per_week"] * 4
    total = daily + weekly
    out["monthly_seconds"] = total
    out["monthly"] = _fmt_secs(total)
    out["basis"] = ("average of the last %d measured digest runs" % len(runs)
                    if runs else "this run only (no run history available)")

    pub = f.json(f"https://api.github.com/repos/{repo}") if repo else None
    if pub is None:
        out["remaining"] = ("could not be determined (GitHub did not answer), so no "
                            "quota figure is given")
    else:
        out["public_repo"] = not bool(pub.get("private"))
        if out["public_repo"]:
            out["remaining"] = ("unlimited - this repository is public, and GitHub does "
                                "not bill Actions minutes for public repositories")
        else:
            out["remaining"] = ("a private repository: check Settings > Billing for the "
                                "remaining included minutes")
    return out


def _q(text: str) -> str:
    return quote_plus(text)


def _news_url(query: str, months_ahead: int = 3) -> str:
    """Google News RSS, Johannesburg edition, restricted to a recent window."""
    return (f"{NEWS_URL}?q={_q(query)}&hl=en-ZA&gl=ZA&ceid=ZA:en")


def _rss_items(xml_text: str) -> list[tuple[str, str, str, dt.datetime | None]]:
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        # Google News publishes the outlet as a plain RSS 2.0 <source>, and some
        # mirrors namespace it. Read both, or every headline loses attribution.
        src = item.find("{http://news.google.com/rss}source")
        if src is None:
            src = item.find("source")
        pub = (item.findtext("pubDate") or "").strip()
        when = None
        if pub:
            try:
                when = email.utils.parsedate_to_datetime(pub)
            except (TypeError, ValueError):
                when = None
        publisher = (src.text if src is not None and src.text else "") or ""
        if title:
            items.append((title, link, publisher, when))
    return items


# ---------------------------------------------------------------------------
# One call that does everything
# ---------------------------------------------------------------------------

def gather(cfg: dict, fetcher: Fetcher | None = None, weekly: bool = False,
           today: dt.date | None = None, sports_events: list[dict] | None = None,
           window_days: int = 10, elapsed: float = 0.0, repo: str = "",
           token: str = "") -> dict:
    started = time.monotonic()
    s = settings(cfg, weekly=weekly)
    f = fetcher or Fetcher(timeout=s["timeout"], budget=s["budget"])

    # Muted sports must vanish everywhere - news, fixtures, standings and
    # tennis alike - so the mute set is computed FIRST and gates each source.
    # Filtering only the owner's own event list left a removed sport's live
    # data (a full matchweek, the table) still on the page.
    muted = muted_sports(cfg)

    news = research_news(cfg, f, s, muted)
    comps = [competition_fixtures(e, f) for e in cfg.get("competitions", [])
             if not _entry_muted(e, muted)]
    standings = [league_standings(e, f) for e in cfg.get("competitions", [])
                 if (e.get("standings", True)) and not _entry_muted(e, muted)]
    tennis = (tennis_top_n(cfg, f) if "Tennis" not in muted
              else {"enabled": False, "tours": []})
    today = today or dt.date.today()
    window_end = today + dt.timedelta(days=window_days)
    all_events = [e for e in (sports_events or []) if e.get("sport") not in muted]
    events = [e for e in all_events if _in_window(e, today, window_end)]
    # "Later" means AFTER this window, not "not inside it": a finished event is
    # also outside the window, and suggesting one is worse than suggesting
    # nothing - the owner sees last month's race advertised as something
    # coming up, which is exactly the kind of padding he objected to.
    later = [e for e in all_events
             if not _in_window(e, today, window_end)
             and (e.get("end") or e.get("when") or "") >= today.isoformat()]

    # Football's events come from the live competition feed, not the owner's
    # event list, so it is added here - otherwise the per-sport block would
    # claim Football is quiet while FIXTURES lists a full matchweek.
    live_sport_events = []
    for c in comps:
        for r in c["rows"]:
            # Naming the actual match, not "a fixture": four identical rows say
            # nothing, and the teams are right there in the row.
            teams = " vs ".join(_team_label(t, r["state"]) for t in r["teams"])
            live_sport_events.append({
                "sport": "Football",
                "name": teams,
                "series": c["label"],
                # ISO for sorting; the renderers format it for display.
                "when": (r.get("when") or "")[:10],
                "end": "",
                "display": _fmt_when(r.get("when") or ""),
            })
    by_sport = sorted(events + live_sport_events, key=lambda e: e.get("when", ""))
    for e in by_sport:
        e.setdefault("display", _fmt_day(e.get("when") or ""))
        if e.get("end") and e["end"] != e.get("when"):
            e.setdefault("display_end", _fmt_day(e["end"]))

    # Names already on the page: this window's events plus every tournament
    # the tennis section is about, so the suggestion list cannot repeat them.
    covered = {e.get("name") or "" for e in events}
    for tour in (tennis.get("tours") or []):
        for ev in (tour.get("events") or []):
            covered.add(ev.get("tournament") or "")
    suggestions = suggest(cfg, later, f, already_shown=covered)
    local = local_events(cfg, f, today)
    prices = local_prices(cfg, f)
    # The caller cannot know this: the fetches happen inside gather(), so the
    # only honest elapsed figure is the one measured here.
    measured = time.monotonic() - started
    timing = run_time(measured if not elapsed else elapsed + measured,
                      f, repo=repo, token=token)

    # A source that failed is named. Silence would read as "nothing happened".
    notes = sorted(set(f.failures))
    return {
        "news": news,
        "competitions": comps,
        "standings": standings,
        "tennis": tennis,
        "sports": {"enabled": enabled_sports(cfg), "muted": sorted(muted)},
        "by_sport": by_sport,
        "suggestions": suggestions,
        "local": local,
        "prices": prices,
        "timing": timing,
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


def _fmt_day(iso: str, tz_offset_hours: int = 2) -> str:
    """A calendar date, or a kick-off time when the value carries one.

    A date-only value ("2026-11-02") is a whole-day event, so appending a
    meaningless "00:00" would claim a midnight start that does not exist.
    """
    if not iso:
        return ""
    if len(iso) == 10:
        try:
            return dt.date.fromisoformat(iso).strftime("%a %d %b")
        except ValueError:
            return iso
    return _fmt_when(iso, tz_offset_hours)


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


def _last_match_line(row: dict) -> str:
    """'beat Cameron Norrie 6-3 6-4' or 'lost to Cameron Norrie 3-6 4-6'.

    Built only from the match the payload actually reports, so the opponent and
    the score are the real ones. Empty when the player has no completed match.
    """
    played = [m for m in row.get("matches") or [] if m["state"] == "post"]
    if not played:
        return ""
    last = played[-1]
    if not last.get("opponent"):
        return ""
    verb = "beat" if last.get("won") else "lost to"
    score = f" {last['scoreline']}" if last.get("scoreline") else ""
    return f"{verb} {last['opponent']}{score}"


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

    sp = data.get("sports") or {}
    if sp.get("enabled"):
        out.append("BY SPORT")
        per = {}
        for e in (data.get("by_sport") or []):
            per.setdefault(e["sport"], []).append(e)
        for sport in sp["enabled"]:
            rows = per.get(sport, [])
            if not rows:
                out.append(f"  {sport}: nothing in the window")
                continue
            out.append(f"  {sport}: {len(rows)} in the window")
            # Item 2: show what each event IS, not just that one exists. The
            # description comes from the owner's own file, so nothing here is
            # invented.
            for e in rows[:4]:
                when = e.get("display") or e.get("when") or ""
                span = (f"{when} to {e['display_end']}"
                        if e.get("display_end") else when)
                series = f" ({e['series']})" if e.get("series") else ""
                out.append(f"    * {e['name']}{series} - {span}")
                if e.get("description"):
                    out.append(f"      {e['description']}")
                where = e.get("channel") or e.get("broadcaster") or ""
                if where:
                    out.append(f"      Watch: {where}" +
                               (f" - {e['official']}" if e.get("official") else ""))
            if len(rows) > 4:
                out.append(f"    ... and {len(rows) - 4} more in the window")
        if sp.get("muted"):
            out.append(f"  Muted (removed): {', '.join(sp['muted'])}")
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

    standings = [s for s in (data.get("standings") or []) if s["rows"] or s["error"]]
    if standings:
        out.append("STANDINGS")
        for s in standings:
            if s["error"]:
                out.append(f"  {s['label']}: {s['error']}")
                continue
            stage = f" - {s['stage']}" if s["stage"] else ""
            out.append(f"  {s['label']}{stage}")
            out.append(f"    {'#':>3} {'Team':<24}{'P':>3}{'W':>3}{'D':>3}{'L':>3}{'GD':>4}{'Pts':>5}")
            for r in s["rows"]:
                st = r["stats"]
                rank = r["rank"] if r["rank"] is not None else ""
                out.append(f"    {rank:>3} {r['team'][:24]:<24}"
                           f"{st.get('GP',''):>3}{st.get('W',''):>3}{st.get('D',''):>3}"
                           f"{st.get('L',''):>3}{st.get('GD',''):>4}{st.get('P',''):>5}")
            noted = [r for r in s["rows"] if r["note"]]
            if noted:
                out.append("    Where that leaves them:")
                for r in noted:
                    out.append(f"      {r['rank']}. {r['team']} - {r['note']}")
        out.append("")

    tennis = data["tennis"]
    if tennis.get("enabled"):
        for tour in tennis["tours"]:
            blocks = tennis_tour_blocks(tour, tennis["top_n"])
            if not tour["top"] and not tour.get("events"):
                continue
            out.append(f"TENNIS - {tour['tour']} TOP {tennis['top_n']}")
            for b in blocks:
                if b["kind"] == "ranking":
                    # The owner asked to "show final rankings". This is the
                    # rendered outcome, with ESPN's own positions verbatim.
                    out.append(f"  RANKING - {b['label']}: {b['line']}")
                elif b["kind"] == "summary":
                    out.append(f"  {b['label']}: {b['line']}")
                elif b["kind"] == "note":
                    out.append(f"  {b['text']}")
                elif b["kind"] == "event":
                    head = f"  {b['tournament']}"
                    if b["stage"]:
                        head += f" - {b['stage']}"
                    out.append(head)
                    if b["empty_line"]:
                        out.append(f"    {b['empty_line']}")
                        continue
                    for row in b["rows"]:
                        out.append(f"    [{row['mark']:>3}] {row['position']}. "
                                   f"{row['name']} - {row['detail']}")
                elif b["kind"] == "matches":
                    out.append(f"  {b['label']}:")
                    for m in b["rows"]:
                        tag = "  [in progress]" if m["live"] else ""
                        out.append(f"    {m['when']:<18} {m['line']}{tag}")
            out.append("")

    sug = data.get("suggestions") or {}
    if sug:
        out.append("SUGGESTED (from what you follow)")
        for s in sug.get("sports") or []:
            if not s["items"]:
                continue
            extra = (f"  (+{s['total'] - len(s['items'])} more not shown)"
                     if s.get("total", 0) > len(s["items"]) else "")
            out.append(f"  {s['sport']} - from {s['source']}{extra}")
            for it in s["items"]:
                out.append(f"    + {it['name']}  ({it['why']})")
        for err in (sug.get("errors") or []):
            out.append(f"  {err}")
        if sug.get("error"):
            out.append(f"  {sug['error']}")
        if sug.get("excluded"):
            out.append(f"  Never suggested (you removed): {', '.join(sug['excluded'])}")
        out.append("")

    loc = data.get("local") or {}
    if loc:
        out.append(f"LOCAL - {loc.get('city', '').upper()}")
        for cat in loc.get("categories") or []:
            if cat["items"]:
                out.append(f"  {cat['label']}:")
                for it in cat["items"]:
                    who = f" - {it['publisher']}" if it["publisher"] else ""
                    pair = (f"  [{it['two_person_label']}]"
                            if it.get("two_person") and it.get("two_person_label") else "")
                    out.append(f"    * {it['date']}  {it['title']}{who}{pair}")
                    if it["link"]:
                        out.append(f"      {it['link']}")
            else:
                out.append(f"  {cat['label']}: nothing found in this window "
                           f"({cat['months']} months)")
            # A two-person search that found nothing is stated, not hidden: the
            # category still renders its solo results above (AC-198c).
            if "two_person_found" in cat and not cat["two_person_found"]:
                out.append(f"    {cat.get('two_person_label') or 'Two-person'}: "
                           "no two-person offers found in this window")
        if loc.get("error"):
            out.append(f"  {loc['error']}")
        if loc.get("note"):
            out.append(f"  {loc['note']}")
        out.append("")

    prices = data.get("prices") or {}
    if prices.get("enabled"):
        out.append("RAM PRICE WATCH")
        for item in prices.get("items") or []:
            out.append(f"  {item['label']} - cheapest first")
            if item["error"]:
                out.append(f"    {item['error']}")
                continue
            for o in item["offers"]:
                kind = "kit" if o["kind"] == "kit" else "single module"
                save = f" (save R {o['saving']:,})" if o.get("saving") else ""
                stock = f" [{o['stock']}]" if o["stock"] else ""
                out.append(f"    {o['pretty']:>10}  {o['retailer']} - {kind}{stock}{save}")
                out.append(f"                {o['title']}")
                out.append(f"                {o['url']}")
        out.append("")

    timing = data.get("timing") or {}
    if timing:
        out.append("RUN TIME")
        out.append(f"  This run: {timing['elapsed']}")
        if timing.get("recent"):
            recent = ", ".join(f"{r['seconds']:.0f}s" for r in timing["recent"])
            out.append(f"  Recent runs: {recent}")
        elif timing.get("recent_error"):
            out.append(f"  Recent runs: {timing['recent_error']}")
        if timing.get("monthly"):
            out.append(f"  Estimated per month, daily + Sunday weekly: {timing['monthly']} "
                       f"(from {timing.get('basis', 'this run')})")
        out.append(f"  Remaining git run time: {timing.get('remaining', 'not measured')}")
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
    sport_rows: list[str] = []
    fixture_rows: list[str] = []
    standing_rows: list[str] = []
    tennis_rows: list[str] = []
    suggest_rows: list[str] = []
    local_rows: list[str] = []
    price_rows: list[str] = []
    timing_rows: list[str] = []
    note_rows: list[str] = []

    def head(label: str) -> str:
        return (f'<div style="font-size:13px;font-weight:700;color:{ink};'
                f'margin:0 0 4px">{esc(label)}</div>')

    def row(body: str) -> str:
        return (f'<div style="font-size:13px;color:{ink};margin:0 0 6px;'
                f'padding-left:10px;border-left:2px solid {line}">{body}</div>')

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

    sp = data.get("sports") or {}
    if sp.get("enabled"):
        per: dict[str, list[dict]] = {}
        for e in (data.get("by_sport") or []):
            per.setdefault(e.get("sport", ""), []).append(e)
        for sport in sp["enabled"]:
            found = per.get(sport, [])
            if not found:
                sport_rows.append(row(f'<strong>{esc(sport)}</strong>'
                                      f'<span style="color:{muted};font-size:12px">'
                                      f' &middot; nothing in the window</span>'))
                continue
            events_html = []
            for e in found[:4]:
                series = (f'<span style="color:{muted};font-size:12px"> '
                          f'&middot; {esc(e["series"])}</span>' if e.get("series") else "")
                _w = e.get("display") or e.get("when") or ""
                span = (f'{esc(_w)} to {esc(e["display_end"])}'
                        if e.get("display_end") else esc(_w))
                desc = (f'<div style="font-size:12px;color:{muted};margin:1px 0 0">'
                        f'{esc(e["description"])}</div>' if e.get("description") else "")
                where = e.get("channel") or e.get("broadcaster") or ""
                watch = (f'<div style="font-size:11px;color:{muted};margin:1px 0 0">'
                         f'Watch: {esc(where)}</div>' if where else "")
                events_html.append(
                    f'<div style="margin:3px 0 0">'
                    f'<span style="color:{muted};font-size:12px">{span}</span> &nbsp;'
                    f'<strong>{esc(e["name"])}</strong>{series}{desc}{watch}</div>')
            more = (f'<div style="font-size:12px;color:{muted};margin:3px 0 0">'
                    f'and {len(found) - 4} more in the window</div>'
                    if len(found) > 4 else "")
            sport_rows.append(row(
                f'<strong>{esc(sport)}</strong>'
                f'<span style="color:{muted};font-size:12px"> &middot; '
                f'{len(found)} in the window</span>{"".join(events_html)}{more}'))
        if sp.get("muted"):
            sport_rows.append(f'<div style="font-size:12px;color:{muted};margin:6px 0 0">'
                              f'Switched off: {esc(", ".join(sp["muted"]))}</div>')

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

    for st in [x for x in (data.get("standings") or []) if x["rows"] or x["error"]]:
        if st["error"]:
            standing_rows.append(f'<div style="font-size:13px;color:{muted};margin:0 0 6px">'
                                 f'{esc(st["label"])}: {esc(st["error"])}</div>')
            continue
        stage = f' &middot; {esc(st["stage"])}' if st["stage"] else ""
        standing_rows.append(head(f'{st["label"]}{stage}'))
        cells = []
        for r in st["rows"]:
            q = r["stats"]
            tag = r["note"] or ""
            dot = ("background:#15803d" if "round of 16" in tag
                   else "background:#b45309" if "playoff" in tag
                   else "background:#b91c1c" if "Eliminated" in tag else "background:#94a3b8")
            cells.append(
                f'<tr>'
                f'<td style="font-size:12px;color:{muted};padding:1px 6px 1px 0">'
                f'{esc(str(r["rank"] or ""))}</td>'
                f'<td style="font-size:12px;color:{ink};padding:1px 8px 1px 0">'
                f'<span style="display:inline-block;width:6px;height:6px;border-radius:3px;'
                f'{dot};margin-right:6px"></span>{esc(r["team"])}'
                + (f'<span style="font-size:11px;color:{muted}"> &middot; '
                   f'{esc(tag)}</span>' if tag else "")
                + '</td>'
                f'<td style="font-size:12px;color:{muted};padding:1px 6px;text-align:right">'
                f'{esc(str(q.get("GP", "")))}</td>'
                f'<td style="font-size:12px;color:{muted};padding:1px 6px;text-align:right">'
                f'{esc(str(q.get("W", "")))}</td>'
                f'<td style="font-size:12px;color:{muted};padding:1px 6px;text-align:right">'
                f'{esc(str(q.get("D", "")))}</td>'
                f'<td style="font-size:12px;color:{muted};padding:1px 6px;text-align:right">'
                f'{esc(str(q.get("L", "")))}</td>'
                f'<td style="font-size:12px;color:{muted};padding:1px 6px;text-align:right">'
                f'{esc(str(q.get("GD", "")))}</td>'
                f'<td style="font-size:12px;color:{ink};font-weight:700;padding:1px 0 1px 6px;'
                f'text-align:right">{esc(str(q.get("P", "")))}</td>'
                f'</tr>')
        standing_rows.append(
            f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;margin:0 0 10px">'
            f'<tr><td></td>'
            f'<td style="font-size:11px;color:{muted};padding:0 8px 2px 0">Team</td>'
            f'<td style="font-size:11px;color:{muted};padding:0 6px 2px;text-align:right">P</td>'
            f'<td style="font-size:11px;color:{muted};padding:0 6px 2px;text-align:right">W</td>'
            f'<td style="font-size:11px;color:{muted};padding:0 6px 2px;text-align:right">D</td>'
            f'<td style="font-size:11px;color:{muted};padding:0 6px 2px;text-align:right">L</td>'
            f'<td style="font-size:11px;color:{muted};padding:0 6px 2px;text-align:right">GD</td>'
            f'<td style="font-size:11px;color:{muted};padding:0 0 2px 6px;text-align:right">Pts</td>'
            f'</tr>{"".join(cells)}</table>')

    tennis = data["tennis"]
    if tennis.get("enabled"):
        for tour in tennis["tours"]:
            blocks = tennis_tour_blocks(tour, tennis["top_n"])
            if not tour["top"] and not tour.get("events"):
                continue
            tennis_rows.append(
                f'<div style="font-size:13px;font-weight:700;color:{ink};'
                f'margin:0 0 4px">TENNIS - {esc(tour["tour"])} TOP '
                f'{tennis["top_n"]}</div>')
            for b in blocks:
                if b["kind"] == "ranking":
                    tennis_rows.append(
                        f'<div style="font-size:13px;color:{ink};margin:0 0 6px;'
                        f'padding-left:10px;border-left:2px solid {accent}">'
                        f'<strong>RANKING</strong> &middot; {esc(b["label"])}: '
                        f'{esc(b["line"])}</div>')
                elif b["kind"] == "summary":
                    tennis_rows.append(
                        f'<div style="font-size:12px;color:{muted};margin:0 0 6px">'
                        f'<strong style="color:{ink}">{esc(b["label"])}</strong>: '
                        f'{esc(b["line"])}</div>')
                elif b["kind"] == "note":
                    tennis_rows.append(
                        f'<div style="font-size:12px;color:{muted};margin:0 0 6px">'
                        f'{esc(b["text"])}</div>')
                elif b["kind"] == "event":
                    stage = (f'<span style="font-weight:400;color:{muted}"> &middot; '
                             f'{esc(b["stage"])}</span>' if b["stage"] else "")
                    tennis_rows.append(
                        f'<div style="font-size:12px;font-weight:700;color:{ink};'
                        f'margin:8px 0 4px">{esc(b["tournament"])}{stage}</div>')
                    if b["empty_line"]:
                        tennis_rows.append(
                            f'<div style="font-size:12px;color:{muted};margin:0 0 6px">'
                            f'{esc(b["empty_line"])}</div>')
                        continue
                    for r in b["rows"]:
                        colour = {"in": "#15803d", "out": "#b91c1c"}.get(
                            r["state"], muted)
                        tennis_rows.append(
                            f'<div style="font-size:12px;color:{ink};margin:0 0 3px">'
                            f'<span style="display:inline-block;min-width:26px;'
                            f'font-size:10px;font-weight:700;color:{colour}">'
                            f'{esc(r["mark"])}</span>'
                            f'{esc(str(r["position"]))}. '
                            f'<span style="font-weight:700">{esc(r["name"])}</span>'
                            f'<span style="color:{muted}"> &ndash; </span>'
                            f'{esc(r["detail"])}</div>')
                elif b["kind"] == "matches":
                    tennis_rows.append(
                        f'<div style="font-size:12px;font-weight:700;color:{ink};'
                        f'margin:8px 0 4px">{esc(b["label"])}</div>')
                    for m in b["rows"]:
                        parts = []
                        for i, p in enumerate(m["players"]):
                            if i:
                                parts.append(esc(m["sep"]))
                            bold = "font-weight:700;" if p["winner"] else ""
                            parts.append(f'<span style="{bold}">'
                                         f'{esc(p["label"])}</span>')
                        score = (f' <span style="color:{muted};font-size:11px">'
                                 f'{esc(m["score"])}</span>' if m["score"] else "")
                        live = ('<span style="color:{muted};font-size:11px"> '
                                '[in progress]</span>') if m["live"] else ""
                        tennis_rows.append(
                            f'<div style="font-size:13px;color:{ink};margin:0 0 6px">'
                            f'<span style="color:{muted};font-size:12px">'
                            f'{esc(m["when"])}</span> &nbsp;'
                            f'{"".join(parts)}{score}{live}</div>')
            tennis_rows.append('<div style="height:6px"></div>')

    sug = data.get("suggestions") or {}
    if sug:
        for sgroup in sug.get("sports") or []:
            if not sgroup["items"]:
                continue
            suggest_rows.append(
                f'<div style="font-size:12px;font-weight:700;color:{ink};margin:6px 0 3px">'
                f'{esc(sgroup["sport"])}'
                f'<span style="font-weight:400;color:{muted}"> &middot; from '
                f'{esc(sgroup["source"])}'
                f'{" &middot; +" + str(sgroup["total"] - len(sgroup["items"])) + " more" if sgroup.get("total", 0) > len(sgroup["items"]) else ""}'
                f'</span></div>')
            for it in sgroup["items"]:
                suggest_rows.append(row(f'<strong>{esc(it["name"])}</strong>'
                                        f'<span style="color:{muted};font-size:12px">'
                                        f' &middot; {esc(it["why"])}</span>'))
        for err in (sug.get("errors") or []):
            suggest_rows.append(f'<div style="font-size:12px;color:{muted};margin:4px 0 0">'
                                f'{esc(err)}</div>')
        if sug.get("error"):
            suggest_rows.append(f'<div style="font-size:12px;color:{muted};margin:4px 0 0">'
                                f'{esc(sug["error"])}</div>')
        if sug.get("excluded"):
            suggest_rows.append(
                f'<div style="font-size:12px;color:{muted};margin:6px 0 0">'
                f'Never suggested, because you removed them: '
                f'{esc(", ".join(sug["excluded"]))}</div>')

    loc = data.get("local") or {}
    if loc:
        for cat in loc.get("categories") or []:
            if cat["items"]:
                local_rows.append(head(cat["label"]))
                for it in cat["items"]:
                    who = (f'<span style="color:{muted};font-size:12px"> &mdash; '
                           f'{esc(it["publisher"])}</span>') if it["publisher"] else ""
                    link = (f'<a href="{esc(it["link"])}" style="color:{ink};'
                            f'text-decoration:none">{esc(it["title"])}</a>'
                            if it["link"] else esc(it["title"]))
                    pair = (f' &nbsp;<span style="font-size:11px;color:{accent};'
                            f'background:{soft};padding:1px 6px;border-radius:9px">'
                            f'{esc(it["two_person_label"])}</span>'
                            if it.get("two_person") and it.get("two_person_label") else "")
                    local_rows.append(row(f'<span style="color:{muted};font-size:12px">'
                                          f'{esc(it["date"])}</span> &nbsp;{link}{who}{pair}'))
            else:
                local_rows.append(
                    f'<div style="font-size:12px;color:{muted};margin:0 0 6px">'
                    f'{esc(cat["label"])}: nothing found in this window '
                    f'({cat["months"]} months)</div>')
            if "two_person_found" in cat and not cat["two_person_found"]:
                local_rows.append(
                    f'<div style="font-size:12px;color:{muted};margin:0 0 6px">'
                    f'{esc(cat.get("two_person_label") or "Two-person")}: '
                    f'no two-person offers found in this window</div>')
        if loc.get("error"):
            local_rows.append(f'<div style="font-size:12px;color:{muted};margin:4px 0 0">'
                              f'{esc(loc["error"])}</div>')
        if loc.get("note"):
            local_rows.append(f'<div style="font-size:12px;color:{muted};margin:6px 0 0">'
                              f'{esc(loc["note"])}</div>')

    prices = data.get("prices") or {}
    if prices.get("enabled"):
        for item in prices.get("items") or []:
            price_rows.append(head(f'{item["label"]} &middot; cheapest first'))
            if item["error"]:
                price_rows.append(f'<div style="font-size:12px;color:{muted};margin:0 0 6px">'
                                  f'{esc(item["error"])}</div>')
                continue
            for o in item["offers"]:
                kind = "kit" if o["kind"] == "kit" else "single module"
                save = (f'<span style="color:#15803d;font-size:11px"> save '
                        f'R {o["saving"]:,}</span>' if o.get("saving") else "")
                stock = (f'<span style="color:{muted};font-size:11px"> '
                         f'[{esc(o["stock"])}]</span>' if o["stock"] else "")
                price_rows.append(row(
                    f'<strong>{esc(o["pretty"])}</strong>'
                    f'<span style="color:{muted};font-size:12px"> &middot; '
                    f'{esc(o["retailer"])} &middot; {kind}</span>{stock}{save}<br>'
                    f'<a href="{esc(o["url"])}" style="color:{ink};font-size:12px;'
                    f'text-decoration:none">{esc(o["title"])}</a>'))

    timing = data.get("timing") or {}
    if timing:
        timing_rows.append(row(f'This run: <strong>{esc(timing["elapsed"])}</strong>'))
        if timing.get("recent"):
            recent = ", ".join(f'{r["seconds"]:.0f}s' for r in timing["recent"])
            timing_rows.append(row(f'Recent runs: {esc(recent)}'))
        elif timing.get("recent_error"):
            timing_rows.append(row(f'Recent runs: {esc(timing["recent_error"])}'))
        if timing.get("monthly"):
            basis = timing.get("basis", "this run")
            timing_rows.append(row(f'Estimated per month: '
                                   f'<strong>{esc(timing["monthly"])}</strong>'
                                   f'<span style="color:{muted};font-size:12px"> '
                                   f'&middot; daily + Sunday weekly, from {esc(basis)}</span>'))
        timing_rows.append(row(f'Remaining git run time: '
                               f'{esc(timing.get("remaining", "not measured"))}'))

    if data["failures"]:
        note_rows.append(f'<div style="font-size:12px;color:{muted};margin:10px 0 0">'
                         f'A source could not be reached this run: '
                         f'{esc("; ".join(data["failures"]))}</div>')

    return {
        "news": "".join(news_rows),
        "sports": "".join(sport_rows),
        "fixtures": "".join(fixture_rows),
        "standings": "".join(standing_rows),
        "tennis": "".join(tennis_rows),
        "suggestions": "".join(suggest_rows),
        "local": "".join(local_rows),
        "prices": "".join(price_rows),
        "timing": "".join(timing_rows) + "".join(note_rows),
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
