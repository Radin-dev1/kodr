"""Dataset handling for TinyGPT.

By default it downloads the classic "tiny shakespeare" corpus (1.1 MB of
Shakespeare plays) when it is missing locally. You can instead point at any
plain-text file with --dataset.
"""
import os
import urllib.request

import torch

TINY_SHAKESPEARE_URL = (
    "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/"
    "tinyshakespeare/input.txt"
)


def download(url, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    print(f"Downloading {url} -> {path}")
    urllib.request.urlretrieve(url, path)


def ensure_dataset(path):
    if os.path.exists(path):
        return
    try:
        download(TINY_SHAKESPEARE_URL, path)
    except Exception as e:
        raise SystemExit(
            f"Could not download the dataset ({e}). "
            "Pass any local text file to --dataset instead."
        )


def get_text(path):
    ensure_dataset(path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_batch(data, block_size, batch_size, device="cpu"):
    ix = torch.randint(len(data) - block_size - 1, (batch_size,))
    x = torch.stack([data[i : i + block_size] for i in ix])
    y = torch.stack([data[i + 1 : i + 1 + block_size] for i in ix])
    return x.to(device), y.to(device)