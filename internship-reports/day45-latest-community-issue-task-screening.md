# Day45：AgentCube 最新社区 Issue 可接手任务筛选

日期：2026-07-10

本轮目标是检查 AgentCube 社区最近的 open issues，寻找可以由我们独立接手、不会和现有贡献者重复、并且能在当前环境完成验证的任务。本轮只做 GitHub 只读调查和本地记录，没有执行 `/assign`、issue/PR 评论、review、maintainer mention 或创建 PR。

> 注释：本文中的“最新”是 2026-07-10 通过 GitHub API 查询到的社区快照。Issue assignee、PR 和讨论状态会变化，真正认领前必须重新查询一次。

## 一句话结论

**最近新增的 open issues 中，没有一个同时满足“无人认领、无活跃 PR、范围明确、当前机器可验证”四个条件，因此本轮不建议抢一个新的实现任务。**

最接近可贡献状态的是 #433 的 Helm/RBAC/auth 验证，但它已经有明确作者和对应 issue assignee，只能作为测试或 review 协作，不应另开实现 PR。较老的 #272 仍有 release-policy 后续空间，但与 open PR #249 和既有 #271 stopgap 有交叉，必须先由维护者澄清拆分范围，不能直接认领代码。

> 分析：筛选结果为“零强候选”并不代表本轮没有产出。及时识别重复工作、已修复但未关闭的 stale issue、需要专用环境的 benchmark，以及只适合讨论的 umbrella issue，本身就是开源任务管理能力。

## 筛选标准

本轮把“可以接手”定义为同时满足以下条件：

1. Issue 当前没有 GitHub assignee，也没有有效 `/assign` 信号。
2. 没有对应的 open PR，也没有活跃贡献者已经在同一实现范围内推进。
3. 问题边界足够小，可以说明要改哪些模块、哪些行为不在范围内。
4. 当前机器能够验证关键风险；不能把缺少 KVM、Kuasar、标准 Kubernetes 或发布权限的问题包装成已验证贡献。
5. Issue 不是单纯 discussion、question、umbrella tracker 或已经由 merged PR 修复但尚未关闭的 stale item。
6. 对安全、发布、API contract 等方向，维护者已经给出足够明确的预期，或者可以先形成 focused proposal 再进入实现。

> 注释：`PR 认领 @` 不能只看 issue 的 assignee 字段。还要查 `/assign` 评论、PR body 的 `Fixes #...` / `Refs #...`、PR 作者、changed files 和最近更新时间。

## 数据基线与查询方法

本轮先读取根目录 `PROGRESS.md`，提取已在跟进或明确不要重复的线程，然后使用 issue discussion skill 的紧凑脚本读取候选完整上下文。

核心查询包括：

```bash
gh api --paginate \
  "repos/volcano-sh/agentcube/issues?state=open&per_page=100&sort=created&direction=desc"

gh api --paginate \
  "repos/volcano-sh/agentcube/pulls?state=open&per_page=100&sort=created&direction=desc"

python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 432
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 433
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 430
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 431
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 386
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 365
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 348
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 272
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 249
```

随后执行 `git fetch upstream main`，只更新远端引用，不切换或 rebase 当前 `intern` 分支。最新观测到的 `upstream/main` 是 `eee8aea`，即 PR #423 的 merge commit。

> 分析：本地 `intern` 分支用于实习记录，不应为了读最新源码就混入 upstream rebase。通过 `git show upstream/main:<path>` 和 `git merge-base --is-ancestor` 可以在不改变工作分支历史的情况下核对上游代码。

## 最近 Open Issue 快照

以下表格覆盖 2026-06-01 之后创建、截至本轮仍 open 的 issue。它们是“最近任务”判断的主要集合。

