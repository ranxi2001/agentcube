# Day50：agent-sandbox v0.5.2 独立适配、分层验证与容量边界

## 1. 任务背景

AgentCube PR #387 已经合并，当前主干的稳定基线是 `agent-sandbox v0.4.6`。2026-07-17，
`kubernetes-sigs/agent-sandbox v0.5.2` 正式发布，社区 Issue #438 的 assignee 也已经开始跟进正式适配。

本轮没有竞争 #438 的 upstream ownership，而是在个人 fork 做一份独立实现，目的有三个：

1. 在看到他人实现前，先形成自己的 API、生命周期和 migration 判断。
2. 等 #438 对应 PR 出现后，用冻结的 commit 做 diff-to-diff 对比，而不是被作者方案先入为主。
3. 提前构造 review checklist 和运行证据，缩短后续正式 review 的反馈周期。

> 注释：这里的 “blind implementation” 不是不看官方资料，而是不看 #438 作者未来的实现分支。输入只包括最新
> `upstream/main`、agent-sandbox v0.5.2 官方 release/API/migration guide、AgentCube 当前源码和既有 Day41 运行证据。

> 分析：个人 fork 允许我们学习和验证，但不改变社区 ownership。没有创建 upstream PR、没有向 #438 追加催促，
> 也没有读取 assignee 的未发布代码。

## 2. 冻结边界

| 项目 | 值 |
| --- | --- |
| AgentCube base | `upstream/main@146b75fc4b98f214988b5d0c5059a55a2bc1f9da` |
| fork branch | `compat/agent-sandbox-v052-independent` |
| prerequisite commit | `d70ab94 refactor: use standard HTTP and scheme APIs` |
| adapter commit | `2d90b07 compat: adapt agent-sandbox v0.5.2` |
| remote | `origin/compat/agent-sandbox-v052-independent` |
| upstream action | none |

代码分支：

<https://github.com/ranxi2001/agentcube/tree/compat/agent-sandbox-v052-independent>

两条提交有意分层：

- `d70ab94` 只处理新版依赖触发的 Go/controller-runtime deprecated API。
- `2d90b07` 只表达 agent-sandbox v0.5.2 的 API、控制器、E2E 和文档适配。

> 分析：以后比较 #438 作者实现时，应主要比较 `2d90b07^..2d90b07`。如果把 lint 前置、依赖升级和业务适配
> 混成一个提交，很难判断双方真正不同的是设计，还是工具链副作用。

## 3. 官方 v0.5.2 合同

### 3.1 不能把变化简化为 “alpha API 被删除”

v0.5.2 的真实合同是：

- `v1beta1` 是 hub/storage version，controller 按 beta 对象工作。
- `v1alpha1` Go package 和 served CRD version 仍保留，作为 conversion spoke 支撑迁移。
- clean install 的 `status.storedVersions` 应只有 `v1beta1`。

因此，旧 alpha import 在纯依赖升级后仍可能编译通过。

> 注释：storage version 是 Kubernetes 写入 etcd 时采用的版本；served version 是 API server 仍允许客户端访问的版本。
> 两者不同意味着 “旧客户端还能请求” 不等于 “新 controller 仍按旧模型存储和 reconcile”。

### 3.2 Sandbox 合同

| v0.4.6 alpha | v0.5.2 beta |
| --- | --- |
| `spec.replicas: 1/0` | `spec.operatingMode: Running/Suspended` |
| PodTemplate 直接位于 Spec | Spec 嵌入 `SandboxBlueprint` |
| alpha TypeMeta | beta GroupVersion/Kind |

AgentCube direct session 只创建运行态 Sandbox，因此显式使用 `OperatingModeRunning`。

### 3.3 SandboxClaim 合同

beta Claim 删除了 alpha 的 `TemplateRef` 和 `WarmPoolPolicy`，改为必填：

```yaml
spec:
  warmPoolRef:
    name: <SandboxWarmPool name>
```

AgentCube 的 `CodeInterpreter` controller 创建同名 `SandboxTemplate` 和 `SandboxWarmPool`，所以 Claim 必须写入：

