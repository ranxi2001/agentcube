# Week 8 总结：MCP SDK v2 合入、v0.5.3 独立验证与 Final-Head Review

日期：2026-07-27 至 2026-07-31

证据截止：2026-07-31 23:59 CST

> 统计口径：本周将 AgentCube PR #442 关闭、replacement PR #446 创建、MCP PR #448 merge 和 Karmada PR #7791 merge 分别按实际日期记录。8 月发生的 #446 后续修正与 Review 不计入本周结果。

## 主管摘要

### 本月目标

| 目标 | 状态 |
| --- | --- |
| 完成 AgentCube 对 agent-sandbox v0.5.3 的独立兼容性验证，并对上游 replacement PR 给出可复核 Review | 进行中 |
| 修复 AgentCube Code Interpreter 对 MCP Python SDK v2 的兼容问题 | 已完成 |
| 将多轮 PR Review 从旧评论跟踪升级为 final-head 全范围复核 | 进行中 |
| 继续验证 Karmada scheduler、queue 和 controller 状态处理 | 进行中 |

### 本周进展

| 工作项 | 结果、价值或剩余风险 | 状态 |
| --- | --- | --- |
| Code Interpreter MCP SDK v2 migration（AgentCube Issue #447、PR #448） | 提交并 merge 独立修复，保留 Streamable HTTP `/mcp`，同时覆盖 stdio、Docker rollout 和 in-cluster MCP E2E；避免把 MCP workaround 混入 agent-sandbox upgrade | 已完成并 merge |
| agent-sandbox v0.5.3 replacement PR Review（AgentCube PR #446） | 在 PR #442 关闭后重新从 parent Issue 建立 scope；发布 production scheme、migration producer、Router h2c 和 upgrade guide 等 focused feedback，并在每次 force-push 后复核 exact head | 已完成本周 Review；PR 仍在修改 |
| v0.5.3 独立 adapter 与 Review harness | 在 fork 以 5-file increment 从已验证 v0.5.2 升至 v0.5.3，真实 API Server 验证 `volumeClaimTemplates` immutability；新增 final-head evidence harness 和 agent trajectory evaluator | 已完成本周实现与验证 |
| Karmada scheduler 与 queue 路径（Karmada PR #7791、#7800，Issue #7802） | affinity reset regression PR 已 merge；对 ResourceDetector waiting store 发布深度 Review，并用确定性实验说明 priority queue re-entry 顺序 | 已完成；#7800 与 #7802 等待社区后续 |

### 收获与分享

1. AgentCube agent-sandbox v0.5.3 PR #446 多次 force-push 后，逐条检查旧 finding 不能证明最终版本满足 upgrade Issue #438。以后 final review 从 parent Issue、完整 diff 和 changed-test discovery 重新开始。
2. AgentCube agent-sandbox v0.5.3 PR #446 的 CI 曾执行新增 migration block，但 fixture 没有经过真实 WorkloadManager session producer。测试有运行记录不等于测试能证明目标行为，先验证 producer、对象 lineage 和断言对象。
3. `Sandbox.spec.volumeClaimTemplates` immutability 测试第一次返回 `409 Conflict`，原因是 controller 同时更新 resourceVersion。只有重试后得到 API Server `Invalid` 才能证明 CEL 规则生效，不能把任意 update error 当成功。

### 疑惑与问题

1. AgentCube agent-sandbox v0.5.3 PR #446 是否应保留 codegen、MCP、Router h2c 和跨平台脚本等变更，还是拆出独立 prerequisite / follow-up？范围决定会直接影响 Review 成本和 regression 面。
2. Karmada ResourceDetector 的 waiting store 应在删除事件到达时继续等待对象重新出现，还是让失败对象立即回到普通处理路径？两种选择影响 retry latency 和 stale object cleanup。

### 下周计划

| 任务 | 可检查结果 |
| --- | --- |
| agent-sandbox v0.5.3 final-head Review（AgentCube PR #446） | 对新 head 生成完整 finding ledger，逐项标记 fixed / present / out-of-scope，并确认 changed tests 被 CI 或 direct test 实际执行 |
| CodeInterpreter child ownership Review | 审查 AgentCube WorkloadManager 在同名资源冲突、更新和删除时是否绑定 UID / resourceVersion，并输出 causal regression 要求 |
| WarmPoolAvailable rebase | 在 v0.5.3 基线上重算 AgentCube PR #385 的 6-file feature diff，完成 unit、race、E2E 和 fork checks，保持 feature 与 runtime prerequisite 分离 |
| Agent runtime 架构研究 | 对 node-local fast plane、Kubernetes lifecycle 和 request routing 分层，形成可用于 AgentCube 设计判断的状态所有权模型 |

