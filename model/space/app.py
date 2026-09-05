"""Kodr Playground - chat with the standalone Kodr game-generation model.

The Space ONLY loads the merged Kodr checkpoint from the model repo (no base
model, no adapters). Pick what to build and Kodr writes the code or map.
"""
import os

import gradio as gr
import torch
from huggingface_hub import snapshot_download
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_REPO = os.environ.get("KODR_MODEL_REPO", "Radinkazemian/kodr")

SYSTEM = (
    "You are Kodr, a world-class game generator AI. You turn design ideas into "
    "complete, working game code, systems, and maps for ANY engine. Output only "
    "the code or JSON, no chatter, unless asked for an explanation."
)
MODE_PROMPT = {
    "Roblox (Luau)": "Write clean, production-quality Roblox Luau with server-authoritative logic, remotes, and DataStore.",  # noqa: E501
    "Unity (C#)": "Write clean, production-ready Unity C# with UnityEvents and no allocations in hot paths.",
    "Godot (GDScript)": "Write clean Godot 4 GDScript with typed signals and exported vars.",
    "Unreal (C++)": "Write clean Unreal C++ with UFUNCTION/UCLASS macros and UPARAM usage.",
    "Map (kodr-map-v1 JSON)": "Design a complete level and output ONLY the kodr-map-v1 JSON schema (name, theme, tile_scale, size, heightmap, lighting, spawn_logic, game_rules, objects, soundscape, design_notes).",  # noqa: E501
}


def build_model():
    path = snapshot_download(MODEL_REPO, ignore=["*.json", "README*", "*.md", "adapter_*"]) or "./model"
    model = AutoModelForCausalLM.from_pretrained(path, device_map="auto", torch_dtype=torch.float16)
    tokenizer = AutoTokenizer.from_pretrained(path)
    return model, tokenizer


try:
    model, tokenizer = build_model()
    READY = True
except Exception as e:
    model = tokenizer = None
    READY = False
    print("WARNING: model not available yet:", e)


def generate(mode, idea, temperature, max_new_tokens):
    if not READY:
        return "Kodr weights are not published yet. Run model/train.py --push (see the Colab notebook in the repo) and this box will serve your model instantly."
    prompt = [
        {"role": "system", "content": SYSTEM + "\n" + MODE_PROMPT[mode]},
        {"role": "user", "content": idea},
    ]
    text = tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=int(max_new_tokens),
            temperature=float(temperature),
            top_p=0.95,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


with gr.Blocks(theme=gr.themes.Soft(primary_hue="lime"), title="Kodr Playground") as demo:
    gr.Markdown(
        "# ⚡ Kodr — make games in any engine\n"
        "Open-source AI that writes **code, systems, and complete maps**. "
        f"Model: [`{MODEL_REPO}`](https://huggingface.co/{MODEL_REPO})."
    )
    with gr.Row():
        with gr.Column(scale=2):
            mode = gr.Dropdown(list(MODE_PROMPT.keys()), value="Roblox (Luau)", label="What are you making?")
            idea = gr.Textbox(label="Describe your idea", lines=5,
                              value="A parkour arena with wall-jumps, moving platforms, and a lava ring that slowly closes in.")
            with gr.Row():
                temp = gr.Slider(0.1, 1.5, value=0.7, step=0.05, label="Creativity")
                tokens = gr.Slider(128, 4096, value=1024, step=128, label="Max tokens")
            btn = gr.Button("Generate", variant="primary")
        with gr.Column(scale=3):
            out = gr.Code(label="Output", language="lua")

    btn.click(generate, [mode, idea, temp, tokens], out)


if __name__ == "__main__":
    demo.launch()