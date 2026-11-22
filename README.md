<p align="center">
  <img src="docs/assets/brand/swingform-icon.svg" alt="SwingForm AI icon" width="72">
</p>

<h1 align="center">SwingForm AI</h1>

<p align="center">
  <a href="https://github.com/rayford295/swingform-ai/actions/workflows/test.yml"><img alt="Tests" src="https://github.com/rayford295/swingform-ai/actions/workflows/test.yml/badge.svg"></a>
  <a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-2f6f4e"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%E2%80%933.13-2458a6">
  <img alt="Sports" src="https://img.shields.io/badge/sports-golf%20%C2%B7%20basketball%20%C2%B7%20badminton-c46a2c">
  <a href="https://rayford295.github.io/swingform-ai/"><img alt="Website" src="https://img.shields.io/badge/website-live-1d6fa5"></a>
</p>

<p align="center">
  <a href="docs/assets/promo/swingform-promo.mp4"><img src="docs/assets/promo/poster.jpg" alt="Watch the SwingForm AI promo (narrated)" width="900"></a>
  <br><sub><b>▶ <a href="docs/assets/promo/swingform-promo.mp4">Watch the narrated promo</a></b> · or on the <a href="https://rayford295.github.io/swingform-ai/">website</a></sub>
</p>

SwingForm AI turns an ordinary phone video of a golf swing, a basketball jump shot or a badminton stroke into
phase-by-phase posture metrics, plain-language feedback, and review visuals. Every number
can be traced back to a frame, a joint, and a reference range.

```
video ─► pose (MediaPipe, 33 landmarks) ─► reps + phases ─► metrics at each phase ─► feedback + report
```

## Flagship Demos

### Basketball: Rayford, oceanside jump shot

The shooter fills only **9% of a 1080×1920, 120 fps frame**. SwingForm locates him, zooms in
for a second pose pass, and splits the shot into six phases.

![Rayford key poses](docs/assets/rayford-basketball/keyposes.jpg)

| Check | Value | Reference | Status |
| --- | --- | --- | --- |
| Elbow extension at release | 176° | ≥ 145° | in range |
| Knee bend in the dip | 152° | 95° to 160° | in range |
| Release height above head | +0.52 torso | ≥ 0.2 | in range |
| Dip-to-release time | 0.37 s | 0.2 to 0.8 s | in range |
| Sideways drift on landing | 0.23 torso | ≤ 0.5 | in range |

[Report](examples/rayford-basketball/report.md) · [overlay video](examples/rayford-basketball/overlay.mp4) · [timeline](examples/rayford-basketball/timeline.png)

### Badminton: Chen Jingyi (陈静仪), mixed strokes

A new badminton profile finds **4 strokes in 12 s** from racket-hand speed, classifies them
as **drive** or **overhead**, and applies stroke-specific checks. On overheads, contact is
placed at the highest point of the reach, because the arm keeps accelerating after the hit.

![Chen Jingyi key poses](docs/assets/chen-jingyi-badminton/keyposes.jpg)

| Stroke | Type | Checks in range | Main cue |
| --- | --- | --- | --- |
| #1 | drive | 0 / 2 | Long, slow preparation; ready stance very low |
| #2 | overhead | 2 / 4 | Contact low for an overhead; raise the free arm |
| #3 | drive | 3 / 3 | All in range |
| #4 | overhead | 2 / 4 | Strike at full extension, take the shuttle earlier |

[Report](examples/chen-jingyi-badminton/report.md) · [overlay video](examples/chen-jingyi-badminton/overlay.mp4) · [timeline](examples/chen-jingyi-badminton/timeline.png)

## Quickstart

```bash
pip install -e ".[pose]"          # core + video/pose dependencies

swingform analyze my_swing.mp4 --sport golf --out runs/range-day
swingform analyze my_shot.mov  --sport basketball --side auto
swingform analyze rally.mp4    --sport badminton  --side auto
```

```
golf: 2 rep(s), side=right
  rep 2: 60% in range (confidence 0.84)
    - Tempo (backswing : downswing): Downswing is slow relative to the backswing; ...
    - Lead arm at top: Lead arm is noticeably bent at the top; a wider arc usually adds consistency.
Wrote:
  runs/range-day/pose.json  metrics.csv  report.json  report.md  overlay.mp4  timeline.png  keyposes.jpg
```

| Output | What it is |
| --- | --- |
| `report.md` / `report.json` | Per-rep phases, timing, metrics, checks with reference ranges, cross-rep consistency |
| `overlay.mp4` | Skeleton, ghost trail, phase labels and live joint angles (H.264, plays in browsers) |
| `keyposes.jpg` | Real frames at every detected phase, one row per rep |
| `timeline.png` | Hand/wrist signals and angles with phase markers |
| `metrics.csv` | Every per-frame metric, phase-tagged |
| `pose.json` | Raw landmarks, re-analyzable without re-running pose |

Already have landmarks? `swingform analyze pose.json --sport golf` needs no video
dependencies at all.

## What It Measures

**Golf** (`address → top → impact → finish`): tempo ratio, backswing/downswing time, lead-arm
angle at the top, hand height, hip sway, head drift to impact, knee flex, stance width,
shoulder-hip separation, peak hand speed.

**Basketball** (`set → dip → lift → release → follow-through → landing`): elbow extension at
release, knee bend in the dip, release height above the head, dip-to-release time, guide-hand
gap, sideways drift on landing.

