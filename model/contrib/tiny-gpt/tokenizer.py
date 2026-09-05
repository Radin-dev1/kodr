"""Character-level tokenizer: maps text <-> token ids using the corpus vocab.

A tokenizer is what turns raw text into the integers a language model actually
learns on. This one learns a vocabulary from the training text itself, so it
works out of the box on any corpus.
"""
import json
from collections import Counter


class CharTokenizer:
    def __init__(self, vocab):
        self.chars = vocab
        self.stoi = {ch: i for i, ch in enumerate(vocab)}
        self.itos = {i: ch for i, ch in enumerate(vocab)}
        self.vocab_size = len(vocab)

    @classmethod
    def build(cls, text, max_vocab=512):
        counter = Counter(text)
        most_common = [ch for ch, _ in counter.most_common()]
        vocab = most_common[:max_vocab]
        return cls(vocab)

    def encode(self, text):
        return [self.stoi[ch] for ch in text if ch in self.stoi]

    def decode(self, ids):
        return "".join(self.itos[i] for i in ids)

    @classmethod
    def from_file(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data["vocab"])

    def to_file(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": "char-tokenizer", "vocab": self.chars}, f, ensure_ascii=False)