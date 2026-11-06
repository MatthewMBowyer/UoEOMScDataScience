# Following sport: how the research layer works

You asked for the daily message to do more research, so it now reports on what
you follow rather than only the fixed 16-event list. This page explains what it
does, how to change what it follows, and how to run it yourself.

Nothing here is published to the internet. The pages are local-only and the
email comes from your own GitHub Actions job.

---

## 1. What the daily email now contains

The digest still opens with the 16 events, your special days and the check-in
line. Below that come the sections this generation added.

**BY SPORT** — one line for every sport you have switched ON: how many events
are in the window, and the next one with its date. A sport you follow that has
nothing on says so in one line instead of disappearing, and a sport you switched
OFF has **no row at all**. Its on/off state is shown only by the follow table on
`sports.html`.

**What you follow** — recent headlines for each topic you follow. Each line names
the publisher, and each headline links to the article.

**Fixtures** — the matches in each competition you follow. If you have set a team
filter, only your teams' matches appear. If you have not, every fixture in that
competition appears and the heading says so.

**STANDINGS** — the league table for every competition you follow that publishes
one, with position, team, played, won, drawn, lost, goal difference and points,
plus the note the source attaches to the row ("Advances to round of 16",
"Eliminated"). The column headings and the numbers are the publisher's own.
Every followed competition is asked for a table; one that has no table says so in
a named note rather than vanishing.

**Tennis** — the current top 5 of the ATP and WTA tours, grouped **by event** so
the tournament name is a heading rather than a suffix on every line. See section
9 for the full reading of item 5.

**SUGGESTED** — competitions and events of the sports you follow that you are
*not* following yet, each with the source it came from and why it appeared. A
sport you removed, or an item you already follow, can never be suggested: both
exclusion lists are applied before anything is rendered. An empty list is a legal
answer and prints one line saying so.

**LOCAL - JOHANNESBURG** — what is on near you, in three separately renderable
categories: buffets / all-you-can-eat, massages and spa specials, and general
great events. The spa and buffet searches also run a two-person query for you
(the "nice massage sale i can take Chloe and i" request) and label those matches
"For two / couples". These are news headlines with their publisher and date,
clearly labelled as headlines rather than a verified event calendar.

**KINGSTON FURY BEAST 16GB — BEST PRICES NOW** — the featured watch gets its own
heading above the rest: the cheapest current price for the memory kit you named,
cheapest first, with the retailer, whether it is a kit or a single module, and
the saving against the dearest listing of the same kind.

**OTHER PARTS YOU WATCH** — every other watched part, same rules. This heading
used to read "RAM PRICE WATCH" while the rows beneath it were a GPU, a CPU, a PSU,
an SSD, a cooler and a case, so it named memory that was not in the list. The price
printed is the selling price the retailer displays; the saving is the difference
between two printed prices.

**RUN TIME** — four facts, every run: how long this run took, how long the recent
runs took (measured from the Actions runs, not estimated), the projected monthly
total on the actual schedule (daily at 05:00 SAST plus the Sunday weekly run), and
the Actions-minutes position. This repository is public and GitHub does not bill
Actions minutes for public repositories, so the position is stated as unlimited
rather than as a shrinking number that would be made up.

If a source is down, that section says which one could not be reached. It never
guesses and it never invents a result.

---

## 2. Changing what you follow

Everything is decided by one file: `personal/data/follow.json`. Three ways to
change it, easiest first.

### Option A — the menu (recommended)

Double-click **`MANAGE_SPORTS.bat`** in the project folder. You get a numbered
menu:

```
  1  Add news to follow        (e.g. Formula 1, Springboks)
  2  Remove news
  3  Add a team to a competition
  4  Remove a team
  5  Add a competition
  6  Remove a competition
  7  Change the tennis top N
  8  Show teams playing in a competition right now
  9  Show the competition ids
  0  Exit
```

Type a number, answer the question, and it is done. Nothing to install.

### Option B — one command

From the project folder:

```
python3 scripts/follow_edit.py --show
python3 scripts/follow_edit.py add-news "Formula 1" --sport Motorsport
python3 scripts/follow_edit.py remove-news "Formula 1"
python3 scripts/follow_edit.py add-team uefa.champions Arsenal
python3 scripts/follow_edit.py remove-team uefa.champions Arsenal
python3 scripts/follow_edit.py add-competition uefa.europa
python3 scripts/follow_edit.py remove-competition uefa.europa
python3 scripts/follow_edit.py --list-teams uefa.champions
python3 scripts/follow_edit.py --tennis top_n 10
python3 scripts/follow_edit.py --tennis enabled off
```

