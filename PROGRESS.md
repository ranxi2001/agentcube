# PROGRESS.md

这个文件是给 Agent 循环用的短记忆，不是日报。每次开始工作先读这里，每次结束只更新关键状态，避免下一轮从零开始。

## Goal

当前主线：参与 AgentCube upstream 社区，跟进 PR #385，并围绕 SnapStart / warm pool / sandbox benchmark 找可验证、低重复的贡献点。

## Last Run

- Day15 报告已补入 2026-06-17 14:30 线上会议任务：和 `FAUST-BENCHOU` 讨论 AgentCube 下一步计划，重点围绕 v0.2.0 umbrella issue #386。
- `internship-reports/todo.md` 已新增 P0 任务“讨论 AgentCube v0.2.0 下一步计划”，下一步是整理 #386 中文内部总结并明确会后是否发英文 proposal / review / test plan。
- 已核查 #386 中 `zhzhuang-zju` 的 agent-sandbox 适配提案：AgentCube 确实依赖 `sigs.k8s.io/agent-sandbox v0.1.1`；临时升级到 `v0.4.6` 会因 `controllers.SandboxPodNameAnnotation` 缺失编译失败，但 `SandboxWarmPool` / `SandboxClaim` 类型和核心字段仍存在。
- 已溯源 agent-sandbox 编译失败：`v0.2.1` 可编译，`v0.3.10+` 失败；直接原因是 `SandboxPodNameAnnotation` 从 `controllers` 包迁到公开 API 包 `api/v1alpha1`，深层背景是 warm pool 从 bare Pod adoption 重构为 full Sandbox CR adoption。
- Day15 报告已更新更强版 #386 英文 comment 草稿：最小常量修复 + 依赖升级可让 `v0.3.10`/`v0.4.6` 非 e2e 测试通过，但不保证运行；新版 warm pool 可能 adopt generated-name Sandbox，AgentCube 当前按 claim/sandboxName watch Ready 事件，存在漏通知/超时风险。
- #386 评论已发布：https://github.com/volcano-sh/agentcube/issues/386#issuecomment-4725375092；当前暂无 maintainer 回复。
- 已固化“issue/PR 分析优先脚本化”的偏好：`AGENTS.md`、`agentcube-issue-discussion`、`agentcube-pr-management` 都已加入脚本优先和持续优化 skill 的规则。
- 新增 `.agents/skills/agentcube-issue-discussion/scripts/thread_brief.py`，用于输出 compact Markdown 版 issue/PR 摘要；已用 #386 和 #385 验证，能捕捉 PR review 中的 `/assign` 信号。
- 已对 #386 中 FAUST-BENCHOU 的 Sandbox Sleep/Resume 提案做代码级分析并写入 Day15：当前实现是 idle/TTL 直接删除式 GC，不是 Ready -> Paused -> Ready；最小实现也要跨 API/CRD、store state、GC、WorkloadManager pause/resume、Router resume-before-proxy、agent-sandbox replicas=0/1 语义和 e2e。
- 已补充 #386 两个提案关系：agent-sandbox 适配是 Sleep/Resume 的底层兼容性 foundation；如果先按 v0.1.1 实现 Sleep/Resume，后续升级到 v0.3.10+/v0.4.6 可能因 SandboxClaim / warm pool / Ready condition 语义变化返工。
- 已将 `/home/agentcube/会议记录` 中 2026-06-17 AgentCube 例会整理进 Day15：会后方向扩展为 agent-sandbox compatibility、Sleep/Resume lifecycle、E2B-compatible API/SDK/template、SnapStart/MicroVM snapshot/runtime 能力四层关系。
- Day16 已创建 `internship-reports/day16-agent-sandbox-latest-adaptation.md`，记录 `agent-sandbox` 适配任务由 ranxi 独立负责，并按“两条腿走路”拆成升级历史/行为审计与直接升级/测试驱动适配两条路线。
- 已创建 clean code worktree `/home/agentcube-agent-sandbox-latest`，分支 `feat/agent-sandbox-latest`，基线 `upstream/main` commit `0fd9151`；主目录继续保留实习报告，不把中文记录混入 upstream PR 分支。
- 在 feature 分支中 `go get sigs.k8s.io/agent-sandbox@v0.4.6` 已复现：该版本要求 Go `>=1.26.2`，并带动 K8s/controller-runtime 等依赖升级；随后 `go test ./pkg/workloadmanager ./cmd/workload-manager ./cmd/agentd` 失败在 `controllers.SandboxPodNameAnnotation` 未定义。
- 已确认 `v0.5.0rc1` Git tag 存在且可由 Go 解析为 pseudo-version `v0.4.7-0.20260608211546-6af1bbd0cf64`，但 `go list -m ...@latest` 仍是 `v0.4.6`，PR 是否依赖 rc/pseudo-version 需维护者确认。
- `/home/agentcube-agent-sandbox-latest` Day16 适配已推进到真实运行验证：升级 `agent-sandbox v0.4.6`，移除 `controllers` 内部包依赖，SandboxClaim 路径等待 `claim.Status.SandboxStatus.Name` 指向的 adopted Sandbox，store 仍保存 claim 名用于 delete/GC；另发现并修复 v0.4.6 `SandboxTemplate` 默认 Managed NetworkPolicy 阻断 AgentCube Router/WorkloadManager 的问题，当前显式设 `networkPolicyManagement: Unmanaged`。
- Day16 验证已通过：`go test ./pkg/workloadmanager`、`go test -race ./pkg/workloadmanager`、非 e2e Go 全量、`make build-all`、Docker build 三镜像、Helm template/lint、k3s direct CodeInterpreter e2e、warm pool e2e、warm pool load 100/100、Python SDK、LangChain sandbox、MCP HTTP/stdio、math-agent LLM e2e（OpenAI-compatible base URL 需带 `/v1`）。
- 新增 `.agents/skills/llm-e2e-test/SKILL.md`，用于复用 AgentCube math-agent / OpenAI-compatible LLM 端到端测试流程；已通过 `quick_validate.py`。
- Day16 `agent-sandbox v0.4.6` 适配代码已提交并 push：`/home/agentcube-agent-sandbox-latest` branch `feat/agent-sandbox-latest` commit `5316358`，DCO signoff 已包含，origin 分支已存在。Upstream PR 已创建：#387 `https://github.com/volcano-sh/agentcube/pull/387`。第一次 token API 创建返回 `401 Bad credentials`；第二次 token 创建成功。token 未落盘，临时 body 已删除，workspace 文件中未发现 GitHub token pattern；用户应 revoke / rotate 明文暴露过的 token。
- PR #387 初始状态已更新：open、非 draft、labels `kind/bug` / `size/XL`，commit `5316358`。当前 DCO、build、e2e-test、Codegen Check、python-sdk-tests、Python Lint、codespell 已通过；失败 check 为 `coverage` 和 `golangci-lint`；bot 提示 review 获得 `lgtm` 后再 assign `hzxuzhonghu` approval。
- 用户要求后续 GitHub API/PR 操作不再重复索要 token；本地 token 已保存到 git-ignored `.agents/.env`，变量名 `GITHUB_TOKEN` / `GH_TOKEN`，权限 `600`。只记录位置和变量名，不记录密钥值。
- Day16 提交前新发现并修复 codegen 问题：旧 `hack/update-codegen.sh` 固定 `code-generator v0.34.1` 且用 `go get -d`，会在生成过程中把 `agent-sandbox` 降级；当前 PR 已对齐 `code-generator v0.35.4` 并改用 `go mod download`。commit 后 `make gen-check` 已通过。
- Day17 已创建 `internship-reports/day17-pr387-copilot-review-and-ci-triage.md`：Copilot 7 条评论合并为 4 类（direct wait nil channel guard、annotation comment、e2e warm-pool UID 匹配、recordingStore 错误传播和 slice deep copy）；`golangci-lint` 失败根因初判为 workflow 用 Go 1.24 构建 linter，而 PR `go.mod` target 为 Go 1.26.2；`coverage` 失败发生在 `go test -race -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...`，日志可见 package summary 均为 `ok`，需要 exact command 复现。
- Mentor 建议已固化到 `.agents/skills/agentcube-pr-management/SKILL.md` 和 Day17：不要默认在已打开的 upstream PR 上不断累积 review/CI 修复；先用临时 fix branch 或独立小 PR 验证，属于原 PR 范围的再 clean rebase/squash/cherry-pick 回原 PR，通用 CI/toolchain 修复应从 `upstream/main` 单独提 PR，合并后再让原 PR rebase。
- `/home/agentcube-agent-sandbox-latest` 已从 #387 head 创建验证分支 `fix/pr387-review-feedback`，commit `13f19e3 fix: address agent-sandbox adaptation review feedback`，并推送 fork stacked PR `https://github.com/ranxi2001/agentcube/pull/1`（base `feat/agent-sandbox-latest`，head `fix/pr387-review-feedback`）。该 commit 修复 lint/coverage workflow Go 版本、Copilot 指出的 nil watcher guard、annotation comment、warm-pool e2e UID 匹配、recordingStore error/deep copy，并降低两个 gocyclo 报警点。
- 已按用户确认创建 upstream CI 验证 PR #390：`https://github.com/volcano-sh/agentcube/pull/390`，标题 `[DO NOT MERGE] validation for PR #387 with review fixes`，分支 `test/pr387-with-review-fixes` 基于 `upstream/main`，包含两个 commit：`2c93451`（#387 原始适配）和 `6f94052`（review/CI 修复）。该 PR 只用于跑 upstream bot/CI，不作为最终合并目标。#390 最新 CI 已全绿，包括 `coverage`、`golangci-lint` 和 `e2e-test`。
- #390 新增 AI review 已 triage 并写入 Day17：Gemini 关于 `client-go` fake client WatchList 方法名的 `critical` 评论是误报，`client-go@v0.35.4` 和 `code-generator@v0.35.4` 实际接口/生成器均使用 `IsWatchListSemanticsUnSupported()`；Copilot 的生成代码注释评论不应在 AgentCube PR 手改。有效评论是 3 条：`waitForDirectSandboxReady` 需要处理 closed channel / nil sandbox，`waitForClaimSandboxReady` 遇到 context error 应立即返回，`hack/update-codegen.sh` 的 `sed` 解析不应依赖尾随逗号。暂不回灌 #390 到 #387。
- #390 暴露的 upstream 协作流程问题已固化为规则：提交任何 upstream PR/draft/WIP、issue、comment、review comment、`/assign`、request review 或 mention 维护者之前必须先让用户确认完整内容；upstream PR 必须使用官方 `.github/PULL_REQUEST_TEMPLATE.md`，draft/WIP 也不能自拟风格；未完成 upstream PR 用 `[WIP]`，不用 `[DO NOT MERGE]`；只为跑 CI 时优先用 fork branch / fork PR / fork Actions / 本地测试；阅读分析别人的 PR 默认写本地报告，不需要维护者验证就不发社区。
- 已更正“不要在一个 PR 反复更新”的理解：这不是机械禁止更新 PR。当前 PR 引入的问题可以验证后 clean update 当前 PR；需要拆出去的是独立前置条件或仓库级兼容性变化。Go/toolchain 升级属于 `agent-sandbox` 适配的独立前置条件，正确路径是从 `upstream/main` 做纯净 Go/toolchain upgrade 分支，先证明原始 AgentCube 项目在新 Go 下 build/test/lint/e2e 能跑，再让 #387 rebase 到合入后的 `main`。
- 纯净 Go/toolchain 前置分支已按 mentor 建议重做：官方 Go feed 当前稳定版本为 `go1.26.4`，workflow 改用 `go-version-file: go.mod`，Docker builder 镜像显式对齐到 `1.26.4`。`/home/agentcube-go-toolchain-upgrade` branch `chore/go-stable-toolchain`，base `upstream/main 0fd9151`，commit `3f1a823 chore: update Go toolchain to 1.26.4`。本地验证通过：非 e2e Go tests、race coverage、`make build-all`、`make lint`、提交后 `make gen-check`、三 Docker builds、`git diff --check`。fork validation PR `https://github.com/ranxi2001/agentcube/pull/3` CI 全绿：codespell、Codegen Check、Python Lint、两个 build、coverage、e2e-test、golangci-lint、python-sdk-tests。旧 1.26.2 fork PR #2 已关闭为 superseded。
- upstream Go/toolchain PR #391 已合并：`https://github.com/volcano-sh/agentcube/pull/391`，title `chore: update Go toolchain to 1.26.4`，merge commit `a31651e5aba6ab0ce6ef854ffdb724146b40af5b`，merged at `2026-06-18T06:37:52Z` by `volcano-sh-bot` after `RainbowMango` approved with `/lgtm /approve` and “Good job! Thanks.” This is the accepted Go 1.26.4 prerequisite for #387.
- PR #385 已按 Gemini 建议更新：`WarmPoolNotFound` condition 保留，但不再记录 Warning Event。
- PR #385 最新 commit `d885b4e` 已 push，DCO 漏签已用 `git commit --amend --no-edit --signoff` 修复。
- PR #385 Gemini thread 已回复，附了 focused tests、`go test ./pkg/workloadmanager` 和 `git diff --check`。
- PR #379 已读实现范围：CRD、controller、agentd Kuasar driver、artifact store、CodeInterpreter restore intent。
- PR #379 找到一个非重复 review 点：promotion 重置 `ReadyAt` 后，可能因 `snapshotStatusEqual` 不比较 `ReadyAt` 而没有持久化，导致 `RebuildAfter` 继续触发 rebuild。
- #391 合并后已在 `/home/agentcube-agent-sandbox-latest` 创建本地验证分支 `rebase/pr387-on-go1264`：从 `origin/feat/agent-sandbox-latest` rebase 到 `upstream/main a31651e`，冲突仅为 Go/toolchain 文件并保留 Go `1.26.4`。直接 rebase 后 `go test ./pkg/workloadmanager` 和 coverage exact command 通过，但 `make lint` 仍失败，说明 #391 只解决工具链基线，不能自动修复 #387 自身代码问题。
- `rebase/pr387-on-go1264` 已补本地 commit `5867183 fix: address agent-sandbox adaptation review feedback`，处理 direct watcher nil/closed/nil sandbox、claim context error、lint complexity、recordingStore、e2e warm-pool UID matching、codegen sed 解析；验证通过：`go test ./pkg/workloadmanager -count=1`、`make lint`、`go test -race ./pkg/workloadmanager -count=1`、coverage exact command、非 e2e Go tests、`make gen-check`、`go test ./test/e2e -run '^$' -count=1`、`make build-all`、`git diff --check`、`git diff --exit-code`。该分支尚未 push，也未更新 #387。
- Fork CI validation PR 已创建并全绿：`https://github.com/ranxi2001/agentcube/pull/4`，base `release-pr387-go1264` -> `a31651e`，head `ci/pr387-rebase-go1264` -> `5867183`，mergeable clean。完整通过 Codespell、Python SDK Tests、Python Lint、Copyright Check、Codegen Check、Agentcube CI Workflow build jobs、Lint/golangci-lint、Test Coverage、Agentcube E2E Tests。注意：fork PR base 需用 `release-*` 或 `main` 才会触发完整 PR workflows；普通 `ci/*` base 只触发无 branch filter 的 coverage / python-sdk-tests。
- 用户确认后已更新 upstream PR #387：`ranxi2001:feat/agent-sandbox-latest` force-with-lease 从 `5316358` 更新到 `5867183`，PR body 已去掉旧 Go 1.26.2 / Go 版本前置问题描述，保留 dependency stack 说明和 fork CI evidence。Upstream checks 全绿：DCO、Approve workflows、codespell、Codegen、Python Lint、两个 build、coverage、e2e-test、golangci-lint、python-sdk-tests。当前 `mergeable_state=unstable` 预计是等待 maintainer review / lgtm / approve / tide，不是测试失败。
- 已按源码方式分析 #387 中 `zhzhuang-zju` 对 label 和 `v0.5.0rc1` 的评论。结论：#387 更适合 `/kind feature`；`v0.5.0rc1` 不是当前 Go module `@latest`，会解析为 pseudo-version，且源码已从 `api/v1alpha1` / `extensions/api/v1alpha1` 迁到 `v1beta1`。本地试验显示 `go mod tidy` 先因 v1alpha1 package 缺失失败；机械改 import 后又失败在 `SandboxSpec.Replicas` 被 `OperatingMode` 替换、`SandboxClaimSpec.TemplateRef` 被 required `WarmPoolRef` 替换。Day17 已记录完整源码证据和英文回复草稿。
- 新增 `.agents/skills/agentcube-pr-management/scripts/audit_go_module_version.py`，并补充 PR skill 的 Dependency Release / RC Triage 流程，用于复用 `go list @latest/@tag/-versions`、package presence 和最小 bump 实验。
- 用户确认后更新了 PR #387 body：`What type of PR is this?` 已从 `/kind bug` 改为 `/kind feature`，`What this PR does / why we need it` 已改为 current stable `agent-sandbox v0.4.6` compatibility feature 口径，target-version note 也说明 `v0.5.0rc1` 不只是 pseudo-version 问题，更涉及 `v1alpha1` -> `v1beta1`、`TemplateRef` -> required `WarmPoolRef`、`Replicas` -> `OperatingMode` 的语义迁移。随后按用户要求改 label；直接 Labels API 因无 admin 权限返回 403，已用 bot 命令评论 `/remove-kind bug` + `/kind feature` 完成，当前 labels 为 `kind/feature` / `size/XL`。未发布解释性技术回复。
- 已形成 `agent-sandbox v0.5.x` follow-up 计划并写入 Day17/TODO：#387 保持 current stable `v0.4.6` 兼容范围；`v0.5.x`/`v1beta1` 迁移另开干净 follow-up，核心改动包括 imports/scheme/GVR v1beta1、direct Sandbox `Replicas -> OperatingMode`、warm-pool claim `TemplateRef -> WarmPoolRef`、真实 v0.5.x manifests/e2e/math-agent 验证，并把 Sleep/Resume 作为后续状态机设计而非混入兼容 PR。
- 用户确认将 `agent-sandbox v0.5.x` 前沿适配测试拆出 #387；已新增 Day18 `internship-reports/day18-agent-sandbox-v05-forward-adaptation.md`，并把 TODO 拆成 stable `v0.4.6` review 任务和 `v0.5.x/v1beta1` fork-only validation 任务。
- Day18 `agent-sandbox v0.5.0rc1` 前沿适配已完成真实 runtime 和 fork CI 验证：`/home/agentcube-agent-sandbox-latest` fork branch `test/agent-sandbox-v05-forward` 当前 head `c0122da`，包含最小 v1beta1/API 迁移 commit `ee1aecf` 和 e2e manifest 版本对齐 commit `c0122da`。Fork PR `https://github.com/ranxi2001/agentcube/pull/5`，base `release-agent-sandbox-v05-base` -> `5867183`，head `test/agent-sandbox-v05-forward` -> `c0122da`，所有 checks 全绿：approve workflows、codespell、Codegen、Python Lint、两个 build、coverage、e2e-test、golangci-lint、python-sdk-tests。第一次 fork CI 失败根因是 e2e setup 仍安装旧 agent-sandbox manifest，集群无 v1beta1 CRD，workloadmanager 报 `no matches for kind "SandboxWarmPool" in version "extensions.agents.x-k8s.io/v1beta1"`；`c0122da` 已将 `make e2e` / `run_e2e.sh` 默认 agent-sandbox manifest 对齐到 `v0.5.0rc1`。未更新 #387，未创建 upstream PR。
- Day18 runtime 关键发现：当前默认 k3s 的 agent-sandbox CRD 仍是 `v1alpha1` storedVersions；rc1 manifest 是 v1beta1-only，`kubectl apply --dry-run=server` 会因 `status.storedVersions[0]: "v1alpha1" must appear in spec.versions` 拒绝原地 apply。干净 k3d 集群可直接安装 rc1。后续不能把“代码能跑”说成“现有集群可无缝升级”，需要单独处理 CRD migration / clean install 口径。
- 已更新 PR skill / AGENTS：完整 GitHub Actions CI 通常由 `pull_request` 事件触发，单纯 push fork branch 不会跑全量 checks；需要 fork CI 时创建 fork PR，base 用 `main` 或 `release-*` 以匹配 workflow branch filters。
- 已完成 #387 下周 review 准备材料：[Day19](internship-reports/day19-pr387-code-review-prep.md) 按文件/行级别整理了 changed files 的修改原因、为什么这样改、local-vs-project 分类、`go.mod` 依赖栈解释、generated files 口径、review Q&A 和测试覆盖矩阵。重点结论：#387 是 `agent-sandbox v0.4.6` current stable compatibility feature；`k8s.io/* v0.35.4` 由 `agent-sandbox v0.4.6` 依赖链驱动；claim path 必须通过 `SandboxClaim.Status.SandboxStatus.Name` 找 adopted Sandbox，但 store 仍保存 claim 名；`NetworkPolicyManagementUnmanaged` 是保持现有 AgentCube connectivity。`pkg/workloadmanager/k8s_client.go` 段落已扩展，解释了 `getSandboxClaim -> getSandbox` 读取链路、dynamic client 选择、unstructured/typed conversion 和 review 答辩口径。`pkg/workloadmanager/sandbox_helper.go` 段落已补充 placeholder `CreatedAt` / `ExpiresAt` 和 store expiry index 关系。`test/e2e/e2e_test.go` 段落已补充删改较多的原因：三处旧 warm-pool Pod 过滤逻辑统一到 `listWarmPoolPods`，以兼容旧 direct `SandboxWarmPool -> Pod` 和新版 `SandboxWarmPool -> Sandbox -> Pod` ownerRef 链。
- 用户确认后已 push #387 最小修复 commit `ff8260e chore: drop unrelated picod Dockerfile cleanup` 到 `origin/feat/agent-sandbox-latest`。PR #387 当前 changed files 为 15，`docker/Dockerfile.picod` 已不在 diff 中。验证已通过：`go test ./pkg/workloadmanager -count=1`、`docker build -f docker/Dockerfile.picod -t agentcube-pr387-minimal-picod:test .`、`make build-all`、`make gen-check`、`go test ./test/e2e -run '^$' -count=1`、`git diff --check`、`git diff --cached --check`。
- 用户确认后已 push #387 注释对齐 commit `bc8e85b docs: align sandbox pod annotation comment` 到 `origin/feat/agent-sandbox-latest`。该 commit 只修改 `pkg/workloadmanager/handlers.go` 注释：从硬编码 `agents.x-k8s.io/pod-name` 改为引用 `sandboxv1alpha1.SandboxPodNameAnnotation`，用于回应 Copilot 的低风险注释维护性建议。验证通过：`go test ./pkg/workloadmanager -count=1`、`git diff --check`。PR #387 当前 head 为 `bc8e85b`，changed files 仍为 15。
- PR skill 已强化最小修原则：fix/feature/compatibility PR 默认把 upstream base 当作稳定基线，只改解决目标问题必需的最少文件；代码清洁、格式、镜像卫生、注释润色、无关 refactor 不应夹带在功能/修复 PR 中，目标测试不依赖的 cleanup 必须移除或另开 cleanup PR。
- 已调整 fork 分支语义：`origin/main` 已 force-with-lease 重置为 `upstream/main bed6bd4` 的干净镜像；所有实习报告、TODO、local skills 和中文记录保存在 `origin/intern`。本地当前应在 `intern` 上继续做记录，upstream PR topic branches 继续从 `upstream/main` 创建。
- Day20 已创建并补充分段适配实验：[项目二次梳理学习](internship-reports/day20-project-second-pass-architecture-and-dependencies.md)。核心结论：当前 main 是 Go `1.26.4` + `agent-sandbox v0.1.1`；设计文档中的 `Ready -> Paused -> Ready` 尚未实现，当前真实语义是 Router/Store last_activity + WorkloadManager/AgentD delete-on-idle。新增 `agent-sandbox v0.2.1` / `v0.3.10` 实验：0.2.1 是 2 文件 dependency-only 且 `make gen-check` 通过；0.3.10 开始需要 claim adopted Sandbox、public annotation、NetworkPolicy opt-out 等 runtime-aware 修复，实验分支 9 文件，通过非 e2e Go tests / e2e static compile / build-all，但旧 `hack/update-codegen.sh` 会把依赖降级回 `agent-sandbox v0.2.1`，正式 PR 仍需 codegen 脚本修复。

