from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import requests
from dotenv import load_dotenv

PROMPT_PATH = Path("llm_agent/prompts/planner.md")


def _load_env() -> None:
    load_dotenv(dotenv_path=".env", override=False)


def _provider() -> str:
    return (os.getenv("LLM_PROVIDER", "ollama") or "ollama").strip().lower()


def _ollama_base_url() -> str:
    return (os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434") or "http://127.0.0.1:11434").rstrip("/")


def _ollama_model() -> str:
    return (os.getenv("OLLAMA_MODEL", "qwen2.5:7b") or "qwen2.5:7b").strip()


def _chat_ollama(system: str, user: str) -> str:
    url = f"{_ollama_base_url()}/api/chat"
    payload = {
        "model": _ollama_model(),
        "messages": [
            {"role": "system", "content": str(system)},
            {"role": "user", "content": str(user)},
        ],
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {
        "num_predict": 350,   # start 250–400; adjust later
        "temperature": 0.2,
        },
    }
    r = requests.post(url, json=payload, timeout=(10, 600))
    if not r.ok:
        raise RuntimeError(f"Ollama error {r.status_code}: {r.text}")
    data = r.json()
    return ((data.get("message") or {}).get("content") or "").strip()

def _compact_incident(incident: Dict[str, Any]) -> Dict[str, Any]:
    inc = dict(incident)

    # Kill huge sections
    inc.pop("logs", None)
    inc.pop("events_tail", None)

    # Keep only high-signal pod fields
    pods = []
    for p in inc.get("pods", [])[:5]:
        pods.append({
            "name": p.get("name"),
            "phase": p.get("phase"),
            "node": p.get("node"),
            "reason": p.get("reason"),
            "restartCount": p.get("restartCount") or p.get("restart_count"),
            # if your collector includes a shortened message, keep it
            "message": p.get("message"),
        })
    inc["pods"] = pods

    # Keep only last few events (and truncate messages)
    events = []
    for e in inc.get("events", [])[-10:]:
        msg = e.get("message") or ""
        events.append({
            "reason": e.get("reason"),
            "type": e.get("type"),
            "message": msg[:240],
        })
    inc["events"] = events

    return inc


def plan(incident: Dict[str, Any]) -> Dict[str, Any]:
    _load_env()
    system = PROMPT_PATH.read_text(encoding="utf-8")

    incident = _compact_incident(incident)
    incident_json = json.dumps(incident, indent=2, ensure_ascii=False)

    user = (
        "Incident context JSON:\n"
        f"{incident_json}\n\n"
        "Return ONLY valid JSON."
    )

    content = _chat_ollama(system, user)
    try:
        return json.loads(content)
    except Exception as e:
        raise RuntimeError("Planner returned non-JSON:\n" + content) from e

