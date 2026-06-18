# Day 18 - agent-sandbox v0.5.x Forward Adaptation Test

日期：2026-06-18

## 任务定位

Day18 单独跟进 `sigs.k8s.io/agent-sandbox v0.5.x` / `v1beta1` 前沿适配测试，不再堆到 upstream PR #387 里。

当前边界：

- #387：只负责 current stable Go module `@latest`，也就是 `agent-sandbox v0.4.6` 的兼容适配。
- Day18：负责预研 `v0.5.0rc1` / 后续正式 `v0.5.0` 的 breaking changes、最小代码适配、运行验证和后续独立 PR 材料。
- upstream 行为：Day18 默认只做 local / fork-only validation。没有用户确认前，不开 upstream PR、不发 issue comment、不 mention maintainer。

## 已知事实

来自 Day17 的源码和 module 审计：

- `go list -m sigs.k8s.io/agent-sandbox@latest` 当前解析到 `v0.4.6`。
- `v0.5.0rc1` 是 Git tag / release candidate，但不是当前 Go module `@latest`；Go 会解析为 pseudo-version。
- `v0.5.0rc1` 已把 AgentCube 使用的 API 从 `v1alpha1` 迁到 `v1beta1`。
- 直接 `go get sigs.k8s.io/agent-sandbox@v0.5.0rc1 && go mod tidy` 会因为 current imports 缺失失败：

```text
sigs.k8s.io/agent-sandbox/api/v1alpha1
sigs.k8s.io/agent-sandbox/extensions/api/v1alpha1
```

- 机械改 import 到 `v1beta1` 后，`pkg/workloadmanager` 编译继续失败在结构字段变化：

```text
unknown field Replicas in .../api/v1beta1.SandboxSpec
unknown field TemplateRef in .../extensions/api/v1beta1.SandboxClaimSpec
```

## 为什么必须拆出 #387

`v0.5.x` 不是 #387 的小补丁，而是语义迁移：

- direct Sandbox 生命周期从 `replicas` 模型切换到 `operatingMode: Running/Suspended`。
- CodeInterpreter warm-pool claim 从 `TemplateRef` / optional warm pool 策略变成 required `WarmPoolRef`。
- claim controller 通过 `WarmPoolRef` 找 `SandboxWarmPool`，再从 warm pool 找 `SandboxTemplate`；不再是 #387 中“claim references template, optionally adopt from warm pool, otherwise cold create”的模型。
- `OperatingMode` 与 #386 中 Sleep/Resume 方向直接相关，但 AgentCube 自身的 session state machine 还没有设计和实现。

因此 Day18 的目标是先证明迁移路径，而不是修改 #387。

## 适配假设

第一版最小适配假设：

- `warmPoolSize == nil/0`：继续创建 direct `Sandbox`，不使用 `SandboxClaim`。
- direct `Sandbox`：用 `SandboxSpec.OperatingMode = Running` 替代 `Replicas = 1`。
- `warmPoolSize > 0`：继续由 AgentCube 创建 `SandboxTemplate` 和 `SandboxWarmPool`；创建 session 时用 `SandboxClaimSpec.WarmPoolRef.Name = codeInterpreter.Name`。
- claim 完成后仍通过 `claim.Status.SandboxStatus.Name` 定位实际 adopted Sandbox。
- `NetworkPolicyManagementUnmanaged` 继续保留，防止 agent-sandbox 默认 network policy 阻断 AgentCube Router / WorkloadManager。
- GC / delete 暂时维持当前 session store 设计，但必须验证 v1beta1 下删除 claim 是否仍能清理 underlying sandbox。

待验证风险：

- warm pool 为空时，v1beta1 claim 是否还能 cold create，还是只返回 dependency/candidate not found。
- claimed sandbox 被 delete / GC 后，claim owner reference、finalizer 和 underlying sandbox 是否与 v0.4.6 一致。
- `OperatingMode=Suspended` 会如何影响 Ready condition、pod annotation、entrypoint 和 router 连接。
- v0.5.x controller manifests / CRDs 是否和 Go module tag 完全一致。

