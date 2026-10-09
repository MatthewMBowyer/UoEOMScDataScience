# Running the portfolio preview

Everything below is the exact sequence that was actually run to build, serve and
inspect the delivered site. The delivered site is plain static HTML/CSS/JS — no
build step, no bundler and no package manager are involved, so "running" it means
serving the directory over HTTP and opening a page.

The site must be **served over HTTP**, not opened from the file system. Each
academic page fetches the shared `footer.html` fragment at runtime, and the
`file://` scheme blocks that fetch. Opening `index.html` by double-clicking will
render the page without the shared navigation and footer.

## 1. Serve the preview

### On your own Windows PC — double-click this

Double-click **`START_PREVIEW.bat`** in this folder (not `index.html`, and not a
`.ps1` — Windows opens PowerShell scripts in a text editor rather than running
them). It starts a local web server on port 8756 and opens your browser at the
site. Nothing is installed and nothing leaves your PC. Close the console window
(or press `Ctrl+C` in it) to stop the server.

**Every page, listed: see [`PAGES.md`](../PAGES.md).** It is generated from the
delivered tree by `scripts/gen_page_index.py`, so it always matches what is
actually there. Once the preview is running, any page in that list opens by
adding its file name to the address in the browser bar.

Do this on your own machine. The server binds to `127.0.0.1` on whatever machine
it runs on, so the `http://localhost:8756/...` URL it prints only works on that
machine — it is not a public link and it will not open from anywhere else.

If Python 3 is not installed, the `.bat` says so and opens `index.html`
directly as a fallback; that still renders the pages, but the shared navigation
and footer need the server. Install Python 3 from
<https://www.python.org/downloads/> and double-click `START_PREVIEW.bat` again
for the full site.

### The same thing from a shell

The `.bat` is the double-click path; this is what it runs. Use whichever suits
you, and pick your own port if 8756 is taken:

```bash
cd projects/eportfolio_rebuild
./scripts/serve_preview.sh          # defaults to port 8756
./scripts/serve_preview.sh 8080     # or pick your own port
```

The script prints the URL and serves the directory with Python's built-in HTTP
server bound to localhost:

```
Serving /.../projects/eportfolio_rebuild
Open http://localhost:8756/index.html  (Ctrl+C to stop)
```

Equivalent command if you prefer not to use the script:

```bash
cd projects/eportfolio_rebuild
python3 -m http.server 8756 --bind 127.0.0.1
```

Then open <http://localhost:8756/index.html> on the machine running the server
and click through
Home → About → Skills & Capabilities → Projects & Modules → Evidence → CV →
Contact.
Every page links the same nine-item navigation, so the whole site is reachable
from that first page. Press `Ctrl+C` to stop the server.

## 2. View the CV

The CV is a normal part of the site, so the preview above covers it: open
<http://localhost:8756/cv.html>, or click **CV** in the navigation, or click
**Download CV** in the header, footer or landing-page hero. Download CV
downloads `assets/cv/Matthew-Bowyer-CV.pdf`, a real two-page PDF. If your
browser downloads it rather than displaying it, open the downloaded file.

## 3. Verify the served site

With the preview already running on port 8756:

```bash
cd projects/eportfolio_rebuild
python3 tests/verify_site.py
```

This is the deterministic harness. It crawls the delivered HTML for links and
images, checks navigation consistency across every page, then probes the served
site over HTTP — every delivered page and every referenced asset is requested and
its status code recorded. It writes `output/evidence/verification_summary.json`
and exits non-zero if any check fails. It reads the port from `EPO_PORT` if you
served on a different one:

```bash
EPO_PORT=8080 python3 tests/verify_site.py
```

Add `--self-test` to also prove the mobile-menu gate is fallible. It mutates the
open-mobile-menu report in memory with each defect the gate names — a transparent
panel, white-on-white links, an empty probe, a stale report, a page left
unmeasured, an unlabelled toggle, a blank capture, a light open-menu capture —
and requires the matching row to fail and no other row to break. It refuses to
pass if the real report is not already green, so it cannot be satisfied
vacuously:

```bash
python3 tests/verify_site.py --self-test
```

`tests/verify_site.py` also imports and runs `tests/verify_gen3.py`, which holds
the improvement-pass checks: CV validity and the Download CV link on every page,
Open Graph / Twitter metadata, `robots.txt` and `sitemap.xml`, impact-led
content, recruiter CTAs, the hero first-viewport geometry, uniform image
treatment, the design-quality report, static discipline (no new external host or
build step) and the before/after non-regression report. Those checks write their
own reports under `output/evidence/`.

