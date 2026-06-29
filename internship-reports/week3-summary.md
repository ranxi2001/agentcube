# Week 3 总结：从功能适配转向 Session Runtime Control Plane

日期：2026-06-24 至 2026-06-29

## 核心转变

Week 3 的主线不是继续堆功能，而是把前两周的代码适配、竞品调研、benchmark 和 review 经验，收束成一个更清楚的工程判断：

```text
AgentCube 的下一阶段竞争点
不是单个 sandbox 创建得更快，
而是能不能成为一个清晰、可验证、可扩展的 Session Runtime Control Plane。
```

> 注释：这里的 Session Runtime Control Plane 指的是围绕一个长期会话建立统一控制面：Router 负责请求入口和 resume-before-proxy，WorkloadManager 负责生命周期编排，Store 负责状态和 CAS，RuntimeProvider 负责隔离底层 runtime 差异，benchmark/conformance 负责证明能力边界。

Week 2 的重点是“从写代码转向审代码与工程判断”。Week 3 更进一步：审代码不能只看 diff，还要把 PR 放回到系统边界里看：

- 这个改动属于上层 Session/API/control-plane contract，还是下层 runtime/provider/substrate capability？
- 它改变的是编译关系，还是运行时对象流？
- 它有没有清楚说明状态保存语义、失败路径、并发路径和 cleanup？
- 它是否适合作为 upstream 小 PR，还是应该先做本地设计、review matrix、测试计划和证据沉淀？

## 本周实际完成

| 方向 | 结果 | 复用价值 |
| --- | --- | --- |
| Sleep/Resume 设计 | 完成 Session 状态机、Store CAS、WorkloadManager lifecycle service、GC split、Router resume-before-proxy、RuntimeProvider capability 和测试矩阵的系统拆解 | 把 Sleep/Resume 从“runtime 能不能暂停”升级成跨 Router / Store / WorkloadManager / Provider / SDK 的控制面 contract |
| Sleep/Resume review 复盘 | 以 reviewer 视角复盘本地 Store/CAS 与 WorkloadManager lifecycle 两层实现，形成风险分级、PR 拆分建议和测试设计 | 后续不管谁实现 #386，都可以用同一套 gate 审查 correctness、scope 和 tests |
| 社区问题面整理 | 把 #401/#397/#394/#395/#392/#388/#386 等 issue 和 Day22-Day25 的实测/设计串成上层 contract 与下层 runtime capability 两层问题面 | 避免看到一个 issue 就抢实现，先判断它落在哪个系统层、是否已有 assignee、适合 comment 还是 review/test feedback |
| Agent Infra 能力地图 | 把实习目标拆成 runtime、Kubernetes/control plane、session lifecycle、tool protocol、Router/API、安全、observability/eval、open-source review 八条能力线 | 让后续周报从“做了什么”转成“能力闭环是否推进” |
| Agent Substrate 架构吃透 | 复核 Agent Substrate 源码和 counter demo，画出 Counter Actor 架构图，拆解控制面、状态面、数据面、runtime 面 | 形成 AgentCube 不照搬 Substrate，而是转译其系统边界的判断 |
| AgentCube 架构设计 | 重写 `design.md`，生成 AgentCube 会话运行时架构图和配套拆解文档 | 把 Session lifecycle、Store CAS、Router activation、RuntimeProvider、capacity pool 和 preservation level 画成可讨论的架构资产 |
| 清理 unused agentd | 分析 `cmd/agentd` 实际作用，确认它不是 PicoD、不是 WorkloadManager、也不是当前主线 GC；创建 upstream PR #403 删除 unused component | 训练“先理解组件职责，再决定删不删”的代码考古和 PR scope 纪律 |
| PR #387 warm pool review | 从运行时对象流重新审 #387：`SandboxWarmPool -> Sandbox -> SandboxClaim adoption -> Pod -> Store -> Router`，并用 k3d 跑通 L1 object-flow | 把 review 从 import/API 层推进到真实 Kubernetes 对象和 Store identity 语义 |
| PR #400 metrics review | 本地复测 PicoD Prometheus metrics PR，发现 body-size 413 请求因为 middleware 顺序没有被计入 `http_requests_total` | 证明 observability review 不能只看 `/metrics` 能暴露，还要覆盖失败路径和中间件短路路径 |
| 开源流程修正 | 按 mentor 反馈修正 fork CI 规则：不再为了跑 CI 向个人 fork 开 self-PR，改用 fork-only push validation 模板 | 把开源贡献质量信号和 CI 验证手段分开，避免留下低质量协作历史 |

