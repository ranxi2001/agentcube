# 实习生术语扫盲

日期：2026-06-23

这份文件用于沉淀 AgentCube 实习过程中反复遇到的工程术语。目标不是写百科，而是让以后读 PR、issue、设计文档和源码时，能快速知道一个词大概在系统里承担什么角色。

> 使用方式：先按等级读。L0 / L1 是读懂文档的最低前置；L2 / L3 是理解 sandbox lifecycle、Sleep/Resume、agent-sandbox 适配的核心；L4 用于做 review、测试设计、benchmark 和安全分析。
>
> 更新规则：如果一个术语在日报、PR review、设计文档里反复出现，或者不解释就会影响判断，应补到这里。解释要优先回答“它是什么、为什么在 AgentCube 里重要、容易误解什么”，不要只翻译英文。

## L0：先能读懂项目文档

这一层是进入 AgentCube / OpenSandbox / Agent Substrate 文档前必须先熟悉的词。

| 术语 | 简明解释 | 在本项目里的意义 |
| --- | --- | --- |
| API | 系统对外或对内暴露的调用接口 | WorkloadManager、Router、OpenSandbox Server、Agent Substrate `ate-api-server` 都通过 API 协作 |
| SDK | 给开发者使用的语言库 | Python SDK / Go SDK 让用户不用直接拼 HTTP 请求 |
| CLI | 命令行工具 | 例如 `osb`、`kubectl-ate`，用于手工创建、查询、删除资源 |
| MCP server | Model Context Protocol server，用于把工具能力暴露给 LLM/agent | OpenSandbox 支持 MCP，说明它不只是容器平台，也想接入 agent 工具生态 |
| endpoint | 可访问地址或服务入口 | Router 最终要代理到 sandbox endpoint；resume 后 endpoint 可能变化 |
| entrypoint | 进入某个 workload 的具体入口信息 | AgentCube store 里保存的 endpoint/entrypoint 必须和当前 sandbox 状态一致 |
| FastAPI | Python Web 框架 | OpenSandbox Server 使用 FastAPI 做生命周期控制面 |
| REST / HTTP JSON | 用 URL + HTTP method 操作资源，数据常用 JSON | 适合 SDK、CLI、外部用户入口，容易用 curl/debug |
| gRPC | 强类型远程函数调用框架，常配合 protobuf | 适合内部控制面调用，例如 `ResumeActor`、`SuspendActor` |
| protobuf / proto | `.proto` 文件定义的数据结构和 RPC 契约 | 读 Agent Substrate 的 `ateapi.proto` 能看到真实生命周期 API |
| WebSocket | 双向长连接 | 适合浏览器终端、实时交互、持续输出 |
| SSE | Server-Sent Events，服务端单向事件流 | 适合日志流、状态进度流，比 WebSocket 简单 |
| command API | 执行命令的接口 | 例如让 sandbox 执行 `python -c 'print(2)'` |
| file API | 文件读写接口 | 用于验证 workspace / rootfs 是否在 resume 后保留 |
| PTY | pseudo-terminal，伪终端 | 支持交互式 shell、REPL、彩色输出、光标控制 |
| code execution | 更高层的代码执行接口 | 不只是 shell command，可能直接提交一段 Python/JS 代码 |
| metrics | 运行指标 | 用于观察 CPU、memory、请求耗时、sandbox 健康状态 |

> 注释：REST 更像“操作资源”，例如 `GET /sessions/123`；gRPC 更像“调用函数”，例如 `ResumeActor(session_id)`。AgentCube 当前外部入口更适合 REST/HTTP，内部 Sleep/Resume 控制面可以先把契约设计清楚，不必急着全面 gRPC 化。

## L1：Kubernetes 与控制面基础

这一层用于读 AgentCube、agent-sandbox、OpenSandbox Kubernetes provider 和 Agent Substrate controller。

