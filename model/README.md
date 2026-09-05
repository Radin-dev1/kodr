---
license: apache-2.0
datasets:
- Radinkazemian/kodr-dataset
pipeline_tag: text-generation
tags:
- game-generation
- roblox
- unity
- godot
- unreal
- code
---

# Kodr — the game generator AI

Kodr is an **open-source AI that turns design ideas into working games**: engine code,
gameplay systems, and complete levels — for **any** engine (Roblox Luau, Unity C#,
Godot GDScript, Unreal C++).

It is trained from one of the Qwen3-class coder reference models using QLoRA,
then **merged into a single standalone checkpoint**. The reference model is
removed completely after training — only Kodr remains.

## What it does

| Capability | Example output |
| --- | --- |
| Code | Full scripts: controllers, combat, inventories, saving, round systems, AI |
| Maps | `kodr-map-v1` JSON — heightmap, spawns, lighting, rules, objects |
| Any engine | Roblox Luau, Unity C#, Godot GDScript, Unreal C++ |
| Compile maps | `python model/tools/compile_map.py map.json --engine roblox` |

## Quickstart

```bash
pip install -r model/requirements.txt

# chat
python - <<'PY'
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
m = AutoModelForCausalLM.from_pretrained("Radinkazemian/kodr", device_map="auto", torch_dtype=torch.float16)
t = AutoTokenizer.from_pretrained("Radinkazemian/kodr")
msg = [{"role":"system","content":"You are Kodr, a game generator AI."},
       {"role":"user","content":"A parkour arena with wall-jumps and a lava ring."}]
inp = t.apply_chat_template(msg, tokenize=True, add_generation_prompt=True, return_tensors="pt")
print(t.decode(m.generate(inp, max_new_tokens=800)[0].tolist(), skip_special_tokens=True))
PY
```

Train it yourself: run `model/train.py` (or the Colab notebook in this repo).

## Architecture

- **Reference:** a Qwen3-class 27B coder model (open weights, Apache-2.0)
- **Training:** QLoRA (4-bit) + LoRA merge → one standalone `.safetensors` model
- **Total params:** 27B | **Seq len:** 1024

## License

Apache-2.0. The dataset is small and hand-curated per engine; see
`model/dataset/build_dataset.py`.