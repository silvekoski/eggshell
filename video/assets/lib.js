/* Shared helpers for the scenes. No timers, no randomness, no network: all output is a function of timeline time. */
(function () {
  const SVGNS = "http://www.w3.org/2000/svg";
  const TIMING = window.VID_TIMING || { lead: 0.2, scenes: {}, cues: {} };
  const norm = (w) => w.toLowerCase().replace(/[^a-z0-9]/g, "");

  const VID = {
    data: window.VIDEO_DATA || {},
    timing: TIMING,
    color: { bg: "#0E1116", paper: "#F4F1EA", blue: "#4C9BE8", amber: "#F0A63A", green: "#3FBF8F", red: "#E5604D", grey: "#8A93A3", ink: "#E8ECF2" },

    /* Scene length in seconds. */
    dur(scene) { return TIMING.scenes[scene].dur; },

    /* Time (scene clock) when the voice starts to say `phrase`. nth picks a later occurrence. edge "e" gives the end of the phrase. */
    t(scene, phrase, nth, edge) {
      const words = TIMING.scenes[scene].words;
      const want = phrase.split(/\s+/).map(norm).filter(Boolean);
      let seen = 0;
      for (let i = 0; i + want.length <= words.length; i++) {
        let ok = true;
        for (let k = 0; k < want.length; k++) if (norm(words[i + k][0]) !== want[k]) { ok = false; break; }
        if (ok) {
          if (seen === (nth || 0)) return TIMING.lead + (edge === "e" ? words[i + want.length - 1][2] : words[i][1]);
          seen++;
        }
      }
      throw new Error("phrase not in narration of " + scene + ": " + phrase);
    },

    svg(tag, attrs, parent) {
      const el = document.createElementNS(SVGNS, tag);
      for (const k in attrs || {}) el.setAttribute(k, attrs[k]);
      if (parent) parent.appendChild(el);
      return el;
    },
    el(tag, cls, parent, text) {
      const el = document.createElement(tag);
      if (cls) el.className = cls;
      if (text != null) el.textContent = text;
      if (parent) parent.appendChild(el);
      return el;
    },
    path(pts, closed) {
      return "M" + pts.map((p) => p[0] + " " + p[1]).join("L") + (closed ? "Z" : "");
    },

    /* Text that types on: one span per character, shown in order. */
    typeOn(tl, el, text, start, duration) {
      el.textContent = "";
      const spans = [];
      for (const ch of text) {
        if (ch === "\n") { el.appendChild(document.createElement("br")); continue; }
        const s = document.createElement("span");
        s.textContent = ch;
        s.style.opacity = "0";
        el.appendChild(s);
        spans.push(s);
      }
      tl.fromTo(spans, { opacity: 0 }, { opacity: 1, duration: 0.02, ease: "none", stagger: duration / spans.length }, start);
    },

    /* A number that ticks linearly from a to b. fmt turns the value into text. */
    counter(tl, el, a, b, start, duration, fmt) {
      const o = { v: a };
      const show = () => { el.textContent = fmt(o.v); };
      el.textContent = fmt(a);
      tl.fromTo(o, { v: a }, { v: b, duration, ease: "none", onUpdate: show }, start);
    },

    /* Entrance: fade and rise. */
    enter(tl, target, start, opts) {
      const o = Object.assign({ y: 18, duration: 0.5 }, opts || {});
      tl.fromTo(target, { opacity: 0, y: o.y }, { opacity: 1, y: 0, duration: o.duration, ease: "power2.out", stagger: o.stagger || 0 }, start);
    },
    fadeOut(tl, target, start, duration) {
      tl.to(target, { opacity: 0, duration: duration || 0.3, ease: "power1.in" }, start);
    },

    /* Draw a stroke from its start to its end. */
    draw(tl, pathEl, start, duration, ease) {
      const len = pathEl.getTotalLength ? pathEl.getTotalLength() : 1000;
      pathEl.style.strokeDasharray = len;
      // hidden until the stroke starts: a zero-length dash with a round cap would show as a dot
      gsap.set(pathEl, { strokeDashoffset: len, opacity: 0 });
      tl.to(pathEl, { opacity: 1, duration: 0.05, ease: "none" }, start);
      tl.to(pathEl, { strokeDashoffset: 0, duration, ease: ease || "power2.inOut" }, start);
    },

    /* The numbered amber mark of a counted item, built in an SVG in drawing pixels. */
    mark(svg, x, y, n, r) {
      const g = VID.svg("g", { class: "mark", transform: "translate(" + x + " " + y + ")" }, svg);
      const inner = VID.svg("g", {}, g);
      VID.svg("circle", { r: r, fill: "#F0A63A", stroke: "#0E1116", "stroke-width": r * 0.12 }, inner);
      const tx = VID.svg("text", { "text-anchor": "middle", "dominant-baseline": "central", "font-size": r * 1.15, "font-weight": 600, fill: "#0E1116", "font-family": "VID Mono, monospace" }, inner);
      tx.textContent = String(n);
      return inner;
    },

    /* Scene fade at both ends, so cuts are soft. */
    sceneEnvelope(tl, stage, scene, opts) {
      const d = VID.dur(scene);
      const o = opts || {};
      if (!o.noIn) tl.fromTo(stage, { opacity: 0 }, { opacity: 1, duration: 0.35, ease: "power1.out" }, 0);
      if (!o.noOut) tl.to(stage, { opacity: 0, duration: 0.25, ease: "power1.in" }, d - 0.27);
      /* keep the timeline as long as the scene */
      tl.set({}, {}, d);
    },
  };

  window.VID = VID;
})();

