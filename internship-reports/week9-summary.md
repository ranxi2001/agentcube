# Week 9 总结：Ownership 修复验收、升级实证与实习收尾

日期：2026-08-03 至 2026-08-11

证据截止：2026-08-11 23:59 CST（收尾延长周）

> 统计口径：Week 9 覆盖 8 月 3 日至 8 月 11 日的收尾工作。8 月 11 日之后的 Go 版本、PR 新 head、维护者评论和 merge 状态不计入本周完成情况；相关动态只在后续 `PROGRESS.md` 中维护。

## 主管摘要

### 本月目标

| 目标 | 状态 |
| --- | --- |
| 完成 AgentCube CodeInterpreter lifecycle 的 ownership、migration 和 warm-pool health 验证 | 已完成当期实现与 Review；部分 PR 等待社区决定 |
| 将 AgentCube final-head Review 固化为可执行、可回归的检查流程 | 已完成当期工具和回放 |
| 完成 Agent runtime、cluster placement 和 request routing 的分层架构研究 | 已完成当期研究 |
| 完成实习期主要代码、Review、测试和文档交付 | 已完成 |

### 本周进展

| 工作项 | 结果、价值或剩余风险 | 状态 |
| --- | --- | --- |
| CodeInterpreter child ownership Review（AgentCube PR #450） | 发现 ownership check 与最终 DELETE 对象之间存在同名 replacement 窗口；作者增加 UID / resourceVersion preconditions 和 replacement regressions，本地 causal red/green、package 与 race tests 通过，已发布复核结论与 `/lgtm` | 已完成；等待维护者 approval / merge |
| agent-sandbox v0.5.3 migration Review（AgentCube PR #446） | 多轮 exact-head closure 推动 upgrade guide、webhook gate、对象 lineage 和 cleanup 修正；fork same-lineage E2E 证明 warm-pool member adoption、GC 与 refill；维护者随后提出 scope / decomposition 意见，PR 仍开放 | 已完成本周 Review；外部修改继续 |
| WarmPoolAvailable 刷新（AgentCube PR #385） | 将 6-file feature 迁移到 v0.5.3 最终行为，补 Event RBAC 与生产权限验证；upstream 13/13 非 Tide checks、fork 9/9 workflows 和 CodeInterpreter E2E 通过 | 已完成当期更新；等待维护者审核 |
| Karmada 与架构收尾（Karmada PR #7795、Issue #7492；AgentENV / Volcano / Kthena） | `karmadactl top` fixture PR 已 merge；完成多组件 scheduling result API 设计，并形成 request routing、lifecycle、cluster placement、node-local fast plane 四层对照 | 已完成当期交付；#7492 后续实现继续 |

### 收获与分享

1. Kubernetes 对象名称不是对象身份。AgentCube WorkloadManager 在 ownership check 后按名称删除资源时，同名对象可被替换；删除必须绑定已观察对象的 UID / resourceVersion preconditions。
2. AgentCube agent-sandbox v0.5.3 PR #446 的多轮 Review 证明 final-head readiness 不能由“旧 finding 已回复”推出。以后从 parent Issue 验收条件重新建 ledger，并要求每个 changed test 有 CI exact-head PASS 或 clean direct execution。
3. Volcano、Kthena、AgentENV 和 AgentCube 使用的 scheduler 分别处理 `Pod -> Node`、`Request -> Backend Pod`、`Sandbox -> Runtime Node` 和 sandbox lifecycle。以后讨论架构前先说明调度单位、绑定目标和权威状态。

### 疑惑与问题

1. AgentCube 的 v0.5.3 upgrade PR 应继续承载 dependency prerequisite、upgrade guide 和 repository cleanup，还是按维护者建议拆成多个 merge unit？该决定影响 #446 的最终 scope，不能由 contributor 单方面决定。
2. AgentCube 是否需要 node-local fast plane，应先测量 per-sandbox API Server / etcd / informer 成本，还是先定义 intent、runtime truth 和 failure recovery 接口？缺少目标规模数据时，不应直接选择“去 Kubernetes”路线。
3. Karmada Issue #7492 的 component scheduling result 在新一轮调度失败时应保留最近一次成功结果，还是清空并阻止下发？这一失败状态机需要维护者明确后才能完成后续 producer PR。

### 下周计划

| 任务 | 可检查结果 |
| --- | --- |
| AgentCube open PR handoff | 为 WarmPoolAvailable #385、Go update workflow #429、agent-sandbox v0.5.3 upgrade #446、CodeInterpreter ownership #450 分别保留 current state、验证证据、外部 owner 和停止条件，不自动追加评论或提交 |
| Final-head Review 复用 | 下一次真实 PR Review 直接采集 normalized events、finding ledger、token/time/tool telemetry，并用至少 3 个 frozen tasks 做 held-out regression |
| Agent runtime 架构验证 | 先建立统一 benchmark schema，分别测 request routing、lifecycle、cluster placement 和 node-local runtime，再决定 slow global plane 与 fast local plane 的边界 |
| 实习答辩材料 | 以最终总结、Week 1-9 和系统位置图为唯一事实基线，确保 merged/open、测试边界和个人职责表述一致 |

