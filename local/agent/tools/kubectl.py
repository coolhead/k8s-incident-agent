from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CmdResult:
    cmd: List[str]
    returncode: int
    stdout: str
    stderr: str


def run(cmd: List[str], timeout_s: int = 25) -> CmdResult:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    return CmdResult(cmd=cmd, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)


def k(*args: str, namespace: Optional[str] = None) -> CmdResult:
    cmd = ["kubectl"]
    if namespace:
        cmd += ["-n", namespace]
    cmd += list(args)
    return run(cmd)


def current_context() -> CmdResult:
    return k("config", "current-context")


def get_pods(namespace: str) -> CmdResult:
    return k("get", "pods", "-o", "wide", namespace=namespace)


def get_pods_json(namespace: str) -> CmdResult:
    return k("get", "pods", "-o", "json", namespace=namespace)


def get_events(namespace: str) -> CmdResult:
    return k("get", "events", "--sort-by=.lastTimestamp", namespace=namespace)


def describe_pod(namespace: str, pod: str) -> CmdResult:
    return k("describe", "pod", pod, namespace=namespace)


def logs(
    namespace: str,
    pod: str,
    container: Optional[str] = None,
    tail: int = 120,
    previous: bool = False,
) -> CmdResult:
    args = ["logs", pod, f"--tail={tail}"]
    if previous:
        args.append("--previous")
    if container:
        args += ["-c", container]
    return k(*args, namespace=namespace)
