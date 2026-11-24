#!/usr/bin/env python
"""Pixel-art assets for the website and README, drawn by the cover's own code.

Exports, into docs/assets/pixel/ (native size, scaled in CSS with
image-rendering: pixelated):

    rayford.png, chen.png, shuttle.png   transparent sprites
    rayford-idle.png, chen-idle.png      2-frame idle sheets (frame 2 hops 1px)

and docs/assets/readme/banner-pixel.png (1920x480, the README banner).

    python tools/promo/make_pixel_assets.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _cover():
    spec = importlib.util.spec_from_file_location("make_pixel_cover", HERE / "make_pixel_cover.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = _cover()


def idle_sheet(sprite: Image.Image) -> Image.Image:
    """Two frames side by side: resting, then raised 1px (a small hop)."""
    w, h = sprite.size
    sheet = Image.new("RGBA", (2 * w, h + 1), (0, 0, 0, 0))
    sheet.alpha_composite(sprite, (0, 1))
    sheet.alpha_composite(sprite, (w, 0))
    return sheet


def banner() -> Image.Image:
    """320x80 README banner: starfield, both athletes, wordmark, tagline."""
    W, H, GRASS_TOP = 320, 80, 66
    img = Image.new("RGBA", (W, H), (*C.NAVY, 255))
    d = ImageDraw.Draw(img)
    C.stars(d, W, GRASS_TOP - 4, 30, seed=5, avoid=[(92, 10, 312, 64)])
    C.grass(d, W, GRASS_TOP, H)
    ray, ch = C.rayford(), C.chen()
    C.paste(img, ray, 22, GRASS_TOP - ray.height + 1, 1)
    C.paste(img, ch, 56, GRASS_TOP - ch.height + 1, 1)
    C.paste(img, C.shuttle(), 64, 12, 1)
    d = ImageDraw.Draw(img)
    x0 = 100
    C.text_l(d, x0, 14, "MOTION", 16, C.CREAM, shadow=C.OUTLINE)
    C.text_l(d, x0 + 104, 14, "MIRROR", 16, C.GOLD, shadow=C.OUTLINE)
    C.text_l(d, x0 + 1, 40, "SEE YOUR FORM,", 8, (196, 208, 230))
    C.text_l(d, x0 + 1, 51, "PHASE BY PHASE", 8, (196, 208, 230))
    C.text_l(d, x0 + 128, 40, "BASKETBALL", 8, C.GOLD)
    C.text_l(d, x0 + 128, 51, "BADMINTON", 8, (172, 150, 255))
    C.frame(d, W, H)
    return img


MIST = (196, 208, 230)
DIM = (140, 154, 186)
NAVY_3 = (26, 52, 96)

# README section labels, matching the website's stage tags.
STAGES = {
    "watch": ("STAGE 1", "WATCH"),
    "results": ("STAGE 2", "REAL RESULTS"),
    "gameplay": ("STAGE 3", "BUILT FOR GAMEPLAY"),
    "how": ("STAGE 4", "HOW IT WORKS"),
    "examples": ("STAGE 5", "LEVEL SELECT"),
    "compare": ("STAGE 6", "YOU VS. YOU"),
    "start": ("CONTINUE?", "QUICKSTART"),
    "dev": ("BONUS", "DEVELOPMENT"),
}


def stage_strip(no: str, label: str) -> Image.Image:
    """320x16 label: gold stage number, dim label, dotted gold trail."""
    W, H = 320, 16
    img = Image.new("RGBA", (W, H), (*C.NAVY, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 2, H - 1), fill=C.GOLD)
    C.text_l(d, 8, 4, no, 8, C.GOLD, shadow=C.OUTLINE)
    x = 8 + int(d.textlength(no + " ", font=C.font(8)))
    C.text_l(d, x, 4, "· " + label, 8, MIST)
    x += int(d.textlength("· " + label, font=C.font(8))) + 8
    for dx in range(x, W - 4, 6):
        d.rectangle((dx, 7, dx + 2, 8), fill=C.GOLD_DARK)
    return img


def hiscore() -> Image.Image:
    """320x40 arcade high-score strip with the site's four headline numbers."""
    W, H = 320, 40
    img = Image.new("RGBA", (W, H), (*C.NAVY_2, 255))
    d = ImageDraw.Draw(img)
    cells = (("3", "SPORTS"), ("6", "EXAMPLES"), ("33", "LANDMARKS"), ("1", "COMMAND"))
    cw = W / len(cells)
    for i, (num, lab) in enumerate(cells):
        cx = cw * i + cw / 2
        C.text_c(d, cx, 7, num, 16, C.GOLD, shadow=C.OUTLINE)
        C.text_c(d, cx, 27, lab, 8, MIST)
        if i:
            for y in range(6, H - 6, 4):
                d.rectangle((int(cw * i), y, int(cw * i) + 1, y + 1), fill=NAVY_3)
    C.frame(d, W, H, bg=C.NAVY)
    return img


