// Reviewable screenshots — viewport-sized, so detail survives being looked at.
// visual_check.mjs writes full-page captures, which for a long page shrink to a
// thumbnail where nothing is legible. This writes three per page at 1280:
//
//   <page>-top.png     the fold
//   <page>-mid.png     40% down the document
//   <page>-focus.png   two Tab presses in, to show the focus ring
//
//   node tests/visual/shots.mjs                 # every live page
//   node tests/visual/shots.mjs contact.html    # just these
import { launch } from "puppeteer-core";
import { mkdirSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { PAGES, launchChrome } from "./pages.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = resolve(root, "tests/visual/shots");
mkdirSync(OUT, { recursive: true });

const wanted = process.argv.slice(2);
const pages = wanted.length ? wanted : PAGES;

const { browser, close } = await launchChrome({ launch }, root,
  ["--force-color-profile=srgb"]);

const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });

for (const rel of pages) {
  const file = resolve(root, rel);
  if (!existsSync(file)) {
    console.error(`shots: ${rel} is missing`);
    continue;
  }
  const label = rel.replace(/[\/.]/g, "_");
  await page.goto("file://" + file, { waitUntil: "networkidle0" });
  // Long enough for reveal-on-scroll to settle; motion is NOT suppressed here,
  // because the point is to see what a visitor sees.
  await new Promise((r) => setTimeout(r, 500));
  await page.screenshot({ path: resolve(OUT, `${label}-top.png`) });

  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.evaluate((y) => window.scrollTo(0, y), Math.round(h * 0.4));
  await new Promise((r) => setTimeout(r, 600));
  await page.screenshot({ path: resolve(OUT, `${label}-mid.png`) });

  await page.evaluate(() => window.scrollTo(0, 0));
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await new Promise((r) => setTimeout(r, 300));
  await page.screenshot({ path: resolve(OUT, `${label}-focus.png`) });
  console.log(`shot ${rel}`);
}

await close();
console.log(`\nshots: ${OUT}`);
