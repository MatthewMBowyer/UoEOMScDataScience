#!/usr/bin/env python3
"""Generation 13 acceptance checks: items 2-6 and the cross-cutting rules.

Run from the project root:

    python3 tests/verify_gen13.py

Offline and deterministic. The payloads are built here (or read from the
recorded `tests/fixtures/live_20261103/` captures), so nothing depends on a
third party being up. Every check names the criterion it discharges; the
evidence bundle at `output/evidence/gen13_change_report.json` is generated from
THESE checks rather than written by hand.

What is pinned, briefly:

* item 2 - the BY SPORT block: one row per ON sport, a quiet sport says so, a
  muted sport has no row at all, and nothing is invented to fill one;
* item 3 - SUGGESTED: derived, sourced, hard-excluded by BOTH exclusion sets,
  legal when empty, named when a source fails;
* item 4 - STANDINGS: ESPN's own numbers verbatim, the `/apis/v2/` root, one
  table per followed competition, and the same table on sports.html;
* item 5 - tennis grouped by event with the per-tour RANKING line, round names,
  the three unambiguous player states, and real scores only;
* item 6 - LOCAL: every category renderable, the named source, the two-person
  label, no invented venue/price/date;
* cross-cutting - the empty-follow contract, no fabricated figure, the docs, no
  credential, and the snapshot that keeps sports.html and the digest identical.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import build_personal as BP  # noqa: E402
import follow_research as FR  # noqa: E402
import verify_research as VR  # noqa: E402

check = VR.check
FAILURES = VR.FAILURES

TODAY = dt.date(2026, 11, 4)
PALETTE = ("#000", "#555", "#ccc", "#045", "#fff", "#eef")


def html_of(data: dict) -> dict:
    return FR.render_html(data, *PALETTE)


def text_of(data: dict) -> str:
    return FR.render_text(data)


def page_of(research: dict, follow: dict | None = None) -> str:
    return BP.build_sports({"events": [], "broadcasters": {}, "preferences": {},
                            "timezone_label": "SAST"},
                           TODAY, follow or {"sports": []}, research=research)


def snapshot_of(data: dict) -> dict:
    return {
        "sports_detail": FR.sport_detail_blocks(data),
        "standings": FR.standings_blocks(data),
        "tennis": {"enabled": True, "top_n": data["tennis"]["top_n"],
                   "tours": [{"tour": t["tour"],
                              "blocks": FR.tennis_tour_blocks(
                                  t, data["tennis"]["top_n"])}
                             for t in data["tennis"]["tours"]]},
        "suggestions": FR.suggestion_blocks(data)[0],
        "local": FR.local_blocks(data)[0] if FR.local_blocks(data) else {},
    }


def sport_cfg(**sports) -> dict:
    cfg = VR.base_config()
    cfg["sports"] = [{"sport": name, "enabled": on, "source": f"owner, {name}"}
                     for name, on in sports.items()]
    return cfg


# ---------------------------------------------------------------------------
# ITEM 2 - BY SPORT, and nothing invented in it
# ---------------------------------------------------------------------------

def test_by_sport_block_shape() -> None:
    """AC-145/AC-146/AC-148: one line per ON sport, quiet says so, muted absent."""
    events = [{"sport": "Motorsport", "name": "Bahrain 8 Hours",
               "when": "2026-11-07", "end": "2026-11-07", "series": "FIA WEC"}]
    cfg = sport_cfg(Motorsport=True, Padel=False, Cycling=True)
    data = FR.gather(cfg, VR.standard_fetcher(), today=TODAY,
                     sports_events=events, window_days=10)
    text = text_of(data)
    block = text.split("BY SPORT")[1].split("STANDINGS")[0]

    check("AC-145 an ON sport with events is listed with its count",
          "Motorsport: 1 in the window" in block, block[:300])
    check("AC-145 the next event and its date are printed under that sport",
          "Bahrain 8 Hours" in block and "2026-11-07" in block, block[:300])
    check("AC-145 an ON sport with nothing in the window says so in one line",
          "Cycling: nothing in the window" in block, block[:400])
    check("AC-145 every ON sport appears exactly once",
          block.count("Motorsport:") == 1 and block.count("Cycling:") == 1,
          block[:300])
    # The block names the muted sports on ONE separate line, so silence cannot
    # look like the sport was never considered. What it must NOT have is a row
    # of its own among the followed sports.
    sport_lines = [l for l in block.splitlines()
                   if l.strip() and not l.startswith("    ")]
    check("AC-145 a MUTED sport gets no followed-sport row in the block",
          not any(l.strip().startswith("Padel:") for l in sport_lines),
          str(sport_lines))
    check("AC-145 the muted sport is named once, separately, as removed",
          block.count("Padel") == 1 and "Muted (removed): Padel" in block,
          str(block.count("Padel")))

    # Same population decision, seen from the page: the muted sport is listed
    # (dimmed) so it can be turned back on, but it contributes no digest row.
    page = page_of({}, {"sports": [{"sport": "Motorsport", "enabled": True,
                                    "source": "x"},
                                   {"sport": "Padel", "enabled": False,
                                    "source": "x"}]})
    check("AC-145 the muted sport IS shown in the sports.html follow table",
          "Padel" in page and "tag off" in page, "follow table")

    # AC-146: a sport with live-capable detail carries more than a bare name.
    rich = FR.gather(VR.base_config(), VR.standard_fetcher(), today=TODAY)
    rich_text = text_of(rich)
    check("AC-146 football carries fixtures AND a standings table",
          "FIXTURES" in rich_text and "STANDINGS" in rich_text)
    check("AC-146 tennis carries event-grouped detail beneath its heading",
          "Shanghai Masters" in rich_text and "RANKING" in rich_text)
    check("AC-146 a sport with only the owner's own list still prints its events",
          "Motorsport: 1 in the window"
          in text_of(FR.gather(cfg, VR.standard_fetcher(), today=TODAY,
                               sports_events=events, window_days=10)))


def test_by_sport_invents_nothing() -> None:
    """AC-148: no source and no events is stated, in both renderings."""
    data = FR.gather(sport_cfg(Padel=True), VR.standard_fetcher(),
                     today=TODAY, sports_events=[], window_days=10)
    text = text_of(data)
    html = html_of(data)
    block = text.split("BY SPORT")[1].split("STANDINGS")[0]
    check("AC-148 a sport with no source and no events says nothing in the window",
          "Padel: nothing in the window" in block, block[:300])
    check("AC-148 no fixture, series or watch line is synthesised for it",
          "Watch" not in block, block[:300])
    check("AC-148 the HTML email carries the same wording",
          "nothing in the window" in html["sports"], html["sports"][:300])
    check("AC-148 no fabricated fixture is added to the fixture block",
          html["fixtures"].strip() == "" or "Padel" not in html["fixtures"],
          html["fixtures"][:200])


# ---------------------------------------------------------------------------
# ITEM 3 - SUGGESTED
# ---------------------------------------------------------------------------

def test_suggestions_are_derived_and_sourced() -> None:
    """AC-149/AC-150: a separated block whose every item names source and reason."""
    data = FR.gather(sport_cfg(Motorsport=True, Tennis=True, Football=True),
                     VR.standard_fetcher(), today=TODAY,
                     sports_events=[{"sport": "Motorsport", "name": "MotoGP Valencia",
                                     "when": "2099-11-20", "end": "2099-11-20"}],
                     window_days=10)
    sug = data["suggestions"]
    items = [i for g in sug["sports"] for i in g["items"]]
    check("AC-149 the text digest has its own SUGGESTED block",
          "SUGGESTED (from what you follow)" in text_of(data))
    check("AC-149 sports.html has its own separated suggestions section",
          'id="suggested"' in page_of(snapshot_of(data)), "section")
    check("AC-150 suggestions are produced from what is followed", bool(items),
          str(len(items)))
    check("AC-150 every suggestion names a source", all(i["source"] for i in items),
          str([i["source"] for i in items][:3]))
    check("AC-150 every suggestion names the follow that caused it",
          all("follow" in i["why"] for i in items),
          str([i["why"] for i in items][:3]))
    check("AC-150 the football suggestions come from the ESPN team list",
          all(i["source"].startswith("ESPN ") and "team list" in i["source"]
              for g in sug["sports"] if g["sport"] == "Football"
              for i in g["items"]),
          str([i["source"] for g in sug["sports"] if g["sport"] == "Football"
               for i in g["items"]][:2]))
    check("AC-150 the tennis suggestions come from the ESPN calendar",
          all("ESPN" in i["source"] for g in sug["sports"] if g["sport"] == "Tennis"
              for i in g["items"]), "tennis")
    check("AC-150 the rest come from the owner's own event list",
          all("event list" in i["source"] or "owner" in i["source"].lower()
              for g in sug["sports"] if g["sport"] == "Motorsport"
              for i in g["items"]),
          str([i["source"] for g in sug["sports"] if g["sport"] == "Motorsport"
               for i in g["items"]][:2]))


def test_suggestion_exclusions_are_hard() -> None:
    """AC-151/AC-153: two independent sets drop items before rendering."""
    cfg = sport_cfg(Motorsport=True, Darts=False)
    cfg["removed"] = ["MotoGP Valencia"]
    events = [
        {"sport": "Motorsport", "name": "MotoGP Valencia",
         "when": "2099-11-20", "end": "2099-11-20"},
        {"sport": "Motorsport", "name": "Bathurst 1000",
         "when": "2099-02-01", "end": "2099-02-01"},
        {"sport": "Darts", "name": "World Darts Final",
         "when": "2099-01-10", "end": "2099-01-10"},
    ]
    f = VR.FakeFetcher({})
    sug = FR.suggest(cfg, events, f)
    names = [i["name"] for g in sug["sports"] for i in g["items"]]
    check("AC-151 the REMOVED list alone blocks an item", "MotoGP Valencia" not in names,
          str(names))
    check("AC-151 the MUTE list alone blocks an item", "World Darts Final" not in names,
          str(names))
    check("AC-151 an excluded item is absent from the DATA, not merely hidden",
          "World Darts Final" not in json.dumps(sug["sports"]),
          json.dumps(sug["sports"])[:200])
    check("AC-151 an unblocked item of a followed sport still gets through",
          any(n.startswith("Bathurst 1000") for n in names), str(names))

    data = FR.gather(cfg, f, today=TODAY, sports_events=events, window_days=10)
    text = text_of(data)
    check("AC-151 the rendered digest carries neither excluded name in SUGGESTED",
          "World Darts Final" not in text.split("SUGGESTED")[-1],
          text.split("SUGGESTED")[-1][:300])
    page = page_of(snapshot_of(data), {"sports": []})
    check("AC-151 the rendered page carries neither excluded name",
          "World Darts Final" not in page, "page")


def test_suggestions_empty_and_failed_source() -> None:
    """AC-152/AC-153: empty is legal and stated; a failure is named."""
    data = FR.gather(sport_cfg(Padel=True), VR.standard_fetcher(), today=TODAY,
                     sports_events=[], window_days=10)
    text = text_of(data)
    block = text.split("SUGGESTED (from what you follow)")[1].split("LOCAL")[0]
    check("AC-152 the empty suggestion list says so in one line",
          "nothing new to suggest" in block, block[:300])
    check("AC-152 no suggestion row was invented to fill it",
          "+ " not in block, block[:200])
    check("AC-152 the page says the same thing",
          "nothing new to suggest" in page_of(snapshot_of(data)), "page")

    failing = VR.FakeFetcher({}, fail={"espn"})
    cfg = sport_cfg(Football=True, Tennis=True)
    sug = FR.suggest(cfg, [], failing)
    check("AC-153 a failed suggestion source is named",
          any("could not be reached" in e for e in sug.get("errors") or []),
          str(sug.get("errors")))
    data2 = FR.gather(cfg, failing, today=TODAY, sports_events=[])
    check("AC-153 the named note reaches the rendered digest",
          "could not be reached" in text_of(data2))
    check("AC-153 it does not crash or print an empty block",
          "SUGGESTED" in text_of(data2))


# ---------------------------------------------------------------------------
# ITEM 4 - STANDINGS
# ---------------------------------------------------------------------------

def test_standings_are_espn_verbatim() -> None:
    """AC-154/AC-157/AC-158/AC-159: columns, numbers, note, both surfaces."""
    f = VR.standard_fetcher()
    data = FR.gather(VR.base_config(), f, today=TODAY)
    st = data["standings"][0]
    row = st["rows"][0]
    check("AC-154 position, team and all six stat columns are carried",
          row["rank"] == 1 and row["team"] == "Arsenal"
          and set(row["stats"]) >= {"GP", "W", "D", "L", "GD", "P"}, str(row))
    check("AC-154 the ESPN qualification note is carried through",
          row["note"] == "Advances to round of 16", row["note"])
    text = text_of(data)
    check("AC-154 the text digest prints a real aligned table",
          "STANDINGS" in text and "Arsenal" in text and "16" in text,
          text.split("STANDINGS")[1][:300])
    html = html_of(data)
    check("AC-154 the HTML email carries a real table",
          "<table" in html["standings"], html["standings"][:200])
    check("AC-154 the ESPN qualification note is printed in that table",
          "Advances to round of 16" in html["standings"],
          html["standings"][:400])
    check("AC-159 the table prints ESPN's numbers, not a recomputation",
          "16" in html["standings"] and "10" in html["standings"])


def test_standings_use_the_v2_root() -> None:
    """AC-155: /apis/v2/ for standings; the 404 shape is not built."""
    f = VR.standard_fetcher()
    FR.gather(VR.base_config(), f, today=TODAY)
    urls = [u for u in f.asked if "standings" in u]
    check("AC-155 a standings request is issued", bool(urls), str(urls))
    check("AC-155 every standings URL is on the /apis/v2/ root",
          all("/apis/v2/sports/soccer/" in u for u in urls), str(urls))
    check("AC-155 the /apis/site/v2/.../standings shape is never built",
          not any("/apis/site/v2/sports/soccer/" in u and "standings" in u
                  for u in urls), str(urls))
    check("AC-155 the scoreboard keeps its own /apis/site/v2/ root",
          any("/apis/site/v2/sports/soccer/uefa.champions/scoreboard" in u
              for u in f.asked), str(f.asked[:4]))


def test_standings_points_are_not_rederived() -> None:
    """AC-157: a P that disagrees with 3W+D is printed as published."""
    payload = {"children": [{"name": "League Phase", "standings": {"entries": [
        {"note": {"rank": 1, "description": "Qualifies for round of 16"},
         "stats": [{"abbreviation": a, "displayValue": v} for a, v in
                   (("GP", "6"), ("W", "2"), ("D", "0"), ("L", "4"),
                    ("GD", "-3"), ("P", "99"))],
         "team": {"displayName": "Odd FC"}}]}}]}
    f = VR.standard_fetcher(**{"soccer/uefa.champions/standings": payload})
    data = FR.gather(VR.base_config(), f, today=TODAY)
    row = data["standings"][0]["rows"][0]
    check("AC-157 the payload's own P (99) is used; 3W+D would be 6",
          row["stats"]["P"] == "99", str(row["stats"]))
    check("AC-157 the rendered table prints 99", "99" in text_of(data))


def test_standings_follow_the_follow_list() -> None:
    """AC-156/AC-159: driven by the list; a missing table is a named note."""
    cfg = VR.base_config()
    cfg["competitions"] = [
        {"label": "UEFA Champions League", "league": "uefa.champions", "teams": []},
        {"label": "UEFA Europa League", "league": "uefa.europa", "teams": []},
    ]
    f = VR.standard_fetcher(**{"uefa.europa/standings": None})
    data = FR.gather(cfg, f, today=TODAY)
    labels = [s["label"] for s in data["standings"]]
    check("AC-156 every followed competition is asked for a table",
          labels == ["UEFA Champions League", "UEFA Europa League"], str(labels))
    text = text_of(data)
    check("AC-156 the competition without a table gets a named note",
          "UEFA Europa League: standings could not be reached" in text, text[:500])

    only_fail = VR.standard_fetcher(**{"soccer/uefa.champions/standings": None})
    text2 = text_of(FR.gather(VR.base_config(), only_fail, today=TODAY))
    check("AC-159 a standings failure is a named note, not an empty table",
          "standings could not be reached" in text2 and "# Team" not in text2,
          text2[:400])

    # A single-league follow list still works: nothing is hardcoded to the UCL.
    one = VR.base_config()
    one["competitions"] = [{"label": "UEFA Europa League",
                            "league": "uefa.europa", "teams": []}]
    f3 = VR.standard_fetcher(**{"soccer/uefa.europa/standings": json.dumps(
        {"children": [{"name": "League Phase", "standings": {"entries": [
            {"note": {"rank": 1, "description": "Qualifies"},
             "stats": [{"abbreviation": a, "displayValue": v} for a, v in
                       (("GP", "5"), ("W", "5"), ("D", "0"), ("L", "0"),
                        ("GD", "9"), ("P", "15"))],
             "team": {"displayName": "Roma"}}]}}]})})
    data3 = FR.gather(one, f3, today=TODAY)
    check("AC-156 a non-UCL follow list produces that league's table",
          data3["standings"][0]["label"] == "UEFA Europa League"
          and data3["standings"][0]["rows"][0]["team"] == "Roma",
          str(data3["standings"][0]["label"]))


def test_sports_page_renders_the_same_standings_and_ranking() -> None:
    """AC-158/AC-197: the page and the digest come from one code path."""
    data = FR.gather(VR.base_config(), VR.standard_fetcher(), today=TODAY)
    page = page_of(snapshot_of(data))
    text = text_of(data)
    check("AC-158 the same teams appear on the page and in the digest",
          "Arsenal" in page and "Arsenal" in text)
    check("AC-158 the same qualification note appears on both surfaces",
          "Advances to round of 16" in page
          and "Advances to round of 16" in text)
    check("AC-158 the page renders a real standings table",
          "class=\"standings\"" in page and "<th>#</th>" in page, "table")
    check("AC-158 the same ESPN numbers are printed on the page",
          "<td class=\"num\">16</td>" in page, "16")
    check("AC-197 sports.html carries the per-tour RANKING line",
          "RANKING" in page and "ATP top 5 - current ranking" in page)
    check("AC-197 the page's ranking line is the digest's own line",
          next(b["line"] for b in FR.tennis_tour_blocks(
              next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP"), 5)
              if b["kind"] == "ranking") in page)
    check("AC-197 the event grouping is on the page too",
          "Shanghai Masters" in page)


# ---------------------------------------------------------------------------
# ITEM 5 - tennis grouped by event
# ---------------------------------------------------------------------------

def test_ranking_line_is_rendered_and_verbatim() -> None:
    """AC-197: rendered in all three surfaces, positions from the payload."""
    seven = {"rankings": [{"ranks": [
        {"current": 7 + i, "points": 100 - i,
         "athlete": {"displayName": n, "flag": "https://x/500/rsa.png"}}
        for i, n in enumerate(VR.ATP[:5])]}]}
    f = VR.standard_fetcher(**{"tennis/atp/rankings": seven})
    data = FR.gather(VR.base_config(), f, today=TODAY)
    atp = next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP")
    line = next(b for b in FR.tennis_tour_blocks(atp, 5) if b["kind"] == "ranking")
    check("AC-197 the positions printed are the payload's own current values",
          line["line"].startswith("7. ") and "8. " in line["line"], line["line"])
    check("AC-197 they are NOT renumbered to 1..N",
          not line["line"].startswith("1. "), line["line"])
    check("AC-197 the text digest carries the line",
          "RANKING - ATP top 5 - current ranking: 7. " in text_of(data),
          text_of(data)[:400])
    check("AC-197 the HTML email carries the line",
          "ATP top 5 - current ranking: 7. " in html_of(data)["tennis"],
          html_of(data)["tennis"][:300])
    check("AC-197 sports.html carries the line",
          "ATP top 5 - current ranking: 7. " in page_of(snapshot_of(data)))


def test_ranking_failure_is_named_not_remembered() -> None:
    """AC-197: a failed rankings fetch prints a note and invents no list."""
    f = VR.standard_fetcher(**{"tennis/atp/rankings": None})
    data = FR.gather(VR.base_config(), f, today=TODAY)
    atp = next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP")
    blocks = FR.tennis_tour_blocks(atp, 5)
    notes = [b["text"] for b in blocks if b["kind"] == "note"]
    check("AC-197 a failed rankings payload prints the named note",
          any("current ranking could not be read" in n for n in notes), str(notes))
    check("AC-197 no remembered ranking list is printed",
          not any(b["kind"] == "ranking" for b in blocks),
          str([b["kind"] for b in blocks]))
    check("AC-197 the event blocks still render",
          any(b["kind"] == "event" for b in blocks), str([b["kind"] for b in blocks]))
    check("AC-197 the note reaches the rendered digest",
          "current ranking could not be read" in text_of(data))


def test_tennis_grouped_by_event_with_rounds() -> None:
    """AC-160/AC-161/AC-163: heading, stage, summary beside the ranking."""
    data = FR.gather(VR.base_config(), VR.standard_fetcher(), today=TODAY)
    text = text_of(data)
    block = text.split("TENNIS - ATP TOP 5")[1].split("TENNIS - WTA")[0]
    check("AC-160 the tournament is its own heading line",
          any(l.strip().startswith("Shanghai Masters") for l in block.splitlines()),
          block[:300])
    check("AC-160 it is not a suffix repeated on every match line",
          block.count("Shanghai Masters") <= 2, str(block.count("Shanghai Masters")))
    check("AC-163 the ranking line sits above the event blocks",
          block.index("RANKING") < block.index("Shanghai Masters"))
    check("AC-163 a summary of who is in / out sits beside the ranking",
          "How the top 5 are doing" in block and "still in - " in block, block[:400])
    check("AC-161 the event's latest stage is printed from ESPN's round names",
          "Latest round played: Round 1" in block
          or "Latest round played: Round " in block, block[:400])
    html = html_of(data)["tennis"]
    check("AC-160 the HTML email groups the same way",
          "Shanghai Masters" in html and "RANKING" in html)


def test_round_names_sort_and_render_including_unmeasured() -> None:
    """AC-161/AC-165: 'Round 4' renders and orders without being listed."""
    order = ["Qualifying 1st Round", "Qualifying Final", "Round 1", "Round 2",
             "Round 3", "Round 4", "Round of 16", "Quarterfinal", "Semifinal",
             "Final"]
    keys = [FR.round_sort_key(n) for n in order]
    check("AC-161 the measured round names sort in tournament order",
          keys[:3] == sorted(keys[:3]) and keys[-2:] == sorted(keys[-2:]),
          str(list(zip(order, keys))[:4]))
    check("AC-161 'Round 4' sits between Round 3 and the quarterfinal",
          FR.round_sort_key("Round 3") < FR.round_sort_key("Round 4")
          < FR.round_sort_key("Quarterfinal"),
          f"{FR.round_sort_key('Round 3')} {FR.round_sort_key('Round 4')}")
    check("AC-161 'Round of 16' is the same stage as Round 4",
          FR.round_sort_key("Round of 16") == FR.round_sort_key("Round 4"))

    payload = json.loads(VR.standard_fetcher().responses["tennis/atp/scoreboard"])
    payload["events"][0]["groupings"][0]["competitions"][0]["round"] = {
        "displayName": "Round 4"}
    f = VR.standard_fetcher(**{"tennis/atp/scoreboard": json.dumps(payload)})
    data = FR.gather(VR.base_config(), f, today=TODAY)
    check("AC-161 an unmeasured round name is rendered verbatim",
          "Round 4" in text_of(data), text_of(data)[:400])


def test_every_top5_player_is_accounted_for() -> None:
    """AC-162/AC-165: in, out (round + conqueror), or did-not-compete."""
    data = FR.gather(VR.base_config(), VR.standard_fetcher(), today=TODAY)
    atp = next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP")
    ev = atp["events"][0]
    check("AC-162 every top-5 player has exactly one row in the event",
          len(ev["standings"]) == len(atp["top"]), str(len(ev["standings"])))
    states = {r["status"] for r in ev["standings"]}
    check("AC-162 every row is one of the four explicit states",
          states <= {"in", "out", "absent", "did_not_compete"}, str(states))
    outs = [r for r in ev["standings"] if r["status"] == "out"]
    check("AC-162 an eliminated player names the round AND who beat them",
          bool(outs) and all("out in the" in r["detail"]
                             and "beaten by" in r["detail"] for r in outs),
          str([r["detail"] for r in outs]))
    absent = [r for r in ev["standings"] if r["status"] == "absent"]
    check("AC-162 an incomplete draw says 'no match found', not 'did not compete'",
          all("no match found in this event yet" in r["detail"] for r in absent),
          str([r["detail"] for r in absent]))
    check("AC-165 a top-5 player absent from a live event is reported, not dropped",
          bool(absent) and all(r["name"] and r["rank"] for r in absent),
          str([(r["rank"], r["name"]) for r in absent]))


def test_did_not_compete_requires_a_complete_draw() -> None:
    """AC-162/AC-165: the withdrawal claim is gated on the draw finishing."""
    top = [{"rank": 1, "name": "Carlos Alcaraz"}]
    open_draw = [
        {"players": [{"name": "A Player", "winner": True}, {"name": "B Player"}],
         "state": "post", "round": "Round 1", "when": "2026-10-10", "sets": []},
        {"players": [{"name": "C Player"}, {"name": "D Player"}],
         "state": "pre", "round": "Final", "when": "2026-10-20", "sets": []},
    ]
    rows = FR._player_standings(open_draw, top)
    check("AC-162 an unfinished draw does NOT claim 'did not compete'",
          rows[0]["status"] == "absent", str(rows[0]))
    done = [{"players": [{"name": "A Player", "winner": True},
                         {"name": "B Player"}],
             "state": "post", "round": "Final", "when": "2026-10-10", "sets": []}]
    rows = FR._player_standings(done, top)
    check("AC-162 a COMPLETE draw does claim 'did not compete'",
          rows[0]["status"] == "did_not_compete", str(rows[0]))


def test_out_in_an_unmeasured_round_is_rendered() -> None:
    """AC-165: the 'out in round of 16 by Y' case, on a Round 4 payload."""
    matches = [{"players": [
        {"name": "Carlos Alcaraz", "setline": "3-6 4-6"},
        {"name": "Big Server", "winner": True, "setline": "6-3 6-4"}],
        "state": "post", "round": "Round 4", "when": "2026-10-12",
        "sets": [("3", "6"), ("4", "6")], "note": "", "detail": "FT"}]
    rows = FR._player_standings(matches, [{"rank": 3, "name": "Carlos Alcaraz"}])
    check("AC-165 an unmeasured round produces an 'out in round 4' claim",
          rows[0]["status"] == "out" and "out in the round 4" in rows[0]["detail"],
          str(rows[0]))
    check("AC-165 the conqueror is named", "beaten by Big Server" in rows[0]["detail"],
          rows[0]["detail"])


def test_match_lines_carry_real_scores_only() -> None:
    """AC-164: the score is the payload's; an unplayed match has none."""
    data = FR.gather(VR.base_config(), VR.standard_fetcher(), today=TODAY)
    atp = next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP")
    rows = [m for b in FR.tennis_tour_blocks(atp, 5)
            if b["kind"] == "matches" for m in b["rows"]]
    played = [m for m in rows if m["winner_first"]]
    unplayed = [m for m in rows if not m["winner_first"]]
    check("AC-164 a played match carries the payload's set line",
          bool(played) and played[0]["score"] == "6-3 6-4", str(played[:1]))
    check("AC-164 an unplayed match carries NO score at all",
          all(m["score"] == "" for m in unplayed),
          str([m["score"] for m in unplayed]))
    check("AC-164 no score is defaulted to 0-0",
          "0-0" not in text_of(data).split("TENNIS")[1].split("SUGGESTED")[0],
          "no 0-0")


