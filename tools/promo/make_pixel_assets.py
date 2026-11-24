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
    b = banner()
    paths["banner"] = readme_dir / "banner-pixel.png"
    b.convert("RGB").resize((b.width * C.SCALE, b.height * C.SCALE), Image.NEAREST) \
        .save(paths["banner"], optimize=True)
    return paths


def main() -> None:
    for path in export(ROOT / "docs" / "assets" / "pixel", ROOT / "docs" / "assets" / "readme").values():
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