### Option C — edit the file

Open `personal/data/follow.json` in any text editor. Every list has a comment
explaining it. Save, and the next email uses it.

### The competition ids

Use these with `add-competition` and `add-team`:

| id | Competition |
|---|---|
| `uefa.champions` | UEFA Champions League |
| `uefa.europa` | UEFA Europa League |
| `eng.1` | English Premier League |
| `esp.1` | Spanish LaLiga |
| `ita.1` | Italian Serie A |
| `ger.1` | German Bundesliga |
| `fra.1` | French Ligue 1 |
| `rsa.1` | South African Premiership |
| `usa.1` | Major League Soccer |

More can be added by editing the `LEAGUES` table at the top of
`scripts/follow_research.py`.

---

## 3. Your UEFA question

You said "UEFA i only want specific teams". The competition is followed, but the
team list is **empty on purpose** — you did not name the teams, so none were
invented. While it is empty the email shows every Champions League fixture and
labels the heading "every team (no team filter set)".

To narrow it, add the teams you want:

```
python3 scripts/follow_edit.py add-team uefa.champions Arsenal
python3 scripts/follow_edit.py add-team uefa.champions Barcelona
```

Or pick option 3 from `MANAGE_SPORTS.bat`. Option 8 lists the teams currently in
the competition, if you want the exact spelling.

Team names match loosely, so "Bayern" finds "Bayern München" and "Atletico"
finds "Atlético Madrid". Removing every team puts you back to showing all of
them.

---

## 4. Running it on the laptop instead of waiting for the cloud

You asked whether it could "trigger on laptop to do the work". Here are the
options, cheapest first.

### Option 1 — build it on demand, right now (implemented)

Double-click **`RUN_DIGEST_NOW.bat`**. It runs the same script the cloud job runs
and opens the result in your browser. Takes about 15–20 seconds because it makes
a few web requests. It writes `digest-preview.html` next to the batch file.

This needs no GitHub account, no runner minutes, and nothing installed. It does
not send email — email still comes from the cloud job.

To look further ahead, pass a number of days:

```
RUN_DIGEST_NOW.bat 30
```

### Option 2 — Windows Task Scheduler (not set up; 5 minutes if you want it)

Make the laptop run the digest itself on a schedule, so it arrives without
GitHub at all. Create a task with:

- **Program:** `python`
- **Arguments:** `scripts\personal_digest.py --days 10 --html`
- **Start in:** the project folder
- **Trigger:** daily, whenever you like

To send email as well, add `&& python scripts\send_digest_email.py` after the
first command and set `MAIL_USERNAME`, `MAIL_PASSWORD` and `MAIL_TO` in the
task's environment.

Trade-off: the laptop has to be on and awake at that moment. The cloud job does
not.

### Option 3 — cloud only (what runs today)

GitHub Actions builds and emails it. Nothing needs to be switched on. This is the
only option that works while the laptop is shut.

**Recommendation:** keep the cloud job as the daily email, and use
`RUN_DIGEST_NOW.bat` when you want to see it immediately.

---

## 5. The weekly run

There are now two schedules, both in `.github/workflows/personal-digest.yml`:

| When | What |
|---|---|
| Daily 05:00 SAST | The normal digest, 10 days ahead, 3 days of news |
| Sunday 07:00 SAST | The weekly digest, 14 days ahead, 7 days of news |

The weekly one looks further ahead and reaches back a week for news, so it is a
summary rather than a repeat. Both use the same script and the same follow list.

You can also trigger either by hand: **Actions → personal-digest → Run workflow**,
with an optional day count and a "weekly" checkbox.

---

## 6. Time and cost

You asked to check the time costs on GitHub, in case the runs ran out.

- **Measured locally: 15-20 seconds** for a full run with research on. Most of
  that is waiting on the news feed.
- Each job now has `timeout-minutes: 5`, so a hung source cannot burn the budget.
- Inside the script, `total_budget_seconds` (90 by default) is a tighter cap: once
  it is spent, remaining fetches are skipped and reported as such.
- There are no retries by design. A source that is down is down, and retrying
  costs the sections that would otherwise have worked.
- Both runs are well inside the free minutes for a public repository.

GitHub's own scheduler is best-effort, so a delay of a few minutes is normal. It
is not a precise alarm clock.

---

## 7. Where the information comes from

All sources are free and need no API key.