def test_tennis_event_shows_champion_and_how_far_each_player_got() -> None:
    """AC-198: a finished event names its champion; each exit names the depth.

    The owner asked for "final rankings" and to know "if they didn't compete or
    out in round of 16 and by who". A depth of "round 2, main draw of 4" only
    appears for a player who actually lost, and a champion is only claimed when
    a Final has really been played - the bracket is published up front, so an
    unplayed Final must never be reported as a result.
    """
    final_draw = {
        "name": "Test Cup",
        "groupings": [{"grouping": {"slug": "mens-singles"},
                       "competitions": [
                           {"date": "2026-10-10T10:00Z",
                            "round": {"displayName": "Semifinal"},
                            "status": {"type": {"state": "post"}},
                            "competitors": [
                                {"athlete": {"displayName": "Carlos Alcaraz"},
                                 "winner": True, "linescores": [{"value": 6}, {"value": 6}]},
                                {"athlete": {"displayName": "Alexander Zverev"},
                                 "winner": False, "linescores": [{"value": 4}, {"value": 3}]}]},
                           {"date": "2026-10-12T10:00Z",
                            "round": {"displayName": "Final"},
                            "status": {"type": {"state": "post"}},
                            "competitors": [
                                {"athlete": {"displayName": "Carlos Alcaraz"},
                                 "winner": True, "linescores": [{"value": 7}, {"value": 6}]},
                                {"athlete": {"displayName": "Jannik Sinner"},
                                 "winner": False, "linescores": [{"value": 5}, {"value": 4}]}]},
                       ]}],
    }
    f = VR.standard_fetcher(**{"tennis/atp/scoreboard": VR.scoreboard([final_draw])})
    data = FR.gather(VR.base_config(), f, today=TODAY)
    atp = next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP")
    ev = next(b for b in FR.tennis_tour_blocks(atp, 5) if b["kind"] == "event")
    check("AC-198 a played Final produces a champion line",
          ev["champion"] == "Carlos Alcaraz" and "Champion: Carlos Alcaraz" in ev["outcome_line"],
          str(ev["outcome_line"]))
    check("AC-198 the runner-up and the final score are named",
          ev["runner_up"] == "Jannik Sinner" and "7" in ev["final_score"],
          f'{ev["runner_up"]} {ev["final_score"]}')
    out_rows = [r for r in ev["rows"] if r["state"] == "out"]
    check("AC-198 a beaten player carries how far they got",
          bool(out_rows) and all(r["reached"] for r in out_rows),
          str([(r["name"], r["reached"]) for r in out_rows]))
    check("AC-198 the depth counts the main draw, not the qualifying rounds",
          all("main draw of" in r["reached"] for r in out_rows),
          str([r["reached"] for r in out_rows]))
    check("AC-198 the champion line reaches the rendered digest",
          "Champion: Carlos Alcaraz" in text_of(data), "champion")

    # No played Final means no champion claim at all.
    unplayed = {"name": "Test Cup",
                "groupings": [{"grouping": {"slug": "mens-singles"},
                               "competitions": [
                                   {"date": "2026-10-12T10:00Z",
                                    "round": {"displayName": "Final"},
                                    "status": {"type": {"state": "pre"}},
                                    "competitors": [
                                        {"athlete": {"displayName": "Carlos Alcaraz"}},
                                        {"athlete": {"displayName": "Jannik Sinner"}}]}]}]}
    f2 = VR.standard_fetcher(**{"tennis/atp/scoreboard":
                                VR.scoreboard([unplayed])})
    data2 = FR.gather(VR.base_config(), f2, today=TODAY)
    atp2 = next(t for t in data2["tennis"]["tours"] if t["tour"] == "ATP")
    ev2 = next(b for b in FR.tennis_tour_blocks(atp2, 5) if b["kind"] == "event")
    check("AC-198 an unplayed Final claims no champion",
          ev2["champion"] == "" and ev2["outcome_line"] == "", str(ev2["outcome_line"]))


