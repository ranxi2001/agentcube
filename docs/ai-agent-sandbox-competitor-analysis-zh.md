# AI Agent 沙盒运行环境背景与竞品分析

本文是 `README-ZH.md` 的中文补充材料，用来解释 AgentCube 所处的基础设施背景，以及它与 forkd、CubeSandbox、cage-bro 等项目的关系。

## 背景：AI Agent 为什么需要专属运行环境

大模型应用正在从“只生成文本”的 Chatbot，演进到能自主规划、调用工具、执行代码、读写文件、访问浏览器和修复工程问题的 AI Agent。这个变化带来了一个新的基础设施问题：

> AI Agent 不只需要推理服务，还需要一个极速、安全、可隔离、可复用状态的执行环境。

传统 Docker 容器和标准虚拟机都能运行代码，但直接用于高频 AI Agent 工作流时会遇到几个明显痛点：

1. **冷启动慢**

   Agent 经常要执行 Python、Node.js、shell 或浏览器任务。如果每次都从零启动容器，再加载 `numpy`、`pandas`、`torch`、Playwright、Jupyter 这类依赖，延迟会很高。

2. **状态难以快速复制**

   复杂 Agent 常常需要在同一个上下文上并行试错。例如修复一个 bug 时，Agent 可能希望从“已经读完代码、装好依赖、跑过测试”的状态开始，同时尝试 5 个不同方案。如果底层 runtime 能像“存盘/读档”一样快照和复制当前状态，就能显著提升 fan-out 效率。

3. **安全隔离要求更高**

   Agent 生成的代码不完全可控，可能误删文件、执行危险命令、访问网络，甚至触发恶意行为。普通进程或容器的隔离边界未必足够，生产场景通常需要更强的资源限制、网络控制和硬件级隔离。

4. **云原生调度复杂**

   Agent 工作负载常常是间歇活跃的：用户交互时需要低延迟和资源保障，空闲时又应该快速回收资源。传统批处理、在线推理和普通 Pod 管理方式都不能完全覆盖这种生命周期。

因此，AI Agent 基础设施正在出现一个新方向：面向 Agent 的 code execution sandbox、microVM runtime、warm pool、snapshot/clone、branch/fan-out 和 Kubernetes 原生调度。

## 概念速览

| 概念 | 简单解释 | 在 Agent 场景中的作用 |
| --- | --- | --- |
| Sandbox | 沙盒执行环境 | 隔离执行 Agent 生成的代码、命令和工具调用 |
| Warm Pool | 预热池 | 提前准备好一批可用 sandbox，降低新 session 延迟 |
| Snapshot | 快照 | 保存文件系统、内存或运行状态，便于回滚或复制 |
| Fan-out | 并行分支 | 从同一状态复制出多个执行分支，尝试不同方案 |
| KVM | Linux 内核硬件虚拟化能力 | Firecracker、RustVMM、QEMU 等 microVM 通常需要它 |
| MicroVM | 轻量化小虚拟机 | 比容器隔离更强，比传统 VM 更轻，适合高密度沙盒 |
| RuntimeClass | Kubernetes 选择底层运行时的机制 | AgentCube 可通过它接入 Kata/Kuasar 等更强隔离 runtime |

## 相关项目

### AgentCube

AgentCube 是 Volcano 社区的拟议子项目，当前处于提案和早期设计阶段。它的目标不是单纯提供一个本地代码执行器，而是扩展 Kubernetes / Volcano，使其能够原生支持和管理 AI Agent 工作负载。

AgentCube 关注的问题包括：

- 用 `AgentRuntime` 和 `CodeInterpreter` 这类 CRD 描述 Agent 运行环境。
- 通过 Workload Manager 管理 sandbox 生命周期。
- 通过 Router 将请求路由到对应 session。
- 通过 warm pool 降低 CodeInterpreter session 启动延迟。
- 在 Kubernetes 集群层面处理 Agent 的长会话、间歇活跃、高密度和资源隔离问题。

从定位上看，AgentCube 更偏“云原生控制面和调度层”。它可以运行普通 Pod 路径，也可以通过 `runtimeClassName` 对接 Kata、Kuasar 等更强隔离 runtime。具体隔离强度取决于集群节点和底层 RuntimeClass。

### forkd

forkd 是一个面向 AI Agent fan-out 的 microVM runtime。它基于 Firecracker 和 KVM，核心思想是先启动一个预热父 VM，把 Python 依赖、JIT 状态或模型权重等加载好，然后从这个父 VM 快速 fork/branch 出多个子 microVM。

forkd 的优势在于：

- 每个 child 是独立 Firecracker microVM，有硬件隔离边界。
- 子 VM 可以继承父 VM 的预热内存状态，减少重复加载依赖的时间。
- 适合代码解释器、评测 rollout、SWE-bench 类任务和多分支 Agent 探索。

需要注意的是，forkd 对机器环境要求较高。官方 quick start 要求 x86_64 Linux、KVM、较新的 Linux 发行版和内核能力。我们当前 CentOS 8 测试机没有 `/dev/kvm`，CPU 也没有暴露 `vmx` / `svm`，因此不能在本机完成 forkd microVM 实测。

### CubeSandbox

CubeSandbox 是腾讯云开源的高性能 sandbox 服务，定位是面向 AI Agent 的 E2B-compatible 硬件隔离沙盒。它基于 RustVMM 和 KVM，官方文档强调：

