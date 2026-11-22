"""Golf swing profile: per-frame posture metrics, swing detection, feedback.

Phase model (face-on or down-the-line single camera):

``address`` -> ``top`` -> ``impact`` -> ``finish``

* top     – hands reach their highest point (local minimum of image-y)
* address – last quiet frame before the takeaway that leads into that top
* impact  – hands return closest to their address position, within 0.7 s
            after the top (a downswing is typically ~0.2-0.4 s)
* finish  – hands settle high after impact

Impact is a *pose proxy*: without a club or ball model the exact strike frame
can be a frame or two off.
"""

from __future__ import annotations

from statistics import mean
from typing import Any

from motionmirror.feedback import Check
from motionmirror.geometry import angle_difference_degrees
from motionmirror.profiles.base import (
    Rep,
    Row,
    body_frame,
    drift,
    mark,
    mid,
    rep_visibility,
    safe_angle,
    safe_dist,
    value_at,
)
from motionmirror.profiles.base import build_rows as _build_rows
from motionmirror.schema import FramePose, PoseSequence
from motionmirror.signal import argmax, argmin, local_extrema, percentile

NAME = "golf"
PHASES = ["address", "top", "impact", "finish"]
SWING_EVENTS = PHASES  # v1 name
SIDE_HELP = "Golfer handedness (right-handed golfers lead with the left side)."


def side_roles(handedness: str = "right") -> tuple[str, str]:
    """Return (lead, trail) side names for a golfer."""

    normalized = handedness.lower()
    if normalized == "right":
        return ("left", "right")
    if normalized == "left":
        return ("right", "left")
    raise ValueError("handedness must be 'right' or 'left'.")


def frame_metrics(frame: FramePose, handedness: str = "right") -> dict[str, float | None]:
    """Golf posture metrics for one frame (``None`` when a joint is hidden)."""

    lead, trail = side_roles(handedness)
    p = frame.point
    b = body_frame(frame)
    torso = b["torso"]
    sep = None
    if b["shoulder_line_deg"] is not None and b["hip_line_deg"] is not None:
        sep = angle_difference_degrees(b["shoulder_line_deg"], b["hip_line_deg"])
        sep = min(sep, 180.0 - sep)  # compare line orientation, not direction
    stance = safe_dist(p(f"{lead}_ankle"), p(f"{trail}_ankle"))
    head_hip = safe_dist(b["nose"], b["hip_mid"])
    return {
        "lead_arm_angle_deg": safe_angle(p(f"{lead}_shoulder"), p(f"{lead}_elbow"),
                                         p(f"{lead}_wrist")),
        "trail_elbow_angle_deg": safe_angle(p(f"{trail}_shoulder"), p(f"{trail}_elbow"),
                                            p(f"{trail}_wrist")),
        "lead_knee_angle_deg": safe_angle(p(f"{lead}_hip"), p(f"{lead}_knee"),
                                          p(f"{lead}_ankle")),
        "trail_knee_angle_deg": safe_angle(p(f"{trail}_hip"), p(f"{trail}_knee"),
                                           p(f"{trail}_ankle")),
        "shoulder_hip_separation_deg": sep,
        "trunk_tilt_deg": b["trunk_tilt_deg"],
        "stance_width_torso": stance / torso if stance and torso else None,
        "head_to_hip_torso": head_hip / torso if head_hip and torso else None,
        "torso_len": torso,
        "shoulder_y": b["shoulder_mid"][1] if b["shoulder_mid"] else None,
    }


def _hands(frame: FramePose):
    return mid(frame.point("left_wrist"), frame.point("right_wrist"))


def _hips(frame: FramePose):
    return mid(frame.point("left_hip"), frame.point("right_hip"))


def build_rows(sequence: PoseSequence, handedness: str = "right") -> list[Row]:
    return _build_rows(
        sequence,
        lambda f: frame_metrics(f, handedness),
        track_points={"hands": _hands, "hips": _hips, "head": lambda f: f.point("nose")},
    )


