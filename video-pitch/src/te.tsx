// The teenage-engineering look for Egg Shell: a flat grey page, black hardware panels, outline knobs,
// a vertical grip fader with an 8 N tick, a dotted lift meter, LED labels and a red pill.
// Simulation footage: public/rec/<name>.mp4 with per-frame data in src/clips/<name>.json (rokoko-teleop/out/footage-light/).
import React from "react";
import { AbsoluteFill, Freeze, Img, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { C, MONO, SceneFade, TEXT, prog } from "./kit";
import egg from "./clips/egg.json";
import crush from "./clips/crush.json";
import drop from "./clips/drop.json";
import miss from "./clips/miss.json";

export const ORANGE = "#FF5A1F";
export const RED = "#FF1A0D";
export const GREY = "#767676";
export const WHITE = "#FFFFFF";
export const MUTED = "#5E5E5E";

type Clip = { frames: { t: number; force_n: number; lift_cm: number; cracked: boolean }[] };
export const CLIPS: Record<string, Clip> = { egg, crush, drop, miss } as unknown as Record<string, Clip>;

/** Lowercase thin grotesk text. */
export const T: React.FC<{ size?: number; weight?: number; color?: string; style?: React.CSSProperties; children: React.ReactNode }> = ({ size = 28, weight = 300, color = WHITE, style, children }) => (
  <div style={{ fontFamily: TEXT, fontSize: size, fontWeight: weight, color, lineHeight: 1.12, letterSpacing: "-0.01em", ...style }}>{children}</div>
);

/** The grey page with the header row. Every scene carries "glove input: simulated". */
export const Page: React.FC<{ dur: number; children?: React.ReactNode; header?: boolean }> = ({ dur, children, header = true }) => (
  <SceneFade dur={dur} inF={8} outF={8}>
    <AbsoluteFill style={{ background: GREY }}>
      {header && (
        <div style={{ position: "absolute", top: 48, left: 120, right: 120, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <T size={26}>egg shell — robot teleoperation</T>
          <T size={26}>rokoko × junction 2026</T>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 14, height: 14, borderRadius: 7, border: `2px solid ${WHITE}` }} />
            <T size={26}>glove input: simulated</T>
          </div>
        </div>
      )}
      {children}
    </AbsoluteFill>
  </SceneFade>
);

/** A black rounded hardware panel. */
export const Hw: React.FC<{ x: number; y: number; w: number; h: number; title?: string; dim?: boolean; style?: React.CSSProperties; children?: React.ReactNode }> = ({ x, y, w, h, title, dim, style, children }) => (
  <div style={{ position: "absolute", left: x, top: y, width: w, height: h, background: dim ? "#5A5A5A" : "#0B0B0B", borderRadius: 36, overflow: "hidden", ...style }}>
    {title && <T size={26} style={{ position: "absolute", left: 30, top: 24 }} color={dim ? "#9A9A9A" : WHITE}>{title}</T>}
    {children}
  </div>
);

/** Vertical fader: grip force, with a tick at the crack threshold. Fills red once cracked. */
export const Fader: React.FC<{ x: number; y: number; h: number; value: number; max?: number; tick?: number; red?: boolean; label?: string }> = ({ x, y, h, value, max = 20, tick = 8, red, label = "grip" }) => {
  const v = Math.min(1, Math.max(0, value / max));
  const tk = tick / max;
  const w = 30;
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, height: h }}>
      <div style={{ position: "absolute", inset: 0, border: `2px solid ${WHITE}`, borderRadius: w / 2, overflow: "hidden" }}>
        {red && <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: `${v * 100}%`, background: RED }} />}
      </div>
      <div style={{ position: "absolute", left: -20, width: w + 40, top: (1 - tk) * h, height: 2, background: WHITE }} />
      <T size={22} style={{ position: "absolute", left: w + 26, top: (1 - tk) * h - 13, whiteSpace: "nowrap" }}>8 N</T>
      <div style={{ position: "absolute", left: -8, width: w + 16, height: 22, borderRadius: 6, background: WHITE, top: (1 - v) * (h - 22) }} />
      <T size={22} style={{ position: "absolute", top: h + 14, width: 120, left: w / 2 - 60, textAlign: "center" }}>{label}</T>
    </div>
  );
};

/** Dotted meter: lift in cm, 0..12. */
export const DotMeter: React.FC<{ x: number; y: number; h: number; value: number; max?: number; n?: number; label?: string }> = ({ x, y, h, value, max = 12, n = 12, label }) => {
  const lit = Math.round((Math.max(0, value) / max) * n);
  return (
    <div style={{ position: "absolute", left: x, top: y, width: 20, height: h }}>
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} style={{ position: "absolute", left: 2, top: (h - 16) * (1 - i / (n - 1)), width: 16, height: 16, borderRadius: 8, border: `2px solid ${WHITE}`, background: i < lit ? WHITE : "transparent" }} />
      ))}
      <T size={22} style={{ position: "absolute", top: h + 14, width: 140, left: 10 - 70, textAlign: "center" }}>{label ?? `${Math.max(0, value).toFixed(1)} cm`}</T>
    </div>
  );
};

