# PROGRESS.md

这个文件只保存下一轮 Agent 需要的短记忆，不做日报。详细过程、证据和长分析放在 `internship-reports/` 与 `internship-reports/todo.md`。

## Goal

当前主线：参与 AgentCube upstream 社区，围绕 agent-sandbox compatibility、SandboxPool / slow resource control plane、Sleep/Resume、observability、SDK lifecycle、benchmark 和开源 review 找可验证、低重复的贡献点。

## Current State

- Branch/workflow：当前本地在 `intern`，该分支是本地记录专用分支，只跟踪 `.agents/`、`internship-reports/`、`PROGRESS.md`、`AGENTS.md`、`README-ZH.md`；不要在 `intern` 跟踪 AgentCube 源码、charts、client-go、workflow 或 `internship-reports/` 外的 benchmark/source 工具。代码工作切到 `main` 或 clean topic branch from `upstream/main`。记录类 commit 完成后默认 push `origin intern:intern`。
- Intern branch cleanup：用户要求精简 `intern` 后，已在 `bceff94 chore: prune intern branch to local records [skip ci]` 删除上游源码/CI/SDK/docs 等 tracked 文件并保留 `.agents/`；该 commit 已 push 到 `origin/intern`。`.agents/.gitignore` 会忽略 `.agents/.env`、`__pycache__` 和 `*.pyc`。
- Community freshness scan：最近一次增量复核到 `2026-07-30 17:42 CST`。自 17:36 起只有 #446 因我们的 immutability review 更新；head 仍为 `2eefda6`，没有新作者补丁。复盘确认 #438 明确要求 tested v0.4.6 migration lifecycle；exact head 的 `go test ./cmd/workload-manager -count=1` 稳定失败 5 个 scheme assertions，而 green coverage 只跑 `./pkg/...`。
- Final-head review harness：已新增 `agentcube-pr-review/scripts/final_head_review.py`。对 #446 `2eefda6` 的 forward test 能追踪 workflow -> Makefile -> shell test scope，只运行 CI 未覆盖的 `./cmd/workload-manager`，并命中 5 个 assertion failures、dead migration URL、lexicographic semver、removed validation 和 personal PATH；skill 14 个单测及结构校验通过。
- Upstream comments rule：任何 upstream issue/PR/comment/review request/maintainer mention 都必须先让用户确认 exact target/body；不要自动 `/assign`、`/lgtm`、request review 或 mention maintainer。

## Active Upstream Threads