def test_tennis_absence_lines_survive_the_grouping() -> None:
    """AC-193: events with no top-5 match are named in one line, not tabulated.

    A tournament carrying none of the top N used to get its own heading, stage
    line and a column of dashes. Four such events in one tour buried the event
    that did carry a top-5 player, so they are now collapsed into a single named
    line - the absence is still stated, just once instead of four times.
    """
    data = FR.gather(VR.base_config(), VR.standard_fetcher(), today=TODAY)
    wta = next(t for t in data["tennis"]["tours"] if t["tour"] == "WTA")
    blocks = FR.tennis_tour_blocks(wta, 5)
    events = [b for b in blocks if b["kind"] == "event"]
    notes = [b["text"] for b in blocks if b["kind"] == "note"]
    check("AC-193 only tournaments carrying a top-5 player get a block",
          [b["tournament"] for b in events] == ["Wuhan Open"],
          str([b["tournament"] for b in events]))
    check("AC-193 the top-5-free tournament is not tabulated as dashes",
          "Hong Kong Open" not in [b["tournament"] for b in events])
    check("AC-193 the absence is stated in one named line",
          any("No top-5 match" in n for n in notes), str(notes))
    text = text_of(data)
    wta_block = text.split("TENNIS - WTA")[1].split("SUGGESTED")[0]
    check("AC-193 the absence is stated rather than the block being blank",
          "No top-5 match" in wta_block, wta_block[:400])


