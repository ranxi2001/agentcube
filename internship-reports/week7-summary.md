# Week 7 总结：版本升级 Review、运行时安全与 Karmada 调度修复

日期：2026-07-20 至 2026-07-24

证据截止：2026-07-24 23:59 CST

> 统计口径：本周总结只记录 7 月 20 日至 7 月 24 日已经发生的提交、Review、测试和社区状态。后续 PR 的 merge 或新 head 只在 Week 8、Week 9 中记录，不倒填本周状态。

## 主管摘要

### 本月目标

| 目标 | 状态 |
| --- | --- |
| 完成 AgentCube 对 agent-sandbox v0.5.x 的兼容性和存量升级路径验证 | 进行中 |
| 用可复核的 PR Review 推进 AgentCube runtime、security 和 lifecycle 问题 | 进行中 |
| 将 AgentCube 中形成的状态机、cleanup 和测试判断迁移到 Karmada 控制器工作 | 进行中 |

### 本周进展

| 工作项 | 结果、价值或剩余风险 | 状态 |
| --- | --- | --- |
| agent-sandbox v0.5.2 适配 PR Review（AgentCube PR #442） | 完成 diff-to-diff Review，并发布升级路径与 generated informer identity 反馈；确认 12 项 CI 检查只覆盖 clean install，尚不能证明 v0.4.6 存量 Claim 升级 | 已完成；等待作者继续修改 |
| AgentRuntime 示例与 Router-PicoD mTLS（AgentCube PR #437、Issue #444） | 复现示例容器 PID 1 收到 SIGTERM 后等待强制退出的问题并发布 inline comment，作者已修正；同时发布 mTLS 设计评论，明确 TLS 终止、Router 身份和 PicoD key ownership 的边界 | 已完成；两个上游对象仍开放 |
| Remedy 状态修复与 scheduler 回归（Karmada PR #7777、#7791、#7795） | RemedyActions 状态变化修复已 merge；提交 affinity reset scheduler test 和稳定 `karmadactl top` E2E fixture，后两项等待维护者审核 | 已完成当周提交；外部审核进行中 |
| 社区治理与删除保护 Review（AgentCube PR #439、Karmada PR #7779） | RainbowMango OWNERS 提名已 merge；Karmada Cluster 删除保护 Review 证明 `DeleteCollection` 可绕过单对象保护，并发布完整调用链与最小修正建议 | 已完成 |

### 收获与分享

1. AgentCube agent-sandbox v0.5.2 PR #442 的 GitHub thread 即使显示 `resolved` 或 `outdated`，current head 仍可能保留同一缺陷。以后依据最终代码和 exact head 判断 finding 是否关闭，不依据按钮状态。
2. AgentCube AgentRuntime 示例把 Python server 作为容器 PID 1 运行时，未处理 SIGTERM 会让 Pod 删除等待默认 termination grace 后再被 SIGKILL。以后审查示例和 sidecar 时，把 process lifecycle 与 cleanup 作为独立测试面。
3. Router-PicoD mTLS 不只需要链路加密，还要定义谁持有私钥、PicoD 如何识别 Router、JWT 与目标实例如何绑定。以后安全设计先画 trust boundary，再讨论证书分发。

### 疑惑与问题

1. AgentCube 的 agent-sandbox v0.5.x 适配是否必须在同一个 PR 中交付 v0.4.6 存量 CRD migration，还是允许将 clean install 与 in-place upgrade 拆分？该决定会直接影响 AgentCube PR #442 的验收范围。
2. Router-PicoD mTLS 的第一阶段应采用全局 PicoD identity，还是为每个 workload 绑定独立 identity？前者部署简单，后者隔离更强，但需要明确证书生命周期和 Router target binding。

### 下周计划

| 任务 | 可检查结果 |
| --- | --- |
| agent-sandbox replacement PR Review | 对 AgentCube PR #442 的新 head 或 replacement PR 重新建立 API、migration、lifecycle、MCP 和 E2E 风险清单，不沿用过期结论 |
| MCP SDK compatibility | 若 MCP v2 drift 已形成稳定复现，提交一个只处理 Code Interpreter MCP migration 的独立 AgentCube Issue / PR，并完成 HTTP、stdio 和 in-cluster 验证 |
| Karmada scheduler / queue Review | 完成至少一个 source-proven 调度问题的 PR Review 或 Issue 分析，并把 producer、queue、retry 和 cleanup 路径写清楚 |
| 竞品架构校准 | 比较 node-local sandbox transaction 与 Kubernetes per-sandbox control path，输出状态所有权和 benchmark 口径，不直接复用厂商 headline |

## 本周工程记录

### 1. AgentCube v0.5.2 适配 Review

本周以未读取作者实现前完成的 fork adapter 为独立基线，对 AgentCube PR #442 做 diff-to-diff Review。Review 把兼容问题拆为六个面：API package、CRD storage、存量 migration、warm-pool adoption、generated client 和 E2E。

已确认作者实现完成了 v1beta1 API 的主要机械迁移，并将 Kubernetes runtime modules 与 `code-generator` 对齐；本地 adapter 此前保留旧 generator，这是对照后发现的自身遗漏。

同时确认两项当前风险：

- 官方 agent-sandbox migration guide 要求 cold-start Claim 在 v0.4.x 阶段先执行 bootstrap，PR 文档当时直接升级 CRD/controller，无法支持其承诺的 active Claim 平滑迁移。
- generated informer identity 使用短 group `runtime`，真实 API group 为 `runtime.agentcube.volcano.sh`。typed List/Watch 仍可工作，但启用 informer naming 时 metrics identity 和 uniqueness 会出错。

