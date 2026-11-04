#!/usr/bin/env python3
"""Add or remove the people, teams and competitions you follow.

Owner request (2026-10-12): "Maybe find a way i can easily add or remove
people/teams from sports. I.e. UEFA i only want specific teams".

Three ways to do it, in increasing order of effort:

  1. Double-click `MANAGE_SPORTS.bat` on Windows. A numbered menu; nothing to
     remember and no file to open.
  2. Run a command from here (see `--help`).
  3. Edit `personal/data/follow.json` by hand. It is plain JSON with a comment
     on every list. This tool only ever rewrites that same file.

The file is the single source of truth; this is a convenience layer over it.
Nothing is ever added that you did not type, and removing the last entry of a
list leaves it empty rather than filling it with a default.

Usage:
    python3 scripts/follow_edit.py --show
    python3 scripts/follow_edit.py add-news "Formula 1" --sport Motorsport
    python3 scripts/follow_edit.py remove-news "Formula 1"
    python3 scripts/follow_edit.py add-team uefa.champions Arsenal
    python3 scripts/follow_edit.py remove-team uefa.champions Arsenal
    python3 scripts/follow_edit.py add-competition uefa.champions
    python3 scripts/follow_edit.py remove-competition uefa.champions
    python3 scripts/follow_edit.py --list-teams uefa.champions
    python3 scripts/follow_edit.py --list-sports
    python3 scripts/follow_edit.py add-sport "Padel"
    python3 scripts/follow_edit.py remove-sport "Weightlifting"
    python3 scripts/follow_edit.py --list-competitions
    python3 scripts/follow_edit.py --tennis top_n 10
    python3 scripts/follow_edit.py --tennis enabled off
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import follow_research as FR  # noqa: E402

PATH = os.path.join(ROOT, "personal", "data", "follow.json")


def read() -> dict:
    if not os.path.exists(PATH):
        return {"news": [], "sports": [], "competitions": [],
                "tennis": {"enabled": False}, "settings": {}}
    with open(PATH, encoding="utf-8") as fh:
        return json.load(fh)


def write(cfg: dict) -> None:
    """Write the file back, preserving the explanatory keys the owner reads."""
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def find_sport(cfg: dict, sport: str) -> dict | None:
    for row in cfg.setdefault("sports", []):
        if row.get("sport", "").lower() == sport.lower():
            return row
    return None


def add_sport(cfg: dict, sport: str) -> str:
    """Add a sport, or switch a muted one back on."""
    sport = sport.strip()
    if not sport:
        return "A sport needs a name."
    row = find_sport(cfg, sport)
    if row is not None:
        if row.get("enabled", True):
            return f"'{row['sport']}' is already on."
        row["enabled"] = True
        return f"Switched '{row['sport']}' back on."
    cfg.setdefault("sports", []).append({
        "sport": sport, "enabled": True,
        "source": "Added by you with MANAGE_SPORTS.bat",
    })
    return f"Added '{sport}'."


def remove_sport(cfg: dict, sport: str) -> str:
    """Mute a sport. The row stays, so this is reversible with add-sport."""
    row = find_sport(cfg, sport)
    if row is None:
        return f"'{sport}' is not in the sport list."
    if not row.get("enabled", True):
        return f"'{row['sport']}' is already off."
    row["enabled"] = False
    return (f"Removed '{row['sport']}' - it is switched off and will not appear in "
            f"events, suggestions or local matches. Add it back to undo.")


def list_sports(cfg: dict) -> str:
    rows = cfg.get("sports") or []
    if not rows:
        return "No sports listed yet. Add one with: --add-sport \"Tennis\""
    return "\n".join(
        f"  [{'on ' if r.get('enabled', True) else 'OFF'}] {r['sport']}"
        for r in rows if r.get("sport"))


def remember_removed(cfg: dict, name: str) -> None:
    """Record a removal so suggestions can never re-propose it."""
    if not name:
        return
    removed = cfg.setdefault("removed", [])
    if not any(r.lower() == name.lower() for r in removed):
        removed.append(name)


def find_competition(cfg: dict, league: str) -> dict | None:
    for entry in cfg.setdefault("competitions", []):
        if entry.get("league") == league:
            return entry
    return None


def ensure_competition(cfg: dict, league: str) -> dict:
    entry = find_competition(cfg, league)
    if entry is None:
        entry = {"label": FR.LEAGUES.get(league, league), "league": league, "teams": []}
        cfg["competitions"].append(entry)
    entry.setdefault("teams", [])
    return entry


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def add_news(cfg: dict, label: str, sport: str) -> str:
    cfg.setdefault("news", [])
    for entry in cfg["news"]:
        if entry.get("label", "").lower() == label.lower():
            return f"Already following '{entry['label']}'."
    entry = {"label": label, "query": label}
    if sport:
        entry["sport"] = sport
    cfg["news"].append(entry)
    return f"Following '{label}'" + (f" ({sport})" if sport else "") + "."


def remove_news(cfg: dict, label: str) -> str:
    before = len(cfg.get("news", []))
    cfg["news"] = [e for e in cfg.get("news", [])
                   if e.get("label", "").lower() != label.lower()]
    if len(cfg["news"]) == before:
        return f"'{label}' was not in the news list."
    return f"Stopped following '{label}'."


def add_team(cfg: dict, league: str, team: str) -> str:
    if league not in FR.LEAGUES:
        return (f"Unknown competition '{league}'. "
                f"Run --list-competitions to see the ids I know.")
    entry = ensure_competition(cfg, league)
    if any(t.lower() == team.lower() for t in entry["teams"]):
        return f"'{team}' is already in {entry['label']}."
    entry["teams"].append(team)
    return f"Added '{team}' to {entry['label']}."


def remove_team(cfg: dict, league: str, team: str) -> str:
    entry = find_competition(cfg, league)
    if entry is None:
        return f"Not following {league}."
    before = len(entry["teams"])
    entry["teams"] = [t for t in entry["teams"] if t.lower() != team.lower()]
    if len(entry["teams"]) == before:
        return f"'{team}' was not in {entry['label']}."
    return f"Removed '{team}' from {entry['label']}."


def add_competition(cfg: dict, league: str) -> str:
    if league not in FR.LEAGUES:
        return (f"Unknown competition '{league}'. "
                f"Run --list-competitions to see the ids I know.")
    ensure_competition(cfg, league)
    return f"Now following {FR.LEAGUES[league]} (all teams until you add some)."


def remove_competition(cfg: dict, league: str) -> str:
    before = len(cfg.get("competitions", []))
    kept = [e for e in cfg.get("competitions", []) if e.get("league") != league]
    if len(kept) == before:
        return f"Not following {league}."
    # Remember it, so the suggestions block can never propose it back.
    for e in cfg["competitions"]:
        if e.get("league") == league:
            remember_removed(cfg, e.get("label") or league)
    cfg["competitions"] = kept
    return f"Stopped following {league}. It will not be suggested back."


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def show(cfg: dict) -> None:
    print("WHO YOU FOLLOW")
    print(f"  file: {os.path.relpath(PATH, ROOT)}")
    print()
    rows = cfg.get("sports") or []
    print(f"Sports ({len(rows)})  <- ADD OR REMOVE A SPORT WITH --add-sport / --remove-sport")
    for r in rows:
        print(f"  [{'on ' if r.get('enabled', True) else 'OFF'}] {r.get('sport')}")
    if not rows:
        print("  (none listed - add one with --add-sport \"Tennis\")")
    print()

    news = cfg.get("news", [])
    print(f"News ({len(news)})")
    for e in news:
        print(f"  - {e.get('label')}" + (f"  [{e['sport']}]" if e.get("sport") else ""))
    if not news:
        print("  (nothing - the digest will not search for news)")
    print()

    comps = cfg.get("competitions", [])
    print(f"Competitions ({len(comps)})")
    for e in comps:
        teams = e.get("teams") or []
        scope = ", ".join(teams) if teams else "ALL TEAMS (no filter set)"
        print(f"  - {e.get('label')} [{e.get('league')}]: {scope}")
    if not comps:
        print("  (nothing)")
    print()

    t = cfg.get("tennis", {})
    state = "on" if t.get("enabled") else "off"
    print(f"Tennis: {state}")
    if t.get("enabled"):
        print(f"  tours: {', '.join(t.get('tours', []))}   top: {t.get('top_n')}")
    print()


def list_competitions() -> None:
    print("Competition ids I know (use these with add-competition / add-team):")
    for key, name in sorted(FR.LEAGUES.items()):
        print(f"  {key:<16} {name}")


def list_teams(league: str) -> int:
    if league not in FR.LEAGUES:
        print(f"Unknown competition '{league}'. Run --list-competitions.")
        return 1
    f = FR.Fetcher(timeout=15, budget=30)
    data = f.json(f"{FR.ESPN}/soccer/{league}/scoreboard")
    if data is None:
        print(f"Could not reach ESPN for {league}: {'; '.join(f.failures) or 'no response'}")
        return 1
    teams = set()
    for ev in data.get("events") or []:
        for c in ev.get("competitions") or []:
            for t in c.get("competitors", []):
                name = (t.get("team") or {}).get("displayName")
                if name:
                    teams.add(name)
    if not teams:
        print(f"No fixtures listed for {league} right now, so no team names to show. "
              f"You can still add a team by name - it matches loosely.")
        return 0
    print(f"Teams playing in {FR.LEAGUES[league]} in the current matchweek:")
    for name in sorted(teams):
        print(f"  {name}")
    print()
    print("Note: this is the current matchweek only, not the full competition. "
          "Adding a team that is not playing now is fine - it simply shows up "
          "when it plays.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", action="store_true", help="print the current follow list")
    ap.add_argument("--list-competitions", action="store_true", help="competition ids")
    ap.add_argument("--list-sports", action="store_true",
                    help="the sports you follow, and whether each is on")
    ap.add_argument("--list-teams", metavar="LEAGUE", help="teams playing in a competition now")
    ap.add_argument("--tennis", nargs=2, metavar=("KEY", "VALUE"),
                    help="set a tennis option, e.g. --tennis top_n 10")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("add-news"); p.add_argument("label"); p.add_argument("--sport", default="")
    p = sub.add_parser("remove-news"); p.add_argument("label")
    p = sub.add_parser("add-team"); p.add_argument("league"); p.add_argument("team")
    p = sub.add_parser("remove-team"); p.add_argument("league"); p.add_argument("team")
    p = sub.add_parser("add-sport"); p.add_argument("sport")
    p = sub.add_parser("remove-sport"); p.add_argument("sport")
    p = sub.add_parser("add-competition"); p.add_argument("league")
    p = sub.add_parser("remove-competition"); p.add_argument("league")

    args = ap.parse_args()
    cfg = read()

    if args.list_competitions:
        list_competitions(); return 0
    if args.list_sports:
        print(list_sports(cfg))
        return 0
    if args.list_teams:
        return list_teams(args.list_teams)
    if args.tennis:
        key, value = args.tennis
        t = cfg.setdefault("tennis", {})
        if key in ("top_n",):
            t[key] = int(value)
        elif key == "enabled":
            t[key] = value.strip().lower() not in ("off", "false", "no", "0")
        elif key == "tours":
            t[key] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            print(f"Unknown tennis option '{key}'. Try top_n, enabled or tours.")
            return 2
        write(cfg)
        print(f"Tennis {key} is now {t[key]}.")
        return 0

    if args.cmd is None:
        show(cfg)
        return 0

    message = {
        "add-news": lambda: add_news(cfg, args.label, args.sport),
        "remove-news": lambda: remove_news(cfg, args.label),
        "add-team": lambda: add_team(cfg, args.league, args.team),
        "remove-team": lambda: remove_team(cfg, args.league, args.team),
        "add-competition": lambda: add_competition(cfg, args.league),
        "remove-competition": lambda: remove_competition(cfg, args.league),
        "add-sport": lambda: add_sport(cfg, args.sport),
        "remove-sport": lambda: remove_sport(cfg, args.sport),
    }[args.cmd]()

    write(cfg)
    print(message)
    print()
    show(cfg)
    print("Rebuild the pages if you want them to reflect this: "
          "python3 scripts/build_personal.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
