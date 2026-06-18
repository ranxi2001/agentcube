---
name: llm-e2e-test
description: Run and document AgentCube LLM end-to-end validation, especially math-agent or OpenAI-compatible provider checks. Use when testing a live LLM-backed AgentCube example, validating OPENAI_API_KEY / OPENAI_API_BASE / OPENAI_MODEL settings, distinguishing LLM/provider failures from AgentCube sandbox failures, or preparing internship/PR evidence for math-agent, SDK, MCP, or OpenAI-compatible gateway tests.
---

# LLM E2E Test

Use this skill to run LLM-backed AgentCube tests without leaking credentials or confusing provider errors with sandbox errors.

## Safety Rules

- Never write real API keys to repo files, reports, command history notes, or final answers.
- Pass secrets through process environment only. Disable shell tracing with `set +x` before commands that include secrets.
- Redact `sk-...` patterns from logs before showing or saving excerpts.
- Record provider config as presence and non-secret values only: base URL, model name, wire/API mode if known, status codes, and error class.
- Do not commit `.env` files or generated test logs that may include headers.

## Required Inputs

Collect these before running:

```text
OPENAI_API_KEY=<secret, do not print>
OPENAI_API_BASE=<OpenAI-compatible base URL>
OPENAI_MODEL=<model name>
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080
ROUTER_URL=http://127.0.0.1:18081
API_TOKEN=<AgentCube bearer token, if auth is enabled>
```

For OpenAI-compatible gateways, test both of these if the first one fails:

```text
https://host.example
https://host.example/v1
```

LangChain/OpenAI chat-completions clients usually expect a `/v1` API root. A missing `/v1` can surface as malformed response parsing, for example `'str' object has no attribute 'model_dump'`.

## Environment Setup

From the AgentCube repo root, prefer an isolated Python 3.11+ venv:

```bash
/root/.local/bin/python3.11 -m venv /tmp/agentcube-llm-e2e-venv
/tmp/agentcube-llm-e2e-venv/bin/python -m pip install --upgrade pip setuptools wheel
/tmp/agentcube-llm-e2e-venv/bin/python -m pip install -e ./sdk-python -e ./integrations/code-interpreter-mcp -e ./integrations/langchain-agentcube
/tmp/agentcube-llm-e2e-venv/bin/python -m pip install -r cmd/cli/examples/math-agent/requirements.txt
```

If the system `python3` is too old, look for `/root/.local/bin/python3.11` or `uv`.

## Three-Layer Validation

Run these layers in order.

1. AgentCube sandbox backend:

```bash
TOKEN=$(KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl create token e2e-test -n agentcube --duration=24h)
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
API_TOKEN="$TOKEN" \
/tmp/agentcube-llm-e2e-venv/bin/python - <<'PY'
from agentcube import CodeInterpreterClient
with CodeInterpreterClient(
    name="e2e-code-interpreter",
    namespace="agentcube-day16",
    workload_manager_url="http://127.0.0.1:18080",
    router_url="http://127.0.0.1:18081",
    auth_token=__import__("os").environ.get("API_TOKEN"),
) as client:
    print(client.run_code("python", "print(6*7)").strip())
PY
```

Expected output: `42`.

2. math-agent tool layer:

Important: `cmd/cli/examples/math-agent/main.py` currently calls `CodeInterpreterClient()` without arguments. The SDK default target is `default/my-interpreter`; `CODE_INTERPRETER_NAME` and `CODE_INTERPRETER_NAMESPACE` environment variables do not change that default unless the example code is modified. Before running the tool layer unchanged, ensure this CR exists:

```bash
kubectl get codeinterpreter my-interpreter -n default
```

If the intended target is different, either create a temporary `default/my-interpreter` fixture in the test cluster or patch the example code in a local-only validation branch. A 404 response like `{"message":"code interpreter not found"}` from `POST /v1/code-interpreter` is an example wiring/precondition problem, not evidence that AgentCube sandbox creation is broken.

```bash
set +x
TOKEN=$(KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl create token e2e-test -n agentcube --duration=24h)
cd cmd/cli/examples/math-agent
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
API_TOKEN="$TOKEN" \
/tmp/agentcube-llm-e2e-venv/bin/python - <<'PY'
from main import run_python_code
print(run_python_code.invoke({"code": "print(6*7)"}).strip())
PY
```

Expected output: `42`. If this passes but the full agent fails, the problem is likely LLM/provider/framework side, not AgentCube sandbox creation.

3. full math-agent HTTP query:

```bash
set +x
TOKEN=$(KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl create token e2e-test -n agentcube --duration=24h)
cd cmd/cli/examples/math-agent
OPENAI_API_KEY="$OPENAI_API_KEY" \
OPENAI_API_BASE="$OPENAI_API_BASE" \
OPENAI_MODEL="$OPENAI_MODEL" \
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
API_TOKEN="$TOKEN" \
PORT=18082 \
/tmp/agentcube-llm-e2e-venv/bin/python main.py >/tmp/agentcube-math-agent.log 2>&1 &
echo $! >/tmp/agentcube-math-agent.pid

curl -sS http://127.0.0.1:18082/health
curl --max-time 180 -sS -o /tmp/agentcube-math-agent-response.json -w '%{http_code}\n' \
  -X POST http://127.0.0.1:18082/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"Use the run_python_code tool to calculate 6*7. Return only the final number.","thread_id":"llm-e2e"}'
cat /tmp/agentcube-math-agent-response.json
sed -E 's/sk-[A-Za-z0-9_-]+/<redacted>/g' /tmp/agentcube-math-agent.log | tail -120
kill "$(cat /tmp/agentcube-math-agent.pid)" 2>/dev/null || true
```

Expected response:

```json
{
  "response": "42",
  "thread_id": "llm-e2e",
  "agent": "math-agent"
}
```

If `OPENAI_API_BASE=https://host` fails with a LangChain/OpenAI parsing error, retry `OPENAI_API_BASE=https://host/v1` before changing AgentCube code.

## Result Classification

Use this table when writing reports or PR notes.

| Result | Meaning |
| --- | --- |
| SDK / direct CodeInterpreter fails | AgentCube control plane, router, auth, sandbox, or picod path may be broken. Inspect WorkloadManager, Router, Pod logs. |
| SDK passes but math-agent tool layer fails | Example wiring or `CodeInterpreterClient()` defaults may be wrong. Check name/namespace/env support and session cleanup. |
| Tool layer passes but full HTTP query fails | LLM provider, model, base URL, wire API, or LangChain/OpenAI compatibility issue. |
| Full HTTP query returns `42` | End-to-end path works: LLM agent -> tool call -> AgentCube CodeInterpreter -> sandbox execution -> final answer. |

## Report Template

Use concise evidence in internship reports:

```md
### LLM / math-agent E2E

- Python runtime:
- Venv:
- Provider base URL:
- Model:
- Secret handling:
- AgentCube URLs:
- CodeInterpreter target:
- Commands:
- Results:
  - SDK direct:
  - math-agent tool layer:
  - math-agent HTTP health:
  - math-agent full query:
- Failures / fixes:
- Cleanup:
```

Do not include API keys, bearer tokens, request headers, or full raw logs.
