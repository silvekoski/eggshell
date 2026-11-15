// Egg Shell pitch scenes. Every number has its source in rokoko-teleop/video-pitch/SCRIPT.md.
import React from "react";
import { useCurrentFrame } from "remotion";
import { cue, prog } from "../kit";
import { DotMeter, Hw, Knob, Led, MUTED, ORANGE, Page, Pill, RED, Rig, SimScreen, T, Term, WHITE, clipT, fade } from "../te";

type S = React.FC<{ dur: number }>;

const Wordmark: React.FC<{ size: number; style?: React.CSSProperties }> = ({ size, style }) => (
  <T size={size} weight={100} style={{ letterSpacing: "-0.04em", lineHeight: 0.9, ...style }}>egg shell</T>
);

// s00: the wordmark.
export const S00: S = ({ dur }) => {
  const f = useCurrentFrame();
  return (
    <Page dur={dur}>
      <Wordmark size={360} style={{ position: "absolute", left: 110, top: 330, ...fade(f, 2, 18) }} />
    </Page>
  );
};

// s01: hook. Three demos, no touch feedback, sorted by hand.
export const S01: S = ({ dur }) => {
  const f = useCurrentFrame();
  const nothing = cue("s01", "nothing", 0, 180);
  const drops = cue("s01", "drops", 0, 250);
  const crushes = cue("s01", "crushes", 0, 265);
  const sorts = cue("s01", "sorts", 0, 310);
  const cards: { name: string; t: number; label: string; kind: "lifted" | "dropped" | "crushed"; at: number }[] = [
    { name: "egg", t: 7.75, label: "lifted", kind: "lifted", at: drops - 6 },
    { name: "drop", t: 6.5, label: "dropped", kind: "dropped", at: drops },
    { name: "crush", t: 4.6, label: "crushed", kind: "crushed", at: crushes },
  ];
  return (
    <Page dur={dur}>
      <T size={72} style={{ position: "absolute", left: 120, top: 150, ...fade(f, 4) }}>robots learn to grasp from human demos.</T>
      <T size={72} style={{ position: "absolute", left: 120, top: 245, ...fade(f, nothing - 10) }}>through a glove, you feel nothing.</T>
      <Hw x={120} y={400} w={1680} h={500}>
        {cards.map((c, i) => (
          <div key={c.name} style={{ ...fade(f, 20 + i * 8) }}>
            <SimScreen name={c.name} t={c.t} x={40 + i * 550} y={40} w={500} h={281} />
            <div style={{ position: "absolute", left: 40 + i * 550, top: 350, display: "flex", alignItems: "center", gap: 16, ...fade(f, c.at) }}>
              <Led kind={c.kind} size={30} /><T size={36}>{c.label}</T>
            </div>
          </div>
        ))}
        <div style={{ position: "absolute", left: 40, top: 420, display: "flex", alignItems: "center", gap: 16, ...fade(f, nothing) }}>
          <T size={26} color="#A8A8A8">touch feedback to the operator:</T><T size={26}>none</T>
        </div>
      </Hw>
      <Pill color={MUTED} size={30} style={{ position: "absolute", right: 120, top: 935, ...fade(f, sorts) }}>sorted by hand, before training</Pill>
    </Page>
  );
};

