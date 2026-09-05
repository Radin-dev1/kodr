"""Train TinyGPT from scratch on character-level text.

Example:
    python train.py --outdir out --max-iters 3000

The model, its config, the tokenizer, and the modules needed to load it later
are all written into --outdir so the folder can be pushed to Hugging Face as-is.
"""
import argparse
import json
import math
import os
import random
import shutil
import time

import torch

import data
from gpt import Config, Gpt, save_checkpoint, save_config_json
from tokenizer import CharTokenizer

OUTPUT_EXTRA_FILES = ("gpt.py", "tokenizer.py")


def parse_args():
    p = argparse.ArgumentParser(description="Train TinyGPT from scratch")
    p.add_argument("--outdir", default="out", help="where checkpoints go")
    p.add_argument("--dataset", default="data/tinyshakespeare.txt", help="text file (auto-downloaded)")
    p.add_argument("--n-layer", type=int, default=6)
    p.add_argument("--n-head", type=int, default=4)
    p.add_argument("--n-embd", type=int, default=128)
    p.add_argument("--block-size", type=int, default=128)
    p.add_argument("--dropout", type=float, default=0.0)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--max-iters", type=int, default=3000)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--min-lr", type=float, default=3e-5)
    p.add_argument("--warmup-iters", type=int, default=200)
    p.add_argument("--eval-interval", type=int, default=500)
    p.add_argument("--eval-iters", type=int, default=100)
    p.add_argument("--sample-interval", type=int, default=1000)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--grad-clip", type=float, default=1.0)
    return p.parse_args()


def configure_optimizer(model, lr):
    decay, no_decay = [], []
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if param.dim() >= 2 and "lm_head" not in name and "position_embedding" not in name:
            decay.append(param)
        else:
            no_decay.append(param)
    groups = [
        {"params": decay, "weight_decay": 0.1},
        {"params": no_decay, "weight_decay": 0.0},
    ]
    return torch.optim.AdamW(groups, lr=lr, betas=(0.9, 0.95))


@torch.no_grad()
def estimate_loss(model, train_data, val_data, block_size, batch_size, eval_iters, device):
    model.eval()
    losses = {}
    for split, split_data in (("train", train_data), ("val", val_data)):
        total = 0.0
        for _ in range(eval_iters):
            x, y = data.get_batch(split_data, block_size, batch_size, device)
            _, loss = model(x, y)
            total += loss.item()
        losses[split] = total / eval_iters
    model.train()
    return losses


@torch.no_grad()
def sample_text(model, tokenizer, prompt, max_new_tokens, device):
    idx = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long, device=device)
    out = model.generate(idx, max_new_tokens=max_new_tokens, temperature=0.8, top_k=100)
    text = tokenizer.decode(out[0].tolist())
    return prompt + text[len(prompt):]


def main():
    args = parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    os.makedirs(args.outdir, exist_ok=True)
    text = data.get_text(args.dataset)
    tokenizer = CharTokenizer.build(text)
    split_at = int(len(text) * 0.9)
    train_data = torch.tensor(tokenizer.encode(text[:split_at]), dtype=torch.long)
    val_data = torch.tensor(tokenizer.encode(text[split_at:]), dtype=torch.long)

    config = Config(
        vocab_size=tokenizer.vocab_size,
        block_size=args.block_size,
        n_layer=args.n_layer,
        n_head=args.n_head,
        n_embd=args.n_embd,
        dropout=args.dropout,
    )
    model = Gpt(config)
    print(f"vocab={tokenizer.vocab_size} params={model.num_parameters():,}")

    save_config_json(os.path.join(args.outdir, "config.json"), config)
    tokenizer.to_file(os.path.join(args.outdir, "tokenizer.json"))
    for f in OUTPUT_EXTRA_FILES:
        shutil.copy(f, os.path.join(args.outdir, f))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    optimizer = configure_optimizer(model, args.lr)
    best_val = float("inf")

    train_iter = args.max_iters
    start = time.time()
    for step in range(train_iter):
        lr = args.lr
        if step < args.warmup_iters:
            lr = args.lr * (step + 1) / args.warmup_iters
        else:
            progress = (step - args.warmup_iters) / max(1, args.max_iters - args.warmup_iters)
            lr = args.min_lr + 0.5 * (args.lr - args.min_lr) * (1 + math.cos(math.pi * progress))
        for group in optimizer.param_groups:
            group["lr"] = lr

        x, y = data.get_batch(train_data, args.block_size, args.batch_size, device)
        _, loss = model(x, y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
        optimizer.step()

        if step % args.eval_interval == 0 or step == args.max_iters - 1:
            losses = estimate_loss(
                model, train_data, val_data, args.block_size, args.batch_size,
                args.eval_iters, device,
            )
            model.to(device)
            model.train()
            dt = time.time() - start
            print(
                f"step {step:6d} | train {losses['train']:.4f} | val {losses['val']:.4f} "
                f"| lr {lr:.2e} | {dt:.0f}s"
            )
            if losses["val"] < best_val:
                best_val = losses["val"]
                save_checkpoint(
                    os.path.join(args.outdir, "model.pt"), model, config, tokenizer.chars
                )
                print(f"    saved checkpoint (val {best_val:.4f})")

        if step % args.sample_interval == 0 or step == args.max_iters - 1:
            text_out = sample_text(model, tokenizer, "To be or not to be, ", 300, device)
            print("    sample:", text_out.replace("\n", " ")[:160])

    if not os.path.exists(os.path.join(args.outdir, "model.pt")):
        save_checkpoint(os.path.join(args.outdir, "model.pt"), model, config, tokenizer.chars)
    print(f"DONE. checkpoint at {args.outdir}/model.pt (best val {best_val:.4f})")


if __name__ == "__main__":
    main()