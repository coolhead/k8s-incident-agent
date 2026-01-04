from __future__ import annotations

import json
import os
import requests
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LLMResponse:
    text: str
    raw: Dict[str, Any]


def ollama_chat(prompt: str, system: Optional[str] = None) -> LLMResponse:
    """
    Calls Ollama's chat endpoint.
    Default model chosen via OLLAMA_MODEL env var.
    """
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.2")),
            "num_ctx": int(os.getenv("OLLAMA_CTX", "4096")),
        },
    }

    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()

    # Ollama returns: {"message": {"role":"assistant","content":"..."} , ...}
    text = data.get("message", {}).get("content", "") or ""
    return LLMResponse(text=text, raw=data)
