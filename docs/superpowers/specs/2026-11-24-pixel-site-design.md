# Pixel-Game Redesign of the Website and README

Date: 2026-11-24 · Status: draft for approval

## Intent

MotionMirror's public faces are the GitHub README and the project site
(`docs/index.html`, served at https://rayford295.github.io/motionmirror/). The owner
wants ordinary visitors, not only developers, to land on the site and find the project
**fancy and fun**. The pixel-art cover (`docs/assets/promo/cover-pixel.png`, drawn by
`tools/promo/make_pixel_cover.py`) sets the look: a navy starfield, a gold pixel frame,
Press Start 2P lettering, two chibi athletes (Rayford with a basketball, Chen Jingyi with
a racket) on a strip of grass, and a "PRESS PLAY" button.

## Goals

- **Website:** a full redesign as a retro pixel game (option A, chosen by the owner). The
  first screen should make a visitor smile and want to scroll; each section reads like a
  game stage.
- **README:** a restrained refresh. It should match the cover without being loud.
- Keep every fact, number, link and example the current site and README carry, each on
  its own surface. This is a restyle and reorganisation, not a content cut. *(Call made
  during review.)* The site does not need to absorb README-only material (the "What It
  Measures" table, CLI flags); it links to the README and `docs/metrics.md` for those.

## Non-Goals

- No playable mini-game in the hero (option C). It may come later.
- No change to the Python package, CLI, tests or example data.
- No new build step: the site stays one static HTML file plus assets on GitHub Pages.
- No changes to `docs/viewer/pose3d.html` beyond what a link needs.

## Anti-Goals (Failure Even If It Works)

- Body text that is tiring to read because it is set in a pixel font.
- A page that feels like a gimmick and hides the real product: the skeleton-overlay GIFs
  and the measured numbers must stay prominent.
- Blurry pixel art (any sprite scaled without `image-rendering: pixelated` or by a
  non-integer factor).
- Heavy pages: the hero must appear quickly on a phone; no autoplaying video on load.
- Motion that ignores `prefers-reduced-motion`.

## Constraints

- GitHub strips CSS, scripts and iframes from READMEs. The README can carry the style
  only through images; text and tables stay GitHub's default.
- GitHub Pages serves `docs/` as static files. External scripts and fonts may load from a
  CDN or Google Fonts.
- Sprites must come from the same code that draws the cover, so the site and the cover
  never drift apart.
- Fonts: Press Start 2P (already vendored, SIL OFL) for display; a readable font for body.

## Approaches Considered

| | Approach | Trade-off |
|---|---|---|
| **A (chosen)** | Whole site styled as a retro pixel game: starfield hero with idle-animated chibi sprites, sections as "stages", demos in gold cartridge frames, metrics as RPG stat bars, pipeline as a level map. Pixel font for headings and labels only. | Most fun and memorable; needs care to keep body text readable. |
| B | Pixel hero only; the rest a clean dark product page. | Safer and faster, but loses the fun past the first screen. |
| C | A plus a playable hero (keys make the sprites shoot or smash). | Most delightful, but much more code and risk. Deferred. |

## Design: Website

**Palette and type.** Reuse the cover's palette as CSS tokens: navy `#0d1d36` and
`#132848` (backgrounds), gold `#d6a858` and dark gold `#966c30` (frames, buttons),
cream `#f6e8c8` (text on navy), grass greens `#76be5a` / `#5ca248` / `#92d26c`, outline
`#1e1622`, plus the cover's basketball orange and badminton violet as the two sport
accents. Headings, labels, buttons and numbers use Press Start 2P. Body copy uses a
plain, readable sans at 16 px or more (builder's pick; one that sits well next to pixel
type). A softer pixel face such as Pixelify Sans may be used for short secondary labels.

**Shared pixel vocabulary.** Gold double-line pixel frames (CSS borders or
`border-image`, square corners, hard drop shadow), stepped "dialog box" panels like a
handheld RPG, hard-edged buttons that press down 2-4 px on click, a slow twinkling
starfield behind navy sections, and a grass strip as the section divider into the
footer.

**Page, top to bottom.** Each section header reads as a stage, e.g. `STAGE 1 · WATCH`.

1. **Nav.** Pixel wordmark "MOTION MIRROR" (cream/gold like the cover), links to the
   stages, GitHub, 3D Viewer.
2. **Hero (title screen).** Starfield, gold frame, the two chibi sprites standing on grass
   with a small idle loop (ball bounce or dribble for Rayford, racket bob and a floating
   shuttle for Chen). Title, the tagline "See your form, phase by phase", the sport tags
   (basketball orange, badminton violet), and a blinking **▶ PRESS START** button that
   scrolls to the video. A secondary button links to GitHub.
3. **Stage 1 · Watch.** The YouTube video (`Kd4xoJ1RMb0`, 2:08) inside a pixel TV or
   cartridge frame. Load it with a click-to-play facade showing the pixel cover, so the
   page does not pull YouTube's player until asked.
4. **Stage 2 · Real results.** The two flagship demo GIFs (basketball, badminton) in gold
   frames with their captions and report links. Under each, the key checks as **RPG stat
   bars**: a bar per metric showing the value against its reference range, green when in
   range and amber when out, with the number printed in pixel type. *(Call made during
   review.)* Basketball shows its five checks as value-vs-range bars (README table, e.g.
   elbow extension 176° vs ≥ 145°). Badminton shows all four strokes, one bar each for
   "checks in range" (0/2, 2/4, 3/3, 2/4) with the stroke type and main cue; showing only
   the all-green stroke would flatter the result. The headline counters (sports, example
   sessions, 33 landmarks, tests in CI) become a "high score" strip.
5. **Stage 3 · Tracks the right athlete.** The three cards (TRACK, GATE, MEASURE) as RPG
   dialog boxes, and the "3 → 2" proof as a boss-fight style callout.
6. **Stage 4 · How it works.** The five pipeline steps as a **level map**: five nodes on a
   dotted path (Video QA → Pose + Track → Phases → Metrics → Output), each node a small
   pixel icon. Wraps vertically on phones.
7. **Bonus stage · 3D swing.** The existing three.js 3D skeleton player, kept working and
   reframed in a pixel frame (it is the current hero; it moves here). Its play button gets
   the pixel button style.
8. **Stage 5 · Open examples.** The six example cards as a **level-select grid**
   (thumbnail, sport tag, meta, file links).
9. **Stage 6 · You vs. you.** The compare section (text, chips, figure, command).
10. **Continue? · Quickstart.** Install and analyze commands in a terminal-style pixel
    window with a copy button.
11. **Footer.** Grass strip with the two sprites small, credits, links, MIT.

**Golf.** Basketball and badminton lead, as on the cover and in the README. Golf keeps
its example cards and is mentioned as an extra profile; it gets no hero sprite.

**Motion and behaviour.** Sections reveal with a short stepped (not smooth) animation.
Sprite idle loops use CSS `steps()` on sprite sheets. Everything animated stops under
`prefers-reduced-motion`. Works at 360 px width with no horizontal scroll.

**Assets.** Extend `tools/promo/make_pixel_cover.py` (or a sibling script) to export:
transparent sprite PNGs and small idle sprite sheets for both athletes at integer scale,
a pixel wordmark if text rendering in CSS is not crisp enough, and the README banner. All
outputs go under `docs/assets/pixel/`. The site scales them with
`image-rendering: pixelated`.

## Design: README

- Replace `docs/assets/readme/banner.png` at the top with a pixel banner (wide, short:
  starfield, gold frame, wordmark, both sprites, tagline), generated by the same script.
- The video block: the pixel cover image (or the existing teaser GIF) linking to YouTube,
  then the "▶ Watch on YouTube (2:08)" line. Builder's call which image; the owner liked
  the cover.
- Tidy only: keep sections, tables, examples-table markers and details blocks; trim the
  badge row to the useful ones; keep the language links. No pixel images per section.
- Apply the same top block to `README.zh-CN.md`.

## Left to the Builder

Exact body font, exact sprite animation frames, CSS techniques for pixel borders, the
copy-button implementation, the YouTube facade details, icon art for the level map, and
how the existing 3D player code is wrapped.

## Done When

- The site renders correctly on desktop and at 360 px, with no console errors, the
  3D bonus stage still plays, the video plays on click, and all links resolve.
- Pixel art is crisp at every size.
- README renders on GitHub with the new banner and working links.
- Changes are committed on `main` and pushed; the Pages deploy succeeds and the live
  site shows the new design.
