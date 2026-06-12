# Day 8 实习记录：沙箱竞品隔离能力与部署兼容性矩阵

## 基本信息

- 实习项目：AgentCube
- 实习方向：华为公司开源小组 / AgentCube 开源项目研究
- 日期：Day 8
- 今日主题：建立 AgentCube、forkd、CubeSandbox、cage-bro 的横向能力表
- 核心目标：把隔离等级、OS / 云环境支持、部署编译难度、安全性、云原生和集群调度能力放到同一张表里，后续继续补竞品时沿用同一套维度

## 数据口径

这张表同时使用三类数据，必须分开看：

| 标记 | 含义 | 使用位置 |
| --- | --- | --- |
| 实测 | 我们在当前 CentOS 8 云 VM 上实际跑过的结果 | AgentCube、cage-bro、本机 forkd 预检 |
| 官方 | 项目 README / 官方文档 / 官方 benchmark 写明的数据 | forkd、CubeSandbox、cage-bro |
| 推断 | 根据项目架构和系统要求得到的工程判断 | K8s 调度适配、云 VM 约束、安全边界对比 |

当前测试机环境是：

| 项 | 值 | 备注 |
| --- | --- | --- |
| OS | CentOS Linux 8 | 操作系统发行版，决定默认软件包、系统库版本和官方二进制能不能直接运行 |
| kernel | `4.18.0-348.7.1.el8_5.x86_64` | Linux 内核版本，决定 KVM、Landlock、userfaultfd 等底层隔离能力是否可用 |
| glibc | `2.28` | Linux C 标准库版本；forkd、cage-bro 官方二进制需要更新的 glibc，所以在本机直接运行失败 |
| CPU | 4 vCPU，运行在 KVM 虚拟机里 | 这台机器本身是云上的虚拟机，不是裸金属；性能和虚拟化能力会受云厂商配置限制 |
| `/dev/kvm` | 不存在 | KVM 设备入口；forkd、CubeSandbox 这类 microVM 项目通常需要它来启动硬件虚拟化沙箱 |
| CPU 虚拟化 flags | 未暴露 `vmx` / `svm` | CPU 是否把 Intel VT-x / AMD-V 虚拟化能力暴露给当前系统；未暴露时一般无法在这台 VM 里再跑 KVM microVM |
| Kubernetes | 本地 k3s，用于 AgentCube 实测 | 轻量级 Kubernetes 集群；本次 AgentCube 测的是 k3s Pod + warm pool 路径 |

这个环境对 forkd / CubeSandbox 这类 KVM microVM 项目不友好。因此 forkd 和 CubeSandbox 的性能数字先采用官方数据，等后续换 KVM 可用机器再做同机实测。

## 隔离等级定义

为了避免只写“安全”但不说明边界，我先把隔离等级分成 5 级：

| 等级 | 名称 | 边界 | 代表形态 | 风险说明 |
| --- | --- | --- | --- | --- |
| L1 | 进程级隔离 | 同一宿主内核，子进程限制 | `rlimit`、Landlock、工作目录 jail | 依赖宿主内核安全，不能单独承载强对抗代码 |
| L2 | 容器 / Pod 隔离 | 同一宿主内核，namespace + cgroup | Docker、Kubernetes Pod | 比进程隔离强，但仍共享内核 |
| L3 | 强化容器运行时 | RuntimeClass 或用户态内核/轻量 VM | Kata、Kuasar、gVisor | 安全性取决于实际 runtime 和节点配置 |
| L4 | microVM 硬件隔离 | 每个 sandbox 有独立 guest kernel | Firecracker、RustVMM、KVM microVM | 需要 KVM 或等价虚拟化能力 |
| L5 | 预热 microVM fork / branch | L4 + 预热父 VM + CoW 快照 | forkd warm parent fork | 高隔离同时追求 fan-out 启动速度，但环境要求更高 |

AgentCube 在这张表里要特别标注两种状态：

- 当前实测 `CodeInterpreter` 没有设置 `runtimeClassName`，所以是 L2：普通 k3s Pod 路径。
- AgentCube 的 API 设计支持在 `CodeInterpreter.spec.template.runtimeClassName` 指定 Kata / Kuasar 这类 runtime，因此在正确集群上可以接近 L3 / L4，具体隔离等级取决于底层 RuntimeClass。

