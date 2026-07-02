# 基于 K8s CRD 的沙箱资源池生命周期管理控制体系设计

## 一、设计哲学

借鉴 Agent Substrate WorkerPool 的双层架构思想，做以下关键改造：

| substrat 设计 | 本设计 | 原因 |
|--------------|-------|------|
| Deployment 管理 Worker Pod | DaemonSet-like 管理**占位 Pod** | 每节点一个资源池实例 |
| Pod 内含 ateom-gvisor | Pod 内运行**占位代理进程** | 实际编排由 node-ctl 处理 |
| 存储：etcd + Redis | 存储：**纯 etcd（K8s API Server）** | 资源池控制面只需要 CRD 状态 |
| 管理 sandbox 多路复用 | **不管理 sandbox 生命周期** | sandbox 的编排、调度、快照等由 node-ctl 独立完成 |

**核心假设**：
- 混部场景：节点上一般容器业务与沙箱业务共存
- 沙箱资源通过**形式占位 Pod** 锁定，仅与调度器配合，不创建实际 cgroup 实体
- 节点预装 node-ctl 组件包，但**只有在占位 Pod 拉起时才被激活**
- **node-ctl agent 作为黑盒**，仅通过预定义接口与其交互，不设计其内部实现

**本设计范围**：
- ✅ SandboxPoolTemplate 管理（全局策略定义、占位 Pod 生命周期）
- ✅ SandboxPool 管理（节点级状态、与 node-ctl 的策略同步）
- ❌ sandbox 的创建/挂起/恢复/删除（由 node-ctl 负责）
- ❌ sandbox 的资源超配协调（由 node-ctl 负责）
- ❌ sandbox 的快照管理（由 node-ctl 负责）

---

## 二、API 设计

### 2.1 SandboxPoolTemplate CRD（全局策略定义）

类比 substrate 的 `WorkerPool`，但增加 DaemonSet-like 的节点选择能力。

```yaml
apiVersion: sandbox-pool.io/v1alpha1
kind: SandboxPoolTemplate
metadata:
  name: default-pool
  namespace: sandbox-system
spec:
  # 调度范围：与 DaemonSet 类似
  selector:
    matchLabels:
      sandbox-node: "true"

  nodeSelector:                     # 附加节点选择条件
    kubernetes.io/os: linux

  # 节点级资源池配置（每个节点的资源上限）
  resourcePolicy:
    cpu: "8"                          # 每个节点锁定的 CPU 核数（严格上下限一致）
    memory: "16Gi"                    # 每个节点锁定的 Memory 大小

  # 占位 Pod 模板配置
  placeholderPodTemplate:
    annotations:
      sandbox-pool.io/skip-cgroup: "true"   # 标记：不创建实际 cgroup
    tolerations:
    - operator: Exists                        # 容忍所有污点
    runtimeClassName: placeholder             # 可选：使用自定义 RuntimeClass

  # 节点级同步配置
  syncPolicy:
    syncInterval: 30s                       # 控制器与 node-ctl 状态同步间隔
    healthCheckInterval: 60s                # 节点健康检查间隔

status:
  # 仅维护 SandboxPool 实例的聚合数量与状态，不携带任何节点级或 Sandbox 级详情
  totalSandboxPools: 10              # 期望的 SandboxPool 实例总数（对应匹配到的节点数）
  readySandboxPools: 9               # 状态为 Ready 的 SandboxPool 数量
  notReadySandboxPools: 1            # 状态非 Ready 的 SandboxPool 数量

  conditions:
  - type: TemplateReady
    status: True
    reason: AllPoolsReady
    lastTransitionTime: "2024-01-01T00:00:00Z"
```

### 2.2 SandboxPool CRD（节点级状态，每节点一个实例）

类比 substrate 的每个 Worker Pod，但这里是**每节点一个实例**，用于记录该节点资源池的运行状态。

```yaml
apiVersion: sandbox-pool.io/v1alpha1
kind: SandboxPool
metadata:
  name: default-pool-node-1
  namespace: sandbox-system
  labels:
    sandbox-pool.io/template: default-pool    # 关联父级 SandboxPoolTemplate
    sandbox-pool.io/node: node-1
spec:
  # 关联的模板
  templateRef:
    name: default-pool
    namespace: sandbox-system

  # 目标节点
  nodeName: node-1

  # node-ctl 接口配置（blackbox dependency）
  nodeCtl:
    endpoint: "unix:///run/node-ctl/node-ctl.sock"   # node-ctl 本地监听地址
    healthCheckInterval: 60s

status:
  phase: Ready                                  # Pending / Ready / Degraded / Failed

  # 占位 Pod 信息
  placeholderPod:
    name: sandbox-pool-placeholder-default-pool-node-1
    uid: abc123-def456
    phase: Running
    ip: 10.0.0.5

  # 占位代理进程状态
  placeholderAgent:
    version: "v0.1.0"
    nodeCtlStarted: true                        # 是否已调用 node-ctl serve
    nodeCtlStartAt: "2024-01-01T00:00:00Z"

  # 资源覆盖标记（直接修改 SandboxPool 时的标记）
  override:
    enabled: true                               # 是否已脱离模板，使用自定义资源
    reason: "manually overridden by user"
    overriddenAt: "2024-01-01T00:00:00Z"

  # 节点级资源池独立配置（当 override.enabled=true 时生效）
  resourcePolicyOverride:
    cpu: "16"                         # 覆盖后的 CPU 配额
    memory: "32Gi"                    # 覆盖后的 Memory 配额

  # 占位 Pod VPA Resize 状态
  resize:
    status: InProgress                          # None / InProgress / Completed / Deferred
    requestedCpu: "12"                          # VPA 请求的 CPU
    requestedMemory: "24Gi"                     # VPA 请求的 Memory
    deferredReason: "watermark too high"        # 缩容被推迟的原因
    lastProbeTime: "2024-01-01T00:00:00Z"       # 上次探测资源水位的时间

  # node-ctl 状态
  nodeCtl:
    connected: true
    version: "v1.2.3"
    lastHeartbeat: "2024-01-01T00:00:00Z"

  # 资源池状态（从 node-ctl 获取，只读）
  poolInfo:
    cpuQuotaUs: 4000000                          # 已同步到 node-ctl 的 CPU quota
    memoryMaxBytes: 17179869184                  # 已同步到 node-ctl 的 Memory limit
    sandboxCount: 45
    activeSandboxCount: 4
    actualCpuUsage: "1.5"                        # node-ctl 上报的实际用量
    actualMemoryUsage: "6Gi"

  lastAppliedGeneration: 1                       # 记录最后成功应用的 Spec 版本

  conditions:
  - type: ResourceSynced
    status: True
    reason: PolicyAppliedSuccessfully
    lastTransitionTime: "2024-01-01T00:00:00Z"
    observedGeneration: 1
  - type: NodeCtlHealthy
    status: True
    reason: HealthCheckPassed
    lastTransitionTime: "2024-01-01T00:00:00Z"
    observedGeneration: 1
```

---

## 三、占位 Pod 的功能和定位

### 3.1 占位 Pod 的核心定位

占位 Pod 的核心是 **placeholder-agent** 进程，它承担两个层面的角色：

**角色一：RuntimeClass Handler（CRI 接口响应者）**

当 SandboxPoolTemplate Controller 创建占位 Pod 时，kubelet 通过标准 CRI 接口调用 placeholder-agent 来完成 Pod 生命周期的管理。placeholder-agent 实现了 **kubelet RuntimeClass handler** 的能力，响应 kubelet 为创建占位 Pod 触发的完整 CRI 调用链路。

**角色二：node-ctl 守护者**

作为占位 Pod 的常驻进程，placeholder-agent 负责拉起、守护和代理 node-ctl 的状态。