def levelmap() -> Image.Image:
    """320x56 world map: five pads on a dotted path, labelled below."""
    W, H = 320, 56
    img = Image.new("RGBA", (W, H), (*C.NAVY_2, 255))
    d = ImageDraw.Draw(img)
    steps = (("1-1", "VIDEO"), ("1-2", "POSE"), ("1-3", "PHASES"),
             ("1-4", "METRICS"), ("GOAL", "REPORT"))
    cw = W / len(steps)
    pw, ph, py = 38, 18, 10
    for x in range(int(cw / 2), int(W - cw / 2), 8):
        d.rectangle((x, py + ph // 2 - 1, x + 3, py + ph // 2), fill=C.GOLD)
    for i, (pad, lab) in enumerate(steps):
        cx = int(cw * i + cw / 2)
        x0 = cx - pw // 2
        if i == len(steps) - 1:
            face, hi, lo = C.GRASS, C.GRASS_LIGHT, C.GRASS_DARK
        else:
            face, hi, lo = C.GOLD, (240, 204, 130), C.GOLD_DARK
        d.rectangle((x0 - 1, py - 1, x0 + pw, py + ph), fill=C.OUTLINE)
        d.rectangle((x0, py, x0 + pw - 1, py + ph - 1), fill=face)
        d.line((x0, py, x0 + pw - 1, py), fill=hi)
        d.line((x0, py + ph - 1, x0 + pw - 1, py + ph - 1), fill=lo)
        C.text_c(d, cx, py + 5, pad, 8, C.NAVY)
        C.text_c(d, cx, py + ph + 9, lab, 8, C.CREAM)
    C.frame(d, W, H, bg=C.NAVY)
    return img


def footer() -> Image.Image:
    """320x56 closing scene: starfield, both athletes on the grass."""
    W, H, GRASS_TOP = 320, 56, 46
    img = Image.new("RGBA", (W, H), (*C.NAVY, 255))
    d = ImageDraw.Draw(img)
    C.stars(d, W, GRASS_TOP - 4, 22, seed=9, avoid=[(130, 0, 190, GRASS_TOP)])
    C.grass(d, W, GRASS_TOP, H)
    ray, ch = C.rayford(), C.chen()
    C.paste(img, ray, 136, GRASS_TOP - ray.height + 1, 1)
    C.paste(img, ch, 160, GRASS_TOP - ch.height + 1, 1)
    return img


def _save_scaled(img: Image.Image, path: Path) -> Path:
    img.convert("RGB").resize((img.width * C.SCALE, img.height * C.SCALE), Image.NEAREST) \
        .save(path, optimize=True)
    return path


def export(out_dir: Path, readme_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    readme_dir.mkdir(parents=True, exist_ok=True)
    sprites = {"rayford": C.rayford(), "chen": C.chen(), "shuttle": C.shuttle()}
    paths: dict[str, Path] = {}
    for name, img in sprites.items():
        paths[name] = out_dir / f"{name}.png"
        img.save(paths[name], optimize=True)
    for name in ("rayford", "chen"):
        paths[f"{name}-idle"] = out_dir / f"{name}-idle.png"
        idle_sheet(sprites[name]).save(paths[f"{name}-idle"], optimize=True)
    paths["banner"] = _save_scaled(banner(), readme_dir / "banner-pixel.png")
    for key, (no, label) in STAGES.items():
        paths[f"stage-{key}"] = _save_scaled(stage_strip(no, label), readme_dir / f"stage-{key}.png")
    paths["hiscore"] = _save_scaled(hiscore(), readme_dir / "hiscore.png")
    paths["levelmap"] = _save_scaled(levelmap(), readme_dir / "levelmap.png")
    paths["footer"] = _save_scaled(footer(), readme_dir / "footer.png")
    return paths


def main() -> None:
    for path in export(ROOT / "docs" / "assets" / "pixel", ROOT / "docs" / "assets" / "readme").values():
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
