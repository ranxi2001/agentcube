# Week 5 总结：从构建与 CI 维护走向版本适配和架构 Review

日期：2026-07-06 至 2026-07-10

证据截止：2026-07-10 23:59 CST

## 第一层：可汇报成果

这一部分只保留经理可以快速读取的结果、状态和下一步。详细技术判断、失败过程和验证证据放在后半部分。

### 1. 本月目标

| 目标 | 状态 |
| --- | --- |
| 完成 AgentCube 的 agent-sandbox v0.5 适配验证 | 进行中 |
| 实现 AgentCube 和 Karmada 构建、基础镜像与 CI 环境维护 | 进行中 |
| 参与 AgentCube 代码及 Feature Proposal Review | 进行中 |

### 2. 本周进展

| 工作项 | 结果、价值或剩余风险 | 完成时间 | 状态 |
| --- | --- | --- | --- |
| AgentCube 与 Karmada 构建和 CI 维护 | 合入 4 个 PR：AgentCube #420、#422、#423 优化多架构构建、基础镜像更新与 runner 稳定性；Karmada #7728 将 18 个 workflow 更新到 Ubuntu 24.04 | 7/9 | 已完成 |
| Go 版本自动升级 | 提交 PR #429：每周检查 Go 新版本并创建待 review PR，同步更新 `go.mod` 与 3 个 Dockerfile；验证已通过，等待社区 review | 待社区评审 | 进行中 |
| 参与 #431 Feature Proposal Review | 提出 stale status/heartbeat、Static Pod 重建语义、RuntimeClass/containerd 路由 3 个实现问题；作者于周内补充设计，三条 review thread 均已解决 | 7/10 | 已完成（本周 review 点） |
| agent-sandbox v0.5 适配 | 完成运行时 adapter 和对象身份调整，关键单测、构建、lint、生成检查、Ubuntu 24 kind runtime 与 fork CI 通过；旧 CRD 迁移和 direct WorkloadManager mTLS harness 尚未验证 | 待补充验证 | 进行中 |

### 3. 收获与分享

Go baseline 升级不是单个镜像 tag 更新：`go.mod` 是语言版本基线，CI 从它读取版本，3 个 Docker builder 也必须同步。自动化只有在跨文件一致性和合并前验证都被编码后，才真正减少维护成本。

### 4. 疑惑与问题

agent-sandbox v0.5 的旧 CRD migration 与 direct WorkloadManager CodeInterpreter/warm-pool mTLS 客户端证书链路尚未验证。默认 AgentRuntime mTLS 已通过，但当前本地适配仍不能写成 AgentCube 已正式支持 v0.5，也不应在证据不完整时提交 upstream。

### 5. 下周计划

| 任务 | 可验收结果 |
| --- | --- |
| 跟进 PR #429 | 处理维护者反馈，保持只负责 Go toolchain baseline 同步，不混入普通 module dependency 更新 |
| 补齐 agent-sandbox v0.5 证据 | 验证旧 CRD migration、conversion webhook 与 direct WorkloadManager mTLS harness，形成是否可提交 upstream 的明确结论 |

### 活动指标

| 指标 | 数量 | 去重对象 |
| --- | ---: | --- |
| 周内创建的 PR | 4 | AgentCube #422、#423、#429；Karmada #7728 |
| 周内合并的本人 PR | 4 | AgentCube #420、#422、#423；Karmada #7728 |
| 实质 Review 的 PR | 1 | AgentCube #431 |
| 分析并形成去重决策的 issue | 17 | #432、#430、#408、#406、#404、#397、#395、#394、#388、#386、#381、#375、#374、#365、#362、#348、#272 |
| 可执行 proposal review 点 | 3 条提出 / 3 条解决 | #431 SP-09、SP-01、SP-02 |

> 注释：活动指标按唯一 PR / issue 去重，不把 commit 数、机器人评论、格式评论或单纯 LGTM 当成工程影响。

## 第二层：学习与工程记录

这一层保留需求拆分、组件 contract、失败修正、测试与残余风险。它用于继续提升开发和架构 review 能力，不要求原样放进公司周报。

### 本周工程主线