## 本周工程记录

### 1. MCP SDK v2 独立修复

AgentCube 的 MCP dependency 原先写为无上界 `mcp>=1.8.0`。clean CI 解析到 v2 后，旧 `FastMCP` import、SSE client 和 transport 参数不再兼容，导致共享 CodeInterpreter E2E 失败。

本周创建 AgentCube Issue #447 并提交 PR #448。修复保持 v2 的 Streamable HTTP 路线，没有通过 pin 回 v1 回避问题；同时保留 stdio client，更新 server、Docker readiness、deployment 和 E2E。local Streamable HTTP、stdio、Docker rollout、in-cluster MCP E2E 与 upstream 13 项检查通过，PR 于 7 月 30 日 merge。

> 注释：MCP SDK v2 drift 是 AgentCube 的独立 SDK integration 问题，不是 agent-sandbox v0.5.3 API 变化。把它拆成 PR #448 后，replacement PR #446 可以 rebase 并删除重复 workaround。

### 2. v0.5.3 adapter 与真实 API Server 测试

fork branch `compat/agent-sandbox-v053-independent@5957314` 从已验证的 v0.5.2 adapter 增加一个 5-file patch，只更新 module、安装文档和 E2E version/immutability case。production controller 不需要再次大改，因为 beta GVR、scheme、watch、OperatingMode、SandboxBlueprint、WarmPoolRef 和 pointer replicas 已在 v0.5.2 层完成。

新增测试在 k3d / k3s v1.32.5 上安装官方 v0.5.3 CRD/controller，创建 Sandbox 后修改 `volumeClaimTemplates`，要求 API Server 返回 `Invalid`。最初因 controller 并发更新返回 `409 Conflict`，改为 `RetryOnConflict` 后到达 CEL validation 并通过。

该结果说明 v0.5.3 相对正确的 v0.5.2 baseline 是小增量，也说明 #446 的 generated code、MCP 和 Router 大 diff 不能都解释成 v0.5.3 必需项。

### 3. PR #446 多轮 Review

AgentCube PR #442 于 7 月 29 日关闭，作者创建 PR #446 升级到 v0.5.3。Review 首先证明 production binary 仍注册 alpha scheme，而 reconciler 已读写 beta types；本地 binary-level red/green test 使作者能按最小方向修正 scheme、watch 和 regression test。

随后多次 force-push 又暴露新的 scope 和测试问题：

- MCP workaround 与已独立验证的 PR #448 重叠，且一度引入 transport、lint、DCO 和 Router source failure。
- upgrade fixture 使用 admission-invalid CodeInterpreter 字段，并且没有调用 WorkloadManager create-session producer，因此不会创建它声称要迁移的 Claim。
- final head 一度移除 Router 默认 h2c，超出 agent-sandbox upgrade scope。
- Docusaurus upgrade guide 的路径与静态站点 base path 不一致，用户按文档访问会得到 404。
- 新增 `cmd/workload-manager/main_test.go` 不在当时的 `./pkg/...` coverage command 中，绿色 workflow 不能证明该 regression 被执行。

本周把这些问题从聊天 checklist 固化为 final-head evidence harness：冻结 base/head/merge-base，逐个解释 hand-written path，检查 changed tests 的 package 与 workflow command 是否对应，并对 unresolved finding fail closed。

### 4. Karmada 调度与 queue 反馈

Karmada PR #7791 于 7 月 31 日 merge。该 PR 只增加 scheduler regression，证明显式 Full reschedule 时必须重置 affinity cursor；没有把仍未定稿的 `PreserveAvailableReplicas` API 一并加入。

对 Karmada PR #7800 的 Review 发现 waiting store 在 matching object 删除后可能永久保留 stale queue item，导致后续同名对象被错误匹配。Review 将问题定位到 ResourceDetector producer、waiting store identity 和 delete path，而不是只建议加 timeout。

