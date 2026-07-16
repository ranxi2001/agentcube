# Day48：PR #387 合并后审计与 RainbowMango OWNERS 提名

日期：2026-07-16

状态：#387 两项 follow-up 已完成源码审计；Claim polling 暂不改 watch；Pod label fallback cleanup 已在独立分支实现并通过验证，但不是 correctness hotfix。两个 fork topic branch 已按用户确认推送，upstream PR 均未创建。用户进一步澄清 `RainbowMango` 已多次实际承担 AgentCube review/approve；公开记录验证后，OWNERS 变更按 formalize existing responsibilities 处理，不再要求新建 membership issue。

## 今日目标

1. 复核 #387 合并后的两个次要观察，区分 correctness bug、可维护性 cleanup 与没有规模证据的架构优化。
2. 不用 commit 数量代替维护贡献，按 issue、comment、review、作者响应和最终结果梳理 `RainbowMango` 的项目质量把控事件。
3. 基于最新 `upstream/main` 准备只修改 root `OWNERS` 的提名分支，并核对 Volcano 社区晋升规则。
4. 保存精确 PR body、验证结果、失败命令和发布门禁；fork branch push 与 upstream PR 创建分别确认。

> 注释：`reviewer` 和 `approver` 不只是 YAML 中的两个名字。它们分别对应 `/lgtm` 与 `/approve` 权限，会改变整个仓库的合并门禁，因此贡献依据应重点证明长期 review 判断、项目方向和质量责任，而不是简单列举 authored commits。

## 一句话结论

- #387 当前没有需要立即修复的生产 bug。
- Claim 路径的 1 秒 polling 在并发慢创建时约产生 `1N-2N GET/s`，但现有实现有完整 timeout、取消和错误分类；没有实际 QPS / throttling 证据前，不值得直接换成双资源 watch。
- `GetSandboxPodIP` 的 label-selector fallback 在受支持 Ready producer 中不会被使用；清理它还能移除全集群 Pod informer 与 `list/watch` RBAC，因此有独立 cleanup 价值，但不应包装成 #387 bugfix。
- `RainbowMango` 的提名依据应是已经发生的 root-level stewardship：路线拆分、scope 门禁、Kubernetes API 合同、规模与恢复审查、自动化治理和最终 head 合并门禁。

## #387 合并基线