```go
Spec.WarmPoolRef.Name = codeInterpreter.Name
```

### 3.4 为什么 “只 bump 依赖” 会假绿

本地先做过一次纯 `go get sigs.k8s.io/agent-sandbox@v0.5.2 && go mod tidy`。旧 alpha import 仍能编译，
但这不是兼容性证明。

旧 AgentCube 创建 alpha Claim 时：

```text
sandboxTemplateRef = <CodeInterpreter name>
warmPoolPolicy     = empty/default
status.sandbox     = empty
```

v0.5.2 conversion webhook 会把这种 Claim 转成：

```text
warmPoolRef.name = shadow-pool-<CodeInterpreter name>
```

而 clean AgentCube 实际创建的是：

```text
SandboxWarmPool.name = <CodeInterpreter name>
```

最终会得到 `WarmPoolNotFound`。所以原生 beta Claim 是当前正确性要求，不只是未来 alpha 移除后的优化。

> 分析：这是本轮最重要的 review 经验。依赖升级能编译，只能证明包仍存在；必须继续追 producer 写出的对象、
> conversion 结果、controller 查找 key 和集群中真实对象名，才能证明运行时合同成立。

### 3.5 SandboxWarmPool 合同

`SandboxWarmPoolSpec.Replicas` 从 `int32` 变为 `*int32`，默认值为 1。

实现选择：

```go
Replicas: ptr.To(*codeInterpreter.Spec.WarmPoolSize)
```

更新比较使用：

```go
ptr.Deref(warmPool.Spec.Replicas, 1)
```

> 注释：这里创建独立指针，不直接复用 CodeInterpreter 对象中的字段指针，避免两个 informer/cache 对象共享可变地址。

### 3.6 release assets

v0.5.2 不再提供旧的 `manifest.yaml`，clean install 使用：

1. `sandbox.yaml`
2. `extensions.yaml`

旧 `manifest.yaml` URL 返回 404，因此 E2E 只改 Go 类型、不改安装资产仍会在 setup 阶段失败。

## 4. 设计与改动矩阵

### 4.1 adapter commit

`2d90b07` 修改 18 个文件，`466 insertions / 388 deletions`。

| 文件/组件 | 改动原因 | 不做什么 |
| --- | --- | --- |
| `go.mod`, `go.sum` | v0.4.6 -> v0.5.2，并接受 MVS 带来的 Kubernetes v0.36.2/controller-runtime v0.24.1 | 不手工压回不兼容的旧 K8s 版本 |
| WorkloadManager main | 注册 beta Scheme，Sandbox controller watch beta GVK | 不改变 AgentCube 自身 API version |
| informer GVR | Sandbox/Claim 从 alpha 切 beta | API group/resource 名不变，因此 RBAC 不扩张 |
| workload builder | beta TypeMeta、Blueprint、OperatingMode、WarmPoolRef | 不保留 shadow-pool fallback |
| CodeInterpreter controller | beta Template/Pool，pointer replicas | 不把 WarmPool 逻辑下沉到 Handler |
| handlers/K8s client | producer/consumer 类型统一 beta | 不改变 Store identity |
| Sandbox controller/helper | beta readiness/lifecycle types | 不改变 Ready=True 的业务门槛 |
| E2E | beta Scheme/Get/List、WarmPoolRef 断言、v0.5.2 assets、storage version gate | 不把 compile-only 当 E2E |
| getting started | clean install 与 v0.4.x 两阶段 migration 提示 | 不宣称本轮已完成原地升级 |

Store 身份仍保持两层：

| 场景 | 控制身份 | 运行身份 |
| --- | --- | --- |
| direct | `Kind=Sandbox`, `Name=Sandbox name` | `SandboxID=Sandbox UID` |
| warm | `Kind=SandboxClaim`, `Name=Claim name` | `SandboxID=adopted Sandbox UID` |

> 分析：不能把 warm path 的 Store `Name` 改为 adopted Sandbox 名。显式 delete 和 GC 需要删除控制对象 Claim，
> 而 Router/PicoD endpoint 又需要真实 Sandbox/Pod identity；两者必须分别保存。

