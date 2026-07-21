# Day 53: PR #437 AgentRuntime examples review

## 1. 结论

PR [#437](https://github.com/volcano-sh/agentcube/pull/437) 值得 review。它修复 AgentRuntime SDK 示例、补一个可运行 echo server，并纠正 PCAP analyzer 的 Router Service 地址；当前仍 open，而且没有真人技术 review。

本轮对 exact head `c18707fd468b26b0d94594657cc0c33ccfacd4e9` 做了完整只读审查。结论是：

- 已证明 1 个非重复 P2 finding：嵌入 Python server 作为容器 PID 1 时没有处理 SIGTERM，正常 Pod 删除会耗完整 termination grace 后被 SIGKILL；
- SDK session reuse、README 工作目录、PCAP Service DNS 和 bootstrap 404 兼容逻辑均核验成立；
- 两个仍有语义的旧问题已经被 AI reviewer 提过，不能再复制成新 inline；
- 可以准备 1 条聚焦 SIGTERM lifecycle 的 human inline，发布前仍需用户确认 exact text。

当前没有执行任何 upstream review、comment、resolve 或 mention。

## 2. Exact review surface

| Item | Value |
| --- | --- |
| Base at authoring time | `eee8aea40c3b6b6697b7dd06510d2ff525a23362` |
| Current upstream main | `58422c02b673daf1cb7991f22e4e1476e97ea1f3` |
| Exact head | `c18707fd468b26b0d94594657cc0c33ccfacd4e9` |
| Ahead / behind current main | 1 ahead / 7 behind |
| Commits | 1 signed-off commit, no merge commit |
| Diff | 4 files, `+121/-23` |
| Merge state | `mergeable=true`; `git merge-tree --write-tree` clean |
| Labels | `kind/bug`, `kind/documentation`, `size/L` |
| CI | 10 workflow checks plus DCO success; Tide pending for `lgtm` / `approved` |

Changed files:

1. `example/agent-runtime/agent-runtime.yaml`
2. `example/pcap-analyzer/deployment.yaml`
3. `sdk-python/examples/README.md`
4. `sdk-python/examples/agent_runtime_usage.py`

The seven upstream commits after the PR base do not touch these four files. The branch should still be rebased before merge so new CI runs on the current baseline, but base age is not a correctness finding here.

## 3. Review landscape and duplicate audit

PR #437 currently has 11 inline threads. All came from Gemini or Copilot; there is no human review. All 11 are marked resolved, 10 are outdated after the author's force-push, and one current thread concerns bootstrap `GET /` returning 404.

> 注释：`resolved` 是 GitHub workflow metadata，不证明 current artifact 已修复。这里逐条检查了 current head，而不是按按钮状态推断。

Existing signals that remain visible in current code:

| Existing thread | Current artifact | Decision |
| --- | --- | --- |
| Use context managers around both clients | Manual `.close()` still follows each successful `invoke()` | Semantically valid, but already reported; do not duplicate |
| Bound `Content-Length` before reading | Embedded server still has no body limit | Semantically valid, but already reported; do not duplicate |
| Bootstrap `GET /` should return 200 | Server still returns 404 at `/` | False positive for this SDK contract; do not repeat |

The bootstrap 404 is intentional. `AgentRuntimeDataPlaneClient.bootstrap_session_id()` reads `x-agentcube-session-id` before checking status and returns the ID even for non-2xx responses. `sdk-python/tests/test_agent_runtime.py:114-131` locks that behavior, and local mock-Router execution confirmed it.

## 4. Finding

### P2: PID 1 does not exit on SIGTERM

Anchor: `example/agent-runtime/agent-runtime.yaml:81`.

The manifest starts `python3 -c`, so Python is PID 1 inside the container. The embedded program calls `ThreadingHTTPServer(...).serve_forever()` but installs no SIGTERM termination path. The Pod also leaves `terminationGracePeriodSeconds` unset.

Production reachability:

1. The example configures `sessionTimeout: 15m` and `maxSessionDuration: 8h`.
2. Session expiry or explicit resource deletion eventually deletes the Sandbox-owned Pod.
3. Kubelet asks the container process to terminate with SIGTERM.
4. In this PID-1 configuration the process stays alive, so Kubelet waits the default 30-second grace period and then sends SIGKILL.

This is not an inferred signal-only concern. Two independent Docker checks reproduced the lifecycle:

The locally resolved `python:3.11-slim` image was `python@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93`; recording the digest avoids treating a mutable tag as permanently identical evidence.

| Variant | Stop command | Elapsed | Container result |
| --- | --- | --- | --- |
| PR behavior on the recorded image digest | `docker stop -t 2` | about 2.3s | exit 137, `OOMKilled=false` |
| Independent minimal `ThreadingHTTPServer(...).serve_forever()` | `docker stop -t 2` | 2.21s | exit 137, `OOMKilled=false` |
| Counterfactual with explicit SIGTERM exit handler | `docker stop -t 2` | 0.20s | exit 0, `OOMKilled=false` |

> 分析：Docker 的 two-second timeout only shortens the reproduction. Kubernetes uses the Pod grace period; because this manifest does not override it, the normal default is 30 seconds. The concrete consequence is delayed Pod/process cleanup and delayed resource release, not that the session-delete HTTP response necessarily blocks for 30 seconds.

Smallest correction direction: add a SIGTERM path that makes the server process exit cleanly, then add a smoke check that sends TERM and asserts prompt exit. Avoid calling `HTTPServer.shutdown()` directly from the same serve thread if that implementation can deadlock; the contract needed by the review is clean process termination, not a prescribed helper.

## 5. Verified non-findings

### SDK and README

- README now consistently says all commands run from repository root.
- `pip install ./sdk-python`, manifest apply/delete, port-forward, and script paths are mutually consistent.
- `ROUTER_URL` is consumed by `AgentRuntimeClient` when no explicit URL is passed.
- Script defaults `simple-agentruntime/default` match the manifest.
- `AgentRuntimeClient.close()` closes only local HTTP resources; it does not delete the remote session, so the reuse explanation is correct.
- Remote timeout wording matches the manifest's 15-minute idle timeout and 8-hour maximum duration.

A local fake Router run observed exactly:

```text
GET  /v1/namespaces/default/agent-runtimes/simple-agentruntime/invocations/
POST /v1/namespaces/default/agent-runtimes/simple-agentruntime/invocations/echo  session=sid-123
POST /v1/namespaces/default/agent-runtimes/simple-agentruntime/invocations/echo  session=sid-123
```

The script exited 0 and reused one session ID across both clients.

### Embedded echo server

The exact YAML parsed as one `AgentRuntime` document. Running the extracted server locally produced:

```text
GET /echo  -> 200 {"status": "healthy"}
POST /echo -> 200 {"output": "echo: hello"}
GET /      -> 404 {"error": "not found"}
```

The 404 remains compatible with session bootstrap because Router adds the session header to the proxied response and the SDK deliberately accepts it.

### PCAP deployment

`ROUTER_URL=http://agentcube-router.agentcube.svc.cluster.local:8080` matches:

- Helm Service name `agentcube-router`;
- official installation namespace `agentcube`;
- default Router service port `8080`.

The PCAP Deployment runs in `default`, so the fully qualified cross-namespace Service DNS is the correct form. No new PCAP finding was proven.

## 6. Test evidence and limitations

Exact-head GitHub checks are green for 10 workflow jobs plus DCO: build, lint, codegen, coverage, E2E, Python lint, Python SDK tests, spelling and contributor-workflow approval. Their evidence boundary matters:

- E2E does not deploy `example/pcap-analyzer/deployment.yaml` or `example/agent-runtime/agent-runtime.yaml`.
- Python SDK CI runs `sdk-python/tests/`; it does not execute `sdk-python/examples/agent_runtime_usage.py`.
- Kubernetes API dry-run proves manifest acceptance, not Router DNS reachability or SIGTERM behavior.

Local process notes:

- `python3 -m pytest sdk-python/tests/test_agent_runtime.py -q` could not run because this detached worktree's `/usr/bin/python3` lacks pytest.
- `ruff check sdk-python/examples/agent_runtime_usage.py` could not run because `ruff` is absent from PATH.
- Two initial temporary smoke commands failed because nested shell quotes mangled Python literals; corrected structured-YAML and server smoke commands then passed.
- These environment/script failures are not PR failures. Exact-head GitHub pytest/ruff checks are green, and the locally relevant runtime checks were rerun successfully.

## 7. Recommended participation

Yes, this PR is suitable for our review because it has no human technical review and the SIGTERM lifecycle point is non-duplicate, source-reachable and runtime-reproduced.

Recommended review shape:

1. one P2 inline at `example/agent-runtime/agent-runtime.yaml:81`;
2. a short COMMENT summary only if needed to state that the other three surfaces were reviewed;
3. no repeated inline for context-manager cleanup, request-body limit, working directory or bootstrap 404;
4. no `/lgtm`, approval, reviewer request or maintainer mention from us.

The finding is a linear termination path and fits in short prose; Mermaid would add more reconstruction than it removes. The user reviewed the plain-language explanation and exact English text, then explicitly approved publication. Immediately before posting, the PR was still open at `c18707fd468b26b0d94594657cc0c33ccfacd4e9`, line 81 was unchanged, and a fresh duplicate scan found no SIGTERM/PID-1 thread.

### Published inline

Published at `2026-07-21 16:25 CST` as [discussion_r3620553817](https://github.com/volcano-sh/agentcube/pull/437#discussion_r3620553817). This was one standalone inline comment on the right side of the current diff; it did not submit `/lgtm`, `REQUEST_CHANGES`, an overall review summary, a reviewer request or a maintainer mention.

Target: `example/agent-runtime/agent-runtime.yaml:81`, right side.

> The container starts `python3 -c` directly, so the embedded server runs as PID 1 and installs no SIGTERM handler. In a local reproduction using this image and command, `docker stop -t 2` waited 2.21s before exit 137 (`OOMKilled=false`); a version with a TERM exit handler stopped in 0.20s with exit 0. Since Kubernetes also terminates containers with TERM followed by KILL, and this Pod does not set `terminationGracePeriodSeconds`, session expiry or deletion can leave the container running until the default 30-second grace period ends, delaying Pod teardown and resource release. Could we add a SIGTERM exit path and a smoke test that verifies prompt, clean exit?

A fresh-context teach-back understood the exact observation, red/green evidence, Kubernetes consequence and requested change. It corrected two draft ambiguities: do not call a mutable image tag an exact configuration, and do not imply the session-delete HTTP response itself blocks for 30 seconds. No Mermaid is needed because the event chain is linear.

`draft_metrics.py`: 106 visible words, 1 nonblank line, below the 300-word soft limit. GitHub returned comment ID `3620553817` on the intended path, line, side and exact head commit.

## 8. Community freshness

The read-only freshness scan was advanced to `2026-07-21 16:05 CST`. No issue or PR was newly updated after the 14:45 scan during this review. PR #437 itself remains on its July 13 head; no competing human review or new author push appeared while the analysis ran.