// s02: what Egg Shell is, the pipeline, and the simulated-glove disclosure.
export const S02: S = ({ dur }) => {
  const f = useCurrentFrame();
  const steps = [
    { title: "rokoko glove stream", sub: "rgmp v2 · tcp 12277\n26 openxr joints", at: cue("s02", "glove", 0, 100) },
    { title: "retargeting", sub: "joint angles →\nactuator targets", at: cue("s02", "drives", 0, 120) },
    { title: "shadow hand", sub: "20 actuators\nin mujoco", at: cue("s02", "Shadow", 0, 165) },
    { title: "crackable egg", sub: "crack threshold\n8 N", at: cue("s02", "egg", 0, 240) },
    { title: "labelled episode", sub: "force per frame\n+ outcome", at: cue("s02", "crack", 0, 260) + 8 },
  ];
  const honest = cue("s02", "honest", 0, 300);
  const sim = cue("s02", "simulated", 0, 430);
  const w = 290, gap = 37;
  return (
    <Page dur={dur}>
      <Wordmark size={190} style={{ position: "absolute", left: 110, top: 120, ...fade(f, 2) }} />
      <T size={40} style={{ position: "absolute", left: 1050, top: 205, ...fade(f, cue("s02", "sense", 0, 50)) }}>the robot feels what you can't.</T>
      <Hw x={120} y={380} w={1680} h={300}>
        {steps.map((s, i) => {
          const dashed = i === 0 && f >= sim;
          return (
            <div key={s.title} style={{ position: "absolute", left: 34 + i * (w + gap), top: 40, width: w, height: 220, borderRadius: 22, border: `2px ${dashed ? "dashed" : "solid"} ${dashed ? ORANGE : WHITE}`, padding: 22, boxSizing: "border-box", ...fade(f, s.at) }}>
              <T size={30}>{dashed ? "scripted operator" : s.title}</T>
              <T size={22} color="#BDBDBD" style={{ marginTop: 14, whiteSpace: "pre-line" }}>{dashed ? "same openxr hand frames\nas the rokoko solver" : s.sub}</T>
              {i < steps.length - 1 && <T size={34} style={{ position: "absolute", right: -32, top: 86 }}>→</T>}
            </div>
          );
        })}
      </Hw>
      <div style={{ position: "absolute", left: 120, top: 740, display: "flex", alignItems: "center", gap: 28, ...fade(f, honest) }}>
        <Pill color={ORANGE} size={34}>glove input: simulated</Pill>
        <T size={34}>no rokoko gloves or sdk licence were available.</T>
      </div>
      <T size={30} color="#E6E6E6" style={{ position: "absolute", left: 120, top: 840, ...fade(f, sim) }}>a scripted operator drives the real pipeline: retargeting, the mujoco hand, egg physics, labels.</T>
    </Page>
  );
};

const Readout: React.FC<{ n: string; unit: string; kind: "lifted" | "crushed" | "not lifted" | "dropped"; label: string; extra?: string; at: number }> = ({ n, unit, kind, label, extra, at }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 22, ...fade(f, at) }}>
      <Led kind={kind} size={30} />
      <T size={84} weight={100}>{n}</T><T size={40}>{unit}</T>
      <T size={34} style={{ marginLeft: 12 }}>{label}</T>
      {extra && <T size={30} color="#BDBDBD" style={{ marginLeft: 12 }}>{extra}</T>}
    </div>
  );
};

// s03: careful vs squeeze.
export const S03: S = ({ dur }) => {
  const f = useCurrentFrame();
  const sq = cue("s03", "Squeeze", 0, 200);
  const tEgg = Math.min(8.6, clipT("egg", f, 3.0, 1.4)); // hold the egg in the air
  const tCr = f < sq ? 2.0 : clipT("crush", f, 2.0, 0.4, sq);
  return (
    <Page dur={dur}>
      <Rig name="egg" x={120} y={200} title="careful · episode 0" t={tEgg}>
        <Readout n="3.76" unit="N" kind="lifted" label="lifted" extra="11.0 cm" at={cue("s03", "three", 0, 100)} />
      </Rig>
      <Rig name="crush" x={980} y={200} title="squeeze · episode 1" t={tCr} dim={f < sq - 6}>
        <Readout n="19.63" unit="N" kind="crushed" label="crushed" at={cue("s03", "nineteen", 0, 250)} />
      </Rig>
      <T size={32} style={{ position: "absolute", left: 120, top: 840, ...fade(f, cue("s03", "threshold", 0, 360)) }}>crack threshold: 8 N, a simulation proxy, not measured on a real egg.</T>
    </Page>
  );
};

