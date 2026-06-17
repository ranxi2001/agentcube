# Week 2 工作计划：从社区 issue / PR 出发选择开发任务

日期：2026-06-15

## 背景

本周工作从 AgentCube 开源社区当前的 issue、PR 和讨论出发，选择适合实习阶段实际推进的开发任务。正式开始提 issue、proposal 或 PR 前，先固定贡献和讨论格式标准，避免内容方向正确但社区格式不符合要求。

当前社区规模（GitHub API，2026-06-15）：

| 指标 | 数量 |
| --- | ---: |
| open issues | 40 |
| open PRs | 55 |

上周我们已经完成了部署、benchmark、warm pool 实测、竞品矩阵和社区初步分析。本周应该从“调研和测评”进入“参与社区开发和提交 PR”。格式标准见：[开源贡献与社区讨论格式标准](open-source-contribution-format-standard.md)。

## 当前进展（截至 2026-06-16）

Week 2 已经从“看 issue / 选方向”推进到“提交 PR、参与社区讨论、补齐环境能力边界”的阶段。当前进展如下：

| 方向 | 状态 | 进展 |
| --- | --- | --- |
| 贡献格式和社区规则 | DONE | 已整理 AgentCube issue / PR 讨论格式、PR 管理规范、fork 同步规范，并沉淀为 `.agents/skills/agentcube-issue-discussion` 和 `.agents/skills/agentcube-pr-management` 两个技能 |
| #265 WarmPoolAvailable | REVIEW | 已基于 #265 做 CodeInterpreter warm pool 可用性 PoC，提交 upstream PR [#385](https://github.com/volcano-sh/agentcube/pull/385)，并按 Codecov 提示补充覆盖 warm pool 边界的单测 |
| SnapStart / benchmark | DONE / WATCH | 已仔细阅读 #365、#366、#379，确认本地数据不能证明 Kuasar SnapStart，但可以证明 warm pool 命中 / miss 对延迟影响极大；已将可直接发社区的观测数据评论到 PR #366 |
| CubeSandbox 调研 | DONE | 已完成 Day11 深入调研，覆盖架构图、RustVMM/KVM、PVM、CubeEgress/eBPF、CubeCoW、E2B 兼容、Go/Python SDK 和 benchmark 口径 |
| Karmada 学习 | DONE | 已完成 Day13 学习记录，理解 Karmada 的 Kubernetes-native 多集群控制面、组件式开发方式，以及它成功的核心痛点 |
| Kubernetes 测试环境 | PARTIAL / BLOCKED | 已在现有 k3s 上补 KWOK 伪节点环境，可测调度 / placement / controller 语义；已安装 Docker 和 kind，但标准 kind 集群被当前 CentOS 8、kernel 4.18、cgroup v1、kubelet QOS 初始化问题卡住 |
| 本地硬隔离 / MicroVM | BLOCKED | 当前机器无 `/dev/kvm`，CPU 未暴露 `vmx/svm`，无法直接验证 KVM / Kuasar / Firecracker / CubeSandbox PVM 相关真实隔离路径 |

当前可汇报的 Week 2 结果是：我们已经完成一个真实 upstream PR、一次有数据支撑的社区设计评论、一个云厂商沙箱深度调研、一个成熟 Kubernetes 项目学习记录，并把本地测试环境从单节点 k3s 扩展到了“k3s + KWOK fake nodes”。主要卡点不是代码推进，而是当前机器无法提供标准 kind/kubeadm 集群和 KVM/MicroVM 能力。

后续优先级：

| 优先级 | 下一步 | 原因 |
| --- | --- | --- |
| P0 | 跟进 PR #385 review / CI / maintainer 反馈 | 这是 Week 2 最具体的 upstream 代码产出 |
| P0 | 申请或准备一台 cgroup v2 / 新内核 / 标准 Kubernetes 环境 | 当前机器已证明不适合继续硬调 kind，继续投入性价比低 |
| P1 | 继续读 #379 SnapStart 实现 PR | #366 是设计，#379 才是落地实现，可以判断后续是否能参与测试或补小修 |
| P1 | 在当前 k3s + KWOK 上补 controller / placement 级别验证 | 这类测试不依赖真实 sandbox，可以继续产出有效数据 |

## 社区当前关注方向

