# Week 4 总结：从架构方向讨论走向可验证的工程闭环

日期：2026-06-30 至 2026-07-05

证据截止：2026-07-05 23:59 CST（有效工作记录截至 7 月 3 日）

## 第一层：可汇报成果

这一部分按公司周报的阅读顺序压缩结果，适合作为后续邮件或周会汇报的事实基础。详细过程、限制和证据保留在后半部分。

### 1. 本月目标

| 目标 | 状态 |
| --- | --- |
| 明确 AgentCube 在 Session Runtime 与 Kubernetes 资源控制面中的架构边界 | 进行中 |
| 完善贡献者 CI、proposal 与 release 等开源工程基础设施 | 进行中 |
| 用可复现 benchmark 定位并优化多架构镜像构建瓶颈 | 进行中 |

### 2. 本周进展

| 工作项 | 结果、价值或剩余风险 | 完成时间 | 状态 |
| --- | --- | --- | --- |
| AgentCube 控制面边界设计 | 明确 Kubernetes 慢资源控制面、节点本地快路径及 E2B L0-L4 兼容层级；当前是设计结论，尚未进入正式实现 | 7/1 | 已完成（设计阶段） |
| 组件清理与社区治理 | PR #403 删除未进入默认运行链路的 `agentd`；PR #414 让 fork branch push 复用 9 类验证；PR #415 建立 proposal 入口与模板 | 7/2 | 已完成 |
| Release 正确性修复 | PR #416 将 Docker tag、Helm chart version 与 app version 分开，保留 `latest` 镜像发布并使用合法 chart version `0.0.0` | 7/3 | 已完成 |
| 多架构构建性能优化 | 创建 issue #419 和最小 PR #420；实测 job wall time 从 1610 秒降至 331 秒，Week 4 截止时仍待社区 review | 待社区评审 | 进行中 |

### 3. 收获与分享

基础设施问题不能只修最后一条报错。先区分触发条件、元数据语义和实际执行平台，才能把 release 失败与 QEMU 构建慢拆成两个独立问题，并分别形成最小修复和 benchmark 证据。

### 4. 疑惑与问题

E2B SDK conformance、skip-cgroup、RuntimeClass、microVM restore 和资源池延迟目标仍缺真实验证；在这些证据补齐前，不能把架构设计写成已实现或兼容能力。

### 5. 下周计划

| 任务 | 可验收结果 |
| --- | --- |
| 跟进 PR #420 | 处理 reviewer 反馈并保持只修改 3 个 Dockerfile builder platform 的最小范围 |
| 验证 agent-sandbox 新版本兼容面 | 区分依赖可编译、API 迁移和已有集群升级，形成可执行测试矩阵 |

### 活动指标

活动指标用于审计工作量，不替代结果和影响：

| 指标 | 数量 | 去重对象 |
| --- | ---: | --- |
| 周内创建的 upstream PR | 4 | AgentCube #414、#415、#416、#420 |
| 周内合并的本人 PR | 4 | AgentCube #403、#414、#415、#416 |
| 创建并完成根因分析的 issue | 1 | AgentCube #419 |

> 注释：#420 在 Week 4 只完成 benchmark、提交和等待 review，实际合并发生在 Week 5，因此不在本周计作“已合入”。

## 第二层：学习与工程记录

这一层保留需求为什么这样拆、组件职责如何判断、哪些尝试失败、测试覆盖什么风险，以及仍不能对外承诺什么。它用于后续工程复盘，不要求原样放进公司周报。

### 本周工程主线

Week 4 的变化，是从“讨论 AgentCube 下一步应该做什么”推进到“每个判断都要能落到组件边界、最小 PR 或实测证据”。架构方向上，E2B、Session Runtime、SandboxPool 和 Kubernetes control plane 不再混成一个大概念；工程执行上，组件清理、贡献者 CI、proposal 治理、release 修复与构建优化分别形成了独立闭环。

本周可以用下面这条链路概括：

```text
协议与架构边界
  -> 组件职责和非目标
  -> 最小化 upstream 改动
  -> fork / runtime 真实验证
  -> 把残余风险留给独立 follow-up
```

