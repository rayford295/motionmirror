"""Video I/O and MediaPipe pose extraction (needs the ``pose`` extra)."""

from __future__ import annotations

import os
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from swingform_ai.schema import FramePose, Landmark, PoseSequence

MODEL_URLS = {
    variant: (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        f"pose_landmarker_{variant}/float16/latest/pose_landmarker_{variant}.task"
    )
    for variant in ("lite", "full", "heavy")
}
DEFAULT_MODEL_DIR = Path.home() / ".cache" / "swingform-ai"

MP_LANDMARK_NAMES = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner", "right_eye",
    "right_eye_outer", "left_ear", "right_ear", "mouth_left", "mouth_right", "left_shoulder",
    "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist", "left_pinky",
    "right_pinky", "left_index", "right_index", "left_thumb", "right_thumb", "left_hip",
    "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle", "left_heel",
    "right_heel", "left_foot_index", "right_foot_index",
]


def _cv2():
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - depends on extras
        raise SystemExit('Video features need extras: pip install "swingform-ai[pose]"') from exc
    return cv2


@dataclass(frozen=True)
class VideoInfo:
    fps: float
    frame_count: int
    width: int
    height: int

    @property
    def duration_s(self) -> float:
        return self.frame_count / self.fps if self.fps else 0.0


def read_video_info(path: str | Path) -> VideoInfo:
    cv2 = _cv2()
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {path}")
    info = VideoInfo(
        fps=float(cap.get(cv2.CAP_PROP_FPS)) or 30.0,
        frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    )
    cap.release()
    return info


def iter_frames(path: str | Path, start: int = 0) -> Iterator[tuple[int, object]]:
    cv2 = _cv2()
    cap = cv2.VideoCapture(str(path))
    if start:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    idx = start
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            yield idx, frame
            idx += 1
    finally:
        cap.release()


def read_frame(path: str | Path, index: int):
    for _, frame in iter_frames(path, start=index):
        return frame
    return None


def ensure_model(model: str | Path = "full") -> Path:
    """Return a local model path, downloading ``lite``/``full``/``heavy`` on demand."""

    if str(model) in MODEL_URLS:
        path = DEFAULT_MODEL_DIR / f"pose_landmarker_{model}.task"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            print(f"Downloading MediaPipe pose model ({model}) to {path} ...")
            urllib.request.urlretrieve(MODEL_URLS[str(model)], path)
        return path
    path = Path(model)
    if not path.exists():
        raise FileNotFoundError(f"Pose model not found: {path}")
    return path


def extract_pose(
    video: str | Path,
    model: str | Path = "full",
    *,
    min_confidence: float = 0.4,
    roi: str = "auto",
    progress: Callable[[int, int], None] | None = None,
) -> PoseSequence:
    """Run MediaPipe Pose Landmarker over every frame of a video.

    ``roi="auto"`` adds a second, zoomed pass when the athlete is small in the
    frame (median body height under 35% of the image): pass one locates the
    person, pass two runs pose on a smoothed, upscaled crop around them and maps
    landmarks back to full-frame coordinates. ``roi="on"``/``"off"`` force it.
    When several people are visible, the one continuing the previous track
    (largest at the start) is kept.
    """

    info = read_video_info(video)
    frames = _run_pose(video, info, model, min_confidence, None, progress)
    used_roi = False
    heights = sorted(_bbox(f)[3] for f in frames) if frames else []
    small = bool(heights) and heights[len(heights) // 2] < 0.35
    if roi == "on" or (roi == "auto" and small):
        crops = _crop_track(frames, info)
        if crops:
            frames = _run_pose(video, info, model, min_confidence, crops, progress)
            used_roi = True
    backend = f"mediapipe-pose-landmarker-{model}" if str(model) in MODEL_URLS \
        else "mediapipe-pose-landmarker"
    return PoseSequence(
        frames=frames, source=Path(video).name, fps=info.fps, width=info.width,
        height=info.height, total_frames=info.frame_count,
        meta={"backend": backend, "roi_zoom": used_roi},
    )


def _bbox(frame: FramePose, min_vis: float = 0.3) -> tuple[float, float, float, float]:
    """(cx, cy, w, h) of visible landmarks in normalized coordinates."""

    pts = [lm for lm in frame.landmarks.values()
           if lm.visibility is None or lm.visibility >= min_vis] or list(frame.landmarks.values())
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs), max(ys) - min(ys))


