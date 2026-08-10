# PROGRESS.md

这个文件只保存下一轮 Agent 需要的短记忆，不做日报。详细过程、证据和长分析放在 `internship-reports/` 与 `internship-reports/todo.md`。

## Goal

当前主线：参与 AgentCube upstream 社区，围绕 agent-sandbox compatibility、SandboxPool / slow resource control plane、Sleep/Resume、observability、SDK lifecycle、benchmark 和开源 review 找可验证、低重复的贡献点。

## Current State

- Branch/workflow：当前本地在 `intern`，该分支是本地记录专用分支，只跟踪 `.agents/`、`internship-reports/`、`PROGRESS.md`、`AGENTS.md`、`README-ZH.md`；不要在 `intern` 跟踪 AgentCube 源码、charts、client-go、workflow 或 `internship-reports/` 外的 benchmark/source 工具。代码工作切到 `main` 或 clean topic branch from `upstream/main`。记录类 commit 完成后默认 push `origin intern:intern`。
- Intern branch cleanup：用户要求精简 `intern` 后，已在 `bceff94 chore: prune intern branch to local records [skip ci]` 删除上游源码/CI/SDK/docs 等 tracked 文件并保留 `.agents/`；该 commit 已 push 到 `origin/intern`。`.agents/.gitignore` 会忽略 `.agents/.env`、`__pycache__` 和 `*.pyc`。
- Community freshness scan：最近一次 #446 target-local 复核到 `2026-08-10 16:30 CST`。PR 仍 open/non-draft，base `939abb5`、head `624c875`、updatedAt 仍停在 RainbowMango 最后一条 comment；7 条均为 same-head inline comments，没有作者回复或新提交。此前 `15:39 CST` 的 #450/#385/#444 扫描没有 decision-relevant 增量。
- Final-head review harness：入口 refs 先冻结为 SHA，scope closure 绑定 exact base/head/merge-base；hand-written path、boundary lead、URL 和 structural conflict 都有硬门禁。CI waiver 只接受 immutable setup、exact clean checkout、受控 GitHub-hosted runner、safe full-execution flags 与 `push/workflow_dispatch` exact-head API PASS；`pull_request` merge ref、Makefile/script/matrix/dynamic/duplicate-name、环境注入和 control flow 均 lead-only。direct fallback 从 exact-head Git blobs 物化临时 tree，忽略 ambient/ignored files；只接受显式受审 Linux/amd64 `--go-binary`，清理环境并固定 local toolchain，使用 HEAD governing `go.work` 且拒绝 tree 外本地 module path，同时识别 nested module、wildcard ignored dirs 与 build constraints。终局 52/52 focused、81/81 review skill、109/109 seven-skill tests；#446 覆盖 Rainbow 6/6 且 fail closed，#450 precision pass 保持单一 unit。
- Review harness learning：Rainbow 的 7 条评论归并为 5 个 stable topics；codegen 非必要 rewrite、MCP EOF churn、PicoD Windows test noise 三项此前已经明确发现，属于 known-item closure miss，不是 correctness discovery miss。upgrade docs placement 与 dependency prerequisite split 是 maintainer project-policy/sequencing 决定。fresh #446 forward test 重建三项 technical scope + 两项 policy questions；held-out 式 #450 pass 正确保留一个 coherent unit，0 remove/separate/unresolved。以后分别报告 correctness discovery、scope discovery、known-item closure 与 maintainer-policy calibration，不能用 raw comment 数量混算。
- Agent AutoHarness：scorer 现支持 built-in `reference-coverage` outcome grader；corrected #446 v2 trace 对 10 项 gold 的 7 个 finding events 得到 recall `70%`、strict failure，并标记自报 completeness 与 grader 冲突。整个 #438/#442/#446 lineage 已污染，只能用于 train/regression；效率 telemetry 仍缺失。
- PR timeline harness：`pr_status.py` 默认输出最新而非最早 20 条 review comments，并保留 exact base/head、`original_commit_id`、current `commit_id`、review/reply IDs、timestamp 和 URL；用 `--review-comment-limit 0` 获取全量。
- Upstream comments rule：任何 upstream issue/PR/comment/review request/maintainer mention 都必须先让用户确认 exact target/body；不要自动 `/assign`、`/lgtm`、request review 或 mention maintainer。

## Active Upstream Threads

