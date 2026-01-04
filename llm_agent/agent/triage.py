from __future__ import annotations
import json
from typing import Any, Dict, List, Optional
from llm_agent.agent.tools.kubectl import k


def collect(namespace: str, max_pods: int = 5) -> Dict[str, Any]:
    ctx = k("config", "current-context").stdout.strip()

    pods_json = k("get", "pods", "-o", "json", namespace=namespace)
    pods: List[Dict[str, Any]] = []
    if pods_json.returncode == 0:
        data = json.loads(pods_json.stdout or "{}")
        for item in (data.get("items") or [])[:max_pods]:
            pods.append({
                "name": item["metadata"]["name"],
                "phase": (item.get("status") or {}).get("phase"),
                "conditions": (item.get("status") or {}).get("conditions", []),
                "containerStatuses": (item.get("status") or {}).get("containerStatuses", []),
            })

    events = k("get", "events", "--sort-by=.lastTimestamp", namespace=namespace).stdout.strip()

    # Small, useful logs for suspicious pods
    logs: Dict[str, Dict[str, str]] = {}
    for p in pods:
        name = p["name"]
        # always try current + previous, but keep it short
        cur = k("logs", name, "--tail=80", namespace=namespace).stdout.strip()
        prev = k("logs", name, "--previous", "--tail=80", namespace=namespace)
        logs[name] = {
            "current": cur,
            "previous": (prev.stdout.strip() if prev.returncode == 0 else (prev.stderr.strip() or "")),
        }

    return {
        "context": ctx,
        "namespace": namespace,
        "pods": pods,
        "events_tail": "\n".join(events.splitlines()[-30:]),
        "logs": logs,
    }
