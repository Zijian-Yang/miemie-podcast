import { chromium } from "playwright";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function main() {
  const [htmlPath, pngPath] = process.argv.slice(2);

  if (!htmlPath || !pngPath) {
    console.error("Usage: node scripts/render-mindmap.mjs <htmlPath> <pngPath>");
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1800, height: 1200, deviceScaleFactor: 2 },
  });

  const absoluteHtml = path.resolve(htmlPath);
  const absolutePng = path.resolve(pngPath);

  await page.goto(pathToFileURL(absoluteHtml).href, { waitUntil: "networkidle" });
  await page.screenshot({
    path: absolutePng,
    fullPage: true,
    animations: "disabled",
  });
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