- #450 `check CodeInterpreter child ownership`：open、non-draft、head `0b646d8`。作者已为 Template / WarmPool delete 增加 UID/resourceVersion preconditions 和 replacement regressions；本地 exact-head 六项 causal red/green、完整 `pkg/workloadmanager` 与 race tests 通过。已于 `2026-08-10` 发布 [review completion comment](https://github.com/volcano-sh/agentcube/pull/450#issuecomment-5235089386) 与 `/lgtm`；后续只等 maintainer approval / merge，不追评。
- #447 / #448 Code Interpreter MCP SDK v2：maintainer 选择 latest v2 SDK 后，upstream PR [#448](https://github.com/volcano-sh/agentcube/pull/448) exact head `1286b3a` 已于 `2026-07-30 09:53 CST` 通过 merge commit `0704bb9` 合入 `main`，关联 bug #447 已关闭。合入前 fork 9/9 与 upstream 13/13 checks 全绿，覆盖 local Streamable HTTP、stdio、Docker rollout 与 in-cluster MCP E2E；该前置不再是 #429/#446 的 blocker。
- #446 `Upgrade agent sandbox v0.5.3`：open、non-draft、head `624c875`，已 squash 为 1 commit、36 files，mergeable，core checks / DCO 全绿并有 `lgtm`。根 `OWNERS` reviewer/approver RainbowMango 对 same head 提出 7 条 comments：Getting Started 不承载 upgrade guide、codegen 只需 version line、删除 MCP EOF churn、PicoD Windows skips 无关，并先拆 Kubernetes/controller-runtime prerequisite PR。当前没有作者回复或新 commit；旧的“review 已结束，只等 merge”判断失效。不要把 docs 意见误读成删除 #438 要求的 documented/tested upgrade path。
- Fork-only v0.5.3 adapter：`compat/agent-sandbox-v053-independent@5957314` 基于 `upstream/main@0704bb9`，保留已验证的 v0.5.2 beta adapter，仅用 5-file increment 升到 v0.5.3，并新增真实 API Server 的 `volumeClaimTemplates` immutability E2E。local lint/gen-check/build/non-E2E all-Go/workloadmanager race 与隔离 k3d v1.32.5 + official v0.5.3 manifest focused E2E 通过；fork push checks 9/9 success。分支只用于实现/review 证据，不创建竞争 upstream PR。
- #438 `Upgrade agent-sandbox to v0.5.2 or a later stable release`：open，assignee `safiya2610`；已有 replacement PR #446。不要重复认领或开替代 PR。
- #444 `Implement mTLS between Router and PicoD`：open、无 assignee/PR。作者 [reply 5231615498](https://github.com/volcano-sh/agentcube/issues/444#issuecomment-5231615498) 接受 TLS sidecar key isolation、operator-level global policy 和归入 #441 的方向；但 TLS 终止后应由 sidecar 校验 Router、agent-sandbox creator 不是不可伪造 attestation boundary、shared PicoD identity / JWT target binding 仍未定义。#352 仍 open / dirty，不能代替合同；已发布 [175-word follow-up](https://github.com/volcano-sh/agentcube/issues/444#issuecomment-5235190227)，等待正文更新或 maintainer 决策。
- #435 / #434 CLI cloud build：#434 open；#435 open、head `e45837c`、4 files `+537/-48`，没有新 push，维护者 @acsoto 于 `2026-07-30 10:04 CST` 评论 `e2e breaks`。此前 DCO/Codegen/lint/build 通过但 E2E 与 codeinterpreter-e2e 失败；run `30387869568` 的 `mcp.server.fastmcp` failure 来自 #448 已修复的 shared drift，但仍需作者 rebase 后用 exact-head checks 验证，不能直接断言全部 E2E failure 已解决。不要把 #434 当未认领任务；如参与，只做源码验证型 review，并先让用户确认 exact comment。
- #431 SandboxPool proposal：open、head `49576e8`，自 2026-07-15 无更新；checks 通过，Tide pending needs `approved`/`lgtm`。此前 5 个 current active / 6 个 outdated thread 结论保留在 Day44；新 push 后再复核 Lease namespace/RBAC、required `ResourceList` serialization、RuntimeClass bootstrap、generation freshness、name/label/path budget 和 real node shim contract。
- #429 Go toolchain update workflow：open、remote head `cf4024b` 直接基于旧 `upstream/main@87e6e37`；local validation 全过，exact-head Actions run `30431293490` 为 10 success / 2 shared MCP failure。#448 已合入并解除该 shared blocker；下一步是先在 fork-only validation branch rebase `upstream/main@0704bb9`、重跑 exact-head checks，再让用户确认是否更新 open PR branch，不直接催 reviewer。
- #413 Sandbox Pod lookup：open、head `65d38f5`、merge state dirty；maintainer 明确拒绝依赖即将被 upstream 移除的 pod-name annotation，建议按 Sandbox name 直接查 Pod。fork `cleanup/remove-sandbox-pod-fallback@eefce59` 与该方向一致，但 #413 仍有 active author/PR；不提交竞争 PR，先等作者响应或只做 review/test evidence。
- #400 PicoD Prometheus metrics：open、head `b8c4ed5`、assignee `acsoto`、label `lgtm`；checks 通过，Tide pending only needs `approved` label。我们的 review 已公开完成，不重复 `/lgtm` 或追评。
- #437 AgentRuntime/PCAP examples：open、head `37792e4`；作者已修复我们指出的 SIGTERM/PID 1 cleanup 问题，current review threads 为 0，checks 通过。不要追评；除非新 push 或用户要求再审。
- #385 WarmPoolAvailable：已按用户确认把公开 head 从 `d885b4e` force-with-lease 更新为 `7361e021`，PR body 已同步为 v0.5.3 最终行为与验证合同。当前 `MERGEABLE/UNSTABLE`；整体 6 commits、37 files、`+2655/-510`，其中 signed feature commit 仍只改 6 files。exact-head upstream 非 Tide checks `13/13 success`，fork push workflows `9/9 success` / jobs `10/10 success`，普通与 CodeInterpreter E2E 均通过；Tide 只等待 `approved`、`lgtm`。
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
- 本轮曾创建隔离 k3d v1.32.5 集群完成 #446 v0.4.6 -> v0.5.3 focused migration，验证结束后已删除 cluster/network/volume/kubeconfig；当前仍无 active Kubernetes context。standard kind 的 kubelet/cgroup stop condition 未解除，冷启动/p99/并发 benchmark 仍需另行准备环境。