Karmada Issue #7802 则通过 priority queue 的确定性实验说明：对象 retry 后重新入队可能保留旧 sequence，较低优先级对象因此持续排在后面。发布评论明确这是 queue ordering 问题，没有把单次实验外推成已观察生产事故。

### 5. 平台架构调研

Day 56 对 `sandbox-operator` 与 `agent-sandbox-platform` 做固定 SHA 对照。结论是：aggregated API + NodeInventory + direct node claim/release 改变了每请求 transaction path，但 33 ms 数据测的是预热 microVM ownership transfer，不能与 E2B snapshot resume 或 AgentCube cold create 混排。

该研究把 benchmark schema固定为 control plane、claim、runtime ready、Router、exec 和 cleanup 六层，并把 durable Kubernetes intent 与 node-local runtime truth 分开。

## 输出与验证

### 社区活动

| 类型 | 数量 | 对象 |
| --- | ---: | --- |
| 本周新开 PR | 1 | AgentCube Code Interpreter MCP SDK v2 migration #448 |
| 本周 merge 的本人 PR | 2 | AgentCube MCP SDK v2 #448、Karmada scheduler affinity reset #7791 |
| 他人 PR 实质 Review | 3 | AgentCube v0.5.2 / v0.5.3 replacement #442 / #446、Karmada ResourceDetector #7800 |
| Issue 深度分析 | 2 | AgentCube MCP v2 compatibility #447、Karmada priority queue #7802 |

### 关键测试证据

| 风险 | 证据 | 结论边界 |
| --- | --- | --- |
| MCP v2 migration | local HTTP / stdio、Docker rollout、in-cluster MCP E2E；upstream 13/13 checks | PR #448 已 merge；只覆盖 MCP integration |
| v0.5.3 CRD immutability | k3d v1.32.5 + official v0.5.3 manifest，RetryOnConflict 后 API Server 返回 Invalid | 证明 CRD CEL；不代替完整 AgentCube migration |
| PR #446 production scheme | binary-level test 在 alpha wiring 下 fail，beta scheme/watch 对齐后 pass | 关闭原 finding；不代表整个 PR ready |
| Karmada affinity reset | focused scheduler tests 与 exact-head CI 通过 | 证明 Full cursor reset；不实现 preserve-available API |

### 失败与处理

| 失败步骤 | 现象 | 根因与处理 |
| --- | --- | --- |
| PR #446 upgrade E2E | CodeInterpreter manifest strict-decoding 失败，修字段后仍不会产生 Claim | fixture 未使用真实 session producer；要求先通过 WorkloadManager create-session 创建同一条 Claim/Sandbox/Pod lineage |
| MCP workaround 内嵌进 PR #446 | transport 404、unused import、DCO 和 Router compile failure 交替出现 | 让独立 PR #448承担完整 v2 migration；#446 后续只需 rebase 并删除重复 patch |
| v0.5.3 immutability test | 第一次 Update 返回 `409 Conflict` | controller 并发写 resourceVersion；使用 RetryOnConflict，只接受最终 `Invalid` 作为规则生效证据 |
| Karmada PR #7791 merge CI | recurring chart registry / infrastructure failure | 分类为共享 CI 问题，不修改 scheduler test 迎合无关失败；最终 PR merge |

## 证据索引

- [AgentCube Day 55：v0.5.x 新 Head Review](day55-pr442-agent-sandbox-v052-new-head-review.md)
- [AgentCube Day 55：Review drafts](day55-pr442-review-drafts.md)
- [AgentCube Day 56：sandbox platform study](day56-sandbox-operator-agent-sandbox-platform-study.md)
- [AgentCube Day 57：Agent AutoHarness](day57-agent-autoharness-trajectory-evaluation.md)
- [Karmada PR #7800 waiting store Review](https://github.com/ranxi2001/karmada/blob/intern/internship-reports/day36-pr7800-waiting-store-deep-review.md)
- [Karmada Issue #7802 priority queue experiment](https://github.com/ranxi2001/karmada/blob/intern/internship-reports/day36-issue7802-priority-queue-experiment.md)
- [Karmada Descheduler 专项调研](https://github.com/ranxi2001/karmada/blob/intern/internship-reports/day38-karmada-descheduler-special-study.md)
