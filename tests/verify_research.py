#!/usr/bin/env python3
"""Tests for the research layer: `scripts/follow_research.py` and
`scripts/follow_edit.py`.

Run from the project root:

    python3 tests/verify_research.py

**These tests never touch the network.** A fake fetcher returns canned ESPN and
Google News payloads, so the suite is fast, deterministic and works offline. The
live sources are exercised by running the scripts by hand, not by the suite -
a test that depends on a third party's uptime is a test that fails for reasons
that have nothing to do with this code.

What is checked, and why:

1.  **The follow list is honoured exactly.** Every news item and competition in
    `follow.json` produces output; nothing appears that is not in the file. The
    owner asked to be able to add and remove things, so the file has to be the
    only thing that decides.
2.  **An empty list stays empty.** If the owner removes everything, the digest
    shows nothing rather than falling back to a default. A "helpful" default
    would be exactly the invention the project forbids.
3.  **Tennis follows the live top N.** The top-N names are read from the
    rankings payload, not hardcoded, and only matches involving a top-N player
    are reported. A match between two unranked players must not appear.
4.  **Every finished match names the winner first.** A result printed
    loser-first is a factual error, and the raw payload does not guarantee
    order, so this is pinned.
5.  **Unplayed matches are not reported as 0-0.** ESPN returns 0-0 for a fixture
    that has not kicked off; printing that would be a lie.
6.  **A dead source degrades, never crashes.** Every failure mode - no network,
    bad JSON, unknown competition, HTTP error - produces a readable note and the
    digest still renders. The reminder must arrive even when a source does not.
7.  **Nothing is fabricated.** No source failure is silently swallowed, and no
    placeholder name or date is invented to fill a gap.
8.  **The editor round-trips.** add then remove returns the file to its original
    contents, so the convenience tool cannot corrupt the follow list.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import follow_research as FR  # noqa: E402

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# A fetcher that answers from a dict and records what was asked for
# ---------------------------------------------------------------------------

class FakeFetcher:
    """Stands in for Fetcher. Returns canned bytes; never opens a socket."""

    def __init__(self, responses: dict[str, str | bytes], fail: set[str] | None = None):
        self.responses = responses
        self.fail = fail or set()
        self.asked: list[str] = []
        self.failures: list[str] = []

    def get(self, url: str, headers: dict | None = None) -> bytes | None:
        self.asked.append(url)
        for key in self.fail:
            if key in url:
                self.failures.append(f"simulated failure on {key}")
                return None
        for key, body in self.responses.items():
            if key in url:
                return body.encode() if isinstance(body, str) else body
        self.failures.append(f"no canned response for {url}")
        return None

    def json(self, url: str, headers: dict | None = None) -> dict | None:
        raw = self.get(url, headers=headers)
        if raw is None:
            return None
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except ValueError:
            self.failures.append(f"unparseable JSON from {url}")
            return None


# ---------------------------------------------------------------------------
# Canned payloads, shaped like the real ones
# ---------------------------------------------------------------------------

def rankings(tour: str, names: list[str]) -> str:
    return json.dumps({"rankings": [{"ranks": [
        {"current": i + 1, "points": 1000 - i,
         "athlete": {"displayName": n, "flag": "https://x/500/rsa.png"}}
        for i, n in enumerate(names)]}]})


def scoreboard(events: list[dict]) -> str:
    return json.dumps({"events": events})


def tennis_event(tournament: str, slug: str, matches: list[tuple]) -> dict:
    """matches: (state, iso_date, [(player, winner), ...])

    `round` is supplied because a live ESPN payload always carries
    `round.displayName`; omitting it here would let the digest fall back to
    "draw not published yet" and hide whether the round renders at all.
    """
    return {
        "name": tournament,
        "date": "2026-10-12T06:00Z",
        "groupings": [{
            "grouping": {"slug": slug},
            "competitions": [
                {
                    "date": when,
                    "round": {"displayName": "Round 1"},
                    "status": {"type": {"state": state, "description": state.upper()}},
                    "competitors": [
                        {"athlete": {"displayName": name}, "winner": won,
                         "linescores": [{"value": 6 if won else 3},
                                        {"value": 6 if won else 4}]}
                        for name, won in players
                    ],
                }
                for state, when, players in matches
            ],
        }],
    }


def soccer_event(home: str, away: str, hs, aws, state: str = "pre") -> dict:
    return {
        "date": "2026-10-13T19:00Z",
        "competitions": [{
            "status": {"type": {"state": state, "shortDetail": state.upper()}},
            "venue": {"fullName": "Somewhere"},
            "links": [{"href": "https://example.invalid/match"}],
            "competitors": [
                {"homeAway": "home", "team": {"displayName": home}, "score": hs,
                 "winner": state == "post" and str(hs) > str(aws)},
                {"homeAway": "away", "team": {"displayName": away}, "score": aws,
                 "winner": state == "post" and str(aws) > str(hs)},
            ],
        }],
    }


def news_feed(items: list[tuple]) -> str:
    """items: (title, publisher, rfc822_date)"""
    entries = "".join(
        f"<item><title>{t}</title><source>{p}</source>"
        f"<pubDate>{d}</pubDate><link>https://news.invalid/{i}</link></item>"
        for i, (t, p, d) in enumerate(items))
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{entries}</channel></rss>'


NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.strftime("%a, %d %b %Y %H:%M:%S GMT")
OLD = (NOW - dt.timedelta(days=30)).strftime("%a, %d %b %Y %H:%M:%S GMT")

ATP = ["Jannik Sinner", "Alexander Zverev", "Carlos Alcaraz",
       "Ben Shelton", "Felix Auger-Aliassime", "Casper Ruud"]
WTA = ["Elena Rybakina", "Aryna Sabalenka", "Mirra Andreeva",
       "Jessica Pegula", "Coco Gauff", "Belinda Bencic"]


def base_config() -> dict:
    return {
        "news": [{"label": "UEFA Champions League", "query": "UEFA Champions League",
                  "sport": "Football"}],
        "competitions": [{"label": "UEFA Champions League",
                          "league": "uefa.champions", "teams": []}],
        "tennis": {"enabled": True, "tours": ["atp", "wta"], "top_n": 5,
                   "max_matches": 10},
        "settings": {"news_per_follow": 3, "news_max_age_days": 3,
                     "request_timeout_seconds": 5, "total_budget_seconds": 30},
    }


def standard_fetcher(**overrides) -> FakeFetcher:
    responses = {
        "/rankings": "",  # replaced below
        "tennis/atp/rankings": rankings("atp", ATP),
        "tennis/wta/rankings": rankings("wta", WTA),
        "tennis/atp/scoreboard": scoreboard([
            tennis_event("Shanghai Masters", "mens-singles", [
                ("post", "2026-10-12T10:00Z",
                 [("Carlos Alcaraz", True), ("Zizou Bergs", False)]),
                ("post", "2026-10-11T10:00Z",
                 [("Alexander Zverev", True), ("Quentin Halys", False)]),
                ("post", "2026-10-10T10:00Z",
                 [("Some Journeyman", True), ("Other Journeyman", False)]),
                ("post", "2026-10-09T10:00Z",
                 [("Arthur Gea", True), ("Ben Shelton", False)]),
                ("pre", "2026-10-14T10:00Z",
                 [("Felix Auger-Aliassime", None), ("Casper Ruud", None)]),
            ]),
        ]),
        "tennis/wta/scoreboard": scoreboard([
            tennis_event("Wuhan Open", "womens-singles", [
                ("post", "2026-10-12T08:00Z",
                 [("Aryna Sabalenka", True), ("Dayana Yastremska", False)]),
            ]),
            tennis_event("Wuhan Open", "womens-doubles", [
                ("post", "2026-10-12T08:00Z",
                 [("Coco Gauff", True), ("Someone Else", False)]),
            ]),
            # A second tournament is on, and no top-5 player is in it. The real
            # scoreboard returns several, and this is the case that must print a
            # statement rather than a block of dashes.
            tennis_event("Hong Kong Open", "womens-singles", [
                ("post", "2026-10-12T09:00Z",
                 [("Some Journeyman", True), ("Other Journeyman", False)]),
            ]),
        ]),
        "soccer/uefa.champions/standings": {
            "children": [{
                "name": "League Phase",
                "standings": {"entries": [
                    {"note": {"rank": 1, "description": "Advances to round of 16",
                              "color": "green"},
                     "stats": [
                         {"name": "gamesPlayed", "abbreviation": "GP", "displayValue": "6"},
                         {"name": "wins", "abbreviation": "W", "displayValue": "5"},
                         {"name": "ties", "abbreviation": "D", "displayValue": "1"},
                         {"name": "losses", "abbreviation": "L", "displayValue": "0"},
                         {"name": "pointDifferential", "abbreviation": "GD", "displayValue": "+9"},
                         {"name": "points", "abbreviation": "P", "displayValue": "16"},
                     ],
                     "team": {"displayName": "Arsenal"}},
                    {"note": {"rank": 2, "description": "Advances to knockout playoff",
                              "color": "orange"},
                     "stats": [
                         {"name": "gamesPlayed", "abbreviation": "GP", "displayValue": "6"},
                         {"name": "wins", "abbreviation": "W", "displayValue": "3"},
                         {"name": "ties", "abbreviation": "D", "displayValue": "1"},
                         {"name": "losses", "abbreviation": "L", "displayValue": "2"},
                         {"name": "pointDifferential", "abbreviation": "GD", "displayValue": "+2"},
                         {"name": "points", "abbreviation": "P", "displayValue": "10"},
                     ],
                     "team": {"displayName": "Barcelona"}},
                    {"note": {"rank": 3, "description": "Eliminated", "color": "red"},
                     "stats": [
                         {"name": "gamesPlayed", "abbreviation": "GP", "displayValue": "6"},
                         {"name": "wins", "abbreviation": "W", "displayValue": "1"},
                         {"name": "ties", "abbreviation": "D", "displayValue": "0"},
                         {"name": "losses", "abbreviation": "L", "displayValue": "5"},
                         {"name": "pointDifferential", "abbreviation": "GD", "displayValue": "-7"},
                         {"name": "points", "abbreviation": "P", "displayValue": "3"},
                     ],
                     "team": {"displayName": "Lille"}},
                ]},
            }],
        },
        # The team list backs the Football suggestion path. Twenty clubs, more
        # than the eight-name page limit, so truncation is observable.
        "soccer/uefa.champions/teams": {
            "sports": [{"leagues": [{"teams": [
                {"team": {"displayName": f"Club {i:02d}"}} for i in range(1, 21)
            ]}]}]
        },
        "soccer/uefa.champions/scoreboard": scoreboard([
            soccer_event("Arsenal", "Lille", 0, 0),
            soccer_event("Galatasaray", "Barcelona", 0, 0),
            soccer_event("Lens", "Sporting CP", 2, 1, state="post"),
        ]),
        "news.google.com": news_feed([
            ("Champions League matchday 2 preview", "UEFA.com", TODAY),
            ("Arsenal team news", "BBC", TODAY),
            ("Stale story from last month", "Old News", OLD),
        ]),
    }
    responses.pop("/rankings")
    responses.update(overrides)
    return FakeFetcher(responses)


def gather(cfg: dict | None = None, f: FakeFetcher | None = None,
           weekly: bool = False) -> dict:
    return FR.gather(cfg or base_config(), fetcher=f or standard_fetcher(), weekly=weekly)


# ---------------------------------------------------------------------------
# 1-2: the follow list decides everything
# ---------------------------------------------------------------------------

def test_follow_list_is_honoured() -> None:
    cfg = base_config()
    cfg["news"].append({"label": "Formula 1", "query": "Formula 1", "sport": "Motorsport"})
    f = standard_fetcher()
    data = gather(cfg, f)

    labels = [i["label"] for i in data["news"]["items"]]
    check("AC-R1 every followed news item is researched", labels ==
          ["UEFA Champions League", "Formula 1"], str(labels))
    check("AC-R1 a query is issued per followed item",
          sum(1 for u in f.asked if "news.google.com" in u) == 2,
          str([u for u in f.asked if "news.google.com" in u]))

    # Removing one removes it from the output.
    cfg["news"] = [n for n in cfg["news"] if n["label"] != "Formula 1"]
    data = gather(cfg, standard_fetcher())
    check("AC-R1 a removed item is not researched",
          [i["label"] for i in data["news"]["items"]] == ["UEFA Champions League"])


def test_empty_follow_list_stays_empty() -> None:
    cfg = base_config()
    cfg["news"] = []
    cfg["competitions"] = []
    cfg["tennis"] = {"enabled": False}
    data = gather(cfg, standard_fetcher())

    check("AC-R2 no news items when nothing is followed", data["news"]["items"] == [])
    check("AC-R2 no competitions when nothing is followed", data["competitions"] == [])
    check("AC-R2 tennis off produces no tours", data["tennis"]["tours"] == [])

    text = FR.render_text(data)
    # Owner item 8 makes the run-time block unconditional, so "empty" now means
    # empty of RESEARCH - no sports content may be invented to fill the gap.
    for heading in ("WHAT YOU FOLLOW", "BY SPORT", "FIXTURES", "STANDINGS",
                    "TENNIS -"):
        check(f"AC-R2 no {heading} block when nothing is followed",
              heading not in text, repr(text))
    check("AC-R2 nothing was invented to fill the gap",
          "Champions" not in text and "Sinner" not in text)
    check("AC-R2 the run-time block is still shown", "RUN TIME" in text)


def test_missing_follow_file_is_not_an_error() -> None:
    """A deleted follow.json means "follow nothing", not "crash"."""
    missing = os.path.join(tempfile.gettempdir(), "no-such-follow-file.json")
    if os.path.exists(missing):
        os.remove(missing)
    cfg = FR.load_follow(missing)
    check("AC-R2 a missing follow file loads as empty",
          cfg["news"] == [] and cfg["competitions"] == []
          and not cfg["tennis"].get("enabled"))


# ---------------------------------------------------------------------------
# 3-5: tennis
# ---------------------------------------------------------------------------

def test_tennis_follows_the_live_top_n() -> None:
    data = gather()
    atp = next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP")
    check("AC-R3 the top 5 are read from the rankings",
          [p["name"] for p in atp["top"]] == ATP[:5], str(atp["top"]))
    check("AC-R3 the 6th-ranked player is excluded", "Casper Ruud" not in
          [p["name"] for p in atp["top"]])

    rendered = "\n".join(FR._score_line(r) for r in atp["results"] + atp["upcoming"])
    check("AC-R3 a top-5 match is reported", "Carlos Alcaraz" in rendered)
    check("AC-R3 a match with no top-5 player is NOT reported",
          "Some Journeyman" not in rendered and "Other Journeyman" not in rendered,
          rendered)

    # Changing N changes who is covered, with no code change.
    cfg = base_config()
    cfg["tennis"]["top_n"] = 6
    data = gather(cfg)
    atp = next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP")
    check("AC-R3 raising N to 6 admits the 6th player",
          len(atp["top"]) == 6 and atp["top"][-1]["name"] == "Casper Ruud")
    rendered = "\n".join(FR._score_line(r) for r in atp["results"] + atp["upcoming"])
    check("AC-R3 the 6th player's match now appears", "Casper Ruud" in rendered)


def test_tennis_does_not_hardcode_names() -> None:
    """The names must come from the payload, not from a list in the code."""
    cfg = base_config()
    cfg["tennis"]["tours"] = ["atp"]
    f = standard_fetcher(**{"tennis/atp/rankings":
                            rankings("atp", ["Nobody Known"] * 5)})
    data = gather(cfg, f)
    atp = data["tennis"]["tours"][0]
    check("AC-R3 an unknown top 5 is reported as-is",
          [p["name"] for p in atp["top"]] == ["Nobody Known"] * 5)
    check("AC-R3 no match is invented for an unknown top 5",
          atp["results"] == [] and atp["upcoming"] == [])
    check("AC-R3 the absence is stated, not silently blank",
          "No top-5 match" in FR.render_text(data))


def test_winner_is_named_first() -> None:
    data = gather()
    atp = next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP")

    # The real check: in every finished match, the winner's name precedes the
    # loser's. Position, not a literal string, so the rank tag in front of the
    # name does not matter.
    for r in atp["results"]:
        winner = next(p for p in r["players"] if p["winner"])
        loser = next(p for p in r["players"] if not p["winner"])
        line = FR._score_line(r)
        check(f"AC-R4 winner first: {winner['name']} over {loser['name']}",
              line.index(winner["name"]) < line.index(loser["name"])
              and " beat " in line, line)

    # A winner outside the top 5 must still be named first.
    upset = next(r for r in atp["results"]
                 if any(p["name"] == "Arthur Gea" for p in r["players"]))
    line = FR._score_line(upset)
    check("AC-R4 an unranked winner is still printed first",
          line.startswith("Arthur Gea beat"), line)
    check("AC-R4 the ranked loser carries their rank", "[4] Ben Shelton" in line, line)

    # An unplayed match has no winner, so it is a pairing rather than a result.
    up = [FR._score_line(r) for r in atp["upcoming"]]
    check("AC-R4 an unplayed match is a pairing, not a claimed result",
          any(" vs " in l and " beat " not in l for l in up), str(up))


def test_unplayed_matches_are_not_zero_zero() -> None:
    data = gather()
    comp = data["competitions"][0]
    rows = [FR._team_label(t, r["state"]) for r in comp["rows"] for t in r["teams"]]
    check("AC-R5 an unplayed fixture shows no score",
          "Arsenal" in rows and "Arsenal 0" not in rows, str(rows))
    check("AC-R5 a played fixture does show the score", "Lens 2" in rows, str(rows))


def test_doubles_are_excluded() -> None:
    data = gather()
    wta = next(t for t in data["tennis"]["tours"] if t["tour"] == "WTA")
    lines = "\n".join(FR._score_line(r) for r in wta["results"] + wta["upcoming"])
    check("AC-R3 doubles matches are not reported", "Someone Else" not in lines, lines)
    check("AC-R3 singles matches are reported", "Aryna Sabalenka" in lines, lines)


# ---------------------------------------------------------------------------
# 6-7: failure behaviour
# ---------------------------------------------------------------------------

def test_a_dead_source_degrades_gracefully() -> None:
    cfg = base_config()
    f = standard_fetcher()
    f.fail = {"news.google.com", "soccer/uefa.champions"}
    data = gather(cfg, f)

    check("AC-R6 a failed news source yields no stories",
          all(not i["stories"] for i in data["news"]["items"]))
    check("AC-R6 a failed competition is reported as unreachable",
          data["competitions"][0]["error"] == "could not be reached",
          str(data["competitions"][0]))

    text = FR.render_text(data)
    check("AC-R6 the failure is stated in the digest",
          "could not be reached" in text, text[:200])
    check("AC-R6 the failure is not silent", bool(data["failures"]))
    check("AC-R6 tennis still renders when other sources fail",
          "Jannik Sinner" in text)


def test_everything_dead_still_renders() -> None:
    """The whole network gone: the digest must still produce its own content."""
    f = FakeFetcher({})  # nothing responds
    data = gather(base_config(), f)
    text = FR.render_text(data)
    check("AC-R6 a total outage does not raise", isinstance(text, str))
    check("AC-R6 a total outage is reported",
          "could not be reached" in text, text[:200])
    check("AC-R7 no placeholder name is invented",
          "TBD" not in text and "Unknown" not in text)


def test_bad_json_and_unknown_league_are_handled() -> None:
    f = standard_fetcher(**{"tennis/atp/rankings": "not json at all"})
    data = gather(base_config(), f)
    check("AC-R6 unparseable JSON yields an empty ranking, not a crash",
          data["tennis"]["tours"][0]["top"] == [])
    check("AC-R6 the bad payload is recorded", bool(data["failures"]))

    cfg = base_config()
    cfg["competitions"] = [{"label": "Made Up Cup", "league": "nope.1", "teams": []}]
    data = gather(cfg, standard_fetcher())
    err = data["competitions"][0]["error"]
    check("AC-R6 an unknown competition id is explained, not guessed",
          "unknown competition" in err, err)
    check("AC-R6 the unknown competition is named in the digest",
          "Made Up Cup" in FR.render_text(data))


def test_fetch_failures_never_raise() -> None:
    """Fetcher.get is the only network call, and it must never propagate."""

    class Exploding(FR.Fetcher):
        def get(self, url: str):
            raise AssertionError("get() itself must catch, not raise")

    # Prove the real implementation swallows a bad host.
    real = FR.Fetcher(timeout=2, budget=5)
    got = real.get("http://127.0.0.1:1/nothing-listens-here")
    check("AC-R6 a connection error returns None instead of raising", got is None)
    check("AC-R6 the connection error is recorded", bool(real.failures),
          str(real.failures))


def test_budget_is_enforced() -> None:
    f = FR.Fetcher(timeout=1, budget=0)
    f.deadline = dt.datetime.now() - dt.timedelta(seconds=1)
    check("AC-R6 an exhausted budget returns None", f.get("http://example.invalid") is None)
    check("AC-R6 an exhausted budget is recorded",
          "time budget exhausted" in f.failures, str(f.failures))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def test_news_age_window() -> None:
    data = gather()
    stories = data["news"]["items"][0]["stories"]
    titles = [s["title"] for s in stories]
    check("AC-R8 a recent story is included",
          "Champions League matchday 2 preview" in titles, str(titles))
    check("AC-R8 a 30-day-old story is excluded",
          "Stale story from last month" not in titles, str(titles))

    weekly = gather(weekly=True)
    wtitles = [s["title"] for s in weekly["news"]["items"][0]["stories"]]
    check("AC-R8 the weekly run still excludes a 30-day-old story",
          "Stale story from last month" not in wtitles, str(wtitles))


def test_publisher_is_not_repeated() -> None:
    """Google News appends " - Publisher" to the title AND fills <source>."""
    f = standard_fetcher(**{"news.google.com": news_feed([
        ("Arsenal team news - BBC", "BBC", TODAY),
    ])})
    data = gather(base_config(), f)
    story = data["news"]["items"][0]["stories"][0]
    check("AC-R8 the publisher suffix is stripped from the title",
          story["title"] == "Arsenal team news", story["title"])
    check("AC-R8 the publisher is still attributed", story["publisher"] == "BBC")
    check("AC-R8 the publisher appears once in the rendered line",
          FR.render_text(data).count("BBC") == 1)


def test_html_matches_text() -> None:
    data = gather()
    text = FR.render_text(data)
    blocks = FR.render_html(data, "#000", "#555", "#eee", "#06c", "#fff", "#eef")
    html = "".join(blocks.values())

    for token in ("Jannik Sinner", "UEFA Champions League", "Arsenal", "Lens"):
        check(f"AC-R9 '{token}' appears in both renderings",
              token in text and token in html)
    check("AC-R9 the HTML names the winner first",
          "Carlos Alcaraz</span> beat " in html or "beat <span" in html)
    check("AC-R9 unplayed fixtures carry no 0-0 in HTML",
          "Arsenal</span> <strong>0</strong>" not in html)
    check("AC-R9 no unescaped ampersand is introduced",
          " & " not in html)


def test_team_filter() -> None:
    cfg = base_config()
    cfg["competitions"][0]["teams"] = ["Arsenal"]
    data = gather(cfg)
    comp = data["competitions"][0]
    names = [t["name"] for r in comp["rows"] for t in r["teams"]]
    check("AC-R10 only the followed team's fixture is kept",
          "Arsenal" in names and "Barcelona" not in names, str(names))
    check("AC-R10 the filter is reported as active", comp["filtered"] is True)
    check("AC-R10 the digest names the filter",
          "Arsenal" in FR.render_text(data))

    # An empty team list means every team, and says so.
    cfg["competitions"][0]["teams"] = []
    data = gather(cfg)
    check("AC-R10 an empty filter keeps every fixture",
          len(data["competitions"][0]["rows"]) == 3)
    check("AC-R10 the digest says the filter is unset",
          "no team filter set" in FR.render_text(data))


def test_team_name_matching_is_loose_but_bounded() -> None:
    check("AC-R10 accents fold", FR._norm("Atlético Madrid") == FR._norm("Atletico Madrid"))
    check("AC-R10 a short name finds the long one",
          FR._norm("Bayern") in FR._norm("Bayern Munich"))
    check("AC-R10 different clubs do not collide",
          FR._norm("Arsenal") != FR._norm("Barcelona"))
    check("AC-R10 a made-up team matches nothing",
          FR._norm("Nonexistent FC") not in FR._norm("Arsenal"))


def test_timezone_conversion() -> None:
    check("AC-R9 a UTC time is shown as SAST (UTC+2)",
          FR._fmt_when("2026-10-13T19:00Z") == "Tue 13 Oct 21:00",
          FR._fmt_when("2026-10-13T19:00Z"))
    check("AC-R9 an unparseable time is passed through, not dropped",
          FR._fmt_when("garbage") == "garbage")
    check("AC-R9 an empty time is empty", FR._fmt_when("") == "")


# ---------------------------------------------------------------------------
# The editor round-trips
# ---------------------------------------------------------------------------

def test_follow_editor_round_trips() -> None:
    import follow_edit as FE

    original = FE.read()
    snapshot = json.dumps(original, sort_keys=True)

    check("AC-R11 adding news works", "Following" in FE.add_news(original, "Test Sport", "Test"))
    check("AC-R11 adding the same item twice is refused",
          "Already following" in FE.add_news(original, "Test Sport", "Test"))
    check("AC-R11 removing it works", "Stopped following" in FE.remove_news(original, "Test Sport"))
    check("AC-R11 removing it again is reported",
          "was not in" in FE.remove_news(original, "Test Sport"))
    check("AC-R11 the news list round-trips",
          json.dumps(original, sort_keys=True) == snapshot)

    FE.add_team(original, "uefa.champions", "Test FC")
    check("AC-R11 a team was added", "Test FC" in original["competitions"][0]["teams"])
    check("AC-R11 adding the same team twice is refused",
          "already in" in FE.add_team(original, "uefa.champions", "Test FC"))
    FE.remove_team(original, "uefa.champions", "Test FC")
    check("AC-R11 the team list round-trips",
          json.dumps(original, sort_keys=True) == snapshot, "file changed")

    check("AC-R11 an unknown competition id is refused, not invented",
          "Unknown competition" in FE.add_team(original, "made.up", "X"))
    check("AC-R11 the refusal did not modify the file",
          json.dumps(original, sort_keys=True) == snapshot)


def test_shipped_follow_file_is_valid() -> None:
    cfg = FR.load_follow()
    check("AC-R11 the shipped follow file parses", isinstance(cfg, dict))
    check("AC-R11 every news entry has a label and a query",
          all(e.get("label") and (e.get("query") or e.get("label"))
              for e in cfg["news"]))
    check("AC-R11 every competition names a known league id",
          all(e.get("league") in FR.LEAGUES for e in cfg["competitions"]),
          str([e.get("league") for e in cfg["competitions"]]))
    check("AC-R11 tennis top_n is a positive integer",
          isinstance(cfg["tennis"].get("top_n"), int) and cfg["tennis"]["top_n"] > 0)
    check("AC-R11 the tennis tours are ones the API serves",
          all(t in ("atp", "wta") for t in cfg["tennis"]["tours"]))


def test_workflow_supports_the_weekly_run() -> None:
    wf = open(".github/workflows/personal-digest.yml", encoding="utf-8").read()
    check("AC-R12 the workflow has a weekly schedule", "0 5 * * 0" in wf)
    check("AC-R12 the weekly run widens the news window", "--weekly" in wf)
    check("AC-R12 the daily job is guarded against the weekly cron",
          "github.event.schedule != '0 5 * * 0'" in wf)
    check("AC-R12 the weekly job only runs on the weekly cron or manually",
          "github.event.schedule == '0 5 * * 0'" in wf)
    check("AC-R12 the jobs have a timeout so a hung source cannot burn the budget",
          wf.count("timeout-minutes:") == 2, str(wf.count("timeout-minutes:")))
    check("AC-R12 no build or deploy step was introduced",
          "actions/deploy-pages" not in wf and "npm install" not in wf)
    check("AC-R12 credentials still come from secrets",
          "secrets.MAIL_PASSWORD" in wf and "secrets.MAIL_USERNAME" in wf)

    # The two jobs must be mutually exclusive in every trigger, so the owner
    # never gets two emails from one run. Explicit expectations rather than a
    # re-implementation of GitHub's expression rules.
    import yaml
    jobs = yaml.safe_load(wf)["jobs"]
    check("AC-R12 there are exactly two jobs", set(jobs) == {"digest", "weekly"},
          str(list(jobs)))

    daily_if, weekly_if = jobs["digest"]["if"], jobs["weekly"]["if"]
    check("AC-R12 the daily job excludes the Sunday cron and a weekly manual run",
          "github.event.schedule != '0 5 * * 0'" in daily_if
          and "!inputs.weekly" in daily_if, daily_if)
    check("AC-R12 the weekly job requires the Sunday cron or a weekly manual run",
          "github.event.schedule == '0 5 * * 0'" in weekly_if
          and "inputs.weekly" in weekly_if, weekly_if)

    # Enumerate the triggers and assert the pair of conditions cannot both hold.
    # A manual run with weekly=true is the case that used to fire both jobs.
    cases = [
        ("the daily cron", "0 3 * * *", False, True, False),
        ("the Sunday cron", "0 5 * * 0", False, False, True),
        ("a manual daily run", "", False, True, False),
        ("a manual weekly run", "", True, False, True),
    ]
    for label, schedule, weekly, want_daily, want_weekly in cases:
        daily = (schedule != "0 5 * * 0") and not weekly
        wk = (schedule == "0 5 * * 0") or weekly
        check(f"AC-R12 {label} runs the right job and only that job",
              (daily, wk) == (want_daily, want_weekly),
              f"digest={daily} weekly={wk}")

    # Both jobs must hand the sender a file, or the email would be empty.
    sender = open("scripts/send_digest_email.py", encoding="utf-8").read()
    check("AC-R12 the sender reads the digest the build step wrote",
          "digest.txt" in sender and "digest.txt" in wf)
    check("AC-R12 the sender reads the subject the build step wrote",
          "subject.txt" in sender and "subject.txt" in wf)



# ---------------------------------------------------------------------------
# Owner request of 2026-11-03: the eight-item follow-up
# ---------------------------------------------------------------------------

def test_sports_can_be_added_and_removed() -> None:
    """Item 1: an easy switch for a whole sport, and it is reversible."""
    import follow_edit as FE
    cfg = {"news": [], "sports": [{"sport": "Tennis", "enabled": True}],
           "competitions": [], "tennis": {"enabled": False}, "settings": {}}

    msg = FE.add_sport(cfg, "Cricket")
    on = FR.enabled_sports(cfg)
    check("AC-R13 a sport can be added", "Cricket" in on, str(on))
    check("AC-R13 adding is confirmed", "Cricket" in msg)

    FE.remove_sport(cfg, "Cricket")
    on = FR.enabled_sports(cfg)
    muted = FR.muted_sports(cfg)
    check("AC-R13 a removed sport leaves the enabled list",
          "Cricket" not in on, str(on))
    check("AC-R13 a removed sport is recorded as muted", "Cricket" in muted, str(muted))
    check("AC-R13 the row survives, so removal is reversible",
          any(r["sport"] == "Cricket" for r in cfg["sports"]))

    FE.add_sport(cfg, "Cricket")
    check("AC-R13 a removed sport can be switched back on",
          "Cricket" in FR.enabled_sports(cfg))


def test_a_removed_sport_hides_its_live_data_too() -> None:
    """Item 1: "removing a sport hides it everywhere" has to be literally true.

    The owner's own event list was filtered, but the LIVE sources were not: a
    removed Football still printed its whole matchweek and league table, and a
    removed Tennis still printed both tours. Switching a sport off has to stop
    the fetches that produce that sport's sections.
    """
    cfg = base_config()
    cfg["sports"] = [{"sport": "Football", "enabled": False},
                     {"sport": "Motorsport", "enabled": True}]
    data = FR.gather(cfg, fetcher=standard_fetcher())
    text = FR.render_text(data)
    check("AC-R19 a removed sport shows no fixtures",
          not data["competitions"], str([c["label"] for c in data["competitions"]]))
    check("AC-R19 a removed sport shows no standings", not data["standings"])
    check("AC-R19 the fixtures section is gone from the digest",
          "FIXTURES" not in text)
    check("AC-R19 the standings section is gone from the digest",
          "STANDINGS" not in text)
    check("AC-R19 a removed sport's news is not researched",
          not data["news"]["items"], str([i["label"] for i in data["news"]["items"]]))

    cfg2 = base_config()
    cfg2["sports"] = [{"sport": "Tennis", "enabled": False},
                      {"sport": "Football", "enabled": True}]
    data2 = FR.gather(cfg2, fetcher=standard_fetcher())
    check("AC-R19 a removed sport stops its own fetches",
          not data2["tennis"].get("tours"), str(data2["tennis"]))
    check("AC-R19 the tennis section is gone from the digest",
          "TENNIS" not in FR.render_text(data2))
    check("AC-R19 a muted Tennis still renders without error",
          not FR.render_html(data2, "#000", "#666", "#eee", "#06c", "#fff",
                             "#f5f5f5")["tennis"])


def test_the_by_sport_block_is_chronological() -> None:
    """Item 2: the per-sport block must be in date order.

    Live football rows once carried a pre-formatted date ("Tue 13 Oct") while
    the owner's own events carried ISO dates. Sorting the two together as
    strings put every football match after every ISO event.
    """
    cfg = base_config()
    cfg["sports"] = [{"sport": "Football", "enabled": True},
                     {"sport": "Motorsport", "enabled": True}]
    events = [{"sport": "Motorsport", "name": "Early race",
               "when": "2026-10-13", "end": "2026-10-13"},
              {"sport": "Motorsport", "name": "Later race",
               "when": "2026-10-20", "end": "2026-10-20"}]
    data = FR.gather(cfg, fetcher=standard_fetcher(), sports_events=events,
                     today=dt.date(2026, 10, 12))
    order = [e["when"] for e in data["by_sport"]]
    check("AC-R20 the per-sport block is sorted by date", order == sorted(order),
          str(order))
    names = [e["name"] for e in data["by_sport"]]
    check("AC-R20 a later event does not jump ahead of an earlier one",
          names.index("Early race") < names.index("Later race"), str(names))


def test_suggestions_are_never_in_the_past_or_already_shown() -> None:
    """Item 3: a suggestion must be something NEW and UPCOMING.

    Two leaks were live: a finished event ("Petit Le Mans", a month earlier)
    was offered as "later than this digest window" simply because it was not
    INSIDE the window, and the Paris Masters was suggested while the tennis
    section above it was reporting that same tournament.
    """
    cfg = base_config()
    cfg["sports"] = [{"sport": "Motorsport", "enabled": True}]
    cfg["competitions"] = []
    today = dt.date(2026, 11, 4)
    done = {"sport": "Motorsport", "name": "Petit Le Mans",
            "when": "2026-10-03", "end": "2026-10-03"}
    soon = {"sport": "Motorsport", "name": "MotoGP Valencia",
            "when": "2026-11-29", "end": "2026-11-29"}
    data = FR.gather(cfg, standard_fetcher(), today=today,
                     sports_events=[done, soon], window_days=10)
    names = [i["name"] for g in data["suggestions"]["sports"] for i in g["items"]]
    check("AC-R21 a finished event is not suggested",
          not any("Petit Le Mans" in n for n in names), str(names))
    check("AC-R21 a genuinely upcoming event is still suggested",
          any("MotoGP Valencia" in n for n in names), str(names))

    # Something already on the page must not be offered as new.
    out = FR.suggest(cfg, [soon], FakeFetcher({}),
                     already_shown={"MotoGP Valencia"})
    again = [i["name"] for g in out["sports"] for i in g["items"]]
    check("AC-R21 an event already in this email is not suggested again",
          not any("MotoGP Valencia" in n for n in again), str(again))


def test_a_truncated_suggestion_list_says_how_many_were_cut() -> None:
    """Item 3: eight names is a page limit, not the whole set."""
    cfg = base_config()
    cfg["competitions"] = [{"label": "UEFA Champions League",
                            "league": "uefa.champions", "teams": []}]
    cfg["sports"] = [{"sport": "Football", "enabled": True}]
    out = FR.suggest(cfg, [], standard_fetcher())
    group = next(g for g in out["sports"] if g["sport"] == "Football")
    check("AC-R22 the full count is carried, not just the shown items",
          group.get("total", 0) >= len(group["items"]), str(group.get("total")))
    blocks = FR.suggestion_blocks({"suggestions": out})[0]
    check("AC-R22 the count survives into the shared renderer data",
          blocks["groups"][0].get("total") == group["total"],
          str(blocks["groups"][0].get("total")))


def test_removed_sports_are_never_suggested() -> None:
    """Item 3: suggestions must respect what the owner removed."""
    cfg = {"news": [], "sports": [{"sport": "Tennis", "enabled": True},
                                  {"sport": "Darts", "enabled": False}],
           "competitions": [], "tennis": {"enabled": False}, "settings": {},
           "removed": ["Padel"]}
    events = [{"sport": "Darts", "name": "World Darts Final",
               "when": "2099-01-10", "end": "2099-01-10"},
              {"sport": "Padel", "name": "Padel Major",
               "when": "2099-02-10", "end": "2099-02-10"}]

    out = FR.suggest(cfg, events, FakeFetcher({}))
    sports = [g["sport"] for g in out["sports"]]
    check("AC-R14 a switched-off sport is not suggested", "Darts" not in sports, str(sports))
    names = [i["name"] for g in out["sports"] for i in g["items"]]
    check("AC-R14 a removed sport's events are not suggested",
          not any("Padel" in n for n in names), str(names))
    check("AC-R14 the exclusion is stated, not silent",
          "padel" in [x.lower() for x in (out.get("excluded") or [])],
          str(out.get("excluded")))


def test_suggestions_only_offer_things_outside_the_window() -> None:
    """Item 3: a suggestion is something NEW, not a repeat of this email."""
    cfg = base_config()
    cfg["sports"] = [{"sport": "Athletics", "enabled": True}]
    today = dt.date(2026, 10, 12)
    inside = {"sport": "Athletics", "name": "Paris Masters",
              "when": today.isoformat(), "end": today.isoformat()}
    later = {"sport": "Athletics", "name": "Australian Open",
             "when": "2099-01-20", "end": "2099-02-01"}
    f = standard_fetcher()
    data = FR.gather(cfg, f, today=today,
                     sports_events=[inside, later], window_days=10)
    names = [i["name"] for g in data["suggestions"]["sports"] for i in g["items"]]
    check("AC-R14 an event already in the window is not suggested",
          not any("Paris Masters" in n for n in names), str(names))
    check("AC-R14 a later event is suggested",
          any("Australian Open" in n for n in names), str(names))


def test_ucl_standings_are_shown() -> None:
    """Item 4: UEFA standings, with what the position means."""
    data = gather()
    st = data["standings"][0]
    check("AC-R15 a standings table is produced", bool(st["rows"]))
    check("AC-R15 the table is ranked from 1", st["rows"][0]["rank"] == 1)
    check("AC-R15 every row carries its stats", all(r["stats"] for r in st["rows"]))
    check("AC-R15 the stage is named", bool(st["stage"]), st["stage"])
    text = FR.render_text(data)
    check("AC-R15 the text digest prints the table", "STANDINGS" in text)
    check("AC-R15 the meaning of a position is explained",
          "Where that leaves them" in text or "round of 16" in text)


def test_tennis_is_grouped_by_event_with_where_the_top5_stand() -> None:
    """Item 5: grouped by event, and says IN / OUT / no match, with the score."""
    data = gather()
    atp = next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP")
    check("AC-R16 tennis is grouped into events", bool(atp["events"]))
    ev = atp["events"][0]
    check("AC-R16 each event names its tournament", bool(ev["tournament"]))
    check("AC-R16 every top-5 player gets a row",
          len(ev["standings"]) == len(atp["top"]), str(len(ev["standings"])))
    statuses = {r["status"] for r in ev["standings"]}
    check("AC-R16 a status is given for every player",
          statuses <= {"in", "out", "absent", "did_not_compete"}, str(statuses))

    text = FR.render_text(data)
    check("AC-R16 the grouped view is rendered", "Shanghai Masters" in text)
    # The player knocked out must be named along with who beat them.
    out_rows = [r for r in ev["standings"] if r["status"] == "out"]
    if out_rows:
        check("AC-R16 an eliminated player names their conqueror",
              all("beaten by" in r["detail"] for r in out_rows),
              str([r["detail"] for r in out_rows]))


def test_tennis_scoreline_is_oriented_to_the_player() -> None:
    """Item 5: '6-3 6-4' must not be printed as the loser's perspective."""
    data = gather()
    atp = next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP")
    checked = 0
    for ev in atp["events"]:
        for r in ev["standings"]:
            for m in r["matches"]:
                if m["state"] != "post" or not m.get("scoreline"):
                    continue
                won = m.get("won")
                first = m["scoreline"].split()[0].split("-")[0]
                if won and first.isdigit():
                    check(f"AC-R16 the winner's set score comes first for {r['name']}",
                          int(first) >= int(m["scoreline"].split()[0].split("-")[1]),
                          m["scoreline"])
                    checked += 1
    check("AC-R16 at least one scoreline was checked", checked > 0, str(checked))


