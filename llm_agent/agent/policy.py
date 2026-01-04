from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple


WRITE_VERBS = {"apply", "delete", "patch", "create", "edit", "replace", "scale", "rollout"}


@dataclass
class Decision:
    allowed: bool
    reason: str


def is_write(cmd: List[str]) -> bool:
    return bool(cmd) and cmd[0] in WRITE_VERBS


def evaluate(step: Dict) -> Decision:
    cmd = step.get("cmd") or []
    ro = step.get("read_only", True)

    # If it *looks* like a write, must not be marked read_only
    if is_write(cmd) and ro:
        return Decision(False, "Write-like command marked read_only=true")

    # Hard deny dangerous stuff (tighten later)
    joined = " ".join(cmd)
    if "delete ns" in joined or "delete namespace" in joined:
        return Decision(False, "Refusing namespace deletion")

    return Decision(True, "ok")
