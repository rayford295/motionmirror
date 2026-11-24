<p align="center">
  <a href="https://rayford295.github.io/motionmirror/"><img src="docs/assets/readme/banner-pixel.png" alt="MotionMirror: see your form, phase by phase" width="100%"></a>
</p>

<p align="center">
  <a href="https://github.com/rayford295/motionmirror/actions/workflows/test.yml"><img alt="Tests" src="https://github.com/rayford295/motionmirror/actions/workflows/test.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%E2%80%933.13-0d1d36">
  <a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-d6a858"></a>
  <br>
  <b>English</b> · <a href="README.zh-CN.md">中文</a> ·
  <a href="https://rayford295.github.io/motionmirror/"><b>▶ Website</b></a> ·
  <a href="https://youtu.be/Kd4xoJ1RMb0">Video</a> ·
  <a href="https://rayford295.github.io/motionmirror/viewer/pose3d.html">3D viewer</a>
</p>

<table>
<tr>
<td width="50%" align="center"><img src="docs/assets/rayford-basketball/demo.gif" alt="Basketball jump shot overlay" width="100%"><br><sub>🏀 <b>Jump shot</b> · 120 fps · auto-zoom</sub></td>
<td width="50%" align="center"><img src="docs/assets/chen-jingyi-badminton/demo.gif" alt="Badminton overhead overlay" width="100%"><br><sub>🏸 <b>Badminton overhead</b> · contact detection</sub></td>
</tr>
</table>

**MotionMirror** turns one phone video of a jump shot or a badminton stroke into phases,
measurements and plain-language feedback. Every number traces back to a frame and a joint.

<img src="docs/assets/readme/hiscore.png" alt="3 sports · 6 example sessions · 33 body landmarks per frame · 1 command" width="100%">

<img src="docs/assets/readme/stage-watch.png" alt="Stage 1 · Watch" width="100%">

<p align="center">
  <a href="https://youtu.be/Kd4xoJ1RMb0"><img src="docs/assets/promo/teaser.gif" alt="Watch the MotionMirror video on YouTube" width="100%"></a>
  <br><b><a href="https://youtu.be/Kd4xoJ1RMb0">▶ Watch the 2-minute video on YouTube</a></b>
</p>

<img src="docs/assets/readme/stage-results.png" alt="Stage 2 · Real results" width="100%">

<table>
<tr>
<th width="50%">🏀 Rayford · jump shot · <a href="examples/rayford-basketball/report.md">report</a></th>
<th width="50%">🏸 Chen Jingyi · 4 strokes · <a href="examples/chen-jingyi-badminton/report.md">report</a></th>
</tr>
<tr>
<td valign="top">

| Check | Value | |
| --- | --- | --- |
| Elbow at release | **176°** | ✅ |
| Knee bend in dip | **152°** | ✅ |
| Release height | **+0.52 torso** | ✅ |
| Dip → release | **0.37 s** | ✅ |
| Landing drift | **0.23 torso** | ✅ |

</td>
<td valign="top">

| Stroke | Type | In range |
| --- | --- | --- |
| 1 | drive | 🟥🟥 |
| 2 | overhead | 🟩🟩🟥🟥 |
| 3 | drive | 🟩🟩🟩 |
| 4 | overhead | 🟩🟩🟥🟥 |

</td>
</tr>
</table>

<img src="docs/assets/readme/stage-how.png" alt="Stage 3 · How it works" width="100%">

<img src="docs/assets/readme/levelmap.png" alt="Video → pose (33 landmarks) → reps and phases → metrics at each phase → feedback and report" width="100%">

Metrics are read at the moment that matters (the dip, the release, the contact), checked
against a reference range, and explained in plain words. Tiny or contested athletes get an
auto-zoom pass and a primary-athlete tracker.

<img src="docs/assets/readme/stage-start.png" alt="Continue? · Quickstart" width="100%">

```bash
pip install -e ".[pose]"
motionmirror analyze my_shot.mov --sport basketball --side auto
motionmirror analyze rally.mp4   --sport badminton  --side auto
```

You get a report with feedback, a skeleton overlay video, key poses and a metrics CSV.
Results, examples and how it works: **[the website](https://rayford295.github.io/motionmirror/)**.
Metric definitions: [docs/metrics.md](docs/metrics.md).

<details>
<summary><b>Examples</b></summary>

<!-- examples-table:start -->
| Session | Sport | Clip | Pose frames | Reps | Report |
|---|---|---|---|---|---|
| [rayford-basketball](examples/rayford-basketball/) | 🏀 Basketball · 120 fps | 6.8 s · 1080×1920 | 706 / 820 | 1 shot | [report.md](examples/rayford-basketball/report.md) |
| [chen-jingyi-badminton](examples/chen-jingyi-badminton/) | 🏸 Badminton | 12.1 s · 1920×1080 | 364 / 364 | 4 strokes | [report.md](examples/chen-jingyi-badminton/report.md) |
| [yifan-basketball-0710](examples/yifan-basketball-0710/) | 🏀 Basketball · 1v1 | 56.1 s · 480×854 | 1592 / 1712 | 2 shots | [report.md](examples/yifan-basketball-0710/report.md) |
<!-- examples-table:end -->

</details>

<details>
<summary><b>CLI reference</b></summary>

```text
motionmirror analyze SOURCE [--sport golf|basketball|badminton] [--side right|left|auto]
                            [--out DIR] [--model lite|full|heavy|PATH] [--labels FILE]
                            [--no-render] [--ball-trail off|detect|proxy]
                            [--min-confidence 0-1] [--json]
motionmirror compare SESSION_A SESSION_B                       # same athlete, two sessions
motionmirror highlights LONG_VIDEO --session-id ID [--top-k 3]  # cut the best swings
motionmirror register VIDEO --sport badminton                      # private local manifest
```

</details>

<details>
<summary><b>Development</b></summary>

```bash
pip install -e ".[pose,dev]"
pytest -q && ruff check src tests tools
```

The pixel art is drawn in code: `python tools/promo/make_pixel_assets.py`.
See [CONTRIBUTING.md](CONTRIBUTING.md) and the [changelog](CHANGELOG.md).

</details>

<p align="center">
  <img src="docs/assets/readme/footer.png" alt="" width="100%">
  <br><sub>MIT License · Formerly <i>SwingForm AI</i></sub>
</p>
