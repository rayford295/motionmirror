#!/usr/bin/env python
"""Pixel-art promo covers, horizontal (1920x1080) and vertical (1080x1920).

Chibi sprites of the two flagship athletes are drawn in code (filled shapes on
a tiny canvas, then an automatic 1px outline), composed on a low-resolution
canvas and scaled 6x with nearest-neighbour so every pixel stays crisp.

    python tools/promo/make_pixel_cover.py

Font: Press Start 2P (SIL OFL 1.1, tools/promo/fonts/OFL.txt).
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "assets" / "promo"
PIXEL_FONT = str(HERE / "fonts" / "PressStart2P-Regular.ttf")
SCALE = 6

NAVY = (13, 29, 54)
NAVY_2 = (19, 40, 72)
GOLD = (214, 168, 88)
GOLD_DARK = (150, 108, 48)
CREAM = (246, 232, 200)
OUTLINE = (30, 22, 34)
GRASS = (118, 190, 90)
GRASS_DARK = (92, 162, 72)
GRASS_LIGHT = (146, 210, 108)

SKIN = (246, 204, 168)
SKIN_SH = (222, 170, 136)
BLUSH = (240, 150, 150)
HAIR = (44, 30, 32)
HAIR_HI = (86, 60, 56)
TOP = (246, 236, 214)
TOP_SH = (222, 206, 172)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(PIXEL_FONT, size)


# ----------------------------------------------------------------- sprites ---

def outline(sprite: Image.Image) -> Image.Image:
    """Add a 1px dark outline around every opaque pixel."""

    w, h = sprite.size
    pad = Image.new("RGBA", (w + 2, h + 2), (0, 0, 0, 0))
    pad.alpha_composite(sprite, (1, 1))
    a = np.asarray(pad.getchannel("A")) > 0
    ring = np.zeros_like(a)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        ring |= np.roll(np.roll(a, dy, 0), dx, 1)
    ring &= ~a
    px = pad.load()
    for y, x in zip(*np.nonzero(ring)):
        px[int(x), int(y)] = (*OUTLINE, 255)
    return pad


def face(d: ImageDraw.ImageDraw, x: int, y: int):
    """8x8 head block at (x, y): skin, eyes, blush, mouth."""
    d.rectangle((x, y, x + 7, y + 7), fill=SKIN)
    d.point((x + 2, y + 4), fill=OUTLINE)
    d.point((x + 5, y + 4), fill=OUTLINE)
    d.point((x + 2, y + 3), fill=(255, 255, 255))
    d.point((x + 1, y + 5), fill=BLUSH)
    d.point((x + 6, y + 5), fill=BLUSH)
    d.point((x + 3, y + 6), fill=(214, 110, 110))
    d.point((x + 4, y + 6), fill=(214, 110, 110))


def rayford() -> Image.Image:
    """Basketball shooter: navy jersey, light pants, ball held overhead."""
    s = Image.new("RGBA", (24, 36), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.ellipse((8, 0, 15, 7), fill=(232, 112, 48))           # ball
    d.line((11, 0, 11, 7), fill=(150, 62, 26))
    d.line((8, 3, 15, 3), fill=(150, 62, 26))
    d.point((9, 1), fill=(252, 170, 110))
    d.rectangle((5, 7, 6, 18), fill=SKIN)                   # arms up, clear of the head
    d.rectangle((17, 7, 18, 18), fill=SKIN)
    d.rectangle((6, 5, 8, 6), fill=SKIN)                    # hands on the ball
    d.rectangle((15, 5, 17, 6), fill=SKIN)
    d.rectangle((5, 19, 7, 20), fill=(38, 56, 112))         # shoulders
    d.rectangle((16, 19, 18, 20), fill=(38, 56, 112))
    face(d, 8, 10)                                          # head + hair
    d.rectangle((8, 8, 15, 11), fill=HAIR)
    d.point((8, 12), fill=HAIR)
    d.point((15, 12), fill=HAIR)
    d.line((10, 8, 13, 8), fill=HAIR_HI)
    d.rectangle((11, 18, 12, 18), fill=SKIN_SH)             # neck
    d.rectangle((8, 19, 15, 26), fill=(38, 56, 112))        # jersey
    d.rectangle((8, 19, 9, 26), fill=(30, 44, 92))
    d.line((10, 19, 13, 19), fill=(236, 236, 244))
    d.rectangle((11, 21, 12, 24), fill=(236, 236, 244))     # number 1
    d.point((10, 21), fill=(236, 236, 244))
    d.rectangle((8, 27, 15, 33), fill=(214, 214, 222))      # pants
    d.rectangle((8, 27, 9, 33), fill=(176, 176, 190))
    d.line((12, 29, 12, 33), fill=(176, 176, 190))
    d.rectangle((7, 34, 11, 35), fill=(250, 250, 250))      # shoes
    d.rectangle((12, 34, 16, 35), fill=(250, 250, 250))
    d.line((7, 35, 11, 35), fill=(232, 112, 48))
    d.line((12, 35, 16, 35), fill=(232, 112, 48))
    return outline(s)


def chen() -> Image.Image:
    """Badminton player: cream top, grey leggings, ponytail, racket raised."""
    s = Image.new("RGBA", (26, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.ellipse((1, 0, 8, 8), fill=(60, 186, 176))            # racket frame
    d.ellipse((2, 1, 7, 7), fill=(240, 244, 246))           # strings
    for gx in (3, 5):
        d.line((gx, 2, gx, 6), fill=(196, 206, 214))
    d.line((3, 4, 6, 4), fill=(196, 206, 214))
    d.line((5, 8, 6, 11), fill=(232, 96, 140))              # handle
    d.rectangle((6, 11, 7, 12), fill=SKIN)                  # raised hand
    d.rectangle((6, 13, 7, 21), fill=TOP)                   # raised sleeve
    d.line((6, 13, 6, 21), fill=TOP_SH)
    face(d, 9, 13)                                          # head
    d.rectangle((9, 11, 16, 14), fill=HAIR)                 # hair + bangs
    d.point((9, 15), fill=HAIR)
    d.point((16, 15), fill=HAIR)
    d.rectangle((17, 12, 18, 18), fill=HAIR)                # ponytail
    d.point((19, 17), fill=HAIR)
    d.line((11, 11, 14, 11), fill=HAIR_HI)
    d.rectangle((12, 21, 13, 21), fill=SKIN_SH)             # neck
    d.rectangle((8, 22, 17, 29), fill=TOP)                  # long-sleeve top
    d.rectangle((8, 22, 9, 29), fill=TOP_SH)
    d.rectangle((18, 22, 19, 28), fill=TOP)                 # lowered arm
    d.rectangle((18, 29, 19, 29), fill=SKIN)
    d.rectangle((9, 30, 16, 36), fill=(150, 150, 164))      # leggings
    d.rectangle((9, 30, 10, 36), fill=(122, 122, 138))
    d.line((13, 32, 13, 36), fill=(122, 122, 138))
    d.rectangle((8, 37, 12, 38), fill=(250, 250, 250))      # shoes
    d.rectangle((13, 37, 17, 38), fill=(250, 250, 250))
    return outline(s)


def shuttle() -> Image.Image:
    s = Image.new("RGBA", (6, 7), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.polygon([(0, 0), (5, 0), (4, 4), (1, 4)], fill=(250, 250, 250))
    d.line((1, 1, 4, 1), fill=(210, 214, 220))
    d.rectangle((1, 5, 4, 6), fill=GOLD)
    return outline(s)


# ------------------------------------------------------------------ scenery ---

def stars(d: ImageDraw.ImageDraw, w: int, h: int, n: int, seed: int, avoid=()):
    rnd = random.Random(seed)
    placed = 0
    while placed < n:
        x, y = rnd.randrange(6, w - 6), rnd.randrange(6, h)
        if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in avoid):
            continue
        c = rnd.choice([(255, 236, 170), GOLD, (190, 204, 236)])
        d.point((x, y), fill=c)
        if rnd.random() < 0.15:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                d.point((x + dx, y + dy), fill=(120, 108, 82))
        placed += 1


def grass(d: ImageDraw.ImageDraw, w: int, top: int, bottom: int):
    d.rectangle((0, top, w, bottom), fill=GRASS)
    for x in range(0, w, 6):
        d.rectangle((x, top + 3, x + 2, bottom), fill=GRASS_DARK)
    d.rectangle((0, top, w, top + 1), fill=GRASS_LIGHT)
    for x in range(1, w, 9):
        d.point((x, top - 1), fill=GRASS)
        d.point((x + 4, top + 2), fill=GRASS_LIGHT)


def frame(d: ImageDraw.ImageDraw, w: int, h: int, bg=(255, 255, 255)):
    """Rounded gold border, like the reference banner."""
    d.rounded_rectangle((0, 0, w - 1, h - 1), 4, outline=GOLD_DARK, width=1)
    d.rounded_rectangle((1, 1, w - 2, h - 2), 3, outline=GOLD, width=2)
    for cx, cy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):  # transparent-looking corners
        sx, sy = (1 if cx == 0 else -1), (1 if cy == 0 else -1)
        for dx in range(2):
            for dy in range(2 - dx):
                d.point((cx + sx * dx, cy + sy * dy), fill=bg)


def text_c(d, cx: float, y: int, s: str, size: int, fill, shadow=None):
    w = d.textlength(s, font=font(size))
    if shadow:
        d.text((cx - w / 2 + 1, y + 1), s, font=font(size), fill=shadow)
    d.text((cx - w / 2, y), s, font=font(size), fill=fill)


def text_l(d, x: int, y: int, s: str, size: int, fill, shadow=None):
    if shadow:
        d.text((x + 1, y + 1), s, font=font(size), fill=shadow)
    d.text((x, y), s, font=font(size), fill=fill)


def button(d, x: int, y: int, label: str) -> int:
    w = int(d.textlength(label, font=font(8))) + 12
    d.rectangle((x + 1, y + 1, x + w + 1, y + 13), fill=GOLD_DARK)
    d.rectangle((x, y, x + w, y + 12), fill=GOLD)
    d.line((x + 1, y + 1, x + w - 1, y + 1), fill=(240, 204, 130))
    d.text((x + 6, y + 3), label, font=font(8), fill=NAVY)
    return w


def paste(canvas: Image.Image, sprite: Image.Image, x: int, y: int, k: int):
    canvas.alpha_composite(sprite.resize((sprite.width * k, sprite.height * k), Image.NEAREST),
                           (x, y))


# -------------------------------------------------------------------- views ---

def horizontal() -> Image.Image:
    W, H = 320, 180
    img = Image.new("RGBA", (W, H), (*NAVY, 255))
    d = ImageDraw.Draw(img)
    stars(d, W, 140, 42, seed=7, avoid=[(146, 30, 316, 146)])
    grass(d, W, 146, H)
    k = 2
    ray, ch = rayford(), chen()
    paste(img, ray, 24, 146 - ray.height * k + 2, k)
    paste(img, ch, 84, 146 - ch.height * k + 2, k)
    paste(img, shuttle(), 94, 50, 1)
    d = ImageDraw.Draw(img)
    x0 = 152
    text_l(d, x0, 34, "MOTION", 16, CREAM, shadow=OUTLINE)
    text_l(d, x0, 54, "MIRROR", 16, GOLD, shadow=OUTLINE)
    text_l(d, x0 + 1, 80, "SEE YOUR FORM,", 8, (196, 208, 230))
    text_l(d, x0 + 1, 91, "PHASE BY PHASE", 8, (196, 208, 230))
    text_l(d, x0 + 1, 106, "BASKETBALL", 8, GOLD)
    text_l(d, x0 + 1, 117, "BADMINTON", 8, (172, 150, 255))
    bw = button(d, x0, 130, "PRESS PLAY")
    text_l(d, x0 + bw + 8, 133, "2:08", 8, (140, 154, 186))
    frame(d, W, H)
    return img


def vertical() -> Image.Image:
    W, H = 180, 320
    img = Image.new("RGBA", (W, H), (*NAVY, 255))
    d = ImageDraw.Draw(img)
    stars(d, W, 276, 58, seed=11, avoid=[(10, 24, 170, 146)])
    grass(d, W, 284, H)
    text_c(d, W / 2, 28, "MOTION", 24, CREAM, shadow=OUTLINE)
    text_c(d, W / 2, 58, "MIRROR", 24, GOLD, shadow=OUTLINE)
    text_c(d, W / 2, 96, "SEE YOUR FORM,", 8, (196, 208, 230))
    text_c(d, W / 2, 107, "PHASE BY PHASE", 8, (196, 208, 230))
    text_c(d, W / 2, 124, "BASKETBALL", 8, GOLD)
    text_c(d, W / 2, 135, "BADMINTON", 8, (172, 150, 255))
    k = 3
    ray, ch = rayford(), chen()
    paste(img, ray, 10, 284 - ray.height * k + 3, k)
    paste(img, ch, 94, 284 - ch.height * k + 3, k)
    paste(img, shuttle(), 112, 152, 2)
    d = ImageDraw.Draw(img)
    bw = int(d.textlength("PRESS PLAY", font=font(8))) + 12
    button(d, int(W / 2 - bw / 2), 298, "PRESS PLAY")
    frame(d, W, H)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, img in (("cover-pixel.png", horizontal()), ("cover-pixel-vertical.png", vertical())):
        path = OUT / name
        img.convert("RGB").resize((img.width * SCALE, img.height * SCALE), Image.NEAREST) \
            .save(path, optimize=True)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
