# Day 10：从 #265 开始做 WarmPoolAvailable PoC

## 今日目标

今天正式从社区 issue 进入一个小范围开发任务。选择目标是：

- [#265](https://github.com/volcano-sh/agentcube/issues/265)：在 `CodeInterpreter` status 中观察 `SandboxWarmPool` 健康状态。
- 目标不是马上发 PR，而是先确认社区状态、代码路径、最小实现范围和本地测试结果。

## 为什么选 #265

Day 9 已经看过当前社区方向。今天重新确认后，#265 比其他候选更适合做 Day 10 的第一项开发工作：

| 候选 | 当前状态 | 判断 |
| --- | --- | --- |
| #375 TokenCache JWT `exp` bug | 已由 @HarshitPal25 认领 | 不重复开 PR，只适合后续 review / 复现 |
| #366 SnapStart proposal | @lyuyun 的大型设计 PR | 适合阅读和 review，不适合作为第一刀 |
| #379 SnapStart implementation | @lyuyun 的大型实现 PR | 范围大，涉及 CRD、agentd、Kuasar，先不直接改 |
| #365 SnapStart benchmark | 无 assignee，但依附 #366 方向 | 适合补 benchmark 口径，不是今天主开发线 |
| #265 WarmPoolAvailable | open、无 assignee、未见直接实现 PR | 和我们上周 warmPoolSize / pool miss 实测直接相关，范围可控 |

## #265 问题理解

issue 作者希望 `CodeInterpreterReconciler` 不只创建和维护 `SandboxWarmPool`，还要读取它的健康状态，并把结果反映到 `CodeInterpreter.status.conditions` 中。

当前问题是：

- `CodeInterpreter` 只要 reconcile 成功就显示 `Ready=true`。
- 即使底层 `SandboxWarmPool` 因镜像拉取失败、runtimeClass 错误、quota 不足等原因没有 ready sandbox，`CodeInterpreter` 仍然看起来是 ready。
- 当 pool 为空时，创建 session 会退化到 cold start。外部看到的可能是偶发 500 或超时，但从 `kubectl describe codeinterpreter` 看不出 warm pool 已经不可用。

期望改进：

- 增加 `WarmPoolAvailable` condition。
- 读取 `SandboxWarmPool.Status.ReadyReplicas`。
- pool 低于低水位或为 0 时，通过 condition 和 Kubernetes Event 给出信号。
- `CodeInterpreterReconciler` watch 自己拥有的 `SandboxWarmPool`，让 warm pool status 变化能触发重新 reconcile。

## 社区状态

今天通过 GitHub API 重新确认：

```bash
curl -fsSL https://api.github.com/repos/volcano-sh/agentcube/issues/265 | python3 -c '...'
```

结果：

- issue open。
- label 是 `kind/enhancement`。
- assignees 为空。
- 暂时没有看到直接实现 `WarmPoolAvailable` 的 open PR。

复查命令：

```bash
python3 - <<'PY'
import json
import urllib.parse
import urllib.request
headers={'Accept':'application/vnd.github+json','User-Agent':'agentcube-local-check'}
repo='volcano-sh/agentcube'
...
PY
```

复查结果：

```text
issue_url https://github.com/volcano-sh/agentcube/issues/265
state open
title feat: observe SandboxWarmPool health in CodeInterpreter status (WarmPoolAvailable condition + events)
author @Sanchit2662
labels kind/enhancement
assignees -
comments 3
```

PR 重复性搜索：

| 搜索 | 结果 | 判断 |
| --- | ---: | --- |
| `is:pr is:open "WarmPoolAvailable"` | 0 | 没有直接实现同名 condition 的 open PR |
| `is:pr is:open "SandboxWarmPool" "CodeInterpreter"` | 2 | 命中 #366 SnapStart proposal、#224 enhanced warm pool proposal，不是 #265 直接实现 |
| `is:pr is:open "#265"` | 3 | 命中 #320、#379、#39，但不是直接实现 `WarmPoolAvailable` |

参与者：

| 角色 | 账号 | 说明 |
| --- | --- | --- |
| issue 作者 | @Sanchit2662 | 提出 WarmPoolAvailable condition 和 Event 需求 |
| 维护者 / member | @hzxuzhonghu | 在 issue 中 cc @YaoZengzeng |
| 潜在 reviewer | @YaoZengzeng | 被维护者 cc，后续可能需要关注其意见 |

## 代码路径

重点文件：

| 文件 | 作用 |
| --- | --- |
| `pkg/workloadmanager/codeinterpreter_controller.go` | `CodeInterpreterReconciler` 创建 / 删除 `SandboxTemplate` 和 `SandboxWarmPool`，并更新 `CodeInterpreter` status |
| `pkg/workloadmanager/codeinterpreter_controller_test.go` | CodeInterpreter controller 相关单测 |
| `cmd/workload-manager/main.go` | 构造 reconciler，可以注入 Kubernetes event recorder |
| `pkg/apis/runtime/v1alpha1/codeinterpreter_types.go` | `CodeInterpreterStatus` 已经有 `Conditions []metav1.Condition`，不需要新增 CRD 字段 |

外部依赖确认：

```bash
curl -fsSL https://raw.githubusercontent.com/kubernetes-sigs/agent-sandbox/v0.1.1/extensions/api/v1alpha1/sandboxwarmpool_types.go
```

`agent-sandbox v0.1.1` 的 `SandboxWarmPoolStatus` 已经包含：

```go
Replicas int32
ReadyReplicas int32
```

所以这次 PoC 可以直接读 `ReadyReplicas`，不需要修改 `agent-sandbox`。

## 分支和 worktree

当前 fork `main` 有实习报告、skills、TODO 等未提交改动。为了避免污染 upstream PR，今天没有直接在 `/home/agentcube` 上改代码，而是从最新 `upstream/main` 建了单独 worktree：

```bash
git fetch upstream main
git worktree add -b feat/warmpool-available-condition ../agentcube-pr265 upstream/main
```

开发目录：

```text
/home/agentcube-pr265
```

分支：

```text
feat/warmpool-available-condition
```

基线：

```text
upstream/main 0fd9151
```

## 当前 PoC 改动

PoC 已在 `/home/agentcube-pr265` 完成，涉及 3 个文件：

| 文件 | 改动 |
| --- | --- |
| `pkg/workloadmanager/codeinterpreter_controller.go` | 增加 `WarmPoolAvailable` condition 计算；读取 `SandboxWarmPool.Status.ReadyReplicas`；低水位/为空时设置 false；disabled 时设置 unknown；ready 时设置 true；增加 warning Event 去重逻辑；watch owned `SandboxWarmPool` |
| `pkg/workloadmanager/codeinterpreter_controller_test.go` | 增加 condition 表驱动测试、event 去重判断测试、`updateStatus` 写入 `WarmPoolAvailable` 的测试 |
| `cmd/workload-manager/main.go` | 给 `CodeInterpreterReconciler` 注入 `mgr.GetEventRecorderFor("codeinterpreter-controller")` |

当前 condition 语义：

| 场景 | `WarmPoolAvailable` |
| --- | --- |
| 未配置 warm pool | `Unknown / WarmPoolDisabled` |
| 配置了 warm pool 但对象不存在 | `False / WarmPoolNotFound` |
| `ReadyReplicas == 0` | `False / WarmPoolEmpty` |
| `ReadyReplicas < ceil(warmPoolSize / 2)` | `False / WarmPoolBelowWatermark` |
| 达到低水位 | `True / WarmPoolReady` |

## 测试和验证

当前测试机一开始没有 Go 工具链：

```bash
go env GOMODCACHE GOMOD
```

错误：

```text
/bin/bash: go: command not found
```

也没有 `gofmt`：

```bash
which gofmt
which go
```

结果：

```text
no gofmt
no go
```

临时处理方式：

```bash
mkdir -p /tmp/go-toolchain
curl -fsSL -o /tmp/go-toolchain/go1.24.9.linux-amd64.tar.gz https://go.dev/dl/go1.24.9.linux-amd64.tar.gz
tar -C /tmp/go-toolchain -xzf /tmp/go-toolchain/go1.24.9.linux-amd64.tar.gz
/tmp/go-toolchain/go/bin/go version
```

结果：

```text
go version go1.24.9 linux/amd64
```

格式化：

```bash
/tmp/go-toolchain/go/bin/gofmt -w \
  cmd/workload-manager/main.go \
  pkg/workloadmanager/codeinterpreter_controller.go \
  pkg/workloadmanager/codeinterpreter_controller_test.go
```

目标包测试：

```bash
/tmp/go-toolchain/go/bin/go test ./pkg/workloadmanager
```

结果：

```text
ok  	github.com/volcano-sh/agentcube/pkg/workloadmanager	0.224s
```

重新跑 verbose 测试并保存完整报告：

```bash
/tmp/go-toolchain/go/bin/go test -v ./pkg/workloadmanager 2>&1 | tee /tmp/agentcube-pr265-workloadmanager-test.log
```

第一次结果：

```text
PASS
ok  	github.com/volcano-sh/agentcube/pkg/workloadmanager	0.228s
```

完整测试输出保存在：

```text
/tmp/agentcube-pr265-workloadmanager-test.log
```

本次新增相关测试全部通过：

| 测试 | 覆盖点 |
| --- | --- |
| `TestWarmPoolAvailableCondition` | 未配置 warm pool、warm pool missing、ready=0、低于低水位、达到低水位、单副本 ready |
| `TestShouldRecordWarmPoolWarningEvent` | warning Event 首次触发、相同 warning 去重、reason 变化再触发、ready/disabled 不触发 |
| `TestUpdateStatusSetsWarmPoolAvailableCondition` | `updateStatus` 写入 `Ready` 和 `WarmPoolAvailable` conditions |

后来复查时发现，上面三类测试主要证明 helper 和 status 更新逻辑能跑通，还不够直接证明 issue 作者提出的几个用户可见问题被解决。于是补了 Reconcile 层测试，直接模拟 `CodeInterpreter` 已配置 warm pool，但底层 pool 不健康的场景：

| 测试 | 对应 #265 问题 |
| --- | --- |
| `TestReconcileReportsWarmPoolEmptyInsteadOfOnlyReady` | 以前 `CodeInterpreter` 只显示 `Ready=true`；现在即使 `Ready=true`，也会同时设置 `WarmPoolAvailable=False/WarmPoolEmpty`，并发出 warning Event |
| `TestReconcileReportsWarmPoolBelowWatermark` | pool 没空但低于低水位时，`WarmPoolAvailable=False/WarmPoolBelowWatermark`，不是静默退化 |
| `TestReconcileUpdatesWarmPoolAvailableWhenPoolRecovers` | pool 从 0 ready 恢复到 ready 后，condition 变回 `WarmPoolAvailable=True/WarmPoolReady`，并且不会重复发 warning Event |

针对性测试命令：

```bash
/tmp/go-toolchain/go/bin/go test -v ./pkg/workloadmanager -run 'TestReconcileReportsWarmPoolEmptyInsteadOfOnlyReady|TestReconcileReportsWarmPoolBelowWatermark|TestReconcileUpdatesWarmPoolAvailableWhenPoolRecovers'
```

结果：

```text
=== RUN   TestReconcileReportsWarmPoolEmptyInsteadOfOnlyReady
--- PASS: TestReconcileReportsWarmPoolEmptyInsteadOfOnlyReady (0.08s)
=== RUN   TestReconcileReportsWarmPoolBelowWatermark
--- PASS: TestReconcileReportsWarmPoolBelowWatermark (0.00s)
=== RUN   TestReconcileUpdatesWarmPoolAvailableWhenPoolRecovers
--- PASS: TestReconcileUpdatesWarmPoolAvailableWhenPoolRecovers (0.01s)
PASS
ok  	github.com/volcano-sh/agentcube/pkg/workloadmanager	0.120s
```

补完针对性测试后重新跑全包：

```bash
/tmp/go-toolchain/go/bin/go test -v ./pkg/workloadmanager 2>&1 | tee /tmp/agentcube-pr265-workloadmanager-test.log
```

最新结果：

```text
PASS
ok  	github.com/volcano-sh/agentcube/pkg/workloadmanager	0.240s
```

额外检查：

```bash
git diff --check
```

结果：通过，无 trailing whitespace。

## 卡点记录

### 卡点 1：主 worktree 有实习报告改动，不能直接做 upstream PR

失败风险：

- 当前 `/home/agentcube` 的 `main` 分支混有中文日报、skills、TODO 等内容。
- 如果直接从这个分支开 PR，会把实习报告带进 upstream PR。

处理方式：

- 用 `git worktree` 从 `upstream/main` 建干净开发目录 `/home/agentcube-pr265`。
- 代码 PR 改动只放在 `feat/warmpool-available-condition`。

### 卡点 2：系统缺少 Go / gofmt

失败命令：

```bash
go env GOMODCACHE GOMOD
which gofmt
which go
```

错误现象：

```text
/bin/bash: go: command not found
no gofmt
no go
```

处理方式：

- 不改系统环境。
- 临时下载 `go1.24.9.linux-amd64.tar.gz` 到 `/tmp/go-toolchain`。
- 用 `/tmp/go-toolchain/go/bin/go` 和 `/tmp/go-toolchain/go/bin/gofmt` 完成本地验证。

### 卡点 3：第一次获取 Go 最新版本 JSON 的命令写法错误

失败命令：

```bash
curl -fsSL 'https://go.dev/dl/?mode=json' | python3 - <<'PY'
...
PY
```

错误现象：

```text
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
curl: (23) Failed writing body
```

原因：

- 这个写法里 `python3 - <<'PY'` 用 here-doc 占用了 stdin，导致 Python 没有正确读取 curl 输出。

处理方式：

- 不再动态解析 JSON。
- 直接根据 `go.mod` 中的 `toolchain go1.24.9` 下载对应 tarball。

## 人工 review 结论

已经复查 `/home/agentcube-pr265` 的 diff。当前 PoC 范围和 #265 对应关系比较清楚：

| #265 诉求 | 当前覆盖情况 |
| --- | --- |
| 在 `CodeInterpreter.status.conditions` 暴露 warm pool 健康状态 | 已新增 `WarmPoolAvailable` condition |
| 读取 `SandboxWarmPool.Status.ReadyReplicas` | 已读取，并按 `warmPoolSize` 计算状态 |
| pool 为 0 或低于低水位时有信号 | 已设置 `False/WarmPoolEmpty` 或 `False/WarmPoolBelowWatermark` |
| 通过 Kubernetes Event 提醒 | 已注入 event recorder，并在 warning reason 首次出现或变化时发 warning Event |
| warm pool status 变化能触发 reconcile | 已增加 `Owns(&SandboxWarmPool{})` |

这次没有新增 CRD 字段，复用了 `CodeInterpreterStatus.Conditions`，所以不需要跑 `make gen-all`。`cmd/workload-manager/main.go` 只增加了 `CodeInterpreterReconciler` 的 event recorder 注入。

需要在 PR 中主动说明的口径：

- 低水位当前按 `ceil(warmPoolSize / 2)` 计算，对应 issue 中提到的 50% desired。
- 初始创建 warm pool 后，如果 `ReadyReplicas` 仍为 0，也会发一次 `WarmPoolEmpty` warning Event。这能暴露“看起来 Ready 但 warm pool 不可用”的问题，但如果维护者认为初始启动阶段不应告警，可以再改成只在从 ready 退化时发。
- Reconcile 层测试已经补上，不只是证明 helper 能跑通，而是直接验证 issue 中的用户可见症状。

## 最终验证记录

补充编译面测试：

```bash
/tmp/go-toolchain/go/bin/go test ./cmd/workload-manager ./pkg/workloadmanager 2>&1 | tee /tmp/agentcube-pr265-focused-test.log
```

结果：

```text
?   	github.com/volcano-sh/agentcube/cmd/workload-manager	[no test files]
ok  	github.com/volcano-sh/agentcube/pkg/workloadmanager	0.240s
```

完整日志：

```text
/tmp/agentcube-pr265-focused-test.log
```

最终检查：

```bash
git -C /home/agentcube-pr265 diff --check
```

结果：通过。

补充尝试仓库标准测试：

```bash
PATH=/tmp/go-toolchain/go/bin:$PATH make test
```

结果：未通过，失败集中在 `test/e2e`，原因是当前本地没有启动 router / workload-manager 服务，也没有可用 kubeconfig：

```text
dial tcp [::1]:8081: connect: connection refused
failed to get kubeconfig: invalid configuration: no configuration has been provided
```

前面的普通 Go package 测试已经跑到并通过 `pkg/workloadmanager`；这次 `make test` 失败属于本地 e2e 环境缺失，需要在 PR 中如实说明，不应解读为 #265 PoC 的单元测试失败。

当前代码分支状态：

```text
/home/agentcube-pr265
branch: feat/warmpool-available-condition
base: upstream/main 0fd9151
changed files:
  cmd/workload-manager/main.go
  pkg/workloadmanager/codeinterpreter_controller.go
  pkg/workloadmanager/codeinterpreter_controller_test.go
```

## upstream PR 文案草案

````markdown
What type of PR is this?

/kind enhancement

What this PR does / why we need it:

This PR surfaces SandboxWarmPool health on CodeInterpreter status.

Before this change, CodeInterpreter could report Ready=true after reconciliation even when the underlying SandboxWarmPool had zero or too few ready replicas. In that state, session creation may fall back to cold start or fail, but users cannot diagnose the warm pool health from the CodeInterpreter status.

This change adds:

- a WarmPoolAvailable condition on CodeInterpreter status
- ReadyReplicas-based health evaluation for the owned SandboxWarmPool
- Warning Events when the warm pool is missing, empty, or below the low watermark
- a watch on owned SandboxWarmPool resources so warm pool status changes requeue CodeInterpreter reconciliation

Which issue(s) this PR fixes:

Fixes #265

Special notes for your reviewer:

- No new CRD fields are added; this reuses CodeInterpreterStatus.Conditions.
- The low watermark is currently ceil(warmPoolSize / 2), matching the 50% desired threshold proposed in the issue.
- A newly created warm pool with ReadyReplicas=0 emits a WarmPoolEmpty warning once. If the preferred behavior is to warn only after a previously ready pool degrades, I can adjust the event policy.
- No code generation is required.

Tests:

- /tmp/go-toolchain/go/bin/go test ./cmd/workload-manager ./pkg/workloadmanager
- /tmp/go-toolchain/go/bin/go test -v ./pkg/workloadmanager
- /tmp/go-toolchain/go/bin/go test -v ./pkg/workloadmanager -run 'TestReconcileReportsWarmPoolEmptyInsteadOfOnlyReady|TestReconcileReportsWarmPoolBelowWatermark|TestReconcileUpdatesWarmPoolAvailableWhenPoolRecovers'

Does this PR introduce a user-facing change?

```release-note
CodeInterpreter status now reports SandboxWarmPool health through a WarmPoolAvailable condition and warning Events.
```
````

## 可选 issue 评论草案

如果先在 #265 下确认方向，可以发这段：

```markdown
I have a small implementation in progress for this issue.

The current approach reuses CodeInterpreterStatus.Conditions and adds a WarmPoolAvailable condition based on the owned SandboxWarmPool's ReadyReplicas. It also records warning Events for WarmPoolNotFound, WarmPoolEmpty, and WarmPoolBelowWatermark, and adds an Owns(SandboxWarmPool) watch so pool status changes requeue CodeInterpreter reconciliation.

One behavior I would like to confirm before opening the PR: the current low watermark is ceil(warmPoolSize / 2), and a newly created warm pool with ReadyReplicas=0 emits one WarmPoolEmpty warning. If maintainers prefer warning only after a previously ready pool degrades, I can adjust that event policy.
```

## 后续追踪

- 已成功提交 upstream PR [#385](https://github.com/volcano-sh/agentcube/pull/385)，本阶段目标从“准备 PR”切换为“追踪 review / CI / bot 反馈”。
- 继续观察 coverage、e2e、tide、reviewer 评论和 maintainer 是否要求调整 condition / Event 语义。
- 如果维护者希望更保守，就把 Event 策略改成只在从 `WarmPoolReady` 退化到 false 时发 warning，condition 仍然照常更新。
- 后续所有修改继续推到 `ranxi2001:feat/warmpool-available-condition`，不要混入 fork `main` 的实习报告改动。

## PR 提交结果

已从干净 worktree `/home/agentcube-pr265` 提交并推送 upstream PR：

```text
PR: https://github.com/volcano-sh/agentcube/pull/385
branch: ranxi2001:feat/warmpool-available-condition
commit: 809214d feat: expose codeinterpreter warm pool health
follow-up commit: 8344a9f test: cover warm pool status edge cases
```

提交时使用了 DCO sign-off：

```text
Signed-off-by: ranxi2001 <ranxi169@163.com>
```

PR 创建后，社区 bot 已自动识别 `/kind enhancement`，并请求 `acsoto` 和 `LiZhenCheng9527` review。当前状态是已经成功提交 PR，后续继续追踪 CI、coverage、e2e、tide 和 reviewer 反馈。

## Codecov bot 反馈与处理

PR 创建后，`codecov-commenter` 自动评论：

```text
Patch coverage is 83.33333% with 13 lines in your changes missing coverage.
Files with missing lines: pkg/workloadmanager/codeinterpreter_controller.go
```

这类评论是覆盖率 bot 的自动检查，不是真人 reviewer 结论。它的作用是提醒新增代码的测试覆盖率是否足够，和 `volcano-sh-bot`、`tide` 一样属于 PR 流程信号；需要看具体缺失行，而不是只看红叉。

本次判断：

- `Please install the codecov app` 是仓库/组织级配置提示，不是本 PR 能修的代码问题。
- `Report is 125 commits behind head on main` 是 Codecov 基准报告滞后提示，也不是本 PR 代码错误。
- `Patch coverage 83.33%` 和 `13 missing lines` 是需要处理的有效反馈，因为它指出了新增代码中缺少测试覆盖的分支。

本地复现覆盖率：

```bash
/tmp/go-toolchain/go/bin/go test -coverprofile=/tmp/agentcube-pr385-workloadmanager.cover ./pkg/workloadmanager
/tmp/go-toolchain/go/bin/go tool cover -func=/tmp/agentcube-pr385-workloadmanager.cover | rg 'codeinterpreter_controller.go|total'
```

初始主要缺口：

| 函数 | 初始覆盖率 | 缺口 |
| --- | ---: | --- |
| `updateStatus` | 81.2% | status 未变化直接返回、status update error |
| `warmPoolAvailableCondition` | 94.4% | `Get` 返回非 NotFound 错误 |
| `shouldRecordWarmPoolWarningEvent` | 80.0% | unrelated false reason 不发 event |
| `recordEvent` | 66.7% | nil recorder 保护分支 |
| `deleteSandboxWarmPool` / `deleteSandboxTemplate` | 0% | warm pool disabled 时删除资源路径 |

补充测试后推送了第二个 commit：

```text
8344a9f test: cover warm pool status edge cases
```

新增测试覆盖：

| 测试 | 覆盖点 |
| --- | --- |
| `TestUpdateStatusSkipsUnchangedStatus` | status 已经最新时不重复 update |
| `TestUpdateStatusReturnsStatusUpdateError` | status subresource update 失败时返回错误 |
| `TestWarmPoolAvailableConditionReturnsGetError` | 获取 `SandboxWarmPool` 出现非 NotFound 错误时返回包装错误 |
| `TestShouldRecordWarmPoolWarningEvent/does_not_record_unrelated_false_reason` | 非 warm pool warning reason 不发 Event |
| `TestRecordEventSkipsNilRecorder` | `Recorder == nil` 时安全跳过 |
| `TestReconcileDeletesWarmPoolWhenDisabled` | warm pool disabled 后删除 `SandboxWarmPool` / `SandboxTemplate` 路径 |

补充后的本地验证：

```bash
/tmp/go-toolchain/go/bin/go test ./cmd/workload-manager ./pkg/workloadmanager
```

结果：

```text
?   	github.com/volcano-sh/agentcube/cmd/workload-manager	[no test files]
ok  	github.com/volcano-sh/agentcube/pkg/workloadmanager	0.268s
```

补充后的覆盖率变化：

| 函数 | 补充后覆盖率 |
| --- | ---: |
| `updateStatus` | 93.8% |
| `warmPoolAvailableCondition` | 100.0% |
| `shouldRecordWarmPoolWarningEvent` | 100.0% |
| `recordEvent` | 100.0% |
| `deleteSandboxWarmPool` / `deleteSandboxTemplate` | 63.6% |

剩余 `SetupWithManager` 覆盖率仍为 0%，这是 controller builder 注册路径，通常更适合由集成测试或 envtest 覆盖；本次为了回应 patch coverage，先补业务逻辑和错误路径单测，不为覆盖率强行 mock controller-runtime builder。

## PR 规范补充

这次 #385 暴露出一个实际 PR 规范：提交后不能只等真人 review，也要及时阅读自动化 bot 的反馈。

处理顺序：

1. 先区分 bot 类型：流程 bot、CI bot、coverage bot、AI reviewer、真人 reviewer。
2. 对 coverage bot，不要把仓库配置提示当成代码问题，但要处理 `Patch coverage` 和 missing lines。
3. 如果本地无法跑完整 `make test`，必须在 PR 描述中说明失败原因，例如本机缺少 router / workload-manager / kubeconfig 导致 e2e 失败。
4. 补测试后用新 commit 推到同一个 PR 分支，保留 review 过程，除非维护者要求 squash 或 rebase。
5. 每次推送后记录 commit、测试命令和 bot 反馈变化，方便实习报告复盘。

## 一句话总结

在 #265 要求 `CodeInterpreter` 显式暴露 `SandboxWarmPool` 健康状态的背景下，本 PoC 通过在 `CodeInterpreterReconciler` 中新增 `WarmPoolAvailable` condition、读取 owned `SandboxWarmPool.Status.ReadyReplicas`、注入 warning Event recorder 并 watch `SandboxWarmPool`，修复了 `CodeInterpreter` 表面 `Ready=true` 但 warm pool 不可用或低水位不可观测的问题。