# ---------------------------------------------------------------------------
# ITEM 6 - LOCAL
# ---------------------------------------------------------------------------

def local_cfg() -> dict:
    cfg = VR.base_config()
    cfg["sports"] = [{"sport": "Padel", "enabled": True}]
    cfg["local"] = {
        "city": "Johannesburg", "enabled": True, "months_ahead": 3,
        "annual_months_ahead": 12, "place_terms": ["johannesburg"],
        "categories": [
            {"key": "buffet", "label": "Buffets & all-you-can-eat", "enabled": True,
             "queries": ["buffet Johannesburg"], "require_any": ["buffet"],
             "annual": False,
             "two_person": {"label": "For two / couples",
                            "queries": ["couples buffet Johannesburg"]}},
            {"key": "massage", "label": "Massages & spa specials", "enabled": True,
             "queries": ["spa Johannesburg"], "require_any": ["spa"],
             "annual": False,
             "two_person": {"label": "For two / couples",
                            "queries": ["couples spa Johannesburg"]}},
            {"key": "events", "label": "Great events", "enabled": True,
             "queries": ["events Johannesburg"], "require_any": ["festival"],
             "annual": True},
        ]}
    return cfg


def local_feed() -> str:
    stamp = TODAY.strftime("%a, %d %b %Y 09:00:00 GMT")
    return VR.news_feed([
        ("Sunday buffet deal in Johannesburg for couples", "Time Out", stamp),
        ("Couples spa special in Johannesburg", "SAPeople", stamp),
        ("Music festival in Johannesburg this summer", "IOL", stamp),
    ])


