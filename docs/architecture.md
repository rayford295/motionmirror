# Architecture

Sport-independent pose handling lives in the core; each sport is a profile module with the
same interface. Only `video.py`, `render.py`, `ball_tracking.py` and `reel.py` import OpenCV or
MediaPipe, so analysis of an existing `pose.json` runs on plain Python.

```text
            video.py                     analysis.py                       report.py / render.py
video ──► extract_pose ──► PoseSequence ──► profile.build_rows ──► rows ──► report.md / report.json
                              (schema.py)    profile.detect_reps ──► reps     overlay.mp4, keyposes.jpg,
                                             profile.summarize_rep ─► summaries  timeline.png
                                             feedback.evaluate ────► findings
```

## Modules

| Module | Responsibility |
| --- | --- |
| `schema.py` | `Landmark`, `FramePose`, `PoseSequence`; aspect-corrected `point()`, visibility gating, JSON I/O. |
| `signal.py` | `fill_gaps`, `moving_average`, `speed_2d`, `local_extrema`, `argmin` / `argmax`; all tolerate `None`. |
| `profiles/base.py` | `Rep` and `PhaseMark`, shared body geometry, row building with smoothed tracks, phase-value medians, label loading. |
| `profiles/golf.py`, `basketball.py` | `frame_metrics`, `build_rows`, `detect_reps`, `summarize_rep`, `CHECKS`, `CONSISTENCY_KEYS`. |
| `feedback.py` | `Check` / `Finding`, range evaluation, score, cross-rep consistency. |
| `tracking.py` | `PrimaryAthleteTracker`: keeps the primary athlete when several people are detected. |
| `ball_tracking.py` | Tee-anchored, quality-gated golf ball trail (review aid). |
| `compare.py`, `session_compare.py` | Cross-session comparison (`motionmirror compare`). |
| `analysis.py` | `analyze_sequence` (including `side="auto"` and label overrides), quality warnings, CSV/JSON export. |
| `pipeline.py` | `run()`: one source in, one output folder out. |
| `cli.py` | `motionmirror analyze | highlights | register`. |

## Adding a Sport

Create `profiles/<sport>.py` that implements the interface above, then register it in
`profiles/__init__.py`. Add a synthetic generator with known phase times to
`tests/synthetic.py` and assert that detection recovers them. That test is what keeps a
heuristic detector from silently regressing.

## Data Rules

Raw personal video and private notes stay under the ignored `data/local/`. Published pose
files store only the source filename, never an absolute path. See `data_governance.md`.
