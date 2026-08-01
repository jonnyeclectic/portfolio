// The live pages, in one place, so the three sweeps cannot drift apart about
// what "the site" is.
//
// Deliberately NOT included: the meta-refresh redirect stubs (2index, m.index,
// portfolio, samplepage, about) and everything under mobile/ — see CLAUDE.md.
// Those are template cruft that no live page links to; auditing them would
// produce failures nobody should act on.
export const PAGES = [
  "index.html",
  "resume.html",
  "contact.html",
  "docs/index.html",
  "docs/pgvector-guide.html",
  "cerebro/index.html",
  "cerebro/data-and-universe.html",
  "cerebro/backtest-gate1.html",
  "cerebro/validation-gate2.html",
  "cerebro/paper-gate3.html",
  "cerebro/live-gate4.html",
  "cerebro/risk-layer.html",
];

// 375 is the narrowest phone worth supporting; 1680 is where a max-width
// container stops growing and the gutters take over. 768 and 1024 straddle the
// tablet breakpoints, 1280 is the modal laptop.
export const WIDTHS = [375, 768, 1024, 1280, 1680];

// Chrome, in the order worth trying. Set PORTFOLIO_CHROME_BIN to override.
export const CANDIDATE_BINS = [
  process.env.PORTFOLIO_CHROME_BIN,
  "/usr/bin/google-chrome",
  "/usr/bin/chromium-browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].filter(Boolean);

/**
 * Launch headless Chrome the same way for all three sweeps.
 *
 * Two things here are load-bearing and easy to lose:
 *
 * `pipe: true` — puppeteer talks to Chrome over stdio instead of a DevTools
 * websocket, so nothing has to listen on a port. That is what lets this run
 * where `python3 -m http.server` cannot.
 *
 * An explicit `userDataDir` inside the repo. Chrome puts a ProcessSingleton
 * *socket* in the profile directory, and a sandbox that forbids binding sockets
 * forbids that too — puppeteer then reports "the browser is already running",
 * which is a confusing way to say "the profile directory is not usable". A
 * directory in the working tree always is.
 *
 * `--allow-file-access-from-files` — pages link their stylesheet relatively;
 * without this Chrome treats every file:// document as its own opaque origin
 * and the sheet silently never applies.
 */
export async function launchChrome({ launch }, root, extraArgs = []) {
  const { existsSync, mkdirSync, rmSync } = await import("node:fs");
  const { resolve } = await import("node:path");

  const bin = CANDIDATE_BINS.find((p) => existsSync(p));
  if (!bin) {
    console.error("no Chrome binary found (set PORTFOLIO_CHROME_BIN)");
    process.exit(2);
  }

  const profile = resolve(root, "tests/visual/.chrome-profile-" + process.pid);
  rmSync(profile, { recursive: true, force: true });
  mkdirSync(profile, { recursive: true });

  const browser = await launch({
    executablePath: bin,
    pipe: true,
    userDataDir: profile,
    args: ["--allow-file-access-from-files", "--no-sandbox", "--disable-gpu",
           "--disable-dev-shm-usage", "--hide-scrollbars", ...extraArgs],
  });
  const close = async () => {
    await browser.close();
    rmSync(profile, { recursive: true, force: true });
  };
  return { browser, close };
}
