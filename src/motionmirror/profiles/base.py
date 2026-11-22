"""Shared building blocks for sport profiles.

A *profile* turns a :class:`PoseSequence` into:

1. ``rows``  – one metric dict per pose frame (``None`` where a joint was hidden),
2. ``reps``  – detected repetitions (swings / shots) with timestamped phases,
3. ``summaries`` – per-rep metrics read at the phases that matter.

All geometry runs in aspect-corrected image space and distances are expressed
in *torso lengths* (shoulder-midpoint to hip-midpoint), so numbers are
comparable across resolutions, zoom levels and portrait/landscape clips.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Any

from motionmirror.geometry import angle_degrees, distance, line_angle_2d, midpoint
from motionmirror.schema import FramePose, PoseSequence
from motionmirror.signal import fill_gaps, moving_average, speed_2d

Row = dict[str, Any]
Point = tuple[float, float, float]


@dataclass(frozen=True)
class PhaseMark:
    name: str
    frame_index: int
    time_s: float
    row: int  # index into the metric rows


@dataclass
class Rep:
    """One detected swing or shot."""

    index: int
    phases: dict[str, PhaseMark]
    confidence: float = 1.0
    source: str = "auto"  # "auto" or "labels"
    notes: list[str] = field(default_factory=list)

    def time(self, phase: str) -> float:
        return self.phases[phase].time_s

    def to_mapping(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "notes": self.notes,
            "phases": {k: asdict(v) for k, v in self.phases.items()},
        }


# ---------------------------------------------------------------- geometry ---

def mid(a: Point | None, b: Point | None) -> Point | None:
    if a is None or b is None:
        return a or b
    return midpoint(a, b)


def safe_angle(a: Point | None, b: Point | None, c: Point | None) -> float | None:
    if a is None or b is None or c is None:
        return None
    try:
        return angle_degrees(a, b, c)
    except ValueError:
        return None


def safe_dist(a: Point | None, b: Point | None) -> float | None:
    if a is None or b is None:
        return None
    return distance(a, b)


def opposite(side: str) -> str:
    side = side.lower()
    if side not in ("left", "right"):
        raise ValueError("side must be 'right' or 'left'.")
    return "left" if side == "right" else "right"


def body_frame(frame: FramePose) -> dict[str, Any]:
    """Landmarks every profile needs, in aspect-corrected space."""

    p = frame.point
    ls, rs = p("left_shoulder"), p("right_shoulder")
    lh, rh = p("left_hip"), p("right_hip")
    shoulder_mid, hip_mid = mid(ls, rs), mid(lh, rh)
    torso = safe_dist(shoulder_mid, hip_mid) if ls and rs and lh and rh else None
    tilt = None
    if shoulder_mid and hip_mid and ls and rs and lh and rh:
        # forward/side bend of the trunk vs. vertical, image plane
        tilt = abs(90.0 - abs(line_angle_2d(hip_mid, shoulder_mid)))
    shoulder_line = line_angle_2d(ls, rs) if ls and rs else None
    hip_line = line_angle_2d(lh, rh) if lh and rh else None
    return {
        "ls": ls, "rs": rs, "lh": lh, "rh": rh,
        "shoulder_mid": shoulder_mid, "hip_mid": hip_mid,
        "torso": torso, "trunk_tilt_deg": tilt,
        "shoulder_line_deg": shoulder_line, "hip_line_deg": hip_line,
        "nose": p("nose"),
    }


# -------------------------------------------------------------------- rows ---

def build_rows(
    sequence: PoseSequence,
    frame_metrics: Callable[[FramePose], Row],
    *,
    track_points: dict[str, Callable[[FramePose], Point | None]],
    smooth: int = 5,
) -> list[Row]:
    """Compute metric rows plus smoothed position/speed tracks.

    ``track_points`` maps a prefix (e.g. ``"hands"``) to a function returning a
    point; the result gets ``<prefix>_x``, ``<prefix>_y`` and ``<prefix>_speed``
    columns, where speed is in torso lengths per second.
    """

    rows: list[Row] = []
    for frame in sequence.frames:
        row: Row = {"frame_index": frame.frame_index, "time_s": frame.time_s,
                    "visibility": frame.mean_visibility()}
        row.update(frame_metrics(frame))
        for prefix, fn in track_points.items():
            pt = fn(frame)
            row[f"{prefix}_x"] = pt[0] if pt else None
            row[f"{prefix}_y"] = pt[1] if pt else None
        rows.append(row)
    if not rows:
        return rows

    torso_vals = [r.get("torso_len") for r in rows if r.get("torso_len")]
    scale = median(torso_vals) if torso_vals else 1.0
    times = [r["time_s"] for r in rows]
    for prefix in track_points:
        xs = moving_average(fill_gaps([r[f"{prefix}_x"] for r in rows], max_gap=8), smooth)
        ys = moving_average(fill_gaps([r[f"{prefix}_y"] for r in rows], max_gap=8), smooth)
        speeds = moving_average(speed_2d(xs, ys, times), smooth)
        for r, x, y, s in zip(rows, xs, ys, speeds):
            r[f"{prefix}_x_s"] = x
            r[f"{prefix}_y_s"] = y
            r[f"{prefix}_speed"] = None if s is None else s / scale
    for r in rows:
        r["scale"] = scale
    return rows


def mark(rows: list[Row], name: str, idx: int) -> PhaseMark:
    return PhaseMark(name=name, frame_index=int(rows[idx]["frame_index"]),
                     time_s=float(rows[idx]["time_s"]), row=idx)


def value_at(rows: list[Row], rep: Rep, phase: str, key: str, radius: int = 2) -> float | None:
    """Median of ``key`` over +/-``radius`` rows around a phase.

    A short median window absorbs single-frame pose glitches such as the
    model briefly swapping left and right legs.
    """

    if phase not in rep.phases:
        return None
    i = rep.phases[phase].row
    vals = [r.get(key) for r in rows[max(0, i - radius): i + radius + 1]]
    vals = [v for v in vals if v is not None]
    return median(vals) if vals else None


def drift(rows: list[Row], rep: Rep, start: str, end: str, prefix: str,
          axis: str | None = None) -> float | None:
    """Displacement of a tracked point between two phases, in torso lengths."""

    a, b = rows[rep.phases[start].row], rows[rep.phases[end].row]
    ax, ay, bx, by = (a.get(f"{prefix}_x"), a.get(f"{prefix}_y"),
                      b.get(f"{prefix}_x"), b.get(f"{prefix}_y"))
    if None in (ax, ay, bx, by):
        return None
    scale = a.get("scale") or 1.0
    if axis == "x":
        return abs(bx - ax) / scale
    if axis == "y":
        return abs(by - ay) / scale
    return ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5 / scale


def rep_visibility(rows: list[Row], rep: Rep) -> float:
    lo = min(m.row for m in rep.phases.values())
    hi = max(m.row for m in rep.phases.values())
    vis = [r["visibility"] for r in rows[lo: hi + 1] if r.get("visibility") is not None]
    return sum(vis) / len(vis) if vis else 0.5


def nearest_row(rows: list[Row], time_s: float) -> int:
    return min(range(len(rows)), key=lambda i: abs(rows[i]["time_s"] - time_s))


def load_phase_labels(path: str | Path, rows: list[Row], phases: list[str]) -> list[Rep]:
    """Load human-checked labels and snap them to the nearest pose frame.

    Accepts ``{"reps": [{"address": 1.2, ...}]}`` or the v1 golf format
    ``{"swings": [{"address_time_s": 1.2, ...}]}``.
    """

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = payload.get("reps") or payload.get("swings") or payload.get("shots") or []
    reps: list[Rep] = []
    for n, item in enumerate(items, start=1):
        marks: dict[str, PhaseMark] = {}
        for phase in phases:
            t = item.get(phase, item.get(f"{phase}_time_s"))
            if t is not None:
                marks[phase] = mark(rows, phase, nearest_row(rows, float(t)))
        if marks:
            reps.append(Rep(index=item.get("swing", item.get("shot", n)), phases=marks,
                            confidence=1.0, source="labels",
                            notes=[item["label"]] if item.get("label") else []))
    return reps


def round_floats(obj: Any, digits: int = 4) -> Any:
    if isinstance(obj, float):
        return round(obj, digits)
    if isinstance(obj, dict):
        return {k: round_floats(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, digits) for v in obj]
    return obj
