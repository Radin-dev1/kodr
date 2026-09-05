"""Kodr Vision: reads images and videos into a structured scene report."""
from __future__ import annotations

import math
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageStat, ImageFilter

from . import theme


def _to_rgb_array(pil_img):
    return np.asarray(pil_img.resize((96, 96)).convert("RGB"), dtype=np.float32) / 255.0


def _dominant_colors(arr, k=4):
    flat = (arr.reshape(-1, 3) * 255).astype(np.int32)
    mean = flat.mean(axis=0)
    clusters = [list(mean)]
    for _ in range(k - 1):
        # farthest-point sampling, constrained to the image's inhabited colors
        idx = np.argmax(np.linalg.norm(flat - np.array(clusters).mean(axis=0), axis=1))
        clusters.append(list(flat[idx]))
    out = []
    for c in clusters:
        r, g, b = [int(v) for v in c]
        out.append((r, g, b))
    return out


def _gray_score(arr):
    return float(arr.mean())


def _colorfulness(arr):
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    rg = r - g
    yb = (r + g) / 2.0 - b
    return float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) * 0.393 * 255)


def _edge_ratio(arr):
    gray = (arr.mean(axis=2) * 255).astype(np.uint8)
    img = Image.fromarray(gray)
    edges = gray_a = np.asarray(img.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    return float((edges > 32).mean())


def _mood(arr):
    bright = _gray_score(arr)
    color = _colorfulness(arr)
    if bright < 0.35:
        return "dark", "candlelit dungeon, night scene, moody lighting"
    if bright > 0.8:
        if color > 30:
            return "bright", "cheerful daylight, saturated color palette"
        return "bright", "clean daylight, overcast or misty"
    if color > 45:
        return "vivid", "rich mid-tone colors, strong accents"
    return "calm", "soft neutral palette, ambient mid light"


def analyze_image(path):
    """Return a dict report for one image."""
    try:
        img = Image.open(path).convert("RGB")
    except Exception as e:
        return {"error": f"Could not read image: {e}", "ok": False}
    arr = _to_rgb_array(img)
    colors = _dominant_colors(arr)
    w, h = img.size
    mood, mood_note = _mood(arr)
    hexes = ["#%02x%02x%02x" % c for c in colors]
    rep = {
        "ok": True,
        "size": f"{w}x{h}",
        "palette_hex": hexes,
        "palette_rgb": colors,
        "brightness": round(_gray_score(arr), 3),
        "colorfulness": round(_colorfulness(arr), 2),
        "structure": round(_edge_ratio(arr), 3),
        "mood": mood,
        "read": f"{mood_note}. Predominant colors: {', '.join(hexes)}.",
    }
    return rep


def _video_frames(path, n=5, outdir=None):
    outdir = outdir or tempfile.mkdtemp(prefix="kodr_video_")
    try:
        probe = subprocess.run(
            ["ffmpeg", "-i", path, "-t", "1", "-f", "null", "-"],
            capture_output=True, timeout=20,
        )
        vdump = probe.stderr.decode("utf-8", "ignore")
        dur = None
        for line in vdump.splitlines():
            if "Duration:" in line:
                hh, mm, ss = line.split("Duration:")[1].split(",")[0].strip().split(":")
                dur = int(hh) * 3600 + int(mm) * 60 + float(ss)
        if not dur or dur <= 0:
            dur = 2.0
        clip = min(dur, 8.0)
        frames = []
        for i in range(n):
            t = clip * (i + 0.5) / n
            out = os.path.join(outdir, f"f{i}.png")
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(t), "-i", path, "-frames:v", "1", "-q:v", "3", out],
                capture_output=True, timeout=25,
            )
            if os.path.exists(out) and os.path.getsize(out) > 500:
                frames.append(out)
        return frames
    except Exception:
        try:
            import cv2
            cap = cv2.VideoCapture(path)
            count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if count <= 0:
                return []
            picks = sorted(int(count * (i + 0.5) / n) for i in range(n))
            frames = []
            for pi in picks:
                cap.set(cv2.CAP_PROP_POS_FRAMES, pi)
                ok, frame = cap.read()
                if ok:
                    out = os.path.join(outdir, f"c{pi}.png")
                    cv2.imwrite(out, frame)
                    frames.append(out)
            cap.release()
            return frames
        except Exception:
            return []


def analyze_video(path, n=5):
    """Sample frames, merge reports, plus per-frame variety."""
    frames = _video_frames(path, n=n)
    if not frames:
        return {"ok": False, "error": "Could not extract frames (need ffmpeg or OpenCV)."}
    reports = [analyze_image(f) for f in frames]
    ok = [r for r in reports if r.get("ok")]
    if not ok:
        return {"ok": False, "error": "Could not analyze video frames."}
    colors = ok[0]["palette_rgb"]
    brightness = sum(r["brightness"] for r in ok) / len(ok)
    colorfulness = sum(r["colorfulness"] for r in ok) / len(ok)
    structural = sum(r["structure"] for r in ok) / len(ok)
    mood, note = _mood_scalar(sum(r["brightness"] for r in ok) / len(ok), colorfulness)
    if ok[0]["mood"] != ok[-1]["mood"]:
        note += " Scene changes across the clip (multiple shots detected)."
    return {
        "ok": True,
        "frames": len(ok),
        "palette_hex": ok[0]["palette_hex"],
        "palette_rgb": colors,
        "brightness": round(brightness, 3),
        "colorfulness": round(colorfulness, 2),
        "structure": round(structural, 3),
        "mood": mood,
        "read": f"Video: {len(ok)} sampled frames. {note} Predominant colors: {', '.join(ok[0]['palette_hex'])}.",
    }


def _mood_scalar(bright, color):
    if bright < 0.35:
        return "dark", "dark footage, moody or night-time"
    if bright > 0.8:
        return "bright", "bright footage, high-key lighting"
    if color > 45:
        return "vivid", "vivid, saturated color footage"
    return "calm", "neutral-toned footage"


def concept_from_report(rep, text=""):
    """Turn a vision report (plus optional text) into a buildable concept."""
    if not rep.get("ok"):
        return theme.palette_for_image(None), "volcanic", None
    pal = theme.palette_for_image(rep.get("palette_rgb"), theme.detect_theme(text) if text else None)
    return pal, _theme_key(pal), rep


def _theme_key(pal):
    for k, p in theme.PALETTES.items():
        if p is pal:
            return k
    return "volcanic"