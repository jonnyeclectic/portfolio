# Visual checks

Three headless-Chrome sweeps over the live pages. The site itself still has no
build step — this is developer tooling that reads the same static files a
visitor gets, not a pipeline that produces them.

```
cd tests/visual && npm install     # once
node tests/visual/visual_check.mjs # layout invariants + full-page screenshots
node tests/visual/a11y_check.mjs   # axe-core, WCAG 2.1 A + AA
node tests/visual/shots.mjs        # reviewable viewport screenshots
```

All three run from the repo root against `file://` URLs in the working tree, so
a branch's own HTML and CSS are what get checked. Nothing is deployed and
nothing listens on a port.

`pages.mjs` holds the page list, the breakpoints and the shared launcher — edit
the list there and all three sweeps follow.

## What each one is for

**`visual_check.mjs`** asserts things that are never deliberately true: the page
scrolls sideways, the stylesheet did not load, there is not exactly one `<h1>`,
the skip link points at an id that does not exist. When it reports horizontal
overflow it also names the widest element, because "1064px of overflow" on its
own is not actionable.

It is deliberately *not* a pixel-diff. Pixel diffing a hand-written site fails
on every intentional change, and a gate that fails on every change is one people
learn to re-baseline without looking.

**`a11y_check.mjs`** covers the WCAG rules that only exist once the page is laid
out: contrast as rendered (including text over gradients and over hover
surfaces), ARIA validity against the computed tree, landmark structure. It
refuses to report violations at all if the page turns out to be unstyled —
otherwise a stylesheet that failed to load produces a dozen confident, specific,
entirely fictional contrast failures.

**`shots.mjs`** writes viewport-sized captures at 1280 (fold, 40% down, and two
Tab presses in to show the focus ring). `visual_check.mjs`'s full-page captures
are the right thing for a gate but shrink a long page to a thumbnail where
nothing is legible.

Output goes to `tests/visual/out/` and `tests/visual/shots/`, both gitignored.

## Troubleshooting

**"The browser is already running for /tmp/…"** — usually not true. Look further
up the output for:

```
ERROR:chrome/browser/process_singleton_posix.cc] Failed to create socket directory.
```

Chrome puts a ProcessSingleton *socket* in a temp directory at startup and
aborts if it cannot. A sandbox that blocks binding sockets blocks that too, and
puppeteer reports the abort as "already running". Neither a different
`userDataDir` nor `--no-sandbox` helps, because nothing is actually running.
Run outside the sandbox, or use `chrome-headless-shell`, which has no
ProcessSingleton:

```
npx @puppeteer/browsers install chrome-headless-shell@stable --path ~/.cache/puppeteer
PORTFOLIO_CHROME_BIN=~/.cache/puppeteer/chrome-headless-shell-*/chrome-headless-shell node tests/visual/visual_check.mjs
```

**"no Chrome binary found"** — set `PORTFOLIO_CHROME_BIN` to the executable
inside the app bundle, not the bundle itself:
`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.

**Every page reports "unstyled (--bg unresolved)"** — the pages link
`style/portfolio.css` relatively, which over `file://` only resolves because of
`--allow-file-access-from-files`. If that flag stops taking effect, this is what
it looks like.
