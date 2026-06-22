# Day 21：OpenSandbox 与 Agent Substrate 补充调研

日期：2026-06-22

## 今日目标

Day11 已经完成 CubeSandbox 深入调研，但当时对 OpenSandbox 和 Agent Substrate 只保留了项目入口和初步判断。今天补齐这两个开源项目的调研，重点回答：

1. 它们分别解决什么问题，和 AgentCube / CubeSandbox 是同层竞争还是互补。
2. 核心组件、资源模型、生命周期和安全边界是什么。
3. 对 AgentCube 后续适配 `kubernetes-sigs/agent-sandbox`、Sleep/Resume、SnapStart / warm pool 设计有什么可借鉴点。

## 调研方法与资料来源

本次以官方仓库源码和文档为主，不做二手文章复述。

| 项目 | 来源 | 本地浅克隆版本 |
| --- | --- | --- |
| OpenSandbox | <https://github.com/opensandbox-group/OpenSandbox> | `3d40414e794d`，2026-06-22，`Merge pull request #1116 from Pangjiping/fix/docs-image-references` |
| Agent Substrate | <https://github.com/agent-substrate/substrate> | `bbafda0d3729`，2026-06-19，`fix(demo): remove ports from sandbox and agent-secret manifests (#274)` |

重点阅读文件：

| 项目 | 文件 / 目录 | 用途 |
| --- | --- | --- |
| OpenSandbox | `README.md`、`ROADMAP.md`、`docs/components/*.md`、`server/configuration.md` | 官方定位、组件、server 配置、runtime / ingress / egress / secure runtime |
| OpenSandbox | `kubernetes/apis/sandbox/v1alpha1/*types.go`、`docs/kubernetes/index.md`、`oseps/*.md` | Kubernetes CRD、Pool、BatchSandbox、SandboxSnapshot、pause/resume、agent-sandbox provider |
| OpenSandbox | `server/opensandbox_server/services/k8s/*provider.py`、`runtime_resolver.py`、`validators.py` | runtime provider 抽象、agent-sandbox 接入、RuntimeClass 和 egress 组合校验 |
| OpenSandbox | `provider_factory.py`、`kubernetes_service.py`、`workload_provider.py`、`agent_sandbox_provider.py`、`batchsandbox_provider.py`、`snapshot_runtime.py` | 二次阅读：确认 provider 边界、pause/resume 委托、BatchSandbox snapshot 路径和 agent-sandbox provider 当前限制 |
| Agent Substrate | `README.md`、`docs/architecture.md`、`docs/api-guide.md`、`docs/roadmap.md` | 官方定位、架构、资源模型、路线图 |
| Agent Substrate | `pkg/api/v1alpha1/*types.go`、`pkg/proto/ateapipb/ateapi.proto` | CRD schema、控制面 gRPC API、Actor / Worker 状态 |
| Agent Substrate | `cmd/*`、`manifests/ate-install/`、`demos/`、`benchmarking/` | 组件边界、部署形态、demo 和测试工具 |
| Agent Substrate | `cmd/ateapi/internal/controlapi/*actor*.go`、`workflow_resume.go`、`workflow_suspend.go`、`workflow_pause.go`、`cmd/atenet/internal/router/*` | 二次阅读：确认 actor 初始状态、worker 分配、checkpoint/restore、router 触发 resume 和 singleflight 去重 |
| AgentCube | `README.md`、`pkg/router/handlers.go`、`pkg/router/session_manager.go`、`pkg/workloadmanager/handlers.go`、`garbage_collection.go`、`workload_builder.go`、`pkg/store/*` | 对照本项目现状：确认 Router/WorkloadManager/store 如何处理 session、GC、agent-sandbox CRD 和 warm pool |

本日没有做实际部署和 benchmark。原因是两个项目都需要额外运行环境：OpenSandbox 的 Kubernetes 路径需要 CRD / controller / registry / runtime class 等条件；Agent Substrate 需要 Kubernetes、ValKey/Redis、gVisor/runsc、对象存储和多组件控制面。今天的产出是源码级初读和架构对比。

## 一句话结论

OpenSandbox 是一个 **SDK / API 优先的通用 sandbox 平台**：它提供 Docker 和 Kubernetes runtime、server、execd、ingress、egress、多语言 SDK、CLI 和 MCP，并且已经把 `kubernetes-sigs/agent-sandbox` 做成 Kubernetes workload provider 之一。

Agent Substrate 是一个 **Kubernetes 上的 stateful actor multiplexing 系统**：它不是通用代码执行 SDK，而是试图把大量长期存在、经常空闲的 agent-like actors 映射到少量预热 worker Pods 上，通过 gVisor checkpoint / restore、独立控制面和路由层实现低延迟 suspend/resume。

对 AgentCube 来说：

