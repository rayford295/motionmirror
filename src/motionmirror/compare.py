"""Cross-session comparison of exported summary.json files.

This is the "compare Yifan against Yifan" building block: given two session
outputs of the same sport (v2 ``report.json`` or v1 ``summary.json``), extract
per-event metric records and produce aligned comparison rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

GOLF_METRICS = [
    ("tempo_ratio", "Tempo ratio (backswing/downswing)", ""),
    ("backswing_time_s", "Backswing time", "s"),
    ("downswing_time_s", "Downswing time", "s"),
    ("top_lead_arm_angle_deg", "Lead arm angle at top", "deg"),
    ("top_shoulder_hip_separation_deg", "Shoulder-hip separation at top", "deg"),
    ("impact_head_drift", "Head drift at impact", ""),
    ("address_stance_width", "Stance width at address", ""),
]

BASKETBALL_METRICS = [
    ("set_to_release_s", "Set-to-release time", "s"),
    ("lift_to_release_s", "Lift-to-release time", "s"),
    ("release_score", "Release-form score", ""),
]


@dataclass(frozen=True)
class ComparisonRow:
    key: str
    label: str
    unit: str
    values_a: list[float]
    values_b: list[float]

    @property
    def mean_a(self) -> float:
        return mean(self.values_a)

    @property
    def mean_b(self) -> float:
        return mean(self.values_b)

    @property
    def delta(self) -> float:
        return self.mean_b - self.mean_a


# v2 report.json metrics: (dotted key in a rep summary, label, unit)
REPORT_METRICS = {
    "golf": [
        ("timing.tempo_ratio", "Tempo ratio (backswing/downswing)", ""),
        ("timing.backswing_s", "Backswing time", "s"),
        ("timing.downswing_s", "Downswing time", "s"),
        ("top.lead_arm_angle_deg", "Lead arm angle at top", "deg"),
        ("top.hip_sway_torso", "Hip sway in backswing", "torso"),
        ("impact.head_drift_torso", "Head drift to impact", "torso"),
        ("impact.peak_hand_speed_torso_s", "Peak hand speed", "torso/s"),
    ],
    "basketball": [
        ("release.shooting_elbow_angle_deg", "Elbow extension at release", "deg"),
        ("dip.shooting_knee_angle_deg", "Knee bend in the dip", "deg"),
        ("release.wrist_above_head_torso", "Release height above head", "torso"),
        ("timing.dip_to_release_s", "Dip-to-release time", "s"),
        ("timing.set_to_release_s", "Set-to-release time", "s"),
    ],
    "badminton": [
        ("contact.racket_elbow_angle_deg", "Arm extension at contact", "deg"),
        ("contact.racket_hand_height_torso", "Contact height", "torso"),
        ("contact.peak_hand_speed_torso_s", "Peak racket-hand speed", "torso/s"),
        ("timing.backswing_to_contact_s", "Backswing-to-contact time", "s"),
        ("ready.knee_angle_deg", "Ready-position knee bend", "deg"),
    ],
}


def report_records(report: dict[str, Any]) -> list[dict[str, float]]:
    """Flatten each rep of a v2 report.json into dotted-key metric records."""

    records = []
    for rep in report.get("reps", []):
        record: dict[str, float] = {}
        for section, values in rep.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        record[f"{section}.{key}"] = float(value)
        records.append(record)
    return records


def detect_sport(summary: dict[str, Any]) -> str:
    if "reps" in summary and "sport" in summary:
        return summary["sport"]
    if "swing_summaries" in summary:
        return "golf"
    if "shot_events" in summary:
        return "basketball"
    raise ValueError("Summary has neither swing_summaries nor shot_events.")


def golf_records(summary: dict[str, Any]) -> list[dict[str, float]]:
    records = []
    for swing in summary.get("swing_summaries", []):
        record = {
            "tempo_ratio": swing.get("tempo_ratio"),
            "backswing_time_s": swing.get("backswing_time_s"),
            "downswing_time_s": swing.get("downswing_time_s"),
            "top_lead_arm_angle_deg": swing.get("top", {}).get("lead_arm_angle_deg"),
            "top_shoulder_hip_separation_deg": swing.get("top", {}).get(
                "shoulder_hip_separation_deg"
            ),
            "impact_head_drift": swing.get("impact", {}).get("head_drift_from_address"),
            "address_stance_width": swing.get("address", {}).get("stance_width_dist"),
        }
        records.append({key: float(value) for key, value in record.items() if value is not None})
    return records

def basketball_records(summary: dict[str, Any]) -> list[dict[str, float]]:
    records = []
    for event in summary.get("shot_events", []):
        record: dict[str, float] = {}
        if "set_time_s" in event and "release_time_s" in event:
            record["set_to_release_s"] = float(event["release_time_s"] - event["set_time_s"])
        if "lift_time_s" in event and "release_time_s" in event:
            record["lift_to_release_s"] = float(event["release_time_s"] - event["lift_time_s"])
        if "score" in event:
            record["release_score"] = float(event["score"])
        records.append(record)
    return records


def extract_records(summary: dict[str, Any]) -> tuple[str, list[dict[str, float]]]:
    sport = detect_sport(summary)
    if "reps" in summary:
        return sport, report_records(summary)
    records = golf_records(summary) if sport == "golf" else basketball_records(summary)
    return sport, records


def comparison_rows(
    sport: str,
    records_a: list[dict[str, float]],
    records_b: list[dict[str, float]],
) -> list[ComparisonRow]:
    v2 = any("." in key for record in records_a + records_b for key in record)
    if v2:
        metrics = REPORT_METRICS.get(sport, [])
    else:
        metrics = GOLF_METRICS if sport == "golf" else BASKETBALL_METRICS
    rows = []
    for key, label, unit in metrics:
        values_a = [record[key] for record in records_a if key in record]
        values_b = [record[key] for record in records_b if key in record]
        if values_a and values_b:
            rows.append(
                ComparisonRow(key=key, label=label, unit=unit, values_a=values_a, values_b=values_b)
            )
    return rows