Week 5 的主线由三部分组成：将 Week 4 的性能结论合入主线；把一次性 CI 修复升级为可持续的依赖和工具链治理；把 review 从“发现文档问题”推进到“核对 Kubernetes、CRI 和 containerd 的真实 integration contract”。

```text
已验证性能修复合入
  -> 自动化基础镜像与 Go baseline 维护
  -> 固定可复现 CI 环境
  -> 用相同的 contract 思维审 proposal
  -> 对新版 runtime 适配保留证据门槛
```

这周没有把所有发现都转成 upstream 代码。agent-sandbox v0.5 adapter 虽然关键路径和默认 AgentRuntime mTLS 已通过，但旧对象 migration 与 direct WorkloadManager mTLS harness 未闭环，因此保留在本地验证分支；社区 task screening 也接受“没有合适的无主高优任务”这一结果，避免为了产出数量重复认领或扩大范围。

### 需求拆分与架构边界

| 问题 | 拆分决定 | 组件职责或依赖方向 | 未解决部分 |
| --- | --- | --- | --- |
| 多架构 build 为什么慢 | builder 在 host platform 原生编译，target stage 继续产出目标架构镜像 | Dockerfile 负责 builder/target 平台边界，release workflow 不承担编译策略修补 | PicoD 的 arm64 系统包安装仍是独立瓶颈 |
| 哪些镜像交给 Dependabot | updater 管 Alpine/Ubuntu 等 runtime base image，忽略 `golang` builder | 普通 Docker 依赖与 Go language baseline 分离维护 | 自动 PR 仍需逐个验证兼容性，不能自动合并 |
| Go 新版本如何自动跟进 | scheduled workflow 读取版本、统一修改 `go.mod` 与 3 个 Dockerfile，并创建待 review PR | `go.mod` 是 source of truth；Docker builder 与 CI 必须保持一致 | PR #429 仍在 review，自动化长期稳定性待真实周期验证 |
| runner OS 如何治理 | 把浮动 `ubuntu-latest` 固定为 `ubuntu-24.04`，保留已有明确 `ubuntu-22.04` | 明确版本保证 CI 可复现；老 runner 是否升级属于另一项兼容性工作 | 需要按 workflow 特性审计后续 runner 升级，不能机械替换 |
| agent-sandbox v0.5 是否完成适配 | 把编译、API/object-flow、CRD migration、网络与 mTLS 分层验证 | WorkloadManager/provider adapter 消化 SandboxClaim、Sandbox、Pod 身份；Store 保留控制身份 | 旧 CRD migration、conversion webhook 和 direct WorkloadManager mTLS harness 尚未闭环 |
| #431 的节点 runtime 路径是否成立 | 分开审 stale status、Static Pod 资源锁、containerd named runtime 与 runtime v2 shim lifecycle | controller 负责聚合 phase 与超时判断；kubelet 调用唯一 CRI endpoint；containerd 按 handler 选择 named runtime/shim | proposal 整体仍在进行，后续实现需要 task lifecycle spike 和 failure-path e2e |

### 本周实际完成

#### 1. 合入多架构 native Go builder 优化

PR #420 于 7 月 7 日合并。它延续 Week 4 已完成的 A/B benchmark，只修改 3 个 Dockerfile 的 builder platform，让 Go 编译在 GitHub runner 原生架构执行，最终 target stage 仍生成 amd64/arm64 镜像。

这个 PR 的价值不只是“构建更快”，而是证明了最小改动可以解决主要瓶颈：job wall time 从 1610 秒降到 331 秒，下降 79.4%，同时没有把 cache、matrix 或 PicoD 系统包优化塞进同一个 PR。

#### 2. 建立 Docker base image 自动更新边界

PR #422 配置 Dependabot 扫描 `/docker` 下非标准命名的 Dockerfile，并用真实 fork-generated Alpine/Ubuntu update PR 验证 updater 能找到目标文件。它于 7 月 7 日合并。

关键边界是继续忽略 `golang` builder image。Go toolchain 不是普通 runtime base image，只更新 Docker tag 会让 Docker 构建与 `go.mod`、CI 使用不同语言版本。

> 注释：Dependabot 可以发现依赖更新，但不代表每类依赖都适合独立升级。能够自动开 PR，不等于具备跨文件语义一致性。