### 3.2 placeholder-agent 完整功能清单

| 功能大类 | 子功能 | 说明 | 实现方式 |
|---------|--------|------|---------|
| **CRI 接口响应** | RunPodSandbox | 响应 kubelet 创建占位 Pod 的请求 | 实现 `runtime.v1.RuntimeService.RunPodSandbox` RPC |
| | StopPodSandbox | 响应 kubelet 停止占位 Pod 的请求 | 实现 `StopPodSandbox` RPC，清理资源 |
| | RemovePodSandbox | 响应 kubelet 删除占位 Pod 的请求 | 实现 `RemovePodSandbox` RPC |
| | CreateContainer | 响应 kubelet 创建占位容器的请求 | 跳过 cgroup 创建，仅注册容器 ID |
| | StartContainer | 响应 kubelet 启动容器的请求 | 启动 placeholder-agent 进程 |
| | ListPods/ListContainers | 响应 kubelet 查询请求 | 返回占位 Pod/容器状态 |
| | PodSandboxStatus | 响应 kubelet 查询 Pod 状态 | 返回 Running 状态 |
| | ContainerStatus | 响应 kubelet 查询容器状态 | 返回 Running 状态 |
| **健康检查** | liveness probe | kubelet 定期探活 | HTTP `/healthz` 返回 200 |
| | readiness probe | kubelet 就绪检查 | HTTP `/healthz` 返回 200 |
| **node-ctl 管理** | 激活 node-ctl | Pod 启动时拉起 | exec 调用 `/usr/bin/node-ctl serve` |
| | 守护监控 | SIGCHLD 捕获 + 自动重启 | 进程监控 goroutine |
| | 健康代理 | 聚合 node-ctl 健康状态 | `/healthz` 同时检查自身 + node-ctl |
| **状态上报** | 状态同步 | 定期向控制器上报 | gRPC 上报直接读取 CRD |

### 3.3 CRI 接口实现（placeholder-agent 作为 RuntimeClass Handler）

placeholder-agent 需要实现 **Kubernetes Container Runtime Interface (CRI)** 的部分核心接口，以 kubelet RuntimeClass handler 的身份响应占位 Pod 的创建和管理。

#### CRI 调用流程

```
SandboxPoolTemplate Controller 创建占位 Pod CR
        │
        ▼
kubelet 调度 Pod 到目标节点
        │
        ▼
kubelet CRI 调用链
  │
  ├─ 1. RunPodSandbox()        ← 创建 Pod 沙箱
  │     placeholder-agent 接收请求
  │     ├─ 分配 PodSandboxID
  │     ├─ 创建 Pod 网络 namespace（可选）
  │     └─ 注册占位 Pod 状态（内部记录）
  │
  ├─ 2. CreateContainer()      ← 创建 placeholder-agent 容器
  │     placeholder-agent 接收请求
  │     ├─ 跳过 cgroup 创建（占位 Pod 核心要求）
  │     ├─ 分配 ContainerID
  │     └─ 准备 OCI 配置（最小化）
  │
  ├─ 3. StartContainer()       ← 启动容器
  │     placeholder-agent 接收请求
  │     └─ 返回启动成功（自身就是主进程）
  │
  ├─ 4. PodSandboxStatus()     ← 定期探活
  │     placeholder-agent 回复: Ready
  │
  ├─ 5. ContainerStatus()      ← 定期探活
  │     placeholder-agent 回复: Running
  │
  └─ 6. ListPodSandbox()       ← 定期同步
        placeholder-agent 回复: 占位 Pod 列表
```

#### CRI 接口实现示例

placeholder-agent 作为 gRPC Server，监听在节点本地路径（如 `/run/sandbox-pool/cri.sock`），处理 kubelet 的 CRI 调用：

```go
// placeholder-agent 的 CRI Server 实现
type PlaceholderCRIService struct {
    runtimev1.UnimplementedRuntimeServiceServer
    pods   sync.Map   // PodSandboxID -> PodSandbox
    containers sync.Map // ContainerID -> Container
    mu     sync.Mutex
}

// === 核心接口 1: RunPodSandbox ===
// kubelet 创建占位 Pod 时调用此接口
func (s *PlaceholderCRIService) RunPodSandbox(ctx context.Context, req *runtimev1.RunPodSandboxRequest) (*runtimev1.RunPodSandboxResponse, error) {
    config := req.GetConfig()
    podID := config.GetId()

    // 1. 验证是否为占位 Pod
    annotations := config.GetAnnotations()
    if annotations["sandbox-pool.io/skip-cgroup"] != "true" {
        return nil, status.Error(codes.InvalidArgument, "this CRI handler only supports placeholder pods")
    }

    // 2. 创建 Pod Sandbox（不创建 cgroup）
    sandbox := &PodSandbox{
        ID:        podID,
        Name:      config.GetMetadata().GetName(),
        Namespace: config.GetMetadata().GetNamespace(),
        State:     runtimev1.PodSandboxState_SANDBOX_READY,
        CreatedAt: time.Now().UnixNano(),
        // 不创建 cgroup，仅记录状态
    }
    s.pods.Store(podID, sandbox)

    // 3. 创建 Pod 网络 namespace（可选，用于占位 Pod 网络隔离）
    if err := s.createNetNS(podID); err != nil {
        return nil, fmt.Errorf("failed to create netns: %w", err)
    }

    log.Info("placeholder pod sandbox created", "podID", podID, "name", sandbox.Name)
    return &runtimev1.RunPodSandboxResponse{PodSandboxId: podID}, nil
}

// === 核心接口 2: CreateContainer ===
// 跳过 cgroup 创建，仅注册容器
func (s *PlaceholderCRIService) CreateContainer(ctx context.Context, req *runtimev1.CreateContainerRequest) (*runtimev1.CreateContainerResponse, error) {
    containerID := fmt.Sprintf("placeholder-container-%s", uuid.New())
    podID := req.GetPodSandboxId()

    // 1. 验证 Pod 存在
    if _, ok := s.pods.Load(podID); !ok {
        return nil, status.Error(codes.NotFound, "pod sandbox not found")
    }

    // 2. 跳过 cgroup 创建
    // 占位 Pod 的核心设计：不调用 cgroupfs 创建 cgroup
    // 资源锁定完全通过 PodSpec.Resources.Requests 在 kube-scheduler 层面实现

    // 3. 注册容器
    container := &Container{
        ID:        containerID,
        PodID:     podID,
        Name:      req.GetConfig().GetMetadata().GetName(),
        State:     runtimev1.ContainerState_CONTAINER_CREATED,
        CreatedAt: time.Now().UnixNano(),
    }
    s.containers.Store(containerID, container)

    log.Info("placeholder container created (no cgroup)", "containerID", containerID, "podID", podID)
    return &runtimev1.CreateContainerResponse{ContainerId: containerID}, nil
}

// === 核心接口 3: StartContainer ===
func (s *PlaceholderCRIService) StartContainer(ctx context.Context, req *runtimev1.StartContainerRequest) (*runtimev1.StartContainerResponse, error) {
    containerID := req.GetContainerId()

    containerVal, ok := s.containers.Load(containerID)
    if !ok {
        return nil, status.Error(codes.NotFound, "container not found")
    }
    container := containerVal.(*Container)
    container.State = runtimev1.ContainerState_CONTAINER_RUNNING
    container.StartedAt = time.Now().UnixNano()

    return &runtimev1.StartContainerResponse{}, nil
}

// === 核心接口 4: PodSandboxStatus ===
func (s *PlaceholderCRIService) PodSandboxStatus(ctx context.Context, req *runtimev1.PodSandboxStatusRequest) (*runtimev1.PodSandboxStatusResponse, error) {
    podID := req.GetPodSandboxId()

    sandboxVal, ok := s.pods.Load(podID)
    if !ok {
        return nil, status.Error(codes.NotFound, "pod sandbox not found")
    }
    sandbox := sandboxVal.(*PodSandbox)

    return &runtimev1.PodSandboxStatusResponse{
        Status: &runtimev1.PodSandboxStatus{
            Id:        sandbox.ID,
            State:     sandbox.State,
            CreatedAt: sandbox.CreatedAt,
            Network: &runtimev1.PodSandboxNetworkStatus{
                Ip: sandbox.IP, // 由 kubelet 分配
            },
        },
    }, nil
}

// === 核心接口 5: ContainerStatus ===
func (s *PlaceholderCRIService) ContainerStatus(ctx context.Context, req *runtimev1.ContainerStatusRequest) (*runtimev1.ContainerStatusResponse, error) {
    containerID := req.GetContainerId()

    containerVal, ok := s.containers.Load(containerID)
    if !ok {
        return nil, status.Error(codes.NotFound, "container not found")
    }
    container := containerVal.(*Container)

    return &runtimev1.ContainerStatusResponse{
        Status: &runtimev1.ContainerStatus{
            Id:        container.ID,
            PodSandboxId: container.PodID,
            State:     container.State,
            CreatedAt: container.CreatedAt,
            StartedAt: container.StartedAt,
        },
    }, nil
}

// === 清理接口 ===
func (s *PlaceholderCRIService) StopPodSandbox(ctx context.Context, req *runtimev1.StopPodSandboxRequest) (*runtimev1.StopPodSandboxResponse, error) {
    podID := req.GetPodSandboxId()
    if sandbox, ok := s.pods.Load(podID); ok {
        sandbox.(*PodSandbox).State = runtimev1.PodSandboxState_SANDBOX_NOTREADY
    }
    return &runtimev1.StopPodSandboxResponse{}, nil
}

func (s *PlaceholderCRIService) RemovePodSandbox(ctx context.Context, req *runtimev1.RemovePodSandboxRequest) (*runtimev1.RemovePodSandboxResponse, error) {
    podID := req.GetPodSandboxId()
    s.pods.Delete(podID)
    s.removeNetNS(podID)
    return &runtimev1.RemovePodSandboxResponse{}, nil
}
```