| 方向 | 代表 issue / PR | 观察 |
| --- | --- | --- |
| SnapStart / 快速恢复 | [#365](https://github.com/volcano-sh/agentcube/issues/365)、[#366](https://github.com/volcano-sh/agentcube/pull/366)、[#379](https://github.com/volcano-sh/agentcube/pull/379) | 社区正在把快速启动方向收敛到 Kubernetes-native / Kuasar SnapStart，而不是单独走 Firecracker 后端 |
| warm pool 可观测性 | [#265](https://github.com/volcano-sh/agentcube/issues/265)、[#305](https://github.com/volcano-sh/agentcube/issues/305) | CodeInterpreter 目前 Ready 状态不能反映 warm pool 是否真的可用，和我们上周并发 pool miss 观察直接相关 |
| 认证和安全 | [#375](https://github.com/volcano-sh/agentcube/issues/375)、[#367](https://github.com/volcano-sh/agentcube/pull/367) | TokenCache、Keycloak、RBAC、OIDC 是社区重要方向；#375 已由 @HarshitPal25 认领，Keycloak PR 范围很大 |
| 可观测性 | [#333](https://github.com/volcano-sh/agentcube/issues/333)、[#331](https://github.com/volcano-sh/agentcube/pull/331)、[#353](https://github.com/volcano-sh/agentcube/pull/353) | 社区希望增加 session observability、Prometheus metrics 和更清楚的运行状态 |
| 测试和开发体验 | [#383](https://github.com/volcano-sh/agentcube/pull/383)、[#384](https://github.com/volcano-sh/agentcube/pull/384)、[#371](https://github.com/volcano-sh/agentcube/pull/371) | 最近合入和打开的 PR 很多都在补 test、lint、Helm 校验和本地验证目标 |

## PR 修改模式分析

最近的 PR 显示，维护者更容易接受这些类型的改动：

| 类型 | 代表 PR | 对我们的启发 |
| --- | --- | --- |
| 小而明确的测试修复 | [#376](https://github.com/volcano-sh/agentcube/pull/376)、[#378](https://github.com/volcano-sh/agentcube/pull/378) | 小范围、带测试、行为明确，适合作为第一类 upstream PR |
| 开发体验补强 | [#383](https://github.com/volcano-sh/agentcube/pull/383)、[#384](https://github.com/volcano-sh/agentcube/pull/384) | 本地验证命令、CI、Helm lint 这类改动容易 review，但要避免和已有 PR 重复 |
| 控制器 / lifecycle 测试 | [#371](https://github.com/volcano-sh/agentcube/pull/371) | WorkloadManager、SandboxReconciler、GC 相关测试仍是社区关注点 |
| 安全配置和凭据处理 | [#372](https://github.com/volcano-sh/agentcube/pull/372)、[#364](https://github.com/volcano-sh/agentcube/pull/364) | 安全问题可以做，但需要清晰复现、风险解释和兼容性说明 |
| 大功能设计与实现拆分 | [#366](https://github.com/volcano-sh/agentcube/pull/366)、[#379](https://github.com/volcano-sh/agentcube/pull/379) | SnapStart 这类大方向不适合直接贸然改代码，更适合先补 benchmark、测试方案或 review comment |

## 本周可做开发任务候选

| 优先级 | 任务 | 来源 | PR 认领 @ | 开发范围 | 难度 | Token/API 成本 | 预计时间 | 产出 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | 跟进 `TokenCache` 不检查 JWT `exp` 的问题 | [#375](https://github.com/volcano-sh/agentcube/issues/375) | @HarshitPal25 | `pkg/workloadmanager/client_cache.go`、`client_cache_test.go` | 中 | 低 | 0.5 天 | 已有人认领，先做复现、单测思路或后续 PR review，不重复开 PR |
| P0 | 对齐 SnapStart benchmark 口径 | [#365](https://github.com/volcano-sh/agentcube/issues/365)、[#366](https://github.com/volcano-sh/agentcube/pull/366) | #365 无 assignee；#366 @lyuyun | 整理 benchmark 场景、补脚本/文档、在 issue 里提供我们已有数据和环境限制 | 中 | 低 | 1 天 | issue 评论或 benchmark 草案 PR |
| P1 | 给 CodeInterpreter 增加 WarmPoolAvailable 状态设计 / PoC | [#265](https://github.com/volcano-sh/agentcube/issues/265) | 无 assignee；未见直接 PR | `codeinterpreter_controller.go`、`codeinterpreter_controller_test.go`，可能涉及 event recorder | 中高 | 低 | 1-2 天 | PoC 分支或 PR，至少形成设计评论 |
| P1 | 补 AgentCube sandbox benchmark p99、冷启动、资源残留检查 | [#365](https://github.com/volcano-sh/agentcube/issues/365)、[#333](https://github.com/volcano-sh/agentcube/issues/333) | 不适用 | `internship-reports/benchmarks/` 脚本和结果 | 中 | 中 | 1 天 | 本地 benchmark 数据，可用于社区讨论 |
| P1 | 阅读并 review SnapStart 实现 PR | [#379](https://github.com/volcano-sh/agentcube/pull/379) | @lyuyun | 看 CRD、agentd driver、Kuasar driver、fallback 逻辑 | 高 | 低 | 0.5-1 天 | review 笔记，选择是否评论 |
| P2 | 跟进 session observability / Prometheus metrics | [#331](https://github.com/volcano-sh/agentcube/pull/331)、[#353](https://github.com/volcano-sh/agentcube/pull/353) | @Abhinav-kodes | 主要读 PR 和跑测试，避免重复实现 | 中 | 低 | 0.5 天 | review 笔记或测试反馈 |

## 推荐本周主线

建议本周采用“一小 PR + 一条 benchmark/社区参与线”的组合：

1. **主开发 PR 候选：TokenCache JWT 过期修复**
   - 范围小，问题清楚，容易写单测。
   - 但 #375 已由 @HarshitPal25 认领，当前不重复开 PR。
   - 我们可以先做复现、单测思路和后续 PR review；如果该任务长期无进展，再先在 issue 里询问是否需要协助。

2. **主社区参与：SnapStart benchmark 口径对齐**
   - 和我们上周 warm pool、forkd、CubeSandbox 调研高度相关。
   - 当前机器没有 KVM，不能直接跑 Kuasar SnapStart，但可以贡献 benchmark 场景、指标口径、现有 warm pool 数据和环境限制。
   - 可以把我们的测试拆成：N-way session creation、cold start vs warm pool、失败 fallback、p50/p95/p99、资源残留、机器环境说明。

3. **备选开发 PR：WarmPoolAvailable 状态**
   - 因为 TokenCache 已有人认领，可以优先转向 #265。
   - 这个任务和我们上周实测最贴近，但控制器、status、event、watch 逻辑比 TokenCache 更复杂，适合作为第二个 PR 或 PoC。

## 本周排期建议

| 时间 | 工作 |
| --- | --- |
| 周一 | 完成 Week 2 计划；固定贡献和讨论格式标准；同步 fork；阅读 #375、#365、#366、#379、#265；选定第一 PR 方向 |
| 周二 | 检查 #375 是否已有关联 PR；若仍由 @HarshitPal25 认领，则只做本地复现/测试记录，开发方向切到 #265 或 benchmark 草案 |
| 周三 | 根据 issue 认领状态决定是否参与 TokenCache review；同时整理 SnapStart benchmark 场景和已有 warm pool 数据 |
| 周四 | 评估 WarmPoolAvailable PoC，确认是否能在本周形成第二个小 PR 或至少形成设计评论 |
| 周五 | 收尾：跟进 PR review、补测试记录、更新 Day 报告和 TODO，整理本周成果 |

## 暂不建议本周直接做

| 方向 | 原因 |
| --- | --- |
| 直接实现 SnapStart 主功能 | #379 已经是大型实现 PR，涉及 CRD、agentd driver、Kuasar，范围太大 |
| Keycloak / RBAC 大 PR | #367 范围很大，适合读设计，不适合作为本周第一个开发任务 |
| NetworkPolicy 支持 | #291 已有大型 PR，安全语义复杂，容易重复工作 |
| 重复单测清理 | #344 已有 #376 合并，不适合再做 |
| Prometheus metrics 主实现 | #353 已有 PR，先读和测试，不要重复实现 |

## 分支策略

实习报告继续放在 fork `main`。准备 upstream PR 时，按 AGENTS.md 规范从最新 `upstream/main` 拉干净分支：

```bash
git fetch upstream main
git switch -c fix/token-cache-exp upstream/main
```

PR 分支只放一个主题，不带实习报告、benchmark 原始结果和中文-only 文档。

## 本周预期产出

- 至少一个可提交 upstream 的小 PR 或明确的 issue 评论。
- 一份 SnapStart / warm pool benchmark 口径说明。
- 一份 Day 10 / Day 11 开发记录，记录代码修改、测试命令、失败和修复过程。
- 更新 `todo.md`，把 Week 2 任务状态从计划推进到 DOING / DONE / BLOCKED。