| What | Source |
|---|---|
| Headlines | Google News RSS, one query per followed topic |
| Fixtures and scores | ESPN's public site API |
| Tennis rankings and results | ESPN's public site API |
| League standings | ESPN's public API, `/apis/v2/sports/soccer/<league>/standings` |
| Local things to do | Google News RSS, Johannesburg edition (`hl=en-ZA&gl=ZA&ceid=ZA:en`) |
| Memory prices | Takealot's public search API |
| Recent run durations | GitHub Actions runs API, read with the workflow's own token |

The standings table is the **only** call on the `/apis/v2/` root. Scoreboards and
rankings stay on `/apis/site/v2/`; the `/apis/site/v2/.../standings` shape returns
404 and is not used. A test asserts the URL the code builds, so that mistake
cannot come back.

Every line in the email carries the publisher or the competition it came from.
No result, name or date is invented. If something cannot be fetched, the email
says so rather than filling the gap.

---

## 8. Running the checks

```
python3 tests/verify_research.py    # the research layer
python3 tests/verify_personal.py    # the pages and the digest
python3 tests/verify_gen13.py       # the eight items added in this generation
python3 tests/verify_site.py        # the whole site
```

`tests/verify_research.py` and `tests/verify_gen13.py` never touch the network —
they feed the code canned payloads, so they are fast and do not fail because a
third party is having a bad day.

The eight items are proven against the recorded payloads under
`tests/fixtures/live_20261103/`, and the results are collected in
`output/evidence/gen13_change_report.json`, which is regenerated by the checks
rather than written by hand.

---

## 9. Tennis, item 5: what "final rankings" was taken to mean

You said, in full:

> "Tennis displayed so badly. Should be grouped by event and show final rankings
> and show where top 5 are, if they didn't compete or out in round of 16 and by
> who. Make it interesting!"

That is four separate asks, and each is delivered as output you can see, not as a
note here.

**"grouped by event"** — the tournament name is a heading for its block. It is not
repeated as a suffix on every match line, in the email or on `sports.html`.

**"show final rankings"** — **DELIVERED**, as a rendered **RANKING** line above
each tour's event blocks: `RANKING - ATP top 5 - current ranking: 1. Jannik
Sinner, 2. Alexander Zverev, ...`. Positions are the source's own `current`
values, in ascending order, never renumbered `1..N`. When the rankings payload
cannot be read the line is replaced by the named note "current ranking could not
be read" — a remembered list is never printed. The list, not this paragraph, is
the evidence: it appears in the text digest, in the HTML email and on
`sports.html`, produced by one shared renderer.

**"show where top 5 are, if they didn't compete or out in round of 16 and by
who"** — every top-5 player is accounted for in every event shown, in one of
three unambiguous states:

- **in** — with the round they have reached, taken from the source's own
  `round.displayName`;
- **out** — with the round they went out in **and** who beat them
  (`out in the Quarterfinal, beaten by <name>`);
- **did not compete** — only when the tournament's draw is demonstrably
  complete. Before that, the honest wording is "no match found in this event
  yet", because a half-published draw looks exactly like a withdrawal and
  claiming a withdrawal that did not happen would be an invented fact.

A short "How the top 5 are doing" summary sits beside the ranking line and says
who is still alive, who is out, and in which round, so a tour can be read in one
glance. Neither the ranking line nor the summary is dropped by the grouping.

**Scores** — a match line carries the source's real score where one is supplied
(from the match notes and each competitor's set scores). A match that has not
been played carries no score at all; nothing is constructed or defaulted to
`0-0`.

**"Make it interesting"** — a tournament in the window with no top-5 player in it
still says so in one line, so the block is never a wall of dashes and never a
silence.

No separate end-of-event standings table is invented. The ranking list plus each
player's per-event status is the whole delivery.

---

## 10. Local, item 6: the two-person dimension

You said:

> "nice massage sale i can take Chloe and i, same with buffets and great events
> coming up in a year or so in my area. Joburg."

The `two_person` key on a local category in `personal/data/follow.json` carries
that intent. Where it is set, the searches for that category run an extra
couples query alongside the normal one, matched items are labelled
"For two / couples", and the label is rendered in both the text digest and the
HTML email. It is a search dimension, not a filter: the solo results are never
suppressed by it.

The default horizon is 3 months, as you asked ("next 3 months"). A category
flagged `annual: true` looks 12 months ahead instead ("great events coming up in
a year or so"). The two horizons are tested against the same item so the
classification cannot drift.