- #447 / #448 Code Interpreter MCP SDK v2：maintainer 选择 latest v2 SDK 后，upstream PR [#448](https://github.com/volcano-sh/agentcube/pull/448) exact head `1286b3a` 已于 `2026-07-30 09:53 CST` 通过 merge commit `0704bb9` 合入 `main`，关联 bug #447 已关闭。合入前 fork 9/9 与 upstream 13/13 checks 全绿，覆盖 local Streamable HTTP、stdio、Docker rollout 与 in-cluster MCP E2E；该前置不再是 #429/#446 的 blocker。
- #446 `Upgrade agent sandbox v0.5.3`：open、non-draft、current head `2eefda6`，单个 signed commit、33 files、`MERGEABLE` / `UNSTABLE`。11 项实际 checks 与 DCO 全绿，但 current review 已有 7 个 active threads。我们此前的 production scheme finding [inline 3671892415](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3671892415) 已 code-addressed；本轮用户确认后发布 [immutability test validity inline 3681625786](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3681625786)。`@acsoto` 已覆盖 codegen personal PATH，并指出 mandatory migration E2E/asset、错误 GVK、empty-name validation 和 semver comparison；不重复评论，等待作者修复后按新 head 复核。
- Fork-only v0.5.3 adapter：`compat/agent-sandbox-v053-independent@5957314` 基于 `upstream/main@0704bb9`，保留已验证的 v0.5.2 beta adapter，仅用 5-file increment 升到 v0.5.3，并新增真实 API Server 的 `volumeClaimTemplates` immutability E2E。local lint/gen-check/build/non-E2E all-Go/workloadmanager race 与隔离 k3d v1.32.5 + official v0.5.3 manifest focused E2E 通过；fork push checks 9/9 success。分支只用于实现/review 证据，不创建竞争 upstream PR。
- #438 `Upgrade agent-sandbox to v0.5.2 or a later stable release`：open，assignee `safiya2610`；已有 replacement PR #446。不要重复认领或开替代 PR。
- #444 `Implement mTLS between Router and PicoD`：open、无 assignee/PR；我们已发布设计评论，要求先明确 key isolation、identity granularity、JWT/TLS authorization boundary、global/per-workload mode。无新回复；等待作者/maintainer，不追评、不认领、不写实现。
- #435 / #434 CLI cloud build：#434 open；#435 open、head `e45837c`、4 files `+537/-48`，没有新 push，维护者 @acsoto 于 `2026-07-30 10:04 CST` 评论 `e2e breaks`。此前 DCO/Codegen/lint/build 通过但 E2E 与 codeinterpreter-e2e 失败；run `30387869568` 的 `mcp.server.fastmcp` failure 来自 #448 已修复的 shared drift，但仍需作者 rebase 后用 exact-head checks 验证，不能直接断言全部 E2E failure 已解决。不要把 #434 当未认领任务；如参与，只做源码验证型 review，并先让用户确认 exact comment。
- #431 SandboxPool proposal：open、head `49576e8`，自 2026-07-15 无更新；checks 通过，Tide pending needs `approved`/`lgtm`。此前 5 个 current active / 6 个 outdated thread 结论保留在 Day44；新 push 后再复核 Lease namespace/RBAC、required `ResourceList` serialization、RuntimeClass bootstrap、generation freshness、name/label/path budget 和 real node shim contract。
- #429 Go toolchain update workflow：open、remote head `cf4024b` 直接基于旧 `upstream/main@87e6e37`；local validation 全过，exact-head Actions run `30431293490` 为 10 success / 2 shared MCP failure。#448 已合入并解除该 shared blocker；下一步是先在 fork-only validation branch rebase `upstream/main@0704bb9`、重跑 exact-head checks，再让用户确认是否更新 open PR branch，不直接催 reviewer。
- #413 Sandbox Pod lookup：open、head `65d38f5`、merge state dirty；maintainer 明确拒绝依赖即将被 upstream 移除的 pod-name annotation，建议按 Sandbox name 直接查 Pod。fork `cleanup/remove-sandbox-pod-fallback@eefce59` 与该方向一致，但 #413 仍有 active author/PR；不提交竞争 PR，先等作者响应或只做 review/test evidence。
- #400 PicoD Prometheus metrics：open、head `b8c4ed5`、assignee `acsoto`、label `lgtm`；checks 通过，Tide pending only needs `approved` label。我们的 review 已公开完成，不重复 `/lgtm` 或追评。
- #437 AgentRuntime/PCAP examples：open、head `37792e4`；作者已修复我们指出的 SIGTERM/PID 1 cleanup 问题，current review threads 为 0，checks 通过。不要追评；除非新 push 或用户要求再审。
- #385 WarmPoolAvailable：open、assignee `RainbowMango`、merge state dirty；旧 head `d885b4e` 不再适合直接推进。已知可移植语义在本地 `fix/pr385-v052-validation@bc89af4`，但该 branch 混有 v0.5.2 validation 前置，不能直接推 upstream；等 agent-sandbox v0.5.x baseline 明确后再拆 feature commit、range-diff、重跑 E2E，并让用户确认。
- Pod informer cleanup：fork branch `cleanup/remove-sandbox-pod-fallback@eefce59` 仍只在 fork；若要开 upstream PR，先让用户确认 exact title/body、6-file diff、unit/race/repeat/lint/qualified-Helm evidence。

## Durable Constraints

- Bash only. Do not run PowerShell snippets or `.ps1` in this workspace.
- Fork `main` 必须是 clean mirror of `upstream/main`；不要把实习报告、本地 benchmark、中文记录、task tracking 或 intern-only `.agents/` skills 放进 `main`。
- Official upstream PR branch：从最新 `upstream/main` 新建 clean topic branch，小 scope、DCO signoff、无 internship/local artifacts。
- Intern-only record commit subject 加 `[skip ci]`，commit 后默认 `git push origin intern:intern`；rebase 或 mirror reset 后使用 `--force-with-lease`，不要 plain `--force`。
- Before upstream-facing text, follow `internship-reports/open-source-contribution-format-standard.md`；upstream text 用英文，中文分析留在 reports。提交前跑对应 concise-first gate，并报告 visible words / nonblank lines。
- Issue/PR context 优先用 `.agents/skills/agentcube-issue-discussion/scripts/thread_brief.py <number>`；PR branch/body/checks 用 `.agents/skills/agentcube-pr-management/` 的脚本或 `gh pr checks`。

