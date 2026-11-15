// Records the takes in rec/takes.mjs to public/rec/<id>.mp4 (30 fps H.264, needs ffmpeg on PATH).
// Usage: node rec/record.mjs [ids...]
import { mkdirSync } from "node:fs";
import { CURSOR, launch } from "./helpers.mjs";
import { startRecording } from "./screencast.mjs";
import { BASE, VIEWPORT, takes } from "./takes.mjs";

const OUT = new URL("../public/rec/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });
const want = new Set(process.argv.slice(2));
for (const id of want) if (!takes[id]) throw new Error(`No take ${id} in rec/takes.mjs`);

const { deviceScaleFactor, ...viewport } = VIEWPORT;
const browser = await launch();
const ctx = await browser.newContext({ viewport, deviceScaleFactor, reducedMotion: "no-preference" });
await ctx.addInitScript(CURSOR);
const page = await ctx.newPage();

for (const [id, take] of Object.entries(takes)) {
  if (want.size && !want.has(id)) continue;
  await page.goto(BASE + take.url, { waitUntil: "load" });
  await page.waitForTimeout(take.settle ?? 2500);
  await page.mouse.move(viewport.width - 100, viewport.height - 40);
  const stop = await startRecording(page, OUT + id + ".mp4");
  const marks = await take.act(page);
  console.log(id, await stop(), marks ?? "");
}
await browser.close();