> 分析：这条链路的重点不是 PR 数量，而是“结论可证伪”。例如，删除 `agentd` 前先证明它不在默认运行链路；修 release 前先证明 `latest` 同时承担了两种不兼容的版本语义；优化 buildx 前先用分阶段时间定位 QEMU 编译，而不是凭感觉增加 cache 或 matrix。

### 需求拆分与架构边界

| 问题 | 拆分决定 | 组件职责或依赖方向 | 未解决部分 |
| --- | --- | --- | --- |
| AgentCube 是否兼容 E2B | 将兼容性拆成 REST lifecycle、SDK 行为、`envd` process/filesystem、template/snapshot/network/volume，并定义 L0-L4 层级 | AgentCube 先明确自身 API 与 runtime contract，再用官方 SDK conformance 验证兼容层级 | 尚未通过官方 SDK conformance，不能称为 E2B-compatible |
| Kubernetes 如何管理高频 sandbox | Kubernetes 只承载节点选择、资源边界、CRD/status/event 等慢路径；高频 create/restore/pause/delete 下沉节点本地路径 | Template Controller 管全局策略，Pool Controller 管节点实例，`node-ctl` / `sandbox-ctl` 管高频操作 | skip-cgroup、RuntimeClass、microVM restore 与一致性仍需 spike |
| `SandboxPoolTemplate` 与 `SandboxPool` 如何分工 | 前者表达全局调度和容量策略，后者表达单节点资源池实例 | 两类 controller 分离 status 所有权，CRD status 只保存聚合数据 | API 字段、fake node-ctl、CRD skeleton 尚未实现 |
| `agentd` 是否应保留 | 通过 chart、release image、e2e、调用链和实际集群确认生产路径不可达后删除 | WorkloadManager 继续负责生命周期编排；PicoD 负责 sandbox 内执行；后续 Sleep/Resume 不恢复旧 `agentd` | 若未来需要节点侧快路径，应以新 contract 设计，不能复活旧职责 |
| Release 与多架构性能是否同一问题 | 将 Helm 版本错误与 QEMU 编译慢拆成两个问题、两个 PR | workflow 负责发布元数据；Dockerfile builder platform 决定编译执行平台 | PicoD 的 arm64 Ubuntu/Python 安装仍约 122 秒，属于独立优化 |

### 本周实际完成

#### 1. 收敛 E2B 与 Session Runtime 边界

Day33 没有把 E2B 简化成一个 REST API，而是拆成生命周期、SDK 行为、进程与文件系统服务、模板与快照、网络和存储等多层 contract。由此形成 L0-L4 兼容等级：从概念相近、API 相近，一直到官方 SDK 无感接入和完整语义一致。

当前最重要的口径是：AgentCube 可以研究 E2B compatibility layer，但在官方 SDK conformance 通过前，不能直接声称 E2B-compatible。

> 注释：conformance 是一组从外部调用者视角验证行为是否一致的测试。它比“接口名字相同”更严格，因为还会检查错误语义、生命周期、超时和边界行为。

#### 2. 固定 Kubernetes 慢路径与节点快路径

Day35 和 Day36 将新架构拆成两个频率不同的控制面：

- Kubernetes 慢路径负责声明式资源、节点选择、容量策略、CRD status 和 event。
- 节点本地快路径负责高频 sandbox 创建、恢复、暂停和删除。
- `SandboxPoolTemplate` 表达全局策略，`SandboxPool` 表达单节点实例。
- Template Controller 与 Pool Controller 分离状态所有权。
- CRD status 保存资源池聚合信息，不把每个 sandbox 的高频变化写回 API Server。

> 分析：这不是为了绕开 Kubernetes，而是让 Kubernetes 管它擅长的低频声明式状态，把亚秒级、高频且节点局部的操作放到更短的数据路径。设计仍需要通过 fake node-ctl、placeholder spike 和故障恢复测试证明。

#### 3. 完成 unused `agentd` 退出闭环

PR #403 于 7 月 1 日合并，共涉及 15 个文件，净删除 683 行。删除前的代码考古确认：`agentd` 是基于 annotation 删除 idle Sandbox 的 controller，不是 PicoD、WorkloadManager，也没有进入官方 chart、release image、e2e 或默认集群运行路径。

