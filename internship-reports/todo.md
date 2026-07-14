# 实习任务 TODO

更新时间：2026-07-14

这个文档用于管理实习期间的后续任务。日报记录每天做了什么，TODO 记录“现在还要做什么、优先级是什么、做到哪里、卡在哪里”。

## 使用规则

- 状态只保留当前结论：`TODO`、`DOING`、`BLOCKED`、`DONE`。
- 每个任务都要有可检查的产出，例如报告、脚本、benchmark 结果、PR、issue 或代码提交。
- 遇到卡点时要记录失败命令、错误现象、初步原因和临时绕过方式。
- benchmark 任务必须说明测试口径：本机环境、是否包含 LLM、是否包含 Agent、是否只是 sandbox 基础设施链路。
- `难度` 主要指技术不确定性；`成本` 主要看 token / LLM API 消耗，只有机器环境、镜像构建、review 沟通等明显影响任务时才额外备注；`预计时间` 是当前粗估，实际执行后要更新。
- 任务完成后保留在“已完成里程碑”里，方便周报和 mentor 同步。
- 每次新的 Agent 工作循环先读根目录 [PROGRESS.md](../PROGRESS.md)，结束时只更新关键状态：上一轮做了什么、当前卡点、已排除项、下一步、停止条件；不要把它写成长日报。

## 当前优先级