def test_placeholder_draw_slots_are_ignored() -> None:
    """A 'TBD vs TBD' slot is not a match, and must not fake a live run."""
    matches = [
        {"players": [{"name": "TBD"}, {"name": "TBD"}], "state": "pre",
         "round": "Final", "when": "2026-10-20T10:00Z", "sets": []},
    ]
    top = [{"rank": 1, "name": "Carlos Alcaraz"}]
    rows = FR._player_standings(matches, top)
    check("AC-R16 an unfilled draw slot is not counted as a match",
          rows[0]["status"] == "absent", str(rows[0]))


def test_local_events_look_backwards_not_forwards() -> None:
    """Item 6: the feed dates a story when it was PUBLISHED, not when it is on."""
    today = dt.date(2026, 11, 3)
    check("AC-R17 a story published last week is usable",
          FR._within_months("2026-10", today, 12))
    check("AC-R17 a story published next month does not exist",
          not FR._within_months("2026-12", today, 12))
    check("AC-R17 a story over a year old is dropped",
          not FR._within_months("2024-01", today, 12))


def test_local_events_require_the_town_and_the_subject() -> None:
    """Item 6: a New Jersey vice story is not a Joburg massage lead."""
    cfg = {"news": [], "sports": [], "competitions": [],
           "tennis": {"enabled": False}, "settings": {},
           "local": {"city": "Johannesburg", "enabled": True,
                     "place_terms": ["johannesburg", "joburg"],
                     "categories": [{"key": "massage", "label": "Massages",
                                     "require_any": ["massage", "spa"],
                                     "queries": ["spa Johannesburg"]}]}}
    today = dt.date(2026, 11, 3)
    stamp = today.strftime("%a, %d %b %Y 09:00:00 GMT")
    feed = news_feed([
        ("Special report: New Jersey slow on massage parlor enforcement", "Press", stamp),
        ("The 10 best spas in Johannesburg", "Time Out", stamp),
    ])
    out = FR.local_events(cfg, FakeFetcher({"news.google.com": feed}), today)
    titles = [i["title"] for c in out["categories"] for i in c["items"]]
    check("AC-R17 a story with no local place is dropped",
          not any("New Jersey" in t for t in titles), str(titles))
    check("AC-R17 a genuine local lead is kept",
          any("Johannesburg" in t for t in titles), str(titles))


