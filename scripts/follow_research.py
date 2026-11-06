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
    # Big international tournaments. These answer on the same scoreboard
    # endpoint as the leagues, so they are plain entries rather than a special
    # case; they were missing here, which is why adding them earlier produced
    # "unknown competition id" instead of fixtures.
    "fifa.world": "FIFA World Cup",
    "uefa.euro": "UEFA European Championship",
    "fifa.cwc": "FIFA Club World Cup",
    "uefa.nations": "UEFA Nations League",
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
        # The last HTTP status seen. "GitHub did not answer" and "GitHub said
        # 404" are different facts, and the run-time section must not report
        # the second as the first.
        self.last_status: int | None = None

    def remaining(self) -> float:
        return (self.deadline - dt.datetime.now()).total_seconds()

    def get(self, url: str, headers: dict | None = None) -> bytes | None:
        """Fetch, or record why not. Never raises."""
        left = self.remaining()
        if left <= 0:
            self.failures.append("time budget exhausted")
            return None
        self.last_status = None
        try:
            hdrs = {"User-Agent": UA}
            hdrs.update(headers or {})
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=min(self.timeout, left)) as r:
                self.last_status = r.status
                return r.read()
        except urllib.error.HTTPError as exc:
            self.last_status = exc.code
            self.failures.append(f"{type(exc).__name__} on {urllib.parse.urlparse(url).netloc}")
            return None
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
        "briefs_per_sport": int(s.get("briefs_per_sport", 3)),
        "brief_max_age_days": int(s.get("brief_max_age_days", 5)),
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
            ev["outcome"] = _event_outcome(ev["matches"])
            # The rounds this event's draw contains. Published-but-unfilled
            # slots count: ESPN puts the whole bracket up front, so the Final is
            # part of the draw depth even before anyone has reached it.
            rounds = {m["round"] for m in ev["matches"] if m.get("round")}
            ev["rounds"] = sorted(rounds, key=round_sort_key)
            for row in ev["standings"]:
                row["reached"] = _round_reached(row, ev["rounds"])

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


# "Show me more" (owner, item 4): goals for and against join the table. They
# were already in ESPN's payload and were being thrown away, so this is more of
# the publisher's own data rather than a derived figure.
STANDINGS_COLUMNS = [
    ("rank", "#"), ("team", "Team"), ("GP", "P"), ("W", "W"), ("D", "D"),
    ("L", "L"), ("F", "F"), ("A", "A"), ("GD", "GD"), ("P", "Pts"),
]
STANDINGS_STATS = ("GP", "W", "D", "L", "F", "A", "GD", "P")
# The email table draws the same columns; points get their own bolder cell, so
# they are not in this list.
FR_HTML_STANDING_COLS = STANDINGS_STATS[:-1]
STANDINGS_HEAD = {"GP": "P", "P": "Pts"}


def _col_width(key: str) -> int:
    """Width for one standings column, so header and cells stay aligned."""
    return {"GP": 3, "W": 3, "D": 3, "L": 3, "F": 4, "A": 4, "GD": 4}.get(key, 5)


