"""Kodr Playground Space — a working game-generation engine.

Three tabs:
  Code    : idea -> playable Python game file (AI-first, local fallback)
  3D Forge: text or image -> downloadable OBJ/GLB/STL mesh + preview
  Vision  : image/video -> scene report + theme, then optionally a game
"""
from __future__ import annotations

import os
import sys

import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import codegen, three_d, vision  # noqa: E402
from engine import theme as theme_mod  # noqa: E402

TITLE = "Kodr — game-generation engine"
DESC = """Turn a sentence, an image, or a video clip into a playable game and
downloadable 3D world. The build pipeline never hard-fails: code generation uses
a routed open LLM when a token is available, and every output has a guaranteed
offline fallback."""


def make_code(idea, human_theme):
    desc = (idea or "").strip() or "A heroic adventure in a magical land"
    key = human_theme or theme_mod.detect_theme(desc)
    res = codegen.generate(desc, theme_key=key)
    code = codegen.concept_to_py(res)
    fname = "my_game.py"
    with open(fname, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    summary = (
        f"**{res['title']}**  ·  engine `{res['engine']}`  ·  theme `{res['meta']['theme']}`\n\n"
        f"Mechanics detected: {', '.join(res['meta']['mechanics']) or 'none — open-ended'}\n"
        "```python\n"
        + code[:2400]
        + ("\n# … (truncated preview)" if len(code) > 2400 else "")
        + "\n```"
    )
    return summary, fname


def _file_path(x):
    """Normalize gradio's file inputs (str | dict | list | FileData) to a path."""
    if isinstance(x, (list, tuple)):
        for item in x:
            p = _file_path(item)
            if p:
                return p
        return None
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        return x.get("path") or x.get("url") or None
    if hasattr(x, "path"):
        return x.path
    return None


def make_3d(text_theme, image, size):
    img_path = _file_path(image)
    result = three_d.generate(text=(text_theme or ""), image_path=img_path, size=int(size))
    md = f"**World:** `{result['theme']}` · {result['meta']['voxels']} voxels · cloud: {result.get('cloud', False)}\n"
    if result.get("cloud_error"):
        md += f"\n_(cloud mesh failed: {result['cloud_error']}; showing guaranteed local build)_\n"
    md += (
        "\n**Use the mesh in any engine:** import `kodr_world.obj` / `kodr_world.glb` / "
        "`kodr_world.stl` at `size=1`, rotate 90° to match your axis convention.\n"
    )
    return md, result["preview"], [result["obj"], result["glb"], result["stl"]]


def build_concept_from_report(report, brief):
    pal, key, _ = vision.concept_from_report(report, brief)
    return key, pal


def run_vision_report(input_path):
    input_path = _file_path(input_path)
    if not input_path or not os.path.exists(input_path):
        return "Upload an image or a video first."
    ext = os.path.splitext(input_path)[1].lower()
    if ext in (".mp4", ".mov", ".webm", ".mkv", ".avi"):
        rep = vision.analyze_video(input_path, n=5)
    else:
        rep = vision.analyze_image(input_path)
    if not rep.get("ok"):
        return f"Analysis failed: {rep.get('error')}"
    pal, key, _ = vision.concept_from_report(rep, "")
    return (
        f"**Scene read** — mood: `{rep['mood']}` · palette: {', '.join(rep['palette_hex'])}\n\n"
        f"{rep['read']}\n\nSuggested Kodr theme: **{pal['name']}** (`{key}`).\n"
        "Turn this into a game with the button below."
    )


def vision_to_game(input_path, brief):
    input_path = _file_path(input_path)
    from engine import vision as _vision
    rep = None
    if input_path and os.path.exists(input_path):
        ext = os.path.splitext(input_path)[1].lower()
        if ext in (".mp4", ".mov", ".webm", ".mkv", ".avi"):
            rep = _vision.analyze_video(input_path, n=5)
        else:
            rep = _vision.analyze_image(input_path)
    key_ = None
    if rep and rep.get("ok"):
        _, key_, _ = _vision.concept_from_report(rep, "")
    if not key_:
        key_ = theme_mod.detect_theme(brief or "")
    pal = theme_mod.PALETTES[key_]["colors"][:4]
    desc = (brief or "").strip() or "An adventure set in a world like this scene"
    res = codegen.generate(desc, theme_key=key_, palette=list(pal))
    code = codegen.concept_to_py(res)
    fname = "vision_game.py"
    with open(fname, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    out = (f"**Turned your `{os.path.basename(input_path)}` into a game** — theme `{key_}` "
           f"via `{res['engine']}`.\n\n```python\n{code[:1400]}\n```")
    return out, fname


with gr.Blocks(title=TITLE) as demo:
    gr.Markdown(f"# {TITLE}\n\n{DESC}")

    with gr.Tab("🎮 Code"):
        with gr.Row():
            with gr.Column():
                idea = gr.Textbox(
                    label="Your game idea",
                    placeholder="A lava dungeon where you survive waves of enemies and escape…",
                    lines=4,
                )
                code_theme = gr.Dropdown(
                    label="Theme (optional — auto-detected from text)",
                    choices=list(theme_mod.PALETTES.keys()),
                    value=None,
                )
                code_btn = gr.Button("Generate game", variant="primary")
            with gr.Column():
                code_out = gr.Markdown()
                code_file = gr.File(label="Download .py")

    with gr.Tab("🧊 3D Forge"):
        with gr.Row():
            with gr.Column():
                t3 = gr.Textbox(label="Describe a world", placeholder="volcanic arena or neon city…", lines=3)
                img3 = gr.Image(label="…or use an image (optional)", type="filepath")
                size3 = gr.Slider(12, 36, value=20, step=1, label="Grid size")
                forge_btn = gr.Button("Build 3D world", variant="primary")
            with gr.Column():
                forge_md = gr.Markdown()
                forge_preview = gr.Image(label="Preview")
                forge_files = gr.File(label="Mesh files (.obj .glb .stl)")

    with gr.Tab("👁 Vision"):
        with gr.Row():
            with gr.Column():
                media = gr.File(label="Image or video", file_types=["image", "video"])
                brief = gr.Textbox(label="Optional: steer the generated game", placeholder="Make it a race across the scene", lines=2)
                read_btn = gr.Button("Read scene", variant="primary")
                gen_btn = gr.Button("Turn this scene into a game", variant="secondary")
            with gr.Column():
                read_out = gr.Markdown()
                vision_game_out = gr.Markdown()
                vision_file = gr.File(label="Download generated .py")

    code_btn.click(make_code, [idea, code_theme], [code_out, code_file])
    forge_btn.click(make_3d, [t3, img3, size3], [forge_md, forge_preview, forge_files])
    read_btn.click(run_vision_report, [media], [read_out])
    gen_btn.click(vision_to_game, [media, brief], [vision_game_out, vision_file])


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=2).launch(theme=gr.themes.Soft(), show_error=True)