# The personal pages: `sports` and `good_hubby`

Two extra pages, kept out of the professional navigation, plus a daily email that
reminds the owner what is coming up. Nothing here is linked from the portfolio.

- <https://matthewmbowyer.github.io/UoEOMScDataScience/sports.html>
- <https://matthewmbowyer.github.io/UoEOMScDataScience/good_hubby.html>

## Unlisted is not private — read this first

The owner asked for these to be unlisted, and said he does not mind if anyone
sees them. That is the right expectation to hold, because **these pages are not
private** and cannot be made private on this host:

- The site is served from a **public GitHub repository**. Anyone who guesses or
  is told the path can open the page, and anyone can read the source.
- `robots.txt` disallows each page by name and each page carries
  `noindex, nofollow`, so search engines should not list them. That is
  politeness, not a lock. It does not stop a direct visit, and it does not stop
  an archiver that ignores `robots.txt`.

So: treat these pages as **published but not advertised**. Do not put anything
on them you would be unhappy for a stranger to read. The pages say this in a
banner at the top so nobody forgets.

## Leftover pages still live on the public site

Separate from the two pages above, the **live** site still serves twelve
pre-rebuild scratch pages. They are not in this delivered tree, so deploying the
rebuild will **not** remove them — they have to be deleted from the live repo
explicitly. Measured 2026-10-05, all twelve return HTTP 200:

| Page | What it exposes |
|---|---|
| `Cute.html` | private messages to Chloe ("Do you miss me?…") |
| `grumpgrump.html` | menstrual-cycle guide |
| `burpeeeeeees.html` | burpee challenge with participant names |
| `Mattgoals.html` | personal sleep/training/running stats |
| `2026.html` | personal programme tracker |
| `RobJo.html`, `AMsmash.html`, `Americano.html`, `Team_Americano.html` | scratch pages |
| `index01.html`, `index1.html`, `test.html` | template leftovers |

**Unlisted is not private.** Anyone with the URL can read these; `robots.txt`
does not hide a page from a direct visit, and the repo is public. Removing them
is the only real fix.

To remove them, in the live repo `MatthewMBowyer/UoEOMScDataScience`:

```bash
git rm Cute.html grumpgrump.html burpeeeeeees.html Mattgoals.html 2026.html \
       RobJo.html AMsmash.html Americano.html Team_Americano.html \
       index01.html index1.html test.html
git commit -m "Remove personal scratch pages from the public site"
git push
```

Deleting a file does not unpublish it from any archive that already copied it,
and `git rm` leaves it in history — so if any of it must be truly gone, the
history needs rewriting too. Ask before assuming a delete is enough.

The delivered rebuild does not link to any of these and does not contain them,
so no other change is needed.


### `sports.html` — upcoming sport the owner follows

Sixteen events he listed, each with its dates, series and where to watch. He
said "Dont add any more", so the list is exactly his; the test suite pins the
count at 16 and checks every name against his list, so a stray addition fails
the build.

He has DStv, so each event names the SuperSport section to look in. **No channel
number is given, because none could be verified** — a guessed number would send
him to the wrong channel, which is worse than no number. The page says so and
points at the TV guide instead:

- <https://supersport.com/tv-guide>

**Each event now carries a short description** (2026-10-07): one sentence saying
what the event actually is — the series, the format, why it is worth watching —
so the page reads as a guide rather than a bare list of names.

### The recorded sports preference profile

So a future refresh knows what to look for without guessing, the sports he
follows are recorded **explicitly and machine-readably** in
`personal/data/sports.json` under `preferences`, derived ONLY from the 16 events
he supplied:

| Sport | Events | Series |
|---|---|---|
| Motorsport | 9 | IMSA, Supercars, MotoGP, NASCAR, WEC, WRC |
| Tennis | 2 | ATP Masters 1000 |
| Cycling | 2 | UCI |
| Gymnastics | 1 | FIG |
| Weightlifting | 1 | IWF |
| Padel | 1 | Premier Padel |

