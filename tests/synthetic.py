"""Synthetic pose sequences with known phase times, for detector tests."""

from __future__ import annotations

import math

from swingform_ai.schema import FramePose, Landmark, PoseSequence

FPS = 30.0
BASE = {  # standing athlete, normalized coords in a square frame
    "nose": (0.50, 0.20), "left_shoulder": (0.56, 0.30), "right_shoulder": (0.44, 0.30),
    "left_elbow": (0.58, 0.42), "right_elbow": (0.42, 0.42),
    "left_wrist": (0.53, 0.55), "right_wrist": (0.47, 0.55),
    "left_hip": (0.54, 0.55), "right_hip": (0.46, 0.55),
    "left_knee": (0.55, 0.72), "right_knee": (0.45, 0.72),
    "left_ankle": (0.56, 0.90), "right_ankle": (0.44, 0.90),
}


def _frame(i: int, overrides: dict[str, tuple[float, float]]) -> FramePose:
    pts = {**BASE, **overrides}
    lms = {n: Landmark(n, x, y, 0.0, 0.95) for n, (x, y) in pts.items()}
    return FramePose(time_s=i / FPS, landmarks=lms, frame_index=i)


def _ease(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


def golf_swings(n_swings: int = 2, back_s: float = 0.9, down_s: float = 0.3,
                pause_s: float = 0.1) -> tuple[PoseSequence, list[dict[str, float]]]:
    """Hands rise from address to top, pause, drop to impact, rise to finish."""

    # finish ends ABOVE the top on purpose: real swings often do, and a detector
    # that keeps "the highest hands" would mistake the finish for the top.
    address_y, top_y, finish_y = 0.55, 0.18, 0.12
    seg = [("quiet", 1.0), ("back", back_s), ("pause", pause_s), ("down", down_s),
           ("follow", 0.35), ("hold", 1.6)]
    truth, frames, t0 = [], [], 0.0
    plan = []
    for _ in range(n_swings):
        marks = {}
        for name, dur in seg:
            plan.append((name, t0, dur))
            if name == "back":
                marks["address"] = t0
            if name == "down":
                marks["top"] = t0
                marks["impact"] = t0 + dur
            if name == "hold":
                marks["finish"] = t0
            t0 += dur
        truth.append(marks)
    total = int(t0 * FPS)
    for i in range(total):
        t = i / FPS
        name, start, dur = next(p for p in plan if p[1] <= t < p[1] + p[2])
        u = _ease((t - start) / dur)
        y = {"quiet": address_y, "back": address_y + (top_y - address_y) * u, "pause": top_y,
             "down": top_y + (address_y - top_y) * u,
             "follow": address_y + (finish_y - address_y) * u, "hold": finish_y}[name]
        x_shift = {"back": -0.15 * u, "pause": -0.15, "down": -0.15 * (1 - u),
                   "follow": 0.15 * u, "hold": 0.15}.get(name, 0.0)
        frames.append(_frame(i, {"left_wrist": (0.53 + x_shift, y),
                                 "right_wrist": (0.47 + x_shift, y + 0.01)}))
    return PoseSequence(frames=frames, fps=FPS, width=1000, height=1000,
                        total_frames=total, source="synthetic"), truth


def basketball_shots(n_shots: int = 2) -> tuple[PoseSequence, list[dict[str, float]]]:
    """Knees bend (dip), then shooting arm extends overhead (release)."""

    frames, truth = [], []
    shot_len = 2.4
    total = int(n_shots * shot_len * FPS + FPS)
    for k in range(n_shots):
        start = 0.5 + k * shot_len
        truth.append({"dip": start + 0.5, "release": start + 0.9})
    for i in range(total):
        t = i / FPS
        ov: dict[str, tuple[float, float]] = {}
        for marks in truth:
            dip, rel = marks["dip"], marks["release"]
            if dip - 0.4 <= t <= rel + 0.3:
                bend = math.exp(-((t - dip) / 0.12) ** 2)  # knees forward at dip
                ov["right_knee"] = (0.45 - 0.10 * bend, 0.72)
                lift = _ease((t - (dip - 0.1)) / (rel - dip + 0.1))
                if t > rel:
                    lift = 1.0
                ov["right_elbow"] = (0.42, 0.42 - 0.27 * lift)
                ov["right_wrist"] = (0.47 - 0.05 * lift, 0.55 - 0.50 * lift)
        frames.append(_frame(i, ov))
    return PoseSequence(frames=frames, fps=FPS, width=1000, height=1000,
                        total_frames=total, source="synthetic"), truth


def badminton_strokes() -> tuple[PoseSequence, list[dict[str, float | str]]]:
    """One overhead (hand peaks above the head, then whips down) and one drive."""

    truth = [{"stroke": "overhead", "contact": 1.5}, {"stroke": "drive", "contact": 3.9}]
    total = int(5.5 * FPS)
    frames = []
    for i in range(total):
        t = i / FPS
        ov: dict[str, tuple[float, float]] = {}
        # overhead: raise 0.9-1.5 s to above the head, whip down by 1.75 s
        if 0.9 <= t <= 1.5:
            u = _ease((t - 0.9) / 0.6)
            ov["right_elbow"] = (0.42, 0.42 - 0.30 * u)
            ov["right_wrist"] = (0.47 - 0.02 * u, 0.55 - 0.48 * u)
        elif 1.5 < t <= 1.75:
            u = (t - 1.5) / 0.25
            ov["right_elbow"] = (0.42, 0.12 + 0.30 * u)
            ov["right_wrist"] = (0.45 + 0.15 * u, 0.07 + 0.55 * u)
        # drive: arm swings fast sideways at chest height around 4.0 s
        # (slow wind-up from rest, fast swing, slow return: no teleporting joints)
        if 3.0 <= t < 3.7:
            u = _ease((t - 3.0) / 0.7)
            ov["right_wrist"] = (0.47 - 0.22 * u, 0.55 - 0.15 * u)
            ov["right_elbow"] = (0.42 - 0.06 * u, 0.42 - 0.02 * u)
        elif 3.7 <= t <= 4.1:
            u = _ease((t - 3.7) / 0.4)
            ov["right_wrist"] = (0.25 + 0.45 * u, 0.40)
            ov["right_elbow"] = (0.36 + 0.10 * u, 0.40)
        elif 4.1 < t <= 5.0:
            u = _ease((t - 4.1) / 0.9)
            ov["right_wrist"] = (0.70 - 0.23 * u, 0.40 + 0.15 * u)
            ov["right_elbow"] = (0.46 - 0.04 * u, 0.40 + 0.02 * u)
        frames.append(_frame(i, ov))
    return PoseSequence(frames=frames, fps=FPS, width=1000, height=1000,
                        total_frames=total, source="synthetic"), truth