// s04: every try becomes a labelled episode.
export const S04: S = ({ dur }) => {
  const f = useCurrentFrame();
  const eps = [
    { name: "egg", t: 7.75, kind: "lifted" as const, label: "lifted", sub: "11.0 cm · 3.76 N", at: cue("s04", "lifted", 0, 160) },
    { name: "crush", t: 5.5, kind: "crushed" as const, label: "crushed", sub: "19.63 N", at: cue("s04", "crushed", 0, 190) },
    { name: "drop", t: 5.0, kind: "lifted" as const, label: "lifted", sub: "10.9 cm", at: cue("s04", "lifted", 0, 160) + 4 },
    { name: "miss", t: 4.0, kind: "not lifted" as const, label: "not lifted", sub: "0.0 cm · 2.23 N", at: cue("s04", "not", 0, 220) },
  ];
  return (
    <Page dur={dur}>
      <T size={72} style={{ position: "absolute", left: 120, top: 150, ...fade(f, 4) }}>every try → a labelled episode</T>
      {eps.map((e, i) => (
        <Hw key={e.name} x={120 + i * 430} y={310} w={390} h={440} title={`episode ${i}`} style={fade(f, 14 + i * 7)}>
          <SimScreen name={e.name} t={e.t} x={20} y={72} w={350} h={197} radius={14} />
          <div style={{ position: "absolute", left: 24, top: 300, display: "flex", alignItems: "center", gap: 16, ...fade(f, e.at) }}>
            <Led kind={e.kind} size={28} /><T size={38}>{e.label}</T>
          </div>
          <T size={26} color="#BDBDBD" style={{ position: "absolute", left: 24, top: 360, ...fade(f, e.at + 4) }}>{e.sub}</T>
        </Hw>
      ))}
      <T size={28} color="#E6E6E6" style={{ position: "absolute", left: 120, top: 800, ...fade(f, cue("s04", "grip", 0, 100)) }}>each episode: grip force and egg pose per frame, keyframes, inspire hand commands, the simulator label.</T>
    </Page>
  );
};

// s05: thresholds miss the drop, Nemotron catches it.
export const S05: S = ({ dur }) => {
  const f = useCurrentFrame();
  const tDrop = clipT("drop", f, 2.5, 0.77);
  const lifted = cue("s05", "lifted", 0, 240);
  const nem = cue("s05", "NVIDIA", 0, 280);
  const dropped = cue("s05", "dropped", 0, 450);
  return (
    <Page dur={dur}>
      <Rig name="drop" x={120} y={200} title="drop · episode 2" t={tDrop}>
        <div style={{ display: "flex", alignItems: "center", gap: 20, ...fade(f, lifted - 4) }}>
          <Led kind="lifted" size={30} /><T size={40}>simulator: lifted</T><T size={30} color="#BDBDBD">rose 10.9 cm</T>
        </div>
      </Rig>
      <Hw x={980} y={200} w={820} h={581} title="nemotron 3.5 super vl · review" style={fade(f, nem - 6)}>
        <div style={{ position: "absolute", left: 30, top: 80, display: "flex", gap: 12 }}>
          {[2.97, 5.0, 6.5, 7.9].map((t, i) => (
            <div key={t} style={{ position: "relative", width: 180, height: 101, ...fade(f, cue("s05", "four", 0, 360) + i * 4) }}>
              <SimScreen name="drop" t={t} x={0} y={0} w={180} h={101} radius={10} />
            </div>
          ))}
        </div>
        <T size={20} color="#A8A8A8" style={{ position: "absolute", left: 30, top: 192, ...fade(f, cue("s05", "four", 0, 360)) }}>keyframes: contact · max lift · falling · final   + 24-row force/lift log</T>
        <div style={{ position: "absolute", left: 30, top: 240 }}>
          <Term size={22} lines={[
            { text: "$ uv run teleop review --dataset datasets/demo", at: nem + 10, color: WHITE },
            { text: "ep  simulator   nemotron    conf  status", at: nem + 40, color: "#8F8F8F" },
            { text: "0   lifted      lifted      1.00  agree", at: nem + 50 },
            { text: "1   crushed     crushed     1.00  agree", at: nem + 58 },
            { text: "2   lifted      dropped     0.98  FLAG disagree", at: dropped - 8, color: "#FF6A5C" },
            { text: "3   not_lifted  not_lifted  1.00  agree", at: dropped },
          ]} />
        </div>
        <div style={{ position: "absolute", left: 30, top: 470, display: "flex", gap: 18, alignItems: "center", ...fade(f, dropped) }}>
          <Pill size={32}>dropped · 0.98</Pill>
          <T size={30}>flagged for a human</T>
        </div>
      </Hw>
      <T size={27} color="#F0F0F0" style={{ position: "absolute", left: 120, top: 840, width: 1680, ...fade(f, dropped + 20) }}>“the grip force dropped to 0.0 N at t=6.25s while the egg was still at 3.4 cm height”</T>
      <T size={27} color="#E0E0E0" style={{ position: "absolute", left: 120, top: 905, ...fade(f, dropped + 45) }}>the simulator label is kept. agrees on 3 of 4: a smoke test, not an accuracy figure.</T>
    </Page>
  );
};

