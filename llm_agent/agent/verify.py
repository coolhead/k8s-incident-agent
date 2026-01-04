from __future__ import annotations
from llm_agent.agent.tools.kubectl import k


def verify(namespace: str) -> str:
    return k("get", "pods", "-o", "wide", namespace=namespace).stdout.strip()
