"""Prism-1 — fully offline 2D image generation.

Deterministic, seeded procedural art: landscapes, skylines, nebulas, sunsets,
sprites and seamless textures. No model download, no network, always works.
"""
from __future__ import annotations

import hashlib
import math
import os
import random
import tempfile

from PIL import Image, ImageDraw, ImageFilter

STYLE_KEYWORDS = {
    "landscape": ["mountain", "valley", "hill", "ridge", "forest", "field", "landscape", "terrain", "island"],
    "cosmic": ["space", "nebula", "galaxy", "star", "starfield", "cosmic", "universe", "planet"],
    "cyber": ["cyber", "neon", "city", "synthwave", "grid", "retro", "fture", "hologram", "night city"],
    "sunset": ["sunset", "dusk", "dawn", "horizon", "beach", "ocean", "evening", "sunrise"],
    "sprite": ["sprite", "character", "creature", "icon", "pixel", "tileset", "item", "sword", "gem"],
    "texture": ["texture", "pattern", "seamless", "tile", "fabric", "stone", "wall", "wood", "marble", "carpet"],
}
DEFAULT_STYLE = "landscape"


def _hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _rgb2hex(c):
    return "#%02x%02x%02x" % tuple(min(255, max(0, int(v))) for v in c)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _mix(colors, count):
    """N-point palette ramp over a sorted gradient."""
    ramp = []
    for i in range(count):
        t = i / (count - 1)
        seg = t * (len(colors) - 1)
        lo = int(math.floor(seg))
        hi = min(lo + 1, len(colors) - 1)
        ramp.append(_lerp(colors[lo], colors[hi], seg - lo))
    return ramp


def detect_style(prompt):
    low = (prompt or "").lower()
    best, score = DEFAULT_STYLE, 0
    for key, words in STYLE_KEYWORDS.items():
        s = sum(1 for w in words if w in low)
        if s > score:
            best, score = key, s
    return best


def _seed_for(prompt, seed):
    if seed is None:
        seed = int(hashlib.sha256((prompt or "").encode()).hexdigest()[:8], 16) % (2**31)
    return seed


def _landscape(w, h, rng, pal):
    sky = pal[0]
    base = pal[1]
    img = Image.new("RGB", (w, h), sky)
    d = ImageDraw.Draw(img)
    sun = _lerp(pal[2], pal[3], 0.5)
    sx, sy = rng.randint(int(w * 0.2), int(w * 0.8)), int(h * 0.28)
    d.ellipse([sx - 42, sy - 42, sx + 42, sy + 42], fill=sun)
    for band in range(5):
        y0 = int(h * (0.30 + 0.12 * band))
        y1 = y0 + rng.randint(8, 24)
        c = _mix([base, pal[4]], 8)[band]
        d.rectangle([0, y0, w, y1], fill=c)
    # ridge silhouettes
    prev_y = int(h * 0.55)
    pts = [(0, prev_y)]
    for x in range(0, w + 1, w // 12):
        prev_y += rng.randint(-14, 20)
        pts.append((x, prev_y))
    d.polygon(pts + [(w, h), (0, h)], fill=pal[3])
    d.rectangle([0, int(h * 0.82), w, h], fill=base)
    return img


def _cosmic(w, h, rng, pal):
    img = Image.new("RGB", (w, h), (6, 6, 14))
    d = ImageDraw.Draw(img)
    for _ in range(280):
        x, y = rng.randint(0, w), rng.randint(0, int(h * 0.9))
        r = rng.choice([1, 1, 1, 2, 2, 3])
        c = rng.choice(pal)
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    neb = Image.new("RGB", (w, h), (0, 0, 0))
    nd = ImageDraw.Draw(neb)
    for _ in range(6):
        cx, cy = rng.randint(0, w), rng.randint(0, h)
        r = rng.randint(60, 170)
        nd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rng.choice(pal))
    neb = neb.filter(ImageFilter.GaussianBlur(48))
    img = Image.blend(img, neb, 0.62)
    d2 = ImageDraw.Draw(img)
    px, py = int(w * 0.72), int(h * 0.3)
    for r, c in ((70, _lerp(pal[2], (255, 255, 255), 0.25)), (58, pal[3])):
        d2.ellipse([px - r, py - r, px + r, py + r], fill=c)
    return img