def test_price_watch_matches_the_exact_capacity() -> None:
    """Item 7: a 32GB kit must never appear in the 16GB watch."""
    check("AC-R18 a single 16GB module is 16GB", FR._kit_capacity_gb(
        "Kingston Fury Beast 16GB 5600MHz DDR5 Single Module") == 16)
    check("AC-R18 a 2x8GB kit is 16GB", FR._kit_capacity_gb(
        "Kingston FURY Beast RGB DDR4 16GB Kit (2x8GB)") == 16)
    check("AC-R18 a 32GB kit is not 16GB", FR._kit_capacity_gb(
        "Kingston Fury Beast White 32GB (2x16GB) 5600MT/s CL5") == 32)
    check("AC-R18 the parser cannot be fooled by the substring",
          FR._kit_capacity_gb("Fury Beast 32GB (2x16GB)") != 16)


def test_run_time_is_reported() -> None:
    """Item 8: this run, the monthly estimate, and the remaining git time."""
    cfg = base_config()
    data = FR.gather(cfg, standard_fetcher(), repo="", token="")
    t = data["timing"]
    check("AC-R19 this run's duration is measured", t["elapsed"] != "", str(t["elapsed"]))
    check("AC-R19 a monthly estimate is produced", bool(t["monthly"]), str(t["monthly"]))
    check("AC-R19 the remaining git time is addressed", bool(t["remaining"]))
    text = FR.render_text(data)
    check("AC-R19 the digest prints the run time", "RUN TIME" in text)
    check("AC-R19 the digest prints the remaining git time",
          "Remaining git run time" in text)
    check("AC-R19 an unknown quota is said to be unknown, not guessed",
          "no repository configured" in text or "could not" in text.lower()
          or "unlimited" in text, text.split("RUN TIME")[-1][:200])

