# AgentCube 架构设计优化：基于 Agent Substrate 复核后的版本

> 状态：本文件是内部设计草稿，用来把 [Day28 Agent Substrate 架构复核](day28-agent-substrate-architecture-and-agentcube-differentiation.md) 和 [counter 架构图](agent-substrate-counter-architecture.drawio) 中得到的判断落到 AgentCube 后续设计里。它不是已经合入 upstream 的实现说明。

## 一句话结论

原始设计只强调 **Kubernetes placeholder Pod + 二级 sandbox scheduler**，还停留在“如何更快创建 sandbox”的层面。基于 Agent Substrate 最新源码复核后，AgentCube 的设计重心应该升级为：

```text
Kubernetes resource pool
  + Session lifecycle control plane
  + CAS-backed state store
  + Router resume-before-proxy
  + RuntimeProvider abstraction
  + optional MultiAgent Worker Pod / AgentSlot multiplexing
```

核心优化不是照搬 Agent Substrate 的 gVisor / micro-VM 路线，而是吸收它的系统边界：低频配置走 Kubernetes CRD，高频 session / worker 状态走低延迟 Store；请求先到 Router，必要时先 resume 再 proxy；runtime 差异被 provider capability 隔离；session identity 不绑定当前 Pod。

> 分析：Substrate 当前已经不只是 gVisor demo。2026-06-26 复核的源码包含 `sandboxClass=gvisor|microvm`、`SandboxConfig`、worker cache、router-triggered resume 和 workflow/CAS 状态机。这说明 AgentCube 的未来设计不能只写“资源池 + 调度器”，还必须把 session lifecycle、状态一致性、runtime capability 和请求路径放进同一张架构图里。

## 输入依据

| 输入 | 关键结论 | 对本设计的影响 |
| --- | --- | --- |
| [Day28 复核报告](day28-agent-substrate-architecture-and-agentcube-differentiation.md) | Substrate 的价值是 actor/session substrate，不只是 gVisor checkpoint | AgentCube 设计从 sandbox creation 扩展到 session lifecycle substrate |
| [counter drawio](agent-substrate-counter-architecture.drawio) | 请求经 DNS/Router 进入，Router 调 `ResumeActor`，控制面分配 worker，再转发到 worker IP | AgentCube Router 应设计 `resume-before-proxy` |
| Substrate `Store CAS / version` | `UpdateActor` / `UpdateWorker` 都带 expected version | AgentCube Store CAS 是并发 resume/suspend 的正确性要求 |
| Substrate `Worker cache` | 调度热路径不应每次全量扫 Store | AgentCube 后续 `session -> worker -> slot` 也需要 placement cache 或索引 |
| Substrate `SandboxConfig` / `sandboxClass` | runtime assets 与 template 解耦，gVisor / micro-VM 可并存 | AgentCube 需要 `RuntimeProvider` / `RuntimeClassConfig` |
| Claude Code multiplex demo | 多个 Actor 共享少量 Worker Pods，但单 Worker 同时最多一个 Actor | AgentCube 的 MultiAgent Worker Pod 是差异化空间复用，不是 Substrate 已实现能力 |
| micro-VM rootfs 语义 | guest RAM 可恢复，rootfs reset-to-golden，不等于通用 memory + disk checkpoint | AgentCube 必须定义 preservation level，不能笼统说“保存上下文” |

## 原设计的不足

原始草稿的主线是：

```text
SandboxWorkspace -> WorkspaceController -> Placeholder Pods
Sandbox API / CR -> SandboxScheduler -> sandbox-runtime
```

这个方向仍然有价值，因为 Kubernetes Pod 创建延迟和 kube-scheduler 粒度确实是 AgentCube 的约束。但它漏掉了五个关键问题：