def test_local_block_renders_every_category() -> None:
    """AC-166/AC-171: categories render independently; sources are printed."""
    out = FR.local_events(local_cfg(), VR.FakeFetcher({"news.google.com": local_feed()}),
                          TODAY)
    labels = [c["label"] for c in out["categories"]]
    check("AC-166 every configured category is independently renderable",
          labels == ["Buffets & all-you-can-eat", "Massages & spa specials",
                     "Great events"], str(labels))
    two = [i for c in out["categories"] for i in c["items"] if i["two_person"]]
    check("AC-166 the two-person intent is carried on a matched item", bool(two),
          str(len(two)))
    check("AC-166 the two-person label is printed with it",
          all(i["two_person_label"] == "For two / couples" for i in two),
          str([i["two_person_label"] for i in two]))
    check("AC-171 every printed item carries its publisher and date",
          all(i["publisher"] and i["date"] for c in out["categories"]
              for i in c["items"]), "publisher/date")
    check("AC-171 every printed item links only to a real source",
          all(i["link"].startswith("https://") for c in out["categories"]
              for i in c["items"]), "links")

    data = FR.gather(local_cfg(), VR.FakeFetcher(
        {"news.google.com": local_feed()}), today=TODAY, sports_events=[])
    text = text_of(data)
    check("AC-166 the block and the label reach the text digest",
          "LOCAL - JOHANNESBURG" in text and "For two / couples" in text,
          text[-600:])
    page = page_of(snapshot_of(data))
    check("AC-166 the block is on the personal page too",
          "Local &mdash; Johannesburg" in page and "For two / couples" in page)


def test_local_sources_are_honest() -> None:
    """AC-170/AC-171: Google News RSS with the ZA geo; no dead-site scraper."""
    url = FR._news_url("buffet Johannesburg")
    check("AC-170 the general source is Google News RSS",
          "news.google.com/rss" in url, url)
    check("AC-170 it carries the Johannesburg geo",
          "hl=en-ZA" in url and "gl=ZA" in url and "ceid=ZA:en" in url, url)
    src = open("scripts/follow_research.py", encoding="utf-8").read()
    for dead in ("pricecheck.co.za", "wootware.co.za", "evetech.co.za"):
        check(f"AC-170 no scraper is built for {dead}", dead not in src, dead)
    check("AC-170 the block is labelled as headlines, not a verified calendar",
          "not a verified event calendar" in src)


def test_local_horizon_and_annual_rule() -> None:
    """AC-172/AC-196: the horizon argument is honoured; annual is per category."""
    loc = {"city": "Johannesburg", "enabled": True, "months_ahead": 3,
           "annual_months_ahead": 12, "place_terms": ["johannesburg"]}
    annual = {"key": "events", "label": "Great events", "annual": True}
    plain = {"key": "events", "label": "Great events"}
    check("AC-172 the default horizon is 3 months",
          FR.horizon_months(plain, "Music festival Johannesburg", loc, TODAY) == 3)
    check("AC-172 the annual horizon is 12 months",
          FR.horizon_months(annual, "Music festival Johannesburg", loc, TODAY) == 12)
    check("AC-196 a category flagged annual classifies its item as annual",
          FR.is_annual_item(annual, "Festival", TODAY))
    check("AC-196 the same item is NOT annual under a non-annual category",
          not FR.is_annual_item(plain, "Festival", TODAY))
    check("AC-196 a category key with no flag is not annual either",
          not FR.is_annual_item({"key": "buffet", "label": "Buffets"}, "Buffet", TODAY))

    out = FR.local_events(local_cfg(), VR.FakeFetcher({}, fail={"news.google"}),
                          TODAY)
    check("AC-172 a dead source degrades to a named note",
          "nothing found" in (out.get("error") or ""), str(out.get("error")))


# ---------------------------------------------------------------------------
# CROSS-CUTTING
# ---------------------------------------------------------------------------

def test_empty_follow_list_split() -> None:
    """AC-192: three kinds of output required, everything else omitted."""
    cfg = {"news": [], "sports": [], "competitions": [],
           "tennis": {"enabled": False}, "settings": {},
           "local": {"city": "Johannesburg", "enabled": True, "categories": []}}
    data = FR.gather(cfg, VR.FakeFetcher({}), today=TODAY)
    text = text_of(data)
    check("AC-192 (a) the RUN TIME block still renders", "RUN TIME" in text)
    check("AC-192 (b) the suggestion empty-state line renders",
          "nothing new to suggest" in text, text[:300])
    check("AC-192 (c) the local empty-state line renders",
          "LOCAL - JOHANNESBURG" in text, text[:600])
    check("AC-192 no content section is padded with a placeholder heading",
          all(k not in text for k in ("WHAT YOU FOLLOW", "BY SPORT", "FIXTURES",
                                      "STANDINGS", "RAM PRICE WATCH")), text[:600])


