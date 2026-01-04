from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent.tools.kubectl import (
    current_context,
    describe_pod,
    get_events,
    get_pods,
    get_pods_json,
    logs,
)

c = Console()

ISSUE_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("CrashLoopBackOff", re.compile(r"CrashLoopBackOff", re.I)),
    ("ImagePullBackOff", re.compile(r"ImagePullBackOff|ErrImagePull", re.I)),
    ("OOMKilled", re.compile(r"OOMKilled", re.I)),
    ("Pending/Unschedulable", re.compile(r"Pending|Unschedulable|FailedScheduling", re.I)),
    ("ProbeFail", re.compile(r"Readiness probe failed|Liveness probe failed", re.I)),
    ("CreateContainerConfigError", re.compile(r"CreateContainerConfigError", re.I)),
]


@dataclass
class PodIssue:
    pod: str
    phase: str
    restarts: str
    issue: str


def _find_bad_pods_from_table(pods_text: str) -> List[str]:
    bad: List[str] = []
    for line in pods_text.splitlines():
        if line.startswith("NAME") or not line.strip():
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[0]
        status = parts[2]
        if status not in ("Running", "Completed"):
            bad.append(name)
    return bad


def _classify(blob: str) -> str:
    for label, pat in ISSUE_PATTERNS:
        if pat.search(blob):
            return label
    if re.search(r"\bError\b", blob, re.I):
        return "Crashed (likely CrashLoop)"
    return "Unknown"


def _suggest(issue: str) -> str:
    return {
        "CrashLoopBackOff": "Get logs (--previous), confirm exit code, fix command/config, redeploy.",
        "Crashed (likely CrashLoop)": "Pod is crashing fast; check logs/describe; it becomes CrashLoopBackOff soon.",
        "ImagePullBackOff": "Fix image/tag/registry creds; patch deployment; verify imagePullSecrets.",
        "OOMKilled": "Increase memory; reduce load; check leaks; scale; confirm restarts stop.",
        "Pending/Unschedulable": "Requests too high/taints; adjust requests/tolerations or add capacity.",
        "ProbeFail": "Check probe path/port/timeouts; tune probes or fix app startup.",
        "CreateContainerConfigError": "Env/secret/config invalid; check describe events; fix refs.",
        "Unknown": "Inspect describe+events for signal: RBAC, DNS, NetworkPolicy, volumes, probes.",
    }.get(issue, "Inspect describe+events.")


def main(
    namespace: str = typer.Option("demo", "--namespace", "-n"),
    pod: Optional[str] = typer.Option(None, "--pod", "-p"),
    max_pods: int = typer.Option(5, "--max-pods"),
):
    """Read-only triage: pods/events/describe/logs -> diagnosis + suggested actions."""
    ctx = current_context()
    if ctx.returncode == 0:
        c.print(Panel(f"[bold]kubectl context:[/bold] {ctx.stdout.strip()}"))

    pods = get_pods(namespace)
    if pods.returncode != 0:
        c.print(Panel(f"[red]Failed to list pods[/red]\n{pods.stderr}", title="kubectl error"))
        raise typer.Exit(1)

    c.print(Panel(pods.stdout.strip(), title=f"Pods in {namespace}"))

    target_pods = [pod] if pod else _find_bad_pods_from_table(pods.stdout)
    if not target_pods:
        c.print(Panel("[green]No failing pods detected.[/green] You're chilling.", title="Result"))
        return

    events = get_events(namespace)
    events_text = (events.stdout + "\n" + events.stderr).strip()

    pods_json = get_pods_json(namespace)
    pod_meta: Dict[str, Tuple[str, str]] = {}
    if pods_json.returncode == 0:
        data = json.loads(pods_json.stdout)
        for item in data.get("items", []):
            name = item["metadata"]["name"]
            phase = item.get("status", {}).get("phase", "?")
            cs = item.get("status", {}).get("containerStatuses", []) or []
            restarts = str(cs[0].get("restartCount", 0)) if cs else "0"
            pod_meta[name] = (phase, restarts)

    table = Table(title="Triage Summary")
    table.add_column("Pod", style="bold")
    table.add_column("Phase")
    table.add_column("Restarts")
    table.add_column("Likely Issue")
    table.add_column("Suggested Next Actions")

    ranked: List[PodIssue] = []
    for p in target_pods[:max_pods]:
        desc = describe_pod(namespace, p)
        blob = (desc.stdout + "\n" + events_text)
        issue = _classify(blob)
        phase, restarts = pod_meta.get(p, ("?", "?"))
        ranked.append(PodIssue(pod=p, phase=phase, restarts=restarts, issue=issue))
        table.add_row(p, phase, restarts, issue, _suggest(issue))

    c.print(table)

    first = ranked[0].pod

    lg_prev = logs(namespace, first, tail=120, previous=True)
    prev_text = (lg_prev.stdout or "").strip()
    if lg_prev.returncode == 0 and prev_text and "unable to retrieve container logs" not in prev_text:
        c.print(Panel(prev_text, title=f"Logs (previous): {first}"))

    lg_cur = logs(namespace, first, tail=120, previous=False)
    if lg_cur.returncode == 0 and lg_cur.stdout.strip():
        c.print(Panel(lg_cur.stdout.strip(), title=f"Logs (current): {first}"))

    c.print(
        Panel(
            "\n".join(
                [
                    f"kubectl -n {namespace} describe pod {first}",
                    f"kubectl -n {namespace} logs {first} --previous --tail=200",
                    f"kubectl -n {namespace} get events --sort-by=.lastTimestamp | tail -n 30",
                ]
            ),
            title="Dry-run commands (recommended)",
            subtitle="No changes executed",
        )
    )


if __name__ == "__main__":
    typer.run(main)