1. **请求路径没有生命周期语义**：Router 只是 proxy，没有表达 `Paused -> Resuming -> Ready -> proxy`。
2. **状态面没有 CAS / version**：如果两个请求同时触发 resume，可能重复启动 runtime 或写回旧 endpoint。
3. **runtime 能力没有分层**：agent-sandbox、multi-slot worker、micro-VM、Docker/local、OpenSandbox-like backend 的能力差异会扩散到业务逻辑。
4. **worker identity 和 session identity 容易混淆**：session 可能迁移到不同 worker，不能把 Pod IP / Pod name 当成 session identity。
5. **只做资源池，不足以支持 Sleep/Resume**：placeholder Pod 能解决容量预留，但不能单独解决状态保留、恢复前置、快照语义和 cleanup。

> 注释：`placeholder Pod` 只能说明“资源已经被 Kubernetes scheduler 放到某个节点上”，不等于 session 已经可恢复。真正的 Sleep/Resume 还需要 Store 状态机、runtime handle、endpoint refresh、并发控制和失败补偿。

## 优化后的六面架构

| 面 | 核心职责 | AgentCube 设计对象 | 从 Substrate 学到什么 |
| --- | --- | --- | --- |
| Kubernetes Foundation | 节点、Pod、namespace、RBAC、CRD、基础资源预留 | `SandboxWorkspace`、placeholder Pods、agent-sandbox CRDs | Kubernetes 适合低频期望状态和资源边界，不适合承载高频 session 状态 |
| Pool / Capacity Control | 维护 warm pool、placeholder pool、节点容量、水位线 | `WorkspaceController`、`ReservationManager`、future `WorkerPool` | WorkerPool 是容量声明，不等于单个 session |
| Session Lifecycle Control | create、pause、resume、delete、transition state、failure recovery | WorkloadManager lifecycle service | Substrate workflow 是可重入步骤，不是单个同步函数 |
| State / Placement Plane | session 状态、runtime handle、endpoint、worker/slot 状态、CAS、watch/cache | Store、`SessionPlacement`、placement cache | Actor/Worker 高频状态放 Store，更新带 expected version |
| Router / Activation Plane | owner/auth、session lookup、resume-before-proxy、endpoint refresh、singleflight | Router session manager | Router 是 activation gate，请求不能直接打旧 endpoint |
| Runtime Data Plane | 真正创建/恢复/暂停/删除 runtime，暴露 endpoint，清理资源 | `RuntimeProvider`、NodeAgent、sandbox-runtime、AgentSlot supervisor | atelet/ateom 把 node/runtime action 从控制面解耦 |

> 分析：这个六面架构比原来的“四层资源池架构”更接近 AgentCube 的真实问题。AgentCube 面向的是长期 session 和 agent workload，不只是短生命周期 sandbox job。资源池只是底座，真正的产品语义是 session lifecycle。

## 关键对象

| 对象 | 作用 | 关键字段 / 语义 |
| --- | --- | --- |
| `Session` | AgentCube 对外暴露的长期会话主体 | `sessionID`、owner、status、ttl、lastActivity、provider、placementVersion |
| `SandboxWorkspace` | 资源池和 workspace 边界 | namespace、quota、pool policy、storage class、network policy |
| `RuntimeClassConfig` | runtime capability 和资产配置 | provider name、sandbox class、snapshot capability、isolation level、asset refs |
| `RuntimeProvider` | 控制面调用 runtime 的统一接口 | create、pause、resume、delete、probe、capabilities |
| `SessionPlacement` | session 到 runtime location 的绑定 | provider、worker、slot、endpoint、runtimeHandle、version |
| `WorkerPool` / `RuntimePool` | 预热容量声明 | pool selector、warm size、runtime class、node affinity |
| `AgentSlot` | MultiAgent Worker Pod 内部的执行槽 | slot id、port、workspace path、credential scope、resource limit、status |
| `SandboxNodeState` | 节点和 runtime 健康状态 | reserved、allocated、free、image/cache/snapshot locality、provider health |

> 注释：`SessionPlacement` 是防止“把 session 等同于 Pod”的关键对象。当前 endpoint 只是 placement 的一个结果，不是 session identity。resume 后 endpoint 可能变化，Router 必须刷新。

## 核心控制链路

### 1. 低频资源池链路