## Current Blockers

- 当前机器没有 `/dev/kvm`，CPU 虚拟化 flags 未暴露，不能实测 Kuasar / MicroVM / forkd / CubeSandbox 的真实虚拟化路径。
- kind 标准 Kubernetes 在本机 kubelet cgroup/QoS 初始化处失败；KWOK 只能用于调度语义，不等同完整 K8s 实测。
- kind 标准集群创建仍在本机 kubelet/cgroup 环境处失败；Day16 真实 runtime 验证改用已有 k3s。不能把 kind 失败描述成 AgentCube 代码失败。
- PR #385 当前主要等待 maintainer review、`/lgtm`、`/approve` 和 tide 合并门禁。
- PR #387 当前不应直接把 `v0.5.0rc1` 扩入同一 PR；它需要 v1beta1 API / claim `WarmPoolRef` / Sandbox `OperatingMode` 语义迁移，已拆到 Day18 前沿适配测试。PR body 和 label 已更新；后续解释性 comment 由用户自己发，除非用户另行要求。
- 当前 Codex shell 默认 `PATH` 里没有 `go`，但可通过 `/root/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.4.linux-amd64/bin` 使用 Go 1.26.4。全量 `go test ./...` 会因本机未启动 Router/WorkloadManager、无 kubeconfig 而在 `test/e2e` 失败；排除 e2e 的全量 Go 测试已通过。
- `agent-sandbox v0.3.10` 适配实验本身已编译/测试通过，但 `make gen-check` 在未修 `hack/update-codegen.sh` 时会因固定 `code-generator@v0.34.1` 扰动依赖并降级 agent-sandbox；正式化 0.3+ 适配时必须先修 codegen pin / download 逻辑。