## 4. Capture browser evidence (screenshots and console errors)

```bash
cd projects/eportfolio_rebuild
python3 tests/browser_evidence.py
```

This drives headless Chromium over the Chrome DevTools Protocol against the
served site. It probes every delivered page for console errors and captures
desktop (1440×900) and mobile (390×844) screenshots of the home page, the
Projects/Modules index, a representative module page, the Contact page and the CV
page. Each capture is content-verified — a blank or single-colour image fails.
It also clicks the mobile menu toggle and confirms the panel actually opens, and
it measures the hero's first-viewport geometry and the rendered treatment of
every image for the improvement-pass reports.

It additionally opens the mobile menu on **every** delivered page at 390×844 and
measures each link's painted pixels there (the panel is the only menu below
980px), and it captures the opened menu on the home page and a module page so the
fixed state is visible as well as numeric. Those captures are content-verified.

It writes `output/evidence/console_report.json`,
`output/evidence/screenshot_manifest.json`,
`output/evidence/rendered_dom_report.json`,
`output/evidence/mobile_nav_report.json`,
`output/evidence/hero_geometry_report.json`,
`output/evidence/image_treatment_report.json`,
`output/evidence/contrast_report.json` and the PNGs under
`output/evidence/screenshots/`.

The contrast report is produced by `tests/contrast_probe.js`, which this script
evaluates in each rendered page. It measures the WCAG ratio of every text element
against the background actually painted behind it — the ancestor background chain
composited root-first, plus the `::after`/`::before` overlays that sit above the
text — so text on the dark hero band is measured against that band rather than
against the page canvas. `python3 tests/verify_site.py check_contrast()` fails if
any pair falls below AA, and also recomputes the design-token ratios
deterministically so the criterion can fail without a browser.

Override the site port with `EPO_PORT` and the DevTools port with `EPO_CDP_PORT`
if either clashes.

## 5. Rebuild from the immutable inputs (optional)

The delivered pages are already in this directory. The authoring scripts exist
only to show how they were produced from the canonical inputs; the site does not
need them at runtime. Do not run these against a modified `inputs/` — `inputs/`
is the frozen canonical copy.

```bash
cd projects/eportfolio_rebuild
python3 scripts/build_site.py           # author the pages from site_content + inputs
python3 scripts/build_evidence.py       # regenerate the evidence reports
python3 tests/verify_site.py            # re-verify
```

## 6. Regenerate the CV PDF and the share image (optional, offline)

These two files are committed in the delivered tree, so you never have to run
anything to view them. They are produced by one-off offline authoring scripts, so
they can be regenerated without adding a build step to the delivered site — the
site only serves the files, it never runs these:

```bash
cd projects/eportfolio_rebuild
python3 scripts/make_cv_pdf.py          # -> assets/cv/Matthew-Bowyer-CV.pdf
python3 scripts/make_social_card.py     # -> images/social-card.png (1200x630)
```

`make_cv_pdf.py` reads its content from `scripts/site_content.py` — the same CV
tokens `cv.html` is built from — so the page and the PDF cannot drift apart. Both
scripts need their authoring libraries (`reportlab` for the PDF, `Pillow` for the
image); neither is needed to serve the site. After regenerating, re-run
`python3 tests/verify_site.py`, which re-checks the PDF's validity, page count and
text and the image's decodability and size.

## 7. What changed in this improvement pass (and what did not)

This pass added the recruiter-facing layer. All of it is plain static files, so
running the site is unchanged — serve the folder and open `index.html`. The
counts below are measured, not remembered: `output/evidence/pass_file_diff.json`
is a sha256 tree diff of the pre-pass tree (`work/pre_gen3_backup`) against the
delivered tree, and the harness fails if these figures drift.

Features added: a dedicated CV page (`cv.html`) with a real downloadable CV PDF
(`assets/cv/Matthew-Bowyer-CV.pdf`), a **Download CV** call to action in the
header, footer and landing-page hero, Open Graph / Twitter card metadata on every
page with a same-origin 1200×630 share image (`images/social-card.png`),
`robots.txt` and `sitemap.xml` at the site root, and impact-led content on the
landing page and the experience surfaces.