这一工作的复用判断是：删除组件不能只依赖“搜索不到调用”。需要同时检查构建入口、部署入口、运行时对象流、文档承诺和潜在替代职责，才能证明它确实不可达且没有隐藏 owner。

#### 4. 建立 fork push CI 与 proposal 治理

PR #414 在 9 个已有验证 workflow 上增加 branch push 入口，没有复制一套 push-only workflow，也没有把 release/publish 混入普通贡献者验证。干净 fork branch 上 build、e2e、lint、codegen、coverage 和 Python 等 9 类检查全部成功。

PR #415 新增 proposal 索引、模板并更新 CONTRIBUTING。设计上保留历史 `docs/design` 链接，避免已有引用失效；顶层索引只承担入口和 legacy 迁移说明，不要求人工维护所有未来 proposal 的完整目录。

#### 5. 修复 Release Helm 版本语义

至少 10 次历史 `main` push 在 Helm package 阶段失败。根因不是 #414 或 #415 引入回归，而是 workflow 把 Docker 合法标签 `latest` 同时当作 Helm chart `version`，后者必须满足 SemVer。

初版修复曾准备移除 `main` 发布触发。Maintainer 指出社区仍需要 latest images 后，方案被收敛为：

```text
TAG=latest
CHART_VERSION=0.0.0
APP_VERSION=latest
```

真实 fork `main` workflow run 完整成功，约 25 分钟，生成 `agentcube-0.0.0.tgz` 并成功推送 OCI chart。PR #416 于 7 月 3 日合并。

> 分析：这里学到的不是一个 Helm 特例，而是不同生态的“版本”字段可能有不同 contract。相同字符串复用看似减少变量，实际会把 Docker tag、chart package version 和 app version 的语义耦合起来。

#### 6. 用 benchmark 定界多架构构建优化

Release 跑通后继续分析 25 分钟级耗时，确认主要瓶颈是 x86 GitHub runner 通过 QEMU 执行 arm64 Go compiler。最小方案只把三个 Dockerfile 的 builder 固定为 build host platform，最终镜像仍按目标架构生成。

| 指标 | 基线 | 优化后 | 结果 |
| --- | ---: | ---: | ---: |
| 三个 buildx 命令合计 | 1588 秒 | 308 秒 | 5.16 倍加速 |
| job wall time | 1610 秒 | 331 秒 | 降低 79.4% |
| WorkloadManager arm64 Go build | 1404.5 秒 | 169.4 秒 | 约 8.29 倍加速 |

据此创建 issue #419 与 PR #420。PR 只改 3 个 Dockerfile 的 3 行，不混入 cache、matrix、release metadata 或 PicoD runtime 优化。Week 4 截止时该 PR 已完成验证但仍待 review。

### Review 与测试映射

| 风险 | Review 发现或设计决定 | 验证证据 | 残余风险 |
| --- | --- | --- | --- |
| 删除组件破坏隐藏运行链路 | 先检查源码职责、chart、镜像、e2e、文档和集群对象，再删除 `agentd` | PicoD 单测、`make build-all`、文档构建、残留引用扫描、upstream CI | 未来节点快路径仍需新设计，不能沿用旧组件名掩盖新职责 |
| push CI 与 release 权限混淆 | 普通 branch push 只复用验证 workflow，release/publish 保持隔离 | fork branch 9/9 checks success | 特殊发布和审批 workflow 仍不能由普通 push 覆盖 |
| Proposal 新目录破坏历史链接 | 保留 `docs/design`，proposal README 只提供入口和模板 | 链接检查、文档构建、review 修正 README/template 一致性 | 后续 proposal 生命周期和状态治理仍需社区实践 |
| `latest` 不是合法 Helm chart version | 将 tag、chart version、app version 分开 | 真实 fork main release，镜像与 OCI chart 均成功 | 固定 `0.0.0` 的覆盖语义需继续观察 registry 行为 |
| buildx 优化改变目标镜像架构 | 只改变编译 builder 的执行平台，不改变最终 target stage | 两组 benchmark branch 各 10 个 checks 成功，产物架构与构建结果核对 | PicoD 系统包安装仍受 arm64 模拟影响 |

### 卡点、失败与处理

