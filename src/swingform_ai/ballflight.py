"""Golf ball trail detection after impact (visual review aid, needs ``pose`` extra).

Pipeline per swing: skip the frames where the club head still dominates,
find bright moving blobs outside a dilated body mask with dense optical flow,
keep blobs that move in a consistent direction, chain them frame to frame and
RANSAC-fit ``x(t)`` linear / ``y(t)`` quadratic to reject non-ballistic noise.

The result is a pixel-space trail for drawing. It is *not* a ball-flight model:
no speed, launch angle, spin or carry is estimated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from swingform_ai.schema import PoseSequence
from swingform_ai.video import VideoInfo, iter_frames


@dataclass
class BallTrack:
    rep: int
    kind: str  # "detected", "proxy", or "none"
    points: list[dict[str, float]] = field(default_factory=list)


def _params(w: int, h: int) -> dict[str, float]:
    scale = (w * h) / (320 * 568)
    return {
        "bright": 190,
        "flow": max(1.5, 12 * scale ** 0.3 / 8),
        "min_area": max(2.0, 2.0 * scale),
        "max_area": max(300.0, 300.0 * scale),
        "body_px": max(18, int(22 * scale ** 0.5)),
        "max_jump": max(80.0, 80.0 * scale ** 0.5),
    }


def _candidates(video: Path, impact: int, info: VideoInfo, poses: dict[int, object],
                p: dict[str, float], search_s: float = 2.5) -> list[dict[str, float]]:
    import cv2
    import numpy as np

    w, h = info.width, info.height
    start = impact + max(3, round(info.fps * 0.15))
    end = min(info.frame_count - 1, impact + round(search_s * info.fps))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    out: list[dict[str, float]] = []
    dom = [0.0, 0.0, 0]
    prev = None
    for idx, frame in iter_frames(video, start=max(0, start - 1)):
        if idx > end:
            break
        gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (3, 3), 0)
        if prev is not None and idx >= start:
            flow = cv2.calcOpticalFlowFarneback(prev, gray, None, 0.5, 2, 9, 2, 5, 1.1, 0)
            fx, fy = flow[..., 0], flow[..., 1]
            motion = (np.hypot(fx, fy) > p["flow"]).astype(np.uint8) * 255
            _, bright = cv2.threshold(gray, p["bright"], 255, cv2.THRESH_BINARY)
            mask = cv2.bitwise_and(motion, bright)
            pose = poses.get(idx)
            if pose is not None:
                body = np.zeros((h, w), np.uint8)
                for lm in pose.landmarks.values():
                    cv2.circle(body, (int(lm.x * w), int(lm.y * h)), int(p["body_px"]), 255, -1)
                mask = cv2.bitwise_and(mask, cv2.bitwise_not(body))
            mask = cv2.morphologyEx(cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel),
                                    cv2.MORPH_DILATE, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                m = cv2.moments(cnt)
                if not (p["min_area"] <= area <= p["max_area"]) or m["m00"] <= 0:
                    continue
                x0, y0, bw, bh = cv2.boundingRect(cnt)
                dx = float(fx[y0:y0 + bh, x0:x0 + bw].mean())
                dy = float(fy[y0:y0 + bh, x0:x0 + bw].mean())
                if dom[2] >= 3:
                    norm = (dom[0] ** 2 + dom[1] ** 2) ** 0.5 or 1.0
                    blen = (dx * dx + dy * dy) ** 0.5
                    if blen > 0.1 and (dx * dom[0] + dy * dom[1]) / (norm * blen) < 0.26:
                        continue  # moving against the ball's direction: club or body
                elif dom[2] < 6:
                    dom[0] += dx
                    dom[1] += dy
                    dom[2] += 1
                out.append({"frame_index": idx, "x": m["m10"] / m["m00"],
                            "y": m["m01"] / m["m00"], "area": area})
        prev = gray
    return out


def _chain(cands: list[dict[str, float]], launch: tuple[float, float] | None,
           max_jump: float) -> list[dict[str, float]]:
    by_frame: dict[int, list[dict[str, float]]] = {}
    for c in cands:
        by_frame.setdefault(int(c["frame_index"]), []).append(c)
    if not by_frame:
        return []
    frames = sorted(by_frame)
    first = by_frame[frames[0]]
    if launch:
        seed = min(first, key=lambda c: (c["x"] - launch[0]) ** 2 + (c["y"] - launch[1]) ** 2)
    else:
        seed = min(first, key=lambda c: c["area"])
    track = [seed]
    for fi in frames[1:]:
        last = track[-1]
        best = min(by_frame[fi], key=lambda c: (c["x"] - last["x"]) ** 2 + (c["y"] - last["y"]) ** 2)
        gap = fi - last["frame_index"]
        if ((best["x"] - last["x"]) ** 2 + (best["y"] - last["y"]) ** 2) ** 0.5 <= max_jump * gap:
            track.append(best)
    return track


def _ransac(track: list[dict[str, float]], thresh: float = 12.0, iters: int = 80):
    import numpy as np

    if len(track) < 4:
        return track
    t = np.array([p["frame_index"] for p in track], float)
    x = np.array([p["x"] for p in track], float)
    y = np.array([p["y"] for p in track], float)
    rng = np.random.default_rng(42)
    best: list[int] = []
    for _ in range(iters):
        idx = rng.choice(len(t), size=3, replace=False)
        if len(set(t[idx])) < 3:
            continue
        cy, cx = np.polyfit(t[idx], y[idx], 2), np.polyfit(t[idx], x[idx], 1)
        resid = np.hypot(x - np.polyval(cx, t), y - np.polyval(cy, t))
        inliers = list(np.where(resid < thresh)[0])
        if len(inliers) > len(best):
            best = inliers
    return [track[i] for i in sorted(best)] if len(best) >= 3 else track


def _plausible(track: list[dict[str, float]], w: int) -> bool:
    """Accept only tracks that look like a struck ball: enough points, real
    travel, and rising in the image (y decreasing) over the first half."""

    if len(track) < 6:
        return False
    dx, dy = track[-1]["x"] - track[0]["x"], track[-1]["y"] - track[0]["y"]
    half = track[len(track) // 2]
    rises = half["y"] < track[0]["y"] - 0.02 * w
    return (dx * dx + dy * dy) ** 0.5 > 0.10 * w and rises


def _proxy(launch: tuple[float, float], impact: int, info: VideoInfo, direction: int):
    lx, ly = launch
    w, h = info.width, info.height
    end_x = min(w - 1.0, max(0.0, lx + direction * 0.42 * w))
    cx, cy, end_y = (lx + end_x) / 2, ly - 0.36 * h, ly - 0.18 * h
    frames = list(range(impact, impact + round(1.3 * info.fps) + 1, max(1, round(info.fps / 20))))
    pts = []
    for k, fi in enumerate(frames):
        t = k / max(1, len(frames) - 1)
        pts.append({"frame_index": fi,
                    "x": (1 - t) ** 2 * lx + 2 * (1 - t) * t * cx + t * t * end_x,
                    "y": (1 - t) ** 2 * ly + 2 * (1 - t) * t * cy + t * t * end_y})
    return pts


def track_balls(video: str | Path, sequence: PoseSequence, impacts: list[tuple[int, int]],
                info: VideoInfo, *, allow_proxy: bool = False, direction: int = 1) -> list[BallTrack]:
    """Return one :class:`BallTrack` per ``(rep_index, impact_frame)``."""

    poses = {f.frame_index: f for f in sequence.frames}
    p = _params(info.width, info.height)
    tracks: list[BallTrack] = []
    for rep, impact in impacts:
        pose = poses.get(impact)
        launch = None
        if pose is not None:
            pts = [pose.landmarks.get(n) for n in ("left_wrist", "right_wrist")]
            pts = [q for q in pts if q is not None]
            if pts:
                launch = (sum(q.x for q in pts) / len(pts) * info.width,
                          sum(q.y for q in pts) / len(pts) * info.height)
        track = _ransac(_chain(_candidates(Path(video), impact, info, poses, p), launch,
                               p["max_jump"]))
        if _plausible(track, info.width):
            tracks.append(BallTrack(rep, "detected", track))
        elif allow_proxy and launch is not None:
            tracks.append(BallTrack(rep, "proxy", _proxy(launch, impact, info, direction)))
        else:
            tracks.append(BallTrack(rep, "none"))
    return tracks