def _qualification_bands(rows: list[dict]) -> str:
    """The qualification bands in one line, e.g. "1-8 in the round of 16".

    Built only from the notes ESPN attaches to its own rows: consecutive
    positions sharing the same note become one band. Nothing is inferred, so a
    competition without notes returns "" and the line is not printed.
    """
    bands: list[tuple[int, int, str]] = []
    for r in sorted((r for r in rows if r.get("note") and r.get("rank") is not None),
                    key=lambda r: r["rank"]):
        note = r["note"].strip()
        if bands and bands[-1][2] == note and bands[-1][1] == r["rank"] - 1:
            bands[-1] = (bands[-1][0], r["rank"], note)
        else:
            bands.append((r["rank"], r["rank"], note))
    if not bands:
        return ""
    parts = []
    for lo, hi, note in bands:
        where = f"{lo}" if lo == hi else f"{lo}-{hi}"
        parts.append(f"{where} {note[0].lower() + note[1:] if note else ''}".strip())
    return "; ".join(parts)


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
            "bands": _qualification_bands(s["rows"]),
            "columns": [c[1] for c in STANDINGS_COLUMNS],
            "keys": [c[0] for c in STANDINGS_COLUMNS],
            "rows": [{
                "position": r["rank"],
                "team": r["team"],
                "stats": {k: r["stats"].get(k, "") for k in STANDINGS_STATS},
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


def sport_detail_blocks(data: dict) -> list[dict]:
    """Every followed sport's own detail, so the page cannot show only two.

    The owner's complaint was that UEFA and Tennis had detail and the rest had
    a count. A count is not research, so each ON sport contributes its next
    event (from the owner's own list) and the news brief gathered for it. A
    sport with neither says so in one line rather than being omitted - an
    absent sport looks like a bug, a stated empty one does not.
    """
    enabled = (data.get("sports") or {}).get("enabled") or []
    briefs = {b["sport"]: b for b in
              ((data.get("briefs") or {}).get("sports") or [])}
    next_up = data.get("next_up") or {}
    per: dict[str, list] = {}
    for e in (data.get("by_sport") or []):
        per.setdefault(e.get("sport") or "", []).append(e)

    out = []
    for sport in enabled:
        brief = briefs.get(sport) or {}
        rows = per.get(sport) or []
        up = next_up.get(sport) or {}
        out.append({
            "sport": sport,
            "window_count": len(rows),
            "next_up": ({
                "name": up.get("name", ""),
                "series": up.get("series", ""),
                "when": up.get("when", ""),
                "display": up.get("display") or up.get("when", ""),
            } if up.get("when") else {}),
            "stories": [{"title": s.get("title", ""),
                         "publisher": s.get("publisher", ""),
                         "link": s.get("link", "")}
                        for s in (brief.get("stories") or [])],
            "source": brief.get("source") or "",
            "events": [{"name": e.get("name", ""),
                        "when": e.get("display") or e.get("when", ""),
                        "series": e.get("series", "")}
                       for e in rows[:4]],
        })
    return out


def timing_blocks(data: dict) -> dict:
    """Item 8: this run's duration, the monthly projection, the git headroom.

    The email printed these; the page did not, so the owner could only see the
    run time in one place. Every number here is measured - the monthly figure is
    an average of real run durations where GitHub returns them, and the headroom
    is the free allowance minus the minutes the run list still shows.
    """
    t = data.get("timing") or {}
    if not t:
        return {}
    return {
        "elapsed": t.get("elapsed", ""),
        "elapsed_seconds": t.get("elapsed_seconds"),
        "recent": [{"seconds": r.get("seconds"), "at": r.get("at", ""),
                    "conclusion": r.get("conclusion", "")}
                   for r in (t.get("recent") or [])],
        "recent_error": t.get("recent_error", ""),
        "monthly": t.get("monthly", ""),
        "basis": t.get("basis", ""),
        "remaining": t.get("remaining", ""),
        "minutes_used": t.get("minutes_used"),
        "minutes_left": t.get("minutes_left"),
        "runs_measured": t.get("runs_measured") or 0,
    }


def price_blocks(data: dict) -> list[dict]:
    """The watched products with their cheapest real listings (item 7).

    The email already printed this; the static page did not, so the owner's own
    "show me any Kingston Fury Beast 16GB at best prices" request was only
    answered in one of the two surfaces. A saving is only ever the difference
    between two listed prices, so nothing here is estimated.
    """
    pw = data.get("prices") or {}
    if not pw.get("enabled"):
        return []
    out = []
    for item in pw.get("items") or []:
        offers = [{"retailer": o.get("retailer", ""), "pretty": o.get("pretty", ""),
                   "title": o.get("title", ""), "url": o.get("url", ""),
                   "condition": o.get("condition", ""),
                   "note": o.get("note", ""), "save": o.get("save", "")}
                  for o in (item.get("offers") or [])[:int(pw.get("top_n", 3))]]
        out.append({
            "label": item.get("label", ""),
            "unit": item.get("unit", ""),
            "featured": bool(item.get("featured")),
            "offers": offers,
            "below_market": list(item.get("below_market") or []),
            "count": item.get("all_count") or 0,
            "error": item.get("error", ""),
        })
    return out


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
        "round": row.get("round") or "",
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
    # An event carrying none of the top N used to get its own heading, its own
    # stage line and a column of dashes: four tournaments the owner does not
    # care about pushed the one he does off the screen. Those events are named
    # in a single line instead (below), and only events with a top-N player get
    # a block of their own.
    # When the ranking could not be read there is no top N to look for, so every
    # event is still shown (its stage and result are real) but with no player
    # rows - the alternative was to hide the tournaments along with the ranking.
    carried = ([ev for ev in events
                if any(r["status"] in ("in", "out") for r in ev["standings"])]
               if top else list(events))
    for ev in carried:
        outcome = ev.get("outcome") or {}
        blocks.append({
            "kind": "event",
            "tournament": ev["tournament"],
            "stage": ev.get("status_line", ""),
            "champion": outcome.get("champion", ""),
            "runner_up": outcome.get("runner_up", ""),
            "final_score": outcome.get("final_score", ""),
            "outcome_line": _outcome_line(outcome, top_n),
            "rounds": list(ev.get("rounds") or []),
            "rows": [{
                "position": r["rank"],
                "name": r["name"],
                "state": r["status"],
                "mark": {"in": "IN", "out": "OUT"}.get(r["status"], "--"),
                "detail": r["detail"],
                "reached": r.get("reached", ""),
            } for r in ev["standings"]],
        })

    # An event carrying none of the top N is named in one line, never given a
    # table of dashes.
    unplaced = [ev for ev in events if ev not in carried]
    if unplaced:
        names = ", ".join(ev["tournament"] for ev in unplaced)
        if not carried:
            # The owner asked "Why are no top 5 women playing. Would be nice if i
            # could know." An unexplained absence reads like a bug, so the events
            # actually being played are named: the answer is almost always that
            # the top 5 were not entered for this week's smaller tournaments,
            # which is checkable rather than a guess about their reasons.
            blocks.append({"kind": "note",
                           "text": f"No top-{top_n} match for this tour in the "
                                   f"event(s) on now ({names}). They are not "
                                   f"entered for these, rather than missing from "
                                   f"the feed."})
        else:
            blocks.append({"kind": "note",
                           "text": f"No top-{top_n} match in: {names}."})

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


def _event_outcome(matches: list[dict]) -> dict:
    """The champion and runner-up of an event, only once a Final is played.

    The owner asked to "show final rankings". A tournament with no completed
    Final has no winner, and inventing one from the bracket would be a guess, so
    this returns empty strings and the renderer prints nothing.
    """
    real = [m for m in matches if not _is_placeholder(m)]
    finals = [m for m in real if m["state"] == "post"
              and round_sort_key(m.get("round", "")) == round_sort_key("Final")]
    if not finals:
        return {"champion": "", "runner_up": "", "final_score": "",
                "final_round": ""}
    final = finals[-1]
    winner = next((p for p in final["players"] if p.get("winner")), None)
    loser = next((p for p in final["players"] if p is not winner), None)
    return {
        "champion": winner["name"] if winner else "",
        "runner_up": loser["name"] if loser else "",
        "final_score": (winner or {}).get("setline", ""),
        "final_round": final.get("round", ""),
    }


def _round_reached(row: dict, rounds_played: list[str]) -> str:
    """How far a top-N player got, e.g. "round 2 of 7" - never a bare number.

    `rounds_played` is the ordered list of rounds the event actually ran, so the
    "of 7" is the real draw depth rather than a constant that would be wrong at
    a different-sized event.
    """
    # Qualifying is not part of the main draw, so "of 6" means round 1 to the
    # final and not round 1 to the final plus two qualifying rounds.
    main = [r for r in rounds_played if "qualifying" not in r.lower()]
    if not main:
        return ""
    played = row.get("matches") or []
    if not played:
        return ""
    deepest = max(played, key=lambda m: round_sort_key(m.get("round") or ""))
    rnd = deepest.get("round") or ""
    if not rnd:
        return ""
    return f"{_lower_round(rnd)}, main draw of {len(main)}"


def _outcome_line(outcome: dict, top_n: int) -> str:
    """The event's final result in one line, or "" if the Final is unplayed.

    "Show final rankings" is only honest once a Final exists: ESPN publishes the
    whole bracket up front, so an unplayed Final must not be reported as a
    result.
    """
    champ = (outcome or {}).get("champion") or ""
    if not champ:
        return ""
    runner = outcome.get("runner_up") or ""
    score = outcome.get("final_score") or ""
    line = f"Champion: {champ}"
    if runner:
        line += f"; runner-up: {runner}"
    if score:
        line += f" ({score} in the final)"
    return line


def _event_status_line(matches: list[dict]) -> str:
    """The latest round reached in this event, from REAL matches only."""
    real = [m for m in matches if not _is_placeholder(m)]
    rounds = [m["round"] for m in real if m.get("round")]
    if not rounds:
        return "draw not published yet"
    furthest = max(rounds, key=round_sort_key)
    if any(m["state"] == "in" for m in real):
        # "In progress" anywhere on a delivered page reads as a claim about the
        # owner's MSc, which the CV guard (AC-61) rightly rejects. A live tennis
        # event is "under way".
        return f"Under way - {furthest}"
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


def _lower_round(round_name: str) -> str:
    """ESPN's round name folded into running prose ("Round 2" -> "round 2").

    "Round of 16" and "Quarterfinal" keep their words; only the leading capital
    on a plain Round name is removed, so the sentence does not read
    "still in - Round 2" next to "won the Quarterfinal".
    """
    rnd = (round_name or "").strip()
    if not rnd:
        return rnd
    if rnd[:1].isupper() and rnd[1:2].islower():
        return rnd[0].lower() + rnd[1:]
    return rnd


def _out_phrase(round_name: str, beaten_by: str) -> str:
    """'out in round 2, beaten by X' without the stray capital in "the Round 2".

    Round names arrive from ESPN as "Round 2"/"Round of 16"/"Quarterfinal".
    "out in the Round 2" is the shape the owner called out as badly written, so
    the round is folded into the sentence in lower case, keeping acronyms (QF,
    SF) and "Round of 16" intact.
    """
    where = "out"
    if round_name:
        rnd = _lower_round(round_name)
        where = (f"out in the {rnd}" if rnd.lower().startswith("round")
                 else f"out at the {rnd}")
    return f"{where}, beaten by {beaten_by}" if beaten_by else where


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
            detail = (f"still in - {_lower_round(rounds[0])}" if rounds
                      else "still in")
        elif played:
            last = played[-1]
            if last["won"]:
                status = "in"
                detail = (f"won the {_lower_round(last['round'])}"
                          if last["round"] else "won their latest match")
            else:
                status = "out"
                detail = _out_phrase(last["round"], last["beaten_by"])
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
    "F1": "ESPN Formula 1 calendar",
    "Rugby": "ESPN rugby fixtures",
    "Cycling": "your own event list",
    "Gymnastics": "your own event list",
    "Weightlifting": "your own event list (no live feed publishes IWF results)",
    "Padel": "your own event list",
}


def removed_series(cfg: dict) -> set[str]:
    """Series the owner does not want, lowercased.

    The three he removed (NASCAR, WRC, endurance) all sit under Motorsport,
    which he still wants for MotoGP and F1. A sport-level mute would have taken
    those with it, so the removal has to be at series level.
    """
    return {s.strip().lower() for s in (cfg.get("removed_series") or []) if s}


def is_removed_series(event: dict, removed: set[str]) -> bool:
    series = (event.get("series") or "").strip().lower()
    if not series:
        return False
    return any(r and (r in series or series in r) for r in removed)


SPORT_BRIEF_QUERIES = {
    "Weightlifting": ["weightlifting world championships results",
                      "IWF weightlifting results"],
    "Motorsport": ["MotoGP results standings", "motorsport championship news"],
    "F1": ["Formula 1 results drivers championship"],
    "Rugby": ["rugby union results standings", "United Rugby Championship news"],
    "Padel": ["Premier Padel results tournament"],
    "Tennis": ["tennis ATP tour news"],
    "Football": ["football transfer news"],
    "Cycling": ["cycling race results"],
    "Gymnastics": ["gymnastics world championships results"],
}


def sport_briefs(cfg: dict, f: Fetcher, s: dict, muted: set[str]) -> dict:
    """A short brief for EVERY sport that is switched on, not only topics.

    BY SPORT used to print an event count and nothing else, which is why the
    owner said it "gave me nothing on weightlifting". A count is not research.
    Each sport gets its own targeted query, and every story keeps the query that
    produced it so the digest never implies a source it did not use.

    A sport whose sources return nothing says so. Nothing is invented to fill
    the gap.
    """
    out = {"sports": [], "error": ""}
    per = int(s.get("briefs_per_sport", 3))
    for sport in enabled_sports(cfg):
        if sport in muted:
            continue
        terms = SPORT_BRIEF_QUERIES.get(sport) or [sport]
        stories, seen = [], set()
        for query in terms:
            for story in news_for(query, f, s.get("brief_max_age_days", 5), per):
                key = (story["title"] or "").lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                stories.append({**story, "query": query})
                if len(stories) >= per:
                    break
            if len(stories) >= per:
                break
        out["sports"].append({
            "sport": sport,
            "stories": stories,
            "source": SPORT_SOURCES.get(sport, "news search"),
            "queries": terms,
        })
    return out


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
    # Series he wants kept in the digest but never offered as a suggestion.
    no_suggest = {s.strip().lower() for s in (cfg.get("no_suggest_series") or []) if s}
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
        if sport == "Football" and cfg.get("no_team_suggestions"):
            # The owner was explicit that suggesting individual clubs is not
            # what he wants ("Dont suggest football teams to follow. Weird,
            # mainly leagues"). Leagues are followed directly instead, so this
            # sport contributes nothing to the suggestion list.
            continue
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
                # A series he asked not to be suggested is filtered here, so it
                # stays in the digest while never appearing as a recommendation.
                if (e.get("series") or "").strip().lower() in no_suggest:
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


# ---------------------------------------------------------------------------
# Local venue helpers (item 6)
# ---------------------------------------------------------------------------
_VENUE_SPLIT = re.compile(r"\s+[|\u2013\u2014]\s+|\s+-\s+|:\s+")
_AT_VENUE = re.compile(r"\bat\s+([A-Z][\w'&.\- ]{2,40})")
_LIMIT_WORDS = ("limited", "limit", "only", "per person", "per table", "no sharing",
                "first come", "while stocks", "while stock", "sold out",
                "booking essential", "reservation", "minimum spend", "kids eat free",
                "2 for 1", "two for one", "half price", "all you can eat",
                "bottomless", "unlimited")


def _venue_from_headline(title: str) -> str:
    """The place name a local headline actually carries, or ''.

    The owner rejected headline-only output ("you should be reading pages for me
    and giving me best names of places to go"). A venue is only reported when
    the headline itself names one - before a separator, or after "at". Nothing
    is guessed from a generic word, because a wrong venue name sends him to the
    wrong place.
    """
    t = (title or "").strip()
    if not t:
        return ""
    parts = [p.strip() for p in _VENUE_SPLIT.split(t) if p.strip()]
    if len(parts) > 1:
        # Retailer copy is "Venue | Description" or "Description - Venue"; the
        # short fragment is the name far more often than the sentence is, so a
        # proper-noun-looking fragment with 1-5 words wins.
        cands = [p for p in parts if 1 <= len(p.split()) <= 5
                 and p[0].isupper() and not p.lower().startswith(
                     ("the best", "how to", "what", "where", "why"))]
        if cands:
            return cands[0].strip(" -|\u2013")
    m = _AT_VENUE.search(t)
    if m:
        return m.group(1).strip()
    return ""


def _limits_from_headline(title: str) -> list[str]:
    """Conditions the headline states ("kids eat free", "2 for 1", "limited").

    These are the owner's "if they are limited etc". Only phrases present in the
    text are returned, so the digest cannot claim a condition nobody wrote.
    """
    low = (title or "").lower()
    return [w for w in _LIMIT_WORDS if w in low]


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
                              "venue": _venue_from_headline(title),
                              "limits": _limits_from_headline(title),
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


def _ref_page_price(url: str, f: Fetcher) -> dict | None:
    """The retailer's own price from the page the owner pointed at.

    The owner supplied a reference URL per part ("cheapest i can find of this
    exact one ... link"). Reading that page means his own known-good listing is
    always in the comparison, instead of the "best price" being whatever a
    search happened to return. The price is taken from structured JSON on the
    page (`"price":5299`); the R-string in the markup is formatted for display
    and is not used, so nothing is rounded here.
    """
    raw = f.get(url)
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    title = ""
    m = re.search(r"<title>(.*?)</title>", raw, re.S | re.I)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    price = None
    for pat in (r'"price"\s*:\s*"?([\d]+(?:\.[\d]+)?)',
                r'"priceAmount"\s*:\s*([\d]+(?:\.[\d]+)?)',
                r'itemprop="price"[^>]*content="([\d]+(?:\.[\d]+)?)"'):
        found = re.findall(pat, raw)
        if found:
            try:
                price = int(float(found[0]))
            except ValueError:
                price = None
            if price:
                break
    if not price:
        return None
    host = urllib.parse.urlparse(url).netloc.replace("www.", "")
    return {"title": title, "price": price, "retailer": host, "url": url,
            "kind": "single", "stock": "", "list_price": None,
            "pretty": f"R {price:,}"}


def _is_used(title: str, extra: str = "") -> bool:
    low = f"{title} {extra}".lower()
    return any(w in low for w in ("used", "second hand", "secondhand",
                                  "pre-owned", "preowned", "refurbished",
                                  "open box", "open-box"))


def _matches_spec(title: str, spec: dict) -> bool:
    """True if a listing is the SAME product the owner asked for.

    `must_match` alone was too loose: "kingston fury beast 16gb" happily matched
    a DDR4 3600 kit when he wants DDR5 5600, and "b850m" matched three different
    brands of motherboard. Both were then reported as "below market" when they
    were simply a cheaper, different product - the most misleading thing this
    section can do. `must_not_match` and the DDR generation are therefore
    enforced, and the brand word is required.
    """
    low = (title or "").lower()
    for bad in spec.get("must_not_match") or []:
        if bad.lower() in low:
            return False
    # DDR generation is a hard property: DDR4 RAM is not a cheaper DDR5 kit.
    if spec.get("ddr"):
        want = str(spec["ddr"]).lower()
        if want not in low:
            return False
        for other in ("ddr3", "ddr4", "ddr5"):
            if other != want and other in low:
                return False
    return True


def _unit_label(spec: dict) -> str:
    """What one listing of this product IS, or "" when it is not meaningful.

    "new, single module" was printed against a graphics card, a power supply and
    a case, because the kit/single-module split is a MEMORY distinction and was
    being applied to every watched product. Only a memory kit has modules; the
    other parts get their own noun, and anything unrecognised gets no noun
    rather than a wrong one.
    """
    if spec.get("capacity_gb") or spec.get("ddr"):
        return "module"
    label = (spec.get("label") or "").lower()
    for words, unit in ((("graphics", "gpu", "rx ", "rtx", "geforce", "radeon"), "card"),
                        (("ryzen", "core i", "processor", "cpu"), "CPU"),
                        (("power supply", "psu", "80+"), "unit"),
                        (("nvme", "ssd", "hard drive", "hdd"), "drive"),
                        (("cooler", "heatsink", "aio"), "cooler"),
                        (("motherboard", "mainboard"), "board"),
                        (("case", "chassis"), "case")):
        if any(w in label for w in words):
            return unit
    return ""


def _kind_word(item: dict, offer: dict) -> str:
    """The noun for one listing: kit, or a single unit of the product's kind.

    "single module" was printed for a graphics card, a power supply and a case
    before this existed, because kit/module is a memory distinction that had
    been applied to every watched product.
    """
    if offer.get("kind") == "kit":
        return "kit"
    unit = item.get("unit") or ""
    return f"single {unit}" if unit else ""


def local_prices(cfg: dict, f: Fetcher) -> dict:
    """Cheapest real prices for watched products, new and second-hand.

    Takealot's public search API needs no key. The price lives in
    `buybox_summary` (NOT in the empty `pricing` block), as `prices[0]` plus a
    pre-formatted `pretty_price`; the retailer's own string is used where it
    exists so the digest cannot round or mangle it.

    Each item keeps the reference page the owner supplied in the comparison, so
    his own known-good listing can never be missing from "cheapest I found".
    """
    pw = cfg.get("price_watch") or {}
    top_n = int(pw.get("top_n", 3))
    out = {"enabled": bool(pw.get("enabled")), "items": [], "error": "",
           "top_n": top_n}
    if not out["enabled"]:
        out["error"] = "price watch is switched off in personal/data/follow.json"
        return out

    for spec in pw.get("items") or []:
        if not spec.get("enabled", True):
            continue
        label = spec.get("label") or spec.get("key") or "item"
        query = spec.get("query") or label
        must = [m.lower() for m in (spec.get("must_match") or [])]
        offers = []

        # His own reference listing, read directly.
        unit = _unit_label(spec)
        ref = _ref_page_price(spec["ref_url"], f) if spec.get("ref_url") else None
        if ref:
            # A memory kit is "kit"; every other watched product is a single
            # unit of its own kind, so the comparison stays like-for-like.
            ref["kind"] = ("kit" if re.search(r"\d+\s*x\s*\d+\s*gb",
                                              (ref.get("title") or "").lower())
                           else "single")
            offers.append(ref)

        data = f.json(f"{PRICE_API}?qsearch={_q(query)}&size=40")
        if data is None and not offers:
            out["items"].append({"label": label, "offers": [], "below_market": [],
                                 "unit": unit, "featured": bool(spec.get("featured")),
                                 "error": "the price source could not be reached"})
            continue

        results = (((data or {}).get("sections") or {}).get("products") or {}
                   ).get("results") or []
        for r in results:
            views = r.get("product_views") or {}
            core = views.get("core") or {}
            buy = views.get("buybox_summary") or {}
            title = core.get("title") or ""
            low = title.lower()
            if must and not all(m in low for m in must):
                continue
            if not _matches_spec(title, spec):
                continue
            # "16gb" is a substring of "2x16gb" (= 32GB), which would put a 32GB
            # kit in a 16GB watch. Capacity is checked as a NUMBER, not a string.
            capacity = _kit_capacity_gb(low)
            if spec.get("capacity_gb") and capacity != int(spec["capacity_gb"]):
                continue
            # ONE price per row - the SELLING price `prices[0]`, which is the
            # number the retailer displays as `pretty_price`. `listing_price` is
            # the pre-discount list figure and is a different number (measured
            # 2026-11-04: 5,899 vs 5,549), so sorting on it while printing
            # `prices[0]` would rank the page by a price the owner never sees.
            prices = buy.get("prices")
            selling = None
            if isinstance(prices, list) and prices:
                selling = prices[0]
            elif isinstance(buy.get("listing_price"), int):
                selling = buy.get("listing_price")
            if not isinstance(selling, int) or selling <= 0:
                continue
            kind = ("kit" if unit and (
                re.search(r"\d+\s*x\s*\d+\s*gb", low) or " kit" in f" {low}")
                else "single")
            stock = (views.get("stock_availability_summary") or {}).get("status", "")
            offers.append({
                "title": title,
                "price": selling,
                "list_price": (buy.get("listing_price")
                               if isinstance(buy.get("listing_price"), int) else None),
                "pretty": buy.get("pretty_price") or f"R {selling:,}",
                "retailer": "Takealot",
                "kind": kind,
                "condition": "used" if _is_used(title, stock) else "new",
                "stock": stock,
                "url": (f"https://www.takealot.com/{core.get('slug', '')}"
                        f"/PLID{core.get('id', '')}"),
            })

        if not results:
            out["items"].append({
                "label": label, "offers": [], "below_market": [],
                "unit": unit, "featured": bool(spec.get("featured")), "error":
                "no matches came back for this search - the price source may have "
                "changed shape, so no price is given rather than a guessed one"})
            continue

        if not offers:
            out["items"].append({"label": label, "offers": [], "below_market": [],
                "unit": unit, "featured": bool(spec.get("featured")),
                                 "error": "no listing with a usable price was found"
                                          f" among {len(results)} results"})
            continue

        # The same physical product can be listed twice (a search hit and his
        # own reference page); the cheaper of the two is the honest one to show.
        best: dict[str, dict] = {}
        for o in offers:
            key = (o["title"] or "").strip().lower()
            if key not in best or o["price"] < best[key]["price"]:
                best[key] = o
        offers = list(best.values())
        offers.sort(key=lambda o: o["price"])

        # "Below market" is defined against the MEDIAN of the listings found,
        # never a guessed retail price: a listing 15% or more under the median
        # of the same kind is called out. With too few listings there is no
        # market to be under, so nothing is flagged.
        below = []
        for kind in {o["kind"] for o in offers}:
            same = sorted(o["price"] for o in offers if o["kind"] == kind)
            top = same[-1]
            for o in offers:
                if o["kind"] == kind:
                    o["saving"] = (top - o["price"]) if len(same) > 1 else 0
            if len(same) < 3:
                continue
            mid = same[len(same) // 2] if len(same) % 2 else (
                (same[len(same) // 2 - 1] + same[len(same) // 2]) // 2)
            for o in offers:
                if o["kind"] != kind:
                    continue
                o["market_median"] = mid
                over = round((mid - o["price"]) / mid * 100)
                o["below_market_pct"] = over if o["price"] < mid else 0
                if over >= 15:
                    below.append(o)

        out["items"].append({
            "label": label,
            # What one listing of THIS product is: "module" for memory, "card"
            # for a GPU. The renderers name the unit instead of calling every
            # product a memory module.
            "unit": unit,
            # A "featured" product gets its own named section at the top of the
            # price block, so the kit the owner is actively shopping for is not
            # one row among eight.
            "featured": bool(spec.get("featured")),
            # Every priced listing is kept; the renderer shows `top_n`. The
            # saving is a difference within this full set, so cutting the list
            # to 3 here would silently change what the saving means.
            "offers": offers,
            "all_count": len(offers),
            "below_market": [{"title": o["title"], "price": o["price"],
                              "pretty": o["pretty"], "retailer": o["retailer"],
                              "pct": o.get("below_market_pct", 0),
                              "url": o["url"]} for o in below[:top_n]],
        })

    return out


# ---------------------------------------------------------------------------
# Deals / Black Friday (item 6b)
# ---------------------------------------------------------------------------
def deals(cfg: dict, f: Fetcher) -> dict:
    """Black Friday / sale watches for the things the owner named.

    A deal is only reported AS a deal when the page or headline states a
    discount. A normal price is listed as a normal price so a later sale can be
    measured against it - presenting full price as a special would be an
    invention, and the owner said he will "only buy on big special".
    """
    d = cfg.get("deals") or {}
    out = {"enabled": bool(d.get("enabled")), "groups": [], "error": ""}
    if not out["enabled"]:
        out["error"] = "deals watch is switched off in personal/data/follow.json"
        return out

    for spec in d.get("queries") or []:
        group = {"key": spec.get("key", ""), "label": spec.get("label", ""),
                 "note": spec.get("note", ""), "items": [], "error": ""}
        seen = set()
        # Reference pages he supplied are read directly, so his own known
        # product always appears with a real price to compare a sale against.
        for url in spec.get("refs") or []:
            px = _ref_page_price(url, f)
            if not px:
                continue
            key = (px["title"] or url).lower()
            if key in seen:
                continue
            seen.add(key)
            group["items"].append({**px, "headline": px["title"],
                                   "on_special": False, "when": ""})
        for term in spec.get("terms") or []:
            for story in news_for(term, f, 10, 4):
                key = (story["title"] or "").lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                low = story["title"].lower()
                # Only a stated discount counts. These are the words a retailer
                # uses when there IS a discount, so their presence is evidence.
                on_special = any(w in low for w in
                                 ("sale", "deal", "off", "discount",
                                  "black friday", "special", "clearance", "%"))
                group["items"].append({
                    "title": story["title"], "headline": story["title"],
                    "publisher": story.get("publisher", ""),
                    "url": story.get("link", ""),
                    "when": (story["when"].strftime("%Y-%m-%d")
                             if story.get("when") else ""),
                    "price": None, "pretty": "", "kind": "single",
                    "stock": "", "list_price": None, "on_special": on_special,
                    "retailer": story.get("publisher", ""),
                })
        if not group["items"]:
            group["error"] = ("nothing found for this watch in the last 10 days - "
                              "that is no story, not proof of no sale")
        # A stated discount leads, because that is what he asked for.
        group["items"].sort(key=lambda i: not i.get("on_special"))
        group["special_count"] = sum(1 for i in group["items"] if i.get("on_special"))
        out["groups"].append(group)
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
            status = getattr(f, "last_status", None)
            # Name the reason: a refused/anonymous request and a timeout both
            # end up here, and "could not be measured" alone tells the owner
            # nothing about whether the job is healthy.
            if status == 404:
                out["recent_error"] = (f"recent runs were not readable without a "
                                       f"token (GitHub answered 404 for {repo})")
            elif status == 403:
                out["recent_error"] = ("recent runs were refused by GitHub "
                                       "(usually the anonymous rate limit)")
            else:
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

    # Remaining Actions minutes. GitHub's billing endpoint refuses a
    # fine-grained token (403), so the honest measured answer is built from the
    # run history itself: minutes used so far this calendar month, against the
    # 2,000 free included minutes a private repository gets on the Free plan.
    out["minutes_used"] = None
    out["minutes_included"] = None
    out["free_minutes"] = 2000
    if repo:
        month_start = dt.datetime.now(dt.timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        used = 0.0
        for r in (data.get("workflow_runs") or []) if isinstance(data, dict) else []:
            try:
                start = dt.datetime.fromisoformat(
                    (r.get("run_started_at") or r["created_at"]).replace("Z", "+00:00"))
                end = dt.datetime.fromisoformat(
                    (r.get("updated_at") or r["created_at"]).replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            if start >= month_start and end > start:
                used += (end - start).total_seconds() / 60.0
        out["minutes_used"] = round(used, 1)
        out["minutes_included"] = out["free_minutes"]
        out["minutes_left"] = round(max(0.0, out["free_minutes"] - used), 1)

    # The token is sent here too. Without it a PRIVATE repository answers 404
    # and the owner was told his own quota "could not be determined".
    pub = f.json(f"https://api.github.com/repos/{repo}",
                 headers={"Authorization": f"Bearer {token}"} if token else None) if repo else None
    if pub is None:
        status = getattr(f, "last_status", None)
        if status == 404:
            # A 404 is an ANSWER, not silence: the repository is private (or
            # renamed), and an unauthenticated read cannot see it. Reporting
            # "did not answer" for this hid the real cause.
            out["remaining"] = (
                f"not readable without a token (GitHub answered 404 for {repo}, so "
                "it is private or renamed); a private repository's minutes are on "
                "Settings > Billing")
        elif status == 403:
            out["remaining"] = ("not readable right now (GitHub refused the request, "
                                "which is usually the anonymous rate limit); try again "
                                "from the Actions run, which sends a token")
        else:
            out["remaining"] = ("could not be determined (GitHub did not answer), so no "
                                "quota figure is given")
    else:
        out["public_repo"] = not bool(pub.get("private"))
        if out["public_repo"]:
            out["remaining"] = ("unlimited - this repository is public, and GitHub does "
                                "not bill Actions minutes for public repositories")
        else:
            used = out.get("minutes_used")
            if used is None:
                out["remaining"] = ("a private repository: check Settings > Billing for the "
                                    "remaining included minutes")
            else:
                left = out["minutes_left"]
                out["remaining"] = (
                    f"about {left:,.0f} of {out['free_minutes']:,} included minutes left "
                    f"({used:,.0f} used this month by the runs GitHub still lists). "
                    f"At {out['monthly']} a month this job uses about "
                    f"{100.0 * total / 60.0 / out['free_minutes']:.1f}% of the free "
                    f"allowance, so there is roughly "
                    f"{int(left / max(total / 60.0, 0.01))} month(s) of headroom before "
                    f"anything is billed. Settings > Billing has GitHub's own figure.")
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
        # Google News appends " - Publisher" to a clustered headline AND fills
        # <source>. Without this the local section printed "Time Out Worldwide -
        # Time Out Worldwide".
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(f" - {publisher}")].strip()
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
    removed_ser = removed_series(cfg)
    all_events = [e for e in (sports_events or [])
                  if e.get("sport") not in muted
                  and not is_removed_series(e, removed_ser)]
    events = [e for e in all_events if _in_window(e, today, window_end)]
    # "Later" means AFTER this window, not "not inside it": a finished event is
    # also outside the window, and suggesting one is worse than suggesting
    # nothing - the owner sees last month's race advertised as something
    # coming up, which is exactly the kind of padding he objected to.
    later = [e for e in all_events
             if not _in_window(e, today, window_end)
             and (e.get("end") or e.get("when") or "") >= today.isoformat()]

    # What each quiet sport has coming up ANYWAY. "Why do all sports not show"
    # was asked about a sport whose row said only "nothing in the window"; the
    # next dated event after the window answers it with a real date rather than
    # a shrug. Only the owner's own event list is used - nothing is fetched or
    # guessed to fill the line.
    next_up: dict[str, dict] = {}
    for e in sorted(later, key=lambda x: x.get("when") or ""):
        next_up.setdefault(e.get("sport") or "", e)

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
    briefs = sport_briefs(cfg, f, s, muted)
    deal_list = deals(cfg, f)
    # The caller cannot know this: the fetches happen inside gather(), so the
    # only honest elapsed figure is the one measured here.
    measured = time.monotonic() - started
    # The quota lookups get their OWN small budget. They used to reuse `f`,
    # whose budget is usually spent by this point, so item 8's remaining-time
    # line answered "GitHub did not answer" on every real run - the one number
    # the owner asked for. A caller-supplied fetcher is always honoured, so a
    # test (or any injected source) still serves these calls.
    quota_f = f if fetcher is not None else Fetcher(timeout=s["timeout"], budget=20.0)
    timing = run_time(measured if not elapsed else elapsed + measured,
                      quota_f, repo=repo, token=token)

    # A source that failed is named. Silence would read as "nothing happened".
    notes = sorted(set(f.failures))
    return {
        "news": news,
        "competitions": comps,
        "standings": standings,
        "tennis": tennis,
        "sports": {"enabled": enabled_sports(cfg), "muted": sorted(muted)},
        "by_sport": by_sport,
        "next_up": next_up,
        "briefs": briefs,
        "suggestions": suggestions,
        "local": local,
        "prices": prices,
        "deals": deal_list,
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
        briefs = {b["sport"]: b for b in
                  ((data.get("briefs") or {}).get("sports") or [])}
        next_up = data.get("next_up") or {}
        for sport in sp["enabled"]:
            rows = per.get(sport, [])
            brief = briefs.get(sport) or {}
            stories = brief.get("stories") or []
            # The count is about the owner's OWN event list, while the stories
            # below it are the news brief. A bare "nothing in the window" reads
            # as if nothing was found at all, which is the complaint that "all
            # sports do not show"; the note names what the count covers.
            if rows:
                out.append(f"  {sport}: {len(rows)} in the window")
            else:
                out.append(f"  {sport}: nothing in the window")
            if stories and not rows:
                out.append("    (that is your own event list - the brief below "
                           "is what the news has on it this week)")
            up = next_up.get(sport) or {}
            if not rows and up.get("when"):
                span = up.get("display") or up["when"]
                series = f" ({up['series']})" if up.get("series") else ""
                out.append(f"    Next up: {up.get('name', '')}{series} - {span} "
                           f"({up['when']})")
            if stories:
                for story in stories:
                    who = f" - {story['publisher']}" if story.get("publisher") else ""
                    out.append(f"    * {story['title']}{who}")
                    if story.get("link"):
                        out.append(f"      {story['link']}")
            else:
                out.append(f"    No recent {sport} story was found in the news "
                           f"window, so there is no brief to give.")
            if not rows:
                continue
            for e in rows[:4]:
                when = e.get("display") or e.get("when") or ""
                span = (f"{when} to {e['display_end']}"
                        if e.get("display_end") else when)
                if e.get("when") and e["when"] not in span:
                    span = f"{span} ({e['when']})"
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
            # A stat the source did not publish is dropped from the header AND
            # from every row. Keeping a fixed column list printed two blank
            # columns for competitions that publish no goals, which made the
            # table look broken rather than sparse.
            shown = [k for k in STANDINGS_STATS
                     if any(str(r["stats"].get(k, "")) != "" for r in s["rows"])]
            head = "    " + f"{'#':>3} {'Team':<24}" + "".join(
                f"{STANDINGS_HEAD.get(k, k):>{_col_width(k)}}" for k in shown)
            out.append(head)
            for r in s["rows"]:
                st = r["stats"]
                rank = r["rank"] if r["rank"] is not None else ""
                out.append(f"    {rank:>3} {r['team'][:24]:<24}" + "".join(
                    f"{st.get(k, ''):>{_col_width(k)}}" for k in shown))
            noted = [r for r in s["rows"] if r["note"]]
            if noted:
                out.append("    Where that leaves them:")
                for r in noted:
                    out.append(f"      {r['rank']}. {r['team']} - {r['note']}")
            # Where the money places sit, in one line. The bands are the notes
            # ESPN itself attaches, so this is a reading of their data and not
            # an invented cut-off.
            band = _qualification_bands(s["rows"])
            if band:
                out.append(f"    In brief: {band}")
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
                    if b.get("outcome_line"):
                        out.append(f"    {b['outcome_line']}")
                    for row in b["rows"]:
                        how = (f" ({row['reached']})"
                               if row.get("reached") and row["state"] == "out"
                               else "")
                        out.append(f"    [{row['mark']:>3}] {row['position']}. "
                                   f"{row['name']} - {row['detail']}{how}")
                elif b["kind"] == "matches":
                    out.append(f"  {b['label']}:")
                    for m in b["rows"]:
                        tag = "  [in progress]" if m["live"] else ""
                        rnd = f" [{m['round']}]" if m.get("round") else ""
                        out.append(f"    {m['when']:<18} {m['line']}{rnd}{tag}")
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
                    place = f"  {it['venue']}" if it.get("venue") else ""
                    out.append(f"    * {it['date']}  {it['title']}{place}{who}{pair}")
                    if it.get("limits"):
                        out.append(f"      Conditions found: {', '.join(it['limits'])}")
                    if not it.get("venue"):
                        out.append("      No venue named in the source, so treat this "
                                   "as a lead to check, not a booking.")
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
        # The featured watch comes first under its own heading: the owner is
        # actively shopping for it, so it is not one row in a list of eight.
        feats = [i for i in (prices.get("items") or []) if i.get("featured")]
        rest = [i for i in (prices.get("items") or []) if not i.get("featured")]
        for item in feats:
            out.append(f"  {item['label'].upper()} - BEST PRICES NOW")
            if item.get("error"):
                out.append(f"    {item['error']}")
            for o in (item.get("offers") or [])[:prices.get("top_n") or 3]:
                cond = "USED" if o.get("condition") == "used" else "new"
                stock = f" [{o['stock']}]" if o.get("stock") else ""
                beat = (f"  (save R {o['saving']:,})"
                        if o.get("saving") else "")
                out.append(f"    {o['pretty']:>10}  {o['retailer']} - {cond}, "
                           f"{_kind_word(item, o)}{stock}{beat}")
                out.append(f"                {o['title']}")
                out.append(f"                {o['url']}")
            if item.get("all_count"):
                out.append(f"    ({item['all_count']} listings with a price were "
                           f"compared, cheapest first)")
            out.append("")
        out.append("RAM PRICE WATCH")
        for item in rest:
            n = prices.get("top_n") or 3
            out.append(f"  {item['label']} - the {n} cheapest found")
            if item.get("error"):
                out.append(f"    {item['error']}")
            for o in (item.get("offers") or [])[:n]:
                kind = _kind_word(item, o)
                cond = "USED" if o.get("condition") == "used" else "new"
                stock = f" [{o['stock']}]" if o.get("stock") else ""
                beat = (f"  (save R {o['saving']:,})"
                        if o.get("saving") else "")
                out.append(f"    {o['pretty']:>10}  {o['retailer']} - {cond}, "
                           f"{kind}{stock}{beat}")
                out.append(f"                {o['title']}")
                out.append(f"                {o['url']}")
            if item.get("below_market") and not item.get("error"):
                out.append("    Below market:")
                for b in item["below_market"]:
                    out.append(f"      {b['pretty']}  {b['pct']}% under the median "
                               f"- {b['retailer']} - {b['title']}")
            if item.get("all_count"):
                out.append(f"    ({item['all_count']} listings with a price were "
                           f"compared)")
        out.append("")

    dd = data.get("deals") or {}
    if dd.get("enabled"):
        out.append("DEALS & BLACK FRIDAY")
        for g in dd.get("groups") or []:
            if g.get("error"):
                out.append(f"  {g['label']}: {g['error']}")
                continue
            head = f"  {g['label']}"
            if g.get("special_count"):
                head += f" - {g['special_count']} on special"
            out.append(head)
            for it in g["items"][:5]:
                mark = "SPECIAL" if it.get("on_special") else "price"
                when = f"  {it['when']}" if it.get("when") else ""
                price = f"  {it['pretty']}" if it.get("pretty") else ""
                out.append(f"    [{mark:>7}] {it['headline']}{price}{when}")
                if it.get("url"):
                    out.append(f"              {it['url']}")
            if g.get("note"):
                out.append(f"    ({g['note']})")
        if dd.get("error"):
            out.append(f"  {dd['error']}")
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
        brief_map = {b["sport"]: b for b in
                     ((data.get("briefs") or {}).get("sports") or [])}
        next_up = data.get("next_up") or {}
        for sport in sp["enabled"]:
            found = per.get(sport, [])
            brief = brief_map.get(sport) or {}
            stories = brief.get("stories") or []
            brief_html = []
            for story in stories:
                who = (f'<span style="color:{muted};font-size:12px"> &mdash; '
                       f'{esc(story["publisher"])}</span>') if story.get("publisher") else ""
                link = (f'<a href="{esc(story["link"])}" style="color:{ink};'
                        f'text-decoration:none">{esc(story["title"])}</a>'
                        if story.get("link") else esc(story["title"]))
                brief_html.append(
                    f'<div style="font-size:13px;margin:2px 0 0;padding-left:10px;'
                    f'border-left:2px solid {line}">{link}{who}</div>')
            if not stories:
                brief_html.append(
                    f'<div style="font-size:12px;color:{muted};margin:2px 0 0">'
                    f'No recent {esc(sport)} story was found in the news window, '
                    f'so there is no brief to give.</div>')
            if not found:
                # Same words as the text digest: the count line, then - only
                # when a brief exists - a note saying what the count covers.
                # Without the note "nothing in the window" reads as "no
                # information about this sport", which is the owner's complaint.
                note = ('<div style="font-size:12px;color:{m};margin:2px 0 0">'
                        'that is your own event list - the brief above is what '
                        'the news has on it this week</div>'.format(m=muted)
                        if stories else "")
                up = next_up.get(sport) or {}
                up_html = ""
                if up.get("when"):
                    _span = up.get("display") or up["when"]
                    _series = (f' &middot; {esc(up["series"])}'
                               if up.get("series") else "")
                    up_html = (
                        f'<div style="font-size:12px;color:{muted};margin:2px 0 0">'
                        f'Next up: <strong style="color:{ink}">{esc(up.get("name", ""))}'
                        f'</strong>{_series} &mdash; {esc(_span)} ({esc(up["when"])})'
                        f'</div>')
                sport_rows.append(row(
                    f'<strong>{esc(sport)}</strong>{"".join(brief_html)}'
                    f'<div style="font-size:12px;color:{muted};margin:2px 0 0">'
                    f'{esc(sport)}: nothing in the window.</div>{note}{up_html}'))
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
                f'{len(found)} in the window</span>{"".join(brief_html)}'
                f'{"".join(events_html)}{more}'))
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
                + "".join(
                    f'<td style="font-size:12px;color:{muted};padding:1px 6px;'
                    f'text-align:right">{esc(str(q.get(k, "")))}</td>'
                    for k in FR_HTML_STANDING_COLS)
                + f'<td style="font-size:12px;color:{ink};font-weight:700;'
                  f'padding:1px 0 1px 6px;text-align:right">'
                  f'{esc(str(q.get("P", "")))}</td></tr>')
        standing_rows.append(
            f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;margin:0 0 10px">'
            f'<tr><td></td>'
            f'<td style="font-size:11px;color:{muted};padding:0 8px 2px 0">Team</td>'
            f'<td style="font-size:11px;color:{muted};padding:0 6px 2px;text-align:right">P</td>'
            f'<td style="font-size:11px;color:{muted};padding:0 6px 2px;text-align:right">W</td>'
            f'<td style="font-size:11px;color:{muted};padding:0 6px 2px;text-align:right">D</td>'
            + "".join(
                f'<td style="font-size:11px;color:{muted};padding:0 6px 2px;'
                f'text-align:right">'
                f'{STANDINGS_HEAD.get(k, k)}</td>' for k in FR_HTML_STANDING_COLS)
            + f'<td style="font-size:11px;color:{muted};padding:0 0 2px 6px;'
              f'text-align:right">Pts</td>'
            f'</tr>{"".join(cells)}</table>'
            + (f'<div style="font-size:11px;color:{muted};margin:0 0 10px">'
               f'In brief: {esc(st["bands"])}</div>' if st.get("bands") else ""))

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
                    if b.get("outcome_line"):
                        tennis_rows.append(
                            f'<div style="font-size:12px;color:{ink};margin:0 0 4px;'
                            f'padding-left:10px;border-left:2px solid #15803d">'
                            f'{esc(b["outcome_line"])}</div>')
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
                            f'{esc(r["detail"])}'
                            + (f'<span style="color:{muted};font-size:11px"> '
                               f'({esc(r["reached"])})</span>'
                               if r.get("reached") and r["state"] == "out" else "")
                            + '</div>')
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
        # The featured watch gets its own named block above the general one.
        feats = [i for i in (prices.get("items") or []) if i.get("featured")]
        rest = [i for i in (prices.get("items") or []) if not i.get("featured")]
        for item in feats:
            n = prices.get("top_n") or 3
            price_rows.append(head(f'<strong>{esc(item["label"].upper())}</strong>'
                                  f' &middot; best prices now'))
            if item.get("error"):
                price_rows.append(f'<div style="font-size:12px;color:{muted};margin:0 0 6px">'
                                  f'{esc(item["error"])}</div>')
            for o in (item.get("offers") or [])[:n]:
                kind = _kind_word(item, o)
                cond = "used" if o.get("condition") == "used" else "new"
                beat = (f'<span style="color:#15803d;font-size:11px"> save '
                        f'R {o["saving"]:,}</span>' if o.get("saving") else "")
                stock = (f'<span style="color:{muted};font-size:11px"> '
                         f'[{esc(o["stock"])}]</span>' if o.get("stock") else "")
                price_rows.append(row(
                    f'<strong>{esc(o["pretty"])}</strong>'
                    f'<span style="color:{muted};font-size:12px"> &middot; '
                    f'{esc(o["retailer"])} &middot; {cond}, {kind}</span>{stock}{beat}<br>'
                    f'<a href="{esc(o["url"])}" style="color:{ink};font-size:12px;'
                    f'text-decoration:none">{esc(o["title"])}</a>'))
            if item.get("all_count"):
                price_rows.append(
                    f'<div style="font-size:11px;color:{muted};margin:2px 0 8px">'
                    f'{item["all_count"]} listings with a price were compared, '
                    f'cheapest first</div>')
        for item in rest:
            n = prices.get("top_n") or 3
            price_rows.append(head(f'{item["label"]} &middot; the {n} cheapest found'))
            if item.get("error"):
                price_rows.append(f'<div style="font-size:12px;color:{muted};margin:0 0 6px">'
                                  f'{esc(item["error"])}</div>')
            for o in (item.get("offers") or [])[:n]:
                kind = _kind_word(item, o)
                cond = "used" if o.get("condition") == "used" else "new"
                beat = (f'<span style="color:#15803d;font-size:11px"> save '
                        f'R {o["saving"]:,}</span>' if o.get("saving") else "")
                stock = (f'<span style="color:{muted};font-size:11px"> '
                         f'[{esc(o["stock"])}]</span>' if o.get("stock") else "")
                price_rows.append(row(
                    f'<strong>{esc(o["pretty"])}</strong>'
                    f'<span style="color:{muted};font-size:12px"> &middot; '
                    f'{esc(o["retailer"])} &middot; {cond}, {kind}</span>{stock}{beat}<br>'
                    f'<a href="{esc(o["url"])}" style="color:{ink};font-size:12px;'
                    f'text-decoration:none">{esc(o["title"])}</a>'))
            if item.get("all_count"):
                price_rows.append(
                    f'<div style="font-size:11px;color:{muted};margin:2px 0 8px">'
                    f'{item["all_count"]} listings with a price were compared</div>')

    deal_rows: list[str] = []
    dd = data.get("deals") or {}
    if dd.get("enabled"):
        for g in dd.get("groups") or []:
            if g.get("error"):
                deal_rows.append(f'<div style="font-size:12px;color:{muted};margin:0 0 8px">'
                                 f'{esc(g["label"])}: {esc(g["error"])}</div>')
                continue
            label = g["label"] + (f' &middot; {g["special_count"]} on special'
                                  if g.get("special_count") else "")
            deal_rows.append(head(label))
            for it in g["items"][:5]:
                badge = (f'<span style="font-size:11px;color:#15803d;background:#e7f6ec;'
                         f'padding:1px 6px;border-radius:9px">SPECIAL</span>'
                         if it.get("on_special") else
                         f'<span style="font-size:11px;color:{muted}">price</span>')
                price = (f'<strong> {esc(it["pretty"])}</strong>'
                         if it.get("pretty") else "")
                when = (f'<span style="color:{muted};font-size:12px"> '
                        f'&middot; {esc(it["when"])}</span>' if it.get("when") else "")
                link = (f'<a href="{esc(it["url"])}" style="color:{ink};'
                        f'text-decoration:none">{esc(it["headline"])}</a>'
                        if it.get("url") else esc(it["headline"]))
                deal_rows.append(row(f'{badge} {link}{price}{when}'))
            if g.get("note"):
                deal_rows.append(f'<div style="font-size:11px;color:{muted};margin:0 0 8px">'
                                 f'{esc(g["note"])}</div>')

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
        "deals": "".join(deal_rows),
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
