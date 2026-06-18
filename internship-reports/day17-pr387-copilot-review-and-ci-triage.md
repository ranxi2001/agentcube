# Day 17 - PR #387 Copilot Review and CI Triage

日期：2026-06-18

PR：[#387 fix: adapt code interpreter warm pool to agent-sandbox v0.4.6](https://github.com/volcano-sh/agentcube/pull/387)

分支：`ranxi2001:feat/agent-sandbox-latest`

当前 commit：`5316358`

## 背景

Day16 已完成 `sigs.k8s.io/agent-sandbox v0.4.6` 适配并提交 upstream PR #387。PR 创建后 Copilot 自动生成了 7 条 review comment，同时 GitHub Actions 出现 2 个失败 check。Day17 的初始工作先做评论分组、CI 阻塞定位和后续修复计划，避免直接逐条机械回复。

本次使用的本地脚本和命令：

```bash
python3 .agents/skills/agentcube-pr-management/scripts/pr_status.py 387
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 387
```

同时通过 GitHub Checks API 核对了 commit `5316358` 的 check runs 和失败 job 日志。

## PR 当前状态快照

PR surface：

- 状态：open，非 draft
- Labels：`kind/bug`、`size/XL`
- Changed files：18
- Diff：+577 / -250
- Commit：`5316358 fix: adapt code interpreter warm pool to agent-sandbox v0.4.6`
- Human maintainer review：暂无

社区角色分类：

| 来源 | 类型 | 当前含义 | 处理方式 |
| --- | --- | --- | --- |
| `volcano-sh-bot` | 流程 bot | PR 当前 `NOT APPROVED`；获得 review / `lgtm` 后再 assign `hzxuzhonghu` approval | 作为流程门禁记录，不是技术意见 |
| `gemini-code-assist[bot]` | AI reviewer | Gemini review 创建失败，可用 `/gemini review` 重试 | 暂不作为技术阻塞 |
| Copilot review | AI reviewer | 7 条 code review comment | 作为检查清单，先人工验证再采纳 |
| GitHub Actions | CI | `coverage`、`golangci-lint` 失败，其余主要检查通过 | 作为 merge blocker 优先处理 |
| Human maintainer | 真人 reviewer | 暂无评论 | 后续优先级高于 AI reviewer |

## CI 状态

已通过：

- `Approve workflows based on contributor status`
- `Python Lint`
- `Check for spelling errors`
- `build`
- `e2e-test`
- `Codegen Check`
- `python-sdk-tests`
- `DCO`

失败：

| Check | 失败 step | 关键日志 | 初步判断 |
| --- | --- | --- | --- |
| `golangci-lint` | `Run golangci-lint` | `can't load config: the Go language version (go1.24) used to build golangci-lint is lower than the targeted Go version (1.26.2)` | PR 将 `go.mod` 升到 `go 1.26.2`，但 `.github/workflows/lint.yml` 仍用 `setup-go` `1.24`，`make lint` 安装出的 `golangci-lint` 也由 Go 1.24 构建，导致 linter 不能加载目标 Go 版本配置。这不是普通 lint rule 报错，而是 workflow/toolchain 不一致。 |
| `coverage` | `Run tests with coverage` | `go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...` 最终 `Process completed with exit code 1` | 日志中可见的 package summary 都是 `ok`，末尾 `pkg/workloadmanager` 覆盖率为 `25.9%`。workflow 没有显式 coverage threshold，所以不能简单归因为覆盖率太低。需要本地 exact command 复现，或先把 coverage workflow 的 Go 版本对齐到 `1.26.2` 后重跑 CI。 |

PR 分支中发现的 workflow / toolchain 不一致：

```text
go.mod: go 1.26.2
.github/workflows/lint.yml: go-version: "1.24"
.github/workflows/test-coverage.yml: go-version: "1.24"
.github/workflows/codegen-check.yml: go-version: "1.24.4"
.github/workflows/e2e.yml: go-version: "1.23"
Makefile: GOLANGCI_LINT_VERSION ?= v1.64.1
```

其中 `build`、`e2e-test`、`Codegen Check` 当前已通过，说明 Go auto toolchain 在部分 workflow 中能下载 `go1.26.2` 并继续执行；但 `golangci-lint` 需要 linter binary 本身由不低于目标版本的 Go 构建，所以仍会失败。

本地复现卡点：

```bash
go test -race -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
```

当前 Codex shell 里 `go` 不在 `PATH`，命令直接失败：

```text
EXIT:127
/bin/bash: go: command not found
```

后续需要先恢复本地 Go 工具链，或者通过 CI follow-up commit 验证 exact coverage 命令。

## Copilot Comments Triage

Copilot 7 条 comment 实际可以合并成 4 类。

| 文件 | 评论数量 | 结论 | 建议处理 |
| --- | ---: | --- | --- |
| `pkg/workloadmanager/handlers.go` `waitForDirectSandboxReady` | 2 | 有效。`resultChan == nil` 时 `select` 的 receive case 会永久 disabled，只能等 context cancel 或 2 分钟 timeout。虽然正常路径应由 watcher 提供 channel，但这里确实会把 wiring bug 伪装成创建超时。 | 在函数开头增加 `nil` guard，返回明确错误；补一个 focused unit test，验证 nil channel 不会等待 timeout。 |
| `pkg/workloadmanager/handlers.go` annotation comment | 1 | 低风险 style/nit。当前注释写的 `agents.x-k8s.io/pod-name` 与 `agent-sandbox v0.4.6` 的 `sandboxv1alpha1.SandboxPodNameAnnotation` 常量值一致，并非行为 bug。但注释直接写死 key，未来 dependency 变动时容易误导。 | 把注释改成引用 `sandboxv1alpha1.SandboxPodNameAnnotation`，必要时保留当前常量值用于调试。 |
| `test/e2e/e2e_test.go` warm pool pod ownership | 3 | 有效。当前 helper 用 Sandbox name 记录 warm pool membership，再用 Pod ownerRef name 匹配；如果 Sandbox 删除后同名重建，e2e 可能误判。Kubernetes ownerRef 本来就包含 UID，更适合识别真实 owner。 | 对 `SandboxWarmPool -> Sandbox -> Pod` 路径改用 Sandbox UID 匹配 Pod ownerRef UID；保留旧 direct `SandboxWarmPool -> Pod` 路径按 owner name 匹配。 |
| `pkg/workloadmanager/handlers_test.go` `recordingStore.UpdateSandbox` | 1 | 有效。测试 fake store 的 embedded `UpdateSandbox` 返回值被忽略；`copied := *sandbox` 是浅拷贝，`EntryPoints` slice 仍会 alias 原对象。 | 捕获并返回 embedded store error；对 `EntryPoints` 做 deep copy。当前 `SandboxInfo` 没有 map 字段，重点处理 slice。 |

优先级：

1. P0：修复 `golangci-lint` / `coverage` 两个失败 check。
2. P1：采纳 3 个明确有效的 Copilot 工程质量建议：nil channel guard、warm pool UID 匹配、recordingStore 错误传播和 slice deep copy。
3. P2：annotation 注释清理。

## 下一步修复计划

Mentor 给出的开源协作建议是：不要在当前 PR #387 上无限继续累积 commit。更合适的流程是先在单独的 fix branch / 新 PR 中验证当前问题的修复，再决定哪些改动应该 rebase / port 回 #387，哪些应该作为独立 PR 合并后再让 #387 rebase 到新的 `upstream/main`。

据此调整后续计划：

1. 把 Copilot 评论和 CI 失败先拆成两类：属于 #387 适配本身的修复，先用临时验证分支验证；属于仓库通用 CI/toolchain 漂移的问题，优先提单独小 PR。
2. 不直接往 `/home/agentcube-agent-sandbox-latest` 的 `feat/agent-sandbox-latest` 分支继续堆 commit；先创建 `fix/pr387-review-feedback` 或类似分支做验证。
3. 检查并对齐 workflow Go 版本。优先候选方案是让 `lint` 和 `test-coverage` 使用 `1.26.2`，避免 `golangci-lint` 被 Go 1.24 构建；如果判断为通用 CI 修复，应从 `upstream/main` 单独开 PR。
4. 恢复本地 Go 工具链后复现：

```bash
go test ./pkg/workloadmanager -count=1
go test -race ./pkg/workloadmanager -count=1
go test -race -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
make lint
```

5. 如果本地 coverage exact command 仍显示所有 package `ok` 但退出 1，需要保留完整日志并进一步检查 Go 1.26 toolchain、race detector、coverage profile 合并或 workflow runner 差异。
6. 验证通过后再决定 clean update 方式：属于 #387 的小修复可以 rebase/squash/cherry-pick 回原 PR 分支；独立 CI 修复则单独 PR 合并后，让 #387 rebase 到更新后的 upstream。
7. 最后再逐条回复 Copilot review comment。回复内容应说明具体改动和测试结果，不把 AI reviewer 当成 maintainer 共识。

## 当前判断

Copilot 评论里没有发现推翻 Day16 适配方向的问题。主要是边界防御、e2e helper 稳定性和测试 fake store 质量问题，适合用小 patch 修掉。

真正阻塞 merge 的是 CI。`golangci-lint` 的根因比较明确：Go 版本升级后 workflow 没有同步，导致 linter binary 构建版本低于 module target。`coverage` 还需要复现，当前不能把它归结成覆盖率不足，因为 workflow 没有 threshold，且日志中可见 package 全部是 `ok`。

## 修复验证分支

按 mentor 建议，没有直接继续修改 #387 原分支 `feat/agent-sandbox-latest`，而是从 PR head 创建验证分支：

```bash
cd /home/agentcube-agent-sandbox-latest
git switch -c fix/pr387-review-feedback
```

验证分支 commit：

```text
13f19e3 fix: address agent-sandbox adaptation review feedback
```

验证 PR：

- Fork stacked PR：[ranxi2001/agentcube#1](https://github.com/ranxi2001/agentcube/pull/1)
- Base：`feat/agent-sandbox-latest`
- Head：`fix/pr387-review-feedback`
- 用途：只展示相对 #387 原分支的修复 diff，验证通过后再 clean cherry-pick / rebase 回 upstream PR #387。

本次修复内容：

- `.github/workflows/lint.yml` / `.github/workflows/test-coverage.yml`：将 CI 使用的 Go 版本从 `1.24` 对齐到 `1.26.2`，避免 `golangci-lint` 由低于 module target 的 Go 版本构建。
- `pkg/workloadmanager/handlers.go`：提取 `respondSandboxCreateError`，降低 `handleSandboxCreate` cyclomatic complexity；给 `waitForDirectSandboxReady` 增加 `resultChan == nil` guard；注释改为引用 `sandboxv1alpha1.SandboxPodNameAnnotation`。
- `pkg/workloadmanager/handlers_test.go`：`recordingStore.UpdateSandbox` 返回 embedded store error，并 deep copy `EntryPoints`；补 `TestWaitForDirectSandboxReadyNilResultChannel`；修复 fake dynamic reactor 的 unchecked type assertion。
- `test/e2e/e2e_test.go`：warm-pool `Sandbox -> Pod` ownerRef 匹配改用 Sandbox UID，旧 direct `SandboxWarmPool -> Pod` 兼容路径仍按 owner name 匹配；拆出 helper 降低 `listWarmPoolPods` complexity。

本地验证命令和结果：

```bash
export PATH=/root/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.2.linux-amd64/bin:$PATH
go test ./pkg/workloadmanager -count=1
go test ./test/e2e -run TestNonExistent -count=1
make lint
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
go test -race ./pkg/workloadmanager -count=1
go test ./pkg/... -count=1
git diff --check
```

结果：以上命令全部通过。coverage exact command 退出码为 `0`，`pkg/workloadmanager` coverage 从 CI 日志里的 `25.9%` 变为本地 `26.0%`。

额外尝试：

```bash
go test ./... -count=1
```

结果：失败在 `test/e2e` 环境依赖，不是本次 patch 的代码失败。具体原因是本地没有启动 Router / WorkloadManager（`localhost:8080` / `localhost:8081` connection refused），也没有可用 kubeconfig（`no configuration has been provided`）。因此用排除 e2e 的全量 Go 测试作为本次代码验证口径：

```bash
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
```

结果：通过。

后续 clean update 选择：

- 如果采用 stacked validation PR：base 应该是 fork 内的 `feat/agent-sandbox-latest`，head 是 `fix/pr387-review-feedback`，避免向 upstream `main` 提交一个包含 #387 全量改动的重复 PR。
- 如果直接更新 #387：从验证分支 cherry-pick `13f19e3` 到 `feat/agent-sandbox-latest`，再 push 原 PR 分支。

## Upstream CI Validation PR

为了让 volcano-sh upstream bot/CI 验证最终 patch set，按用户确认的方案新建了一个专门的 upstream 验证 PR：

- PR：[volcano-sh/agentcube#390](https://github.com/volcano-sh/agentcube/pull/390)
- Title：`[DO NOT MERGE] validation for PR #387 with review fixes`
- Branch：`ranxi2001:test/pr387-with-review-fixes`
- Base：`volcano-sh/agentcube:main`
- Commits：
  - `2c93451 fix: adapt code interpreter warm pool to agent-sandbox v0.4.6`
  - `6f94052 fix: address agent-sandbox adaptation review feedback`

这个 PR 与 #387 的关系：

- #390 不是最终贡献 PR，不应 review / merge。
- #390 只用于让 upstream bot 跑“#387 原始适配 + review/CI 修复”的最终组合。
- 如果 #390 CI 通过，再把 `6f94052` 对应修复 clean cherry-pick / squash 回 #387 原分支，然后关闭 #390。

创建后初始 check 状态：

- 已通过：`DCO`、`Python Lint`、`Check for spelling errors`
- 正在运行：`coverage`、`golangci-lint`、`Codegen Check`、`build`、`e2e-test`、`python-sdk-tests`、`Approve workflows based on contributor status`

## Upstream Validation PR #390 Review Triage

用户提醒不要急着把 #390 的结果回灌到 #387，因为 #390 上 Copilot / Gemini 又生成了新的 review comments。先重新读取 #390 的完整 review comments、issue comments 和 check-run 状态。

本次使用命令：

```bash
python3 .agents/skills/agentcube-pr-management/scripts/pr_status.py 390
```

并通过 GitHub API 读取：

```text
/repos/volcano-sh/agentcube/pulls/390/comments
/repos/volcano-sh/agentcube/issues/390/comments
/repos/volcano-sh/agentcube/commits/6f940521a378efe770372f2736b813b44b97e689/check-runs
```

最新 CI 状态：

| Check | 结果 |
| --- | --- |
| `DCO` | success |
| `Python Lint` | success |
| `Check for spelling errors` | success |
| `Codegen Check` | success |
| `build` | success |
| `coverage` | success |
| `golangci-lint` | success |
| `e2e-test` | success |
| `python-sdk-tests` | success |
| `Approve workflows based on contributor status` | success |

结论：#390 已证明“#387 原始适配 + 第一轮 review/CI 修复”的组合能通过 upstream CI，包括原先失败的 `coverage`、`golangci-lint` 和完整 `e2e-test`。但是 CI 绿不代表可以直接回灌，因为 review comments 里有 3 条确实指出了健壮性问题。

新增 review comments 共 5 条：

| 来源 | 文件 | 结论 | 处理建议 |
| --- | --- | --- | --- |
| Gemini | `client-go/clientset/versioned/fake/clientset_generated.go` | 误报。Gemini 认为方法应为 `IsWatchListSemanticsUnsupported`，但 `k8s.io/client-go@v0.35.4/util/watchlist/watch_list.go` 的接口就是 `IsWatchListSemanticsUnSupported() bool`，`k8s.io/code-generator@v0.35.4` 生成器也生成这个拼写。 | 不手改生成代码的方法名；否则反而会破坏 client-go optional interface 匹配，并可能导致 `make gen-check` 回退。 |
| Copilot | `client-go/clientset/versioned/fake/clientset_generated.go` | 低价值生成代码注释问题。comment 写 `IsWatchListSemanticsSupported`，方法名是 `IsWatchListSemanticsUnSupported`，确实读起来不一致；但这段来自 Kubernetes code-generator 生成输出。 | 不在 AgentCube PR 手改生成文件；如要修应先确认 upstream code-generator 是否也有同样注释问题。 |
| Gemini | `pkg/workloadmanager/handlers.go` `waitForDirectSandboxReady` | 有效。当前已经有 `resultChan == nil` guard，但如果 channel 被关闭或发送了 `SandboxStatusUpdate{Sandbox:nil}`，仍会在日志行解引用 `createdSandbox.Namespace` 时 panic。 | 增加 `result, ok := <-resultChan` 检查和 `result.Sandbox == nil` 检查；补 focused unit tests，证明 closed channel / nil sandbox 不 panic 且返回明确错误。 |
| Gemini | `pkg/workloadmanager/handlers.go` `waitForClaimSandboxReady` | 有效但低风险。当前 `getSandboxClaim` 返回 context error 时不会 log，随后通常会在 `select { case <-ctx.Done(): ... }` 返回，但语义依赖下一段 select。 | 在 `getSandboxClaim` 返回 context error 时立即 return，减少取消后的额外处理；保持和 `getSandbox` 分支一致。 |
| Gemini | `hack/update-codegen.sh` | 有效。当前 `sed` 解析 `go mod download -json` 的 `"Dir": "...",` 依赖尾随逗号，如果 Go JSON 字段顺序或格式变化会拿不到 path。 | 改成不依赖尾随逗号的 pattern：`sed -n 's/^[[:space:]]*"Dir": "\([^"]*\)".*/\1/p'`。 |

验证 WatchList 评论的本地证据：

```bash
rg -n "IsWatchListSemanticsUnSupported|IsWatchListSemanticsUnsupported|watchListUnsupportedInterface" \
  /root/go/pkg/mod/k8s.io/client-go@v*/ \
  /root/go/pkg/mod/k8s.io/code-generator@v*/cmd/client-gen/generators/fake
```

关键结果：

```text
/root/go/pkg/mod/k8s.io/client-go@v0.35.4/util/watchlist/watch_list.go:85: IsWatchListSemanticsUnSupported() bool
/root/go/pkg/mod/k8s.io/client-go@v0.35.4/kubernetes/fake/clientset_generated.go:198: func (c *Clientset) IsWatchListSemanticsUnSupported() bool {
/root/go/pkg/mod/k8s.io/code-generator@v0.35.4/cmd/client-gen/generators/fake/generator_fake_for_clientset.go:221: func (c *Clientset) IsWatchListSemanticsUnSupported() bool {
```

因此 Gemini 的 `critical` 评级不成立。正确策略是不要为了 AI comment 修改 Kubernetes 生成代码的方法名。

Codecov issue comment：

```text
Patch coverage is 66.37168% with 38 lines in your changes missing coverage.
Project coverage is 58.72%.
```

这不是 GitHub check failure；#390 的 `coverage` check-run 已经是 success。作为最终 #387 的 review 材料，可以说明项目覆盖率相对 base 是提升的，但仍要承认 patch coverage 中 `pkg/workloadmanager/handlers.go` 和 `pkg/workloadmanager/k8s_client.go` 有未覆盖分支。

当前决策：

1. 暂不把 #390 回灌到 #387。
2. 先在验证分支修复 3 条有效 Gemini comment：closed/nil ready channel、claim wait context cancellation、codegen sed parsing。
3. 不处理生成 client 方法名，不手改 Kubernetes code-generator 输出。
4. 修复后再次让 #390 跑 upstream CI；如果仍全绿，再把经过验证的最终修复 clean cherry-pick / squash 回 #387。

## PR Workflow Retrospective

#390 暴露了 upstream 协作流程上的问题。虽然它成功跑通了 CI，但它不应该作为默认验证手段直接提交到 `volcano-sh/agentcube`，因为 upstream PR 会通知社区、触发 reviewer/bot 流程，并占用维护者注意力。后续必须把“能否技术上提交”与“是否应该打扰社区”分开判断。

需要固化的规则：

1. 创建 upstream PR、draft PR、WIP PR、issue、comment、review comment、`/assign`、request review 或 mention 维护者之前，必须先让用户确认目标、标题、完整 body/comment、diff summary、测试结果和为什么现在需要 upstream 介入。
2. upstream PR 必须使用 `.github/PULL_REQUEST_TEMPLATE.md`，包括 draft 和 WIP。不能为了临时验证自拟 PR body。
3. 如果确实需要 upstream 看到未完成工作，标题用 `[WIP] <title>`，不要用 `[DO NOT MERGE]`。
4. 只为了跑 CI 或验证 bot 的场景，优先使用 fork branch、fork PR、fork Actions 或本地测试；不要把 upstream PR 当 disposable CI runner。
5. 阅读、分析、复现别人的 PR 时，默认把证据写入本地报告；除非维护者确实需要验证或用户明确批准，不直接在社区评论。
6. 提交 upstream PR 要更谨慎：PR 是协作请求，不只是测试工具。没有准备好让维护者 review 的内容，就不要进入 upstream 队列。

还需要更正前面关于“不要在一个 PR 反复更新”的理解：这不是机械规则。属于当前 PR 引入的 bug、review feedback 或测试缺口，可以在 fork 验证后 clean update 当前 PR。真正需要拆出去的是独立前置条件或仓库级兼容性变化。

本次 `golangci-lint` / `coverage` 的 Go 版本问题更接近独立前置条件：`agent-sandbox v0.4.6` 要求更高 Go 版本，但 Go/toolchain 升级本身不应该继承 agent-sandbox 适配分支的复杂 diff。更干净的做法是：

1. 从最新 `upstream/main` 新建纯净 Go/toolchain upgrade 分支。
2. 只更新原始项目为了使用新 Go 版本所需的 `go.mod` / workflow / lint 或 toolchain 文件。
3. 证明没有 agent-sandbox 适配改动时，原始 AgentCube 项目在新 Go 版本下也能 build / test / lint / e2e。
4. 该前置 PR 合并后，再让 #387 的 agent-sandbox 适配分支 rebase 到新的 `main`，自然继承新的 Go 基线。

这样拆分的目的不是避免更新 PR，而是保持主仓库历史干净：先证明原始项目能跑新 Go，再证明 agent-sandbox 适配能跑在这个新基线上。

已更新的长期规则文件：

- `.agents/skills/agentcube-pr-management/SKILL.md`
- `AGENTS.md`
- `internship-reports/open-source-contribution-format-standard.md`

## Pure Go Toolchain Upgrade Validation - Initial 1.26.2 Trial

根据纠偏后的策略，先不继续在 #387 / #390 上混合处理 Go/toolchain 问题，而是从最新 `upstream/main` 单独创建纯净 Go/toolchain upgrade 分支，证明原始 AgentCube 项目不带 `agent-sandbox v0.4.6` 适配时也能在新 Go 版本下跑通。

本地 worktree：

```text
/home/agentcube-go-toolchain-upgrade
```

分支和 commit：

```text
branch: chore/go-1.26-toolchain
base: upstream/main 0fd9151
commit: ff12042 chore: update Go toolchain to 1.26.2
```

改动范围保持为工具链基线，不包含 agent-sandbox 依赖升级或业务代码改动：

- `go.mod`：`go 1.24.4` -> `go 1.26.2`，`go mod tidy` 移除了冗余的 `toolchain go1.24.9`。
- `.github/workflows/build-push-release.yml`
- `.github/workflows/codegen-check.yml`
- `.github/workflows/e2e.yml`
- `.github/workflows/lint.yml`
- `.github/workflows/test-coverage.yml`
- `docker/Dockerfile`
- `docker/Dockerfile.router`
- `docker/Dockerfile.picod`

本地验证：

```bash
export PATH=/root/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.2.linux-amd64/bin:$PATH
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
make build-all
make lint
make gen-check
docker build -f docker/Dockerfile -t agentcube-go126-workloadmanager:test .
docker build -f docker/Dockerfile.router -t agentcube-go126-router:test .
docker build -f docker/Dockerfile.picod -t agentcube-go126-picod:test .
git diff --check
```

结果：

- 非 e2e Go packages：通过。
- race coverage：通过。
- `make build-all`：通过。
- `make lint`：通过，说明 `golangci-lint` 在 Go 1.26.2 环境下可正常运行。
- `make gen-check`：提交后在 clean tree 上通过，没有生成代码漂移。
- 三个 Docker image build：通过。
- `git diff --check`：通过。

一次中间现象：

```bash
make gen-check
```

在提交前返回 exit code 2，因为 `gen-check` 最后执行 `git diff --exit-code`，会把尚未提交的 Go/toolchain 改动也当成 diff。检查 `client-go`、`pkg/apis` 和 CRD 后未发现生成代码漂移；提交 `ff12042` 后重新运行 `make gen-check` 通过。因此这不是 codegen 失败。

fork staging / pre-review PR：

- Fork PR：[ranxi2001/agentcube#2](https://github.com/ranxi2001/agentcube/pull/2)
- Title：`chore: update Go toolchain to 1.26.2`
- Base：`ranxi2001:release-go126-ci-base`，精确指向 `upstream/main 0fd9151`
- Head：`ranxi2001:chore/go-1.26-toolchain`
- 用途：先在自己的 fork 仓库做正式预检和 CI 验证，不请求 upstream review，不创建 volcano-sh upstream PR。

fork CI 最终结果：

| Check | Result |
| --- | --- |
| `Check for spelling errors` | success |
| `Codegen Check` | success |
| `Python Lint` | success |
| `build` | success |
| `coverage` | success |
| `e2e-test` | success |
| `golangci-lint` | success |
| `python-sdk-tests` | success |

结论：原始 AgentCube 项目在 Go 1.26.2 基线上可以通过本地核心验证和 fork CI，包括 e2e。下一步如果要提交 upstream Go/toolchain upgrade PR，应先准备官方 PR template body 给用户确认；确认后再提交 upstream。#387 的 agent-sandbox 适配应在该 Go/toolchain 前置 PR 合入后 rebase 到新的 `main`。

后续 mentor review 指出两点需要修正：

1. 如果已经要升级 Go，不应只选依赖要求的最低版本 `1.26.2`，应先核对当前稳定版。
2. 后续版本管理要减少重复维护，参考 Karmada workflow 的 `go-version-file: go.mod` 写法，让 GitHub Actions 从 `go.mod` 读取 Go 版本，而不是多个 workflow 各自写死版本。

因此 #2 作为初始 trial 已关闭并标记 superseded，不再作为 upstream PR 材料。

## Pure Go Toolchain Upgrade Validation - Revised 1.26.4

按 mentor 建议重新从 `upstream/main` 创建纯净分支，目标改为当前稳定 Go patch 版本，并把 workflow Go 版本管理收敛到 `go.mod`。

外部版本依据：

- Official Go release feed：`go1.26.4`，release time `2026-05-29T15:26:39Z`。
- Karmada workflow reference：`actions/setup-go` 使用 `go-version-file: go.mod`。

本地 worktree：

```text
/home/agentcube-go-toolchain-upgrade
```

分支和 commit：

```text
branch: chore/go-stable-toolchain
base: upstream/main 0fd9151
commit: 3f1a823 chore: update Go toolchain to 1.26.4
```

改动范围：

- `go.mod`：`go 1.24.4` -> `go 1.26.4`；`go mod tidy` 移除了冗余的 `toolchain go1.24.9`，最终只保留一个 Go 版本源。
- `.github/workflows/build-push-release.yml`
- `.github/workflows/codegen-check.yml`
- `.github/workflows/e2e.yml`
- `.github/workflows/lint.yml`
- `.github/workflows/test-coverage.yml`
- `docker/Dockerfile`
- `docker/Dockerfile.router`
- `docker/Dockerfile.picod`

workflow 改动不是简单把所有文件从 `1.26.2` 替换成 `1.26.4`，而是改成：

```yaml
with:
  go-version-file: go.mod
```

这样 CI 的 Go 版本以后跟随 `go.mod`，避免再次出现 `go.mod`、lint、coverage、e2e、codegen workflow 各自漂移的问题。Docker builder image 仍需显式更新，因为 Dockerfile 不能自动读取 `go.mod`。

本地验证：

```bash
export PATH=/root/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.2.linux-amd64/bin:$PATH
export GOTOOLCHAIN=go1.26.4
go version
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
make build-all
make lint
make gen-check
docker build -f docker/Dockerfile -t agentcube-go1264-workloadmanager:test .
docker build -f docker/Dockerfile.router -t agentcube-go1264-router:test .
docker build -f docker/Dockerfile.picod -t agentcube-go1264-picod:test .
git diff --check
```

结果：

- `go version`：`go version go1.26.4 linux/amd64`。
- 非 e2e Go packages：通过。
- race coverage：通过，`pkg/workloadmanager` summary coverage `24.1%`，整体命令 exit code 0。
- `make build-all`：通过。
- `make lint`：通过。
- `make gen-check`：提交后 clean tree 通过，无 CRD / client-go 生成漂移。
- 三个 Docker image build：通过，确认 `golang:1.26.4` / `golang:1.26.4-alpine` builder 镜像可用。
- `git diff --check`：通过。

一次中间现象：

```bash
make gen-check
```

在提交前仍返回 exit code 2，原因同初始 trial：`gen-check` 最后执行 `git diff --exit-code`，会把尚未提交的 9 个计划内文件差异当作失败。提交 `3f1a823` 后重新运行 `make gen-check` 通过，说明没有生成文件额外漂移。

修正后的 fork validation PR：

- Fork PR：[ranxi2001/agentcube#3](https://github.com/ranxi2001/agentcube/pull/3)
- Title：`chore: update Go toolchain to 1.26.4`
- Base：`ranxi2001:release-go126-ci-base`，精确指向 `upstream/main 0fd9151`
- Head：`ranxi2001:chore/go-stable-toolchain`
- 用途：在自己的 fork 仓库验证纯净 Go/toolchain PR，不请求 upstream review，不触发 upstream 社区流程。

fork CI 最终结果：

| Check | Result |
| --- | --- |
| `Check for spelling errors` | success |
| `Codegen Check` | success |
| `Python Lint` | success |
| `build` | success |
| `build` | success |
| `coverage` | success |
| `e2e-test` | success |
| `golangci-lint` | success |
| `python-sdk-tests` | success |

结论：原始 AgentCube 项目在 Go 1.26.4 基线上可以通过本地核心验证、Docker builder 验证和 fork CI，包括 e2e、coverage、golangci-lint 与 codegen。下一步如果要提交 upstream Go/toolchain upgrade PR，应以 #3 的 diff 和官方 PR template body 为基础，先给用户确认完整内容；确认前不创建 `volcano-sh/agentcube` upstream PR。

## Upstream Go Toolchain PR

用户确认 PR title 和官方模板正文后，已创建 upstream PR：

- PR：[volcano-sh/agentcube#391](https://github.com/volcano-sh/agentcube/pull/391)
- Title：`chore: update Go toolchain to 1.26.4`
- Type：`/kind cleanup`
- Branch：`ranxi2001:chore/go-stable-toolchain`
- Base：`volcano-sh/agentcube:main`
- Commit：`3f1a823 chore: update Go toolchain to 1.26.4`
- DCO：commit 已包含 `Signed-off-by: ranxi2001 <ranxi169@163.com>`

创建后初始状态：

- PR open，非 draft。
- Label：`kind/cleanup`。
- `DCO`：success。
- `Approve workflows based on contributor status`：success。
- `python-sdk-tests`：success。
- 其余 checks 创建后正在运行：`Check for spelling errors`、`Codegen Check`、`Python Lint`、两个 `build`、`coverage`、`e2e-test`、`golangci-lint`。

注意：这次 PR 是正式 upstream contribution，不是 disposable CI validation；此前已用 fork PR #3 跑通过同一 commit 的完整 CI。

最终 check 状态：

| Check | Result |
| --- | --- |
| `DCO` | success |
| `Approve workflows based on contributor status` | success |
| `Check for spelling errors` | success |
| `Codegen Check` | success |
| `Python Lint` | success |
| `build` | success |
| `build` | success |
| `coverage` | success |
| `e2e-test` | success |
| `golangci-lint` | success |
| `python-sdk-tests` | success |

新增评论：

- `volcano-sh-bot`：流程状态，PR 尚未 approved；获得 review / `lgtm` 后再 assign `hzxuzhonghu` approval。
- `codecov-commenter`：coverage 报告为成功，提示 “All modified and coverable lines are covered by tests.”
- `gemini-code-assist[bot]`：review 结论为 “no feedback to provide”，没有需要处理的技术评论。
- `Copilot`：建议顺手把 `build-push-release.yml` 中 `actions/checkout@v3`、`actions/setup-go@v4` 升到当前 major 版本，避免 Node16 action deprecation。当前判断：这是 GitHub Actions runtime modernization，不是 Go version drift 的必要修复；#391 已通过 CI，暂不直接扩大 PR 范围，后续如 maintainer 认可可作为 follow-up 或在用户确认后追加。

已回复 Copilot：同意 action runtime modernization 有价值，但本 PR 保持聚焦于 Go toolchain 和 `go.mod` 作为 Go version source of truth；`checkout` / `setup-go` major version 升级可作为独立 cleanup follow-up。

## PR #391 Merged

PR #391 已合并，这是本阶段一个关键里程碑：AgentCube upstream `main` 已接受独立 Go/toolchain 前置升级，后续 `agent-sandbox v0.4.6` 适配可以基于新的 Go 1.26.4 baseline rebase，而不需要在 #387 中混入通用工具链升级。

合并信息：

- PR：[volcano-sh/agentcube#391](https://github.com/volcano-sh/agentcube/pull/391)
- State：closed / merged
- Merged at：`2026-06-18T06:37:52Z`
- Merged by：`volcano-sh-bot`
- Approved by：`RainbowMango`
- Review command：`/lgtm /approve`
- Merge commit：`a31651e5aba6ab0ce6ef854ffdb724146b40af5b`
- Original head commit：`3f1a82379b02d7d1acd6d0f94ecfa7f496c0cb9a`
- Final labels：`lgtm`、`approved`、`kind/cleanup`、`size/S`

维护者评价：

```text
/lgtm
/approve

Good job! Thanks.
```

后续影响：

1. `agent-sandbox v0.4.6` 适配 PR #387 可以在修复自身 review comments 后 rebase 到包含 #391 的 upstream `main`。
2. #387 中不再需要承担通用 Go/toolchain 升级职责，scope 可以回到 agent-sandbox compatibility 本身。
3. Copilot 提到的 GitHub Actions runtime modernization 仍是可选独立 cleanup，不应自动追加到已合并的 #391。

## PR #387 Rebase Validation After #391

目的：验证 #391 合并后，#387 是否只需要 rebase 到最新 `upstream/main` 就能自然解决 CI / review 问题。

本地验证分支：

- Worktree：`/home/agentcube-agent-sandbox-latest`
- Branch：`rebase/pr387-on-go1264`
- Base：`upstream/main a31651e`，即 #391 merge commit
- 原始 PR branch：`origin/feat/agent-sandbox-latest`
- Rebased adaptation commit：`9c6dff6 fix: adapt code interpreter warm pool to agent-sandbox v0.4.6`

直接 rebase 过程：

```bash
git switch -C rebase/pr387-on-go1264 origin/feat/agent-sandbox-latest
git rebase upstream/main
```

冲突只发生在 Go/toolchain 相关文件：

- `go.mod`
- `docker/Dockerfile`
- `docker/Dockerfile.router`
- `docker/Dockerfile.picod`

解决方式：保留 upstream #391 的 Go `1.26.4` / Docker builder `1.26.4` 基线，不回退到 #387 原始试验里的 `1.26.2`。

直接 rebase 后验证结果：

```bash
go version
go test ./pkg/workloadmanager -count=1
make lint
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
```

结果：

- `go version`：`go version go1.26.4 linux/amd64`
- `go test ./pkg/workloadmanager -count=1`：通过
- coverage exact command：通过，`pkg/workloadmanager` summary coverage `25.9%`
- `make lint`：失败

`make lint` 失败点：

```text
pkg/workloadmanager/handlers.go:85:1: cyclomatic complexity 16 of func `(*Server).handleSandboxCreate` is high (> 15)
pkg/workloadmanager/handlers_test.go:112:27: Error return value of `f.fakeStore.UpdateSandbox` is not checked
pkg/workloadmanager/handlers_test.go:348:16: forcetypeassert: unchecked type assertion
test/e2e/e2e_test.go:1212:1: cyclomatic complexity 16 of func `(*e2eTestContext).listWarmPoolPods` is high (> 15)
```

结论：#391 / rebase 已经解决 Go toolchain mismatch 和 workflow baseline 问题；但不能自动解决 #387 自身代码质量和 review feedback。#387 仍需要一个 review-fix commit。

本地补丁 commit：

- Commit：`5867183 fix: address agent-sandbox adaptation review feedback`
- DCO：已包含 `Signed-off-by`
- 当前仅存在于本地验证分支，尚未 push，也没有更新 #387

补丁内容：

- 拆出 `respondSandboxCreateError`，降低 `handleSandboxCreate` cyclomatic complexity。
- `waitForDirectSandboxReady` 增加 nil watcher、closed channel、nil sandbox 防护，并把这些内部错误对外统一隐藏为 `internal server error`。
- `waitForClaimSandboxReady` 遇到 `context.Canceled` / `context.DeadlineExceeded` 立即返回，不再等到下一轮 select。
- `recordingStore.UpdateSandbox` 正确检查 fake store error，并 deep copy `EntryPoints`。
- fake dynamic client reactor 使用 checked type assertion。
- e2e warm-pool pod matching 改为用 Sandbox UID 识别 Sandbox-owned Pod，避免只按 name 匹配。
- `hack/update-codegen.sh` 的 `sed` 解析不再依赖 `"Dir"` 行尾必须有逗号。

修复后验证：

```bash
go test ./pkg/workloadmanager -count=1
make lint
go test -race ./pkg/workloadmanager -count=1
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
make gen-check
go test ./test/e2e -run '^$' -count=1
make build-all
git diff --check
git diff --exit-code
```

结果：

- `go test ./pkg/workloadmanager -count=1`：通过
- `make lint`：通过
- `go test -race ./pkg/workloadmanager -count=1`：通过
- coverage exact command：通过，`pkg/workloadmanager` summary coverage `26.3%`
- 非 e2e Go packages：通过
- `make gen-check`：提交后通过，无生成漂移
- `go test ./test/e2e -run '^$' -count=1`：通过，只验证 e2e package 编译
- `make build-all`：通过
- `git diff --check` / `git diff --exit-code`：通过，工作区干净

一次中间现象：

```bash
make gen-check
```

在本地 fix commit 前返回 exit code 2，因为 `gen-check` 最后执行 `git diff --exit-code`，会把 4 个尚未提交的计划内修复文件视为失败。提交 `5867183` 后重跑通过，说明没有额外 CRD / client-go / go.mod 生成漂移。

当前判断：

1. 可以把 #387 原始分支 rebase 到 `upstream/main a31651e`，但 rebase 本身只解决工具链基线，不足以让 PR 全绿。
2. 正确回灌路径是把 `9c6dff6` 和 `5867183` 整理为 clean history 后，在用户确认后更新 `origin/feat/agent-sandbox-latest`，从而更新 upstream PR #387。
3. 在用户确认前，不 push 本地验证分支，也不 force-push 打开的 #387 分支，避免不必要地打扰维护者。

## Fork CI Validation For PR #387 Rebase Path

目的：先在自己的 fork 仓库验证 `rebase/pr387-on-go1264`，不直接更新 upstream PR #387。

Fork PR：

- PR：[ranxi2001/agentcube#4](https://github.com/ranxi2001/agentcube/pull/4)
- Title：`test: validate PR 387 rebase on Go 1.26.4`
- Base：`release-pr387-go1264`，指向 `a31651e5aba6ab0ce6ef854ffdb724146b40af5b`
- Head：`ci/pr387-rebase-go1264`，指向 `58671839c80bb3716146c88de0b5f7ab119b749f`
- Mergeable state：`clean`
- Scope：fork-only CI validation，不请求 upstream review，不更新 #387

一次流程修正：

最初 fork PR 的 base 是 `ci/pr387-base-go1264`。这只触发了没有 branch filter 的 `Test Coverage` 和 `Python SDK Tests`。原因是 AgentCube 多数 PR workflow 只匹配 base branch `main` 或 `release-*`：

- `Agentcube CI Workflow`
- `Agentcube E2E Tests`
- `Lint`
- `Codegen Check`
- `Codespell`
- `Copyright Check`
- `Python Lint`

为了在 fork 内跑完整 CI，又不污染 fork `main`，改用 base branch `release-pr387-go1264`，仍指向同一个 upstream #391 merge commit。`build-push-release.yml` 只在 push `main` 或 tag 时运行，因此这个 `release-*` base 不会触发发布镜像流程。修改 base 后 close/reopen fork PR 触发完整 `pull_request` workflow。

最终 fork CI 结果：

| Workflow / Check | Result |
| --- | --- |
| `Codespell` / `Check for spelling errors` | success |
| `Python SDK Tests` / `python-sdk-tests` | success |
| `Python Lint` | success |
| `Copyright Check` | success |
| `Codegen Check` | success |
| `Agentcube CI Workflow` / two `build` jobs | success |
| `Lint` / `golangci-lint` | success |
| `Test Coverage` / `coverage` | success |
| `Agentcube E2E Tests` / `e2e-test` | success |

结论：`upstream/main a31651e` + #387 rebased adaptation + `5867183` review-fix commit 已在 fork CI 中完整通过，包括 e2e、coverage、golangci-lint、codegen、build 和 spelling checks。下一步可以准备在用户确认后 clean-update upstream PR #387。

## Upstream PR #387 Updated

用户确认后，已更新 upstream PR #387：

- PR：[volcano-sh/agentcube#387](https://github.com/volcano-sh/agentcube/pull/387)
- Branch：`ranxi2001:feat/agent-sandbox-latest`
- Old head：`531635840f56845c4dc1435e9f3f2849e9287077`
- New head：`58671839c80bb3716146c88de0b5f7ab119b749f`
- Base：`a31651e5aba6ab0ce6ef854ffdb724146b40af5b`，即 #391 合并后的 Go 1.26.4 baseline
- Push command：`git push --force-with-lease=refs/heads/feat/agent-sandbox-latest:531635840f56845c4dc1435e9f3f2849e9287077 origin HEAD:refs/heads/feat/agent-sandbox-latest`

PR body 已按用户要求编辑：

- 删除旧的 `Go 1.26.2` / “requires Go 1.26.2” / Docker builder Go 版本问题描述。
- 保留 agent-sandbox / Kubernetes / controller-runtime dependency stack 影响说明。
- 加入 fork CI validation PR #4 和本地验证命令。
- 保持官方 PR template 结构和 release-note block。

最终 upstream checks：

| Check | Result |
| --- | --- |
| `DCO` | success |
| `Approve workflows based on contributor status` | success |
| `Check for spelling errors` | success |
| `Codegen Check` | success |
| `Python Lint` | success |
| `build` | success |
| `build` | success |
| `coverage` | success |
| `e2e-test` | success |
| `golangci-lint` | success |
| `python-sdk-tests` | success |

当前状态：测试和自动检查已全绿；GitHub API `mergeable_state` 仍显示 `unstable`，预期是因为还需要 maintainer review / `lgtm` / `approve` / tide 门禁，不是测试失败。

## PR #387 Human Comment: Label And v0.5.0rc1 Scope

评论链接：[#387 comment 4739375180](https://github.com/volcano-sh/agentcube/pull/387#issuecomment-4739375180)

评论者：`zhzhuang-zju`

评论核心问题：

1. #387 看起来更像 feature，而不是 bug fix，需要确认并更新 label。
2. PR body 中写到“不适配 `v0.5.0rc1` 是因为 Go resolves that tag to a pseudo-version rather than the stable latest release”，需要解释具体在哪一步会成为问题。
3. `agent-sandbox v0.5.0rc1` 引入了 substantial changes；如果未来正式发布 `v0.5.0`，可能又需要新一轮适配。

### AgentCube Source Dependency Points

本轮按源码阅读，不只从版本号推断。

AgentCube 当前 #387 head `5867183` 的关键依赖点：

- `pkg/workloadmanager/workload_builder.go:175-204`：direct `Sandbox` 创建使用 `agents.x-k8s.io/v1alpha1`，并设置 `SandboxSpec.Replicas = 1`。
- `pkg/workloadmanager/workload_builder.go:214-234`：warm-pool `SandboxClaim` 创建使用 `extensions.agents.x-k8s.io/v1alpha1`，并设置 `SandboxClaimSpec.TemplateRef.Name = CodeInterpreter name`。
- `pkg/workloadmanager/informers.go:42-50`：dynamic client GVR 固定为 `sandboxes` / `sandboxclaims` 的 `v1alpha1`。
- `pkg/workloadmanager/codeinterpreter_controller.go:154-162`：CodeInterpreter controller 创建 `SandboxTemplate`，并显式设 `networkPolicyManagement: Unmanaged`。
- `pkg/workloadmanager/codeinterpreter_controller.go:212-222`：CodeInterpreter controller 创建 `SandboxWarmPool`，`TemplateRef.Name = CodeInterpreter name`。
- `pkg/workloadmanager/handlers.go:257-274`：创建 claim 后轮询 `SandboxClaim.Status.SandboxStatus.Name`，再 fetch adopted Sandbox 并等待 Ready。
- `pkg/workloadmanager/handlers.go:327-336`：通过 `sandboxv1alpha1.SandboxPodNameAnnotation` 找 warm pool adopted Pod name，再探测 Pod IP / entrypoint。

这说明 #387 的 v0.4.6 适配依赖的是 `v1alpha1 SandboxClaim -> TemplateRef -> controller adopt/cold-create -> Status.SandboxStatus.Name` 这条链路。

### Module Resolution Evidence

新脚本：

```bash
python3 .agents/skills/agentcube-pr-management/scripts/audit_go_module_version.py \
  sigs.k8s.io/agent-sandbox latest v0.5.0rc1 \
  --show-versions \
  --packages api/v1alpha1 extensions/api/v1alpha1 api/v1beta1 extensions/api/v1beta1
```

结果摘要：

```text
go list -m -versions sigs.k8s.io/agent-sandbox
=> ... v0.4.5 v0.4.6

sigs.k8s.io/agent-sandbox@latest
=> Version: v0.4.6
=> api/v1alpha1: present
=> extensions/api/v1alpha1: present
=> api/v1beta1: missing
=> extensions/api/v1beta1: missing

sigs.k8s.io/agent-sandbox@v0.5.0rc1
=> Version: v0.4.7-0.20260608211546-6af1bbd0cf64
=> Origin hash: 6af1bbd0cf64256ddf099e5a6ee1cbed17298057
=> api/v1alpha1: missing
=> extensions/api/v1alpha1: missing
=> api/v1beta1: present
=> extensions/api/v1beta1: present
```

补充确认：

```bash
git ls-remote --tags https://github.com/kubernetes-sigs/agent-sandbox.git 'refs/tags/v0.5.0rc1*'
```

输出显示 `v0.5.0rc1` 是一个 Git tag，peeled commit 是 `6af1bbd0cf64256ddf099e5a6ee1cbed17298057`。但它不是 Go canonical prerelease tag 形式（例如 `v0.5.0-rc.1`），所以 Go module 解析为 pseudo-version，并且不出现在 `go list -m -versions` 列表中。

结论：pseudo-version 不是唯一阻塞点，只是说明它不是当前稳定 `@latest` 的 Go module release。更重要的是 rc1 源码已经迁到 `v1beta1`，移除了 AgentCube 当前依赖的 `v1alpha1` package。

### API Shape Differences

`agent-sandbox v0.4.6`:

- `api/v1alpha1/sandbox_types.go:132-139`：`SandboxSpec` 有 `Replicas *int32`，只允许 `0/1`。
- `extensions/api/v1alpha1/sandboxclaim_types.go:125-140`：`SandboxClaimSpec` 有 required `TemplateRef`，同时有 optional `WarmPool *WarmPoolPolicy`，可表达 `none/default/specific pool`。

`agent-sandbox v0.5.0rc1` resolved pseudo-version:

- `api/v1beta1/sandbox_types.go:139-173`：`Replicas` 被移除，替换为 `OperatingMode`，取值 `Running` / `Suspended`。
- `extensions/api/v1beta1/sandboxclaim_types.go:84-111`：`SandboxClaimSpec` 不再有 `TemplateRef` / `WarmPoolPolicy`，改为 required `WarmPoolRef`。

这会直接影响 AgentCube 两条创建路径：

1. Direct AgentRuntime / no-warm-pool CodeInterpreter sandbox：不能继续设置 `Spec.Replicas = 1`，需要改成 `OperatingMode: Running`，同时 GVR / TypeMeta / scheme 都要迁到 `v1beta1`。
2. Warm-pool CodeInterpreter claim：不能继续只把 `SandboxTemplate` 名称写入 `SandboxClaim.Spec.TemplateRef`，必须改成引用一个具体 `SandboxWarmPool`。

### Controller Behavior Differences

`v0.4.6` 的 claim controller 行为：

- `extensions/controllers/sandboxclaim_controller.go:1146-1170`：先根据 `WarmPoolPolicy` 尝试 warm pool adoption；如果没有候选 sandbox，返回 nil，让 caller 继续 cold create。
- `extensions/controllers/sandboxclaim_controller.go:1173-1188`：`getTemplate()` 直接按 `claim.Spec.TemplateRef.Name` 获取 `SandboxTemplate`。

`v0.5.0rc1` 的 claim controller 行为：

- `extensions/controllers/sandboxclaim_controller.go:1406-1429`：`getTemplate()` 先按 `claim.Spec.WarmPoolRef.Name` 获取 `SandboxWarmPool`，再从 warm pool 的 `Spec.TemplateRef.Name` 找 `SandboxTemplate`。
- 如果 warm pool 不存在，返回 `ErrWarmPoolNotFound`，并在 controller 上层作为 dependency missing 处理。
- 这意味着 rc1 语义是“claim checkout from a specific warm pool”。它不再是 #387 依赖的“claim references template, optionally adopt from matching/default warm pool, otherwise cold create”模型。

### Local rc1 Bump Experiment

实验分支：`analysis/pr387-agent-sandbox-v050rc1`，未 push，实验后已恢复工作区。

直接升级并 tidy：

```bash
go get sigs.k8s.io/agent-sandbox@v0.5.0rc1
go mod tidy
```

失败：

```text
go: upgraded sigs.k8s.io/agent-sandbox v0.4.6 => v0.4.7-0.20260608211546-6af1bbd0cf64
go: github.com/volcano-sh/agentcube/cmd/agentd imports
    sigs.k8s.io/agent-sandbox/api/v1alpha1: package .../api/v1alpha1 provided by sigs.k8s.io/agent-sandbox at latest version v0.4.6 but not at required version v0.4.7-0.20260608211546-6af1bbd0cf64
go: github.com/volcano-sh/agentcube/cmd/workload-manager imports
    sigs.k8s.io/agent-sandbox/extensions/api/v1alpha1: package .../extensions/api/v1alpha1 provided by sigs.k8s.io/agent-sandbox at latest version v0.4.6 but not at required version v0.4.7-0.20260608211546-6af1bbd0cf64
```

继续做机械 import 迁移（仅实验，不保留）：

```bash
perl -pi -e 's#sigs\.k8s\.io/agent-sandbox/api/v1alpha1#sigs.k8s.io/agent-sandbox/api/v1beta1#g; s#sigs\.k8s\.io/agent-sandbox/extensions/api/v1alpha1#sigs.k8s.io/agent-sandbox/extensions/api/v1beta1#g' $(rg -l 'sigs.k8s.io/agent-sandbox/(api|extensions/api)/v1alpha1' cmd pkg test)
go test ./pkg/workloadmanager -count=1
```

失败：

```text
pkg/workloadmanager/workload_builder.go:203:4: unknown field Replicas in struct literal of type ".../api/v1beta1".SandboxSpec
pkg/workloadmanager/workload_builder.go:231:4: unknown field TemplateRef in struct literal of type ".../extensions/api/v1beta1".SandboxClaimSpec
pkg/workloadmanager/workload_builder_test.go:185:17: claim.Spec.TemplateRef undefined
pkg/workloadmanager/workload_builder_test.go:680:16: claim.Spec.TemplateRef undefined
```

这说明 `v0.5.0rc1` 适配不是“把 import 从 v1alpha1 改成 v1beta1”就能完成。最小实现也需要改 AgentCube 对 direct Sandbox lifecycle 和 CodeInterpreter warm-pool claim 的语义建模。

### Label Judgment And Update

`zhzhuang-zju` 认为 #387 更像 feature。结合代码实际范围，这个判断合理：

- #387 修复了 AgentCube 对当前 stable `agent-sandbox @latest` 的不兼容，但形式上是在增加对新的外部 dependency API / controller 行为的兼容能力。
- 它不仅修一个崩溃点，还改变 warm-pool session 创建等待逻辑、session store 资源名选择、NetworkPolicy 兼容策略、e2e warm-pool discovery 和 codegen stack。

建议把 PR kind 从 `/kind bug` 改为 `/kind feature`。如果社区更偏好“兼容性增强”而不是新功能，也可以用 `/kind enhancement`；但 reviewer 明确说 feature，因此优先用 `/kind feature`。

用户后续确认“label改一下”后，先尝试 GitHub Issues Labels API 直接改 label，失败：

```text
403 Must have admin rights to Repository.
```

随后按社区 bot 命令发布最小评论：

```text
/remove-kind bug
/kind feature
```

评论链接：[#387 issuecomment-4739536274](https://github.com/volcano-sh/agentcube/pull/387#issuecomment-4739536274)

确认结果：

```text
labels: kind/feature, size/XL
```

### Suggested Scope Decision

不建议在 #387 里继续扩展到 `v0.5.0rc1`：

1. #387 当前目标是 current stable Go module `@latest`，也就是 `v0.4.6`。
2. #387 已经较大，且已有完整 fork CI / upstream CI / k3s / SDK / MCP / math-agent 验证材料。
3. rc1 引入 `v1beta1` API、`OperatingMode`、required `WarmPoolRef`、launch type labels 和 suspend/resume 语义，和 #386 的 Sleep/Resume 方向存在直接关联，应该作为 follow-up compatibility/design task 单独追踪。
4. 如果未来 `agent-sandbox v0.5.0` 正式发布，AgentCube 可能确实需要第二轮适配；但这轮适配应以正式 release tag / CRD / controller manifests 为目标，而不是混入当前 v0.4.6 stable compatibility PR。

### English Reply Draft

不要直接发布；先让用户确认。

```md
Thanks for raising this.

For the PR kind, I agree this is better classified as a feature/compatibility PR than a bug fix. It adds support for a newer `agent-sandbox` API/controller behavior rather than only fixing an internal AgentCube regression.

/remove-kind bug
/kind feature

For `v0.5.0rc1`, I rechecked this from the source instead of relying only on the tag name. The pseudo-version resolution is only one signal: `go list -m -json sigs.k8s.io/agent-sandbox@v0.5.0rc1` resolves it to `v0.4.7-0.20260608211546-6af1bbd0cf64`, and it is not listed by `go list -m -versions`. The more important blocker is that the rc1 source has already moved the APIs used by AgentCube from `v1alpha1` to `v1beta1`.

A trial bump fails before compilation because the current imports no longer exist:

```text
sigs.k8s.io/agent-sandbox/api/v1alpha1
sigs.k8s.io/agent-sandbox/extensions/api/v1alpha1
```

After a mechanical import migration to `v1beta1`, the next compile errors are structural:

```text
unknown field Replicas in .../api/v1beta1.SandboxSpec
unknown field TemplateRef in .../extensions/api/v1beta1.SandboxClaimSpec
```

Those fields are part of the current AgentCube integration path. Direct Sandbox creation currently sets `SandboxSpec.Replicas = 1`, while CodeInterpreter warm-pool sessions create a `SandboxClaim` with `Spec.TemplateRef` and then wait for `Status.SandboxStatus.Name`.

In rc1, `SandboxSpec` uses `operatingMode: Running/Suspended` instead of `replicas`, and `SandboxClaimSpec` requires `warmPoolRef` instead of `sandboxTemplateRef` / `WarmPoolPolicy`. The claim controller also resolves the template through the referenced warm pool, so the behavior is no longer the same "claim references template, optionally adopt from a matching/default warm pool, otherwise cold create" model used by the v0.4.6 adaptation.

So I agree that once `agent-sandbox v0.5.0` is officially released, AgentCube will likely need another compatibility pass. My suggestion is to keep this PR focused on the current stable Go module `@latest` (`v0.4.6`) and track the `v0.5.x` / `v1beta1` migration as a separate follow-up, because it changes the API version and the warm-pool claim semantics rather than being a small incremental patch on top of this PR.
```

### PR Body Update

用户确认“回复我自己发，改说明可以更新”后，只更新 PR body，不发评论，不改 label。

旧 PR body note：

```text
Target version: `agent-sandbox v0.4.6`, which is the current Go module `@latest`. I did not target `v0.5.0rc1` because Go resolves that tag to a pseudo-version rather than the stable latest release.
```

更新后的 PR body note：

```text
Target version: `agent-sandbox v0.4.6`, which is the current Go module `@latest`. I did not include `v0.5.0rc1` in this PR because it is not listed as a canonical Go module release and, more importantly, it has already moved the APIs AgentCube uses from `v1alpha1` to `v1beta1` (`SandboxClaimSpec.TemplateRef` -> required `WarmPoolRef`, `SandboxSpec.Replicas` -> `OperatingMode`). I will track the `v0.5.x` / `v1beta1` migration as a separate follow-up because it changes warm-pool claim semantics rather than being a small patch on top of the current v0.4.6 adaptation.
```

结果：

- PR body 更新成功：`https://github.com/volcano-sh/agentcube/pull/387`
- GitHub API `updated_at`：`2026-06-18T08:07:46Z`
- Body 更新时 Labels 未改；随后按用户确认通过 bot 命令改为 `kind/feature`、`size/XL`
- 只发布了 label bot 命令评论；未发布解释性 issue comment / review comment，`zhzhuang-zju` 的技术回复由用户自己发。