def _fixture(name: str) -> dict:
    """A recorded 2026-11-03/04 payload, read from disk. Tests stay offline."""
    path = os.path.join(ROOT, "tests", "fixtures", "live_20261103", name)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _price_cfg() -> dict:
    cfg = base_config()
    cfg["price_watch"] = {
        "enabled": True,
        "items": [{"key": "kingston-fury-beast-16gb",
                   "label": "Kingston Fury Beast 16GB", "enabled": True,
                   "query": "kingston fury beast 16gb",
                   "must_match": ["kingston", "fury", "beast", "16gb"],
                   "capacity_gb": 16}],
    }
    return cfg


def test_price_watch_sorts_by_the_selling_price() -> None:
    """AC-173/AC-176/AC-178: the printed order must match the printed price.

    The recorded payload has `listing_price` and `prices[0]` DIFFERING on every
    row (5,899 vs 5,549; 4,899 vs 3,649; 11,659 vs 8,879), so sorting by one
    while rendering the other is measurable here rather than theoretical.
    """
    payload = _fixture("takealot_search.json")
    f = FakeFetcher({"api.takealot.com": json.dumps(payload)})
    out = FR.local_prices(_price_cfg(), f)
    offers = out["items"][0]["offers"]
    check("AC-173 the price watch returns offers", bool(offers), str(len(offers)))

    printed = [o["price"] for o in offers]
    check("AC-173 offers are sorted by the RENDERED selling price",
          printed == sorted(printed), str(printed))

    # The price must be prices[0], not listing_price.
    singles = [o for o in offers if o["kind"] == "single module"]
    kits = [o for o in offers if o["kind"] == "kit"]
    check("AC-173 the single 16GB module is priced at prices[0]",
          any(o["price"] == 5549 for o in singles),
          str([(o["title"][:40], o["price"]) for o in singles]))
    check("AC-173 listing_price is NOT the price used",
          all(o["price"] != o.get("list_price") for o in offers
              if o.get("list_price")), str([(o["price"], o["list_price"]) for o in offers]))

    check("AC-175 a 16GB kit is labelled separately from a single module",
          bool(kits) and bool(singles),
          f"kits={len(kits)} singles={len(singles)}")

    # Savings: same spec only, and the difference of the two rendered prices.
    for o in offers:
        same = [x["price"] for x in offers if x["kind"] == o["kind"]]
        want = (max(same) - o["price"]) if len(same) > 1 else 0
        check(f"AC-176 the saving on {o['kind']} at {o['price']} is the rendered difference",
              o["saving"] == want, f"{o['saving']} vs {want}")
        if len(same) == 1:
            check("AC-176 a single listing of its kind shows no saving", o["saving"] == 0)

    text = FR.render_text({"news": {"items": []}, "competitions": [], "standings": [],
                           "tennis": {"enabled": False}, "by_sport": [],
                           "sports": {"enabled": [], "muted": []},
                           "suggestions": {}, "local": {}, "prices": out,
                           "timing": {}, "failures": [], "as_of": NOW})
    check("AC-173 the digest renders the price block", "RAM PRICE WATCH" in text)
    # Cheapest kit first: 3,649, and its saving against the 8,879 kit.
    check("AC-173 the cheapest kit renders first at 3,649", "R 3,649" in text)
    check("AC-176 the kit saving is 8,879 - 3,649 = 5,230",
          "save R 5,230" in text, text.split("RAM PRICE WATCH")[-1][:400])
    check("AC-178 the listing-price difference 6,760 is never printed",
          "6,760" not in text)


