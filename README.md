# kodr

**A ready-to-play AI game-dev studio that runs entirely on your own hardware.** No
external AI services are required — every model is fully offline, deterministic,
and works on CPU. Ship it as a static site, or run `server.py` for real accounts,
per-model API keys and usage tracking.

Three models, one website:

| Model | What it does | Engine |
|---|---|---|
| **Nova-1** | Text → runnable game code (Python & Roblox fully playable; Unity / Godot / Unreal scaffolds) | `engine/nova.py` — offline, prompt-adaptive, seeded |
| **rex3d** | Text → voxel 3D world → real `.obj` / `.glb` / `.stl` meshes + preview | `engine/three_d.py` — offline voxel engine |
| **Prism-1** | Text → seeded 2D art (landscapes, nebulae, cyber skylines, sunsets, sprites, textures) | `engine/prism.py` — offline, seeded |

```
server.py                              ← self-hosted backend (auth, keys, usage, model APIs, static site)
index.html · styles.css · app.js        ← the website (demo mode works with zero backend)
engine/
  nova.py                              ← Nova-1 code generation (fully offline)
  prism.py                             ← Prism-1 2D generation (fully offline)
  three_d.py                           ← rex3d voxel world → OBJ/GLB/STL
  theme.py                             ← palettes + world synthesis for every mood
  vision.py                            ← image/video analysis (legacy, used by the old Gradio app)
  codegen.py · llm.py                  ← legacy Smart-code path (optional, needs HF token)
app.py · api.py                        ← legacy Gradio playground + stdlib API
model/                                 ← training pipeline + dataset (optional)
```

## Quick start

**Option A — static site (demo mode).** Open `index.html` in a browser. Accounts,
keys and generation all live in your browser via `localStorage`, with in-browser
generators for all three models.

**Option B — self-hosted server (recommended for real accounts/keys/usage).**

```bash
cd kodr
python server.py                # defaults to :7860  (KODR_PORT to override)
```

Then open <http://localhost:7860>. Sign up, grab an API key per model inside
**Account**, and generate from the in-site playground or over HTTP:

```bash
# sign up
curl -X POST localhost:7860/api/auth/signup -H "Content-Type: application/json" \
     -d '{"username":"dev","email":"dev@example.com","password":"secret123"}'

# create a Nova-1 key (this returns the full key once)
curl -X POST localhost:7860/api/keys -H "Content-Type: application/json" \
     -b <session-cookie> -d '{"model":"nova1"}'

# generate a playable Python game
curl -X POST localhost:7860/api/v1/nova1/generate -H "Content-Type: application/json" \
     -H "Authorization: Bearer <nova1_dev_...>" \
     -d '{"prompt":"ice parkour race with drones","engine":"python"}'

# generate a 3D world (obj/glb/stl/preview in the response)
curl -X POST localhost:7860/api/v1/rex3d/generate -H "Content-Type: application/json" \
     -H "Authorization: Bearer <rex3d_dev_...>" -d '{"prompt":"snow village","size":12}'

# generate 2D art
curl -X POST localhost:7860/api/v1/prism1/generate -H "Content-Type: application/json" \
     -H "Authorization: Bearer <prism1_dev_...>" -d '{"prompt":"neon cyberpunk skyline"}'
```

## Model API surface

| Endpoint | Key model | Returns |
|---|---|---|
| `POST /api/v1/nova1/generate` | `nova1` | playable code, theme, seed, per-prompt features (enemy, difficulty, objective) |
| `POST /api/v1/rex3d/generate` | `rex3d` | mesh dict with `obj`, `glb`, `stl`, `preview_b64` base64 payloads |
| `POST /api/v1/prism1/generate` | `prism1` | `image_b64` PNG + palette + style + seed |

Auth / account endpoints: `/api/auth/signup|login|logout|me`, `/api/keys`,
`/api/keys/revoke`, `/api/keys/regenerate`, `/api/usage`, `/api/config`. Keys are
model-scoped (a Nova-1 key is rejected by rex3d and Prism-1), stored hashed
(SHA-256), shown masked, and usage is logged per key with a daily breakdown.

## Connect to a game engine

Nova-1 emits full, self-contained code you drop straight into your engine:

- **Roblox Studio** — generate the `roblox` variant, copy the script into
  `ServerScriptService`, done.
- **Python / pygame** — `python main.py` from the generated file.
- **Unity** — `MapBuilder.cs` scaffold plugs into a MonoBehaviour.
- **Godot** — `map_builder.gd` scaffold.
- **Unreal** — `kodr_world.h` / `kodr_world.cpp` scaffold.

## Legacy tooling (optional)

- `python model/tools/compile_map.py model/tools/sample_map.json --engine roblox --out buildMap.lua` — compile a hand-authored map into any engine.
- `python model/train.py` — QLoRA-tune a coder model on the game-dev corpus (needs GPU + Hugging Face account). Purely optional; the site never talks to Hugging Face.

## License

Apache-2.0. See [LICENSE](LICENSE).