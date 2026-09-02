# Day 53：云原生 Agent Harness Infrastructure 调研

- 资料发布日期：2026-05-09
- 整理日期：2026-09-02
- 调研角色：AgentCube 项目实习生
- 调研对象：[《云原生 Agent 托管的高效范式：Agent Harness Infra 体系化设计》](https://bbs.huaweicloud.com/blogs/477318)

## 调研背景

原稿按“挑战、产品方案、未来规划、总结”的顺序复述了华为云社区文章，能够说明方案包含哪些模块，但没有区分文章中的架构描述、性能数字、未来目标和本地验证结果。读者容易把“资料中提出的能力”直接理解成“我已经验证的能力”。

这次整理不再做产品介绍，而是站在 AgentCube 实习生的角度回答四个问题：

1. 云原生 Agent 托管真正涉及哪些不同层次的工程问题？
2. 原始资料分别用什么机制处理调度、恢复、隔离和启动速度？
3. 资料中的性能数字能够支持什么结论，还缺少哪些验证信息？
4. 这些思路和 AgentCube 当前的 Workload Manager、Router、warm pool、Kubernetes 调度及后续 Sleep/Resume 方向有什么关系？

> 注释：本文把 `Agent Harness` 理解为协调模型、工具和任务执行的上层运行逻辑，把 `Sandbox` 理解为承载不可信代码或工具进程的隔离执行环境。两者可以部署在同一系统中，但故障状态、安全边界和扩缩容单位并不相同。

## 结论先行

1. 原始资料适合作为一组架构假设和性能目标，不能单独作为生产效果证明。文章列出了多项百分比、时延和规模数字，但没有同时给出测试版本、硬件、工作负载、样本量、统计口径或原始数据。
2. 方案的核心不是单一的“microVM 加速”，而是容量预测与预热、Harness 与 Sandbox 解耦、microVM 隔离、轻量 Guest OS、snapshot/Fork/lazy loading、镜像块级分发六类机制的组合。每类机制解决的对象不同，不能用一个启动时延代表整条请求链。
3. `SessionID + 外置日志 + 重放` 解决的是路由一致性和应用级任务恢复，不等于保存进程内存、文件描述符或 VM 设备状态。要宣称“断点续传”，还需要说明副作用幂等、日志提交点和重放边界。
4. microVM 可以加强不可信代码与宿主机之间的隔离，但不会自动解决凭据泄露、出站访问、镜像供应链、租户授权和审计。凭据是否进入 Guest、谁可以访问 endpoint、请求如何绑定用户身份仍需单独设计。
5. 对 AgentCube 最有价值的启发是继续分开 request routing、sandbox lifecycle、cluster placement 和 node-local runtime 四层，并为 cold create、warm claim、snapshot resume 和 first execution 分别定义指标，而不是直接接受“100 ms 启动”这一合并口径。

## 调研方法与证据边界

### 资料来源

本次使用以下资料：

- 华为云社区文章：[《云原生 Agent 托管的高效范式：Agent Harness Infra 体系化设计》](https://bbs.huaweicloud.com/blogs/477318)，网页署名作者为 Rain Zhang、Qi Zhang、Jian Huang；网页发布日期为 2026-05-09。原本地稿标注 2026-05-08，本文以可核验的网页日期为准。
- CNCF 项目页：[Kuasar](https://www.cncf.io/projects/kuasar/)，用于确认 Kuasar 于 2023-12-19 进入 CNCF Sandbox 阶段。
- Kuasar 开源仓库：[kuasar-io/kuasar](https://github.com/kuasar-io/kuasar)，用于确认它是基于 containerd Sandbox API 的多沙箱容器运行时，并支持以 Cloud Hypervisor 等 VMM 承载 microVM sandbox。
- 本地 AgentCube 学习记录：[Day 1](./day1-getting-started.md)、[Day 21](./day21-opensandbox-agent-substrate-study.md)、[Day 44](./day44-sandbox-pool-management-proposal-review.md)、[Day 56](./day56-sandbox-operator-agent-sandbox-platform-study.md)、[Day 59](./day59-kvcache-ai-agentenv-kubernetes-boundary-study.md) 和 [Day 60](./day60-volcano-kthena-architecture-and-project-study.md)。

华为云社区网页同时声明，文章内容来自社区博主，不代表平台观点。原文正文没有给出性能测试脚本、原始结果或可定位的实现版本，因此本文把这些数字归类为“来源主张”，不写成本地实测。

### 证据标签

| 标签 | 本文含义 | 可以支持的表述 |
| --- | --- | --- |
| 来源主张 | 原始文章直接给出的架构或数字 | “文章提出”“资料宣称” |
| 本地既有证据 | 之前报告中的源码阅读、命令结果或集群验证 | 写明对应报告和验证边界 |
| 分析 | 根据两类资料做出的工程推导 | “我的分析是”“需要进一步验证” |
| 未验证 | 当前没有源码、环境、日志或原始数据 | 不写成已实现、已通过或已达到 |

### 本轮没有执行的验证

- 没有获得文章所述托管 Agent Harness 的源码、部署清单或 benchmark 工具。
- 没有获得容量预测模型、分片调度器、On-the-fly OS、镜像分发底座的具体版本和配置。
- 没有在相同硬件上复现 microVM 创建、Snapshot 恢复、Fork 或每分钟十万级创建。
- 没有验证“200 多家公司使用”对应的是 Volcano、某个沙箱调度组件还是完整 Agent Harness 方案。
- 当前报告只完成资料审阅和 AgentCube 架构对照，不包含新的运行时测试结果。

## 问题拆解：原稿中的三个“痛点”并不是三个单一问题

| 调研问题 | 用户可观察现象 | 实际涉及的状态或资源 | 原始资料提出的机制 | 需要继续追问 |
| --- | --- | --- | --- | --- |
| 冷启动与资源浪费 | 首次请求等待时间长；空闲时预热资源占用高 | 镜像、Guest OS、网络、存储、sandbox 实例、预热池容量 | 容量预测、分片调度、资源预置、snapshot、Fork、分层预热 | 时延从哪个开始点量到哪个结束点？预热成本是否计入？ |
| 长任务恢复 | Harness 或 Sandbox 故障后任务中断 | 会话路由、任务事件、workspace、进程内存、外部副作用 | `SessionID` 亲和、日志外置、日志重放 | 恢复的是会话、文件、进程还是业务步骤？重复执行是否安全？ |
| 不可信代码与凭据 | 代码越权、密钥泄露、横向移动 | Host kernel、Guest kernel、网络、endpoint、credential、tenant identity | microVM、Harness/Sandbox 分离、最小权限、凭据托管 | 凭据是否仍进入 Guest？出站访问由谁拦截和审计？ |

### 冷启动需要分阶段定义

“Sandbox 启动”至少可能包含以下阶段：

1. API 接收创建请求。
2. 控制面完成容量选择或 Node placement。
3. 镜像、内核、rootfs 和网络资源准备完成。
4. VMM 进程创建，Guest kernel 启动。
5. Guest 内执行服务开始监听。
6. Router 获得 endpoint 并完成第一条真实命令。

如果 benchmark 只测第 4 步，不能推导用户看到的端到端 first execution latency。warm claim、snapshot resume 和完全 cold create 也必须分开报告。

> 注释：`cold create` 表示没有可复用实例或本地缓存时从头创建；`warm claim` 表示从预热池领取已经准备好的实例；`snapshot resume` 表示从已保存的运行状态恢复。三者消耗的资源和保证的状态不同，不能放在同一列直接比较。

### “上下文遗忘”和“沙箱故障”属于不同故障域

原文把大模型上下文窗口有限、长任务“遗忘”和 Sandbox 故障放在同一段。两者确实都会让任务失败，但恢复机制不同：

- 上下文窗口问题发生在模型与 Agent 协调层，需要记忆压缩、外部任务状态或重新规划。
- Sandbox 故障发生在执行层，需要重建环境、恢复 workspace、进程或 VM 状态。
- Harness 故障发生在协调进程，需要恢复任务图、工具调用记录和路由状态。
- 外部 API 已产生的副作用还需要幂等键、事务日志或补偿动作。

因此，“重放会话日志”只有在任务步骤可重入、外部副作用可识别、日志提交点明确时，才能接近应用级断点续传。它不能自动恢复被中断进程的内存现场。

## 原始方案的分层分析

### 1. 容量预测与并行调度

原始资料提出：

- 对 Agent 资源做画像和预热管理；
- 相比传统时序算法，预测拟合精度提高 30%，资源碎片率降低 25%，利用率提高 10%；
- 调度考虑资源碎片率、资源余量和预热分配量，并通过分片并行调度把吞吐量提高到 5 倍；
- Volcano 沙箱调度器生态有 200 多家公司参与使用。

这些数字说明作者关注容量和调度成本，但缺少以下信息：

- 预测对象是 CPU、内存、GPU、Sandbox 数还是请求率；
- “拟合精度”使用什么指标，基线算法和训练窗口是什么；
- “资源碎片率”和“利用率”按 Node、集群还是租户统计；
- 5 倍吞吐量对应的并发、队列长度、调度成功率和 p99 延迟；
- 200 家公司的统计对象、时间点和采用深度。

> 分析：这里至少存在两种不同的调度。Volcano 或 kube-scheduler 处理 `Pod -> Node` placement；warm pool 或 SandboxPool 处理“预建多少实例、把哪个 ready sandbox 分给哪个 session”。两者都可能使用队列和打分，但输入对象、输出决策和状态所有者不同。Day 60 已记录这一边界，不能因为都叫 scheduler 就合并成一个能力。

### 2. Harness 与 Sandbox 解耦及恢复

原始资料提出用 microVM 将 Harness 协调层和 Sandbox 执行层分开，并通过以下组合恢复任务：

- `SessionID` 保证多轮请求路由到同一实例；
- 会话日志外置持久化；
- Harness 故障后由新实例重放日志。

这组设计包含四个不同层次：

| 层次 | 可恢复对象 | 原始资料是否明确 |
| --- | --- | --- |
| 路由绑定 | `SessionID -> Sandbox endpoint` | 有描述 |
| 协调状态 | 对话、工具调用和任务步骤日志 | 有描述，但日志格式和提交点未知 |
| 文件状态 | workspace、rootfs、挂载卷 | 未说明 |
| 运行状态 | 进程内存、文件描述符、socket、VM 设备状态 | 未说明 |

我的判断是：这段资料能够支持“方案考虑了路由亲和与日志恢复”，不能直接支持“任意长任务可无损断点续传”。进一步验证至少需要 Harness 崩溃、Sandbox 崩溃、Node 故障和外部 API 已成功但日志未提交四类测试。

### 3. microVM 安全隔离

原始资料提出使用 Cloud Hypervisor 作为 VMM，以定制 Guest 和动态资源控制实现 VM 级隔离，并给出“每 VM 进程开销 3-13 MiB、单节点数千并发 Sandbox”的描述。

microVM 的直接价值是减少不可信 Guest 与 Host 共用内核的范围，但完整安全边界仍包括：

- 谁可以创建、访问、续期和删除 Sandbox；
- Router 是否把 tenant identity 绑定到 session 和 endpoint；
- credential 是注入 Guest、由 sidecar 代理，还是由外部 vault 按请求签发；
- Sandbox 的 DNS、IP、FQDN 和跨租户流量如何限制；
- Guest image、kernel、VMM 和 snapshot 如何升级、签名和审计；
- snapshot、共享只读页和跨租户块复用是否引入数据残留或侧信道风险。

> 注释：VMM（Virtual Machine Monitor）负责创建和管理虚拟机。microVM 减少设备模型和启动开销，但“设备更少”不等于“所有安全问题已解决”；身份、凭据、网络和供应链仍位于 VMM 之外或跨越 VMM 边界。

Day 21 对 OpenSandbox 的调研说明，credential vault、egress policy 和 RuntimeClass 之间存在真实兼容边界。AgentCube 后续如果引入 microVM，也需要把这些能力放进 E2E 测试矩阵，而不能只验证 Pod 或 VM 已进入 `Ready`。

### 4. 轻量 Guest OS 与不可变基础设施

原始资料提出 `ContainerOS + On-the-fly OS` 组合：基础系统只保留运行容器所需服务，增量系统按 Agent 需求生成；根文件系统只读，并以镜像为粒度升级和回滚。资料同时给出空载内存低于 50 MB 和秒级启动的描述。

这里需要进一步区分：

- 50 MB 是 Guest 内存、Host 侧 VMM RSS/PSS，还是两者之和；
- 是否包含 page cache、共享页、virtiofsd、网络和存储进程；
- “秒级启动”是完全 cold boot，还是本地已有 kernel/rootfs 的 Guest boot；
- 动态生成 OS 的缓存键、可复现构建、漏洞扫描和回滚单位；
- 不同 Agent 依赖导致多少镜像变体和缓存碎片。

不可变 rootfs 有利于回滚和减少运行时漂移，但 Agent 任务通常仍需要可写 workspace。报告后续应明确只读系统层和用户数据层的分界，以及删除 Sandbox 时 workspace、snapshot 和日志分别如何回收。

### 5. Snapshot、Fork、UFFD 与预热池

原始资料把资源预置、OS 裁剪、共享内存、snapshot、Fork 和组件预热组合起来，并提出实例创建从十秒级缩短到 100 ms。工作展望又提出：

- 以 Kuasar 为底座构建单 VM 单应用的 Appliance Sandbox，目标是单 Sandbox 底噪降低 20%；
- 扩展 VMM，使用 `userfaultfd`（UFFD）处理缺页，实现内存 lazy loading；
- 把 SnapStart 作为 Kuasar 的标准启动方式，目标是单 Sandbox 启动小于 100 ms；
- 复用 VM 内存只读页以降低资源消耗。

> 注释：UFFD 是 Linux `userfaultfd` 机制的常见缩写。它允许用户态程序参与处理内存缺页，因此可以先恢复少量关键页，再按访问需要加载其余 snapshot 页面。这样可能缩短“开始运行”的时间，但会把部分成本推迟到后续 page fault，首条真实任务的尾延迟仍需单独测量。

这部分还要区分当前能力和未来目标。文章第 3 节标题为“工作展望”，其中的 20%、小于 100 ms 和每分钟十万级创建不应与第 2 节描述的现有方案状态合并。

### 6. 镜像块级分发与跨租户复用

原始资料提出基于内容寻址和块级复用的镜像分发底座：相同指纹的数据块跨租户复用，不同数据按租户隔离并全链路加密；目标负载为连续 10 分钟、每分钟创建 10 万个 Sandbox，并给出同构工作负载下存储和带宽缩减 10 倍的描述。

该方向可能降低重复镜像和 snapshot 的网络成本，但验证时必须同时记录：

- 镜像与 snapshot 的平均大小、相似度和块大小；
- 冷缓存、热缓存和跨 Node 缓存命中率；
- registry、对象存储和 Node 网络带宽；
- 加密前后去重顺序、租户密钥边界和元数据泄露风险；
- 创建成功率、p95/p99 延迟、失败重试和垃圾回收积压；
- “10 倍缩减”是相对不去重、文件级去重还是某个现有分发系统。

没有这些字段时，10 倍数字只能作为同构工作负载下的来源主张，不能外推到依赖高度异构的 Agent 任务。

## 性能与规模主张审计

| 来源主张 | 原文语境 | 当前证据等级 | 独立验证至少需要 |
| --- | --- | --- | --- |
| 预测拟合精度提高 30% | 当前方案描述 | 来源主张，未验证 | 指标定义、基线、数据集、时间窗口 |
| 资源碎片率降低 25%，利用率提高 10% | 当前方案描述 | 来源主张，未验证 | 资源维度、集群规模、负载分布、采样周期 |
| 调度吞吐量提高到 5 倍 | 当前方案描述 | 来源主张，未验证 | 并发、成功率、队列延迟、scheduler 数量和基线 |
| 200 多家公司参与使用 | 生态描述 | 对象不明确 | 统计口径、时间点、使用的具体项目或组件 |
| 每 VM 进程开销 3-13 MiB | microVM 描述 | 来源主张，未验证 | RSS/PSS/Guest memory 口径、VMM 版本和设备配置 |
| 空载内存低于 50 MB | 轻量 OS 描述 | 来源主张，未验证 | Host/Guest 边界、共享页和辅助进程是否计入 |
| 实例创建从十秒级缩短到 100 ms | 启动优化描述 | 来源主张，未验证 | 起止点、cold/warm/resume 分类、percentile、样本数 |
| 预热命中率达到 80% | 预热策略描述 | 原文分母表述不清 | 请求总量、cold request 占比、预测窗口和误命中成本 |
| 单 Sandbox 底噪降低 20% | 工作展望 | 目标 | 底噪指标、基线 runtime、Host/Guest 资源口径 |
| 单 Sandbox 启动小于 100 ms | 工作展望 | 目标 | snapshot 类型、page-fault 尾延迟和 first execution |
| 连续 10 分钟每分钟创建 10 万个 Sandbox | 工作展望 | 目标负载 | 100 万实例的成功率、生命周期、节点数和清理结果 |
| 存储和带宽缩减 10 倍 | 同构工作负载描述 | 来源主张，未验证 | 数据相似度、块大小、缓存、加密和对照系统 |

> 分析：指标审计不是否定这些数字，而是把它们转换成可复现问题。对实习生而言，能够指出“缺哪个分母、哪个基线、哪个结束点”，比复述“提升多少倍”更接近工程调研。

## 与 AgentCube 当前架构的对照

### 现有责任边界

根据 Day 1 以及后续源码调研，AgentCube 当前主要分工为：

- Workload Manager：把 CodeInterpreter 或 AgentRuntime 请求转换成 Sandbox、SandboxClaim 等生命周期操作，并处理创建、删除、超时和回收。
- Router：根据 session 信息把请求转发到正确的 Sandbox endpoint。
- Redis/store：保存 session、owner、endpoint 和过期等共享状态。
- `kubernetes-sigs/agent-sandbox`：提供 Sandbox、SandboxTemplate、SandboxWarmPool、SandboxClaim 等底层资源和 controller 能力。
- Kubernetes scheduler 或显式选择的其他 scheduler：负责 Pod 到 Node 的 placement。

这与原始资料有可比较的结构，但不能据此推断两套系统实现相同。

| 原始资料关注点 | AgentCube 当前对应能力 | 当前差距或待确认问题 |
| --- | --- | --- |
| `SessionID` 路由亲和 | Router + store 维护 session 到 endpoint | store 重建不等于任务日志重放；恢复语义仍需设计 |
| Harness 与 Sandbox 解耦 | Workload Manager/Router 与 Sandbox/PicoD 分层 | Harness 任务图、外部副作用和 checkpoint 不在当前 Sandbox 生命周期模型内 |
| 预热与快速分配 | SandboxWarmPool + SandboxClaim | 需要分别测 pool refill、claim adoption、endpoint Ready 和 first execution |
| 并行调度与资源画像 | Kubernetes placement；Agent Scheduler 可选 | Pod placement 与 warm-pool allocation 是不同 loop；预测模型未建立 |
| microVM 隔离 | runtime 由 Kubernetes、agent-sandbox 和 RuntimeClass 边界承载 | AgentCube 控制面没有固定某个 VMM；credential、egress 和 audit 仍需跨层设计 |
| Snapshot/Fork/lazy loading | 当前主线主要是 create/delete/warm reuse | Sleep/Resume 要先选择 rootfs、process、VM snapshot 或 log replay 的状态等级 |
| 块级镜像分发 | 依赖现有 image/registry/runtime 路径 | 没有对应的跨租户块级分发和一致性模型 |

### 四层模型

结合 Day 44、Day 59 和 Day 60，更适合 AgentCube 的分析框架是：

| 层 | 输入与输出 | 当前主要所有者 | 原始资料中的对应机制 |
| --- | --- | --- | --- |
| Request routing | request/session -> ready endpoint | AgentCube Router + store | `SessionID` 亲和 |
| Sandbox lifecycle | intent/pool -> create/claim/delete；pause/resume 待设计 | Workload Manager + agent-sandbox controller | 预热池、日志恢复、idle reclaim |
| Cluster placement | Pod/coarse worker -> Node | kube-scheduler 或显式 scheduler | 容量预测、分片调度、Volcano 相关描述 |
| Node-local runtime | instance -> process/container/microVM handle | container runtime、VMM 或未来 node agent | Cloud Hypervisor、Kuasar、Snapshot/Fork/UFFD |

这个模型说明，Volcano 可以参与全局资源策略和 Pod placement，但不会自动提供 VM snapshot、session routing、凭据代理或 Sandbox 内 command/file API。反过来，node-local microVM runtime 也不能替代 Kubernetes 中的租户策略、全局容量和声明式审计。

### 对 AgentCube 后续工作的具体启发

1. **先定义操作，再设置性能目标。** 分别定义 cold create、warm claim、snapshot resume 和 first execution，报告 p50/p95/p99、成功率和资源成本。
2. **先定义状态等级，再设计 Sleep/Resume。** 明确只保留 workspace、保存 rootfs、保存进程内存，还是保存完整 VM 状态；Router 必须知道何时可以安全地 resume-before-proxy。
3. **把 credential 放到独立安全边界审查。** 即使采用 microVM，也要回答密钥是否进入 Guest、外部 API 请求如何代理、tenant identity 如何绑定和日志如何脱敏。
4. **分开 slow global policy 与 node-local fast path。** Kubernetes 可以保存 pool intent、quota 和审计，Node 可以保存高频 runtime truth；但两层之间必须有失效检测、对账和恢复规则。
5. **把性能数字绑定到固定版本和环境。** 任何“100 ms”“5 倍”“10 倍”都应能定位到 commit、manifest、硬件、负载、脚本和原始日志。

## 实习生视角的学习记录

从原稿可以看出，我第一次整理这份资料时主要做了“把文章内容完整复述出来”，因此保留了较多“极致、高效、完整方案”一类产品表达，也直接重复了性能数字。经过 AgentCube 的 warm pool、agent-sandbox 升级、SandboxPool proposal、竞品源码和 benchmark 边界调研后，我对这类资料的阅读方式发生了四点变化。

### 1. 从记功能转向找状态所有者

看到“调度、恢复、路由”时，我现在会先问：调度的对象是 request、session、Sandbox 还是 Pod；恢复的状态在日志、Redis、Kubernetes CRD、Node 本地还是 snapshot；组件重启后以谁为准。这个问题比先记住组件名称更能解释故障路径。

### 2. 从接受结果转向审计指标口径

“100 ms 启动”只有在操作、起止点、缓存状态、percentile 和环境确定后才可比较。Day 56 已经说明，warm claim latency、fleet fill 和用户 ready-to-execute 是不同操作。本报告据此把原文数字逐项转成待验证字段。

### 3. 从“用了 microVM 所以安全”转向检查完整信任边界

运行时代码隔离只是安全的一层。用户身份、session ownership、Router 鉴权、credential 注入、egress、镜像和 snapshot 数据都可能跨越 microVM 边界。后续 review 需要沿请求链检查这些边界，而不是只确认 VMM 类型。

### 4. 从照搬竞品方案转向识别可迁移的设计原则

华为云社区文章、Kuasar、AgentENV、OpenSandbox 和 AgentCube 的实现边界不同。可以迁移的是“分层、状态归属、操作定义、证据分级”这些方法，不能因为某个系统宣称 100 ms 或十万级创建，就直接把同一指标设为 AgentCube 的已承诺能力。

> 分析：实习阶段的调研价值不只是收集更多名词，而是把外部方案转成项目可以评审、实现和测试的问题。最终结论应能说明“哪些已确认、哪些只是来源主张、下一步如何验证”。

## 建议的验证计划

如果后续能够获得对应实现或可部署版本，建议按以下顺序验证。

### 阶段一：固定输入

- 固定源代码 commit、VMM、Guest kernel/rootfs、containerd/Kuasar 和控制面版本。
- 保存 manifest、feature gate、pool size、snapshot 格式和镜像摘要。
- 记录 OS、kernel、glibc、CPU/vCPU、内存、磁盘、网络、NUMA、虚拟化标志及 `/dev/kvm` 权限。

### 阶段二：功能闭环

- cold create -> endpoint Ready -> first command -> delete。
- warm claim -> session reuse -> idle reclaim -> pool refill。
- Harness restart -> session route 恢复 -> 日志重放。
- Sandbox/Node failure -> 状态失效 -> 重建或失败返回。
- credential、egress、tenant ownership 和 audit 的正向与拒绝路径。

### 阶段三：性能分层

| 操作 | 主要指标 | 必须单独记录的成本 |
| --- | --- | --- |
| cold create | accepted-to-ready、first execution p50/p95/p99 | 镜像拉取、Guest boot、网络和服务 bootstrap |
| warm claim | claim-to-bound、claim-to-ready、first execution | 预热池常驻 CPU/内存、refill 延迟 |
| snapshot resume | resume-to-ready、first execution、page-fault tail | snapshot 存储、传输、预取和 lazy loading |
| high concurrency | throughput、success rate、queue latency | scheduler CPU、API/etcd write、Node imbalance |
| image distribution | bytes transferred、cache hit、GC backlog | registry/object storage、加密和去重元数据 |

### 阶段四：故障与一致性

- 在日志提交前后分别终止 Harness，检查任务是否丢失或重复执行。
- 在 claim、route binding、Sandbox Ready 各阶段终止控制面或 Node，检查真相来源和清理。
- 让 snapshot repository、Redis/store、registry 或 webhook 短暂不可用，检查 fail-open/fail-closed 和重试上限。
- 完成测试后确认 Sandbox、VM、网络、volume、snapshot、route binding 和预热池均被清理或恢复到原设置。

## 局限与未解决问题

- 原始文章没有公开托管 Agent Harness 的完整代码和 benchmark artifact，本报告无法检查实现是否与架构图一致。
- Kuasar 开源仓库可以验证运行时方向，但不能替代对文章所述华为云内部调度、OS 生成和分发系统的验证。
- 本报告没有可用的目标 microVM fleet，也没有执行 KVM runtime benchmark。
- “预热命中率达到 80%”的原文分母表述不清，本文未自行修正为另一个指标。
- 资料没有说明日志重放的幂等、外部副作用和 exactly-once/at-least-once 语义。
- 资料没有给出多租户块复用与独立加密同时成立时的密钥和去重边界。
- AgentCube 对照是架构层分析，不表示两个系统已经完成接口兼容或可以直接替换。

## 最终判断

这份资料的价值在于展示了云原生 Agent 托管可能需要同时处理的六类问题：容量、调度、恢复、隔离、启动和分发。原稿的问题不是信息不足，而是把来源主张、未来目标和已验证事实写在了同一个肯定语气中。

从 AgentCube 实习工作的角度，更可靠的结论是：原始方案提供了值得继续研究的架构方向，但所有性能与规模数字都需要绑定固定版本、操作定义、环境和原始结果。AgentCube 后续不应简单追求一个“100 ms Sandbox”指标，而应先明确四层状态所有者和恢复边界，再分别验证 warm reuse、Sleep/Resume、node-local runtime、credential/egress 和全局调度的实际收益与故障成本。
