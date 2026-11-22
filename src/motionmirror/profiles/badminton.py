"""Badminton stroke profile: racket-arm metrics, stroke detection, feedback.

Phase model per stroke: ``ready`` -> ``backswing`` -> ``contact`` -> ``follow_through``
-> ``recovery``.

* contact        – peak speed of the racket-hand wrist (a pose proxy: the
                   shuttle and racket head are not tracked)
* backswing      – most cocked racket arm (smallest elbow angle) in the 0.6 s
                   before contact
* ready          – stillest racket hand in the 0.8 s before the backswing
* follow_through – racket hand slows below 40% of its peak after contact
* recovery       – hips settle within 1.2 s after contact

Each stroke is classified by where contact happens relative to the body:
``overhead`` (hand above the head), ``drive`` (between hip and head) or
``underhand`` (below the hip). Checks differ by stroke type.
"""

from __future__ import annotations

from statistics import mean
from typing import Any

from motionmirror.feedback import Check
from motionmirror.profiles.base import (
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
from motionmirror.profiles.base import build_rows as _build_rows
from motionmirror.schema import FramePose, PoseSequence
from motionmirror.signal import argmax, argmin, local_extrema, percentile

NAME = "badminton"
PHASES = ["ready", "backswing", "contact", "follow_through", "recovery"]
SIDE_HELP = "Racket hand."


def frame_metrics(frame: FramePose, racket_side: str = "right") -> dict[str, float | None]:
    side = racket_side.lower()
    off = opposite(side)
    p = frame.point
    b = body_frame(frame)
    torso = b["torso"]
    wrist, off_wrist = p(f"{side}_wrist"), p(f"{off}_wrist")
    shoulder_y = b["shoulder_mid"][1] if b["shoulder_mid"] else None
    hip_y = b["hip_mid"][1] if b["hip_mid"] else None

    def above_shoulder(pt):
        if pt is None or shoulder_y is None or not torso:
            return None
        return (shoulder_y - pt[1]) / torso

    stance = safe_dist(p("left_ankle"), p("right_ankle"))
    knees = [safe_angle(p(f"{s}_hip"), p(f"{s}_knee"), p(f"{s}_ankle")) for s in ("left", "right")]
    knees = [k for k in knees if k is not None]
    return {
        "racket_elbow_angle_deg": safe_angle(p(f"{side}_shoulder"), p(f"{side}_elbow"), wrist),
        "racket_shoulder_angle_deg": safe_angle(p(f"{side}_hip"), p(f"{side}_shoulder"),
                                                p(f"{side}_elbow")),
        "racket_hand_height_torso": above_shoulder(wrist),
        "off_hand_height_torso": above_shoulder(off_wrist),
        "below_hip": (wrist[1] > hip_y) if wrist and hip_y is not None else None,
        "head_y": b["nose"][1] if b["nose"] else None,
        "knee_angle_deg": min(knees) if knees else None,
        "stance_width_torso": stance / torso if stance and torso else None,
        "trunk_tilt_deg": b["trunk_tilt_deg"],
        "torso_len": torso,
        "shoulder_y": shoulder_y,
    }


def build_rows(sequence: PoseSequence, racket_side: str = "right") -> list[Row]:
    side = racket_side.lower()
    return _build_rows(
        sequence,
        lambda f: frame_metrics(f, side),
        track_points={
            "wrist": lambda f: f.point(f"{side}_wrist"),
            "hips": lambda f: mid(f.point("left_hip"), f.point("right_hip")),
        },
        smooth=3,  # strokes are fast; keep the speed peak sharp
    )


def stroke_type(rows: list[Row], contact: int) -> str:
    r = rows[contact]
    hand, head, sh = r.get("wrist_y"), r.get("head_y"), r.get("shoulder_y")
    if hand is not None and head is not None and hand < head:
        return "overhead"
    if r.get("below_hip"):
        return "underhand"
    if hand is not None and sh is not None:
        return "drive"
    return "unknown"


def detect_reps(rows: list[Row], fps: float) -> list[Rep]:
    if len(rows) < 10:
        return []
    fps = fps or 30.0
    n = len(rows)
    spd = [r.get("wrist_speed") for r in rows]
    elbow = [r.get("racket_elbow_angle_deg") for r in rows]
    hspd = [r.get("hips_speed") for r in rows]
    peaks = local_extrema(spd, kind="max", threshold=max(2.5, percentile(spd, 0.85)),
                          min_separation=int(0.8 * fps), radius=max(2, int(0.08 * fps)))
    reps: list[Rep] = []
    height = [r.get("racket_hand_height_torso") for r in rows]
    for peak_idx in peaks:
        contact = peak_idx
        # Overheads: the arm keeps accelerating DOWN after the hit, so the speed
        # peak lands in the follow-through. If the hand was above the head just
        # before, contact is the highest-hand frame instead.
        top = argmax(height, peak_idx - int(0.4 * fps), peak_idx + 1)
        if top is not None and height[top] is not None and height[top] > 0.45:
            contact = top
        back = argmin(elbow, contact - int(0.6 * fps), max(contact - int(0.05 * fps), 1))
        if back is None:
            back = max(0, contact - int(0.2 * fps))
        ready = argmin(spd, back - int(0.8 * fps), back + 1)
        if ready is None:
            ready = back
        peak = spd[peak_idx] or 0.0
        contact_for_follow = peak_idx
        follow = None
        for k in range(contact_for_follow + 1, min(n, contact_for_follow + int(0.5 * fps))):
            if spd[k] is not None and spd[k] < 0.4 * peak:
                follow = k
                break
        if follow is None:
            follow = min(n - 1, contact_for_follow + int(0.2 * fps))
        recovery = argmin(hspd, follow + 1, min(n, contact + int(1.2 * fps)))
        if recovery is None:
            recovery = min(n - 1, follow + 1)
        idx = {"ready": ready, "backswing": back, "contact": contact,
               "follow_through": follow, "recovery": recovery}
        rep = Rep(index=len(reps) + 1, phases={k: mark(rows, k, i) for k, i in idx.items()})
        rep.confidence = rep_visibility(rows, rep)
        rep.notes.append(f"stroke type: {stroke_type(rows, contact)}")
        b2c = rep.time("contact") - rep.time("backswing")
        if not 0.05 <= b2c <= 0.6:
            rep.confidence *= 0.7
            rep.notes.append(f"backswing-to-contact {b2c:.2f}s is outside 0.05-0.6s")
        reps.append(rep)
    return reps


def summarize_rep(rows: list[Row], rep: Rep) -> dict[str, Any]:
    def v(phase: str, key: str, radius: int = 1) -> float | None:
        return value_at(rows, rep, phase, key, radius=radius)

    lo, hi = rep.phases["backswing"].row, rep.phases["follow_through"].row  # whole swing
    speeds = [r["wrist_speed"] for r in rows[lo: hi + 1] if r.get("wrist_speed") is not None]
    return {
        "index": rep.index,
        "confidence": rep.confidence,
        "source": rep.source,
        "notes": rep.notes,
        "stroke": stroke_type(rows, rep.phases["contact"].row),
        "phases": {k: {"frame": m.frame_index, "time_s": m.time_s} for k, m in rep.phases.items()},
        "timing": {
            "backswing_to_contact_s": rep.time("contact") - rep.time("backswing"),
            "contact_to_recovery_s": rep.time("recovery") - rep.time("contact"),
        },
        "ready": {
            "knee_angle_deg": v("ready", "knee_angle_deg", 2),
            "stance_width_torso": v("ready", "stance_width_torso", 2),
        },
        "backswing": {
            "racket_elbow_angle_deg": v("backswing", "racket_elbow_angle_deg"),
            "off_hand_height_torso": v("backswing", "off_hand_height_torso"),
        },
        "contact": {
            "racket_elbow_angle_deg": v("contact", "racket_elbow_angle_deg"),
            "racket_hand_height_torso": v("contact", "racket_hand_height_torso"),
            "peak_hand_speed_torso_s": max(speeds) if speeds else None,
            "stance_width_torso": v("contact", "stance_width_torso"),
            "trunk_tilt_deg": v("contact", "trunk_tilt_deg"),
        },
        "recovery": {
            "hip_travel_torso": drift(rows, rep, "contact", "recovery", "hips"),
        },
    }


_READY_KNEE = Check(
    "ready.knee_angle_deg", "Ready-position knee bend", 115.0, 165.0, "deg",
    "Very low ready stance; it can slow your first step.",
    "Standing tall in the ready position; bend the knees to react faster.",
    "A flexed, athletic ready stance shortens the first step to the shuttle.")

CHECKS_BY_STROKE: dict[str, list[Check]] = {
    "overhead": [
        Check("contact.racket_elbow_angle_deg", "Arm extension at contact", 150.0, None, "deg",
              "Hitting with a bent arm; reach up and strike at full extension.", "",
              "Contact at full reach gives the steepest angle and most power overhead."),
        Check("contact.racket_hand_height_torso", "Contact height", 0.8, None, "torso",
              "Contact is low for an overhead; take the shuttle earlier, above the head.", "",
              "The higher the contact point, the more options and the steeper the shot."),
        Check("backswing.off_hand_height_torso", "Non-racket arm raised", 0.0, None, "torso",
              "Non-racket arm stays low; raise it to aim and to balance the rotation.", "",
              "Pointing the free arm at the shuttle helps timing and trunk rotation."),
        _READY_KNEE,
    ],
    "default": [
        Check("timing.backswing_to_contact_s", "Backswing-to-contact time", 0.08, 0.5, "s",
              "Very short swing; check that the racket is prepared early.",
              "Long, slow swing; a compact preparation is easier to time.",
              "Compact, early preparation is a hallmark of consistent drives and lifts."),
        Check("contact.stance_width_torso", "Base width at contact", 0.7, None, "torso",
              "Narrow base at contact; step or lunge into the shot for stability.", "",
              "A wide base keeps balance on fast mid-court and net strokes."),
        _READY_KNEE,
    ],
}
CHECKS: list[Check] = CHECKS_BY_STROKE["overhead"] + CHECKS_BY_STROKE["default"][:2]


def checks_for(summary: dict[str, Any]) -> list[Check]:
    return CHECKS_BY_STROKE.get(summary.get("stroke", ""), CHECKS_BY_STROKE["default"])


CONSISTENCY_KEYS = ["contact.racket_elbow_angle_deg", "contact.peak_hand_speed_torso_s",
                    "timing.backswing_to_contact_s", "ready.knee_angle_deg"]


def summarize_sequence(sequence: PoseSequence, racket_side: str = "right") -> dict[str, object]:
    per_frame = [{"time_s": f.time_s, "metrics": frame_metrics(f, racket_side)}
                 for f in sequence.frames]
    names = list(per_frame[0]["metrics"]) if per_frame else []
    summary = {}
    for name in names:
        vals = [fr["metrics"][name] for fr in per_frame
                if isinstance(fr["metrics"][name], float)]
        summary[name] = mean(vals) if vals else None
    return {"sport": NAME, "phases": PHASES, "frames": per_frame, "summary": summary}



def pick_side(sequence: PoseSequence) -> str:
    """The racket hand moves fastest: compare 90th-percentile wrist speeds."""

    def p90(side: str) -> float:
        rows = build_rows(sequence, side)
        return percentile([r.get("wrist_speed") for r in rows], 0.9)

    return "right" if p90("right") >= p90("left") else "left"