## Current Blockers / Environment Limits

- Current machine has `/dev/kvm` and exposes VT-x under Microsoft virtualization, but user `ranxi` is not in the `kvm` group and cannot read/write the device. Do not claim real MicroVM / KVM / forkd / CubeSandbox virtualization validation until device access and runtime stack are available.
- Standard kind Kubernetes has failed on this host at kubelet/cgroup/QoS initialization. Use existing k3s or record KWOK/kind limitations clearly; do not describe kind environment failure as AgentCube code failure.
- Full `go test ./...` can fail in `test/e2e` when Router/WorkloadManager/kubeconfig are not running. For ordinary code changes prefer targeted packages or non-e2e all-Go tests; document exclusions.
- Go 1.26.4 下 `pkg/store/TestInitStore/return_error_when_initRedisStore_fails` 的 gomonkey patch 未生效，会落到真实 Redis 初始化并报 `missing env var REDIS_ADDR`；已在纯 `upstream/main@3de1272` 同样复现。
- OpenSandbox / Agent Substrate runtime smoke tests are not yet deployed locally; use `.agents/skills/sandbox-runtime-smoke/SKILL.md` if resuming that work.
- `2026-07-29` 本机 `kubectl` 没有 current context，并回退访问 `localhost:8080` 失败；恢复 cluster 前不安排冷启动/p99/并发 benchmark。

## Ruled Out / Do Not Repeat

- Do not treat `WarmPoolNotFound` as a stable Warning Event requirement; it may be normal controller cache timing.
- Do not simplify `agent-sandbox v0.5.0rc1` incompatibility to “pseudo-version”; the real issues were v1alpha1 package removal, `Sandbox.spec.replicas` -> `OperatingMode`, and claim `TemplateRef` -> required `WarmPoolRef`.
- Do not compare Cocoon's 33 ms pre-booted ownership claim with E2B snapshot resume, or its 50k fleet fill with 50k user `ready-to-exec`; Day56 fixed operation and environment boundaries.
- Do not call AgentCube “E2B-compatible” based only on E2B-like behavior; Day33 split compatibility into SDK, REST lifecycle, envd process/filesystem RPC, template/snapshot/network/volume.

## Next

- 每个 substantive AgentCube work loop 开始先做只读 community freshness scan；更新 scan timestamp 和 decision-relevant changes，不发布 upstream 内容。
- #447 / #448：已完成并合入，不再追踪 review；仅在发现 merged regression 时重新打开调查。
- #429：保持 `cf4024b` 两文件 scope；先在 fork-only validation branch rebase 到 `upstream/main@0704bb9` 并跑 exact-head checks，再让用户确认 open PR branch update。
- #446：immutability test validity inline 已发布；codegen 草稿因 `@acsoto` 同主题评论跳过。等待作者处理 current 7 个 active threads 和 migration root finding；新 push 后先运行 `agentcube-pr-review/scripts/final_head_review.py`，再按其 ledger 关闭 #438 acceptance、hand-written files、changed test packages、workflow coverage、external asset/semver boundary、真实 API CEL 与 migration lifecycle。不要重复 maintainer feedback，也不要把 fork adapter 直接开成竞争 PR。
- 若用户要下一项贡献：优先选择可验证 review/testing feedback；#413 cleanup 即使技术方向匹配也不要与 active PR 重复。
- 若用户要代码工作：切到 `main` 或 clean topic branch from `upstream/main`，不要在 `intern` 写 AgentCube 源码。

## Stop Conditions

- Same environment blocker fails three times in a row, such as kind kubelet/cgroup/QoS or `/dev/kvm` access denial: stop debugging, record BLOCKED, switch task or machine.
- An upstream PR/issue already has an active assignee working on the same change: do not open duplicate PR; offer review, reproduction, or test feedback instead.
- If a community comment would be speculative without source, code evidence, official docs, or local test evidence: stop and gather evidence first.