### 4.2 generated CRD 为什么变化

依赖升级把 Kubernetes API 提升到 v0.36.2，AgentCube CRD 中内嵌的 PodSpec OpenAPI schema 因此发生变化。

这不是 AgentCube 公共字段设计变化，但 `make gen-check` 证明 generated CRD 必须同步，否则代码生成不幂等。

### 4.3 prerequisite commit

新版依赖使原有代码出现五条 SA1019：

- controller-runtime `scheme.Builder` deprecated。
- Router/WorkloadManager 的 `x/net/http2/h2c` import 和 `NewHandler` deprecated。

`d70ab94` 做两项独立调整：

1. API Scheme 改为 `runtime.NewSchemeBuilder(addKnownTypes)`。
2. cleartext server 使用 Go 1.26 `http.Server.Protocols`，同时开启 HTTP/1 和 `UnencryptedHTTP2`。

新增测试验证：

- 四个 AgentCube GVK 均可通过 Scheme 构造。
- HTTP/1 与 h2 prior-knowledge 均能通过真实 TCP listener 到达 handler。

### 4.4 prerequisite 的兼容边界

这两个重构不是完全没有代价：

1. Go 1.26 native h2c 支持 prior knowledge，但不再接受旧 `HTTP/1.1 Upgrade: h2c` 握手。
2. exported `SchemeBuilder` 的具体 Go 类型从 controller-runtime Builder 变为 apimachinery SchemeBuilder。

仓库内没有发现 Upgrade caller，也没有代码调用 `SchemeBuilder.Build()` 或 object-style `Register()`；AgentCube 内部路径使用 HTTP/1、TLS HTTP/2 或 prior knowledge。

> 分析：这是已知兼容限制，不能写成 “完全等价”。如果未来 upstream scope 要求保留 HTTP/1 Upgrade 或外部 Go source
> compatibility，应把前置提交重新评估；不能仅用 lint 通过掩盖这个事实。

## 5. 静态与单元验证

### 5.1 通过项

```text
go test ./pkg/workloadmanager ./cmd/workload-manager -count=1
go test ./pkg/... ./cmd/... ./client-go/... -count=1
go test -race ./pkg/router ./pkg/workloadmanager -count=1
go test ./test/e2e -run '^$' -count=1
make lint
make gen-check
make build-all
go mod verify
bash -n test/e2e/run_e2e.sh
git diff --check
```

结果均通过。

### 5.2 新增的重点测试

| 风险 | 测试 |
| --- | --- |
| direct beta contract | APIVersion、`OperatingModeRunning`、Blueprint |
| warm Claim lookup | `WarmPoolRef.Name == CodeInterpreter name` |
| pointer replicas | create/update 时非 nil、值正确 |
| adopted identity | Claim/Sandbox/Pod ownerRef 与 UID 连续性 |
| generated contract | `make gen-check` 无 diff |
| cleartext protocol | HTTP/1 + HTTP/2 prior knowledge 实际协商 |

### 5.3 调试过程

第一次把 prerequisite 与 adapter 组合后，`make gen-check` 发现：

```diff
- runtime "k8s.io/apimachinery/pkg/runtime"
+ "k8s.io/apimachinery/pkg/runtime"
```

根因是 Scheme import 变化让 DeepCopy 生成器去掉多余 alias。该行被归入 prerequisite commit，再重放 adapter，最终 `make gen-check` 通过。

另一次 rebase 命令误把 commit 写成 `9b3a9ba33a7?`，Git 明确返回 “does not point to a valid commit”；没有产生工作树变化，随后使用正确 commit 重跑成功。

> 分析：这些失败应保留，因为它们说明 generated diff 和提交归属是如何被校正的，而不是只记录最终绿灯。

### 5.4 一次无效的 E2E 调用

曾直接把 `./test/e2e` 放入普通 `go test`，但当时没有 Router、WorkloadManager 和 kubeconfig，得到 connection refused / no kubeconfig。

这不是 adapter 回归，而是违反 E2E 前置条件。随后使用：

```text
go test ./test/e2e -run '^$' -count=1
```

只验证 E2E package 编译，再单独启动真实 runtime。