// s06: weight-space programming.
export const S06: S = ({ dur }) => {
  const f = useCurrentFrame();
  const trained = cue("s06", "trained", 0, 80);
  const added = cue("s06", "added", 0, 190);
  const rose = cue("s06", "twenty-seven", 0, 350);
  const sub = cue("s06", "Subtracting", 0, 440);
  const rows = [
    { name: "θ₀", note: "base policy, all demos", lifted: 27, crushed: 62, at: trained, knob: 0 },
    { name: "θ₀ + τ lifted", note: "no new training", lifted: 67, crushed: 28, at: added, knob: 1 },
    { name: "θ₀ + τ crushed", note: "", lifted: 13, crushed: 83, at: rose + 30, knob: 2 },
    { name: "θ₀ − τ crushed", note: "breaks the reach", lifted: 3, crushed: 57, at: sub, knob: 3 },
  ];
  const BW = 760;
  return (
    <Page dur={dur}>
      <T size={64} style={{ position: "absolute", left: 120, top: 140, ...fade(f, 4) }}>labels make the data trainable</T>
      <T size={28} color="#EDEDED" style={{ position: "absolute", left: 120, top: 230, ...fade(f, trained) }}>weight-space programming · closed-loop policy · 480 scripted demos · egg moved up to ±15 mm · 100 unseen rollouts per row</T>
      <Hw x={120} y={300} w={1680} h={560}>
        {rows.map((r, i) => {
          const g = prog(f, r.at + 6, 30);
          const y = 40 + i * 125;
          const neg = i === 3;
          return (
            <div key={r.name} style={{ position: "absolute", left: 0, top: y, width: 1680, height: 110, ...fade(f, r.at) }}>
              <Knob x={40} y={18} size={64} fill={i === 1 ? ORANGE : undefined} angle={-120 + g * (i === 3 ? 30 : 140)} />
              <T size={38} style={{ position: "absolute", left: 140, top: 18, whiteSpace: "nowrap" }}>{r.name}</T>
              <T size={22} color={neg ? "#FF6A5C" : "#A8A8A8"} style={{ position: "absolute", left: 140, top: 66 }}>{r.note}</T>
              <div style={{ position: "absolute", left: 520, top: 34, width: BW, height: 36, borderRadius: 18, border: `2px solid ${WHITE}`, overflow: "hidden" }}>
                <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: BW * (r.lifted / 100) * g, background: WHITE }} />
                <div style={{ position: "absolute", left: BW * (r.lifted / 100) * g, top: 0, bottom: 0, width: BW * (r.crushed / 100) * g, background: RED }} />
              </div>
              <T size={40} style={{ position: "absolute", left: 1310, top: 24 }}>{Math.round(r.lifted * g)} %</T>
              <T size={22} color="#BDBDBD" style={{ position: "absolute", left: 1312, top: 72 }}>lifted</T>
              <T size={40} color="#FF6A5C" style={{ position: "absolute", left: 1480, top: 24 }}>{Math.round(r.crushed * g)} %</T>
              <T size={22} color="#BDBDBD" style={{ position: "absolute", left: 1482, top: 72 }}>crushed</T>
            </div>
          );
        })}
      </Hw>
      <div style={{ position: "absolute", left: 120, top: 905, display: "flex", gap: 22, alignItems: "center", ...fade(f, sub + 10) }}>
        <Pill size={28}>honest negative</Pill>
        <T size={28}>subtracting τ crushed lifts only 3 %. source: docs/weightspace/results_v2.md</T>
      </div>
    </Page>
  );
};