## 本周最重要的工程判断

### 1. Sleep/Resume 不是一个 runtime 开关

本周最容易误判的地方是把 Sleep/Resume 简化成“把 Sandbox replicas 改成 0/1”或“等 agent-sandbox 支持 suspend”。这只是底层 provider 能力，不是 AgentCube 层面的完整语义。

AgentCube 真正要定义的是：

```text
Session 状态机
  -> Store CAS / placement version
  -> WorkloadManager lifecycle workflow
  -> Router owner/auth 后 resume-before-proxy
  -> RuntimeProvider capability gate
  -> GC Ready / Paused / Failed / Deleted 分流
  -> SDK / API / benchmark 对外承诺
```

> 分析：如果只做底层 pause，不做 Router 和 Store，用户请求仍可能打到旧 endpoint；如果只做 Store 状态，不做 provider capability，控制面会承诺底层无法恢复的能力；如果只做 happy path e2e，不测并发 resume 和 final CAS failure，系统在真实流量下仍可能不一致。

### 2. Store CAS 是 correctness 要求，不是性能优化

在并发 resume、provider 成功但最终 Store 写回失败、旧 endpoint 失效、GC 与用户请求并发等场景里，Store 不能只是保存 endpoint 的缓存。

它需要承担：

- session status 的 source of truth；
- placement version / runtime handle 的原子更新；
- pause expiry / last activity / max duration 的索引；
- CAS conflict 的明确错误语义；
- delete/cleanup 的最终身份依据。

这个判断来自 Day24 的本地 spike 和 Day25 的 review 复盘。后续任何 Sleep/Resume PR 都应该先回答：状态在哪里原子更新，冲突如何返回，provider 成功但 Store 失败怎么补偿。

### 3. Router 是 activation gate，不只是 reverse proxy

Agent Substrate 给 AgentCube 最大的启发之一是：Router 不能只是拿到 endpoint 后盲目转发。对于长期 session，它必须成为 activation gate。

目标顺序应该是：

```text
请求进入 Router
  -> match session
  -> owner/auth check
  -> 如果 Ready，直接 proxy
  -> 如果 Paused，调用 WorkloadManager resume
  -> resume 成功后重新读取 Store
  -> 使用新的 endpoint proxy
```

> 注释：owner/auth 必须在 resume 之前。否则一个无权请求可能触发资源恢复，造成安全和成本问题。resume 成功后也必须重新读 Store，因为旧 endpoint 可能已经无效。

### 4. Review 要看运行时对象流，不只看 API diff

PR #387 的复盘把这一点说得很清楚。只看 diff 会觉得它是在改 agent-sandbox API import、annotation 和测试字段；但真正关键的是运行时对象身份发生了变化：

```text
旧观测假设：SandboxWarmPool -> Pod
v0.4.6 真实链路：SandboxWarmPool -> warm Sandbox -> Pod -> SandboxClaim adoption
```

WorkloadManager 需要同时处理两类身份：

- Store 里的控制身份：`Kind=SandboxClaim`、`Name=<claim name>`，用于 delete/GC。
- Runtime 里的执行身份：adopted Sandbox / Pod / EntryPoints，用于 Router proxy。

> 分析：如果 Store 只保存 adopted Sandbox 或 Pod 名，delete/GC 可能删错对象或无法释放 claim；如果 Router 需要知道 adoption 细节，数据面就会泄漏 provider 内部实现。正确边界是 WorkloadManager/provider adapter 消化 adoption 细节，Store 保留控制身份和 runtime endpoint。