### 3.4 placeholder-agent 启动流程

placeholder-agent 同时作为 CRI Server（响应 kubelet）和普通进程（管理 node-ctl），其启动流程如下：

```
占位 Pod 被 kubelet 调度到节点
  │
  ▼
kubelet → placeholder-agent CRI Server
  │
  ├─ RunPodSandbox() → 创建占位 Pod 状态
  ├─ CreateContainer() → 跳过 cgroup，注册容器
  └─ StartContainer() → 启动 placeholder-agent 主进程
       │
       ▼
  placeholder-agent 主进程启动
       │
       ├─ 1. 监听 CRI socket 端口（持续响应 kubelet 查询）
       │
       ├─ 2. 调用 /usr/bin/node-ctl serve → node-ctl 进程启动
       │
       ├─ 3. 启动 HTTP liveness/readiness 端点（:8080/healthz）
       │
       ├─ 4. 启动 node-ctl 进程监控 goroutine
       │     - SIGCHLD 捕获
       │     - 异常退出时自动重启
       │
       └─ 5. 定期向 SandboxPool Controller 上报状态
```

### 3.5 node-ctl 的生命周期管理

node-ctl 组件**随节点创建时预装**（安装在节点的 `/usr/bin/node-ctl`），但**不自动启动**。只有在占位 Pod 真正调度到该节点并拉起后，placeholder-agent 才会调用 `node-ctl serve` 来激活 node-ctl。

```
节点创建/加入
  │
  ▼
node-ctl 二进制预装到 /usr/bin/
  │ (此时 node-ctl 未运行)
  │
  ▼
SandboxPoolTemplate Controller 调度占位 Pod 到节点
  │
  ▼
placeholder-agent 启动（kubelet 通过 CRI 创建 Pod → CreateContainer → StartContainer）
  │
  ├─ 1. 调用 node-ctl serve ──→ node-ctl 进程启动
  │
  ├─ 2. 启动健康检查 HTTP 端点
  │
  └─ 3. 监控 node-ctl 进程状态
        │
        ▼ (异常情况)
     node-ctl 异常退出
        │
        └─ placeholder-agent 自动重启 node-ctl serve
```

### 3.6 为什么不使用标准 kubelet 内置 runtime

常规容器使用 containerd/cri-o 等标准 CRI 实现，会创建 cgroup、网络 namespace 等。占位 Pod 需要**跳过 cgroup 创建**，因此必须使用自定义的 placeholder-agent 作为独立的 RuntimeClass handler，完全控制 Pod/容器的生命周期管理。

### 3.7 Pod Spec 定义

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: sandbox-pool-placeholder-{template}-{node}
  namespace: sandbox-system
  labels:
    sandbox-pool.io/template: default-pool
    sandbox-pool.io/node: node-1
    sandbox-pool.io/skip-cgroup: "true"
spec:
  nodeSelector:
    sandbox-node: "true"
    kubernetes.io/os: linux

  # 容忍所有污点，确保不被驱逐
  tolerations:
  - operator: Exists
    effect: NoSchedule
  - operator: Exists
    effect: NoExecute
  - operator: Exists
    effect: PreferNoSchedule

  # 高优先级，确保优先调度
  priorityClassName: system-cluster-critical

  containers:
  - name: placeholder-agent
    image: sandbox-pool.io/placeholder-agent:v0.1.0
    command: ["/placeholder-agent"]
    args:
    - "--node-ctl-path=/usr/bin/node-ctl"
    - "--node-ctl-socket=unix:///run/node-ctl/node-ctl.sock"
    - "--healthz-port=8080"

    ports:
    - name: healthz
      containerPort: 8080

    # 健康检查
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
      periodSeconds: 30
      failureThreshold: 3

    readinessProbe:
      httpGet:
        path: /healthz
        port: 8080
      periodSeconds: 10
      failureThreshold: 3

    # 资源请求（用于调度锁定）
    resources:
      requests:
        cpu: "2"
        memory: "4Gi"

  # 挂载 hostPath 用于 node-ctl 通信（可选）
  volumes:
  - name: run-node-ctl
    hostPath:
      path: /run/node-ctl
      type: DirectoryOrCreate
