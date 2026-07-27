# Day 56：sandbox-operator 与 agent-sandbox-platform 调研——是不是新瓶装旧酒

日期：2026-07-27

## 调研问题

本次调研回答三个问题：

1. [`cocoonstack/sandbox-operator`](https://github.com/cocoonstack/sandbox-operator) 到底实现了什么，`PERFORMANCE.md` 中的性能数字测的又是什么？
2. [`geminixiang/agent-sandbox-platform`](https://github.com/geminixiang/agent-sandbox-platform) 是新的 sandbox runtime，还是 `kubernetes-sigs/agent-sandbox` 之上的产品控制面？
3. 它们相对 Day5、Day8、Day11、Day12 的最早调研，以及 Day21、Day28、Day35 的后续架构判断，究竟增加了什么？

## 一句话结论

> 两个项目都没有发明新的 sandbox 基础原语，但不能一概说成没有价值的换皮。`sandbox-operator` 的传统 CRD / warm-pool 路径属于旧酒，它把 aggregated API、`NodeInventory` 和 node-local `sandboxd` claim 组合成“不为每个 sandbox 写 etcd”的事务路径，属于实质工程增量；`agent-sandbox-platform` 不提供新的 runtime 或加速原语，主要是在 `agent-sandbox` 上补 Lease、租户隔离、HTTP SDK、workspace 和部署体验，因而更接近“有价值的产品化新瓶”。

更重要的结论是：Day56 没有推翻最早调研，反而验证了当时的分层判断。竞争仍然发生在三层：

- 底层隔离与恢复：container、gVisor、Kata、Firecracker、Cloud Hypervisor、snapshot / CoW；
- 中层生命周期与容量：CRD、warm pool、claim、node-local placement、pause / resume、cleanup；
- 上层产品接口：Lease、tenant、Router、REST / SDK、commands、files、E2B facade。

## 结论分级

| 项目 | 底层原语新颖性 | 系统边界增量 | 工程与验证增量 | Day56 判定 |
| --- | --- | --- | --- | --- |
| `cocoonstack/sandbox-operator` | 低：warm pool、microVM、snapshot、Virtual Kubelet、aggregated API 都有先例 | **中高**：保留 Kubernetes API 表面，把 claim / release 事务下沉到 node-local `sandboxd`，不持久化每个 Sandbox | **中高但仍早期**：作者报告的大规模 live-cluster 结果、当前 Go package tests；安装闭环、对象语义、原始性能证据和 HA 仍有缺口 | **不是简单换皮；旧原语的新事务路径** |
| `geminixiang/agent-sandbox-platform` | 很低：runtime、WarmPool、Claim、gVisor 都由外部项目提供 | 中：明确 `(Consumer, Subject)`、Lease 权利、operator-owned Pool 和 SDK 边界 | 中：Go 控制面、三语言 SDK、作者侧 Colima/GKE 验收、流式文件；但单副本、无 snapshot/restore、无新调度器 | **更接近产品化新瓶，底层仍是旧酒** |

> 注释：这里的“新颖性”不是评价代码有没有价值，而是区分三种贡献：发明新原语、重新划分系统责任、把已有原语做成可运行产品。开源基础设施往往主要靠后两种贡献产生价值。

## 调研口径与证据边界

### 固定版本

| 项目 | 本轮固定提交 | 首个公开提交 | 仓库快照 |
| --- | --- | --- | --- |
| `sandbox-operator` | `0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d` | `6188e3a8`，2026-07-17 | 79 commits、2 contributors、2 merged PR、v0.1.0 当日发布 |
| `agent-sandbox-platform` | `ec01ad2a317e67fe38940882598a4b7027d71736` | `0e2415cd`，2026-07-21 | 71 commits、1 contributor、无 PR、无 release，Chart 为 0.1.0，TS SDK 为 0.2.0-rc.1 |

仓库创建时间和提交数量只是成熟度信号，不直接证明代码质量。它们说明两个项目都处于非常早的公开阶段，不能用 README 完成度代替长期升级、多人 review、故障恢复和生产运维证据。

### 本轮做了什么

- 读取两个仓库的 README、架构、API、lifecycle、benchmark、ADR、Roadmap、Helm 和关键 Go 实现；
- 通过 GitHub API 检查仓库元数据、完整 commit / PR / release 历史；
- 对 `sandbox-operator` 运行 `go test ./...`，当前提交全部通过；
- 对 `agent-sandbox-platform` 运行 `go test ./...`，当前提交全部通过；
- 先执行 `npm ci`，再运行 `npm test`，control plane、contracts、TypeScript SDK、类型检查和 local-process HTTP / SDK contract E2E 全部通过；
- 回读 Day5、Day8、Day11、Day12、Day21、Day28、Day32、Day35，避免把本地已经得出的结论重新包装成“新发现”。

### 本轮没有证明什么

- 当前机器存在 `/dev/kvm` 且暴露 VT-x，但当前用户不在 `kvm` 组、无设备读写权限；同时缺少 Cocoon / vk-sandbox / sandboxd 集群和 20 节点同构 fleet，因此没有独立复现 microVM、snapshot、node-local claim 或 50k 实验；
- 没有部署两个项目到 AgentCube 当前集群；
- 没有把作者自测数字当成独立 benchmark；
- 没有根据短期 commit 速度推断作者使用了什么开发工具；
- 没有把 GitHub stars、commit 数或文档篇幅当成生产成熟度。

## 项目一：cocoonstack/sandbox-operator

### 它不是一条路径，而是两条路径

README 容易把它读成一个统一的“超大规模 Kubernetes microVM operator”，但源码实际包含两条性质不同的路径。

| 路径 | 控制对象 | 请求关键路径 | 每 sandbox 是否写 Kubernetes 对象 | 性能数字 |
| --- | --- | --- | --- | --- |
| 传统 agent-sandbox 路径 | `Sandbox`、`SandboxTemplate`、`SandboxWarmPool`、`SandboxClaim` | API Server -> controller -> warm Sandbox adoption -> Pod / vk-cocoon | 是 | warm claim p50 约 33 ms；高并发和大 informer cache 下退化 |
| L3 aggregated path | `SandboxWarmPool` intent + 每节点 `NodeInventory` + 外部 `sandboxd` | aggregated API -> 从 inventory 选节点 -> 直接 node-local claim / release | **否**，返回合成的 `Sandbox` | L3 API 以进程内 8 个对象合成 3000 个 Sandbox；作者报告的 50k warm-pool supply 是另一个 node-local fleet 实验，不是 50k aggregated API / claim 测试 |

这两条路径共享 Kubernetes API 外观，却有不同的状态所有权和一致性语义，不能混成一个 benchmark 排名。

### 传统路径：明显继承自 agent-sandbox

项目在 [`UPSTREAM.md`](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/UPSTREAM.md) 明确记录：

- `api/`、`controllers/`、`extensions/api/`、`extensions/controllers/`、`internal/` 和 controller command 从 `kubernetes-sigs/agent-sandbox@bfcb49d` 导入；
- upstream CRD、RBAC、Helm 和 controller manifest 作为部署基线；
- 最初本地差异主要是命名、默认启用 extensions、Pod runtime mutation seam 和 Cocoon identity。

粗略统计当前 Go 源码时，声明为 imported 的目录约占 Go 行数的三分之二。这个比例不能说明对应行仍与 upstream 完全相同，但足以说明“完整 agent-sandbox API”主要来自 upstream，不应归因成该仓库从零发明。

传统 warm path 的核心仍然是：

```text
SandboxWarmPool 预建 Sandbox / Pod / microVM
  -> 请求创建 SandboxClaim
  -> controller 从 ready pool 选一个 Sandbox
  -> 通过 resourceVersion / ownership 更新完成 adoption
  -> pool 后台补位
```

这和 Day5 已经读到的 AgentCube -> `SandboxWarmPool` -> `SandboxClaim` 路径属于同一种原语。差别在于 backing Pod 可由 `vk-cocoon` materialize 为 Cloud Hypervisor / KVM microVM，而不是本地 Day5 的普通 k3s Pod。

### L3 路径：真正值得读的增量

项目最有价值的部分不是再写一个 warm-pool controller，而是把 Kubernetes 从每个 sandbox 的事务存储中移开。

```text
SandboxWarmPool desired replicas
  -> warmpool driver 按节点分发 pool target
  -> 每个 sandboxd 在节点本地维持 golden microVM pool
  -> NodeInventory 周期上报节点摘要与 sandbox entries
  -> aggregated sandbox-apiserver 接管 agents.x-k8s.io/v1beta1
  -> Create 依据 warm capacity 选择节点并直接 claim
  -> List / Get / Watch 从 NodeInventory 合成 Sandbox
  -> Delete 直接向 owning node release
```

其核心命题可以概括为：

> Kubernetes 保存 intent、policy 和 API surface；节点保存高频 sandbox truth；单次 claim 不把每个 sandbox 作为 etcd 事务。

> 注释：`record-of-intent` 表示 Kubernetes 保存“希望有多少池容量、允许什么策略”这类低频期望，而不是保存每个高频实例的全部实时状态。这样可以降低 etcd key 和 write amplification，但会引入最终一致性、节点丢失和读语义退化问题。

具体增量包括：

- aggregated APIService 继续暴露 `agents.x-k8s.io/v1beta1/Sandbox`；
- `NodeInventory` 把节点地址、pool warm 数和 live sandbox entries 汇总到每节点对象；
- node choice 使用 power-of-two choices，避免一份过时 inventory 把突发请求全部打到表面最空闲的节点；
- `Create` / `Delete` 通过 `sandboxd` claim / release，不落每-sandbox etcd key；
- pause、resume、fork、snapshot 作为 subresource 映射到 node-local lifecycle；
- e2b REST surface 翻译到同一个 `SandboxStore`，不是另起一套状态控制面。

对应实现可从 [`SandboxStore`](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/pkg/scale/sandboxstore_impl.go)、[`warmpool driver`](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/pkg/scale/warmpool/driver.go) 和 [`sandbox-apiserver`](https://github.com/cocoonstack/sandbox-operator/tree/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/pkg/scale/apiserver) 看到。

### 它和 Day35 的关系

L3 的架构方向和 Day35 的核心判断高度一致：

| Day35 | sandbox-operator L3 | 关系 |
| --- | --- | --- |
| Kubernetes 管慢资源与声明式边界 | WarmPool intent、API、RBAC 留在 Kubernetes | 同方向 |
| 高频生命周期下沉 node-local | claim / release / pause / resume / fork 直达 sandboxd | **实现性证据** |
| 每个 sandbox 不应完整走 Pod 调度路径 | pool target 先下发，节点本地供给 golden microVM | 同方向 |
| 控制面与节点状态需要 reconcile | NodeInventory + orphan reconciliation | 有部分实现 |
| run-builder + L1/L2/L3 artifact cache | 依赖外部 Cocoon/sandbox stack，operator 本身没有完整构建与缓存产品面 | Day35 更宽 |
| placeholder Pod 锁慢资源边界 | 主要通过 virtual-kubelet / external runtime fleet，不是 Day35 placeholder Pod 模型 | 实现路线不同 |

按照公开时间线，Day35 报告早于这两个仓库的首个公开 commit。这个事实只能说明双方独立收敛到相近架构，不能推断任何一方影响或复制另一方。

### 性能数字应怎样读

项目的 [`PERFORMANCE.md`](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/PERFORMANCE.md) 有真实价值，因为它主动披露了不少反例和边界；但 headline 仍必须分层。

#### 33 ms 不是 microVM 启动

| 数字 | 实际动作 | 是否从停止状态恢复内存 | 是否包含 cold boot |
| --- | --- | --- | --- |
| 33 ms p50 | 已启动 warm microVM 的 Kubernetes ownership adoption | 否 | 否 |
| sandboxd 0.2-0.7 ms | 外部 Cocoon stack 作者报告的节点本地已启动 VM ownership transfer | 否 | 否 |
| Cocoon clone 45-75 ms | 外部 Cocoon stack 作者报告的 snapshot clone / resume | 是 | 否 |
| operator cold boot 26-32 s | 完整 OCI microVM boot | 否 | **是** |
| E2B 约 150 ms | `sandbox-operator` 引用的 vendor headline，未固定原始 benchmark | 文档将其归为 snapshot / resume | 否 |

因此，“33 ms 比 E2B 150 ms 快”不是同层比较。`sandbox-operator` 文档把前者标为 warm claim、后者标为 snapshot / resume；但约 150 ms 没有固定原始 benchmark，不能作为当前 E2B 性能事实。本报告只用它说明两种操作不能混排，不接受“microVM 启动快 4.5 倍”的结论。

本轮核对时，[E2B 首页](https://e2b.dev/) 同时出现同区域启动低于 200 ms 和 80 ms 的产品文案，而 [Persistence 文档](https://e2b.dev/docs/sandbox/persistence) 把 paused sandbox resume 写为约 1 s。三者不是稳定的同一指标，进一步说明不能把约 150 ms 当成当前、统一、可复现的 E2B resume baseline。

#### 33 ms 也不是任意并发下都成立

作者数据已经显示：

| pool / concurrency | p50 | p95 | 说明 |
| --- | ---: | ---: | --- |
| pool 200 / c1 | 33 ms | 39 ms | 最适合 headline 的串行 warm hit |
| pool 200 / c5 | 53 ms | 183 ms | 开始出现争用 |
| pool 200 / c20 | 316 ms | 454 ms | claim 与补位同时放大控制面事件 |
| pool 约 2300 / c1 | 516 ms | 554 ms | API list + informer cache 成为瓶颈 |

这和 Day5 `warmPoolSize=2` 在并发 10 下 p50 7.3 s 的结论并不冲突。两者共同说明：warm-hit 单点数字不是平台容量，必须同时记录 pool size、warm hit、replenishment、并发和控制面事件放大。

#### 50k 是 fleet fill，不是 50k 用户 ready-to-exec

50k headline 的实验是：

- 20 台同构 bare-metal node；
- 每台 384 vCPU / 1.5 TiB RAM / 本地 NVMe；
- 一次把 WarmPool target 从 0 patch 到 50,000；
- 节点从本地 golden snapshot 批量恢复 microVM；
- 通过 node telemetry 与 CR status 观察 10-15 s / 15.7 s fill；
- 每 VM 约 99 MB net RAM；
- 因为 Sandbox 是合成对象，etcd 主要保存 node inventory，约 2 writes/s。

作者结果支持的是“在特定大机器 fleet 上，节点本地 snapshot supply 可以横向扩展，且不为每个 VM 写 etcd”。它没有证明：

- 50k 个独立用户同时完成 auth、claim、network、envd / PicoD ready、exec；
- 任意镜像或任意 snapshot 都能保持相同恢复率；
- 50k 个 sandbox 的读、watch、生命周期请求能保持相同延迟；
- 1M sandbox 已经实测。文档中的 1M / 25 s 是线性外推，Roadmap 仍把 million-sandbox validation 列为后续。

> 分析：这个实验最有价值的不是“50k”三个字符，而是它把扩展公式拆成 node-local supply rate 与 O(nodes) control-plane overhead。对 AgentCube 真正可借鉴的是状态模型和事务路径，而不是直接复用 headline。

#### L3 API benchmark 与 50k fleet 是两组实验

L3 自己的 contract / complexity 证据是：用 3 个 node inventory 和 5 个 pool 共 8 个对象，通过 client-go List / Get / Watch 合成 3000 个 Sandbox。[`test/l3bench`](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/test/l3bench/main.go) 明确在进程内运行，没有真实 etcd、cluster、TLS 或 microVM。

所以这组测试能验证 aggregated API 的对象合成路径和“无 per-sandbox object”的数据模型，不能证明 50k Sandbox API、50k 并发 claim 或生产网络下的延迟。前述 50k 数字只属于 node-local warm-pool supply 的作者侧 live-fleet 实验。

### 当前实现的关键缺口

#### 合成 Sandbox 不是完整 CRD 对象语义

[`entryToSandbox`](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/pkg/scale/sandboxstore_impl.go#L583-L633) 主要重建：

- namespace / name；
- owning node；
- phase / ready condition；
- claim id / address；
- 合成 resourceVersion。

它没有持久保存用户提交的完整 spec、UID、creationTimestamp、任意 labels / annotations。NodeInventory 延迟发布时，create 后立即 Get 可在约 30 s 内返回 404；当某个 NodeInventory 对象丢失或读取失败时，List 会跳过对应 inventory。仓内没有证明真实 node partition 必然触发该条件，生产读取缓存中的既有 NodeInventory 也可能继续暴露陈旧视图。Watch 当前通过周期性全量重算和 diff 实现，不是 merged per-node event stream。

所以准确口径是：

> 它保留了 Kubernetes discovery、RBAC 和 `kubectl get` 的大部分表面，但没有保留传统持久 CRD 的全部对象语义。

#### O(nodes) 只适用于 key / write 数，不适用于全部字节

每个节点只有一个 `NodeInventory` key，但该对象的 `entries` 仍包含节点上的所有 sandbox。于是：

- etcd key 数从 O(sandboxes) 降为 O(nodes + pools)；
- publish 次数也可按节点慢速进行；
- 单个 inventory payload、合成 List 的 CPU / 内存和网络字节仍随 sandbox 数增长；
- NodeInventory 变大后还要面对 Kubernetes object size、SSA、watch payload 和热点更新边界。

这比每 sandbox 多个 CR / Pod 写入强很多，但不能简化成“整个状态复杂度已从 O(sandboxes) 变成 O(nodes)”。

#### 发布与安装链路还未闭环

- `NodeInventoryPublisher` 在当前仓库 production command 中没有调用点，主要出现在 library 与 test；生产发布链路依赖外部 `vk-sandbox` / `sandboxd` stack；
- 默认 Helm / Kustomize 主要安装传统 operator、CRD 和 extensions，没有把 aggregated apiserver、APIService、sandboxd 与 vk-sandbox 组合成 README 同等级的一键安装路径；
- 文档存在漂移：`docs/index.md` 仍称 L2/L3 为 skeleton，`docs/e2b-compat.md` 仍称 pause / fork / snapshot 未实现，但当前源码已经注册对应 endpoints；
- `docs/scaling-design.md` 引用的 `test/run100` 不在仓库中；
- Roadmap 仍列出 L2 authorization / quota hardening、aggregated API HA、merged watch stream、prompt release、durable checkpoint 与 million-scale validation。

### 对 sandbox-operator 的最终判断

它不是“一个新 operator 就发明了新 sandbox”。传统路径大部分是上游 agent-sandbox 与外部 Cocoon runtime 的组合。

但它也不是无意义换皮。L3 具体实现了一个 Day35 只在设计层描述的关键方向：

> 在保留 Kubernetes API facade 的同时，把高频 sandbox transaction 和 source of truth 移到节点侧。

当前最适合的成熟度标签是：

> **强技术原型 / 有作者侧规模实验记录 / 尚未形成可独立安装和长期运维验证的生产平台。**

## 项目二：geminixiang/agent-sandbox-platform

### 它明确不是 sandbox runtime

项目 README 对责任边界写得很清楚：

```text
Consumer
  -> Python / TypeScript / Go SDK
  -> HTTP control plane
  -> Kubernetes backend
  -> kubernetes-sigs/agent-sandbox SandboxClaim / WarmPool
  -> Pod + selected RuntimeClass, currently gVisor reference path
```

Helm 文档进一步说明：Chart 不安装 agent-sandbox controller 或 runtime。目标集群必须预先具备：

- agent-sandbox v0.5.2 CRD / controller / extensions；
- Pool 引用的 RuntimeClass；
- 可运行该 RuntimeClass 的节点；
- StorageClass；
- control-plane image。

因此它不应与 forkd、CubeSandbox 或 Cocoon 的 VMM / snapshot 性能放在同一层。它是一个 product control plane。

### 它真正增加了什么

项目最明确的产品抽象是 Lease：消费者获得临时使用权，而不是拥有 Pod、VM、Sandbox 或 Claim。

| 增量 | 当前实现 |
| --- | --- |
| tenant scope | 每次请求从短期 Subject token 推导 `(Consumer, Subject)` |
| 防枚举 | 跨 scope 访问与不存在的 Lease 返回相同外观 |
| logical Pool | SDK 只选择 `coding` / `browser` 等逻辑池，image、RuntimeClass、network、scheduling 由 operator 管理 |
| idempotency | scope-aware idempotency key，重试不重复 claim |
| lifecycle | acquire、get/connect、list/cursor、release、delete、expiry cleanup、restart recovery |
| execution | Kubernetes SPDY Pod exec，前台 command result 与 typed error |
| workspace | `/workspace` 路径限制、PVC、流式 upload / download、digest、大小与并发限制 |
| SDK | async-first Python、零 runtime dependency TypeScript、standard-library-only Go |
| deployment | Colima + k3s + gVisor golden path、Helm、GKE acceptance evidence |

> 注释：Lease 抽象的价值在于把“谁有权临时使用某个运行环境”与“底层资源叫什么、在哪个 Pod、由谁回收”分开。它不是更快的 VM 原语，但能显著改善多租户 API 的安全和生命周期一致性。

### 它与 AgentCube 的重叠

| agent-sandbox-platform | AgentCube 当前 / 已设计边界 | 判断 |
| --- | --- | --- |
| HTTP control plane | WorkloadManager | 高度重叠 |
| logical Pool -> WarmPool mapping | CodeInterpreter / SandboxTemplate / SandboxWarmPool | 高度重叠 |
| Lease ID -> Claim / Sandbox | session -> SandboxClaim / Sandbox / Store | 同类 identity mapping |
| SDK create / run / files / release | Python SDK + PicoD / Router | 同类开发者路径 |
| restart recovery | Store / Kubernetes object recovery | 同类控制面要求 |
| `(Consumer, Subject)` scope | AgentCube user/session identity、JWT / mTLS 讨论 | **该项目的边界表达更直接** |
| list / reconnect / idempotency | Day32 Session contract / Store CAS 方向 | 已在本地设计中出现，该项目有可运行实现 |
| gVisor RuntimeClass Pool | AgentCube RuntimeProvider / agent-sandbox | provider 选择，不是新 runtime |

它最值得 AgentCube 学习的不是“再建一个 control plane”，而是三件更窄的事：

1. 把 consumer、subject、lease、underlying runtime identity 分开；
2. 每个 lookup 都以 `(scope, leaseID)` 为键，possession of ID 不等于 authorization；
3. Pool policy 归 operator，SDK 不暴露 Kubernetes image、RuntimeClass、network policy 等基础设施细节。

### 性能证据怎样读

项目的 [Colima baseline](https://github.com/geminixiang/agent-sandbox-platform/blob/ec01ad2a317e67fe38940882598a4b7027d71736/docs/benchmarks/colima-2026-07-22.md) 使用：

- 2 vCPU / 4 GiB 的单节点 arm64 Colima；
- k3s + gVisor；
- agent-sandbox v0.5.2；
- coding / browser 各 1 个 ready WarmPool replica；
- clean-installed Python wheel -> Go control plane -> agent-sandbox -> Pod / gVisor 的完整公共路径。

关键结果：

| 场景 | samples | p50 | 解释 |
| --- | ---: | ---: | --- |
| warm acquire | 每个 Pool 10 | 约 526-527 ms | agent-sandbox warm claim + HTTP control plane |
| concurrency 2 | 每个 Pool 3 | 约 1.045 s | 只有 1 个 warm replica，第二个请求进入补位 / 资源争用 |
| concurrency 4 | 每个 Pool 3 | 约 2.21-2.22 s | 单节点、单 warm replica 下近似串行放大 |
| warm-pool replenishment | 每个 Pool 10 | 约 3.46-3.52 s | release 后重新达到 desired ready |
| foreground exec / common file ops | 每个 series 10 | 多数约 0.4-0.5 s | 包含 HTTP + control plane + SPDY exec |
| Chromium launch | 10 | 337 ms | sandbox 内部 workload milestone，不等同 acquisition |

这几乎重现了 Day5 的核心结论：

> warm pool 的性能取决于 hit ratio 与 replenishment；单个 warm-hit 数字不能代表突发容量。

项目的 [32 MiB streaming report](https://github.com/geminixiang/agent-sandbox-platform/blob/ec01ad2a317e67fe38940882598a4b7027d71736/docs/benchmarks/colima-streaming-2026-07-22.md) 更有产品工程价值：它验证了 chunking、SHA-256、atomic replacement、early close、release-during-upload、cross-subject isolation、symlink escape 与 cleanup。它证明的是 workspace data path，而不是新 sandbox 启动原语。

### 当前成熟度与缺口

项目自己明确限制：

- exactly one control-plane replica；
- production Go backend 用进程内 mutex 串行 acquire，但 admission quota 尚未实现；
- multi-replica acquisition、idempotency 与 quota distributed coordination 尚未实现；
- billing、restore、direct Firecracker、multi-cluster placement 不在当前范围；
- pause / resume、snapshot / fork、完整 E2B parity 尚未实现；
- command supervisor 和 workload router 仍是 prototype，并明确不能当 production support；
- 所有 Claim 当前仍在一个 namespace，认证主要是 HMAC consumer secret -> short-lived subject token；OIDC、secret rotation、audit 和组织 / 项目治理尚未完成；
- `CHANGELOG.md` 与 `docs/architecture.md` 仍描述 single-replica quota，但 README 和当前 Go backend 已显示该能力不存在，属于文档漂移；
- 没有正式 release，公开历史只有数天且主要由单作者提交。

它也有比“README 原型”更强的信号：

- root Go test 当前全部通过；
- npm workspace test / TypeScript type test / local-process HTTP / SDK contract E2E 当前全部通过；
- 仓库记录了 Colima 和 GKE 的 real-environment acceptance；
- negative tests 覆盖 cross-subject、cross-consumer、path escape、stream interruption、cleanup；
- Helm 强制单副本，而不是在缺乏 distributed lock 时假装 HA。

当前最合适的成熟度标签是：

> **边界清楚、测试认真、可试用的单副本产品原型；不是新的 sandbox substrate，也不是已经完成的多租户生产平台。**

## 和最开始调研相比，究竟有什么区别

### Day5：当时已经知道的核心事实

Day5 已经确认：

- AgentCube 的优化原语是 `SandboxWarmPool` + `SandboxClaim` adoption；
- warm hit 可到 100 ms 级，但 pool size 2 面对并发 10 会排队到秒级；
- forkd 是 snapshot + CoW fan-out；
- CubeSandbox 是 KVM runtime + pool + snapshot + E2B；
- cage-bro 是 shared-kernel tool runtime，不能与 microVM 数字直接比较；
- AgentCube 应定位为 Kubernetes-native orchestration，而不是重复实现单机 VMM；
- benchmark 必须拆 control plane、claim、runtime ready、Router、exec 与 cleanup。

所以 Day56 看到下面这些词，并不构成新发现：

```text
Operator / CRD / Sandbox / WarmPool / Claim
microVM / snapshot / CoW / E2B
SDK / API / Router / command / files
RuntimeClass / gVisor / Kubernetes-native
```

### Day8：当时已经建立了正确比较口径

Day8 已经要求按以下维度比较：

- isolation boundary；
- control / scheduling unit；
- Kubernetes relationship；
- SDK / API；
- snapshot 与 memory semantics；
- host OS、kernel、glibc、`/dev/kvm`；
- cold / warm / pool hit / miss / concurrency；
- 官方数据与本地实测分开。

Day56 的性能审计没有换口径，只是把它应用到两个新仓库：

- 33 ms warm ownership transfer 不能与 `sandbox-operator` 引用、但未固定原始 benchmark 的 E2B 约 150 ms snapshot / resume headline 混排；
- 50k fleet fill 不能与 50k ready-to-exec 用户请求混排；
- Colima 2 vCPU / 4 GiB 的核心 series 各 10 个样本、并发 series 各 3 个样本；这些单节点小样本不能外推到多节点 SLO。

### Day11 / Day12：完整 platform 形态早已出现

Day11 对 CubeSandbox 已拆过：

- API / Master / scheduler / proxy；
- node agent / shim / hypervisor；
- Template / Snapshot / Clone / Rollback；
- SDK / E2B；
- eBPF network、egress、安全与审计；
- 多节点与 Web UI。

Day12 也已经得出：“AgentCube 不应重造 VMM，而应管理不同 runtime backend，并补 benchmark、observability、SDK 和 production governance。”

因此 `agent-sandbox-platform` 的 SDK + HTTP + Pool + gVisor 不是新类别；它的增量是把 Lease / tenant / workspace contract 做成了一个较小且可测试的实现。

### Day21 / Day28：控制面和状态面也不是新词

Day21 的 OpenSandbox 已包含 SDK / API-first platform、Kubernetes operator、Pool / Snapshot、provider adapter、Ingress / Egress 与执行面。

Day21 / Day28 的 Agent Substrate 调研已包含：

- 低频配置放 CRD，高频 Actor / Worker state 放 Redis / ValKey；
- Router 在 proxy 前 resume；
- WorkerPool 与 runtime identity 分离；
- golden snapshot 与 latest state 分离；
- RuntimeProvider boundary；
- lifecycle 中间态、失败补偿与 endpoint refresh。

因此，“Kubernetes 不是所有高频状态的 source of truth”在 Day56 之前也已经明确。

### Day35：Day56 真正新增的是实现性参照

Day35 的主线是：

```text
Kubernetes = slow resource / policy boundary
node-local runtime = fast sandbox lifecycle
run-builder + cache = artifact data path
E2B facade = developer API surface
```

两个 Day56 项目分别命中了这张图的不同部分：

| Day35 层 | sandbox-operator | agent-sandbox-platform |
| --- | --- | --- |
| 接入 / E2B facade | 有 Kubernetes API + 部分 e2b REST | 有自定义 Lease HTTP + 三语言 SDK，不是 E2B wire compatible |
| cluster control plane | operator + aggregated apiserver | Go control plane + logical Pool mapping |
| node-local lifecycle | **外部 sandboxd / vk-sandbox，有源码级实现与作者侧验收记录** | 无，继续依赖 agent-sandbox -> Pod |
| microVM / isolation | 外部 Cocoon / CH / Firecracker stack | gVisor RuntimeClass reference path |
| template / snapshot | node-local checkpoint / fork，durability 未完成 | operator-defined image Pool，无 snapshot |
| artifact cache | 依赖外部 substrate，operator 内不完整 | 无独立 cache architecture |
| tenant / SDK product layer | e2b API key 较薄 | **Lease / `(Consumer, Subject)` 更完整** |
| scale data model | **NodeInventory + synthesized Sandbox** | 仍是 per-Claim / per-Sandbox Kubernetes objects |

这意味着 Day56 的新增价值不是“重新发现了一个方向”，而是获得两个独立实现参照：

- 一个为 node-local transaction path 藏在 Kubernetes API facade 后面提供源码级实现参照和分层 benchmark；
- 一个提供 Lease / tenant / SDK 作为 agent-sandbox 独立产品层的可运行参照。

## “新瓶装旧酒”最终判定表

| 能力 | 最早报告是否已有 | sandbox-operator | agent-sandbox-platform | 判定 |
| --- | --- | --- | --- | --- |
| CRD / Operator | Day5 | 大量来自 upstream agent-sandbox | 依赖外部 agent-sandbox | 旧酒 |
| WarmPool / Claim adoption | Day5 | 传统路径同类；L3 改为 node claim | 直接映射 WarmPool / Claim | 旧酒 |
| microVM isolation | Day5 / Day8 / Day11 | 由 Cocoon / vk-cocoon / sandboxd 提供 | 无，参考 gVisor | operator 本身不是新 VMM |
| snapshot / CoW / fork | Day5 / Day11 | 外部 runtime 提供并映射 lifecycle | 未实现 | 旧原语，前者有集成增量 |
| SDK / HTTP facade | Day11 / Day21 / Day33 | e2b translation layer | 三语言 Lease SDK | 产品化增量 |
| tenant-aware Lease | Day24 / Day32 有 lifecycle / identity 方向 | e2b API key 较薄 | `(Consumer, Subject)` 实现明确 | 后者的实质产品增量 |
| 高频状态绕开 K8s | Day21 / Day28 / Day35 | **L3 已实现源码关键路径，部署闭环未证** | 否 | 前者的实质架构增量 |
| O(nodes) intent storage | Day35 方向有、细节未落 | **NodeInventory / aggregated API** | 否 | Day56 最重要的新实现参照 |
| placeholder Pod / resource anchor | Day35 / Day36 | 不是该模型 | 无 | 两者都没有覆盖 |
| run-builder / artifact cache | Day35 | 主要在外部 stack | 无 | 两者都未完整覆盖 |
| 可复现性能方法 | Day5 / Day8 已要求 | 有 harness 和环境，50k raw evidence 不完整 | 小规模报告、环境与限制较完整 | 工程证据增量，不是原语创新 |

## 对 AgentCube 的直接启发

### 1. 不需要因为新项目出现就推翻 Day35

Day35 的快慢资源分离仍然成立。`sandbox-operator` 提供了同方向的独立源码实现参照，但部署闭环和生产语义仍待验证。当前更合理的动作是收紧 AgentCube 自己的 contract，而不是追着两个仓库复制目录和组件名。

### 2. SandboxPool proposal 必须回答状态复杂度

如果未来目标是 10k、50k 甚至更高密度，不能只问 controller 能否创建这么多 sandbox，还要问：

- API Server 中是 O(sandboxes) 个对象，还是 O(nodes + pools) 个 intent / summary 对象？
- 每次状态变化写几个对象、多少字节？
- List / Get / Watch 是强一致、cache view、node-authoritative 还是合成视图？
- 单节点 inventory 是否会超过 Kubernetes object size 或 watch payload 边界？
- 一个 node partition 后，用户看到 NotFound、Unknown、Stale 还是 Degraded？
- create 成功后，read-after-write contract 是什么？

### 3. 不应照抄 NodeInventory entries 设计

这个设计降低了 key / write 数，却把每 sandbox entry 塞进单个 CR。AgentCube Day36 已倾向 `status` 只保留聚合值，不保存完整实例列表，这个边界更稳。

可借鉴的是“节点权威 + 集群摘要”，不一定是“把所有实例压成一个大 CR”。候选实现可以是：

- bounded summary CR + node RPC；
- Lease / heartbeat 只报告 generation、watermark、capacity；
- 分片 inventory；
- 独立状态存储 + Kubernetes intent；
- aggregated API 只作 facade，不假装完整 CRD persistence。

### 4. Lease identity 可以直接反哺 Router / Store 设计

`agent-sandbox-platform` 的 `(Consumer, Subject, LeaseID)` 比“拿到 session ID 就有权访问”更清晰。AgentCube 后续可把身份矩阵固定为：

| identity | 责任 |
| --- | --- |
| user / subject | 最终用户身份与授权主体 |
| workload / consumer | 哪个 Agent 产品或集成发起请求 |
| session / lease | 对某个 sandbox 的临时使用权 |
| runtime handle | Pod、Sandbox、VM、slot、claim 等可变化位置 |
| route generation | 防止旧 endpoint / old incarnation 被继续使用 |

这也能连接 Day54 的 Router -> PicoD mTLS / JWT 讨论：证书只证明组件身份，session / subject 仍要在应用层绑定。

### 5. benchmark schema 继续坚持分层

以后看到任何“X ms 启动”或“N 万 sandbox”先填：

| 字段 | 必须回答 |
| --- | --- |
| operation | create、claim、resume、fork、ready-to-exec、first exec 中哪个？ |
| precondition | VM / Pod 是否已启动？image / snapshot 是否已在本地？ |
| isolation | process、container、gVisor、Kata、microVM 中哪个？ |
| state | 是否保留内存、filesystem、workspace、network identity？ |
| path | 是否经过 SDK、auth、Router、API Server、scheduler、runtime agent？ |
| capacity | pool size、hit ratio、miss、replenishment 与 queue 是什么？ |
| scale | node 数、每节点资源、对象数、payload bytes、control-plane writes？ |
| statistics | sample count、p50/p95/p99、error、cleanup residue？ |

### 6. 近期可执行判断

| 方向 | 是否值得立刻做 | 原因 |
| --- | --- | --- |
| 复制 sandbox-operator controller | 否 | AgentCube 已依赖 agent-sandbox，重复 ownership controller 价值低 |
| 复制其 50k headline | 否 | 环境不可复现，且指标不是 ready-to-exec |
| 深入 aggregated API / NodeInventory contract | **是，作为 SandboxPool review 参照** | 能逼出 source-of-truth、read-after-write、payload 和 failure semantics |
| 复制 agent-sandbox-platform HTTP API | 否 | WorkloadManager / SDK 已存在，容易形成第二套 control plane |
| 吸收 Lease / tenant lookup invariants | **是** | 可直接强化 Store / Router auth 与 reconnect contract |
| 建立同一 benchmark schema | **是** | 能公平比较 agent-sandbox、node-local runtime、OpenSandbox、Substrate 与未来 provider |
| 立即发 upstream issue / PR | 否 | 本轮只有竞品研究，没有形成已证明且无人认领的 AgentCube bug |

## 本轮被排除的误判

1. **“33 ms 就是 microVM 冷启动。”** 错。它是已启动 VM 的 warm ownership transfer。
2. **“33 ms 已证明比 E2B 150 ms 强。”** 错。一个是 warm claim，另一个只是目标仓库引用但未固定原始 benchmark 的 snapshot / resume headline；既不同口径，也不是当前 E2B 性能事实。
3. **“50k 表示 50k 用户在 15 秒内可执行命令。”** 错。它是 pool fill / supply 实验。
4. **“O(nodes) 表示总状态量与 sandbox 数无关。”** 错。key / write 次数可降，inventory payload 与合成计算仍随实例数增长。
5. **“agent-sandbox-platform 是新的 sandbox runtime。”** 错。它明确要求预装 agent-sandbox 和 RuntimeClass。
6. **“有三语言 SDK 就是 E2B compatible。”** 错。该项目自己也承认 API 不是 source-compatible 或 wire-compatible，pause、snapshot、port、PTY 等仍缺。
7. **“项目很新，所以代码只是 PPT。”** 也错。两个仓库当前单测都能通过，且仓库记录了作者侧真实环境验收或 benchmark；正确结论是工程实现存在，但长期成熟度尚未建立。

## 本轮验证结果

| 项目 | 命令 | 结果 | 证明范围 |
| --- | --- | --- | --- |
| sandbox-operator | `go test ./...` | PASS | 当前 Go 单元 / package tests 可编译通过；不证明真实 microVM 或 50k 数据 |
| agent-sandbox-platform | `go test ./...` | PASS | Go control plane、backend、router、supervisor 单元测试通过 |
| agent-sandbox-platform | `npm ci && npm test` | PASS | Node control plane、contracts、TS SDK、type tests 与 local-process HTTP / SDK contract E2E 通过；后者使用 `ProcessLeaseBackend`，不是 Kubernetes E2E |

`sandbox-operator` 的 `go.mod` 要求 Go 1.26.5；本轮仍使用 plain `go test ./...`，Go toolchain 自动下载并使用 1.26.5，而不是通过手工 `PATH` 覆盖系统 Go 1.26.4。

第一次直接运行 `npm test` 时因为浅克隆后尚未安装依赖，出现 `@kubernetes/client-node`、workspace package 和 `tsc` 找不到；执行仓库正常前置步骤 `npm ci` 后，完整 npm 测试通过。这是本地测试环境缺依赖，不是项目代码失败。

> 注释：本轮没有运行 Python SDK 的 `uv` test，也没有运行需要真实 Kubernetes / gVisor / KVM 的 E2E。报告不能把 unit pass 写成 full-stack pass。

## 最终回答：是不是新瓶装旧酒

### 对 sandbox-operator

答案是：**一半是，一半不是。**

- agent-sandbox CRD、controller、warm pool、claim、microVM backend 和 snapshot 原语不是新的；
- 33 ms warm claim 也只是把既有预热路径做得更薄；
- 但 aggregated API + NodeInventory + direct node claim / release 确实改变了每请求事务路径和状态所有权；
- 它是 Day35 node-local fast path 的具体实现参照，不只是换名字；
- 目前仍是 v0.1.0 早期技术原型，不能直接当作生产级 50k 结论。

### 对 agent-sandbox-platform

答案是：**更接近“新瓶装旧酒”，但这个瓶子有工程价值。**

- 它不实现新的 runtime、snapshot、scheduler 或 microVM；
- 核心资源仍是 agent-sandbox WarmPool / Claim / Pod；
- 新增价值在 Lease、tenant isolation、idempotency、workspace streaming、三语言 SDK 和部署边界；
- 这些解决的是产品接入与安全合同，而不是 sandbox acceleration；
- 它和早期 AgentCube / Day32 Session control plane 高度同类，当前实现规模反而可以作为 contract 参照。

### 对最开始调研

最开始的结论仍然有效，只是今天能说得更精确：

> Day5 主要回答“底层隔离和启动原语有什么不同”；Day56 进一步回答“谁拥有高频状态、一次请求是否必须写 Kubernetes、以及产品 API 如何隐藏 runtime”。新项目没有改变 sandbox 的基本物理原理，它们分别把 node-local transaction plane 和 tenant Lease product plane 做成了更具体的实现。

因此，这次调研最重要的收获不是再收集两个项目名，而是把 AgentCube 的差异化标准收紧为：

1. 是否把 slow resource control 与 fast sandbox lifecycle 真正分开；
2. 是否明确 session / lease、runtime handle、route generation 和 source of truth；
3. 是否用同口径 benchmark 证明 ready-to-exec、并发、恢复和 cleanup；
4. 是否保留 Kubernetes 的策略与生态价值，而不伪装成完整的持久对象语义；
5. 是否把 SDK / E2B facade 当成产品层，而不是拿一层 wrapper 冒充 runtime 创新。

## 主要资料

### sandbox-operator

- [README，固定提交](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/README.md)
- [Performance，固定提交](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/PERFORMANCE.md)
- [Scaling design，固定提交](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/docs/scaling-design.md)
- [Upstream provenance，固定提交](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/UPSTREAM.md)
- [Lifecycle，固定提交](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/docs/lifecycle.md)
- [Roadmap，固定提交](https://github.com/cocoonstack/sandbox-operator/blob/0ef7022fc613e14a31d0c5cf9b375fa4b738bc7d/ROADMAP.md)
- [PR #2 performance review round](https://github.com/cocoonstack/sandbox-operator/pull/2)
- [v0.1.0 release](https://github.com/cocoonstack/sandbox-operator/releases/tag/v0.1.0)

### agent-sandbox-platform

- [README，固定提交](https://github.com/geminixiang/agent-sandbox-platform/blob/ec01ad2a317e67fe38940882598a4b7027d71736/README.md)
- [Architecture，固定提交](https://github.com/geminixiang/agent-sandbox-platform/blob/ec01ad2a317e67fe38940882598a4b7027d71736/docs/architecture.md)
- [Kubernetes backend，固定提交](https://github.com/geminixiang/agent-sandbox-platform/blob/ec01ad2a317e67fe38940882598a4b7027d71736/docs/kubernetes-backend.md)
- [Helm deployment，固定提交](https://github.com/geminixiang/agent-sandbox-platform/blob/ec01ad2a317e67fe38940882598a4b7027d71736/deploy/helm/README.md)
- [Colima benchmark，固定提交](https://github.com/geminixiang/agent-sandbox-platform/blob/ec01ad2a317e67fe38940882598a4b7027d71736/docs/benchmarks/colima-2026-07-22.md)
- [Streaming report，固定提交](https://github.com/geminixiang/agent-sandbox-platform/blob/ec01ad2a317e67fe38940882598a4b7027d71736/docs/benchmarks/colima-streaming-2026-07-22.md)
- [Test report index，固定提交](https://github.com/geminixiang/agent-sandbox-platform/blob/ec01ad2a317e67fe38940882598a4b7027d71736/docs/test-reports.md)
- [E2B / Cloudflare competitive study，固定提交](https://github.com/geminixiang/agent-sandbox-platform/blob/ec01ad2a317e67fe38940882598a4b7027d71736/docs/research/competitive-e2b-cloudflare.md)

### 本地历史对照

- [Day5：沙箱延迟与第一轮竞品分析](day5-sandbox-latency-and-competitor-analysis.md)
- [Day8：隔离、部署与性能口径矩阵](day8-sandbox-competitor-capability-matrix.md)
- [Day11：CubeSandbox 与完整 sandbox platform](day11-cloud-agent-sandbox-projects.md)
- [Day12：从 CubeSandbox 反推 AgentCube 路线](day12-agentcube-roadmap-from-cubesandbox.md)
- [Day21：OpenSandbox / Agent Substrate](day21-opensandbox-agent-substrate-study.md)
- [Day28：控制面、状态面、数据面、runtime 面](day28-agent-substrate-architecture-and-agentcube-differentiation.md)
- [Day32：Session Runtime Control Plane PRD](day32-substrate-competitive-analysis-and-agentcube-prd.md)
- [Day35：快慢资源分离与 node-local lifecycle](day35-agentcube-architecture-iteration-conclusion.md)
