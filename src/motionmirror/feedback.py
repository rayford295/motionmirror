"""Turn per-rep metrics into plain-language, explainable feedback.

Every check is a reference range on one summary metric. Ranges are deliberately
broad *starter* values for single-camera 2D pose proxies: they flag outliers
worth reviewing on video, they are not a substitute for a coach or a launch
monitor. Each finding carries the measured value, the range and the reason, so
a reader can always see why a cue was raised.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any


@dataclass(frozen=True)
class Check:
    key: str            # dotted path into a rep summary, e.g. "top.lead_arm_angle_deg"
    label: str
    low: float | None
    high: float | None
    unit: str
    cue_low: str
    cue_high: str
    why: str


@dataclass(frozen=True)
class Finding:
    key: str
    label: str
    value: float | None
    low: float | None
    high: float | None
    unit: str
    status: str         # "ok", "low", "high", "unknown"
    message: str
    why: str

    def to_mapping(self) -> dict[str, Any]:
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


def lookup(summary: dict[str, Any], dotted: str) -> float | None:
    node: Any = summary
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return float(node) if isinstance(node, (int, float)) else None


def evaluate(summary: dict[str, Any], checks: list[Check]) -> list[Finding]:
    findings: list[Finding] = []
    for c in checks:
        value = lookup(summary, c.key)
        if value is None:
            status, msg = "unknown", "Not measurable in this clip (joint hidden or phase missing)."
        elif c.low is not None and value < c.low:
            status, msg = "low", c.cue_low
        elif c.high is not None and value > c.high:
            status, msg = "high", c.cue_high
        else:
            status, msg = "ok", "Within the reference range."
        findings.append(Finding(c.key, c.label, value, c.low, c.high, c.unit, status, msg, c.why))
    return findings


def consistency(summaries: list[dict[str, Any]], keys: list[str]) -> dict[str, dict[str, float]]:
    """Mean and spread of key metrics across reps (needs at least two reps)."""

    out: dict[str, dict[str, float]] = {}
    for key in keys:
        vals = [v for v in (lookup(s, key) for s in summaries) if v is not None]
        if len(vals) >= 2:
            out[key] = {"mean": mean(vals), "std": pstdev(vals), "n": len(vals),
                        "min": min(vals), "max": max(vals)}
    return out


def score(findings: list[Finding]) -> float | None:
    """Share of measurable checks that are in range, 0..100."""

    measured = [f for f in findings if f.status != "unknown"]
    if not measured:
        return None
    return 100.0 * sum(f.status == "ok" for f in measured) / len(measured)