```

---

## 四、系统架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Kubernetes 控制平面                              │
│  存储：纯 etcd（所有状态通过 K8s API Server 读写）                      │
│                                                                      │
│  ┌──────────────────────────┐            ┌──────────────────────┐     │
│  │  SandboxPoolTemplate     │            │  SandboxPool         │     │
│  │  Controller              │            │  Controller           │     │
│  │  (Deployment, 全局)       │          ◄─│  (DaemonSet, 每节点)  │     │
│  │                          │            │                       │     │
│  │  - 管理 SandboxPoolTemplate│            │  - watch 各自节点的    │     │
│  │    占位 Pod 生命周期       │            │    SandboxPool 实例    │     │
│  │  - 维护 status 聚合视图   │            │  - 与本地 node-ctl    │     │
│  │  - 管理 SandboxPool 实例  │            │    同步策略和状态      │     │
│  └────────────┬─────────────┘            └───────────┬───────────┘     │
│               │ 1. 创建/销毁占位 Pod                 │ 2. 同步/采集     │
└───────────────┼──────────────────────────────────────┼─────────────────┘
                │                                      │
┌───────────────┼──────────────────────────────────────┼─────────────────┐
│               ▼                                      ▼                │
│  ┌────────────────────────┐            ┌──────────────────────────┐   │
│  │ Node (kubelet)          │            │ 占位 Pod (DaemonSet-like) │   │
│  │                         │            │                          │   │
│  │  ┌──────────────────┐   │            │  ┌────────────────────┐  │   │
│  │  │ 占位 Pod          │   │            │  │ placeholder-agent │  │   │
│  │  │                   │   │            │  │                    │  │   │
│  │  │  placeholder-    │   │            │  │ 1.健康检查端点     │  │   │
│  │  │  agent           │   │            │  │ 2.node-ctl serve   │  │   │
│  │  │                  │   │            │  │ 3.node-ctl 守护     │  │   │
│  │  │  [启动]          │   │            │  │ 4.健康代理          │  │   │
│  │  │  node-ctl serve──┼───┼────────────┼──┼──┐                 │  │   │
│  │  │                  │   │            │  │  │                 │  │   │
│  │  │  CPU Req: 2      │   │            │  └──┼─────────────────┘  │   │
│  │  │  Mem Req: 4Gi    │   │            └─────┼────────────────────┘   │
│  │  │  无真实 cgroup   │   │                  │ gRPC/Unix Socket        │
│  │  +──────────────────+   │                  ▼                         │
│  │                         │            ┌──────────────────┐            │
│  │  剩余资源可调度一般 Pod  │            │  node-ctl agent   │            │
│  │  (节点总 - 占位 Pod)    │            │  (已有实现/黑盒)   │            │
│  │                         │            │                  │            │
│  └─────────────────────────┘            │  职责（本设计     │            │
│                                         │  不实现）:        │            │
│                                         │  - 沙箱创建/销毁  │            │
│                                         │  - 资源超配协调   │            │
│                                         │  - 快照管理      │            │
│                                         │  - 空闲检测      │            │
│                                         │  - 本地 cgroup    │            │
│                                         │    管理           │            │
│                                         └──────────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 五、占位 Pod 的可靠性设计

### 5.1 抗污点与防驱逐

占位 Pod 默认**容忍所有污点**，确保不会因为节点打标或主动驱逐而被调度器迁走：

```yaml
tolerations:
- operator: Exists
  effect: NoSchedule
- operator: Exists
  effect: NoExecute
- operator: Exists
  effect: PreferNoSchedule

priorityClassName: system-cluster-critical   # 最高优先级之一
```

这意味着：
- 节点添加任何 taint（包括维护模式）→ 占位 Pod 不受影响
- 节点资源紧张触发驱逐 → 占位 Pod 不会被驱逐（system-cluster-critical）
- 管理员主动 cordon → 不影响已运行的占位 Pod

### 5.2 DaemonSet-like 自动补偿

当占位 Pod 被意外删除（如误删、节点异常恢复），SandboxPoolTemplate Controller 的 **DaemonSet-like 补偿机制** 会立即感知并创建新的占位 Pod：

```
占位 Pod 被误删
  │
  ▼
SandboxPoolTemplate Controller
  - Watch 到 Pod 删除事件 (或定期 Reconcile 发现缺失)
  - 检测到目标节点缺少对应占位 Pod
  - 立即创建新的占位 Pod
  │
  ▼
新的 placeholder-agent 启动
  - 调用 node-ctl serve（如果 node-ctl 未运行）
  - 恢复健康检查端点
  - 上报状态到控制器
  │
  ▼
结果：整体无实际影响
  - 调度资源重新被锁定（kubelet 重新看到资源占用）
  - node-ctl 重新被拉起
  - 已运行的 sandbox 不受影响（node-ctl 进程独立管理）
```

### 5.3 故障场景应对

| 故障场景 | 影响 | 自动恢复机制 | 恢复时间 |
|---------|------|------------|---------|
| 占位 Pod 被删除 | 资源暂时解锁 | Controller 自动重建 | < 10s |
| 节点短暂断连后恢复 | 占位 Pod 可能重启 | Controller 检测到节点 Ready 后重建 | < 30s |
| placeholder-agent 崩溃 | Pod 重启，node-ctl 可能残留 | kubelet 自动重启容器；placeholder-agent 重新调用 serve | < 30s |
| node-ctl 崩溃 | sandbox 管理中断 | placeholder-agent 捕获并自动重启 node-ctl | < 5s |

### 5.4 占位 Pod VPA（Vertical Pod Autoscaler）资源调整设计

SandboxPool 支持通过 K8s VPA 机制对占位 Pod 的资源配额进行扩容或缩容，实现节点级沙箱资源池的动态调整。

#### 5.4.1 VPA 触发的两种入口

```
┌─────────────────────────────────────────────────────────────────────┐
│  入口 1: 修改 SandboxPoolTemplate 资源策略                           │
│                                                                     │
│  用户修改 template.spec.resourcePolicy.cpu.max                      │
│  从 "8" 改为 "12"                                                  │
│       │                                                              │
│       ▼                                                              │
│  SandboxPoolTemplate Controller 检测 Spec 变化                       │
│       │                                                              │
│       ▼                                                              │
│  遍历所有关联的 SandboxPool 实例                                     │
│  对每个未标记 override 的 SandboxPool                                │
│       │                                                              │
│       ▼                                                              │
│  更新对应占位 Pod 的 resources → 触发 kubelet VPA resize            │
│  更新对应占位 Pod 的 resourceVersion → kubelet 重新感知              │
│                                                                     │
│  特点: 全局生效，所有节点统一调整                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  入口 2: 直接修改指定 SandboxPool 资源策略                           │
│                                                                     │
│  用户直接修改 sandboxpool/default-pool-node-1                       │
│  spec.resourcePolicyOverride.cpu.max = "16"                         │
│       │                                                              │
│       ▼                                                              │
│  SandboxPool Controller 检测 override 变更                          │
│       │                                                              │
│       ▼                                                              │
│  为该 SandboxPool 打上 override 标记:                                │
│  status.override.enabled = true                                     │
│  status.override.reason = "manually overridden by user"             │
│       │                                                              │
│       ▼                                                              │
│  仅更新该节点的占位 Pod resources → 触发 VPA resize                 │
│       │                                                              │
│       ▼                                                              │
│  ⚠️ 此后修改 SandboxPoolTemplate 时:                                │
│  该 SandboxPool 被跳过，不再受模板策略影响                            │
│  （除非用户手动清除 override 标记，重新绑定模板）                     │
│                                                                     │
│  特点: 单节点精准调整，脱离模板自治                                   │
└─────────────────────────────────────────────────────────────────────┘
```

#### 5.4.2 VPA Resize 完整交互流程

```
VPA/用户修改占位 Pod 资源配额
  │
  ▼
kubelet 感知 Pod resources 变更
  │
  ▼
kubelet → placeholder-agent CRI Server
  │
  └─ UpdateContainerResources() ──────┐
                                       ▼
                              placeholder-agent 处理
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
              扩容场景            缩容场景           无效变更
                    │                  │                  │
                    ▼                  ▼                  ▼
         与 node-ctl 联动      与 node-ctl 联动      直接返回 Success
         apply 新上限          检测水位              (资源无变化)
                    │                  │
                    │         ┌────────┼────────┐
                    │         ▼                 ▼
                    │   水位安全             水位危险
                    │   < emergency_pool     ≥ emergency_pool
                    │   (默认 95%)
                    │         │                 │
                    │         ▼                 ▼
                    │   apply 生效        返回 Deferred
                    │   Pod resize        Pod resize 状态:
                    │   状态: Active      deferred
                    │                     产生 K8s Event
                    │                     │
                    │                     ▼
                    │              周期性探测 (30s)
                    │                     │
                    │              与 node-ctl 确认水位
                    │                     │
                    │              水位降至安全?
                    │                ├─ 是 → apply 生效，resize 状态: Active
                    │                └─ 否 → 继续等待，更新 Event
