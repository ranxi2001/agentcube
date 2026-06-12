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
| E2B 兼容 | 兼容 E2B 这类 AI code interpreter / sandbox 服务的 SDK 或 API 形态 | 现有使用 E2B SDK 的应用可以少改代码迁移到兼容实现 |

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

CubeSandbox 是腾讯云开源的高性能 sandbox 服务，定位是面向 AI Agent 的 E2B-compatible（兼容 E2B 的 SDK/API 形态，方便已有 E2B code interpreter 应用迁移）硬件隔离沙盒。它基于 RustVMM 和 KVM，官方文档强调：

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

这里的 AgentCube benchmark 不是端到端 AI Agent 测试，而是 CodeInterpreter sandbox 基础设施测试。它测的是 `create session -> claim/create sandbox -> Router 转发 -> picod 执行 print("ok") -> delete session` 这条最小路径，不包含 LLM 调用、Agent 规划/推理循环、工具选择、LangChain/LangGraph 流程、复杂依赖加载或任务正确率。因此这些数字只能说明“Agent 调用代码执行沙盒时，底层 sandbox session 路径有多快”，不能代表完整 Agent 应用的端到端时延。

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

### AgentCube warmPoolSize 对性能的影响

`warmPoolSize` 的作用是提前准备一批可用 CodeInterpreter sandbox。它不能让单个 sandbox 里的 Python 执行变快，但可以显著减少并发请求因为“没有可用预热 sandbox”而等待补池的时间。

在当前测试机上，并发 10 的变化非常明显：

| `warmPoolSize` | run | 成功数 | total p50 | total p95 | create session p50 | 现象 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 2 | run1 | 10/10 | `7315.21 ms` | `9299.62 ms` | `7278.76 ms` | 只有 2 个预热位，8 个请求等待补池 |
| 5 | run1 | 10/10 | `503.56 ms` | `11924.62 ms` | `341.07 ms` | 前半数命中快，后半数长尾明显 |
| 5 | run2 | 9/10 | `528.07 ms` | `16943.74 ms` | `392.89 ms` | 1 个请求 504，说明 5 个预热位覆盖不了并发 10 |
| 10 | run1 | 10/10 | `436.11 ms` | `803.94 ms` | `375.22 ms` | 覆盖并发 10，整体降到亚秒级 |
| 10 | run2 | 10/10 | `565.23 ms` | `932.83 ms` | `344.74 ms` | 结果稳定，没有 pool miss 长尾 |
| 20 | run1 | 10/10 | `698.37 ms` | `1025.89 ms` | `521.58 ms` | 稳定，但没有比 10 更快 |
| 20 | run2 | 10/10 | `671.82 ms` | `996.04 ms` | `518.03 ms` | 说明超过并发需求后收益不再线性增加 |

这说明当前 AgentCube 最主要的并发瓶颈不是 `run_code` 本身，而是 session 创建/claim sandbox 阶段。当并发量超过 warm pool 容量时，请求会等待新的 sandbox 被调度和补进池里；当 warm pool 容量覆盖突发并发量时，延迟会从秒级下降到亚秒级。但 `warmPoolSize` 也不是越大越好：在并发 10 这个口径下，`warmPoolSize=10` 是当前观察到的最佳档，`warmPoolSize=20` 更稳但没有继续降延迟，反而略慢，可能是更多预热 Pod 和控制面对象带来的管理开销。

目前看到的 AgentCube 最佳时延状态可以分三层理解：

| 状态 | 现有数据 | 含义 |
| --- | ---: | --- |
| 单次热池命中 | 顺序测试最小 total `91.95 ms`，p50 `177.14 ms` | 没有明显排队时，普通 Pod 路径可以到 100ms 级 |
| 并发 10 且预热位匹配 | `warmPoolSize=10` total p50 `436.11-565.23 ms` | 10 个请求都能命中预热池，当前口径下是最佳档 |
| 并发 10 且预热位过量 | `warmPoolSize=20` total p50 `671.82-698.37 ms` | 稳定但没有继续变快，说明 pool 过量也可能带来额外管理开销 |
| 并发 10 但预热位不足 | total p50 `7315.21 ms` | 主要是在等补池，不代表系统最佳状态 |

因此，AgentCube 的“最佳时延状态”不是简单调大一个参数就无限变快，而是要让 `warmPoolSize` 和目标突发并发量匹配，并确保 sandbox 模板、镜像、Router、Workload Manager、Redis/Valkey 和底层 Kubernetes 调度都处于稳定状态。当前并发 10 口径下，最佳观察值来自 `warmPoolSize=10`。继续优化的方向应该是：用更大样本重复 `warmPoolSize=8/10/12` 附近的测试、缩短 claim 路径、减少并发 session 删除开销、以及在 Kata/Kuasar 等 RuntimeClass 下重测强隔离路径。

## 相对值：用倍数理解生态位置

不同项目的官方 benchmark 往往跑在不同机器上，绝对毫秒值不能直接混用。但如果某个项目已经在同一张官方竞品表里列出了多个 backend 的结果，就可以在这个表内部计算相对值。相对值不能替代真实同机测试，但能帮助判断生态位置。

### forkd 官方同机 N=100 fan-out 表

forkd README 给出了一组同机 benchmark：Ubuntu 24.04、Linux 6.14、20 vCPU、30 GiB、KVM；workload 是同时 spawn 100 个 sandbox，每个 sandbox 执行 `import numpy; numpy.zeros(5).tolist()`。按 forkd `101 ms` 作为 1x，得到：