### 5. Observability review 要覆盖短路失败路径

PR #400 的 metrics review 不是发现“没有指标”这么简单。它暴露的是 middleware 顺序问题：

```text
maxBodySizeMiddleware 在 metrics middleware 前面
  -> oversized POST /api/execute 返回 413
  -> 请求提前短路
  -> picod_http_requests_total 没有记录这个 413
```

这说明 Prometheus endpoint 存在不等于 observability 完整。对于 HTTP metrics，至少要看：

- 成功请求是否计数；
- 失败请求是否计数；
- middleware 提前 return 是否计数；
- status code label 是否覆盖 4xx/5xx；
- active gauge 的语义是 handler 生命周期，还是实际执行中的 command；
- `/metrics` endpoint 是否只是暴露本进程指标，还是已经接入完整 Prometheus scrape。

### 6. 竞品调研要转成架构边界，而不是功能清单

Agent Substrate 的价值不在于“它有 gVisor / micro-VM checkpoint，所以 AgentCube 也照抄”。更有价值的是它证明了几个系统边界：

- Kubernetes CRD 适合承载低频声明式资源，不适合承载高频 actor 状态。
- 高频 session/actor 状态需要 Store、CAS 和 workflow。
- Router 需要 activation gate，而不是静态 service discovery。
- runtime 能力需要抽象成 `sandboxClass` / provider capability，不能散落到业务逻辑。
- preservation level 必须明说，不同 runtime 对“恢复”的承诺不同。

AgentCube 的差异化方向因此不是复制 Substrate，而是结合 Kubernetes-native、agent-sandbox、CodeInterpreter、SDK 和开源协作优势，做更容易验证和接入的 open session runtime control plane。

## 本周开源协作收获

### 1. 上游动作必须少而准

本周没有把所有发现都发到 upstream。真正发出去的是用户确认后的 PR #400 review comment，内容基于本地临时测试和可复现 bug。

这比“看到问题就评论”更稳：

- #387 继续本地做数据流 review，不主动扩大 PR。
- #403 等待正式 review，不主动继续 push/comment。
- Sleep/Resume 不抢 FAUST-BENCHOU 可能接手的实现，先做设计、test matrix 和 review material。
- Day32 PRD 保持内部产品设计草稿，不当作 upstream proposal 直接发布。

> 分析：开源协作里，贡献不只是写代码或发评论。能证明某个问题、能把范围拆清楚、能避免重复抢活，也是贡献质量的一部分。

### 2. CI 验证不能污染贡献历史

mentor 反馈后，本周修正了一个流程规则：不要为了跑 CI 向个人 fork 仓库开 self-PR。以后需要提前验证时，优先走 fork-only push validation：

```text
真实 topic branch
  -> 切 ci/<topic> 验证分支
  -> 临时加入 fork-only workflow
  -> push 跑 checks
  -> 最终 upstream PR 分支不带该 workflow commit
```

这条规则已经写入 `AGENTS.md`、`agentcube-pr-management` skill、根 README 和格式标准文档。

### 3. 本地 skills 开始成为工作流资产

本周继续使用并修正了几个本地 workflow：

- `agentcube-issue-discussion`：抓取 PR / issue conversation，避免只看标题和最后一条评论。
- `agentcube-pr-management`：约束 upstream PR 分支、模板、DCO、OWNERS、测试和用户确认。
- `drawio-skill`：复杂架构图导出后检查 edge label overlap，并把图作为架构讨论资产。
- `llm-e2e-test`：保留 math-agent / OpenAI-compatible provider 的验证流程。

> 注释：skill 的价值不是“自动化一切”，而是把容易重复犯错的流程固化下来，例如 PR 评论前必须确认全文、敏感 token 不落报告、fork/intern/upstream 分支不能混用。

## 本周主要证据

