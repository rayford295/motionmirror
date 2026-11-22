"""Review visuals: overlay video, keypose sheet, metric timeline (``pose`` extra)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from swingform_ai.schema import FramePose
from swingform_ai.video import iter_frames, read_video_info

if TYPE_CHECKING:  # pragma: no cover
    from swingform_ai.analysis import Analysis
    from swingform_ai.ballflight import BallTrack

EDGES = {
    "torso": [("left_shoulder", "right_shoulder"), ("left_shoulder", "left_hip"),
              ("right_shoulder", "right_hip"), ("left_hip", "right_hip")],
    "arms": [("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
             ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist")],
    "legs": [("left_hip", "left_knee"), ("left_knee", "left_ankle"),
             ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
             ("left_ankle", "left_foot_index"), ("right_ankle", "right_foot_index")],
}
GROUP_BGR = {"torso": (255, 214, 64), "arms": (64, 196, 255), "legs": (110, 230, 90)}
PHASE_BGR = [(180, 180, 180), (90, 210, 160), (60, 120, 240), (210, 90, 210),
             (60, 200, 240), (200, 160, 60)]
LIVE_METRICS = {
    "golf": [("lead_arm_angle_deg", "lead arm"), ("lead_knee_angle_deg", "lead knee")],
    "basketball": [("shooting_elbow_angle_deg", "elbow"), ("shooting_knee_angle_deg", "knee")],
    "badminton": [("racket_elbow_angle_deg", "racket arm"), ("knee_angle_deg", "knee")],
}


def _px(frame_pose: FramePose, name: str, w: int, h: int, min_vis: float = 0.3):
    lm = frame_pose.get(name, min_vis)
    return None if lm is None else (int(lm.x * w), int(lm.y * h))


def draw_skeleton(img, pose: FramePose, *, thickness: int | None = None, alpha_color=None) -> None:
    import cv2

    h, w = img.shape[:2]
    t = thickness or max(2, round(min(w, h) / 220))
    for group, edges in EDGES.items():
        color = alpha_color or GROUP_BGR[group]
        for a, b in edges:
            pa, pb = _px(pose, a, w, h), _px(pose, b, w, h)
            if pa and pb:
                cv2.line(img, pa, pb, color, t, cv2.LINE_AA)
    if alpha_color:
        return
    for name in ("nose", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
                 "left_wrist", "right_wrist", "left_hip", "right_hip", "left_knee",
                 "right_knee", "left_ankle", "right_ankle"):
        pt = _px(pose, name, w, h)
        if pt:
            cv2.circle(img, pt, t + 2, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(img, pt, t + 2, (30, 30, 30), 1, cv2.LINE_AA)


def _text(img, text, org, scale, color, thick=1) -> None:
    import cv2

    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 2, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def draw_hud(img, time_s: float, label: str | None, color, metrics: list[str]) -> None:
    import cv2

    h, w = img.shape[:2]
    s = max(0.45, min(w, h) / 700)
    bar = int(30 * s / 0.6)
    over = img.copy()
    cv2.rectangle(over, (0, 0), (w, bar), (12, 12, 12), -1)
    cv2.addWeighted(over, 0.6, img, 0.4, 0, dst=img)
    _text(img, f"{time_s:5.2f}s", (8, int(bar * 0.7)), s, (225, 225, 225))
    if label:
        tw = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, s, 2)[0][0]
        _text(img, label, (w - tw - 10, int(bar * 0.7)), s, color, 2)
        cv2.rectangle(img, (0, bar), (5, h), color, -1)
    for i, line in enumerate(metrics):
        _text(img, line, (10, bar + int((i + 1) * 26 * s / 0.6)), s * 0.85, (235, 235, 235))


def draw_trail(img, points: list[dict[str, float]], frame_index: int, dashed: bool) -> None:
    import cv2

    pts = [(int(p["x"]), int(p["y"])) for p in points if p["frame_index"] <= frame_index]
    if len(pts) < 2 or frame_index - points[0]["frame_index"] > 75:
        return
    for k, (a, b) in enumerate(zip(pts, pts[1:])):
        if dashed and k % 2:
            continue
        for thick, color in ((8, (20, 100, 255)), (4, (60, 210, 255)), (1, (255, 255, 255))):
            cv2.line(img, a, b, color, thick, cv2.LINE_AA)


def open_writer(path: Path, fps: float, width: int, height: int):
    """Prefer H.264 (plays in browsers and on GitHub); fall back to MPEG-4 Part 2."""

    import cv2

    for codec in ("avc1", "mp4v"):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), fps, (width, height))
        if writer.isOpened():
            return writer
        writer.release()
    raise RuntimeError(f"Could not open a video writer for {path}")


def render_overlay(analysis: Analysis, video: str | Path, output: str | Path,
                   tracks: list[BallTrack] | None = None, ghost: int = 4,
                   hud: bool = True) -> Path:
    import cv2

    info = read_video_info(video)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = open_writer(output, info.fps, info.width, info.height)
    poses = {f.frame_index: f for f in analysis.sequence.frames}
    rows = {r["frame_index"]: r for r in analysis.rows}
    phases = analysis.phases
    labels: dict[int, tuple[str, tuple[int, int, int]]] = {}
    for rep in analysis.reps:
        for m in rep.phases.values():
            color = PHASE_BGR[phases.index(m.name) % len(PHASE_BGR)]
            labels[m.frame_index] = (f"#{rep.index} {m.name.replace('_', ' ').upper()}", color)
    live = LIVE_METRICS.get(analysis.sport, [])
    active, hold, history = None, 0, []
    for idx, frame in iter_frames(video):
        if idx in labels:
            active, hold = labels[idx], int(info.fps * 0.9)
        pose = poses.get(idx)
        if pose is not None:
            for k, past in enumerate(history[-ghost:]):
                over = frame.copy()
                draw_skeleton(over, past, thickness=1, alpha_color=(200, 170, 120))
                a = 0.10 + 0.05 * k
                cv2.addWeighted(over, a, frame, 1 - a, 0, dst=frame)
            draw_skeleton(frame, pose)
            history = (history + [pose])[-ghost:]
        for tr in tracks or []:
            if tr.points:
                draw_trail(frame, tr.points, idx, dashed=tr.kind == "proxy")
        row = rows.get(idx, {})
        lines = [f"{name} {row[key]:.0f} deg" for key, name in live if row.get(key) is not None]
        if hud:
            draw_hud(frame, idx / info.fps, active[0] if hold > 0 and active else None,
                     active[1] if active else (255, 255, 255), lines)
        hold -= 1
        writer.write(frame)
    writer.release()
    return output


def keypose_sheet(analysis: Analysis, video: str | Path, output: str | Path,
                  tile_h: int = 360) -> Path | None:
    """One row per rep, one tile per phase, real frames with skeleton."""

    import cv2
    import numpy as np

    if not analysis.reps:
        return None
    poses = {f.frame_index: f for f in analysis.sequence.frames}
    wanted = {m.frame_index for rep in analysis.reps for m in rep.phases.values()}
    frames = {i: f for i, f in iter_frames(video) if i in wanted}
    rows_img = []
    for rep in analysis.reps[:6]:
        tiles = []
        for name in analysis.phases:
            m = rep.phases.get(name)
            img = frames.get(m.frame_index) if m else None
            if img is None:
                continue
            img = img.copy()
            if m.frame_index in poses:
                draw_skeleton(img, poses[m.frame_index])
            scale = tile_h / img.shape[0]
            img = cv2.resize(img, (int(img.shape[1] * scale), tile_h))
            _text(img, f"#{rep.index} {name.replace('_', ' ')}", (8, 24), 0.6, (255, 255, 255), 2)
            _text(img, f"{m.time_s:.2f}s", (8, tile_h - 10), 0.5, (220, 220, 220))
            tiles.append(img)
        if tiles:
            rows_img.append(np.hstack(tiles))
    if not rows_img:
        return None
    width = max(r.shape[1] for r in rows_img)
    rows_img = [np.pad(r, ((0, 0), (0, width - r.shape[1]), (0, 0))) for r in rows_img]
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), np.vstack(rows_img), [cv2.IMWRITE_JPEG_QUALITY, 88])
    return output


TIMELINE_KEYS = {
    "golf": [("hands_y_s", "hand height (up = higher)", True),
             ("hands_speed", "hand speed (torso/s)", False),
             ("lead_arm_angle_deg", "lead arm angle (deg)", False)],
    "basketball": [("wrist_above_head_torso", "wrist above head (torso)", False),
                   ("shooting_elbow_angle_deg", "elbow angle (deg)", False),
                   ("shooting_knee_angle_deg", "knee angle (deg)", False)],
    "badminton": [("wrist_speed", "racket-hand speed (torso/s)", False),
                  ("racket_hand_height_torso", "racket hand above shoulder (torso)", False),
                  ("racket_elbow_angle_deg", "racket elbow angle (deg)", False)],
}


def timeline_plot(analysis: Analysis, output: str | Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = TIMELINE_KEYS[analysis.sport]
    t = [r["time_s"] for r in analysis.rows]
    fig, axes = plt.subplots(len(keys), 1, figsize=(10, 2.2 * len(keys)), sharex=True)
    phase_colors = ["#8a8a8a", "#2a9d78", "#e4572e", "#8e44ad", "#d4a017", "#3b6fb6"]
    for ax, (key, label, invert) in zip(axes, keys):
        vals = [r.get(key) for r in analysis.rows]
        ax.plot(t, [v if v is not None else float("nan") for v in vals], color="#1d3557", lw=1.4)
        ax.set_ylabel(label, fontsize=8)
        ax.grid(alpha=0.25)
        if invert:
            ax.invert_yaxis()
        for rep in analysis.reps:
            for m in rep.phases.values():
                c = phase_colors[analysis.phases.index(m.name) % len(phase_colors)]
                ax.axvline(m.time_s, color=c, lw=1, alpha=0.8)
    for i, name in enumerate(analysis.phases):
        axes[0].plot([], [], color=phase_colors[i % len(phase_colors)], label=name)
    axes[0].legend(ncol=len(analysis.phases), fontsize=7, loc="upper right", frameon=False)
    axes[-1].set_xlabel("time (s)")
    fig.suptitle(f"{analysis.sport} timeline - {len(analysis.reps)} rep(s)", fontsize=10)
    fig.tight_layout()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=130)
    plt.close(fig)
    return output