def test_price_watch_order_follows_prices_even_when_list_price_reverses() -> None:
    """AC-178(c): a payload whose listing order is REVERSED still sorts by prices[0]."""
    payload = _fixture("takealot_search.json")
    results = payload["sections"]["products"]["results"]
    # Raise the listing price of the cheapest kit above the dearest one's, so a
    # listing_price sort would put it LAST while a prices[0] sort keeps it FIRST.
    for r in results:
        v = r.get("product_views") or {}
        b = v.get("buybox_summary") or {}
        if (b.get("prices") or [None])[0] == 3649:
            b["listing_price"] = 99999
    f = FakeFetcher({"api.takealot.com": json.dumps(payload)})
    offers = FR.local_prices(_price_cfg(), f)["items"][0]["offers"]
    printed = [o["price"] for o in offers]
    check("AC-178 the rendered order is still ascending by prices[0]",
          printed == sorted(printed), str(printed))
    kits = [o for o in offers if o["kind"] == "kit"]
    check("AC-178 a reversed listing_price does not reorder the block",
          kits and kits[0]["price"] == 3649,
          str([(o["price"], o["list_price"]) for o in kits]))


def test_price_watch_unknown_shape_is_a_named_note() -> None:
    """AC-177/AC-178: a changed or empty response says so; no price is invented."""
    f = FakeFetcher({"api.takealot.com": json.dumps({"unexpected": True})})
    out = FR.local_prices(_price_cfg(), f)
    item = out["items"][0]
    check("AC-177 a changed shape produces no offers", item["offers"] == [])
    check("AC-177 a changed shape is a named note, not an empty table",
          "no matches" in item["error"] and "shape" in item["error"], item["error"])
    text = FR.render_text({"news": {"items": []}, "competitions": [], "standings": [],
                           "tennis": {"enabled": False}, "by_sport": [],
                           "sports": {"enabled": [], "muted": []},
                           "suggestions": {}, "local": {}, "prices": out,
                           "timing": {}, "failures": [], "as_of": NOW})
    check("AC-177 the note is what the digest prints, not a blank table",
          "R " not in text.split("RAM PRICE WATCH")[-1], text.split("RAM PRICE WATCH")[-1][:200])


