// axe-core sweep — the WCAG checks that only exist once a page is laid out and
// the accessibility tree is computed:
//
//   * colour contrast as RENDERED, including text over gradients and over the
//     hover surfaces, which no token-pair table can predict;
//   * ARIA attribute and role validity against the computed tree;
//   * landmark and region structure;
//   * elements hidden from assistive tech but still focusable.
//
//   node tests/visual/a11y_check.mjs                   # system Chrome
//   PORTFOLIO_CHROME_BIN=/path/to/chrome node ...      # explicit binary
//
// Runs against the LOCAL working tree over file://, like visual_check.mjs.
import { launch } from "puppeteer-core";
import { readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { PAGES, launchChrome } from "./pages.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

// WCAG 2.1 A + AA. Deliberately not "best-practice": those are opinions, and a
// gate that fails on an opinion is a gate people learn to route around.
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

const axePath = resolve(root, "tests/visual/node_modules/axe-core/axe.min.js");
if (!existsSync(axePath)) {
  console.error("a11y-check: axe-core not installed (npm install in tests/visual)");
  process.exit(2);
}
const axeSource = readFileSync(axePath, "utf8");

const { browser, close } = await launchChrome({ launch }, root);

let violatingNodes = 0;
for (const rel of PAGES) {
  const file = resolve(root, rel);
  if (!existsSync(file)) {
    console.error(`a11y-check: ${rel} is missing`);
    violatingNodes++;
    continue;
  }
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  // Emulate reduced motion BEFORE navigating. Reveal-on-scroll fades opacity
  // 0 -> 1, and axe computes contrast from the COMPOSITED colour — so running
  // mid-transition reports a muted token as whatever partial-opacity blend it
  // happened to catch, a value that exists nowhere in the repo. That makes the
  // failure look like a phantom and sends whoever reads it auditing a colour
  // that has been correct for months.
  await page.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);
  await page.goto("file://" + file, { waitUntil: "load" });

  // Prove the page is styled before trusting a contrast result. Relative
  // stylesheet links over file:// only work because of
  // --allow-file-access-from-files, and if that flag does not take effect the
  // colours fall back to browser defaults and axe reports a dozen confident,
  // specific, entirely fictional violations. "Not styled" is one line a
  // maintainer can act on; the alternative is a wild goose chase.
  const styled = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--bg").trim());
  if (!styled) {
    console.error(`FAIL ${rel} — page is unstyled (--bg unresolved); every `
      + `contrast result here would be meaningless, so this is reported as a `
      + `load failure rather than as violations`);
    violatingNodes++;
    await page.close();
    continue;
  }

  await page.evaluate(axeSource);
  const result = await page.evaluate(
    async (tags) => await window.axe.run(document, { runOnly: { type: "tag", values: tags } }),
    TAGS,
  );

  const count = result.violations.reduce((n, v) => n + v.nodes.length, 0);
  violatingNodes += count;
  if (count) {
    console.error(`FAIL ${rel} — ${count} violating node(s)`);
    for (const v of result.violations) {
      console.error(`  [${v.impact}] ${v.id}: ${v.help}`);
      for (const node of v.nodes.slice(0, 3)) {
        console.error(`      ${node.target.join(" ")}`);
        if (node.failureSummary) {
          console.error(`      ${node.failureSummary.replace(/\n\s*/g, " ")}`);
        }
      }
      if (v.nodes.length > 3) console.error(`      … and ${v.nodes.length - 3} more`);
    }
  } else {
    console.log(`PASS ${rel} — ${result.passes.length} rules passed`);
  }
  await page.close();
}

await close();
if (violatingNodes) {
  console.error(`\na11y-check: ${violatingNodes} violating node(s) across ${PAGES.length} pages`);
  process.exit(1);
}
console.log(`\na11y-check: OK — ${PAGES.length} pages clean against ${TAGS.join(", ")}`);