def _cyber(w, h, rng, pal):
    horizon = int(h * 0.62)
    img = Image.new("RGBA", (w, h), (*_lerp(pal[0], (0, 0, 0), 0.6), 255))
    d = ImageDraw.Draw(img)
    grid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for x in range(0, w + 1, max(4, w // 48)):
        gd.line([x, h, (x - 20), 10], fill=(*pal[3], 160))
    for y in range(0, h - horizon, max(4, (h - horizon) // 40)):
        gd.line([0, h - y, w, h - y], fill=(*pal[3], 120))
    img.alpha_composite(grid)
    d = ImageDraw.Draw(img)
    for _ in range(26):
        bw = rng.randint(14, 48)
        bh = rng.randint(int(h * 0.14), int(h * 0.42))
        bx, by = rng.randint(0, w - bw), h - rng.randint(0, 6) - bh
        d.rectangle([bx, by, bx + bw, by + bh], fill=(*pal[2], 255))
        wins = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        wd = ImageDraw.Draw(wins)
        for wy in range(3, bh - 3, 11):
            for wx2 in range(3, bw - 3, 9):
                if rng.random() < 0.72:
                    wd.rectangle([wx2, wy, wx2 + 4, wy + 5], fill=(*pal[4], 235))
        img.paste(wins, (bx, by), wins)
    return img.convert("RGB")


def _sunset(w, h, rng, pal):
    ramp = _mix([*pal[2:], (30, 18, 40)], h)
    img = Image.new("RGB", (w, h))
    for y in range(h):
        img.paste(ramp[y], (0, y, w, y + 1))
    d = ImageDraw.Draw(img)
    horiz = int(h * 0.58)
    sx, sy = int(w * 0.5), horiz - 2
    d.ellipse([sx - 46, sy - 46, sx + 46, sy + 46], fill=_lerp(pal[4], (255, 240, 210), 0.7))
    for i, (r, c) in enumerate([(70, (56, 40, 60)), (120, (70, 50, 76)), (170, (40, 34, 52))]):
        d.ellipse([sx - r, sy - r, sx + r, sy + r], outline=c, width=8)
    water = Image.new("RGB", (w, h - horiz), (34, 30, 54))
    wd = ImageDraw.Draw(water)
    for i in range(0, w, 6):
        amp = abs(math.sin(i / 18) * 12) + 3
        wd.line([i, 0, i + 8, amp], fill=(245, 190, 140))
    img.paste(water, (0, horiz))
    return img


def _sprite(w, h, rng, pal, label):
    side = min(w, h)
    px = 4  # pixel size for chunky sprite
    grid_w, grid_h = side // px, side // px
    body = Image.new("RGB", (grid_w * px, grid_h * px), pal[0])
    bd = ImageDraw.Draw(body)
    cx = grid_w // 2
    head_r = grid_w // 5
    # head
    bd.ellipse([(cx - head_r) * px, 6 * px, (cx + head_r) * px, (6 + head_r * 2) * px],
               fill=pal[3])
    # eyes
    for s in (-1, 1):
        bd.rectangle([(cx + s * (head_r // 2) - 2) * px, 10 * px,
                      (cx + s * (head_r // 2) + 2) * px, 14 * px], fill=pal[4])
    # torso
    bd.rectangle([(cx - grid_w // 3) * px, (8 + head_r * 2) * px,
                  (cx + grid_w // 3) * px, (10 + head_r * 2 + grid_h // 4) * px], fill=pal[2])
    # legs
    legs = int(h * 0.06)
    for s in (-1, 1):
        bd.rectangle([(cx + s * grid_w // 6 - 2) * px, (10 + head_r * 2 + grid_h // 4) * px,
                      (cx + s * grid_w // 6 + 3) * px, h - 8 * px], fill=pal[1])
    if any(k in (label or "").lower() for k in ("sword", "attack")) or rng.random() < 0.4:
        bd.rectangle([(cx + grid_w // 3 + 2) * px, 4 * px,
                      (cx + grid_w // 3 + 3) * px, h - 6 * px], fill=(230, 230, 230))
    img = Image.new("RGB", (w, h), (245, 245, 245))
    img.paste(body, ((w - body.width) // 2, 4))
    return img


def _texture(w, h, rng, pal):
    cell = 128
    img = Image.new("RGB", (w, h))
    for ty in range(math.ceil(h / cell)):
        for tx in range(math.ceil(w / cell)):
            base = Image.new("RGB", (cell, cell), pal[int(rng.random() * len(pal))])
            d = ImageDraw.Draw(base)
            blobs = rng.randint(6, 12)
            for _ in range(blobs):
                bx, by = rng.randint(0, cell), rng.randint(0, cell)
                r = rng.randint(8, 30)
                c = pal[int(rng.random() * len(pal))]
                d.ellipse([bx - r, by - r, bx + r, by + r], fill=c)
            img.paste(base, (tx * cell, ty * cell))
    img = img.filter(ImageFilter.GaussianBlur(2))
    return img


def generate(prompt="a distant mountain range", style=None, size=(640, 640),
             seed=None, out_path=None):
    """Produce a seeded Prism-1 image. Returns a result dict with the PNG path."""
    if style in (None, "", "auto"):
        style = detect_style(prompt)
    seed = _seed_for(prompt, seed)
    rng = random.Random(seed)
    from . import theme
    key = theme.detect_theme(prompt)
    pal = theme.PALETTES[key]["colors"]
    w, h = int(size[0]), int(size[1])
    fns = {
        "landscape": _landscape,
        "cosmic": _cosmic,
        "cyber": _cyber,
        "sunset": _sunset,
        "sprite": lambda w, h, rng, pal: _sprite(w, h, rng, pal, prompt),
        "texture": _texture,
    }
    img = fns.get(style, _landscape)(w, h, rng, pal)
    out_path = out_path or os.path.join(tempfile.mkdtemp(prefix="prism1_"), "prism.png")
    img.save(out_path)
    return {
        "path": out_path,
        "style": style,
        "seed": seed,
        "theme": key,
        "palette_hex": [_rgb2hex(c) for c in pal[:4]],
        "size": (w, h),
    }


if __name__ == "__main__":
    import sys
    r = generate(sys.argv[1] if len(sys.argv) > 1 else "neon city skyline")
    print(r)