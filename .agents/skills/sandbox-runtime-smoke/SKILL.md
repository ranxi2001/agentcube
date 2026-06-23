---
name: sandbox-runtime-smoke
description: Use when running or documenting external sandbox runtime smoke tests for OpenSandbox, Agent Substrate, or similar sandbox/actor platforms; covers host environment capture, log layout, image pre-pull, OpenSandbox Docker CLI/Python SDK validation, Agent Substrate kind quickstart triage, cleanup, and report updates.
---

# Sandbox Runtime Smoke

Use this skill for external sandbox runtime validation, especially when comparing AgentCube with OpenSandbox or Agent Substrate.

## Ground Rules

- Record raw logs under `internship-reports/benchmarks/<date-or-task>/`.
- Separate local measured data, upstream docs, and engineering inference.
- Capture host environment before starting services: date, kernel, Docker, kubectl, kind, Go, Python, CPU, memory, cgroup, and relevant ports.
- Do not leave dev servers, port-forward sessions, kind clusters, registries, or sandbox containers running.
- If a heavy environment fails at the infrastructure layer, record the exact failing phase and stop instead of repeatedly retrying the full stack.

## OpenSandbox Docker Smoke

Preferred order:

1. Generate config with `uvx opensandbox-server init-config <config> --example docker --force`.
2. Pre-pull images before the timed smoke:
   - `docker pull opensandbox/execd:v1.0.19`
   - `docker pull python:3.12`
3. Start server with:
   ```bash
   OPENSANDBOX_INSECURE_SERVER=YES SANDBOX_CONFIG_PATH=<config> uvx opensandbox-server
   ```
4. Set CLI connection:
   ```bash
   export OPEN_SANDBOX_DOMAIN=localhost:8080
   export OPEN_SANDBOX_PROTOCOL=http
   ```
5. Validate CLI path:
   - `curl -fsS http://127.0.0.1:8080/health`
   - `uvx --from opensandbox-cli osb sandbox create --image python:3.12 --timeout 10m -o json`
   - `osb sandbox get`, `osb sandbox health`
   - `osb command run <id> -o raw -- python -c "print(1 + 1)"`
   - `osb file write <id> /workspace/agentcube-smoke.txt -c "hello opensandbox" -o json`
   - `osb file cat <id> /workspace/agentcube-smoke.txt -o raw`
   - `osb sandbox kill <id> -o json`
6. Validate Python SDK path with `uv run --python 3.12 --with opensandbox`.

Notes:

- First create may synchronously pull the sandbox image and exceed CLI/SDK default timeout. If `/health` also stalls during pull, record it as server responsiveness evidence and pre-pull before rerunning.
- `osb -o json` may print pretty JSON; parse the whole JSON object, not one line.
- Current Python SDK command output is under `execution.logs.stdout[*].text`, not `result.stdout`.

## Agent Substrate Kind Smoke

Preferred order:

1. Run from the Agent Substrate repository root.
2. Ensure Go is on `PATH`; if only Go toolchain cache exists, prepend the exact `.../bin` path for the current shell and record it.
3. Check `hack/kind.sh version` before creating a cluster.
4. Run:
   ```bash
   hack/create-kind-cluster.sh
   hack/install-ate-kind.sh --deploy-ate-system
   hack/install-ate-kind.sh --deploy-demo-counter
   go install ./cmd/kubectl-ate
   kubectl ate create actor my-counter-1 --template ate-demo-counter/counter
   kubectl port-forward -n ate-system svc/atenet-router 8000:80
   ```
5. In a separate shell, curl the router with Host `my-counter-1.actors.resources.substrate.ate.dev`, then check `kubectl ate get actor`, suspend, curl again, and verify counter state continues.

Failure handling:

- If kind/kubeadm fails before Agent Substrate install, classify it as environment/bootstrap failure, not Agent Substrate behavior failure.
- cgroup v1 warnings, kubeadm wait-control-plane timeouts, or API server bootstrap timeouts should be recorded with the exact log excerpt.
- Cleanup with `hack/delete-kind-cluster.sh`; verify `kind get clusters`, Docker containers, and registry port 5001 are clean.

## Report Update Checklist

- Add or update the day report with commands, observed output, root cause, workaround, and final state.
- Link raw log directory.
- State what passed, what failed, and what was not reached.
- Update root `PROGRESS.md` with only short next-run state.
