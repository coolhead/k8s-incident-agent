from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict

RUNS = Path("llm_agent/runs")
RUNS.mkdir(parents=True, exist_ok=True)


def write(record: Dict[str, Any]) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = RUNS / f"run-{ts}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return str(path)