## 6. clean runtime 验证

### 6.1 环境

| 项目 | 值 |
| --- | --- |
| OS | Ubuntu 24.04.4 LTS |
| kernel | 6.8.0-124-generic |
| CPU | 4 vCPU |
| memory | 15 GiB，无 swap |
| Docker | 29.1.3, cgroup v2/systemd |
| kind | v0.30.0 |
| Kubernetes node | v1.34.0 |
| kubectl | v1.36.2 |
| Helm | v3.18.4 |
| Go | 1.26.4 |
| `/dev/kvm` | absent |

> 注释：默认 container Sandbox 不需要 KVM，因此可以验证 Kubernetes/Pod 路径；不能据此宣称 MicroVM、Kata 或 forkd 已验证。

主机在测试前已有 10 个长期 kind node container，只剩约 4.6 GiB available memory。测试没有停止或删除这些已有集群。

### 6.2 隔离设置

```text
cluster:    agentcube-v052-clean
kubeconfig: /tmp/agentcube-v052-clean.kubeconfig
WM port:    18080
Router:     18081
MCP:        19456
MTLS:       false
require CI: true
```

### 6.3 安装门

以下实际通过：

- controller image 是 `registry.k8s.io/agent-sandbox/agent-sandbox-controller:v0.5.2`。
- `sandbox.yaml` 与 `extensions.yaml` 均成功 apply。
- controller rollout 成功。
- 四个 CRD 都是 `storage=v1beta1`。
- 四个 CRD 都是 `served=[v1beta1,v1alpha1]`。
- 四个 CRD clean install 的 `status.storedVersions=[v1beta1]`。

### 6.4 kind image-load 限制

Docker 29 的多平台 image store 在 `kind load docker-image` 时出现 content digest missing：

```text
ctr: content digest ... not found
```

controller、Python 和 Redis 均由 kind node 直接从 registry 拉取后成功运行；三张本地 AgentCube image 成功 load。

> 分析：这是 image import path 限制，不是 v0.5.2 API 失败。controller 的 actual image 和 rollout 已单独核验。

## 7. 运行结果

### 7.1 核心 v0.5.2 lifecycle

以下 Go E2E 通过：

| 测试 | 结果 | 说明 |
| --- | --- | --- |
| `TestCodeInterpreterWarmPool` | PASS, 11.25s | WarmPoolRef、adoption、ownerRef、Pod UID、delete、refill |
| `TestCodeInterpreterBasicInvocation` | PASS, 5.94s | beta direct CodeInterpreter 调用 |
| `TestCodeInterpreterFileOperations` | PASS, 4.62s | upload/download/list |
| `TestCodeInterpreterBasicInvocationLoad` | PASS, 20/20 | 2 QPS cold/direct path |

`TestCodeInterpreterWarmPool` 是本轮最关键证据。测试显式断言：

1. Claim 的 `spec.warmPoolRef.name` 等于 CodeInterpreter/WarmPool 名。
2. adopted Sandbox ownerRef 精确指向 Claim UID。
3. Pod ownerRef 精确指向 Sandbox UID。
4. adopted Pod 名和 UID 来自初始 warm pool，而不是重建的 replacement。
5. Claim 删除后 exact Claim/Sandbox/Pod UID 消失。
6. WarmPool 补回配置大小。

### 7.2 direct AgentRuntime 首次拉取抖动

`TestAgentRuntimeBasicInvocation` 的前两例各在约 60 秒超时，第三例在镜像就绪后 12.82 秒通过。

事件证据：

- kind node 首次拉取 `python:3.9-slim` 用时 `1m29.932s`。
- 同期 kube-apiserver 出现 TLS handshake timeout。
- scheduler/controller-manager 和 AgentCube probes 出现短时失败/重启。
- 镜像拉取完成后 Sandbox 转为 `DependenciesReady`，后续同路径成功。

> 分析：失败发生在 direct AgentRuntime，不经过 SandboxClaim/WarmPoolRef。它说明当前共享主机 cold-image E2E 不稳定，
> 不能用来否定或证明 beta Claim 适配。

