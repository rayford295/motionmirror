# Pixel-Game Website and README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle `docs/index.html` as a retro pixel game and give both READMEs a pixel banner, matching `docs/assets/promo/cover-pixel.png`.

**Architecture:** A Python tool reuses the cover's sprite functions to export crisp PNG assets into `docs/assets/pixel/`. The site stays one static HTML file (inline CSS/JS, three.js from unpkg for the bonus stage) that scales those PNGs with `image-rendering: pixelated`. A stdlib-only pytest checks the page's structure and that every local asset it references exists.

**Tech Stack:** Python 3.10+, Pillow, numpy (already used by the cover script); HTML/CSS/vanilla JS; Google Fonts (Press Start 2P, body sans); Playwright for visual checks (local only, not CI).

**Spec:** `docs/superpowers/specs/2026-11-24-pixel-site-design.md`

## Global Constraints

- Palette tokens from the cover: navy `#0d1d36`, navy-2 `#132848`, gold `#d6a858`, gold-dark `#966c30`, cream `#f6e8c8`, grass `#76be5a` / `#5ca248` / `#92d26c`, outline `#1e1622`, basketball orange `#e87030`, badminton violet `#ac96ff`.
- Press Start 2P for headings, labels, buttons and numbers only; body copy a plain sans at ≥ 16 px.
- All sprite scaling is integer and `image-rendering: pixelated`.
- YouTube id `Kd4xoJ1RMb0`, duration 2:08, loaded only after a click.
- Animations off under `prefers-reduced-motion: reduce`.
- No horizontal scroll at 360 px.
- Every number, link and example on the current site survives.
- Commit on `main`, push, confirm the Pages deploy and the live page.

## Review Focus

1. Phone width (360 px): level map, stat bars and the six-card grid must wrap without horizontal scroll. Pinned by the Playwright check in Task 4.
2. Visitor who never clicks play: no YouTube request on load. Pinned by `test_video_is_click_to_load` in Task 2.
3. A renamed or missing asset: every local `src`/`href` in the page must exist on disk. Pinned by `test_local_refs_exist` in Task 2.
4. Reduced-motion users: no running animation. Pinned by `test_reduced_motion_rule` in Task 2.
5. Bonus 3D stage: the three.js player still renders and toggles play. Pinned by the Playwright console-error and canvas check in Task 4.

---

### Task 1: Pixel asset exporter

**Files:**
- Create: `tools/promo/make_pixel_assets.py`
- Create: `tests/test_pixel_assets.py`
- Output: `docs/assets/pixel/*.png`, `docs/assets/readme/banner-pixel.png`

**Interfaces:**
- Consumes: `rayford()`, `chen()`, `shuttle()`, `stars()`, `grass()`, `frame()`, `text_l()`, `paste()`, `font()`, palette constants from `tools/promo/make_pixel_cover.py` (imported by path).
- Produces: `export(out_dir: Path, readme_dir: Path) -> dict[str, Path]` writing
  `rayford.png`, `chen.png`, `shuttle.png` (native size × 1, transparent),
  `rayford-idle.png`, `chen-idle.png` (2-frame horizontal sheets, frame 2 = sprite raised 1 px, transparent),
  and `banner-pixel.png` (README banner, 320×80 native scaled ×6 = 1920×480, opaque).

- [ ] **Step 1: Test** `test_export_writes_assets(tmp_path)`: calls `export(tmp_path/"pixel", tmp_path/"readme")`; asserts all six files exist; sprite PNGs are mode RGBA with a fully transparent corner pixel; each idle sheet's width is exactly 2 × the matching sprite's width and same height (+1 px headroom allowed: height == sprite height + 1); banner size == (1920, 480). Skip the test module if Pillow or numpy is missing (`pytest.importorskip`).
- [ ] **Step 2:** Run `pytest tests/test_pixel_assets.py -q` → fails (module missing).
- [ ] **Step 3:** Implement `export()` and a `main()` that writes to the real paths. Banner layout: starfield, grass strip at the bottom 14 px, both sprites ×1 on the left, "MOTION" cream / "MIRROR" gold at size 16, tagline at size 8, gold `frame()`.
- [ ] **Step 4:** Run the test → passes; run `python tools/promo/make_pixel_assets.py` and look at `banner-pixel.png`.
- [ ] **Step 5:** Commit.

