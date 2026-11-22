#!/usr/bin/env python
"""Render docs/assets/readme/banner.png: three analyzed frames with a mirror reflection.

    python tools/make_banner.py
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1800, 640
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"
TILES = [("rayford-basketball", "release"), ("chen-jingyi-badminton", "contact")]


def font(index: int, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(AVENIR, size, index=index)


def athlete_crop(name: str, phase: str) -> Image.Image:
    folder = ROOT / "examples" / name
    rep = json.loads((folder / "report.json").read_text())["reps"][-1]
    idx = rep["phases"][phase]["frame"]
    poses = {p["frame_index"]: p for p in json.loads((folder / "pose.json").read_text())["frames"]}
    clean = ROOT / "tools" / "promo" / ".cache" / f"{name}-clean.mp4"
    cap = cv2.VideoCapture(str(clean if clean.exists() else folder / "overlay.mp4"))
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, img = cap.read()
    if not ok:
        raise RuntimeError(f"cannot read frame {idx} of {name}")
    h, w = img.shape[:2]
    lm = poses[min(poses, key=lambda k: abs(k - idx))]["landmarks"]
    xs, ys = [p["x"] for p in lm.values()], [p["y"] for p in lm.values()]
    bh = (max(ys) - min(ys)) * h * 1.35
    bw = bh * 0.78
    cx, cy = np.mean(xs) * w, (min(ys) + max(ys)) / 2 * h
    x0 = int(max(0, min(w - bw, cx - bw / 2)))
    y0 = int(max(0, min(h - bh, cy - bh / 2)))
    crop = img[y0:y0 + int(bh), x0:x0 + int(bw)]
    return Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)).resize((300, 385), Image.LANCZOS)


def main() -> None:
    bg = Image.new("RGBA", (W, H), (11, 17, 29, 255))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((900, -300, 2100, 500), fill=(255, 122, 69, 60))
    bg = Image.alpha_composite(bg, glow.filter(ImageFilter.GaussianBlur(180)))

    x = 1000
    for name, phase in TILES:
        tile = athlete_crop(name, phase)
        mask = Image.new("L", tile.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, *tile.size), 22, fill=255)
        top = tile.convert("RGBA")
        top.putalpha(mask)
        bg.alpha_composite(top, (x, 70))
        # the "mirror": a flipped, fading, slightly blurred reflection
        ref = tile.transpose(Image.FLIP_TOP_BOTTOM).crop((0, 0, 300, 170)).convert("RGBA")
        fade = Image.linear_gradient("L").resize((300, 170)).point(lambda v: int((255 - v) * 0.35))
        rmask = Image.new("L", (300, 170), 0)
        ImageDraw.Draw(rmask).rounded_rectangle((0, -30, 300, 170), 22, fill=255)
        ref.putalpha(ImageChops.multiply(fade, rmask))
        bg.alpha_composite(ref.filter(ImageFilter.GaussianBlur(1.2)), (x, 463))
        x += 315

    d = ImageDraw.Draw(bg, "RGBA")
    d.line((1000, 462, 1615, 462), fill=(96, 104, 118), width=2)
    d.ellipse((90, 150, 124, 184), fill=(255, 122, 69, 255))
    d.text((140, 167), "MotionMirror", font=font(0, 92), fill=(245, 247, 250), anchor="lm")
    d.text((92, 262), "See your form, phase by phase.", font=font(5, 40), fill=(170, 182, 200))
    d.text((92, 330), "Golf · Basketball · Badminton, from one phone video:", font=font(7, 30),
           fill=(170, 182, 200))
    d.text((92, 372), "pose, phases, metrics and plain-language feedback.", font=font(7, 30),
           fill=(170, 182, 200))
    xx = 92
    for label, color in (("Open source", (46, 196, 182)), ("Explainable", (255, 196, 61)),
                         ("Honest about limits", (255, 122, 69))):
        w = d.textlength(label, font=font(2, 24)) + 40
        # opaque mix with the backdrop: ImageDraw overwrites alpha on RGBA images
        tint = tuple(int(c * 0.18 + b * 0.82) for c, b in zip(color, (11, 17, 29)))
        d.rounded_rectangle((xx, 450, xx + w, 494), 22, fill=tint, outline=color, width=2)
        d.text((xx + 20, 472), label, font=font(2, 24), fill=color, anchor="lm")
        xx += w + 16
    out = ROOT / "docs" / "assets" / "readme" / "banner.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.convert("RGB").save(out, optimize=True)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