- OpenSandbox 更接近“上层 sandbox API / SDK 平台 + 多 backend adapter”的参考样本。
- Agent Substrate 更接近“未来 Sleep/Resume / 高密度会话复用 / actor 状态管理”的架构样本。
- 二者都证明了一个方向：Agent sandbox 不能只做 create/delete；后续重点会转向 provider adapter、pause/resume、snapshot state、路由唤醒、egress / credential / audit。

## OpenSandbox 调研

### 官方定位

OpenSandbox 官方定位是面向 AI 应用的通用 sandbox 平台，覆盖 Coding Agents、GUI Agents、Agent Evaluation、AI Code Execution 和 RL Training 等场景。它不是单一 runtime demo，而是从 SDK、server、runtime backend 到 Kubernetes operator 都提供一整套能力。

核心能力可以分成六层：

| 层级 | OpenSandbox 能力 |
| --- | --- |
| API / SDK | Python、Java/Kotlin、JavaScript/TypeScript、C#/.NET、Go SDK；CLI `osb`；MCP server |
| Server | FastAPI 生命周期控制面，提供 create / get / list / pause / resume / endpoint / renew / delete |
| In-sandbox runtime | `execd`，提供 command、file、PTY、code execution、metrics 等 HTTP API |
| Backend runtime | Docker runtime、Kubernetes runtime；Kubernetes 下支持 `batchsandbox` 和 `agent-sandbox` provider |
| Network | Ingress gateway、egress sidecar、FQDN / CIDR policy、Credential Vault、secure endpoint access |
| Isolation | 默认 runc，也可配置 gVisor、Kata、Firecracker/Kata-FC 等 secure runtime |

### 组件结构

OpenSandbox 的组件边界比较清晰：

| 组件 | 目录 / 文档 | 作用 |
| --- | --- | --- |
| Server | `server/opensandbox_server/` | FastAPI 控制面，统一生命周期 API，调 Docker 或 Kubernetes backend |
| Execd | `docs/components/execd.md`、`components/execd` 文档入口 | 运行在 sandbox 内部，提供 shell command、file、PTY、code interpreter、metrics |
| Ingress | `docs/components/ingress.md` | Kubernetes 路由入口，支持 header / URI / host 路由，能 watch BatchSandbox 或 AgentSandbox |
| Egress | `docs/components/egress.md` | sidecar 方式做 FQDN / IP / CIDR 出站控制、DNS / nftables enforcement、Credential Vault |
| Kubernetes Controller | `kubernetes/` | 管理 `BatchSandbox`、`Pool`、`SandboxSnapshot` CRD |
| SDK / CLI / MCP | `sdks/`、`cli/` | 开发者入口，隐藏后端 runtime 细节 |

一个简化调用链：

```mermaid
flowchart TD
    client["SDK / CLI / MCP"]
    server["OpenSandbox Server REST API"]
    docker["Docker runtime"]
    k8s["Kubernetes runtime"]
    batch["BatchSandbox provider"]
    agentSandbox["agent-sandbox provider"]
    endpoint["sandbox endpoint"]
    execd["execd inside sandbox"]
    network["optional ingress / egress / credential vault"]

    client -->|create / manage| server
    server --> docker
    server --> k8s
    k8s --> batch
    k8s --> agentSandbox
    server -->|endpoint info| endpoint
    client -->|execute / proxy| endpoint
    endpoint --> execd
    endpoint --> network
```

### Kubernetes 资源模型

OpenSandbox Kubernetes controller 定义了三个核心 CRD：

| CRD | 作用 | 关键字段 / 状态 |
| --- | --- | --- |
| `BatchSandbox` | 创建和管理一批 sandbox Pod，也可作为单个 sandbox 的运行态资源 | `spec.replicas`、`spec.template`、`spec.poolRef`、`spec.pause`；状态有 `Pending / Succeed / Pausing / Paused / Resuming / Failed` |
| `Pool` | 预热资源池，用于快速分配 sandbox Pod | `capacitySpec.bufferMin/bufferMax/poolMin/poolMax`、scale/update/recycle strategy |
| `SandboxSnapshot` | Kubernetes pause/resume 的内部 snapshot 资源 | `spec.sandboxName`；`status.phase` 为 `Pending / Committing / Succeed / Failed`，记录 source pod/node 和容器 snapshot image |

这和 AgentCube 当前依赖 `kubernetes-sigs/agent-sandbox` 的方式不同：

- OpenSandbox 自己实现了 `BatchSandbox` / `Pool` / `SandboxSnapshot`，并把 `agent-sandbox` 作为另一个 provider。
- AgentCube 当前更直接依赖 `agent-sandbox` 的 Sandbox / SandboxWarmPool / SandboxClaim 生态，WorkloadManager 和 Router 自己管理 session 和流量入口。

