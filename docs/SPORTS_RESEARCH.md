# Following sport: how the research layer works

You asked for the daily message to do more research, so it now reports on what
you follow rather than only the fixed 16-event list. This page explains what it
does, how to change what it follows, and how to run it yourself.

Nothing here is published to the internet. The pages are local-only and the
email comes from your own GitHub Actions job.

---

## 1. What the daily email now contains

The digest still opens with the 16 events, your special days and the check-in
line. Below that come three new sections:

**What you follow** — recent headlines for each topic you follow. Each line names
the publisher, and each headline links to the article.

**Fixtures** — the matches in each competition you follow. If you have set a team
filter, only your teams' matches appear. If you have not, every fixture in that
competition appears and the heading says so.

**Tennis** — the current top 5 of the ATP and WTA tours, plus their results and
their upcoming matches. Only matches involving a top-5 player are listed, and
they are listed for whichever tournament those players are in. That is what you
asked for: "only give me results of top 5" and "make sure we follow any tennis
the top 5 are in".

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

Every line in the email carries the publisher or the competition it came from.
No result, name or date is invented. If something cannot be fetched, the email
says so rather than filling the gap.

---

## 8. Running the checks

```
python3 tests/verify_research.py    # the research layer
python3 tests/verify_personal.py    # the pages and the digest
python3 tests/verify_site.py        # the whole site
```

`tests/verify_research.py` never touches the network — it feeds the code canned
payloads, so it is fast and does not fail because a third party is having a bad
day.
