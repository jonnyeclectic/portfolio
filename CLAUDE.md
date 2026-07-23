# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Jonathan Reyes's personal portfolio site: static HTML/CSS/JS, no build tooling, no
package manager, no test suite. There is nothing to `npm install` or compile — edit
the HTML files directly.

## Working locally

Open the HTML files directly in a browser, or serve the directory statically to test
relative links and the favicon data-URI, e.g.:

```
python3 -m http.server 8000
```

There is no linter, formatter, or test command configured for this repo.

## Live site vs. legacy cruft

The repo mixes a current, actively-maintained site with leftover files from earlier
template-based redesigns. Knowing which is which matters before editing:

**Live pages** (linked from the site nav, each fully self-contained — inline
`<style>` in the `<head>` and inline `<script>` before `</body>`, no external CSS/JS
files, only a data-URI SVG favicon):
- `index.html` — the single-page portfolio (hero, highlights, experience, skills,
  education, footer). Section nav links (`#work`, `#experience`, etc.) are in-page
  anchors, not separate pages.
- `resume.html` — résumé page, same design system.
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
