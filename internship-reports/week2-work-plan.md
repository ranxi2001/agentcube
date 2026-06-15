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

## 社区当前关注方向

| 方向 | 代表 issue / PR | 观察 |
| --- | --- | --- |
| SnapStart / 快速恢复 | [#365](https://github.com/volcano-sh/agentcube/issues/365)、[#366](https://github.com/volcano-sh/agentcube/pull/366)、[#379](https://github.com/volcano-sh/agentcube/pull/379) | 社区正在把快速启动方向收敛到 Kubernetes-native / Kuasar SnapStart，而不是单独走 Firecracker 后端 |
| warm pool 可观测性 | [#265](https://github.com/volcano-sh/agentcube/issues/265)、[#305](https://github.com/volcano-sh/agentcube/issues/305) | CodeInterpreter 目前 Ready 状态不能反映 warm pool 是否真的可用，和我们上周并发 pool miss 观察直接相关 |
| 认证和安全 | [#375](https://github.com/volcano-sh/agentcube/issues/375)、[#367](https://github.com/volcano-sh/agentcube/pull/367) | TokenCache、Keycloak、RBAC、OIDC 是社区重要方向，但 Keycloak PR 范围很大 |
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

| 优先级 | 任务 | 来源 | 开发范围 | 难度 | Token/API 成本 | 预计时间 | 产出 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | 修复 `TokenCache` 不检查 JWT `exp` 的问题 | [#375](https://github.com/volcano-sh/agentcube/issues/375) | `pkg/workloadmanager/client_cache.go`、`client_cache_test.go` | 中 | 低 | 0.5-1 天 | 一个小型 bugfix PR，含单测 |
| P0 | 对齐 SnapStart benchmark 口径 | [#365](https://github.com/volcano-sh/agentcube/issues/365)、[#366](https://github.com/volcano-sh/agentcube/pull/366) | 整理 benchmark 场景、补脚本/文档、在 issue 里提供我们已有数据和环境限制 | 中 | 低 | 1 天 | issue 评论或 benchmark 草案 PR |
| P1 | 给 CodeInterpreter 增加 WarmPoolAvailable 状态设计 / PoC | [#265](https://github.com/volcano-sh/agentcube/issues/265) | `codeinterpreter_controller.go`、`codeinterpreter_controller_test.go`，可能涉及 event recorder | 中高 | 低 | 1-2 天 | PoC 分支或 PR，至少形成设计评论 |
| P1 | 补 AgentCube sandbox benchmark p99、冷启动、资源残留检查 | [#365](https://github.com/volcano-sh/agentcube/issues/365)、[#333](https://github.com/volcano-sh/agentcube/issues/333) | `internship-reports/benchmarks/` 脚本和结果 | 中 | 中 | 1 天 | 本地 benchmark 数据，可用于社区讨论 |
| P1 | 阅读并 review SnapStart 实现 PR | [#379](https://github.com/volcano-sh/agentcube/pull/379) | 看 CRD、agentd driver、Kuasar driver、fallback 逻辑 | 高 | 低 | 0.5-1 天 | review 笔记，选择是否评论 |
| P2 | 跟进 session observability / Prometheus metrics | [#331](https://github.com/volcano-sh/agentcube/pull/331)、[#353](https://github.com/volcano-sh/agentcube/pull/353) | 主要读 PR 和跑测试，避免重复实现 | 中 | 低 | 0.5 天 | review 笔记或测试反馈 |

## 推荐本周主线

建议本周采用“一小 PR + 一条 benchmark/社区参与线”的组合：

1. **主开发 PR：TokenCache JWT 过期修复**
   - 范围小，问题清楚，容易写单测。
   - 和安全认证方向相关，但不需要直接卷入 Keycloak 大 PR。
   - 注意先看 issue 是否已有活跃 assignee，避免重复抢工作；可以先准备本地分支和测试，再在 issue 里说明愿意补 PR。

2. **主社区参与：SnapStart benchmark 口径对齐**
   - 和我们上周 warm pool、forkd、CubeSandbox 调研高度相关。
   - 当前机器没有 KVM，不能直接跑 Kuasar SnapStart，但可以贡献 benchmark 场景、指标口径、现有 warm pool 数据和环境限制。
   - 可以把我们的测试拆成：N-way session creation、cold start vs warm pool、失败 fallback、p50/p95/p99、资源残留、机器环境说明。

3. **备选开发 PR：WarmPoolAvailable 状态**
   - 如果 TokenCache 已被别人处理，可以转向 #265。
   - 这个任务和我们上周实测最贴近，但控制器、status、event、watch 逻辑比 TokenCache 更复杂，适合作为第二个 PR 或 PoC。

## 本周排期建议

| 时间 | 工作 |
| --- | --- |
| 周一 | 完成 Week 2 计划；固定贡献和讨论格式标准；同步 fork；阅读 #375、#365、#366、#379、#265；选定第一 PR 方向 |
| 周二 | 基于 `upstream/main` 创建干净分支，实现 TokenCache 修复和单测；跑 `go test ./pkg/workloadmanager` |
| 周三 | 根据 issue 状态决定是否提交 TokenCache PR；同时整理 SnapStart benchmark 场景和已有 warm pool 数据 |
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