#### 3. 固定 AgentCube 与 Karmada runner 环境

AgentCube PR #423 将仍使用 `ubuntu-latest` 的 11 个 workflow 固定到 `ubuntu-24.04`，并保留 e2e 中已有的明确 `ubuntu-22.04`，因为后者是否升级需要单独兼容性验证。YAML、actionlint 和 fork push 9/9 checks 均通过，PR 于 7 月 9 日合并。

Karmada PR #7728 同样将 18 个 workflow 固定到 Ubuntu 24.04，并通过 lint、compile、unit、codegen、image、compatibility 和 e2e 等检查，于 7 月 9 日合并。

> 分析：`ubuntu-latest` 当天并不一定错误，风险在于它会被平台迁移。CI 的职责是可复现，因此显式 runner label 是稳定性选择；已经显式固定的旧版本则不能当作“漏网之鱼”机械升级。

#### 4. 提交 scheduled Go toolchain maintenance

PR #429 把 Go baseline 升级拆成独立自动化：每周检查新版本，统一更新 `go.mod` 与 3 个 Dockerfile 的 Go builder tag，执行一致性与基础验证后创建待人工 review 的 PR。

Week 5 截止时 PR 已提交且验证通过，但仍等待社区 review。它不自动合并，也不混入普通 Go module dependency 更新。

#### 5. 完成 agent-sandbox v0.5 本地适配验证

正式 v0.5 同时保留 v1alpha1 与 v1beta1 API，并通过 multi-version CRD 和 conversion webhook 提供迁移窗口。适配工作处理了依赖、API 常量、SandboxClaim / Sandbox / Pod 对象身份和 runtime adapter 变化。

已完成的验证包括：

- 相关 Go unit tests；
- `make build-all`、lint 与生成代码检查；
- Ubuntu 24 kind runtime 场景；
- fork branch 9/9 validation checks。

尚未完成的验证包括：

- 已存在 v1alpha1 CRD / object 的升级迁移；
- conversion webhook 在真实升级路径中的行为；
- direct WorkloadManager CodeInterpreter/warm-pool 的客户端证书 mTLS harness；
- 正式 upstream PR 的最小 scope 评估。

默认 AgentRuntime mTLS 路径已经验证；缺口是绕过 Router、直接访问 WorkloadManager 的 CodeInterpreter/warm-pool client-cert harness。这个区别必须保留，避免把“部分安全路径未覆盖”误写成“mTLS 完全未测试”。

> 分析：依赖能编译、全新集群能运行、旧集群能升级是三种不同结论。本周只证明了前两类中的关键路径，不能由此推导第三类已经成立。

#### 6. 对 #431 做 contract-first Feature Proposal Review

本周对 SandboxPool proposal 提出三条 substantive inline review：

| Review 点 | 原问题 | 作者周内修正 | Week 5 状态 |
| --- | --- | --- | --- |
| SP-09 stale status / heartbeat | Node 仍存在但 node agent 停止时，旧的 Healthy/Ready condition 可能永久残留 | 增加 `PlaceholderAgentHealthy` 和 heartbeat 语义，让 controller 有独立健康信号 | 已解决 |
| SP-01 Static Pod resize | 文档把资源调整描述为类似 VPA / in-place resize，但 Static Pod manifest 变化会触发重建 | 明确改为 local manifest delete-and-recreate，并区分 node-level cgroup 与 mirror Pod 窗口 | 已解决 |
| SP-02 RuntimeClass / CRI routing | 文档暗示 RuntimeClass 可让 kubelet 改连第二个 CRI socket，和 Kubernetes/CRI contract 不符 | 改为 kubelet 调用 containerd，containerd 根据 handler 选择 runtime v2 shim | 已解决 |

这三条 thread 解决的是 proposal contract，不代表 proposal 已实现、已通过 maintainer 架构批准或整体 review 完成。后续 heartbeat timeout 的 time-driven reconcile、runtime v2 shim 的 `Create/Start/Wait/Delete`、PID 与 no-process 假设仍需最小 spike 和 failure-path e2e。

#### 7. 完成社区任务去重筛选