```

#### 5.4.3 UpdateContainerResources CRI 接口实现

placeholder-agent 需要额外实现 `UpdateContainerResources` CRI 接口，用于响应 kubelet 的 VPA resize 动作：

```go
// placeholder-agent CRI Server - UpdateContainerResources
func (s *PlaceholderCRIService) UpdateContainerResources(ctx context.Context, req *runtimev1.UpdateContainerResourcesRequest) (*runtimev1.UpdateContainerResourcesResponse, error) {
    containerID := req.GetContainerId()
    linuxResources := req.GetLinux()

    // 1. 验证容器存在
    containerVal, ok := s.containers.Load(containerID)
    if !ok {
        return nil, status.Error(codes.NotFound, "container not found")
    }
    container := containerVal.(*Container)

    // 2. 提取新的资源配额
    newCPUQuota := linuxResources.GetCpuPeriod()     // CFS period
    newCPUPeriod := linuxResources.GetCpuQuota()     // CFS quota
    newMemLimit := linuxResources.GetMemoryLimitInBytes()

    // 3. 判断是扩容还是缩容
    oldResources := container.Resources
    isScaleUp := isScaleUp(oldResources, newCPUQuota, newMemLimit)

    // 4. 与 node-ctl 联动
    nodeCtlClient := s.getNodeCtlClient(container.PodID)

    if isScaleUp {
        // === 扩容场景：直接 apply ===
        applyReq := &nodectl.ApplyResourcePolicyRequest{
            CpuQuotaUs:    newCPUPeriod,
            MemoryMaxBytes: newMemLimit,
        }
        resp, err := nodeCtlClient.ApplyResourcePolicy(ctx, applyReq)
        if err != nil {
            return nil, status.Errorf(codes.Internal, "node-ctl apply failed: %v", err)
        }
        if !resp.GetApplied() {
            return nil, status.Errorf(codes.Internal, "node-ctl rejected: %s", resp.GetError())
        }

        // 更新容器状态
        container.Resources = &ContainerResources{
            CpuQuotaUs:    newCPUPeriod,
            MemoryMaxBytes: newMemLimit,
        }

        // 更新 SandboxPool CRD resize 状态
        s.updateSandboxPoolResizeStatus(container.PodID, "Active", "")

        log.Info("placeholder pod scale up succeeded",
            "containerID", containerID,
            "newCpuQuota", newCPUPeriod,
            "newMemLimit", newMemLimit,
        )
        return &runtimev1.UpdateContainerResourcesResponse{}, nil

    } else {
        // === 缩容场景：先检查水位 ===
        poolState, err := nodeCtlClient.GetPoolState(ctx)
        if err != nil {
            return nil, status.Errorf(codes.Internal, "failed to get pool state: %v", err)
        }

        // 计算缩容后的预期水位
        currentUsage := poolState.GetActualCpuUsage()
        currentLimit := float64(oldResources.CpuQuotaUs) / 100000.0
        newLimit := float64(newCPUPeriod) / 100000.0
        projectedWatermark := currentUsage / newLimit

        emergencyThreshold := 0.95  // node-ctl 默认紧急水位 95%

        if projectedWatermark >= emergencyThreshold {
            // 水位过高，拒绝缩容
            s.updateSandboxPoolResizeStatus(container.PodID, "Deferred",
                fmt.Sprintf("projected watermark %.1f%% exceeds emergency threshold %.1f%%",
                    projectedWatermark*100, emergencyThreshold*100))

            // 产生 K8s Event（通过上报控制器或直接调用 K8s API）
            s.recordEvent(container.PodID, corev1.EventTypeWarning, "ResizeDeferred",
                fmt.Sprintf("Scale-down deferred: projected watermark %.1f%% exceeds emergency threshold",
                    projectedWatermark*100))

            // 启动周期性探测 goroutine
            go s.deferredScaleDownWatch(ctx, container, newCPUPeriod, newMemLimit, emergencyThreshold)

            return &runtimev1.UpdateContainerResourcesResponse{}, nil
        }

        // 水位安全，apply 缩容
        applyReq := &nodectl.ApplyResourcePolicyRequest{
            CpuQuotaUs:    newCPUPeriod,
            MemoryMaxBytes: newMemLimit,
        }
        resp, err := nodeCtlClient.ApplyResourcePolicy(ctx, applyReq)
        if err != nil {
            return nil, status.Errorf(codes.Internal, "node-ctl apply failed: %v", err)
        }

        container.Resources = &ContainerResources{
            CpuQuotaUs:    newCPUPeriod,
            MemoryMaxBytes: newMemLimit,
        }
        s.updateSandboxPoolResizeStatus(container.PodID, "Active", "")

        log.Info("placeholder pod scale down succeeded",
            "containerID", containerID,
            "newCpuQuota", newCPUPeriod,
            "newMemLimit", newMemLimit,
        )
        return &runtimev1.UpdateContainerResourcesResponse{}, nil
    }
}

// 周期性探测 goroutine：等待水位降至安全阈值以下
func (s *PlaceholderCRIService) deferredScaleDownWatch(ctx context.Context,
    container *Container, targetCPU, targetMem int64, emergencyThreshold float64) {

    ticker := time.NewTicker(30 * time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            nodeCtlClient := s.getNodeCtlClient(container.PodID)
            poolState, err := nodeCtlClient.GetPoolState(ctx)
            if err != nil {
                continue
            }

            currentUsage := poolState.GetActualCpuUsage()
            newLimit := float64(targetCPU) / 100000.0
            projectedWatermark := currentUsage / newLimit

            if projectedWatermark < emergencyThreshold {
                // 水位安全，执行缩容
                applyReq := &nodectl.ApplyResourcePolicyRequest{
                    CpuQuotaUs:    targetCPU,
                    MemoryMaxBytes: targetMem,
                }
                resp, err := nodeCtlClient.ApplyResourcePolicy(ctx, applyReq)
                if err != nil || !resp.GetApplied() {
                    s.recordEvent(container.PodID, corev1.EventTypeWarning, "ResizeFailed",
                        fmt.Sprintf("Deferred scale-down apply failed: %v", err))
                    continue
                }

                container.Resources = &ContainerResources{
                    CpuQuotaUs:    targetCPU,
                    MemoryMaxBytes: targetMem,
                }
                s.updateSandboxPoolResizeStatus(container.PodID, "Active", "")
                s.recordEvent(container.PodID, corev1.EventTypeNormal, "ResizeCompleted",
                    "Deferred scale-down completed successfully")

                log.Info("deferred scale-down completed",
                    "containerID", container.ID,
                    "projectedWatermark", projectedWatermark,
                )
                return
            }

            // 继续等待，更新 Event
            s.recordEvent(container.PodID, corev1.EventTypeNormal, "ResizeDeferred",
                fmt.Sprintf("Still waiting: current watermark %.1f%%, threshold %.1f%%",
                    projectedWatermark*100, emergencyThreshold*100))
        }
    }
}

func isScaleUp(old *ContainerResources, newCPU, newMem int64) bool {
    return newCPU > old.CpuQuotaUs || newMem > old.MemoryMaxBytes
}
```

#### 5.4.4 控制器侧的 VPA 响应逻辑

SandboxPool Controller 和 SandboxPoolTemplate Controller 需要感知 VPA 变化并做相应处理：

```
SandboxPoolTemplate Controller Reconcile 循环
  │
  ▼
for each SandboxPool instance:
  │
  ├─ if SandboxPool.status.override.enabled == true:
  │     │
  │     └─ SKIP 该 SandboxPool，不应用模板策略变更
  │
  └─ if SandboxPool.status.override.enabled == false:
        │
        └─ 检测 template generation 变化
              │
              └─ 更新占位 Pod resources → 触发 VPA