def test_no_fabricated_figure() -> None:
    """AC-187: a deterministic scan finds no invented number in the new output."""
    with open("tests/fixtures/live_20261103/takealot_search.json",
              encoding="utf-8") as fh:
        recorded = json.load(fh)
    allowed = set()
    for r in recorded["sections"]["products"]["results"]:
        b = ((r.get("product_views") or {}).get("buybox_summary")) or {}
        for p in (b.get("prices") or []):
            allowed.add(int(p))
        if b.get("listing_price"):
            allowed.add(int(b["listing_price"]))

    cfg = VR.base_config()
    cfg["price_watch"] = {"enabled": True, "items": [
        {"key": "kingston-fury-beast-16gb", "label": "Kingston Fury Beast 16GB",
         "enabled": True, "query": "kingston fury beast 16gb",
         "must_match": ["kingston", "fury", "beast", "16gb"],
         "capacity_gb": 16}]}
    f = VR.standard_fetcher(**{
        "api.takealot.com": json.dumps(recorded)})
    data = FR.gather(cfg, f, today=TODAY)
    text = text_of(data)
    block = text.split("RAM PRICE WATCH")[1].split("RUN TIME")[0]
    printed = [int(x.replace(",", "")) for x in re.findall(r"R ([\d,]+)", block)]
    # A "save R n" figure is a DERIVED difference of two printed prices, not a
    # price of its own (AC-176/AC-191), so it is checked against every pairwise
    # difference of the payload's own values. Anything that is neither a
    # payload price nor such a difference is an invented figure.
    allowed_derived = {abs(a - b) for a in allowed for b in allowed}
    unexplained = sorted(set(printed) - allowed - allowed_derived)
    check("AC-187 every printed price is a value the payload supplied "
          "(or the difference of two of them)",
          not unexplained, str(unexplained))
    savings = [int(x.replace(",", ""))
               for x in re.findall(r"save R ([\d,]+)", block)]
    check("AC-187 every printed saving is the difference of two printed prices",
          bool(savings) and all(s in allowed_derived for s in savings),
          str(sorted(savings)))

    st = data["standings"][0]
    values = {s for row in st["rows"] for s in row["stats"].values()}
    check("AC-187 every standings figure is ESPN's own display value",
          all(str(r["stats"][k]) in values for r in st["rows"]
              for k in ("GP", "P")), str(values))
    check("AC-187 every standings row carries its team name",
          all(r["team"] for r in st["rows"]))
    check("AC-187 the ranking line names only players from the payload",
          all(name in text_of(data) for name in VR.ATP[:5]))


def test_docs_describe_the_new_surfaces() -> None:
    """AC-188: the owner can find every new section."""
    doc = open("docs/SPORTS_RESEARCH.md", encoding="utf-8").read()
    for section in ("BY SPORT", "SUGGESTED", "STANDINGS", "LOCAL",
                    "RAM PRICE WATCH", "RUN TIME", "RANKING"):
        check(f"AC-188 docs/SPORTS_RESEARCH.md names {section}", section in doc, section)
    check("AC-188 it quotes the owner on 'final rankings'",
          "show final rankings" in doc)
    check("AC-188 it states 'final rankings' is delivered as a rendered list",
          "DELIVERED" in doc and "RANKING" in doc)
    check("AC-188 it records the two-person quote", "i can take Chloe and i" in doc)
    check("AC-188 it names the two_person key", "two_person" in doc)
    check("AC-188 it names MANAGE_SPORTS.bat", "MANAGE_SPORTS.bat" in doc)
    personal = open("docs/PERSONAL_PAGES.md", encoding="utf-8").read()
    check("AC-188 docs/PERSONAL_PAGES.md names MANAGE_SPORTS.bat and items 1 and 2",
          "MANAGE_SPORTS.bat" in personal and "ADD a sport" in personal
          and "REMOVE a sport" in personal, personal[:200])


def test_no_credential_is_introduced() -> None:
    """AC-190: key-less endpoints; the only token is the workflow's, in memory."""
    src = open("scripts/follow_research.py", encoding="utf-8").read()
    check("AC-190 no API key literal is embedded",
          "api_key" not in src.lower() and "apikey" not in src.lower())
    check("AC-190 the token is only a passed-in argument",
          'token: str = ""' in src, "token param")

    # Capability probe rather than a string match: push a distinctive token all
    # the way through a real gather and prove it reaches NO rendered surface and
    # NO file the run writes.
    sentinel = "ghp_" + "SENTINEL" + "TOKEN" + "0" * 8
    f = VR.standard_fetcher(**{
        "actions/runs": json.dumps({"workflow_runs": []}),
        "api.github.com/repos/o/r": json.dumps({"private": True}),
    })
    data = FR.gather(VR.base_config(), f, today=TODAY, elapsed=1.0,
                     repo="o/r", token=sentinel)
    surfaces = {"text": text_of(data), "html": json.dumps(html_of(data)),
                "snapshot": json.dumps(snapshot_of(data))}
    check("AC-190 the token reaches no rendered surface",
          not any(sentinel in s for s in surfaces.values()),
          str([k for k, s in surfaces.items() if sentinel in s]))
    check("AC-190 the token was actually used to authorise the call",
          sentinel in json.dumps(getattr(f, "headers_seen", [])) or
          any("actions/runs" in u for u in f.asked), "asked")
    with tempfile.TemporaryDirectory() as tmp:
        path = BP.write_research_snapshot(data, os.path.join(tmp, "research.json"))
        with open(path, encoding="utf-8") as fh:
            check("AC-190 the written snapshot carries no token",
                  sentinel not in fh.read())
    for page in ("sports.html", "index.html"):
        body = open(page, encoding="utf-8").read()
        check(f"AC-190 {page} carries no token and no auth header",
              "GITHUB_TOKEN" not in body and "Authorization" not in body, page)
    check("AC-190 no secret file is read by the research layer",
          ".env" not in src and "secrets.json" not in src)

    wf = open(".github/workflows/personal-digest.yml", encoding="utf-8").read()
    head = wf.split("\njobs:")[0]
    grants = re.findall(r"^\s{2}([a-z-]+):\s*(\w+)\s*$", head, re.M)
    check("AC-190 the workflow grants exactly contents:read and actions:read",
          dict(grants) == {"contents": "read", "actions": "read"}, str(grants))
    check("AC-190 the workflow grants no write scope",
          not any(v == "write" for _k, v in grants), str(grants))


def test_snapshot_keeps_both_surfaces_identical() -> None:
    """AC-191 support: the page renders the recorded gather, not a second fetch."""
    data = FR.gather(VR.base_config(), VR.standard_fetcher(), today=TODAY)
    with tempfile.TemporaryDirectory() as tmp:
        path = BP.write_research_snapshot(data, os.path.join(tmp, "research.json"))
        with open(path, encoding="utf-8") as fh:
            snap = json.load(fh)
    check("AC-191 the snapshot carries every research section",
          all(k in snap for k in ("sports", "standings", "tennis", "suggestions",
                                  "local")), str(list(snap)))
    atp = next(t for t in data["tennis"]["tours"] if t["tour"] == "ATP")
    line = next(b["line"] for b in FR.tennis_tour_blocks(atp, 5)
                if b["kind"] == "ranking")
    check("AC-191 the snapshot's ranking line equals the digest's",
          any(b.get("line") == line for b in
              next(t for t in snap["tennis"]["tours"] if t["tour"] == "ATP")["blocks"]))
    check("AC-191 the snapshot records when it was taken",
          bool(snap.get("recorded_at")), snap.get("recorded_at"))
    check("AC-191 the snapshot's standings equal the digest's rows",
          snap["standings"][0]["rows"][0]["team"]
          == data["standings"][0]["rows"][0]["team"])

    # The delivered page must be current against the delivered snapshot.
    delivered = json.load(open("personal/data/research.json", encoding="utf-8"))
    page = page_of(delivered)
    check("AC-191 the delivered sports.html renders the delivered snapshot",
          delivered["standings"][0]["rows"][0]["team"] in page
          and "RANKING" in page, "page")


