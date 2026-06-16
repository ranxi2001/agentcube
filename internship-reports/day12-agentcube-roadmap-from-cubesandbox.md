# Day 12：从 CubeSandbox 反推 AgentCube 开发方向

## 今日目标

Day11 已经完成 CubeSandbox 深入调研，确认它的核心优势集中在 RustVMM / KVM MicroVM、E2B 兼容、CubeCoW snapshot / clone / rollback、PVM 云 VM 路线、CubeVS / CubeEgress 出网治理，以及 Python / Go SDK 和 Web UI。

Day12 不继续泛泛扩展竞品，而是把这些能力反推到 AgentCube：看哪些差距应该由底层 sandbox runtime 解决，哪些应该由 AgentCube 这个 Kubernetes-native 调度 / 管理层解决，并从社区 issue / PR 中选出本周可落地的开发或社区参与任务。

## 前置结论

CubeSandbox 和 AgentCube 不是同一层项目：

| 项目 | 主要层级 | 核心问题 |
| --- | --- | --- |
| CubeSandbox | 底层 sandbox platform | 如何快速、安全、低成本地创建、复制、回滚硬件隔离沙箱 |
| AgentCube | Kubernetes-native 管理层 | 如何把 Agent runtime、session、warm pool、snapshot backend 和调度策略接入 Kubernetes |

因此 AgentCube 不应该直接重复实现一个 VMM。更合理的方向是：把 Kuasar、Kata、gVisor、agent-sandbox、未来可能的 CubeSandbox / Firecracker 类 backend，通过 Kubernetes 原生抽象管理起来，并补齐 benchmark、状态可观测性、E2B 兼容和生产治理能力。

## 社区状态快照

以下状态通过 GitHub API 在 2026-06-16 核对：

