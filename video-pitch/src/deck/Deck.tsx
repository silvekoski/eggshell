// The pitch deck: one slide per frame (1920x1080, fps 30 so the clip frames in SimScreen map to seconds), same TE look as the video. Rendered by src/deck/build.sh.
// Every number has its source in SCRIPT.md.
import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { DotMeter, Hw, Knob, Led, MUTED, ORANGE, Pill, RED, Rig, SimScreen, T, WHITE, type Outcome } from "../te";

const GREY = "#767676";

const Slide: React.FC<{ n: number; children: React.ReactNode }> = ({ n, children }) => (
  <AbsoluteFill style={{ background: GREY }}>
    <div style={{ position: "absolute", top: 48, left: 120, right: 120, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <T size={26}>egg shell — robot teleoperation</T>
      <T size={26}>rokoko × junction 2026</T>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 14, height: 14, borderRadius: 7, border: `2px solid ${WHITE}` }} />
        <T size={26}>glove input: simulated</T>
      </div>
    </div>
    {children}
    <T size={22} color="#D0D0D0" style={{ position: "absolute", right: 120, bottom: 44 }}>{String(n).padStart(2, "0")} / {String(SLIDES.length).padStart(2, "0")}</T>
  </AbsoluteFill>
);

const Title: React.FC<{ children: React.ReactNode; sub?: string }> = ({ children, sub }) => (
  <div style={{ position: "absolute", left: 120, top: 140 }}>
    <T size={72}>{children}</T>
    {sub && <T size={30} color="#EDEDED" style={{ marginTop: 18 }}>{sub}</T>}
  </div>
);

const Wordmark: React.FC<{ size: number; style?: React.CSSProperties }> = ({ size, style }) => (
  <T size={size} weight={100} style={{ letterSpacing: "-0.04em", lineHeight: 0.9, ...style }}>egg shell</T>
);

const LedRow: React.FC<{ kind: Outcome; children: React.ReactNode; size?: number }> = ({ kind, children, size = 34 }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 18 }}><Led kind={kind} size={size * 0.8} /><T size={size}>{children}</T></div>
);

const S1 = () => (
  <>
    <Wordmark size={400} style={{ position: "absolute", left: 100, top: 160 }} />
    <T size={60} style={{ position: "absolute", left: 120, top: 540 }}>the robot feels what you can't.</T>
    <Hw x={760} y={680} w={1040} h={300}>
      {[0, 1, 2, 3].map((i) => <Knob key={i} x={60 + i * 120} y={50} size={80} angle={-60 + i * 35} />)}
      {[0, 1, 2, 3].map((i) => <Knob key={"o" + i} x={60 + i * 120} y={170} size={80} fill={ORANGE} angle={-30 + i * 25} />)}
      <DotMeter x={540} y={50} h={190} value={11.0} label="11.0 cm" />
      <Pill size={30} style={{ position: "absolute", left: 620, top: 120 }}>rokoko × junction 2026</Pill>
    </Hw>
    <T size={28} color="#EDEDED" style={{ position: "absolute", left: 120, top: 700, width: 580 }}>pick up an egg with a robot hand, and every try becomes labelled training data.</T>
  </>
);

const S2 = () => (
  <>
    <Title sub="teleoperation is how labs collect demonstrations. the operator feels nothing through the glove.">robots learn grasps from human demos</Title>
    <Hw x={120} y={380} w={1680} h={460}>
      {[{ n: "egg", t: 7.75, k: "lifted" as const, l: "good demo" }, { n: "drop", t: 6.5, k: "dropped" as const, l: "dropped" }, { n: "crush", t: 4.6, k: "crushed" as const, l: "crushed" }].map((c, i) => (
        <div key={c.n}>
          <SimScreen name={c.n} t={c.t} x={40 + i * 550} y={40} w={500} h={281} />
          <div style={{ position: "absolute", left: 40 + i * 550, top: 360 }}><LedRow kind={c.k}>{c.l}</LedRow></div>
        </div>
      ))}
    </Hw>
    <div style={{ position: "absolute", left: 120, top: 890, display: "flex", gap: 24, alignItems: "center" }}>
      <Pill color={MUTED} size={30}>sorted by hand, before training</Pill>
      <T size={30}>bad grasps cost lab time on every dataset.</T>
    </div>
  </>
);