| 术语 | 简明解释 | 在本项目里的意义 |
| --- | --- | --- |
| Kubernetes / K8s | 容器编排系统 | AgentCube 是 Kubernetes-native 项目，大部分 runtime 生命周期落在 K8s 上 |
| Pod | Kubernetes 最小调度单元 | sandbox 最终通常对应一个或多个 Pod |
| Namespace | Kubernetes 资源隔离空间 | e2e、AgentCube 组件、agent-sandbox CRD 常在特定 namespace 下运行 |
| CRD | Custom Resource Definition，自定义 Kubernetes 资源类型 | `Sandbox`、`SandboxWarmPool`、`BatchSandbox`、`WorkerPool` 都是或类似 CRD |
| CR | Custom Resource，某个 CRD 的具体实例 | 一个 `Sandbox` 对象就是一个 CR |
| controller | 持续观察资源并让实际状态接近期望状态的控制器 | agent-sandbox controller、OpenSandbox controller、Agent Substrate controller 都是这个模式 |
| reconcile | controller 的核心循环：比较期望状态和实际状态并修正 | patch CRD 后通常不是马上完成动作，而是等 reconcile |
| etcd | Kubernetes API server 背后的持久存储 | 低频配置适合放 K8s/etcd，高频 session 状态未必适合 |
| ownerReference | Kubernetes 资源之间的归属关系 | e2e 里判断 warm pool Pod 属于哪个 Sandbox/SandboxWarmPool 会用到 |
| generated client | 根据 API types 自动生成的 Kubernetes typed client | 改 CRD/API type 后通常要跑 codegen |
| codegen | 生成 DeepCopy、client-go、CRD 等代码的流程 | PR #387 里 codegen 版本和依赖解析会影响 generated files |
| Helm chart | Kubernetes 应用打包模板 | AgentCube / OpenSandbox 部署会涉及 chart values |
| operator | controller + CRD 组合出来的自动化运维系统 | OpenSandbox Kubernetes controller、agent-sandbox 都可以按 operator 思路理解 |
| kind | Kubernetes in Docker，本地 K8s 测试工具 | Agent Substrate quickstart 曾卡在 kind/kubeadm bootstrap |
| k3s | 轻量 Kubernetes 发行版 | AgentCube 本机 runtime 验证曾使用已有 k3s |
| GKE | Google Kubernetes Engine，托管 Kubernetes | Agent Substrate 更适合在干净 GKE 或 cgroup v2 VM 上验证 |
| RuntimeClass | Kubernetes 指定容器 runtime 的方式 | 让某些 Pod 使用 gVisor、Kata 等 secure runtime |
| NetworkPolicy | Kubernetes 网络访问控制资源 | 控制 Pod 间或出入站访问，AgentCube 适配时要避免 Router 到 sandbox 被阻断 |

> 注释：CRD 是“声明式资源”，不是同步函数调用。写入 `spec.pause=true` 只表示“我希望它暂停”，真正 pause 是否完成要看 controller reconcile 后的 `status`。

## L2：Sandbox 与 runtime 基础

这一层用于理解“sandbox 到底怎么运行”，以及为什么不同 runtime 会影响安全、性能和兼容性。

