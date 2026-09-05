# kodr

**An open-source game-generation engine that actually runs.** Feed it a sentence,
an image, or a video clip — it returns a playable game and a downloadable 3D world.

```
app.py                               ← Gradio playground (Hugging Face Spaces)
api.py                               ← stdlib HTTP API (GET /v1/engines, POST /v1/generate|/v1/map|/v1/3d|/v1/vision)
engine/
  llm.py                             ← routed open LLM over the free HF Inference router
  vision.py                          ← reads images AND videos (ffmpeg/OpenCV frame sampling)
  three_d.py                         ← text/image → voxel world → real .obj/.glb/.stl meshes
  codegen.py                         ← AI-first game code, guaranteed local fallback
  theme.py                           ← palettes + world synthesis for every mood
model/                               ← training pipeline, dataset + kodr-map-v1 compiler (optional)
index.html · styles.css · app.js     ← the website (served by GitHub Pages)
```

## What works (all verified end-to-end)

| Capability | How | Verification |
|---|---|---|
| Text → game code | Qwen2.5-Coder-7B over `router.huggingface.co` (free token) | Generated game executed all 60 frames to victory |
| Image / video understanding | Local CV: palette, mood, structure; ffmpeg frame sampling | Image + synthesized clip both analyzed |
| Text / image → 3D | Procedural voxel worlds → OBJ + GLB + STL + PNG preview | Files parsed + cross-validated (face counts match) |
| Never breaks | Every layer has an offline fallback; cloud bits are opt-in | Fallback produced runnable code when LLM was down |

Codegen is **LLM-first**: a real open coder model writes the game. If the router is
unreachable or no `HF_TOKEN` is present, a self-contained template engine takes
over — the user always gets working code, never an error screen.

## Try it
- Live playground: <https://huggingface.co/spaces/Radinkazemian/kodr-playground>
- Website: <https://radin-dev1.github.io/kodr/>
- Model / dataset (training artifacts): <https://huggingface.co/Radinkazemian/kodr>
- Run locally: `python app.py` (needs `pip install -r requirements.txt`)

## Use the API
```bash
python api.py            # defaults to :8080

curl localhost:8080/v1/engines
curl -X POST localhost:8080/v1/generate -H "Content-Type: application/json" \
     -d '{"description": "A lava dungeon survival game"}'
curl -X POST localhost:8080/v1/map -H "Content-Type: application/json" \
     -d '{"description": "neon city race", "size": 20}'
curl -X POST localhost:8080/v1/3d -H "Content-Type: application/json" \
     -d '{"description": "ocean ruins", "size": 16}'
```

For the smart code path, export your Hugging Face token:
`export HF_TOKEN=hf_…` (the router is OpenAI-compatible; no key needed beyond your
free HF account token). Without it everything still works via the local engine.

## Compile a hand-authored map into any engine (legacy tooling)
```bash
python model/tools/compile_map.py model/tools/sample_map.json --preview
python model/tools/compile_map.py model/tools/sample_map.json --engine roblox --out buildMap.lua
python model/tools/compile_map.py model/tools/sample_map.json --engine unity --out MapBuilder.cs
python model/tools/compile_map.py model/tools/sample_map.json --engine godot --out map_builder.gd
```

## Train your own Kodr
Optional. See `model/train.py` or open `model/colab/Kodr_Train.ipynb` in Google
Colab (Runtime → Change runtime type → GPU). It QLoRA-tunes a Qwen3-class coder on
the public game-dev corpus and pushes a merged standalone checkpoint to your
Hugging Face account.

## License
Apache-2.0. See [LICENSE](LICENSE).