## 总览矩阵

| 维度 | AgentCube | forkd | CubeSandbox | cage-bro |
| --- | --- | --- | --- | --- |
| 项目定位 | Kubernetes 原生 AI Agent / CodeInterpreter 工作负载控制面 | AI agent fan-out microVM runtime | E2B 兼容的高性能 KVM sandbox 服务 | 单机 agent tool runtime，包含 shell/code/browser/files/MCP |
| 核心原语 | `CodeInterpreter` CRD + `SandboxWarmPool` + Router + Workload Manager | 从预热父 Firecracker VM fork 子 microVM，支持 BRANCH | RustVMM/KVM microVM + 资源池 + snapshot/clone | 单 Rust binary，按 workspace 管理执行环境 |
| 默认隔离等级 | 本次实测 L2；配置 RuntimeClass 后可接 L3/L4 | L5 | L4 | L1；放进 Docker/VM 后取决于外层边界 |
| 是否硬件隔离 | 当前实测否；取决于 RuntimeClass | 是，KVM/Firecracker | 是，KVM/RustVMM | 否，项目自身不是 microVM |
| 是否共享宿主内核 | 当前实测共享；Kata/Kuasar 路线可不共享 | 不共享，每个 child 是 microVM | 不共享，每个 sandbox 有 guest kernel | 共享，除非外层再套 VM/microVM |
| 性能优化方式 | Warm pool 预热 Pod / sandbox，减少 session 创建等待 | 父 VM 预热后 CoW fork，导入依赖和内存状态可继承 | 资源池预配置、snapshot cloning、CoW 内存复用 | 轻量进程启动，低 runtime 管理开销 |
| 云原生属性 | 强，CRD + controller + Router + Kubernetes 生命周期 | 中，提供 K8s starter manifest，但自然单位仍是单 host daemon | 中，自己有 CubeMaster/Cubelet 集群组件，不是直接依赖 K8s 调度每个 sandbox | 弱，默认是本地/单机服务，可容器化部署 |
| K8s 调度模型 | 每个 sandbox 通过 K8s / agent-sandbox 生命周期管理 | 一个 controller Pod 承载 N 个 child，K8s 只调度 controller Pod | CubeMaster 调度到 Cubelet，不是标准 Pod-per-sandbox | 没有内置 K8s 调度；可作为 Deployment 跑一个服务 |
| 多节点 / 集群 | 依赖 Kubernetes 集群天然扩展 | 当前 alpha 明确缺 multi-node scheduling，one daemon = one host | 官方写明支持 single-node 和 multi-node cluster，CubeMaster 管调度 | 无内置多节点调度 |
| API / SDK | Python SDK、Router HTTP、LangChain/Dify 等集成 | REST、Python SDK、TypeScript SDK、MCP，Python SDK 走 E2B 风格 | E2B SDK drop-in REST API | REST、MCP、Python/TS SDK，E2B lifecycle 部分兼容 |
| 快照 / 分支能力 | 当前报告未验证内存快照；主要是 session / warm pool | 支持 snapshot、diff chain、BRANCH/live BRANCH | 支持 snapshot、clone、rollback | 文件系统 workspace snapshot / restore / fork，不保存进程内存 |
| 当前本机状态 | 已跑通并完成延迟 benchmark | 未跑通，glibc 和 KVM 双重 blocker | 未跑，当前无 `/dev/kvm`，标准路径会被挡；PVM 路线需要换内核/重启 | 已源码构建并跑通 |
| 适合优先评估的问题 | K8s 原生调度、session 生命周期、warm pool 命中率 | 单机 KVM 上大规模 agent fan-out 和状态继承 | E2B 替代、KVM 安全边界、多节点 sandbox 服务 | 轻量工具运行时、MCP/REST 工具密度、非强对抗代码 |

## OS 与云环境支持

