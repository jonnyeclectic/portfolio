# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Jonathan Reyes's personal portfolio site: static HTML/CSS/JS, no build tooling and
no package manager. There is nothing to compile — edit the HTML files directly.

Two directories are developer tooling rather than site content, and neither is
served to visitors: `tests/` and `tools/`.

## Working locally

Open the HTML files directly in a browser, or serve the directory statically to test
relative links and the favicon data-URI, e.g.:

```
python3 -m http.server 8000
```

There is no linter or formatter configured for this repo. Two test suites exist,
each gated by its own GitHub Actions workflow, and both runnable by hand:

```
python3 -m unittest discover -s tests -p 'test_*.py'   # tools/, offline, stdlib only
node tests/visual/visual_check.mjs                     # headless Chrome, see tests/visual/README.md
```

`tests/visual/` checks the pages as rendered. The Python suite covers `tools/`,
plus two page-level guards:

- `tests/test_site_positioning.py` — the claims the site makes about Jonathan's
  *title*. See "Title vs. headline" below.
- `tests/test_site_claims.py` — the claims it makes about his *work*: retired
  wordings that must not return, cross-page consistency, skill chips that outrun
  the record, and the severance-risk scrubbing. See "Claims that are asserted,
  not remembered" below. It reads the resume PDF via `tests/pdftext.py`.

Both guards are mutation-tested, and that is not ceremony. The first version of
the title guard matched raw HTML in one direction inside a 12-character window,
which let five of seven realistic mutations through — including every form with
a tag between the two strings, which is how this site writes every byline it
has. A page-level assertion that has never been made to fail is worth nothing;
break it on purpose before trusting it.

The two workflows overlap only on `**.html`, which both watch. Check which one
your change actually triggers before assuming it is covered:

- `.github/workflows/visual.yml` — `**.html`, `style/**`, `cerebro/assets/**`,
  `tests/visual/**`. Layout sweep plus axe-core WCAG 2.1 A/AA, and it uploads
  scroll-through screenshots for review by eye.
- `.github/workflows/tools.yml` — `tools/**`, `tests/**.py`, `**.html`,
  `images/**`. The Python suite, no dependency install. It shares the `**.html`
  filter with `visual.yml` because both page-level guards read the live pages,
  and it watches `images/**` because `test_site_claims.py` reads the resume PDF.
  The test glob is `tests/**.py` rather than `tests/test_*.py` so that a change
  to the `pdftext.py` helper cannot land untested.

Both `**.html` globs are repo-wide, so a redirect stub or a `mobile/` page does
trigger them. What runs nothing at all is the legacy template assets (`css/`,
`js/`, `2images/`, root `coolclock.js`/`excanvas.js`/`moreskins.js`/
`default.css`). `images/` used to be in that list — a resume regen was gated by
nothing — and no longer is, but the coverage is text-level only: the PDF's
*claims* are asserted, its layout is not.

## Live site vs. legacy cruft

The repo mixes a current, actively-maintained site with leftover files from earlier
template-based redesigns. Knowing which is which matters before editing:

**Live pages** (linked from the site nav, each fully self-contained — inline
`<style>` in the `<head>` and inline `<script>` before `</body>`, no external CSS/JS
files, only a data-URI SVG favicon):
- `index.html` — the single-page portfolio (hero, highlights, experience, skills,
  education, footer). Section nav links (`#work`, `#experience`, etc.) are in-page
  anchors, not separate pages.
- `resume.html` — resume page, same design system.
- `contact.html` — contact page (mailto/social links, no form backend).

All three share one hand-rolled design system defined inline in each file's
`:root` CSS variables (`--bg`, `--amber`, `--grad`, etc.) — referred to in commit
history as the "Aurora" neon-tech/living-glass reskin. If you change the palette or
a shared component's markup/CSS in one page, replicate the same edit in the other
two; there is no shared stylesheet to edit once.

- `experience.html` (root) **no longer exists.** It was once a standalone landing
  page for *boost* (Jonathan's separate open-source AI-coding-skills package
  manager) in the Aurora design system, but it was deleted when `index.html`'s nav
  switched to linking the live boost site directly
  (`https://jonnyeclectic.github.io/boost/`). The only `experience.html` left is
  `mobile/experience.html`, which is legacy template cruft (see below) — not a live
  page. If a boost landing page is ever wanted again it would have to be recreated.

**Legacy/orphaned, safe to ignore unless specifically asked to clean up:**
- `2index.html`, `m.index.html`, `portfolio.html`, `samplepage.html`, `about.html` —
  meta-refresh redirect stubs (`<meta http-equiv="refresh" ... url=index.html>`,
  `robots noindex`) pointing at `index.html`, left over from a prior template.
