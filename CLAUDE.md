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
plus one page-level guard: `tests/test_site_positioning.py` asserts the claims the
site makes about Jonathan's title — see "Title vs. headline" below.

The two workflows overlap only on `**.html`, which both now watch. Check which one
your change actually triggers before assuming it is covered:

- `.github/workflows/visual.yml` — `**.html`, `style/**`, `cerebro/assets/**`,
  `tests/visual/**`. Layout sweep plus axe-core WCAG 2.1 A/AA, and it uploads
  scroll-through screenshots for review by eye.
- `.github/workflows/tools.yml` — `tools/**`, `tests/test_*.py`, `**.html`. The
  Python suite, no dependency install. It shares the `**.html` filter with
  `visual.yml` because `test_site_positioning.py` reads the live pages.

Both `**.html` globs are repo-wide, so a redirect stub or a `mobile/` page does
trigger them. What runs nothing at all is everything that is not HTML and not
listed above: the legacy template assets (`css/`, `js/`, `2images/`, root
`coolclock.js`/`excanvas.js`/`moreskins.js`/`default.css`), and `images/` —
including `images/Jonathan Reyes Resume.pdf`, so a resume regen is gated by
nothing and its consequences for the pages have to be checked by hand.

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