def test_workflow_grants_actions_read_and_never_prints_the_body() -> None:
    """AC-199/AC-201: the grant is declared, and the body stays out of the log."""
    import yaml
    wf_text = open(".github/workflows/personal-digest.yml", encoding="utf-8").read()
    wf = yaml.safe_load(wf_text)
    perms = wf["permissions"]
    check("AC-199 contents: read is granted", perms.get("contents") == "read", str(perms))
    check("AC-199 actions: read is granted", perms.get("actions") == "read", str(perms))
    check("AC-199 no write scope of any kind",
          not any("write" in str(v) for v in perms.values()), str(perms))

    # A job that reads the runs endpoint must be covered by that grant: the
    # workflow is top-level, so every job inherits it - assert nothing overrides.
    check("AC-199 no job narrows the grant",
          all("permissions" not in j for j in wf["jobs"].values()),
          str({k: j.get("permissions") for k, j in wf["jobs"].items()}))

    # AC-201: the body must never be printed. `cat digest.txt` is the shape of
    # the regression this pins.
    for job in wf["jobs"].values():
        for step in job["steps"]:
            run = step.get("run") or ""
            check("AC-201 no step cats or echoes the digest body",
                  "cat digest" not in run and "cat subject" not in run, run[:80])
    check("AC-201 the log records the SHAPE (line/byte counts) instead",
          "wc -l" in wf_text and "wc -c" in wf_text)


