# Week 2 总结：从写代码转向审代码与工程判断

日期：2026-06-15 至 2026-06-23

## 核心转变

Week 2 最大的收获不是“写了多少代码”，而是把实习定位从单纯开发转成开源工程参与能力训练：

> 可以假设以后自己一行代码都不写，只负责审代码。核心能力就变成：拆分需求、写清楚设计、判断架构边界、理解代码目录如何落地、审查实现、设计测试、判断 CI/CD 和社区协作是否规范。

这意味着后续实习报告不能只记录“我改了哪些文件”。更重要的是记录：

- 需求如何拆分，哪些部分应该做，哪些部分不应该混在同一个 PR。
- 架构边界如何划分，模块职责是否清楚。
- 代码目录和依赖方向是否符合项目已有结构。
- 测试是否分层，是否覆盖成功路径、失败路径、并发路径和 cleanup。
- CI/CD 是否能证明变更可靠，是否存在只靠编译通过的假安全感。
- PR 是否尊重社区协作规范，是否足够小、可解释、可 review。

换句话说，写代码只是整个链路里的一个环节：

```text
拆分需求 -> 写文档 -> 设计架构 -> 代码目录落地 -> 写代码 -> 审代码 -> 测试
```

AI 可以参与写文档和写代码，但不能替代人的工程判断。后续周总结要重点沉淀可复用的审查框架和工程规范，而不是纠结“代码是不是我手写的”。

## 本周实际完成

| 方向 | 结果 | 复用价值 |
| --- | --- | --- |
| 开源贡献规范 | 整理 AgentCube issue / PR 讨论格式、PR 管理规范、fork / upstream 分支规则，并沉淀为本地 skills | 后续每次参与社区前先过模板、分支、测试和用户确认 gate |
| PR #385 WarmPoolAvailable | 提交第一个 upstream PR，并根据 CI / Codecov / Gemini 反馈调整实现和测试 | 学会把小功能拆成可 review 的控制器状态、单测和 PR 说明 |
| SnapStart / benchmark 讨论 | 阅读 #365 / #366 / #379，发布有本地数据支撑的 benchmark 评论 | 学会区分“我测到了什么”和“我不能证明什么”，避免夸大结论 |
| Agent-sandbox compatibility | 从 issue #386 出发，溯源 agent-sandbox 版本升级、warm pool adoption、NetworkPolicy、codegen、e2e 和 math-agent 验证 | 学会用版本演进和测试结果驱动适配，而不是只看编译错误 |
| Go/toolchain prerequisite | 把 Go 升级拆成独立 PR #391，先证明原始项目在新 Go 下可运行，再让依赖升级 PR rebase | 学会拆出独立前置条件，保持 upstream PR 干净 |
| PR #387 review 准备 | 按文件/行级别整理每个变更为什么改、为什么这样改、测试覆盖是什么 | 形成 code rationale matrix，支持后续 review 答辩 |
| Sleep/Resume 设计 | 从 FAUST-BENCHOU 的 proposal 出发，拆成设计、spike、Store CAS、WorkloadManager lifecycle service 四层 | 学会在架构未完全定稿前，只实现高确定性的基础层，并用测试验证设计假设 |
| 竞品和架构学习 | 学习 CubeSandbox、Karmada、OpenSandbox、Agent Substrate，并回看 AgentCube 自身 Router / WorkloadManager / Store | 学会从成熟项目抽取架构边界、控制面职责和测试纪律 |

## 可复用能力沉淀

### 1. 需求拆分能力

本周最重要的工程判断之一是：不要把所有相关问题都塞进一个 PR。

典型例子：

- `agent-sandbox v0.4.6` 适配需要 Go 1.26，但 Go/toolchain 升级本身是独立前置条件。
- 正确做法是先从 `upstream/main` 提纯净 Go 升级 PR #391，证明原始项目能 build/test/lint/e2e。
- 等 #391 合并后，再让 #387 rebase 到新 main。

这个模式可复用为：

```text
如果 A 功能依赖 B 基础变更，
并且 B 对原始项目本身也成立，
那么 B 应拆成独立 PR，
A 只保留自己的 feature/fix 语义。
```

审代码时要问：

- 这个 PR 是否混入了前置条件、清理、工具链修复、格式化和新功能？
- 哪些改动可以单独证明？
- 哪些改动必须和当前功能一起提交？

### 2. 架构边界判断

Sleep/Resume 的处理给了一个清楚样例：架构未最终敲定时，不应该直接把 Router、GC、Store、WorkloadManager、agent-sandbox provider、CRD、SDK 和 e2e 全部一起改。

更稳的拆法是：

1. 设计 session lifecycle contract。
2. 用 spike 验证状态机、CAS 和并发假设。
3. 第一阶段落 Store 状态、CAS 和 indexes。
4. 第二阶段落 WorkloadManager lifecycle service 和 fake provider tests。
5. 后续再接 GC split、Router resume-before-proxy、真实 agent-sandbox provider 和 e2e。

这个拆法背后的架构原则是：

- Store 只负责状态和原子更新。
- WorkloadManager 负责生命周期编排。
- Router 不应理解底层 runtime pause 细节，只做 owner check、resume-before-proxy 和 proxy。
- RuntimeProvider 隔离 `replicas=0/1`、`OperatingMode=Suspended/Running`、soft pause、snapshot pause 等底层差异。