```

### 5.5 节点预留资源比例与 VPA 的协同

| 场景 | 触发方式 | node-ctl 行为 | 占位 Pod resize 结果 |
|------|---------|--------------|-------------------|
| **扩容** | template spec.cpu.max 增加 | 直接 apply 新上限 | resize → Active |
| **缩容（水位安全）** | 实际使用远低于新上限 | 直接 apply 新上限 | resize → Active |
| **缩容（水位危险）** | 缩容后将超过 emergency_pool (95%) | 拒绝 apply | resize → Deferred |
| **缩容等待完成）** | 周期性探测发现水位下降 | apply 新上限 | resize Deferred → Active |

---

## 六、对 node-ctl 的依赖（黑盒接口）

**node-ctl 是已有的节点级沙箱编排组件**，本设计不修改其实现，仅定义需要调用的接口清单。

### 6.1 所需接口

| 接口 | 方向 | 用途 | 调用方 | 频率 |
|------|------|------|--------|------|
| `ApplyResourcePolicy` | 控制器 → node-ctl | 下发资源池上限（CPU quota、Memory limit） | SandboxPool Controller / placeholder-agent | Spec 变更时 + VPA resize 时 |
| `GetPoolState` | 控制器 → node-ctl | 采集该节点资源池运行时状态 | SandboxPool Controller | 定期（30s） |
| `GetVersion` | 控制器 → node-ctl | 获取 node-ctl 版本和健康状态 | SandboxPool Controller | 启动时 + 定期 |
| `GetWatermark` | placeholder-agent → node-ctl | 获取资源池当前水位（用于 VPA 缩容判断） | placeholder-agent | VPA 缩容场景 + 周期性探测 |

### 6.2 接口定义（Protobuf，仅描述依赖，非实现）

```protobuf
syntax = "proto3";
package nodectl.v1;

service NodeCtlReadOnly {
  // 下发资源池上限配置（幂等）
  rpc ApplyResourcePolicy(ApplyResourcePolicyRequest) returns (ApplyResourcePolicyResponse);

  // 采集资源池运行时状态
  rpc GetPoolState(GetPoolStateRequest) returns (GetPoolStateResponse);

  // 获取 node-ctl 版本和健康状态
  rpc GetVersion(GetVersionRequest) returns (GetVersionResponse);

  // 获取资源池当前水位（VPA 缩容判断）
  rpc GetWatermark(GetWatermarkRequest) returns (GetWatermarkResponse);
}

// ============ 接口 1: 下发资源策略 ============

message ApplyResourcePolicyRequest {
  int64 cpu_quota_us = 1;          // CPU CFS quota (微秒)
  int64 memory_max_bytes = 2;      // Memory 硬上限 (字节)
  int32 generation = 3;            // 对应 CRD 的 generation，用于幂等
}

message ApplyResourcePolicyResponse {
  bool applied = 1;
  int64 applied_generation = 2;    // 实际应用的 generation
  string error = 3;                // 非空表示失败
}

// ============ 接口 2: 采集状态 ============

message GetPoolStateRequest {
  // 无参数
}

message GetPoolStateResponse {
  int32 sandbox_count = 1;
  int32 active_sandbox_count = 2;
  double actual_cpu_usage = 3;     // 实际 CPU 使用（核数）
  int64 actual_memory_usage = 4;   // 实际 Memory 使用（字节）
  string node_ctl_version = 5;
  bool healthy = 6;
}

// ============ 接口 3: 版本和健康 ============

message GetVersionRequest {
  // 无参数
}

message GetVersionResponse {
  string version = 1;
  bool healthy = 2;
  int64 uptime_seconds = 3;
}

// ============ 接口 4: 获取水位（VPA 缩容判断） ============

message GetWatermarkRequest {
  // 用于计算预期水位的拟议资源上限
  int64 proposed_cpu_quota_us = 1;
  int64 proposed_memory_max_bytes = 2;
}

message GetWatermarkResponse {
  double current_cpu_usage = 1;              // 当前实际 CPU 使用（核数）
  double current_memory_usage = 2;           // 当前实际 Memory 使用（字节）
  double projected_cpu_watermark = 3;        // 按拟议上限计算的预期 CPU 水位
  double projected_memory_watermark = 4;     // 按拟议上限计算的预期 Memory 水位
  bool would_exceed_emergency = 5;           // 是否会触发 emergency_pool
  double emergency_threshold = 6;            // node-ctl 紧急水位阈值（默认 0.95）
  int64 active_sandbox_count = 7;            // 当前活跃沙箱数
}
```

### 6.3 node-ctl 假设前提

| 假设 | 说明 |
|------|------|
| 本地监听 | node-ctl 在节点本地监听 Unix Socket 或本地端口 |
| 幂等性 | `ApplyResourcePolicy` 在同一 generation 重复调用是幂等的 |
| 可用性 | node-ctl 作为守护进程长期运行，异常退出后由 placeholder-agent 自动重启 |
| 独立性 | node-ctl 独立管理 sandbox 的完整生命周期（创建/挂起/恢复/删除） |

---

## 七、核心控制器设计

### 7.1 SandboxPoolTemplateReconciler（全局协调器）

**职责**：管理 SandboxPoolTemplate 资源，负责创建/销毁占位 Pod 和 SandboxPool 实例

```go
type SandboxPoolTemplateReconciler struct {
    client.Client
    Scheme *runtime.Scheme
}

func (r *SandboxPoolTemplateReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    template := &sandboxpoolv1alpha1.SandboxPoolTemplate{}
    if err := r.Get(ctx, req.NamespacedName, template); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // === 阶段 1: 选择目标节点 ===
    nodes, err := r.listTargetNodes(ctx, template)
    if err != nil {
        return r.updateStatus(ctx, template, err)
    }

    // === 阶段 2: 确保每节点存在占位 Pod ===
    for _, node := range nodes {
        if err := r.ensurePlaceholderPod(ctx, template, &node); err != nil {
            log.Error(err, "failed to ensure placeholder pod", "node", node.Name)
        }
    }

    // === 阶段 3: 清理不需要的占位 Pod ===
    if err := r.cleanupOrphanedPlaceholderPods(ctx, template, nodes); err != nil {
        return ctrl.Result{}, err
    }

    // === 阶段 4: 确保每节点存在 SandboxPool 实例 ===
    for _, node := range nodes {
        if err := r.ensureSandboxPoolInstance(ctx, template, &node); err != nil {
            log.Error(err, "failed to ensure SandboxPool instance", "node", node.Name)
        }
    }

    // === 阶段 5: 清理不需要的 SandboxPool 实例 ===
    if err := r.cleanupOrphanedSandboxPools(ctx, template, nodes); err != nil {
        return ctrl.Result{}, err
    }

    // === 阶段 6: 聚合更新 status ===
    return ctrl.Result{RequeueAfter: 30 * time.Second}, r.updateAggregatedStatus(ctx, template)
}

