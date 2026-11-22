"""Basketball jump-shot profile: posture metrics, shot detection, feedback.

Phase model: ``set`` -> ``dip`` -> ``lift`` -> ``release`` -> ``follow_through``
-> ``landing``.

* release        – peak of a release score (shooting wrist above the head plus
                   elbow extension); a pose proxy, not a ball-leaves-hand event
* dip            – deepest knee bend in the 0.9 s before release
* set            – stillest hands in the 0.6 s before the dip
* lift           – fastest shooting-wrist motion between dip and release
* follow_through – wrist highest within 0.45 s after release
* landing        – hips settle within 0.3-1.2 s after release

Make/miss, ball arc and release angle of the ball are out of scope.
"""

from __future__ import annotations

from statistics import mean
from typing import Any

from swingform_ai.feedback import Check
from swingform_ai.profiles.base import (
    Rep,
    Row,
    body_frame,
    drift,
    mark,
    mid,
    opposite,
    rep_visibility,
    safe_angle,
    safe_dist,
    value_at,
)
from swingform_ai.profiles.base import build_rows as _build_rows
from swingform_ai.schema import FramePose, PoseSequence
from swingform_ai.signal import argmax, argmin, local_extrema, moving_average, percentile

NAME = "basketball"
PHASES = ["set", "dip", "lift", "release", "follow_through", "landing"]
SHOT_PHASES = PHASES  # v1 name
SIDE_HELP = "Shooting hand."


def frame_metrics(frame: FramePose, shooting_side: str = "right") -> dict[str, float | None]:
    """Shot-form metrics for one frame (``None`` when a joint is hidden)."""

    side = shooting_side.lower()
    guide = opposite(side)
    p = frame.point
    b = body_frame(frame)
    torso = b["torso"]
    wrist = p(f"{side}_wrist")
    guide_gap = safe_dist(wrist, p(f"{guide}_wrist"))
    above_head = None
    if wrist and b["nose"] and torso:
        above_head = (b["nose"][1] - wrist[1]) / torso
    return {
        "shooting_elbow_angle_deg": safe_angle(p(f"{side}_shoulder"), p(f"{side}_elbow"), wrist),
        "shooting_knee_angle_deg": safe_angle(p(f"{side}_hip"), p(f"{side}_knee"),
                                              p(f"{side}_ankle")),
        "guide_knee_angle_deg": safe_angle(p(f"{guide}_hip"), p(f"{guide}_knee"),
                                           p(f"{guide}_ankle")),
        "wrist_above_head_torso": above_head,
        "guide_hand_gap_torso": guide_gap / torso if guide_gap and torso else None,
        "trunk_tilt_deg": b["trunk_tilt_deg"],
        "torso_len": torso,
        "shoulder_y": b["shoulder_mid"][1] if b["shoulder_mid"] else None,
    }


def build_rows(sequence: PoseSequence, shooting_side: str = "right") -> list[Row]:
    side = shooting_side.lower()
    return _build_rows(
        sequence,
        lambda f: frame_metrics(f, side),
        track_points={
            "wrist": lambda f: f.point(f"{side}_wrist"),
            "hips": lambda f: mid(f.point("left_hip"), f.point("right_hip")),
            "head": lambda f: f.point("nose"),
        },
    )


def _release_score(row: Row) -> float | None:
    above, elbow = row.get("wrist_above_head_torso"), row.get("shooting_elbow_angle_deg")
    if above is None or elbow is None:
        return None
    return above + elbow / 180.0


def detect_reps(rows: list[Row], fps: float) -> list[Rep]:
    if len(rows) < 10:
        return []
    fps = fps or 30.0
    n = len(rows)
    score = moving_average([_release_score(r) for r in rows], 5)
    peaks = local_extrema(score, kind="max", threshold=max(1.0, percentile(score, 0.9)),
                          min_separation=int(1.2 * fps), radius=max(2, int(0.1 * fps)))
    knee = [r.get("shooting_knee_angle_deg") for r in rows]
    wspd = [r.get("wrist_speed") for r in rows]
    wy = [r.get("wrist_y_s") for r in rows]
    hspd = [r.get("hips_speed") for r in rows]
    reps: list[Rep] = []
    for rel in peaks:
        if (rows[rel].get("wrist_above_head_torso") or 0) < 0.05:
            continue
        dip = argmin(knee, rel - int(0.9 * fps), rel - int(0.08 * fps))
        if dip is None:
            continue
        set_ = argmin(wspd, dip - int(0.6 * fps), dip + 1)
        lift = argmax(wspd, dip, rel + 1)
        follow = argmin(wy, rel, min(n, rel + int(0.45 * fps)))
        # A jump shot is airborne ~0.3-0.7 s; look for the hips settling there,
        # not later when the player walks away.
        landing = argmin(hspd, rel + int(0.25 * fps), min(n, rel + int(0.8 * fps)))
        if landing is None or rows[landing]["time_s"] <= rows[rel]["time_s"]:
            continue  # pose lost right after release: not a measurable shot
        if any(rows[k]["frame_index"] - rows[k - 1]["frame_index"] > 0.25 * fps
               for k in range(max(1, dip), landing + 1)):
            continue  # a tracking gap inside the shot makes its phases unreliable
        idx = {"set": set_ if set_ is not None else dip, "dip": dip,
               "lift": lift if lift is not None else rel, "release": rel,
               "follow_through": follow if follow is not None else rel,
               "landing": landing if landing is not None else min(n - 1, rel + 1)}
        rep = Rep(index=len(reps) + 1, phases={k: mark(rows, k, i) for k, i in idx.items()})
        rep.confidence = rep_visibility(rows, rep)
        d2r = rep.time("release") - rep.time("dip")
        if not 0.15 <= d2r <= 0.9:
            rep.confidence *= 0.6
            rep.notes.append(f"dip-to-release {d2r:.2f}s is outside the usual 0.15-0.9s window")
        reps.append(rep)
    return reps