## Ruled Out

- 不再把 `WarmPoolNotFound` 当成需要 Warning Event 的稳定故障；它可能只是 controller 创建 warm pool 后 cache 尚未同步。
- 不重复评论 #379 里 Copilot 已经指出的 `ctrl.SetupSignalHandler()` 双调用问题。
- 不声称本机跑通过真实 SnapStart restore；当前只能做代码阅读、controller/unit test 级验证。
- 不把 `v0.5.0rc1` 不适配的原因简化成“pseudo-version”。真实阻塞是 `v1alpha1` package 缺失、direct Sandbox `Replicas` 字段移除、SandboxClaim `TemplateRef` 语义改成 required `WarmPoolRef`。

## Next

- User confirmed updating #387. `origin/feat/agent-sandbox-latest` was force-with-lease pushed from `bc8e85b` to `c2633c5` using local branch `/home/agentcube-agent-sandbox-latest` `rebase/pr387-on-bed6bd4`. PR #387 now lists 5 commits (`bacf12d`, `1272052`, `1cb73f7`, `5ffc44b`, `c2633c5`) and 15 changed files. This should resolve tide's merge conflict caused by `upstream/main bed6bd4`; wait for refreshed CI/tide before further action. Do not post comments or push more updates without user confirmation.
- Branch hygiene: keep fork `main` as a clean mirror of `upstream/main`; do not put internship reports or Chinese notes there. Continue local records on `intern`; rebase `intern` onto `upstream/main` when project code needs to be current.
- Day20 后续：如继续做架构学习，下一步专项深读 Python SDK / CLI auth/session 封装，或补 agent-sandbox controller 源码状态机。0.2/0.3 分段适配实验分支已本地提交：`/home/agentcube-agent-sandbox-v02` head `a4506d6`，`/home/agentcube-agent-sandbox-v03` head `02cfae5`；尚未 push。不要把 Day20 的 general notes 混入 upstream PR。
- Day18 `agent-sandbox v0.5.x` next step: decide follow-up packaging. Runtime evidence is now strong on clean rc1/v1beta1 install, but no upstream PR should be opened until official `v0.5.0` release or explicit maintainer request for rc support. If preparing PR material, include the clean-install limitation and do not claim in-place upgrade from existing v1alpha1 CRDs.
- 根据 2026-06-17 例会纪要，把 `Sleep/Resume`、E2B-compatible API / SDK / template 分别拆成可公开讨论的英文 proposal / issue comment；`agent-sandbox` 适配已进入代码分支推进。
- 与 FAUST-BENCHOU 讨论 Sleep/Resume 时优先确认第一版语义：是否接受基于 `Sandbox.spec.replicas=0/1` 的 stop/recreate，`context` 是否仅指 workspace/PVC，是否新增 `pauseTimeout`，warm-pool-backed CodeInterpreter 是否纳入第一版。
- 建议把 #386 两个方向作为同一 v0.2.0 epic 的两个子任务讨论：先定 agent-sandbox target version / compatibility foundation，再做 AgentCube Sleep/Resume lifecycle。
- 跟踪 #386 maintainer 是否 triage agent-sandbox 适配为 dedicated sub-issue；有明确方向后再准备 compatibility audit PR 或最小修复 PR。
- 后续看 issue/PR 时先跑 `thread_brief.py <number>`；看 PR 再配合 `pr_status.py <number>`，如果流程重复就继续补脚本而不是手工重做。
- 优先把 #379 的 `ReadyAt` status equality 评论发到 PR，或先在临时分支补最小 controller unit test 验证。
- 继续跟踪 #385 的 CI、Codecov、tide、maintainer review，有反馈再小步处理。
- 如果继续做 benchmark，只跑当前环境能支撑的 AgentCube / k3s / controller 层测试，并明确“不包含真实 MicroVM/KVM restore”。

## Stop Conditions

- 同一个环境问题连续失败 3 次，例如 kind kubelet cgroup/QoS 或 `/dev/kvm` 缺失，不再硬调，转为记录 BLOCKED 并换机器/环境。
- 同一个 upstream PR 已有人明确认领并正在改同一问题，不开重复 PR，只做 review、复现或测试反馈。
- 如果只能基于推测发社区评论，先停止，补代码证据、测试证据或引用具体文件行后再发。