Files added (12) to the delivered tree: `cv.html`,
`assets/cv/Matthew-Bowyer-CV.pdf`, `images/social-card.png`, `robots.txt`,
`sitemap.xml`, `scripts/make_cv_pdf.py`, `scripts/make_social_card.py`,
`tests/verify_gen3.py`, `tests/launcher_check.py`, `tests/contrast_probe.js`,
`tests/mobile_nav_probe.js`, `START_PREVIEW.bat`. This pass also adds sixteen
reports under `output/evidence/` and two CV screenshots, which the count excludes
because the harness rewrites that directory on every run.

Files changed (39), the substantive ones being every delivered page (re-emitted
with the nine-item navigation, the recruiter CTA row, the Open Graph / Twitter
metadata and the impact-led copy), `footer.html`, `assets/css/portfolio.css`
(extended with the CV, impact and CTA components), the authoring scripts
(`build_site.py`, `site_content.py`, `pages_extra.py`, `pages_evidence.py`), the
test harnesses that verify them, and this documentation.

Before / after quality improvements: delivered pages 26 → 27; pages with Open
Graph metadata 0 → 27; pages with a Twitter/X card 0 → 27; pages offering
Download CV 0 → 27; landing-page hero calls to action 3 → 4; `robots.txt` and
`sitemap.xml` absent → present; a real downloadable CV absent → a two-page PDF;
the design-system stylesheet 26,644 → 44,015 bytes. The non-regression verdict is
`NON_REGRESSION_HOLDS` — no page or link that worked before stopped working, and
the only navigation change is the documented addition of `CV` → `cv.html`.

Not done in this pass (with reasons — the full list is in
`docs/DELIVERY_SUMMARY.md`): no employer name or date range is published on the
CV because the supplied material names neither and inventing them is forbidden
(recorded as `HUMAN_DEPENDENT`); no unverified claim from the owner's private
capability list is published as fact, only as OWNER CONFIRMATION points; no new
framework, bundler, package manager or build step was introduced; no new
third-party host is referenced; no backend or form submission handler was added;
and nothing was pushed to any repository.

The one thing the owner does — double-click `START_PREVIEW.bat` — has its own
deterministic check, because a green site harness does not prove the launch path
works:

```bash
cd projects/eportfolio_rebuild
python3 tests/launcher_check.py --self-test
```

It asserts over the artifact the owner actually touches (the `.bat`) and the
documents that instruct them, and it runs two negative controls on a temp copy
(remove the launcher; restore a "double-click the .ps1" instruction) to prove it
can fail. `tests/verify_site.py` folds its verdict into AC-58.

Two defects raised by the first independent review were repaired after that pass,
and both now have a check that can fail:

- Contrast (AC-24). The muted text colour was `#667585`, which rendered
  normal-size text at 4.36:1 on `#f4f6f9` and 4.10:1 on `#eceff4`, under WCAG AA.
  It is now `#556274` (5.73:1 and 5.38:1). `tests/verify_site.py check_contrast()`
  recomputes every design-token ratio deterministically, and
  `tests/browser_evidence.py` loads `tests/contrast_probe.js` to measure the
  composited pixels of every text element on every page
  (`output/evidence/contrast_report.json`, worst 5.73:1, 0 failures).
- Oversized images (AC-26). `scripts/optimise_images.py` used a 1 MiB threshold
  although the requirement says "over 1 MB", leaving two 1879×1879 covers at
  ~1.02 MB each. The threshold is now 1,000,000 bytes and both are resized to
  1100×1100 (`output/evidence/image_optimisation.csv`: 1,025,628 → 303,612 and
  1,036,437 → 293,433 bytes). `tests/verify_site.py check_image_weight()` fails
  if a referenced image exceeds 1 MB or has no matching report row.
- The mobile menu (AC-18). Below 980px `#nav` is hidden and the template
  off-canvas `#navPanel` is the only menu. Stripping the panel's dead template
  background left it transparent while `main.css` still painted `.depth-0` links
  `#fff`, so the opened panel was white on `#f4f6f9` at 1.08:1 on every page —
  visible to the DOM, invisible to a reader, and missed because the contrast
  probe skips the off-canvas panel and the nav check only asked whether it
  opened. `tests/mobile_nav_probe.js` now opens the panel and measures every
  link's painted pixels; the panel is painted on `#10161d` (worst link 15.45:1),
  the hamburger is repainted on the accent at 7.88:1 with a 44px target, and the
  toggle is named (`Open navigation menu`, with `aria-expanded`) because the
  template injects it as an empty `<a>`. 189 links across all 27 pages at
  390×844, zero below WCAG AA (`output/evidence/mobile_nav_report.json`).
  Removing the fix fails the check 189 of 189 at 1.08:1.

