"""Generate text from a trained TinyGPT checkpoint.

Example:
    python generate.py --outdir out --prompt "To be or not to be, " --max-tokens 300
"""
import argparse

import torch

from gpt import load_checkpoint
from tokenizer import CharTokenizer


def parse_args():
    p = argparse.ArgumentParser(description="Sample text from a TinyGPT checkpoint")
    p.add_argument("--outdir", default="out")
    p.add_argument("--ckpt", default=None, help="model.pt path (defaults to --outdir/model.pt)")
    p.add_argument("--prompt", default="To be or not to be, ")
    p.add_argument("--max-tokens", type=int, default=500)
    p.add_argument("--temperature", type=float, default=0.8)
    p.add_argument("--top-k", type=int, default=200)
    p.add_argument("--seed", type=int, default=None)
    return p.parse_args()


def main():
    args = parse_args()
    if args.seed is not None:
        torch.manual_seed(args.seed)

    ckpt = args.ckpt or f"{args.outdir}/model.pt"
    model, config, vocab = load_checkpoint(ckpt, device="cpu")
    tokenizer = CharTokenizer(vocab)

    idx = torch.tensor([tokenizer.encode(args.prompt)], dtype=torch.long)
    out = model.generate(
        idx,
        max_new_tokens=args.max_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
    )
    print(tokenizer.decode(out[0].tolist()))


if __name__ == "__main__":
    main()