# Day 55：PR #442 Review Drafts

日期：2026-07-27

状态：`LOCAL DRAFT / NOT POSTED`

## Approval Package

| 项目 | 内容 |
| --- | --- |
| Target | `volcano-sh/agentcube` PR #442 |
| Base branch | upstream `main` |
| Exact reviewed head | `4f9d4f3265c722b367dcf4e0430eb59aa0ff7d6e` |
| Action | upstream-facing GitHub `COMMENT` review with 4 inline comments |
| Posting state | 未发布；等待用户确认 exact text |
| Diff reviewed | 38 files，`+924/-710` |
| Why now | 作者 force-push 恢复完整 v0.5.2 adapter 并重新请求 review；没有真人 review 绑定 current head |

验证摘要：focused Go tests、WorkloadManager race、E2E compile、shell syntax、module verify、gen-check、lint、build 通过；exact-head 12 checks green；release `migrate.sh` URL 返回 404；diff check 有 6 处 whitespace；Docusaurus 本地 build 因依赖未安装而未执行。

Visualization gate：保留 prose。Migration comment 只有两个互斥配置分支，readiness comment 只有一条线性启动顺序；短 prose 比 Mermaid 更易扫描。

Reviewer-visible metrics：review body `116 words / 2 nonblank lines`；inline 1 `146 / 3`；inline 2 `107 / 2`；inline 3 `141 / 3`；inline 4 `89 / 2`。没有单条超过 450-word soft gate；aggregate 为 `599 words / 12 nonblank lines`，因为四个独立文件/责任边界需要分别锚定，不把它们压成一个难以定位的长 root comment。

## Review Body

<!-- DRAFT:REVIEW_BODY:START -->
Reviewed `4f9d4f3`. The production v0.5.2 adapter and fresh-install checks are back, and the exact-head checks are green. However, those jobs explicitly disable the migration block, and the current opt-in path still cannot construct or execute a v0.4.6 to v0.5.2 migration. The inline comments below cover that test path, the operator guide, a WorkloadManager readiness regression, and removed integration coverage.

I did not duplicate the existing `Resource()` compatibility thread. Although that GitHub thread is marked resolved, the current exported helper still returns `GroupResource`, so the compatibility concern remains in the artifact. I think the PR remains not ready until the upgrade path is executable and required, startup readiness is dependency-aware, and the removed E2E suites are restored.
<!-- DRAFT:REVIEW_BODY:END -->

## Inline 1: Migration Reachability And Fixture

Target: `test/e2e/run_e2e.sh:537`

<!-- DRAFT:INLINE_1:START -->
The opt-in block still cannot produce a v0.4.6 to v0.5.2 migration. With the default and CI value (`AGENT_SANDBOX_VERSION=v0.5.2`), setup installs v0.5.2 before reaching this block, so step 5 only reapplies the same release. With `AGENT_SANDBOX_VERSION=v0.4.6`, setup exits at `validate_agent_sandbox_crd_version` because it unconditionally requires v1beta1.

There is also no claim fixture yet: both `CodeInterpreter` manifests omit the required `spec.template`, and even a valid `CodeInterpreter` only makes its SandboxTemplate/WarmPool. A SandboxClaim is created after a session request, which this block never sends. The block also never invokes the official `bootstrap` or `migrate` phases.

Could this become a dedicated required migration job that starts from v0.4.6 and either uses a v1alpha1-compatible pre-upgrade WorkloadManager to create the claims or applies explicit v1alpha1 fixtures, then runs the pinned helper through bootstrap, install, webhook readiness, and migrate? It should fail CI if warm-adopted or cold/unbound claim identity, readiness, GC, or refill regresses.
<!-- DRAFT:INLINE_1:END -->

## Inline 2: Operator Guide

Target: `docs/getting-started.md:48`

<!-- DRAFT:INLINE_2:START -->
The earlier helper/readiness concern remains on the current head: this command returns 404 because the v0.5.2 release does not publish a `migrate.sh` asset. The [tagged upstream guide](https://github.com/kubernetes-sigs/agent-sandbox/blob/v0.5.2/docs/api-migration-guide.md) runs `dev/tools/migrate.sh` from a source checkout (it wraps `helm/files/migrate.sh`), backs up all four agent-sandbox kinds, and probes the conversion webhook before the post-upgrade rewrite. This guide instead omits SandboxTemplate/SandboxWarmPool from the backup and waits only for the controller Deployment.

Could this use the exact tagged guide as the authoritative procedure, retain the existing CodeInterpreter backup while adding Sandbox/SandboxClaim/SandboxTemplate/SandboxWarmPool, wait for the webhook to answer a beta list, and describe bootstrap as conditionally mandatory while the v0.5.2 storage rewrite remains optional?
<!-- DRAFT:INLINE_2:END -->

## Inline 3: WorkloadManager Readiness

Target: `pkg/workloadmanager/server.go:154`

<!-- DRAFT:INLINE_3:START -->
Starting the listener here creates a false-readiness window whenever cache sync or the Store ping outlasts the first readiness probe. `/health` always returns 200, and the chart uses that endpoint (or a TCP socket with SPIRE) for readiness, so Kubernetes can route requests before those dependencies are ready. Those requests can observe unsynced listers or an unavailable Store.

There is a second lifecycle gap after initialization: `Start` performs one non-blocking read from `startupErr` and returns nil, so a later fatal listener error is queued with no remaining consumer. The process stays alive without surfacing the error to `main`, relying on probes to trigger an eventual restart.

Could we keep early liveness but expose a separate readiness signal gated by cache sync plus Store availability, prevent business traffic until that state is true, and supervise the listener error for the process lifetime?
<!-- DRAFT:INLINE_3:END -->

## Inline 4: Removed Integration Coverage

Target: `test/e2e/run_e2e.sh:534`

<!-- DRAFT:INLINE_4:START -->
This replacement removes the conditional OIDC block, the unconditional LangChain and local MCP HTTP/stdio runs, and the in-cluster MCP run used when setup is enabled. Their test files, dependencies, README contract, and some cleanup variables remain, but `run_e2e.sh` no longer invokes them. The green E2E jobs therefore provide materially less regression coverage for behavior unrelated to this dependency upgrade.

Could equivalent invocations be restored and the migration scenario moved to its own script/job, so adding upgrade coverage does not trade away the integration coverage previously exercised by `make e2e`?
<!-- DRAFT:INLINE_4:END -->

## Posting Guard

Do not submit this review, create inline threads, resolve existing threads, mention maintainers, or issue Prow commands until the user confirms the exact target, `COMMENT` event, review body, and four inline bodies above.