> 注释：clean-install E2E 从空集群直接安装新 CRD，验证的是新对象能否工作；in-place upgrade E2E 还要先创建旧版本对象、升级 conversion webhook 和 controller，并验证原对象 identity、GC 与 pool refill。两种测试不能互相替代。

### 2. AgentRuntime 与 mTLS Review

AgentCube PR #437 的四个文件主要修复 SDK 示例、echo server 和 PCAP Router 地址。本周没有重复 AI reviewer 已报告的 context-manager 和 body-limit 问题，而是通过两个 Docker 对照实验复现 PID 1 termination：原实现 `docker stop -t 2` 后退出码为 137，增加显式 SIGTERM exit 后约 0.20 秒退出且返回 0。

该 finding 发布后，作者增加 SIGTERM 处理。复核时保留了一个边界：现有 AgentCube E2E 不部署该示例 manifest，因此只能写成“代码路径已修正”，不能写成“termination E2E 已覆盖”。

AgentCube Issue #444 的 mTLS 分析则把问题拆成 transport encryption、peer authentication、private-key ownership、workload identity 和 token target binding。发布评论只确认 sidecar key isolation 和 operator-level policy 方向，不把 agent-sandbox creator identity 当作不可伪造的 attestation。

### 3. Karmada 修复与 Review

Karmada Remedy 状态修复 PR #7777 于 7 月 21 日 merge。该修复让 `RemedyActions` 变化触发 controller 重新处理，并以 test-only failure、fix pass 和 reverse-patch failure 证明因果边。

随后提交两个测试类 PR：

- Karmada PR #7791：覆盖完整重调度时 affinity cursor 必须从第一个 term 重新评估，避免只重新计算 replicas 而沿用旧搜索位置。
- Karmada PR #7795：稳定 `karmadactl top` E2E 的 Pod fixture，避免短生命周期对象在指标采集前消失。

对 Karmada PR #7779 的 Review 证明 `Cluster` storage 只覆盖 `Delete`，嵌入的 generic store 仍暴露 `DeleteCollection`，因此 collection delete 可绕过 deletion-protection label。该结论有 generated client、API installer、REST method promotion 和 unit test 证据，不依赖构造出的不可能状态。

## 输出与验证

### 社区活动

| 类型 | 数量 | 对象 |
| --- | ---: | --- |
| 本周新开 PR | 2 | Karmada scheduler affinity reset #7791、`karmadactl top` E2E fixture #7795 |
| 本周 merge 的本人 PR | 2 | AgentCube OWNERS 提名 #439、Karmada Remedy 状态修复 #7777 |
| 他人 PR 实质 Review | 3 | AgentCube v0.5.2 适配 #442、AgentRuntime 示例 #437、Karmada Cluster 删除保护 #7779 |
| Issue 深度分析 | 1 | AgentCube Router-PicoD mTLS #444 |

### 关键测试证据

| 风险 | 证据 | 结论边界 |
| --- | --- | --- |
| v0.5.2 compatibility | AgentCube PR #442 exact head 12/12 checks，CodeInterpreter target path 实际执行 | 证明 clean install，不证明 v0.4.6 in-place migration |
| AgentRuntime termination | 两组原行为 Docker stop 约 2.2-2.3 秒且 exit 137；显式 handler 约 0.20 秒且 exit 0 | 证明 PID 1 lifecycle；不代表 AgentCube E2E 已覆盖 |
| Karmada deletion protection | `go test ./pkg/registry/cluster/storage` 与相关 package 通过；调用链证明 `DeleteCollection` bypass | finding 是 production-reachable；当前 PR 仍需作者修正 |
| RemedyActions reconcile | test-only fail、fix pass、reverse-patch fail | 局部 E4；不把无关 CI host I/O 失败归为产品问题 |

### 失败与处理

| 失败步骤 | 现象 | 处理 |
| --- | --- | --- |
| 本地运行 AgentRuntime Python SDK tests | detached worktree 缺少 `pytest` 和 `ruff` | 使用 exact-head GitHub Python checks 作为对应证据，同时单独运行与 finding 直接相关的容器 smoke test；未把本地缺依赖写成 PR 失败 |
| 仅看 AgentCube PR #442 的 E2E 名称 | CI 全部通过，但没有旧版本安装和 migration 步骤 | 阅读脚本和日志确认实际测试选择，将结论限定为 clean install |
| Karmada PR #7777 CI 重跑 | 三个 etcd 同时出现 I/O stall，产品 spec 未执行 | 不修改产品逻辑迎合无关失败，保留 host I/O observability 作为 CI 改进项 |

## 证据索引

- [AgentCube Day 52：v0.5.2 Diff-to-Diff Review](day52-pr442-agent-sandbox-v052-diff-to-diff-review.md)
- [AgentCube Day 53：AgentRuntime examples Review](day53-pr437-agent-runtime-examples-review.md)
- [AgentCube Day 54：Router-PicoD mTLS design](day54-issue444-router-picod-mtls-design-screening.md)
- [Karmada Cluster 删除保护 Review](https://github.com/ranxi2001/karmada/blob/intern/internship-reports/day30-pr7779-cluster-deletion-protection-review.md)
- [Karmada WorkloadRebalancer API 计划](https://github.com/ranxi2001/karmada/blob/intern/internship-reports/day31-workload-rebalancer-api-development-plan.md)
- [Karmada PR #7791 E2E Flake RCA](https://github.com/ranxi2001/karmada/blob/intern/internship-reports/day33-pr7791-e2e-flake-root-cause-analysis.md)