def summarize_rep(rows: list[Row], rep: Rep) -> dict[str, Any]:
    def v(phase: str, key: str) -> float | None:
        return value_at(rows, rep, phase, key)

    return {
        "index": rep.index,
        "confidence": rep.confidence,
        "source": rep.source,
        "notes": rep.notes,
        "phases": {k: {"frame": m.frame_index, "time_s": m.time_s} for k, m in rep.phases.items()},
        "timing": {
            "set_to_release_s": rep.time("release") - rep.time("set") if "set" in rep.phases
            else None,
            "dip_to_release_s": rep.time("release") - rep.time("dip") if "dip" in rep.phases
            else None,
        },
        "set": {"shooting_elbow_angle_deg": v("set", "shooting_elbow_angle_deg")},
        "dip": {
            "shooting_knee_angle_deg": v("dip", "shooting_knee_angle_deg"),
            "guide_knee_angle_deg": v("dip", "guide_knee_angle_deg"),
        },
        "release": {
            "shooting_elbow_angle_deg": v("release", "shooting_elbow_angle_deg"),
            "wrist_above_head_torso": v("release", "wrist_above_head_torso"),
            "guide_hand_gap_torso": v("release", "guide_hand_gap_torso"),
            "trunk_tilt_deg": v("release", "trunk_tilt_deg"),
        },
        "landing": {
            "lateral_drift_torso": drift(rows, rep, "set", "landing", "hips", axis="x")
            if "set" in rep.phases and "landing" in rep.phases else None,
        },
    }


CHECKS: list[Check] = [
    Check("release.shooting_elbow_angle_deg", "Elbow extension at release", 145.0, None, "deg",
          "Shooting arm is still bent at release; finish with a full extension.", "",
          "Full extension at release makes the launch more repeatable."),
    Check("dip.shooting_knee_angle_deg", "Knee bend in the dip", 95.0, 160.0, "deg",
          "Very deep dip; it can slow the shot and change your release height.",
          "Little knee bend; more leg drive takes load off the arms.",
          "Leg drive supplies most of the shot's power."),
    Check("release.wrist_above_head_torso", "Release height", 0.2, None, "torso",
          "Release is close to head height; a higher release is harder to contest.", "",
          "A release well above the head is a common proxy for a high set point."),
    Check("timing.dip_to_release_s", "Dip-to-release time", 0.2, 0.8, "s",
          "Very quick dip-to-release; check that legs and arms are still in sync.",
          "Slow dip-to-release; a smoother one-motion shot is usually more consistent.",
          "Fluid shots move from dip to release in a fraction of a second."),
    Check("landing.lateral_drift_torso", "Sideways drift", None, 0.5, "torso",
          "", "Hips drift sideways between set and landing; aim to land where you took off.",
          "Landing on the take-off spot is a simple balance proxy."),
]
CONSISTENCY_KEYS = ["release.shooting_elbow_angle_deg", "dip.shooting_knee_angle_deg",
                    "timing.dip_to_release_s", "release.wrist_above_head_torso"]


def summarize_sequence(sequence: PoseSequence, shooting_side: str = "right") -> dict[str, object]:
    """Whole-clip summary (v1 compatible): per-frame metrics plus clip means."""

    per_frame = [
        {"time_s": f.time_s, "phase": f.phase, "metrics": frame_metrics(f, shooting_side)}
        for f in sequence.frames
    ]
    names = list(per_frame[0]["metrics"]) if per_frame else []
    summary = {}
    for name in names:
        vals = [fr["metrics"][name] for fr in per_frame if fr["metrics"][name] is not None]
        summary[name] = mean(vals) if vals else None
    return {"sport": NAME, "phases": PHASES, "frames": per_frame, "summary": summary}