| 运行环境 | AgentCube | forkd | CubeSandbox | cage-bro |
| --- | --- | --- | --- | --- |
| 普通 Linux 云 VM，无 `/dev/kvm` | 可跑普通 Pod 路径；强隔离 runtime 取决于节点 | 不适合，核心依赖 KVM/Firecracker | 标准 KVM 路径不适合；官方提供 PVM 路线给普通云服务器 | 可跑，但 Linux kernel < 5.13 时没有 Landlock，只剩 rlimit/timeout |
| Linux 云 VM，有 nested virt / `/dev/kvm` | 可作为 K8s 节点；可接 Kata/Kuasar 等 RuntimeClass | 可跑，官方 quick start 要求 x86_64 Linux + KVM + Ubuntu 22.04+ | 可跑标准部署，要求 x86_64 Linux + KVM | 可跑，安全边界仍是进程级 |
| 裸金属 / bare metal | 可作为 K8s 节点，适合跑强隔离 runtime | 官方 benchmark 环境就是 KVM Linux 主机 | 官方支持 bare-metal 部署 | 可跑 |
| Managed K8s | 项目最匹配的部署形态 | 需要节点暴露 `/dev/kvm`、cgroup v2；GKE/EKS/AKS 通常要 metal SKU 或显式 nested virt | 不是原生 K8s 项目，使用自己的 CubeMaster/Cubelet；需要评估与现有 K8s 的边界 | 可以容器化部署，但没有 sandbox 级调度能力 |
| macOS 开发机 | 客户端/SDK 可用；服务端仍需要 Kubernetes/Linux 节点 | 官方 quick start 不是 macOS 路线 | 服务端要求 x86_64 Linux + KVM/PVM | 官方支持 macOS，但没有 Landlock |
| Windows | 服务端未见支持；需要 Linux/Kubernetes | 未见支持 | 未见支持 | 官方明确暂不支持 Windows |
| CentOS 8，本机现状 | 已实测 | 官方二进制因 glibc 2.28 不兼容；且无 `/dev/kvm` | 未实测；标准路径会被无 `/dev/kvm` 挡住，PVM 需要换内核 | 官方二进制 glibc 不兼容；源码构建成功，但 kernel 4.18 无 Landlock |

## 部署和编译难度

| 项目 | 部署难度 | 编译难度 | 当前机器观察 | 主要卡点 |
| --- | --- | --- | --- | --- |
| AgentCube | 中到高：需要 Kubernetes、CRD、Router、Workload Manager、Redis/Valkey 等组件 | 中：Go-first，`make build-all`；文档站另需 npm | 已部署并完成 CodeInterpreter 延迟实测 | 初学成本在 K8s 控制面和 CRD；强隔离还要准备 RuntimeClass |
| forkd | 在合适机器上中等：Ubuntu 22.04+、KVM、cgroup v2、Firecracker/rootfs/snapshot | 未本机源码构建；官方提供 release 二进制 | 当前机器官方二进制缺 `GLIBC_2.29` 到 `GLIBC_2.39`，且无 `/dev/kvm` | CentOS 8 glibc 太旧；云 VM 未暴露 VT-x/AMD-V；alpha 阶段缺多节点调度 |
| CubeSandbox | 中到高：root、Docker、KVM/PVM、模板构建、CubeMaster/Cubelet 等组件 | 官方 quick start 主打无需源码构建；源码未测 | 当前机器未跑；标准路径会被 `/dev/kvm` 挡住 | 需要 KVM 或 PVM 内核；PVM 路线需要换内核和重启，不适合随便在共享测试机上做 |
| cage-bro | 低到中：单二进制服务，`serve --port` 即可；浏览器能力另需 setup | 中：Rust + C++ 编译器 + dashboard npm build | 官方二进制 glibc 不兼容；安装 rustup、`gcc-c++`、dashboard 后源码构建成功 | CentOS 8 glibc 旧；kernel 4.18 缺 Landlock，安全能力降级 |

## 安全能力对比