| 优先级 | 任务 | 状态 | PR 认领 @ | 难度 | 成本 | 预计时间 | 产出/证据 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | 准备一个低争议 upstream PR 或 issue | REVIEW | #265 无 assignee；PR #385 | 中 | 低 | 0.5-1 天 | [Day 10](day10-warmpoolavailable-poc.md) 已成功提交 upstream PR [#385](https://github.com/volcano-sh/agentcube/pull/385)，并已按 Codecov 反馈补测试 | 持续追踪 CI、coverage、e2e、tide 和 reviewer 反馈 |
| P0 | 固定开源贡献和社区讨论格式标准 | DONE | 不适用 | 中 | 低 | 0.5 天 | [格式标准](open-source-contribution-format-standard.md) 已整理官方格式、近期样本、reviewer-attention 软阈值和 long-form exception | 后续草稿先报告 visible words/nonblank lines，再按类型保留关键风险证据 |
| P0 | 建立 issue 讨论和 PR 管理本地 skills | DONE | 不适用 | 中 | 低 | 0.5 天 | [issue skill](../.agents/skills/agentcube-issue-discussion/SKILL.md)、[PR skill](../.agents/skills/agentcube-pr-management/SKILL.md) 已补 concise references、`draft_metrics.py` 和 CRD/API 前向测试 | 后续用对应 skill 起草；普通 PR 超 300 words 复查，超 450 words 说明例外 |
| P0 | 建立 maintainer review 历史学习闭环 | DONE | 不适用 | 中高 | 低 | 0.5 天 | [Day 46](day46-rainbowmango-maintainer-review-method-study.md) 已从 AgentCube/Karmada 2020-2026 的 15 个有效 PR 样本提炼 problem premise、scope、ownership/precedent、shared routing、status transition 和 second-round 方法；新增 reviewer history 抽取脚本、2 个单测和 maintainer-calibrated skill reference | 下一次真实 review 前使用 problem card 与 kind/scope/destination matrix；只把新 maintainer correction 或真实漏审升级为 pattern |
| P0 | 建立实习周报邮件私有工作流 | DONE | 不适用 | 中 | 低 | 0.5 天 | 已在 `/home/intern-week-mail` 建立独立 private repository，包含 local-first Git evidence collector、脱敏 Outlook HTML 模板、结构化 renderer、Week 5 数据/证据和最终 HTML；真实身份配置仅在 ignored `.env`，含身份输出只进入该 private repo | 每周从本机仓库/报告生成，PR/Issue/review 状态按需从 GitHub 核对；任何发送动作前确认完整邮件 payload |
| P0 | 建立干净 upstream PR 分支 | DONE | 不适用 | 中 | 低 | 0.5 天 | [Day 10](day10-warmpoolavailable-poc.md) 已在 `/home/agentcube-pr265` 基于 `upstream/main` 创建 `feat/warmpool-available-condition` | fork `intern` 保留实习报告；fork `main` 只同步 `upstream/main`；PR 分支只放 #265 代码改动 |
| P0 | 准备 AgentCube push CI upstream PR | DONE | Upstream PR [#414](https://github.com/volcano-sh/agentcube/pull/414) | 中 | 低 | 0.5 天 | [Day 34](day34-agentcube-push-ci-workflow-pr-prep.md) 已完成 shared workflow 方案、fork push 9/9 验证和 upstream PR；#414 于 2026-07-02 合并 | 后续只观察 push workflow 行为；新 CI 问题另开 focused task |
| P0 | 修复 Release Image CI 的 Helm chart `latest` version 失败 | DONE | Upstream PR [#416](https://github.com/volcano-sh/agentcube/pull/416) | 中 | 中 | 0.5 天 | [Day 38](day38-release-image-ci-helm-chart-version-failure-analysis.md) 已完成 latest image + chart `0.0.0` 方案、fork release validation 和 review 处理；#416 于 2026-07-03 合并 | 仅在出现 immutable development chart 需求时另开 follow-up |
| P0 | 调研并准备 Release Image 多架构构建性能优化 | DONE | Issue [#419](https://github.com/volcano-sh/agentcube/issues/419); PR [#420](https://github.com/volcano-sh/agentcube/pull/420) | 中 | 中 | 0.5-1 天 | [Day 39](day39-karmada-image-build-and-agentcube-buildx-performance-optimization.md) 已完成 baseline/Scheme A benchmark、真实 release run 和原理说明；#420 于 2026-07-07 合并 | #419 中的 prebuild、PicoD runtime layer、matrix/cache 作为独立 follow-up，不扩大已合并 PR |
| P0 | 准备 Dependabot Docker base image updates PR | DONE | #386 task；Upstream PR [#422](https://github.com/volcano-sh/agentcube/pull/422) | 低 | 低 | 0.5 天 | [Day 42](day42-dependabot-alpine-base-image-updates.md) 已验证 Alpine/Ubuntu update 与 `golang` ignore 边界；#422 于 2026-07-07 合并，随后 #424/#425 自动更新已合并 | 观察 Docker Dependabot 噪音和更新质量；Go baseline 继续由 #429 独立治理 |
| P0 | 固定 GitHub Actions runner 到明确 Ubuntu 版本 | DONE | Upstream PR [#423](https://github.com/volcano-sh/agentcube/pull/423) | 低 | 低 | 0.5 天 | [Day 43](day43-go-toolchain-and-github-runner-pinning.md) 已完成 11 个 `ubuntu-latest` 到 `ubuntu-24.04` 的固定并保留 e2e `ubuntu-22.04`；#423 于 2026-07-09 合并 | 后续 runner OS 升级另开 focused PR，不回改既有明确标签 |
| P0 | 提出 Go toolchain 长期治理方案 | REVIEW | #386 umbrella；Upstream PR [#429](https://github.com/volcano-sh/agentcube/pull/429) | 中 | 低 | 0.5 天 | [Day 43](day43-go-toolchain-and-github-runner-pinning.md) 已形成 source-of-truth、alignment verifier、scheduled stable check 和 focused update PR 闭环；#429 已提交 scheduled workflow，普通 checks 通过，tide 等 review/labels | 等待 #429 maintainer review；Day45 已确认这条方向已有 active PR，不再把它作为“新可认领任务”重复提出 |
| P0 | 跟进 `TokenCache` 不检查 JWT `exp` 的问题 | WATCH | @HarshitPal25 | 中 | 低 | 0.5 天 | [Week 2](week2-summary.md) 已列为跟进项；来源 #375 | 已有人认领，先不重复开 PR；跟踪其 PR，必要时做 review / 复现测试 |
| P0 | 对齐 SnapStart / warm pool benchmark 口径 | WATCH | #365 无 assignee；#366/#379 @lyuyun | 中 | 低 | 1 天 | [Day 12](day12-agentcube-roadmap-from-cubesandbox.md) 已整理 #366 实验验证矩阵、补跑 plain Pod / warm pool 本机数据，并在 [#366](https://github.com/volcano-sh/agentcube/pull/366#issuecomment-4714612811) 发布评论；来源 #365/#366/#379 | 重复评论已删除；跟踪维护者是否希望整理 proposal patch / docs PR |
| P0 | 学习 Karmada Kubernetes-native 控制面设计 | DONE | 不适用 | 中 | 低 | 1 天 | [Day 13](day13-karmada-project-study.md) 已完成：项目定位、组件、核心资源链路、Binding/Work 控制器初读、成功原因和 AgentCube 对比 | 后续如继续学习，再单独开 scheduler / status aggregation 深读任务 |
| P0 | 建立更完整 Kubernetes 测试环境 | BLOCKED | 不适用 | 中高 | 低 | 1-2 天 | [Day 14](day14-kubernetes-environment-and-test-plan.md) 已制定 L0/L1/L2/L3 环境分层；KWOK 已跑通 1 个真实节点 + 3 个 fake nodes；Docker `26.1.3` 和 kind `v0.32.0` 已安装，但 kind 标准 K8s 在 kubelet cgroup/QoS 初始化处失败 | 本机继续硬调收益低；下一步换 cgroup v2 / 新内核机器，或使用云厂商标准 K8s / 新 VM 跑 L1；KWOK 仅保留为调度语义环境 |
| P0 | 分析社区 issue / PR 动态 | DOING | 按 issue 逐项记录 | 中 | 中 | 0.5-1 天 | [Day 40](day40-agentcube-latest-community-pr-issue-trends.md) 记录 2026-07-06 社区快照；[Day 45](day45-latest-community-issue-task-screening.md) 按 assignee、active PR、scope、环境和 stale-code 五层筛选 2026-07-10 最新 issues，结论是没有可直接认领的 A 级任务；#348 已由 merged PR #378 修复，#432/#430 等最新项均已有 owner/PR | 不 `/assign` 新 issue；#433 仅作为可选 Helm/auth 验证协作；#272 需先协调 #249 与 release-policy scope；等待新的 focused unowned issue |
| P0 | 跟进 PR #385 review 反馈 | DOING | PR #385；assignee @RainbowMango | 中 | 低 | 0.5 天 | [Day 15](day15-upstream-pr-review-and-snapstart-implementation.md) 已处理 Gemini 关于 `WarmPoolNotFound` warning event 噪音的建议，commit `d885b4e` 已 push；DCO signoff 已修复并通过 | 等待 CI、Codecov、tide、maintainer review；当前 tide 主要等待 `approved` / `lgtm` |
| P0 | 阅读 SnapStart 实现 PR #379 | DOING | PR #379 @lyuyun | 高 | 低 | 1 天 | [Day 15](day15-upstream-pr-review-and-snapstart-implementation.md) 已完成代码范围初读，并找到一个非重复 review 点：promotion 重置 `ReadyAt` 后可能因 `snapshotStatusEqual` 不比较 `ReadyAt` 而没有持久化 | 将 `ReadyAt` status equality 评论发到 #379，或先在本地临时分支补最小 controller unit test 验证 |
| P0 | 讨论 AgentCube v0.2.0 下一步计划 | DONE | #386 无 assignee；`FAUST-BENCHOU` 已提 Sandbox Sleep/Resume | 中 | 低 | 0.5 天 | [Day 15](day15-upstream-pr-review-and-snapstart-implementation.md) 已整理 2026-06-17 会议纪要，明确 agent-sandbox compatibility、Sleep/Resume、E2B-compatible API/SDK/template、SnapStart/MicroVM snapshot/runtime 四层关系 | 后续拆到具体子任务，不再作为单独会议任务跟踪 |
| P0 | 适配 current stable `kubernetes-sigs/agent-sandbox` | REVIEW | #386；PR [#387](https://github.com/volcano-sh/agentcube/pull/387)；Go 前置 PR [#391](https://github.com/volcano-sh/agentcube/pull/391) 已合并 | 高 | 低 | 1-2 天 | [Day 16](day16-agent-sandbox-latest-adaptation.md) 保存 v0.4.6 适配与 runtime 验证；[Day 17](day17-pr387-copilot-review-and-ci-triage.md) 保存 review/CI triage；[Day 19](day19-pr387-code-review-prep.md) 保存 code rationale/test matrix；[Day 30](day30-pr387-warm-pool-dataflow-review.md) 保存 warm-pool adoption、conflict rebase、test-only E2E、runner 复核、reviewer note、最终架构复核和 #433 认证边界观察。PR head `9c3402e` 已对齐 Ubuntu 24.04 与 codegen guidance；official 可执行 checks 全绿，focused v0.4.6 WarmPool/UID cleanup/load 真实 PASS；[Mermaid comment](https://github.com/volcano-sh/agentcube/pull/387#issuecomment-4966669956) 解释双 job 和数据流 | #433 head 仍为 `fe295b6` 旧 credential-delegation 方案，只有 create/delete RBAC；等待其新 push 明确 WM ServiceAccount 模型。#387 不追加认证/RBAC 产品修改，只等待 maintainer `lgtm`/`approved`；无新 head/design decision 时不自动评论或请求 review |
| P0 | 设计 / 实现 Warm Pool Data-Flow Inspector | TODO | #387 follow-up；当前不绑定 upstream PR | 高 | 低 | 0.5-1 天 | [Day 30](day30-pr387-warm-pool-dataflow-review.md) 已提出 white-box 测试工具方案，并手工执行 L1：直接驱动 agent-sandbox `SandboxTemplate/SandboxWarmPool/SandboxClaim/Sandbox/Pod` API，观测 owner/status/UID 流转、claim adoption、warm pool refill 和 cleanup；L2 可选验证 WorkloadManager response / Store adapter，不以 CodeInterpreter stdout 为通过条件 | 如果 reviewer 继续追问或要可复现工具，再在 fork/local 写 `test/tools/warmpool-flow-inspector`，使用 dynamic client + watch-first 输出 JSON timeline + Mermaid；先不把工具塞进 #387 |
| P0 | 前沿适配测试 `agent-sandbox v0.5.x` / `v1beta1` | DOING | #386；后续独立 follow-up，当前不绑定 upstream PR | 高 | 低 | 1-2 天 | [Day 18](day18-agent-sandbox-v05-forward-adaptation.md) 已完成 `v0.5.0rc1` 最小编译适配、clean runtime 验证和 fork CI 验证；fork PR [#5](https://github.com/ranxi2001/agentcube/pull/5) 已 rebase 到最新 #387 head `c2633c5`，当前 head `3abdb94`，本地 rebase 后 build/lint/unit/gen-check 全通过，fork CI 10/10 全绿；第一次 CI e2e 失败溯源为 e2e setup 仍安装旧 agent-sandbox manifest，集群无 v1beta1 CRD，已在 v0.5 分支对齐 `AGENT_SANDBOX_VERSION=v0.5.0rc1`；隔离 k3d + rc1 manifest 下 direct/warm-pool e2e、留存式 v1beta1 字段检查、delete cleanup、SDK、LangChain、MCP HTTP/stdio、math-agent LLM e2e 均通过；[Day 41](day41-agent-sandbox-v050-release-and-agentcube-adaptation.md) 已确认正式 `v0.5.0` 于 2026-06-24 发布，且正式版保留 `v1alpha1` / `v1beta1` 多版本包和 conversion webhook。正式 `v0.5.0` adapter 分支 `feat/agent-sandbox-runtime-adapter-v05` 当前 head `726a984`，已新增 `pkg/workloadmanager/agentsandbox` 适配层、SandboxClaim ready watcher、v0.5 E2E 默认版本和 warm-pool owner 链测试修正；本地静态验证、Ubuntu 24 + kind clean runtime、默认 mTLS AgentRuntime 路径、非 mTLS direct CodeInterpreter / warm-pool adoption 目标测试均通过 | 正式 release 已发布，fork-only runtime validation 已完成。下一步不是直接扩大 #387，而是准备是否提 clean upstream PR 的范围判断：说明 clean-install 证据、旧 CRD storedVersions migration 未覆盖、conversion webhook、migration guide、NetworkPolicy namespace、#277/#413 边界，以及是否暂不处理 `code-generator@v0.34.1` 与 k8s `v0.35.4` 对齐 |
| P0 | 设计 AgentCube Sleep/Resume 生命周期 | DOING | #386；FAUST-BENCHOU 已提出方案，未正式 assign | 高 | 低 | 1-2 天 | [Day 24](day24-sandbox-sleep-resume-design-note.md) 已完成设计先行版本、本地 spike、第一阶段 Store 状态/CAS、第二阶段 WorkloadManager lifecycle service，并在 2026-06-24 基于当前 `main` 源码补充 Stage 3 Router / GC 行为表、代码落点、last-activity 语义、explicit delete 策略和测试矩阵；结论是不等待 agent-sandbox 全部定稿，但也不重复实现底层 pause；AgentCube 先定义 session lifecycle contract、Store CAS/状态、Router resume-before-proxy、GC split 和 RuntimeProvider capability；已核对 agent-sandbox [#36](https://github.com/kubernetes-sigs/agent-sandbox/issues/36) / [#103](https://github.com/kubernetes-sigs/agent-sandbox/issues/103)；`/home/agentcube-sleep-resume-store-state` branch `feat/sleep-resume-store-state` 已有两层 commit：`3d0427a` Store 状态/CAS，`cb66c8a` WorkloadManager pause/resume service + fake provider tests；[Day 25](day25-sleep-resume-code-review-and-architecture-retrospective.md) 已按 reviewer 视角复盘这两层实现，形成 code review matrix、风险分级、测试矩阵和第三阶段 gate | 见下方 Stage 3 子任务拆解；暂不发 upstream，不抢 FAUST-BENCHOU 可能接手的实现；#387 合并前优先做设计、fake-provider validation、review/test plan |
| P0 | 系统化整理 Agent Infra 职业能力地图与实习目标管理 | DONE | 不适用 | 中 | 低 | 0.5 天 | [Day 27](day27-agent-infra-career-roadmap-and-internship-goals.md) 已把 Agent Infra 拆成 runtime、Kubernetes control plane、session lifecycle、tool protocol、Router/API、安全、observability/eval、开源 review 八条能力线，并映射到当前 AgentCube 实习证据和后续 4 周目标 | 后续周总结按 Day27 的能力闭环写：问题定义、证据、设计判断、测试、review 材料、skill 沉淀 |
| P0 | 深入吃透 Agent Substrate 架构并提炼 AgentCube 差异化方向 | DONE | 不适用 | 中高 | 低 | 0.5 天 | [Day 28](day28-agent-substrate-architecture-and-agentcube-differentiation.md) 已基于 drawio 架构图、explainer、Day21/22 和 `/tmp/agent-substrate` 源码，拆解控制面、状态面、数据面、runtime 面，并提出 AgentCube 两个方向：MultiAgent Worker Pod / AgentSlot multiplexing、RuntimeProvider / provider abstraction；2026-06-26 已重新 clone 复核 `/tmp/agent-substrate` @ `4bbd39f322c6`，确认原判断仍成立，同时补充 micro-VM sandboxClass、SandboxConfig、Claude Code multiplex 语义和 gVisor/rootfs caveat | 后续可继续画 AgentCube future architecture drawio，或另画 Agent Substrate micro-VM runtime path；暂不发 upstream |
| P0 | 收敛 AgentCube 三期架构迭代方案 | DONE | 不适用 | 高 | 低 | 0.5 天 | [Day 35](day35-agentcube-architecture-iteration-conclusion.md) 已把新架构图、docs/design 中的 K8s CRD 资源池参考设计、Substrate 差异化、E2B 兼容边界和四大技术支柱收束成会议结论分析；详细 CRD 设计见 [docs/design/k8s-crd-sandbox-resource-pool-lifecycle-control-design.md](../docs/design/k8s-crd-sandbox-resource-pool-lifecycle-control-design.md) | 后续如要推进 upstream，先拆成 design proposal、RuntimeProvider / node-ctl contract、CRD skeleton、placeholder spike、benchmark suite，不开大而全 PR |
| P0 | 深入设计 K8s 慢资源控制面与资源池 CRD 分工 | DONE | 不适用 | 高 | 低 | 0.5 天 | [Day 36](day36-k8s-slow-resource-control-plane-design.md) 已按当前项目分工把 node-ctl / sandbox-ctl 快路径排除出本轮范围，重点展开 K8s 生态内慢资源控制面：快慢双轨体系、`SandboxPoolTemplate` 全局策略 CRD、`SandboxPool` 节点实例 CRD、Template Controller / Pool Controller 职责边界、reconcile 流程、状态机、故障恢复和落地切片，并用 Mermaid 图辅助理解 | 后续可把 Day36 压缩成 API 字段表、controller test plan 和 CRD skeleton proposal；先用 fake node-ctl 验证，不直接做大而全实现 |
| P0 | 跟进 SandboxPool 管理正式 proposal #431 | REVIEW | PR [#431](https://github.com/volcano-sh/agentcube/pull/431) 无 assignee；关联 issue [#430](https://github.com/volcano-sh/agentcube/issues/430) | 高 | 低 | 0.5-1 天 | [Day 44 主报告](day44-sandbox-pool-management-proposal-review.md) 与[Batch Review Payload](day44-sandboxpool-pr431-comment-drafts.md#2026-07-13-batch-review-payload) 已同步 force-push head `3d1bd0d`；[review `4681333180`](https://github.com/volcano-sh/agentcube/pull/431#pullrequestreview-4681333180) 已批量发布 4 个未重复问题，覆盖 Task lifecycle、heartbeat timer、orphan cleanup 和 atomic Class ownership | 当前 `POSTED_WAITING`；等待作者逐 thread 回复或更新 proposal，不自动追加评论；有回复后分别判断 resolved、窄追问或 Phase 2 spike/e2e gate |
| P0 | 设计 docs/proposals 提案管理入口 | DONE | PR #415 | 中 | 低 | 0.5 天 | [Day 37](day37-docs-proposal-directory-management.md) 已调研 AgentCube 历史提案存放方式和 Karmada `docs/proposals` 结构；基于 `upstream/main f9c37d5` 创建分支 `docs/proposals-management`，commit `8e8c455` 新增 `docs/proposals/README.md`、`docs/proposals/proposal-template.md` 并更新 `CONTRIBUTING.md`；按用户反馈，README 不维护新增 proposal 全量索引，只索引遗留 `docs/design` 旧提案；新 proposal 使用 `docs/proposals/<proposal-name>/README.md` 统一目录式布局，optional 字段已显式标注；已按 Gemini 评论补齐 README 清单中的 `risks and mitigations` | 已创建 upstream PR [#415](https://github.com/volcano-sh/agentcube/pull/415)；push 后 CI 重新运行，后续等待 maintainer review、`/lgtm`、`/approve`，不要自动 push/comment |
| P0 | 删除未使用的 `agentd` 组件 | DONE | upstream PR [#403](https://github.com/volcano-sh/agentcube/pull/403) | 中 | 低 | 0.5 天 | [Day 29](day29-agentd-component-role-analysis.md) 已记录组件职责、mentor 确认、Dockerfile scope、测试和 review；#403 于 2026-07-01 合并 | Agent-side lifecycle 后续以 PicoD/RuntimeProvider 真实边界为准，不恢复已删除 agentd |
| P0 | Review PR #400 PicoD Prometheus metrics | REVIEW | PR [#400](https://github.com/volcano-sh/agentcube/pull/400) 无 assignee | 中 | 低 | 0.5 天 | [Day 31](day31-picod-prometheus-metrics-review.md) 已完成本地 review：`go test ./pkg/picod -count=1`、`go test -race ./pkg/picod -count=1`、`TestMetrics_Exposition -count=20` 通过；临时测试证明 `maxBodySizeMiddleware` 早于 metrics middleware 会导致 `413` 请求不进入 `picod_http_requests_total`；同时记录 `active_executions` 指标语义和 scrape scope 限制 | 若用户确认参与 #400 review，可发送 Day31 中压缩后的英文 comment；否则继续做本地 review，不抢作者实现 |
| P0 | 项目二次梳理学习 | DONE | 不适用 | 中 | 低 | 0.5 天 | [Day 20](day20-agent-sandbox-v02-v03-v05-wip-pr-implementations-and-project-study.md) 已完成：按 Router、WorkloadManager、Store、PicoD、agent-sandbox、codegen、auth、测试分层重新梳理当前 main 的真实实现；并补充 `agent-sandbox v0.2.1` / `v0.3.10` / `v0.5.0rc1` 三段 WIP PR / validation PR 实现记录，形成从 dependency-only 到 warm-pool adoption / codegen drift / v1beta1 API migration 的演进证据；fork-only 归档/验证 PR [#6](https://github.com/ranxi2001/agentcube/pull/6) / [#7](https://github.com/ranxi2001/agentcube/pull/7) / [#5](https://github.com/ranxi2001/agentcube/pull/5) 均已通过 fork CI | 后续改代码前按 Day20 的阅读顺序和测试矩阵定位影响面；#387 review 可引用 Day20 的 0.2/0.3/0.4/0.5 对比 |
| P0 | 补 Agent 端到端 benchmark | TODO | 不适用 | 中 | 中 | 1-2 天 | 已有 shortest path 单次结果和 sandbox benchmark | 重复测试 LLM + Agent planning + tool call + AgentCube sandbox 的完整链路 |
| P0 | 补多轮 p50/p95/p99 benchmark | DOING | 不适用 | 中 | 低 | 0.5-1 天 | 已有 AgentCube sandbox p50/p95 和 warmPoolSize 曲线 | 增加 p99；统一输出格式；补 Agent/math-agent 多轮统计 |
| P0 | 补冷启动 vs warm pool 对比 | TODO | 不适用 | 中 | 低 | 0.5 天 | 已测 warmPoolSize=2/5/10/20 | 增加 `warmPoolSize=0` 或无 warm pool 场景 |
| P0 | 补并发 5/10/20 sandbox 测试 | DOING | 不适用 | 中 | 中 | 0.5-1 天 | 已测 concurrent=10，warmPoolSize=2/5/10/20 | 增加 concurrent=5 和 concurrent=20；记录失败率和资源压力 |
| P1 | 检查 sandbox 删除后的资源残留 | TODO | 不适用 | 中 | 低 | 0.5 天 | 部分测试后人工恢复过 warm pool 和 port-forward | 固化检查项：Pod、Sandbox CR、SandboxWarmPool、Redis 状态 |
| P1 | 验证 `math-agent` session 自动清理 | TODO | 待查 | 中 | 低 | 0.5-1 天 | 第一周计划中已标记风险 | 检查 `CodeInterpreterClient().stop()` 或等价清理逻辑，并做回归验证 |
| P1 | 构建数学 benchmark 专用镜像 | TODO | 不适用 | 中 | 中 | 1-2 天 | 高考数学测试已暴露 `sympy/numpy/scipy/pandas` 依赖问题 | 构建包含常用数学库的 sandbox 镜像，并复测高考数学题 |
| P1 | 拆分 Workload Manager 内部阶段耗时 | TODO | 不适用 | 高 | 中 | 1-2 天 | 当前只记录 create/run/delete 总耗时 | 拆 API 接收、SandboxClaim、调度、Pod Ready、Router 更新、Redis 写入 |
| P1 | 形成官方 benchmark suite 草案 | TODO | 待查 | 中 | 低 | 1 天 | 已有多个本地 benchmark 脚本和结果 | 整理脚本接口、环境记录、输出 JSON schema 和 README |
| P1 | 评估 `WarmPoolAvailable` 状态 PoC | REVIEW | #265 无 assignee；PR #385 | 中高 | 低 | 1-2 天 | [Day 10](day10-warmpoolavailable-poc.md) 已完成 PoC 并提交 upstream PR [#385](https://github.com/volcano-sh/agentcube/pull/385)；focused tests 通过；已补 coverage 边界测试 | 跟进 CI 和 reviewer 对 condition/event 语义的反馈 |
| P2 | 深读 `agentd`、`picod`、`router` 链路 | DONE | 不适用 | 中 | 低 | 1 天 | [Day 20](day20-agent-sandbox-v02-v03-v05-wip-pr-implementations-and-project-study.md) 已补 session 到 Router reverse proxy、PicoD JWT/execute、AgentD delete-on-idle 的代码级笔记 | 后续如改具体模块，再按 Day20 的模块 checklist 做专项测试 |
| P2 | 梳理 CRD / DeepCopy / client-go 生成链路 | DONE | 不适用 | 中 | 低 | 0.5 天 | [Day 19](day19-pr387-code-review-prep.md) 和 [Day 20](day20-agent-sandbox-v02-v03-v05-wip-pr-implementations-and-project-study.md) 已解释 `make gen-all`、`make gen-check`、CRD YAML、DeepCopy、client-go/informer/lister/fake client 的作用 | 后续 API 字段改动必须跑 `make gen-check` 并解释 generated diff |
| P2 | 跑通 `browser-agent` 或 `pcap-analyzer` demo | BLOCKED | 不适用 | 高 | 中 | 1-2 天 | 第一周记录过 Docker/镜像环境限制 | 等待可用镜像构建路径或 containerd/registry 方案 |
| P2 | 在 KVM 机器上复测 forkd | BLOCKED | 不适用 | 高 | 高 | 1 天 | [Day 6](day6-forkd-competitor-benchmark-precheck.md) 已记录当前 CentOS 8 阻塞 | 换有 `/dev/kvm`、vmx/svm、合适 kernel/glibc 的机器 |
| P2 | 在 KVM 机器上预检/复测 CubeSandbox | BLOCKED | 不适用 | 高 | 高 | 1-2 天 | [Day 8](day8-sandbox-competitor-capability-matrix.md) 已记录环境要求 | 换支持 KVM 或可切 PVM kernel 的机器 |
| P2 | 在 kernel >=5.13 机器上复测 cage-bro Landlock | BLOCKED | 不适用 | 中 | 中 | 0.5-1 天 | [Day 7](day7-cage-bro-competitor-benchmark.md) 已记录当前 kernel 4.18 不支持 Landlock | 换新 kernel Linux 环境，补安全隔离表现 |

## Sleep/Resume Stage 3 子任务拆解

当前状态：

- #386 是 v0.2.0 umbrella issue，暂无正式 assignee。
- FAUST-BENCHOU 已提出 Sandbox Sleep/Resume proposal，并表示如果被接受愿意接手。
- #387 仍 open，是 `agent-sandbox v0.4.6` compatibility 前置工作；Sleep/Resume 不应混入 #387。
- 我们当前更适合做设计、代码审查、测试设计、fake-provider validation 和 benchmark，不应默认抢完整实现。

> 注释：这里的“适合我们做”不是只看能不能写代码，而是看是否符合开源协作边界。已经有人表达愿意接手的功能，优先提供设计证据、测试矩阵和 review feedback；如果维护者或实现者需要帮助，再按小任务进入代码。

| 编号 | 子任务 | 状态 | 适合我们做吗 | 是否等 #387 合并 | 是否会和 FAUST-BENCHOU 冲突 | 需要的测试 | 产出类型 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3A | Store / GC split：把 idle `Ready` 从 delete 改成 pause candidate；`Paused` 超过 `pauseTimeout` 后 delete；`maxSessionDuration` 对所有 active 状态优先 delete | DONE | 已完成设计、源码基线、fake-lifecycle 单测骨架和 review checklist；真实代码实现仍需等维护者分工 | 正式 upstream 代码建议等 #387 合并；本地 spike 不必等 | 中等风险：这是核心实现路径，若 FAUST-BENCHOU 接手，我们应提供 review/test matrix，不直接抢 PR | unit：`ready` idle -> pause、不 delete；`paused` 未过期 keep；`paused` 过期 delete；max TTL 覆盖 ready/paused/resuming/failed；unknown status 不 destructive delete；Store CAS / pause expiry index | Day24 已补 3A 完成记录；可作为后续 review/test matrix | 若继续写代码，只在 fork/local spike 做；正式 upstream 等 #387 合并和 #386 分工明确 |
| 3B | Router resume-before-proxy：Router 看到 `Paused` session 时，在 owner check 后调用 WorkloadManager resume，再重新读 Store 使用新 entrypoint proxy | TODO | 很适合我们做设计、review 和 handler test；代码实现需谨慎 | 依赖 Store status 和 WorkloadManager resume API；正式代码建议等 3A/3C 基础稳定，不一定等真实 provider | 中等风险：如果 FAUST-BENCHOU 实现主流程，我们可专注 Router 安全顺序和测试 | unit：ready 直接 proxy；paused owner mismatch 不 resume；paused resume success 后 reload Store；resuming 返回 `409 + Retry-After`；resume failure 不更新 last activity；failed 不 proxy | 设计 + handler tests + review feedback | 先整理 `handleInvoke -> checkSandboxOwnership -> ensureSandboxReadyForProxy` 的最小代码草图和测试矩阵 |
| 3C | WorkloadManager resume API：新增内部 `POST /v1/sessions/{sessionId}/resume`，包装 lifecycle service，映射 state conflict / unsupported / timeout / provider failure | TODO | 适合做 API contract 和 fake provider tests；实现前需和社区确认是否内部 API 或 SDK API | 可本地设计；正式 upstream 最好等 #387 合并并确认 Sleep/Resume 子 issue | 低到中：如果只做 API contract 和错误映射，不抢主实现；直接提 PR 可能冲突 | unit：already ready idempotent；paused -> ready；CAS conflict -> 409；unsupported provider；provider timeout -> 504；refresh entrypoints；owner/auth 语义 | 设计 + API contract + unit tests | 先把 Day24 草案转成中文/英文 API contract；暂不发社区，等维护者分工明确 |
| 3D | agent-sandbox hard-pause provider：`v0.4.6` 用 `Sandbox.spec.replicas=0/1`；未来 `v0.5.x` 用 `OperatingMode=Suspended/Running` | TODO | 适合做 provider capability audit、版本差异文档、fork-only runtime validation；不宜现在抢 upstream 实现 | 真实 provider 强依赖 #387 合并；`v0.5.x` 等正式 release 或维护者要求 | 高风险：这是底层实现，容易和 FAUST-BENCHOU 或 agent-sandbox upstream 方向冲突 | unit：provider patch 构造、Ready/Suspended condition 解析、unsupported version；e2e：direct Sandbox pause/resume、Pod IP 变化、workspace retention、cleanup；warm-pool 先标 unsupported/skip | 版本矩阵 + fork validation + benchmark；后续可转 provider PR | 先保持在 Day18/Day24 文档，不发 upstream；等 #387 合并和 Sleep/Resume 分工确认 |
| 3E | e2e / math-agent validation：验证 direct CodeInterpreter hard pause/resume、workspace、endpoint refresh、delete cleanup、math-agent 同 session 继续执行 | TODO | 非常适合我们做，且不容易和实现者冲突；测试/benchmark 是高价值贡献 | 可以先设计；真实 e2e 需要 3A-3D 最小实现后再跑 | 低风险：测试计划和验证结果通常是协作增强，不抢实现 | e2e：create session、写 `/workspace`、触发 pause、同 session resume、文件保留、session id 不变、delete cleanup；math-agent：LLM tool call pause/resume 后继续；benchmark：cold/warm/pause-resume p50/p95/p99 | test plan + benchmark schema + raw logs + review evidence | 今天先把测试计划纳入 TODO；后续等最小实现后运行 fork CI / k3s e2e |

推荐今天之后的执行顺序：

1. 不开 upstream PR，不发社区评论。
2. 先把 3A / 3B 的 test skeleton 在本地设计清楚，继续写在 Day24 或 Day25。
3. 如果要写代码，只做 fork/local spike，验证 Store/GC/Router 单元语义。
4. #387 合并或维护者明确 Sleep/Resume 分工后，再决定是否切出官方 PR。
5. 任何 upstream-facing proposal / comment / PR body 先给用户确认全文。

## 本周收尾建议

1. 先选一个 P0 文档类 PR/issue，完成一次完整开源贡献流程。
2. 把已有 benchmark 脚本整理成统一入口，补 p99、环境信息和结果说明。
3. 补 Agent 端到端多轮测试，明确和 sandbox 基础设施测试的差异。
4. 补 warmPoolSize=0、concurrent=5/20、资源残留检查，形成更完整的性能结论。

## 已完成里程碑

| 事项 | 产出 |
| --- | --- |
| 跑通 AgentCube Getting Started | [Day 1](day1-getting-started.md) |
| 梳理项目结构和技术栈 | [Day 2](day2-implementation-tech-stack.md) |
| 跑通真实 Agent 工作流和最短路径 benchmark | [Day 3](day3-real-agent-workflow.md) |
| 设计并执行高考数学 benchmark 初步测试 | [Day 4](day4-gaokao-math-benchmark-plan.md) |
| 完成 AgentCube sandbox 延迟测试和初步竞品分析 | [Day 5](day5-sandbox-latency-and-competitor-analysis.md) |
| 完成 forkd 当前机器预检并确认阻塞原因 | [Day 6](day6-forkd-competitor-benchmark-precheck.md) |
| 源码构建 cage-bro 并完成基础延迟对比 | [Day 7](day7-cage-bro-competitor-benchmark.md) |
| 建立 sandbox 竞品隔离能力、兼容性和部署难度矩阵 | [Day 8](day8-sandbox-competitor-capability-matrix.md) |
| 补充 OpenSandbox / Agent Substrate 云厂商开源项目调研 | [Day 21](day21-opensandbox-agent-substrate-study.md) |
| 拆解 OpenSandbox / Agent Substrate 实测 runbook | [Day 22](day22-opensandbox-agent-substrate-runtime-runbook.md) |
| 完成 AgentCube 未来发展方向与架构设计探讨 | [Day 23](day23-agentcube-future-architecture-and-design.md)；`design.md` 已在 2026-06-26 结合 Day28 Substrate 源码复核重写为 Substrate-informed 架构设计，突出 Session lifecycle、Store CAS、Router resume-before-proxy、RuntimeProvider、preservation level 和 AgentSlot 差异化 |
| 完成 Sandbox Sleep/Resume 设计先行稿 | [Day 24](day24-sandbox-sleep-resume-design-note.md) |
| 完成 Sleep/Resume 本地状态机 spike | [Day 24](day24-sandbox-sleep-resume-design-note.md) 已记录 `/home/agentcube-sleep-resume-spike` 的 fake provider / Store CAS / GC decision 测试结果 |
| 完成 Sleep/Resume 第一阶段 Store 状态/CAS | [Day 24](day24-sandbox-sleep-resume-design-note.md) 已记录 `/home/agentcube-sleep-resume-store-state` 的 `feat/sleep-resume-store-state` 实现和测试结果 |
| 完成 Sleep/Resume 第二阶段 WorkloadManager lifecycle service | [Day 24](day24-sandbox-sleep-resume-design-note.md) 已记录 `cb66c8a` 的 pause/resume service、RuntimeProvider 边界、fake provider 测试和验证结果 |
| 完成 Sleep/Resume 阶段性代码审查与架构复盘 | [Day 25](day25-sleep-resume-code-review-and-architecture-retrospective.md) 已记录 Store/CAS 与 WorkloadManager lifecycle 的 review matrix、测试矩阵、架构边界和第三阶段 gate |
| 完成 Week 3 社区最新讨论与双层架构问题面总结 | [Day 26](day26-week3-community-latest-and-two-layer-architecture-bug-surface.md) 已把 #401/#397/#394/#395/#392/#388 最新 issue 信号和 Day22-25 的实测/设计/review 汇总成上层 session/API contract 与下层 runtime/provider substrate 两层问题面 |
| 完成 Agent Infra 职业能力地图与实习目标管理 | [Day 27](day27-agent-infra-career-roadmap-and-internship-goals.md) 已把 Agent Infra 拆成技术分层、岗位方向、能力等级、当前短板、后续 4 周目标和每周看板 |
| 完成 Agent Substrate 架构吃透与 AgentCube 差异化设计方向 | [Day 28](day28-agent-substrate-architecture-and-agentcube-differentiation.md) 已把 counter drawio / explainer / Substrate 源码证据转成 AgentCube future design 判断；2026-06-26 已按最新源码 `4bbd39f322c6` 复核，图和 explainer 已明确限定为 gVisor counter 路径，并补 micro-VM runtime 变体 caveat |
| 完成 Substrate 竞品分析、缺陷升级与 AgentCube 开源 PRD | [Day 32](day32-substrate-competitive-analysis-and-agentcube-prd.md) 已综合 Day28、`design.md` 和 AgentCube 会话运行时架构拆解，形成竞品分析、缺陷升级、Session Runtime Control Plane PRD、功能/非功能需求、验收指标、路线图和开源打法；Day35 后已在文末追加新版 PRD 修订，明确 Day32 调整为历史版 / v1 设计，当前主线改为高并发 Agent 沙箱加速平台 |
| 完成 E2B 协议面与“Agent 时代 Docker”调研 | [Day 33](day33-e2b-protocol-and-agent-era-docker-study.md) 已把 E2B 拆成 SDK、REST lifecycle、envd process/filesystem RPC、template/snapshot/network/volume 产品面，并形成 AgentCube E2B facade / conformance test 后续方向 |
| 完成 AgentCube push CI 工作流方案与 PR 准备 | [Day 34](day34-agentcube-push-ci-workflow-pr-prep.md) 已形成 Karmada-style shared workflow 方案、clean branch diff、9/11 checks 解释、fork push validation 证据和英文 upstream PR 草稿 |
| 完成 AgentCube 三期架构迭代结论分析 | [Day 35](day35-agentcube-architecture-iteration-conclusion.md) 已把快慢资源分离、占位 Pod、node-ctl / sandbox-ctl、microVM、run-builder、L1/L2/L3 缓存、E2B-compatible facade 边界和风险拆分路线整理成会议结论；架构图已按 Day35 命名，外部 CRD 参考设计已放入 `docs/design/` |
| 完成 K8s 慢资源控制面与资源池 CRD 深入设计 | [Day 36](day36-k8s-slow-resource-control-plane-design.md) 已把当前项目分工、快慢资源双轨体系、`SandboxPoolTemplate` / `SandboxPool` CRD 关系、Template Controller / Pool Controller 职责、创建 / 更新 / override / 故障恢复流程和状态机用 Mermaid 系统化整理 |
| 完成 docs/proposals 提案目录管理调研与分支准备 | [Day 37](day37-docs-proposal-directory-management.md) 已调研 Karmada proposal 目录和 AgentCube 历史设计存放方式，并在 fork 分支 `docs/proposals-management` 准备 `docs/proposals/README.md`、proposal template 和 CONTRIBUTING 更新；README 只标注 legacy `docs/design` 旧提案，不维护未来新增 proposal 索引 |
| 完成 Release Image CI 的 Helm chart version 失败分析 | [Day 38](day38-release-image-ci-helm-chart-version-failure-analysis.md) 已确认 `Build and Push Release Images` 在 main push 场景下把 `TAG=latest` 同时用于 Docker image tag 和 Helm chart version，导致 `helm package --version latest` 必然失败；报告已区分 #415/#414 与既有 release workflow bug，并在 reviewer 反馈后重新收敛为保留 latest image 发布、chart version 使用固定 SemVer `0.0.0` 的方案 |
| 完成 Karmada image build 与 AgentCube buildx 性能优化调研 | [Day 39](day39-karmada-image-build-and-agentcube-buildx-performance-optimization.md) 已分析 Karmada `dockerhub-latest-image.yml`、Makefile、`hack/build.sh`、`hack/docker.sh` 和 `buildx.Dockerfile`，明确 Karmada 用宿主 Go 交叉编译 + runtime-only buildx 组装镜像，AgentCube 可先用 `FROM --platform=$BUILDPLATFORM` 作为小 PR 避免 QEMU arm64 Go 编译；Scheme A 本地 buildx smoke 已完成并归档日志，三镜像成功，PicoD runtime 层另有 QEMU Python 安装瓶颈；真实 Scheme A 分支已按 PR 标准 DCO commit 并推到 fork |
| 完成 Day40 AgentCube 最新社区 PR / Issue 动态观察 | [Day 40](day40-agentcube-latest-community-pr-issue-trends.md) 已按 issue discussion skill 扫描 2026-07-06 最新 PR / issue，整理 #421/#420/#419/#405/#400 等重点线程，确认 #420 实际 checks 全过但 tide 等 `lgtm` / `approved`，并把后续可选参与点收敛到 #400 验证型 review 与 #405 docs 实现一致性 review |
| 完成 Day41 agent-sandbox v0.5.0 正式发布后的 AgentCube 适配分析 | [Day 41](day41-agent-sandbox-v050-release-and-agentcube-adaptation.md) 已确认 `agent-sandbox v0.5.0` 正式 release、模块元数据、破坏性 API 变化、migration guide、#277/#413 边界，并在临时 worktree 上验证最小依赖 bump 的第一处失败和临时修复后的非 e2e Go 测试结果 |
| 完成 agent-sandbox v0.5.0 adapter 分支实现 | [Day 41](day41-agent-sandbox-v050-release-and-agentcube-adaptation.md) 已在 `feat/agent-sandbox-runtime-adapter-v05` 增加 `pkg/workloadmanager/agentsandbox` 适配层和 SandboxClaim ready watcher，commit `726a984` 已推到 fork；本地测试、lint、build、gen-check 通过；Ubuntu 24 + kind 下 `agent-sandbox v0.5.0` clean runtime、默认 mTLS AgentRuntime 路径、非 mTLS direct CodeInterpreter / warm-pool adoption 目标测试均通过；fork push CI 对 `726a98444dd7eaab09468cf74b87d74e1756f9a0` 的 9 个 workflow 全部 success，原始证据在 `benchmarks/day41-agent-sandbox-v05-runtime/`；旧 CRD storedVersions migration 仍待验证 |
| 完成 Day42 Dependabot Docker base image updates PR 准备 | [Day 42](day42-dependabot-alpine-base-image-updates.md) 已确认 #386 新增 Alpine base image automation task、Karmada 参考配置、Dependabot Docker updater 对 `Dockerfile.router` / `Dockerfile.picod` 的文件名匹配行为，并在 clean branch `chore/dependabot-docker-base-images` 形成 DCO commit `1084c7f`；fork branch 已推送，#386 `/help` 已回复且 RainbowMango 确认 scope looks good，fork-only Dependabot validation 已生成 #17 Alpine 和 #18 Ubuntu Docker update PR；PR body 草稿已准备，等待用户确认后创建 upstream PR |
| 完成 Day43 Go toolchain 与 GitHub runner pinning 判断 | [Day 43](day43-go-toolchain-and-github-runner-pinning.md) 已把 `golang` builder image 从 Docker runtime base image updater 中拆出，明确 Go baseline 升级应独立处理；runner pinning PR #423 已创建且普通 CI 全绿；Go toolchain 长期方案已形成 source-of-truth、verifier、scheduled check 和 focused PR 四层闭环 |
| 完成 Day44 SandboxPool proposal review 方法论整理 | [Day 44](day44-sandbox-pool-management-proposal-review.md) 已跟进正式 proposal #431、拆解 #430 到 #431 的设计边界、整理可 review 的 scope / API / Static Pod / stale heartbeat / source-of-truth 问题，并把通用 CNCF-style proposal review checklist 与 #28/#29/#37/#38/#44/#80/#114/#164/#241 等早期 proposal/issue battle 一起沉淀到 issue-discussion skill |
| 完成 Day45 最新社区 Issue 可接手任务筛选 | [Day 45](day45-latest-community-issue-task-screening.md) 已扫描 2026-07-10 open issues / PRs，逐项交叉 assignee、`/assign`、active PR、环境和当前源码；确认最近没有可直接认领的 A 级任务，#348 是已由 PR #378 修复的 stale issue，#433 只适合协作验证，#272 需先协调 release-policy scope |
| 完成 Day46 maintainer review 方法研究 | [Day 46](day46-rainbowmango-maintainer-review-method-study.md) 已对 `@RainbowMango` 在 AgentCube/Karmada 的 15 个有效 PR review 样本做跨年度分析，排除 author/self-review 与 approval-only 噪音，并把 problem-first、existing ownership、shared helper routing、meaningful status transition、second-round review 固化进 AgentCube review skill |
| 完成实习周报邮件私有工作流与 Week 5 验收 | `/home/intern-week-mail` 已成为唯一 skill/template/report-source 仓库；skill validation、author-date Git filtering、HTML escaping、隐私扫描和五段表格结构检查均通过；Week 5 HTML 仅版本化到 private repo 的 `output/week5/`，未发送 |
| 完成 PR #387 warm pool adoption 数据流 review | [Day 30](day30-pr387-warm-pool-dataflow-review.md) 已从运行时对象流、claim status 观测、Pod 查找、Store/Router 语义和 delete/GC identity 拆解 #387，不再停留在 API import / interface 适配层面 |
| 完成 PR #400 PicoD Prometheus metrics 本地 review | [Day 31](day31-picod-prometheus-metrics-review.md) 已验证 PicoD metrics PR 的测试状态、middleware 顺序缺口、指标语义问题和可选 upstream review 草稿 |
| 完成独立 AgentCube PR Review skill 与 #387 前向验证 | [Day 30](day30-pr387-warm-pool-dataflow-review.md) 已建立 point-line-surface/组件职责/类型指针/冲突语义/测试真实性 review workflow；fork run `29304884501` 证明 v0.4.6 安装但目标用例被 mTLS skip，run `29306285285` 在 focused non-mTLS 模式实际跑通 WarmPool claim-adoption、SDK、LangChain 和 MCP |
| 完成 Week 3 总结：从功能适配转向 Session Runtime Control Plane | [Week 3](week3-summary.md) 已把 Day24-Day32 的 Sleep/Resume 设计、Substrate 竞品复核、AgentCube 架构图、#387/#400/#403 review、开源流程修正和下周建议收束成能力复盘 |

## 卡点记录模板

```text
任务：
日期：
环境：
失败命令/步骤：
错误现象：
初步原因：
已尝试方案：
临时绕过方式：
后续需要：
```
