from __future__ import annotations
from typing import Any, Dict, List, Tuple

from rich.console import Console
from rich.panel import Panel
from llm_agent.agent.tools.kubectl import k
from llm_agent.agent.policy import evaluate, is_write

c = Console()


def run_step(step: Dict[str, Any], approve: bool) -> Tuple[bool, str]:
    ns = step.get("namespace")
    cmd = step.get("cmd") or []
    decision = evaluate(step)

    if not decision.allowed:
        return False, f"Policy denied: {decision.reason}"

    if is_write(cmd) and not approve:
        return False, "Refusing to execute write action without --approve"

    res = k(*cmd, namespace=ns)
    out = (res.stdout + "\n" + res.stderr).strip()
    ok = (res.returncode == 0)
    return ok, out or "(no output)"


def execute_plan(plan: Dict[str, Any], approve: bool) -> Dict[str, Any]:
    results = []

    for step in plan.get("plan", []):
        ok, out = run_step(step, approve=approve)
        results.append({"step": step, "ok": ok, "output": out})

    fix = plan.get("recommended_fix")
    fix_result = None
    if fix:
        ok, out = run_step(fix, approve=approve)
        fix_result = {"step": fix, "ok": ok, "output": out}

    return {"steps": results, "fix": fix_result}
