# Day 27: Agent Infra 系统化调研与实习目标管理

日期：2026-06-24

## 今日目标

今天不继续追某一个具体 PR，而是把过去三周的 AgentCube、agent-sandbox、OpenSandbox、Agent Substrate、Sleep/Resume、SDK lifecycle、CI/codegen、benchmark 和社区 issue 统一放到一个职业能力地图里。

需要回答四个问题：

1. `Agent Infra` 到底是什么，不是什么。
2. 如果以后要在这个领域就职，需要掌握哪些技术。
3. 当前 AgentCube 实习已经覆盖了哪些能力，还缺哪些能力。
4. 后续实习目标如何管理，才能从“做任务”升级成“能审架构、审代码、审测试”的工程能力。

> 注释：这里的 `Agent Infra` 不是“会写 prompt”或“会调一个 agent framework”。更准确地说，它是让 agent 能安全、可靠、低延迟、可观测、可扩展地使用模型、工具、沙箱、数据、凭据和外部系统的一整套基础设施。
>
> 注释：本文偏职业路线和实习目标管理，不准备直接发 upstream。里面的判断分三类：官方资料事实、本地 AgentCube 实践证据、基于前两者的工程推断。

## 输入来源

### 官方和外部一手资料

| 资料 | 本文采用的重点 | 对 Agent Infra 的启发 |
| --- | --- | --- |
| [Kubernetes Controllers](https://kubernetes.io/docs/concepts/architecture/controller/) | controller 通过控制循环让实际状态接近期望状态，并把当前状态写回 API server | Agent Infra 的 session / sandbox / warm pool / snapshot 很多都不是同步函数，而是控制面状态机 |
| [CNCF Cloud Native Definition](https://github.com/cncf/toc/blob/main/DEFINITION.md) | cloud native 强调可编程、可重复、松耦合、弹性、可管理、可观测、自动化 | Agent Infra 本质上是 AI workload 的 cloud-native 化 |
| [OCI Runtime Specification](https://opencontainers.org/) / [runtime spec](https://specs.opencontainers.org/runtime-spec/) | OCI 规范定义容器 runtime、image 和 distribution 的基础契约 | sandbox runtime、image、rootfs、snapshot、runc/gVisor/Kata 都绕不开 OCI 语义 |
| [Model Context Protocol](https://modelcontextprotocol.io/docs/getting-started/intro) / [MCP spec](https://modelcontextprotocol.io/specification/2025-03-26) | MCP 是把 AI 应用连接到外部数据、工具和工作流的开放协议 | Agent Infra 需要标准化 tool/data/context 接入，不应该每个工具都私有适配 |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/agents/) / [Tools](https://openai.github.io/openai-agents-python/tools/) / [Tracing](https://openai.github.io/openai-agents-python/tracing/) / [Guardrails](https://openai.github.io/openai-agents-python/guardrails/) | 现代 agent SDK 已把 turns、tools、handoffs、sessions、guardrails、tracing 作为一套运行时能力 | AgentCube 不一定实现 agent loop，但必须承接 tool execution、session lifecycle 和 tracing 需求 |
| [OpenTelemetry](https://opentelemetry.io/docs/what-is-opentelemetry/) | OTel 解决 instrumentation 和 telemetry 数据导出的标准化问题，覆盖 traces、metrics、logs | Agent Infra 不能只看“能跑”，需要对 LLM call、tool call、sandbox lifecycle、router proxy 做端到端观测 |
| [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) / [2025 LLM risks](https://genai.owasp.org/llm-top-10/) | prompt injection、sensitive information disclosure、supply chain、excessive agency、unbounded consumption 等是 agent 安全核心风险 | Agent Infra 必须限制 agent 的工具权限、网络出口、凭据访问、资源消耗和审计边界 |
| [NIST AI RMF Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) | 生成式 AI 风险管理需要贯穿设计、开发、使用和评估生命周期 | Agent Infra 的目标不是“模型能回答”，而是持续治理、评估和风险管理 |

> 注释：表里没有列所有 agent framework。LangChain、LlamaIndex、AutoGen、CrewAI 等对应用开发很重要，但本文重点是 `infra`，所以优先选控制面、runtime、协议、观测和安全的一手资料。

### 本地实践资料

| 本地材料 | 已沉淀的能力线索 |
| --- | --- |
| [Day16](day16-agent-sandbox-latest-adaptation.md) | `agent-sandbox v0.4.6` 适配、真实运行验证、math-agent e2e、NetworkPolicy 影响 |
| [Day18](day18-agent-sandbox-v05-forward-adaptation.md) | `v0.5.0rc1` / `v1beta1` 前沿适配、CRD migration 风险、fork CI 验证 |
| [Day19](day19-pr387-code-review-prep.md) | PR #387 文件级 review 答辩材料、generated files、go.mod 依赖栈、最小修原则 |
| [Day20](day20-agent-sandbox-v02-v03-v05-wip-pr-implementations-and-project-study.md) | AgentCube 二次架构梳理，0.2/0.3/0.5 三段适配分支对比 |
| [Day21](day21-opensandbox-agent-substrate-study.md) | OpenSandbox / Agent Substrate 源码级对比，gRPC/proto、controller、runtime adapter、actor multiplexing |
| [Day22](day22-opensandbox-agent-substrate-runtime-runbook.md) | OpenSandbox Docker runtime 实测，Agent Substrate kind quickstart 阻塞，benchmark 环境记录 |
| [Day23](day23-agentcube-future-architecture-and-design.md) | AgentCube 未来架构路线：session lifecycle control plane、RuntimeProvider、benchmark discipline |
| [Day24](day24-sandbox-sleep-resume-design-note.md) | Sleep/Resume 设计先行、Store CAS、WorkloadManager lifecycle service、本地 spike |
| [Day25](day25-sleep-resume-code-review-and-architecture-retrospective.md) | 从 reviewer 视角复盘 Sleep/Resume 阶段性实现，形成风险矩阵和测试矩阵 |
| [Day26](day26-week3-community-latest-and-two-layer-architecture-bug-surface.md) | 最新社区 issue 汇总，抽象出上层 session/API contract 与下层 runtime/provider capability 两层问题面 |
| [术语扫盲](intern-glossary.md) | 把 API、SDK、CRD、controller、runtime、CAS、egress、benchmark 等基础术语分级解释 |

## 一句话定义

Agent Infra 是：

```text
把 LLM agent 从 demo 变成可运行、可隔离、可恢复、可观测、可审计、可评估、可协作的生产系统基础设施。
```

它连接三类世界：

1. AI 应用世界：LLM、tool calling、memory、agent loop、MCP、SDK、guardrails。
2. 云原生世界：Kubernetes、controller、CRD、container runtime、service/network、CI/CD、observability。
3. 安全治理世界：identity、auth、secrets、egress policy、audit、prompt injection、excessive agency、risk management。

> 分析：AgentCube 刚好站在这三个世界的交界处。它不是纯 agent framework，也不是纯容器平台，而是把 code execution、sandbox lifecycle、router、store、Kubernetes runtime、SDK/API 组织起来的中间控制面。

## Agent Infra 不是什么

| 容易误解 | 更准确的理解 |
| --- | --- |
| 会调 OpenAI / Claude API 就是 Agent Infra | 这只是模型调用层。Infra 要处理 session、工具、隔离、网络、安全、观测、测试和运维 |
| 会写 prompt 就是 Agent Infra | prompt 是应用逻辑的一部分。Infra 更关注权限边界、执行环境、状态恢复、失败处理和成本控制 |
| 会用 LangChain 就是 Agent Infra | LangChain 更偏应用编排。Infra 要让这些框架有稳定的底座运行 |
| 能创建容器就是 Agent Infra | sandbox 还需要 workspace、entrypoint、exec API、auth、egress、TTL、GC、snapshot、cleanup |
| 编译通过就是 Infra 稳定 | Infra 稳定至少还要有 unit、race、e2e、runtime smoke、LLM e2e、资源残留检查和 CI 可复现 |
| PR 改得越多越完整 | 开源 infra 更看重最小修、边界清楚、测试充分、可 review、可回滚 |

> 注释：这个认知很重要。未来无论是写代码还是审代码，判断标准都不是“这个功能看起来实现了”，而是“这个功能在系统边界、失败模式、测试证据、社区协作上是否站得住”。

## 技术分层地图

下面按从底到上的顺序拆 Agent Infra。每层都写明需要掌握什么、为什么需要、AgentCube 对应在哪里、如何验证自己真的理解。

### L0: Linux / Container / Runtime 基础

| 需要掌握 | 为什么重要 | AgentCube 对应 | 掌握证据 |
| --- | --- | --- | --- |
| process、filesystem、network namespace、cgroup | sandbox 隔离和资源限制的基础 | sandbox Pod、container resource limits、kind/k3s 问题 | 能解释 Pod 内进程为什么看不到宿主机进程，能解释 cgroup 导致的 kind/kubelet 问题 |
| OCI image / OCI runtime | 镜像、rootfs、runc/gVisor/Kata 都依赖 OCI 语义 | agent-sandbox、OpenSandbox、SnapStart、Kuasar | 能解释 image pull、container create、rootfs snapshot、runtime start 的区别 |
| Docker / containerd / CRI-O / runc | Kubernetes 最终要通过 container runtime 启动 workload | k3s / k3d / agent-sandbox runtime path | 能定位一个 sandbox 慢是 image pull、container create 还是 execd bootstrap |
| gVisor / runsc / Kata / Firecracker | stronger isolation 和 checkpoint/restore 方向 | Agent Substrate、SnapStart、Kuasar、future secure runtime | 能解释它们和普通 runc 的隔离/性能/兼容性差异 |
| image registry / layer cache | cold start benchmark 很容易被镜像拉取污染 | Day22 OpenSandbox 首次 create 246s | benchmark 能区分 cold image pull 和 warm image cache |

> 注释：OCI 可以理解成容器世界的底层契约。只要不同 runtime 遵守同一类 image/runtime 规范，上层系统就能在一定程度上切换 runtime。但 checkpoint、network、filesystem snapshot 这类高级能力仍然会有 runtime-specific 差异。

### L1: Kubernetes / Cloud Native 控制面

| 需要掌握 | 为什么重要 | AgentCube 对应 | 掌握证据 |
| --- | --- | --- | --- |
| Pod / Service / ConfigMap / Secret / Namespace | 运行 agent infra 的最小 K8s 资源集合 | AgentCube Helm chart、Router、WorkloadManager、Redis、PicoD | 能从 manifest 画出组件访问路径 |
| CRD / CR / status / condition | sandbox、warm pool、snapshot、actor 都会用声明式资源表达 | `Sandbox`、`SandboxWarmPool`、`SandboxClaim`、future `Snapshot` | 能解释 spec 和 status 区别，知道 status 不能当同步返回值 |
| controller / reconcile | K8s 资源最终靠控制循环收敛 | agent-sandbox controller、OpenSandbox controller、SnapStart controller | 能说明 create CR 后为什么需要 watch status，而不是立刻假设资源 ready |
| ownerReference / finalizer | 资源归属、级联删除、清理残留 | warm-pool Pod ownership、delete cleanup、e2e 资源检查 | 能用 ownerRef 追踪 warm pool Pod 属于哪个 higher-level object |
| NetworkPolicy / CNI / Service routing | sandbox 不能裸奔，但也不能阻断 Router/WM 数据路径 | #387 `NetworkPolicyManagementUnmanaged`、#291 | 能解释为什么 agent-sandbox managed NetworkPolicy 可能阻断 AgentCube |
| Helm / Kustomize / manifests | 用户最终通过 chart 部署系统 | `manifests/charts/base`、e2e setup | 能判断一个代码字段改动是否需要同步 chart values 和 CRD |

> 注释：Agent Infra 大量行为是异步的。API 接收成功只表示“期望状态已提交”，不表示 runtime 已经 ready。审代码时要特别警惕“创建对象后直接认为它可用”的逻辑。

### L2: Distributed State / Session Lifecycle

| 需要掌握 | 为什么重要 | AgentCube 对应 | 掌握证据 |
| --- | --- | --- | --- |
| state machine | session/sandbox 必须有明确状态转换 | Ready / Paused / Resuming / Deleted / Failed | 能列出哪些转换合法，哪些转换必须拒绝 |
| CAS / optimistic concurrency | resume、delete、GC 并发时必须避免双执行 | Day24 Store CAS、Redis Lua CAS | 能解释为什么 final CAS 失败会导致 runtime/store 不一致风险 |
| TTL / idle timeout / pause timeout / max duration | 成本和资源回收的核心政策 | #394 ttl、#395 delete、#386 Sleep/Resume | 能写出 Ready->Paused、Paused->Deleted、any->Deleted 的决策表 |
| indexes | list/get/GC 不能靠全表扫描长期撑住 | Store pause_expiry index、session list 问题 | 能说明 Redis key 设计如何支撑 owner/list/pause-expired |
| idempotency | retry 和重复请求不能造成重复创建/重复删除 | create/delete/resume API | 能设计重复 delete、重复 resume、超时重试测试 |
| eventual consistency | runtime action 和 store 状态可能短暂不一致 | WorkloadManager provider、agent-sandbox watch | 能说明如何用 intermediate state 和 retry 收敛 |

> 分析：这是 AgentCube 当前最关键的职业能力线。因为 AgentCube 的核心不是“跑一个容器”，而是管理有身份、有状态、有 endpoint、有超时、有 owner、有恢复语义的 session。

### L3: Agent Runtime / Tool Protocol / SDK

| 需要掌握 | 为什么重要 | AgentCube 对应 | 掌握证据 |
| --- | --- | --- | --- |
| tool calling / function calling | agent 真正行动是通过工具完成 | code interpreter、MCP HTTP/stdio、math-agent | 能说明一次 LLM tool call 如何变成 sandbox command/file API |
| MCP client/server | 标准化 agent 和工具/数据的连接 | Day16 MCP HTTP/stdio 验证，OpenSandbox MCP support | 能画出 host、client、server、tool 的边界 |
| SDK contract | 用户不会直接拼内部 HTTP，SDK 是真实产品入口 | Python SDK ttl/delete issues #394/#395 | 能从 SDK 参数追到后端 request struct 和 store 字段 |
| agent loop / turns / sessions | 应用层 agent 和 infra session 不完全相同，但会相互映射 | math-agent、OpenAI Agents SDK、AgentRuntimeClient | 能解释 chat session、agent session、sandbox session 的区别 |
| streaming / SSE / WebSocket | terminal、logs、long-running command、agent event 都会用到 | Router / PicoD / future streaming API | 能判断场景适合 REST、SSE、WebSocket 还是 gRPC |
| handoffs / multi-agent | 更复杂 agent 会把任务转给其他 agent | future multi-AgentCube、OpenAI Agents SDK handoffs | 能说明 handoff 需要怎样的 session/credential/audit 边界 |

> 注释：OpenAI Agents SDK 这类框架把 turns、tools、handoffs、sessions、guardrails、tracing 放在应用 runtime 里。AgentCube 不一定复制这套 runtime，但需要给它们提供安全可靠的工具执行和会话底座。

### L4: Router / Gateway / API Control Plane

| 需要掌握 | 为什么重要 | AgentCube 对应 | 掌握证据 |
| --- | --- | --- | --- |
| REST API design | SDK、CLI、外部用户入口需要稳定协议 | WorkloadManager create/delete/list/get | 能判断新增字段是否需要 API schema、SDK、docs、tests 同步 |
| reverse proxy | Router 把请求代理到 sandbox endpoint | `pkg/router`、entrypoints、pathPrefix | 能解释 #388 longest valid prefix match 为什么不是字符串小 bug |
| authn / authz / identity propagation | session owner、delete/list、endpoint 访问都需要身份 | Keycloak/OIDC/RLAC、Router->WM identity forwarding | 能设计 owner-aware list/delete/resume 测试 |
| resume-before-proxy | paused session 第一次请求必须先唤醒再代理 | Sleep/Resume Stage 3 | 能说明 Router 遇到 Paused/Resuming/Failed 应分别怎么返回 |
| API compatibility | 用户 SDK 不能频繁破坏 | #394 ttl 被忽略、#395 delete 缺失 | 能写出兼容策略：新增字段、默认值、deprecated、validation |
| error semantics | 用户需要可诊断错误，不是统一 500 | waitForDirectSandboxReady nil watcher、closed channel | 能区分 timeout、not found、conflict、runtime unavailable、auth denied |

> 分析：Agent Infra 的 gateway 层不是简单转发。它要做 identity、routing、resume、rate-limit、audit、trace propagation 和错误语义。Router 是未来 Sleep/Resume 能否真实可用的关键模块。

### L5: Security / Governance / Risk Management

| 需要掌握 | 为什么重要 | AgentCube 对应 | 掌握证据 |
| --- | --- | --- | --- |
| prompt injection | 用户/网页/文件内容可能改变 agent 行为 | agent 工具调用、MCP、browser/pcap demos | 能说明 sandbox 只能降低代码执行风险，不能自动解决 prompt injection |
| excessive agency | agent 权限过大时会执行破坏性动作 | file API、command API、network egress、delete API | 能设计 tool permission、approval、dry-run、audit 的边界 |
| secrets management | API key 不应直接长期暴露在 sandbox 内 | `.env`、K8s Secret、Credential Vault 方向 | 能说明凭据注入和凭据长期落盘的风险差异 |
| egress control | agent 可以访问外部网络，必须限制和审计 | NetworkPolicy、egress sidecar、FQDN/CIDR policy | 能设计 allow/deny policy 和测试矩阵 |
| supply chain | model、image、dependency、GitHub Actions 都可能被污染 | #392 workflows hardening、Docker images、go.sum | 能说明 pin action SHA、dependency drift、generated code check 的关系 |
| audit log | 生产系统要知道谁在何时让 agent 做了什么 | Router/WM/store trace and audit | 能定义最低审计字段：user、session、tool、target、result、timestamp |
| risk framework | 安全不是一次性 patch，而是 lifecycle governance | NIST AI RMF、OWASP LLM Top 10 | 能把风险映射到可执行控制项和测试 |

> 注释：sandbox 是 Agent Infra 的安全基石，但不是全部安全。Agent 可以通过合法工具做错误的事，所以还要有工具权限、网络策略、凭据边界、审计、限流、人工确认和输出处理。

### L6: Observability / Evaluation / Benchmark

| 需要掌握 | 为什么重要 | AgentCube 对应 | 掌握证据 |
| --- | --- | --- | --- |
| logs / metrics / traces | infra 出问题时必须能定位是模型、路由、沙箱还是网络 | PicoD metrics #400、future OTel | 能把一次 request 分解成 LLM call、WM create、sandbox ready、tool exec、proxy |
| p50 / p95 / p99 | 单次成功不能说明稳定性 | sandbox benchmark、warm pool curve | 能跑多轮并解释尾延迟 |
| cold/warm/pause/resume split | 不同优化目标不同 | warm pool、Sleep/Resume、SnapStart | 能分别测 image pull、create、ready、first command、resume |
| LLM e2e | 编译/e2e 通过不等于 agent 可用 | math-agent LLM e2e | 能区分 provider failure、sandbox failure、prompt/tool failure |
| cleanup verification | lifecycle feature 必须证明没有资源泄漏 | Pod/Sandbox/Redis cleanup | 能在测试后检查 K8s CR、Pod、Redis、port-forward |
| CI reliability | CI 结论要可信 | #401 false pass、#399 go.sum | 能判断 workflow path filter 是否会漏测关键变化 |
| benchmark schema | 结果要可比较、可复现 | Day22 raw logs、future benchmark suite | 能记录 host、kernel、runtime、image cache、cluster、model provider |

> 分析：未来写 PR 材料不能只写 `make test passed`。Agent Infra 的 PR 需要说明影响面，并按层次给出 unit、integration、runtime smoke、LLM e2e、cleanup、CI 的证据。

### L7: Open Source Engineering / Review Ability

| 需要掌握 | 为什么重要 | AgentCube 对应 | 掌握证据 |
| --- | --- | --- | --- |
| minimal PR scope | infra 社区最怕一个 PR 混多个目标 | #387 移除 Dockerfile cleanup、Go upgrade 单独 PR #391 | 能解释每个文件为什么必须改，为什么不改无关文件 |
| PR template / DCO / labels | 社区流程影响协作质量 | upstream PR 规则、`/kind feature`、tide | 能按模板准备 PR，不打扰维护者跑无意义 CI |
| review triage | Copilot/Gemini/maintainer 评论要区分真 bug 和误报 | Day17 review triage | 能逐条判断：must fix、nice-to-have、false positive、out of scope |
| code rationale | reviewer 关心为什么这样改 | Day19 文件级答辩 | 能在 review 时解释 generated files、dependency、compatibility、test |
| rebase / fork CI | 大 PR 需要干净基线和可复现验证 | fork PR #4/#5/#6/#7 | 能用 fork PR 跑 CI，而不是随便打扰 upstream |
| skills/scripts | 重复分析要工具化 | issue/pr scripts、llm-e2e skill、runtime smoke skill | 能把 5 步以上流程写成 skill，降低遗漏和 token 成本 |

> 注释：导师说“以后可以假设自己一行代码都不写，只负责审代码”，核心不是放弃工程能力，而是把工程能力转成更高层的判断力：需求拆分、架构边界、代码组织、测试策略、CI/CD、review 质量和社区协作。

## 职业岗位地图

Agent Infra 不是一个单一岗位，它会落在不同公司和团队的不同名字下。

| 岗位方向 | 典型工作 | 需要特别强的能力 | 和当前实习的连接 |
| --- | --- | --- | --- |
| Agent Platform Engineer | 给业务团队提供 agent runtime、SDK、tool registry、eval、observability | API design、SDK、agent loop、tool protocol、observability | Python SDK lifecycle、math-agent e2e、MCP 验证 |
| AI Infrastructure Engineer | 管理模型网关、工具执行、sandbox、resource scheduling、cost | distributed systems、K8s、runtime、queue/cache、reliability | AgentCube Router/WM/Store、agent-sandbox 适配、Sleep/Resume |
| Sandbox / Runtime Engineer | 做 code execution、container isolation、snapshot、checkpoint、workspace | Linux、OCI、gVisor/Kata/Firecracker、filesystem/network | OpenSandbox、Agent Substrate、SnapStart、Kuasar、Day22 runtime smoke |
| Kubernetes Platform Engineer | 用 CRD/controller/operator 管理 AI workload | K8s controllers、CRD、Helm、network/security、CI | agent-sandbox、codegen、CRD migration、v0.5/v1beta1 |
| LLMOps / Evaluation Engineer | 构建 agent benchmark、eval、trace、quality/cost/reliability dashboard | experiment design、metrics、traces、LLM failure analysis | math-agent、benchmark suite、OpenTelemetry 方向 |
| AI Security Engineer | 设计 prompt injection、tool permission、credential、egress、audit 控制 | security threat model、IAM、network policy、secret management | NetworkPolicy、Credential Vault 方向、OWASP LLM risk |
| Open Source Infra Engineer | 在社区中做兼容、测试、CI、review、release engineering | minimal PR、DCO、CI、dependency、review communication | #385/#387/#391、skills、fork CI workflow |

> 分析：当前最适合沉淀的定位不是“模型算法工程师”，而是 `AI-native cloud infrastructure / agent runtime control plane`。这条线和 AgentCube 的经验最匹配，也最容易用 PR、测试、报告、review 证据证明能力。

## 能力等级模型

### Level 0: 能跑 demo

能做到：

- 跑通 AgentCube Getting Started。
- 能创建 sandbox。
- 能让 math-agent 调用 code interpreter。
- 能看懂基础日志。

不足：

- 不能解释失败时是模型、SDK、Router、WorkloadManager、agent-sandbox、K8s 还是 runtime 的问题。
- 容易把“单次成功”当成“系统可靠”。

### Level 1: 能定位单点问题

能做到：

- 看懂 `go test` / CI / e2e 失败。
- 能追到相关文件和函数。
- 能区分编译失败、lint 失败、runtime 失败、provider 失败。
- 能做最小复现。

实习证据：

- Day16 找到 `SandboxPodNameAnnotation` package 迁移。
- Day17 triage Copilot/Gemini 评论。
- Day19 解释 #387 每个文件为什么改。

### Level 2: 能做兼容适配

能做到：

- 升级依赖前先看版本历史和 API 差异。
- 用最小代码修复编译。
- 用 runtime/e2e 验证行为，不只停在语法。
- 能解释 go.mod/go.sum/generated files 的变化。

实习证据：

- #391 Go toolchain 独立 PR。
- #387 `agent-sandbox v0.4.6` compatibility。
- Day18 `v0.5.0rc1` fork-only validation。
- Day20 0.2/0.3/0.5 逐版本适配分支。

### Level 3: 能设计状态机和测试矩阵

能做到：

- 把 issue 归纳为状态机/API contract 问题。
- 设计 Ready/Paused/Resuming/Deleted 等状态转换。
- 设计 CAS、GC、Router、Store、Provider 的边界。
- 能把测试分成 unit、race、integration、runtime smoke、LLM e2e、cleanup。

实习证据：

- Day24 Sleep/Resume design note 和 Store CAS spike。
- Day25 reviewer 视角的风险矩阵。
- Day26 双层架构问题面。

### Level 4: 能做架构 review

能做到：

- 不只看代码对不对，还看是否符合项目边界。
- 能判断功能 PR 是否夹带 cleanup。
- 能识别 API/SDK/Store/Router/GC 是否契约一致。
- 能把社区多个 issue 归纳成系统性设计缺口。

实习证据：

- Day23 未来架构路线。
- Day26 将 #394/#395/#397/#388/#401/#386 汇总成 contract / runtime 两层。
- 对 #387 的 review 答辩准备。

### Level 5: 能主导一个 Agent Infra 方向

目标能力：

- 可以提出一个不空泛的 upstream proposal。
- 可以拆成阶段性 PR。
- 每个 PR 都能说明 scope、compatibility、tests、risk、rollback。
- 能与维护者协作，不抢任务、不打扰、不堆 PR、不混 unrelated changes。
- 能让测试和文档服务于架构判断，而不是只为了提交。

当前状态：

- 还没有完全达到。
- 已具备向 Level 4 靠近的材料。
- 接下来要通过 #387 review、Sleep/Resume Stage 3 设计、SDK lifecycle review、benchmark suite 来补齐。

## 当前实习能力盘点

### 已经比较扎实的部分

| 能力 | 证据 | 还要注意 |
| --- | --- | --- |
| 开源 PR 流程 | #385/#387/#391、fork PR CI、DCO、PR template、labels | 任何 upstream 操作仍需先给用户确认 |
| agent-sandbox 版本适配 | v0.2/v0.3/v0.4/v0.5 分支和 Day20 总结 | 不能把 rc1 适配和 stable compatibility 混在一个 PR |
| codegen/generated files 理解 | Day19、#401/#399 分析 | 需要继续熟悉 controller-runtime 和 client-go 生成链路 |
| runtime smoke 测试 | Day16、Day22、Day18 | kind 环境仍有 blocker，真实 KVM/MicroVM 未测 |
| Sleep/Resume 状态机 | Day24/Day25 | Router resume-before-proxy 和 GC split 还未进入完整实现 |
| review 材料组织 | Day19/Day25/Day26 | 下周要把材料压缩成 maintainer 能快速读懂的英文口径 |

### 明显短板

| 短板 | 为什么影响 Agent Infra 就职 | 补强方式 |
| --- | --- | --- |
| Kubernetes controller-runtime 深度 | 未来 CRD/controller/reconcile 是核心能力 | 选 agent-sandbox 或 OpenSandbox controller 做一次逐函数阅读，补 reconcile 状态机图 |
| Linux runtime 深度 | gVisor/Kata/Firecracker/SnapStart 不懂底层会影响判断 | 学 OCI runtime lifecycle、containerd/shim、runsc checkpoint、Kata RuntimeClass |
| 网络与安全 | Agent Infra 的生产化难点大量在 egress/auth/secret/audit | 做一份 AgentCube threat model，覆盖 prompt injection、tool abuse、credential leak、network policy |
| Observability | 不能只说“加 metrics”，要知道 cardinality、trace context、span boundary | 设计 AgentCube OTel trace schema，不一定马上实现 |
| Evaluation / Benchmark 体系 | Agent Infra 优化必须能量化 | 统一 math-agent + sandbox lifecycle benchmark schema |
| 产品/API 设计 | SDK lifecycle 是用户真实入口 | 对 #394/#395 做 review matrix，定义 ttl/delete/stop/attach/list semantics |
| 英文 upstream 表达 | 社区影响力需要清晰英文 proposal/review | 每个 issue 先写中文分析，再压缩成英文 comment 草稿，代码块保存 |

## 实习目标管理框架

后续实习目标不要只按“今天改了什么代码”管理，而是按能力闭环管理。

一个合格任务应至少包含：

```text
问题定义 -> 源码/文档证据 -> 设计判断 -> 最小实现或复现 -> 分层测试 -> review 材料 -> 可复用规则/skill
```

> 注释：如果某一步暂时做不了，例如没有 KVM、kind 卡在 cgroup、维护者已有 assignee，也要记录阻塞原因和替代产出。阻塞不是失败，未记录才会浪费下一轮时间。

### Objective 1: 成为能 review AgentCube lifecycle 代码的人

关键结果：

- 能解释 Router / WorkloadManager / Store / agent-sandbox / PicoD 的调用链。
- 能解释 create、ready、proxy、delete、GC、warm pool、future pause/resume 的状态流。
- 能对任意 lifecycle PR 写出至少 5 个有质量的 review questions。
- 能设计状态机测试和并发测试，不只依赖原始 CI。

对应任务：

- 继续维护 [Day20](day20-agent-sandbox-v02-v03-v05-wip-pr-implementations-and-project-study.md) 的项目二次梳理。
- 在 [Day24](day24-sandbox-sleep-resume-design-note.md) / [Day25](day25-sleep-resume-code-review-and-architecture-retrospective.md) 基础上补 Router/GC Stage 3 设计。
- 下周 review #387 时，用 [Day19](day19-pr387-code-review-prep.md) 做答辩底稿。

### Objective 2: 建立 Agent Infra 测试和 benchmark 方法论

关键结果：

- 对每个 infra PR 都能列出 unit、race、integration、runtime smoke、LLM e2e、cleanup 的测试矩阵。
- 能区分编译通过、e2e 通过、math-agent 通过、真实生产可用之间的差异。
- 能输出统一 JSON/Markdown benchmark 结果，记录环境和限制。
- 能证明一个优化提升的是 cold start、warm pool hit、pause/resume、restore 还是 first command。

对应任务：

- 整理已有 sandbox benchmark、math-agent 结果和 Day22 runtime smoke。
- 给 AgentCube 建一个可复用 benchmark schema 草案。
- 把 `llm-e2e-test` skill 继续扩展到 cleanup 和 provider failure 分类。

### Objective 3: 建立 Agent Infra 安全与治理视角

关键结果：

- 能把 OWASP LLM Top 10 映射到 AgentCube 的工具、沙箱、网络、凭据、审计边界。
- 能解释 sandbox 解决了什么风险，没有解决什么风险。
- 能设计 egress / credential / audit 的最小可测方案。
- 能在 review 时识别 excessive agency、sensitive information disclosure、unbounded consumption 相关风险。

对应任务：

- 在后续报告中新增 AgentCube threat model。
- 把 NetworkPolicy、Credential Vault、secure endpoint access、audit log 加入术语和设计文档。
- 针对 SDK delete/ttl、Router entrypoint、PicoD command API 设计安全测试问题。

### Objective 4: 提升开源社区协作质量

关键结果：

- upstream-facing 文案都先本地准备，用户确认后再发。
- 不在一个 PR 中混入 unrelated cleanup。
- 不抢已经 `/assign` 的 issue。
- 不用 upstream PR 只为了跑 CI，优先用 fork PR。
- 能用脚本/skill 复用 issue/PR 分析流程。

对应任务：

- 继续维护 `.agents/skills/agentcube-issue-discussion`、`agentcube-pr-management`、`llm-e2e-test`、`sandbox-runtime-smoke`。
- 每次社区分析先跑脚本，再人工看关键源码。
- 对 mentor / maintainer 的反馈更新 AGENTS.md 或 skill，不让同类问题重复出现。

## 后续 4 周学习路线

### Week 4: 生命周期契约和 #387 review

重点：

- 完成 #387 review 答辩材料压缩版。
- 继续跟踪 #387 CI、tide、maintainer review。
- 不把 v0.5/rc1 混入 #387。
- 针对 #394/#395/#397/#388 做代码级 review，不抢实现。
- 给 Sleep/Resume Stage 3 写 Router/GC behavior table。

产出：

- 一份英文 review explanation 草稿。
- 一份 `session lifecycle API semantics table`。
- 一个 Router resume-before-proxy 测试矩阵。

### Week 5: Kubernetes controller 和 runtime 深挖

重点：

- 精读 agent-sandbox controller 或 OpenSandbox controller 的 reconcile。
- 画 CRD -> controller -> Pod/Sandbox -> status 的状态流。
- 补 `controller-runtime`、client-go informer/lister/fake client 的学习记录。
- 学 OCI runtime lifecycle、RuntimeClass、gVisor/runsc checkpoint 资料。

产出：

- controller 源码阅读文档。
- 一个小型 reconcile 状态机图。
- 一个 runtime capability matrix。

### Week 6: Security / Observability / Benchmark

重点：

- 设计 AgentCube threat model。
- 设计 OTel trace/span schema。
- 整理 benchmark schema，并把现有 raw data 对齐。
- 设计 egress / credential / audit 的最小 smoke test。

产出：

- threat model 文档。
- benchmark suite 草案。
- observability schema 草案。

### Week 7: Upstream proposal / review quality

重点：

- 根据前面材料准备一个低重复的 upstream proposal 或 review。
- 只在有代码证据、测试证据或官方资料依据时发社区。
- 形成“问题 -> 证据 -> 建议 -> 测试”的英文表达模板。

产出：

- 一个 upstream-ready proposal/comment 草稿。
- 一个可复用的 proposal checklist skill 更新。
- 一份周总结，强调 review 能力和工程判断沉淀。

## 每周目标管理看板

| 维度 | 每周最低产出 | 合格标准 | 不合格信号 |
| --- | --- | --- | --- |
| 源码理解 | 至少一个模块/PR 的调用链图或文件级说明 | 能解释为什么改、为什么这样改、怎么测 | 只复述 issue 内容，没有代码行或测试证据 |
| 测试能力 | 至少一个测试矩阵或 runtime/LLM 验证记录 | 写清命令、环境、结果、失败原因、cleanup | 只写“测试通过”，没有范围和限制 |
| 架构判断 | 至少一个状态机/API contract/风险矩阵 | 能把多个 issue 汇总成系统问题 | 每个 issue 都孤立分析，无法抽象 |
| 社区协作 | 至少一次本地 review/comment 草稿或 PR 跟踪 | 符合模板、最小 scope、先确认再发 | 直接打扰维护者、忽略模板、混入无关改动 |
| 知识沉淀 | 至少更新一处 report/todo/skill/AGENTS | 下轮能复用，不需要重问 | 知识只留在聊天里 |

## 面试和就业准备问题库

这些问题可以用来检验自己是否真的进入 Agent Infra 视角。

### 架构类

1. 你会如何设计一个支持 code execution 的 agent sandbox service？
2. Session、Sandbox、Workspace、Tool invocation 四个概念有什么区别？
3. 为什么 Sleep/Resume 不能只加一个 `Paused` 状态？
4. Router 在请求一个 paused sandbox 时应该同步等待、异步返回还是排队？
5. Store 为什么需要 CAS？不用 CAS 会出现什么并发 bug？
6. TTL、idle timeout、pause timeout、max session duration 的语义如何区分？
7. Warm pool、SnapStart、pause/resume、image cache 分别优化哪个阶段？
8. 什么时候应该把状态放 Kubernetes CRD，什么时候放 Redis/ValKey？

### Runtime 类

1. runc、gVisor、Kata、Firecracker 的安全和性能取舍是什么？
2. OCI image、rootfs、workspace、snapshot、checkpoint 有什么区别？
3. 为什么一次 sandbox 创建很慢不能直接归因于调度慢？
4. 如何设计 benchmark 区分 image pull、container create、execd bootstrap、first command？
5. RuntimeClass 对 Kubernetes sandbox 有什么作用？

### 安全类

1. sandbox 能防什么，不能防什么？
2. prompt injection 和普通命令注入有什么不同？
3. excessive agency 在 agent infra 中如何体现？
4. 如何设计 agent 的 egress policy？
5. 凭据应该放在哪里，如何注入，如何审计？
6. Tool permission 和 user approval 应该放在 SDK、Router 还是 runtime 层？

### Observability / Evaluation 类

1. 一个 agent request 的 trace 应该包含哪些 span？
2. sandbox lifecycle 应该有哪些 metrics？
3. 如何避免 metrics label cardinality 爆炸？
4. LLM e2e 测试失败时如何区分 provider、prompt、tool、sandbox、network？
5. p95 和 p99 对 infra 优化有什么意义？

### 开源协作类

1. 为什么一个 Go toolchain 升级应该从 feature PR 中拆出来？
2. 为什么 generated files 变化需要解释？
3. 为什么 fork PR 可以用于 CI 验证，而不是直接发 upstream WIP？
4. 如何判断 bot review 是真问题、误报还是 out-of-scope？
5. 一个 upstream PR 的 `What this PR does / why we need it` 应该怎么写？

## 对 AgentCube 后续设计的启发

### 1. AgentCube 应该先成为 session lifecycle control plane

现在社区多个 issue 都指向同一个方向：

- #394：SDK `ttl` 和后端 API contract 不一致。
- #395：SDK 能 create，缺少 delete/stop。
- #397：direct path 和 warm-pool path auth default 不一致。
- #388：Router pathPrefix match 规则不明确。
- #386：Sleep/Resume 需要 Ready -> Paused -> Ready。
- #387：agent-sandbox compatibility 是 runtime foundation。

这些问题的共同答案不是“每个地方 patch 一下”，而是定义统一 session lifecycle contract。

> 分析：未来写 proposal 时，应该用 `Session` 作为上层对象，把 SDK、Router、Store、GC、RuntimeProvider 的语义串起来。底层 agent-sandbox 版本适配只是 provider capability 的一部分。

### 2. RuntimeProvider 是必要边界，不是过度抽象

`agent-sandbox v0.4.6`、`v0.5.0rc1`、SnapStart、OpenSandbox、Agent Substrate 的差异说明：

- CRD group/version 会变。
- warm pool claim 语义会变。
- direct Sandbox 字段会变。
- pause/resume/snapshot capability 不同。
- NetworkPolicy 默认管理方式可能不同。
- clean install 和 in-place upgrade 风险不同。

如果 WorkloadManager handler 到处直接写 provider-specific 字段，后续每次升级都会扩大 diff。

> 分析：RuntimeProvider 的边界应该从测试和兼容性痛点中长出来，而不是先写一个很大的抽象。#387 和 Day18 已经给了足够证据：版本差异需要隔离。

### 3. Benchmark 必须变成设计输入

AgentCube 后续会遇到多个优化方向：

- warm pool
- Sleep/Resume
- SnapStart
- runtime checkpoint
- node-local cache
- SDK / Router API 优化

如果没有统一 benchmark，大家会用不同口径比较结果。

最小 benchmark schema 应该至少包括：

- host OS / kernel / CPU / memory
- cluster type: kind / k3s / k3d / GKE
- runtime: runc / gVisor / Kata / Kuasar
- image cache status
- model provider and model
- workload type: command / file / MCP / math-agent / SDK
- lifecycle phase: cold create / warm pool hit / pause / resume / delete
- latency: p50 / p95 / p99
- failure rate
- cleanup result

### 4. 安全要从一开始进入设计

Agent Infra 的安全不是最后加一个 auth middleware。

需要在 session lifecycle 中提前考虑：

- 谁创建 session。
- 谁能 list/get/delete/resume session。
- Router proxy 时如何验证 owner。
- sandbox 出站能访问哪里。
- tool call 是否需要 approval。
- 凭据是否进入 sandbox 文件系统。
- audit log 是否能复原关键操作。
- GC/delete 是否会误删其他 owner 的资源。

> 注释：OWASP LLM 风险里 `prompt injection` 和 `excessive agency` 对 AgentCube 特别相关。因为 AgentCube 给 agent 提供的是代码执行和外部访问能力，一旦权限边界不清楚，agent 的错误判断会变成真实系统动作。

## 当前可执行下一步

优先级从高到低：

1. 继续推进 #387 review/merge 材料，但不扩大 scope。
2. 针对 #394/#395/#397/#388 做源码级 review 和测试矩阵，不抢已认领实现。
3. 写 `Session lifecycle contract table`：字段、API、状态、超时、delete/stop、owner、Router 行为。
4. 为 Sleep/Resume Stage 3 写 Router resume-before-proxy 和 GC split 的行为表。
5. 整理 benchmark schema，把已有 Day16/Day18/Day22/math-agent 结果映射进去。
6. 新增 AgentCube threat model 草稿，覆盖 prompt injection、tool abuse、egress、credential、audit。
7. 继续把重复流程固化到 skills，尤其是 issue/PR review、LLM e2e、runtime smoke、benchmark reporting。

## 本文结论

如果未来要在 Agent Infra 领域就职，当前最值得强化的不是“多写几个 demo agent”，而是：

- 理解 agent 如何使用工具和外部系统。
- 理解 sandbox/runtime 如何提供安全执行环境。
- 理解 Kubernetes/control plane 如何管理异步资源状态。
- 理解 session lifecycle 如何在 API、Router、Store、GC、runtime provider 之间保持一致。
- 理解 observability、benchmark、安全治理如何证明系统真的可用。
- 理解开源社区如何用最小 PR、清晰测试和高质量 review 推动复杂系统演进。

当前实习已经从“跑通项目”进入“review 架构和工程判断”的阶段。后续目标应该围绕可复用的审查能力展开：能拆需求、能写设计、能看源码、能识别风险、能设计测试、能准备 PR 材料、能把经验沉淀成规范和 skill。

> 最终判断：AgentCube 是一个很适合训练 Agent Infra 能力的项目，因为它同时包含 agent-facing API、sandbox runtime、Kubernetes control plane、session store、Router、SDK、CI/codegen、benchmark 和开源协作。只要后续不陷入单点修 bug，而是持续把 bug 归纳成 contract、state machine、testing 和 security 问题，这段实习经历就能转化成可迁移的职业能力。