| 编号 | 类型 | 标题 | 状态 | 负责人 / 作者 | 对 Day12 的意义 |
| --- | --- | --- | --- | --- | --- |
| [#267](https://github.com/volcano-sh/agentcube/issues/267) | issue | Position AgentCube as a Stateful, Isolated, Concurrent Rollout Execution Layer for Agentic RL and Verifiable Agentic Tasks | open | `acsoto` | 定义 AgentCube 在 RL rollout / verifiable task 中的战略定位 |
| [#365](https://github.com/volcano-sh/agentcube/issues/365) | issue | AgentCube SnapStart Validation for Agentic RL Rollouts | open | `Abhinav-kodes` | 最适合承接我们 Day5-Day11 benchmark 和竞品调研结果 |
| [#366](https://github.com/volcano-sh/agentcube/pull/366) | PR | docs: add agentcube snapstart proposal | open, mergeable | `lyuyun` | SnapStart 设计主线；适合 review 和补 benchmark / fallback 口径 |
| [#379](https://github.com/volcano-sh/agentcube/pull/379) | PR | feat: implement snapstart for codeinterpreter | open, mergeable | `lyuyun` | SnapStart 实现主线；不适合贸然抢实现，但适合读代码和 review |
| [#265](https://github.com/volcano-sh/agentcube/issues/265) | issue | observe SandboxWarmPool health in CodeInterpreter status | open | `Sanchit2662` | 我们 Day10 已经围绕它提交 PR |
| [#385](https://github.com/volcano-sh/agentcube/pull/385) | PR | feat: expose CodeInterpreter warm pool health | open, mergeable | `ranxi2001` | 我们已提交的 PR，本周需要继续跟踪 CI / reviewer 反馈 |

当前判断：

- SnapStart 主方向已经有人在做，不能另起一个 competing backend 设计。
- 我们更适合在 #365 / #366 / #379 周边补 benchmark 口径、测试场景、文档和 review comment。
- #385 是我们已经进入 review 的开发成果，需要持续维护，不能开完 PR 就不管。

## CubeSandbox 能力到 AgentCube 缺口映射

| CubeSandbox 能力 | AgentCube 当前相关能力 | 明显缺口 | 可做工作 |
| --- | --- | --- | --- |
| RustVMM / KVM / PVM MicroVM | 通过 RuntimeClass / agent-sandbox / Kuasar / Kata 等接底层 runtime | AgentCube 自身不直接提供硬隔离；实际隔离等级依赖集群节点和 runtime provider | 文档里明确“AgentCube 管理层 vs runtime backend”的边界，避免把普通 Pod 实测误写成 microVM 能力 |
| E2B SDK 兼容 | Router HTTP、Python SDK；社区有 E2B 兼容讨论 | 没有完整 E2B-compatible API 矩阵和缺口列表 | 做 E2B API gap analysis：create/list/delete/connect/execute/logs/timeout/snapshot 哪些已有、哪些依赖 runtime |
| CubeCoW snapshot / clone / rollback | SnapStart proposal / implementation 正在进行；warm pool 已有 | snapshot、restore、fallback、artifact lifecycle、benchmark 指标还需要统一口径 | 围绕 #365/#366 补 benchmark 场景和指标定义 |
| Web UI / 版本矩阵 / 状态面板 | Kubernetes status、events、logs；我们 #385 补 WarmPoolAvailable | 用户对 warm pool / session / sandbox 健康状态的可观测性还不完整 | 跟进 #385；后续继续补 status / event / doc |
| CubeVS / CubeEgress 出网治理 | 可依赖 K8s NetworkPolicy / runtime policy | Agent 不可信代码的出网审计、凭据注入、按域名/路径治理还没有清晰设计 | 先做调研和设计讨论，不建议本周直接实现 |
| 官方 benchmark | 我们已有 Day5 warm pool、cage-bro、CubeSandbox 官方数据 | AgentCube 缺统一 benchmark 文档：机器环境、warm pool size、cold start、p50/p95/p99、失败 fallback、资源残留 | 本周最适合落地：写 benchmark 口径说明或 issue comment |

## 本周可做开发任务候选

| 优先级 | 候选任务 | 对应社区线索 | 难度 | 成本 | 时间 | 产出 |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | 跟进 #385 WarmPoolAvailable PR | #265 / #385 | 中 | 低 | 持续 | 回复 review、补测试或调整 condition/event 语义 |
| P0 | SnapStart / warm pool benchmark 口径说明 | #365 / #366 / #379 | 中 | 低 | 0.5-1 天 | issue 评论或文档草案，复用 Day5-Day11 数据 |
| P1 | E2B compatibility gap analysis | Day11 CubeSandbox E2B 调研；AgentCube 社区讨论 | 中 | 低 | 0.5-1 天 | API 对照表，明确 AgentCube 要兼容 E2B 需要补哪些接口 |
| P1 | Review SnapStart design / implementation | #366 / #379 | 中高 | 低 | 0.5-1 天 | review 笔记或 PR comment，重点看 fallback、artifact 生命周期、benchmark |
| P2 | 出网治理设计调研 | CubeEgress 对照样本 | 高 | 中 | 1-2 天 | 设计调研，不建议今天直接写代码 |
| P2 | AgentCube 可观测性后续增强 | #385 后续 | 中 | 低 | 1 天 | 视 review 反馈决定是否补 status/event/doc |

## Day12 优先选择

今天优先推进两条线：

1. **主线：SnapStart / warm pool benchmark 口径说明**
   - 原因：#365 仍 open，#366 / #379 正在 review，社区方向已经明确需要 benchmark 场景。
   - 我们有现成输入：AgentCube warmPoolSize=2/5/10/20 实测、当前机器环境限制、forkd / CubeSandbox / cage-bro 竞品数据口径。
   - 这件事风险低，不会和 #379 实现 PR 冲突。

2. **维护线：继续跟进 #385**
   - 原因：这是我们已经提交的代码 PR。
   - 今天不主动扩大范围，等 CI / reviewer 反馈；如果出现 review comment，再按最小修改处理。

暂不优先做：

- 直接实现 SnapStart 主功能：#379 已经是大型实现 PR，贸然改代码容易冲突。
- 直接做 CubeEgress 类出网治理：方向重要，但本周范围过大，且需要先有 AgentCube 的 runtime / network policy 边界设计。
- 在当前 CentOS 8 机器上完整跑 CubeSandbox：环境不满足，Day11 已记录需要换 KVM/PVM 独立机器。

## Benchmark 口径草案

如果今天要在 #365 或相关文档中贡献 benchmark 口径，建议拆成这些场景：

| 场景 | 目的 | 指标 |
| --- | --- | --- |
| cold start baseline | 无 warm pool / 无 snapshot 时的基线 | create session total p50/p95/p99、成功率、失败原因 |
| warm pool hit | 验证已有 warm sandbox 命中时延迟 | claim latency、router execute latency、delete latency |
| warm pool miss | 验证突发并发超过 pool 容量时的长尾 | miss 数量、补池耗时、p95/p99、timeout |
| SnapStart restore hit | 验证 snapshot restore 替代 cold start 的收益 | restore latency、fallback 率、snapshot compatibility |
| restore fallback | snapshot 不可用或节点无 artifact 时是否正确降级 | fallback path、用户可见状态、event/log |
| N-way rollout fan-out | Agentic RL / SWE-bench 多分支场景 | N 个 sandbox ready wall time、per sandbox avg、隔离性验证 |
| cleanup / residue | 验证 benchmark 后资源是否清理干净 | Sandbox / Pod / warm pool / Redis / PVC / artifact residue |

指标统一建议：

- 必写：机器环境、OS、kernel、CPU、内存、Kubernetes 版本、runtimeClass、warmPoolSize、并发数、样本数。
- 延迟：p50 / p95 / p99 / min / max，不只写 average。
- 成功率：成功数、失败数、失败类型。
- 资源：ready sandbox 数、CPU/memory、残留资源。
- 安全边界：普通 Pod、Kuasar/Kata/gVisor、MicroVM 要分开标注。

## 英文社区评论草稿

下面是一版可发到 #365 或 #366 的英文草稿。先不直接发布，等 mentor 确认语气和内容后再贴到社区。

```markdown
I looked at this from the benchmark angle, based on our local AgentCube warm-pool measurements and a comparison with sandbox systems such as CubeSandbox, forkd, and cage-bro.

One thing I think would help the SnapStart discussion is to separate the benchmark scenarios by startup path and isolation level, instead of comparing only one end-to-end number.

Suggested scenarios:

| Scenario | Purpose | Suggested metrics |
| --- | --- | --- |
| Cold start baseline | Measure the path without warm pool or snapshot restore | total create-session p50/p95/p99, success rate, failure reason |
| Warm pool hit | Measure the already-ready sandbox path | claim latency, router execution latency, delete-session latency |
| Warm pool miss | Measure burst concurrency above pool capacity | miss count, refill time, p95/p99 tail latency, timeout rate |
| SnapStart restore hit | Measure restore from a compatible snapshot/template | restore latency, sandbox-ready latency, snapshot compatibility result |
| Restore fallback | Verify behavior when snapshot/artifact is unavailable | fallback path, user-visible status/condition/event, log message |
| N-way rollout fan-out | Model agentic RL / SWE-bench branch-out workload | wall time for N ready sandboxes, per-sandbox average, isolation check |
| Cleanup / residue | Ensure repeated benchmark runs do not leave resources behind | remaining Sandbox/Pod/SandboxWarmPool/PVC/artifact/Redis entries |

For each run, I would also record:

- OS, kernel, CPU, memory, Kubernetes version, node type
- runtimeClass / runtime provider / whether it is plain Pod, Kuasar/Kata/gVisor, or MicroVM-backed
- warmPoolSize, concurrency, sample count, image/template used
- p50/p95/p99/min/max, not only average
- success count, failure count, failure type
- resource residue after cleanup

This distinction matters because warm pool and SnapStart optimize different parts of the path:

- SandboxWarmPool hit reuses an already-running Sandbox and should avoid both cold start and restore latency.
- SnapStart restore optimizes creation of a newly started Sandbox from a prepared runtime baseline.
- WarmPool refill may itself use SnapStart, but the user-facing path is different from a direct warm-pool hit.

In our current local environment, only the plain Pod / warm-pool path is measurable:

- OS: CentOS Linux 8
- kernel: 4.18.0-348.7.1.el8_5.x86_64
- glibc: 2.28
- CPU: 4 vCPU on KVM VM
- /dev/kvm: unavailable
- vmx/svm flags: not exposed
- Kubernetes: local k3s

So this machine cannot validate Kuasar/KVM-based SnapStart restore. It can still provide warm-pool baseline data and show why the benchmark should separate warm-pool hit, warm-pool miss, and future snapshot-restore paths.

One local observation: under a concurrent-10 workload, warmPoolSize=2 had very large tail latency because most requests missed the pool. Increasing warmPoolSize to 10 reduced concurrent-10 total p50 to the sub-second range in our setup. This suggests that benchmark reports should always include warmPoolSize, ready replicas before the run, and whether each request hit or missed the pool.

This also aligns with the SnapStart proposal direction: the benchmark should validate not only the best-case restore latency, but also restore availability, fallback behavior, and resource cleanup after repeated fan-out runs.
```

## 今天结束时希望产出

1. Day12 文档：明确从 CubeSandbox 反推 AgentCube 的开发方向。
2. 一份可发到 #365 / #366 的 benchmark 口径草案。
3. 英文社区评论草稿已整理，先不急着发，等和 mentor 对齐。
