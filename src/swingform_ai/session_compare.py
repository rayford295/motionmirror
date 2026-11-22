"""Two-session comparison report: chart + Markdown (``swingform compare``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from swingform_ai.compare import ComparisonRow, comparison_rows, extract_records

# Session identity is fixed to argument order (A = first, B = second).
SESSION_COLORS = ["#2a78d6", "#1baf7a"]
TEXT_PRIMARY = "#1a1a19"
TEXT_SECONDARY = "#5f5e56"
GRID = "#e5e4dc"


def load_session(session_dir: Path) -> dict[str, Any]:
    for name in ("report.json", "summary.json"):
        path = session_dir / name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise SystemExit(f"{session_dir} has neither report.json nor summary.json.")


def plot_comparison(rows: list[ComparisonRow], name_a: str, name_b: str, output: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cols = 2
    grid_rows = (len(rows) + cols - 1) // cols
    fig, axes = plt.subplots(grid_rows, cols, figsize=(8.6, 2.6 * grid_rows))
    axes = list(axes.flat) if hasattr(axes, "flat") else [axes]
    for axis in axes[len(rows):]:
        axis.axis("off")
    for axis, row in zip(axes, rows):
        for idx, (values, color) in enumerate(
            [(row.values_a, SESSION_COLORS[0]), (row.values_b, SESSION_COLORS[1])]
        ):
            session_mean = sum(values) / len(values)
            axis.hlines(session_mean, idx - 0.22, idx + 0.22, color=color, linewidth=3)
            axis.plot([idx] * len(values), values, linestyle="none", marker="o", markersize=6,
                      markerfacecolor="white", markeredgecolor=color, markeredgewidth=1.6)
            unit = f" {row.unit}" if row.unit else ""
            axis.annotate(f"{session_mean:.2f}{unit}", (idx, session_mean),
                          textcoords="offset points", xytext=(28, -4), fontsize=8,
                          color=TEXT_PRIMARY)
        axis.set_xlim(-0.6, 1.6)
        axis.set_xticks([0, 1])
        axis.set_xticklabels([name_a, name_b], fontsize=8, color=TEXT_SECONDARY)
        axis.set_title(row.label, fontsize=9, color=TEXT_PRIMARY, loc="left")
        axis.tick_params(axis="y", labelsize=8, colors=TEXT_SECONDARY)
        axis.grid(True, axis="y", color=GRID, linewidth=0.8)
        for spine in axis.spines.values():
            spine.set_visible(False)
    fig.suptitle(f"{name_a} vs {name_b} · per-event metrics", fontsize=11, color=TEXT_PRIMARY)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)
    return output


def _meta(s: dict[str, Any]) -> dict[str, Any]:
    if "quality" in s:  # v2 report.json
        q = s["quality"]
        cov = q.get("coverage")
        return {"events": s.get("rep_count", 0), "duration": q.get("duration_s") or 0.0,
                "res": f"{q.get('width')}x{q.get('height')}",
                "coverage": None if cov is None else cov * 100}
    v = s.get("video", {})
    return {"events": len(s.get("swing_summaries", s.get("shot_events", []))),
            "duration": v.get("duration_s", 0.0), "res": f"{v.get('width')}x{v.get('height')}",
            "coverage": s.get("pose", {}).get("coverage_pct")}


def write_report(sport: str, rows: list[ComparisonRow], a: dict, b: dict, name_a: str,
                 name_b: str, chart_rel: str, output: Path) -> Path:
    word = {"golf": "swing", "basketball": "shot", "badminton": "stroke"}.get(sport, "rep")
    ma, mb = _meta(a), _meta(b)
    cov = lambda m: "n/a" if m["coverage"] is None else f"{m['coverage']:.1f}%"  # noqa: E731
    lines = [
        f"# Session Comparison: {name_a} vs {name_b}", "",
        f"Same athlete, same sport ({sport}), two sessions. Values are per-{word} means; "
        "open dots on the chart are individual events.", "",
        f"![Comparison chart]({chart_rel})", "",
        f"| Metric | {name_a} | {name_b} | Delta |", "| --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        unit = f" {row.unit}" if row.unit else ""
        lines.append(f"| {row.label} | {row.mean_a:.2f}{unit} | {row.mean_b:.2f}{unit} | "
                     f"{row.delta:+.2f}{unit} |")
    lines += [
        "", "## Sessions", "", f"| | {name_a} | {name_b} |", "| --- | --- | --- |",
        f"| Events | {ma['events']} | {mb['events']} |",
        f"| Duration | {ma['duration']:.1f}s | {mb['duration']:.1f}s |",
        f"| Resolution | {ma['res']} | {mb['res']} |",
        f"| Pose coverage | {cov(ma)} | {cov(mb)} |", "",
        "## Limitations", "",
        "- Single-camera pose proxies; camera angle and distance differ between sessions, so "
        "cross-session deltas are directional, not calibrated measurements.",
        "- Metrics compare only events the detector isolated in both sessions.", "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def compare_sessions(session_a: Path, session_b: Path, output_doc: Path | None = None,
                     asset_output: Path | None = None) -> dict[str, Any]:
    name_a, name_b = session_a.name, session_b.name
    slug = f"compare-{name_a}-vs-{name_b}"
    output_doc = output_doc or Path("docs/examples") / f"{slug}.md"
    asset_output = asset_output or Path("docs/assets") / slug
    a, b = load_session(session_a), load_session(session_b)
    sport_a, rec_a = extract_records(a)
    sport_b, rec_b = extract_records(b)
    if sport_a != sport_b:
        raise SystemExit(f"Cannot compare {sport_a} against {sport_b}.")
    rows = comparison_rows(sport_a, rec_a, rec_b)
    if not rows:
        raise SystemExit("No shared metrics between the two sessions.")
    chart = plot_comparison(rows, name_a, name_b, asset_output / "metric_comparison.png")
    import os
    rel = os.path.relpath(chart, output_doc.parent)
    doc = write_report(sport_a, rows, a, b, name_a, name_b, rel, output_doc)
    return {"doc": str(doc), "chart": str(chart), "metrics": len(rows)}
