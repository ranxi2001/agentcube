# AgentCube 会话运行时架构拆解

> 配套图：[`day28-agentcube-session-runtime-architecture.drawio`](day28-agentcube-session-runtime-architecture.drawio)
>
> 状态：本文是设计拆解文档，用来解释架构图中的对象边界、真实流转、合理性和收益。它不是声明这些能力已经全部合入 upstream；其中 Sleep/Resume、Store CAS、RuntimeProvider 和 MultiAgent Worker / AgentSlot 属于后续设计方向或分阶段落地目标。

## 1. 架构总览

```mermaid
flowchart TB
    Client["Client / SDK<br/>携带 sessionID"]

    subgraph RouterPlane["Router / Activation Plane"]
        Router["AgentCube Router<br/>owner/auth<br/>resume-before-proxy"]
    end

    subgraph LifecyclePlane["Session Lifecycle Control Plane"]
        WLM["WorkloadManager<br/>create / pause / resume / delete<br/>可重入 workflow"]
    end

    subgraph StatePlane["State / Placement Plane"]
        Store[("CAS-backed Store<br/>Session / Placement<br/>expected version")]
        Placement["SessionPlacement<br/>provider / worker / slot<br/>endpoint / runtimeHandle / version"]
        Cache["Placement cache / watch<br/>热路径索引，不替代 Store"]
    end

    subgraph RuntimePlane["RuntimeProvider + Runtime Data Plane"]
        Provider["RuntimeProvider<br/>Create / Pause / Resume / Delete / Probe"]
        Runtime["Runtime endpoint<br/>workspace / tool server / agent process"]
    end

    subgraph K8sPlane["Kubernetes Foundation + Capacity Pool"]
        Workspace["SandboxWorkspace<br/>namespace / quota / policy"]
        Pool["placeholder Pods / warm worker Pods"]
        Worker["Worker Pod / AgentSlot"]
        NodeState["SandboxNodeState<br/>reserved / allocated / free"]
    end

    Client -->|"请求 / 控制调用"| Router
    Router -->|"状态查询 / endpoint 读取"| Store
    Router -->|"Paused 时触发 ResumeSession"| WLM
    Router -->|"Ready 时代理"| Runtime

    WLM -->|"CAS 状态迁移"| Store
    WLM -->|"runtime 操作契约"| Provider
    Provider -->|"创建 / 恢复 / 暂停 / 删除"| Runtime
    Provider -->|"控制底层 CRD / Pod / slot"| Worker

    Workspace -.->|"低频期望状态"| Pool
    Pool -.->|"容量预留"| Worker
    Worker -.->|"健康与容量信号"| NodeState
    NodeState -->|"容量 / endpoint 记录"| Cache
    Cache -->|"辅助 placement 查询"| Store
    Store --> Placement
```

> 注释：图里的核心设计不是“把所有请求都塞进 Kubernetes”，而是拆成五类不同的系统面：Router 负责激活入口，WorkloadManager 负责生命周期，Store 负责高频一致性状态，RuntimeProvider 负责屏蔽底层 runtime 差异，Kubernetes 负责低频资源边界和容量池。

### 连线语义

```mermaid
flowchart LR
    Blue["蓝色实线<br/>请求 / 控制调用"] --> B1["Router 调 WorkloadManager<br/>WorkloadManager 调 Provider"]
    Purple["紫色实线<br/>状态读写 / CAS / Placement"] --> P1["GetSession<br/>CAS transitions<br/>placement endpoint"]
    Green["绿色实线<br/>数据面代理"] --> G1["Router proxy<br/>runtime endpoint"]
    Gray["灰色虚线<br/>容量 / 健康 / capability 信号"] -.-> S1["warm pool<br/>health report<br/>capability guide"]
```

> 分析：这些线不是同一种“调用”。把数据面、控制面、状态面和容量信号分开，是为了避免把旧 endpoint、runtime identity、session identity 和 worker capacity 混成一个概念。

## 2. 为什么要这样分层

