#!/usr/bin/env python
"""Pixel-art promo cover in the style of a retro handheld RPG battle screen.

The two athletes become real pixel sprites: MediaPipe person segmentation cuts
them out of the actual frames, then they are downsampled, palette-reduced and
outlined. Everything is composed on a 320x180 canvas and scaled 6x with
nearest-neighbour, so every pixel stays crisp at 1920x1080.

    python tools/promo/make_pixel_cover.py

Font: Press Start 2P (SIL OFL 1.1, tools/promo/fonts/OFL.txt).
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PIXEL_FONT = str(HERE / "fonts" / "PressStart2P-Regular.ttf")
LW, LH, SCALE = 320, 180, 6

OUTLINE = (24, 22, 38)
WHITE = (248, 248, 240)
INK = (40, 40, 56)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(PIXEL_FONT, size)


# ----------------------------------------------------------------- sprites ---

def person_cutout(video: Path, frame_idx: int, pose: dict, zoom: float):
    """Return (RGBA crop of the athlete, landmarks in crop pixel coords)."""

    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    from motionmirror.video import ensure_model

    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError(f"cannot read frame {frame_idx} of {video}")
    h, w = frame.shape[:2]
    lm = pose["landmarks"]
    xs = [p["x"] * w for p in lm.values()]
    ys = [p["y"] * h for p in lm.values()]
    bh = (max(ys) - min(ys)) * zoom
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    side = int(max(bh, (max(xs) - min(xs)) * zoom))
    x0, y0 = int(max(0, cx - side / 2)), int(max(0, cy - side / 2))
    x1, y1 = int(min(w, x0 + side)), int(min(h, y0 + side))
    crop = frame[y0:y1, x0:x1]
    up = cv2.resize(crop, (768, int(768 * crop.shape[0] / crop.shape[1])),
                    interpolation=cv2.INTER_CUBIC)

    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(ensure_model("heavy"))),
        running_mode=vision.RunningMode.IMAGE, num_poses=1,
        output_segmentation_masks=True)
    with vision.PoseLandmarker.create_from_options(options) as lmk:
        res = lmk.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                  data=cv2.cvtColor(up, cv2.COLOR_BGR2RGB)))
    if not res.segmentation_masks:
        raise RuntimeError("no person mask")
    mask = res.segmentation_masks[0].numpy_view()
    rgba = np.dstack([cv2.cvtColor(up, cv2.COLOR_BGR2RGB),
                      (mask > 0.5).astype(np.uint8) * 255])
    sx, sy = up.shape[1] / (x1 - x0), up.shape[0] / (y1 - y0)
    pts = {n: ((p["x"] * w - x0) * sx, (p["y"] * h - y0) * sy) for n, p in lm.items()}
    return Image.fromarray(rgba, "RGBA"), pts


def pixelate(cut: Image.Image, pts: dict, height: int, colors: int = 14):
    """Trim, downsample to ``height`` px, reduce the palette, add an outline."""

    box = cut.getchannel("A").getbbox()
    cut = cut.crop(box)
    pts = {n: (x - box[0], y - box[1]) for n, (x, y) in pts.items()}
    s = height / cut.height
    small = cut.resize((max(1, round(cut.width * s)), height), Image.BOX)
    pts = {n: (x * s, y * s) for n, (x, y) in pts.items()}
    alpha = small.getchannel("A").point(lambda v: 255 if v > 110 else 0)
    rgb = small.convert("RGB")
    # gentle contrast/saturation lift so the sprite reads at tiny size
    arr = np.asarray(rgb).astype(np.float32)
    gray = arr.mean(axis=2, keepdims=True)
    arr = np.clip(gray + (arr - gray) * 1.35, 0, 255)
    arr = np.clip((arr - 128) * 1.12 + 136, 0, 255).astype(np.uint8)
    rgb = Image.fromarray(arr).quantize(colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    sprite = rgb.convert("RGBA")
    sprite.putalpha(alpha)
    # 1px dark outline around the silhouette
    pad = Image.new("RGBA", (sprite.width + 2, sprite.height + 2), (0, 0, 0, 0))
    pad.alpha_composite(sprite, (1, 1))
    a = np.asarray(pad.getchannel("A")) > 0
    ring = np.zeros_like(a)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        ring |= np.roll(np.roll(a, dy, 0), dx, 1)
    ring &= ~a
    px = pad.load()
    for y, x in zip(*np.nonzero(ring)):
        px[int(x), int(y)] = (*OUTLINE, 255)
    pts = {n: (x + 1, y + 1) for n, (x, y) in pts.items()}
    return pad, pts


def load_sprite(name: str, phase: str, height: int, zoom: float):
    folder = ROOT / "examples" / name
    rep = json.loads((folder / "report.json").read_text())
    rep = rep["reps"][-1]
    idx = rep["phases"][phase]["frame"]
    poses = {p["frame_index"]: p for p in json.loads((folder / "pose.json").read_text())["frames"]}
    pose = poses[min(poses, key=lambda k: abs(k - idx))]
    video = next(folder.glob("*.mp4")) if not (folder / f"{name.split('-')[-1]}.mp4").exists() \
        else folder / f"{name.split('-')[-1]}.mp4"
    cut, pts = person_cutout(video, idx, pose, zoom)
    return pixelate(cut, pts, height)


# ------------------------------------------------------------------ scenery ---

def dither_bands(img: Image.Image, top: int, bottom: int, colors: list[tuple]):
    """Vertical gradient with 2x2 ordered dithering between colour bands."""

    d = img.load()
    bayer = [[0, 2], [3, 1]]
    n = len(colors) - 1
    for y in range(top, bottom):
        t = (y - top) / max(1, bottom - top - 1) * n
        i = min(int(t), n - 1)
        frac = t - i
        for x in range(LW):
            c = colors[i + 1] if frac * 4 > bayer[y % 2][x % 2] + 0.5 else colors[i]
            d[x, y] = c


def cloud(dr: ImageDraw.ImageDraw, x: int, y: int, w: int):
    for cx, cy, r in ((x, y, w // 4), (x + w // 4, y - 3, w // 3), (x + w // 2, y, w // 4)):
        dr.ellipse((cx - r, cy - r // 2, cx + r, cy + r // 2), fill=WHITE)
    dr.rectangle((x - w // 4, y, x + w // 2 + w // 4, y + 2), fill=WHITE)


def platform(dr: ImageDraw.ImageDraw, cx: int, cy: int, rx: int, ry: int):
    dr.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(86, 150, 70), outline=OUTLINE)
    dr.ellipse((cx - rx + 6, cy - ry + 2, cx + rx - 6, cy + ry - 3), fill=(112, 182, 86))
    dr.ellipse((cx - rx // 2, cy - ry // 3, cx + rx // 3, cy + 1), fill=(140, 206, 104))


def panel(dr: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int):
    dr.rectangle((x + 2, y + 2, x + w + 2, y + h + 2), fill=OUTLINE)  # drop shadow
    dr.rectangle((x, y, x + w, y + h), fill=(248, 244, 224), outline=OUTLINE)
    dr.rectangle((x + 2, y + 2, x + w - 2, y + h - 2), outline=(176, 168, 140))


def bar(dr: ImageDraw.ImageDraw, x: int, y: int, w: int, frac: float, color):
    dr.rectangle((x, y, x + w, y + 4), fill=OUTLINE)
    dr.rectangle((x + 1, y + 1, x + w - 1, y + 3), fill=(80, 80, 96))
    dr.rectangle((x + 1, y + 1, x + 1 + int((w - 2) * frac), y + 3), fill=color)
    dr.line((x + 1, y + 1, x + 1 + int((w - 2) * frac), y + 1),
            fill=tuple(min(255, c + 60) for c in color))


def text(dr, xy, s, size=8, fill=INK, shadow=None):
    if shadow:
        dr.text((xy[0] + 1, xy[1] + 1), s, font=font(size), fill=shadow)
    dr.text(xy, s, font=font(size), fill=fill)


# -------------------------------------------------------------------- main ---

def main() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "src"))

    bb_rep = json.loads((ROOT / "examples/rayford-basketball/report.json").read_text())["reps"][0]
    bd = json.loads((ROOT / "examples/chen-jingyi-badminton/report.json").read_text())

    canvas = Image.new("RGB", (LW, LH))
    dither_bands(canvas, 0, 92, [(88, 136, 248), (128, 176, 248), (184, 216, 248), (232, 240, 248)])
    dr = ImageDraw.Draw(canvas)
    # sea horizon (Rayford's oceanside court) and the field
    dr.rectangle((0, 86, LW, 92), fill=(56, 112, 200))
    for x in range(0, LW, 7):
        dr.point((x + (x // 7) % 3, 88), fill=(150, 196, 248))
    dither_bands(canvas, 92, 134, [(126, 198, 96), (104, 176, 80), (88, 156, 68)])
    dr = ImageDraw.Draw(canvas)
    for x0 in range(-40, LW, 24):  # mown stripes
        dr.polygon([(x0, 134), (x0 + 12, 134), (x0 + 30, 92), (x0 + 24, 92)], fill=(116, 188, 88))
    dr.ellipse((262, 10, 286, 34), fill=(255, 236, 140), outline=(255, 214, 96))
    cloud(dr, 168, 60, 26)
    cloud(dr, 300, 46, 22)
    cloud(dr, 30, 34, 20)

    # platforms + sprites (badminton "opponent" top-right, basketball "player" bottom-left)
    platform(dr, 236, 100, 46, 9)
    platform(dr, 84, 129, 54, 10)
    bd_sprite, bd_pts = load_sprite("chen-jingyi-badminton", "contact", 62, 1.25)
    bb_sprite, bb_pts = load_sprite("rayford-basketball", "release", 54, 1.3)
    bdx, bdy = 236 - bd_sprite.width // 2, 100 - bd_sprite.height + 3
    bbx, bby = 84 - bb_sprite.width // 2, 129 - bb_sprite.height + 3
    canvas.paste(bd_sprite, (bdx, bdy), bd_sprite)
    canvas.paste(bb_sprite, (bbx, bby), bb_sprite)
    dr = ImageDraw.Draw(canvas)
    # pixel props: shuttle racket from the racket wrist, ball above the shooting hands
    side = bd["side"]
    ex, ey = bd_pts[f"{side}_elbow"]
    wx, wy = bd_pts[f"{side}_wrist"]
    vx, vy = wx - ex, wy - ey
    norm = max(1e-6, (vx * vx + vy * vy) ** 0.5)
    hx, hy = wx + vx / norm * 9 + bdx, wy + vy / norm * 9 + bdy
    dr.line((wx + bdx, wy + bdy, hx, hy), fill=OUTLINE, width=1)
    dr.ellipse((hx - 4, hy - 6, hx + 4, hy + 2), outline=OUTLINE, fill=(232, 236, 240))
    dr.line((hx - 2, hy - 4, hx + 2, hy), fill=(170, 176, 190))
    lw_, rw_ = bb_pts["left_wrist"], bb_pts["right_wrist"]
    bx, byy = (lw_[0] + rw_[0]) / 2 + bbx, min(lw_[1], rw_[1]) + bby - 6
    dr.ellipse((bx - 4, byy - 4, bx + 4, byy + 4), fill=(232, 112, 48), outline=OUTLINE)
    dr.line((bx - 4, byy, bx + 4, byy), fill=OUTLINE)
    dr.arc((bx - 2, byy - 4, bx + 6, byy + 4), 100, 260, fill=OUTLINE)

    # status panels, each next to its own athlete
    ok = sum(f["status"] == "ok" for f in bb_rep["findings"])
    tot = len(bb_rep["findings"])
    panel(dr, 8, 42, 122, 26)
    text(dr, (14, 47), "RAYFORD", 8)
    text(dr, (86, 47), f"{ok}/{tot}", 8, fill=(40, 140, 72))
    text(dr, (14, 57), "SHOT", 8, fill=(200, 96, 40))
    bar(dr, 50, 58, 74, ok / tot, (72, 200, 96))

    n_strokes = bd["rep_count"]
    panel(dr, 176, 106, 136, 26)
    text(dr, (182, 111), "CHEN JINGYI", 8)
    text(dr, (182, 121), f"STROKES x{n_strokes}", 8, fill=(112, 84, 200))

    # title
    title = "MOTIONMIRROR"
    tw = dr.textlength(title, font=font(16))
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (2, 2), (1, 2), (2, 1)):
        dr.text(((LW - tw) / 2 + dx, 8 + dy), title, font=font(16), fill=OUTLINE)
    dr.text(((LW - tw) / 2, 8), title, font=font(16), fill=(255, 204, 64))
    sub = "SEE YOUR FORM"
    sw = dr.textlength(sub, font=font(8))
    text(dr, ((LW - sw) / 2, 29), sub, 8, fill=WHITE, shadow=OUTLINE)

    # dialogue box
    dr.rectangle((4, 136, LW - 5, LH - 4), fill=OUTLINE)
    dr.rectangle((6, 138, LW - 7, LH - 6), fill=(248, 248, 248))
    dr.rectangle((8, 140, LW - 9, LH - 8), outline=(96, 176, 232))
    text(dr, (16, 147), "Analyze every phase of your", 8)
    text(dr, (16, 160), "shot and stroke. PRESS PLAY!", 8)
    dr.polygon([(LW - 22, 162), (LW - 14, 162), (LW - 18, 167)], fill=(232, 80, 64))
    text(dr, (LW - 74, 147), "2:08", 8, fill=(140, 140, 160))

    out = ROOT / "docs" / "assets" / "promo" / "cover-pixel.png"
    canvas.resize((LW * SCALE, LH * SCALE), Image.NEAREST).save(out, optimize=True)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
