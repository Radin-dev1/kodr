"""Minimal OpenAI-compatible client for the free Hugging Face Inference router."""
import json
import os

import requests

ROUTER = "https://router.huggingface.co/v1/chat/completions"
CODER_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
REASONER_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"


def available() -> bool:
    return bool(os.environ.get("HF_TOKEN"))


def chat(model, messages, max_tokens=1024, temperature=0.4, timeout=150):
    """Return assistant text, or None if the router is unreachable / no token."""
    if not available():
        return None
    try:
        r = requests.post(
            ROUTER,
            headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": int(max_tokens),
                "temperature": float(temperature),
            },
            timeout=timeout,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def strip_fences(text):
    if not text:
        return ""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        lines = lines[1:] if lines and lines[0].startswith("```") else lines
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def parse_json(text):
    """Best-effort parse of a JSON object from (possibly fenced) model output."""
    cleaned = strip_fences(text)
    start = cleaned.find("{")
    if start == -1:
        return None
    # scan for the first complete top-level object
    depth = 0
    in_str = False
    esc = False
    end = -1
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
    if end == -1:
        return None
    try:
        return json.loads(cleaned[start:end])
    except Exception:
        return None