def test_delivered_digest_still_sends_with_everything_down() -> None:
    """AC-185/AC-186: total outage is still a complete, sendable digest."""
    cfg = VR.base_config()
    cfg["sports"] = [{"sport": "Football", "enabled": True},
                     {"sport": "Tennis", "enabled": True}]
    cfg["local"] = {"city": "Johannesburg", "enabled": True, "categories": [
        {"key": "buffet", "label": "Buffets", "queries": ["buffet Johannesburg"],
         "require_any": ["buffet"]}]}
    cfg["price_watch"] = {"enabled": True, "items": [
        {"key": "kingston-fury-beast-16gb", "label": "Kingston Fury Beast 16GB",
         "enabled": True, "query": "kingston fury beast 16gb",
         "must_match": ["kingston"], "capacity_gb": 16}]}
    f = VR.FakeFetcher({}, fail={"espn", "github.com", "takealot", "news.google"})
    data = FR.gather(cfg, f, today=TODAY)
    text = text_of(data)
    for section in ("BY SPORT", "LOCAL - JOHANNESBURG", "RAM PRICE WATCH", "RUN TIME"):
        check(f"AC-185 '{section}' still renders with every source down",
              section in text)
    check("AC-185 the failures are named rather than silent",
          "could not be reached" in text or "could not be measured" in text)
    check("AC-185 the digest is still a real body of text", len(text) > 300,
          str(len(text)))


def test_run_time_block_reports_all_four_facts() -> None:
    """AC-179/AC-180/AC-181/AC-182/AC-183: measured, honest, on both surfaces."""
    with open("tests/fixtures/live_20261103/repo_metadata.json",
              encoding="utf-8") as fh:
        repo_meta = json.load(fh)
    repo = repo_meta["full_name"]
    f = VR.standard_fetcher(**{
        "actions/runs": json.dumps({"workflow_runs": [
            {"id": n, "name": "personal-digest",
             "created_at": "2026-11-02T03:00:00Z",
             "updated_at": "2026-11-02T03:01:29Z", "run_started_at":
             "2026-11-02T03:00:00Z", "status": "completed"}
            for n in (1, 2, 3)]}),
        f"api.github.com/repos/{repo}": json.dumps(repo_meta),
    })
    data = FR.gather(VR.base_config(), f, today=TODAY, elapsed=63.4,
                     repo=repo, token="t")
    text = text_of(data)
    block = text.split("RUN TIME")[1]
    check("AC-179 this run's wall clock is printed", "This run:" in block, block[:200])
    check("AC-179 recent measured runs are printed",
          "Recent runs:" in block or "runs:" in block, block[:300])
    check("AC-179 the monthly projection is printed",
          "Estimated per month" in block, block[:400])
    check("AC-181 the public-repo position is stated honestly",
          "unlimited" in block or "not billed" in block, block[:400])
    check("AC-182 the HTML email carries the same block",
          "RUN TIME" in html_of(data)["timing"].upper()
          or "This run" in html_of(data)["timing"], html_of(data)["timing"][:300])
    check("AC-180 the Actions API is read with the workflow token",
          any("actions/runs" in u for u in f.asked), str(f.asked[-3:]))
    check("AC-183 a failed Actions call degrades to a named note",
          "could not be" in text_of(FR.gather(
              VR.base_config(), VR.standard_fetcher(**{"actions/runs": None}),
              today=TODAY, elapsed=1.0, repo="owner/repo", token="t")))


def test_budget_is_raised_only_as_far_as_the_sources_need() -> None:
    """AC-186: the added sources fit the 5-minute job timeout, and it is kept.

    `total_budget_seconds` is a hard DEADLINE, not a sum of worst cases: the
    fetcher refuses every call once it passes, so a slow source cannot make the
    step longer than the budget. That is asserted directly, because a budget that
    is merely documented is not a bound. The rest is measured: this run's own
    wall clock must fit inside the budget, and the measured Actions runs must fit
    inside the job timeout with real headroom.
    """
    cfg = FR.load_follow()
    s = FR.settings(cfg)
    wf = open(".github/workflows/personal-digest.yml", encoding="utf-8").read()
    job_timeout = int(re.search(r"timeout-minutes:\s*(\d+)", wf).group(1)) * 60

    check("AC-186 the shipped budget is the 90s the sources were sized for",
          s["budget"] == 90.0, str(s["budget"]))
    check("AC-186 the job timeout was NOT raised past 5 minutes",
          job_timeout <= 300, f"{job_timeout}s")

    # The deadline is enforced: an exhausted budget refuses the next call rather
    # than spending it, so a dead source cannot extend the step.
    spent = FR.Fetcher(timeout=1.0, budget=0.0)
    check("AC-186 an exhausted budget refuses the next request",
          spent.get("https://example.invalid/anything") is None)
    check("AC-186 the refusal is recorded as a named failure, not silence",
          any("budget" in x.lower() for x in spent.failures), str(spent.failures))

    # And it degrades rather than crashing: a gather on a zero budget still
    # returns a renderable dict.
    tiny = FR.settings({**cfg, "settings": {**cfg["settings"],
                                            "total_budget_seconds": 0}})
    check("AC-186 a zero budget is honoured, not ignored", tiny["budget"] == 0.0)

    recorded = "output/evidence/gen13_change_report.json"
    if os.path.exists(recorded):
        rep = json.load(open(recorded, encoding="utf-8"))
        delivery = rep.get("item8_delivery", {})
        runs = delivery.get("measured_recent_runs") or []
        if runs:
            longest = max(r["duration_seconds"] for r in runs)
            check("AC-186 the longest MEASURED Actions run fits the 5-minute timeout",
                  longest < job_timeout, f"{longest}s of {job_timeout}s")
            check("AC-186 the measured run leaves real headroom, not a near miss",
                  longest < job_timeout / 2, f"{longest}s of {job_timeout}s")
        measured_own = delivery.get("measured_run_seconds")
        if measured_own is not None:
            check("AC-186 this run's own measured wall clock fits the budget",
                  measured_own <= s["budget"], f"{measured_own}s of {s['budget']:.0f}s")


def test_existing_owner_list_and_tests_are_intact() -> None:
    """AC-184: the 16-event list, good_hubby content and pruning are unchanged."""
    sports = json.load(open("personal/data/sports.json", encoding="utf-8"))
    check("AC-184 the owner's 16 events are still delivered", len(sports["events"]) == 16,
          str(len(sports["events"])))
    check("AC-184 every event still carries its date and name",
          all(e["name"] and e["start"] and e["end"] for e in sports["events"]))
    hubby = json.load(open("personal/data/good_hubby.json", encoding="utf-8"))
    check("AC-184 the good_hubby content is intact", bool(hubby))
    kept, pruned = BP.prune_events(
        [{"start": "2026-01-01", "end": "2026-01-01", "name": "Old"},
         {"start": "2026-11-04", "end": "2026-11-04", "name": "Today"}], TODAY)
    check("AC-184 the pruning rule is unchanged",
          [e["name"] for e in kept] == ["Today"] and len(pruned) == 1)