## 执行计划

### Phase 1：版本和源码审计

- 用 `audit_go_module_version.py` 检查：
  - `sigs.k8s.io/agent-sandbox@latest`
  - `sigs.k8s.io/agent-sandbox@v0.5.0rc1`
  - 后续正式 `v0.5.0`
  - package presence：`api/v1alpha1`、`extensions/api/v1alpha1`、`api/v1beta1`、`extensions/api/v1beta1`
- 对比 `v0.4.6` 和 `v0.5.0rc1` 的：
  - `SandboxSpec`
  - `SandboxClaimSpec`
  - `SandboxWarmPoolSpec`
  - claim controller `getTemplate()` / adoption / cold-create path
  - annotations / labels / conditions
  - release manifests / CRD versions

### Phase 2：fork-only 编译适配分支

从最新 `upstream/main` 或 #387 合并后的 `main` 创建本地 / fork-only 分支：

```bash
git fetch upstream main
git switch -c test/agent-sandbox-v05-forward upstream/main
```

先做最小代码改动：

- `api/v1alpha1` imports -> `api/v1beta1`
- `extensions/api/v1alpha1` imports -> `extensions/api/v1beta1`
- dynamic GVR version -> `v1beta1`
- `SandboxSpec.Replicas` -> `SandboxSpec.OperatingMode`
- `SandboxClaimSpec.TemplateRef` -> `SandboxClaimSpec.WarmPoolRef`
- 更新 workload builder / controller tests 的断言。

### Phase 3：本地测试

最小验证：

```bash
go test ./pkg/workloadmanager -count=1
make lint
go test -race ./pkg/workloadmanager -count=1
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
make gen-check
make build-all
git diff --check
```

如果 codegen 或 CRD 版本变化触发生成差异，记录具体文件和原因，不把生成差异混成手工改动。

### Phase 4：真实 runtime 验证

只有编译通过不算完成。需要在安装 v0.5.x agent-sandbox CRDs/controller 后验证：

- direct CodeInterpreter e2e
- warm pool e2e
- warm pool load test
- session delete / GC resource cleanup
- Python SDK
- LangChain sandbox
- MCP HTTP / stdio
- math-agent LLM e2e

每次测试记录：

- agent-sandbox module version / manifest source
- AgentCube branch / commit
- cluster environment
- commands
- pass/fail
- root cause / workaround

## 和 Sleep/Resume 的关系

Day18 只把 `OperatingMode` 接入现有生命周期，不实现 AgentCube Sleep/Resume。

Sleep/Resume 后续应单独设计：

- store 增加 `Ready / Paused / Deleted` 和 `PausedAt`
- GC 从单一 delete 改成 `Ready -> Paused`、`Paused -> Deleted`
- WorkloadManager idle 后 patch Sandbox `OperatingMode=Suspended`
- Router 收到 session 请求时先 resume，再 proxy
- 新增 `pauseTimeout`，并明确与 `sessionTimeout` / `maxSessionDuration` 的关系

这个功能依赖 v0.5.x 的接口更自然，但不是兼容性适配 PR 的一部分。

## 当前产出目标

Day18 的阶段性产出不是 upstream PR，而是：

- 一份 v0.5.x 适配差异表。
- 一个 fork-only 编译适配分支。
- 一组本地和 e2e 测试结果。
- 一个后续独立 upstream PR 的英文材料草稿。

停止条件：

- 如果 `v0.5.0` 尚未正式发布，且 rc1 行为仍可能变化，则不向 upstream 提交正式 PR。
- 如果 runtime 失败来自 release manifests / controller 与 Go module 不匹配，先记录并等待正式 release 或 maintainer 指示。
- 如果连续三次卡在同一个环境问题，例如 cluster / CRD 安装 / kind cgroup，则停止硬调，改为记录 BLOCKED 和所需环境。
