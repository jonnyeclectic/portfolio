// Scroll-through capture: viewport-sized slices down each page, for review by
// eye rather than by assertion.
//
//   node tests/visual/scroll.mjs                    # every live page, 1280
//   node tests/visual/scroll.mjs --width 390        # phone pass
//   node tests/visual/scroll.mjs index.html         # just these
//
// visual_check.mjs writes fullPage captures, which is right for a gate but
// useless for review: index.html is 11,682px tall, so a full-page PNG scales
// down to a thumbnail where no text is legible. These are 1:1 slices with a
// small overlap, so nothing falls in a seam.
import { launch } from "puppeteer-core";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync } from "node:fs";
import { PAGES, launchChrome } from "./pages.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

const argv = process.argv.slice(2);
const wIdx = argv.indexOf("--width");
const WIDTH = wIdx >= 0 ? Number(argv[wIdx + 1]) : 1280;
const wanted = argv.filter((a, i) => !a.startsWith("--") && i !== wIdx + 1);
const pages = wanted.length ? wanted : PAGES;

const HEIGHT = WIDTH < 700 ? 780 : 900;
const OVERLAP = 70;          // so a heading never lands exactly on a seam
const MAX_SLICES = 7;        // a very long page is sampled, not exhausted

const OUT = resolve(root, `tests/visual/scroll-${WIDTH}`);
mkdirSync(OUT, { recursive: true });

const { browser, close } = await launchChrome({ launch }, root,
  ["--force-color-profile=srgb"]);
const page = await browser.newPage();
await page.setViewport({ width: WIDTH, height: HEIGHT, deviceScaleFactor: 1 });

for (const rel of pages) {
  const file = resolve(root, rel);
  if (!existsSync(file)) { console.error(`scroll: ${rel} is missing`); continue; }
  const label = rel.replace(/[\/.]/g, "_");
  await page.goto("file://" + file, { waitUntil: "networkidle0" });
  // Motion is NOT suppressed — the point is to see what a visitor sees — but
  // reveal-on-scroll needs a beat to settle after each jump.
  await new Promise((r) => setTimeout(r, 600));

  const total = await page.evaluate(() => document.documentElement.scrollHeight);
  const step = HEIGHT - OVERLAP;
  const needed = Math.max(1, Math.ceil((total - HEIGHT) / step) + 1);
  const slices = Math.min(needed, MAX_SLICES);
  // When a page is longer than MAX_SLICES covers, spread the captures over the
  // whole document instead of stopping partway down.
  const stride = slices > 1 ? (total - HEIGHT) / (slices - 1) : 0;

  for (let i = 0; i < slices; i++) {
    const y = Math.round(i * stride);
    await page.evaluate((yy) => window.scrollTo(0, yy), y);
    await new Promise((r) => setTimeout(r, 450));
    await page.screenshot({ path: resolve(OUT, `${label}-${String(i).padStart(2, "0")}.png`) });
  }
  console.log(`${rel}: ${slices} slice(s) over ${total}px`);
}

await close();
console.log(`\nscroll: ${OUT}`);
