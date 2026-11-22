"""Dependency-free 1-D signal helpers for metric time series.

Missing samples are represented as ``None`` throughout; helpers either skip or
interpolate them so a few dropped pose frames never crash an analysis.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import hypot, isfinite

Series = Sequence[float | None]


def _valid(value: float | None) -> bool:
    return value is not None and isfinite(value)


def fill_gaps(values: Series, max_gap: int | None = None) -> list[float | None]:
    """Linearly interpolate interior ``None`` runs; hold edges at nearest value.

    Runs longer than ``max_gap`` are left as ``None``.
    """

    out: list[float | None] = [v if _valid(v) else None for v in values]
    known = [i for i, v in enumerate(out) if v is not None]
    if not known:
        return out
    first, last = known[0], known[-1]
    for i in range(first):
        out[i] = out[first]
    for i in range(last + 1, len(out)):
        out[i] = out[last]
    for a, b in zip(known, known[1:]):
        gap = b - a - 1
        if gap <= 0 or (max_gap is not None and gap > max_gap):
            continue
        va, vb = out[a], out[b]
        for k in range(1, gap + 1):
            out[a + k] = va + (vb - va) * k / (gap + 1)  # type: ignore[operator]
    return out


def moving_average(values: Series, window: int = 5) -> list[float | None]:
    """Centered moving average that ignores ``None`` samples."""

    if window <= 1:
        return list(values)
    half = window // 2
    out: list[float | None] = []
    for i in range(len(values)):
        chunk = [v for v in values[max(0, i - half): i + half + 1] if _valid(v)]
        out.append(sum(chunk) / len(chunk) if chunk else None)
    return out


def percentile(values: Series, q: float) -> float:
    """Nearest-rank percentile with ``q`` in [0, 1]; ignores ``None``."""

    data = sorted(v for v in values if _valid(v))
    if not data:
        return 0.0
    idx = min(len(data) - 1, max(0, round(q * (len(data) - 1))))
    return data[idx]


def speed_2d(xs: Series, ys: Series, times: Sequence[float]) -> list[float | None]:
    """Central-difference planar speed (units per second)."""

    n = len(times)
    out: list[float | None] = [None] * n
    for i in range(n):
        a, b = max(0, i - 1), min(n - 1, i + 1)
        if a == b or not all(_valid(v) for v in (xs[a], xs[b], ys[a], ys[b])):
            continue
        dt = times[b] - times[a]
        if dt > 0:
            out[i] = hypot(xs[b] - xs[a], ys[b] - ys[a]) / dt  # type: ignore[operator]
    return out


def argmin(values: Series, start: int = 0, stop: int | None = None) -> int | None:
    stop = len(values) if stop is None else min(stop, len(values))
    best: int | None = None
    for i in range(max(0, start), stop):
        v = values[i]
        if _valid(v) and (best is None or v < values[best]):  # type: ignore[operator]
            best = i
    return best


def argmax(values: Series, start: int = 0, stop: int | None = None) -> int | None:
    stop = len(values) if stop is None else min(stop, len(values))
    best: int | None = None
    for i in range(max(0, start), stop):
        v = values[i]
        if _valid(v) and (best is None or v > values[best]):  # type: ignore[operator]
            best = i
    return best


def local_extrema(
    values: Series,
    *,
    kind: str,
    threshold: float,
    min_separation: int,
    radius: int = 2,
    keep: str = "extreme",
) -> list[int]:
    """Indices of local minima (``kind='min'``) below / maxima above ``threshold``.

    Peaks closer than ``min_separation`` samples are merged, keeping the more
    extreme one (``keep="extreme"``) or the earlier one (``keep="first"``).
    """

    if kind not in ("min", "max"):
        raise ValueError("kind must be 'min' or 'max'")
    better = (lambda a, b: a < b) if kind == "min" else (lambda a, b: a > b)
    passes = (lambda v: v <= threshold) if kind == "min" else (lambda v: v >= threshold)
    peaks: list[int] = []
    for i, v in enumerate(values):
        if not _valid(v) or not passes(v):
            continue
        window = [w for w in values[max(0, i - radius): i + radius + 1] if _valid(w)]
        if any(better(w, v) for w in window):
            continue
        if peaks and i - peaks[-1] < min_separation:
            if keep == "extreme" and better(v, values[peaks[-1]]):
                peaks[-1] = i
        else:
            peaks.append(i)
    return peaks