const S3 = () => {
  const steps = [
    ["rokoko glove stream", "rgmp v2 over tcp 12277\n26 openxr joints"],
    ["retargeting", "joint angles →\nactuator targets"],
    ["shadow hand", "20 actuators\nin mujoco"],
    ["crackable egg", "turns red above\n8 N (sim proxy)"],
    ["labelled episode", "force per frame,\nkeyframes, label"],
  ];
  return (
    <>
      <Title sub="a glove stream drives a simulated dexterous hand. the simulator feels the squeeze the operator cannot.">what we built</Title>
      <Hw x={120} y={380} w={1680} h={300}>
        {steps.map(([a, b], i) => (
          <div key={a} style={{ position: "absolute", left: 34 + i * 327, top: 40, width: 290, height: 220, borderRadius: 22, border: `2px ${i === 0 ? "dashed" : "solid"} ${i === 0 ? ORANGE : WHITE}`, padding: 22, boxSizing: "border-box" }}>
            <T size={30}>{a}</T>
            <T size={22} color="#BDBDBD" style={{ marginTop: 14, whiteSpace: "pre-line" }}>{b}</T>
            {i < 4 && <T size={34} style={{ position: "absolute", right: -32, top: 86 }}>→</T>}
          </div>
        ))}
      </Hw>
      <div style={{ position: "absolute", left: 120, top: 740, display: "flex", gap: 28, alignItems: "center" }}>
        <Pill color={ORANGE} size={32}>glove input: simulated</Pill>
        <T size={30}>no rokoko gloves or sdk licence were available.</T>
      </div>
      <T size={28} color="#EDEDED" style={{ position: "absolute", left: 120, top: 830, width: 1680, lineHeight: 1.35 }}>a scripted operator sends the same openxr hand frames as the rokoko solver. the client is rebuilt from rokoko's rokoko-ros2-bridge code. inspire hand commands (0–1000 per finger) are computed every frame, not sent yet.</T>
    </>
  );
};

const Read: React.FC<{ n: string; kind: Outcome; label: string; extra?: string }> = ({ n, kind, label, extra }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
    <Led kind={kind} size={30} /><T size={84} weight={100}>{n}</T><T size={40}>N</T>
    <T size={34} style={{ marginLeft: 12 }}>{label}</T>
    {extra && <T size={30} color="#BDBDBD" style={{ marginLeft: 12 }}>{extra}</T>}
  </div>
);

const S4 = () => (
  <>
    <Rig name="egg" x={120} y={150} title="careful · episode 0" t={7.75}><Read n="3.76" kind="lifted" label="lifted" extra="11.0 cm" /></Rig>
    <Rig name="crush" x={980} y={150} title="squeeze · episode 1" t={5.5}><Read n="19.63" kind="crushed" label="crushed" /></Rig>
    <T size={32} style={{ position: "absolute", left: 120, top: 790 }}>careful vs squeeze. crack threshold: 8 N, a simulation proxy, not measured on a real egg.</T>
    <T size={28} color="#EDEDED" style={{ position: "absolute", left: 120, top: 850 }}>grip force: the vertical fader, red once cracked. lift: the dotted meter.</T>
  </>
);

const S5 = () => {
  const eps = [
    { n: "egg", t: 7.75, k: "lifted" as const, l: "lifted", s: "11.0 cm · 3.76 N" },
    { n: "crush", t: 5.5, k: "crushed" as const, l: "crushed", s: "19.63 N" },
    { n: "drop", t: 5.0, k: "lifted" as const, l: "lifted", s: "rose 10.9 cm, then the hand opened" },
    { n: "miss", t: 4.0, k: "not lifted" as const, l: "not lifted", s: "0.0 cm · 2.23 N" },
  ];
  return (
    <>
      <Title sub="each episode: grip force and egg pose per frame, keyframes, inspire commands, and the simulator label.">every try → a labelled episode</Title>
      {eps.map((e, i) => (
        <Hw key={e.n} x={120 + i * 430} y={360} w={390} h={460} title={`episode ${i}`}>
          <SimScreen name={e.n} t={e.t} x={20} y={72} w={350} h={197} radius={14} />
          <div style={{ position: "absolute", left: 24, top: 300 }}><LedRow kind={e.k} size={38}>{e.l}</LedRow></div>
          <T size={24} color="#BDBDBD" style={{ position: "absolute", left: 24, top: 360, right: 20 }}>{e.s}</T>
        </Hw>
      ))}
      <T size={28} color="#EDEDED" style={{ position: "absolute", left: 120, top: 880 }}>labels by threshold: lifted needs 5 cm or more, crushed needs a force above the crack threshold.</T>
    </>
  );
};