// 创建占位 Pod
func (r *SandboxPoolTemplateReconciler) ensurePlaceholderPod(ctx context.Context,
    template *sandboxpoolv1alpha1.SandboxPoolTemplate, node *corev1.Node) error {

    podName := placeholderPodName(template.Name, node.Name)
    existing := &corev1.Pod{}
    err := r.Get(ctx, types.NamespacedName{Name: podName, Namespace: template.Namespace}, existing)

    if err == nil {
        // Pod 已存在，检查 OwnerReference
        if !metav1.IsControlledBy(existing, template) {
            if err := controllerutil.SetControllerReference(template, existing, r.Scheme); err == nil {
                return r.Update(ctx, existing)
            }
        }
        return nil
    }
    if !apierrors.IsNotFound(err) {
        return err
    }

    // 创建新 Pod
    pod := &corev1.Pod{
        ObjectMeta: metav1.ObjectMeta{
            Name:      podName,
            Namespace: template.Namespace,
            Labels: map[string]string{
                "sandbox-pool.io/template":     template.Name,
                "sandbox-pool.io/node":         node.Name,
                "sandbox-pool.io/skip-cgroup":  "true",
            },
        },
        Spec: corev1.PodSpec{
            NodeName:       node.Name,
            RuntimeClassName: template.Spec.PlaceholderPodTemplate.RuntimeClassName,
            Containers: []corev1.Container{{
                Name:    "placeholder-agent",
                Image:   "sandbox-pool.io/placeholder-agent:v0.1.0",
                Command: []string{"/placeholder-agent"},
                Args: []string{
                    "--node-ctl-path=/usr/bin/node-ctl",
                    "--node-ctl-socket=unix:///run/node-ctl/node-ctl.sock",
                    "--healthz-port=8080",
                },
                Ports: []corev1.ContainerPort{{
                    Name:          "healthz",
                    ContainerPort: 8080,
                }},
                LivenessProbe: &corev1.Probe{
                    ProbeHandler: corev1.ProbeHandler{
                        HTTPGet: &corev1.HTTPGetAction{
                            Path: "/healthz",
                            Port: intstr.FromInt(8080),
                        },
                    },
                    PeriodSeconds: 30,
                },
                Resources: corev1.ResourceRequirements{
                    Requests: corev1.ResourceList{
                        corev1.ResourceCPU:    template.Spec.ResourcePolicy.CPU,
                        corev1.ResourceMemory: template.Spec.ResourcePolicy.Memory,
                    },
                    Limits: corev1.ResourceList{
                        corev1.ResourceCPU:    template.Spec.ResourcePolicy.CPU,
                        corev1.ResourceMemory: template.Spec.ResourcePolicy.Memory,
                    },
                },
            }},
            Tolerations: template.Spec.PlaceholderPodTemplate.Tolerations,
            PriorityClassName: "system-cluster-critical",
        },
    }

    if err := controllerutil.SetControllerReference(template, pod, r.Scheme); err != nil {
        return err
    }
    return r.Create(ctx, pod)
}

// 创建 SandboxPool 实例（每节点一个）
func (r *SandboxPoolTemplateReconciler) ensureSandboxPoolInstance(ctx context.Context,
    template *sandboxpoolv1alpha1.SandboxPoolTemplate, node *corev1.Node) error {

    poolName := sandboxPoolInstanceName(template.Name, node.Name)
    existing := &sandboxpoolv1alpha1.SandboxPool{}
    err := r.Get(ctx, types.NamespacedName{Name: poolName, Namespace: template.Namespace}, existing)

    if err == nil {
        return nil  // 已存在
    }
    if !apierrors.IsNotFound(err) {
        return err
    }

    pool := &sandboxpoolv1alpha1.SandboxPool{
        ObjectMeta: metav1.ObjectMeta{
            Name:      poolName,
            Namespace: template.Namespace,
            Labels: map[string]string{
                "sandbox-pool.io/template": template.Name,
                "sandbox-pool.io/node":     node.Name,
            },
        },
        Spec: sandboxpoolv1alpha1.SandboxPoolSpec{
            TemplateRef: sandboxpoolv1alpha1.TemplateRef{
                Name:      template.Name,
                Namespace: template.Namespace,
            },
            NodeName:  node.Name,
            NodeCtl: sandboxpoolv1alpha1.NodeCtlConfig{
                Endpoint:            template.Spec.NodeCtlEndpoint,
                HealthCheckInterval: template.Spec.SyncPolicy.HealthCheckInterval,
            },
        },
    }

    if err := controllerutil.SetControllerReference(template, pool, r.Scheme); err != nil {
        return err
    }
    return r.Create(ctx, pool)
}

func placeholderPodName(templateName, nodeName string) string {
    return fmt.Sprintf("sandbox-pool-placeholder-%s-%s", templateName, nodeName)
}

func sandboxPoolInstanceName(templateName, nodeName string) string {
    return fmt.Sprintf("%s-%s", templateName, nodeName)
}
```

### 7.2 SandboxPoolReconciler（节点级协调器）

**职责**：每节点一个实例（DaemonSet 部署），负责与本地 node-ctl 通信，同步策略和采集状态

```go
type SandboxPoolReconciler struct {
    client.Client
    Scheme        *runtime.Scheme
    NodeCtlClient nodectl.ReadOnlyClient   // gRPC 连接本地 node-ctl
    NodeName      string                    // 当前节点名（通过 Downward API 注入）
}

func (r *SandboxPoolReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    pool := &sandboxpoolv1alpha1.SandboxPool{}
    if err := r.Get(ctx, req.NamespacedName, pool); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // === 步骤 1: 获取父级 SandboxPoolTemplate ===
    template, err := r.getTemplate(ctx, pool)
    if err != nil {
        return r.updateCondition(ctx, pool, Failed, "TemplateNotFound", err.Error())
    }

    // === 步骤 2: 检查 Spec 是否变更，需要同步策略到 node-ctl ===
    if pool.Status.LastAppliedGeneration != template.Generation {
        if err := r.syncPolicyToNodeCtl(ctx, pool, template); err != nil {
            return r.updateCondition(ctx, pool, Degraded, "SyncFailed", err.Error())
        }
        pool.Status.LastAppliedGeneration = template.Generation
    }

    // === 步骤 3: 采集 node-ctl 状态 ===
    poolState, err := r.NodeCtlClient.GetPoolState(ctx)
    if err != nil {
        return r.updateCondition(ctx, pool, Degraded, "NodeCtlUnreachable", err.Error())
    }

    // === 步骤 4: 更新 status ===
    pool.Status.Phase = sandboxpoolv1alpha1.PoolPhaseReady
    pool.Status.PoolInfo = sandboxpoolv1alpha1.PoolInfo{
        SandboxCount:       poolState.SandboxCount,
        ActiveSandboxCount: poolState.ActiveSandboxCount,
        ActualCpuUsage:     poolState.ActualCpuUsage,
        ActualMemoryUsage:  poolState.ActualMemoryUsage,
    }
    pool.Status.NodeCtl.Connected = true
    pool.Status.NodeCtl.Version = poolState.NodeCtlVersion
    pool.Status.NodeCtl.LastHeartbeat = metav1.Now()

    if err := r.Status().Update(ctx, pool); err != nil {
        return ctrl.Result{}, err
    }

    return ctrl.Result{RequeueAfter: template.Spec.SyncPolicy.SyncInterval.Duration}, nil
}

// 同步资源策略到 node-ctl
func (r *SandboxPoolReconciler) syncPolicyToNodeCtl(ctx context.Context,
    pool *sandboxpoolv1alpha1.SandboxPool, template *sandboxpoolv1alpha1.SandboxPoolTemplate) error {

    cpuQuotaUs := int64(template.Spec.ResourcePolicy.CPU.Max.Fraction() * 100000)
    memoryBytes := template.Spec.ResourcePolicy.Memory.Max.Value()

    req := &nodectl.ApplyResourcePolicyRequest{
        CpuQuotaUs:    cpuQuotaUs,
        MemoryMaxBytes: memoryBytes,
        Generation:     template.Generation,
    }

    resp, err := r.NodeCtlClient.ApplyResourcePolicy(ctx, req)
    if err != nil {
        return fmt.Errorf("ApplyResourcePolicy failed: %w", err)
    }
    if !resp.Applied {
        return fmt.Errorf("node-ctl rejected policy: %s", resp.Error)
    }

    // 记录已应用的配额到 status
    pool.Status.PoolInfo.CpuQuotaUs = resp.AppliedCpuQuotaUs
    pool.Status.PoolInfo.MemoryMaxBytes = resp.AppliedMemoryMaxBytes
    return nil
}
```

---

## 八、生命周期完整流程

### 8.1 SandboxPoolTemplate 创建到就绪

```
用户创建 SandboxPoolTemplate
        │
        ▼