Broadcasters recorded: `supersport`, `redbulltv`, `f1tv`. **No sport is added
that he has not shown an interest in** — the profile is a reflection of his list,
not an expansion of it.

### Pruning expired events (deterministic)

Nothing used to prune the calendar, so it would accumulate stale entries. Now
`scripts/build_personal.py` drops any event whose **end date has passed** before
generating the page and the `.ics`. The prune is deterministic and reproducible:

- it is a pure function of (the 16-event list, a reference date), so two runs
  over the same input always produce the same split;
- an event still running **today is kept** (the rule is `end >= as_of`);
- the **source list is never modified** — all 16 events stay in
  `personal/data/sports.json`; only the generated `sports.html` and `sports.ics`
  drop the expired ones;
- the reference date is stored as `pruning.as_of` in `sports.json`
  (currently **2026-10-06**), so a rebuild reproduces the committed page rather
  than drifting each day. A later refresh re-derives it.

**What is pruned as of the delivered build (as_of 2026-10-06):** one event —
`Petit Le Mans` (ended 2026-10-03). The page states this in its own text
("Pruned as already finished before this build: Petit Le Mans."). The next
events to expire are `Shanghai Masters` (2026-10-18) and `UCI Track Cycling World
Championships` (2026-10-18).

### `good_hubby.html` — the reminders page

Dates that matter for Chloe: the three relationship milestones (chatting,
dating, engaged), the anniversaries they generate each year, and the holidays
worth marking. Each milestone shows a live countdown.

**The chatting date was corrected on 2026-10-07.** It used to be *derived* from
"2969 days before 18 December 2024" → **2016-11-01**. Mr Bowyer then stated the
date **directly: 22 March 2017**, which supersedes the derivation. The data file
records both facts and the arithmetic that shows they differ: 2017-03-22 is
**2828** days before 2024-12-18, not 2969. Every day-count, countdown and
anniversary on the page, in `good_hubby.ics` and in the digest is re-derived from
**2017-03-22**; no stale 2016-11-01 value or 2969-day figure survives in any
generated artefact (the test suite greps all three for it).

### Check-in reminders ("checking on each other")

A new, deliberately *event-anchored* reminder type — **not** a fixed daily
schedule, so it does not nag every day. The prompts attach to occasions already
on the page:

- the **1st** and the **22nd** of each month (the 22nd is the day of the month
  the chatting milestone starts on), which lands roughly **weekly-to-fortnightly**;
- plus the three **milestone anniversaries** already listed on the page.

Substance: the prompts are about checking in on each other and naming what each
does well for the other, warm and specific rather than generic. There are four:

1. Name one thing your partner did well this week, and tell them — not just think it.
2. Ask how your partner is really doing, then listen before you answer.
3. Thank your partner for one specific thing they did, rather than a general "thanks".
4. Check in on how your partner is feeling about the week, and name what they do
   well for you.

**Name.** Two options were proposed — **"Check-in"** and **"Us time"** — and the
plainest, **"Check-in"**, was chosen. No invented jargon.

**Nothing is fabricated about the partner or the relationship.** The prompts are
warm but generic; if Mr Bowyer wants them to name specific things (a pet, a
shared joke, a nickname) that is recorded as an OWNER CONFIRMATION point in the
data file (`checkins.unsupported`) and will not be invented. The reminders appear
on the page, in `good_hubby.ics` (a `FREQ=MONTHLY;BYMONTHDAY=1` and
`…=22` recurrence) and in the daily digest.

Two kinds of holiday, handled differently on purpose:

