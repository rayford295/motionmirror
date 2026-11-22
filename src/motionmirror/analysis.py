"""Pose sequence -> reps -> metrics -> feedback. Pure Python, no video deps."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any

from motionmirror import __version__
from motionmirror.feedback import Finding, consistency, evaluate, score
from motionmirror.profiles import get_profile
from motionmirror.profiles.base import Rep, Row, load_phase_labels, round_floats
from motionmirror.schema import PoseSequence


@dataclass
class Analysis:
    sport: str
    side: str
    sequence: PoseSequence
    rows: list[Row]
    reps: list[Rep]
    summaries: list[dict[str, Any]]
    findings: list[list[Finding]]
    consistency: dict[str, dict[str, float]]
    quality: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    @property
    def phases(self) -> list[str]:
        return get_profile(self.sport).PHASES

    def to_report(self) -> dict[str, Any]:
        reps = []
        for summary, findings in zip(self.summaries, self.findings):
            reps.append({**summary, "score": score(findings),
                         "findings": [f.to_mapping() for f in findings]})
        return round_floats({
            "tool": f"motionmirror {__version__}",
            "sport": self.sport,
            "side": self.side,
            "source": Path(self.sequence.source).name if self.sequence.source else None,
            "quality": self.quality,
            "warnings": self.warnings,
            "rep_count": len(self.reps),
            "reps": reps,
            "consistency": self.consistency,
            "disclaimer": (
                "Metrics are 2D single-camera pose proxies. Reference ranges are broad starter "
                "values for spotting outliers, not coaching verdicts. No club, ball-flight or "
                "make/miss measurement is performed."
            ),
        })

    def write_metrics_csv(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        keys: list[str] = []
        for row in self.rows:
            keys.extend(k for k in row if k not in keys)
        phase_at = {m.row: f"{rep.index}:{m.name}" for rep in self.reps for m in rep.phases.values()}
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["phase", *keys])
            writer.writeheader()
            for i, row in enumerate(self.rows):
                out = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in row.items()}
                writer.writerow({"phase": phase_at.get(i, ""), **out})
        return path

    def write_report_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_report(), indent=2), encoding="utf-8")
        return path


def quality_of(sequence: PoseSequence) -> tuple[dict[str, Any], list[str]]:
    vis = [v for v in (f.mean_visibility() for f in sequence.frames) if v is not None]
    quality = {
        "fps": sequence.fps,
        "width": sequence.width,
        "height": sequence.height,
        "pose_frames": len(sequence),
        "total_frames": sequence.total_frames,
        "coverage": sequence.coverage,
        "mean_visibility": mean(vis) if vis else None,
        "duration_s": sequence.frames[-1].time_s if sequence.frames else 0.0,
    }
    warnings = []
    if sequence.coverage is not None and sequence.coverage < 0.8:
        warnings.append(f"Pose found in only {sequence.coverage:.0%} of frames; "
                        "frame the whole body and avoid back-lighting.")
    if quality["mean_visibility"] is not None and quality["mean_visibility"] < 0.5:
        warnings.append("Low landmark visibility; metrics may be noisy.")
    if not (sequence.width and sequence.height):
        warnings.append("Video size unknown; angles assume square pixels in normalized space.")
    return quality, warnings


def analyze_sequence(
    sequence: PoseSequence,
    sport: str = "golf",
    side: str = "right",
    *,
    labels: str | Path | None = None,
    min_confidence: float = 0.0,
) -> Analysis:
    """Run the full sport analysis on a pose sequence.

    ``side="auto"`` runs both sides and keeps the one that yields more reps
    (ties broken by confidence). Selfie-mode clips are mirrored, so a
    right-handed athlete can look left-handed on camera.
    """

    if side == "auto" and hasattr(get_profile(sport), "pick_side"):
        picked = get_profile(sport).pick_side(sequence)
        result = analyze_sequence(sequence, sport, picked, labels=labels,
                                  min_confidence=min_confidence)
        result.warnings.append(f"side=auto picked '{picked}' (fastest-moving hand).")
        return result
    if side == "auto":
        tries = [analyze_sequence(sequence, sport, s, labels=labels,
                                  min_confidence=min_confidence) for s in ("right", "left")]
        best = max(tries, key=lambda a: (len(a.reps),
                                         sum(r.confidence for r in a.reps)))
        best.warnings.append(f"side=auto picked '{best.side}' (mirrored selfie video flips it).")
        return best

    profile = get_profile(sport)
    rows = profile.build_rows(sequence, side)
    quality, warnings = quality_of(sequence)
    if labels:
        reps = load_phase_labels(labels, rows, profile.PHASES) if rows else []
    else:
        reps = profile.detect_reps(rows, sequence.fps or 30.0)
        dropped = [r for r in reps if r.confidence < min_confidence]
        reps = [r for r in reps if r.confidence >= min_confidence]
        if dropped:
            warnings.append(f"Dropped {len(dropped)} low-confidence rep(s).")
    if not reps:
        warnings.append(f"No {profile.NAME} rep was detected; try --labels with hand-marked "
                        "phase times, or check the camera angle.")
    summaries = [profile.summarize_rep(rows, rep) for rep in reps]
    checks_for = getattr(profile, "checks_for", lambda _s: profile.CHECKS)
    findings = [evaluate(s, checks_for(s)) for s in summaries]
    return Analysis(
        sport=profile.NAME, side=side, sequence=sequence, rows=rows, reps=reps,
        summaries=summaries, findings=findings,
        consistency=consistency(summaries, profile.CONSISTENCY_KEYS),
        quality=quality, warnings=warnings,
    )
