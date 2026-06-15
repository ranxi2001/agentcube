# 实习任务 TODO

更新时间：2026-06-15

这个文档用于管理实习期间的后续任务。日报记录每天做了什么，TODO 记录“现在还要做什么、优先级是什么、做到哪里、卡在哪里”。

## 使用规则

- 状态只保留当前结论：`TODO`、`DOING`、`BLOCKED`、`DONE`。
- 每个任务都要有可检查的产出，例如报告、脚本、benchmark 结果、PR、issue 或代码提交。
- 遇到卡点时要记录失败命令、错误现象、初步原因和临时绕过方式。
- benchmark 任务必须说明测试口径：本机环境、是否包含 LLM、是否包含 Agent、是否只是 sandbox 基础设施链路。
- `难度` 主要指技术不确定性；`成本` 主要看 token / LLM API 消耗，只有机器环境、镜像构建、review 沟通等明显影响任务时才额外备注；`预计时间` 是当前粗估，实际执行后要更新。
- 任务完成后保留在“已完成里程碑”里，方便周报和 mentor 同步。

## 当前优先级

| 优先级 | 任务 | 状态 | PR 认领 @ | 难度 | 成本 | 预计时间 | 产出/证据 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | 准备一个低争议 upstream PR 或 issue | REVIEW | #265 无 assignee；PR #385 | 中 | 低 | 0.5-1 天 | [Day 10](day10-warmpoolavailable-poc.md) 已提交 upstream PR [#385](https://github.com/volcano-sh/agentcube/pull/385) | 等待维护者 review，按反馈调整 |
| P0 | 固定开源贡献和社区讨论格式标准 | DONE | 不适用 | 中 | 低 | 0.5 天 | [格式标准](open-source-contribution-format-standard.md) 已整理官方 issue / PR / proposal / benchmark / review 格式 | 后续 issue、proposal、PR 前按 checklist 检查 |
| P0 | 建立 issue 讨论和 PR 管理本地 skills | DONE | 不适用 | 中 | 低 | 0.5 天 | [issue skill](../skills/agentcube-issue-discussion/SKILL.md)、[PR skill](../skills/agentcube-pr-management/SKILL.md) 已创建 | 后续社区讨论和 PR 准备用对应 skill 工作流 |
| P0 | 建立干净 upstream PR 分支 | DONE | 不适用 | 中 | 低 | 0.5 天 | [Day 10](day10-warmpoolavailable-poc.md) 已在 `/home/agentcube-pr265` 基于 `upstream/main` 创建 `feat/warmpool-available-condition` | fork `main` 保留实习报告；PR 分支只放 #265 代码改动 |
| P0 | 跟进 `TokenCache` 不检查 JWT `exp` 的问题 | WATCH | @HarshitPal25 | 中 | 低 | 0.5 天 | [Week 2](week2-work-plan.md) 已列为跟进项；来源 #375 | 已有人认领，先不重复开 PR；跟踪其 PR，必要时做 review / 复现测试 |
| P0 | 对齐 SnapStart / warm pool benchmark 口径 | TODO | 待查 | 中 | 低 | 1 天 | [Week 2](week2-work-plan.md) 已列为主社区参与线；来源 #365/#366/#379 | 整理已有 warm pool 数据、环境限制和 benchmark 指标，在 issue 或草案文档中反馈 |
| P0 | 分析社区 issue / PR 动态 | DOING | 按 issue 逐项记录 | 中 | 中 | 0.5-1 天 | [Day 9](day9-open-source-community-and-fork-sync.md) 和 [Week 2](week2-work-plan.md) 已完成两轮统计 | 重点跟进 #375、#365、#366、#379、#265，选择可参与点 |
| P0 | 补 Agent 端到端 benchmark | TODO | 不适用 | 中 | 中 | 1-2 天 | 已有 shortest path 单次结果和 sandbox benchmark | 重复测试 LLM + Agent planning + tool call + AgentCube sandbox 的完整链路 |
| P0 | 补多轮 p50/p95/p99 benchmark | DOING | 不适用 | 中 | 低 | 0.5-1 天 | 已有 AgentCube sandbox p50/p95 和 warmPoolSize 曲线 | 增加 p99；统一输出格式；补 Agent/math-agent 多轮统计 |
| P0 | 补冷启动 vs warm pool 对比 | TODO | 不适用 | 中 | 低 | 0.5 天 | 已测 warmPoolSize=2/5/10/20 | 增加 `warmPoolSize=0` 或无 warm pool 场景 |
| P0 | 补并发 5/10/20 sandbox 测试 | DOING | 不适用 | 中 | 中 | 0.5-1 天 | 已测 concurrent=10，warmPoolSize=2/5/10/20 | 增加 concurrent=5 和 concurrent=20；记录失败率和资源压力 |
| P1 | 检查 sandbox 删除后的资源残留 | TODO | 不适用 | 中 | 低 | 0.5 天 | 部分测试后人工恢复过 warm pool 和 port-forward | 固化检查项：Pod、Sandbox CR、SandboxWarmPool、Redis 状态 |
| P1 | 验证 `math-agent` session 自动清理 | TODO | 待查 | 中 | 低 | 0.5-1 天 | 第一周计划中已标记风险 | 检查 `CodeInterpreterClient().stop()` 或等价清理逻辑，并做回归验证 |
| P1 | 构建数学 benchmark 专用镜像 | TODO | 不适用 | 中 | 中 | 1-2 天 | 高考数学测试已暴露 `sympy/numpy/scipy/pandas` 依赖问题 | 构建包含常用数学库的 sandbox 镜像，并复测高考数学题 |
| P1 | 拆分 Workload Manager 内部阶段耗时 | TODO | 不适用 | 高 | 中 | 1-2 天 | 当前只记录 create/run/delete 总耗时 | 拆 API 接收、SandboxClaim、调度、Pod Ready、Router 更新、Redis 写入 |
| P1 | 形成官方 benchmark suite 草案 | TODO | 待查 | 中 | 低 | 1 天 | 已有多个本地 benchmark 脚本和结果 | 整理脚本接口、环境记录、输出 JSON schema 和 README |
| P1 | 评估 `WarmPoolAvailable` 状态 PoC | REVIEW | #265 无 assignee；PR #385 | 中高 | 低 | 1-2 天 | [Day 10](day10-warmpoolavailable-poc.md) 已完成 PoC 并提交 upstream PR [#385](https://github.com/volcano-sh/agentcube/pull/385)；focused tests 通过 | 跟进 CI 和 reviewer 对 condition/event 语义的反馈 |
| P2 | 深读 `agentd`、`picod`、`router` 链路 | TODO | 不适用 | 中 | 低 | 1 天 | Day 2 已完成项目结构初读 | 形成代码阅读笔记，重点解释 session 到 sandbox exec 的调用路径 |
| P2 | 梳理 CRD / DeepCopy / client-go 生成链路 | TODO | 不适用 | 中 | 低 | 0.5 天 | 暂无单独文档 | 读 `make gen-all` 相关脚本和 API type，写一页说明 |
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