Day40 与 Day45 对最新和积压 issue 做了 owner、状态、重现条件、环境约束与重复工作检查，17 个 issue 被归入等待作者、已有负责人、需要环境、适合 review 或暂不介入等决策。

最终没有发现 A 级无主且可立即实现的任务。这是一次有效 triage，而不是“没有产出”：open issue 不等于 bug 仍存在，assignee 为空不等于没有人在推进，缺少特定集群或硬件也会改变任务是否适合当前接手。

### Review 与测试映射

| 风险 | Review 发现或设计决定 | 验证证据 | 残余风险 |
| --- | --- | --- | --- |
| builder platform 优化破坏 multi-arch 产物 | host 原生 builder 与 target architecture 分离 | Week 4 A/B benchmark、fork checks、upstream #420 checks | PicoD arm64 apt/Python 安装未优化 |
| Dependabot 误升 Go builder | Docker updater 显式忽略 `golang`，Go baseline 交给独立 workflow | fork-generated Alpine/Ubuntu PR、配置 diff、#422 CI | 自动 PR 仍需人工判断 breaking changes |
| runner 替换引入 YAML 或 action 兼容问题 | 只替换浮动 label，保留明确旧 label | actionlint、YAML parse、AgentCube 9/9 checks；Karmada 全套 checks | 后续 OS major upgrade 仍需针对性验证 |
| Go baseline 多文件漂移 | `go.mod` 与 3 个 builder tag 原子更新并加一致性检查 | #429 helper/workflow 本地验证和真实 schedule run | PR 尚未合并；未来 Go release 格式变化需观察 |
| v0.5 adapter 在新集群通过但旧集群升级失败 | 将 fresh install 与 migration 分开，不提交 upstream | unit/build/lint/gen、Ubuntu 24 kind runtime、默认 AgentRuntime mTLS、fork 9/9 | migration、conversion webhook、direct WorkloadManager mTLS harness 未验证 |
| #431 文档方向正确但实现 contract 不成立 | 用 controller stale status、Kubernetes Static Pod、CRI RuntimeHandler、containerd runtime v2 contract 校准 | 三条 inline review、作者三次更新 proposal 并 resolve | timeout reconcile、shim task lifecycle、故障恢复和资源记账仍需实现验证 |

### 卡点、失败与处理

| 失败步骤 | 现象 | 根因 | 处理与当前状态 |
| --- | --- | --- | --- |
| 将 Go builder 交给 Docker Dependabot | 自动升级看似可行，但只会修改 Dockerfile | Go baseline 同时存在于 `go.mod`、CI 和 3 个 Docker builder | #422 忽略 `golang`；另建 #429 做跨文件一致升级 |
| runner OS 全量替换 | 审计时发现 e2e 仍是 `ubuntu-22.04` | 它是明确版本，不属于浮动 `latest` 风险；升级可能改变 e2e 环境 | #423 保持最小范围，只替换 11 个 `ubuntu-latest` |
| 仅凭 v0.5 编译成功判断适配完成 | v1alpha1 兼容包仍存在，容易产生“已经升级”的错觉 | 正式版提供兼容窗口，但资源语义和旧 CRD migration 仍不同 | 建立分层验证口径，本地保留 adapter，暂不上游 |
| #431 stale Ready 设计 | node agent 停止但 Kubernetes Node 仍存在时，旧 True conditions 可能持续保留 | phase aggregator 没有独立 agent heartbeat/health signal | inline review 后作者增加 `PlaceholderAgentHealthy`；超时触发仍作为后续实现 gate |
| #431 Static Pod resize 设计 | proposal 用 VPA/in-place 类比表达资源变化 | Static Pod 由 kubelet读取本地 manifest，变更会 delete-and-recreate | inline review 后作者明确重建路径，SP-01 解决 |
| #431 RuntimeClass 路由设计 | proposal 把 handler 描述成切换独立 CRI socket | RuntimeClass 只把 handler 传给既有 CRI implementation | 作者改为 containerd named runtime + runtime v2 shim，SP-02 解决 |
| 寻找新的社区开发任务 | issue 列表很多，但没有适合立即认领的 A 级无主项 | 多数已有负责人、等待作者、缺环境或与现有工作重复 | 记录 17 项去重决策，转向 review、测试与已有 PR 跟进 |

