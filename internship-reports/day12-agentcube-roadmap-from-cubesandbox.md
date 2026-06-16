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

## 重新阅读 #365 后的判断

#365 的正文已经在 2026-05-30 更新为 “supporting benchmark and validation tracker for #366, not a separate backend proposal”。评论区最关键的是 `acsoto` 的回复：

- 他认可 #365 的问题陈述和 agentic RL rollout 动机，并认为它和 #267 大方向一致。
- 但他明确建议近期实现方向应对齐 #366 的 SnapStart 设计，而不是先引入 separate direct-to-Firecracker backend。
- 原因是 AgentCube 当前控制面是 Kubernetes-native：runtime 表达为 `CodeInterpreter` / `AgentRuntime`，session 通过 `Sandbox` / `SandboxClaim` 创建，router 依赖 Workload Manager session metadata。
- #366 的价值在于保留这个模型：在现有 runtime 上叠加独立 SnapStart CRD，能用 Kuasar WarmForkSnapshot 时使用，snapshot 不可用时 fallback 到 cold start。
- Firecracker / direct-runtime 仍可作为动机和未来比较点，尤其是 RL fan-out latency target，但要等 Kuasar SnapStart / Kubernetes-native 路径验证后再决定是否需要。

因此，我们准备发到 #365 的评论应该满足几个条件：

| 判断 | 对评论草稿的要求 |
| --- | --- |
| #365 已经收敛为 #366 的 benchmark tracker | 开头要明确 “aligned with #366 / acsoto's direction”，不要像另起一个设计 |
| 不抢 #379 实现方向 | 只补 benchmark matrix、metrics、environment metadata，不建议新的 backend |
| 竞品数据只能做参考 | CubeSandbox / forkd / cage-bro 只用于说明为什么要拆分 startup path 和 isolation level，不写成 AgentCube 应优先接这些 backend |
| 近期验证重点是 Kuasar SnapStart | benchmark 应围绕 cold start、snapshot restore、restore fallback、N-way rollout，而不是 Firecracker direct backend |
| warm pool 和 SnapStart 是不同层 | 建议拆开 warm-pool hit、warm-pool miss + SnapStart restore、restore fallback，避免一个总延迟掩盖路径差异 |

## #366 需要补的实验验证点

