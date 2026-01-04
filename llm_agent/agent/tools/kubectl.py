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