┌─────────────────────────────────┐
│ SandboxPoolTemplate Controller   │
│ (watch SandboxPoolTemplate)      │
│                                 │
│ 1. Selector 匹配目标节点         │
│ 2. 每节点创建占位 Pod            │
│    - CPU/Memory 配置             │
│    - 容忍所有污点                │
│    - system-cluster-critical     │
│ 3. 每节点创建 SandboxPool CRD    │
│ 4. 聚合更新 Status（仅统计摘要，  │
│    不枚举具体节点）              │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ kubelet 调度器                    │
│                                 │
│ 看到资源被占位 Pod 锁定           │
│ 一般 Pod 无法分配到这些资源       │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐              ┌──────────────────┐
│ SandboxPool Controller           │              │ placeholder-agent │
│ (DaemonSet, 每节点)               │              │ (占位 Pod 内)     │
│                                 │              │                  │
│ 1. watch 本节点的 SandboxPool   │              │ 1.启动            │
│ 2. 检测 Spec 变化                │              │ 2.node-ctl serve  │
│ 3. ApplyResourcePolicy()         │              │ 3.监控 node-ctl   │
│ 4. GetPoolState() 定期采集      │◄──Unix Socket│ 4.健康检查端点    │
│ 5. 更新 SandboxPool Status      │              │                  │
└─────────────────────────────────┘              └────────┬─────────┘
                                                          │ gRPC
                                                          ▼
                                                ┌──────────────────┐
                                                │  node-ctl agent  │
                                                │  (已有实现/黑盒)  │
                                                │                  │
                                                │  - 接收资源上限   │
                                                │  - 配置本地 cgroup│
                                                │  - 管理 sandbox   │
                                                │    生命周期        │
                                                └──────────────────┘
```

### 8.2 SandboxPoolTemplate 更新流程

```
用户修改 SandboxPoolTemplate.Spec
  （如 CPU max 从 8 改为 12）
        │
        ▼
SandboxPoolTemplate Controller
  - 检测到 Spec 变更 (generation 增加)
  - 更新所有 SandboxPool 实例的关联关系
        │
        ▼
每节点的 SandboxPool Controller
  - watch 到 template generation 变化
  - 对比 Status.LastAppliedGeneration
  - 调用 ApplyResourcePolicy(newGeneration)
  - 更新 Status.LastAppliedGeneration
        │
        ▼
node-ctl
  - 收到新的资源上限
  - 调整本地 cgroup 配置
  - 超配策略重新计算
```

### 8.3 SandboxPoolTemplate 删除流程

```
用户删除 SandboxPoolTemplate
        │
        ▼
SandboxPoolTemplate Controller
  - 检测到删除事件
  - 级联删除所有占位 Pod
  - 级联删除所有 SandboxPool CRD
  │
  ▼
占位 Pod 被删除
  │
  ▼
kubelet
  - 占位 Pod 资源解锁
  - 资源可调度一般 Pod
  │
  ▼
placeholder-agent 退出
  - node-ctl 可能被终止（或继续运行残留）
  │
  ▼
SandboxPool Controller (每个节点)
  - SandboxPool 实例被删除
  - 停止与 node-ctl 通信
  - 控制器退出
```

---

## 九、存储设计（纯 etcd）

所有状态存储在 Kubernetes etcd 中，无外部存储依赖。

| CRD 类型 | 存储内容 | 读写方 |
|---------|---------|--------|
| **SandboxPoolTemplate** | Spec: 策略、Selector<br>Status: 聚合视图（只读） | 写: 用户 + Template Controller<br>读: Template Controller + 用户 |
| **SandboxPool** | Spec: 模板引用 + node-ctl 配置<br>Status: 节点状态（只读，由 Controller 更新） | 写: Template Controller + Pool Controller<br>读: Pool Controller + 用户 |
| **Pod (占位)** | 标准 K8s Pod 状态 | 写: kubelet<br>读: Template Controller |

### 乐观并发控制

与 substrate 类似，使用 K8s 内置的 `resourceVersion` 和 `generation` 字段做乐观锁：

```
SandboxPoolTemplate.Spec 变更 → .metadata.generation 递增
SandboxPool.Controller 同步 → .status.lastAppliedGeneration 对齐
如果不一致 → 重新同步
```

---

## 十、关键设计决策

### 对比 substrate WorkerPool

| 设计理念 | substrate | 本设计 |
|---------|-----------|-------|
| CRD 名称 | WorkerPool | **SandboxPoolTemplate** (全局) + **SandboxPool** (节点级) |
| Pod 管理 | Deployment | DaemonSet-like（每节点一个实例） |
| 存储 | etcd + Redis | **纯 etcd**（仅 K8s CRD） |
| 沙箱管理 | 由 ateom-gvisor + atelet 实现 | **完全交由 node-ctl**（黑盒） |
| Pod 进程 | ateom-gvisor | **placeholder-agent**（健康检查 + node-ctl 守护） |
| 控制器职责 | 创建 + 管理 + 多路复用 | **仅创建占位 Pod + 同步策略** |

### 核心优势

| 优势 | 说明 |
|------|------|
| 纯 K8s 原生 | 无外部存储（Redis），所有状态通过 etcd 持久化 |
| 解耦 node-ctl | sandbox 生命周期完全由 node-ctl 管理，控制面不侵入 |
| 混部友好 | 占位 Pod 仅锁定调度资源，不影响一般 Pod 调度 |
| 抗污点/防驱逐 | 容忍所有污点 + system-cluster-critical 优先级 |
| 自动补偿 | DaemonSet-like 机制保障占位 Pod 始终存在 |
| 声明式 API | 用户只需关注 SandboxPoolTemplate，节点级状态自动管理 |

---

## 十一、部署清单

### 11.1 组件列表

| 组件 | 类型 | 职责 |
|------|------|------|
| `sandbox-pool-controller-manager` | Deployment | 运行 SandboxPoolTemplateReconciler |
| `sandbox-pool-node-controller` | DaemonSet | 每节点运行 SandboxPoolReconciler |
| `placeholder-agent` | 占位 Pod 内进程 | 实现 CRI 接口，响应 kubelet，管理 node-ctl 生命周期 |
| `sandbox-pool-crd.yaml` | CRD 定义 | SandboxPoolTemplate + SandboxPool |
| placeholder RuntimeClass | K8s RuntimeClass | 指定 placeholder-agent 为占位 Pod 的 runtime handler |

### 11.2 部署示例

```bash
# 1. 安装 CRD
kubectl apply -f config/crd/sandbox-pool-crd.yaml

# 2. 安装控制器
kubectl apply -f config/manifests/sandbox-pool-controller-manager.yaml
kubectl apply -f config/manifests/sandbox-pool-node-controller.yaml

# 3. 创建 SandboxPoolTemplate 实例
kubectl apply -f config/samples/sandbox-pool-template-default.yaml

# 4. 验证
kubectl get sandboxpooltemplate -n sandbox-system
kubectl get sandboxpool -n sandbox-system
kubectl get pods -n sandbox-system -l sandbox-pool.io/skip-cgroup=true
```

---

## 十二、已知限制

| 限制 | 影响 | 缓解措施 |
|------|------|---------|
| 占位 Pod 无真实 cgroup | 节点 OOM 时可能被 kill | 使用 Guaranteed QoS + 低频探针 |
| node-ctl 不可达 | Status 不更新，策略不同步 | Controller 设置 Degraded 条件 |
| K8s 调度器看不到 sandbox 真实使用 | 可能整体过载 | node-ctl 负责超配控制 |