- `mobile/` — an entire parallel copy of an old W3Layouts jQuery template
  (its own `css/`, `js/`, `2images/`, HTML pages). Not linked from any live page.
- Root-level `css/`, `js/`, `2images/`, plus `coolclock.js`, `excanvas.js`,
  `moreskins.js`, `default.css` — old template assets (Bootstrap, jQuery,
  mixitup, swipebox, modernizr, responsiveslides) consumed only by the legacy
  stub/mobile pages above, not by the live Aurora pages.
- `css/css/`, `js/js/`, `2images/images/` — literal duplicate copies of their
  parent directory's files, apparent leftovers from an old template zip
  extraction. Don't edit these thinking they're the real source.

When asked to update site content or styling, assume the request is about
`index.html`, `resume.html`, or `contact.html` unless told otherwise.

## Content conventions

- Don't state specific proprietary metrics from employer work (e.g. exact
  request/throughput numbers, transaction volumes) — history shows these were
  deliberately generalized (`10,000+ requests/hour` → "a high-throughput...
  platform", `10K Loan apps / hour orchestrated` → "Millions of events processed
  monthly") after being flagged as proprietary. Prefer qualitative framing
  ("high-throughput", "at scale") over precise figures for current-employer work.
- Recent history also shows a deliberate copy-tone pass ("mature copy tone and fix
  grammar/formatting") — keep new copy consistent with that tone rather than
  reintroducing casual phrasing.
- Ratios about employer work are proprietary metrics too. "A fifth of submissions
  arrived as phone-camera photos" states an internal input mix; "a significant
  share" makes the identical point and discloses nothing. `test_site_claims.py`
  checks for the shape, not just that one sentence.

### Claims that are asserted, not remembered

`tests/test_site_claims.py` pins four things that a reasonable-looking edit has
already broken once each. Read it before rewording anything factual.

- **The document-intelligence rebuild was driven by input format.** Image
  submissions defeated OCR. It was *not* driven by a data-classification review
  — that was a separate problem with a different consequence (file truncation
  and temporary manual review). Beyond being the wrong cause, the retired
  phrasing had a named bank employee publicly describing what a classification
  review found inside a production system he owns. Keep the two accomplishments
  in separate sentences; welding them with a semicolon is how they merged.
- **`index.html` and `resume.html` must tell the same story.** They are one
  click apart and a reader opens both. When they disagreed about why the
  pipeline was rebuilt, whichever one a reader believed, the other looked
  written to impress — strictly worse than a single wrong claim.
- **A bare chip in a skills table reads as "I ship this."** LangChain was an
  internal hackathon prototype and never shipped; Kubernetes is OpenShift at IBM
  in 2017–2019, while the current platform runs on ECS. Neither may stand
  unqualified. The nuance belongs in the `contact.html` FAQ, which draws the
  distinction properly — and that FAQ is also where the *under*-claiming lives,
  so check it against the boost source rather than trusting it.
- **No public availability banner.** A "looking for roles" line, indexed, next
  to a named employer and a component-level description of its production
  platform, is the one item here whose cost is not measured in interviews. The
  contact page's role spec says the same thing to someone who already chose to
  land there.

**The resume PDF lags the pages** and it is the artifact that gets forwarded.
It is a Google Docs export, so correcting it means editing the source document
and re-exporting — it cannot be patched from this repo. `KNOWN_PDF_LAG` in
`test_site_claims.py` pins exactly which retired claims it still carries; the
test fails both if a new one appears *and* once the PDF is regenerated, which
is the prompt to empty the set and delete the test.

### Title vs. headline

Two near-identical strings on this site mean different things, and conflating them
is the easiest mistake to make here:

- **"AI Lead Software Engineer"** is the *headline* — how Jonathan positions
  himself. It belongs in the hero badge, the footer byline on every page, the
  cerebro project byline, and meta descriptions.
- **"Lead Software Engineer"**, plain, is the *employer job title* — what Capital
  One actually calls the role. It belongs in the experience-timeline `<h4>` on
  `index.html` and `resume.html`, and nowhere else.

The resume PDF keeps them apart the same way: its header reads "AI LEAD SOFTWARE
ENGINEER" while its experience entry reads "Lead Software Engineer | CAPITAL ONE".
Prefixing the role heading with "AI", or writing "AI Lead Software Engineer ·
Capital One", turns a self-description into a claim about what an employer
conferred — on a page recruiters verify. A site-wide find-and-replace does exactly
that and looks perfectly reasonable in a diff, which is why
`tests/test_site_positioning.py` asserts both halves.

The five redirect stubs still carry the old title in `<title>`. They are
`noindex` + meta-refresh + canonical, so it reaches neither reader nor crawler;
they are deliberately out of scope, and the test records that.