### Task 2: Pixel-game site

**Files:**
- Modify (rewrite): `docs/index.html`
- Create: `tests/test_site.py`

**Interfaces:**
- Consumes: Task 1 assets under `docs/assets/pixel/`; existing demo GIFs, posters, compare figure, `viewer/pose3d.html`; the existing `MINI_POSE`, `EDGES`, `ECOL` data and three.js code from the current page (moved, not rewritten).
- Produces: section ids `hero`, `watch`, `results`, `tracking`, `pipeline`, `bonus`, `examples`, `compare`, `quickstart`.

- [ ] **Step 1: Tests** in `tests/test_site.py` (stdlib `html.parser` + `re` only):
  - `test_sections_present`: all nine ids above exist.
  - `test_local_refs_exist`: every `src`/`href`/`poster` that is not `http(s):`, `#`, `mailto:` or `data:` resolves to a file under `docs/`.
  - `test_video_is_click_to_load`: the page contains `Kd4xoJ1RMb0` but no `<iframe` element in the static HTML.
  - `test_reduced_motion_rule`: the page contains `prefers-reduced-motion: reduce`.
  - `test_facts_kept`: page text contains `176°`, `0.37 s`, `3 → 2`, `33`, `0/2`, `2/4`, `3/3`, and all six example slugs (`rayford-basketball`, `chen-jingyi-badminton`, `yifan-golf-0601`, `yifan-basketball-0710`, `yifan-golf-0520`, `golf-swing-demo`).
- [ ] **Step 2:** Run `pytest tests/test_site.py -q` → `test_sections_present` and `test_video_is_click_to_load` fail on the current page.
- [ ] **Step 3:** Rewrite `docs/index.html` per the spec's page outline (nav; hero title screen with sprites, twinkling stars, PRESS START; Stage 1 watch facade; Stage 2 demos + stat bars + high-score strip; Stage 3 dialog boxes + 3 → 2 boss callout; Stage 4 level map; Bonus 3D stage; Stage 5 level select; Stage 6 compare; Continue? quickstart with copy buttons; grass footer). Stat bar data: basketball five checks from README (176° vs ≥145°, 152° vs 95–160°, +0.52 vs ≥0.2 torso, 0.37 s vs 0.2–0.8 s, 0.23 vs ≤0.5 torso); badminton four strokes (#1 drive 0/2, #2 overhead 2/4, #3 drive 3/3, #4 overhead 2/4) with the README's main cues.
- [ ] **Step 4:** Run `pytest -q` → all pass (including the existing suite).
- [ ] **Step 5:** Commit.

### Task 3: README refresh

**Files:**
- Modify: `README.md:1-25`, `README.zh-CN.md:1-…` (top block only)

- [ ] **Step 1:** Replace the banner with `docs/assets/readme/banner-pixel.png`; the video block becomes the pixel cover linking to `https://youtu.be/Kd4xoJ1RMb0` plus the watch line; keep badges for Tests, Python, License, Website; keep language links. Same top block in Chinese.
- [ ] **Step 2:** Run `python tools/generate_examples_table.py --check` if it supports it, else confirm the examples-table markers are untouched (`git diff` shows no change inside them).
- [ ] **Step 3:** Commit.

### Task 4: Visual verification, push, live check

- [ ] **Step 1:** Serve `docs/` locally (`python -m http.server`), Playwright screenshots at 1440×900 and 360×780, full page; record console errors; assert `document.documentElement.scrollWidth <= innerWidth` at 360; click the watch facade and assert an iframe appears; click the bonus play button and assert the canvas has non-zero size.
- [ ] **Step 2:** Inspect screenshots; fix issues; repeat until clean.
- [ ] **Step 3:** `pytest -q && ruff check src tests tools`.
- [ ] **Step 4:** Push `main`; wait for the Pages and test workflows to succeed; fetch the live page and confirm it serves the new markup.
