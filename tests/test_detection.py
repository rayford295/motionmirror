from __future__ import annotations

import pytest

from swingform_ai.analysis import analyze_sequence
from tests.synthetic import FPS, basketball_shots, golf_swings

TOL = 3 / FPS  # three frames


def test_golf_detects_each_swing_with_correct_phases():
    seq, truth = golf_swings(n_swings=2)
    a = analyze_sequence(seq, "golf")
    assert len(a.reps) == 2
    for rep, expected in zip(a.reps, truth):
        assert rep.time("top") == pytest.approx(expected["top"], abs=TOL)
        assert rep.time("impact") == pytest.approx(expected["impact"], abs=TOL)
        assert rep.time("address") == pytest.approx(expected["address"], abs=0.2)
        assert rep.time("finish") > rep.time("impact")


def test_golf_tempo_matches_ground_truth():
    seq, _ = golf_swings(n_swings=1, back_s=0.9, down_s=0.3, pause_s=0.1)
    summary = analyze_sequence(seq, "golf").summaries[0]
    # pause belongs to the backswing: (0.9 + 0.1) / 0.3
    assert summary["timing"]["tempo_ratio"] == pytest.approx(10 / 3, rel=0.2)


def test_golf_tolerates_dropped_frames():
    seq, truth = golf_swings(n_swings=1)
    seq.frames[:] = [f for f in seq.frames if f.frame_index % 7]  # drop every 7th frame
    a = analyze_sequence(seq, "golf")
    assert len(a.reps) == 1
    assert a.reps[0].time("impact") == pytest.approx(truth[0]["impact"], abs=TOL)


def test_basketball_detects_release_and_dip():
    seq, truth = basketball_shots(n_shots=2)
    a = analyze_sequence(seq, "basketball")
    assert len(a.reps) == 2
    for rep, expected in zip(a.reps, truth):
        assert rep.time("release") == pytest.approx(expected["release"], abs=0.2)
        assert rep.time("dip") == pytest.approx(expected["dip"], abs=0.15)


def test_auto_side_finds_mirrored_shooter():
    seq, _ = basketball_shots(n_shots=1)
    a = analyze_sequence(seq, "basketball", side="auto")
    assert a.side == "right"
    assert len(a.reps) == 1
    assert any("side=auto" in w for w in a.warnings)


def test_no_motion_means_no_reps_and_a_warning():
    seq, _ = golf_swings(n_swings=1)
    still = type(seq)(frames=[seq.frames[0]] * 60, fps=FPS, width=1000, height=1000)
    a = analyze_sequence(still, "golf")
    assert a.reps == []
    assert any("No golf rep" in w for w in a.warnings)


def test_badminton_classifies_strokes_and_finds_overhead_contact():
    from tests.synthetic import badminton_strokes

    seq, truth = badminton_strokes()
    a = analyze_sequence(seq, "badminton", side="auto")
    assert a.side == "right"  # the fastest-moving hand
    assert [s["stroke"] for s in a.summaries] == [t["stroke"] for t in truth]
    for rep, expected in zip(a.reps, truth):
        assert rep.time("contact") == pytest.approx(expected["contact"], abs=0.2)
    # overhead strokes get overhead-specific checks
    assert any(f.key == "contact.racket_hand_height_torso" for f in a.findings[0])


def test_one_arm_contest_is_not_a_shot():
    """A defender reaching up with one arm while the other hangs at the hip."""

    seq, _ = basketball_shots(n_shots=1)
    from dataclasses import replace

    from swingform_ai.schema import Landmark

    frames = []
    for f in seq.frames:
        lms = dict(f.landmarks)
        lms["left_wrist"] = Landmark("left_wrist", 0.75, 0.58, 0.0, 0.95)  # far, at the hip
        frames.append(replace(f, landmarks=lms))
    contest = replace(seq, frames=frames)
    assert analyze_sequence(contest, "basketball").reps == []