### Pause / Resume 设计

OpenSandbox 的 Kubernetes pause/resume 当前是 **rootfs snapshot** 路线：

1. `pause`：Server patch `BatchSandbox.spec.pause=true`。
2. Controller 创建内部 `SandboxSnapshot`。
3. 同节点 commit Job 把容器 rootfs commit 成 OCI image 并 push 到 registry。
4. Snapshot ready 后释放 runtime Pod / pooled allocation。
5. `resume`：Server patch `BatchSandbox.spec.pause=false`。
6. Controller 读取最新 snapshot，把模板 image 改写为 snapshot image，重新创建 runtime。

重要限制：

- 当前文档明确限制在 `BatchSandbox.spec.replicas=1` 场景。
- 这种方案保存的是 rootfs，不保存进程内存、打开 socket 或 CPU register。
- Snapshot image 的清理依赖 registry retention / GC，删除 `SandboxSnapshot` 不等于删除 registry 中的 OCI image。

对 AgentCube 的启发：

- Sleep/Resume 可以先从“rootfs / workspace 保留”开始，不必一步到位实现内存级 checkpoint。
- 状态机必须显式区分 `Ready / Paused / Deleted` 或更细的 `Pausing / Resuming`，否则 Router 很难在请求到来时做 resume-before-proxy。
- 删除策略要拆开：Ready idle -> Paused，Paused timeout / max TTL -> Deleted。

### `kubernetes-sigs/agent-sandbox` 接入

OpenSandbox 已经把 `kubernetes-sigs/agent-sandbox` 做成 provider：

```toml
[runtime]
type = "kubernetes"
execd_image = "opensandbox/execd:v1.0.19"

[kubernetes]
namespace = "default"
workload_provider = "agent-sandbox"

[agent_sandbox]
shutdown_policy = "Delete"
```

从 OSEP-0002 和 server config 看，OpenSandbox 的接入思路是：

- 保持 OpenSandbox 生命周期 API / SDK 不变。
- 在 server 内部新增 `agent-sandbox` workload provider。
- 创建、查询、删除时由 provider 生成 / 读取 `agent-sandbox` CR。
- Ingress 组件也支持 `--provider-type=agent-sandbox`，通过 `status.serviceFQDN` 找到目标 sandbox。

