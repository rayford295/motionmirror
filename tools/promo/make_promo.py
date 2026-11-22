#!/usr/bin/env python
"""Render the MotionMirror promo video from the flagship example outputs.

    python tools/promo/make_promo.py               # free edge-tts neural voice (default)
    python tools/promo/make_promo.py --tts elevenlabs   # needs ~/.elevenlabs_key
    python tools/promo/make_promo.py --no-voice    # silent preview with estimated timing

Narration clips are cached in tools/promo/voice/, so later re-renders are offline.
Output: docs/assets/promo/motionmirror-promo.mp4 (+ poster.jpg).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import urllib.request
import wave
from functools import cache, lru_cache
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from script import MODEL_ID, SCENES, VOICE_ID  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
VOICE_DIR = HERE / "voice"
OUT_DIR = ROOT / "docs" / "assets" / "promo"
W, H, FPS = 1920, 1080, 30
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

BB = ROOT / "examples" / "rayford-basketball"
BD = ROOT / "examples" / "chen-jingyi-badminton"

INK = (14, 20, 32)
WHITE = (245, 247, 250)
MUTED = (160, 172, 190)
ORANGE = (255, 122, 69)
TEAL = (46, 196, 182)
GOLD = (255, 196, 61)
RED = (240, 84, 79)
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"
DIN = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
WEIGHT = {"bold": 0, "demi": 2, "medium": 5, "regular": 7, "heavy": 8, "light": 10}


@cache
def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    if weight == "din":
        return ImageFont.truetype(DIN, size)
    return ImageFont.truetype(AVENIR, size, index=WEIGHT[weight])


class BlendDraw:
    """ImageDraw that alpha-blends onto RGBA images (Pillow overwrites pixels there)."""

    MEASURE = {"textlength", "textbbox"}

    def __init__(self, img: Image.Image):
        self.img = img

    def __getattr__(self, name):
        def call(*args, **kwargs):
            if name in self.MEASURE:
                return getattr(ImageDraw.Draw(self.img), name)(*args, **kwargs)
            overlay = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
            result = getattr(ImageDraw.Draw(overlay), name)(*args, **kwargs)
            self.img.alpha_composite(overlay)
            return result
        return call


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def appear(t: float, start: float, dur: float = 0.5) -> float:
    return ease((t - start) / dur)


# ------------------------------------------------------------------ voice ---

def api_key() -> str | None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    path = Path.home() / ".elevenlabs_key"
    if not key and path.exists():
        key = path.read_text().strip()
    return key or None


def tts(scene_id: str, text: str, prev: str, nxt: str, key: str) -> Path:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    mp3 = VOICE_DIR / f"{scene_id}.mp3"
    meta = VOICE_DIR / f"{scene_id}.txt"
    if mp3.exists() and meta.exists() and meta.read_text() == text:
        return mp3
    body = json.dumps({
        "text": text, "model_id": MODEL_ID,
        "previous_text": prev, "next_text": nxt,
        "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "style": 0.25,
                           "use_speaker_boost": True},
    }).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}?output_format=mp3_44100_128",
        data=body, headers={"xi-api-key": key, "Content-Type": "application/json",
                            "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        mp3.write_bytes(resp.read())
    meta.write_text(text)
    print(f"  voiced {scene_id}")
    return mp3


def tts_edge(scene_id: str, text: str, voice: str, rate: str) -> Path:
    """Free Microsoft neural voice via edge-tts (no key); cached per text+voice."""

    import asyncio

    import edge_tts

    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    mp3 = VOICE_DIR / f"{scene_id}.mp3"
    meta = VOICE_DIR / f"{scene_id}.txt"
    stamp = f"edge|{voice}|{rate}|{text}"
    if mp3.exists() and meta.exists() and meta.read_text() == stamp:
        return mp3
    asyncio.run(edge_tts.Communicate(text, voice, rate=rate).save(str(mp3)))
    meta.write_text(stamp)
    print(f"  voiced {scene_id} ({voice})")
    return mp3


def to_wav(mp3: Path) -> np.ndarray:
    wav = mp3.with_suffix(".wav")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(mp3), "-ac", "1",
                    "-ar", "48000", str(wav)], check=True)
    with wave.open(str(wav)) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    wav.unlink()
    return data


# ------------------------------------------------------------ video input ---

class Clip:
    """Sequential-friendly random access to video frames."""

    def __init__(self, path: Path):
        self.path = path
        self.cap = cv2.VideoCapture(str(path))
        self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.pos, self.last = -1, None

    def frame(self, idx: int) -> np.ndarray:
        idx = int(min(max(idx, 0), self.n - 1))
        if idx == self.pos:
            return self.last
        if idx < self.pos or idx > self.pos + 30:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            self.pos = idx - 1
        while self.pos < idx:
            ok, img = self.cap.read()
            if not ok:
                break
            self.pos += 1
            self.last = img
        return self.last


def bgr_to_pil(img: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).convert("RGBA")


def cover(img: Image.Image, w: int, h: int, zoom: float = 1.0) -> Image.Image:
    s = max(w / img.width, h / img.height) * zoom
    r = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def rounded(img: Image.Image, radius: int = 28) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *img.size), radius, fill=255)
    out = img.copy()
    out.putalpha(mask)
    return out


def shadowed(canvas: Image.Image, img: Image.Image, xy: tuple[int, int], alpha: float = 1.0):
    sh = Image.new("RGBA", (img.width + 80, img.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((40, 50, img.width + 40, img.height + 50), 30,
                                          fill=(0, 0, 0, int(130 * alpha)))
    sh = sh.filter(ImageFilter.GaussianBlur(22))
    canvas.alpha_composite(sh, (xy[0] - 40, xy[1] - 40))
    if alpha < 1:
        img = img.copy()
        a = img.getchannel("A").point(lambda v: int(v * alpha))
        img.putalpha(a)
    canvas.alpha_composite(img, xy)


def text(d: ImageDraw.ImageDraw, xy, s, f, fill=WHITE, alpha=1.0, anchor="la"):
    d.text(xy, s, font=f, fill=(*fill, int(255 * alpha)), anchor=anchor)


def pill(layer: Image.Image, xy, s, color=ORANGE, alpha=1.0, size=30, fg=INK):
    d = BlendDraw(layer)
    f = font("demi", size)
    w = d.textlength(s, font=f)
    x, y = xy
    d.rounded_rectangle((x, y, x + w + 2 * size * 0.8, y + size * 1.9), size,
                        fill=(*color, int(235 * alpha)))
    d.text((x + size * 0.8, y + size * 0.95), s, font=f, fill=(*fg, int(255 * alpha)),
           anchor="lm")
    return w + 2 * size * 0.8


def background(t: float) -> Image.Image:
    bg = Image.new("RGBA", (W, H), (*INK, 255))
    d = BlendDraw(bg)
    for i in range(0, W + H, 90):  # slow diagonal grid
        off = int((t * 12) % 90)
        d.line([(i - H + off, H), (i + off, 0)], fill=(255, 255, 255, 9), width=1)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((W * 0.55, -H * 0.4, W * 1.3, H * 0.7), fill=(*ORANGE, 38))
    return Image.alpha_composite(bg, glow.filter(ImageFilter.GaussianBlur(160)))


# ------------------------------------------------------------------- data ---

CACHE = HERE / ".cache"


def clean_overlay(folder: Path, video: str, sport: str) -> Path:
    """Skeleton-only overlay (no HUD text) so promo graphics own the frame."""

    out = CACHE / f"{folder.name}-clean.mp4"
    if out.exists() and out.stat().st_mtime > (folder / "report.json").stat().st_mtime:
        return out
    sys.path.insert(0, str(ROOT / "src"))
    from motionmirror.analysis import analyze_sequence
    from motionmirror.render import render_overlay
    from motionmirror.schema import PoseSequence

    rep = load(folder / "report.json")
    seq = PoseSequence.load(folder / "pose.json")
    analysis = analyze_sequence(seq, sport, rep["side"])
    CACHE.mkdir(exist_ok=True)
    print(f"  rendering clean overlay for {folder.name}")
    return render_overlay(analysis, folder / video, out, hud=False)


def load(path: Path) -> dict:
    return json.loads(path.read_text())


class Data:
    def __init__(self):
        self.bb = load(BB / "report.json")
        self.bd = load(BD / "report.json")
        self.bb_rep = self.bb["reps"][0]
        overheads = [r for r in self.bd["reps"] if r.get("stroke") == "overhead"]
        flagged = [r for r in overheads if any(
            f["key"] == "contact.racket_hand_height_torso" and f["status"] == "low"
            for f in r["findings"])]
        self.bd_over = (flagged or overheads or self.bd["reps"])[-1]
        self.bb_pose = {f["frame_index"]: f for f in load(BB / "pose.json")["frames"]}
        self.bd_pose = {f["frame_index"]: f for f in load(BD / "pose.json")["frames"]}
        self.bb_clip = Clip(clean_overlay(BB, "basketball.mp4", "basketball"))
        self.bb_raw = Clip(BB / "basketball.mp4")
        self.bd_clip = Clip(clean_overlay(BD, "badminton.mp4", "badminton"))
        self._follow = self._follow_track()

    def finding(self, rep: dict, key: str) -> dict:
        return next(f for f in rep["findings"] if f["key"] == key)

    def verify_script(self):
        """Fail loudly if the narration no longer matches the reports."""

        elbow = self.finding(self.bb_rep, "release.shooting_elbow_angle_deg")["value"]
        d2r = self.finding(self.bb_rep, "timing.dip_to_release_s")["value"]
        assert round(elbow) == 176, f"script says 176 deg, report says {elbow}"
        assert 0.33 <= d2r <= 0.40, f"script says just over a third of a second, report {d2r}"
        assert self.bb_rep["score"] == 100, "script says every check in range"
        h = self.finding(self.bd_over, "contact.racket_hand_height_torso")
        assert h["status"] == "low", "script says overhead contact is a little low"

    def _follow_track(self):
        """Smoothed athlete centre (pixels) per basketball frame for the follow-cam."""

        n, w, h = self.bb_clip.n, 1080, 1920
        cx, cy, hh = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
        for i, f in self.bb_pose.items():
            pts = [p for p in f["landmarks"].values() if p.get("visibility", 1) > 0.3]
            if pts and i < n:
                ys = [p["y"] for p in pts]
                cx[i] = np.mean([p["x"] for p in pts]) * w
                cy[i] = (min(ys) + max(ys)) / 2 * h
                hh[i] = (max(ys) - min(ys)) * h
        idx = np.arange(n)
        for arr in (cx, cy, hh):
            ok = ~np.isnan(arr)
            arr[:] = np.interp(idx, idx[ok], arr[ok])
        k = np.ones(31) / 31
        pad = lambda a: np.convolve(np.pad(a, 15, mode="edge"), k, mode="valid")  # noqa: E731
        return pad(cx), pad(cy), float(np.median(hh))

    def follow(self, idx: int, pw: int, ph: int, scale: float = 2.6) -> Image.Image:
        cx, cy, body = self._follow
        idx = int(min(max(idx, 0), len(cx) - 1))
        ch = body * scale
        cw = ch * pw / ph
        x0 = int(min(max(cx[idx] - cw / 2, 0), 1080 - cw))
        y0 = int(min(max(cy[idx] - ch / 2, 0), 1920 - ch))
        crop = self.bb_clip.frame(idx)[y0:y0 + int(ch), x0:x0 + int(cw)]
        return bgr_to_pil(cv2.resize(crop, (pw, ph), interpolation=cv2.INTER_CUBIC))


# ----------------------------------------------------------------- scenes ---

def brand(layer: Image.Image, alpha: float = 1.0):
    d = BlendDraw(layer)
    d.ellipse((60, 52, 84, 76), fill=(*ORANGE, int(255 * alpha)))
    text(d, (98, 64), "MotionMirror", font("demi", 28), alpha=alpha, anchor="lm")


def scene_title(t, dur, D: Data):
    src = bgr_to_pil(D.bd_clip.frame(int(t * 30) % D.bd_clip.n))
    frame = cover(src, W, H, zoom=1.08 + 0.04 * t / dur).filter(ImageFilter.GaussianBlur(6))
    frame = Image.alpha_composite(frame, Image.new("RGBA", (W, H), (*INK, 200)))
    d = BlendDraw(frame)
    a = appear(t, 0.3, 0.9)
    text(d, (W // 2, 430 + 30 * (1 - a)), "MotionMirror", font("bold", 150), alpha=a,
         anchor="mm")
    b = appear(t, 1.2, 0.8)
    text(d, (W // 2, 555), "One phone video.  Every phase.  Every angle.", font("medium", 46),
         fill=MUTED, alpha=b, anchor="mm")
    for i, s in enumerate(["Golf", "Basketball", "Badminton"]):
        c = appear(t, 2.0 + 0.25 * i, 0.5)
        x = W // 2 - 330 + i * 230
        pill(frame, (x, 650), s, color=[TEAL, ORANGE, GOLD][i], alpha=c, size=28)
    return frame


def scene_bb_intro(t, dur, D: Data):
    frame = background(t)
    raw = bgr_to_pil(D.bb_raw.frame(int(t * 120) % D.bb_raw.n))
    raw = rounded(raw.resize((500, 889), Image.LANCZOS))
    a = appear(t, 0.1)
    shadowed(frame, raw, (150, 100 + int(40 * (1 - a))), alpha=a)
    # tracking box on the small athlete
    cx, cy, body = D._follow
    i = int(t * 120) % D.bb_raw.n
    s = 500 / 1080
    d = BlendDraw(frame)
    bx, by, bh = cx[i] * s + 150, cy[i] * s + 100, body * s * 1.4
    b = appear(t, 1.2)
    d.rounded_rectangle((bx - bh * 0.45, by - bh / 2, bx + bh * 0.45, by + bh / 2), 8,
                        outline=(*ORANGE, int(255 * b)), width=4)
    # zoomed follow-cam
    c = appear(t, 2.0, 0.7)
    cam = rounded(D.follow(i, 820, 820))
    shadowed(frame, cam, (860 + int(80 * (1 - c)), 100), alpha=c)
    d = BlendDraw(frame)
    d.line((bx + bh * 0.45, by, 860, 510), fill=(*ORANGE, int(180 * c)), width=3)
    pill(frame, (890, 130), "AUTO-ZOOM", color=ORANGE, alpha=appear(t, 2.6), size=26)
    pill(frame, (1110, 130), "33 LANDMARKS / FRAME", color=TEAL, alpha=appear(t, 4.2), size=26)
    text(d, (1270, 960), "Athlete fills 9% of the frame", font("medium", 30), fill=MUTED,
         alpha=b, anchor="ms")
    brand(frame)
    return frame


def phase_bar(layer, rep, t_src, x, y, w, alpha=1.0):
    d = BlendDraw(layer)
    phases = list(rep["phases"].items())
    t0, t1 = phases[0][1]["time_s"] - 0.25, phases[-1][1]["time_s"] + 0.25
    d.rounded_rectangle((x, y, x + w, y + 8), 4, fill=(255, 255, 255, int(50 * alpha)))
    prog = min(1, max(0, (t_src - t0) / (t1 - t0)))
    d.rounded_rectangle((x, y, x + w * prog, y + 8), 4, fill=(*ORANGE, int(255 * alpha)))
    for k, (name, v) in enumerate(phases):
        px = x + w * (v["time_s"] - t0) / (t1 - t0)
        on = t_src >= v["time_s"]
        r = 13 if on else 9
        d.ellipse((px - r, y + 4 - r, px + r, y + 4 + r),
                  fill=(*(ORANGE if on else MUTED), int(255 * alpha)))
        label = name.replace("_", " ").upper()
        text(d, (px, y + 58 if k % 2 == 0 else y - 34), label, font("demi", 24),
             fill=WHITE if on else MUTED, alpha=alpha, anchor="mm")


def scene_bb_phases(t, dur, D: Data):
    frame = background(t)
    rep = D.bb_rep
    start = rep["phases"]["set"]["time_s"] - 0.25
    t_src = start + t / 4  # 120 fps played at 30 fps = 4x slow motion
    t_src = min(t_src, rep["phases"]["landing"]["time_s"] + 0.25)
    cam = rounded(D.follow(int(t_src * 120), 1100, 680, scale=2.3))
    shadowed(frame, cam, (410, 110), alpha=appear(t, 0, 0.4))
    d = BlendDraw(frame)
    pill(frame, (440, 140), "4x SLOW MOTION", color=GOLD, size=24)
    current = [n for n, v in rep["phases"].items() if v["time_s"] <= t_src]
    if current:
        text(d, (1480, 760), current[-1].replace("_", " ").upper(), font("bold", 64),
             fill=ORANGE, anchor="rs")
    phase_bar(frame, rep, t_src, 260, 870, 1400)
    brand(frame)
    return frame


def metric_card(layer, xy, label, value, unit, status, alpha):
    x, y = xy
    card = Image.new("RGBA", (620, 168), (0, 0, 0, 0))
    d = BlendDraw(card)
    d.rounded_rectangle((0, 0, 620, 168), 26, fill=(255, 255, 255, 22),
                        outline=(255, 255, 255, 40), width=2)
    col = TEAL if status == "ok" else RED
    d.rounded_rectangle((0, 0, 10, 168), 5, fill=(*col, 255))
    text(d, (36, 38), label, font("medium", 28), fill=MUTED, anchor="lm")
    text(d, (36, 112), value, font("din", 92), anchor="lm")
    vw = d.textlength(value, font=font("din", 92))
    text(d, (46 + vw, 128), unit, font("medium", 30), fill=MUTED, anchor="ls")
    text(d, (590, 38), "IN RANGE" if status == "ok" else status.upper(), font("demi", 22),
         fill=col, anchor="rm")
    shadowed(layer, card, (x + int(60 * (1 - alpha)), y), alpha=alpha)


def scene_bb_metrics(t, dur, D: Data):
    frame = background(t)
    rep = D.bb_rep
    rel = int(rep["phases"]["release"]["time_s"] * 120)
    cam = rounded(D.follow(rel, 720, 900, scale=2.0 - 0.1 * t / dur))
    shadowed(frame, cam, (140, 90))
    pill(frame, (170, 120), "RELEASE", color=ORANGE, size=26)
    f = {k: D.finding(rep, k) for k in ("release.shooting_elbow_angle_deg",
                                        "release.wrist_above_head_torso",
                                        "timing.dip_to_release_s")}
    elbow = f["release.shooting_elbow_angle_deg"]
    cards = [
        ("Elbow extension at release", f"{elbow['value'] * min(1, appear(t, 0.6, 1.2)):.0f}",
         "deg", elbow["status"], 0.6),
        ("Release height above head", f"+{f['release.wrist_above_head_torso']['value']:.2f}",
         "torso", f["release.wrist_above_head_torso"]["status"], 3.2),
        ("Dip to release", f"{f['timing.dip_to_release_s']['value']:.2f}", "s",
         f["timing.dip_to_release_s"]["status"], 5.6),
    ]
    for k, (label, val, unit, st, at) in enumerate(cards):
        metric_card(frame, (1000, 130 + k * 200), label, val, unit, st, appear(t, at))
    a = appear(t, 7.6)
    n = len(rep["findings"])
    ok = sum(x["status"] == "ok" for x in rep["findings"])
    pill(frame, (1000, 760), f"{ok} / {n} CHECKS IN RANGE", color=TEAL, alpha=a, size=34)
    brand(frame)
    return frame


def scene_bd_intro(t, dur, D: Data):
    idx = int(t * 30)
    src = bgr_to_pil(D.bd_clip.frame(idx))
    frame = cover(src, W, H)
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle((0, 0, W, 150), fill=(*INK, 150))
    frame = Image.alpha_composite(frame, shade)
    brand(frame)
    t_src = idx / 30
    x = 1880
    for rep in reversed(D.bd["reps"]):
        c = rep["phases"]["contact"]["time_s"]
        if t_src >= c:
            label = f"#{rep['index']}  {rep['stroke'].upper()}"
            color = GOLD if rep["stroke"] == "overhead" else TEAL
            w = BlendDraw(frame).textlength(label, font=font("demi", 30)) + 48
            x -= w + 16
            pill(frame, (x, 46), label, color=color, alpha=appear(t_src, c, 0.3), size=30)
    return frame


def draw_angle(layer, pts, color, alpha, label):
    d = BlendDraw(layer)
    (ax, ay), (bx, by), (cx, cy) = pts
    d.line([(ax, ay), (bx, by), (cx, cy)], fill=(*color, int(255 * alpha)), width=8)
    for p in pts:
        d.ellipse((p[0] - 12, p[1] - 12, p[0] + 12, p[1] + 12), fill=(*WHITE, int(255 * alpha)))
    a1 = math.degrees(math.atan2(ay - by, ax - bx))
    a2 = math.degrees(math.atan2(cy - by, cx - bx))
    lo, hi = sorted([a1, a2])
    if hi - lo > 180:
        lo, hi = hi, lo + 360
    d.arc((bx - 60, by - 60, bx + 60, by + 60), lo, hi, fill=(*GOLD, int(255 * alpha)), width=6)
    text(d, (bx + 80, by + 10), label, font("din", 64), fill=GOLD, alpha=alpha, anchor="lm")


def scene_bd_overhead(t, dur, D: Data):
    rep = D.bd_over
    c_t = rep["phases"]["contact"]["time_s"]
    start = rep["phases"]["backswing"]["time_s"] - 0.3
    slow = start + t / 2.5  # 2.5x slow motion up to contact, then hold
    t_src = min(slow, c_t)
    idx = int(round(t_src * 30))
    zoom = 1.0 + 0.35 * appear(t, (c_t - start) * 2.5, 1.2)
    lm = D.bd_pose.get(idx) or D.bd_pose[min(D.bd_pose, key=lambda k: abs(k - idx))]
    L = lm["landmarks"]
    side = D.bd["side"]
    cx = L[f"{side}_shoulder"]["x"] * 1920
    cy = L[f"{side}_shoulder"]["y"] * 1080
    src = bgr_to_pil(D.bd_clip.frame(idx))
    s = zoom
    view = src.resize((int(1920 * s), int(1080 * s)), Image.LANCZOS)
    ox = int(min(max(cx * s - W * 0.45, 0), view.width - W))
    oy = int(min(max(cy * s - H * 0.45, 0), view.height - H))
    frame = view.crop((ox, oy, ox + W, oy + H))
    brand(frame)
    pill(frame, (60, 120), f"#{rep['index']}  OVERHEAD", color=GOLD, size=28)
    held = slow >= c_t
    if held:
        a = appear(t, (c_t - start) * 2.5 + 0.4)
        P = lambda n: (L[n]["x"] * 1920 * s - ox, L[n]["y"] * 1080 * s - oy)  # noqa: E731
        ext = D.finding(rep, "contact.racket_elbow_angle_deg")["value"]
        draw_angle(frame, [P(f"{side}_shoulder"), P(f"{side}_elbow"), P(f"{side}_wrist")],
                   ORANGE, a, f"{ext:.0f}°")
        d = BlendDraw(frame)
        sy = (P("left_shoulder")[1] + P("right_shoulder")[1]) / 2
        wy = P(f"{side}_wrist")[1]
        b = appear(t, (c_t - start) * 2.5 + 2.0)
        d.line((P(f"{side}_wrist")[0] - 200, sy, P(f"{side}_wrist")[0] + 40, sy),
               fill=(*TEAL, int(220 * b)), width=4)
        d.line((P(f"{side}_wrist")[0] - 100, sy, P(f"{side}_wrist")[0] - 100, wy),
               fill=(*TEAL, int(255 * b)), width=6)
        hgt = D.finding(rep, "contact.racket_hand_height_torso")["value"]
        text(d, (P(f"{side}_wrist")[0] - 125, (sy + wy) / 2), f"+{hgt:.2f} torso",
             font("din", 52), fill=TEAL, alpha=b, anchor="rm")
        pill(frame, (60, 200), "CONTACT", color=ORANGE, alpha=a, size=28)
    return frame


def scene_bd_feedback(t, dur, D: Data):
    rep = D.bd_over
    idx = int(round(rep["phases"]["contact"]["time_s"] * 30))
    frame = cover(bgr_to_pil(D.bd_clip.frame(idx)), W, H, zoom=1.12 + 0.03 * t / dur)
    frame = frame.filter(ImageFilter.GaussianBlur(3))
    frame = Image.alpha_composite(frame, Image.new("RGBA", (W, H), (*INK, 150)))
    brand(frame)
    card = Image.new("RGBA", (1120, 600), (0, 0, 0, 0))
    d = BlendDraw(card)
    d.rounded_rectangle((0, 0, 1120, 600), 34, fill=(16, 24, 38, 235),
                        outline=(255, 255, 255, 40), width=2)
    text(d, (50, 64), f"Stroke #{rep['index']} · overhead", font("demi", 34), fill=MUTED,
         anchor="lm")
    y = 140
    for k, f in enumerate(x for x in rep["findings"] if x["status"] != "unknown"):
        a = appear(t, 0.5 + 0.5 * k, 0.4)
        col = TEAL if f["status"] == "ok" else RED
        d.ellipse((50, y - 12, 74, y + 12), fill=(*col, int(255 * a)))
        text(d, (96, y), f["label"], font("demi", 32), alpha=a, anchor="lm")
        val = f["value"]
        unit = {"deg": "°", "torso": " torso"}.get(f["unit"], f" {f['unit']}")
        text(d, (1070, y), f"{val:.2f}{unit}" if f["unit"] != "deg" else f"{val:.0f}°",
             font("din", 44), fill=col, alpha=a, anchor="rm")
        y += 72
    cue = D.finding(rep, "contact.racket_hand_height_torso")["message"]
    a = appear(t, 2.6, 0.6)
    d.rounded_rectangle((40, 450, 1080, 560), 22, fill=(*ORANGE, int(40 * a)),
                        outline=(*ORANGE, int(200 * a)), width=2)
    words, lines, line = cue.split(), [], ""
    for wd in words:
        if d.textlength(line + " " + wd, font=font("medium", 30)) > 960:
            lines.append(line)
            line = wd
        else:
            line = (line + " " + wd).strip()
    lines.append(line)
    for k, ln in enumerate(lines[:2]):
        text(d, (70, 487 + k * 40), ln, font("medium", 30), alpha=a, anchor="lm")
    shadowed(frame, card, (400, 240 + int(30 * (1 - appear(t, 0.1)))), alpha=appear(t, 0.1))
    return frame


def scene_outputs(t, dur, D: Data):
    frame = background(t)
    d = BlendDraw(frame)
    text(d, (W // 2, 120), "Everything in one output folder", font("bold", 60), anchor="mm",
         alpha=appear(t, 0.1))
    tiles = [
        ("keyposes.jpg", Image.open(BD / "keyposes.jpg").convert("RGBA"), 0.4),
        ("timeline.png", Image.open(BB / "timeline.png").convert("RGBA"), 1.6),
        ("overlay.mp4", bgr_to_pil(D.bd_clip.frame(int(t * 30) % D.bd_clip.n)), 2.8),
        ("report.md", report_card(D), 4.0),
    ]
    for k, (name, img, at) in enumerate(tiles):
        a = appear(t, at, 0.6)
        x, y = 150 + (k % 2) * 830, 210 + (k // 2) * 420
        tile = rounded(cover(img, 790, 360, zoom=1.0))
        shadowed(frame, tile, (x, y + int(40 * (1 - a))), alpha=a)
        pill(frame, (x + 20, y + 296 + int(40 * (1 - a))), name, color=WHITE, alpha=a, size=22)
    brand(frame)
    return frame


@lru_cache(maxsize=1)
def _report_card_cached(rep_json: str) -> Image.Image:
    rep = json.loads(rep_json)
    img = Image.new("RGBA", (790, 360), (250, 250, 248, 255))
    d = BlendDraw(img)
    text(d, (30, 40), f"Rep {rep['index']} · {rep.get('stroke', '')}", font("bold", 30),
         fill=INK, anchor="lm")
    y = 100
    for f in rep["findings"][:4]:
        col = (30, 150, 120) if f["status"] == "ok" else (210, 70, 60)
        text(d, (30, y), f["label"], font("medium", 24), fill=INK, anchor="lm")
        text(d, (760, y), f["status"].upper(), font("demi", 22), fill=col, anchor="rm")
        d.line((30, y + 28, 760, y + 28), fill=(220, 220, 220, 255), width=1)
        y += 62
    return img


def report_card(D: Data) -> Image.Image:
    return _report_card_cached(json.dumps(D.bd_over))


def scene_honesty(t, dur, D: Data):
    frame = cover(bgr_to_pil(D.bb_clip.frame(int(t * 40) % D.bb_clip.n)), W, H)
    frame = frame.filter(ImageFilter.GaussianBlur(14))
    frame = Image.alpha_composite(frame, Image.new("RGBA", (W, H), (*INK, 215)))
    d = BlendDraw(frame)
    items = [("Every number traces to a frame", TEAL),
             ("Every check shows its reference range", GOLD),
             ("Hidden joint? It says n/a, never guesses", ORANGE)]
    for k, (s, col) in enumerate(items):
        a = appear(t, 0.4 + 1.6 * k, 0.6)
        y = 330 + k * 150
        d.rounded_rectangle((420, y - 8, 432, y + 78), 6, fill=(*col, int(255 * a)))
        text(d, (470 + int(40 * (1 - a)), y + 35), s, font("demi", 56), alpha=a, anchor="lm")
    brand(frame)
    return frame


def scene_close(t, dur, D: Data):
    frame = background(t)
    d = BlendDraw(frame)
    a = appear(t, 0.2, 0.8)
    d.ellipse((W // 2 - 40, 250, W // 2 + 40, 330), fill=(*ORANGE, int(255 * a)))
    text(d, (W // 2, 430), "MotionMirror", font("bold", 130), alpha=a, anchor="mm")
    text(d, (W // 2, 530), "See your form.", font("medium", 52), fill=MUTED,
         alpha=appear(t, 1.0), anchor="mm")
    b = appear(t, 1.8)
    box = (W // 2 - 560, 620, W // 2 + 560, 760)
    d.rounded_rectangle(box, 24, fill=(255, 255, 255, int(18 * b)),
                        outline=(255, 255, 255, int(50 * b)), width=2)
    text(d, (box[0] + 50, 666), "$ pip install -e \".[pose]\"", font("medium", 36),
         fill=MUTED, alpha=b, anchor="lm")
    text(d, (box[0] + 50, 718), "$ motionmirror analyze clip.mp4 --sport badminton",
         font("demi", 36), fill=WHITE, alpha=b, anchor="lm")
    text(d, (W // 2, 860), "github.com/rayford295/motionmirror", font("demi", 40),
         fill=ORANGE, alpha=appear(t, 2.6), anchor="mm")
    return frame


RENDER = {
    "title": scene_title, "bb_intro": scene_bb_intro, "bb_phases": scene_bb_phases,
    "bb_metrics": scene_bb_metrics, "bd_intro": scene_bd_intro,
    "bd_overhead": scene_bd_overhead, "bd_feedback": scene_bd_feedback,
    "outputs": scene_outputs, "honesty": scene_honesty, "close": scene_close,
}
MIN_DUR = {"bb_metrics": 9.5, "bd_overhead": 9.0, "outputs": 6.5, "honesty": 6.0,
           "close": 5.5}


# --------------------------------------------------------------- captions ---

def caption_chunks(textv: str, start: float, dur: float) -> list[tuple[float, float, str]]:
    parts = [p.strip() for p in re.split(r"(?<=[.,:?!])\s+", textv) if p.strip()]
    merged: list[str] = []
    for p in parts:
        if merged and len(merged[-1]) + len(p) < 60:
            merged[-1] += " " + p
        else:
            merged.append(p)
    total = sum(len(p) for p in merged)
    out, t = [], start
    for p in merged:
        d = dur * len(p) / total
        out.append((t, t + d, p))
        t += d
    return out


def draw_caption(frame: Image.Image, s: str):
    d = BlendDraw(frame)
    f = font("medium", 38)
    w = d.textlength(s, font=f)
    x0, y0 = (W - w) / 2 - 28, H - 118
    d.rounded_rectangle((x0, y0, x0 + w + 56, y0 + 66), 18, fill=(0, 0, 0, 150))
    d.text((W / 2, y0 + 33), s, font=f, fill=WHITE, anchor="mm")


# ------------------------------------------------------------------- main ---

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-voice", action="store_true", help="Silent preview, estimated timing.")
    ap.add_argument("--tts", choices=["edge", "elevenlabs"], default="edge",
                    help="edge = free Microsoft neural voice (default); elevenlabs needs a key.")
    ap.add_argument("--voice", default="en-US-ChristopherNeural",
                    help="edge-tts voice (the ray-resilience teaser voice)")
    ap.add_argument("--rate", default="+0%", help="edge-tts speaking rate")
    ap.add_argument("--only", help="Render a single scene id (preview).")
    ap.add_argument("--out", type=Path, default=OUT_DIR / "motionmirror-promo.mp4")
    args = ap.parse_args(argv)

    D = Data()
    D.verify_script()

    clips: dict[str, np.ndarray] = {}
    if not args.no_voice and args.tts == "edge":
        for sid, txt in SCENES:
            clips[sid] = to_wav(tts_edge(sid, txt, args.voice, args.rate))
    elif not args.no_voice:
        key = api_key()
        if key is None and not all((VOICE_DIR / f"{s}.mp3").exists() for s, _ in SCENES):
            print("No ElevenLabs key (~/.elevenlabs_key or ELEVENLABS_API_KEY). "
                  "Use --tts edge or --no-voice.")
            return 1
        for i, (sid, txt) in enumerate(SCENES):
            prev = SCENES[i - 1][1] if i else ""
            nxt = SCENES[i + 1][1] if i + 1 < len(SCENES) else ""
            mp3 = VOICE_DIR / f"{sid}.mp3"
            if key:
                mp3 = tts(sid, txt, prev, nxt, key)
            clips[sid] = to_wav(mp3)

    lead, tail = 0.45, 0.75
    plan = []
    t0 = 0.0
    for sid, txt in SCENES:
        vo = len(clips[sid]) / 48000 if sid in clips else len(txt.split()) / 2.55
        dur = max(MIN_DUR.get(sid, 4.0), vo + lead + tail)
        if args.only and sid != args.only:
            continue
        plan.append((sid, txt, t0, dur, vo))
        t0 += dur
    total = t0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    silent = args.out.with_suffix(".silent.mp4")
    writer = imageio_ffmpeg.write_frames(str(silent), (W, H), fps=FPS, codec="libx264",
                                         quality=None, bitrate=None,
                                         output_params=["-crf", "19", "-preset", "slow",
                                                        "-pix_fmt", "yuv420p"],
                                         macro_block_size=8)
    writer.send(None)
    captions = [c for sid, txt, s, dur, vo in plan for c in caption_chunks(txt, s + lead, vo)]
    poster = None
    for sid, _txt, start, dur, _vo in plan:
        n = int(round(dur * FPS))
        print(f"  scene {sid:12s} {dur:5.1f}s")
        for k in range(n):
            t = k / FPS
            img = RENDER[sid](t, dur, D)
            fade = min(1.0, t / 0.35, (dur - t) / 0.35)
            if fade < 1:
                img = Image.blend(Image.new("RGBA", (W, H), (*INK, 255)), img, max(0.0, fade))
            now = start + t
            cap = next((c for c in captions if c[0] <= now < c[1]), None)
            if cap:
                draw_caption(img, cap[2])
            if sid == "bd_overhead" and k == n - 10:
                poster = img.copy()
            writer.send(np.ascontiguousarray(np.asarray(img.convert("RGB"))))
    writer.close()

    if clips:
        audio = np.zeros(int((total + 1) * 48000), np.float32)
        for sid, _txt, start, _dur, _vo in plan:
            a = clips[sid]
            s = int((start + lead) * 48000)
            audio[s:s + len(a)] += a
        peak = np.abs(audio).max() or 1
        audio = (audio / peak * 0.89 * 32767).astype(np.int16)
        wav = args.out.with_suffix(".wav")
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(audio.tobytes())
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", str(args.out)], check=True)
        silent.unlink()
        wav.unlink()
    else:
        silent.replace(args.out)
    if poster is not None:
        CACHE.mkdir(exist_ok=True)  # the designed cover comes from make_cover.py
        poster.convert("RGB").save(CACHE / "frame-poster.jpg", quality=88)
    print(f"Wrote {args.out} ({total:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