### 开源协作记录

| 对象 | 本人角色 | 周内动作 | Week 5 截止状态 |
| --- | --- | --- | --- |
| AgentCube #420 | author / tester | 跟进 native builder 优化合并 | 7/7 已合并 |
| AgentCube #422 | author / validator | 配置并验证 Docker base image updater | 7/7 已合并 |
| AgentCube #423 | author / tester | 固定 11 个 workflow runner，保留明确旧版本 | 7/9 已合并 |
| Karmada #7728 | author / tester | 固定 18 个 workflow 到 Ubuntu 24.04 | 7/9 已合并 |
| AgentCube #429 | designer / author / tester | 提交 scheduled Go baseline upgrade workflow | 进行中，等待 review |
| AgentCube #431 | reviewer / researcher | 发布 3 条 contract-level inline review 并核对作者修正 | 3 条周内问题已解决；proposal 仍进行中 |
| agent-sandbox v0.5 adapter | author / tester | 本地实现并完成新集群关键路径验证 | 进行中，未提交 upstream |

### 本周形成的可复用工程判断

1. **自动化必须尊重依赖类型。** Runtime base image、Go module 和 Go language baseline 的 owner、变更面和验证要求不同。
2. **CI 固定版本与升级版本是两项工作。** 消除 `latest` 的漂移风险可以最小化处理；升级已有明确旧版本必须另做兼容性验证。
3. **新版适配要按证据层级陈述。** Compile、fresh install、object-flow、migration、security path 缺一层，就不能声称完整支持。
4. **Proposal review 要核对下层真实 contract。** 架构图中的箭头必须能映射到 kubelet、CRI、containerd 和 shim 的实际接口。
5. **Review 完成度属于具体 thread，不自动扩展到整个 PR。** 三条问题 resolved 只说明作者处理了这些点，不代表 proposal 整体 LGTM。
6. **没有合适任务也是有效结论。** 高质量 triage 的目标是减少冲突和无效工作，不是强行增加认领数量。

### 证据索引

| 结论或工作流 | 本地证据 |
| --- | --- |
| 多架构 native builder benchmark 与 #420 | [Day39：Buildx 性能优化机会](day39-karmada-image-build-and-agentcube-buildx-performance-optimization.md) |
| 社区趋势、已有 owner 与任务方向 | [Day40：AgentCube 最新社区动态](day40-agentcube-latest-community-pr-issue-trends.md) |
| agent-sandbox v0.5 API、adapter 与 runtime 验证 | [Day41：v0.5 正式发布后的适配分析](day41-agent-sandbox-v050-release-and-agentcube-adaptation.md) |
| v0.5 runtime 原始证据 | [Day41 benchmark 目录](benchmarks/day41-agent-sandbox-v05-runtime/) |
| Dependabot Docker updater 范围与 fork-generated PR | [Day42：Dependabot 自动更新 base image](day42-dependabot-alpine-base-image-updates.md) |
| Go baseline、runner pinning、#423 与 #429 | [Day43：Go Toolchain 升级边界与 runner 固定](day43-go-toolchain-and-github-runner-pinning.md) |
| #431 三条 inline review、回复和设计校准 | [Day44：SandboxPool Proposal Review](day44-sandbox-pool-management-proposal-review.md) |
| Review comment 状态与 exact payload | [Day44：#431 评论草稿与状态跟踪](day44-sandboxpool-pr431-comment-drafts.md) |
| 17 个 issue 去重与任务筛选 | [Day45：最新社区 Issue 任务筛选](day45-latest-community-issue-task-screening.md) |
| 公司周报结构化事实基线 | `/home/intern-week-mail/reports/week5/week5-weekly-report-evidence-matrix.md`（本机私有周报仓库，已按 GitHub 回读校准） |

### 一句话总结

Week 5 把性能、依赖与 CI 维护沉淀成可重复工作流，同时用 Kubernetes/CRI/containerd 的真实 contract 提升 proposal review 深度，并对尚未完成的 v0.5 migration 与 direct WorkloadManager mTLS harness 保持了清楚边界。
