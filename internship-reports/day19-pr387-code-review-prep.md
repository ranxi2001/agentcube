# Day 19 - PR #387 Code Review Preparation

日期：2026-06-22

## 目标

为 upstream PR [#387](https://github.com/volcano-sh/agentcube/pull/387) 准备代码级 review 答辩材料。

本文件只分析当前 #387 的 `agent-sandbox v0.4.6` 适配，不把 Day18 的 `v0.5.0rc1` / `v1beta1` 前沿实验混进本 PR。

## 范围基线

当前分析对象：

- Base：`a31651e5aba6ab0ce6ef854ffdb724146b40af5b`，即 #391 Go 1.26.4 前置 PR 合并后的 upstream main。
- Upstream 当前 Head：`ff8260e`，已移除非必要 `docker/Dockerfile.picod` cleanup。
- 本地待推送 Head：`bc8e85b`，新增 commit `docs: align sandbox pod annotation comment`，仅对齐 `SandboxPodNameAnnotation` 注释。
- PR 状态：open，labels 为 `kind/feature` / `size/XL`。
- 文件规模：upstream 当前为 16 files changed；本地最小修复后为 15 files changed，`docker/Dockerfile.picod` 不再出现在 PR diff。
- 结论口径：这是 current stable `sigs.k8s.io/agent-sandbox v0.4.6` compatibility feature，不是 Go/toolchain PR，也不是 v0.5 API migration PR。

本地验证命令：

```bash
python3 .agents/skills/agentcube-pr-management/scripts/pr_status.py 387
git -C /home/agentcube-agent-sandbox-latest diff --stat a31651e..5867183
git -C /home/agentcube-agent-sandbox-latest diff --name-status a31651e..5867183
```

## Review 总叙事

#387 的核心不是“把一个依赖版本号改大”，而是对 `agent-sandbox` warm pool 语义变化做兼容：

1. `SandboxPodNameAnnotation` 不再从 `sigs.k8s.io/agent-sandbox/controllers` 内部包读取，而应使用公开 API 包常量。
2. 新版 warm pool 不再能假设 `SandboxClaim` 名等于实际 serving `Sandbox` 名；claim status 会指向 adopted Sandbox。
3. `agent-sandbox v0.4.6` 的 `SandboxTemplate` 默认 `networkPolicyManagement: Managed`，会为同一模板下的 sandbox Pod 创建共享 Kubernetes `NetworkPolicy`。该默认策略是严格隔离口径，而 AgentCube 当前没有同步创建允许 Router / WorkloadManager 访问 sandbox entrypoint 的配套规则，所以 #387 显式设置 `Unmanaged` 来保留现有连通性。
4. 升级 `agent-sandbox v0.4.6` 必然牵动 Kubernetes `v0.35.x` 依赖栈和 generated client / CRD 文件；这些不是手写业务逻辑。
5. 测试不能只说 CI 绿，必须能说明新增行为：claim adopted sandbox、store 仍保存 claim 名、direct watcher 失败路径、warm-pool e2e helper 的 ownership 识别、network policy create/update 都有覆盖。

## 本地需要 vs 项目需要

本 PR 不应包含 local-only 代码。按最小修复原则，本地已把非必要 Dockerfile cleanup 从 PR diff 中移除。保留的 15 个文件可以分为 3 类：

| 类别 | 文件 | 是否项目需要 | 说明 |
| --- | --- | --- | --- |
| 核心兼容逻辑 | `pkg/workloadmanager/handlers.go`, `k8s_client.go`, `sandbox_helper.go`, `codeinterpreter_controller.go` | 是 | 解决 `agent-sandbox v0.4.6` API / warm pool / network policy 行为变化 |
| 测试覆盖 | `pkg/workloadmanager/*_test.go`, `test/e2e/e2e_test.go` | 是 | 证明新行为和失败路径，不是本地临时测试 |
| 依赖与生成物 | `go.mod`, `go.sum`, `hack/update-codegen.sh`, `client-go/*`, CRD yaml | 是 | 与 `agent-sandbox v0.4.6` 的 Kubernetes 依赖栈和 `make gen-check` 对齐 |

需要明确排除：

- Go `1.26.4` 选择已经由 #391 单独合入，不属于 #387 的争议点。
- Day18 `v0.5.0rc1` / `v1beta1` 改动不在 #387。
- 本地 `.env`、fork CI 分支、k3d/k3s 调试脚本不在 #387。
- `docker/Dockerfile.picod` 的 apt cleanup 已经本地验证不是 `agent-sandbox v0.4.6` 适配所需，已由 `ff8260e` 从 PR diff 中移除，后续如有需要应单独 cleanup PR。

## 逐文件代码依据

顺序按 review 答辩叙事排列，不按 GitHub Files changed 的顺序排列：先讲依赖和 codegen 脚本，再讲手写核心逻辑和测试，最后集中解释 `client-go` / CRD 这类生成结果。`docker/Dockerfile.picod` 不是 agent-sandbox 兼容所需改动，已本地移出 #387 diff。

### `go.mod`

关键行：

- `go.mod:16-23`：`golang.org/x/net`、`k8s.io/api`、`k8s.io/apimachinery`、`k8s.io/client-go`、`k8s.io/klog/v2`、`sigs.k8s.io/agent-sandbox`、`sigs.k8s.io/controller-runtime`。
- `go.mod:98`：`k8s.io/apiextensions-apiserver v0.35.4`。

为什么改：

- PR 目标是 `sigs.k8s.io/agent-sandbox v0.4.6`。
- 该版本自身声明 `k8s.io/api/apimachinery/client-go/apiextensions-apiserver@v0.35.4` 和 `sigs.k8s.io/controller-runtime@v0.23.3`。
- 所以 `k8s.io/* v0.35.4` 是目标依赖的项目级要求，不是因为本地机器需要，也不是把 Go 版本升级混进来。

本地模块图证据：

```text
github.com/volcano-sh/agentcube sigs.k8s.io/agent-sandbox@v0.4.6
github.com/volcano-sh/agentcube sigs.k8s.io/controller-runtime@v0.23.3
sigs.k8s.io/agent-sandbox@v0.4.6 k8s.io/api@v0.35.4
sigs.k8s.io/agent-sandbox@v0.4.6 k8s.io/apiextensions-apiserver@v0.35.4
sigs.k8s.io/agent-sandbox@v0.4.6 k8s.io/apimachinery@v0.35.4
sigs.k8s.io/agent-sandbox@v0.4.6 k8s.io/client-go@v0.35.4
sigs.k8s.io/agent-sandbox@v0.4.6 sigs.k8s.io/controller-runtime@v0.23.3
sigs.k8s.io/controller-runtime@v0.23.3 k8s.io/api@v0.35.0
sigs.k8s.io/controller-runtime@v0.23.3 k8s.io/client-go@v0.35.0
```

为什么这样改：

- 让 AgentCube 主模块直接显式记录 MVS 最终选择的 Kubernetes 版本，避免 indirect / generated code 与实际编译依赖不一致。
- 依赖栈和 code-generator 版本保持一致，避免 `make gen-check` 在 reviewer 机器上生成不同结果。

测试覆盖：

- `make gen-check`
- 非 e2e Go 全量测试
- `make build-all`
- fork validation PR [ranxi2001/agentcube#4](https://github.com/ranxi2001/agentcube/pull/4) 全量 CI

答辩句子：

```text
The Kubernetes dependency bump is driven by agent-sandbox v0.4.6 itself. It is not a local Go/toolchain workaround; the Go toolchain prerequisite was already split and merged separately in #391.
```

### `go.sum`

为什么改：

- `go.mod` 依赖栈变化后的校验和同步。
- 删除旧 indirect 校验和、加入新版本校验和是 `go mod tidy` / module resolution 的正常结果。

为什么这样改：

- 不手工挑选 checksum。
- 保持与 `go.mod`、CI、codegen 使用的依赖一致。

分类：

- 项目需要，生成性依赖文件。
- 不是本地需要。

### `hack/update-codegen.sh`

关键行：

- `hack/update-codegen.sh:15`：`CODEGEN_VERSION="v0.35.4"`。
- `hack/update-codegen.sh:24`：使用 `go mod download -json` 下载 code-generator。
- `hack/update-codegen.sh:27`：从 JSON 里解析 `Dir`，pattern 不依赖尾随逗号。

为什么改：

- `agent-sandbox v0.4.6` 把项目依赖推进到 Kubernetes `v0.35.4`，client-go / informer generated output 也应使用相同版本的 `code-generator`。
- 原脚本固定 `v0.34.1`，会导致生成代码与当前依赖栈不一致。
- 原脚本用 `go get -d` 获取 code-generator，可能修改 `go.mod`，在本 PR 场景中曾导致 dependency resolution 被扰动。

这个 codegen 是干什么的：

- AgentCube 自己定义了 Kubernetes CRD API 类型，主要在：
  - `pkg/apis/runtime/v1alpha1/agent_type.go`
  - `pkg/apis/runtime/v1alpha1/codeinterpreter_types.go`
- 这些类型不是普通 Go struct，它们通过 `+genclient`、`+kubebuilder:object:root=true`、`+kubebuilder:subresource:status` 等注解声明“我要成为 Kubernetes API 资源”。
- codegen 的作用是根据这些 API 类型生成 Kubernetes 生态需要的配套代码和 YAML，而不是生成业务逻辑。
- 本仓库的生成链路分两段：
  - `make generate`：用 `controller-gen` 生成 CRD YAML 和 DeepCopy。
  - `make gen-client`：用 `k8s.io/code-generator` 生成 typed client、fake client、informer、lister。
- 具体产物包括：
  - `pkg/apis/runtime/v1alpha1/zz_generated.deepcopy.go`：为 `AgentRuntime` / `CodeInterpreter` 等类型生成 `DeepCopy` / `DeepCopyObject`，让它们能作为 Kubernetes runtime object 被缓存、拷贝、序列化。
  - `manifests/charts/base/crds/runtime.agentcube.volcano.sh_*.yaml`：Kubernetes CRD manifest，用于让 API server 认识 `AgentRuntime` / `CodeInterpreter`。
  - `client-go/clientset/versioned/...`：typed clientset，例如通过 `agentcubeclientset.NewForConfig` 操作 AgentCube CRD。
  - `client-go/informers/externalversions/...`：informer，用于 list/watch CRD 并接入 controller cache。
  - `client-go/listers/runtime/v1alpha1/...`：lister，用于从 informer cache 里按 namespace/name 读取对象。
  - `client-go/clientset/versioned/fake/...`：fake client，用于单元测试里模拟 Kubernetes API 行为。
- 所以 `make gen-check` 的正确语义是：重新生成这些文件，然后检查 git diff 是否为空；如果有 diff，说明提交里的生成文件和 API 类型 / generator 版本不一致。

为什么这样改：

- `go mod download -json` 是只下载模块，不修改主模块依赖的方式。
- 这里的 JSON 不是业务配置，也不会进入 AgentCube runtime。它只是 Go toolchain 返回的 module download metadata，用来告诉脚本 `k8s.io/code-generator@v0.35.4` 被放在本机 module cache 的哪个目录。
- 脚本后面需要执行 `source "${CODEGEN_PKG}/kube_codegen.sh"`，所以必须拿到 code-generator module 的真实目录。JSON 里的 `Dir` 字段就是这个路径，例如：

```json
{
  "Path": "k8s.io/code-generator",
  "Version": "v0.35.4",
  "Dir": "/root/go/pkg/mod/k8s.io/code-generator@v0.35.4"
}
```

- 解析 `Dir` 比猜 GOPATH 路径可靠，也比先 `go get` 再 `go list -m -f '{{.Dir}}'` 更干净，因为它不会把工具依赖写回当前主模块。
- `sed` pattern 不依赖 `"Dir": "...",` 末尾逗号，避免 Go JSON 输出格式变化导致找不到 generator。

为什么不能只改第 15 行：

- 只把 `CODEGEN_VERSION` 从 `v0.34.1` 改到 `v0.35.4`，脚本仍会走旧的 `go get -d "k8s.io/code-generator@${CODEGEN_VERSION}" || true`。
- `go get` 在 module 模式下不是单纯下载工具，它可能修改当前仓库的 `go.mod` / `go.sum` 和 module graph。
- `make gen-check` 的语义应是“验证生成物是否最新”，不是“运行过程中顺手改依赖”。因此这里需要同时改下载方式和路径定位方式。
- 这次 PR 的依赖图已经因为 `agent-sandbox v0.4.6` 发生变化，继续用 `go get` 找工具会增加额外不确定性。用 `go mod download -json` 可以把 codegen 工具定位变成无副作用步骤。

分类：

- 项目需要，codegen reproducibility。
- 不是本地需要。

测试覆盖：

- `make gen-check`
- fork validation PR [ranxi2001/agentcube#4](https://github.com/ranxi2001/agentcube/pull/4) `Codegen Check`

### 已移出：`docker/Dockerfile.picod`

关键行：

- `Dockerfile.picod:28-29`：`apt-get install -y --no-install-recommends python3`，并清理 `/var/lib/apt/lists/*`。

原改动是什么：

- 这是镜像卫生优化：减少 runtime image 中不必要推荐包和 apt cache。
- 它不是 `agent-sandbox v0.4.6` 兼容性的核心要求。

为什么不留在 #387：

- #387 的目标是 current stable `agent-sandbox v0.4.6` compatibility。`Dockerfile.picod` 的 apt cleanup 不解决 annotation import、SandboxClaim adopted Sandbox、NetworkPolicyManagement、codegen 或 e2e ownership 问题。
- 不改这个文件，#387 代码和镜像仍能构建通过。临时 worktree 验证：

```bash
git checkout a31651e -- docker/Dockerfile.picod
go test ./pkg/workloadmanager -count=1
make build-all
docker build -f docker/Dockerfile.picod -t agentcube-pr387-no-picod:test .
```

结果：

```text
go test ./pkg/workloadmanager -count=1: pass
make build-all: pass
docker build -f docker/Dockerfile.picod ...: pass
```

- 因此它不属于“必须改才能适配 agent-sandbox v0.4.6”的最小集合。
- commit `ff8260e` 已把该文件恢复为 upstream main 状态并 push 到 #387 分支，#387 相对 base 的文件数从 16 降到 15。

分类：

- cleanup，非 local-only，但也非 #387 必需。
- 按最小修原则，已从 #387 移除；如果未来需要，可单独开 cleanup PR。

答辩句子：

```text
I rechecked this against the minimal-fix principle. The Dockerfile.picod cleanup is not required for the agent-sandbox v0.4.6 compatibility path, and the branch still builds without it. I will drop it from #387 or keep it for a separate cleanup PR.
```

### `pkg/workloadmanager/codeinterpreter_controller.go`

关键行：

- `codeinterpreter_controller.go:43`：新增 `codeInterpreterNetworkPolicyManagement = NetworkPolicyManagementUnmanaged` 常量。
- `codeinterpreter_controller.go:159-162`：创建 `SandboxTemplate` 时显式设置 `NetworkPolicyManagement`。
- `codeinterpreter_controller.go:180-190`：已有 `SandboxTemplate` 如果不是 Unmanaged，则 reconcile 回 Unmanaged。

为什么改：

- `agent-sandbox v0.4.6` 的 `SandboxTemplate` 默认 network policy management 会让 agent-sandbox 管理 NetworkPolicy。
- Kubernetes `NetworkPolicy` 可以理解成 Pod 级别的网络防火墙；一旦某个 Pod 被 policy 选中，未显式允许的 ingress / egress 流量可能被 CNI 拦截。
- agent-sandbox 的默认 Managed 行为会在 `SandboxTemplate` 级别维护一个共享 policy。上游文档说明：未提供自定义 policy 时会应用 strict secure default，ingress 只允许来自它自己的 Sandbox Router，egress 只允许公网并阻断内部网段。
- AgentCube 当前不是通过 agent-sandbox 的 Sandbox Router 访问 sandbox，而是由 AgentCube Router / WorkloadManager 按自己的 entrypoint 和 session 路由链路访问 sandbox Pod。#387 没有设计或创建一套匹配 agent-sandbox 默认 policy 的 allow rules。
- 因此如果保持默认 Managed，sandbox Pod 可能已经 Ready，但 AgentCube 这边访问 entrypoint / router path 被 NetworkPolicy 拦住，表现为会话请求超时或连接失败。Day16 runtime 验证中已经遇到过这类连通性问题。

为什么这样改：

- 使用 `NetworkPolicyManagementUnmanaged` 保持 AgentCube 现有网络行为，不让 dependency 默认策略改变项目语义。
- create 和 update 都处理：新建模板直接正确，已有旧模板也能被 reconcile 修正，避免升级后 drift。
- 这不是长期网络安全方案，只是 `v0.4.6` 兼容 PR 的最小行为保持。后续如果 AgentCube 要接入 agent-sandbox-managed NetworkPolicy，需要单独设计 Router / WorkloadManager / sandbox entrypoint 的 ingress/egress allow policy 和对应 e2e。

分类：

- 项目需要，核心兼容逻辑。

测试覆盖：

- `TestEnsureSandboxTemplateDisablesAgentSandboxDefaultNetworkPolicy`
- `TestEnsureSandboxTemplateUpdatesManagedNetworkPolicyToUnmanaged`
- k3s direct / warm-pool runtime 验证
- upstream/fork e2e CI

### `pkg/workloadmanager/codeinterpreter_controller_test.go`

关键行：

- `codeinterpreter_controller_test.go:49-62`：新增 `newTestReconcilerWithObjects`，支持给 controller-runtime fake client 预置对象。
- `codeinterpreter_controller_test.go:53`：给 test scheme 注册 `extensionsv1alpha1`，否则 fake client 无法正确存取 `SandboxTemplate` / `SandboxWarmPool` 这类 agent-sandbox extension CR。
- `codeinterpreter_controller_test.go:68-83`：新增 `testCodeInterpreterWithWarmPool` fixture，构造能触发 `ensureSandboxTemplate` 的最小 `CodeInterpreter`。
- `codeinterpreter_controller_test.go:86-100`：验证 create path：没有现存 `SandboxTemplate` 时，controller 新建出来的 template 必须显式带 `NetworkPolicyManagementUnmanaged`。
- `codeinterpreter_controller_test.go:102-133`：验证 update path：已有 `SandboxTemplate` 如果处于 `Managed`，下一次 reconcile 必须把它修正为 `Unmanaged`。

为什么改：

- `codeinterpreter_controller.go` 新增了一个兼容性行为：AgentCube 创建/维护的 `SandboxTemplate` 不能落到 agent-sandbox v0.4.6 的默认 `Managed` network policy 行为，否则可能阻断 AgentCube Router / WorkloadManager 到 sandbox entrypoint 的现有访问路径。
- 这个行为如果只靠 e2e 发现，失败形态会很晚才暴露成“session 超时 / entrypoint 连接失败”，定位成本高。单元测试直接检查 `SandboxTemplate.Spec.NetworkPolicyManagement`，能把问题收敛在 controller 层。
- 只测 create path 不够。真实升级场景可能已经存在旧的 `SandboxTemplate`，或者某次 reconcile 前该字段已经是 `Managed` / 空值。controller 不仅要新建正确，也要能把已有对象 reconcile 回 AgentCube 需要的状态。
- 这两个测试对应两个最容易回归的分支：新模板漏设字段，以及已有模板只更新 `PodTemplate` 但忘了修正 network policy management。

为什么这样改：

- 使用 controller-runtime fake client，而不是起真实 Kubernetes 集群，是因为这里要验证的是 AgentCube controller 写出的 `SandboxTemplate` spec，不需要 CNI 或 agent-sandbox controller 真正执行 NetworkPolicy。
- 新 helper 支持传入 initial objects，这样可以构造“已有 `SandboxTemplate`”的 update 场景。原来的 `setupTestReconciler` 只能创建空 client，覆盖不了这条分支。
- fixture 里设置 `WarmPoolSize=2`，因为 `SandboxTemplate` 是 warm pool 模式下给 `SandboxWarmPool` 使用的模板；设置 `AuthModeNone` 是为了绕过 PicoD public key cache 等无关前置条件，让测试只聚焦 network policy 字段。
- create 测试先调用 `ensureSandboxTemplate`，再从 fake client 读回同名对象并断言字段值。这样验证的是 controller 实际写入 Kubernetes object 的结果，而不是只验证本地变量。
- update 测试预置一个同名同 namespace 的 `SandboxTemplate`，并把 `NetworkPolicyManagement` 设成 `Managed`。调用 `ensureSandboxTemplate` 后再读回对象，确认 reconcile 会覆盖为 `Unmanaged`。这证明 #387 不只是“新建时正确”，也能修复已存在对象的 drift。
- 这两个测试不声称覆盖真实 CNI enforcement；真实连通性仍由 Day16 k3s runtime、warm-pool e2e 和 fork/upstream CI 补充验证。

分类：

- 项目需要，feature-specific test。

答辩句子：

```text
These tests are not generic field-copy tests. They pin the AgentCube-specific compatibility contract for agent-sandbox v0.4.6: CodeInterpreter-owned SandboxTemplates must stay NetworkPolicyManagement=Unmanaged on both create and update paths, otherwise agent-sandbox's default managed NetworkPolicy can change AgentCube's existing routing behavior.
```

### `pkg/workloadmanager/handlers.go`

这是 #387 最核心的行为变更文件。

关键行和原因：

| 行 | 改动 | 为什么 |
| --- | --- | --- |
| `30-31` | 使用 `sandboxv1alpha1` / `extensionsv1alpha1` 公开 API 包，移除 `controllers` 内部包依赖 | `SandboxPodNameAnnotation` 已从 internal controller 包迁到 public API 包，继续 import internal package 会编译失败 |
| `42-49` | 增加 direct watcher 失败错误：未注册、channel closed、empty sandbox | 避免 direct path wiring bug 被伪装成 2 分钟超时或 panic |
| `117-121`, `178-192` | rebase 到最新 `main` 后，把 ownerID 解析抽成 `resolveSandboxOwnerID` helper | 最新 `main` 合入 Keycloak/OIDC/RLAC 后，`handleSandboxCreate` 新增 identity owner 分支；和 #387 的 sandbox create/wait/error 逻辑合并后触发 gocyclo `16 > 15`，抽 helper 是最小 lint 修复 |
| `148-155` | 只在 direct Sandbox path 注册 `WatchSandboxOnce` | warm-pool claim path 的 serving Sandbox 名创建前未知，按 claim/template 名注册 watcher 会等错对象 |
| `166-196` | 抽出 create error response 和内部错误判断 | 降低复杂度，并把 watcher 内部错误映射为 generic 500，避免泄漏内部状态 |
| `218-248` | `waitForDirectSandboxReady` 增加 nil/closed/nil sandbox guard | 处理 Copilot/Gemini 指出的失败路径，直接返回明确错误 |
| `250-289` | 新增 `waitForClaimSandboxReady`，轮询 claim status，再读取 adopted Sandbox | `agent-sandbox v0.4.6` warm pool 通过 `SandboxClaim.Status.SandboxStatus.Name` 暴露实际 serving Sandbox |
| `291-295` | `waitForCreatedSandbox` 按 direct/claim 分派 | 保持 direct path 原 watcher 语义，claim path 使用 status polling |
| `322-336` | 使用 `createdSandbox` 的 annotation 和 name 获取 Pod IP；注释引用 `sandboxv1alpha1.SandboxPodNameAnnotation` 而不是硬编码 key | warm-pool Pod 属于 adopted Sandbox，不一定等于 claim 名；注释和依赖公开常量保持同一个 source of truth |
| `350-356` | claim path store 仍保存 claim name/namespace，并保留 placeholder `CreatedAt` / `ExpiresAt` | 后续 delete / GC 需要删除 SandboxClaim；TTL 也应来自 AgentCube session，不应被 warm pool 里旧 Sandbox 创建时间污染 |
| `366-370` | `UpdateSandbox` 错误统一包装 | 保持 store update 失败能被 API 层正确响应 |

为什么这样改：

- direct Sandbox：名字是 AgentCube 创建时确定的，原 watcher 模型仍然有效，继续使用 watcher 可以避免无意义的 polling。
- Copilot 对 `resultChan == nil` 的评论成立：Go 的 `select` 中对 nil channel 的 receive case 会永久 disabled，如果没有显式 guard，就只能等 context cancel 或 2 分钟 timer，看起来像普通 sandbox create timeout。当前实现已在 `waitForDirectSandboxReady` 开头返回 `errSandboxReadyWatcherNotRegistered`，并额外处理 closed channel 和 nil sandbox event。
- warm-pool SandboxClaim：实际 adopted Sandbox 名只有 claim controller 写入 status 后才知道，所以必须先读 claim status，再读真实 Sandbox Ready condition。
- store 里保存 claim 名：AgentCube delete / GC 逻辑根据 `Kind == SandboxClaim` 调用 `deleteSandboxClaim(namespace, name)`。如果这里保存 adopted Sandbox 名，后续会拿 sandbox 名删 claim，可能删不到真正 claim，造成资源泄漏。
- 使用 dynamic client：create path 已经根据 auth 选择 dynamic client。claim / sandbox polling 使用同一个 dynamic client，可以保持用户态权限模型一致，不引入新的 typed client plumbing。
- Copilot 关于 annotation 注释的建议是低风险但合理的维护性修正。代码已经使用 `sandboxv1alpha1.SandboxPodNameAnnotation`，本地 commit `bc8e85b` 只把注释也改成引用该常量，避免注释硬编码 `agents.x-k8s.io/pod-name` 后未来和依赖常量漂移。
- `resolveSandboxOwnerID` 是 rebase 到最新 `main` 后的最小结构性修复，不是新的业务语义。它保持 upstream main 的身份处理行为：没有 identity header 时 ownerID 为空并继续创建；public key 未缓存时返回 503 `identity verifier not ready`；其他 identity token 错误返回 401 `invalid identity token`。后续仍然把同一个 `ownerID` 传给 `buildSandboxByAgentRuntime` / `buildSandboxByCodeInterpreter`，并在 `sandboxEntry.OwnerID` 中保存。
- 这个 helper 的目的只是把身份错误分支从 `handleSandboxCreate` 主流程中移出，避免 `handleSandboxCreate` 同时承担 request validation、identity extraction、workload build、dynamic client selection、watch registration、create response 等过多分支而超过 lint 阈值。它没有改变 #387 的 warm-pool adopted Sandbox 逻辑。

分类：

- 项目需要，核心兼容逻辑。

测试覆盖：

- `TestServerCreateSandboxClaimUsesAdoptedSandboxButStoresClaimName`
- `TestWaitForDirectSandboxReadyWatcherFailures`
- `TestHandleSandboxCreate`
- k3s warm-pool runtime / upstream e2e

review 时要避免的错误说法：

- 不要说“编译过了所以兼容”。真正兼容点是 adopted Sandbox status lookup、pod annotation lookup、store claim name preservation、entrypoint probing。
- 不要说“claim 就是 sandbox”。在 v0.4.6 warm pool 中，claim 是 checkout 资源，serving object 是 claim status 指向的 adopted Sandbox。

### `pkg/workloadmanager/k8s_client.go`

关键行：

- `k8s_client.go:241-253`：新增 `getSandbox`。
- `k8s_client.go:278-290`：新增 `getSandboxClaim`。

这两个函数做什么：

- `getSandboxClaim`：从 Kubernetes API 重新读取当前 `SandboxClaim`，并转成 `extensionsv1alpha1.SandboxClaim`。
- `getSandbox`：从 Kubernetes API 读取真实的 `Sandbox`，并转成 `sandboxv1alpha1.Sandbox`。
- 两个 helper 都是 read-side helper，对应现有 `createSandbox` / `createSandboxClaim` / `deleteSandbox` 这些 dynamic client 写入和删除路径。

为什么必须新增读取逻辑：

- v0.1.1 的 warm pool 使用方式里，AgentCube 创建后主要等待自己创建出来的 `Sandbox` ready。
- 适配 agent-sandbox v0.4.6 后，warm-pool checkout 的主路径变成 `SandboxClaim`：
  - AgentCube 先创建 `SandboxClaim`；
  - agent-sandbox controller 再把一个 warm-pool 里的 sandbox 分配给这个 claim；
  - 分配结果写到 `SandboxClaim.Status.SandboxStatus.Name`；
  - 这个 name 指向真正承载流量的 adopted `Sandbox`。
- 因此 `waitForClaimSandboxReady` 不能只看本地刚构造出来的 claim 对象。本地对象没有 controller 后续写入的 status，必须每秒从 API server 重新读取最新的 `SandboxClaim`。
- 读到 `claim.Status.SandboxStatus.Name` 后，还不能直接认为 sandbox ready。claim 只是 checkout 资源，真正的 readiness condition、annotation、UID、namespace/name 都在 serving `Sandbox` 上，所以还要用 `getSandbox` 读取实际 `Sandbox`，再调用 `getSandboxStatus(createdSandbox)` 判断是否 `Ready`。

为什么用 dynamic client：

- AgentCube 这个文件里已有的 sandbox CRUD 路径本来就是 `dynamic.Interface + GVR`：
  - `SandboxGVR` 操作 `sandboxes.runtime.x-k8s.io`；
  - `SandboxClaimGVR` 操作 `sandboxclaims.extensions.x-k8s.io`。
- 创建 sandbox / claim 时已经通过 `runtime.DefaultUnstructuredConverter.ToUnstructured(...)` 转成 unstructured 再提交给 dynamic client。
- 新增的两个读取函数只是把同一条路径补完整：从 dynamic client 拿到 `*unstructured.Unstructured` 后，再通过 `runtime.DefaultUnstructuredConverter.FromUnstructured(...)` 转回 typed Go struct。
- 这样 handler 层可以用正常的强类型字段访问：
  - `claim.Status.SandboxStatus.Name`
  - `sandbox.Status.Conditions`
  - `sandbox.Annotations`
- 如果不用 converter，而是在 `map[string]interface{}` 里手写路径解析，代码会更脆弱，也更难 review。

为什么不新增 agent-sandbox typed client：

- 这次 PR 的目标是最小化适配 agent-sandbox v0.4.6 warm pool，不是重做 Kubernetes client 架构。
- 引入 typed client 会要求给 `K8sClient` 增加新的 clientset wiring，并且要重新检查 workload-manager 当前的 user-token / kubeconfig / RBAC 路径。
- dynamic client 已经是当前代码创建、删除 sandbox 资源的既有抽象，继续复用能保证读取、创建、删除走同一套认证和权限模型。
- 对 review 来说，这个选择的重点是“补齐缺失读取能力”，而不是扩大 PR 范围。

错误处理为什么这样写：

- `Get` 失败时把 namespace/name 包到错误里，例如 `failed to get sandbox claim ns/name`，方便从日志里直接定位是哪一个 claim 或 sandbox 没取到。
- conversion 失败单独报 `failed to convert ...`，这类错误通常说明依赖版本、CRD schema 或对象结构不匹配，和普通 API server get 失败不是一类问题。
- 在 `waitForClaimSandboxReady` 里，context canceled / deadline exceeded 会立即返回；普通 get / status 未就绪会继续等待直到 2 分钟超时。
- 这个等待策略符合 controller 异步写 status 的现实情况：claim 刚创建时 status 可能为空，claim 指向的 sandbox 也可能还没被 API server 读取到或还没 Ready。

分类：

- 项目需要，核心兼容 helper。

测试覆盖：

- `TestServerCreateSandboxClaimUsesAdoptedSandboxButStoresClaimName` 通过 `dynamicfake` 和 unstructured object 模拟 claim / sandbox。
- 这个测试实际覆盖了 `getSandboxClaim -> claim.Status.SandboxStatus.Name -> getSandbox -> getSandboxStatus` 这条适配链路。
- 测试重点不是单独测试 getter，而是验证 handler 在 warm-pool claim 模式下能找到 adopted sandbox，同时 store 里仍然保留 AgentCube session 对应的 claim name。
- 本地验证命令：`go test ./pkg/workloadmanager -count=1`；完整 runtime 验证还需要 k3s warm-pool e2e。

review 时可以这样解释：

```text
k8s_client.go adds read-side companions for the existing dynamic-client create/delete helpers. In agent-sandbox v0.4.6 warm-pool mode, AgentCube first creates a SandboxClaim, then the agent-sandbox controller records the adopted Sandbox name in claim.status.sandboxStatus.name. The workload-manager therefore has to poll the latest SandboxClaim, resolve it to the real Sandbox, and check readiness/annotations on that Sandbox. The helpers keep this logic on the existing dynamic client path and convert unstructured CRs back to typed structs so the handler can access status and annotations safely.
```

### `pkg/workloadmanager/sandbox_helper.go`

关键行：

- `sandbox_helper.go:50-60`：placeholder 记录 `CreatedAt`，如果 CR 没有 creationTimestamp，则用 `time.Now()`。
- `sandbox_helper.go:61-65`：placeholder 记录 `ExpiresAt`，优先使用 `Sandbox.Spec.Lifecycle.ShutdownTime`，否则使用 `time.Now().Add(DefaultSandboxTTL)`。
- `sandbox_helper.go:77-104`：`buildSandboxInfo` 从真实 `Sandbox` 生成最终 store 信息，但 claim path 会在 `handlers.go` 中把时间字段回填为 placeholder 的时间。

为什么改：

- warm pool adopted Sandbox 可能早于本次用户 session 创建。
- 最终 store 需要混合两类信息：
  - serving Sandbox 的 UID / Ready status / entrypoints；
  - AgentCube session 的 claim name / CreatedAt / ExpiresAt。
- 如果完全使用 adopted Sandbox 的 `CreationTimestamp`，用户 session TTL 可能被 warm pool 里旧 Sandbox 创建时间污染。
- `createSandbox` 一开始就会调用 `StoreSandbox(ctx, placeholder)`，也就是先在 store 里占住这个 session。
- store 的 `StoreSandbox` 要求 `ExpiresAt` 非零，并且会立刻把 `ExpiresAt.Unix()` 写进 expiry sorted-set。这个索引后面被 `ListExpiredSandboxes` 和 GC 使用。
- store 的 `UpdateSandbox` 只更新 session JSON，不更新 expiry / last-activity sorted-set。因此 placeholder 阶段写入的 `ExpiresAt` 必须已经是正确的 session 过期时间，不能等 adopted Sandbox ready 之后再修。

为什么这样改：

- 创建 placeholder 时就记录本次 session 的生命周期时间：
  - `CreatedAt`：表示 AgentCube 这次 session 创建/占位时间，不是 warm-pool sandbox 在池子里诞生的时间。
  - `ExpiresAt`：表示这次 session 的最大存活期限，用于 store expiry index 和 GC。
- direct sandbox path 中，`sandboxCR.GetCreationTimestamp()` 通常在 create 前为空，所以 fallback 到 `time.Now()` 能保证 placeholder 可写入 store。
- warm-pool claim path 中，最终 ready 的 adopted Sandbox 可能已经存在很久；`buildSandboxInfo(createdSandbox, ...)` 得到的是 serving Sandbox 的对象时间，不一定是本次用户 session 的时间。
- 因此 `handlers.go` 在 `sandboxClaim != nil` 时执行：
  - `storeCacheInfo.Name = sandboxClaim.Name`
  - `storeCacheInfo.SandboxNamespace = sandboxClaim.Namespace`
  - `storeCacheInfo.ExpiresAt = placeholder.ExpiresAt`
  - `storeCacheInfo.CreatedAt = placeholder.CreatedAt`
- 这样最终 store 里同时保留两类语义：
  - routing/runtime 需要的真实 serving Sandbox 信息：`SandboxID`、entrypoints、ready status；
  - AgentCube session 生命周期需要的 claim 名和时间字段：`Name`、`CreatedAt`、`ExpiresAt`。

如果不这么做会怎样：

- 如果 `CreatedAt` 用 adopted Sandbox 的 creationTimestamp，warm-pool 里预热很久的 sandbox 会让新 session 看起来“很早就创建了”，GC 在缺少 `LastActivityAt` 时 fallback 到 `CreatedAt`，可能提前判断 idle。
- 如果 `ExpiresAt` 用 adopted Sandbox 的 creationTimestamp + 默认 TTL，或者 placeholder 里没有正确写入 `ShutdownTime`，`MaxSessionDuration` 就可能失效。
- 因为 expiry sorted-set 是 `StoreSandbox` 阶段写的，不是最终 `UpdateSandbox` 阶段重建的，错误的 `ExpiresAt` 会直接影响后续过期回收。
- 如果 `ExpiresAt` 为空，store 会直接拒绝写入：`StoreSandbox: sandbox expired at is zero`。

分类：

- 项目需要，生命周期语义修正。

测试覆盖：

- `TestBuildSandboxPlaceHolder_TableDriven` 覆盖默认 TTL、显式 `ShutdownTime`、短 TTL、warm-pool path 的 `MaxSessionDuration`。
- handler claim test 验证 claim path 的 store 写入形态。
- runtime delete / cleanup 验证。

review 时可以这样解释：

```text
The placeholder is stored before the Kubernetes Sandbox or SandboxClaim finishes provisioning, and StoreSandbox immediately indexes ExpiresAt for GC. In the warm-pool path, the ready object is an adopted Sandbox that may have been created before this user session. Therefore we keep CreatedAt/ExpiresAt from the session placeholder and later combine them with the adopted Sandbox runtime fields, instead of letting the warm-pool Sandbox creation timestamp define the AgentCube session lifecycle.
```

### `pkg/workloadmanager/handlers_test.go`

关键行：

- `handlers_test.go:86`：test fixture 使用 `sandboxv1alpha1.SandboxPodNameAnnotation`。
- `handlers_test.go:106-119`：`recordingStore` 返回 embedded fake store error，并 deep-copy `EntryPoints`。
- `handlers_test.go:302-410`：验证 claim path 使用 adopted Sandbox，但 store / response 保留 claim name。
- `handlers_test.go:412-431`：验证 direct watcher nil、closed channel、empty sandbox 失败路径。
- `handlers_test.go:524-535`：context canceled / deadline response mapping。

为什么改：

- #387 的核心风险不在“能创建 object”，而在 claim/adopted sandbox 名称分离后是否仍能正确查 Pod IP、写 store、响应 Router、后续 delete。
- Copilot 指出原 `recordingStore` 测试 fake 忽略 update error 且 shallow copy slice，可能掩盖测试问题。
- 这条 Copilot 评论是有效的测试质量问题。如果 fake store 的 `UpdateSandbox` 返回错误但 wrapper 忽略它，测试可能误判“store update 成功”；如果 `lastUpdated` 只是 `copied := *sandbox` 的浅拷贝，`EntryPoints` slice 仍和原对象共享底层数组，后续修改可能污染断言样本。

为什么这样改：

- 用 `dynamicfake` + unstructured 模拟真实 dynamic client path，而不是绕过转换逻辑。
- test case 明确 claim 名 `ci-claim` 和 adopted sandbox 名 `warm-pool-sandbox-abc` 不同，这正是 v0.4.6 适配风险。
- `recordingStore.UpdateSandbox` 先调用 embedded `fakeStore.UpdateSandbox` 并返回其错误，保证测试不会吞掉 store failure。
- `recordingStore.UpdateSandbox` 对 `EntryPoints` 做 `append([]types.SandboxEntryPoint(nil), sandbox.EntryPoints...)`，切断 slice alias。`SandboxInfo` 当前唯一需要额外处理的引用字段是 `EntryPoints` slice，其他被断言字段都是 string/time/duration 这类值类型。
- watcher failure test 覆盖 negative path，避免只测 happy path。

答辩句子：

```text
This was a valid test-fake issue rather than a runtime bug. The recording store now propagates the embedded store error and deep-copies EntryPoints before saving lastUpdated, so the test cannot accidentally hide an UpdateSandbox failure or assert against a later-mutated slice.
```

分类：

- 项目需要，feature-specific unit tests。

### `test/e2e/e2e_test.go`

关键行：

- `e2e_test.go:57-59`：增加 `ownerKindSandbox`。
- `e2e_test.go:1183-1195`：warm-pool pod count / name helper 改为复用 `listWarmPoolPods`。
- `e2e_test.go:1208-1251`：新增 `listWarmPoolPods`，先收集 warm-pool-owned Sandbox UID，再匹配 Pod ownerRef。
- `e2e_test.go:1253-1263`：`isWarmPoolSandbox` 过滤 deleting sandbox 和空 UID。
- `e2e_test.go:1265-1274`：`isWarmPoolPodOwner` 同时兼容旧 direct owner 和新 `Sandbox` owner UID。
- `e2e_test.go:1303-1305`：ready check 复用统一 warm pool pod list。

为什么看起来删改多：

- 这个文件的 diff 是 `75 insertions / 51 deletions`，主要不是新增测试场景，而是替换 warm-pool Pod discovery helper。
- 原代码里有三份近似逻辑：
  - `countWarmPoolPods`：list pods，然后按 `Pod.ownerReferences.kind == SandboxWarmPool` 计数；
  - `getWarmPoolPodNames`：list pods，然后按同样 ownerRef 取名字；
  - `arePodsReady`：再次 list pods，然后按同样 ownerRef 判断 ready。
- 如果只在其中一处补新版 ownerRef，另外两处仍会用旧判断，e2e 会出现“计数通过但 ready 判断失败”或“初始 Pod 记录和后续验证不是同一套语义”的问题。
- 所以这次删掉的是重复的旧 Pod 过滤循环，把“什么算 warm-pool Pod”收敛到 `listWarmPoolPods` 一个 helper 里。review 时要强调这是测试语义修正，不是为了做代码清洁而大改 e2e。

为什么改：

- AgentCube 的 warm-pool e2e 不是只看请求能不能返回，它还验证三件事：
  - warm pool 初始能创建到 `warmPoolSize` 个 ready Pod；
  - 执行一次 CodeInterpreter 请求后，被 claim 的 Pod 来自初始 warm pool，而不是冷启动新建；
  - claim 后 warm pool 能 refill 回目标大小，load test 后也保持容量。
- 在旧 `agent-sandbox v0.1.1` 形态里，warm-pool Pod 可以直接通过 `Pod.ownerReferences` 找到 `SandboxWarmPool`。
- 在 `agent-sandbox v0.3+ / v0.4.6` 形态里，warm pool 会先创建完整 `Sandbox` CR，Pod 通常是由 `Sandbox` 拥有，owner 链变成：
  - `SandboxWarmPool -> Sandbox -> Pod`
- 因此旧 helper 只看 `Pod.ownerRef.kind == SandboxWarmPool` 会数不到新版 warm-pool Pod，直接导致：
  - `waitForWarmPoolReady` 一直等不到 expected count；
  - `getWarmPoolPodNames` 记录不到初始池子 Pod；
  - `arePodsReady` 不能判断新版池子 Pod 是否 ready；
  - `cleanupCodeInterpreter` / warm-pool load 的容量断言失真。
- 这属于 agent-sandbox runtime 行为变化带来的测试适配，不是无关重构。

为什么这样改：

- `listWarmPoolPods` 先 list `Sandbox`，收集仍属于目标 `SandboxWarmPool` 的 `Sandbox.UID`：
  - 只接受 ownerRef 是 `SandboxWarmPool/<CodeInterpreter name>` 的 Sandbox；
  - 跳过 `DeletionTimestamp != nil` 的 Sandbox；
  - 跳过空 UID，避免后续 ownerRef UID 匹配没有意义。
- 然后 list namespace 下的 Pod，对每个 Pod 的 ownerRef 做两种兼容判断：
  - 旧形态：`Pod.ownerRef.kind == SandboxWarmPool && ownerRef.name == CodeInterpreter name`；
  - 新形态：`Pod.ownerRef.kind == Sandbox && ownerRef.uid` 在 warm-pool Sandbox UID 集合里。
- 新形态必须用 UID 匹配，而不是只用 name：
  - Kubernetes ownerRef 本来就包含 UID，UID 才是对象身份；
  - warm-pool Sandbox 可能是 generated name；
  - 删除/重建、refill、controller rolling 期间，按 name 判断更容易误把旧对象或同名新对象当成同一个 owner。
- 跳过 `DeletionTimestamp != nil` 的 Pod，是为了让 helper 统计“仍属于 warm pool 容量的活跃 Pod”，避免 terminating object 在 refill / cleanup 过程中污染容量判断。
- `seen[pod.Name]` 是防御性去重：如果一个 Pod 同时满足兼容路径，或者 ownerRef 列表里出现多个可匹配 owner，不会被重复计数。
- `countWarmPoolPods`、`getWarmPoolPodNames`、`arePodsReady` 都复用同一个 `listWarmPoolPods`，保证“计数、初始 Pod 名记录、ready 判断”使用同一套 warm-pool membership 定义。

和主 e2e 流程的关系：

- `TestCodeInterpreterWarmPool` 调用 `verifyWarmPoolReady`：
  - `waitForWarmPoolReady` 用 `countWarmPoolPods` 等池子容量；
  - `getWarmPoolPodNames` 记录初始池子 Pod 名。
- 执行 CodeInterpreter 后，`verifyWarmPoolStatus` 会查：
  - `CodeInterpreter -> SandboxClaim`；
  - `SandboxClaim -> adopted Sandbox`；
  - `adopted Sandbox -> Pod`；
  - 然后确认这个 Pod 的名字在初始 warm-pool Pod 列表里。
- 如果 `getWarmPoolPodNames` 仍然只支持旧 direct ownerRef，它记录的初始列表在 v0.4.6 下可能为空，这个“是否真的从 warm pool 取 Pod”的核心断言就失效了。
- `TestCodeInterpreterWarmPoolLoad` 结束后再次调用 `verifyWarmPoolReady`，所以 load 场景也依赖同一个 helper 判断 refill 后容量是否恢复。

为什么不只保留新版判断：

- #387 的目标是把 AgentCube 适配到 current stable `agent-sandbox v0.4.6`，但 e2e helper 没必要主动破坏旧 controller shape 的可解释性。
- 保留 direct `SandboxWarmPool -> Pod` 兼容分支，可以让测试在旧形态和新形态下都描述同一个业务语义：这些 Pod 是否仍属于目标 CodeInterpreter 的 warm pool。
- 这也降低 review 风险：helper 不是“只为新版本硬编码”，而是把 warm-pool ownership 的两种已观察形态都纳入。

测试语义是否和之前一致：

- 用户可见的 e2e 语义保持一致：仍然验证 warm pool ready、Pod ready、初始池子 Pod 名、一次请求后是否从初始池子 claim、执行后是否 refill 回 `warmPoolSize`、load 后是否仍保持容量。
- helper 实现语义不是简单“完全相同”，而是把 warm-pool membership 的定义从旧的单一路径扩展为两条路径：
  - 旧语义仍保留：`Pod.ownerRef == SandboxWarmPool/<CodeInterpreter name>`。
  - 新语义新增：`Sandbox.ownerRef == SandboxWarmPool/<CodeInterpreter name>`，并且 `Pod.ownerRef.uid` 指向这个 warm-pool-owned Sandbox。
- 因此这不是降低测试强度，而是让同一组 e2e 断言能在旧 controller shape 和 `agent-sandbox v0.4.6` 新 controller shape 下都识别正确对象。

是否有“删除之前单元测试”的风险：

- 没有删除 `Test...` 或 `t.Run` 测试用例。`test/e2e/e2e_test.go` 中保留了原来的 warm-pool e2e 流程，变化只在 helper 层。
- 本 PR 反而新增/加强了 focused tests：
  - `TestEnsureSandboxTemplateDisablesAgentSandboxDefaultNetworkPolicy`
  - `TestEnsureSandboxTemplateUpdatesManagedNetworkPolicyToUnmanaged`
  - `TestServerCreateSandboxClaimUsesAdoptedSandboxButStoresClaimName`
  - `TestWaitForDirectSandboxReadyWatcherFailures`
- 真实风险不是“删掉测试”，而是 helper 统一后如果 `listWarmPoolPods` 判断错，`countWarmPoolPods` / `getWarmPoolPodNames` / `arePodsReady` 会一起受影响。
- 这个风险通过三点缓解：
  - 保留旧 direct ownerRef 分支，旧语义没有丢；
  - 新版 `Sandbox -> Pod` 分支用 UID 匹配，避免 name-based 误判；
  - fork CI e2e 和 Day16 k3s warm-pool / warm-pool load runtime 都跑过。
- 如果 reviewer 要求进一步降低 helper 回归风险，可以补非常小的 focused unit test 只测 `isWarmPoolSandbox` / `isWarmPoolPodOwner` 两个纯函数。但就当前 PR 最小修原则来说，已有 e2e 通过已经覆盖主路径，不必主动再扩大修改。

分类：

- 项目需要，e2e 测试适配。

测试覆盖：

- fork validation PR [ranxi2001/agentcube#4](https://github.com/ranxi2001/agentcube/pull/4) `Agentcube E2E Tests / e2e-test`
- Day16 k3s warm-pool e2e / warm-pool load validation

review 时可以这样解释：

```text
Most of the e2e_test.go diff replaces duplicated warm-pool Pod discovery logic with a single helper. The old helper only recognized Pods directly owned by SandboxWarmPool, but agent-sandbox v0.4.6 creates warm-pool Sandboxes first and the Pods are owned by those Sandboxes. The new helper collects Sandbox UIDs owned by the target SandboxWarmPool and then matches Pod ownerReferences by UID, while keeping the old direct SandboxWarmPool owner path for compatibility. This is necessary for the warm-pool e2e assertions that record the initial pool Pods, verify the claimed Pod came from that pool, and check refill after execution/load.
```

### `client-go/clientset/versioned/fake/clientset_generated.go`

这是生成文件，放在后面统一解释。review 时不要把它作为手写核心逻辑来讲。

关键行：

- `clientset_generated.go:89`：`IsWatchListSemanticsUnSupported() bool`。

为什么改：

- 这是 `k8s.io/code-generator v0.35.4` 生成输出的一部分。
- Kubernetes `client-go v0.35.x` informer / reflector 增加 watch-list semantics 的 optional interface 检查；fake client 需要声明不支持 watch-list 语义。

为什么这样改：

- 不手工改 generated file 的方法名。
- 方法名里 `UnSupported` 的拼写看起来奇怪，但它匹配当前 `client-go@v0.35.4` 的 optional interface。把它改成更自然的拼写反而会破坏接口匹配。

分类：

- 项目需要，生成文件。
- 不是本地需要。

测试覆盖：

- `make gen-check`
- package tests / CI build

### `client-go/informers/externalversions/runtime/v1alpha1/agentruntime.go`

这是生成文件。

关键行：

- `agentruntime.go:60`：`cache.ToListWatcherWithWatchListSemantics(&cache.ListWatch{...}, client)`。

为什么改：

- `code-generator v0.35.4` 对 informer 生成方式的变化。
- 与 `client-go v0.35.4` watch-list semantics 支持对齐。

为什么这样改：

- 这不是业务逻辑重写，而是 generator 的标准输出。
- 手工保留旧 `&cache.ListWatch{}` 会导致 `make gen-check` 失败。

分类：

- 项目需要，生成文件。

### `client-go/informers/externalversions/runtime/v1alpha1/codeinterpreter.go`

同 `agentruntime.go`，这是生成文件。

关键行：

- `codeinterpreter.go:60`：`cache.ToListWatcherWithWatchListSemantics(&cache.ListWatch{...}, client)`。

答辩重点：

- 这是 Kubernetes generated informer 对齐，不是为 warm pool 手写的 informer behavior。

### `client-go/informers/externalversions/factory.go`

这是生成文件。

为什么改：

- `code-generator v0.35.4` 的文档注释输出变化。
- 包括 deprecated 注释空行和示例 `context.WithCancel(context.Background())`。

为什么这样改：

- 保持 generated output，不手工挑选注释。

分类：

- 项目需要，生成文件，但不影响 runtime 行为。

### `manifests/charts/base/crds/runtime.agentcube.volcano.sh_agentruntimes.yaml`

这是生成文件。

关键行：

- `CRD:8045-8062`：新增 / 更新 Kubernetes Pod schema 中的 `userAnnotations`。
- `CRD:8488-8505`：新增 / 更新 Pod schema 中的 `workloadRef`。
- 其他 diff 主要是 Kubernetes upstream OpenAPI 描述文字变化，例如 `resizePolicy`、`resourceClaims`、`toleration.operator`。

为什么改：

- AgentCube 的 CRD 包含嵌套 Kubernetes Pod template schema。
- Kubernetes API 版本从 `v0.34.1` 到 `v0.35.4` 后，controller-gen / API schema 输出变化。

为什么这样改：

- CRD 是生成物，应与 API types / dependency stack 同步。
- 如果只改 Go 依赖不提交 CRD 生成差异，`make gen-check` 会失败，实际 chart 安装也可能和代码 schema 不一致。

分类：

- 项目需要，生成文件。
- 不是业务手写变更。

测试覆盖：

- `make gen-check`
- Helm / e2e 安装路径通过 fork CI。

## go.mod 变更专门解释

用户指出的 `go.mod` diff 是 review 中最容易被问的问题。建议答辩时按三层解释：

第一层：Go 版本不是本 PR 目标。

```text
The Go toolchain update was split out and merged in #391. This PR is based on the post-#391 main branch, so the remaining go.mod changes are dependency stack changes for agent-sandbox v0.4.6.
```

第二层：`k8s.io/* v0.35.4` 是 `agent-sandbox v0.4.6` 的依赖要求。

```text
agent-sandbox v0.4.6 itself depends on k8s.io/api, apimachinery, client-go, and apiextensions-apiserver v0.35.4, and on controller-runtime v0.23.3. Keeping AgentCube on v0.34.1 would leave generated clients and Kubernetes API types out of sync with the selected sandbox dependency.
```

第三层：codegen 和 generated files 是同步结果。

```text
Because the Kubernetes stack moved to v0.35.4, hack/update-codegen.sh now uses code-generator v0.35.4. The client-go and CRD diffs are generated outputs required by make gen-check.
```

如果 reviewer 问 `go mod download -json` 的 JSON 有什么用：

```text
The JSON is only Go module download metadata. We read its Dir field to locate kube_codegen.sh in the module cache without using go get. This keeps code generation tool discovery read-only for go.mod/go.sum.
```

如果 reviewer 问为什么有 indirect 依赖删除：

```text
Those are go mod tidy results after the dependency graph changed. They are not hand-picked removals.
```

## Review Q&A 草稿

### Q: Why does this PR target `agent-sandbox v0.4.6` instead of `v0.5.0rc1`?

`v0.4.6` is the current stable Go module `@latest`. `v0.5.0rc1` is a release candidate that resolves as a pseudo-version and also changes the API surface from `v1alpha1` to `v1beta1`. A minimal bump experiment showed missing `v1alpha1` packages, `SandboxSpec.Replicas` replaced by `OperatingMode`, and `SandboxClaimSpec.TemplateRef` replaced by required `WarmPoolRef`. That is a separate API migration, tracked in Day18, and should not be hidden inside #387.

### Q: Why not continue to watch the original sandbox name for warm-pool sessions?

For direct Sandbox creation the original name is correct, so the watcher remains. For warm-pool sessions the initial object is a `SandboxClaim`; the actual serving `Sandbox` is chosen by agent-sandbox and exposed through `SandboxClaim.Status.SandboxStatus.Name`. Watching the claim/template name can miss the Ready event and time out even when the adopted Sandbox is ready.

### Q: Why does store keep the SandboxClaim name instead of the adopted Sandbox name?

AgentCube later deletes based on `Kind` and stored `Name`. For `Kind == SandboxClaim`, delete / GC calls `deleteSandboxClaim(namespace, name)`. If we store the adopted Sandbox name, cleanup will try to delete a claim with the wrong name and can leak the real claim/session resource. The store still records adopted Sandbox UID and entrypoints for runtime identity and routing.

### Q: Why force `NetworkPolicyManagementUnmanaged`?

Kubernetes `NetworkPolicy` is pod-level traffic control. In `agent-sandbox v0.4.6`, `SandboxTemplate` defaults to `networkPolicyManagement: Managed`; if no custom policy is provided, agent-sandbox creates a strict default policy that only allows ingress from its own Sandbox Router and restricts egress. AgentCube currently routes through its own Router / WorkloadManager path and does not create matching allow rules for that policy, so leaving the default can make a Ready sandbox unreachable from AgentCube. Setting `Unmanaged` preserves the existing connectivity contract until AgentCube intentionally designs its own network policy integration.

### Q: Why are generated files included?

The PR upgrades the Kubernetes dependency stack to the version required by `agent-sandbox v0.4.6`. `client-go` informers, fake client, and CRD schema are generated outputs from the matching `code-generator` / Kubernetes API stack. Keeping old generated files would fail `make gen-check` and leave manifests out of sync.

### Q: Is `Dockerfile.picod` part of the compatibility fix?

No. It is image hygiene only and not required for agent-sandbox compatibility. I verified the branch still passes `go test ./pkg/workloadmanager`, `make build-all`, and `docker build -f docker/Dockerfile.picod ...` without this change, so it should be removed from #387 under the minimal-fix rule. If needed, it can be proposed later as a separate cleanup PR.

## 测试覆盖矩阵

| 风险 | 覆盖方式 | 证据 |
| --- | --- | --- |
| 旧 internal annotation import 编译失败 | build / tests | non-e2e Go tests, `make build-all` |
| warm-pool claim 名和 adopted sandbox 名不同 | focused unit test | `TestServerCreateSandboxClaimUsesAdoptedSandboxButStoresClaimName` |
| direct watcher nil / closed / empty event 导致 timeout 或 panic | focused unit test | `TestWaitForDirectSandboxReadyWatcherFailures` |
| network policy 默认值阻断 AgentCube data path | controller unit tests + runtime | `TestEnsureSandboxTemplate*`, Day16 k3s runtime |
| e2e helper 不能识别新版 warm pool Pod ownership | e2e helper change + CI | fork validation PR [ranxi2001/agentcube#4](https://github.com/ranxi2001/agentcube/pull/4) e2e green |
| generated files drift | codegen check | `make gen-check`, CI `Codegen Check` |
| dependency stack build/lint/coverage | CI + local | fork validation PR [ranxi2001/agentcube#4](https://github.com/ranxi2001/agentcube/pull/4) all green, upstream #387 checks green |
| real AgentCube user workflow | runtime validation | direct/warm-pool e2e, SDK, LangChain, MCP, math-agent LLM e2e from Day16 |

已通过的主要本地 / fork 验证：

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

fork CI evidence：

- Fork PR：`https://github.com/ranxi2001/agentcube/pull/4`
- Base：`release-pr387-go1264` -> `a31651e`
- Head：`ci/pr387-rebase-go1264` -> `5867183`
- 结果：Codespell、Python SDK Tests、Python Lint、Copyright Check、Codegen Check、Agentcube CI Workflow build、golangci-lint、coverage、e2e-test 全绿。

runtime evidence 来自 Day16：

- k3s direct CodeInterpreter e2e：通过。
- warm pool e2e：通过。
- warm pool load 100/100：通过。
- Python SDK：通过。
- LangChain sandbox：通过。
- MCP streamable HTTP / stdio：通过。
- math-agent LLM e2e：通过。

## 仍然不能过度声明的内容

- #387 不支持 `agent-sandbox v0.5.0rc1` / `v1beta1`；该方向已拆到 Day18。
- #387 不实现 Sleep/Resume state machine。
- #387 不声明现有 `v1alpha1` CRD 集群可以无缝原地升级到未来 `v1beta1` CRD。
- #387 不新增 AgentCube 自己的 NetworkPolicy 设计，只是保留现有通信语义。
- `Dockerfile.picod` cleanup 不是 compatibility 必需项，已从 #387 移除；如后续需要，拆到单独 cleanup PR。

## 2026-06-22 tide merge conflict 处理记录

现象：

- #387 checks 中 `tide` 显示 `Not mergeable. PR has a merge conflict`。
- 这不是代码测试失败，而是 PR head `bc8e85b` 落后于最新 `upstream/main`，tide 无法自动合并。

本地验证分支：

- worktree：`/home/agentcube-agent-sandbox-latest`
- branch：`rebase/pr387-on-bed6bd4`
- base：`upstream/main bed6bd4`
- head：`c2633c5 fix: reduce sandbox create handler complexity after rebase`

冲突来源：

- 最新 `upstream/main` 合入了 Keycloak/OIDC/RLAC 相关改动，`pkg/workloadmanager/handlers.go` 新增 ownerID 提取和 store ownership 字段。
- #387 同一文件改了 Sandbox / SandboxClaim 创建、ready wait、错误映射和 warm-pool adopted Sandbox 逻辑。
- rebase 时需要同时保留 main 的 ownerID 行为和 #387 的 agent-sandbox v0.4.6 适配行为。

冲突处理原则：

- 保留 upstream main 的 ownerID 提取、auth error mapping、`sandboxEntry.OwnerID`、response `OwnerID` 行为。
- 保留 #387 的 direct Sandbox watcher、SandboxClaim adopted Sandbox resolution、claim-name store cleanup 语义。
- `go.sum` 以 rebase 后 `go mod tidy` 的结果为准，避免手工选择导致 dependency graph 漂移。
- 不引入无关 cleanup，不改 `docker/Dockerfile.picod`。

rebase 后新增问题：

- `make lint` 发现 `handleSandboxCreate` cyclomatic complexity 从 main 和 #387 合并后的 16 超过阈值 15。
- 最小修复为抽出 `resolveSandboxOwnerID(*http.Request) (ownerID string, statusCode int, errMsg string)` helper。
- helper 保持原有行为：无 identity header 允许匿名 owner；public key 未缓存返回 503 `identity verifier not ready`；其他 identity token 错误返回 401 `invalid identity token`。
- 这次新增 commit 实际只改 `pkg/workloadmanager/handlers.go`：`c2633c5 fix: reduce sandbox create handler complexity after rebase`。

本地验证结果：

```bash
go test ./pkg/workloadmanager -count=1
make lint
go test ./test/e2e -run '^$' -count=1
make gen-check
make build-all
go test -race ./pkg/workloadmanager -count=1
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
git diff --check upstream/main...HEAD
git diff --exit-code
```

结论：

- tide merge conflict 可以通过把 #387 分支 rebase 到 `upstream/main bed6bd4` 解决。
- 已随 rebase 带一个最小 lint 修复 commit `c2633c5`。
- 用户确认后已执行：`git push --force-with-lease origin rebase/pr387-on-bed6bd4:feat/agent-sandbox-latest`，#387 head 已更新到 `c2633c5`。

## 下周 review 前检查清单

- 能解释 `go.mod` 每个 direct dependency bump 的来源，尤其是 `k8s.io/* v0.35.4`。
- 能说明 `SandboxClaim.Status.SandboxStatus.Name` 是 warm-pool serving Sandbox 的真实来源。
- 能说明为什么 store 保存 claim 名而不是 adopted Sandbox 名。
- 能说明 network policy 为什么选 Unmanaged，以及这不是长期网络安全设计，只是保持当前 AgentCube connectivity。
- 能说明 generated files 为什么不能手改，也不能省略。
- 按最小修原则，`Dockerfile.picod` cleanup 已从 #387 移除；review 时只需说明它不属于 compatibility 必需集合。
- 不主动把 Day18 `v0.5.0rc1` 内容塞进 #387 review；除非 reviewer 继续问 target version，再用 Day18 证据回答。
