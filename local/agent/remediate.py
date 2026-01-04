from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict

import typer
from rich.console import Console
from rich.panel import Panel

from agent.tools.kubectl import k, get_pods

app = typer.Typer(add_completion=False)
c = Console()

RUNS_DIR = Path("runs")
RUNS_DIR.mkdir(exist_ok=True)


def _ts() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _audit(namespace: str, action: str, target: str, ok: bool, details: str):
    payload: Dict[str, object] = {
        "ts": _ts(),
        "namespace": namespace,
        "action": action,
        "target": target,
        "ok": ok,
        "details": details,
    }
    path = RUNS_DIR / f"remediate-{payload['ts']}.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


@app.command("delete-pod")
def delete_pod(
    namespace: str = typer.Option("demo", "--namespace", "-n"),
    pod: str = typer.Option(..., "--pod", "-p"),
    approve: bool = typer.Option(False, "--approve", help="Required to execute changes"),
):
    """Safe remediation: delete a single pod (K8s will recreate it)."""
    if not approve:
        c.print(Panel("[yellow]Refusing to change cluster without --approve[/yellow]", title="Dry-run"))
        c.print(f"Would run: kubectl -n {namespace} delete pod {pod}")
        return

    res = k("delete", "pod", pod, namespace=namespace)
    ok = res.returncode == 0
    details = (res.stdout + "\n" + res.stderr).strip()
    audit_path = _audit(namespace, "delete_pod", pod, ok, details)

    c.print(Panel(details or "(no output)", title=f"delete pod {pod}"))
    c.print(Panel(f"Audit: {audit_path}", title="Recorded"))

    time.sleep(2)
    pods = get_pods(namespace)
    c.print(Panel(pods.stdout.strip(), title=f"Pods in {namespace} (post-action)"))


@app.command("rollout-restart")
def rollout_restart(
    namespace: str = typer.Option("demo", "--namespace", "-n"),
    deployment: str = typer.Option(..., "--deploy", "-d"),
    approve: bool = typer.Option(False, "--approve"),
):
    """Safe-ish: rollout restart a deployment."""
    if not approve:
        c.print(Panel("[yellow]Refusing to change cluster without --approve[/yellow]", title="Dry-run"))
        c.print(f"Would run: kubectl -n {namespace} rollout restart deploy/{deployment}")
        return

    res = k("rollout", "restart", f"deploy/{deployment}", namespace=namespace)
    ok = res.returncode == 0
    details = (res.stdout + "\n" + res.stderr).strip()
    audit_path = _audit(namespace, "rollout_restart", deployment, ok, details)

    c.print(Panel(details or "(no output)", title=f"rollout restart deploy/{deployment}"))
    c.print(Panel(f"Audit: {audit_path}", title="Recorded"))

    time.sleep(2)
    pods = get_pods(namespace)
    c.print(Panel(pods.stdout.strip(), title=f"Pods in {namespace} (post-action)"))


@app.command("patch-command")
def patch_command(
    namespace: str = typer.Option("demo", "--namespace", "-n"),
    deployment: str = typer.Option(..., "--deploy", "-d"),
    approve: bool = typer.Option(False, "--approve"),
):
    """Patch deploy command to recover CrashLoop (demo-safe)."""
    if not approve:
        c.print(Panel("[yellow]Refusing to change cluster without --approve[/yellow]", title="Dry-run"))
        c.print(
            f"Would patch: deploy/{deployment} -> command=['sh','-c','echo recovered && sleep 3600']"
        )
        return

    # JSONPatch: replace /spec/template/spec/containers/0/command
    new_cmd = ["sh", "-c", "echo recovered && sleep 3600"]
    patch = [{"op": "replace", "path": "/spec/template/spec/containers/0/command", "value": new_cmd}]

    res = k("patch", f"deploy/{deployment}", "--type=json", "-p", json.dumps(patch), namespace=namespace)
    ok = res.returncode == 0
    details = (res.stdout + "\n" + res.stderr).strip()
    audit_path = _audit(namespace, "patch_command", f"deploy/{deployment}", ok, details)

    c.print(Panel(details or "(no output)", title=f"patch deploy/{deployment} command"))
    c.print(Panel(f"Audit: {audit_path}", title="Recorded"))

    # Verify rollout
    k("rollout", "status", f"deploy/{deployment}", "--timeout=60s", namespace=namespace)
    time.sleep(2)
    pods = get_pods(namespace)
    c.print(Panel(pods.stdout.strip(), title=f"Pods in {namespace} (post-action)"))


if __name__ == "__main__":
    app()