```text
SandboxWorkspace / WorkerPool
  -> WorkspaceController
  -> placeholder Pods / warm worker Pods
  -> Store records worker capacity
```

用途：

- 让 Kubernetes 先完成节点选择和资源预留。
- 避免真实请求到来时才走完整 Pod scheduling。
- 给 RuntimeProvider 提供可用 worker / slot 容量。

> 分析：这部分保留原设计。优化点不是删除 placeholder Pod，而是避免把它误认为完整 lifecycle。它负责 capacity，不负责 session 状态正确性。

### 2. 请求激活链路

```text
Client request
  -> Router owner/auth check
  -> Store GetSession
  -> if Ready: proxy current endpoint
  -> if Paused/Suspended: ResumeSession
  -> Store refresh endpoint / placement version
  -> proxy refreshed endpoint
```

设计要求：

- Router 必须先做 owner/auth，再触发 resume。
- Resume 成功后不能复用旧 endpoint，必须使用 WorkloadManager 返回的新 placement，或重新读 Store。
- 同一个 session 的并发 resume 要 singleflight，底层仍必须靠 Store CAS 保底。
- transition state 例如 `Resuming` 不能被当成 `Ready` 直接 proxy。

> 分析：这是 Substrate counter 图里最值得学的一条线。`atenet-router -> ResumeActor -> workerIP:80` 说明 Router 是 activation gate。AgentCube 如果只让 GC 把 session 标成 Paused，而 Router 不懂 resume-before-proxy，就没有形成真正闭环。

### 3. Pause / Resume workflow 链路

Resume 不应是一个不可拆分的同步函数，而应拆成可重试步骤：

```text
LoadSessionForResume
  -> MarkResuming with CAS
  -> ReserveWorkerOrSlot with CAS
  -> ProviderResume / ProviderCreate
  -> ProbeEndpoint
  -> FinalizeReady with CAS
```

Pause / Suspend 可拆成：

```text
LoadSessionForPause
  -> MarkPausing with CAS
  -> ProviderPause / ProviderCheckpoint
  -> ReleaseWorkerOrSlot with CAS
  -> FinalizePaused with CAS
```

失败处理：

| 失败点 | 风险 | 设计要求 |
| --- | --- | --- |
| MarkResuming CAS conflict | 并发请求重复 resume | 返回 conflict / retry，Router singleflight 降低重复 |
| ReserveWorker 成功但 ProviderResume 失败 | worker/slot 被占住 | provider failure cleanup 或 compensating release |
| ProviderResume 成功但 FinalizeReady CAS 失败 | runtime 已运行但 Store 不知道 | 必须有 reconcile / orphan cleanup / finalization retry |
| Router 在 Resuming 中再次请求 | 读到 transition state | wait / retry / return 503 with retry-after，不能 proxy 旧 endpoint |

> 注释：CAS 是 Compare-And-Swap，意思是“只有当前版本仍等于我读取时的版本，才允许写入”。它不是性能优化，而是并发状态机的正确性基础。

## RuntimeProvider 抽象

AgentCube 不应把 Kubernetes / agent-sandbox 当成唯一底层。更合理的是让 WorkloadManager 依赖 `RuntimeProvider` 能力，而不是依赖某个 CRD 的具体字段。

概念接口：

```go
type RuntimeProvider interface {
    Capabilities(ctx context.Context) RuntimeCapabilities
    Create(ctx context.Context, session SessionSpec) (Placement, error)
    Pause(ctx context.Context, placement Placement) (PauseResult, error)
    Resume(ctx context.Context, session SessionSpec, snapshot SnapshotRef) (Placement, error)
    Delete(ctx context.Context, placement Placement) error
    Probe(ctx context.Context, placement Placement) (ProbeResult, error)
}
```

Provider 类型：

