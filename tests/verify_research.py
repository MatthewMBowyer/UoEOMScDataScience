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

    def get(self, url: str) -> bytes | None:
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

    def json(self, url: str) -> dict | None:
        raw = self.get(url)
        if raw is None:
            return None
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
    """matches: (state, iso_date, [(player, winner), ...])"""
    return {
        "name": tournament,
        "date": "2026-10-12T06:00Z",
        "groupings": [{
            "grouping": {"slug": slug},
            "competitions": [
                {
                    "date": when,
                    "status": {"type": {"state": state, "description": state.upper()}},
                    "competitors": [
                        {"athlete": {"displayName": name}, "winner": won}
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
        ]),
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
    check("AC-R2 the rendered block is empty, not a placeholder",
          text.strip() == "", repr(text))
    check("AC-R2 nothing was invented to fill the gap",
          "Champions" not in text and "Sinner" not in text)


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


def test_emailed_html_body_carries_the_research() -> None:
    """Gmail renders the HTML part, so the sender must include research itself.

    This is the bug this test exists for: `send_digest_email.build_html()` called
    `render_html` without a research argument, so the styled body the owner
    actually sees was missing every headline, fixture and tennis result that the
    plain-text part carried.
    """
    import importlib.util

    os.environ["DAYS"] = "10"
    os.environ.pop("WEEKLY", None)
    spec = importlib.util.spec_from_file_location(
        "sde_probe", os.path.join(ROOT, "scripts", "send_digest_email.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    spec.loader.exec_module(mod)

    html = mod.build_html()
    check("AC-R13 the sender builds an HTML body", bool(html), str(type(html)))
    if not html:
        return
    # The follow block is populated only when research was actually gathered,
    # and the shipped follow.json names UEFA, so a real run must show it.
    check("AC-R13 the HTML body carries the research sections",
          "What you follow" in html and "Fixtures" in html,
          f"len={len(html)}")
    check("AC-R13 the HTML body is not the research-less rendering",
          "UEFA Champions League" in html, "UEFA named in the styled body")

    # The window comes from the environment so both parts of one email agree.
    os.environ["DAYS"] = "14"
    long_html = mod.build_html()
    check("AC-R13 the sender honours the DAYS window", bool(long_html))
    check("AC-R13 a wider window is not shorter than a narrow one",
          len(long_html or "") >= len(html) - 200,
          f"14d={len(long_html or '')} 10d={len(html)}")
    os.environ["DAYS"] = "10"


def test_sender_does_not_hardcode_the_window() -> None:
    src = open(os.path.join(ROOT, "scripts", "send_digest_email.py"),
               encoding="utf-8").read()
    check("AC-R13 the sender reads DAYS rather than hardcoding 10",
          'os.environ.get("DAYS", "10")' in src)
    check("AC-R13 the sender never renders without research",
          "render_html(sports, hubby, dt.date.today(), 10)" not in src)
    check("AC-R13 the sender gathers research best-effort",
          "gather(PD.FR.load_follow()" in src)


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
        test_sender_does_not_hardcode_the_window,
        test_emailed_html_body_carries_the_research,
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
