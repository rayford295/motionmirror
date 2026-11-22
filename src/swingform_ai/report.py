"""Human-readable Markdown report for an :class:`Analysis`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

STATUS_ICON = {"ok": "OK", "low": "LOW", "high": "HIGH", "unknown": "n/a"}


def _fmt(value: Any, unit: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        text = f"{value:.2f}" if abs(value) < 10 else f"{value:.0f}"
    else:
        text = str(value)
    return f"{text} {unit}".strip() if unit and unit != ":1" else (text + (":1" if unit else ""))


def _range(lo: Any, hi: Any) -> str:
    if lo is not None and hi is not None:
        return f"{lo:g} - {hi:g}"
    if lo is not None:
        return f">= {lo:g}"
    if hi is not None:
        return f"<= {hi:g}"
    return ""


def render_markdown(report: dict[str, Any], assets: dict[str, str] | None = None) -> str:
    assets = assets or {}
    q = report["quality"]
    coverage = "n/a" if q.get("coverage") is None else f"{q['coverage']:.0%}"
    lines = [
        f"# SwingForm report: {report['sport']} ({report.get('source') or 'clip'})",
        "",
        f"*{report['tool']}* | side: **{report['side']}** | reps detected: "
        f"**{report['rep_count']}**",
        "",
        "## Capture quality",
        "",
        "| Duration | FPS | Resolution | Pose coverage | Mean visibility |",
        "| --- | --- | --- | --- | --- |",
        f"| {_fmt(q.get('duration_s'), 's')} | {_fmt(q.get('fps'))} | "
        f"{q.get('width')}x{q.get('height')} | {coverage} | "
        f"{_fmt(q.get('mean_visibility'))} |",
        "",
    ]
    for w in report.get("warnings", []):
        lines.append(f"> **Note:** {w}")
    if report.get("warnings"):
        lines.append("")
    for label, key in (("Overlay video", "overlay"), ("Timeline", "timeline"),
                       ("Key poses", "keyposes")):
        if key in assets and key != "overlay":
            lines += [f"![{label}]({assets[key]})", ""]
    if "overlay" in assets:
        lines += [f"Overlay video: [{assets['overlay']}]({assets['overlay']})", ""]

    for rep in report["reps"]:
        phases = ", ".join(f"{k} {v['time_s']:.2f}s" for k, v in rep["phases"].items())
        score = rep.get("score")
        lines += [
            f"## Rep {rep['index']}" + (f" - {score:.0f}% of checks in range" if score is not None
                                         else ""),
            "",
            f"Phases: {phases}  ",
            f"Detection confidence: {rep['confidence']:.2f} ({rep['source']})",
            "",
        ]
        for note in rep.get("notes", []):
            lines.append(f"- {note}")
        timing = rep.get("timing", {})
        if timing:
            lines.append("Timing: " + ", ".join(f"{k.replace('_', ' ')} {_fmt(v)}"
                                                 for k, v in timing.items()))
            lines.append("")
        lines += ["| Check | Value | Reference | Status | Cue |", "| --- | --- | --- | --- | --- |"]
        for f in rep["findings"]:
            cue = f["message"] if f["status"] != "ok" else ""
            lines.append(f"| {f['label']} | {_fmt(f['value'], f['unit'])} | "
                         f"{_range(f['low'], f['high'])} | {STATUS_ICON[f['status']]} | {cue} |")
        lines.append("")

    if report.get("consistency"):
        lines += ["## Consistency across reps", "", "| Metric | Mean | Std | Min | Max | n |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for key, s in report["consistency"].items():
            lines.append(f"| {key} | {_fmt(s['mean'])} | {_fmt(s['std'])} | {_fmt(s['min'])} | "
                         f"{_fmt(s['max'])} | {s['n']} |")
        lines.append("")
    lines += ["## How to read this", "", report["disclaimer"],
              "Distances are in torso lengths (shoulder-midpoint to hip-midpoint), so they do "
              "not depend on resolution or zoom.", ""]
    return "\n".join(lines)


def write_markdown(report: dict[str, Any], path: str | Path,
                   assets: dict[str, str] | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report, assets), encoding="utf-8")
    return path