**Badminton** (`ready → backswing → contact → follow-through → recovery`, each stroke
classified as overhead, drive or underhand): arm extension and hand height at contact, free-arm
position, peak racket-hand speed, ready-stance knee bend, base width, swing timing.

Definitions, units and the reasoning behind each reference range are in
[docs/metrics.md](docs/metrics.md).

## How It Stays Honest

- **Aspect-correct geometry.** MediaPipe normalizes x by width and y by height; angles are
  computed after undoing that, so portrait phone clips are not distorted.
- **Image-plane angles.** Monocular depth is noisy enough to swing a knee angle by 20°, so
  angles use 2D image geometry by default.
- **Scale-free distances.** Drift and gaps are in *torso lengths*, comparable across zoom levels.
- **Gaps are not crashes.** Hidden joints become `n/a`, short dropouts are interpolated, and
  each phase value is a 5-frame median.
- **Small athletes get a zoom pass.** When the person is under 35% of the frame height, pose
  runs a second time on a smoothed, upscaled crop around them.
- **Confidence on every rep.** Detection confidence drops when visibility is low or timing is
  implausible, and the report says why.
- **No invented ball flight.** The golf ball trail is drawn only when a rising, ballistic track
  is actually detected (`--ball-trail detect`). `--ball-trail proxy` draws a clearly dashed,
  unmeasured arc. No speed, launch, spin, carry or make/miss is claimed.

Auto-detection is heuristic. When it gets a phase wrong, pass hand-marked times with
`--labels labels.json` (see [examples/golf-swing-demo/labels.json](examples/golf-swing-demo/labels.json)).

## Examples

Every artifact below was produced by `swingform analyze` from the clip in the same folder.

| Session | Reps | Report | Visuals |
| --- | --- | --- | --- |
| `rayford-basketball` | 1 shot | [report.md](examples/rayford-basketball/report.md) | [overlay](examples/rayford-basketball/overlay.mp4) · [key poses](examples/rayford-basketball/keyposes.jpg) · [timeline](examples/rayford-basketball/timeline.png) |
| `chen-jingyi-badminton` | 4 strokes | [report.md](examples/chen-jingyi-badminton/report.md) | [overlay](examples/chen-jingyi-badminton/overlay.mp4) · [key poses](examples/chen-jingyi-badminton/keyposes.jpg) · [timeline](examples/chen-jingyi-badminton/timeline.png) |
| `yifan-golf-0520` | 2 swings | [report.md](examples/yifan-golf-0520/report.md) | [overlay](examples/yifan-golf-0520/overlay.mp4) · [key poses](examples/yifan-golf-0520/keyposes.jpg) · [timeline](examples/yifan-golf-0520/timeline.png) |
| `golf-swing-demo` | 2 swings | [report.md](examples/golf-swing-demo/report.md) | [overlay](examples/golf-swing-demo/overlay.mp4) · [key poses](examples/golf-swing-demo/keyposes.jpg) · [timeline](examples/golf-swing-demo/timeline.png) |
| `yifan-basketball-0601` | 1 shot | [report.md](examples/yifan-basketball-0601/report.md) | [overlay](examples/yifan-basketball-0601/overlay.mp4) · [key poses](examples/yifan-basketball-0601/keyposes.jpg) · [timeline](examples/yifan-basketball-0601/timeline.png) |

## CLI Reference

```text
swingform analyze SOURCE [--sport golf|basketball|badminton] [--side right|left|auto] [--out DIR]
                         [--model lite|full|heavy|PATH] [--labels FILE] [--no-render]
                         [--ball-trail off|detect|proxy] [--min-confidence 0-1] [--json]
swingform highlights LONG_VIDEO --session-id ID [--top-k 3]   # cut the best swings
swingform register VIDEO --sport golf                          # private local manifest
```

Python API:

```python
from swingform_ai.schema import PoseSequence
from swingform_ai.analysis import analyze_sequence

analysis = analyze_sequence(PoseSequence.load("pose.json"), sport="golf", side="right")
for summary in analysis.summaries:
    print(summary["timing"]["tempo_ratio"], summary["top"]["lead_arm_angle_deg"])
```

## Project Map

```text
src/swingform_ai/
  schema.py        pose data model (aspect-aware, visibility-gated)
  signal.py        gap filling, smoothing, peak finding (pure Python)
  profiles/        golf.py, basketball.py, badminton.py: metrics, rep detection, checks
  feedback.py      reference-range checks, scoring, consistency
  analysis.py      pose sequence -> reps -> summaries -> report
  video.py         video I/O and MediaPipe pose extraction
  render.py        overlay video, key-pose sheet, timeline
  ballflight.py    golf ball trail detection (review aid)
  reel.py          long-video highlight cutting
  pipeline.py      one call: source -> output folder
  cli.py           `swingform` command
tools/promo/       narrated promo video generator (ElevenLabs voice, cached)
tests/             synthetic swings/shots/strokes with known phase times
docs/              website, 3D viewer, metrics, architecture
```

## Development

```bash
pip install -e ".[pose,dev]"
pytest -q && ruff check src tests
```

Core tests need no video stack; CI also runs an end-to-end smoke test on the bundled clip.
See [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md).

---

[Website](https://rayford295.github.io/swingform-ai/) · [3D Viewer](https://rayford295.github.io/swingform-ai/viewer/pose3d.html) · [中文说明](README.zh-CN.md) · MIT License
