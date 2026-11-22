"""Pose data model shared by every sport profile.

Coordinates follow the MediaPipe convention: ``x`` and ``y`` are normalized to
the image width and height (0..1, origin top-left), ``z`` is relative depth.
Because x and y are normalized by *different* lengths, angles computed on raw
coordinates are distorted for any non-square video. ``PoseSequence.aspect``
records width/height so geometry can be done in an isotropic space via
``FramePose.point``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "swingform-pose-v2"
DEFAULT_MIN_VISIBILITY = 0.3


@dataclass(frozen=True)
class Landmark:
    """One named body landmark."""

    name: str
    x: float
    y: float
    z: float = 0.0
    visibility: float | None = None

    @classmethod
    def from_value(cls, name: str, value: Any) -> Landmark:
        if isinstance(value, dict):
            vis = value.get("visibility")
            return cls(
                name=name,
                x=float(value["x"]),
                y=float(value["y"]),
                z=float(value.get("z", 0.0) or 0.0),
                visibility=None if vis is None else float(vis),
            )
        coords = list(value)
        if len(coords) < 2:
            raise ValueError(f"Landmark {name!r} needs at least x and y.")
        z_value = coords[2] if len(coords) > 2 else 0.0
        visibility = float(coords[3]) if len(coords) > 3 and coords[3] is not None else None
        return cls(name=name, x=float(coords[0]), y=float(coords[1]), z=float(z_value or 0.0),
                   visibility=visibility)

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def to_mapping(self, digits: int = 5) -> dict[str, float]:
        out = {"x": round(self.x, digits), "y": round(self.y, digits), "z": round(self.z, digits)}
        if self.visibility is not None:
            out["visibility"] = round(self.visibility, 3)
        return out


@dataclass(frozen=True)
class FramePose:
    """Pose landmarks for one video frame."""

    time_s: float
    landmarks: dict[str, Landmark]
    phase: str | None = None
    frame_index: int | None = None
    aspect: float = 1.0  # image width / height

    @classmethod
    def from_mapping(cls, payload: dict[str, Any], aspect: float = 1.0) -> FramePose:
        landmarks = {
            name: Landmark.from_value(name, value)
            for name, value in payload.get("landmarks", {}).items()
        }
        return cls(
            time_s=float(payload.get("time_s", 0.0)),
            landmarks=landmarks,
            phase=payload.get("phase"),
            frame_index=payload.get("frame_index"),
            aspect=aspect,
        )

    def require(self, name: str) -> Landmark:
        try:
            return self.landmarks[name]
        except KeyError as exc:
            raise KeyError(f"Missing landmark {name!r} in frame at {self.time_s:.3f}s.") from exc

    def get(self, name: str, min_visibility: float = DEFAULT_MIN_VISIBILITY) -> Landmark | None:
        """Return the landmark if present and visible enough, else ``None``."""

        lm = self.landmarks.get(name)
        if lm is None:
            return None
        if lm.visibility is not None and lm.visibility < min_visibility:
            return None
        return lm

    def point(self, name: str, min_visibility: float = DEFAULT_MIN_VISIBILITY):
        """Return an aspect-corrected image-plane point ``(x*aspect, y, 0)`` or ``None``.

        One unit equals the image height on both axes, so angles and distances
        are geometrically faithful. Depth is dropped on purpose: monocular
        ``z`` is noisy enough to swing joint angles by 20 degrees frame to frame.
        Use :meth:`point3d` when you explicitly want it.
        """

        lm = self.get(name, min_visibility)
        if lm is None:
            return None
        return (lm.x * self.aspect, lm.y, 0.0)

    def point3d(self, name: str, min_visibility: float = DEFAULT_MIN_VISIBILITY):
        lm = self.get(name, min_visibility)
        if lm is None:
            return None
        return (lm.x * self.aspect, lm.y, lm.z * self.aspect)

    def mean_visibility(self) -> float | None:
        vis = [lm.visibility for lm in self.landmarks.values() if lm.visibility is not None]
        return sum(vis) / len(vis) if vis else None

    def to_mapping(self) -> dict[str, Any]:
        out: dict[str, Any] = {"frame_index": self.frame_index, "time_s": round(self.time_s, 4)}
        if self.phase:
            out["phase"] = self.phase
        out["landmarks"] = {name: lm.to_mapping() for name, lm in self.landmarks.items()}
        return out


@dataclass(frozen=True)
class PoseSequence:
    """A time-ordered sequence of frame poses from one clip."""

    frames: list[FramePose]
    source: str | None = None
    fps: float | None = None
    width: int | None = None
    height: int | None = None
    total_frames: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def aspect(self) -> float:
        if self.width and self.height:
            return self.width / self.height
        return 1.0

    def __iter__(self) -> Iterator[FramePose]:
        return iter(self.frames)

    def __len__(self) -> int:
        return len(self.frames)

    @property
    def coverage(self) -> float | None:
        if not self.total_frames:
            return None
        return len(self.frames) / self.total_frames

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> PoseSequence:
        video = payload.get("video", {})
        width = payload.get("width") or video.get("width")
        height = payload.get("height") or video.get("height")
        aspect = (width / height) if width and height else 1.0
        return cls(
            frames=[FramePose.from_mapping(f, aspect) for f in payload.get("frames", [])],
            source=payload.get("source"),
            fps=payload.get("fps") or video.get("fps"),
            width=width,
            height=height,
            total_frames=payload.get("total_frames") or video.get("total_frames"),
            meta=dict(payload.get("meta", {})),
        )

    def with_aspect(self, width: int, height: int) -> PoseSequence:
        aspect = width / height
        return replace(
            self,
            width=width,
            height=height,
            frames=[replace(f, aspect=aspect) for f in self.frames],
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "source": self.source,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "total_frames": self.total_frames,
            "meta": self.meta,
            "frames": [f.to_mapping() for f in self.frames],
        }

    @classmethod
    def load(cls, path: str | Path) -> PoseSequence:
        return cls.from_mapping(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_mapping(), separators=(",", ":")), encoding="utf-8")
        return path
