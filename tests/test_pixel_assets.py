"""The pixel-art site assets are exported from the same sprites as the cover."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")
pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parents[1]


def _load_exporter():
    path = ROOT / "tools" / "promo" / "make_pixel_assets.py"
    spec = importlib.util.spec_from_file_location("make_pixel_assets", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_export_writes_assets(tmp_path):
    paths = _load_exporter().export(tmp_path / "pixel", tmp_path / "readme")

    for name in ("rayford", "chen", "shuttle", "rayford-idle", "chen-idle", "banner"):
        assert paths[name].exists(), name

    for name in ("rayford", "chen", "shuttle"):
        img = Image.open(paths[name])
        assert img.mode == "RGBA"
        assert img.getpixel((0, 0))[3] == 0, f"{name} corner should be transparent"

    for name in ("rayford", "chen"):
        sprite = Image.open(paths[name])
        sheet = Image.open(paths[f"{name}-idle"])
        assert sheet.mode == "RGBA"
        assert sheet.width == 2 * sprite.width
        assert sheet.height == sprite.height + 1

    assert Image.open(paths["banner"]).size == (1920, 480)
