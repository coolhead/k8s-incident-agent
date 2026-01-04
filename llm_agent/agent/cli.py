from __future__ import annotations
import typer
from rich.console import Console
from rich.panel import Panel

from llm_agent.agent.triage import collect
from llm_agent.agent.planner_llm import plan
from llm_agent.agent.executor import execute_plan
from llm_agent.agent.audit import write
from llm_agent.agent.verify import verify

app = typer.Typer(add_completion=False)
c = Console()


@app.command()
def run(
    namespace: str = typer.Option("demo", "--namespace", "-n"),
    approve: bool = typer.Option(False, "--approve"),
    max_pods: int = typer.Option(5, "--max-pods"),
):
    """LLM-planned incident agent: triage -> plan -> (optional) execute -> audit -> verify."""
    incident = collect(namespace=namespace, max_pods=max_pods)
    c.print(Panel(f"kubectl context: {incident['context']}", title="Context"))

    p = plan(incident)
    c.print(Panel(p.get("summary", "(no summary)"), title="LLM Summary"))
    c.print(Panel(p.get("diagnosis", "(no diagnosis)"), title="LLM Diagnosis"))

    results = execute_plan(p, approve=approve)
    audit_path = write({"incident": incident, "plan": p, "results": results, "approved": approve})

    c.print(Panel(audit_path, title="Audit record"))
    c.print(Panel(verify(namespace), title="Verify pods"))


if __name__ == "__main__":
    app()
