# AgentCube 实习研发导航

这个 `intern` 分支主要用于实习研发记录、开源贡献复盘、架构调研、测试证据和技能沉淀。它不是 AgentCube 上游项目的正式 README，也不作为 upstream PR 的提交材料。

如果需要看原项目介绍，可以打开：

- [README-ZH.md](README-ZH.md)
- [AgentCube upstream](https://github.com/volcano-sh/agentcube)

## 快速入口

| 入口 | 用途 |
| --- | --- |
| [internship-reports/todo.md](internship-reports/todo.md) | 当前任务看板、优先级、社区 issue/PR 跟踪、后续计划 |
| [PROGRESS.md](PROGRESS.md) | Agent 工作循环短记忆，只记录下一轮需要立刻知道的状态 |
| [internship-reports/README.md](internship-reports/README.md) | 实习报告目录 |
| [internship-reports/open-source-contribution-format-standard.md](internship-reports/open-source-contribution-format-standard.md) | 上游 issue / PR / review 的格式规范 |
| [internship-reports/intern-glossary.md](internship-reports/intern-glossary.md) | 实习生术语扫盲，按难度分级解释 Kubernetes、runtime、sandbox、网络、安全等概念 |
| [AGENTS.md](AGENTS.md) | 本仓库协作规则、分支规则、测试规则和知识沉淀规则 |

## 当前主线

1. 参与 AgentCube upstream 社区，跟进 PR / issue / proposal。
2. 推进 `agent-sandbox` compatibility，重点包括 v0.4.6 stable 适配和 v0.5.x 前沿验证。
3. 围绕 Sleep/Resume 设计 AgentCube session lifecycle、Store CAS、Router resume-before-proxy、GC split 和 provider adapter。
4. 调研 OpenSandbox、Agent Substrate、E2B-like API、Agent Infra 生态，并沉淀对 AgentCube 架构演进的判断。
5. 把实习工作从“写代码”升级为“拆需求、做设计、审代码、设计测试、维护开源协作纪律”。

## 专题索引

| 专题 | 重点文档 |
| --- | --- |
| 周总结和能力复盘 | [week1-summary.md](internship-reports/week1-summary.md), [week2-summary.md](internship-reports/week2-summary.md), [week3-summary.md](internship-reports/week3-summary.md) |
| 开源社区与贡献规范 | [day9-open-source-community-and-fork-sync.md](internship-reports/day9-open-source-community-and-fork-sync.md), [open-source-contribution-format-standard.md](internship-reports/open-source-contribution-format-standard.md) |
| CI/CD 与发布工作流 | [day34-agentcube-push-ci-workflow-pr-prep.md](internship-reports/day34-agentcube-push-ci-workflow-pr-prep.md), [day38-release-image-ci-helm-chart-version-failure-analysis.md](internship-reports/day38-release-image-ci-helm-chart-version-failure-analysis.md) |
| AgentCube roadmap 和竞品基准 | [day11-cloud-agent-sandbox-projects.md](internship-reports/day11-cloud-agent-sandbox-projects.md), [day12-agentcube-roadmap-from-cubesandbox.md](internship-reports/day12-agentcube-roadmap-from-cubesandbox.md) |
| `agent-sandbox` stable 适配 | [day16-agent-sandbox-latest-adaptation.md](internship-reports/day16-agent-sandbox-latest-adaptation.md), [day19-pr387-code-review-prep.md](internship-reports/day19-pr387-code-review-prep.md) |
| `agent-sandbox` v0.2 / v0.3 / v0.5 演进 | [day18-agent-sandbox-v05-forward-adaptation.md](internship-reports/day18-agent-sandbox-v05-forward-adaptation.md), [day20-agent-sandbox-v02-v03-v05-wip-pr-implementations-and-project-study.md](internship-reports/day20-agent-sandbox-v02-v03-v05-wip-pr-implementations-and-project-study.md) |
| PR #387 review 准备 | [day17-pr387-copilot-review-and-ci-triage.md](internship-reports/day17-pr387-copilot-review-and-ci-triage.md), [day19-pr387-code-review-prep.md](internship-reports/day19-pr387-code-review-prep.md), [day30-pr387-warm-pool-dataflow-review.md](internship-reports/day30-pr387-warm-pool-dataflow-review.md) |
| Sleep/Resume 设计 | [day24-sandbox-sleep-resume-design-note.md](internship-reports/day24-sandbox-sleep-resume-design-note.md), [day25-sleep-resume-code-review-and-architecture-retrospective.md](internship-reports/day25-sleep-resume-code-review-and-architecture-retrospective.md), [day26-week3-community-latest-and-two-layer-architecture-bug-surface.md](internship-reports/day26-week3-community-latest-and-two-layer-architecture-bug-surface.md), [week3-summary.md](internship-reports/week3-summary.md) |
| OpenSandbox / Agent Substrate / E2B | [day21-opensandbox-agent-substrate-study.md](internship-reports/day21-opensandbox-agent-substrate-study.md), [day22-opensandbox-agent-substrate-runtime-runbook.md](internship-reports/day22-opensandbox-agent-substrate-runtime-runbook.md), [day28-agent-substrate-architecture-and-agentcube-differentiation.md](internship-reports/day28-agent-substrate-architecture-and-agentcube-differentiation.md), [day32-substrate-competitive-analysis-and-agentcube-prd.md](internship-reports/day32-substrate-competitive-analysis-and-agentcube-prd.md), [day33-e2b-protocol-and-agent-era-docker-study.md](internship-reports/day33-e2b-protocol-and-agent-era-docker-study.md) |
| AgentCube 三期新架构 | [day35-agentcube-architecture-iteration-conclusion.md](internship-reports/day35-agentcube-architecture-iteration-conclusion.md), [day36-k8s-slow-resource-control-plane-design.md](internship-reports/day36-k8s-slow-resource-control-plane-design.md), [k8s-crd-sandbox-resource-pool-lifecycle-control-design.md](docs/design/k8s-crd-sandbox-resource-pool-lifecycle-control-design.md) |
| Agent Infra 职业能力地图 | [day27-agent-infra-career-roadmap-and-internship-goals.md](internship-reports/day27-agent-infra-career-roadmap-and-internship-goals.md) |
| 实测和 benchmark 原始材料 | [internship-reports/benchmarks](internship-reports/benchmarks) |

## Sleep/Resume 快速定位

当前 Sleep/Resume 相关判断集中在：

- [Day24 设计笔记](internship-reports/day24-sandbox-sleep-resume-design-note.md)：状态机、Store CAS、GC split、Router resume-before-proxy、3A Store / GC split 测试骨架。
- [Day25 代码审查复盘](internship-reports/day25-sleep-resume-code-review-and-architecture-retrospective.md)：从 reviewer 视角分析 Store/CAS、WorkloadManager lifecycle service、测试风险和 PR 拆分方式。
- [Day26 社区方向总结](internship-reports/day26-week3-community-latest-and-two-layer-architecture-bug-surface.md)：把上层 session/API/control-plane contract 与下层 runtime/provider/substrate capability 分开。
- [todo.md](internship-reports/todo.md)：Stage 3 子任务拆解，包含 3A GC split、3B Router、3C WorkloadManager API、3D provider、3E e2e/math-agent。

当前口径：我们已经完成了控制面设计、spike 验证、review checklist 和部分 test skeleton，不声称完整产品能力已经合入。正式 upstream 实现仍要等 #387 合并和 #386 分工明确。

## 分支和协作纪律

- `origin/main`：尽量保持为 `upstream/main` 的干净镜像。
- `origin/intern`：保存实习报告、中文分析、TODO、skills、本地 benchmark 记录。
- upstream PR：必须从最新 `upstream/main` 新建干净 topic branch，只包含一个 focused change。
- 上游 PR / issue / review：必须使用官方模板和英文，不能把中文实习记录、raw benchmark、私密配置或无关清理混进去。
- 只想跑 CI 时，先看 fork 分支 push 是否有 Actions/checks；当前仓库完整 CI 主要由真实 PR 触发。需要提前验证时，用 `.agents/skills/agentcube-pr-management/` 下的 fork-only push CI 模板在 `ci/<topic>` 分支跑，不要为了验证向自己的 fork 仓库提 PR，也不要把该 workflow 带进 upstream PR。
- 任何真实 token、API key、kubeconfig、Redis 密码、模型凭证都不能进入提交。

## 常用本地入口

```bash
git switch intern
git pull origin intern
rg -n "TODO|BLOCKED|Sleep/Resume|agent-sandbox|#387" internship-reports PROGRESS.md
```

如果要开始新一轮工作，先读：

1. [PROGRESS.md](PROGRESS.md)
2. [internship-reports/todo.md](internship-reports/todo.md)
3. 与当前任务相关的 day 文档
4. 需要开源协作时再读 [open-source-contribution-format-standard.md](internship-reports/open-source-contribution-format-standard.md)