## Ruled Out / Do Not Repeat

- Do not treat `WarmPoolNotFound` as a stable Warning Event requirement; it may be normal controller cache timing.
- Do not simplify `agent-sandbox v0.5.0rc1` incompatibility to “pseudo-version”; the real issues were v1alpha1 package removal, `Sandbox.spec.replicas` -> `OperatingMode`, and claim `TemplateRef` -> required `WarmPoolRef`.
- Do not compare Cocoon's 33 ms pre-booted ownership claim with E2B snapshot resume, or its 50k fleet fill with 50k user `ready-to-exec`; Day56 fixed operation and environment boundaries.
- Do not call AgentCube “E2B-compatible” based only on E2B-like behavior; Day33 split compatibility into SDK, REST lifecycle, envd process/filesystem RPC, template/snapshot/network/volume.

## Next

- 每个 substantive AgentCube work loop 开始先做只读 community freshness scan；更新 scan timestamp 和 decision-relevant changes，不发布 upstream 内容。
- #450：review 已完成并发布 `/lgtm`；除非新 push 引入相关回归，不再追评。
- #444：follow-up 已发布；不 `/assign`、不追评或启动实现，先等作者更新正文及 #441 owner / maintainer 决策。
- #447 / #448：已完成并合入，不再追踪 review；仅在发现 merged regression 时重新打开调查。
- #429：保持 `cf4024b` 两文件 scope；先在 fork-only validation branch rebase 到 latest `upstream/main@939abb5` 并跑 exact-head checks，再让用户确认 open PR branch update。
- #446：等待作者按 RainbowMango 的 scope/decomposition 意见更新或解释；不自动回复、撤销/重发 `/lgtm` 或追加评论。新 head 到来后先做 anchor-free scope closure，再复核 correctness 与 acceptance；任何已知 `remove/separate/unresolved` 项仍在时不得宣告 review complete。
- #385：公开更新和 exact-head CI 已完成；不自动评论、请求 reviewer 或添加标签。等待 maintainer review / #446 / #450 merge；任一前置合入后先在本地重算 rebase，再单独请求用户确认新的 force-with-lease 更新。
- Agent harness：下一次真实 Review 用 `agent-autoharness` 直接采集 normalized events、model/environment/budget/seed context 与 token/time/tool telemetry；先扩成至少 3 个 frozen labeled tasks、每个 3 attempts，再判断 task achievement、reliability、finding recall 和 efficiency 是否真实改善。不要用 Day57 单任务 post-hoc reconstruction 训练后再当 held-out 证据。
- 若用户要下一项贡献：优先选择可验证 review/testing feedback；#413 cleanup 即使技术方向匹配也不要与 active PR 重复。
- 若用户要代码工作：切到 `main` 或 clean topic branch from `upstream/main`，不要在 `intern` 写 AgentCube 源码。

## Stop Conditions

- Same environment blocker fails three times in a row, such as kind kubelet/cgroup/QoS or `/dev/kvm` access denial: stop debugging, record BLOCKED, switch task or machine.
- An upstream PR/issue already has an active assignee working on the same change: do not open duplicate PR; offer review, reproduction, or test feedback instead.
- If a community comment would be speculative without source, code evidence, official docs, or local test evidence: stop and gather evidence first.