| Issue | 创建时间 | PR 认领 @ | 关联 open PR / 活跃线程 | 筛选结论 |
| --- | --- | --- | --- | --- |
| [#432](https://github.com/volcano-sh/agentcube/issues/432) WorkloadManager chart 未启用 auth | 2026-07-09 | `avinxshKD` | [#433](https://github.com/volcano-sh/agentcube/pull/433) | 排除：已 `/assign` 且已有 focused PR |
| [#430](https://github.com/volcano-sh/agentcube/issues/430) 快慢资源双轨架构讨论 | 2026-07-08 | 无 | [#431](https://github.com/volcano-sh/agentcube/pull/431) | 排除：discussion，不是直接实现单；slow track 已有 proposal 作者 |
| [#408](https://github.com/volcano-sh/agentcube/issues/408) landing page | 2026-06-27 | `vanshika2720` | #409 | 排除：已有 assignee 和 PR |
| [#406](https://github.com/volcano-sh/agentcube/issues/406) user client token cache | 2026-06-27 | `avinxshKD` | #407 | 排除：已有 assignee 和 PR |
| [#404](https://github.com/volcano-sh/agentcube/issues/404) contributor docs | 2026-06-25 | `vanshika2720` | #405 | 排除：已有 assignee 和 PR |
| [#397](https://github.com/volcano-sh/agentcube/issues/397) CodeInterpreter authMode default | 2026-06-22 | `avinxshKD` | #398 | 排除：已有 assignee 和 PR |
| [#395](https://github.com/volcano-sh/agentcube/issues/395) Python AgentRuntime delete session | 2026-06-19 | `nabrahma`、`vivek41-glitch` | #426 | 排除：两名 assignee 且已有 PR |
| [#394](https://github.com/volcano-sh/agentcube/issues/394) Python SDK TTL 被忽略 | 2026-06-19 | `kavyarathod05`、`vivek41-glitch` | issue 内两次 `/assign` | 排除：已有明确认领者，即使暂未发现 focused PR 也不能抢 |
| [#388](https://github.com/volcano-sh/agentcube/issues/388) Router longest path prefix | 2026-06-17 | `avinxshKD` | #389 | 排除：已有 assignee 和 PR |
| [#386](https://github.com/volcano-sh/agentcube/issues/386) v0.2.0 Call for proposals | 2026-06-15 | 无 | umbrella discussion；我们的 #429 仍 open | 排除：当前 checklist 已 triage 项均完成或已有负责人，没有裸露的 focused task |
| [#381](https://github.com/volcano-sh/agentcube/issues/381) logo/favicon/visual assets | 2026-06-07 | `safiya2610` | 活跃设计线程 | 排除：已有 assignee，且不是当前工程主线 |
| [#375](https://github.com/volcano-sh/agentcube/issues/375) TokenCache JWT `exp` | 2026-06-04 | `HarshitPal25` | 已表达实现 ownership | 排除：安全 bug 已认领 |
| [#374](https://github.com/volcano-sh/agentcube/issues/374) SPIRE 初启 Pod restart | 2026-06-02 | `avinxshKD` | 已认领 | 排除：已有 assignee，且需要 mTLS/SPIRE 环境 |
| [#365](https://github.com/volcano-sh/agentcube/issues/365) SnapStart benchmark | 2026-05-27 | 无 | #366 / #379 由 `lyuyun` 推进 | 排除：benchmark 被明确绑定到现有 SnapStart 路径；本机也缺 Kuasar/KVM 验证环境 |
| [#362](https://github.com/volcano-sh/agentcube/issues/362) SandboxReconciler unit tests | 2026-05-27 | `Maximus-08` | #371 | 排除：已有 assignee 和 PR |

> 分析：只看 assignee 会误判 #430、#365 和 #386。三者的 assignee 都为空，但分别是已有 proposal 的 discussion、依赖活跃设计/实现 PR 的 benchmark tracker，以及需要先 triage 子任务的 umbrella issue。

## 重点线程分析

### #432 / #433：最新安全修复，但已有人完整推进

#432 指出 Helm chart 没有给 WorkloadManager 传 `--enable-auth`，导致部署后 auth middleware 处于跳过状态。作者 `avinxshKD` 在创建 issue 后立即执行 `/assign`，约 22 分钟后创建 #433。

#433 的改动面是：

- `manifests/charts/base/templates/workloadmanager.yaml`
- `manifests/charts/base/templates/rbac-router.yaml`
- `manifests/charts/base/values.yaml`

PR 不只增加 auth flag，还补 Router service account 在启用 caller-token 路径后所需的最小 sandbox create/delete RBAC。Gemini 提出的 ClusterRole 范围过大问题已由作者响应并更新为 namespace-scoped 权限。

本轮查询 #433 checks 时观察到：build、coverage、e2e、lint、Python checks 和 DCO 均成功，只有 `tide` 因缺少 `lgtm` / `approved` pending。

作者在 PR body 中明确记录本地没有 Helm，因此没有运行 `helm template` / `helm lint`。这形成了一个有价值的**协作验证点**，但不构成另开实现 PR 的理由。

> 分析：安全问题优先级高不等于可以覆盖原作者。正确协作方式是验证 rendered args、Role/RoleBinding namespace、Router token 和 WorkloadManager auth 的端到端关系，再把证据作为 review feedback；本轮没有执行该 review，也没有发表评论。

### #430 / #431：架构 review 主线，不是新的 ownership 任务

#430 由 collaborator `RainbowMango` 发起，目标是把 Kubernetes 管理资源的慢路径与 AgentCube 管理 session 的快路径分开。Issue 明确邀请 proposal，不是已经切分好的实现任务。

#431 已由 `lichuqiang` 提交 644 行 SandboxPool management proposal，覆盖 slow resource track。真人 MEMBER `acsoto` 已提出 SandboxPool 与现有 WarmPool 两代架构关系问题；我们已经在 Day44 对 stale status 和 Static Pod/native in-place resize compatibility 提出两条有证据的 review comment。

因此 #430 当前可做的是继续理解/评审 proposal 或等待 fast-track 子问题被正式切出，而不是对 slow track 再开竞争 proposal。

> 注释：AI reviewer 对 #431 的 SSA、`omitempty`、状态机等意见是检查线索，不能代替 maintainer 对架构方向的共识。

### #386：欢迎 proposal，但当前没有现成子任务

#386 是 v0.2.0 umbrella issue。当前 body 中已经列出的 security、cleanup、testing 和 CI 项均已打勾，包括：

- Dependabot Docker base image updates #422
- runner pinning #423
- Go 1.26.4 baseline #391
- remove agentd #403
- fork push CI #414
- proposal template #415
- chart workflow fix #416
- multi-arch image performance #420

Sleep/Resume 虽未进入 checklist，但 MEMBER `FAUST-BENCHOU` 已明确表示如果接受愿意接手。agent-sandbox compatibility 已由我们的 #387 推进。Go toolchain scheduled update 也已有我们的 #429 open PR。

所以 #386 的“无 assignee”不能解释为“里面的方向都无人做”。若继续在这里提出任务，应该是一个新的、边界明确且不与 #429/#387/Sleep-Resume owner 重叠的 proposal，并等待 maintainer triage 成 dedicated sub-issue。

### #365：无 assignee，但验证条件不成立

#365 已由 MEMBER `acsoto` 明确定位为 #366 SnapStart proposal 的 supporting benchmark tracker，而不是独立 Firecracker backend。近期路径应先 review/refine #366，再定义 N-way fan-out、snapshot restore、fallback 和 memory/throughput benchmark。

本机没有 `/dev/kvm`，也没有可用的 Kuasar WarmForkSnapshot 环境。当前能做的只有 benchmark schema、fake-provider test plan 或源码 review，不能声称完成真实 SnapStart benchmark。

> 注释：`/dev/kvm` 是 Linux 暴露硬件虚拟化能力的设备入口。缺少它时，MicroVM 或依赖硬件虚拟化的 snapshot/restore 数据不能作为真实产品性能证据。

## 反例核验：#348 看似完美，实际已经修复

#348 表面上非常像可接手任务：

- `kind/bug`
- 无 assignee
- 无评论
- 单文件测试修复
- 当前机器可重复运行 Go unit test

但是当前 `upstream/main` 的 `pkg/router/jwt_test.go` 已经使用：

```go
assert.True(t, manager.privateKey.Equal(privateKey))
```

而不是 issue 所描述的直接深比较。继续追历史后确认：

- commit `723d732`：`test: fix flaky router private key PEM test`
- 对应 merged PR：[#378](https://github.com/volcano-sh/agentcube/pull/378)
- merged at：2026-06-08
- `git merge-base --is-ancestor 723d732 upstream/main` 返回成功

#348 只是没有被 PR body 自动关闭，已经没有实现工作可接。最多可以在用户确认后留一条 triage comment，附 #378 并建议关闭。

> 分析：这是本轮最重要的反例。GitHub issue 的 OPEN 状态不是源码事实；接手前必须检查当前代码、相关 commit 和 PR association，否则很容易提交重复修复。

## 较老 Backlog 备选：#272 仍需先协调

#272 由 MEMBER `acsoto` 提出 Python CLI/SDK release policy：稳定包应只由 AgentCube release tag 发布，开发构建使用 TestPyPI 或唯一 `.devN` 版本，并希望 CLI/SDK 有统一版本 source of truth。

当前代码状态说明该问题只解决了一部分：

- #271 已把 Python CLI/SDK publish workflow 限制为 `v*.*.*` tag，停止 main push 发布。
- 两个 `pyproject.toml` 当前仍分别硬编码 `0.1.0`。
- open PR #249 正在单独修改 SDK version，并已有 `lgtm`、assignees 和多轮维护者讨论。
- #272 自创建以来没有评论，没有明确把“version source unification”切成独立 sub-issue。

因此 #272 是一个有价值的旧 backlog，但不是本轮可直接认领的任务。合理顺序应是先询问维护者：#249 是否继续、关闭或被新 policy supersede；随后再决定是否拆一个只负责 source-of-truth / tag-version validation 的 focused issue。

> 分析：发布治理属于跨 CLI、SDK、tag 和 PyPI 不可变版本约束的契约。直接改两个版本字符串很容易重复 #249，却没有真正定义 release policy。

## 候选分级

| 等级 | 候选 | 可以做什么 | 为什么现在不直接接手 |
| --- | --- | --- | --- |
| A：直接认领 | 无 | 无 | 最近 issue 没有同时通过四项 gate |
| B：协作验证 | #433 | Helm render/lint、RBAC namespace、auth-enabled request path 验证 | #432 已认领且 #433 活跃；只能帮助原作者 |
| B：继续既有 review | #431 | 等作者回应 Static Pod resize；必要时继续基于证据 review | 已是 Day44 主线，不是新任务；不能堆评论 |
| C：先协调再拆分 | #272 | Python package version source / tag validation policy | #249 open 且维护者讨论未收敛 |
| D：环境阻塞 | #365 | benchmark schema / test plan | 本机缺 Kuasar/KVM，真实 benchmark 不成立 |
| STALE | #348 | 建议关联 #378 后关闭 | 修复已于 6 月合入 |

## 本轮推荐决策

1. **现在不要 `/assign` 新 issue。** 没有 A 级候选，强行选择只会造成重复或低可信验证。
2. **把 #433 保留为可选的 review/test 协作。** 如果后续要做，应先拉取 PR head，在临时 worktree 运行 Helm render/lint 和 focused auth/RBAC 检查，再决定是否有值得反馈的新证据。
3. **继续等待 #431 当前 resize thread 回复。** 不在架构问题尚未回答时追加 RuntimeClass/CRI 等新评论。
4. **#272 只作为未来 backlog。** 必须先确认 #249 的去留和 maintainer 期望，再谈 focused issue/PR。
5. **优先消化现有 open PR，而不是累积 ownership。** #429、#387、#385 仍 open；本轮发现 #420、#422、#423 已合并，应更新本地任务状态。

> 分析：开源贡献不是以“同时占有多少 issue”为目标。当前更高价值的行为是让已有 PR 进入 review、保持 proposal review 质量，并等待社区切出真正没有 owner 的子任务。

## 过程阻塞与调试记录

### GitHub API 初次访问失败

失败步骤：第一次在受限网络环境运行 `gh api` 查询 open issues / PRs。

观察到的错误：

```text
error connecting to api.github.com
check your internet connection or https://githubstatus.com
```

原因：当时执行环境的网络 sandbox 禁止直接访问 GitHub API，不是 GitHub repository 或 token 错误。

解决：按工作区权限流程切换到允许的只读 GitHub API 查询后重试，issue/PR 元数据与 thread brief 均成功返回。整个过程中没有输出 token。

### `gh pr checks 433` 返回 exit code 8

观察：命令列出的 build、coverage、e2e、lint、DCO 等实际 checks 全部 `pass`，但命令退出码是 8。

原因：`tide` 仍是 pending，缺少 `lgtm` / `approved`。这是 merge gate 未满足，不是测试失败。

解决：报告中把“实际验证 checks”与“合并审批 gate”分开描述。

### #348 搜索一度没有找到 PR

失败路径：用 PR 文本搜索 `348 OR TestGetPrivateKeyPEM` 没有结果。

原因：merged PR #378 的文本没有稳定的 `#348` 关联，GitHub 文本搜索不能证明“没有 PR”。

解决：从 git history 找到 `723d732`，再查询 commit association API，定位到 merged PR #378，并验证该 commit 是 `upstream/main` 祖先。

> 分析：文本搜索适合发现候选，不适合证明不存在。需要把 issue metadata、代码现状、git history 和 commit-to-PR association 组合起来。

## 可复用工程判断

1. **Issue open 不等于 bug still exists。** 代码和 merge history 是行为事实来源。
2. **Assignee empty 不等于无人推进。** Discussion、benchmark tracker、umbrella 和 proposal PR 都可能有实际 owner。
3. **PR checks pass 不等于可合并。** Prow 项目还需要 `lgtm`、`approved` 和 tide gate。
4. **环境不满足时，不把设计稿当 benchmark。** #365 的真实 snapshot/restore 数据必须来自可运行 Kuasar/KVM 的环境。
5. **已有作者缺测试环境时，优先提供验证证据。** 这比另开重复 PR 更符合社区协作边界。
6. **跨包 release policy 要先定义契约。** 版本 source、tag、PyPI stable/pre-release 和不可重用 artifact 必须一起考虑。

## 下一步与停止条件

下一次筛选前先重新抓取 open issue / PR 元数据。只有出现新的 A 级候选，或 maintainer 将 #386/#272 中的方向拆成 dedicated sub-issue，才建议进入 `/assign` 文本准备。

本轮停止条件已经满足：最近 issue 全部完成 assignee、PR、讨论类型、环境和 stale-code 交叉核验；没有授权进行上游写操作；因此到此停止，不为了“必须找到一个任务”而降低认领标准。

## 2026-07-16 主动 freshness scan

用户要求后续不要依赖人工转述社区新进展。19:39 CST 只读扫描 `2026-07-10` 之后新建的 AgentCube issues，并逐项交叉 assignee、`/assign` 和同主题 PR：

| Issue | 表面状态 | 交叉结果 | 决策 |
| --- | --- | --- | --- |
| [#438](https://github.com/volcano-sh/agentcube/issues/438) agent-sandbox v0.5.2+ | assigned `@safiya2610` | maintainer 要求等待尚未发布的 v0.5.2；无 linked PR | 不竞争实现，后续做 migration/lifecycle/E2E review |
| [#434](https://github.com/volcano-sh/agentcube/issues/434) CLI cloud build | 无 assignee、无 issue comment | issue 作者已提交 [PR #435](https://github.com/volcano-sh/agentcube/pull/435)；DCO fail、5 条 current active AI thread、无真人 review | 已有 active owner，不认领；可作为后续验证型 review 候选 |

结论：本次没有可无冲突认领的新 issue。#434 证明“无 assignee”不是充分条件；社区扫描必须同时搜索 `Fixes #N`、issue URL、同主题 title/head branch 和 cross-reference。

> 注释：freshness scan 是只读任务发现机制，不授权自动 `/assign`、评论或请求 reviewer。任何 upstream-facing 动作仍需用户确认 exact target/text。

## 2026-07-17：最近 issue / PR 的问题发现来源复盘

本轮问题不是“最近还有哪个 open issue 可以抢”，而是更基础的能力缺口：如果 mentor 没有直接给出特性，如何自己从仓库运行和工程合同里发现值得做的工作。

先说明证据边界：公开记录能证明作者看到了什么代码、给了什么复现、issue 与 PR 相隔多久，以及 maintainer 后续怎样校准方案；通常不能证明作者私下到底运行了哪条搜索命令。因此下文把 issue 正文、PR、review 和源码称为**事实**，把“最可能的问题发现路径”明确称为**重建或推断**。

> 分析：成熟贡献者通常也不是坐在那里“想一个功能”。他们站在一条具体表面上，例如失败的 CI、可运行示例、SDK 字段、缓存、两条平行创建路径或刚合并 PR 的遗留范围，然后寻找“承诺与真实行为不一致”的地方。

### 案例总表

| 案例 | 公开事实 | 最可信的问题来源重建 | 我们可复制的探针 |
| --- | --- | --- | --- |
| [#438](https://github.com/volcano-sh/agentcube/issues/438) agent-sandbox v0.5.2+ | #387 明确把 v0.5.x / v1beta1 migration 留作独立 follow-up；#387 合并约 25 分钟后 maintainer 创建 #438，并直接引用 migration guide 与 warm-claim upgrade fix | 合并 PR 的 scope boundary + 上游 release 监听 | 每次 PR 合并后提取 `follow-up`、版本 pin、non-goal、review 遗留和 migration 缺口；依赖正式发布时重新触发 |
| [#434](https://github.com/volcano-sh/agentcube/issues/434) cloud build | `_build_cloud` 有显式 TODO，实际回退 local；设计文档也写 placeholder；同作者 7 分钟后开 #435 | TODO / placeholder + 文档和代码承诺不一致 | `rg 'TODO|FIXME|placeholder|not implemented|falling back'`，再证明路径真实可选、不是死代码 |
| [#432](https://github.com/volcano-sh/agentcube/issues/432) chart auth | 二进制有 `--enable-auth`，Helm 没传，middleware 在 false 时跳过；同作者 22 分钟后开 #433 | flag/default -> Helm -> middleware -> RBAC 的跨层配置审计 | 给 auth、TLS、RBAC、timeout、feature gate 建 flag/values/template/runtime/permission 矩阵 |
| [#430](https://github.com/volcano-sh/agentcube/issues/430) control-plane decoupling | issue 把一次 session 创建拆成 CR -> reconcile -> Pod -> scheduler -> kubelet -> pull -> microVM，并讨论短生命周期 burst 下的 etcd 写入、idle 浪费和容量耦合 | 对热路径做目标规模乘法，而非从某个小 bug 外推 | 数 API call、持久对象、controller hop、调度与 status write，再乘 burst/QPS/生命周期；先区分架构假设和实测瓶颈 |
| [#419](https://github.com/volcano-sh/agentcube/issues/419) multi-arch build | #416 修通后继续观察到 image step `1487.1s`、arm64 Go build `1291.4s`；单变量 A/B 得到总时间 `1588s -> 308s` | 在“功能成功”之后继续看二阶指标，定位 CI 长尾 | 每次 workflow 记录 top-3 step duration；画 host/build/target platform 矩阵并做单变量 A/B |
| [#417](https://github.com/volcano-sh/agentcube/issues/417) Helm `latest` | 主干 run 明确报 `chart.metadata.version "latest" is invalid`；同一 `TAG` 同时流向 Docker tag 与 Helm SemVer | 从主干红灯沿 workflow 变量扇出追到两个不兼容合同 | 对一个变量列出所有消费者，检查格式、唯一性、可变性；覆盖 branch/tag/PR event 矩阵 |
| [#401](https://github.com/volcano-sh/agentcube/issues/401) Codegen false pass | #393 才暴露 #367 引入的多余 `go.sum`；#367 的绿色 job 只有 5 秒，关键步骤实际 skipped；path filter 漏了 `go.mod/go.sum` | 审计“绿色 CI 是否真的执行”，并追命令的依赖闭包 | 不只看 conclusion；检查 step execution、异常短耗时、path filters，以及 `make gen-check` 实际读写哪些文件 |
| [#406](https://github.com/volcano-sh/agentcube/issues/406) token cache | cache key 只有 namespace + service account，但 cached client 固化首次 bearer token；同 key 换 token 仍复用旧 client | cache identity 没覆盖可变安全输入 | 对每个 cache 列 key、value 固化字段、expiry、invalidation；保持 key 不变轮换 token/config/permission |
| [#397](https://github.com/volcano-sh/agentcube/issues/397) authMode default | CRD/default 为 `picod`；direct path 用 `== picod`，warm path 用 `!= none`；作者在 PR 讨论中说检查两条 auth path 时发现 | 平行路径行为不一致 + default/zero-value 边界 | 对 absent、zero、explicit default、non-default 做矩阵，并横向比较 direct/warm、SDK/controller |
| [#395](https://github.com/volcano-sh/agentcube/issues/395) AgentRuntime delete | AgentRuntime SDK 能 create，但 `close()` 只关本地连接；CodeInterpreter 已有 server-side `stop()`；后端 delete route 已存在 | 同类组件的生命周期不对称 | 建 create/attach/invoke/close/stop/delete/context-exit 矩阵，区分 owned 与 attached resource |
| [#394](https://github.com/volcano-sh/agentcube/issues/394) SDK TTL | SDK 发送 `ttl=60`，Go DTO 无此字段，Gin 丢弃；真实集群 Redis expiry 仍约 8h | 实际使用产品 + producer/consumer 字段链断裂 | SDK 参数 -> JSON -> DTO -> builder -> Store/status 全链追踪，用明显区别默认值的 sentinel 验证 |
| [#388](https://github.com/volcano-sh/agentcube/issues/388) Router prefix | Router 遇到第一个 `HasPrefix` 就返回；`/`、`/api` 顺序影响 `/api/foo`，`/api2` 也误匹配 | 阅读选择算法时检查顺序、重叠和边界 | 测输入顺序置换、最长匹配、精确边界、相邻字符串、根/空值和 tie |
| [#436](https://github.com/volcano-sh/agentcube/pull/436) macOS path test | maintainer 在 Darwin arm64 上运行 focused test；`/var` canonicalize 为 `/private/var`，生产代码不需修改 | 换一个受支持 OS 运行测试，发现测试假设而非产品 bug | 对 path、权限、shell、line ending、architecture 做跨平台 focused test；保留 before/after 真实输出 |
| [#437](https://github.com/volcano-sh/agentcube/pull/437) runnable examples | maintainer 实际运行 AgentRuntime / PCAP examples，发现缺 echo server/health probe、Router service address 错；无独立 issue | 把自己当首次用户，严格执行仓库示例 | 从 clean environment 逐步执行 README；核对 manifest、Service DNS、probe、payload、response、404 和 cleanup |

### 这些案例不是同一种“想到”

可以把来源压成五组：

1. **真实运行信号**：#394、#417、#436、#437 从集群、CI、跨平台测试或示例运行直接得到异常。
2. **合同对照**：#397、#395、#406、#432 分别来自平行路径、生命周期、缓存和配置链的合同不一致。
3. **边界输入**：#388 不需要线上事故，读到 first-match 算法后系统测试顺序和 prefix boundary 就能发现。
4. **二阶观察**：#419 的 workflow 已经成功，但步骤耗时暴露了下一项高价值优化。
5. **规划与版本演进**：#430 把当前热路径代入未来规模；#438 从已合并 PR 的明确 non-goal 和上游 release 形成自然 follow-up。

这解释了为什么只刷新 issue 列表很难主动发现工作：issue 列表展示的是别人已经完成问题发现后的结果，不展示他们站在哪条代码/运行表面上观察。

> 注释：所谓“合同”，不是只指 API 文档。默认值、缓存失效条件、Helm flag、SDK close 行为、CI path filter、artifact version 格式和 controller ownership 都是工程合同。

### 两个必须学习的反例

#### #432：发现 gap 正确，不代表直接修法正确

#432 的静态观察成立：WorkloadManager 有 auth middleware，而 chart 没传 enable flag。但 maintainer 在 #433 指出，当前 `EnableAuth` 同时耦合 caller authentication 与 credential delegation；直接打开后会立即改变 Router 使用调用者 token 操作 Kubernetes 的权限模型。

因此 #433 最终关闭，等待 auth/RBAC contract 先定义清楚。

可复用结论：从配置缺口发现候选后，必须继续问“谁的身份、谁的权限、谁拥有下游对象”。安全开关不是简单 bool wiring。

#### #397：源码差异正确，生产可达性仍要证明

#397 发现 direct 与 warm path 对 empty `authMode` 行为不同，这是可信的源码不一致。但 Kubernetes API admission 正常可能已经应用 CRD default，因此 empty value 在真实生产路径是否可达，需要继续验证 unstructured/client/create/update 等 producer。

可复用结论：单测构造 zero value 可以证明条件行为，却不能自动证明线上一定触发。issue 标题、严重度和 blocking 判断仍需通过 production reachability gate。

### 我们今后的固定发现闭环

以后不再以“有没有新的空闲 issue”为起点，而按以下顺序执行：

1. 刷新最近创建/更新的 issue、PR 和 default-branch Actions，交叉 assignee、`/assign`、same-topic PR、cross-reference 和 maintainer blocker。
2. 每轮只选择一个真实表面：失败/虚假绿色 CI、示例、公共字段、生命周期、cache、Helm 配置、算法、刚合并 PR 或依赖 release。
3. 保存最初 observation：命令、输入、日志、耗时、response 或明确源码不变量。
4. 贯穿 producer -> transport/type -> consumer -> state owner -> cleanup，并对照同类平行路径。
5. 检查 admission/default、验证、锁、retry/resync/restart/self-heal，判断 observed、reachable latent 还是 hypothetical。
6. 搜索 issue、PR、branch、commit、discussion 和 umbrella ownership；无 assignee 仍不等于无人做。
7. 再决定产物：bug、enhancement、discussion，或给已有作者补 reproduction/test/review evidence。
8. 将第一项改动压到可独立 review/test 的边界，并写出 compatibility、non-goal 与残余 follow-up。

对应 discovery card 已固化到 `.agents/skills/agentcube-issue-discussion/references/issue-discovery.md`。今后每次推荐新任务前先填：

```text
surface / observable trigger / actual behavior / expected contract
producer -> type -> consumer -> owner / reachability / recovery
decisive evidence / duplicate and ownership search
artifact class / smallest change / tests / compatibility / unknowns
```

### 对当前仓库的实际判断

截至本轮扫描，最近显眼的实现点大多已经有 owner：#438 assigned，#434 已有 #435，#430 已有 #431，#395 已有 #426；#432/#433 还卡在权限模型，不适合复活旧解法。因此现在强行再找一个“空 issue”会降低质量。

下一轮最合理的主动探索不是继续翻 issue 标题，而是执行以下三个互不冲突的本地 investigation：

1. **剩余 runnable examples clean-run audit**：#437 已覆盖 AgentRuntime 与 PCAP，继续选择一个未覆盖示例，严格按 README 从 manifest 到 invoke/cleanup 跑通；只有得到具体 mismatch 才形成候选。
2. **公共请求字段传播矩阵**：从 SDK/CLI 的 session create 参数出发，逐字段对照 Go DTO、builder、Store/status，优先检查 default 值和 direct/warm 两条路径。
3. **default-branch CI truth audit**：查看最近绿色 job 的关键步骤是否执行、耗时是否异常短，以及 workflow command 的 path-filter 依赖闭包；不要先假设存在 bug。

这三个方向的共同停止条件是：如果没有 decisive evidence、路径不可达、已有 owner，或需要 maintainer 先决定产品/安全合同，就不发 issue。没有新 issue 也是一次有效筛选结果。

### 本轮工具阻塞与修正

第一次批量读取 issue 时，给 `gh issue view --json` 传了不受支持的 `closedByPullRequestsReferences` 字段，命令返回 available fields 列表并全部失败。

修正方式：改用受支持的 `number,title,body,author,createdAt,state,comments,assignees,url` 字段读取 issue，再单独查询 PR 与时间线关系。没有把第一次空结果误判为“issue 无关联 PR”。

> 分析：工具查询失败与社区没有数据是两回事。任务发现流程也要保留查询完整性，不能用失败或不完整的搜索结果证明不存在 owner、PR 或历史修复。