| 失败步骤 | 现象 | 根因 | 处理与当前状态 |
| --- | --- | --- | --- |
| 判断 release 失败来源 | #415 合并后 main workflow 失败，看起来像新 PR 回归 | 历史 main push 已连续失败，真正原因是 `latest` 不满足 Helm SemVer | 回看历史 run，将验证 CI 与 release CI 分开分析 |
| #416 初版范围 | 准备移除 main release 触发 | 只消除了失败入口，却破坏 latest image 的既有需求 | 根据 maintainer review 改为三类版本元数据分离 |
| 本地复现 Helm package | 初始环境缺少 Helm，无法直接得到完整本地产物 | 工具环境不足，不是代码行为证据 | 先用 workflow 源码和历史日志定根因，再用真实 fork main run 完整验证 |
| 优化 25 分钟 release | 直觉上可能增加 cache 或并行 matrix | 分阶段计时显示 arm64 Go compiler 在 QEMU 下执行才是主瓶颈 | 先做 A/B benchmark，只提交 builder platform 的 3 行最小改动 |

### 开源协作记录

| 对象 | 本人角色 | 周内动作 | Week 4 截止状态 |
| --- | --- | --- | --- |
| AgentCube #403 | author / analyst | 完成组件职责考古、删除、测试与 review 跟进 | 7/1 已合并 |
| AgentCube #414 | designer / author / tester | 设计 fork push CI，验证 9 类 checks | 7/2 已合并 |
| AgentCube #415 | author / reviewer | 建立 proposal 入口与模板，修正一致性问题 | 7/2 已合并 |
| AgentCube #416 | analyst / author / tester | 定位 Helm version 根因，根据 maintainer 意见收敛方案并跑真实 release | 7/3 已合并 |
| AgentCube #419 / #420 | analyst / author / tester | 建立 benchmark、创建 issue、提交 3 行性能修复 | #419 已建；#420 待 review |

### 本周形成的可复用工程判断

1. **架构兼容要分层。** API 路径相似不等于 SDK、生命周期和错误语义兼容；没有 conformance 证据就降低对外口径。
2. **慢控制面与快数据路径要按更新频率拆。** CRD 适合聚合和策略，不适合承载每个 sandbox 的高频状态抖动。
3. **删除代码前先证明生产不可达。** 搜索引用只是起点，部署、镜像、测试和运行时对象流都要核对。
4. **维护者反馈优先校正需求，不只校正语法。** #416 的关键 review 是“latest image 仍需发布”，它改变了方案边界。
5. **性能 PR 必须先有对照实验。** 基线、变量控制、产物正确性和残余瓶颈都明确后，才知道 3 行修改是否足够。

### 证据索引

| 结论或工作流 | 本地证据 |
| --- | --- |
| E2B 协议面、L0-L4 兼容等级与差距 | [Day33：E2B 协议面与 Agent 时代 Docker 调研](day33-e2b-protocol-and-agent-era-docker-study.md) |
| fork branch push CI 设计与 9/9 验证 | [Day34：AgentCube Push CI 工作流方案与 PR 准备](day34-agentcube-push-ci-workflow-pr-prep.md) |
| AgentCube 架构迭代结论 | [Day35：三期会议后的新架构结论](day35-agentcube-architecture-iteration-conclusion.md) |
| Kubernetes 慢资源控制面、Template/Pool 职责 | [Day36：K8s 慢资源控制面深入设计](day36-k8s-slow-resource-control-plane-design.md) |
| Proposal 目录与模板治理 | [Day37：Docs Proposal 目录设计](day37-docs-proposal-directory-management.md) |
| Release Helm version 根因、修正与真实验证 | [Day38：Release Image CI Helm Chart Version 失败分析](day38-release-image-ci-helm-chart-version-failure-analysis.md) |
| buildx A/B benchmark 与 PR #420 scope | [Day39：Buildx 性能优化机会](day39-karmada-image-build-and-agentcube-buildx-performance-optimization.md) |
| `agentd` 职责与删除依据 | [Day29：`agentd` 组件作用分析](day29-agentd-component-role-analysis.md) |

### 一句话总结

Week 4 把架构讨论变成了可审查的边界，把 CI、proposal、release 和构建性能问题变成了有根因、有最小改动、有真实验证、也有明确残余风险的工程闭环。