def detect_reps(rows: list[Row], fps: float) -> list[Rep]:
    """Detect swings from the smoothed hand path."""

    if len(rows) < 10:
        return []
    fps = fps or 30.0
    y = [r.get("hands_y_s") for r in rows]
    spd = [r.get("hands_speed") for r in rows]
    scale = rows[0]["scale"]
    # Range-relative threshold: a percentile breaks when a long, high finish
    # hold fills the top quarter of the samples.
    lo, hi = percentile(y, 0.02), percentile(y, 0.90)
    tops = local_extrema(y, kind="min", threshold=lo + 0.4 * (hi - lo),
                         min_separation=int(1.8 * fps), radius=max(2, int(0.12 * fps)),
                         keep="first")  # the finish often ends higher than the top
    quiet = max(percentile(spd, 0.3), 0.15)
    reps: list[Rep] = []
    for top in tops:
        if reps and top <= reps[-1].phases["finish"].row:
            continue  # still inside the previous swing (e.g. a held finish)
        sh = rows[top].get("shoulder_y")
        if sh is not None and y[top] > sh + 0.35 * scale:
            continue  # hands never got near shoulder height: a waggle, not a swing
        start = max(0, top - int(3.0 * fps))
        i = top
        while i > start and (spd[i] is None or spd[i] > quiet):
            i -= 1
        address = i if i > start else (argmax(y, start, top) or start)
        if rows[top]["time_s"] - rows[address]["time_s"] < 0.3:
            continue
        ay = y[address]
        if ay is None or ay - y[top] < 0.25 * scale:
            continue  # hands did not really rise from address to this "top"
        # A pause at the top is common: the transition starts at the END of the
        # plateau, so move "top" to the last frame still within 8% of the rise.
        plateau = y[top] + 0.08 * (ay - y[top])
        while top + 1 < len(rows) and y[top + 1] is not None and y[top + 1] <= plateau:
            top += 1
        # Impact proxy: hands bottom out on the way down (first low point that
        # gets at least 60% of the way back to address height).
        stop = min(len(rows), top + int(0.7 * fps) + 1)
        depth = y[top] + 0.6 * (ay - y[top])
        impact = None
        for k in range(top + 1, stop):
            nxt = [v for v in y[k + 1: k + 3] if v is not None]
            if y[k] is not None and y[k] >= depth and all(y[k] >= v for v in nxt):
                impact = k
                break
        if impact is None:
            impact = argmax(y, top + 1, stop)
        if impact is None:
            continue
        finish_stop = min(len(rows), impact + int(2.5 * fps))
        finish = None
        for k in range(impact + int(0.25 * fps), finish_stop):
            s, hy, shy = spd[k], y[k], rows[k].get("shoulder_y")
            if s is not None and s <= quiet and hy is not None and (shy is None or hy < shy):
                finish = k
                break
        if finish is None:
            finish = argmin(spd, impact + 1, finish_stop)
            if finish is None:
                finish = min(len(rows) - 1, impact + 1)
        rep = Rep(index=len(reps) + 1, phases={
            "address": mark(rows, "address", address), "top": mark(rows, "top", top),
            "impact": mark(rows, "impact", impact), "finish": mark(rows, "finish", finish)})
        rep.confidence = _confidence(rows, rep)
        reps.append(rep)
    return reps


def _confidence(rows: list[Row], rep: Rep) -> float:
    conf = rep_visibility(rows, rep)
    back = rep.time("top") - rep.time("address")
    down = rep.time("impact") - rep.time("top")
    if not 0.12 <= down <= 0.6:
        conf *= 0.6
        rep.notes.append(f"downswing {down:.2f}s is outside the usual 0.12-0.6s window")
    if not 0.4 <= back <= 2.0:
        conf *= 0.7
        rep.notes.append(f"backswing {back:.2f}s is outside the usual 0.4-2.0s window")
    return conf