// s07: proof.
export const S07: S = ({ dur }) => {
  const f = useCurrentFrame();
  const rows = [
    { big: "57", text: "automated tests pass", sub: "retargeting, wire format, tcp path, mujoco checks, nemotron review", at: cue("s07", "tests", 0, 20) - 10 },
    { big: "1e-4", text: "rad: angles back through a fake solver", sub: "rgmp v2 client rebuilt from rokoko's rokoko-ros2-bridge code", at: cue("s07", "wire", 0, 80) },
    { big: "4 / 4", text: "replays give the same label", sub: "a fresh simulation driven by each recorded episode", at: cue("s07", "replay", 0, 190) },
  ];
  return (
    <Page dur={dur}>
      <T size={64} style={{ position: "absolute", left: 120, top: 140, ...fade(f, 2) }}>proof</T>
      <Hw x={120} y={260} w={1680} h={600}>
        {rows.map((r, i) => (
          <div key={r.big} style={{ position: "absolute", left: 50, top: 50 + i * 180, display: "flex", alignItems: "center", gap: 36, ...fade(f, r.at) }}>
            <Led kind="lifted" size={30} />
            <T size={96} weight={100} style={{ width: 300 }}>{r.big}</T>
            <div>
              <T size={40}>{r.text}</T>
              <T size={26} color="#A8A8A8" style={{ marginTop: 10 }}>{r.sub}</T>
            </div>
          </div>
        ))}
      </Hw>
      <T size={28} color="#E6E6E6" style={{ position: "absolute", left: 120, top: 905, ...fade(f, 60) }}>not verified yet: real smartglove data, the ros 2 path, the real inspire hand.</T>
    </Page>
  );
};

// s08: next steps, the orange knob row.
export const S08: S = ({ dur }) => {
  const f = useCurrentFrame();
  const items = [
    { title: "real rokoko gloves", sub: "at the venue", at: cue("s08", "real", 0, 30) },
    { title: "inspire hand", sub: "0–1000 per finger, computed\nevery frame, not sent yet", at: cue("s08", "Inspire", 0, 90) },
    { title: "more demonstrations", sub: "humans, not scripts", at: cue("s08", "many", 0, 190) },
  ];
  return (
    <Page dur={dur}>
      <T size={64} style={{ position: "absolute", left: 120, top: 140, ...fade(f, 2) }}>next</T>
      <Hw x={120} y={280} w={1680} h={520}>
        {items.map((it, i) => {
          const g = prog(f, it.at, 24);
          return (
            <div key={it.title} style={{ ...fade(f, it.at - 4) }}>
              <Knob x={80 + i * 540} y={70} size={150} fill={ORANGE} angle={-130 + g * 200} />
              <T size={44} style={{ position: "absolute", left: 80 + i * 540, top: 270 }}>{it.title}</T>
              <T size={28} color="#BDBDBD" style={{ position: "absolute", left: 80 + i * 540, top: 335, whiteSpace: "pre-line" }}>{it.sub}</T>
            </div>
          );
        })}
      </Hw>
    </Page>
  );
};

// s09: end card, TX-6 homage: huge wordmark, black panel with knobs and the red pill.
export const S09: S = ({ dur }) => {
  const f = useCurrentFrame();
  const line = cue("s09", "The", 0, 40);
  return (
    <Page dur={dur}>
      <Wordmark size={330} style={{ position: "absolute", left: 100, top: 150, ...fade(f, 2) }} />
      <T size={56} style={{ position: "absolute", left: 120, top: 470, ...fade(f, line) }}>the robot feels what you can't.</T>
      <Hw x={760} y={640} w={1040} h={330} style={fade(f, 10, 20)}>
        {[0, 1, 2, 3].map((i) => <Knob key={i} x={60 + i * 120} y={60} size={80} angle={-60 + i * 35} />)}
        {[0, 1, 2, 3].map((i) => <Knob key={"o" + i} x={60 + i * 120} y={190} size={80} fill={ORANGE} angle={-30 + i * 25} />)}
        <DotMeter x={540} y={60} h={210} value={11.0} label="11.0 cm" />
        <Pill size={30} style={{ position: "absolute", left: 620, top: 130 }}>rokoko × junction 2026</Pill>
      </Hw>
    </Page>
  );
};
