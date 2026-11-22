#!/usr/bin/env python
"""Render the promo cover (docs/assets/promo/cover.jpg, 1920x1080).

    python tools/promo/make_cover.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from make_banner import athlete_crop  # noqa: E402

W, H = 1920, 1080
INK = (11, 17, 29)
WHITE = (245, 247, 250)
MUTED = (165, 177, 196)
ORANGE = (255, 122, 69)
TEAL = (46, 196, 182)
VIOLET = (157, 134, 255)
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"
DIN = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"


def font(index: int, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(AVENIR, size, index=index)


def mix(color, alpha: float, base=INK):
    """Opaque blend (ImageDraw overwrites alpha on RGBA images)."""
    return tuple(int(c * alpha + b * (1 - alpha)) for c, b in zip(color, base))


def glow(canvas: Image.Image, box, color, alpha: int, blur: int) -> Image.Image:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(box, fill=(*color, alpha))
    return Image.alpha_composite(canvas, layer.filter(ImageFilter.GaussianBlur(blur)))


def tile_with_reflection(canvas: Image.Image, img: Image.Image, x: int, y: int, accent):
    w, h = img.size
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), 30, fill=255)
    # soft shadow + accent rim
    shadow = Image.new("RGBA", (w + 120, h + 120), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((60, 75, w + 60, h + 75), 34, fill=(0, 0, 0, 150))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(30)), (x - 60, y - 60))
    rim = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle((0, 0, w + 7, h + 7), 34, outline=(*accent, 255), width=4)
    top = img.convert("RGBA")
    top.putalpha(mask)
    canvas.alpha_composite(top, (x, y))
    canvas.alpha_composite(rim, (x - 4, y - 4))
    # mirror reflection
    rh = int(h * 0.42)
    ref = img.transpose(Image.FLIP_TOP_BOTTOM).crop((0, 0, w, rh)).convert("RGBA")
    fade = Image.linear_gradient("L").resize((w, rh)).point(lambda v: int((255 - v) * 0.32))
    rmask = Image.new("L", (w, rh), 0)
    ImageDraw.Draw(rmask).rounded_rectangle((0, -40, w, rh), 30, fill=255)
    ref.putalpha(ImageChops.multiply(fade, rmask))
    canvas.alpha_composite(ref.filter(ImageFilter.GaussianBlur(1.5)), (x, y + h + 14))


def pill(d: ImageDraw.ImageDraw, x: int, y: int, text: str, color, size: int = 30) -> int:
    f = font(2, size)
    w = int(d.textlength(text, font=f)) + 2 * int(size * 0.85)
    hgt = int(size * 1.9)
    d.rounded_rectangle((x, y, x + w, y + hgt), hgt // 2, fill=mix(color, 0.16),
                        outline=color, width=2)
    d.text((x + w / 2, y + hgt / 2), text, font=f, fill=color, anchor="mm")
    return w


def main() -> None:
    canvas = Image.new("RGBA", (W, H), (*INK, 255))
    canvas = glow(canvas, (1000, -380, 2300, 640), ORANGE, 70, 200)
    canvas = glow(canvas, (-400, 600, 700, 1500), TEAL, 40, 220)
    # faint diagonal motion lines
    lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    for i in range(-H, W, 70):
        ld.line([(i, H), (i + H, 0)], fill=(255, 255, 255, 7), width=1)
    canvas = Image.alpha_composite(canvas, lines)

    bb = athlete_crop("rayford-basketball", "release").resize((380, 487), Image.LANCZOS)
    bd = athlete_crop("chen-jingyi-badminton", "contact").resize((380, 487), Image.LANCZOS)
    tile_with_reflection(canvas, bb, 1080, 190, ORANGE)
    tile_with_reflection(canvas, bd, 1500, 190, VIOLET)
    d = ImageDraw.Draw(canvas)
    d.line((1060, 690, 1900, 690), fill=mix(WHITE, 0.35), width=2)

    # title block
    d.ellipse((120, 236, 160, 276), fill=ORANGE)
    d.text((182, 256), "MotionMirror", font=font(0, 112), fill=WHITE, anchor="lm")
    d.text((124, 372), "See your form,", font=font(5, 64), fill=WHITE)
    d.text((124, 450), "phase by phase.", font=font(5, 64), fill=ORANGE)
    d.text((126, 566), "One phone video in. Phases, metrics and", font=font(7, 34), fill=MUTED)
    d.text((126, 612), "plain-language feedback.", font=font(7, 34), fill=MUTED)
    x = 124
    x += pill(d, x, 700, "Basketball", ORANGE) + 18
    pill(d, x, 700, "Badminton", VIOLET)

    # play button + duration
    cx, cy, r = 170, 900, 58
    canvas = glow(canvas, (cx - 110, cy - 110, cx + 110, cy + 110), ORANGE, 90, 40)
    d = ImageDraw.Draw(canvas)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ORANGE)
    d.polygon([(cx - 18, cy - 28), (cx - 18, cy + 28), (cx + 30, cy)], fill=WHITE)
    d.text((cx + 92, cy - 20), "Watch the walkthrough", font=font(2, 38), fill=WHITE, anchor="lm")
    d.text((cx + 92, cy + 26), "2:08  ·  Narrated  ·  English", font=font(7, 30), fill=MUTED,
           anchor="lm")

    # small labels on the tiles
    for label, (tx, ty), color in (("JUMP SHOT · 120 FPS", (1080, 144), ORANGE),
                                   ("OVERHEAD · CONTACT", (1500, 144), VIOLET)):
        d.text((tx + 4, ty + 18), label, font=ImageFont.truetype(DIN, 32), fill=color, anchor="lm")

    out = ROOT / "docs" / "assets" / "promo" / "cover.jpg"
    canvas.convert("RGB").save(out, quality=92)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