export type Outcome = "lifted" | "crushed" | "not lifted" | "dropped";
/** LED: white ring = lifted, red = crushed or dropped, grey = not lifted. */
export const Led: React.FC<{ kind: Outcome; size?: number }> = ({ kind, size = 26 }) => {
  const red = kind === "crushed" || kind === "dropped";
  const col = kind === "not lifted" ? "#8A8A8A" : red ? RED : WHITE;
  return <div style={{ width: size, height: size, borderRadius: size, border: `${Math.max(2, size / 9)}px solid ${col}`, background: red ? RED : "transparent", boxShadow: red ? `0 0 ${size}px ${RED}88` : "none", flexShrink: 0 }} />;
};

export const Pill: React.FC<{ color?: string; size?: number; style?: React.CSSProperties; children: React.ReactNode }> = ({ color = RED, size = 30, style, children }) => (
  <div style={{ display: "inline-flex", alignItems: "center", padding: `${size * 0.35}px ${size * 0.9}px`, borderRadius: 999, background: color, color: WHITE, fontFamily: TEXT, fontWeight: 300, fontSize: size, whiteSpace: "nowrap", ...style }}>{children}</div>
);

/** An outline knob with an indicator line. `fill` draws a solid (orange) knob. */
export const Knob: React.FC<{ x: number; y: number; size?: number; angle?: number; fill?: string; label?: string }> = ({ x, y, size = 64, angle = -40, fill, label }) => (
  <div style={{ position: "absolute", left: x, top: y, width: size, height: size }}>
    <div style={{ position: "absolute", inset: 0, borderRadius: size, border: fill ? "none" : `2px solid ${WHITE}`, background: fill ?? "transparent" }} />
    <div style={{ position: "absolute", left: size / 2 - 1.5, top: 6, width: 3, height: size / 2 - 6, background: fill ? "#0B0B0B" : WHITE, transformOrigin: `1.5px ${size / 2 - 6}px`, transform: `rotate(${angle}deg)` }} />
    {label && <T size={20} style={{ position: "absolute", top: size + 10, width: 160, left: size / 2 - 80, textAlign: "center" }}>{label}</T>}
  </div>
);

/** Clip time in seconds at scene frame f. */
export const clipT = (name: string, f: number, startFrom = 0, rate = 1, at = 0) => {
  const fr = CLIPS[name].frames;
  const end = fr[fr.length - 1].t;
  return Math.min(end, Math.max(0, startFrom + (Math.max(0, f - at) / 30) * rate));
};
export const sample = (name: string, t: number) => {
  const fr = CLIPS[name].frames;
  return fr[Math.min(fr.length - 1, Math.max(0, Math.round(t * 30)))];
};

/** A simulation clip as a screen, frozen at the frame that clipT gives (holds the last frame past the end). */
export const SimScreen: React.FC<{ name: string; t: number; x: number; y: number; w: number; h: number; radius?: number; style?: React.CSSProperties }> = ({ name, t, x, y, w, h, radius = 18, style }) => {
  // The deck is a 10-frame composition, where a frozen video frame does not resolve: it uses stills from
  // public/stills/<name>-<t>.jpg (extracted from the same clips with ffmpeg) instead.
  const { durationInFrames } = useVideoConfig();
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, height: h, borderRadius: radius, overflow: "hidden", background: "#D9D9D9", ...style }}>
      {durationInFrames < 60 ? (
        <Img src={staticFile(`stills/${name}-${t}.jpg`)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      ) : (
        <Freeze frame={Math.round(t * 30)}>
          <OffthreadVideo src={staticFile(`rec/${name}.mp4`)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </Freeze>
      )}
    </div>
  );
};

/** One episode rig: a panel with the sim screen, grip fader and lift meter. */
export const Rig: React.FC<{ name: string; x: number; y: number; w?: number; title: string; t: number; dim?: boolean; children?: React.ReactNode }> = ({ name, x, y, w = 820, title, t, dim, children }) => {
  const s = sample(name, t);
  const sw = w - 250;
  const sh = Math.round((sw * 9) / 16);
  const h = sh + 260;
  return (
    <Hw x={x} y={y} w={w} h={h} title={title} dim={dim}>
      <SimScreen name={name} t={t} x={26} y={74} w={sw} h={sh} />
      <Fader x={sw + 70} y={80} h={sh - 20} value={s.force_n} red={s.cracked} />
      <DotMeter x={sw + 170} y={80} h={sh - 20} value={s.lift_cm} />
      <div style={{ position: "absolute", left: 30, top: sh + 120, right: 30 }}>{children}</div>
    </Hw>
  );
};

/** A typed terminal with real output lines. Each line appears at its frame. */
export const Term: React.FC<{ lines: { text: string; at: number; color?: string }[]; size?: number }> = ({ lines, size = 24 }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ fontFamily: MONO, fontSize: size, lineHeight: 1.5, color: WHITE, whiteSpace: "pre" }}>
      {lines.map((l, i) => {
        const n = Math.floor(Math.max(0, f - l.at) * 3);
        if (f < l.at) return null;
        return <div key={i} style={{ color: l.color ?? "#D0D0D0" }}>{l.text.slice(0, n)}</div>;
      })}
    </div>
  );
};

export const fade = (f: number, at: number, d = 14) => ({ opacity: prog(f, at, d), transform: `translateY(${(1 - prog(f, at, d)) * 10}px)` });
export { C };