- **Fixed** ones (Christmas, Valentine's Day, the South African public holidays)
  are stored as month/day and repeat every year.
- **Moving** ones (Easter, Mother's Day, Father's Day, Diwali, Chinese New Year)
  are **computed from their rule** for any year, so the page does not rot. Easter
  uses the Gregorian computus; the rest use "nth weekday of a month".

## The reminder email

A static site cannot send email, so the site does not try. Instead a GitHub
Actions workflow runs once a day, builds a short digest, and emails it:

- Workflow: `.github/workflows/personal-digest.yml` — daily at 05:00 SAST.
- Digest: `scripts/personal_digest.py`
- Sending: `scripts/send_digest_email.py`

GitHub Actions is free at this volume, so this costs nothing. **This is the only
reason the workflow directory exists**, and the AC-57 check was narrowed to
allow it: the workflow may not build, bundle or deploy the site, and a test
fails if one ever does.

### Turning the email on (one time, by the owner)

Without this the job still runs and prints the digest into the run log — it just
does not email it, and it does not fail.

0. Put the workflow file on GitHub first. It is **not there yet**: the token used
   to publish the site can write code but not workflow files (GitHub rejects it
   with "without `workflow` scope", and the API route returns 403), so
   `.github/workflows/personal-digest.yml` exists on your PC but not on the
   remote. Repo → Add file → Create new file, name it exactly
   `.github/workflows/personal-digest.yml`, paste the file's contents, commit to
   `main`. Everything the workflow calls is already pushed.
1. Use a mail account that allows SMTP with an **app password**. For Gmail:
   Google Account → Security → 2-Step Verification → App passwords. A normal
   account password will not work.
2. In the repository: Settings → Secrets and variables → Actions → New secret.

   | Secret | Value |
   |---|---|
   | `MAIL_USERNAME` | the sending address, e.g. `you@gmail.com` |
   | `MAIL_PASSWORD` | the app password |
   | `MAIL_TO` | where to send it (may be the same address) |

3. To test it immediately: Actions → `personal-digest` → Run workflow. The button
   only exists once step 0 is done.

To stop the emails, delete the workflow file or disable it in the Actions tab.

### If you would rather not set up email

Nothing breaks. Either read the digest in the Actions run log, or just open the
two pages — `good_hubby.html` already lists everything upcoming, in order, and
the `.ics` files below subscribe into a real calendar.

## The calendar files

`sports.ics` and `good_hubby.ics` can be imported into Google
Calendar, Outlook or Apple Calendar, which gives phone notifications for free
with no email setup at all:

- `sports.ics` — the sixteen events, one entry each.
- `good_hubby.ics` — milestones and holidays. Fixed dates and
  milestones carry a yearly repeat; moving holidays are listed explicitly for
  the years whose dates are actually known.

## Editing them

The pages are **generated**, not hand-written. Edit the data, not the HTML:

| File | Holds |
|---|---|
| `personal/data/sports.json` | the event list, broadcasters, the "no channel number" note |
| `personal/data/good_hubby.json` | milestones, fixed and moving holidays, the timezone label |

Then rebuild and verify:

```bash
python3 scripts/build_personal.py            # regenerate pages and .ics
python3 scripts/build_personal.py --check    # report drift instead of writing
python3 tests/verify_personal.py             # the checks
```

`--check` is what the test suite uses, so a page that has drifted from its data
fails rather than shipping stale.

## Rules this data follows

Two of the project's standing rules apply here with no exceptions:

1. **Every date carries a `source`.** The test suite fails if any holiday or
   milestone is missing one. If a date cannot be verified, it is left out rather
   than guessed. Where the owner states a date directly, that statement wins over
   any earlier derivation (this is what happened to the chatting date).
2. **Nothing is invented.** No channel numbers (unverified), no events beyond the
   sixteen the owner listed, and nothing about the partner or the relationship
   that he has not said — unsupported specifics are recorded as OWNER
   CONFIRMATION points rather than filled in.

## OWNER CONFIRMATION points (this pass)

Open items the owner may want to decide, all recorded rather than guessed:

1. **Check-in prompts are warm but generic.** If you want them to name specific
   things (a pet, a shared joke, a nickname), tell me the words and I will put
   them in. I will not invent details about your partner.
2. **Check-in name.** "Check-in" was chosen as the plainest of two options; say
   the word if you prefer "Us time" or something else.
3. **Channel numbers** for the sports events remain blank because none could be
   verified — supply them and they go in.

## Deploying

These pages ship with the rest of the site. They are excluded from
`sitemap.xml` and disallowed in `robots.txt`, so publishing them does not
advertise them.