| 安全维度 | AgentCube | forkd | CubeSandbox | cage-bro |
| --- | --- | --- | --- | --- |
| 计算隔离 | 当前实测是 Pod 隔离；可通过 RuntimeClass 接 Kata/Kuasar | 每个 child 是独立 Firecracker microVM | 每个 Agent 独立 guest OS kernel | 子进程 + Landlock/rlimit；共享内核 |
| 文件系统隔离 | 取决于 Pod spec、镜像、runtime 和 agent-sandbox 实现 | 子 microVM 独立文件系统/快照 | 模板和 microVM 文件系统；支持 snapshot/rollback | workspace 级；Linux Landlock 限制系统 allowlist 和 workspace |
| 网络隔离 | 取决于 Kubernetes NetworkPolicy / runtime / CNI | per-child netns；官方状态里 default-deny egress 仍是 production gap | CubeVS/eBPF 网络隔离和细粒度 egress policy | 项目自身不做网络隔离，交给外层 VM/容器/防火墙 |
| 资源限制 | Kubernetes resources、session timeout、max session duration | per-child cgroup v2 memory limit | Cubelet / sandbox 规格和资源池 | `rlimit` 限制内存、CPU time、文件大小、进程/fd 数 |
| API 认证 | PicoD 模式注入 Router 公钥，Router 用短期 JWT 代理请求 | REST bearer auth、audit log；早期版本有安全修复，官方建议升级 | 文档有本地 E2B API key 占位和认证章节；本表未深入验证 | README 强调 REST 可审计；未把 auth 当核心能力介绍 |
| 对抗代码适配 | 需要配置强隔离 runtime 才适合更高风险代码 | 适合强隔离需求，但仍依赖 hypervisor/kernel 安全 | 官方目标就是硬件级隔离运行 LLM 生成代码 | README 明确说不是 microVM，不应作为 adversarial code 的唯一边界 |

## 集群化和调度能力

| 项目 | 调度单位 | 集群支持 | 与 K8s 的关系 | 评价 |
| --- | --- | --- | --- | --- |
| AgentCube | `AgentRuntime` / `CodeInterpreter` 产生的 sandbox | 强，直接站在 Kubernetes 上 | 原生 CRD/controller，适合和 Volcano/K8s 调度体系结合 | 这是 AgentCube 的核心差异点 |
| forkd | 一个 host daemon/controller 内的 microVM child | 当前 alpha 缺官方 multi-node scheduler | 可把 forkd-controller 放进 Pod，但 K8s 不感知每个 child | 单机 fan-out 很强，集群调度还不是强项 |
| CubeSandbox | CubeMaster 调度 sandbox 到 Cubelet | 官方支持 multi-node cluster | 自带控制面，不依赖 K8s 调度每个 sandbox | 更像独立 sandbox 平台 |
| cage-bro | 一个本地 server 内的 workspace/sandbox | 无内置集群 | 可用 K8s 跑服务实例，但 sandbox 调度要自己做 | 适合作为工具层，不适合作为独立集群调度层 |

## 性能数据

### 官方数据

| 项目 | 官方性能数据 | 环境/口径 | 注意事项 |
| --- | --- | --- | --- |
| forkd | N=100 microVM spawn wall-clock `101 ms`；live BRANCH pause `56 ms p50 / 64 ms p90`；每 sandbox memory delta `0.12 MiB` | Ubuntu 24.04、Linux 6.14、20 vCPU、30 GiB、KVM；workload 是 `import numpy; numpy.zeros(5).tolist()` | 是 fork-from-warm，不等同于冷启动；项目状态 alpha |
| CubeSandbox | 单并发 cold start `60 ms`；50 并发 avg `67 ms`、P95 `90 ms`、P99 `137 ms`；内存开销 `<5 MB` | 官方 README 写明 cold start benchmarked on bare-metal | 需要 KVM/PVM；真实表现取决于模板、资源池和节点 |
| cage-bro | `~1 ms` init、`~100 MB` per sandbox、1c1g VM 上 `20+` sandboxes | 官方 README 和 Why not Docker 表 | 这是轻量进程工具运行时，不是 microVM |
| AgentCube | README 强调低延迟调度、warm pool；没有找到类似 forkd/CubeSandbox 的固定官方毫秒 benchmark | 本地源码/文档 | 因此本表主要用我们的 Day5 实测值 |

### 我们当前环境实测

| 项目 | 测试口径 | 顺序测试 | 并发测试 | 解读 |
| --- | --- | ---: | ---: | --- |
| AgentCube | `create session -> run print("ok") -> delete session`，`warmPoolSize=2`，普通 Pod 路径 | total p50 `177.14 ms`，min `91.95 ms` | 并发 10 total p50 `7315.21 ms`，min `188.42 ms` | warm pool 命中能到 100ms 级；并发 10 被 pool miss 和补池等待放大 |
| cage-bro | E2B lifecycle: `POST /sandboxes -> exec -> DELETE`，执行 `printf 'print("ok")\n' \| python3` | total p50 `18.41 ms` | 并发 10 total p50 `58.48 ms` | 很快，但隔离等级是 L1；本机 kernel 4.18 无 Landlock |
| forkd | 预检 | 未进入 benchmark | 未进入 benchmark | glibc 2.28 不兼容官方二进制；无 `/dev/kvm`，无法测 microVM |
| CubeSandbox | 未测 | 未测 | 未测 | 当前机器无 `/dev/kvm`，标准路径不适合；PVM 路线需要换内核 |