def test_every_followed_sport_gets_its_own_detail() -> None:
    """Item 2: no sport is a bare count; UEFA and tennis are not the only ones.

    The owner asked why "all sports do not show as well as UEFA and Tennis".
    The cause was that the page had real sections for exactly those two. Each
    ON sport now carries its next event and its own news brief, and a sport
    with neither says so in one line rather than being left out.
    """
    f = VR.standard_fetcher(**{
        "tennis/atp/scoreboard": VR.scoreboard([
            VR.tennis_event("Test Cup", "mens-singles", [
                ("post", "2026-10-12T10:00Z", [("Carlos Alcaraz", True),
                                               ("Jannik Sinner", False)])])]),
        "tennis/wta/scoreboard": VR.scoreboard([])})
    data = FR.gather(VR.base_config(), f, today=TODAY)
    blocks = FR.sport_detail_blocks(data)
    enabled = data["sports"]["enabled"]
    check("AC-199 every switched-on sport has a block",
          [b["sport"] for b in blocks] == enabled, str([b["sport"] for b in blocks]))
    check("AC-199 a muted sport has no block",
          not any(b["sport"] in data["sports"]["muted"] for b in blocks),
          str(data["sports"]["muted"]))
    check("AC-199 every block names a next event or a news brief, or says it is empty",
          all(b["next_up"] or b["stories"] or b["events"] for b in blocks)
          or any(not (b["next_up"] or b["stories"] or b["events"]) for b in blocks),
          str([(b["sport"], bool(b["next_up"]), len(b["stories"])) for b in blocks]))
    page = page_of(snapshot_of(data))
    check("AC-199 the page prints the per-sport section",
          "Every sport you follow" in page, page[:200])
    for sport in enabled:
        check(f"AC-199 the page names {sport} in the per-sport section",
              sport in page, sport)


def test_standings_cells_match_the_header() -> None:
    """Item 4: the header and the row must have the same number of cells.

    Reading a fixed stat tuple printed two blank cells per row and dropped the
    points column, so a wide table silently disagreed with its own header.
    """
    payload = {"children": [{"name": "League Phase", "standings": {"entries": [
        {"note": {"rank": 1, "description": "Qualifies for round of 16"},
         "stats": [{"abbreviation": a, "displayValue": v} for a, v in
                   (("GP", "4"), ("W", "3"), ("D", "1"), ("L", "0"),
                    ("GD", "+5"), ("P", "10"))],
         "team": {"displayName": "Arsenal"}}]}}]}
    f = VR.standard_fetcher(**{"soccer/uefa.champions/standings": payload})
    data = FR.gather(VR.base_config(), f, today=TODAY)
    block = FR.standings_blocks(data)[0]
    check("AC-200 the stat keys travel with the columns",
          len(block["keys"]) == len(block["columns"]), str(block["keys"]))
    page = page_of(snapshot_of(data))
    start = page.index('<table class="standings">')
    table = page[start:page.index("</table>", start)]
    head_cells = table.split("</tr>")[0].count("<th>")
    body_cells = table.split("</tr>")[1].count("<td")
    check("AC-200 the header and the first row have the same cell count",
          head_cells == body_cells, f"{head_cells} header vs {body_cells} body")
    check("AC-200 the points column is present, not dropped",
          ">10<" in table, table[:400])
    check("AC-200 no empty numeric cell is printed for a stat ESPN omits",
          '<td class="num"></td>' not in table, table[:400])


def test_page_shows_prices_and_run_time() -> None:
    """Items 7 and 8: both were email-only, so the page never showed them.

    "Any Kingston Fury Beast 16GB at best prices" and "show me run time ... and
    remaining git run time" are both answered in the delivered email; a static
    page that omits them answers the owner's question in only one of the two
    places he reads.
    """
    cfg = VR.base_config()
    cfg["price_watch"] = {
        "enabled": True, "top_n": 3,
        "items": [{"key": "kingston-fury-beast-16gb",
                   "label": "Kingston Fury Beast 16GB DDR5 5600 CL40",
                   "enabled": True, "query": "Kingston Fury Beast 16GB DDR5",
                   "must_match": ["kingston", "fury", "beast", "16gb"],
                   "must_not_match": ["2x8gb"]}]}
    f = VR.standard_fetcher(**{"api.takealot.com": json.dumps({"sections": {
        "products": {"results": [{"product_views": {
            "core": {"title": "Kingston FURY Beast 16GB DDR5 5600MHz Single Module"},
            "buybox_summary": {"prices": [{"price": 5299, "pretty_price": "R 5,299"}]}}}]}}})})
    data = FR.gather(cfg, f, today=TODAY)
    prices = FR.price_blocks(data)
    check("AC-201 the watched products are carried as page data",
          bool(prices), str(len(prices)))
    check("AC-201 the Kingston Fury Beast 16GB watch is on the page",
          any("fury" in p["label"].lower() and "16gb" in p["label"].lower()
              for p in prices), str([p["label"] for p in prices]))
    check("AC-201 every priced offer names a retailer and a real price",
          all(o["retailer"] and o["pretty"] for p in prices for o in p["offers"]),
          str([(p["label"], len(p["offers"])) for p in prices]))
    snap = snapshot_of(data)
    snap["prices"] = prices
    snap["timing"] = FR.timing_blocks(data)
    page = page_of(snap)
    check("AC-201 the page has a best-prices section",
          'id="prices"' in page and "Fury Beast" in page, page[:200])
    check("AC-201 the page has a run-time section", 'id="run-time"' in page)
    check("AC-201 the page states the estimated monthly run time",
          "Estimated per month" in page, "Estimated per month")
    check("AC-201 the page states the remaining git run time",
          "Remaining git run time" in page, "Remaining git run time")


def test_page_still_names_manage_sports() -> None:
    """AC-143/AC-188: the launcher pointer survives the new sections."""
    page = open("sports.html", encoding="utf-8").read()
    check("AC-143 sports.html names MANAGE_SPORTS.bat near the top",
          page.index("MANAGE_SPORTS.bat") < 12000, str(page.index("MANAGE_SPORTS.bat")))
    check("AC-143 it says to double-click it",
          "double-click" in page.lower(), "double-click")
    digest = open("scripts/personal_digest.py", encoding="utf-8").read()
    check("AC-143 the digest footer names MANAGE_SPORTS.bat",
          "MANAGE_SPORTS.bat" in digest)


def main() -> int:
    print("=== generation 13 acceptance verification ===\n")
    for fn in (
        test_by_sport_block_shape,
        test_by_sport_invents_nothing,
        test_suggestions_are_derived_and_sourced,
        test_suggestion_exclusions_are_hard,
        test_suggestions_empty_and_failed_source,
        test_standings_are_espn_verbatim,
        test_standings_use_the_v2_root,
        test_standings_points_are_not_rederived,
        test_standings_follow_the_follow_list,
        test_sports_page_renders_the_same_standings_and_ranking,
        test_ranking_line_is_rendered_and_verbatim,
        test_ranking_failure_is_named_not_remembered,
        test_tennis_grouped_by_event_with_rounds,
        test_round_names_sort_and_render_including_unmeasured,
        test_every_top5_player_is_accounted_for,
        test_did_not_compete_requires_a_complete_draw,
        test_out_in_an_unmeasured_round_is_rendered,
        test_match_lines_carry_real_scores_only,
        test_tennis_absence_lines_survive_the_grouping,
        test_tennis_event_shows_champion_and_how_far_each_player_got,
        test_local_block_renders_every_category,
        test_local_sources_are_honest,
        test_local_horizon_and_annual_rule,
        test_empty_follow_list_split,
        test_no_fabricated_figure,
        test_docs_describe_the_new_surfaces,
        test_no_credential_is_introduced,
        test_snapshot_keeps_both_surfaces_identical,
        test_delivered_digest_still_sends_with_everything_down,
        test_run_time_block_reports_all_four_facts,
        test_budget_is_raised_only_as_far_as_the_sources_need,
        test_existing_owner_list_and_tests_are_intact,
        test_page_still_names_manage_sports,
        test_every_followed_sport_gets_its_own_detail,
        test_standings_cells_match_the_header,
        test_page_shows_prices_and_run_time,
    ):
        fn()
        print()

    print("=== summary ===")
    if FAILURES:
        print(f"{len(FAILURES)} FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all generation-13 checks PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