| Backend | 官方 wall-clock | 相对 forkd | 说明 |
| --- | ---: | ---: | --- |
| forkd | `101 ms` | `1x` | warm parent + snapshot CoW fork |
| Firecracker cold-boot | `759 ms` | `7.5x` | 原始 Firecracker 冷启动，无上层编排 |
| CubeSandbox | `1.06 s` | `10.5x` | forkd 表里的 CubeSandbox fast-path N=100 数据 |
| BoxLite | `113.2 s` | `1121x` | KVM microVM，冷启动 OCI rootfs |
| OpenSandbox | `122.0 s` | `1208x` | Docker/K8s/gVisor/Kata/FC 抽象层 |
| gVisor | `288.6 s` | `2857x` | userspace kernel container |
| Docker runc | `335.3 s` | `3320x` | 标准容器 runtime |

同一张表还给了内存相对值：

| Backend | 官方 memory delta / sandbox | 相对 forkd |
| --- | ---: | ---: |
| forkd | `0.12 MiB` | `1x` |
| Docker runc | `4 MiB` | `33.3x` |
| CubeSandbox | `5 MiB` | `41.7x` |
| Firecracker cold-boot | `84 MiB` | `700x` |

这个相对值说明 forkd 在“同一个预热状态 fan-out 出很多 microVM”这个细分问题上非常激进，位置更靠近 snapshot/fork primitive，而不是普通 sandbox platform。它的代价是机器要求高、当前更偏单机 daemon、生产化调度能力还在补。

### CubeSandbox 官方自述表

CubeSandbox README 的自述表没有给出完整同机多 backend 数字，但给了几个定位指标：

| 指标 | Docker Container | CubeSandbox | 相对理解 |
| --- | ---: | ---: | --- |
| Boot speed | `200 ms` | `<60 ms` | CubeSandbox 至少约 `3.3x` 更快 |
| 50 并发创建 | 未给 Docker 对照 | avg `67 ms`，P95 `90 ms`，P99 `137 ms` | 说明它关注高并发 cold start 稳定性 |
| Memory overhead | 未给 Docker 精确值 | `<5 MB` | 说明它关注高密度 microVM |
| Isolation | shared kernel namespace | dedicated kernel + eBPF | CubeSandbox 用更强隔离换取仍然较低的启动/内存开销 |

CubeSandbox 的生态位置更像“E2B 兼容的 KVM sandbox 平台”：比单一 fork primitive 更平台化，提供 API、模板、网络隔离、集群组件和 E2B 迁移路径。

### cage-bro 官方自述表

cage-bro README 把自己和 Docker sandbox 做了工具层对比：

| 指标 | Docker sandbox | cage-bro | 相对理解 |
| --- | ---: | ---: | --- |
| Memory | `~2 GB` per Chromium container | `~100 MB` per sandbox | cage-bro 约 `20x` 更省内存 |
| Init time | seconds | `~1 ms` | cage-bro 启动开销明显更低 |
| Density | 1 container per VM | `20+` sandboxes per 1c1g VM | 单机工具密度约 `20x+` |

这个相对值说明 cage-bro 的位置不是“强隔离 microVM”，而是“轻量 agent tool runtime”。它牺牲一部分隔离边界，换取非常低的工具启动和执行开销。

### 我们本机相对值

我们当前测试机只能有效跑 AgentCube 普通 Pod 路径和 cage-bro 进程级 runtime。按 cage-bro 并发 10 p50 `58.48 ms` 作为对照：

| 对比项 | AgentCube | cage-bro | 相对值 | 解读 |
| --- | ---: | ---: | ---: | --- |
| 顺序 p50 total | `177.14 ms` | `18.41 ms` | cage-bro 约 `9.6x` 快 | 只比较本机执行路径，不代表同隔离等级 |
| 并发 10 p50 total，AgentCube `warmPoolSize=2` | `7315.21 ms` | `58.48 ms` | cage-bro 约 `125.1x` 快 | 不公平，AgentCube 8 个请求 pool miss |
| 并发 10 p50 total，AgentCube `warmPoolSize=10` | `436.11 ms` / `565.23 ms` | `58.48 ms` | cage-bro 约 `7.5x-9.7x` 快 | 更接近“都提前准备好”的口径，但仍不是同隔离等级 |

这组相对值的意义是：AgentCube 的并发突发延迟高度依赖 warm pool 容量；cage-bro 的进程级工具 runtime 在本机很快；但二者安全边界和系统目标不同。

### 生态位置总结

按“相对值 + 能力边界”看，可以粗略分成四类：

| 生态位置 | 代表项目 | 相对特征 |
| --- | --- | --- |
| Snapshot/fork primitive | forkd | 在预热父 VM fan-out 场景下相对值极强，但更依赖 KVM host 和单机 daemon 能力 |
| KVM sandbox platform | CubeSandbox | 启动和内存相对传统 VM/容器更优，同时保留硬件隔离和平台组件 |
| Agent tool runtime | cage-bro | 相对 Docker 工具容器更轻、更快、更高密度，但自身不是 microVM |
| Kubernetes Agent control plane | AgentCube | 绝对执行延迟受 warm pool 和底层 runtime 影响；优势在 K8s 原生生命周期、调度和资源治理 |

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