def summarize_rep(rows: list[Row], rep: Rep) -> dict[str, Any]:
    def v(phase: str, key: str) -> float | None:
        return value_at(rows, rep, phase, key)

    back = rep.time("top") - rep.time("address")
    down = rep.time("impact") - rep.time("top")
    scale = rows[0]["scale"]
    lo, hi = rep.phases["top"].row, rep.phases["impact"].row
    speeds = [r["hands_speed"] for r in rows[lo: hi + 1] if r.get("hands_speed") is not None]

    def hand_height(phase: str) -> float | None:
        hy, sy = v(phase, "hands_y_s"), v(phase, "shoulder_y")
        return None if hy is None or sy is None else (sy - hy) / scale

    return {
        "index": rep.index,
        "confidence": rep.confidence,
        "source": rep.source,
        "notes": rep.notes,
        "phases": {k: {"frame": m.frame_index, "time_s": m.time_s} for k, m in rep.phases.items()},
        "timing": {
            "backswing_s": back,
            "downswing_s": down,
            "tempo_ratio": back / down if down > 0 else None,
            "total_s": rep.time("finish") - rep.time("address"),
        },
        "address": {
            "lead_knee_angle_deg": v("address", "lead_knee_angle_deg"),
            "trail_knee_angle_deg": v("address", "trail_knee_angle_deg"),
            "trunk_tilt_deg": v("address", "trunk_tilt_deg"),
            "stance_width_torso": v("address", "stance_width_torso"),
        },
        "top": {
            "lead_arm_angle_deg": v("top", "lead_arm_angle_deg"),
            "trail_elbow_angle_deg": v("top", "trail_elbow_angle_deg"),
            "shoulder_hip_separation_deg": v("top", "shoulder_hip_separation_deg"),
            "hand_height_torso": hand_height("top"),
            "hip_sway_torso": drift(rows, rep, "address", "top", "hips", axis="x"),
        },
        "impact": {
            "lead_knee_angle_deg": v("impact", "lead_knee_angle_deg"),
            "head_drift_torso": drift(rows, rep, "address", "impact", "head"),
            "hip_slide_torso": drift(rows, rep, "address", "impact", "hips", axis="x"),
            "peak_hand_speed_torso_s": max(speeds) if speeds else None,
        },
        "finish": {
            "hand_height_torso": hand_height("finish"),
            "lead_knee_angle_deg": v("finish", "lead_knee_angle_deg"),
        },
    }


# Starter reference ranges for 2D single-camera proxies. Tune them to your
# own baseline; docs/metrics.md explains each one.
CHECKS: list[Check] = [
    Check("timing.tempo_ratio", "Tempo (backswing : downswing)", 2.0, 4.0, ":1",
          "Backswing is quick relative to the downswing; try a smoother, longer takeaway.",
          "Downswing is slow relative to the backswing; let the transition accelerate.",
          "Skilled swings commonly cluster around a 3:1 backswing-to-downswing time ratio."),
    Check("top.lead_arm_angle_deg", "Lead arm at top", 145.0, None, "deg",
          "Lead arm is noticeably bent at the top; a wider arc usually adds consistency.",
          "",
          "A fairly straight lead arm keeps the swing radius stable."),
    Check("top.hip_sway_torso", "Hip sway in backswing", None, 0.35, "torso",
          "",
          "Hips slide away from the target in the backswing; rotate around the trail hip instead.",
          "Lateral hip drift moves the low point of the swing and costs strike consistency."),
    Check("impact.head_drift_torso", "Head movement to impact", None, 0.35, "torso",
          "",
          "Head moves a lot between address and impact; keep a steadier centre.",
          "A stable head is a common proxy for a stable swing centre."),
    Check("address.lead_knee_angle_deg", "Knee flex at address", 135.0, 175.0, "deg",
          "Very deep knee flex at address; stand a little taller.",
          "Legs are nearly locked at address; add a little knee flex.",
          "Moderate knee flex gives an athletic, balanced setup."),
]
CONSISTENCY_KEYS = ["timing.tempo_ratio", "timing.backswing_s", "top.lead_arm_angle_deg",
                    "impact.head_drift_torso", "top.hand_height_torso"]


def summarize_sequence(sequence: PoseSequence, handedness: str = "right") -> dict[str, object]:
    """Whole-clip summary (v1 compatible): per-frame metrics plus clip means."""

    per_frame = [
        {"time_s": f.time_s, "phase": f.phase, "metrics": frame_metrics(f, handedness)}
        for f in sequence.frames
    ]
    names = list(per_frame[0]["metrics"]) if per_frame else []
    summary = {}
    for name in names:
        vals = [fr["metrics"][name] for fr in per_frame if fr["metrics"][name] is not None]
        summary[name] = mean(vals) if vals else None
    return {"sport": NAME, "events": PHASES, "frames": per_frame, "summary": summary}