| 证据 | 说明 |
| --- | --- |
| [Day24：Sandbox Sleep/Resume 设计笔记](day24-sandbox-sleep-resume-design-note.md) | 状态机、Store CAS、RuntimeProvider、Router、GC、SDK/API、测试计划、本地 spike、Stage 3 拆解 |
| [Day25：Sleep/Resume 代码审查与架构复盘](day25-sleep-resume-code-review-and-architecture-retrospective.md) | reviewer 视角的风险分级、测试矩阵、PR 拆分、Router/GC/provider gate |
| [Day26：社区最新讨论与双层架构问题面](day26-week3-community-latest-and-two-layer-architecture-bug-surface.md) | 把最新 issue 和本地实测/设计映射到上层 contract 与下层 runtime capability |
| [Day27：Agent Infra 职业能力地图](day27-agent-infra-career-roadmap-and-internship-goals.md) | 八条能力线、职业方向、短板和后续 4 周目标 |
| [Day28：Agent Substrate 架构吃透](day28-agent-substrate-architecture-and-agentcube-differentiation.md) | Substrate counter demo、源码复核、四面拆解、AgentCube 差异化 |
| [Agent Substrate Counter Actor 架构图](agent-substrate-counter-architecture.png) | 竞品架构视觉证据，说明 WorkerPool / ActorTemplate / router / ate-api / gVisor / checkpoint 链路 |
| [AgentCube 会话运行时架构图](agentcube-session-runtime-architecture.drawio.png) | AgentCube 目标架构图，覆盖 Router activation、Store CAS、RuntimeProvider 和 capacity pool |
| [Day29：agentd 组件作用分析](day29-agentd-component-role-analysis.md) | unused agentd 删除前的组件考古、PicoD 对照、PR #403 scope 解释 |
| [Day30：PR #387 warm pool 数据流 review](day30-pr387-warm-pool-dataflow-review.md) | v0.4.6 object-flow 实测、claim adoption、Store identity、Router 数据流 |
| [Day31：PR #400 PicoD metrics review](day31-picod-prometheus-metrics-review.md) | Prometheus middleware 顺序 bug、测试命令、英文 review comment 草稿和上游评论记录 |
| [Day32：Substrate 竞品分析与 AgentCube PRD](day32-substrate-competitive-analysis-and-agentcube-prd.md) | 把竞品能力、AgentCube 缺口、产品需求、非目标、验收指标和开源路线连起来 |

## 本周卡点和限制

| 卡点 | 当前结论 |
| --- | --- |
| Agent Substrate 没有完整跑通 counter demo | 本机 kind / kubeadm bootstrap 曾失败，当前 Substrate 主要基于源码复核和架构图分析；如果要证明 runtime 行为，需要换更适合的 K8s 环境 |
| MicroVM / Firecracker 类能力无法实测 | 当前机器没有 `/dev/kvm`，不能声称已经验证 micro-VM snapshot / restore，只能记录源码能力和环境限制 |
| Sleep/Resume 不是已合入产品能力 | 本周完成设计、spike、review matrix 和测试计划，不应对外说 AgentCube 已支持完整 Paused -> Ready 恢复 |
| #387 仍在 review | warm pool adoption 的本地证据已经充分，但 upstream 还需要 maintainer review、`/lgtm`、`/approve` 和 tide |
| #403 仍在 review | agentd 删除 PR 不再主动 push/comment，除非 reviewer 要求解释 Dockerfile scope 或拆 follow-up |
| #400 bug 已评论 | 后续只跟踪作者/maintainer 回复；如果作者 push 新 commit，再重新复测 413 metrics 行为 |
| fork CI 流程已修正但还需实际复用 | 新的 fork-only push validation 模板已经建立，后续第一次使用时还要记录完整命令和结果 |

## 能力复盘

### 1. 需求拆分

Week 3 的拆分能力主要体现在 Sleep/Resume 和 #387：

- Sleep/Resume 被拆成 Store/CAS、WorkloadManager lifecycle、GC split、Router resume-before-proxy、provider hard pause、e2e/math-agent validation。
- #387 被限定为 `agent-sandbox v0.4.6` compatibility，不把 v0.5.x / v1beta1、Pod informer race、Data-Flow Inspector、Sleep/Resume 都塞进去。
- #403 被限定为 unused agentd cleanup，不把所有 PicoD 或 GC 改造混进去。

### 2. 架构边界

本周最稳定的架构边界是：

```text
Router: owner/auth + activation gate + proxy
WorkloadManager: lifecycle workflow + provider coordination
Store: status / placement / CAS / indexes
RuntimeProvider: runtime-specific create/pause/resume/delete/probe
Kubernetes: low-frequency declarative resources and capacity pool
PicoD: sandbox 内 data-plane daemon
Benchmark: external evidence, not product implementation
```

这些边界以后可以直接用于 PR review：只要一个改动让 Router 直接理解 agent-sandbox CRD 细节，或让 Store 只保存 endpoint 而没有 status/version，就应该追问是否破坏了分层。

### 3. 测试设计

Week 3 的测试思路从“跑通 e2e”升级成“风险到测试”：

| 风险 | 对应测试 |
| --- | --- |
| 并发 resume 写回旧状态 | Store CAS conflict / race tests |
| Router resume 后使用旧 endpoint | paused resume success 后重新读 Store 的 handler test |
| GC 把 paused session 直接 delete | GC decision table unit tests |
| provider 成功但 final CAS 失败 | lifecycle service compensation / failure-state tests |
| warm-pool claim adoption 语义错误 | L1 object-flow inspector / k3d 手工验证 |
| metrics middleware 短路 | oversized 413 request metrics test |
| cleanup 不完整 | SandboxClaim / Sandbox / Pod / Store / warm pool refill 检查 |

### 4. 代码审查

本周 review 的核心习惯是：先建立“正确运行应该长什么样”，再看代码是否满足。

对于 #387，正确运行图是 claim adoption 和 Store identity 分离；对于 #400，正确运行图是所有 HTTP status 都应被 metrics middleware 看到；对于 #403，正确运行图是当前主线不再依赖 agentd，PicoD 才是 sandbox 内 daemon。

### 5. 开源纪律

Week 3 固化了几个更成熟的边界：

- upstream-facing 内容必须英文、模板化、先给用户确认。
- 不把中文报告、raw benchmark 和本地 workflow 混入 upstream PR。
- 不主动在别人已认领的 issue 上抢实现。
- 本地证明 bug 后才发 review comment。
- fork/intern/upstream 分支职责明确。
- CI 验证不能牺牲贡献历史质量。

## 下周建议

下周不建议马上开大 PR。更高价值的路线是继续做小而可验证的 review / design / test asset：

1. 跟踪 PR #400 作者回复；如果有新 commit，复测 oversized 413 metrics 是否被记录。
2. 跟踪 PR #387 review；如 reviewer 追问 warm-pool 数据流，用 Day30 的 object-flow 证据和英文草稿回应。
3. 跟踪 PR #403 review；只在 reviewer 质疑 scope 时解释 agentd / PicoD / Dockerfile 关系。
4. 如果继续 Sleep/Resume，优先把 3B Router resume-before-proxy 的 handler test matrix 写成更具体的本地 test skeleton，不直接发 upstream。
5. 把 benchmark / conformance suite 草案推进成统一 schema：cold、warm、pause、resume、delete cleanup、p50/p95/p99、环境记录。
6. 如要做新的 upstream 贡献，优先选择低争议、可单测、scope 小的 docs/test/review patch，而不是抢完整功能实现。

## 一句话总结

Week 3 的真正产出不是某一个 PR，而是把 AgentCube 的工作重心从“适配一个 sandbox 版本”推进到“设计和审查一个长期 session runtime 控制面”。这套判断已经落到架构图、PRD、review matrix、测试矩阵、上游评论和本地工作流里；下周的重点是继续用小证据、小 PR 和高质量 review 去证明这些判断。