def _crop_track(frames: list[FramePose], info: VideoInfo) -> dict[int, tuple[int, int, int, int]]:
    """Smoothed square crop (pixels) around the athlete for every frame."""

    from swingform_ai.signal import fill_gaps, moving_average

    n = info.frame_count
    cx: list[float | None] = [None] * n
    cy: list[float | None] = [None] * n
    hh: list[float | None] = [None] * n
    for f in frames:
        if f.frame_index is not None and f.frame_index < n:
            bx, by, bw, bh = _bbox(f)
            cx[f.frame_index] = bx * info.width
            cy[f.frame_index] = by * info.height
            hh[f.frame_index] = max(bw * info.width, bh * info.height)
    win = max(3, int(info.fps * 0.3)) | 1
    cx, cy, hh = (moving_average(fill_gaps(s), win) for s in (cx, cy, hh))
    crops = {}
    for i in range(n):
        if cx[i] is None:
            continue
        side = int(min(max(hh[i] * 1.9, 256), info.width, info.height))
        x0 = int(min(max(cx[i] - side / 2, 0), info.width - side))
        y0 = int(min(max(cy[i] - side / 2, 0), info.height - side))
        crops[i] = (x0, y0, side, side)
    return crops


def _run_pose(video, info: VideoInfo, model, min_confidence: float,
              crops: dict[int, tuple[int, int, int, int]] | None,
              progress: Callable[[int, int], None] | None) -> list[FramePose]:
    cv2 = _cv2()
    os.environ.setdefault("GLOG_minloglevel", "2")  # silence MediaPipe/TFLite chatter
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(ensure_model(model))),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1 if crops else 3,
        min_pose_detection_confidence=min_confidence,
        min_pose_presence_confidence=min_confidence,
        min_tracking_confidence=min_confidence,
    )
    aspect = info.width / info.height if info.height else 1.0
    frames: list[FramePose] = []
    last: tuple[float, float, float, float] | None = None
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        for idx, frame in iter_frames(video):
            x0, y0, cw, ch = 0, 0, info.width, info.height
            img = frame
            if crops is not None:
                if idx not in crops:
                    continue
                x0, y0, cw, ch = crops[idx]
                img = cv2.resize(frame[y0:y0 + ch, x0:x0 + cw], (640, 640),
                                 interpolation=cv2.INTER_CUBIC)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(image, int(round(idx / info.fps * 1000)))
            candidates = []
            for pose in result.pose_landmarks or []:
                named = {
                    name: Landmark(name, (x0 + float(lm.x) * cw) / info.width,
                                   (y0 + float(lm.y) * ch) / info.height,
                                   float(lm.z) * cw / info.width,
                                   float(getattr(lm, "visibility", 0.0) or 0.0))
                    for name, lm in zip(MP_LANDMARK_NAMES, pose)
                }
                candidates.append(FramePose(time_s=idx / info.fps, landmarks=named,
                                            frame_index=idx, aspect=aspect))
            if candidates:
                if last is None:
                    best = max(candidates, key=lambda f: _bbox(f)[3])  # largest person
                else:
                    best = min(candidates, key=lambda f: abs(_bbox(f)[0] - last[0])
                               + abs(_bbox(f)[1] - last[1]) + abs(_bbox(f)[3] - last[3]))
                last = _bbox(best)
                frames.append(best)
            if progress and idx % 15 == 0:
                progress(idx, info.frame_count)
    return frames