const S6 = () => (
  <>
    <Title sub="nvidia nemotron 3.5 super vl reviews each episode from 4 keyframes and a 24-row force/lift log.">thresholds miss the drop. nemotron catches it.</Title>
    <Hw x={120} y={380} w={1680} h={430}>
      <div style={{ position: "absolute", left: 40, top: 40, fontFamily: "'JetBrains Mono Variable', monospace", fontSize: 28, lineHeight: 1.6, color: "#D0D0D0", whiteSpace: "pre" }}>
        <div style={{ color: "#8F8F8F" }}>ep  simulator   nemotron    conf  status</div>
        <div>0   lifted      lifted      1.00  agree</div>
        <div>1   crushed     crushed     1.00  agree</div>
        <div style={{ color: "#FF6A5C" }}>2   lifted      dropped     0.98  FLAG disagree</div>
        <div>3   not_lifted  not_lifted  1.00  agree</div>
      </div>
      <div style={{ position: "absolute", left: 1050, top: 50 }}>
        <Pill size={36}>dropped · 0.98</Pill>
        <T size={30} style={{ marginTop: 24 }}>flagged for a human.</T>
        <T size={30} style={{ marginTop: 8 }}>the simulator label is kept.</T>
      </div>
      <T size={26} color="#EDEDED" style={{ position: "absolute", left: 40, top: 320, right: 40, lineHeight: 1.35 }}>“the grip force dropped to 0.0 N at t=6.25s while the egg was still at 3.4 cm height, followed by a rapid descent …”</T>
    </Hw>
    <T size={28} color="#EDEDED" style={{ position: "absolute", left: 120, top: 860, width: 1680, lineHeight: 1.35 }}>agrees on 3 of 4: a smoke test, not an accuracy figure. strict json schema, a grounding check against the log, at most 3 requests per episode. source: docs/demo-run/review.md</T>
  </>
);

const S7 = () => {
  const rows = [
    { name: "θ₀", note: "base policy, all demos", l: 27, c: 62 },
    { name: "θ₀ + τ lifted", note: "no new training", l: 67, c: 28, hot: true },
    { name: "θ₀ + τ crushed", note: "", l: 13, c: 83 },
    { name: "θ₀ − τ crushed", note: "honest negative: breaks the reach", l: 3, c: 57, neg: true },
  ];
  const BW = 760;
  return (
    <>
      <Title sub="closed-loop policy · 480 scripted demos · egg moved up to ±15 mm · 5 seeds × 20 unseen egg positions = 100 rollouts per row">labels make the data trainable</Title>
      <Hw x={120} y={340} w={1680} h={560}>
        {rows.map((r, i) => (
          <div key={r.name} style={{ position: "absolute", left: 0, top: 40 + i * 125, width: 1680, height: 110 }}>
            <Knob x={40} y={18} size={64} fill={r.hot ? ORANGE : undefined} angle={-120 + (r.neg ? 30 : 140)} />
            <T size={38} style={{ position: "absolute", left: 140, top: 18 }}>{r.name}</T>
            <T size={22} color={r.neg ? "#FF6A5C" : "#A8A8A8"} style={{ position: "absolute", left: 140, top: 66 }}>{r.note}</T>
            <div style={{ position: "absolute", left: 520, top: 34, width: BW, height: 36, borderRadius: 18, border: `2px solid ${WHITE}`, overflow: "hidden" }}>
              <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: (BW * r.l) / 100, background: WHITE }} />
              <div style={{ position: "absolute", left: (BW * r.l) / 100, top: 0, bottom: 0, width: (BW * r.c) / 100, background: RED }} />
            </div>
            <T size={40} style={{ position: "absolute", left: 1310, top: 24 }}>{r.l} %</T>
            <T size={22} color="#BDBDBD" style={{ position: "absolute", left: 1312, top: 72 }}>lifted</T>
            <T size={40} color="#FF6A5C" style={{ position: "absolute", left: 1480, top: 24 }}>{r.c} %</T>
            <T size={22} color="#BDBDBD" style={{ position: "absolute", left: 1482, top: 72 }}>crushed</T>
          </div>
        ))}
      </Hw>
      <T size={26} color="#EDEDED" style={{ position: "absolute", left: 120, top: 935 }}>weight-space programming: task vectors from fine-tunes on the lifted and crushed labels. source: docs/weightspace/results_v2.md</T>
    </>
  );
};