### 同机可比性说明

当前只有 AgentCube 和 cage-bro 是同机实测，但二者不是同隔离等级：

| 对比项 | AgentCube | cage-bro | 表面比例 | 是否公平 |
| --- | ---: | ---: | ---: | --- |
| 顺序 p50 total | `177.14 ms` | `18.41 ms` | cage-bro 约快 `9.6x` | 只反映当前机器和当前隔离模型，不代表同安全等级 |
| 并发 10 p50 total | `7315.21 ms` | `58.48 ms` | cage-bro 约快 `125x` | 不公平，AgentCube `warmPoolSize=2`，8 个请求发生 pool miss |

这个比例有参考意义：它说明进程级工具 runtime 的管理开销非常低，也说明 AgentCube 的并发突发测试必须把 warm pool 容量纳入变量。但不能据此得出 cage-bro 比 AgentCube “整体更好”，因为它们安全边界和调度目标不同。

## 选型结论

| 场景 | 优先看 | 原因 |
| --- | --- | --- |
| 要和 Kubernetes / Volcano 调度体系结合，管理大量 agent session 生命周期 | AgentCube | CRD、controller、Router、warm pool 都围绕 K8s 设计 |
| 要在单台强 KVM host 上做大规模 agent fan-out，并继承预热内存状态 | forkd | warm parent fork 是它的核心优势 |
| 要自建 E2B 替代服务，重视硬件隔离、E2B SDK 兼容和多节点 sandbox 服务 | CubeSandbox | 官方直接定位为 E2B-compatible KVM sandbox platform |
| 要快速给 agent 提供 shell/code/browser/files/MCP 工具，且可接受外层 VM/容器负责强安全边界 | cage-bro | 单 binary、REST/MCP、低启动成本、工具面完整 |

## 当前缺口和下一步

1. AgentCube 需要补一轮 `warmPoolSize=10` 的并发 10 测试，区分 pool 命中和 pool miss 的真实比例。
2. AgentCube 需要在有 Kata/Kuasar RuntimeClass 的节点上重测，得到 L3/L4 路径下的延迟和资源开销。
3. forkd 需要换到 Ubuntu 22.04+、Linux 新内核、cgroup v2、`/dev/kvm` 可用的机器上跑官方 quick start 和我们的最小 benchmark。
4. CubeSandbox 下一步先做 precheck：`/dev/kvm`、Docker、内存、磁盘、是否允许 PVM 换内核；如果当前云 VM 不适合，直接换 PVM/裸金属环境。
5. cage-bro 需要在 Linux kernel >= 5.13 的机器上重测，确认 Landlock 生效时的延迟变化；如果用于强风险代码，应放进 VM/microVM 内再测。
6. 后续补新竞品时沿用这张表的列：定位、隔离等级、OS/云支持、部署难度、安全边界、K8s/集群、API 兼容、性能、我们当前状态。

## 资料来源

AgentCube 本地源码和文档：

- `README.md`
- `pkg/apis/runtime/v1alpha1/codeinterpreter_types.go`
- `pkg/workloadmanager/workload_builder.go`
- `pkg/workloadmanager/codeinterpreter_controller.go`
- `docs/agentcube/docs/tutorials/python-sdk.md`
- `internship-reports/day5-sandbox-latency-and-competitor-analysis.md`
- `internship-reports/day6-forkd-competitor-benchmark-precheck.md`
- `internship-reports/day7-cage-bro-competitor-benchmark.md`

竞品官方资料：

- forkd README：<https://github.com/deeplethe/forkd>
- forkd Kubernetes manifest 说明：<https://github.com/deeplethe/forkd/tree/main/packaging/k8s>
- CubeSandbox README：<https://github.com/TencentCloud/CubeSandbox>
- CubeSandbox PVM deployment：<https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/pvm-deploy.md>
- CubeSandbox bare-metal deployment：<https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/bare-metal-deploy.md>
- cage-bro README：<https://github.com/aeroxy/cage-bro>