这接近整洁架构的思路：核心业务规则和外部 runtime 细节隔离，依赖方向从业务抽象指向 provider 接口，而不是把 Kubernetes 字段散落进 Router / Store / SDK。

### 3. 代码审查能力

本周开始形成 code rationale matrix 的习惯。审查一个 PR 时，不只看 diff 是否能编译，而是逐文件回答：

| 审查问题 | 目的 |
| --- | --- |
| 这个文件为什么必须改？ | 防止无关 cleanup 混入 feature/fix |
| 改动是项目需要，还是本地环境需要？ | 防止把本地 workaround 提到 upstream |
| 是否改变了公共 API / CRD / generated code？ | 判断是否需要 codegen 和兼容性说明 |
| 是否改变运行语义而不只是编译语义？ | 防止“编译通过但运行不通” |
| 失败路径怎么处理？ | 避免只测 happy path |
| 并发或重复请求时是否安全？ | 对 controller、store、router 特别关键 |
| cleanup 是否完整？ | 避免 Kubernetes 资源、Store 状态、port-forward 或 warm pool 残留 |

PR #387 的经验尤其重要：小到只有几行的文件改动，也需要解释为什么存在。例如 `hack/update-codegen.sh` 看起来只是脚本调整，但它关系到 codegen 是否会扰动依赖版本；`test/e2e/e2e_test.go` 看起来删改多，但本质是在适配 warm-pool ownerRef 链变化。

### 4. 分层测试能力

本周反复验证了一个规则：编译通过不等于功能可用，e2e 通过也不等于测试充分。

更合理的测试层次是：

| 层次 | 用途 | 例子 |
| --- | --- | --- |
| Unit | 验证局部逻辑、状态迁移、失败路径 | Store CAS、WorkloadManager lifecycle service fake provider tests |
| Race / concurrency | 验证并发路径 | 并发 resume 只能一个成功 |
| Static / lint / codegen | 验证代码规范和生成文件一致 | `make lint`、`make gen-check` |
| Package integration | 验证相关包组合编译和单测 | `go test ./pkg/store ./pkg/workloadmanager` |
| E2E | 验证真实组件链路 | direct/warm-pool CodeInterpreter、SDK、MCP |
| LLM e2e | 验证真实 agent 使用场景 | math-agent 使用 OpenAI-compatible provider |
| Cleanup check | 验证资源最终状态 | Pod、Sandbox CR、SandboxClaim、Store、warm pool refill |

后续审 PR 时，应该把测试写成“风险 -> 测试”的映射，而不是只列命令。

### 5. CI/CD 和社区协作规范

本周踩过并修正的规范：

- 不用 upstream PR 当一次性 CI runner；优先用 fork PR / fork Actions / 本地测试。
- fork branch push 不一定触发完整 PR workflow，需要 fork PR，base 选择 `main` 或 `release-*`。
- upstream PR 即使是 draft / WIP 也要使用官方 PR 模板。
- 未完成 upstream PR 使用 `[WIP]`，不要写 `[DO NOT MERGE]`。
- 提 upstream PR、comment、review comment、request review、mention maintainer 前必须先让用户确认完整内容。
- 不要在一个 PR 里不断累积无关任务；但当前 PR 引入的问题可以在验证后 clean update。
- 对 AI reviewer / bot 评论要分类处理，不能当 maintainer consensus。

这些规则比单次代码修改更重要，因为它们决定开源协作是否可持续。

## 本周主要卡点

| 卡点 | 结论 |
| --- | --- |
| kind 标准集群失败 | 当前 CentOS 8 / kernel 4.18 / cgroup v1 环境不适合继续硬调 kind；应换 cgroup v2 / 新内核 / 云 K8s |
| KVM/MicroVM 不能测 | 当前机器没有 `/dev/kvm`，不能证明 Kuasar / Firecracker / CubeSandbox PVM 的真实路径 |
| agent-sandbox 版本演进复杂 | 不能只说“升级最新版”；需要区分 v0.4.6 stable、v0.5.0rc1 / v1beta1、CRD storedVersions 和 runtime behavior |
| 编译通过不代表运行通过 | #386 / #387 已证明 warm-pool adoption、NetworkPolicy、e2e manifest、math-agent 都可能暴露编译外问题 |
| 周总结不能只写成果 | 要记录失败命令、错误现象、原因和绕过方式，方便后续审查和复盘 |

## 后续周总结写法

后续每周 summary 应该固定回答这些问题：

1. 本周拆了哪些需求？哪些被拆出，哪些被合并，依据是什么？
2. 本周学到哪些架构边界？是否符合整洁架构的依赖方向和模块职责？
3. 本周审了哪些代码？发现的问题属于 correctness、scope、test、CI、style 还是 community process？
4. 本周设计了哪些测试？每个测试覆盖哪个风险？
5. 本周 CI/CD 或开源协作踩了什么坑？规则如何固化到 `AGENTS.md` / skills？
6. 哪些结论有代码证据、测试证据或上游讨论链接？哪些只是推测？
7. 下周如果只做 review，不写代码，最值得推进的 review / design / test plan 是什么？

这会让实习报告从“流水账”变成可复用的工程判断训练记录。