### 7.3 10 QPS warm load 的容量边界

`TestCodeInterpreterWarmPoolLoad` 结果：

```text
total:        100
success:       54
failed:        46
success rate:  54%
elapsed:       2m49s
```

失败请求返回 `504 sandbox creation timed out`。现场证据：

- WarmPool replicas 为 2。
- 所有抽查 Claim 都正确使用同名 `WarmPoolRef`。
- 没有 `WarmPoolNotFound`。
- Claim 已绑定 Sandbox，但大量 Pod 是 `Pending` / `DependenciesNotReady`。
- scheduler 事件持续出现 `Insufficient cpu`，大量 Pod 无法调度或停在 Pending。
- 测试同时创建 100 个 session，远超两实例池和单节点可调度容量。

> 注释：warm pool 只降低前两个 session 的 cold-start；超过池大小后，controller 仍需创建新的 Sandbox/Pod。
> 2 个预热实例不等于可以在 4 vCPU 单节点上同时承载 100 个 100m-request Pod。

> 分析：压测现场曾观察到接近饱和的瞬时 allocation，但留存的 `node-describe` 是清理后的快照，不能支持精确峰值；
> 因此报告只把 `Insufficient cpu` 事件和 Pending 对象作为可复核证据。这是容量/benchmark 环境结果，不是兼容性结果。
> 未来在独占 runner 上重跑前，必须固定节点资源、并发、
> WarmPoolSize 和镜像缓存条件；否则 “90% 成功率” 没有可比性。

### 7.4 Python 与集成层

| 层 | 结果 |
| --- | --- |
| Python CodeInterpreter SDK | 3/3 PASS |
| LangChain AgentcubeSandbox | 4/4 PASS |
| MCP streamable HTTP | 5/5 PASS |
| MCP stdio | 1/1 PASS |
| MCP in-cluster Deployment | 1/1 PASS |

因此完整 `make e2e` 最终非零，但不能简写为 “E2E 全失败”，也不能写成 “全绿”。准确结论是：

- v0.5.2 clean install/API/storage/lifecycle 主链通过。
- 核心 warm adoption/delete/refill 通过。
- integration consumers 通过。
- cold-image direct 两例和单节点 10 QPS load 因资源条件失败。

### 7.5 fork push CI

fork branch push 在 exact head `2d90b074cdea21a04e076741a8acc36ed352d88c` 触发 10 个 check run，最终 10/10 success：

- Go build、coverage、golangci-lint、codegen。
- Python SDK、Python lint、codespell、copyright。
- 默认 mTLS `e2e-test`。
- 非 mTLS且强制 CodeInterpreter coverage 的 `codeinterpreter-e2e-test`。

其中 `codeinterpreter-e2e-test` 的 `Run E2E Tests` 与 `Clean up E2E Environment` 均成功，job 从
`2026-07-17T03:03:10Z` 运行到 `03:11:25Z`。

Actions：<https://github.com/ranxi2001/agentcube/actions/runs/29551431322>

> 分析：独占 Ubuntu 24 runner 的完整 E2E 成功，说明本机 direct/load 失败主要由共享主机的首次拉取和调度容量造成。
> 但不能删除本机失败记录：它仍暴露了测试对镜像缓存、节点 CPU 和 WarmPoolSize 的敏感性，是后续 benchmark 可比性输入。

## 8. cleanup

运行结束后已删除：

- `agentcube-v052-clean` kind cluster。
- 独立 kubeconfig。
- WorkloadManager/Router/MCP port-forward。
- Python temporary venv。

复核结果：

- `kind get clusters` 只剩测试前已有的 8 个 cluster name。
- 没有匹配 `agentcube-v052-clean` 的 Docker container。
- 18080/18081/19456 无监听。
- 无匹配 port-forward process。

## 9. 尚未验证的风险

### 9.1 v0.4.6 -> v0.5.2 原地升级

本轮是 clean install，不是 in-place migration。不能宣称已有 alpha stored objects、session、Pod UID 在升级中连续。

官方流程仍需单独验证：