```mermaid
flowchart TB
    Problem["原始设计偏重<br/>更快创建 sandbox"] --> Missing["遗漏长期 session 的关键问题"]

    Missing --> M1["请求路径没有生命周期语义<br/>Router 只是 proxy"]
    Missing --> M2["状态面没有 CAS / version<br/>并发 resume 可能写回旧 endpoint"]
    Missing --> M3["runtime 能力散落在业务逻辑<br/>agent-sandbox / micro-VM / Docker 差异扩散"]
    Missing --> M4["session identity 与 worker identity 混淆<br/>Pod IP 不应等于 session"]
    Missing --> M5["placeholder Pod 只表示容量<br/>不代表 session 可恢复"]

    M1 --> Design["AgentCube 会话运行时架构"]
    M2 --> Design
    M3 --> Design
    M4 --> Design
    M5 --> Design

    Design --> D1["Router activation gate"]
    Design --> D2["CAS-backed Store"]
    Design --> D3["RuntimeProvider abstraction"]
    Design --> D4["SessionPlacement"]
    Design --> D5["Kubernetes capacity pool"]
```

> 注释：Kubernetes 非常适合承载 namespace、quota、Pod、CRD、RBAC 这类低频期望状态，但不适合把每一次 session 状态跳转都放进 apiserver 热路径。高频状态应该落到低延迟 Store，并用 CAS 保证并发正确性。

## 3. 真实请求流转：Ready session

```mermaid
sequenceDiagram
    autonumber
    participant C as Client / SDK
    participant R as Router
    participant S as Store
    participant RT as Runtime endpoint

    C->>R: Invoke(sessionID, request)
    R->>R: owner/auth check
    R->>S: GetSession(sessionID)
    S-->>R: status=Ready, endpoint, placementVersion
    R->>RT: proxy request to current endpoint
    RT-->>R: runtime response
    R-->>C: response
```

> 分析：Ready 路径里，Router 仍然不能绕过 Store。原因是 endpoint 只是 `SessionPlacement` 的一个结果，可能在上一次 resume、迁移或 failover 后变化。Router 每次进入前至少要确认 session 状态和 endpoint 是否可信。

## 4. 真实请求流转：Paused session 恢复后再代理

```mermaid
sequenceDiagram
    autonumber
    participant C as Client / SDK
    participant R as Router
    participant S as Store
    participant W as WorkloadManager
    participant P as RuntimeProvider
    participant RT as Runtime endpoint

    C->>R: Invoke(sessionID, request)
    R->>R: owner/auth check
    R->>S: GetSession(sessionID)
    S-->>R: status=Paused, no usable endpoint
    R->>W: ResumeSession(sessionID)

    W->>S: MarkResuming(expectedVersion)
    S-->>W: CAS ok / new version
    W->>S: ReserveWorkerOrSlot(expectedVersion)
    S-->>W: worker / slot reserved
    W->>P: Resume or Create(session spec, snapshot ref)
    P-->>W: new placement(endpoint, runtimeHandle)
    W->>P: Probe(placement)
    P-->>W: healthy
    W->>S: FinalizeReady(new placement, expectedVersion)
    S-->>W: CAS ok / placementVersion++

    W-->>R: ResumeSession result(new placement)
    R->>S: Re-read or refresh placement
    S-->>R: status=Ready, refreshed endpoint
    R->>RT: proxy request to refreshed endpoint
    RT-->>R: runtime response
    R-->>C: response
```

> 注释：关键点是“resume-before-proxy”。Router 不能拿 Paused 时留下的旧 endpoint 直接转发；恢复完成后必须使用 WorkloadManager 返回的新 placement，或者重新读 Store 获得最新 endpoint。

## 5. Session 状态机

```mermaid
stateDiagram-v2
    [*] --> Creating
    Creating --> Ready: provider create + probe ok
    Creating --> Failed: create timeout / provider error

    Ready --> Pausing: idle timeout / explicit pause
    Ready --> Deleting: explicit delete / max duration

    Pausing --> Paused: checkpoint or release ok
    Pausing --> Failed: provider pause failed / timeout

    Paused --> Resuming: request arrives / explicit resume
    Paused --> Deleting: pause timeout / cleanup policy

    Resuming --> Ready: provider resume + probe ok
    Resuming --> Failed: resume timeout / finalization failed

    Deleting --> Deleted: cleanup ok
    Deleting --> Failed: cleanup retry exhausted

    Failed --> Deleting: policy cleanup
    Deleted --> [*]
```

> 分析：`Paused`、`Resuming`、`Ready` 不能只是 UI 字段。它们决定 Router 是否可以 proxy、GC 是否可以删除、Store endpoint 是否可信、SDK 是否还能继续使用同一个 session id。