| Provider | 近期用途 | 能力边界 |
| --- | --- | --- |
| `AgentSandboxProvider` | 当前 Kubernetes-native 主路径 | warm pool、SandboxClaim、Pod endpoint、workspace/rootfs 语义 |
| `MultiAgentWorkerProvider` | 高密度方向 | 一个 Worker Pod 内多个 AgentSlot，需要 slot isolation |
| `DockerLocalProvider` | 本地开发 / benchmark | 快速验证 API contract，不代表生产隔离 |
| `OpenSandboxLikeProvider` | 对外部 sandbox backend 做实验 | 依赖外部 API，不直接控制底层 CRD |
| `MicroVMProvider` | 高隔离 future path | 需要 `/dev/kvm`、Kata/Cloud Hypervisor/Firecracker 等环境 |

> 分析：Substrate 的 `SandboxConfig` 给了很好的启发：runtime assets 和 runtime class 不应该散落在每个模板或 handler 里。AgentCube 可以先定义 `RuntimeClassConfig` / `RuntimeCapabilities`，即使第一版 provider 只有 agent-sandbox，也能避免后续 v0.5、micro-VM 或 multi-slot worker 迁移时大面积改 SDK、Router 和 Store。

## Preservation Level：明确“保存上下文”到底保存什么

Substrate micro-VM 路径已经说明一个风险：guest RAM 可以恢复，不代表 rootfs 写入一定保留。AgentCube 设计中应该显式定义 preservation level。

| Level | 名称 | 恢复承诺 | 适用场景 |
| --- | --- | --- | --- |
| L0 | No preservation | 只保留 session metadata，runtime 可重建 | 无状态 tool / 短任务 |
| L1 | Workspace preservation | workspace / rootfs 文件保留，进程重启 | CodeInterpreter、文件型 agent |
| L2 | Process restart + workspace | 进程重启，但能从 workspace 恢复上下文 | 依赖应用级 checkpoint 的 agent |
| L3 | Memory snapshot | 进程内存恢复，文件语义按 provider 定义 | gVisor/runsc 或 micro-VM memory snapshot |
| L4 | Memory + writable disk snapshot | 内存和可写磁盘都恢复 | 高一致性长期 agent，成本最高 |

设计要求：

- SDK / API 不能只说 `pause` 会保存 context，必须说明 preservation level。
- RuntimeProvider 必须声明自己支持哪些 level。
- Router / WorkloadManager 不应该假设所有 provider 都能 memory checkpoint。
- benchmark 需要按 level 分组，否则不同 runtime 的 resume 数据不可比。

> 注释：用户真正关心的是恢复后“文件还在吗、进程内变量还在吗、网络连接还在吗、token 还有效吗、tool server 还活着吗”。这些不是一个 `Paused` 字段能表达清楚的。

## AgentCube 相比 Substrate 的优化点

### 1. 从时间复用扩展到空间复用

Substrate 当前 Worker 语义是：

```text
many Actors -> fewer Worker Pods
one Worker Pod hosts at most one Actor at a time
```

AgentCube 可以探索的差异化是：

```text
many Sessions -> fewer MultiAgent Worker Pods
one Worker Pod hosts multiple isolated AgentSlots at the same time
```

收益：

- 对轻量 agent / tool session 提高 Pod 密度。
- 减少 kube-scheduler 压力。
- 更适合模型工具调用频繁但每个 session CPU/内存占用不高的场景。

风险：

| 风险 | 需要的设计 |
| --- | --- |
| workspace 泄漏 | 每个 slot 独立目录 / volume mount / cleanup test |
| credential 泄漏 | 每个 slot 独立 token scope，不能共享 env secret |
| port 冲突 | slot port allocator / per-slot reverse proxy |
| noisy neighbor | cgroup / process limit / per-slot quota |
| metrics 混淆 | per-slot labels：session、owner、provider、worker、slot |
| Pod failure blast radius | 一个 Worker Pod 挂掉会影响多个 sessions，需要批量 failover / cleanup |

> 分析：这不是 Substrate 已经完成的能力。Day28 复核明确了 Claude Code multiplex 是 3 个 Actors 竞争 2 个 Worker Pods，是时间复用。AgentCube 如果做 AgentSlot，是更激进的空间复用，必须先把隔离和测试矩阵写清楚。

### 2. Provider-first，而不是 runtime-first

