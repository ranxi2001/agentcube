# Day 44：SandboxPool 管理正式 Proposal #431 Review

日期：2026-07-09

## 今日目标

今天开始看 upstream PR [#431](https://github.com/volcano-sh/agentcube/pull/431)：`[Proposal] add sandbox-pool management proposal`。这是基于 [#430](https://github.com/volcano-sh/agentcube/issues/430) 的正式 proposal，主题是 AgentCube 下一代架构里的 **slow resource track**：用 Kubernetes CRD 管理节点级 sandbox resource pool，把每个 session 的高频生命周期从 Kubernetes hot path 中拆出去。

> 注释：这里的 “formal proposal” 不是普通 issue comment，而是新增 `docs/proposals/sandbox-pool-management/README.md` 的文档 PR。它进入了 AgentCube 的 proposal 目录体系，因此后续讨论会更像设计评审，而不是临时 brainstorm。

本文记录四件事：

1. #431 当前社区和 CI 状态。
2. #430 到 #431 的设计脉络。
3. #431 proposal 的架构和 API 设计拆解。
4. 我们可以关注的 review 点，以及是否适合发 upstream comment。

## Proposal Review 应该怎么做

导师说“有疑问和意见可以提 PR comment”，这里的前提不是“看到一个点就评论”，而是先把 proposal 当成一份设计稿彻底读懂。Proposal review 更像审一份架构本子：

1. 先复述作者到底想解决什么问题。
2. 再复述作者明确不解决什么问题。
3. 然后画出对象、组件、状态机、读写边界和失败路径。
4. 最后才判断文本有没有漏掉假设、边界、验证方式或会误导实现者的地方。

> 注释：proposal 还没有代码，很多“问题”不是 bug，而是“文本没有把未来实现必须知道的约束写清楚”。所以 review 的贡献往往不是直接要求改逻辑，而是建议把 scope、source of truth、状态转换、feature gate、failure mode、test plan、rollout plan 写得更清楚。

### 读 proposal 的四层顺序

| 层级 | 要回答的问题 | #431 中对应内容 |
| --- | --- | --- |
| 问题层 | 为什么现在要改架构？旧架构瓶颈是什么？ | #430 的 K8s per-session hot path、API server 压力、idle waste、capacity planning 混乱 |
| 边界层 | 这个 proposal 做什么、不做什么？ | #431 只做 slow resource track，不做 node-ctl sandbox lifecycle / overcommit / snapshot |
| 机制层 | API、controller、agent、状态机如何协作？ | `SandboxPoolClass` / `SandboxPool`、SandboxPool Controller、placeholder-agent、Static Pod、SSA status ownership |
| 验证层 | 哪些高风险声明需要实验或测试证明？ | Static Pod resource locking、skip-cgroup、InPlace Resize、stale heartbeat、deletion/finalizer |

如果这四层里任意一层说不清，就不应该急着发 upstream comment。可以先写中文内部笔记，直到能用自己的话完整解释提案。

### 评论不是找茬，而是补齐可实现性

Proposal comment 适合聚焦三类内容：

1. **文本范围问题**：例如 `Fixes #430` 是否会过早关闭一个 broad discussion；front matter 是否缺 `tracking-issue`。
2. **实现者会误解的问题**：例如 CRD 里有 `nodeCtlEndpoint`，但 placeholder-agent 又说只读 systemd 参数，这就是 source of truth 不清。
3. **验证计划不足的问题**：例如 Static Pod + skip-cgroup + InPlace Resize 是 proposal 最有风险的组合，文本需要说明用什么 spike / e2e 证明。

不适合评论的内容：

- 个人偏好的命名风格，除非会影响 API 长期一致性。
- 已经被作者或 maintainer 正在处理的 AI review 小问题。
- 没有证据支撑的“我觉得可能不行”。
- 一口气把所有疑问塞进很长的 omnibus comment。

> 分析：真正有质量的 proposal review 应该能让作者说“这个点补进 proposal 后，后续实现和 review 都会更清楚”。如果只是证明自己发现了很多问题，反而会增加社区沟通噪音。

### 这次 #431 的评论策略

短期更合理的策略不是马上发评论，而是先把疑问分级：

| 等级 | 例子 | 是否适合现在评论 |
| --- | --- | --- |
| 流程/文本小修 | DCO、`tracking-issue`、`Fixes #430` | 可以评论，但 DCO/tracking issue 可能作者会自己修；`Fixes #430` 更值得提醒 |
| 设计澄清 | `nodeCtlEndpoint` source of truth、API group 是否用 `sandbox-pool.io` | 适合以 question 形式评论 |
| 高风险机制 | Static Pod resource locking、skip-cgroup、Static Pod resize、stale heartbeat | 最好先配合官方文档或最小实验，再评论 |
| 实现建议 | 具体 controller 代码、node-ctl 细节 | 现在不适合，因为 proposal 明确把 node-ctl 内部作为 non-goal |

因此，如果后面要写 #431 comment，第一版应该短，只选 1-2 个最关键点，例如：

- “Since #430 is the broader architecture discussion and this PR covers only the slow resource track, should this be `Refs #430` instead of `Fixes #430`?”
- “Could the proposal add a validation spike for Static Pod resource accounting and in-place resize behavior, since these mechanisms are central to the resource-locking guarantee?”

这类评论不是否定 proposal，而是帮助 proposal 文本变得更可实现、可验证、可维护。

### Skill 沉淀

这次经验应该沉淀到本地 skill，而不是只留在日报里。后续看 proposal 时应复用固定流程：

1. 抓 thread context。
2. 读 proposal template。
3. 写 understand-first 中文 summary。
4. 用 review matrix 分类：scope / API / state machine / ownership / failure mode / security / compatibility / test plan。
5. 只把高价值、可行动、英文清楚的问题变成 upstream comment draft。

已将这个流程沉淀到 `.agents/skills/agentcube-issue-discussion/references/proposal-review.md`，并在 issue-discussion skill 中加入入口。后续如果 proposal review 变成高频独立任务，再考虑拆出单独 `agentcube-proposal-review` skill；现在先作为 issue-discussion 的专项 reference 更合适，因为它仍依赖同一套 GitHub thread 抓取、角色权重和 upstream comment guardrails。

## 早期 Proposal PR 是怎么 battle 的

为了理解 proposal review 到底该看什么，我回看了一批早期 AgentCube proposal / design PR 和关联 issue。这里的 “battle” 不是吵架，而是维护者通过问题把 proposal 从“大方向描述”压到“可实现、可维护、可验证的设计契约”。

> 注释：早期 proposal 大多还放在 `docs/design/`，不是现在的 `docs/proposals/<name>/README.md` 目录结构。#415 合入后，AgentCube 才正式有了 proposal index 和 template。因此看历史样本时，不能只按当前模板要求倒推，而要看 reviewer 关注了哪些稳定问题。

### 样本概览

| PR / issue | 结果 | battle 主线 | 对 proposal review 的启发 |
| --- | --- | --- | --- |
| [#28 AgentRun CLI proposal](https://github.com/volcano-sh/agentcube/pull/28) | merged | CLI 命令语义、provider 行为、proxy / status / publish 等用户可见 contract | 用户入口类 proposal 要问清命令到底等待什么、失败怎么报、哪些字段只对某 provider 生效 |
| [#29 PicoD Design](https://github.com/volcano-sh/agentcube/pull/29) | merged | PicoD 是否是 sandbox manager、HTTP/gRPC/API 细节、auth token 传递、workspace 限制 | 名词边界和协议细节不能模糊；proposal 不能把组件职责写成另一个系统 |
| [#37 AgentCube Task design](https://github.com/volcano-sh/agentcube/pull/37) | closed | 范围过大，几乎没有真人 maintainer 深入 review | 太大的 outsider proposal 即使内容多，也可能因为 scope 不可评审而停掉 |
| [#38 sandbox warm pool proposal](https://github.com/volcano-sh/agentcube/pull/38) | closed | WarmPool API 是否该完整暴露给用户、namespace 是否该出现在 path、admin 流程和 apiserver 内部流程混在一起 | 资源池 proposal 最重要的是区分用户 API、管理员 API 和内部实现细节 |
| [#44 runtime API design](https://github.com/volcano-sh/agentcube/pull/44) | merged | 为什么新设计 API，而不是复用已有 SandboxTemplate；设计文档和 Go API type 一致性 | 正式 API proposal 必须回答 reuse-vs-new-resource，并保持文档 / 代码 contract 一致 |
| [#80 overall AgentCube proposal](https://github.com/volcano-sh/agentcube/pull/80) | merged | AgentRuntime / CodeInterpreter / WorkloadManager / Router 的边界、用户入口、session 概念 | 系统级 proposal 的核心是产品模型和组件边界，不只是架构图漂亮 |
| [#114 PicoD plain auth proposal](https://github.com/volcano-sh/agentcube/pull/114) | merged | JWT issuer 概念、Secret / ConfigMap source of truth、token reuse/rotation、部分写入失败恢复 | 安全 proposal 要审 threat model、source of truth、atomicity、rotation 和 recovery |
| [#164 PR template proposal issue](https://github.com/volcano-sh/agentcube/issues/164) | closed | 维护者要求参考 Volcano 生态已有模板，而不是随意新造流程 | 流程类 proposal 也要先对齐项目生态惯例 |
| [#241 AuthN/AuthZ design proposal](https://github.com/volcano-sh/agentcube/pull/241) | merged | 用户身份如何从 Router 传到 runtime、mTLS/SPIRE 是否影响低延迟、tenant isolation、证书轮换和安装边界 | 安全和性能 trade-off 要落到具体路径、延迟预算、配置方式和实现切片 |

### 真人 review 和 AI review 的差别

这些样本里，AI reviewer 的价值主要是帮助扫一致性和局部错误，例如字段名不一致、示例代码错误、endpoint 表述与当前实现不一致、文档链接或模板问题。它很有用，但通常不是设计方向的来源。

真人 maintainer 的评论更像架构压力测试，常见问题是：

1. 这个能力应该暴露给用户，还是应该藏在 AgentCube apiserver / controller 后面？
2. 为什么要新增 API / CRD，而不是复用已有资源？
3. 这个字段谁写、谁读、是否有两个 source of truth？
4. 如果一半成功一半失败，系统怎么恢复？
5. 安全方案会不会破坏低延迟或多租户隔离？
6. 图里每一步是动作还是名词？用户流程和内部流程是否混在一起？
7. proposal 是否写了太多安装教程或实现细节，反而没有讲清核心设计？

> 分析：这说明 proposal review 不是“挑文档毛病”，而是在代码出现前提前保护未来实现边界。一个好问题应该能让 proposal 多出一段清楚的 contract，而不是只让作者改一个词。

### 几个典型 battle 模式

**1. API 暴露边界**

#38 的 warm pool proposal 很接近 #431。维护者关注的不是 warm pool 是否有价值，而是完整 WarmPool API 是否应该直接暴露给用户。如果用户可以绕过 AgentCube apiserver 创建或操纵 WarmPool，那 AgentCube 再包装一层 API 的意义就会变弱。

对 #431 的启发：`SandboxPoolClass` / `SandboxPool` 是管理员资源、AgentCube 内部资源，还是未来用户可见资源？`nodeCtlEndpoint`、namespace、host socket 这类细节是否应该进入 CRD spec，需要用“谁应该 declaratively control 它”来判断。

**2. Reuse vs new API**

#44 的 runtime API proposal 被追问为什么要设计新 API，而不是直接使用已有 `SandboxTemplate`。这类问题很关键，因为 API 一旦合入，后续会带来兼容性、client-go、CRD 版本和迁移成本。

对 #431 的启发：如果新增 `sandbox-pool.io` API group 和 `SandboxPoolClass`，proposal 应该解释它和现有 AgentCube runtime API、agent-sandbox `SandboxWarmPool` / `SandboxTemplate` 的关系。不是说不能新增，而是要说明为什么不能复用、为什么应该成为长期 API。

**3. 用户流程 vs 内部实现流程**

#80 的 overall proposal 被反复追问 WorkloadManager 是否应该暴露给用户、CodeInterpreter 和 AgentRuntime 为什么并存、session 到底是应用会话还是基础设施会话。#29 也类似，PicoD 的定位不能写成 sandbox management。

对 #431 的启发：proposal 应该把两条路径拆开：管理员创建 / 更新 pool 的慢路径，以及 AgentCube session 从 pool 中快速分配 runtime 的快路径。否则 reviewer 很难判断 Static Pod、placeholder-agent、node-ctl 分别在哪条路径上工作。

**4. Source of truth 和 atomicity**

#114 的 PicoD auth proposal 里，Secret / ConfigMap 分离方案被追问原子性：如果 Secret 创建成功但 ConfigMap 创建失败，系统会处于什么状态？最后设计收敛到更清楚的 Secret source of truth。

对 #431 的启发：`SandboxPoolClass.spec.nodeCtlEndpoint`、`SandboxPool.spec.nodeCtl.endpoint`、placeholder-agent 启动参数、systemd 配置之间不能同时宣称自己是 source of truth。若 endpoint 只是状态展示或文档 hint，就应写清楚；若未来可配置，就要写 reconcile 和失败恢复。

**5. 性能 / 安全 trade-off**

#241 的 auth proposal 最后不是停在“mTLS 更安全”这个抽象层，而是讨论 Router -> PicoD / runtime 路径是否需要用户身份、TLS handshake 是否破坏 100ms 级 bootstrap、JWT mode 和 mTLS mode 是否都要保留。

对 #431 的启发：Static Pod + skip-cgroup + RuntimeClass CRI handler 不能只说“可以锁资源”。它的 trade-off 是 scheduler accounting、eviction、metrics、QoS、host 权限和 resize 行为都要被验证。proposal 的 Test Plan 应该写 targeted spike，而不是只写 controller unit test。

**6. Closed proposal 的失败模式**

#37 和 #38 都 closed。它们的共同点不是“没有想法”，而是范围或边界让 review 成本太高：#37 设计面太大，像一次性定义新系统；#38 则把 API 暴露、namespace path、apiserver 内部流程和用户流程混在一起。

对 #431 的启发：#431 要避免变成“资源池、node-ctl、overcommit、snapshot、session runtime 全部一次讲完”。它现在明确 non-goal 是优点；review 可以帮助它继续保持 slow resource track 的边界。

### 可以迁移到 #431 的 review 视角

结合这些历史样本，#431 的高价值 comment 不应是“我觉得 Static Pod 风险大”这种泛泛意见，而应该压成可回答的问题：

1. **Scope**：#431 只覆盖 slow resource track，是否应该 `Refs #430` 而不是 `Fixes #430`？
2. **API boundary**：`SandboxPoolClass` / `SandboxPool` 面向管理员还是内部控制面？哪些字段是 declarative spec，哪些只是 status / hint？
3. **Reuse rationale**：为什么使用新的 `sandbox-pool.io` API group，而不是沿用 AgentCube 域名或复用 agent-sandbox warm pool 资源？
4. **Source of truth**：node-ctl endpoint 到底由 CRD、systemd flag，还是 placeholder-agent 配置决定？
5. **Validation**：Static Pod resource accounting、skip-cgroup、mirror Pod rebuild、manifest resize 是否有独立 spike？
6. **Failure mode**：placeholder-agent 挂死但 Node 仍存在时，Ready phase 如何避免 stale？

> 分析：这就是 mentor 说的“有疑问和意见可以提 PR comment”的前提。不是把自己所有疑问发出去，而是先知道历史上 maintainer 真正关心什么，再选择能改善 proposal 文本和未来实现路径的问题。

## 社区状态快照

时间点：2026-07-09 本地查询。

| 项目 | 当前状态 |
| --- | --- |
| PR | [#431](https://github.com/volcano-sh/agentcube/pull/431) |
| 标题 | `[Proposal] add sandbox-pool management proposal` |
| 作者 | `@lichuqiang` |
| 类型 | Proposal PR / `/kind feature` |
| 状态 | Open，非 draft |
| 文件范围 | 新增 `docs/proposals/sandbox-pool-management/README.md` |
| Diff | 1 file, +642 lines |
| labels | `kind/feature`, `size/XL` |
| assignee | 无 |
| PR 认领 @ | 无 |
| 关联 issue | [#430](https://github.com/volcano-sh/agentcube/issues/430) |
| 最近提交 | `9787221 fix AI review comments` |
| DCO | `ACTION_REQUIRED` |
| tide | Pending |
| 普通 CI | build / e2e / codegen / codespell / lint / Python / coverage 均 success |

两个 commit 都没有 `Signed-off-by` trailer：

```text
9787221 fix AI review comments
7d97d7e add sandbox-pool management proposal
```

> 分析：DCO 是当前合并门禁中的明确阻塞点。它和 proposal 技术内容无关，通常需要作者用 signed-off commit amend/rebase 修复。我们不应该把 DCO 红色状态解读成 proposal 设计失败。

## 参与者与评论权重

| 角色 | 账号 | 权重判断 |
| --- | --- | --- |
| 讨论 issue 作者 / 维护者 | `@RainbowMango` | #430 作者，Collaborator；目前 #431 中被 `/cc`，但尚未技术回复 |
| Proposal PR 作者 | `@lichuqiang` | 负责当前 proposal 内容；不是 maintainer consensus |
| 流程 bot | `@volcano-sh-bot` | 提示 approval / OWNERS / first PR；不是技术判断 |
| CI / coverage bot | `@codecov-commenter` | 说明 coverage 和上传状态；不是技术判断 |
| AI reviewer | `@gemini-code-assist[bot]`, `@copilot-pull-request-reviewer[bot]` | 可作为检查清单；不能当作维护者结论 |

目前没有真人维护者对 #431 的技术意见。因此今天的结论只能写成“我们的 review 观察”，不能写成“社区已经达成共识”。

## #430 到 #431 的脉络

#430 由 `@RainbowMango` 发起，核心问题是 AgentCube 当前把每个 agent / code-interpreter session 都落到 Kubernetes CR / Pod 上，会遇到几个瓶颈：

1. session 创建慢：CR 创建、reconcile、Pod 创建、调度、kubelet sync、image pull、microVM boot 都在用户可见路径上。
2. API server / etcd 不适合承载大量短生命周期对象。
3. idle sandbox 浪费资源，Kubernetes 没有原生 Pod suspend/resume。
4. 容量规划和 session 生命周期混在一起，管理员不能先规划 agent capacity，再由 AgentCube 快速分配 session。

#430 的方向可以压缩成一句话：

> Kubernetes owns the pool; AgentCube owns the sessions.

也就是说，Kubernetes 负责管理长期存在、低频变化的资源池；AgentCube 控制面负责高频 session 分配，不再为每个 session 触发 Kubernetes 对象创建。

#431 是对这个方向里 **Kubernetes owns the pool** 部分的正式 proposal。它明确说只做 slow resource track，不设计 node-ctl 的 sandbox create/suspend/resume/delete、overcommit coordination、snapshot 这些 fast path 内部实现。

> 注释：这和 Day35/Day36 的内部结论对齐：Kubernetes 适合管理慢状态、资源边界和全局可观测性；真正高频的 sandbox 生命周期应该下沉到 node-local runtime / node-ctl / sandbox-ctl。

## Proposal 设计拆解

### 1. 总体架构

#431 把系统分成两层：

| 层 | 组件 | 职责 |
| --- | --- | --- |
| Global Policy Layer | `SandboxPool Controller` | Class 到 Pool 的映射、节点选择、policy snapshot sync、Phase 聚合、finalizer、node check |
| Node Execution Layer | `placeholder-agent` | host-level systemd service，负责 CRI handler、Static Pod manifest 管理、node-ctl proxy、CRD watch、condition 上报 |
| Node Execution Layer | Static Pod / mirror Pod | 作为 Kubernetes 调度资源占位，锁定 `resources.requests/limits` |
| Node Execution Layer | `node-ctl` | sandbox create/suspend/resume/delete、资源超配、snapshot 等 fast path；proposal 中当作黑盒 |

核心设计选择：

- 用 Static Pod 锁定调度资源，mirror Pod 被误删后由 kubelet 重建。
- placeholder-agent 是 host-level systemd 服务，不跑在 placeholder Pod 内。
- RuntimeClass handler `placeholder` 把 CRI 调用路由到 placeholder-agent 的 socket。
- 通过 SSA FieldOwner 协调 controller 和 placeholder-agent 的 status 写入。
- 用 InPlace Pod Resize 做资源在线调整。

> 分析：这个结构比 Day36 的“Template Controller + Pool Controller”更节点本地化。Day36 里 Pool Controller 仍像 DaemonSet/controller；#431 则把节点侧职责集中到 host-level placeholder-agent，并让它直接写 Static Pod manifest、实现 CRI handler、代理 node-ctl。

### 2. CRD 模型

Proposal 定义两个 cluster-scoped CRD：

| CRD | 作用 |
| --- | --- |
| `SandboxPoolClass` | 全局资源池策略，包含 node selector、resource policy、placeholder Pod template、node-ctl endpoint 等 |
| `SandboxPool` | 节点级资源池实例，包含 `classRef`、`nodeName`、policy snapshot、override 和节点状态 |

`SandboxPoolClass` 的关键字段：

- `spec.selector`
- `spec.nodeSelector`
- `spec.resourcePolicy.cpu`
- `spec.resourcePolicy.memory`
- `spec.placeholderPodTemplate`
- `spec.nodeCtlEndpoint`

`SandboxPool` 的关键字段：

- `spec.classRef`
- `spec.nodeName`
- `spec.nodeCtl`
- `spec.resourcePolicy`
- `spec.override`
- `status.phase`
- `status.placeholderPod`
- `status.placeholderAgent`
- `status.resize`
- `status.nodeCtl`
- `status.poolInfo`
- `status.conditions`

当前 API group 写成 `sandbox-pool.io/v1alpha1`。

> 分析：现有 AgentCube runtime API group 是 `runtime.agentcube.volcano.sh/v1alpha1`。新 proposal 使用 `sandbox-pool.io`，可能来自早期独立设计稿。正式进入 AgentCube upstream 前，API group 是否应该对齐 AgentCube 域名，是一个值得 reviewer 问清楚的问题。

### 3. Status 写入模型

Proposal 用 SSA FieldOwner 分离 status 写入：

| FieldOwner | 组件 | 管理字段 |
| --- | --- | --- |
| `placeholder-agent` | node-local agent | `placeholderPod`, `placeholderAgent`, `override`, `resize`, `nodeCtl`, `poolInfo`, non-`NodeNotFound` conditions, `lastAppliedGeneration` |
| `sandboxpool-controller` | global controller | `phase`, `NodeNotFound` condition |

好处是 controller 可以在节点被删除或 placeholder-agent 不可达时仍然更新 `phase`，不会完全依赖节点本地组件。

风险是 stale condition：如果 placeholder-agent 挂了但 Node 还存在，controller 只靠 `NodeNotFound` 并不能判断 status 是否过期。Proposal 的 risk table 说“Node NotReady 间接覆盖”，但没有定义 controller 如何把 Node NotReady、heartbeat stale 或 `LastHeartbeat` 超时转换成 `Unready`。

> 分析：这可能是 #431 最值得深入 review 的正确性问题。节点不存在时好处理；节点存在但 placeholder-agent / CRI socket / node-ctl proxy 卡死时，旧的 Ready condition 可能保留在 CRD status 里。如果 controller 不主动检查 `lastHeartbeat` 或 Node condition，Phase 可能继续显示 Ready。

### 4. Phase 状态机

#431 定义四个 phase：

| Phase | 语义 |
| --- | --- |
| `Pending` | placeholder Pod 从未 ready |
| `Ready` | placeholder Pod ready，node-ctl healthy，resource synced 或 resize deferred |
| `Degraded` | node-ctl 短时不可达，或 policy 未同步 |
| `Unready` | node-ctl 长时间不可达、placeholder Pod 异常、NodeNotFound |

AI reviewer 曾指出 `NodeNotFound=False -> Ready` 不安全，因为 Node 恢复不等于 placeholder Pod 和 node-ctl 健康。当前 head 已修成：`NodeNotFound=False` 后重新评估所有 conditions，再决定 Ready/Pending/Degraded。

proposal 自己也记录了一个风险：`hasEverBeenReady` 只是近似判断，可能误判 Pending / Unready，未来可能加 `status.hasBeenReady`。

> 分析：既然 phase 语义已经依赖 “was Ready” 和 “never Ready”，`status.hasBeenReady` 不一定应该等未来。v1alpha1 若直接需要这个判断，最好从第一版就把字段纳入 status，避免实现时靠内存或 condition history 猜。

### 5. Static Pod / RuntimeClass / skip-cgroup 模型

#431 最关键也最有风险的点是：

- Static Pod 用来锁定 Kubernetes 调度资源。
- placeholder Pod “no actual process, skip cgroup”。
- placeholder-agent 作为 host-level systemd 进程提前启动。
- kubelet 根据 RuntimeClass handler 把 CRI 调用路由到 `/run/sandbox-pool/cri.sock`。
- placeholder-agent 通过 CRI handler 响应 kubelet，并把 carved-out resources 交给 node-ctl 使用。

Kubernetes 官方文档里，Static Pod 是由 kubelet 在特定节点直接管理的 Pod；kubelet 会在 API server 中创建 mirror Pod，让它可见，但不能从 API server 控制该 Pod。文档也说明 Static Pod 不能引用 ServiceAccount / Secret / ConfigMap，且如果是在集群里给每个节点跑节点级 workload，通常应优先考虑 DaemonSet。

> 注释：这不表示 #431 的 Static Pod 方案一定错。它利用 Static Pod 的地方恰恰是“mirror Pod 被删后 kubelet 会重建”这个特性。但它偏离常规节点 agent 模型，所以需要额外证明调度资源、kubelet admission、eviction、metrics、QoS 和 resize 行为都符合预期。

需要验证的具体问题：

1. Static Pod 的 mirror Pod 是否稳定参与 scheduler resource accounting，能否真实阻止普通 Pod 抢占这部分 request。
2. 如果 CRI shim 故意 `skip-cgroup`，kubelet / cadvisor / eviction manager 是否还能正确看待这个 Pod 的 request、limit、usage、QoS。
3. mirror Pod 被删后“<5s 重建”在不同 kubelet config、API server 延迟、压力场景下是否成立。
4. Static Pod manifest 更新资源后，kubelet 是原地 resize 还是重建 Pod。
5. host-level placeholder-agent 如何安全获取 kubeconfig / token，因为 Static Pod 本身不能挂 ServiceAccount。

### 6. InPlace Resize 版本和适用范围

#431 的兼容性表写：

```text
VPA InPlaceResize: 1.27 Alpha / 1.31 GA
```

需要复核。Kubernetes 官方博客显示 In-Place Pod Resize 在 v1.33 进入 Beta 并默认启用，在 v1.35 进入 Stable。官方 v1.35 博客也提到 VPA 的 `InPlaceOrRecreate` update mode 当时是 beta，`InPlace` mode 仍在推进。

> 分析：#431 把 “Kubernetes in-place Pod resize feature” 和 “VPA 集成能力” 有点混在一起。Proposal 里应明确到底依赖原生 Pod resize subresource、VPA recommender/updater，还是 placeholder-agent 自己改 Static Pod manifest。三者的版本、权限、测试方式不一样。

尤其要注意：Kubernetes in-place resize 通常通过更新 Pod spec / `resize` subresource 触发；Static Pod 的 mirror Pod 又不能由 API server 控制。#431 需要用 e2e spike 证明“Static Pod + local manifest update + CRI UpdateContainerResources”真的能在不重建 Pod 的情况下生效，否则目标里的 “without rebuilding Pods” 可能不成立。

### 7. Process / metadata 问题

当前 #431 还有几个低风险但正式 proposal 应补齐的问题：

1. DCO 失败：两个 commit 缺 `Signed-off-by`。
2. proposal front matter 缺 `tracking-issue: "#430"`。`docs/proposals/proposal-template.md` 已把 tracking issue 作为 optional 字段。
3. PR body 写 `Fixes #430`，但 #430 是更大的 architecture discussion；#431 只覆盖 slow track，merge 后自动关闭 #430 可能过早。更稳妥的写法是 `Refs #430` 或 `Part of #430`。
4. front matter 里 `reviewers` / `approvers` 仍是 `TBD`，作为 draft proposal 可以接受，但如果准备进入正式 review，至少应说明期待哪些 reviewer 参与。

> 分析：这些不是技术设计硬伤，但它们会影响 proposal 的检索、关闭语义和社区流程。尤其 `Fixes #430` 容易把 broad discussion 关闭掉，和 #431 自己“只做 slow resource track”的 scope 不一致。

## 和 Day35 / Day36 内部方案的关系

| 主题 | Day35/Day36 内部判断 | #431 当前 proposal | 判断 |
| --- | --- | --- | --- |
| 快慢资源分离 | K8s 管慢资源，node-local 管高频生命周期 | 明确 slow resources / fast resources 双轨 | 对齐 |
| CRD 模型 | `SandboxPoolTemplate` + `SandboxPool` | `SandboxPoolClass` + `SandboxPool` | 名称不同，语义接近 |
| controller 分层 | Template Controller + Pool Controller | SandboxPool Controller + host-level placeholder-agent | #431 更强调节点本地 agent |
| 占位资源 | Day36 建议先用普通 Guaranteed Pod，skip-cgroup 另做 spike | 直接选择 Static Pod + skip-cgroup + CRI handler | #431 激进，需要验证 |
| node-ctl 边界 | 先定义接口，node-ctl 可 fake | node-ctl 黑盒，placeholder-agent 唯一 proxy | 对齐，但接口还不够细 |
| status 聚合 | 需要定义 source of truth、heartbeat、stale state | SSA FieldOwner + controller phase aggregation | 方向好，但 stale heartbeat 仍需补 |
| upstream 形态 | 建议先拆 design proposal / CRD skeleton / placeholder spike | 先提交完整 design proposal | 合理，但 review 应要求测试切片 |

> 注释：#431 并不是把 Day36 原样搬到 upstream。它做了两个明显选择：一是把 `SandboxPoolTemplate` 改成 `SandboxPoolClass`；二是直接采用 Static Pod + CRI shim 模型。这两个选择都可以讨论，但后者的验证成本更高。

## 当前可 review 的问题清单

下面这些是我认为如果要参与 #431 讨论，最值得压缩成英文 comment 的点。先不发 upstream，等用户确认。

### A. Scope / metadata

- 建议把 PR body 的 `Fixes #430` 改成 `Refs #430`，因为 #430 是 broader architecture discussion，而 #431 只覆盖 slow track。
- 建议 front matter 增加 `tracking-issue: "#430"`。
- 修复 DCO signoff。

### B. Static Pod 资源锁定需要独立验证

问题不是“Static Pod 会不会重建”，而是：

- mirror Pod 的 requests 是否稳定进入 scheduler accounting；
- `skip-cgroup` 后 kubelet / metrics / eviction / QoS 是否仍然一致；
- Static Pod manifest 更新是否真的支持 in-place resize，而不是重建；
- host-level systemd agent 的 kube credential / CRI socket 权限如何管控。

建议 proposal 的 Test Plan 增加一个独立 spike：

1. 创建 Static Pod placeholder，设置明确 CPU/memory requests。
2. 尝试调度普通 Pod，验证 scheduler 是否把 placeholder requests 纳入 Node allocatable 计算。
3. 删除 mirror Pod，测量重建时间。
4. 修改 manifest resources，验证是 in-place resize 还是 Pod rebuild。
5. 检查 kubelet/cadvisor/metrics-server/eviction 对 skip-cgroup Pod 的行为。

### C. Stale status / heartbeat

当前 controller 只拥有 `NodeNotFound` condition，placeholder-agent 拥有 `NodeCtlHealthy` 等 condition。如果 placeholder-agent 本身挂死，且 Node 还存在，旧 condition 可能长期保持 Ready。

建议增加：

- controller-owned `PlaceholderAgentHeartbeatStale` 或 `NodeAgentReachable` condition；
- phase computation 使用 `status.placeholderAgent.lastHeartbeat` / `status.nodeCtl.lastHeartbeat` 的过期时间；
- fault injection test 覆盖 “Node exists, placeholder-agent stopped, previous status Ready”。

### D. InPlace Resize 依赖边界

需要把以下三件事拆清：

| 概念 | 问题 |
| --- | --- |
| Kubernetes In-Place Pod Resize | 官方版本状态要更新；v1.33 beta、v1.35 stable |
| VPA `InPlaceOrRecreate` / `InPlace` | 是否真的引入 VPA 组件，还是只借用概念 |
| Static Pod manifest resource update | 是否能触发原地 resize，需要实测 |

### E. API group / naming

`sandbox-pool.io` 是否要作为 AgentCube 长期 API group 需要确认。现有 runtime API group 是 `runtime.agentcube.volcano.sh`，正式 CRD proposal 最好解释为什么新 group 不沿用 AgentCube 域名。

### F. node-ctl endpoint source of truth

`SandboxPoolClass.spec.nodeCtlEndpoint` 和 `SandboxPool.spec.nodeCtl.endpoint` 出现在 API 中，但注释说 placeholder-agent 不读这些字段，而是从 `--node-ctl-socket` 启动参数拿地址。

这会造成两个 source of truth：

- 用户看到 CRD 中有 endpoint，以为能 declaratively change；
- 节点实际行为由 systemd 参数决定。

建议要么删除 CRD endpoint 字段，要么明确它只是 documentation/status hint；如果未来要支持 per-pool endpoint，也要定义 placeholder-agent 何时读取和如何 reconcile。

## 建议下一步

短期不建议我们直接发长评论。原因：

1. 现在还没有真人 maintainer review，贸然发大段评论可能打断作者和维护者的第一轮对齐。
2. 一部分问题属于作者已经在修 AI comments 的过程，可能马上会补 DCO / tracking issue。
3. Static Pod / InPlaceResize 的问题最好用 Kubernetes 官方文档和最小实验证据支撑，不要只凭直觉质疑。

更好的顺序：

1. 先持续观察 #431 是否修 DCO、`tracking-issue`、`Fixes #430`。
2. 本地准备一个小的 Static Pod resource accounting / manifest resize 验证计划，必要时再跑。
3. 如果用户确认发 upstream comment，评论应聚焦 2-3 个高价值问题：`Fixes #430` scope、Static Pod + in-place resize validation、stale heartbeat / phase correctness。
4. 不认领实现，不承诺我们会做 node-ctl / placeholder-agent；当前更适合做 design review、test plan 和验证反馈。

## 今日结论

#431 是值得认真跟进的正式 proposal，因为它把 Day35/Day36 的内部架构方向推进到了 upstream 可评审状态。它的总体方向和 #430 一致：Kubernetes 管资源池，AgentCube 管 session。

但它也做了几个需要强验证的设计选择：Static Pod 作为资源锁、placeholder-agent 作为 host-level CRI handler、skip-cgroup、不通过 API server 控制的 Static Pod resize。这些设计不是普通 controller 逻辑，必须靠 targeted spike 和 failure-path test plan 证明。

当前最现实的行动是：先记录并观察，不直接发社区评论；等作者修完 DCO/metadata 后，再根据用户确认准备一条短英文 review comment。

## 参考链接

- AgentCube discussion #430: <https://github.com/volcano-sh/agentcube/issues/430>
- AgentCube proposal PR #431: <https://github.com/volcano-sh/agentcube/pull/431>
- Kubernetes Static Pods 文档: <https://kubernetes.io/docs/concepts/workloads/pods/static-pods/>
- Kubernetes Static Pod 创建文档: <https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/>
- Kubernetes v1.33 In-Place Pod Resize Beta: <https://kubernetes.io/blog/2025/05/16/kubernetes-v1-33-in-place-pod-resize-beta/>
- Kubernetes v1.35 In-Place Pod Resize Stable: <https://kubernetes.io/blog/2025/12/19/kubernetes-v1-35-in-place-pod-resize-ga/>
