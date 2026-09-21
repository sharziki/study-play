/* Drive the real UI in a real browser and report what the learner sees.
 *
 * A screenshot proves the page painted. It does not prove the mathematics
 * rendered, because `x^{2}` and a KaTeX-typeset x squared look different only
 * if you are reading carefully at the right zoom. This asks the DOM directly:
 * how many KaTeX nodes exist, and does any raw markup survive in the text the
 * learner actually reads.
 *
 * Usage: node ui/scripts/inspect-ui.mjs [url] [--shot path.png]
 */
import { chromium } from "playwright-core";

const url = process.argv[2] ?? "http://localhost:4173/";
const shotIndex = process.argv.indexOf("--shot");
const shot = shotIndex > -1 ? process.argv[shotIndex + 1] : null;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 900 } });
const errors = [];
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});
page.on("pageerror", (error) => errors.push(String(error)));

await page.goto(url, { waitUntil: "networkidle" });
// KaTeX renders in a layout effect after the question arrives, so wait for the
// question itself rather than a fixed delay.
await page.waitForSelector("h1, [data-testid=path]", { timeout: 20000 }).catch(() => {});
await page.waitForTimeout(2500);

const report = await page.evaluate(() => {
  const text = document.body.innerText;
  const buttons = [...document.querySelectorAll("button")]
    .map((b) => b.innerText.trim())
    .filter(Boolean);
  return {
    katexNodes: document.querySelectorAll(".katex").length,
    heading: document.querySelector("h1")?.innerText ?? null,
    // Raw markup the learner should never see.
    rawMarkup: [...text.matchAll(/\\\(|\\\)|\\frac|\\sqrt|\\lim|\^\{|_\{/g)].map((m) => m[0]),
    buttons: buttons.slice(0, 10),
    textLength: text.length,
    bodyPreview: text.slice(0, 600),
  };
});

if (shot) await page.screenshot({ path: shot, fullPage: true });
console.log(JSON.stringify({ url, errors, ...report }, null, 1));
await browser.close();
