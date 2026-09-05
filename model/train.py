"""Train Kodr - your standalone, universal game-generation model.

Workflow ("use a reference model, then remove it"):
  1. Grab one of the reference models (Qwen3 class, 27B):
       - Qwen/Qwen3.8-27B                          (primary trainable base)
       - Kwaipilot/KAT-Coder-V2.5-Dev              (alternative coder base)
       - DavidAU/Qwen3.8-27B-TURBO-...-GGUF        (GGUF build - use as
         teacher to generate more training data, not as a LoRA base)
  2. Fine-tune it on the game-dev dataset with LoRA (QLoRA 4-bit on GPU).
  3. Merge the LoRA adapter INTO the base weights -> a single standalone model.
  4. Delete every trace of the base model (local dir + HF cache + adapters).
     From here on you only ship / run / read YOUR merged model - the
     reference model is fully removed.

A 27B base needs ~40 GB VRAM with QLoRA. Free Colab T4 (16 GB) cannot fit it;
the provided notebook auto-picks the largest trainable Qwen3 base for the GPU
it sees. Verify the pipeline cheaply on CPU with:
    python train.py --base-model sshleifer/tiny-gpt2 --steps 4
"""
import argparse
import gc
import json
import os
import shutil

import torch
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SYSTEM = (
    "You are Kodr, a world-class game generator AI. You turn design ideas "
    "into complete, working game code, systems, and maps for ANY engine "
    "(Roblox Luau, Unity C#, Godot GDScript, Unreal C++). You output universal "
    "kodr-map-v1 JSON for maps. Be concise, correct, and engine-agnostic."
)
DEFAULT_BASE = "Qwen/Qwen3.8-27B"
REFERENCE_MODELS = {
    "qwen3-27b": "Qwen/Qwen3.8-27B",
    "kat-coder": "Kwaipilot/KAT-Coder-V2.5-Dev",
    "turbo-gguf": "DavidAU/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NEO-CODER-MAX-MTP-GGUF",
}
DATASET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset", "kodr-dataset.jsonl")


def parse_args():
    p = argparse.ArgumentParser(description="Train the Kodr model")
    p.add_argument("--dataset", default=DATASET)
    p.add_argument("--base-model", default=DEFAULT_BASE,
                   help="the reference model to train from: " + ", ".join(REFERENCE_MODELS.values()))
    p.add_argument("--repo", default="kodr", help="HF repo name for the final standalone model")
    p.add_argument("--output", default="merged")
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    p.add_argument("--max-seq-len", type=int, default=1024)
    p.add_argument("--steps", type=int, default=None, help="override total steps (smoke test)")
    p.add_argument("--push", action="store_true", help="push the standalone model to HF")
    p.add_argument("--keep-base", action="store_true", help="DANGER: keep the base model files after merging")
    return p.parse_args()


def load_dataset(path):
    try:
        from datasets import Dataset
    except ImportError:
        raise SystemExit("Missing dependency. Run: pip install -r requirements.txt")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise SystemExit("Dataset is empty. Run dataset/build_dataset.py first.")
    return Dataset.from_list(rows)


def main():
    args = parse_args()
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
    use_gpu = torch.cuda.is_available()
    print(f"device: {'CUDA' if use_gpu else 'CPU'} | base (reference): {args.base_model}")

    from transformers import AutoModelForCausalLM, AutoTokenizer

    # 4-bit QLoRA when we have a GPU; plain fp32 LoRA otherwise.
    kwargs = {"device_map": "auto" if use_gpu else "cpu"}
    if use_gpu:
        try:
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
        except Exception as e:
            print(f"  (no 4-bit on this box: {e})")

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.base_model, trust_remote_code=True, **kwargs)

    from peft import LoraConfig
    from trl import SFTTrainer
    from transformers import TrainingArguments

    lora = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )

    def fmt(example):
        return tokenizer.apply_chat_template(example["messages"], tokenize=False, add_generation_prompt=False)

    max_steps = args.steps
    if max_steps is None:
        max_steps = -1  # run epochs until done

    import inspect
    trainer_kwargs = {}
    if "processing_class" in inspect.signature(SFTTrainer.__init__).parameters:
        trainer_kwargs["processing_class"] = tokenizer
    else:
        trainer_kwargs["tokenizer"] = tokenizer

    trainer = SFTTrainer(
        model=model,
        args=TrainingArguments(
            output_dir="training-out",
            per_device_train_batch_size=1 if use_gpu else 4,
            gradient_accumulation_steps=8 if use_gpu else 2,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            max_steps=max_steps,
            fp16=use_gpu,
            logging_steps=5,
            save_strategy="no",
            report_to=[],
            seed=1337,
        ),
        train_dataset=load_dataset(args.dataset),
        peft_config=lora,
        formatting_func=fmt,
        max_seq_length=args.max_seq_len,
        **trainer_kwargs,
    )

    trainer.train()
    print(">> Training done. Merging LoRA into the base weights...")

    # ---- MERGE: produce a single standalone model ----
    merged = trainer.model.merge_and_unload()
    os.makedirs(args.output, exist_ok=True)
    merged.save_pretrained(args.output, safe_serialization=True)
    tokenizer.save_pretrained(args.output)
    del trainer, merged
    gc.collect()
    if use_gpu:
        torch.cuda.empty_cache()

    # ---- REMOVE the reference model fully (unless --keep-base) ----
    if not args.keep_base:
        print(">> Removing the reference model completely...")
        for d in ("training-out", "adapted"):
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
        from huggingface_hub import scan_cache_dir
        try:
            info = scan_cache_dir()
            for rev in info.revisions:
                repo = rev.repo_name.replace("--", "/")
                if repo == args.base_model or args.base_model.endswith(rev.repo_name):
                    print("   purging HF cache for", repo)
                    delete_stale = rev.delete()
                    delete_stale.commit()
        except Exception as e:
            print("   (cache cleanup skipped:", e, ")")
    else:
        print(">> NOTE: --keep-base set - reference model files kept (not recommended).")

    # ---- PUSH the standalone model to Hugging Face ----
    if args.push or token:
        from huggingface_hub import HfApi
        user = HfApi().whoami()["name"]
        repo_id = f"{user}/{args.repo}"
        api = HfApi()
        api.create_repo(repo_id, token=token, exist_ok=True, private=False)
        api.upload_folder(folder_path=args.output, repo_id=repo_id, token=token)
        print(f">> DONE. Your standalone model: https://huggingface.co/{repo_id}")
    else:
        print(">> Model saved locally in", args.output, "- push it later with --push.")


if __name__ == "__main__":
    main()