- 硬件级隔离，每个 sandbox 有独立 guest kernel。
- E2B SDK 兼容，便于迁移现有 code interpreter 应用。
- 资源池、snapshot、clone、rollback 等能力。
- 支持单节点和多节点集群。
- 通过 CubeVS/eBPF 做网络隔离和流量策略。

CubeSandbox 更像一个独立 sandbox 平台，自己提供 CubeAPI、CubeMaster、Cubelet、CubeProxy、CubeVS 和 hypervisor/shim 等组件。它和 AgentCube 的差异在于：CubeSandbox 侧重提供 E2B 兼容的 KVM sandbox 服务；AgentCube 侧重 Kubernetes 原生的 Agent 工作负载生命周期和调度。

### cage-bro

cage-bro 是一个轻量的 agent tool runtime，单个 Rust binary 提供 shell、code execution、文件操作、浏览器、MCP 和 REST API。

它的优势是：

- 部署轻，单机即可运行。
- API 面丰富，适合快速给 Agent 接入工具能力。
- 启动和执行开销低，当前测试机上 E2B lifecycle 并发 10 p50 约 `58.48 ms`。

但 cage-bro 的安全边界和 forkd / CubeSandbox 不同。它的核心隔离是进程级，Linux 上可用 Landlock + `rlimit` + timeout；网络隔离、seccomp 等交给外层部署环境。cage-bro README 也明确说明它不是 microVM，不应作为强对抗代码的唯一隔离边界。生产中更适合把它放进 Docker、VM 或 microVM 内部，作为高密度工具层。

## 横向关系

| 项目 | 主要定位 | 关键技术 | 隔离等级倾向 | 云原生/集群属性 |
| --- | --- | --- | --- | --- |
| AgentCube | Kubernetes 原生 Agent 工作负载管理 | CRD、Workload Manager、Router、warm pool、RuntimeClass | 取决于 Pod/runtime；本次实测是普通 Pod | 强，直接面向 Kubernetes |
| forkd | 单机高性能 microVM fan-out | Firecracker、KVM、warm parent、CoW fork/branch | microVM 硬件隔离 | 当前更偏单机 daemon；K8s 只是承载 controller |
| CubeSandbox | E2B 兼容的 KVM sandbox 平台 | RustVMM、KVM、CubeMaster/Cubelet、CubeVS、snapshot/clone | microVM 硬件隔离 | 自带多节点 sandbox 控制面 |
| cage-bro | 轻量 agent tool runtime | Rust binary、REST、MCP、Landlock、rlimit | 进程级隔离 | 默认单机，可容器化部署 |

## 当前实测观察

我们在当前 CentOS 8 测试机上做过 AgentCube 和 cage-bro 的同机 benchmark。测试环境关键限制是：无 `/dev/kvm`，CPU 未暴露 `vmx` / `svm`，所以 forkd 和 CubeSandbox 标准 microVM 路线无法有效实测。

| 项目 | 测试配置 | 并发 10 p50 | 说明 |
| --- | --- | ---: | --- |
| AgentCube | `warmPoolSize=2`，普通 k3s Pod 路径 | `7315.21 ms` | 8 个请求发生 pool miss，主要延迟来自补池等待 |
| AgentCube | 临时 `warmPoolSize=10`，warm pool READY=10 后测两次 | `436.11 ms` / `565.23 ms` | 预热位足够时，并发 10 降到亚秒级 |
| cage-bro | E2B lifecycle，进程级 runtime | `58.48 ms` | 很快，但不是 microVM 隔离 |
| forkd | 本机预检 | 未跑通 | glibc 与 KVM 条件不满足 |
| CubeSandbox | 本机预检 | 未跑通 | 无 `/dev/kvm`，标准路径不适合 |

因此，不能简单得出“某项目一定更快”。不同项目的隔离等级、调度目标和测试口径不同：

- 如果只看本机轻量进程执行，cage-bro 很快。
- 如果把 AgentCube 的 warm pool 配足，并发突发性能会显著改善。
- 如果要比较 forkd / CubeSandbox 的 microVM 能力，需要换到有 KVM 的机器。
- 如果要比较 Kubernetes 原生调度能力，需要看 AgentCube 与 K8s/Volcano 的整合，而不是只看单次代码执行延迟。

## 选型理解

可以用一个类比理解这些项目：

- forkd 和 CubeSandbox 更像在打造“更安全、更轻、更快的隔离执行舱”。
- cage-bro 更像一个“工具齐全、启动很快的 Agent 工具工作台”。
- AgentCube 更像 Kubernetes 集群里的“Agent 工作负载调度和生命周期管理系统”。

它们不是完全替代关系。未来一个完整的 AI Agent 平台可能会同时需要：

- AgentCube 负责 Kubernetes 层面的声明式管理、调度、session 生命周期和资源治理。
- 底层 RuntimeClass 或 sandbox backend 提供 Kata/Kuasar/CubeSandbox/firecracker 等强隔离执行能力。
- cage-bro 这类工具 runtime 提供浏览器、shell、MCP、文件操作等高层工具能力。
- forkd 这类机制提供快速 snapshot/fork/branch，服务高并发 fan-out 和复杂任务试错。

## 参考资料

- AgentCube README：<https://github.com/volcano-sh/agentcube>
- Volcano AgentCube proposal：<https://github.com/volcano-sh/volcano/issues/4686>
- forkd：<https://github.com/deeplethe/forkd>
- CubeSandbox：<https://github.com/TencentCloud/CubeSandbox>
- cage-bro：<https://github.com/aeroxy/cage-bro>
- Firecracker：<https://firecracker-microvm.github.io/>
- Linux KVM project：<https://www.linux-kvm.org/page/Main_Page>
