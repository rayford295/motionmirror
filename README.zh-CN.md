<p align="center">
  <a href="https://rayford295.github.io/motionmirror/"><img src="docs/assets/readme/banner-pixel.png" alt="MotionMirror（动作镜像）：看清每个阶段的动作" width="100%"></a>
</p>

<p align="center">
  <a href="https://github.com/rayford295/motionmirror/actions/workflows/test.yml"><img alt="Tests" src="https://github.com/rayford295/motionmirror/actions/workflows/test.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%E2%80%933.13-0d1d36">
  <a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-d6a858"></a>
  <br>
  <a href="README.md">English</a> · <b>中文</b> ·
  <a href="https://rayford295.github.io/motionmirror/"><b>▶ 网站</b></a> ·
  <a href="https://youtu.be/Kd4xoJ1RMb0">视频</a> ·
  <a href="https://rayford295.github.io/motionmirror/viewer/pose3d.html">3D 查看器</a>
</p>

<table>
<tr>
<td width="50%" align="center"><img src="docs/assets/rayford-basketball/demo.gif" alt="篮球跳投骨架叠加" width="100%"><br><sub>🏀 <b>跳投</b> · 120 fps · 自动放大</sub></td>
<td width="50%" align="center"><img src="docs/assets/chen-jingyi-badminton/demo.gif" alt="羽毛球高手击球骨架叠加" width="100%"><br><sub>🏸 <b>羽毛球高手击球</b> · 击球点识别</sub></td>
</tr>
</table>

**MotionMirror（动作镜像）** 把一段手机拍的篮球跳投或羽毛球击球视频，变成分阶段的测量和通俗的建议。
每个数字都能追溯到具体的帧和关节。

<img src="docs/assets/readme/stage-watch.png" alt="第 1 关 · 观看" width="100%">

<p align="center">
  <a href="https://youtu.be/Kd4xoJ1RMb0"><img src="docs/assets/promo/teaser.gif" alt="在 YouTube 观看 MotionMirror 视频" width="100%"></a>
  <br><b><a href="https://youtu.be/Kd4xoJ1RMb0">▶ 在 YouTube 观看两分钟介绍视频</a></b>
</p>

<img src="docs/assets/readme/stage-start.png" alt="继续？· 快速开始" width="100%">

```bash
pip install -e ".[pose]"
motionmirror analyze my_shot.mov --sport basketball --side auto
motionmirror analyze rally.mp4   --sport badminton  --side auto
```

输出包括带建议的报告、骨架叠加视频、关键姿态图和指标 CSV。
效果、示例和原理见 **[网站](https://rayford295.github.io/motionmirror/)**；指标说明见 [docs/metrics.md](docs/metrics.md)。

<details>
<summary><b>示例</b></summary>

<!-- examples-table:start -->
| Session | Sport | Clip | Pose frames | Reps | Report |
|---|---|---|---|---|---|
| [rayford-basketball](examples/rayford-basketball/) | 🏀 Basketball · 120 fps | 6.8 s · 1080×1920 | 706 / 820 | 1 shot | [report.md](examples/rayford-basketball/report.md) |
| [chen-jingyi-badminton](examples/chen-jingyi-badminton/) | 🏸 Badminton | 12.1 s · 1920×1080 | 364 / 364 | 4 strokes | [report.md](examples/chen-jingyi-badminton/report.md) |
| [yifan-basketball-0710](examples/yifan-basketball-0710/) | 🏀 Basketball · 1v1 | 56.1 s · 480×854 | 1592 / 1712 | 2 shots | [report.md](examples/yifan-basketball-0710/report.md) |
<!-- examples-table:end -->

</details>

<details>
<summary><b>开发</b></summary>

```bash
pip install -e ".[pose,dev]"
pytest -q && ruff check src tests tools
```

像素画由代码绘制：`python tools/promo/make_pixel_assets.py`。

</details>

<p align="center">
  <img src="docs/assets/readme/footer.png" alt="" width="100%">
  <br><sub>MIT License · 原名 <i>SwingForm AI</i></sub>
</p>