| 术语 | 简明解释 | 在本项目里的意义 |
| --- | --- | --- |
| sandbox | 隔离执行环境 | Agent 代码、用户代码、工具调用都在 sandbox 中运行，降低风险 |
| runtime | 真正启动和管理容器/沙箱的底层实现 | Docker、containerd、runc、gVisor、Kata 都属于相关 runtime 体系 |
| runc | 常见 OCI 容器 runtime | 普通容器路径，兼容和性能较好，隔离强度主要依赖 Linux 内核机制 |
| OCI runtime | 符合 Open Container Initiative 规范的 runtime | `runc`、gVisor 的 `runsc` 都可按 OCI runtime 理解 |
| OCI image | 标准容器镜像格式 | OpenSandbox rootfs snapshot 会 commit 成 OCI image |
| image | 容器镜像 | 冷启动慢可能只是 image 没缓存，需要从 registry 拉取 |
| registry | 镜像仓库 | Docker Hub、私有 registry；镜像拉取速度会影响 benchmark |
| rootfs | 容器根文件系统 | rootfs snapshot 只保存文件系统，不保存进程内存 |
| workspace | 用户工作目录或会话文件空间 | 第一版 Sleep/Resume 通常可先保证 workspace 保留 |
| container | 由镜像启动的隔离进程环境 | sandbox 通常以容器或更强隔离 runtime 形式运行 |
| namespace | Linux 隔离机制，隔离进程、网络、挂载等视图 | 普通容器隔离的基础之一 |
| cgroup | Linux 资源限制和统计机制 | 限制 CPU/memory，kind/kubelet 问题常和 cgroup 环境相关 |
| seccomp | Linux syscall 过滤机制 | 普通容器增强隔离的手段之一 |
| syscall | 应用请求内核服务的接口 | gVisor 通过拦截/模拟 syscall 减少直接碰宿主机内核 |
| gVisor | 用户态内核 sandbox runtime | 比 runc 隔离更强，可参与 checkpoint/restore，但有兼容和性能成本 |
| runsc | gVisor 的 OCI runtime | Agent Substrate 通过 `runsc` 做 checkpoint/restore |
| Kata | 把容器放进轻量虚拟机的 runtime | 隔离更接近 VM，成本通常比 runc/gVisor 更高 |
| Firecracker | 轻量 VMM | Kata-FC 路线用 Firecracker 做底层虚拟机管理 |
| Kata-FC | Kata + Firecracker 组合路线 | 在隔离强度和启动/资源成本之间折中 |
| CNI | Container Network Interface，K8s 网络插件规范 | FQDN policy、NetworkPolicy、Pod 网络连通都可能依赖 CNI |
| iptables / nftables | Linux 网络包过滤/转发规则系统 | egress sidecar 常通过它们拦截或重定向流量 |
| netstack | 网络协议栈实现 | gVisor 自带 netstack，可能不支持某些 iptables nat 行为 |
| sidecar | 和主容器一起部署的辅助容器 | egress sidecar 负责出站控制或凭据注入 |
| execd | sandbox 内部命令/文件 API 服务 | OpenSandbox command/file/PTY/code execution 依赖它 |
| bootstrap | 服务启动并完成可用准备的过程 | `execd bootstrap` 慢会影响 first command 耗时 |

> 分析：如果 benchmark 只写“create sandbox 246s”，信息不足。需要拆成 image pull、container create、execd bootstrap、first command、file API，才能知道优化点在哪里。

## L3：生命周期、状态机与调度

这一层用于理解 AgentCube v0.2.0 方向：warm pool、adapter、Sleep/Resume、snapshot、Router 唤醒和并发控制。

