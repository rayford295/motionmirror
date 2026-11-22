"""End-to-end: video (or pose JSON) -> analysis -> report folder."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from swingform_ai.analysis import Analysis, analyze_sequence
from swingform_ai.report import write_markdown
from swingform_ai.schema import PoseSequence


@dataclass
class RunResult:
    analysis: Analysis
    out_dir: Path
    files: dict[str, Path] = field(default_factory=dict)


def _progress(i: int, n: int) -> None:
    if n:
        sys.stderr.write(f"\r  pose {i}/{n} frames ({100 * i // n}%)")
        sys.stderr.flush()


def run(
    source: str | Path,
    out_dir: str | Path,
    *,
    sport: str = "golf",
    side: str = "right",
    model: str = "full",
    labels: str | Path | None = None,
    render: bool = True,
    ball_trail: str = "off",  # "off", "detect", "proxy"
    min_confidence: float = 0.0,
    width: int | None = None,
    height: int | None = None,
) -> RunResult:
    """Analyze a video or a pose JSON and write every artifact into ``out_dir``.

    Outputs: ``pose.json``, ``metrics.csv``, ``report.json``, ``report.md`` and,
    for video input with ``render=True``, ``overlay.mp4``, ``timeline.png``,
    ``keyposes.jpg``.
    """

    source, out = Path(source), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    is_video = source.suffix.lower() not in (".json",)
    if is_video:
        from swingform_ai.video import extract_pose

        print(f"Extracting pose from {source.name} ...", file=sys.stderr)
        sequence = extract_pose(source, model, progress=_progress)
        print(file=sys.stderr)
    else:
        sequence = PoseSequence.load(source)
    if width and height:
        sequence = sequence.with_aspect(width, height)

    analysis = analyze_sequence(sequence, sport, side, labels=labels,
                                min_confidence=min_confidence)
    files: dict[str, Path] = {}
    if is_video:
        files["pose"] = sequence.save(out / "pose.json")
    files["metrics"] = analysis.write_metrics_csv(out / "metrics.csv")
    files["report_json"] = analysis.write_report_json(out / "report.json")

    assets: dict[str, str] = {}
    if is_video and render:
        from swingform_ai import render as rd

        tracks = None
        if analysis.sport == "golf" and ball_trail != "off" and analysis.reps:
            from swingform_ai.ballflight import track_balls
            from swingform_ai.video import read_video_info

            impacts = [(r.index, r.phases["impact"].frame_index) for r in analysis.reps
                       if "impact" in r.phases]
            tracks = track_balls(source, sequence, impacts, read_video_info(source),
                                 allow_proxy=ball_trail == "proxy",
                                 direction=1 if analysis.side == "right" else -1)
            for t in tracks:
                analysis.warnings.append(f"Rep {t.rep} ball trail: {t.kind}"
                                         + (" (drawn dashed, not measured)" if t.kind == "proxy"
                                            else ""))
            files["report_json"] = analysis.write_report_json(out / "report.json")
        print("Rendering overlay ...", file=sys.stderr)
        files["overlay"] = rd.render_overlay(analysis, source, out / "overlay.mp4", tracks)
        files["timeline"] = rd.timeline_plot(analysis, out / "timeline.png")
        sheet = rd.keypose_sheet(analysis, source, out / "keyposes.jpg")
        if sheet:
            files["keyposes"] = sheet
        assets = {k: files[k].name for k in ("overlay", "timeline", "keyposes") if k in files}
    files["report_md"] = write_markdown(analysis.to_report(), out / "report.md", assets)
    return RunResult(analysis=analysis, out_dir=out, files=files)