## 8. The amendment pass (professional history, VLM demo, ambient facts bot)

### View the new surfaces

The amendment added two new pages, both in the shared navigation and neither
needing a build step:

- `experience.html` — the professional-history / roles surface.
- `thesis-demo.html` — the offline VLM thesis demonstration. It loads and stays
  interactive with **all network access blocked**; it needs no key or backend.

`chat.html` was **removed** by the 2026-10-01 governed change that scrapped the
chatbot for the ambient facts bot; the shared navigation is now nine items. The
bot appears on every page automatically — there is nothing to enable and no key
to enter.

### The ambient facts bot (build time vs run time)

The bot is **Python at build time, JavaScript at run time**. Python cannot
run in a browser and GitHub Pages serve no server-side code, so the answering
engine must be JS — this split is a hard constraint.

Regenerate the knowledge base offline on your machine (no network needed after
the first mining; the CV and the repos cache are in the tree):

```bash
cd projects/eportfolio_rebuild
python3 scripts/build_knowledge.py                   # rebuild assets/js/knowledge-base.js,
                                                     # assets/data/facts.json,
                                                     # docs/KNOWLEDGE_BUILD_REPORT.md
python3 scripts/build_knowledge.py --refresh-repos   # re-mine the GitHub repos first
```

Run time is entirely local: `assets/js/guide-bot.js` reads the per-page fact
pool from `assets/data/facts.json`, composing any experience-bearing fact at
render time through `assets/js/experience.js`. There is no chat input, no key
and no network request.

### Verify the amendment

```bash
cd projects/eportfolio_rebuild
python3 tests/test_guide_bot.py                    # AC-95..AC-108 (ambient facts bot: pools, specificity, cadence, a11y, offline, silence)
python3 tests/test_knowledge_generator.py          # AC-82..AC-87, AC-92, AC-95, AC-96, AC-108 (generator: clean, deterministic, falsified)
python3 tests/test_vlm_demo.py                     # AC-65, AC-66 (offline, honest label, interactive)
python3 tests/test_experience_clock.py             # AC-63, AC-64 (frozen-clock experience)
python3 tests/verify_amendment_remaining.py        # AC-74, AC-76, AC-77, AC-78, AC-79
python3 scripts/gen_featured_repos.py              # AC-74 featured-repo provenance
python3 scripts/gen_spacing_audit.py               # AC-75 spacing/typography audit
```

The ambient facts bot and its demo guide are described in `docs/GUIDE_BOT_DEMO.md`.

The two unlisted personal pages (`sports.html`, `good_hubby.html`) sit at the
site root but are NOT delivered site pages: they carry no ambient bot and no
shared footer, and `scripts/build_knowledge.py` and `tests/verify_site.py` both
exclude them from the delivered-page set (`PERSONAL_PAGES`). If a page is added
or removed at the root, update `PERSONAL_PAGES`/`NON_DELIVERED_PAGES` in
`scripts/build_knowledge.py` alongside `tests/verify_site.py` or the generator's
AC-96 completeness guard will abort the build.

### Repair pass (2026-10-06)

Two reviewer defects were fixed and the full suite re-run green:

```bash
python3 scripts/build_knowledge.py            # now runs clean on the delivered tree
python3 tests/test_knowledge_generator.py     # AC-82/AC-85/AC-96/AC-133
python3 tests/test_guide_bot.py               # AC-110/INV-46 desktop placement now deterministic
```

`scripts/build_knowledge.py` excludes the two root personal pages from its page
enumeration (mirroring `tests/verify_site.py`), and `assets/js/guide-bot.js`
`chooseSpot()` applies a hard reading-column clearance filter on desktop so the
randomised settled spot can never land on the text being read. Details and
measurements are in `docs/DELIVERY_SUMMARY.md` (Repair pass, 2026-10-06).

### Regenerate the generated amendment artefacts (optional, offline)

The delivered site never runs these; they are one-off authoring/measurement
steps, exactly like the CV and share-image scripts above:

```bash
python3 scripts/gen_thesis_demo.py     # regenerates thesis-demo.html + its data
python3 scripts/gen_sitemap.py         # regenerates sitemap.xml (all delivered pages)
python3 scripts/apply_nav.py           # re-applies the shared nine-item navigation
```