| 术语 | 简明解释 | 在本项目里的意义 |
| --- | --- | --- |
| lifecycle | 生命周期 | sandbox/session 从创建、Ready、Paused、Resuming 到 Deleted 的全过程 |
| state machine | 状态机 | 明确哪些状态能跳到哪些状态，避免模块各自理解 |
| Ready | 可服务状态 | Router 可以把请求代理过去 |
| Paused / Suspended | 暂停状态 | 资源已释放或降载，但希望后续能恢复上下文 |
| Resuming | 恢复中 | Router 不能直接代理旧 endpoint，需要等待或返回明确状态 |
| Deleted | 删除状态 | session/runtime 已不可恢复或已被 GC |
| pause/resume | 暂停和恢复 | AgentCube Sleep/Resume 的核心动作 |
| suspend/resume | 和 pause/resume 接近，但常强调释放 worker 并保存状态 | Agent Substrate 更常用 suspend/resume 描述 actor |
| snapshot | 某个时刻的状态快照 | 可以是 rootfs、workspace，也可以是 memory + disk |
| snapshot state | pause/suspend 保存出的状态 | 决定 resume 后能恢复到什么程度 |
| rootfs snapshot | 只保存文件系统 | OpenSandbox BatchSandbox 路线，第一阶段更容易落地 |
| memory + disk checkpoint | 保存进程内存和文件系统 | 更接近 Agent Substrate 目标，但 runtime 依赖强 |
| checkpoint | 保存运行现场 | gVisor/runsc 可参与保存 actor 状态 |
| restore | 从 checkpoint/snapshot 恢复 | 请求到来后恢复 actor/sandbox |
| golden snapshot | 模板快照 | Agent Substrate 用模板生成新 actor 的初始恢复点 |
| latest snapshot | 最近一次 suspend 后的快照 | 下一次 resume 用来恢复用户会话状态 |
| hydrate | 从 snapshot 恢复/填充运行环境 | 新 actor 从 golden snapshot hydrate |
| warm pool | 预热资源池 | 预先准备 sandbox/worker，减少冷启动 |
| SandboxWarmPool | agent-sandbox 的 warm pool CRD | AgentCube PR #387 适配重点之一 |
| SandboxClaim | 从 warm pool 领取 sandbox 的 CRD | 新版 agent-sandbox claim 会指向 adopted Sandbox |
| adoption | 领用或接管已有资源 | warm pool 场景中 claim adoption 会改变 pod/sandbox 归属链 |
| provider adapter | 封装不同 runtime/provider 差异的适配层 | 避免 WorkloadManager handler 到处散落 agent-sandbox 字段 |
| BatchSandbox | OpenSandbox Kubernetes 批量 sandbox 资源 | 用一个 CR 管理多个 sandbox delivery，减少 N 次独立 reconcile |
| Pool | OpenSandbox 预热池资源 | 控制缓冲容量、回收策略和池大小 |
| SandboxSnapshot | OpenSandbox pause/resume 内部 snapshot 资源 | 记录 snapshot phase、source pod/node、snapshot image |
| Actor | Agent Substrate 的逻辑会话/工作负载主语 | Actor 不等于 Pod，可 suspend 后恢复到不同 worker |
| Worker | 承载 Actor 的物理 worker pod | 可被多个 actor 轮流占用 |
| WorkerPool | Agent Substrate 的 worker 预热池配置 | 定义预热 worker 数量、runtime、调度约束 |
| ActorTemplate | Agent Substrate 的 actor 模板 | 定义 actor image/env/snapshot storage，并生成 golden snapshot |
| state store | 高频动态状态存储 | Redis/ValKey 记录 Actor/Worker 或 AgentCube session 状态 |
| Redis / ValKey | 内存 KV 存储 | 适合 session 状态、last activity、CAS 等高频数据 |
| CAS | Compare-And-Swap，比较后更新 | 防止两个请求同时 resume 同一个 session 时重复执行 |
| lease | 租约/临时占用权 | 可用于防止多个 worker 同时处理同一份状态 |
| singleflight | 同一个 key 的并发请求合并成一次执行 | Agent Substrate router/resume 可用来避免重复唤醒 |
| TTL | Time To Live，最大存活时间 | 到期后 session 应删除或不可恢复 |
| GC | Garbage Collection，清理 | 清理过期 session、snapshot、Pod、Redis entry |
| idle timeout | 空闲超时 | Ready session 空闲多久后进入 Paused 或 Deleted |
| pause timeout | 暂停超时 | Paused session 保留多久后彻底删除 |
| maxSessionDuration | session 最大生命周期 | 不论是否活跃，到上限都应删除 |

> 注释：AgentCube 的 Sleep/Resume 不能只加一个 `Paused` 字段。Router、WorkloadManager、GC、Store、runtime provider 都要对状态机有同一套理解，否则会出现代理旧 endpoint、重复 resume、GC 删除正在恢复的 session 等问题。

## L4：网络、安全、观测与 benchmark

这一层用于做生产化设计、测试矩阵、PR review 和 benchmark 判断。

