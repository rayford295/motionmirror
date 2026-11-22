from __future__ import annotations

import json
from pathlib import Path

import pytest

from motionmirror.cli import main
from motionmirror.feedback import Check, evaluate, score
from motionmirror.profiles import basketball, get_profile, golf
from motionmirror.schema import FramePose, Landmark, PoseSequence
from motionmirror.signal import fill_gaps, local_extrema, moving_average, percentile
from tests.synthetic import golf_swings

ROOT = Path(__file__).resolve().parents[1]


def test_fill_gaps_interpolates_and_respects_max_gap():
    assert fill_gaps([1.0, None, 3.0]) == [1.0, 2.0, 3.0]
    assert fill_gaps([None, 2.0, None]) == [2.0, 2.0, 2.0]
    assert fill_gaps([0.0, None, None, None, 4.0], max_gap=2)[2] is None


def test_moving_average_and_percentile_skip_none():
    assert moving_average([1.0, None, 3.0], 3) == [1.0, 2.0, 3.0]
    assert percentile([None, 1.0, 2.0, 3.0], 0.5) == 2.0


def test_local_extrema_merges_close_peaks():
    vals = [0, 5, 0, 6, 0, 0, 0, 0, 4, 0]
    assert local_extrema(vals, kind="max", threshold=3, min_separation=3, radius=1) == [3, 8]


def test_aspect_correction_fixes_portrait_angles():
    # A true right angle drawn in a 1:2 portrait frame looks skewed in normalized coords.
    lms = {"a": Landmark("a", 0.5, 0.25), "b": Landmark("b", 0.5, 0.5),
           "c": Landmark("c", 1.0, 0.5)}
    frame = FramePose(0.0, lms, aspect=0.5)
    from motionmirror.geometry import angle_degrees
    assert angle_degrees(frame.point("a"), frame.point("b"), frame.point("c")) == pytest.approx(90)


def test_low_visibility_landmark_is_ignored():
    frame = FramePose(0.0, {"nose": Landmark("nose", 0.5, 0.5, visibility=0.1)})
    assert frame.get("nose") is None
    assert frame.require("nose").x == 0.5


def test_pose_json_round_trip(tmp_path):
    seq, _ = golf_swings(n_swings=1)
    path = seq.save(tmp_path / "pose.json")
    loaded = PoseSequence.load(path)
    assert len(loaded) == len(seq) and loaded.aspect == 1.0
    assert loaded.frames[10].landmarks["left_wrist"].y == pytest.approx(
        seq.frames[10].landmarks["left_wrist"].y, abs=1e-4)


def test_v1_sample_still_loads_and_summarizes():
    payload = json.loads((ROOT / "examples" / "sample_pose_sequence.json").read_text())
    seq = PoseSequence.from_mapping(payload)
    assert "lead_arm_angle_deg" in golf.summarize_sequence(seq)["summary"]
    assert "shooting_elbow_angle_deg" in basketball.summarize_sequence(seq)["summary"]


def test_feedback_statuses_and_score():
    checks = [Check("a.x", "X", 1.0, 2.0, "", "too low", "too high", ""),
              Check("a.y", "Y", None, 5.0, "", "", "too high", ""),
              Check("a.z", "Z", 0.0, None, "", "low", "", "")]
    findings = evaluate({"a": {"x": 0.5, "y": 3.0}}, checks)
    assert [f.status for f in findings] == ["low", "ok", "unknown"]
    assert score(findings) == 50.0


def test_every_profile_check_points_at_a_real_summary_key():
    for sport, maker in (("golf", golf_swings),):
        seq, _ = maker(n_swings=1)
        prof = get_profile(sport)
        summary = prof.summarize_rep(prof.build_rows(seq), prof.detect_reps(prof.build_rows(seq),
                                                                             30.0)[0])
        for check in prof.CHECKS:
            section, key = check.key.split(".")
            assert key in summary[section], check.key


def test_cli_analyze_pose_json(tmp_path, capsys):
    seq, _ = golf_swings(n_swings=2)
    src = seq.save(tmp_path / "in.json")
    out = tmp_path / "run"
    assert main(["analyze", str(src), "--sport", "golf", "--out", str(out)]) == 0
    report = json.loads((out / "report.json").read_text())
    assert report["rep_count"] == 2
    assert (out / "metrics.csv").read_text().count("1:impact") == 1
    assert "## Rep 1" in (out / "report.md").read_text()
    assert "2 rep(s)" in capsys.readouterr().out


def test_unknown_sport_is_rejected():
    with pytest.raises(ValueError):
        get_profile("tennis")