/* Egg Shell (version 4, teenage engineering): header row, fader, dotted meter, knobs, LEDs, footage clock. */
(function () {
  const V = window.VID;
  const RED = "#FF1A0D";
  V.header = function (stage, tl) {
    const h = V.el("div", "hdr", stage);
    ["egg shell — robot teleoperation", "rokoko × junction 2026", "glove input: simulated"].forEach((t) => V.el("div", "", h, t));
    if (tl) tl.fromTo(h, { opacity: 0 }, { opacity: 1, duration: 0.4, ease: "power1.out" }, 0.1);
    return h;
  };
  /* Grip force as a vertical fader (cap = force, a tick at 8 N, the slot fills red once cracked) and, optionally,
     lift as a dotted level meter. opts: {left, top, height, lift: true|false, max: 22, gap: 110}.
     Returns {root, update(i), tickl} for a frame index i. */
  V.hud = function (parent, D, opts) {
    const o = Object.assign({ left: 0, top: 0, height: 300, lift: true, max: 22, gap: 120 }, opts || {});
    const root = V.el("div", "", parent);
    Object.assign(root.style, { position: "absolute", left: o.left + "px", top: o.top + "px", width: (o.lift ? 2 * o.gap : o.gap) + "px", height: o.height + "px" });
    const H = o.height - 40;   // room for the label under the controls
    const f = V.el("div", "fader", root);
    Object.assign(f.style, { left: "0px", top: "0px", width: o.gap + "px", height: H + "px" });
    const slot = V.el("div", "slot", f);
    const fill = V.el("div", "fill", slot);
    const y = (n) => H - 13 - (H - 26) * Math.min(1, n / o.max);
    const tick = V.el("div", "tick", f); tick.style.top = y(D.crack_force_n) + "px";
    const tickl = V.el("div", "tickl", f, "8 N"); tickl.style.top = y(D.crack_force_n) + "px";
    const cap = V.el("div", "cap", f);
    const fl = V.el("div", "fl", f, "grip"); fl.style.top = (H + 10) + "px";
    let dots = [], liftV = null;
    if (o.lift) {
      const m = V.el("div", "meter", root);
      Object.assign(m.style, { left: o.gap + "px", top: "0px", width: o.gap + "px", height: H + "px" });
      const n = Math.max(8, Math.floor(H / 26));
      for (let k = 0; k < n; k++) { const d = V.el("div", "dot", m); d.style.top = (H - 14 - k * (H - 14) / (n - 1)) + "px"; dots.push(d); }
      liftV = V.el("div", "fl", m, "0.0 cm"); liftV.style.top = (H + 10) + "px";
    }
    const pcr = []; D.cracked.forEach((c, i) => pcr.push(c || (i ? pcr[i - 1] : 0)));
    let last = -1;
    const update = (i) => {
      i = Math.max(0, Math.min(D.force.length - 1, i));
      if (i === last) return;
      last = i;
      const yy = y(D.force[i]);
      cap.style.top = yy + "px";
      fill.style.height = pcr[i] ? (H - yy) + "px" : "0px";
      if (o.lift) {
        const lift = Math.max(0, D.lift[i]);
        const on = Math.round(dots.length * Math.min(1, lift / 12));
        dots.forEach((d, k) => d.classList.toggle("on", k < on));
        liftV.textContent = lift.toFixed(1) + " cm";
      }
    };
    update(0);
    return { root, update, tickl };
  };
  /* An outline knob with a pointer. value v maps to an angle; set(v) turns it. */
  V.knob = function (parent, x, y, r, cls) {
    const k = V.el("div", "knob" + (cls ? " " + cls : ""), parent);
    Object.assign(k.style, { left: (x - r) + "px", top: (y - r) + "px", width: 2 * r + "px", height: 2 * r + "px" });
    const p = V.el("div", "ptr", k);
    return { el: k, ptr: p, set: (deg) => { p.style.transform = "rotate(" + deg + "deg)"; } };
  };
  /* A decorative row of orange knobs (the one accent row). */
  V.orangeRow = function (parent, x, y, n, r, gap) {
    const out = [];
    for (let i = 0; i < n; i++) { const k = V.knob(parent, x + i * gap, y, r, "orange"); k.set(-120 + (i * 53) % 240); out.push(k); }
    return out;
  };
  V.syncFootage = function (tl, D, vstart, mstart, vdur, update) {
    const o = { m: mstart };
    const go = () => update(Math.round(o.m * D.fps));
    go();
    tl.fromTo(o, { m: mstart }, { m: mstart + vdur, duration: vdur, ease: "none", onUpdate: go }, vstart);
  };
})();