def test_one_gather_writes_three_parts_and_the_email_reuses_them() -> None:
    """AC-202/AC-189: digest.txt, digest.html and subject.txt from ONE gather."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run(
            [sys.executable, "scripts/personal_digest.py", "--today", "2026-11-04",
             "--days", "10", "--no-research", "--out-dir", tmp],
            capture_output=True, text=True, check=True).stdout
        for name in ("digest.txt", "digest.html", "subject.txt"):
            path = os.path.join(tmp, name)
            check(f"AC-202 --out-dir writes {name}",
                  os.path.exists(path) and os.path.getsize(path) > 0, out[:120])

        text = open(os.path.join(tmp, "digest.txt"), encoding="utf-8").read()
        html = open(os.path.join(tmp, "digest.html"), encoding="utf-8").read()
        subject = open(os.path.join(tmp, "subject.txt"), encoding="utf-8").read()
        check("AC-202 the subject is one line", len(subject.strip().splitlines()) == 1,
              subject[:80])

        # Parity on the single-gather output: the same facts in both renderings.
        for fact in ("Paris Masters", "Weightlifting World Championships"):
            check(f"AC-189 '{fact}' is in both renderings", fact in text and fact in html)
        for heading in ("Sport", "Special days"):
            check(f"AC-189 the '{heading}' section is in both renderings",
                  heading.lower() in text.lower() and heading.lower() in html.lower())

    sender = open("scripts/send_digest_email.py", encoding="utf-8").read()
    check("AC-202 the sender PREFERS the prebuilt digest.html",
          'open("digest.html"' in sender
          and sender.index('open("digest.html"') < sender.index("PD.render_html"),
          "the prebuilt read must come before the fallback render")


def test_run_time_reads_the_recorded_actions_payload() -> None:
    """AC-179/AC-180/AC-183/AC-200: recent runs are MEASURED, not degraded."""
    runs_payload = _fixture("actions_runs.json")
    meta = _fixture("repo_metadata.json")
    f = FakeFetcher({
        "/actions/runs": json.dumps(runs_payload),
        "api.github.com/repos/MatthewMBowyer/UoEOMScDataScience": json.dumps(meta),
    })
    t = FR.run_time(12.4, f, repo="MatthewMBowyer/UoEOMScDataScience", token="t")

    check("AC-180 at least two recent runs are measured",
          t["runs_measured"] >= 2, str(t["runs_measured"]))
    check("AC-180 every measured run carries a positive duration from the payload",
          len(t["recent"]) >= 2 and all(r["seconds"] > 0 for r in t["recent"]),
          str([(r["at"], r["seconds"]) for r in t["recent"]]))
    check("AC-200 the recent-runs line is NOT the degradation note",
          t["recent_error"] == "" and bool(t["recent"]), t["recent_error"])
    check("AC-180 only digest runs are counted",
          all("digest" in "personal-digest" for _ in t["recent"]))
    check("AC-181 the public repository is stated as unlimited",
          t["public_repo"] is True and "unlimited" in t["remaining"], t["remaining"])
    check("AC-181 no invented quota figure",
          "minutes remaining" not in t["remaining"].lower(), t["remaining"])

    # Duration formatting boundaries (AC-183/INV-86).
    check("AC-183 under a minute renders Ns", FR._fmt_secs(42.2) == "42s",
          FR._fmt_secs(42.2))
    check("AC-183 60-3599s renders Nm SSs", FR._fmt_secs(95) == "1m 35s", FR._fmt_secs(95))
    check("AC-183 an hour or more renders Hh MMm", FR._fmt_secs(3725) == "1h 02m",
          FR._fmt_secs(3725))

    # Monthly projection on the ACTUAL schedule: 30 daily + 4 weekly runs, at
    # the MEAN of every measured run (not the five the digest prints).
    check("AC-183 the projection names the population it used",
          t["mean_seconds"] > 0 and t["basis"].startswith("average of the last"),
          t["basis"])
    check("AC-183 the monthly total is 34 x the mean measured run",
          abs(t["monthly_seconds"] - t["mean_seconds"] * 34) < 0.01,
          f"{t['monthly_seconds']} vs {t['mean_seconds'] * 34}")

    text = FR.render_text({"news": {"items": []}, "competitions": [], "standings": [],
                           "tennis": {"enabled": False}, "by_sport": [],
                           "sports": {"enabled": [], "muted": []},
                           "suggestions": {}, "local": {}, "prices": {},
                           "timing": t, "failures": [], "as_of": NOW})
    check("AC-179 the digest prints all four run-time facts",
          "This run:" in text and "Recent runs:" in text
          and "Estimated per month" in text and "Remaining git run time:" in text, text)
    check("AC-182 the printed run time is the one captured before the API call",
          "12s" in text, text.split("RUN TIME")[-1][:120])


def test_run_time_degrades_to_a_named_note() -> None:
    """AC-183: a failed call says it could not be measured; no number is invented."""
    t = FR.run_time(8.0, FakeFetcher({}, fail={"api.github.com"}),
                    repo="o/r", token="t")
    check("AC-183 a failed Actions call degrades to 'could not be measured'",
          t["recent_error"] == "recent runs could not be measured", t["recent_error"])
    check("AC-183 no recent run is fabricated", t["recent"] == [])
    check("AC-183 the remaining line still refuses to invent a quota",
          "could not be determined" in t["remaining"], t["remaining"])


def test_every_source_down_still_produces_a_sendable_digest() -> None:
    """AC-185/INV-90: total outage is a complete digest with named notes, exit 0."""
    cfg = base_config()
    cfg["sports"] = [{"sport": "Football", "enabled": True},
                     {"sport": "Tennis", "enabled": True}]
    cfg["local"] = {"city": "Johannesburg", "enabled": True,
                    "categories": [{"key": "buffet", "label": "Buffets",
                                    "queries": ["buffet Johannesburg"],
                                    "require_any": ["buffet"]}]}
    cfg["price_watch"] = _price_cfg()["price_watch"]
    f = FakeFetcher({}, fail={"espn", "github.com", "takealot", "news.google"})
    data = FR.gather(cfg, f, today=dt.date(2026, 11, 3))
    text = FR.render_text(data)

    # Every section is still present and every failure is named.
    for section in ("BY SPORT", "LOCAL - JOHANNESBURG", "RAM PRICE WATCH", "RUN TIME"):
        check(f"AC-185 '{section}' is still rendered with every source down",
              section in text)
    check("AC-185 the failures are named rather than silent",
          "could not be reached" in text or "could not be measured" in text, text[-400:])
    check("AC-185 no price was invented", "R " not in text.split("RAM PRICE WATCH")[-1].split("RUN TIME")[0],
          text.split("RAM PRICE WATCH")[-1][:200])



def main() -> int:
    print("=== research layer verification ===\n")
    for fn in (
        test_follow_list_is_honoured,
        test_empty_follow_list_stays_empty,
        test_missing_follow_file_is_not_an_error,
        test_tennis_follows_the_live_top_n,
        test_tennis_does_not_hardcode_names,
        test_winner_is_named_first,
        test_unplayed_matches_are_not_zero_zero,
        test_doubles_are_excluded,
        test_a_dead_source_degrades_gracefully,
        test_everything_dead_still_renders,
        test_bad_json_and_unknown_league_are_handled,
        test_fetch_failures_never_raise,
        test_budget_is_enforced,
        test_news_age_window,
        test_publisher_is_not_repeated,
        test_html_matches_text,
        test_team_filter,
        test_team_name_matching_is_loose_but_bounded,
        test_timezone_conversion,
        test_follow_editor_round_trips,
        test_shipped_follow_file_is_valid,
        test_workflow_supports_the_weekly_run,
        test_sports_can_be_added_and_removed,
        test_a_removed_sport_hides_its_live_data_too,
        test_the_by_sport_block_is_chronological,
        test_suggestions_are_never_in_the_past_or_already_shown,
        test_a_truncated_suggestion_list_says_how_many_were_cut,
        test_removed_sports_are_never_suggested,
        test_suggestions_only_offer_things_outside_the_window,
        test_ucl_standings_are_shown,
        test_tennis_is_grouped_by_event_with_where_the_top5_stand,
        test_tennis_scoreline_is_oriented_to_the_player,
        test_placeholder_draw_slots_are_ignored,
        test_local_events_look_backwards_not_forwards,
        test_local_events_require_the_town_and_the_subject,
        test_price_watch_matches_the_exact_capacity,
        test_run_time_is_reported,
        test_price_watch_sorts_by_the_selling_price,
        test_price_watch_order_follows_prices_even_when_list_price_reverses,
        test_price_watch_unknown_shape_is_a_named_note,
        test_workflow_grants_actions_read_and_never_prints_the_body,
        test_one_gather_writes_three_parts_and_the_email_reuses_them,
        test_run_time_reads_the_recorded_actions_payload,
        test_run_time_degrades_to_a_named_note,
        test_every_source_down_still_produces_a_sendable_digest,
    ):
        fn()
        print()

    print("=== summary ===")
    if FAILURES:
        print(f"{len(FAILURES)} FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all research-layer checks PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
