# kodr

**An open-source game generator AI.** Describe a game — get working code,
gameplay systems, and complete maps for **any** engine: Roblox (Luau),
Unity (C#), Godot (GDScript), and Unreal (C++).

```
index.html · styles.css · app.js     ← the website (served by GitHub Pages)
model/
  train.py                           ← grab a reference model → train → merge → delete reference → push
  dataset/                           ← hand-curated game-dev corpus + kodr-map-v1 schema
  tools/compile_map.py               ← compile kodr-map JSON into Luau / C# / GDScript builders
  colab/Kodr_Train.ipynb             ← free-GPU training run (T4/A100)
  space/                             ← Gradio playground (Hugging Face Spaces)
  contrib/tiny-gpt/                  ← a small from-scratch transformer, for learning
```

## Try it
- Live demo: <https://huggingface.co/spaces/Radinkazemian/kodr-playground>
- Model: <https://huggingface.co/Radinkazemian/kodr>
- Dataset: <https://huggingface.co/datasets/Radinkazemian/kodr-dataset>

## Compile a map into any engine
```bash
pip install -r model/requirements.txt
python model/tools/compile_map.py model/tools/sample_map.json --preview
python model/tools/compile_map.py model/tools/sample_map.json --engine roblox --out buildMap.lua
python model/tools/compile_map.py model/tools/sample_map.json --engine unity --out MapBuilder.cs
python model/tools/compile_map.py model/tools/sample_map.json --engine godot --out map_builder.gd
```

## Train your own Kodr
See `model/train.py` or open `model/colab/Kodr_Train.ipynb` in Google Colab
(series: Runtime → Change runtime type → GPU). It:

1. Grabs a Qwen3-class reference coder (27B)
2. QLoRA-tunes it on the public game-dev dataset
3. Merges the adapter into one standalone checkpoint
4. Deletes the reference model completely
5. Pushes **kodr** to your Hugging Face account

## License
Apache-2.0. See [LICENSE](LICENSE).