## 本周工程记录

### 1. CodeInterpreter child ownership

AgentCube PR #450 为 CodeInterpreter 管理的 SandboxTemplate 和 SandboxWarmPool 增加 owner 检查，方向正确，但最初流程是“GET 并验证 owner，然后按 name DELETE”。检查与删除之间若对象被其他 writer 替换，DELETE 会作用于新对象。

Review 通过 fake client hook 在 ownership check 后替换对象，稳定复现错误删除；最小修正是把已观察对象的 UID / resourceVersion 放入 `DeleteOptions.Preconditions`。作者补齐 Template / WarmPool 两条路径和 replacement regressions 后，本地六项 causal red/green、完整 `pkg/workloadmanager` 与 race tests 通过。

> 注释：owner reference 证明“读取时谁拥有该对象”，precondition 证明“删除时仍是同一个对象”。两者解决不同的时间窗口，不能互相替代。

### 2. v0.5.3 migration 与 final-head closure

8 月 3 日至 8 月 10 日，AgentCube PR #446 多次更新。每轮 Review 都冻结 exact head，并用 21-item finding ledger 区分 fixed、present 和 repository follow-up。重点推进包括：

- production scheme 与 beta watch 对齐；
- conversion webhook readiness 从无界等待改为有 timeout、诊断和 non-zero exit；
- upgrade guide 路径、storage migration 和 generated schema 校准；
- migration E2E 从手工孤立 Sandbox 推进到真实 warm-pool member；
- changed test package 的 CI discovery 与 direct fallback；
- authenticated owner persistence、embedded PodSpec 字段兼容和 codegen environment 边界。

为验证最难的 lineage 问题，fork-only branch 让 upgrade Claim 采用真实 `e2e-upgrade-warmpool` member，并在升级后删除同一 Claim，按原 Sandbox / Pod UID 验证 GC，再确认 source pool refill。隔离 k3d v1.32.5、official v0.5.3 manifest、fork 9/9 workflows 与两个 E2E matrix jobs 通过；验证完成后删除集群、network、volume 和 kubeconfig。

8 月 10 日，根 OWNERS reviewer 对同一 head 提出 7 条评论，可归并为 5 个主题：3 个 technical scope closure、upgrade docs placement 和 prerequisite split。前 3 项属于此前已发现但未坚持到最终移除的 known-item closure miss；后 2 项是维护者 project-policy / sequencing 决定。周报因此不把 #446 写成 merge-ready。

### 3. WarmPoolAvailable PR #385

AgentCube PR #385 在 v0.5.3 baseline 上保持 6 个 hand-written files，继续实现 CodeInterpreter 的 `WarmPoolAvailable` condition。更新同时处理 Event RBAC：不仅创建 recorder，还验证 WorkloadManager ServiceAccount 对 `events.k8s.io` create / patch 的生产权限。

当前证据包括 local unit / race / non-E2E Go、CodeInterpreter E2E、upstream 13 项非 Tide checks 和 fork 9 个 workflows。外部状态仍缺 `approved` / `lgtm`，因此本周状态是“本人更新与验证完成，等待维护者审核”，不是“已 merge”。

### 4. Review harness 与 agent trajectory eval

Day 57 将 PR Review 过程归一为 observable events，分别评估 task achievement、finding recall / precision、resource efficiency 和 trajectory reasonableness。对 #446 的 post-hoc replay 发现，自报“完整 Review”与 reference coverage 只有 70% 的结果冲突。

基于该缺口，final-head harness 增加以下 fail-closed gate：

- base / head / merge-base 先冻结为 SHA；
- hand-written changed file 与 material hunk 必须有 scope closure；
- changed `*_test.go` package 必须映射到无条件 full-package command，并有 exact-head CI PASS 或 direct execution；
- pull_request synthetic merge ref、filtered / skipped command、动态 Makefile 或自由文本 PASS 不能作为 exact-head waiver；
- direct fallback 从 Git object 物化 clean tree，固定 Go binary、go.work 和 sanitized environment。

最终 focused harness、review skill 和跨 skill 回归 tests 全部通过，但 #446 lineage 已被用于训练和修正规则，不能再作为独立 held-out 证据。

### 5. Karmada 与四层架构研究

Karmada PR #7795 于 8 月 10 日 merge。该 PR 使用稳定 Pod fixture 修复 `karmadactl top` E2E 的生命周期竞争；无关 chart registry / infrastructure failure 被单独分类，没有通过延长所有 timeout 掩盖。

