# Example Incident: CrashLoopBackOff (Guarded Remediation)

## Scenario
A demo Deployment enters `CrashLoopBackOff` due to an intentionally failing container command.

## Detection (read-only)
The agent collects evidence from Kubernetes signals:
- container wait reason (`CrashLoopBackOff`)
- restart counts
- last termination exit codes
- recent events and logs

## Plan (dry-run)
A remediation plan is proposed but not executed without explicit approval.

## Approval (human-in-the-loop)
State-changing operations require explicit approval (`--approve`).

## Execution
The deployment command is patched to a stable configuration using a scoped, allowlisted action.

## Verification
The agent re-runs triage and confirms the pod is healthy and stable.

## Audit
See `example-incident-run.json` for the immutable record of the approved action.