| 术语 | 简明解释 | 在本项目里的意义 |
| --- | --- | --- |
| ingress | 入站流量 | 用户请求如何进入 Router 或 sandbox endpoint |
| egress | 出站流量 | sandbox/agent 能访问哪些外部服务 |
| Ingress gateway | 入站网关 | 把外部请求路由到正确 sandbox |
| egress sidecar | 出站代理辅助容器 | 控制外部访问、注入凭据、记录审计 |
| FQDN policy | 按域名控制访问 | 例如允许 `api.openai.com`，适合 SaaS/API 场景 |
| CIDR policy | 按 IP 网段控制访问 | 例如允许 `10.0.0.0/8`，更贴近网络层边界 |
| Credential Vault | 凭据集中管理能力 | 避免 sandbox 内直接持有长期 API key |
| credential injection | 凭据注入 | 在受控路径给请求加 token/API key |
| secure endpoint access | endpoint 访问保护 | 防止拿到 URL 就能访问用户 sandbox |
| authn | authentication，认证 | 判断“你是谁” |
| authz | authorization，授权 | 判断“你能做什么” |
| mTLS | mutual TLS，双向 TLS | 内部组件相互验证身份 |
| JWT | JSON Web Token | 常用于携带会话身份或授权信息 |
| certificate | 证书 | mTLS 或身份签发会用到 |
| SessionIdentity | 会话身份 | 如果 sandbox 会迁移，身份不能绑定旧 Pod/IP |
| audit | 审计 | 记录谁在何时做了什么操作，访问了什么资源 |
| logging | 日志 | 调试和追踪单次请求/错误 |
| tracing | 链路追踪 | 观察请求跨 Router、WorkloadManager、runtime 的路径 |
| Prometheus | 指标采集系统 | 采集 CPU、memory、请求耗时、错误率等 |
| Grafana | 指标可视化工具 | 把 Prometheus 数据展示成 dashboard |
| Locust | 压测工具 | benchmark 目录中用于模拟并发用户 |
| benchmark | 性能评测 | 必须说明冷/热启动、镜像缓存、环境、清理状态 |
| smoke test | 最小冒烟测试 | 验证基本链路是否能跑通 |
| e2e test | 端到端测试 | 验证真实部署和用户路径 |
| readiness | 是否已准备好服务 | server 进程存在不等于 readiness 通过 |
| health check | 健康检查 | 判断服务是否还活着或可响应 |
| p95 / p99 | 95/99 分位延迟 | 比平均值更能体现尾延迟 |
| cleanup | 清理 | 测试结束后必须确认 Pod、container、port-forward、Redis entry 无残留 |

> 分析：生产级 agent runtime 的难点不只是“能创建 sandbox”。还要回答：谁能访问它、它能访问哪里、凭据怎么给、日志和指标怎么收、失败后怎么恢复、测试后是否清理干净。

## 常见对照关系

| 容易混淆的词 | 区别 |
| --- | --- |
| endpoint vs entrypoint | endpoint 更偏网络可访问地址；entrypoint 更偏进入 workload 的入口信息，可能包含 endpoint、协议、路径等 |
| CRD vs gRPC API | CRD 是声明期望状态，controller 异步 reconcile；gRPC API 是直接调用内部服务动作 |
| Pod vs Actor | Pod 是 Kubernetes 调度单元；Actor 是逻辑会话，可在不同 worker 上恢复 |
| pause vs delete | pause 期待后续恢复；delete 表示资源和状态应被清理 |
| rootfs snapshot vs memory checkpoint | rootfs snapshot 保存文件系统；memory checkpoint 还保存进程内存和运行现场 |
| warm pool vs SnapStart | warm pool 预热可用资源；SnapStart 更偏从快照快速恢复 |
| ingress vs egress | ingress 是外部进来；egress 是 sandbox 出去 |
| SDK vs CLI | SDK 给程序调用；CLI 给人通过命令行操作 |
| smoke vs e2e | smoke 是最小链路存活验证；e2e 是更完整的用户路径验证 |
| readiness vs health | health 可能只表示进程活着；readiness 更强调能否接真实请求 |

## 后续追加优先级

后续遇到新术语时按这个顺序追加：

1. 影响读懂社区 PR / issue 的词。
2. 影响 review 答辩的词。
3. 影响测试设计和 benchmark 解释的词。
4. 只出现一次、短期不会复用的词可以先不加。
