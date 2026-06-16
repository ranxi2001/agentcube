# Day 13：Karmada 项目初读

## 今日目标

Day12 已完成 AgentCube SnapStart / warm pool benchmark 口径梳理，并在社区 PR [#366](https://github.com/volcano-sh/agentcube/pull/366#issuecomment-4714612811) 发表了 benchmark validation 评论。

Day13 先学习 [karmada-io/karmada](https://github.com/karmada-io/karmada)。Karmada 是一个成熟的 Kubernetes 多集群编排项目，和 AgentCube 不是同一业务领域，但它在 Kubernetes-native API 设计、控制面分层、调度策略、状态回写、proposal 规范和社区协作方面都值得借鉴。

## 本仓库协作规范同步

今天同步整理了 `/home/agentcube/AGENTS.md` 中的本地协作规范，后续读代码、写报告、做测试和准备 PR 都按这个口径执行。

| 方面 | 需要遵守的要点 |
| --- | --- |
| 项目结构 | AgentCube 是 Go-first Kubernetes 项目；核心入口在 `cmd/`，共享逻辑在 `pkg/`，API 类型在 `pkg/apis/runtime/v1alpha1`，生成客户端在 `client-go/`，部署资源在 `manifests/charts/base` 和 `docker/`，Python SDK 在 `sdk-python/` |
| 常用命令 | Go 代码改动优先跑 `make test`，格式化用 `make fmt`，全量构建用 `make build-all`，API / CRD / client-go 变更后跑 `make gen-all`，部署或 sandbox 生命周期改动需要考虑 `make e2e` |
| 代码风格 | Go 使用标准格式和惯用写法；公开 API-facing symbol 需要清晰注释；Python 模块保持 snake_case 并沿用现有目录结构 |
| 测试要求 | 控制器、路由、认证、store 等逻辑要优先补 colocated `*_test.go`；并发敏感逻辑考虑 `go test -race ./...`；SDK / CLI 变更要看对应 Python 测试目录 |
| 实习报告 | 报告不能只写成功路径；需要记录失败命令或步骤、错误现象、初步原因、绕过方式和最终结论，方便复盘和 mentor 同步 |
| commit / PR | commit 使用 `component: imperative summary` 风格；PR 要说明问题、改动、关联 issue、测试结果，并按 `OWNERS` 请求 reviewer |
| 安全配置 | 不提交 Redis 密码、API token、kubeconfig、模型密钥或 `.env`；报告和 shell transcript 也不能粘贴真实密钥 |

这部分规范会直接影响 Day13 后续学习方式：读 Karmada 时重点看它如何组织 `cmd/`、`pkg/`、API 类型、controllers、scheduler、proposal 和 e2e；回到 AgentCube 做开发时，则必须把代码变更、测试证据、报告记录和 PR 说明放在同一条可追踪链路里。

## 项目状态快照

以下信息在 2026-06-16 通过 GitHub API 和官方仓库核对：

| 项 | 值 |
| --- | --- |
| 仓库 | `karmada-io/karmada` |
| 定位 | Open, Multi-Cloud, Multi-Cluster Kubernetes Orchestration |
| CNCF 状态 | CNCF incubation project |
| License | Apache-2.0 |
| 默认分支 | `master` |
| 最新 release | `v1.18.0`，2026-05-30 发布 |
| GitHub stars / forks | stars `5499`，forks `1144` |
| open issues | `730` |
| 本地源码 | 已 shallow clone 到 `/home/karmada` |

## 官方定位

Karmada 的核心目标是：让用户用 Kubernetes 原生 API 管理跨多个 Kubernetes 集群和云厂商的应用，不要求用户改造已有 workload。

它强调几个方向：

- Kubernetes API 兼容：用户继续使用 Deployment、Service、ConfigMap 等原生对象。
- 多集群调度：根据 cluster affinity、权重、region / zone / provider 等维度做放置和副本拆分。
- 集中管理：host cluster / Karmada control plane 统一管理 member clusters。
- 跨集群高可用和故障迁移：支持 failover、graceful eviction、reschedule 等机制。
- 避免 vendor lock-in：多云和混合云，不绑定某一家云厂商。

## 核心价值判断

结合 mentor 的介绍和今天的源码初读，Karmada 收获社区认可的关键不是“组件很多”，而是它抓住了一个真实且成熟的痛点：企业已经有很多 Kubernetes 集群，但缺少一种 Kubernetes-native 的方式，把多个集群当成一个统一资源池来调度、分发、回收和观测。

Karmada 的核心实现可以概括为：

```text
用户原生 Kubernetes 资源
+ 多集群传播策略
-> 调度到哪些集群
-> 生成每个集群的 Work
-> 下发到 member cluster
-> 回收状态 / 失败迁移 / 重新调度
```

它真正有价值的地方是：用户原来怎么写 `Deployment`、`Service`、`ConfigMap`，现在仍然怎么写；Karmada 在旁边补上跨集群调度、资源分发、状态聚合和故障迁移能力。这种设计降低了迁移成本，也更容易融入已有 Kubernetes 生态。

和 Karmada 对比，AgentCube 目前缺的不是组件数量，而是需要把核心痛点打得更清楚。AgentCube 想解决的是 AI Agent 需要安全、快速、可复用、可调度的执行环境，但这个目标还需要进一步收敛成更锋利的杀手场景，例如：

```text
一次 Agent 任务需要并发 fork 10/100 个代码执行环境，
每个环境必须隔离、可回滚、可观测，
并且启动延迟必须从秒级降到百毫秒级。
```

也就是说，AgentCube 需要证明自己不是“能创建 sandbox 的 Kubernetes controller”，而是一个能把 Agent 执行环境变成可调度、可复用、可快照、可观测基础设施的控制面。

| 维度 | Karmada 已经很清楚 | AgentCube 还需要补强 |
| --- | --- | --- |
| 核心痛点 | 多集群 Kubernetes 管理复杂 | Agent sandbox 的极速启动、安全隔离、状态复制痛点需要更强 demo 和 benchmark 证明 |
| 用户入口 | 原生 K8s 资源 + `PropagationPolicy` | 需要明确 Agent 开发者怎么接入，例如 SDK、E2B 兼容或 Code Interpreter 替代 |
| 核心闭环 | policy -> binding -> work -> cluster -> status | runtime -> sandbox/session -> warm pool/snapshot -> execution -> metrics/status |
| 立即价值 | 一套 API 管多个集群 | 需要展示比普通 Pod / Docker / E2B / CubeSandbox 更适合哪些场景 |
| 成熟能力 | 调度、分发、failover、状态聚合 | SnapStart、强隔离 runtime、benchmark suite、生产级观测还在早期 |
| 生态位置 | Kubernetes 多集群控制面 | AI Agent 执行控制面的位置还要讲清楚 |

一句话总结：Karmada 成功是因为它把“多集群管理”这个成熟痛点，用 Kubernetes 原生方式做成了完整控制面；AgentCube 要成功，需要把“Agent 执行环境管理”这个新痛点，也做成一个有明确杀手场景、可量化性能收益、可直接接入的完整控制面。

## 架构组件

Karmada control plane 主要组件：

| 组件 | 作用 |
| --- | --- |
| `karmada-apiserver` | Karmada 控制面的 API 入口，基于 Kubernetes API server 实现，保证 Kubernetes 生态兼容 |
| `karmada-aggregated-apiserver` | 基于 Kubernetes API Aggregation Layer，提供 Cluster API、`cluster/status`、`cluster/proxy` 等能力 |
| `karmada-controller-manager` | 运行自定义 controllers，负责 policy、binding、work、status、failover 等控制逻辑 |
| `karmada-scheduler` | 负责把资源调度到合适 member clusters |
| `karmada-webhook` | validation / mutation，用于默认值、校验和策略约束 |
| `karmada-agent` | Pull 模式下部署在 member cluster，负责从 control plane 同步 manifests 和状态 |
| `karmada-scheduler-estimator` | 为 scheduler 提供更准确的集群可调度资源估算 |
| `karmada-descheduler` | 周期性检测副本和集群状态变化，触发动态重调度 |
| `karmada-search` | 多集群 global search 和 resource proxy |
| `karmadactl` / `kubectl-karmada` | CLI 工具 |

## 核心资源链路

Karmada 的典型资源传播链路：

```text
Kubernetes native resource
  + PropagationPolicy / ClusterPropagationPolicy
  -> ResourceBinding / ClusterResourceBinding
  -> Work
  -> member cluster Kubernetes resource
  -> Work status / aggregated status
```

官方 nginx 示例：

```yaml
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: nginx-propagation
spec:
  resourceSelectors:
    - apiVersion: apps/v1
      kind: Deployment
      name: nginx
  placement:
    clusterAffinity:
      clusterNames:
        - member1
        - member2
    replicaScheduling:
      replicaDivisionPreference: Weighted
      replicaSchedulingType: Divided
      weightPreference:
        staticWeightList:
          - targetCluster:
              clusterNames:
                - member1
            weight: 1
          - targetCluster:
              clusterNames:
                - member2
            weight: 1
```

这个设计有几个值得学习的点：

- 用户 workload 仍是原生 `Deployment`，多集群逻辑放在独立 policy 资源里。
- `PropagationPolicy` 只描述“选哪些资源”和“怎么放置”，不直接执行下发。
- `ResourceBinding` 是调度结果和控制面中间态，类似“资源和目标集群的绑定合同”。
- `Work` 是面向单个 member cluster 的执行单元，里面包含最终要下发的 manifest。

## 源码结构初读

本地目录：

| 路径 | 内容 |
| --- | --- |
| `/home/karmada/cmd` | 多个二进制入口：controller-manager、scheduler、agent、webhook、search、CLI 等 |
| `/home/karmada/pkg/apis` | Karmada API 类型定义，包括 `policy`、`work`、`cluster`、`apps`、`autoscaling`、`remedy` 等 |
| `/home/karmada/pkg/controllers` | 控制器实现，包括 binding、execution、cluster、status、failover、quota、mcs 等 |
| `/home/karmada/pkg/scheduler` | 多集群调度核心 |
| `/home/karmada/pkg/generated` | client / informer / lister 等生成代码 |
| `/home/karmada/charts` | Helm chart |
| `/home/karmada/docs/proposals` | proposal 文档，包含 failover、migration、resource interpreter、resource quota 等 |
| `/home/karmada/test/e2e` | e2e 测试 |

主要二进制入口：

| 入口 | 说明 |
| --- | --- |
| `cmd/controller-manager/controller-manager.go` | Karmada 自定义 controller 管理器 |
| `cmd/scheduler/main.go` | 多集群 scheduler |
| `cmd/agent/main.go` | Pull 模式 member cluster agent |
| `cmd/aggregated-apiserver/main.go` | aggregated API server |
| `cmd/webhook/main.go` | admission webhook |
| `cmd/karmadactl/karmadactl.go` | CLI |

## Binding / Work 控制器观察

`ResourceBindingController` 负责把 `ResourceBinding` 转成 `Work`：

- 监听 `ResourceBinding`。
- 删除时清理 owned `Work`。
- 根据 binding 引用的资源读取 workload template。
- 应用 override policy。
- 调用 `ensureWork(...)` 生成或更新 per-cluster `Work`。
- 通过 events 和 metrics 记录成功 / 失败。

`execution.Controller` 负责把 `Work` 真正同步到 member cluster：

- 监听 `Work`。
- 通过 Work namespace 推导目标 cluster。
- 检查 cluster 是否 Ready。
- 支持 `SuspendDispatching`。
- 删除时根据 `PreserveResourcesOnDeletion` 决定是否保留 member cluster 资源。
- 通过 `ObjectWatcher` 对 member cluster 执行 create / update / delete。
- 回写 Work condition 和 event。

这和 AgentCube 的启发：

```text
业务资源 / 用户请求
-> 中间绑定对象
-> 面向具体执行目标的 Work / Task
-> 执行器同步到目标环境
-> status / event / metric 回写
```

AgentCube 当前已有 `Sandbox`、`SandboxClaim`、`SandboxWarmPool`，未来 SnapStart 又有 `SandboxSnapshot`、`SandboxSnapshotTask`。Karmada 的 `ResourceBinding -> Work -> execution` 可以作为理解这类多阶段控制面的成熟样本。

## 对 AgentCube 的可借鉴点

| Karmada 设计 | AgentCube 可借鉴点 |
| --- | --- |
| 原生 K8s API + policy 分离 | AgentCube 可以继续保持 `CodeInterpreter` / `AgentRuntime` 与底层 runtime policy 分离 |
| `PropagationPolicy` 选择资源，`ResourceBinding` 表示调度结果，`Work` 表示执行单元 | SnapStart 中 `SandboxSnapshot` / artifact set / `SandboxSnapshotTask` 也应清晰分层 |
| scheduler 与 controller 分离 | AgentCube 后续如果做多 runtime / 多 node / 多 cluster 调度，也应避免把所有选择逻辑塞进 Workload Manager |
| status、condition、event、metric 都非常明确 | 我们 #385 和 #366 benchmark 评论都在补这类可观测性 |
| proposal 模板包含 Summary、Motivation、Goals、Non-Goals、Proposal、Design Details、Test Plan、Alternatives | AgentCube 提 proposal 时可直接参考这个结构，尤其补 Test Plan |
| `PreserveResourcesOnDeletion`、failover、graceful eviction | AgentCube session / sandbox 删除和失败恢复也需要类似的资源保留与清理语义 |
| `karmada-agent` 支持 Pull 模式 member cluster | AgentCube 如果未来跨集群管理 sandbox，也可以参考 push / pull 两种连接模式 |
| scheduler-estimator | AgentCube 做 warm pool / sandbox capacity 调度时，需要真实可用容量而不只是节点总资源 |

## 和 AgentCube 的差异

| 维度 | Karmada | AgentCube |
| --- | --- | --- |
| 主要对象 | 多集群 Kubernetes workload | AI Agent runtime / sandbox session |
| 调度目标 | member Kubernetes clusters | sandbox / runtime / node / future cluster |
| 工作负载生命周期 | 相对长生命周期应用 | 短生命周期、高频创建销毁、交互式 session |
| 性能关注 | 多集群资源分布、failover、status aggregation | cold start、warm pool、snapshot restore、agent execution latency |
| 安全隔离 | 依赖 member cluster / workload 安全边界 | 依赖 Pod、gVisor/Kata/Kuasar/MicroVM 等 sandbox backend |

所以 Karmada 不是 AgentCube 的竞品，而是一个成熟 Kubernetes-native 控制面参考项目。

## 今日结论

Karmada 值得 Day13 学习的重点不是“多集群本身”，而是它把复杂分布式控制面拆成了清晰的 Kubernetes API 层次：

```text
user-facing resource
-> policy
-> binding / scheduling result
-> executable work item
-> target runtime / cluster execution
-> status / event / metric feedback
```

这个模式和 AgentCube 的发展方向高度相关。AgentCube 如果继续做 SnapStart、warm pool、runtime backend、甚至未来跨集群 sandbox 调度，就需要类似的资源分层、状态语义和测试计划。

## 学习感悟：为什么是组件式开发

Karmada 采用组件式开发，不是为了把项目拆得更复杂，而是因为它本质上是一个 Kubernetes 控制面项目。控制面要同时处理 API 接入、策略校验、调度决策、控制循环、跨集群执行、状态聚合、命令行工具和可观测性，如果全部塞进一个进程，职责会很快混在一起，后续测试、扩展和排障都会变困难。

Kubernetes 自身也是这种模式：`kube-apiserver` 负责 API，`kube-scheduler` 负责调度，`kube-controller-manager` 负责控制循环，`kubelet` 负责节点执行。Karmada 复用了这套思想，把多集群场景拆成 `karmada-apiserver`、`karmada-controller-manager`、`karmada-scheduler`、`karmada-agent`、`karmada-webhook`、`karmada-search` 等组件。每个组件只对自己的阶段负责，中间通过 Kubernetes API 对象和 status 连接起来。

这种拆分的实际价值有几个：

- 不同职责可以独立开发和测试，例如 scheduler 只关心集群选择，execution controller 只关心把 `Work` 下发到 member cluster。
- 不同组件可以独立扩缩容和部署，API、调度、状态聚合、agent 同步的资源压力不一样。
- 故障边界更清晰，一个 member cluster agent 出问题，不应该直接拖垮整个 control plane。
- 社区协作更容易，开发者可以围绕某个 controller、API 或 scheduler feature 提 issue / PR，不必一次理解整个系统。
- 新能力可以渐进加入，例如 estimator、descheduler、search 都可以作为独立组件演进。

对 AgentCube 的启发是：随着功能从本地 sandbox 扩展到 warm pool、SnapStart、runtime backend、node agent、Kubernetes 调度和未来多集群，不能只依赖一个 Workload Manager 承担所有职责。更合理的方向是继续明确 `router`、`workload-manager`、runtime controller、snapshot controller、node agent / runtime driver、metrics / status 等边界，让每个组件围绕一个稳定 API 或 CRD 工作。

## 后续可继续读

1. 深读 Karmada scheduler：cluster filtering、scoring、replica division。
2. 深读 `Work` status aggregation：如何把 member cluster 状态回写到 control plane。
3. 阅读 Karmada proposal 模板和 1-2 个已完成 proposal，用来改进 AgentCube proposal 写法。
4. 对照 AgentCube：画 `CodeInterpreter -> SandboxTemplate -> SandboxSnapshot/SandboxClaim -> Sandbox/SandboxSnapshotTask` 的资源链路。
5. 评估是否值得把 AgentCube benchmark / proposal 文档补成 Karmada/Kubernetes 风格的 `Test Plan`。