这点和 AgentCube upstream [PR #387](https://github.com/volcano-sh/agentcube/pull/387) 工作直接相关：`agent-sandbox` 上游 CRD 和 lifecycle 逻辑变化会影响使用方。OpenSandbox 的做法值得借鉴的是把 provider 差异收敛在 adapter 层，并在文档里明确 `batchsandbox` 与 `agent-sandbox` 的配置边界。

### Secure Runtime 与出站治理

OpenSandbox 的 secure runtime 是 server-level 配置：

| Runtime | Docker | Kubernetes |
| --- | --- | --- |
| gVisor | OCI runtime，例如 `runsc` | `runtimeClassName`，例如 `gvisor` |
| Kata | OCI runtime 或 RuntimeClass | `kata-qemu` / `kata-clh` 等 |
| Firecracker | Docker 不支持 | 通过 Kata Firecracker RuntimeClass，例如 `kata-fc` |

注意这里的 Firecracker 不是 OpenSandbox 自己实现 VMM，而是借助 Kubernetes RuntimeClass / Kata-FC。

Egress 方面，OpenSandbox 的 sidecar 支持：

- FQDN allowlist / denylist。
- IP / CIDR target。
- wildcard domain。
- DNS proxy 和 `dns+nft` 模式。
- Credential Vault，允许代理层给外部请求注入 bearer / basic / API key / custom header。
- Fail-closed：iptables 设置失败时 sidecar 退出，避免策略没有生效还放行流量。

一个很重要的限制：OpenSandbox 文档明确指出 gVisor 和 egress sidecar 的 iptables nat REDIRECT 路径不兼容，因为 gVisor netstack 不支持所需 nat table。OpenSandbox 的处理是启动时/请求时校验并给出明确错误，建议改用 Kata 或 CNI-level FQDN policy。

对 AgentCube 的启发：

- 以后讨论“支持 gVisor / Kata / NetworkPolicy”时，不能只看 RuntimeClass 是否存在，还要验证 sidecar、iptables、CNI、DNS policy 是否兼容。
- 出站治理需要纳入测试矩阵，不然 Agent 能跑代码但不能安全访问外部 API。

### 性能与成熟度信号

OpenSandbox Kubernetes 文档给出一组“交付 100 个 sandbox”的对比数据：

| 场景 | 总时间 |
| --- | ---: |
| SIG Agent-Sandbox concurrency=1 | 76.35 s |
| SIG Agent-Sandbox concurrency=10 | 23.17 s |
| SIG Agent-Sandbox concurrency=50 | 33.85 s |
| BatchSandbox | 0.92 s |

这组数据来自 OpenSandbox 文档，不是本机复测结果。它表达的设计意图是：`BatchSandbox` 用一个 CR 表达批量 sandbox delivery，避免为 N 个 sandbox 做 N 次独立 CR / controller reconciliation。

工程成熟度方面，OpenSandbox 已经有：

- OSEP 流程。
- 多语言 SDK。
- Helm chart。
- CLI。
- MCP server。
- server config reference。
- Kubernetes CRD / controller / generated client。
- runtime / secure runtime / egress / ingress 文档。

因此它更像一个正在快速补齐生产面的平台，而不是单个实验项目。

## Agent Substrate 调研

### 官方定位

Agent Substrate 官方说明里特别写了：这不是 Google 官方支持产品，而且项目还处于非常早期，API 基本不保证兼容。

它的目标不是帮开发者写 agent，也不是一个多语言 sandbox SDK，而是 **在 Kubernetes 上更高效地运行大量 agent-like workloads**。核心假设是：

- agent-like workloads 大多数时间在等待输入、LLM、工具调用或事件；
- 如果每个 session 都长期占一个 Pod，资源利用率很差；
- Kubernetes API server / scheduler 不适合把每次 session 唤醒都放在关键路径上；
- 更好的做法是预热少量 worker Pods，把大量逻辑 actor suspend/resume 到这些 worker 上。

官方 README 里描述的核心抽象是：

```mermaid
flowchart LR
    actors["many logical actors"]
    workers["fewer ready workers"]
    suspend["suspend idle actors and snapshot state"]
    resume["resume actor on request before routing traffic"]

    actors -->|multiplex onto| workers
    workers --> suspend
    suspend --> resume
```

### 核心组件

Agent Substrate 的组件比 OpenSandbox 更偏控制面 / 数据面系统：

| 组件 | 目录 | 作用 |
| --- | --- | --- |
| `ate-api-server` | `cmd/ateapi` | 控制面 gRPC API，管理 Actor / Worker 生命周期 |
| `atecontroller` | `cmd/atecontroller` | Kubernetes controller，reconcile `WorkerPool`、`ActorTemplate` 等 CRD |
| `atelet` | `cmd/atelet` | 节点级 DaemonSet，管理物理 worker pods，协调 snapshot 传输 |
| `ateom-gvisor` | `cmd/ateom-gvisor` | 运行在 worker pod 内部的 helper，通过 gRPC 调用 `runsc` checkpoint / restore |
| `atenet` | `cmd/atenet` | 网络代理 / Envoy external processing server，负责 actor-aware routing |
| `podcertcontroller` | `cmd/podcertcontroller` | Pod certificate polyfill，用于内部 mTLS / identity |
| `kubectl-ate` | `cmd/kubectl-ate` | 管理 Actor / Worker 的 kubectl plugin |
| `ValKey/Redis` | `manifests/ate-install/valkey.yaml` | 动态 Actor / Worker 状态存储 |

一个简化架构：

```mermaid
flowchart TD
    request["Client request"]
    router["atenet router / Envoy"]
    api["ate-api-server"]
    suspended{"actor suspended?"}
    resume["ResumeActor"]
    scheduler["claim a ready Worker"]
    atelet["atelet"]
    ateom["ateom-gvisor / runsc restore"]
    running["actor RUNNING on worker pod"]
    proxy["proxy request to worker pod IP"]

    request --> router
    router -->|query actor location| api
    api --> suspended
    suspended -->|yes| resume
    resume --> scheduler
    scheduler --> atelet
    atelet --> ateom
    ateom --> running
    suspended -->|no| running
    running --> proxy
    router --> proxy
```

### 资源模型

Agent Substrate 刻意把“低频配置”和“高频状态”分开：

| 类型 | 存储位置 | 资源 | 作用 |
| --- | --- | --- | --- |
| 系统配置 | Kubernetes CRD / etcd | `WorkerPool` | 定义预热 worker pods 数量、sandbox class、runtime assets、调度约束 |
| 系统配置 | Kubernetes CRD / etcd | `ActorTemplate` | 定义 actor workload image、env、snapshot storage、worker selector，并生成 golden snapshot |
| 系统配置 | Kubernetes CRD / etcd | `SandboxConfig` | cluster-scoped，定义 gVisor / microVM 等 sandbox runtime assets |
| 动态实例状态 | ValKey / Redis | `Actor` | 具体 actor instance，记录状态、worker location、snapshot info、version |
| 动态实例状态 | ValKey / Redis | `Worker` | 具体物理 worker pod 的可用 / 占用状态 |

这个设计和 AgentCube 当前很不同：

- AgentCube 当前更多把 runtime 资源作为 Kubernetes CRD 处理。
- Agent Substrate 认为高频 actor state 不应该全部写 Kubernetes API server，因此放到低延迟 state store。
- `kubectl ate get actor` 查询的是 Substrate 控制面，不是 Kubernetes CRD；`kubectl get actortemplate` / `workerpool` 才是 Kubernetes CRD。

### Actor 生命周期

Agent Substrate 的核心生命周期：

| 阶段 | 动作 | 状态 / 数据 |
| --- | --- | --- |
| Template 准备 | 创建 `ActorTemplate` 后生成 golden actor / golden snapshot | 模板进入 `Ready` 后，可用来创建 actor |
| CreateActor | 创建具体 actor 记录 | 初始是 `STATUS_SUSPENDED`，指向模板的 golden snapshot |
| ResumeActor | 请求到来或显式调用时恢复 actor | 调度 free worker，atelet / ateom 恢复 golden 或 latest snapshot，actor 变 `STATUS_RUNNING` |
| SuspendActor | 空闲或显式调用时挂起 actor | gVisor checkpoint memory + disk，写入对象存储，worker 归还池 |
| DeleteActor | 删除已 suspended actor | 删除控制面记录和后续 GC snapshot |

`ateapi.proto` 里还有 `PauseActor` / `STATUS_PAUSED`，注释说 pause 会把 snapshot 保留在 node VM 本地；而主架构文档更多讲 `SuspendActor` 写持久对象存储。这说明 Agent Substrate 的生命周期语义仍在演进，需要读代码和运行验证后才能判断最终稳定行为。

### Snapshot 与状态保留

Agent Substrate 的状态目标比 OpenSandbox rootfs snapshot 更激进：它希望保存 **memory + disk**。

当前文档描述：

- `ateom-gvisor` 在 worker pod 内调用 `runsc` 做 checkpoint / restore。
- `atelet` 负责把 snapshot stream 到 GCS / S3 类对象存储。
- Kind 本地部署清单里有 RustFS，用于替代云对象存储。
- ActorTemplate 会产生 golden snapshot，新 actor 第一次 resume 可以从 golden snapshot hydrate。
- 后续 suspend 会生成 latest snapshot，下一次 resume 从 latest snapshot 继续。

工程 caveat：

- 文档提到当前需要带 `--allow-connected-on-save` 的 `runsc` 版本，用来绕过网络 resumption checkpoint 的问题。
- roadmap 里还有 gVisor snapshot optimization、incremental snapshot、disk-only resume、peer-to-peer snapshot sharing、microVM runtime 等项目，说明这条路线还在快速变化。

### 网络、身份与安全

Agent Substrate 网络层是 `atenet + Envoy`：

- 请求通过统一 DNS / Host 规则定位 actor，例如 `<id>.actors.resources.substrate.ate.dev`。
- Router 从 Host header 提取 actor ID。
- 如果 actor suspended，先触发 `ResumeActor`，再把原始请求转发到恢复后的 worker。

安全方面，当前设计包含：

- gVisor 作为主要 sandbox boundary。
- 内部组件 mTLS。
- SessionIdentity gRPC service，给 session mint JWT / certificate。
- Pod Certificate polyfill。
- Kubernetes NetworkPolicy 可在 WorkerPool 边界控制连接。

roadmap 中还在规划：

- actor-to-actor authz。
- per-actor ingress / egress policy。
- credential injection。
- audit logging。
- threat detection telemetry。
- microVM sandbox backend。

这说明 Agent Substrate 很看重“actor identity 随 actor 迁移，而不是绑定当前 pod”。这点对 AgentCube 后续 session 设计也有参考价值：如果 sandbox 会 sleep/resume 或迁移，身份和权限不能简单绑定 Pod 名或 Pod IP。

### Demo 与测试信号

仓库提供几个 demo：

| Demo | 作用 |
| --- | --- |
| `demos/counter` | Stateful counter，验证 suspend/resume 后计数状态保留 |
| `demos/sandbox` | Alpine sandbox，允许执行 shell command，验证文件系统状态保留 |
| `demos/claude-code-multiplex` | 多个 Claude Code agents 共享较少 worker pods，演示 oversubscription |
| `demos/agent-secret` | 演示 Zero-Idle self-suspension 和 volatile memory re-animation |

benchmark 目录已有 Locust + Prometheus / Grafana 的雏形，但 README 明确说这是 nascent suite。当前更适合作为“方向明确但未成熟”的项目观察，而不是拿官方目标数字直接和 AgentCube 本机 benchmark 横比。

## 源码二次深入后的三者对比

先给最短判断：

| 项目 | 最像 AgentCube 的地方 | 最不像 AgentCube 的地方 | 对 AgentCube 最直接的启发 |
| --- | --- | --- | --- |
| OpenSandbox | 都是“外部 API / SDK 创建 sandbox，再通过 endpoint 执行代码或代理请求” | 它把 Kubernetes backend 做成 `WorkloadProvider` adapter；AgentCube 当前直接在 WorkloadManager 中引用 `agent-sandbox` CRD 语义 | 先抽清楚 provider 边界，再升级 `agent-sandbox`；否则依赖升级会反复波及 handler、helper、e2e、codegen |
| Agent Substrate | 都面向 long-session、stateful、intermittently active 的 agent workloads | 它把 session/actor 状态作为一等对象放到 Redis/ValKey，并让 Router 在代理前触发 resume；不是每个 session 都长期对应一个独立 K8s CR | Sleep/Resume 不能只加状态字段，必须同时设计 store 状态机、router resume-before-proxy、worker/endpoint 更新和并发去重 |
| AgentCube | README 目标和二者相似：低延迟、状态保留、sleep/resume、K8s-native agent workload | 当前 main 的实际路径仍是 create/delete/warm pool：Router 查 session 并代理，GC idle/TTL 后删除 Sandbox/SandboxClaim，没有 Paused 状态和 resume 主路径 | upstream [PR #387](https://github.com/volcano-sh/agentcube/pull/387) 属于“先把依赖和创建路径稳定住”；Sleep/Resume 应另开设计，不应混在 agent-sandbox 兼容修复里 |

源码级对照表：

| 维度 | AgentCube | OpenSandbox | Agent Substrate |
| --- | --- | --- | --- |
| 系统主语 | `AgentRuntime` / `CodeInterpreter` 生成 session，再绑定 `Sandbox` 或 `SandboxClaim` | `Sandbox` 是 API 主语，后端可选 Docker、BatchSandbox、agent-sandbox | `Actor` 是主语，worker pod 只是可复用承载体 |
| 控制面形态 | Router + WorkloadManager + K8s CRD + Redis/ValKey store | FastAPI server + Kubernetes/Docker provider + execd | `ate-api-server` gRPC + Redis/ValKey + controllers + `atelet` + `atenet` |
| K8s 的角色 | 核心生命周期依赖；WorkloadManager 直接创建/删除 agent-sandbox CR | 可选 backend；provider 隔离 BatchSandbox 和 agent-sandbox | 管低频配置和 worker pods；高频 actor 状态绕开 K8s API server |
| 运行态状态 | `SandboxInfo` JSON + expiry / last-activity sorted set；无 `PausedAt` / `pauseTimeout` | 由 provider 读取 CR status；BatchSandbox 有 `Paused/Pausing/Resuming` | Actor proto 明确定义 `RESUMING/RUNNING/SUSPENDING/SUSPENDED/PAUSING/PAUSED` |
| 请求路径 | Router 读 `x-agentcube-session-id`；无 session 则创建；有 session 则直接代理到旧 endpoint | SDK/API 调 server；endpoint 由 provider 或 ingress 解析 | Router 从 Host 解析 actor ID，先 `ResumeActor`，再把请求转发到 worker IP |
| idle 后行为 | `garbage_collection.go` 按 idle/TTL 删除 K8s resource 和 store entry | BatchSandbox 可 patch `spec.pause=true` 并生成 snapshot；agent-sandbox provider 目前未实现 pause/resume | `SuspendActor` 写外部 snapshot；`PauseActor` 写本地 snapshot 并释放 worker |
| 启动加速 | `SandboxWarmPool` / `SandboxClaim`，以及 SnapStart 规划 | Pool、BatchSandbox、client-side pool、snapshot image | WorkerPool + golden/latest snapshot restore |
| 依赖升级风险 | `sigs.k8s.io/agent-sandbox` 类型散落在 WorkloadManager builder/controller/helper/k8s client 测试路径 | `agent-sandbox` 只是一种 provider；但当前 provider 仍写死 `agents.x-k8s.io/v1alpha1`，未来也要适配 v1beta1 | 主要风险不在 agent-sandbox，而在 gVisor/runsc checkpoint、ATE 组件协议和早期 API 变化 |
| 安全/出网 | 目前更多依赖 K8s/CNI/runtime；项目内出网治理还不完整 | egress sidecar、FQDN/CIDR、Credential Vault、RuntimeClass 兼容校验较完整 | identity 随 Actor 迁移，mTLS/SessionIdentity 已有，per-actor egress 和 credential injection 仍在 roadmap |
| 成熟度判断 | 社区主线项目，适配和测试材料正在补齐；README 的 sleep/resume 目标尚未闭合到代码 | 工程面最完整，SDK/CLI/MCP/egress/provider 都有；但 agent-sandbox provider 不等于完整 sleep/resume | 方向最接近 AgentCube 未来态，但 README 明确 very early，部署链路和 runtime 依赖更重 |

### 三个尖锐结论

1. OpenSandbox 更像 AgentCube 的“外壳和接入层”对照组。它不一定更懂 agent session，但 provider adapter 这条边界比 AgentCube 当前更干净，所以它能把 `agent-sandbox` 升级风险压在一个 provider 内。
2. Agent Substrate 更像 AgentCube README 里“smart sleep/resume”的终局对照组。它已经把 Router 触发 resume、actor 状态机、worker 复用、checkpoint/restore 串起来；代价是系统复杂度和 runtime 约束显著高于 AgentCube 当前路径。
3. AgentCube 现在卡在中间层：比 OpenSandbox 更 Kubernetes-native、比 Agent Substrate 更贴近现有 `agent-sandbox` 生态，但 session store、sandbox CR、Router endpoint 三者还没有形成真正的 Paused/Resume 闭环。这也是后续不应把 upstream [PR #387](https://github.com/volcano-sh/agentcube/pull/387) 和 Sleep/Resume 混在一个 PR 里的原因。

### 对 AgentCube 源码的直接映射

| AgentCube 文件 | 当前作用 | 对后续适配/设计的含义 |
| --- | --- | --- |
| `README.md` | 明确写了 stateful lifecycle 和 smart sleep/resume 目标 | 文档目标已经存在，但不能假设 main 已实现；proposal 要区分“设计承诺”和“代码现状” |
| `pkg/router/handlers.go` | `handleInvoke` 读取 `x-agentcube-session-id`，更新 last activity，然后 `forwardToSandbox` | Sleep/Resume 的 resume-before-proxy 必须落在这里或 `SessionManager`，否则 Paused session 仍会被代理到旧 endpoint |
| `pkg/router/session_manager.go` | 空 session 调 WorkloadManager 创建；非空 session 只查 store | 这里目前没有 `Paused -> Ready` 分支，也没有并发 resume 去重；Agent Substrate 的 `ActorResumer` 是直接参考对象 |
| `pkg/workloadmanager/workload_builder.go` | 直接构造 `agent-sandbox` `Sandbox` / `SandboxClaim` / warm-pool 相关对象 | `agent-sandbox` 版本升级应优先把字段差异集中在 builder/helper，而不是扩散到业务 handler |
| `pkg/workloadmanager/handlers.go` | 创建 CR、等 Ready、解析 warm-pool pod annotation、写 store endpoint | v0.4/v0.5 适配的关键是 readiness、pod name、endpoint、NetworkPolicy，不只是编译通过 |
| `pkg/workloadmanager/garbage_collection.go` | idle/TTL 后删除 `Sandbox` 或 `SandboxClaim` 并删除 store | Sleep/Resume 要把 `sessionTimeout` 从删除改为 pause，另加 `pauseTimeout` 删除；否则行为仍是 GC |
| `pkg/store/interface.go`、`store_redis.go` | 存 session JSON、expiry index、last-activity index | 若做 Paused 状态，需要扩展 store schema：`Status`、`PausedAt`、`PauseTimeout`、resume 锁或幂等保护 |

## 和 CubeSandbox 的分层关系

Day11 里已经确认 CubeSandbox 是底层 microVM sandbox platform。把三个项目放在一起看：

| 项目 | 更像哪一层 | 最强特征 |
| --- | --- | --- |
| CubeSandbox | 底层 sandbox platform / microVM runtime | RustVMM/KVM/PVM、E2B 兼容、CubeCoW snapshot / clone / rollback、CubeVS/CubeEgress |
| OpenSandbox | sandbox API / SDK 平台 + 多 backend adapter | 多语言 SDK、Docker/K8s runtime、BatchSandbox、agent-sandbox provider、egress / credential vault |
| Agent Substrate | stateful actor scheduling / multiplexing control plane | actor/worker 分离、K8s control plane bypass、gVisor checkpoint / restore、routing-triggered resume |
| AgentCube | Kubernetes-native Agent workload 管理层 | WorkloadManager、Router、agent-sandbox dependency、warm pool、AgentRuntime / CodeInterpreter |

因此后续写竞品表时不能把它们简单放成“谁启动更快”。更合理的口径是：

- CubeSandbox：强隔离和快照执行层。
- OpenSandbox：开发者 API / SDK 和多 runtime 接入层。
- Agent Substrate：大规模 stateful session multiplexing 层。
- AgentCube：Kubernetes-native agent runtime 编排层。

## 对 AgentCube 后续工作的启发

### 1. `agent-sandbox` 适配要做成 provider compatibility 工作

OpenSandbox 已经把 `agent-sandbox` 明确当成 provider，而不是把 provider 细节散落到所有业务逻辑中。AgentCube upstream [PR #387](https://github.com/volcano-sh/agentcube/pull/387) / 后续 v0.5 适配也应继续保持这个思路：

- CRD schema 差异集中在 helper / adapter。
- WorkloadManager 只关心“创建 / 读取 / 删除 / readiness / pod endpoint”这些稳定语义。
- PR 文档要解释依赖版本、CRD 字段、NetworkPolicy / warm pool / pod name annotation 的变化。

### 2. Sleep/Resume 要先确定状态语义

OpenSandbox 和 Agent Substrate 都把 suspend/resume 作为一等生命周期处理，但两者状态语义不同：

| 路线 | 保存内容 | 恢复成本 | 适合的第一阶段 |
| --- | --- | --- | --- |
| rootfs snapshot | 文件系统 / workspace | 较低，不保留进程内存 | AgentCube 可以先验证 workspace 持久化 |
| memory + disk checkpoint | 进程内存 + 文件系统 | 更复杂，runtime 依赖强 | 更接近 Agent Substrate 的长期目标 |

AgentCube 的 Sleep/Resume proposal 最少需要明确：

- Ready idle 后变 Paused。
- Router 收到带 session-id 的请求时先 resume。
- Paused timeout 或 maxSessionDuration 后 delete。
- Paused 状态下 workspace/context 是否保留，保留到什么程度。
- 失败时是否 fallback recreate，用户能看到什么错误。

### 3. 测试不能只停留在 e2e happy path

OpenSandbox / Agent Substrate 的复杂性说明后续 AgentCube 测试需要覆盖：

| 测试项 | 为什么需要 |
| --- | --- |
| direct sandbox create/run/delete | 验证最小 provider adapter |
| warm pool adoption | 验证已有 sandbox 被 claim 后 pod / endpoint / annotation 不错 |
| router resume-before-proxy | 验证 Sleep/Resume 请求路径 |
| workspace/file persistence | 区分 rootfs resume 和 cold recreate |
| network policy / egress | 避免 sandbox ready 但 router / execd 不通 |
| cleanup / TTL | 避免 Paused / Snapshot / Pod / Redis 残留 |
| math-agent / LLM e2e | 验证真实 Agent 工作流，不只验证 sandbox API |

### 4. 出网安全和凭据注入是未来重点

CubeSandbox 有 CubeEgress，OpenSandbox 有 egress sidecar + Credential Vault，Agent Substrate roadmap 也把 per-actor egress、credential injection、audit logging 列为重点。AgentCube 目前更多关注 sandbox lifecycle 和 runtime compatibility，但 Agent 真正进入生产后，安全问题会集中在：

- Agent 能访问哪些外部域名。
- 密钥是否直接暴露给 Agent 代码。
- 出站请求是否可审计。
- 用户 session identity 是否和 Pod / runtime 解耦。

后续写 roadmap 或 proposal 时可以把它列为独立方向，而不是附属于 “NetworkPolicy” 一个字段。

## 当前卡点与未完成项

| 项 | 状态 | 原因 / 后续 |
| --- | --- | --- |
| OpenSandbox 实际部署 | 未执行 | 需要 Docker 或 K8s runtime；K8s 路径还要 controller、CRD、registry、RuntimeClass。今天先做源码和文档调研 |
| Agent Substrate 实际部署 | 未执行 | 需要 kind/GKE、ValKey/Redis、gVisor/runsc、对象存储、ko 镜像构建；不适合作为今天的轻量调研 |
| OpenSandbox vs AgentCube benchmark | 未执行 | 官方 BatchSandbox 数据只能作为设计信号，不能和本机 AgentCube 数据直接横比 |
| Agent Substrate API 稳定性 | 风险高 | README 明确说 very early development，不保证兼容；后续只能当架构观察样本 |
| Day11 其他云服务 | 未覆盖 | AgentBay / AWS AgentCore 更偏托管云服务和 SDK，应另开产品对比，不和这两个开源项目混在同一篇深读 |

## 下一步

1. 后续如果要实测 OpenSandbox，优先从 Docker runtime 最小 smoke 开始：server health、create python sandbox、execd command、file read/write、delete；再进入 Kubernetes `BatchSandbox` / `agent-sandbox` provider。
2. 如果要实测 Agent Substrate，优先跑 kind quickstart + counter demo，验证 `CreateActor -> router request -> ResumeActor -> SuspendActor -> resume 后计数保留`。
3. AgentCube upstream [PR #387](https://github.com/volcano-sh/agentcube/pull/387) review 时可以引用 OpenSandbox 的 provider adapter 方式，说明 `agent-sandbox` 适配应该集中解释依赖和 CRD 差异。
4. 后续 Sleep/Resume 设计时，把 OpenSandbox rootfs snapshot 和 Agent Substrate memory+disk checkpoint 作为两条技术路线对照，避免直接把“Paused”写成只有状态字段、没有恢复语义。