## 6. Pause / Resume workflow 为什么要拆成 CAS 步骤

```mermaid
flowchart LR
    subgraph Resume["Resume workflow"]
        R1["LoadSessionForResume"] --> R2["MarkResuming<br/>CAS"]
        R2 --> R3["ReserveWorkerOrSlot<br/>CAS"]
        R3 --> R4["ProviderResume<br/>or ProviderCreate"]
        R4 --> R5["ProbeEndpoint"]
        R5 --> R6["FinalizeReady<br/>CAS"]
    end

    subgraph Pause["Pause / Suspend workflow"]
        P1["LoadSessionForPause"] --> P2["MarkPausing<br/>CAS"]
        P2 --> P3["ProviderPause<br/>or ProviderCheckpoint"]
        P3 --> P4["ReleaseWorkerOrSlot<br/>CAS"]
        P4 --> P5["FinalizePaused<br/>CAS"]
    end
```

```mermaid
sequenceDiagram
    autonumber
    participant ReqA as Request A
    participant ReqB as Request B
    participant Store as Store
    participant W as WorkloadManager

    ReqA->>W: ResumeSession(sessionID)
    ReqB->>W: ResumeSession(sessionID)
    W->>Store: MarkResuming(expectedVersion=7)
    Store-->>W: ok, version=8
    W->>Store: MarkResuming(expectedVersion=7)
    Store-->>W: CAS conflict
    W-->>ReqB: wait / retry / join singleflight
```

> 注释：CAS 是 Compare-And-Swap。它的价值不是“更快”，而是保证并发状态机正确：只有当前版本仍等于读取时的版本，才允许写入。没有 CAS 时，两个并发 resume 可能重复启动 runtime，或者把旧 endpoint 写回 Store。

## 7. RuntimeProvider 抽象

```mermaid
classDiagram
    class RuntimeProvider {
      +Capabilities(ctx) RuntimeCapabilities
      +Create(ctx, sessionSpec) Placement
      +Pause(ctx, placement) PauseResult
      +Resume(ctx, sessionSpec, snapshotRef) Placement
      +Delete(ctx, placement) error
      +Probe(ctx, placement) ProbeResult
    }

    RuntimeProvider <|.. AgentSandboxProvider
    RuntimeProvider <|.. MultiAgentWorkerProvider
    RuntimeProvider <|.. DockerLocalProvider
    RuntimeProvider <|.. OpenSandboxLikeProvider
    RuntimeProvider <|.. MicroVMProvider

    class AgentSandboxProvider {
      SandboxClaim
      adopted Sandbox
      Pod endpoint
      warm pool
    }

    class MultiAgentWorkerProvider {
      Worker Pod
      AgentSlot
      per-slot workspace
      per-slot credential scope
    }

    class MicroVMProvider {
      sandboxClass
      snapshot capability
      isolation level
    }
```

> 分析：Provider-first 的好处是上层 API、Router、Store 不需要知道底层到底是 `SandboxClaim`、Pod、AgentSlot、Docker container 还是 micro-VM。底层升级时主要修改 provider adapter，而不是把 CRD 细节扩散到业务逻辑。

## 8. Kubernetes capacity pool 的真实职责

```mermaid
flowchart TB
    SW["SandboxWorkspace<br/>namespace / quota / policy"] --> WC["WorkspaceController<br/>ReservationManager"]
    WC -.-> Pool["placeholder Pods / warm worker Pods"]
    Pool -.-> Kube["Kubernetes scheduler<br/>node placement / resource reservation"]
    Kube -.-> Worker["Worker Pod / AgentSlot capacity"]
    Worker -.-> NS["SandboxNodeState<br/>reserved / allocated / free"]
    NS --> Store["Store / placement cache<br/>capacity and endpoint records"]

    Store --> Provider["RuntimeProvider<br/>uses available worker / slot"]
```

> 注释：placeholder Pod 和 warm worker Pod 解决的是容量与启动延迟问题，不解决 session 状态正确性。真正决定 session 是否 Ready、endpoint 是否可用、resume 是否完成的是 Store 状态机和 RuntimeProvider probe。

## 9. 数据面、控制面、状态面的边界