1. 备份 Sandbox/Template/WarmPool/Claim。
2. 旧 alpha controller 仍运行时执行 `migrate.sh --phase=bootstrap`。
3. 安装 v0.5.2 `sandbox.yaml` + `extensions.yaml`。
4. 等待 controller/webhook Ready。
5. 执行 `migrate.sh --phase=migrate` 重写 storage。
6. 核对 migration annotation、UID、Pod creation time、Claim binding、Store identity。
7. 只有所有对象迁移完成后，才考虑 prune CRD `status.storedVersions`。

> 注释：存在 cold alpha Claim 时 bootstrap 是必需步骤，它会创建 `shadow-pool-<template>`；v0.5.2 的 migrate phase
> 当前可延后，但未来 alpha served version 移除前必须完成。

### 9.2 h2c Upgrade 和 SchemeBuilder source compatibility

这两个风险属于 prerequisite，不属于 beta API 本体。正式 upstream 方案可以选择：

- 接受官方推荐的 Go 1.26 native protocol，并明确不支持 HTTP/1 Upgrade。
- 暂时保留 deprecated h2c handler，并用有理由的 lint exception 保护旧协议。
- 为外部 `SchemeBuilder` caller 提供 compatibility wrapper，或在版本说明中接受 source break。

### 9.3 full E2E benchmark

需要在独占 runner 上重跑：

- 预拉取所有节点镜像。
- 没有其他长期 kind clusters。
- 记录 node allocatable/request/limit。
- 将 cold correctness 与 10 QPS load 分开。

## 10. 后续与 #438 作者方案的比较框架

等 #438 作者 PR 出现后，先冻结其 exact head，再逐项比较：

| 维度 | 问题 |
| --- | --- |
| API strategy | 原生 beta，还是继续依赖 alpha conversion？ |
| Claim mapping | 是否显式写同名 WarmPoolRef？ |
| type boundary | 是否所有 producer/consumer/watch/GVR 同步 beta？ |
| pointer semantics | WarmPool replicas nil/default/update 如何处理？ |
| Store identity | control identity 与 runtime UID 是否分离？ |
| lifecycle | adoption/delete/GC/refill 是否覆盖 exact UID？ |
| install assets | 是否使用 v0.5.2 正确 asset？ |
| migration | clean install 与 in-place upgrade 是否区分？ |
| dependency effects | K8s/controller-runtime/codegen/lint 是否被误混入业务逻辑？ |
| E2E truth | 目标测试是否真正执行，还是被 mTLS/default skip？ |

> 分析：比较目标不是证明我们的方案更复杂或文件更多，而是识别双方假设。若作者有更小且同样覆盖 producer、
> conversion、storage 和 lifecycle 的实现，应优先学习其收敛方式；若作者只做依赖 bump，则本轮 shadow-pool 证据是高优先级 review 输入。

## 11. 原始证据

目录：`internship-reports/benchmarks/day50-agent-sandbox-v052-independent/`

- `host-environment.txt`
- `pre-pull.log`
- `e2e-clean-install.log`
- `e2e-summary.txt`
- `cleanup-verification.txt`
- `fork-checks.json`
- `fork-codeinterpreter-e2e-job.json`
- `runtime-artifacts/crd-version-summary.json`
- `runtime-artifacts/events.txt`
- `runtime-artifacts/node-describe.txt`
- `runtime-artifacts/agent-sandbox-controller.log`
- WorkloadManager、Router、MCP、Sandbox describe/logs

## 12. 参考

- agent-sandbox v0.5.2 release：<https://github.com/kubernetes-sigs/agent-sandbox/releases/tag/v0.5.2>
- v1alpha1 -> v1beta1 migration guide：<https://github.com/kubernetes-sigs/agent-sandbox/blob/v0.5.2/docs/api-migration-guide.md>
- AgentCube Issue #438：<https://github.com/volcano-sh/agentcube/issues/438>
- AgentCube PR #387：<https://github.com/volcano-sh/agentcube/pull/387>
- Day41 v0.5.0 adapter：[day41-agent-sandbox-v050-release-and-agentcube-adaptation.md](day41-agent-sandbox-v050-release-and-agentcube-adaptation.md)
