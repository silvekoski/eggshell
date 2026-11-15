// Shared helpers for the recording scripts: a browser, a visible cursor, eased scrolls and mouse glides.
import { chromium } from "playwright";

/** Launches Chromium. CHROME_PATH picks a local Chrome or Chromium (needed on NixOS); HEADED=1 shows the window. */
export const launch = (opts = {}) =>
  chromium.launch({
    executablePath: process.env.CHROME_PATH || undefined,
    headless: !process.env.HEADED,
    args: ["--hide-scrollbars", "--autoplay-policy=no-user-gesture-required"],
    ...opts,
  });

/** A small arrow cursor that follows the real mouse events, because headless Chromium draws none. Use with addInitScript. */
export const CURSOR = `(() => {
  const c = document.createElement('div');
  c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M4 2l15 11.5-6.6.9 3.9 7.4-2.9 1.4-3.8-7.5L4 20z" fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, { position: 'fixed', left: '-40px', top: '-40px', zIndex: 2147483647, pointerEvents: 'none', transition: 'transform 120ms', filter: 'drop-shadow(0 2px 3px rgba(0,0,0,.25))' });
  addEventListener('mousemove', e => { c.style.left = e.clientX - 3 + 'px'; c.style.top = e.clientY - 2 + 'px'; }, true);
  addEventListener('mousedown', () => c.style.transform = 'scale(.85)', true);
  addEventListener('mouseup', () => c.style.transform = '', true);
  document.addEventListener('DOMContentLoaded', () => document.body.appendChild(c));
})()`;

/** Eased scroll of the page to `to` px over `ms`, so the motion is smooth in the recording. */
export const smoothScroll = (page, to, ms) =>
  page.evaluate(([to, ms]) => new Promise((done) => {
    const from = scrollY, t0 = performance.now();
    const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
    const step = (now) => { const t = Math.min(1, (now - t0) / ms); scrollTo(0, from + (to - from) * ease(t)); t < 1 ? requestAnimationFrame(step) : done(); };
    requestAnimationFrame(step);
  }), [to, ms]);

/** Moves the mouse in small steps to a point inside a locator's box (default: 18 % from its left, middle). */
export async function glide(page, locator, { ms = 1100, fx = 0.18, fy = 0.5 } = {}) {
  const box = await locator.boundingBox();
  if (!box) throw new Error("glide: the element is not visible");
  await page.mouse.move(box.x + box.width * fx, box.y + box.height * fy, { steps: Math.round(ms / 16) });
}

/** A click with a visible press, after a glide. */
export async function press(page, locator, opts) {
  await glide(page, locator, opts);
  await page.waitForTimeout(300);
  await page.mouse.down(); await page.waitForTimeout(90); await page.mouse.up();
}