const S8 = () => (
  <>
    <Title>proof: what is verified, what is simulated</Title>
    <Hw x={120} y={280} w={1000} h={620} title="verified">
      <div style={{ position: "absolute", left: 40, top: 100, display: "flex", flexDirection: "column", gap: 34 }}>
        <LedRow kind="lifted">57 automated tests pass</LedRow>
        <LedRow kind="lifted">rgmp v2 client: angles back within 1e-4 rad</LedRow>
        <T size={24} color="#A8A8A8" style={{ marginTop: -22, marginLeft: 46 }}>through a fake solver, rebuilt from rokoko-ros2-bridge</T>
        <LedRow kind="lifted">replay: the same label for 4 of 4 episodes</LedRow>
        <LedRow kind="lifted">nemotron review: 3 of 4 agree, the drop flagged</LedRow>
        <LedRow kind="lifted">weight-space: 27 % → 67 % lifted</LedRow>
      </div>
    </Hw>
    <Hw x={1160} y={280} w={640} h={620} title="simulated or not verified" dim>
      <div style={{ position: "absolute", left: 40, top: 100, display: "flex", flexDirection: "column", gap: 34 }}>
        <LedRow kind="not lifted" size={30}>all glove input (scripted)</LedRow>
        <LedRow kind="not lifted" size={30}>the 8 N crack threshold</LedRow>
        <LedRow kind="not lifted" size={30}>real smartglove data</LedRow>
        <LedRow kind="not lifted" size={30}>the ros 2 path</LedRow>
        <LedRow kind="not lifted" size={30}>the real inspire hand</LedRow>
        <LedRow kind="not lifted" size={30}>demos are scripted</LedRow>
      </div>
    </Hw>
  </>
);

const S9 = () => (
  <>
    <Title>next</Title>
    <Hw x={120} y={300} w={1680} h={520}>
      {[["real rokoko gloves", "at the venue: record-glove and\nrun --source rgmp are ready"], ["inspire hand", "0–1000 per finger, computed\nevery frame, not sent yet"], ["more demonstrations", "a few hundred episodes,\na hand-labelled sample"]].map(([a, b], i) => (
        <div key={a}>
          <Knob x={80 + i * 540} y={70} size={150} fill={ORANGE} angle={-130 + i * 80} />
          <T size={44} style={{ position: "absolute", left: 80 + i * 540, top: 270 }}>{a}</T>
          <T size={28} color="#BDBDBD" style={{ position: "absolute", left: 80 + i * 540, top: 335, whiteSpace: "pre-line" }}>{b}</T>
        </div>
      ))}
    </Hw>
  </>
);

const S10 = () => (
  <>
    <Wordmark size={400} style={{ position: "absolute", left: 100, top: 160 }} />
    <T size={60} style={{ position: "absolute", left: 120, top: 540 }}>the robot feels what you can't.</T>
    <T size={28} color="#EDEDED" style={{ position: "absolute", left: 120, top: 640, width: 600, lineHeight: 1.4 }}>python · mujoco · shadow dexterous hand (mujoco menagerie) · nvidia nemotron 3.5 super vl · rokoko rgmp v2</T>
    <Hw x={760} y={680} w={1040} h={300}>
      {[0, 1, 2, 3].map((i) => <Knob key={i} x={60 + i * 120} y={50} size={80} angle={-60 + i * 35} />)}
      {[0, 1, 2, 3].map((i) => <Knob key={"o" + i} x={60 + i * 120} y={170} size={80} fill={ORANGE} angle={-30 + i * 25} />)}
      <DotMeter x={540} y={50} h={190} value={11.0} label="11.0 cm" />
      <Pill size={30} style={{ position: "absolute", left: 620, top: 120 }}>rokoko × junction 2026</Pill>
    </Hw>
  </>
);

const SLIDES = [S1, S2, S3, S4, S5, S6, S7, S8, S9, S10];
export const DECK_SLIDES = SLIDES.length;

export const Deck = () => {
  const f = useCurrentFrame();
  const S = SLIDES[Math.min(f, SLIDES.length - 1)];
  return <Slide n={f + 1}><S /></Slide>;
};
