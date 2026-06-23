# AgentCube Architecture Summary

> 内容由办公领域大模型生成，仅供参考。

## Core Challenges Addressed

- Conflict between Kubernetes scheduling granularity and sandbox lifecycle demands.
- Kubernetes Pod creation introduces high latency for sandbox instantiation.
- `kube-scheduler` can become overwhelmed by short-lived workloads.
- The native Pod model lacks direct support for snapshot recovery, pre-warming, and resource pooling.
- The current Kubernetes-only lifecycle path cannot easily achieve sub-second startup or local scheduling.

## Dual-Layer Scheduling Model

### Layer 1: Kubernetes

- Manages resource pools through a `SandboxWorkspace` CRD.
- `WorkspaceController` provisions placeholder Pods for resource reservation.
- Reserves CPU and memory on selected nodes.
- Maintains pool capacity across the cluster.

### Layer 2: Sandbox System

- `SandboxScheduler` performs fine-grained scheduling within reserved resources.
- `sandbox-runtime` handles sandbox lifecycle management and resource isolation.

## Four-Tier Architecture

| Layer | Name | Responsibilities |
| --- | --- | --- |
| Layer 1 | Kubernetes Foundation Layer | Node management, kube-scheduler, namespace isolation, RBAC isolation |
| Layer 2 | Resource Pool Control Layer | `WorkspaceController` manages resource reservations; `ReservationManager` tracks capacity and node distribution |
| Layer 3 | Scheduler Control Layer | `SandboxScheduler` handles admission, placement, recycling, snapshot-priority scheduling, and local-cache-aware scheduling |
| Layer 4 | Node Data Plane | `sandbox-runtime` manages execution, snapshots, resource monitoring, and integration with network/storage layers |

## Dual Control Chains

### Resource Pool Management Chain

```text
SandboxWorkspace -> WorkspaceController -> Placeholder Pods
```

Purpose:

- Maintain pool state.
- Reserve resources before real sandbox requests arrive.
- Rebalance reserved capacity across nodes.

### Sandbox Lifecycle Chain

```text
Sandbox API / CR -> SandboxScheduler -> sandbox-runtime
```

Purpose:

- Drive sandbox instance creation.
- Drive sandbox instance deletion.
- Report sandbox state back to the control plane.

## Key Objects

| Object | Role |
| --- | --- |
| `SandboxWorkspace` | Defines resource pool boundaries, quotas, and policies |
| `Sandbox` | Represents an individual sandbox instance with resource requests |
| `SandboxNodeState` | Tracks node capacity, including reserved, allocated, and free resources, plus runtime health |

## Core Module Responsibilities

| Module | Responsibility |
| --- | --- |
| `WorkspaceController` | Manages pool creation, node selection, and placeholder Pod lifecycle |
| `SandboxScheduler` | Makes scheduling decisions based on pool state |
| `NodeAgent` / `RuntimeAdapter` | Bridges the control plane with runtime execution |
| `sandbox-runtime` | Handles sandbox creation, snapshots, and resource isolation |

## Critical Workflows

### Workspace Creation

```text
User declares pool
  -> Controller selects nodes
  -> Controller creates placeholder Pods
  -> Pool becomes Ready when placeholder Pods are scheduled
```

### Sandbox Scheduling

```text
User submits request
  -> Scheduler selects node based on pool state
  -> NodeAgent invokes runtime to create sandbox instance
```

### Node State Reporting

```text
NodeAgent collects runtime metrics
  -> NodeAgent updates SandboxNodeState
  -> Scheduler uses SandboxNodeState for later placement decisions
```

## Summary

This architecture decouples sandbox lifecycle management from Kubernetes-level scheduling. The intended benefit is efficient resource pooling and rapid sandbox instantiation while preserving Kubernetes compatibility.

---

# AgentCube 架构概要

> 内容由办公领域大模型生成，仅供参考。

## 要解决的核心问题

- Kubernetes 调度粒度和 sandbox 生命周期需求之间存在冲突。
- Kubernetes Pod 创建流程会给 sandbox 实例化带来较高延迟。
- `kube-scheduler` 可能被大量短生命周期 workload 压垮。
- 原生 Pod 模型缺少对快照恢复、预热和资源池化的直接支持。
- 仅依赖 Kubernetes Pod 生命周期，很难实现亚秒级启动或节点本地调度。

## 双层调度模型

### 第一层：Kubernetes

- 通过 `SandboxWorkspace` CRD 管理资源池。
- `WorkspaceController` 创建 placeholder Pods，用于资源预留。
- 在选定节点上预留 CPU 和内存。
- 维护整个集群中的资源池容量。

### 第二层：Sandbox System

- `SandboxScheduler` 在已预留资源内部执行更细粒度的调度。
- `sandbox-runtime` 负责 sandbox 生命周期管理和资源隔离。

## 四层架构

| 层级 | 名称 | 职责 |
| --- | --- | --- |
| Layer 1 | Kubernetes Foundation Layer | 节点管理、kube-scheduler、namespace 隔离、RBAC 隔离 |
| Layer 2 | Resource Pool Control Layer | `WorkspaceController` 管理资源预留；`ReservationManager` 跟踪容量和节点分布 |
| Layer 3 | Scheduler Control Layer | `SandboxScheduler` 处理准入、放置、回收、快照优先调度和本地缓存感知调度 |
| Layer 4 | Node Data Plane | `sandbox-runtime` 管理执行、快照、资源监控，并与网络和存储层集成 |

## 双控制链路

### 资源池管理链路

```text
SandboxWorkspace -> WorkspaceController -> Placeholder Pods
```

用途：

- 维护资源池状态。
- 在真实 sandbox 请求到来前预留资源。
- 在节点之间重新平衡预留容量。

### Sandbox 生命周期链路

```text
Sandbox API / CR -> SandboxScheduler -> sandbox-runtime
```

用途：

- 驱动 sandbox 实例创建。
- 驱动 sandbox 实例删除。
- 将 sandbox 状态回报给控制面。

## 关键对象

| 对象 | 作用 |
| --- | --- |
| `SandboxWorkspace` | 定义资源池边界、配额和策略 |
| `Sandbox` | 表示一个带资源请求的独立 sandbox 实例 |
| `SandboxNodeState` | 跟踪节点容量，包括已预留、已分配、空闲资源，以及 runtime 健康状态 |

## 核心模块职责

| 模块 | 职责 |
| --- | --- |
| `WorkspaceController` | 管理资源池创建、节点选择和 placeholder Pod 生命周期 |
| `SandboxScheduler` | 基于资源池状态做调度决策 |
| `NodeAgent` / `RuntimeAdapter` | 连接控制面和 runtime 执行层 |
| `sandbox-runtime` | 处理 sandbox 创建、快照和资源隔离 |

## 关键流程

### Workspace 创建

```text
用户声明资源池
  -> Controller 选择节点
  -> Controller 创建 placeholder Pods
  -> placeholder Pods 调度完成后，资源池进入 Ready 状态
```

### Sandbox 调度

```text
用户提交请求
  -> Scheduler 根据资源池状态选择节点
  -> NodeAgent 调用 runtime 创建 sandbox 实例
```

### 节点状态上报

```text
NodeAgent 收集 runtime metrics
  -> NodeAgent 更新 SandboxNodeState
  -> Scheduler 在后续放置决策中使用 SandboxNodeState
```

## 总结

该架构将 sandbox 生命周期管理和 Kubernetes 层面的调度解耦。预期收益是在保持 Kubernetes 兼容性的同时，实现更高效的资源池化和更快的 sandbox 实例化。