- PR：[volcano-sh/agentcube#387](https://github.com/volcano-sh/agentcube/pull/387)
- exact feature head：`95fae1f8eab0e9e289a6467f014ca4e96ccc86e5`
- merge commit：`146b75fc4b98f214988b5d0c5059a55a2bc1f9da`
- `@acsoto` 已 `/lgtm`；`@RainbowMango` 在最终 head 上 `/approve`；Tide 于 2026-07-16 合并。
- 本轮源码基线：`upstream/main@146b75f`。

> 分析：PR 已关闭后，follow-up 不应继续堆到原分支。若确有独立价值，应从最新 `upstream/main` 建 focused cleanup；若只是未来规模优化，应先记录触发指标，不能用“watch 看起来更 Kubernetes-native”代替收益证明。

## 观察一：Pod label fallback

### 当前调用链

`pkg/workloadmanager/handlers.go` 的唯一生产调用在读取 Ready Sandbox 后执行：

```text
createdSandbox.Name
  -> 默认 sandboxPodName
  -> 非空 agents.x-k8s.io/pod-name annotation 覆盖
  -> GetSandboxPodIP(namespace, sandboxName, podName)
```

现有 helper 在 `podName != ""` 时按名称 live GET Pod；只有空字符串才使用 Pod informer 按 label list，再检查 owner reference。

### “podName 恒非空”需要精确表述

源码中 handler 只检查 annotation key 是否存在，理论上空值可以覆盖默认值，因此“任何输入下恒非空”并不成立。生产可达性还要看真实 producer：

- agent-sandbox direct controller 的 `resolvePodName` 把空 annotation 当缺失，回退到 Sandbox 名；
- direct controller 创建或接管 Pod 时会写入实际 Pod 名；
- warm-pool adoption 在 Sandbox 可被观察为 Ready 前写入 adopted Pod 名；
- Kubernetes 已持久化对象的 `metadata.name` 非空。

所以更准确的分类是：**受支持 Ready producer 下不可达的历史 fallback**，而不是语言层面绝对死代码。管理员手工把 controller-owned annotation 改为空可构造短暂状态，但这不是当前支持合同，也没有线上 occurrence。

### 为什么仍有 cleanup 价值

仓库搜索证明 `podLister` 只服务这个 fallback。为了它，WorkloadManager 还会：

- 创建并启动全集群 Pod informer；
- 等待 Pod cache sync；
- 保留 Pod `list/watch` RBAC；
- 维护三组只用空 `podName` 的历史单测。

删除 fallback 的价值不是修复 #387，而是减少 API server watch、启动依赖、缓存状态和权限面。

### 建议的独立 cleanup 范围

1. 空 annotation 按缺失处理，与 agent-sandbox `resolvePodName` 一致。
2. Pod 始终按确定名称 live GET。
3. 删除 label-selector、`podLister`、Pod informer 与对应 cache-sync。
4. WorkloadManager Pod RBAC 从 `get/list/watch` 收紧为 `get`。
5. 删除空参数历史测试，保留 direct 与 warm-pool live-GET regression。
6. 不顺手清理其他 helper，不混入 auth/RBAC 产品模型。

建议优先级：低到中，独立 cleanup；不是 merge regression，也不阻塞 release。

### 本地 cleanup 实现结果

- worktree：`/tmp/agentcube-pod-informer-cleanup`
- branch：`cleanup/remove-sandbox-pod-fallback`
- base：`upstream/main@146b75f`
- DCO commit：`eefce59d95bd5be4566abf10ce5b817bc74df139`
- subject：`workloadmanager: remove unused pod informer`
- diff：6 files，`+45/-231`
- 状态：clean，`0 behind / 1 ahead`；已 push [fork branch](https://github.com/ranxi2001/agentcube/tree/cleanup/remove-sandbox-pod-fallback)，未创建 PR。

实际改动严格限于上述范围：保留四参数 `GetSandboxPodIP` 签名，空 Pod 名回退到 Sandbox 名后 live GET；删除 Pod lister/informer/cache-sync；收紧 Pod RBAC；更新相关测试夹具。Claim polling 没有改动。

验证：

```text
go test ./pkg/workloadmanager
PASS

go test -race ./pkg/workloadmanager -count=1
PASS (uncached, 5.116s)

go test ./pkg/workloadmanager \
  -run 'Test(GetSandboxPodIP|RunAndWaitForCacheSync)' -count=10
PASS

git diff --check
PASS

make lint
PASS
```

lint 第一次运行发现新测试 helper 的 `namespace` 参数在所有调用中都恒为 `"test-namespace"`：

```text
pkg/workloadmanager/k8s_client_test.go:48:39:
`newK8sClientForPod` - `namespace` always receives `"test-namespace"` (unparam)
```

删除这个伪参数后，重新运行 uncached unit、race、10 次 focused 和全仓 `make lint` 均通过；commit 因 amend 从 `aea114d` 更新为 `eefce59`。这次失败属于 clean-code 门禁有效发现，不是产品 bug。

Helm 首次独立复跑失败：

```text
make helm-template
helm: command not found
```

根因是默认 `PATH` 没有 Helm。使用机器上已有的 `/tmp/agentcube-tools/linux-amd64/helm`（`v3.18.4`）后，以下命令可复现通过：

```text
PATH=/tmp/agentcube-tools/linux-amd64:$PATH make helm-template
PATH=/tmp/agentcube-tools/linux-amd64:$PATH make helm-lint
1 chart(s) linted, 0 chart(s) failed
```

rendered WorkloadManager RBAC：

```yaml
resources: ["pods"]
verbs: ["get"]
```

残余 source-compatibility 风险：`Informers.PodInformer` 是导出字段，仓库外若直接引用会编译失败；仓库内无调用者，`pkg/workloadmanager` 也不是已声明稳定的库 API。`GetSandboxPodIP` 导出签名保持不变，但仓库外若依赖“空 Pod 名通过 label 找到不同名 Pod”的历史行为，会改为同名 live GET。这个边界已写入 PR draft，不伪装成零风险。

## 观察二：Claim readiness polling

### 精确负载模型

`waitForClaimSandboxReadyWithTimeout` 在进入循环后立即 GET 一次 Claim，然后每秒进入下一轮：

- Claim 尚未发布 Sandbox 名：每轮 1 次 Claim GET；
- Claim 已发布 Sandbox 名但 Sandbox 未 Ready：每轮 1 次 Claim GET + 1 次 Sandbox GET；
- 2 分钟内约 120 轮，通常最多约 120 + 120 次 GET；deadline 与 ticker 同时 ready 时可能多一次已取消尝试，因此不写成严格的 240 上限；
- 并发 `N` 个慢创建理论上约为 `1N-2N GET/s`。

WorkloadManager client 默认 `QPS=50`、`Burst=100`。这说明高并发下值得观察，但不能从配置值直接推断已经发生 throttling。

> 注释：`N` 是同时处于等待状态的 create 请求数量，不是集群中的总 Sandbox 数。正常几秒内完成的请求只短暂贡献 GET；真正需要关注的是长时间 Pending、API error retry 或突发并发。

### 当前实现已经保护的合同

- 两次 GET 都使用内部 2 分钟 `waitCtx`，阻塞 I/O 能被 deadline 取消；
- parent cancellation、parent deadline 与内部 creation timeout 分开返回；
- Forbidden、Unauthorized、conversion 等永久错误立即失败；
- NotFound、server timeout、429、EOF/connection reset 等允许重试；
- deadline 后返回的 late Ready 会被拒绝；
- 失败后 Claim 与 Store placeholder 使用独立 cleanup context 回滚。

这些行为已有 focused tests，说明 polling 虽不优雅，但不是无界 busy loop。

### 为什么现在不换 watch

Claim 与 Sandbox 是两个资源阶段。每请求 watch 需要额外处理：

- LIST/WATCH RBAC，尤其 auth 模式下的用户 ServiceAccount 权限；
- 初始 GET/LIST 与 watch `resourceVersion` 之间的竞态；
- watch close、410 Gone、断线重连、backoff；
- Claim 名字发布后切换到 Sandbox watch；
- request 结束后的 watcher 清理；
- 大量短生命周期 watch connection 本身的 apiserver 成本。

也不能简单在第一次看到 `status.sandbox.name` 后永久缓存名字并停止读 Claim：agent-sandbox 在 Sandbox 消失时可以清空 status，随后重新选择或创建运行对象。持续读 Claim 保留了重新绑定语义。

### 未来触发条件

只有出现以下证据后再设计 watch 或共享 informer：

1. create readiness p95/p99 明显被 GET throttling / apiserver latency 主导；
2. client-side rate limiter wait 或 429 可观测；
3. 同时等待数量和 `GET/s` 达到明确规模预算；
4. 目标身份的 `get/list/watch` RBAC 合同已与 #433 后续 auth 方向对齐；
5. 有 watch restart、resourceVersion、rebind 和 cleanup tests。

当前决策：不提 polling/watch PR。

## RainbowMango 项目质量事件账本

### 评价方法

本次不按 commit 数、approval 数或 GitHub contribution graph 排名。每条证据必须包含：

```text
维护动作 -> 保护的项目合同 -> 作者/社区响应 -> 当前结果
```

纯 `/lgtm`、`/approve` 只能证明 gate outcome，不能反推出 review 方法；author 自己提交的代码也不是 root OWNERS 的充分依据。

### 可复核数量快照

截至 2026-07-16，使用 GitHub 当前 API 可见记录并对 reviews、review comments 和 issue comments 完整分页后，得到以下 AgentCube 仓库内快照：

| 指标 | 数量 | 口径 |
| --- | ---: | --- |
| 提交过正式 review 的非本人 PR | 23 | 19 个真人作者 PR、4 个 Dependabot PR |
| Submitted review events | 34 | 19 次 `APPROVED`、15 次 `COMMENTED`；同一 PR 可有多轮 review |
| 含 GitHub `APPROVED` review 的 PR | 19 | 其中 18 个已合并，#357 仍 open |
| 已合并的 reviewed PR | 19 | 与上一行交集为 18，不能把 merge 直接归因为 reviewer |
| 非本人 PR inline review comments | 28 | 分布在 4 个 PR，包含 20 个 reviewer-root threads 和 8 条跟进回复；#431 单独占 22 条、17 个 root threads |
| 非本人 PR 普通会话评论 | 9 | 分布在 6 个 PR；不属于 inline review comment |
| 任一 review 参与覆盖的非本人 PR | 26 | 23 个 submitted-review PR，加上只留普通会话评论的 #250、#390、#403 |
| 本人创建的 PR | 2 | #326、#363，均已合并 |
| 本人创建的 Issue | 2 | #386 release/proposal umbrella、#430 architecture discussion |
| 真实 Issue 评论 | 6 | 分布在 #263、#381、#386、#419；排除 PR 普通会话评论后统计，其中非本人 Issue 为 4 条、覆盖 3 个 Issue |

> 注释：`34 reviews`、`28 inline comments` 和 `9 PR conversation comments` 不能相加成“71 次 review”。Inline comment 依附于 submitted review，同一 PR 也可能经过多轮 review；这些列分别描述 review 轮次、行级讨论量和普通会话参与。

> 分析：数量证明职责被持续执行，但不能单独证明技术深度。正文仍以 #386、#430/#431、#396、#419/#420 和 #387 的“维护动作 -> 合同 -> 响应 -> 结果”链条作为提名依据；19/4 的真人作者与 Dependabot 拆分用于防止自动依赖 PR 放大技术 review 印象。

> 调试记录：旧 `maintainer_review_history.py` 对每个 REST endpoint 只读取前 100 条，导致 #431 中 RainbowMango 的 inline comment 从真实 22 条少算为 11 条。本轮为 files、reviews、inline comments 和 conversation comments 增加全量分页并补测试。首次用 `python3 -m unittest .agents/...` 调用因目录名以 `.` 开头被解析为空模块而失败；改用 test discovery 后 8/8 通过，真实 #431 回归也读回 22 条。

### 高信号事件

| 质量职责 | 公开事件 | 维护动作 | 结果 / 边界 |
| --- | --- | --- | --- |
| Release 任务拆分与跟进 | [#386 task](https://github.com/volcano-sh/agentcube/issues/386#issuecomment-4899758341)、[#422](https://github.com/volcano-sh/agentcube/pull/422) | 将 Alpine base image 更新纳入 v0.2.0 台账并 `/help`；核对 contributor 提出的 `/docker` scope；在 exact change 上完成 review/approval | 从维护缺口变成 focused、可认领、可合并的自动化任务；#422 已合并 |
| PR 单一职责与安全边界 | [#250 comment](https://github.com/volcano-sh/agentcube/pull/250#issuecomment-4429092718)、[#326](https://github.com/volcano-sh/agentcube/pull/326) | 发现 docs PR 混入 PicoD 32 MiB request-body 限制，主动提出拆分 | 安全代码获得独立 threat/scope review；#326 将限制移到全局 middleware 后合并 |
| 自动化可预测性与 trade-off | [#396 schedule](https://github.com/volcano-sh/agentcube/pull/396#discussion_r3517204392)、[grouping question](https://github.com/volcano-sh/agentcube/pull/396#discussion_r3517380161)、[acceptance](https://github.com/volcano-sh/agentcube/pull/396#discussion_r3517411007) | 引用成熟先例要求 predictable Dependabot schedule；不机械照抄 grouping，而是要求作者解释 | 作者说明减少 PR 噪音后，reviewer 明确接受；#396 合并。体现 precedent + reasoned exception，而不是个人偏好 |
| 组件退役与 owner 协调 | [#403 comment](https://github.com/volcano-sh/agentcube/pull/403#issuecomment-4797990683) | 判断 `agentd` 已无生产用途，但批准前仍邀请相关组件 owner 表达异议 | 删除跨代码、构建、文档与测试，获得 owner-aware gate 后合并 |
| 性能根因证据 | [#419 comment](https://github.com/volcano-sh/agentcube/issues/419#issuecomment-4901072888)、[#420](https://github.com/volcano-sh/agentcube/pull/420) | 对 `$BUILDPLATFORM` 诊断回到 Docker `FROM --platform` 官方合同，确认 arm64 compiler 在 x64 runner 上被 QEMU 模拟是根因 | 性能方案不是凭 benchmark 相关性合并；#420 保持 runtime image multi-arch 合同并合并 |
| 项目架构边界 | [#430](https://github.com/volcano-sh/agentcube/issues/430) | 把 latency、apiserver churn、idle capacity 与 capacity planning 归纳为同一架构问题，提出 “Kubernetes owns the pool; AgentCube owns the sessions” | 为 slow resource control 与 session hot path 建立长期责任边界；#431 只覆盖 slow track，讨论仍 open，不写成最终共识 |
| API 可冻结性 | [selector](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3584268549)、[ResourceList](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3584314319)、[field comments](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3584355665) | 追问重复 selector、硬编码 CPU/memory 扩展性，以及字段 writer/default/immutability 合同 | 最新 `49576e8` 删除冗余 `NodeSelector`、采用 `corev1.ResourceList`、扩展字段注释；proposal 仍在 review，不能称已批准 |
| 规模与状态通道 | [status concern](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3579040898)、[Lease follow-up](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3585166678) | 先计算千节点 periodic CR status 风险，再引用 kubelet Lease 模型 | 作者接受；最新 head 改为 event-driven CR status + Lease heartbeat。新文本仍需修正 Lease scope/RBAC，说明 review 继续发挥门禁作用 |
| 恢复窗口而非最终自愈 | [initial question](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3578884771)、[second-round check](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3585155189) | 先问 manifest 删除，再在作者补 self-healing 后继续检查 reservation release / competing Pod / re-admission 窗口 | 作者把它承认为 destructive-operation constraint；避免把 eventual recreate 写成 uninterrupted resource guarantee，风险仍需 proposal 明示 |
| 部署与 runtime 前置 | [RuntimeClass question](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3584380967) | 追问 custom RuntimeClass 是否需要 kubelet/containerd 节点前置，并把未说明的安装要求视为 serious constraint | 作者澄清 containerd shim；最新 proposal 增加 Task v2 method 表和 Phase 2 shim/e2e acceptance，仍需真实节点 spike |
| 最终 head / 合并门禁 | [#387 conflict request](https://github.com/volcano-sh/agentcube/pull/387#issuecomment-4964924366)、[final approval](https://github.com/volcano-sh/agentcube/pull/387#pullrequestreview-4711905661) | 不在冲突分支上直接批准；等待 rebase、修复、测试和最终 head 后再 approve | exact head `95fae1f` 被 Tide 合并为 `146b75f`；这是 follow-through 证据，不用 approval 数量夸大 |

### 明确排除的伪证据

- #391、#393、#414、#420、#423、#436 等 approval-only 记录：只作为 outcome，不推断审查方法。
- #326、#363 的 authored commit 数：实现贡献真实，但不是本次 root review 能力的中心证据。
- #433 的 auth / credential delegation 质疑来自 `@acsoto`，不是 `RainbowMango`；不得误归因。
- GitHub contribution count：可说明活跃度，不能说明每次 review 的质量。
- #431 thread `resolved` 状态：只表示 UI 对话折叠，必须回读最新 proposal 与未闭合合同。

> 分析：高质量提名不是给候选人写个人简介，而是证明“他已经在做这个角色要求的工作”。对 root OWNERS，最重要的是跨目录 scope、公共 API、架构方向、恢复/安全/规模门禁和最终合并责任。

## OWNERS 当前状态与治理边界

### 当前仓库事实

- `RainbowMango` 当前不在 root 或任一 nested `OWNERS`。
- GitHub 在 AgentCube review 中将其标记为 `COLLABORATOR`。
- root `reviewers` 的 case-insensitive 插入位置是 `hzxuzhonghu` 与 `tjucoder` 之间。
- root `approvers` 的插入位置是 `kevin-wangzefeng` 之后。

### Volcano 社区规则

[community membership policy](https://github.com/volcano-sh/community/blob/master/community-membership.md) 当前写明：

- Reviewer：两位 maintainer sponsor、Member 至少 2 个月、足够 review 与 codebase knowledge；
- Approver：两位 maintainer sponsor、Reviewer 至少 2 个月、足够 review 与 codebase knowledge；
- membership request 还要求候选人确认 2FA、mailing list、sponsor 已事先同意等事实。

我们可以用公开事件证明 review 与 codebase judgment，但不能替候选人证明 2FA、sponsor consent 或 reviewer tenure。AgentCube #137 的 bot 规则说明 collaborator 可以通过 technical trust check；这不等于自动满足社区晋升流程。

近期同组织先例也采用两阶段流程：

- [community#120](https://github.com/volcano-sh/community/issues/120) 先由候选人确认 Reviewer 前置并获得 sponsor，随后 [volcano#5121](https://github.com/volcano-sh/volcano/pull/5121) 只增加 reviewer entry；
- [community#150](https://github.com/volcano-sh/community/issues/150) 说明既有 Reviewer 任期和两位 sponsor，随后 [volcano#5464](https://github.com/volcano-sh/volcano/pull/5464) 才增加 approver/root entries；
- 当前 community issue 搜索没有找到 `RainbowMango` 的 membership request。

> 注释：没有搜到公开 request 不等于候选人不满足能力要求，也不能推断其 2FA 或 sponsor 状态；它只说明我们没有权限替其勾选模板中的私有前置条件。

当前处理：历史 membership 流程保留为新角色申请的背景，但不再把它机械套到本次 existing-responsibility formalization。

## 历史提名 PR 校准

### AgentCube 同仓库样本

AgentCube 历史上只有 [#137 Add reviewers and approvers](https://github.com/volcano-sh/agentcube/pull/137) 一个建立 OWNERS 名单的 PR。它的 reviewer-visible body 只有 `Fix #79`（2 words / 1 nonblank line），一次新增 root 与 14 个目录的 OWNERS，并混入 Copilot instructions。Bot 随后标记 `do-not-merge/invalid-owners-file`，作者也说明部分候选人需要先申请 Volcano membership；最后作者手工绕过 approval gate，以“先让更多 reviewer 参与”为由合并。

> 分析：#137 是仓库启动期 bootstrap，不是个人晋升流程。它早于当前 PR template，且 invalid-owners gate 没有正常收敛，不能用来证明“reviewer 和 approver 可以常规一次授予”，也不能复制两词正文。

### Volcano 近期可复用样本

| 角色路径 | Membership / sponsor 证据 | OWNERS PR | 实际行为 |
| --- | --- | --- | --- |
| Reviewer | [community#119](https://github.com/volcano-sh/community/issues/119) | [volcano#4933](https://github.com/volcano-sh/volcano/pull/4933)，39 words | 候选人先确认 checklist 与两位 sponsor；PR 只链接已批准 issue，并只加入 reviewer |
| Reviewer | [community#120](https://github.com/volcano-sh/community/issues/120) | [volcano#5121](https://github.com/volcano-sh/volcano/pull/5121)，94 words | Maintainer 曾因缺少真实 review 要求候选人先补 review；PR body 误写 both roles，但 exact diff 只加入 scheduler reviewer，不能当作双角色先例 |
| Approver | [community#150](https://github.com/volcano-sh/community/issues/150) | [volcano#5464](https://github.com/volcano-sh/volcano/pull/5464)，14 words | 候选人已通过 #119/#4933 成为 Reviewer 约 5 个月，再单独申请 Approver；贡献和 sponsor 证据留在 issue，PR 只做角色落盘 |
| Approver | [community#101](https://github.com/volcano-sh/community/issues/101) | [volcano#4676](https://github.com/volcano-sh/volcano/pull/4676)，51 words | 两位 maintainer 已在 membership issue 支持后，PR 简短链接该决定并只增加 approver |

当前 community policy 要求普通新申请者按 Member、Reviewer、Approver 逐级进入；近期没有发现普通贡献者一次从无角色直接进入 reviewer+approver 的成功样本。

> 注释：这组普通申请样本回答的是“新成员如何晋升”，不能单独回答“如何把已有 collaborator 长期执行的职责写入 OWNERS”。把两类场景混为一谈，是本轮第一次判断过度收紧的原因。

### 用户澄清后的证据复核

GitHub Search 当前返回 23 个 `repo:volcano-sh/agentcube reviewed-by:RainbowMango -author:RainbowMango` PR；逐 PR GraphQL review state 复核，其中 19 个 PR 包含 `APPROVED` review，19 个 reviewed PR 已合并，18 个同时满足 `APPROVED` 与 merged。数量只说明职责已被反复执行，能力判断仍看具体事件：

- #386 把 v0.2.0 社区 proposal 收集、triage、负责人和合并结果组织成持续维护的 umbrella checklist；
- #430 明确 pool/session 的长期架构边界，并通过 #431 多轮 review 推进其中 Kubernetes resource-pool 一侧；
- #396 追问 Dependabot schedule 与 grouping trade-off，作者解释后接受；
- #420 在批准前用 Docker `FROM --platform` 合同确认多架构构建根因；
- #431 对 API 扩展性、字段合同、状态写入规模和恢复窗口进行多轮审查；
- #387 在冲突解决、最终修复和 exact head 收敛后完成 approval。

这证明本次不是“用 authored commit 数申请新角色”，而是把已经执行的 review/approval 权限与 root OWNERS 责任对齐。此前要求先开 membership issue 的判断撤回。

### 对当前草稿的最终判断

- 不新建或强行关联 membership issue；`Which issue(s)` 写 `NONE`。
- 23/19 只作为职责持续性的背景，四组 issue/review/outcome 事件继续承担质量证明，避免退化成计数提名。
- 两行 reviewer+approver diff 可以保留；PR title 使用 `owners: add RainbowMango as reviewer and approver`，准确表达 formalization，而不是尚待资格审议的 nomination。
- PR body 仍保持一屏，并明确无 runtime/API 行为变化。

## 干净提名分支

- worktree：`/tmp/agentcube-owners-rainbowmango`
- branch：`owners/add-rainbowmango`
- base：`upstream/main@146b75f`
- local DCO commit：`63bea7ac2dbda785a1ace9ef6a37c7f0d7a5236c`
- diff：`OWNERS | 2 ++`
- 已 push [fork branch](https://github.com/ranxi2001/agentcube/tree/owners/add-rainbowmango)；未创建 PR、未 mention maintainer。

```diff
 reviewers:
   - hzxuzhonghu
+  - RainbowMango
   - tjucoder

 approvers:
   - hzxuzhonghu
   - kevin-wangzefeng
+  - RainbowMango
```

### 验证

成功：

- `git diff --check`
- PyYAML `safe_load`
- reviewers / approvers case-insensitive ordering assertion
- `RainbowMango` 在两张列表中各恰好出现一次
- branch 相对 `upstream/main` 为 `0 behind / 1 ahead`
- commit 包含 DCO signoff

失败与替代：

```text
ruby -ryaml ...
/bin/bash: ruby: command not found
```

根因是本机未安装 Ruby，不是 YAML 错误。改用已安装的 PyYAML `6.0.1` 做结构化解析并通过。

## 精确 upstream 草稿

建议 PR title：

```text
owners: add RainbowMango as reviewer and approver
```

PR body canonical draft：[day48-rainbowmango-owners-pr-draft.md](day48-rainbowmango-owners-pr-draft.md)

- reviewer-visible words：285
- nonblank lines：17
- ordinary PR 软门槛：100-300 words / ≤35 nonblank lines
- 官方模板、`/kind cleanup`、`NONE` release note、AI disclosure 均已包含

正文重点不是 commit 清单，而是：

1. #386/#430 的项目方向与贡献边界；
2. #250/#326 与 #396 的 focused scope / automation trade-off；
3. #431 已落到最新 proposal 的 API 与 Lease 变化，同时明确 field/runtime/recovery threads 仍 open；
4. #419 以 Docker 官方 `FROM --platform` 合同确认多架构构建根因；
5. nomination 的治理确认边界。

cleanup PR title：

```text
workloadmanager: remove unused Pod informer
```

cleanup PR body canonical draft：[day48-pod-informer-cleanup-pr-draft.md](day48-pod-informer-cleanup-pr-draft.md)

- reviewer-visible words：208
- nonblank lines：15
- 官方模板、`/kind cleanup`、`Refs #387`、source-compatibility limit、AI disclosure 与 `NONE` release note 均已包含

## Day48 待办状态

| 事项 | 状态 | 下一步 |
| --- | --- | --- |
| #387 post-merge 两项审计 | DONE | polling 不改；Pod fallback cleanup 作为独立低中优先级候选 |
| RainbowMango 维护事件账本 | DONE | 后续若 maintainer 要求，只补直接相关证据，不追加 approval 计数 |
| OWNERS 两行分支与 DCO commit | DONE | formalize existing responsibilities；等待 exact payload 确认 |
| push `origin owners/add-rainbowmango` | DONE | remote exact SHA `63bea7a`；未 push upstream |
| 创建 `volcano-sh/agentcube` PR | PENDING_CONFIRMATION | 不关联新 issue；等待用户确认更新后的 exact title/body 后执行 |
| Volcano membership issue | NOT_REQUIRED | 本次 formalize 已实际执行的 AgentCube collaborator duties；不另造 promotion issue |
| Pod informer/RBAC cleanup PR | READY_FORK / SEPARATE | fork branch `cleanup/remove-sandbox-pod-fallback@eefce59` 已 push，通过 unit/race/repeat/lint/qualified-Helm 验证；upstream PR 等用户另行确认，不与 nomination PR 混合 |

## 今日复用经验

1. **提名看 role behavior，不看 commit 计数。** Root reviewer/approver 的核心证据是他如何改变范围、合同、恢复路径和 merge decision。
2. **每条贡献都要有 outcome。** “留了评论”不够，要验证作者是否修改、解释、拒绝，当前 head 是否仍有 residual risk。
3. **归因先回 GitHub actor。** #433 的 maintainer 意见若只靠本地摘要很容易错归因，必须打开 comment author。
4. **resolved / approved 都不是完整技术证据。** resolved 可能仍有残余约束，approve 可能只有流程命令。
5. **治理 PR 也需要 compatibility thinking。** OWNERS 会改变权限与信任边界，必须同时检查 bot technical trust 与社区 role policy。
6. **删除 dead branch 要看系统收益。** 本次 fallback cleanup 的价值来自 informer、cache sync 和 RBAC，而不是减少几行代码。