### Hero first-screen geometry (AC-01 / AC-55)

The landing-page hero is MEASURED in real rendered DOM, not asserted. Serve the
site and run the browser evidence script, then the harness, which now gates the
measurement:

```bash
python3 -m http.server 8756 --bind 127.0.0.1 &    # or: ./scripts/serve_preview.sh 8756
EPO_PORT=8756 python3 tests/browser_evidence.py   # writes output/evidence/hero_geometry_report.json
EPO_PORT=8756 python3 tests/verify_site.py --self-test
```

`verify_site.py` reads `output/evidence/hero_geometry_report.json` and requires
the name, role, one-sentence positioning, primary specialisms and all four
calls to action to sit inside the first viewport at BOTH 1440x900 desktop and
390x844 mobile. `--self-test` mutates the report in memory to prove the gate
fails for each defect it names (below-the-fold chips/CTAs, a bare-name headline,
a stale report, a missing viewport, four-anchor shortfall) and for nothing else.

## 9. The daily email digest — when to expect it

You asked when the next email arrives. Short answer: **not yet.** The site is
pushed, but two things are still missing, and no email can be sent until both
are done: the workflow file has to reach GitHub, and you have to add three
secrets.

The workflow file is **not on GitHub yet**. The token used to push the site can
write code but not workflow files — GitHub refuses it with "refusing to allow a
Personal Access Token to create or update workflow
`.github/workflows/personal-digest.yml` without `workflow` scope", and the API
route fails the same way with 403. So the site is live and the reminder email is
dormant. Add the file by hand (step 1 below); everything it needs
(`scripts/personal_digest.py`, `scripts/send_digest_email.py`,
`personal/data/*.json`) is already on GitHub.

Once both are done:

1. The workflow `.github/workflows/personal-digest.yml` runs on GitHub's own
   scheduler, not on your PC. Your machine does not need to be on.
2. It runs daily at **05:00 SAST** (03:00 UTC). GitHub's scheduler is
   best-effort, so a few minutes' delay — occasionally more — is normal.
3. It reads `personal/data/*.json`, builds the digest with
   `scripts/personal_digest.py`, and emails it directly via SMTP.

**Step 1 — put the workflow file on GitHub.** The file already exists on your
machine at:

```
C:\Users\matthewbo\Matthew B Python Projects\Masters\openhands-projects\conference-program\projects\eportfolio_rebuild\.github\workflows\personal-digest.yml
```

1. Open the repo → **Add file** → **Create new file**.
2. Name it exactly `.github/workflows/personal-digest.yml` (typing the slashes
   creates the folders).
3. Paste the whole contents of that file.
4. **Commit changes**, straight to `main`.

**Step 2 — add the three secrets.** Settings → Secrets and variables → Actions
→ **New secret** (one at a time; names are case-sensitive, no quotes):

| Name | Value |
|---|---|
| `MAIL_USERNAME` | the sending address, e.g. `you@gmail.com` |
| `MAIL_PASSWORD` | the **app password**, not your normal password |
| `MAIL_TO` | where to send it (may be the same address) |

For Gmail, `MAIL_PASSWORD` must be an App password: 2-Step Verification on first
(Google Account → Security → 2-Step Verification), then Google Account →
Security → App passwords. A normal account password is rejected. Sending is over
`smtp.gmail.com:465` with implicit SSL, which is what this setup expects.

Without those three the job still runs and prints the digest into the run log,
so it degrades to "read the log" instead of failing silently — but no email is
sent. Verified behaviour: no secrets → exit 0 with "Email is not configured";
secrets present but wrong → exit 1 with the SMTP error, which is the red tick you
want to see while debugging.

**Step 3 — send one now.** Repo → **Actions** → **personal-digest** → **Run
workflow**. That button only appears once step 1 is done. To check it worked,
look for a green tick; a red tick means it failed and the log names the reason.
To stop the emails, disable that workflow.

## Requirements

- Python 3 (standard library is enough for the server and the harness).
- `lxml` for the harness HTML parsing, and `Pillow` plus `websocket-client` for
  the browser evidence script. Headless Chromium (`chromium`) is required only
  for the screenshot/console step.
- `reportlab` only if you choose to regenerate the CV PDF, and `Pillow` only if
  you choose to regenerate the share image. The delivered site needs neither.
- On Windows, just double-click `START_PREVIEW.bat`. From a shell, use
  `scripts/serve_preview.sh` or `python3 -m http.server`.
