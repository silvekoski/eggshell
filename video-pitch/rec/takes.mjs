// The screen recordings of this video. Each take opens `url` on BASE, waits, records `act`, and writes
// public/rec/<id>.mp4. Return an object from `act` to print marks (seconds into the take) for the scene code.
// Run: npm run rec            (all takes)
//      npm run rec -- R2 R3   (some)
import { glide, press, smoothScroll } from "./helpers.mjs";

export const BASE = process.env.BASE_URL || "http://localhost:3000";

// 1280x800 at device scale 1.5 records at 1920x1200: sharp text, and RecWindow crops to 16:9.
export const VIEWPORT = { width: 1280, height: 800, deviceScaleFactor: 1.5 };

export const takes = {
  R1: {
    url: "/",
    async act(page) {
      await page.waitForTimeout(600);
      await smoothScroll(page, 1200, 4000);
      await page.waitForTimeout(500);
    },
  },
  // An example with typing, a click and marks. Change the selectors to your app's.
  // R2: {
  //   url: "/",
  //   async act(page) {
  //     const t0 = Date.now();
  //     const box = page.getByPlaceholder("Ask a question");
  //     await press(page, box, { ms: 900 });
  //     await page.keyboard.type("TRN-070: link up after an SFP swap, no traffic", { delay: 22 });
  //     const sent = (Date.now() - t0) / 1000;
  //     await page.keyboard.press("Enter");
  //     await page.getByText(/Confidence/).first().waitFor({ timeout: 120000 });
  //     const answered = (Date.now() - t0) / 1000;
  //     await page.waitForTimeout(1500);
  //     return { sent, answered };
  //   },
  // },
};