Substrate 的当前实现深度绑定自己的 control plane、atelet/ateom、Store 和 gVisor/micro-VM assets。AgentCube 不应复制这些名称或目录结构，而应该抽取可复用的边界：

| Substrate 概念 | AgentCube 对应设计 | 优化点 |
| --- | --- | --- |
| Actor | Session | 沿用 AgentCube 对外语义 |
| WorkerPool | RuntimePool / Workspace pool | 兼容 agent-sandbox warm pool 和 future multi-slot worker |
| Worker | Worker Pod / AgentSlot / runtime handle | 不把 worker identity 等同 session identity |
| ate-api-server | WorkloadManager lifecycle service | 不必第一版引入 gRPC，但要有强 contract |
| Store version | Store CAS / placement version | 明确并发正确性 |
| SandboxConfig | RuntimeClassConfig / RuntimeCapabilities | runtime assets 与 session template 解耦 |
| atelet / ateom | RuntimeProvider / NodeAgent / sidecar | node action 与控制面解耦 |
| atenet router | AgentCube Router | resume-before-proxy + endpoint refresh |

### 3. 显式兼容 agent-sandbox 演进

AgentCube 当前现实约束是已经在推进 `agent-sandbox v0.4.6` compatibility，并且后续 v0.5/v1beta1 会继续变化。因此设计要避免把某个版本的 CRD shape 固化进上层 API。

设计原则：

- Store 保存 AgentCube 自己的 `Session` / `Placement`，不是直接暴露 `SandboxClaim` 全字段。
- Provider adapter 内部处理 `SandboxClaim.status.sandbox.name`、Pod annotation、ownerRef、NetworkPolicy 等版本细节。
- Router 只关心 session status 和 endpoint，不关心底层是 Sandbox、Pod、AgentSlot 还是 external sandbox。
- e2e 既要覆盖 SDK 黑盒，也要覆盖 CRD object-flow，避免只看 stdout 成功。

> 分析：Day30 对 #387 的 warm pool review 说明：真实数据流是 `SandboxClaim -> adopted Sandbox -> Pod -> Store -> Router`。设计里如果只写 “Scheduler selects node -> NodeAgent creates sandbox”，会漏掉 provider adapter 里最容易出错的 identity bridge。

## 状态机建议

| 状态 | 含义 | Router 行为 | GC 行为 |
| --- | --- | --- | --- |
| `Creating` | provider 正在创建 runtime | 等待或返回 retryable error | 超时后 Failed / cleanup |
| `Ready` | endpoint 可用 | proxy endpoint | idle 后 Pausing |
| `Pausing` | provider 正在暂停 / checkpoint | 不 proxy 旧 endpoint，可等待或 503 retry | 超时诊断，不直接 delete |
| `Paused` | runtime 已释放或不可直接访问 | trigger resume-before-proxy | pauseTimeout 后 delete |
| `Resuming` | provider 正在恢复 runtime | singleflight wait / retry | 超时诊断 / Failed |
| `Deleting` | 删除和 cleanup 中 | reject request | cleanup retry |
| `Deleted` | 终态 | 404 / gone | no-op |
| `Failed` | 需要人工或 controller reconcile | 返回明确错误 | 根据 policy cleanup |

> 注释：`Paused` 和 `Ready` 不只是两个字符串。它们决定 Router 是否可以 proxy、GC 是否可以删除、SDK 是否可以继续使用同一个 session id、Store endpoint 是否还可信。

## 测试矩阵

| 风险 | 必要测试 |
| --- | --- |
| 并发 resume 重复启动 | `go test -race` + fake provider + Store CAS conflict |
| provider 成功但 final CAS 失败 | fake provider 注入成功后 CAS conflict，验证 cleanup / retry |
| Router 使用旧 endpoint | paused session resume 后 endpoint 变化，验证 Router 使用新 endpoint |
| Pausing/Resuming 被误 proxy | Router status table unit test |
| Workspace / credential 泄漏 | MultiAgent Worker per-slot cleanup e2e |
| agent-sandbox object identity 错误 | CRD object-flow inspector：claim status、adopted Sandbox、Pod annotation、Store |
| preservation level 混淆 | L1/L2/L3 provider capability tests |
| warm pool refill / delete cleanup | 创建、使用、删除、refill、ownerRef/UID continuity |
| metrics 语义错误 | per-session / per-slot active gauge 和 HTTP status metrics |