```mermaid
flowchart LR
    subgraph Control["控制面：决定做什么"]
        Router["Router"]
        WLM["WorkloadManager"]
        Provider["RuntimeProvider"]
    end

    subgraph State["状态面：记录事实和版本"]
        Store[("Store<br/>Session / Placement / version")]
    end

    subgraph Data["数据面：真正处理用户请求"]
        Runtime["Runtime endpoint<br/>tool server / agent process"]
    end

    Router -->|"ResumeSession / lifecycle command"| WLM
    WLM -->|"ProviderResume / ProviderCreate"| Provider
    Router -->|"GetSession / endpoint"| Store
    WLM -->|"CAS transition / placement update"| Store
    Router -->|"proxy user request"| Runtime
```

> 分析：这条边界能降低故障扩散。控制面失败不应伪装成数据面 endpoint 可用；状态面 CAS 冲突不应变成重复 runtime；数据面 runtime 挂掉后也应该通过 probe / reconcile 反馈到状态面，而不是让 Router 长期打旧 endpoint。

## 10. 失败补偿与 reconcile

```mermaid
flowchart TB
    Start["Resume workflow"] --> Mark["MarkResuming CAS"]
    Mark --> Reserve["ReserveWorkerOrSlot CAS"]
    Reserve --> Provider["ProviderResume / Create"]
    Provider --> Finalize["FinalizeReady CAS"]

    Mark -->|CAS conflict| Conflict["singleflight wait / retry"]
    Reserve -->|reserved but provider failed| Release["compensating release<br/>worker / slot"]
    Provider -->|runtime started but final CAS failed| Orphan["orphan runtime risk"]
    Orphan --> Reconcile["reconcile / finalization retry<br/>or cleanup runtime"]
    Finalize --> Ready["Ready + refreshed endpoint"]
```

> 注释：分布式生命周期最危险的不是“某一步失败”，而是“底层 runtime 已经发生变化，但 Store 还没记录”。所以需要 finalization retry、orphan cleanup 和 reconcile，而不能只依赖一次同步函数返回。

## 11. 为什么这个设计更好

```mermaid
mindmap
  root((AgentCube 会话运行时架构收益))
    正确性
      Store CAS 防并发写回旧状态
      SessionPlacement 不把 Pod 当 session
      Router 避免 proxy 旧 endpoint
    延迟
      warm pool 降低冷启动
      placement cache 避免热路径全量扫描
      Ready 路径快速 proxy
    可演进
      RuntimeProvider 隔离底层 CRD / runtime
      RuntimeCapabilities 描述能力差异
      preservation level 明确恢复承诺
    可观测
      session / worker / slot label 清晰
      状态机可统计卡点
      capacity 与 data-plane 指标分离
    安全与隔离
      per-slot workspace
      per-slot credential scope
      endpoint refresh 降低错路由风险
    成本与密度
      MultiAgent Worker 提高轻量 session 密度
      减少 kube-scheduler 压力
      支持不同 provider 的成本档位
```

> 分析：这个架构的核心价值不是多画几层，而是把“长期会话”作为一等对象。资源池负责容量，Router 负责激活，Store 负责事实，Provider 负责 runtime，Runtime endpoint 负责真正执行。每一层职责清楚后，测试、调试和后续演进都会更可控。

## 12. 与当前实现和后续阶段的关系

```mermaid
timeline
    title AgentCube 会话运行时落地路线
    Phase 0 : 当前基线
            : create / delete / warm pool 更接近资源池能力
            : 不声称完整 Sleep/Resume 已实现
    Phase 1 : Session lifecycle contract
            : SessionStatus
            : SessionPlacement
            : Store CAS API
            : fake provider tests
    Phase 2 : Router resume-before-proxy
            : owner/auth
            : paused -> resume
            : endpoint refresh
            : status table tests
    Phase 3 : RuntimeProvider adapter
            : AgentSandboxProvider
            : SandboxClaim -> adopted Sandbox -> Pod bridge
            : provider capability table
    Phase 4 : MultiAgent Worker / AgentSlot
            : slot isolation
            : per-slot workspace / credential / port / metrics
            : failure domain design
    Phase 5 : Benchmark and observability
            : cold / warm / pause / resume / cleanup
            : p50 / p95 / p99
            : preservation-level grouped results
```

> 注释：这张图应该被理解成目标架构和分阶段设计，不是“一次性大重构”。最小可落地点是先把 Session 状态机、Store CAS 和 Router resume-before-proxy 的 contract 定清楚，再逐步包进真实 provider。

