# 实习任务 TODO

更新时间：2026-06-23

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
| P0 | 固定开源贡献和社区讨论格式标准 | DONE | 不适用 | 中 | 低 | 0.5 天 | [格式标准](open-source-contribution-format-standard.md) 已整理官方 issue / PR / proposal / benchmark / review 格式 | 后续 issue、proposal、PR 前按 checklist 检查 |
| P0 | 建立 issue 讨论和 PR 管理本地 skills | DONE | 不适用 | 中 | 低 | 0.5 天 | [issue skill](../.agents/skills/agentcube-issue-discussion/SKILL.md)、[PR skill](../.agents/skills/agentcube-pr-management/SKILL.md) 已创建 | 后续社区讨论和 PR 准备用对应 skill 工作流 |
| P0 | 建立干净 upstream PR 分支 | DONE | 不适用 | 中 | 低 | 0.5 天 | [Day 10](day10-warmpoolavailable-poc.md) 已在 `/home/agentcube-pr265` 基于 `upstream/main` 创建 `feat/warmpool-available-condition` | fork `intern` 保留实习报告；fork `main` 只同步 `upstream/main`；PR 分支只放 #265 代码改动 |
| P0 | 跟进 `TokenCache` 不检查 JWT `exp` 的问题 | WATCH | @HarshitPal25 | 中 | 低 | 0.5 天 | [Week 2](week2-work-plan.md) 已列为跟进项；来源 #375 | 已有人认领，先不重复开 PR；跟踪其 PR，必要时做 review / 复现测试 |
| P0 | 对齐 SnapStart / warm pool benchmark 口径 | WATCH | #365 无 assignee；#366/#379 @lyuyun | 中 | 低 | 1 天 | [Day 12](day12-agentcube-roadmap-from-cubesandbox.md) 已整理 #366 实验验证矩阵、补跑 plain Pod / warm pool 本机数据，并在 [#366](https://github.com/volcano-sh/agentcube/pull/366#issuecomment-4714612811) 发布评论；来源 #365/#366/#379 | 重复评论已删除；跟踪维护者是否希望整理 proposal patch / docs PR |
| P0 | 学习 Karmada Kubernetes-native 控制面设计 | DONE | 不适用 | 中 | 低 | 1 天 | [Day 13](day13-karmada-project-study.md) 已完成：项目定位、组件、核心资源链路、Binding/Work 控制器初读、成功原因和 AgentCube 对比 | 后续如继续学习，再单独开 scheduler / status aggregation 深读任务 |
| P0 | 建立更完整 Kubernetes 测试环境 | BLOCKED | 不适用 | 中高 | 低 | 1-2 天 | [Day 14](day14-kubernetes-environment-and-test-plan.md) 已制定 L0/L1/L2/L3 环境分层；KWOK 已跑通 1 个真实节点 + 3 个 fake nodes；Docker `26.1.3` 和 kind `v0.32.0` 已安装，但 kind 标准 K8s 在 kubelet cgroup/QoS 初始化处失败 | 本机继续硬调收益低；下一步换 cgroup v2 / 新内核机器，或使用云厂商标准 K8s / 新 VM 跑 L1；KWOK 仅保留为调度语义环境 |
| P0 | 分析社区 issue / PR 动态 | DOING | 按 issue 逐项记录 | 中 | 中 | 0.5-1 天 | [Day 9](day9-open-source-community-and-fork-sync.md)、[Week 2](week2-work-plan.md) 已完成两轮统计；[Day 23](day23-agentcube-future-architecture-and-design.md) 已把 2026-06-23 最新 PR / issue 信号整理成未来架构路线 | 重点跟进 #386、#387、#400、#394/#395、#331、#291、#366/#379，选择可验证参与点 |
| P0 | 跟进 PR #385 review 反馈 | DOING | PR #385；assignee @RainbowMango | 中 | 低 | 0.5 天 | [Day 15](day15-upstream-pr-review-and-snapstart-implementation.md) 已处理 Gemini 关于 `WarmPoolNotFound` warning event 噪音的建议，commit `d885b4e` 已 push；DCO signoff 已修复并通过 | 等待 CI、Codecov、tide、maintainer review；当前 tide 主要等待 `approved` / `lgtm` |
| P0 | 阅读 SnapStart 实现 PR #379 | DOING | PR #379 @lyuyun | 高 | 低 | 1 天 | [Day 15](day15-upstream-pr-review-and-snapstart-implementation.md) 已完成代码范围初读，并找到一个非重复 review 点：promotion 重置 `ReadyAt` 后可能因 `snapshotStatusEqual` 不比较 `ReadyAt` 而没有持久化 | 将 `ReadyAt` status equality 评论发到 #379，或先在本地临时分支补最小 controller unit test 验证 |
| P0 | 讨论 AgentCube v0.2.0 下一步计划 | DONE | #386 无 assignee；`FAUST-BENCHOU` 已提 Sandbox Sleep/Resume | 中 | 低 | 0.5 天 | [Day 15](day15-upstream-pr-review-and-snapstart-implementation.md) 已整理 2026-06-17 会议纪要，明确 agent-sandbox compatibility、Sleep/Resume、E2B-compatible API/SDK/template、SnapStart/MicroVM snapshot/runtime 四层关系 | 后续拆到具体子任务，不再作为单独会议任务跟踪 |
| P0 | 适配 current stable `kubernetes-sigs/agent-sandbox` | REVIEW | #386；PR [#387](https://github.com/volcano-sh/agentcube/pull/387)；Go 前置 PR [#391](https://github.com/volcano-sh/agentcube/pull/391) 已合并 | 高 | 低 | 1-2 天 | [Day 16](day16-agent-sandbox-latest-adaptation.md) 已完成 `agent-sandbox v0.4.6` 适配、codegen 修复、k3s / SDK / MCP / math-agent 验证；[Day 17](day17-pr387-copilot-review-and-ci-triage.md) 已完成 Copilot/Gemini 评论分组、CI triage、#391 rebase validation、fork CI、upstream #387 update；[Day 19](day19-pr387-code-review-prep.md) 已完成逐文件 code rationale matrix、`go.mod` 依赖栈解释、local-vs-project 分类、review Q&A 和测试覆盖矩阵；当前 #387 kind/body/label 已改为 stable `v0.4.6` compatibility feature 口径；commit `ff8260e` 已移除非必要 `docker/Dockerfile.picod` cleanup 并 push，PR changed files 降到 15 | 等待 #387 刷新 checks/review；继续推进 #387 review/merge；不把 rc1 / v1beta1 扩入 #387；review 前按 Day19 解释 `go.mod`、generated files、claim/adopted Sandbox、NetworkPolicyManagement |
| P0 | 前沿适配测试 `agent-sandbox v0.5.x` / `v1beta1` | REVIEW | #386；后续独立 follow-up，当前不绑定 upstream PR | 高 | 低 | 1-2 天 | [Day 18](day18-agent-sandbox-v05-forward-adaptation.md) 已完成 `v0.5.0rc1` 最小编译适配、clean runtime 验证和 fork CI 验证；fork PR [#5](https://github.com/ranxi2001/agentcube/pull/5) 已 rebase 到最新 #387 head `c2633c5`，当前 head `3abdb94`，本地 rebase 后 build/lint/unit/gen-check 全通过，fork CI 10/10 全绿；第一次 CI e2e 失败溯源为 e2e setup 仍安装旧 agent-sandbox manifest，集群无 v1beta1 CRD，已在 v0.5 分支对齐 `AGENT_SANDBOX_VERSION=v0.5.0rc1`；隔离 k3d + rc1 manifest 下 direct/warm-pool e2e、留存式 v1beta1 字段检查、delete cleanup、SDK、LangChain、MCP HTTP/stdio、math-agent LLM e2e 均通过；现有 v1alpha1 CRD 集群 server dry-run 会因 storedVersions 阻塞原地 apply | 等正式 `v0.5.0` release 或 maintainer 明确要求 rc support 后准备独立 upstream PR；PR 材料必须说明 clean-install 已验证、v1alpha1 -> v1beta1 原地升级未覆盖 |
| P0 | 设计 AgentCube Sleep/Resume 生命周期 | DOING | #386；FAUST-BENCHOU 已提出方案 | 高 | 低 | 1-2 天 | [Day 24](day24-sandbox-sleep-resume-design-note.md) 已完成设计先行版本、本地 spike 和第一阶段 Store 状态/CAS 实现记录：结论是不等待 agent-sandbox 全部定稿，但也不重复实现底层 pause；AgentCube 先定义 session lifecycle contract、Store CAS/状态、Router resume-before-proxy、GC split 和 RuntimeProvider capability；已核对 agent-sandbox [#36](https://github.com/kubernetes-sigs/agent-sandbox/issues/36) / [#103](https://github.com/kubernetes-sigs/agent-sandbox/issues/103)；`/home/agentcube-sleep-resume-spike` 验证 fake provider / Store CAS / GC decision；`/home/agentcube-sleep-resume-store-state` branch `feat/sleep-resume-store-state` 已实现 `SandboxInfo` pause 字段、状态常量、Redis/Valkey `UpdateSandboxStatusCAS`、pause expiry index 和并发 CAS 测试 | 暂不发 upstream；下一步进入 WorkloadManager pause/resume API + fake provider 测试，之后再接 GC split / Router resume-before-proxy / direct hard-pause e2e |
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
| 完成 AgentCube 未来发展方向与架构设计探讨 | [Day 23](day23-agentcube-future-architecture-and-design.md) |
| 完成 Sandbox Sleep/Resume 设计先行稿 | [Day 24](day24-sandbox-sleep-resume-design-note.md) |
| 完成 Sleep/Resume 本地状态机 spike | [Day 24](day24-sandbox-sleep-resume-design-note.md) 已记录 `/home/agentcube-sleep-resume-spike` 的 fake provider / Store CAS / GC decision 测试结果 |
| 完成 Sleep/Resume 第一阶段 Store 状态/CAS | [Day 24](day24-sandbox-sleep-resume-design-note.md) 已记录 `/home/agentcube-sleep-resume-store-state` 的 `feat/sleep-resume-store-state` 实现和测试结果 |

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