## 分阶段落地路线

### Phase 0：承认当前基线

当前 AgentCube 更接近 create/delete/warm pool，还不是完整 Sleep/Resume。先不要在文档里声称已经具备 Substrate 式 resume。

输出：

- 当前架构图。
- 当前 Store / Router / WorkloadManager 行为表。
- 已知缺口：Paused state、resume API、Router resume-before-proxy、Store CAS、provider capability。

### Phase 1：Session lifecycle contract

先定义 AgentCube 自己的状态机和 Store 字段。

输出：

- `SessionStatus`：Ready / Pausing / Paused / Resuming / Deleting / Deleted / Failed。
- `SessionPlacement`：provider、runtimeHandle、endpoint、version。
- Store CAS API。
- fake provider tests。

### Phase 2：Router resume-before-proxy

让 Router 理解 Paused/Resuming 状态。

输出：

- owner/auth -> resume -> endpoint refresh -> proxy。
- singleflight 同 session resume。
- Router status table tests。

### Phase 3：RuntimeProvider adapter

把 agent-sandbox 当前路径包进 provider。

输出：

- `AgentSandboxProvider`。
- v0.4.6 warm pool claim/adopted Sandbox/Pod identity bridge。
- Provider capability table。

### Phase 4：MultiAgent Worker Pod / AgentSlot proposal

这是差异化方向，不要直接混进 Sleep/Resume MVP。

输出：

- AgentSlot object model。
- Slot isolation matrix。
- per-slot workspace / credential / port / metric / cleanup tests。
- failure domain 设计。

### Phase 5：Benchmark 和可观测性

按 preservation level 和 provider 分组测。

输出：

- cold create / warm create / pause / resume / delete cleanup。
- p50 / p95 / p99。
- math-agent / tool-call e2e。
- resource pressure 和 failure rate。

## 对原设计文本的具体修正

| 原设计说法 | 优化后说法 |
| --- | --- |
| `SandboxWorkspace -> WorkspaceController -> Placeholder Pods` 是主链路 | 这是 capacity 链路，只解决资源预留，不解决 session lifecycle |
| `SandboxScheduler` 做细粒度调度 | 调度要拆成 placement decision + Store CAS + provider capability，不只是选节点 |
| `sandbox-runtime` 处理 snapshot | snapshot 语义必须通过 preservation level 暴露，不同 provider 能力不同 |
| `SandboxNodeState` 跟踪容量 | 还需要 session/worker/slot placement cache，Store 仍是 source of truth |
| Pod 创建延迟是主要问题 | Pod 延迟只是一个问题；Router activation、状态一致性、runtime abstraction 同等重要 |
| 保持 Kubernetes 兼容即可 | Kubernetes 是底座，不应成为唯一 substrate；provider abstraction 是长期边界 |

## 当前结论

AgentCube 的设计应从“更快创建 sandbox”升级到“可恢复、可路由、可观测、可替换底层 runtime 的 session substrate”。Agent Substrate 提供的是参考边界，不是要复制的实现：

- 学它的控制面 / 状态面 / 数据面 / runtime 面拆分。
- 学 Router resume-before-proxy。
- 学 Store CAS 和 workflow 可重入。
- 学 runtime class / assets 配置解耦。
- 不照搬一个 worker 同时只承载一个 actor。
- 不把 gVisor / micro-VM checkpoint 当作第一版唯一目标。
- 不把早期 gRPC API 和命名直接搬到 AgentCube。

AgentCube 的优化方向是：在 Kubernetes-native 和 agent-sandbox 生态基础上，补齐 Session lifecycle contract，再通过 RuntimeProvider 和 AgentSlot 走向更高密度、更可插拔的 Agent runtime infrastructure。