重新读取 [#366](https://github.com/volcano-sh/agentcube/pull/366) 当前 proposal 后，结论是：设计文档已经写清楚了 API、controller、artifact lifecycle、restore intent、failure handling 和 metrics，但还缺一个独立的 **Benchmark and Validation Plan**。现在的测试内容分散在各节里，不能直接回答“SnapStart 到底怎么证明有效、怎么证明 fallback 正确、怎么和 warm pool 区分”。

#366 提案结构理解：

| 模块 | 关键设计 | 对我们评论的影响 |
| --- | --- | --- |
| 目标 | Phase 1 只做 Code Interpreter `Fork` SnapStart；`Resume` 只是 API 演进预留 | 评论不能要求 Phase 1 完成 session suspend / resume |
| 抽象边界 | 业务 runtime controller 只负责生成 `SandboxTemplate`；`SandboxSnapshotController` 不理解 `CodeInterpreter` 细节 | benchmark 建议要围绕标准 `SandboxTemplate` / `SandboxSnapshot` / `Sandbox` 路径，不写成 CodeInterpreter 私有逻辑 |
| Snapshot 创建 | controller 创建 build `Sandbox` 和 `SandboxSnapshotTask`；node agent 通过 `SnapshotDriver.Create()` 调底层 runtime / VMM | 实验要测 build task、artifact ready、build sandbox cleanup |
| Restore 执行 | Workload Manager 只在 session `Sandbox` 上注入 `agentcube.volcano.sh/snapshot-key`；真正 restore 由 runtime compatibility layer 在 Pod sandbox 创建前消费 | 不能要求 Workload Manager 直接证明 restore success；最多建议 runtime/provider log、event 或 metric 作为证据 |
| Artifact store | Redis / Valkey 保存 `SnapshotArtifactManifest`、active/pending artifact set 和 per-node artifact | 实验要检查 active artifact 不可用时是否 cold-start，重建后是否切换 active set |
| hash / invalidation | `snapshotHash` 由 source identity、pod template、snapshot class 计算；不 dereference ConfigMap / Secret / PVC 内容 | correctness test 要覆盖引用变化与引用背后内容变化的差异 |
| scheduling | build 节点按 `SnapshotClass.nodeSelector` 和源 pod scheduling constraints 选；restore session 仍交给 Kubernetes scheduler | benchmark 要记录 node label、runtimeClass、provider、是否目标节点有 artifact |
| WarmPool | Phase 1 中 WarmPool path 和 Snapshot restore path 独立；warm pool hit 优先，miss 后可走 snapshot restore；warm pool refill 不用 snapshot restore，组合放 Phase 2 | 我们评论必须按 Phase 1 路径拆指标，不把 Phase 2 refill+restore 混进当前验收 |
| failure | artifact store 不可用、无 active artifact、source change 等情况下新 session 应 cold-start；restore intent 注入后失败由 runtime policy 决定 | benchmark 需要覆盖 fallback，并明确只看 `restore_intent_total` 不够 |

当前 #366 已有内容和缺口：

| 位置 | 已有内容 | 缺口 |
| --- | --- | --- |
| `7.4 Code Interpreter Fork-Safe Point` | 写了 Phase 1 tests：恢复后不能看到其他 session 文件、token/context 要刷新、用户代码不能串、artifact 可在 build Sandbox 删除后恢复、版本化引用触发新 hash | 这是正确性测试，不是性能实验；还缺 cold start vs restore、fallback、并发 fan-out、cleanup residue |
| `8.3 Phase 1 Session Path Selection` | 写了 WarmPool path 和 Snapshot restore path 独立，一个请求只走一条路径 | 需要在实验中强制区分 warm-pool hit、warm-pool miss、snapshot restore、cold-start fallback；否则总时延不可解释 |
| `8.3` 与 `15 Delivery Plan` | 当前 PR 明确写 `WarmPool slot refill does not use Snapshot restore in Phase 1`，WarmPool + Snapshot 组合放到 Phase 2 | 实验矩阵要按 Phase 1 口径拆：warm-pool hit、warm-pool miss 后走 snapshot restore path、snapshot unavailable 后 cold-start；不要把 Phase 2 的 refill+restore 写进 Phase 1 验收 |
| `12 Failure Handling` | 写了 artifact store unavailable、no target node、restore fails after intent injection 等处理 | 缺少对应验证步骤：如何制造 unavailable / restore failure、用户侧看什么 condition/event/log、是否卡住资源 |
| `13 Observability` | 提案列出了 `agentcube_snapshot_restore_intent_total{result=cold_start|restore_intent}` 等拟议 metrics | 这个拟议指标只能证明是否注入 restore intent，不能证明 runtime restore 成功；实验报告需要补 runtime log/event 或未来 restore result metric |

建议补入位置：放在 `13 Observability` 之后、`14 Security Boundaries` 之前，标题为 `Benchmark and Validation Plan`。这不改 API，不抢 #379 实现，只是把 #365 的 benchmark tracker 变成 #366 设计文档里的验收标准。

建议实验矩阵：

| 实验 | Setup | 期望路径 | 必看证据 |
| --- | --- | --- | --- |
| cold start baseline | 关闭 warm pool，且没有 Ready `SandboxSnapshot` / active artifact | regular cold-start Sandbox | 无 `snapshot-key`；session ready p50/p95/p99；失败原因 |
| SnapStart restore hit | 预先创建 Ready Fork `SandboxSnapshot`，节点满足 `SnapshotClass` | Workload Manager 注入 restore intent，runtime restore | `snapshot-key`；runtime 侧 restore 成功日志/事件；ready latency |
| snapshot unavailable fallback | 删除 active artifact、artifact store 不可用、或 snapshotHash 失效 | cold start fallback，不阻塞新 session | fallback reason；用户可见 condition/event/log；无 Pending 卡死 |
| restore failure after intent | 注入不兼容 / 不存在 snapshot key，或让 runtime restore 返回失败 | 按 runtime policy fallback 或 fail | 明确 result，不能只看 intent count；记录用户侧错误 |
| N-way rollout fan-out | N 个并发 session，例如 1/5/10/50 | 批量创建并进入 Ready | wall time、per-session p50/p95/p99、成功率、tail latency |
| warm pool separation | 同时配置 `warmPoolSize` 和 Snapshot | Phase 1 中 warm-pool hit 直接复用 ready Sandbox；warm-pool miss 可转入 Snapshot restore path 或 cold-start fallback | hit/miss 数、ready replicas、是否注入 `snapshot-key`、是否 cold-start |
| fork safety / isolation | 多个 restore session 写文件、换 token、提交用户代码 | session 间状态隔离 | 文件不可见、token/context 不复用、用户代码不串 |
| cleanup / residue | 重复 create/delete/rebuild | 无控制面和资源残留 | Sandbox、Pod、SandboxSnapshotTask、artifact record、PVC/Redis 残留数 |

补充观测建议：

- #366 提案中的 `restore_intent_total` 是拟议指标，只能证明“尝试走 restore”，不能证明“restore 成功”。如果 runtime 层暂时无法回写统一结果，实验报告至少要引用 runtime log/event；后续可以考虑补 `restore_success` / `restore_fallback` 这类 runtime provider metric。
- benchmark 报告必须记录 OS、kernel、Kubernetes 版本、runtimeClass、provider、node label、image/template digest、warmPoolSize、并发数、样本数。
- plain Pod、Kuasar/Kata/gVisor、MicroVM 的隔离等级必须分开，不要跨隔离等级只比较一个 total latency。

## 本机补跑实验：给 #366 评论提供观测数据

2026-06-16 补跑了一组 AgentCube CodeInterpreter sandbox 基础设施链路测试，用来支撑 #366 评论里的 “startup path 必须分开统计” 观点。

测试边界：

- 测试脚本：[agentcube_sandbox_latency_benchmark.py](benchmarks/agentcube_sandbox_latency_benchmark.py)
- 链路：`create session -> run print("ok") -> delete session`
- 不包含：LLM 调用、Agent 规划、多轮推理、工具选择、复杂依赖加载、任务正确率。
- 环境：CentOS Linux 8，kernel `4.18.0-348.7.1.el8_5.x86_64`，k3s `v1.24.17+k3s1`。
- Runtime：没有配置 `RuntimeClass`，`kubectl get runtimeclass` 返回空；这是 plain Pod / agent-sandbox 当前路径，不是 Kuasar/KVM SnapStart。
- KVM：`/dev/kvm` 不存在，CPU `vmx/svm` 未暴露，所以本机不能验证 #366 真正关心的 Kuasar / KVM snapshot restore。
- CodeInterpreter：`default/my-interpreter`，镜像 `ghcr.io/volcano-sh/picod:latest`，requests `100m/128Mi`，limits `500m/512Mi`。

结果文件：

| 场景 | 文件 |
| --- | --- |
| smoke test，warmPoolSize=2，顺序 1 次 | [day12_smoke_warmpool2_seq1_result.json](benchmarks/day12_smoke_warmpool2_seq1_result.json) |
| warmPoolSize=2，顺序 10 次 | [day12_warmpool2_sequential_10_result.json](benchmarks/day12_warmpool2_sequential_10_result.json) |
| warmPoolSize=2，并发 2 | [day12_warmpool2_concurrent_2_result.json](benchmarks/day12_warmpool2_concurrent_2_result.json) |
| warmPoolSize=2，并发 5 | [day12_warmpool2_concurrent_5_result.json](benchmarks/day12_warmpool2_concurrent_5_result.json) |
| warmPoolSize=2，并发 10 | [day12_warmpool2_concurrent_10_result.json](benchmarks/day12_warmpool2_concurrent_10_result.json) |
| warmPoolSize=0，顺序 3 次 | [day12_coldstart_warmpool0_sequential_3_result.json](benchmarks/day12_coldstart_warmpool0_sequential_3_result.json) |
| warmPoolSize=0，并发 3 | [day12_coldstart_warmpool0_concurrent_3_result.json](benchmarks/day12_coldstart_warmpool0_concurrent_3_result.json) |

汇总数据：

| 场景 | mode | count / concurrency | success | create p50 / p95 | total p50 / p95 | wall clock |
| --- | --- | --- | --- | --- | --- | --- |
| warmPoolSize=2，smoke | sequential | 1 / 1 | 1/1 | `84.43 / 84.43 ms` | `148.07 / 148.07 ms` | `148.09 ms` |
| warmPoolSize=2，顺序 10 | sequential | 10 / 1 | 10/10 | `79.37 / 5989.48 ms` | `126.67 / 6022.46 ms` | `13710.60 ms` |
| warmPoolSize=2，并发 2 | concurrent | 2 / 2 | 2/2 | `75.76 / 121.92 ms` | `162.07 / 182.82 ms` | `183.39 ms` |
| warmPoolSize=2，并发 5 | concurrent | 5 / 5 | 5/5 | `1909.28 / 4467.21 ms` | `1962.20 / 4501.40 ms` | `4508.24 ms` |
| warmPoolSize=2，并发 10 | concurrent | 10 / 10 | 10/10 | `9718.23 / 12098.60 ms` | `9761.01 / 12139.29 ms` | `12160.23 ms` |
| warmPoolSize=0，顺序 3 | sequential | 3 / 1 | 3/3 | `969.82 / 1287.38 ms` | `1009.69 / 1325.47 ms` | `3339.47 ms` |
| warmPoolSize=0，并发 3 | concurrent | 3 / 3 | 3/3 | `769.80 / 1764.72 ms` | `825.96 / 1798.83 ms` | `1802.23 ms` |

关键观察：

1. `warmPoolSize=2` 且并发 2 时，两条请求都基本命中 warm pool，total p50 / p95 是 `162.07 / 182.82 ms`。
2. `warmPoolSize=2` 且并发 10 时，前两个请求 total 分别是 `200.44 ms` 和 `274.76 ms`，后续请求进入 `5.1s-12.1s` 区间，说明同一个 benchmark 里已经混合了 warm-pool hit 和 warm-pool miss。
3. `warmPoolSize=0` 的 cold-start baseline 在本机约为 `0.8s-1.8s`。这不是 Kuasar/KVM cold start，只是 plain Pod 路径基线。
4. 顺序 10 次也会出现 p95 `6022.46 ms`，说明连续快速请求会把补池速度打穿；“顺序测试”不等于每次都稳定命中 warm pool。
5. 这组数据不能证明 #366 SnapStart restore 的性能，但能证明 #366 的 benchmark 章节必须把 cold start、warm-pool hit、warm-pool miss、snapshot restore 和 fallback 分开。

清理状态：

- 测试结束后已把 `CodeInterpreter.spec.warmPoolSize` 恢复为 `2`。
- `SandboxWarmPool/default/my-interpreter` 已恢复到 `readyReplicas=2 / replicas=2`。
- `kubectl get sandboxes -A` 和 `kubectl get sandboxclaims -A` 均显示无资源。
- default namespace 里仍有一个 4 天前的历史 `my-interpreter-4gvd7` Pod，label 为 `agents.x-k8s.io/claim-uid=...`，它不是本次实验新产生的资源；后续需要单独判断是否为历史残留。

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

## 英文社区评论草稿一：发到 #365

这版更适合发到 benchmark issue [#365](https://github.com/volcano-sh/agentcube/issues/365)。改写后的重点是响应 `acsoto` 的方向：把 #365 当作 #366 的 benchmark / validation tracker，围绕 Kubernetes-native / Kuasar SnapStart 路径补充验证矩阵，不提出新的 direct backend。先不直接发布，等 mentor 确认语气和内容后再贴到社区。

```markdown
I agree with the direction in @acsoto's comment: this issue is most useful as a benchmark and validation tracker for the SnapStart path in #366, rather than as a separate direct-runtime/backend proposal.

From that angle, one thing that may help is to separate the benchmark scenarios by startup path and isolation level, instead of comparing only one end-to-end session startup number.

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

For each run, I would record:

- OS, kernel, CPU, memory, Kubernetes version, node type
- runtimeClass / runtime provider / whether it is plain Pod, Kuasar/Kata/gVisor, or MicroVM-backed
- warmPoolSize, concurrency, sample count, image/template used
- p50/p95/p99/min/max, not only average
- success count, failure count, failure type
- resource residue after cleanup

This distinction matters because SandboxWarmPool and SnapStart optimize different layers:

- SandboxWarmPool hit reuses an already-running Sandbox and should avoid both cold start and restore latency.
- SnapStart restore optimizes creation of a newly started Sandbox from a prepared runtime baseline, for example through the Kuasar path described in #366.
- In #366 Phase 1, WarmPool slot refill is explicitly not combined with Snapshot restore. The proposal keeps that combination for Phase 2, so Phase 1 benchmarks should not merge those paths.

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

This is not meant to suggest a different backend direction. The external sandbox systems we looked at are useful mainly as benchmark references: they show why path-specific metrics matter. For AgentCube, I think the near-term validation should stay aligned with #366: cold start vs Kuasar SnapStart restore, restore availability, fallback behavior, N-way rollout fan-out, and cleanup after repeated runs.
```

## 英文社区评论草稿二：发到 #366

这版更适合发到 SnapStart design PR [#366](https://github.com/volcano-sh/agentcube/pull/366)。重点不是再解释竞品，而是建议 proposal 增加一节实验验证计划。先不直接发布，等 mentor 确认后再贴到社区。

```markdown
One concrete thing that may be worth adding to this proposal is a small "Benchmark and Validation Plan" section. The design already covers the CRDs, artifact lifecycle, restore intent, failure handling, and metrics, but I think the validation criteria would be easier to review if the expected experiments were listed explicitly.

Suggested scenarios:

| Scenario | Setup | Expected path | Evidence to record |
| --- | --- | --- | --- |
| Cold start baseline | No warm pool and no Ready SandboxSnapshot / active artifact | regular cold-start Sandbox | no snapshot-key, session-ready p50/p95/p99, failure reason |
| SnapStart restore hit | Ready Fork SandboxSnapshot on an eligible node | restore intent is injected and the runtime restores | snapshot-key, runtime restore log/event, sandbox-ready latency |
| Snapshot unavailable fallback | no active artifact, artifact store unavailable, or incompatible snapshotHash | cold start fallback without blocking new sessions | fallback reason, user-visible condition/event/log |
| Restore failure after intent | invalid / incompatible snapshot key or runtime restore failure | runtime policy fallback or user-visible failure | explicit result; do not infer success from restore intent alone |
| N-way rollout fan-out | create N sessions concurrently from a ready snapshot | N sandboxes become Ready | wall time, per-session p50/p95/p99, success rate, tail latency |
| WarmPool separation | warmPoolSize and Snapshot are both configured | warm-pool hit, snapshot restore after miss, and cold-start fallback are counted separately | hit/miss count, ready replicas, snapshot-key presence, cold-start fallback |
| Fork-safety / isolation | multiple restored sessions write files, receive tokens, and run user code | no state leaks across sessions | file isolation, fresh token/context, user code isolation |
| Cleanup / residue | repeated create/delete/rebuild runs | no stale control-plane or runtime resources | remaining Sandbox, Pod, SandboxSnapshotTask, artifact records, PVC/Redis entries |

I would also suggest calling out one measurement caveat around the proposed metric `agentcube_snapshot_restore_intent_total{mode=...,result=restore_intent}`. If implemented, that metric would prove that Workload Manager injected restore intent, but it would not by itself prove that the runtime restore succeeded. For validation, the report should include provider/runtime evidence as well, such as a runtime log/event or a future provider-level restore result metric.

The benchmark report should include the environment and path labels too:

- OS, kernel, Kubernetes version, node type
- runtimeClass / provider / isolation level
- SnapshotClass / provider name / node label selector
- image or template digest, warmPoolSize, concurrency, sample count
- p50/p95/p99/min/max, success count, failure count, failure type

This is especially important for the WarmPool + SnapStart boundary. In the current proposal, Phase 1 keeps the WarmPool path and Snapshot restore path independent, and it explicitly leaves WarmPool refill through Snapshot restore to Phase 2. So Phase 1 validation should keep these labels separate instead of reporting only one aggregate session startup number.

One limited local data point from the current AgentCube CodeInterpreter path may help explain why this separation matters. This was **not** a Kuasar/KVM SnapStart run: the node had no RuntimeClass configured and `/dev/kvm` was unavailable. It only measured the plain-Pod warm-pool path.

| Local plain-Pod scenario | Observed result |
| --- | --- |
| `warmPoolSize=2`, concurrency=2 | total p50 / p95 = 162.07 / 182.82 ms |
| `warmPoolSize=2`, concurrency=10 | total p50 / p95 = 9761.01 / 12139.29 ms |
| same concurrency=10 run | fastest two requests = 200.44 ms and 274.76 ms |
| same concurrency=10 run | remaining requests = 5.14 s to 12.14 s |

So this local result should not be used as SnapStart evidence. Its value is narrower: it shows that one aggregate "session startup latency" number can mix already-ready warm-pool hits with pool misses / refill waiting. SnapStart restore and restore fallback would need the same path labels, otherwise their effects could be hidden in the aggregate number as well.

This would also connect the proposal more directly with #365, where the issue is now positioned as the benchmark and validation tracker for the SnapStart direction.


If this direction makes sense, I’d be happy to help turn the benchmark matrix into a small proposal patch or a follow-up docs PR.
```

## 发帖前检查清单

正式发社区评论前按这份 checklist 过一遍：

| 检查项 | 要求 |
| --- | --- |
| 目标位置 | benchmark tracker 草案发 #365；实验验证章节建议发 #366 |
| 语气 | 以补充和建议为主，不写“应该推翻现有设计” |
| 认领状态 | 不认领 #379 主实现，不和 `lyuyun` 的实现方向冲突 |
| 方向边界 | 明确支持 #366 的 Kubernetes-native / Kuasar SnapStart 路径，不提出 separate direct-to-Firecracker backend |
| 数据边界 | 明确我们的机器只能测 plain Pod / warm pool，不能验证 Kuasar / KVM SnapStart |
| 数据来源 | 引用 Day5-Day11 本地测试和竞品调研，不夸大不同机器结果；竞品只作为 benchmark 口径参考 |
| 安全边界 | 明确 plain Pod、Kuasar/Kata/gVisor、MicroVM 不能混为一个隔离等级 |
| 下一步 | 评论末尾可以问维护者是否希望把 benchmark matrix 整理成 proposal patch / docs PR |

## #366 评论发布记录

2026-06-16 已把 “Benchmark and Validation Plan” 建议发布到 [#366](https://github.com/volcano-sh/agentcube/pull/366)：

- 保留评论链接：<https://github.com/volcano-sh/agentcube/pull/366#issuecomment-4714612811>
- 评论性质：补充 benchmark / validation plan，不提出 competing backend，不认领 #379 主实现。
- 内容边界：本机数据只作为 plain Pod / warm-pool path-label evidence，不作为 Kuasar/KVM SnapStart 实测。
- 重复评论处理：GitHub API 曾显示同账号在 2026-06-16 03:33:43 UTC 和 03:34:26 UTC 各发了一条内容相同的评论；现已删除重复项，保留 03:33:43 UTC 的评论。

## Day12 后续执行顺序

1. 跟踪 #366 维护者是否认可 benchmark 口径；如维护者希望 benchmark tracker 承接细节，再把更完整矩阵发 #365。
2. 如果维护者反馈认可 benchmark 口径，再考虑把场景矩阵整理成 proposal patch / 英文 docs PR。
3. 同步跟进 #385，若 reviewer 对 WarmPoolAvailable condition / event 语义有意见，优先处理已有 PR。
4. 不在当前机器继续尝试 Kuasar/KVM/CubeSandbox 完整实测，避免把环境 blocker 变成无效时间消耗。

## 今天结束时希望产出

1. Day12 文档：明确从 CubeSandbox 反推 AgentCube 的开发方向。
2. 两份英文社区评论草稿：一份面向 #365 benchmark issue，一份面向 #366 proposal 实验验证补充。
3. 本机 plain Pod / warm pool 补跑数据：用来说明为什么 #366 benchmark 必须拆分 startup path。
4. #366 评论已发布，并记录后续跟踪点。