Karmada Issue #7492 的收尾工作定义 `TargetCluster.Components` / `TargetComponent` scheduling result API，并按维护者 Draft 拆出 API、scheduler producer、`ReviseComponents`、third-party interpreter 和 downstream E2E。当前仍未确定失败重调度时旧成功结果的保留规则，周内只完成 API 方向和 preflight，不把完整功能写成已完成。

Day 59 / Day 60 对 AgentENV、Volcano 和 Kthena 做固定 SHA 研究：

- AgentENV 把 per-sandbox runtime / lifecycle 放到 node-local Firecracker orchestrator，Kubernetes 仅是可选 deployment / discovery adapter；当前 placement 仍是 advisory，不是强 reservation。
- Volcano 负责 Kubernetes 内的 batch admission、Queue / PodGroup / Gang 和 `Pod -> Node` placement。
- Kthena controller 负责 model lifecycle，Router 负责 `Request -> Backend Pod`；默认 ModelServing 可依赖 Volcano，但 chart 不安装 Volcano。
- AgentCube 当前主要拥有 sandbox lifecycle、warm reuse 和 session route，是否引入 node-local fast plane 需要先量化控制面成本。

## 输出与验证

### 社区活动

| 类型 | 数量 | 对象 |
| --- | ---: | --- |
| 本周新开 PR | 0 | 本周以已有 PR 更新、Review 和架构交付为主 |
| 本周 merge 的本人 PR | 1 | Karmada `karmadactl top` E2E fixture #7795 |
| 他人 PR 实质 Review | 3 | AgentCube CodeInterpreter ownership #450、agent-sandbox v0.5.3 #446、Karmada binding update debounce #7810 |
| Issue 深度分析 | 2 | AgentCube Router-PicoD mTLS #444、Karmada multi-component scheduling #7492 |

### 关键测试证据

| 风险 | 证据 | 结论边界 |
| --- | --- | --- |
| child replacement delete | Template / WarmPool causal red/green、完整 WorkloadManager 与 race tests | 证明 precondition 修复；PR #450 仍待维护者 merge |
| v0.5.3 warm lineage | k3d live migration、same-lineage adoption / GC / refill、fork 9/9 workflows | 证明 fork reference；不把它写成 #446 已接受实现 |
| WarmPoolAvailable | unit、race、CodeInterpreter E2E、upstream 13/13 非 Tide、fork 9/9 | 本人更新完成；缺维护者 labels |
| AgentENV / Volcano / Kthena | AgentENV Go tests / k8s render；Volcano 与 Kthena focused Go tests；Helm lint / template | 未运行 KVM、GPU、真实 cluster E2E 或性能 benchmark |

### 失败与处理

| 失败步骤 | 现象 | 根因与处理 |
| --- | --- | --- |
| #446 focused Go replay | 共享主机 load 接近 200、可用内存约 1.3 GiB、linker 长时间不结束 | 主动中止，不计 PASS 或 product failure；只使用已完成 direct tests 和 exact-head CI 支持对应结论 |
| standard kind / KVM runtime | kind kubelet / cgroup 初始化失败；当前用户不能访问 `/dev/kvm` | 使用隔离 k3d 完成 Kubernetes migration；停止宣称 MicroVM / KVM runtime 验证 |
| Kthena `go test ./...` | 4 个 E2E packages 连接 `localhost:8080` 失败 | 本机无 active cluster；排除 E2E 后非 E2E packages 通过，报告明确两种证据边界 |
| Volcano HyperNode E2E | fixed SHA check 失败 | 原因未查明；不把传统 scheduler focused tests 外推为 HyperNode E2E 通过 |

## 证据索引

- [AgentCube Day 55：v0.5.x 多轮 Review 与 migration](day55-pr442-agent-sandbox-v052-new-head-review.md)
- [AgentCube Day 57：Agent AutoHarness](day57-agent-autoharness-trajectory-evaluation.md)
- [AgentCube Day 58：CodeInterpreter child ownership](day58-pr450-codeinterpreter-child-ownership-review.md)
- [AgentCube Day 59：AgentENV Kubernetes boundary](day59-kvcache-ai-agentenv-kubernetes-boundary-study.md)
- [AgentCube Day 60：Volcano / Kthena architecture](day60-volcano-kthena-architecture-and-project-study.md)
- [Karmada PR #7810 binding update Review](https://github.com/ranxi2001/karmada/blob/intern/internship-reports/day41-pr7810-binding-update-coalescing-review.md)
- [Karmada Issue #7492 API design](https://github.com/ranxi2001/karmada/blob/intern/internship-reports/day44-issue7492-component-scheduling-result-api-design.md)
