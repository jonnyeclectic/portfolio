// Layout-regression sweep: load every live page in headless Chrome at each
// responsive breakpoint and assert the invariants a CSS slip actually breaks.
// Screenshots land in tests/visual/out/ for eyeballing; the exit code is the gate.
//
//   node tests/visual/visual_check.mjs                 # system Chrome
//   PORTFOLIO_CHROME_BIN=/path/to/chrome node ...      # explicit binary
//
// Runs against the LOCAL working tree over file://, so a branch's own HTML/CSS
// is what gets checked — nothing has to be deployed, and no server has to
// listen (puppeteer's `pipe: true` talks to Chrome over stdio, which is what
// makes this work in a sandbox that blocks socket.bind()).
//
// The point is not pixel-perfection. Pixel diffing a hand-written site fails on
// every intentional change and teaches people to regenerate baselines without
// looking. These are assertions about things that are never deliberately true:
// the page scrolls sideways, the stylesheet did not load, the skip link points
// at nothing, a heading level vanished.
import { launch } from "puppeteer-core";
import { mkdirSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { PAGES, WIDTHS, launchChrome } from "./pages.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = resolve(root, "tests/visual/out");
mkdirSync(OUT, { recursive: true });

const { browser, close } = await launchChrome({ launch }, root,
  ["--in-process-gpu", "--single-process"]);

const page = await browser.newPage();
// Reveal-on-scroll starts at opacity 0. Asking for reduced motion is both the
// honest audit (this is how a motion-sensitive visitor receives the page) and
// the only way a screenshot shows the real layout rather than a mid-fade.
await page.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);

let failures = 0;
for (const rel of PAGES) {
  const file = resolve(root, rel);
  if (!existsSync(file)) {
    console.error(`FAIL ${rel} — file is missing`);
    failures++;
    continue;
  }
  for (const width of WIDTHS) {
    await page.setViewport({ width, height: 950 });
    await page.goto("file://" + file, { waitUntil: "load", timeout: 30000 });

    const r = await page.evaluate(() => {
      const doc = document.documentElement;
      const css = getComputedStyle(document.body);
      const skip = document.querySelector("a.skip");
      const skipHash = skip && skip.getAttribute("href");
      return {
        // A page that scrolls sideways is never intentional on this site.
        overflowPx: Math.max(0, doc.scrollWidth - doc.clientWidth),
        bg: css.backgroundColor,
        // --bg resolving proves the cascade reached the page, whether the
        // tokens came from the shared sheet or an inline :root.
        tokenBg: getComputedStyle(doc).getPropertyValue("--bg").trim(),
        h1s: document.querySelectorAll("h1").length,
        headings: document.querySelectorAll("h1,h2").length,
        // Heading levels in document order. axe tags heading-order
        // "best-practice" rather than WCAG, so its sweep passes a page whose
        // outline jumps h1 -> h4; a screen-reader user navigating by heading
        // still lands nowhere. Two pages here did exactly that.
        levels: [...document.querySelectorAll("h1,h2,h3,h4,h5,h6")]
          .map((h) => Number(h.tagName[1])),
        hasSkip: !!skip,
        // A skip link whose target does not exist silently does nothing —
        // exactly the kind of thing that survives a hand review.
        skipResolves: !!(skipHash && skipHash.startsWith("#")
                         && document.getElementById(skipHash.slice(1))),
        // Which elements actually push the page wide. An element inside a
        // deliberate horizontal scroller (the nav bar, a wide code block, a
        // table in its own overflow box) sticks out past the viewport by
        // design and contributes nothing to document overflow — reporting it
        // sends you to fix a scroll container that is working correctly. Only
        // elements with no scrolling or clipping ancestor are named.
        widest: (() => {
          const clipped = (el) => {
            for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
              const o = getComputedStyle(p).overflowX;
              if (o === "auto" || o === "scroll" || o === "hidden" || o === "clip") return true;
            }
            return false;
          };
          const name = (el) => el.tagName.toLowerCase()
            + (el.id ? "#" + el.id : "")
            + (el.className && typeof el.className === "string"
               ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".") : "");
          return [...document.querySelectorAll("body *")]
            .filter((el) => el.getBoundingClientRect().right > doc.clientWidth + 1)
            .filter((el) => !clipped(el))
            .map((el) => ({ w: Math.round(el.getBoundingClientRect().right), sel: name(el) }))
            .sort((a, b) => b.w - a.w)
            .slice(0, 3);
        })(),
      };
    });

    const problems = [];
    if (r.overflowPx > 0) {
      const who = r.widest.length
        ? r.widest.map((x) => `${x.sel} to ${x.w}px`).join(", ")
        // Nothing unclipped sticks out, so the width comes from a box that is
        // itself sized too wide (a min-width, a fixed grid track) rather than
        // from content spilling out of one.
        : "no unclipped element overflows — check for a min-width or a fixed grid track";
      problems.push(`horizontal overflow ${r.overflowPx}px (${who})`);
    }
    if (!r.tokenBg) problems.push("--bg unresolved (stylesheet not applied?)");
    if (!/rgb\(7, 8, 15\)/.test(r.bg)) problems.push(`body background ${r.bg}, expected #07080f`);
    if (r.h1s !== 1) problems.push(`${r.h1s} <h1> elements, expected exactly 1`);
    // A page whose only heading is its <h1> has no outline: every section
    // title on it is a styled <span>, invisible to anyone navigating by
    // heading. resume.html and docs/index.html both shipped that way.
    if (r.headings < 2) problems.push(`only ${r.headings} h1/h2 — the page has no outline`);
    const skips = r.levels
      .map((lv, i) => [r.levels[i - 1], lv])
      .filter(([prev, lv]) => prev !== undefined && lv > prev + 1)
      .map(([prev, lv]) => `h${prev}->h${lv}`);
    if (skips.length) problems.push(`heading level skipped: ${[...new Set(skips)].join(", ")}`);
    if (!r.hasSkip) problems.push("no skip link");
    else if (!r.skipResolves) problems.push("skip link target does not exist");

    const name = rel.replace(/[\/.]/g, "_") + "-" + width;
    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: width === 1280 });

    if (problems.length) {
      failures++;
      console.error(`FAIL ${rel} @${width}: ${problems.join("; ")}`);
    } else {
      console.log(`PASS ${rel} @${width}`);
    }
  }
}

await close();
if (failures) {
  console.error(`\nvisual-check: ${failures} failing page/width combination(s)`);
  console.error(`screenshots: ${OUT}`);
  process.exit(1);
}
console.log(`\nvisual-check: OK — ${PAGES.length} pages × ${WIDTHS.length} widths clean`);
console.log(`screenshots: ${OUT}`);
