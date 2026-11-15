"""Aggregate weight-space results over training seeds: a Markdown table and an
SVG chart of the c * tau_crushed dial (crush rate and mean peak force).

  uv run python scripts/ws_aggregate.py datasets/ws-state datasets/ws-phase --out docs/weightspace
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(root: Path) -> tuple[list[list[dict]], dict]:
    runs = [json.loads((d / "results.json").read_text()) for d in sorted(root.glob("seed*"))
            if (d / "results.json").exists()]
    setup = json.loads((root / "setup.json").read_text())
    return runs, setup


def table(runs: list[list[dict]]) -> list[dict]:
    rows = []
    for i, r0 in enumerate(runs[0]):
        rs = [run[i] for run in runs]
        n = sum(r["rollouts"] for r in rs)
        forces = [r["peak_force_n_mean"] for r in rs]
        rows.append({"program": r0["program"], "a": r0["a_lifted"], "c": r0["c_crushed"], "n": n,
                     "lifted": sum(r["lifted"] for r in rs), "crushed": sum(r["crushed"] for r in rs),
                     "not_lifted": sum(r["not_lifted"] for r in rs),
                     "force": sum(forces) / len(forces), "force_min": min(forces), "force_max": max(forces),
                     "lift_cm": sum(r["max_lift_cm_mean"] for r in rs) / len(rs)})
    return rows


def md(name: str, rows: list[dict], seeds: int, setup: dict) -> str:
    out = [f"### {name}", "",
           f"Policy input `{setup['obs']}`, egg moved ±{setup['egg_range_m'] * 1000:.0f} mm, {seeds} training seeds × "
           f"{rows[0]['n'] // seeds} unseen egg positions = {rows[0]['n']} rollouts per program.", "",
           "| Program | Lifted | Crushed | Not lifted | Mean peak force (N), seed range |", "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['program']} | {r['lifted']}/{r['n']} ({100 * r['lifted'] / r['n']:.0f} %) | "
                   f"{r['crushed']}/{r['n']} ({100 * r['crushed'] / r['n']:.0f} %) | {r['not_lifted']}/{r['n']} | "
                   f"{r['force']:.2f} ({r['force_min']:.2f} to {r['force_max']:.2f}) |")
    return "\n".join(out) + "\n"


def svg(series: dict[str, list[dict]], path: Path) -> None:
    """Two panels: lifted / crushed share vs c, and mean peak force vs c."""
    W, H, pad = 1200, 580, 70
    pw = (W - 3 * pad) / 2
    ph = H - 2 * pad - 60
    colors = {"state": "#0A3CFF", "phase": "#8A8A8A"}
    dial = {k: [r for r in v if r["program"].startswith("dial")] for k, v in series.items()}
    cs = [r["c"] for r in next(iter(dial.values()))]
    cmin, cmax = min(cs), max(cs)
    fmax = max(r["force_max"] for v in dial.values() for r in v) * 1.05

    def x(c, panel):
        return pad + panel * (pw + pad) + (c - cmin) / (cmax - cmin) * pw

    def y(v, vmax):
        return pad + ph - v / vmax * ph

    el = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
          f'font-family="JetBrains Mono, monospace" font-size="15" fill="#111">',
          f'<rect width="{W}" height="{H}" fill="#EEEEEE"/>']
    for panel, title, vmax in ((0, "LIFTED (solid) / CRUSHED (dashed), % OF ROLLOUTS", 100), (1, "MEAN PEAK FORCE, N", fmax)):
        x0 = pad + panel * (pw + pad)
        el.append(f'<text x="{x0}" y="{pad - 28}">{title}</text>')
        el.append(f'<line x1="{x0}" y1="{pad + ph}" x2="{x0 + pw}" y2="{pad + ph}" stroke="#111" stroke-width="1"/>')
        ticks = (0, 25, 50, 75, 100) if panel == 0 else tuple(range(0, int(vmax) + 1, 5))
        for tv in ticks:
            el.append(f'<line x1="{x0}" y1="{y(tv, vmax):.1f}" x2="{x0 + pw}" y2="{y(tv, vmax):.1f}" stroke="#D6D6D6"/>')
            el.append(f'<text x="{x0 - 8}" y="{y(tv, vmax) + 5:.1f}" text-anchor="end" fill="#6B6B6B">{tv}</text>')
        for c in cs:
            el.append(f'<text x="{x(c, panel)}" y="{pad + ph + 24}" text-anchor="middle">{c:+.1f}</text>')
        el.append(f'<text x="{x0 + pw / 2}" y="{pad + ph + 50}" text-anchor="middle" fill="#6B6B6B">'
                  f'c in theta_0 + c * tau_crushed</text>')
        if panel == 1:
            yy = y(8.0, vmax)
            el.append(f'<line x1="{x0}" y1="{yy}" x2="{x0 + pw}" y2="{yy}" stroke="#D0021B" stroke-dasharray="4 4"/>')
            el.append(f'<text x="{x0 + pw - 4}" y="{yy - 6}" text-anchor="end" fill="#D0021B">8 N crack threshold</text>')
        for name, rows in dial.items():
            col = colors.get(name, "#111")
            if panel == 0:
                for key, dash in (("lifted", ""), ("crushed", ' stroke-dasharray="7 5"')):
                    pts = " ".join(f"{x(r['c'], 0):.1f},{y(100 * r[key] / r['n'], 100):.1f}" for r in rows)
                    el.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="3"{dash}/>')
            else:
                pts = " ".join(f"{x(r['c'], 1):.1f},{y(r['force'], vmax):.1f}" for r in rows)
                el.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="3"/>')
                for r in rows:
                    el.append(f'<line x1="{x(r["c"], 1):.1f}" y1="{y(r["force_min"], vmax):.1f}" x2="{x(r["c"], 1):.1f}" '
                              f'y2="{y(r["force_max"], vmax):.1f}" stroke="{col}" stroke-width="1.5" opacity="0.6"/>')
    lx = pad
    for name, col in colors.items():
        if name in dial:
            el.append(f'<rect x="{lx}" y="{H - 22}" width="18" height="4" fill="{col}"/>')
            el.append(f'<text x="{lx + 26}" y="{H - 16}">{"closed-loop (phase + egg + palm)" if name == "state" else "time-indexed (phase only)"}</text>')
            lx += 420
    el.append("</svg>")
    path.write_text("\n".join(el))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("docs/weightspace"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    series, parts, summary = {}, [], {}
    for root in args.roots:
        runs, setup = load(root)
        rows = table(runs)
        series[setup["obs"]] = rows
        summary[setup["obs"]] = {"seeds": len(runs), "setup": setup, "rows": rows}
        label = "Closed-loop policy" if setup["obs"] == "state" else "Time-indexed policy (baseline)"
        parts.append(md(label, rows, len(runs), setup))
    (args.out / "results_v2.md").write_text("\n".join(parts))
    (args.out / "results_v2.json").write_text(json.dumps(summary, indent=1))
    svg(series, args.out / "dial.svg")
    print("\n".join(parts))


if __name__ == "__main__":
    main()
