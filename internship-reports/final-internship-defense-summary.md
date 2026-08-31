# 华为实习最终总结：AgentCube 开源工程、Agent Sandbox 与云原生控制面

| 字段 | 内容 |
| --- | --- |
| 实习生 | 待填写 |
| 部门 / 团队 | 华为开源相关团队（待补充正式名称） |
| 导师 | 待填写 |
| 主要项目 | [volcano-sh/agentcube](https://github.com/volcano-sh/agentcube) |
| 主要实习证据期 | 2026-06-11 至 2026-08-11 |
| 社区状态校准日期 | 2026-08-31 |

> 统计口径：本文以 `intern` 分支的 Day 1 至 Day 60、九份周总结、Git 历史和 GitHub issue / PR 状态为依据。2026-08-31 的查询只用于校正“已合入、仍开放、已关闭未合入”等状态，不把实习证据期之后的维护者动作计作本人新增产出。

## 一、实习总结

两个月的工作围绕 AgentCube 及其上下游生态展开，主线从“跑通一个开源项目”逐步推进到“能够用代码、测试和社区证据参与云原生 Agent 基础设施建设”。工作覆盖 AgentCube 运行链路、CodeInterpreter 与 agent-sandbox 版本兼容、warm pool 生命周期、CI / release 工程、Kubernetes 控制器 Review、性能测评、竞品与架构研究，以及 Karmada 等关联开源项目的代码贡献。

实习期内，在 AgentCube、Karmada 和 drawio-skill 三个上游仓库共创建 **23 个 PR**：**19 个已合入，3 个仍开放，1 个验证 PR 已关闭未合入**；创建 **5 个 issue**；按同一证据期内创建且由本人 Review 的他人 PR 统计，至少完成 **12 个可定位的实质 PR Review**。本地形成 **60 个编号日报主题、69 份 Day 报告、9 份周总结、28 个图示资产和 143 个 benchmark / review 原始结果文件**。

最重要的变化不是提交数量，而是工程方法的变化：从“能否运行”推进到“接口约定是否清楚、失败路径是否安全、测试是否触达真实调用链、CI 是否绑定正确版本与测试目标、Review 结论是否能被复核”。

## 二、两个月的学习、工作与时间分配

### 2.1 分阶段安排

| 阶段 | 时间 | 主要学习与工作 | 阶段输出 |
| --- | --- | --- | --- |
| 项目入门与基线建立 | 第 1-2 周 | 跑通 AgentCube、k3s、Redis、Workload Manager、Router、PicoD、Python SDK 和 `math-agent`；学习 Go、Kubernetes CRD / controller、Helm、Python SDK；建立 benchmark 和 fork / upstream 工作流 | Getting Started 复现、sandbox latency / warm pool benchmark、竞品矩阵、首个 AgentCube PR #385、版本兼容 issue / PR |
| 架构边界与功能适配 | 第 3 周 | 研究 Session Runtime Control Plane、Sleep / Resume、Store CAS、RuntimeProvider、Router 与 Workload Manager 职责；推进 agent-sandbox v0.4.6 兼容 | AgentCube #387、Sleep / Resume 设计、Session Runtime 架构图、测试分层与 code rationale matrix |
| 工程闭环与 CI / release | 第 4-5 周 | 处理组件清理、fork CI、proposal 规范、release 版本、multi-arch build、Dependabot、runner 与 Go toolchain | AgentCube #403、#414、#415、#416、#420、#422、#423、#429；buildx A/B benchmark |
| 深度 Review 与跨项目验证 | 第 6 周 | 让兼容性改动通过真实 Review 和 E2E；将同一套状态机、cleanup、event predicate、证书身份和 CI 判断用于 Karmada | AgentCube #387 合入；Karmada E2E / controller / certificate PR；AgentCube #400、#431 与 Karmada proposal / code Review |
| 版本升级与运行时安全 | 第 7 周 | Review agent-sandbox v0.5.2、AgentRuntime termination、Router-PicoD mTLS 与 Karmada 删除/调度路径 | AgentCube #442 / #437 / #444 Review，Karmada #7777 merge、#7791 / #7795 提交 |
| 兼容性收敛与 Review 工具 | 第 8 周 | 修复 MCP SDK v2，独立验证 agent-sandbox v0.5.3，重置 replacement PR 的 final-head Review | AgentCube #448 merge、#446 Review、v0.5.3 fork adapter、Review harness |
| Ownership、升级实证与收尾 | 第 9 周 | 验收 CodeInterpreter child ownership，完成 warm-pool lineage E2E、PR #385 刷新和四项目架构对照 | AgentCube #450 / #446 Review、#385 更新，Karmada #7795 merge，AgentENV / Volcano / Kthena 研究 |

### 2.2 工作类型分配

下表是按 60 个日报主题、对应 PR / 测试 / 文档的主任务分类折算，不是打卡系统的精确工时。多个任务同时包含代码、测试和 Review，因此比例用于说明精力重心，不用于财务或考勤统计。

| 工作类型 | 估算占比 | 主要内容 |
| --- | ---: | --- |
| 代码实现、版本兼容与 CI / release | 30% | AgentCube agent-sandbox 兼容、warm pool health、MCP SDK v2、组件清理、Go / runner / Dependabot / release / buildx 工作 |
| PR Review 与开源社区协作 | 25% | AgentCube / Karmada PR Review、Issue / proposal 讨论、review comment、作者修改复核、exact-head 状态检查 |
| 架构与生态研究 | 25% | Session Runtime、Sleep / Resume、SandboxPool、mTLS、E2B / OpenSandbox / Agent Substrate / AgentENV / Volcano / Kthena 对比 |
| 测试、benchmark 与环境定位 | 15% | unit、race、E2E、LLM E2E、warm pool 性能、multi-arch build、Kubernetes / KVM 环境分析 |
| 文档、流程与复用工具 | 5% | 日报 / 周报、TODO、贡献规范、Mermaid / draw.io、review skill 与 agent harness |

## 三、本人工作在 AgentCube 系统中的位置

![AgentCube 系统位置与实习工作重点](final-internship-system-position.png)

图的可编辑源文件为 [final-internship-system-position.mmd](final-internship-system-position.mmd)。箭头表示 AgentCube 的主要请求和资源链路；橙色节点是主要实现范围，紫色节点是架构与 Review 重点，蓝色节点表示 SDK / E2E / benchmark 的横向验证覆盖。

### 3.1 主要聚焦模块

| 模块 / 边界 | 在系统中的作用 | 本人工作 |
| --- | --- | --- |
| Workload Manager / CodeInterpreter | 编排 session 创建、查询、删除和 Kubernetes 资源生命周期 | 适配 agent-sandbox v0.4.6；独立验证 v0.5.2 / v0.5.3；实现 warm pool health；Review child ownership、delete precondition、GC / refill |
| SandboxWarmPool / SandboxClaim / Sandbox | 提供预热资源、claim 绑定、Sandbox 与 Pod 生命周期 | 分析 adoption、owner reference、UID、generation、resourceVersion 和 upgrade migration；设计真实 E2E 闭环 |
| Router / PicoD | Router 负责认证、路由和代理，PicoD 负责 sandbox 内代码执行数据面 | 研究 Router -> PicoD mTLS、身份绑定与 sidecar 边界；Review PicoD Prometheus metrics；验证 AgentRuntime 示例链路 |
| Python SDK / MCP | 向 Agent 和用户提供 session / tool 调用接口 | 修复 Code Interpreter MCP SDK v2 兼容并合入 AgentCube #448；运行 Python SDK 与 `math-agent` 链路 |
| CI / release / project governance | 为代码、镜像、Helm chart、proposal 和贡献者分支提供持续验证 | 提交 push validation、chart version、native builder、Dependabot、runner pinning、proposal template、Go update workflow 等 PR |
| 测试与 Review 体系 | 证明功能、兼容、并发、cleanup 和发布结果，而不只证明编译 | 建立 unit -> race -> package -> E2E -> LLM E2E -> cleanup 分层；形成 exact-head、scope closure 和 risk-to-test 方法 |

### 3.2 完成工作需要掌握的知识与技能

| 能力领域 | 需要掌握的知识 | 实际应用 |
| --- | --- | --- |
| Go 与控制器开发 | Go interface、context、error wrapping、goroutine、race test、controller-runtime、client-go | Workload Manager 兼容、deadline、ownership、reconcile、event predicate Review |
| Kubernetes | CRD、owner reference、UID / generation / resourceVersion、RBAC、ServiceAccount、informer cache、finalizer、Pod / RuntimeClass | warm pool lifecycle、资源删除安全、SandboxPool proposal、mTLS 部署边界 |
| 云原生交付 | Helm、Docker / buildx、multi-arch、GitHub Actions、DCO、codegen、release version | AgentCube push validation、release version、native builder、Dependabot、runner pinning、Go update workflow 及 fork validation |
| Python 与 Agent 工具链 | Python SDK、MCP、HTTP / SSE / stdio、OpenAI-compatible provider | `math-agent`、Code Interpreter MCP SDK v2、Python SDK tests |
| 测试与性能工程 | p50 / p95 / p99、并发、warm hit / miss、counterfactual、E2E、cleanup、CI 日志分析 | warm pool benchmark、buildx A/B、Karmada flake RCA、v0.5.x migration E2E |
| 架构与 Review | 控制面 / 数据面、状态所有权、事务边界、失败恢复、Clean Architecture、scope control | Session Runtime、Sleep / Resume、SandboxPool、AgentENV / Volcano / Kthena 对照和 PR Review |
| 开源协作 | fork / upstream、topic branch、PR 模板、review comment、维护者角色、证据与状态表达 | 23 个 PR、5 个 issue、至少 12 个他人 PR Review，以及分支与发布流程规范 |

## 四、主要任务、输出与结果

### 4.1 AgentCube 运行基线、性能测评与竞品分析

实习开始阶段先完成端到端运行基线：本地部署 AgentCube，跑通 Redis、Workload Manager、Router、PicoD、CodeInterpreter、Python SDK 和 `math-agent`，随后把 sandbox 基础设施耗时与 LLM / Agent 规划耗时分开。

主要输出：

- AgentCube sandbox 顺序 5 次测试 `total` p50 约 `177.14 ms`。
- 并发 10、`warmPoolSize=2` 时 p50 约 `7315.21 ms`，定位为预热池容量不足导致 pool miss。
- `warmPoolSize=10` 时 p50 约 `436-565 ms`，p95 约 `804-933 ms`；`warmPoolSize=20` 没有继续改善，证明预热池不是越大越好。
- 同机 cage-bro 顺序 p50 约 `18.41 ms`，但报告明确区分本地轻量沙箱与 Kubernetes 管理 sandbox 的隔离和生命周期边界，没有按倍率直接判断产品优劣。
- 形成 AgentCube、forkd、CubeSandbox、cage-bro、OpenSandbox、Agent Substrate、E2B、AgentENV 等项目的能力与证据矩阵。

证据入口：[Week 1 总结](week1-summary.md)、[Day 5 sandbox latency](day5-sandbox-latency-and-competitor-analysis.md)、[Day 8 竞品能力矩阵](day8-sandbox-competitor-capability-matrix.md)。

### 4.2 CodeInterpreter 与 agent-sandbox 版本兼容

AgentCube 的 CodeInterpreter 依赖 agent-sandbox 的 CRD、warm pool、claim 和 owner reference 语义。版本升级不仅是修改依赖版本，还会影响 API package、stored version、对象 adoption、NetworkPolicy、E2E manifest、SDK 和 cleanup。

主要输出：

- AgentCube PR [#387](https://github.com/volcano-sh/agentcube/pull/387) 将 CodeInterpreter warm pool 适配到 agent-sandbox v0.4.6，补充真实 deadline 与目标 E2E，2026-07-16 合入。
- 在不依赖作者方案的情况下独立实现并验证 v0.5.2 / v0.5.3 adapter，覆盖 v1beta1 API、UID adoption、delete / GC、pool refill 和 conversion webhook 等风险。
- 对 AgentCube agent-sandbox 升级 PR #442 / #446 做多轮 exact-head Review，区分 correctness finding、scope finding、CI discovery 和维护者 policy decision。
- AgentCube PR [#448](https://github.com/volcano-sh/agentcube/pull/448) 完成 Code Interpreter MCP SDK v2 迁移，local Streamable HTTP、stdio、Docker rollout、in-cluster MCP E2E 与 exact-head checks 通过，2026-07-30 合入。
- AgentCube PR [#385](https://github.com/volcano-sh/agentcube/pull/385) 实现 `WarmPoolAvailable`，当前代码和验证已完成但仍等待 maintainer review，不能表述为已合入。

证据入口：[Week 6 总结](week6-summary.md)、[Day 50 v0.5.2 独立适配](day50-agent-sandbox-v052-independent-adaptation.md)、[Day 55 v0.5.x Review](day55-pr442-agent-sandbox-v052-new-head-review.md)。

### 4.3 CI、release 与构建性能工程

这一方向的目标是让普通贡献者分支能得到可信验证，并减少版本、镜像和 GitHub Actions 的长期漂移。

| PR | 输出 | 状态 / 效果 |
| --- | --- | --- |
| AgentCube #391 | Go toolchain 升级到 1.26.4，作为依赖兼容的独立前置 | 已合入 |
| AgentCube #403 | 删除未进入默认 chart / release / E2E 的 `agentd` | 已合入，15 个文件净删除 683 行 |
| AgentCube #414 | 为 9 类既有 workflow 增加 branch push validation | 已合入，fork 9/9 checks 通过 |
| AgentCube #415 | 增加 proposal 索引、模板和贡献入口 | 已合入 |
| AgentCube #416 | 分离 Docker tag、Helm chart version 与 app version | 已合入，真实 release run 生成并推送 `agentcube-0.0.0.tgz` |
| AgentCube #420 | multi-arch image 使用原生 Go builder，保持目标架构不变 | 已合入；job wall time 从 1610 秒降到 331 秒，约减少 79.4% |
| AgentCube #422 | 覆盖非标准路径 Dockerfile 的 base image Dependabot | 已合入，并由真实 fork-generated PR 验证 |
| AgentCube #423 | 将 11 个浮动 `ubuntu-latest` 固定到 `ubuntu-24.04` | 已合入；actionlint、YAML 与 9/9 checks 通过 |
| AgentCube #429 | 每周检查 Go 版本并同步 `go.mod` 与 3 个 builder tag | 仍开放；实现已提交，维护者决策与 rebase 不由本人单方面决定 |

证据入口：[Week 4 总结](week4-summary.md)、[Week 5 总结](week5-summary.md)、[Day 38 release failure](day38-release-image-ci-helm-chart-version-failure-analysis.md)、[Day 39 buildx optimization](day39-karmada-image-build-and-agentcube-buildx-performance-optimization.md)。

### 4.4 架构设计与实质 PR Review

实习后半段把 Review 从“看 diff 和样式”推进到“恢复系统状态机、调用链和失败路径”。重点对象包括：

- AgentCube SandboxPool proposal #431：检查 status writer、per-node ownership、heartbeat、generation freshness、RuntimeClass / CRI 接线、cleanup、downscale reservation 和 RBAC。
- AgentCube PicoD metrics PR #400：用 32 个自定义 HTTP method 复现无界 label cardinality，作者随后增加 bounded method taxonomy 和真实 middleware tests。
- AgentCube CodeInterpreter ownership PR #450：发现“检查 ownership 后再按名称 DELETE”存在对象替换窗口，推动加入 UID / resourceVersion precondition 和 replacement regression tests。
- AgentCube Router -> PicoD mTLS issue #444：区分 TLS 终止、Router 身份验证、PicoD identity、JWT target binding 和 sidecar key isolation，不把“启用 TLS”误写成完整身份安全。
- AgentCube AgentRuntime examples PR #437：通过容器级 TERM 行为验证 PID 1 cleanup，作者修复后复核代码路径，同时保留“现有 E2E 未直接覆盖 termination”的证据边界。

为避免多轮 force-push 后只检查旧 finding，进一步形成 exact-head Review 方法：冻结 base / head / merge-base，逐个解释 hand-written changed file，检查 changed tests 是否被 CI 实际发现，区分 GitHub checks 名称与具体命令执行证据，并对外部 URL、build constraints、clean worktree 和直接测试 fallback 设 fail-closed 门禁。

证据入口：[Day 30 AgentCube PR #387 Review](day30-pr387-warm-pool-dataflow-review.md)、[Day 44 SandboxPool Review](day44-sandbox-pool-management-proposal-review.md)、[Day 54 mTLS 设计](day54-issue444-router-picod-mtls-design-screening.md)、[Day 58 ownership Review](day58-pr450-codeinterpreter-child-ownership-review.md)。

### 4.5 Karmada 与工具链跨项目贡献

为验证工程方法能否迁移到其他大型 Kubernetes 项目，实习期内在 Karmada 创建 7 个 PR，其中 6 个已合入、1 个仍开放；在 drawio-skill 创建 2 个 PR 并全部合入。

代表性输出：

- Karmada #7728：将 18 个 workflow 固定到 Ubuntu 24.04，完整 CI 通过后合入。
- Karmada #7732：等待 FlinkDeployment control-plane CRD、member CRD 和 `Cluster.Status.APIEnablements` 三层 cleanup，关闭 #7719 后合入。
- Karmada #7777：证明 `RemedyActions` 变化未触发 reconcile，形成 test-only fail -> fix pass -> reverse-patch fail 的局部因果证据，合入并关闭 #7776。
- Karmada #7697：设计并实现 init-managed certificate rotation，覆盖身份绑定、共享 CA、远端恢复和部分写入重跑；当前仍开放等待 human review。
- drawio-skill #49 / #94：补充 edge label overlap 检查，并修复 distribution version 与 marketplace metadata 漂移，均已合入。

### 4.6 文档、测试报告与可复用资产

| 类型 | 数量 | 说明 |
| --- | ---: | --- |
| 编号日报主题 | 60 | Day 1 至 Day 60 |
| Day 报告 Markdown | 69 | 部分 Day 拆成主报告、Review 草稿或专项分析 |
| 周总结 | 9 | Week 1 至 Week 9；Week 9 为 8 月 3 日至 8 月 11 日的收尾延长周 |
| 图示资产 | 28 | 19 个 PNG、5 个 draw.io、4 个 Mermaid source；包含本总结的系统位置图 |
| benchmark / review 原始文件 | 143 | 约 2.8 MiB，包含 JSON、日志、closure ledger 和测试证据 |
| 上游 PR | 23 | AgentCube 14、Karmada 7、drawio-skill 2 |
| 上游 issue | 5 | AgentCube 2、Karmada 3 |
| 他人 PR 实质 Review | 至少 12 | 保守统计；只计同一证据期内创建且可由 `reviewed-by` 定位的他人 PR |

## 五、输出数量与状态明细

### 5.1 上游 PR 统计

| 项目 | 创建 PR | 已合入 | 仍开放 | 已关闭未合入 |
| --- | ---: | ---: | ---: | ---: |
| AgentCube | 14 | 11 | 2（#385、#429） | 1（#390 fork validation） |
| Karmada | 7 | 6 | 1（#7697） | 0 |
| drawio-skill | 2 | 2 | 0 | 0 |
| **合计** | **23** | **19** | **3** | **1** |

> 注释：open PR 表示本人已完成当期提交或验证，但外部 review / merge 仍由维护者负责。本文不把 open 写成 merged，也不把绿色本地测试写成社区接受。

### 5.2 代表性测试与版本证据

| 工作 | 版本 / head | 测试证据 | 边界 |
| --- | --- | --- | --- |
| AgentCube #387 | agent-sandbox v0.4.6 | official 12/12 checks、目标 CodeInterpreter E2E、deadline regression | 未把后续 v0.5.x 行为算入该 PR |
| AgentCube #448 | MCP Python SDK v2 | local HTTP / stdio / Docker / in-cluster MCP E2E，upstream 13/13 checks | 只覆盖 Code Interpreter MCP migration |
| AgentCube #385 | v0.5.3-based current branch | upstream 非 Tide 13/13、fork 9/9 workflows、CodeInterpreter E2E | 当前仍等待 maintainer labels / review |
| v0.5.3 adapter | fork commit `5957314` 后续验证线 | lint、gen-check、build、non-E2E Go、race、k3d v1.32.5 migration E2E | fork 证据，不是竞争 upstream PR |
| Multi-arch build | AgentCube #420 | 两组 branch checks、产物架构核对、1610 s -> 331 s | 未宣称 PicoD 的 arm64 系统包安装已优化 |
| Karmada flake fix | #7732 / #7777 | cleanup E2E、test-only / fix / reverse-patch 因果验证 | 与 CI host I/O stall 分开处理 |

## 六、最有成就感的工作

### 6.1 把 AgentCube 兼容 PR #387 从“编译兼容”推进到真实生命周期证据

这个任务最能代表两个月能力变化。初期容易把依赖升级理解为修改 import 和版本号，实际 Review 证明还要处理 warm-pool adoption、claim deadline、owner reference、NetworkPolicy、manifest 版本、SDK 与 cleanup。最终通过真实 target E2E、deadline 进入 I/O context、运行版本和测试选择门禁，使 PR 在 2026-07-16 合入。

成就感来自两点：一是代码进入真实上游主线；二是形成了可以复用的判断，之后面对 v0.5.2 / v0.5.3 不再从编译错误开始，而是先列 migration、storage、lifecycle、auth、cleanup 和 E2E 风险。

### 6.2 用 AgentCube 构建 PR #420 把 27 分钟缩短到约 5.5 分钟

AgentCube release 慢的直觉解法可能是增加 cache 或并行 matrix。实际先对构建阶段计时，定位主要瓶颈是 arm64 Go compiler 在 QEMU 下执行，再只修改 3 个 Dockerfile 的 builder platform，使编译在 runner 原生架构执行，最终 target stage 仍输出 amd64 / arm64 镜像。job wall time 从 1610 秒下降到 331 秒，约减少 79.4%，同时保持 PR scope 很小。

这项工作证明性能优化需要“测量 -> 定位 -> 最小改动 -> 产物验证”，而不是先写方案再找数据。

### 6.3 从参与 Review 到建立可执行 Review 门禁

对 AgentCube SandboxPool #431、agent-sandbox 升级 #442 / #446、CodeInterpreter ownership #450 等多轮 PR 的 Review 暴露了一个问题：作者 force-push、rebase 或 squash 后，旧 finding 即使逐条关闭，也不能证明最终 head 满足 parent Issue。后续把 exact refs、scope closure、changed-test discovery、CI evidence 和 direct fallback 编码成 review harness，并用已知遗漏做回放。

这项工作没有直接增加产品功能，但提高了 Review 的可复核性，也让本人看到“Review 完成”应由完整风险面和最终版本证据决定，而不是由评论数量决定。

## 七、完成不理想的工作与原因

### 7.1 AgentCube WarmPoolAvailable PR #385 尚未合入

本人已完成实现、v0.5.3 rebase、Event RBAC、测试和 fork / upstream checks，但该 PR 同时受 agent-sandbox 升级、ownership 修复和维护者 review 时序影响。实习期内完成的是“可审查提交与验证”，不是“合入结果”。

改进：更早识别依赖链，把 feature、runtime prerequisite 和 repository-wide follow-up 画成明确依赖图；对外汇报使用“已提交 / 等待 review”，避免把维护者时序变成本人的未完成感。

### 7.2 MicroVM / KVM 竞品没有完成真实运行 benchmark

早期机器缺少 `/dev/kvm`；当前机器虽然存在设备并暴露 VT-x，但用户不在 `kvm` 组，仍不能完成真实 Firecracker / MicroVM 路径验证。继续在同一环境反复调试不会产生可靠结果。

改进：在 benchmark 计划开始前把 kernel、glibc、CPU virtualization flags、`/dev/kvm` 权限和容器 runtime 列为硬前置；不满足时及时切换到源码 / 官方数据研究，并明确“官方数据、工程推断、本机实测”的证据等级。

### 7.3 调研与文档投入一度过大

69 份 Day 报告保留了完整证据，但部分阶段的调研面过宽，导致社区任务选择和 open PR 收敛速度下降。高质量记录有价值，但不能替代可交付的代码、Review decision 或测试结果。

改进：后半段开始使用 weekly priority、stop condition、contribution value gate 和 reviewer-visible concise-first 规则。今后每个调研任务开始前先写清“要支持哪个决策”，达到决策证据后停止扩展。

### 7.4 AgentCube Go 自动升级 PR #429 长期处于开放状态

工作流实现已完成，但 Go baseline 后续连续变化，上游 main 和 PR base 多次前进，且自动升级工具本身属于长期治理能力，需要维护者确认 ownership 和 review 方式。单纯继续叠加提交不能解决决策问题。

改进：将新 toolchain 兼容性先在基于最新 upstream/main 的临时 fork 分支验证，再以最小差异更新 open PR；若维护者更倾向其他方案，应及时收敛或关闭，而不是把 sunk cost 当成继续维护的理由。

## 八、困难、对策与解决方法

| 困难 | 现象 | 原因判断 | 采取的对策 | 结果 |
| --- | --- | --- | --- | --- |
| Kubernetes 环境差异 | standard kind 在 kubelet / cgroup / QoS 初始化失败 | 主机 cgroup / runtime 条件与项目默认假设不匹配 | 使用可工作的 k3s / k3d；记录 host 信息；三次同类失败后停止硬调 | 完成 AgentCube 与 v0.5.3 focused E2E，同时保留 kind 限制 |
| KVM 不可用 | forkd / Firecracker 无法运行 | `/dev/kvm` 缺失或当前用户无权限 | 运行前置检查；不伪造 MicroVM 数据；切换源码与官方证据研究 | 避免错误性能比较，形成 benchmark host checklist |
| CI 绿色但目标未执行 | AgentCube 兼容 PR #387 原 E2E 安装旧 runtime，目标 case 在 mTLS 下 skip | runtime version skew 与 test selection 同时存在 | 检查安装日志和 test filter；加入强制目标 job 与版本门禁 | v0.4.6 真实生命周期实际执行并通过 |
| timeout 不能取消请求 | timer 到时后同步 GET 仍阻塞并返回迟到 success | timer channel 没有进入 HTTP context | 把 deadline 传入 client-go GET context，并在 success 前复核 | 形成可复现反例和 regression test |
| API / CRD 版本变化 | v1alpha1 / v1beta1 package、字段和 owner 语义变化 | 版本升级同时改变编译、storage 与 lifecycle | 将兼容分为 compile、storage、lifecycle、auth、cleanup、E2E 六层 | v0.4.6 合入，v0.5.x 独立验证可复用 |
| Review 信息量大 | 短评论缺少上下文，长评论又难扫描 | finding 没有稳定的 trigger -> consequence -> evidence 结构 | 使用 code locator、最小反例、Mermaid 和 concise-first；作者修改后复核 exact head | Review 更易理解，减少重复解释 |
| 多任务时间冲突 | 调研、PR、Review、周报同时推进 | 缺少明确优先级和停止条件 | 用 TODO、周目标、active thread 和 stop conditions；已有 assignee / PR 时转向 Review | 减少重复认领和无效实现 |
| 开源沟通边界 | bot、AI reviewer、作者回复和 maintainer decision 容易混淆 | 不同角色的决定权不同 | 区分作者修正、CI 结果、human review 与 maintainer approval；上游文本先确认 exact target / body | 状态表达更准确，避免把建议写成社区共识 |

## 九、完成任务过程中的感受与收获

第一，开源工程的完成标准不是“代码写完”。一个改动从需求到合入，还需要 scope、兼容、测试、CI、文档、DCO、review 和维护者决策。本人逐步学会把“我完成的工作”和“社区尚未完成的外部状态”分开表达。

第二，控制器和分布式系统最容易出问题的地方不是 happy path，而是状态所有权、对象替换、缓存 freshness、重试、部分失败和 cleanup。只有把 producer、state store、reconcile、delete 和 recovery 串起来，Review 才能发现真实风险。

第三，benchmark 的价值主要在口径。p50 数字只有和样本数、并发、warm hit、pool size、运行环境、失败率和 cleanup 一起出现才有意义；不同隔离等级、不同操作和不同硬件的数据不能为了展示效果而直接比较。

第四，AI 工具可以加速资料检索、脚本执行、测试矩阵和文档整理，但不能替代工程判断。最终需要由人确认需求边界、证据等级、社区状态和对外表达。实习后半段把 AI 从“生成代码”更多地用于“恢复上下文、检查遗漏、保存证据和执行回归门禁”。

第五，本次实习让我明确了后续方向：继续深耕 Agent 基础设施中的 runtime lifecycle、Kubernetes control plane、请求路由、sandbox 安全和可观测性，同时保持跨项目 Review 能力。相比只完成一个功能，更希望具备判断一个设计是否能长期维护、一个测试是否真正覆盖风险、一个 PR 是否适合进入社区主线的能力。

## 十、可复用的工程方法总结

1. **先恢复系统边界，再看 diff**：明确入口、状态所有者、控制面、数据面和外部依赖。
2. **先拆前置，再做功能**：通用 toolchain / compatibility prerequisite 独立验证，feature PR 只保留自身语义。
3. **把风险映射到测试**：成功、失败、并发、重试、对象替换、cleanup 和真实 E2E 分层覆盖。
4. **冻结版本与证据**：Review 和测试绑定 exact head；绿色 check 名称不等于目标命令实际执行。
5. **区分事实等级**：本机实测、源码支持、上游官方数据、工程推断分别陈述。
6. **让评论推动一个决定**：给出触发条件、后果、证据和最小下一步，不把完整实习报告粘贴到上游。
7. **把失败也作为输出**：记录失败命令、现象、根因、绕过和停止条件，避免下一轮重复消耗。

## 十一、答辩陈述建议（8-10 分钟）

| 时间 | 内容 | 建议重点 |
| ---: | --- | --- |
| 1 分钟 | 项目与职责 | AgentCube 是 Kubernetes 上的 Agent sandbox / session runtime 基础设施；本人聚焦 Workload Manager、CodeInterpreter 生命周期、CI 与 Review |
| 1 分钟 | 两个月路线 | 从跑通系统、benchmark，到版本兼容、CI / release，再到架构 Review 和跨项目验证 |
| 2 分钟 | 代表工作一 | AgentCube 兼容 PR #387：为什么依赖升级不只是改版本；如何补 deadline、E2E 和 cleanup 证据 |
| 1.5 分钟 | 代表工作二 | AgentCube 构建 PR #420：用 A/B benchmark 将 1610 秒降到 331 秒，并保持 3 行最小 scope |
| 1.5 分钟 | 代表工作三 | AgentCube SandboxPool #431、agent-sandbox #446、ownership #450：如何从 diff Review 推进到状态所有权、对象替换和 exact-head 门禁 |
| 1 分钟 | 输出数据 | 23 PR、19 合入、5 issue、至少 12 个他人 PR Review、60 个日报主题和完整测试资产 |
| 1 分钟 | 困难与改进 | KVM / kind 环境、CI 假绿、调研过宽；分别用前置检查、目标测试门禁和 stop condition 处理 |
| 1 分钟 | 收获与方向 | 形成 Agent runtime + Kubernetes control plane + evidence-driven Review 的能力闭环 |

## 十二、证据索引

- [Week 1：AgentCube 调研、测评与协作](week1-summary.md)
- [Week 2：从写代码转向审代码与工程判断](week2-summary.md)
- [Week 3：Session Runtime Control Plane](week3-summary.md)
- [Week 4：可验证的工程闭环](week4-summary.md)
- [Week 5：构建、CI、版本适配与架构 Review](week5-summary.md)
- [Week 6：agent-sandbox 适配、Karmada 修复与 PR Review](week6-summary.md)
- [Week 7：版本升级 Review、运行时安全与 Karmada 调度修复](week7-summary.md)
- [Week 8：MCP SDK v2 合入、v0.5.3 独立验证与 Final-Head Review](week8-summary.md)
- [Week 9：Ownership 修复验收、升级实证与实习收尾](week9-summary.md)
- [Day 57：Agent Review harness 评估](day57-agent-autoharness-trajectory-evaluation.md)
- [Day 58：CodeInterpreter child ownership Review](day58-pr450-codeinterpreter-child-ownership-review.md)
- [Day 59：AgentENV Kubernetes 边界研究](day59-kvcache-ai-agentenv-kubernetes-boundary-study.md)
- [Day 60：Volcano / Kthena 架构研究](day60-volcano-kthena-architecture-and-project-study.md)

> 最终结论：本次实习完成了从项目入门、功能开发、版本兼容、测试与 CI，到架构 Review、开源协作和方法沉淀的完整训练。可量化结果以 19 个已合入 PR 为代表，可复用能力则体现在对 Agent sandbox 生命周期、Kubernetes 控制面、失败路径、测试证据和社区状态的系统判断。
