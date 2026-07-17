# Day51：社区动向与 PR #385 Warm Pool 健康状态回溯

日期：2026-07-17

## 1. 今日目标

本轮有两个连续目标：

1. 把 `2026-07-17 18:06 CST` 的 AgentCube 社区 freshness scan 写成可复查的工程记录，而不是只保留聊天中的动态摘要。
2. 回到最早提交的 upstream PR [#385](https://github.com/volcano-sh/agentcube/pull/385)，重新回答它在做什么、为什么需要、当前为什么冲突，以及是否值得在 `agent-sandbox v0.5.2` 基线上继续推进。

本轮只读取 GitHub 元数据、PR/Issue 对话、本地 Git refs、当前源码和既有实习报告；没有执行 `/assign`、评论、review、maintainer mention、PR branch push 或其它 upstream-facing 动作。

> 注释：freshness scan 只能证明某个时间点的社区状态。真正开始实现、评论或请求 review 前，仍要重新检查 exact head、assignee、关联 PR 和维护者方向。

## 2. 结论先行

社区扫描的结论是：**当前没有同时满足方向明确、无人负责、范围独立和本地可验证的直接实现任务。**

最值得关注的两条主线是：

- [#412](https://github.com/volcano-sh/agentcube/pull/412) 的 soft node-affinity 实现正在快速更新，会与我们的 v0.5.2 adapter 和 Pod informer cleanup 大面积重叠，适合做源码 review，不适合重复实现。
- [#441](https://github.com/volcano-sh/agentcube/issues/441) 把 #433 暴露的认证/授权问题提升为架构合同讨论，当前适合梳理身份和权限矩阵，不适合直接写代码。

对 #385 的重新判断是：

- 它不是修复 warm pool 的功能 PR，而是把底层 pool 健康状态投影到用户面对的 `CodeInterpreter` 上，形成可观测性闭环。
- 这个需求在当前 `main@146b75f` 和我们的 v0.5.2 blind adapter 中都仍然存在；升级依赖不会自动提供 `WarmPoolAvailable`。
- 旧 PR 已经 `DIRTY`，相对当前 main 为 `56 behind / 3 ahead`。#387 在 controller 和测试文件中引入了真实冲突。
- 旧 head 还遗漏了 WorkloadManager 写 Kubernetes Event 所需的 RBAC，因此不能只机械 rebase 后推送。
- 最合理的顺序是等待 #438 的 v0.5.2 适配方向落地，再基于 beta API 重新承载 #385 的行为，并重新确认 `Ready`、50% 水位、状态 freshness、Event RBAC 和真实 watch/E2E 证据。

## 3. 证据边界

本报告把证据分成三类：

| 标记 | 含义 | 本轮示例 |
| --- | --- | --- |
| GitHub 当前事实 | Issue/PR 元数据、评论、review、check、assignee 和 merge 状态 | #412 exact head、#438 assignee、#439 review gate |
| 本地源码事实 | Git ref、diff、call path、RBAC、依赖源码和测试代码 | #385 `merge-tree` 冲突、`ReadyReplicas` producer、Event 权限缺口 |
| 工程判断 | 在事实之上给出的优先级、等待条件和重构方向 | 不立即 rebase #385；先等 #438，再做干净迁移 |

> 分析：Issue 作者报告的现象不自动等于我们已经复现。#265 对“父资源 Ready、子 pool 不健康”的描述同时有当前源码支持，因此可以确认机制存在；本轮没有重新制造一次真实 pool 故障，不能把它写成今日新增的运行时复现。

## 4. 社区 freshness 快照

扫描冻结时间：`2026-07-17 18:06 CST`。

上一次记录时间：`2026-07-17 09:16 CST`。

### 4.1 高信号变更

| 对象 | 当前事实 | Ownership / direction | 对我们的影响 | 当前动作 |
| --- | --- | --- | --- | --- |
| [#441](https://github.com/volcano-sh/agentcube/issues/441) auth/authz model | `@acsoto` 新建；open、无 assignee、暂无评论 | 先澄清外部 API boundary、authenticated identity、Kubernetes execution identity、namespace/session authorization | 延续 #432/#433，但没有确定实现合同 | 本地做身份/权限矩阵；不实现、不评论 |
| [#412](https://github.com/volcano-sh/agentcube/pull/412) soft node-affinity | exact head `2aa1831`；13 files，`+905/-98`；latest checks 全绿 | 已有作者和 `@acsoto` / `@hzxuzhonghu` 跟进；新 push 移除了旧 `/lgtm` | 与 v0.5.2 adapter 重叠 10 个文件，与 Pod cleanup 重叠 4 个文件 | 等 head 稳定后做 lifecycle/concurrency review；不重复开发 |
| [#438](https://github.com/volcano-sh/agentcube/issues/438) v0.5.2+ adapter | assigned `@safiya2610`；已确认收到 release 提醒；暂无 linked PR | ownership 明确 | 后续会触及 #385 所在 controller/API 版本 | 不重复提醒；等 PR 后做 diff-to-diff review |
| [#439](https://github.com/volcano-sh/agentcube/pull/439) RainbowMango OWNERS | exact head `63bea7a`；checks 全绿；无真人 review | 我们已提交的治理 PR | 仅缺人类 review 和 Prow labels | 静候，不提前 mention approver |
| [#385](https://github.com/volcano-sh/agentcube/pull/385) warm pool health | open，但 merge state `DIRTY` | assigned `@RainbowMango`，没有真人技术 review | 已被 #387 和未来 v0.5.2 adapter 穿过 | 暂不 rebase；本报告重新评估后续路线 |

### 4.2 #441 为什么是架构问题，不是空闲编码任务

#441 明确指出当前 `EnableAuth=true` 同时承担了两件不同的事：

1. 通过 TokenReview 验证调用者身份。
2. 把调用者携带的 Router ServiceAccount token 当作 WorkloadManager 的 Kubernetes client credential。

这会把“谁调用了 AgentCube”与“AgentCube 用什么身份操作 Kubernetes”耦合起来，并迫使 Router ServiceAccount 获得 Sandbox/SandboxClaim 生命周期权限。

Issue 当前要求先决定：

- 外部 API 是否只暴露 Router，还是允许直接调用 WorkloadManager；
- authenticated user identity 与 Kubernetes execution identity 是否必须分离；
- namespace 和 session ownership 在 Router、WorkloadManager 还是 admission 层授权。

> 注释：认证回答“你是谁”，授权回答“你能做什么”，Kubernetes execution identity 回答“哪个 ServiceAccount 真正向 apiserver 发请求”。三者可以有关联，但不应因为复用一个 token 就被当成同一个概念。

当前没有任何一项被维护者选定，因此 direction gate 不通过。直接恢复 #433 或另写一版 RBAC 只会重复未解决的设计分歧。

### 4.3 #412 为什么优先 review，而不是抢实现

#412 的最新提交在本日多次 force-push，作者还误开并关闭了重复 PR #440。最新 head 的普通 checks 已恢复全绿，但原有 `/lgtm` 因新提交被 Prow 自动移除，尚无维护者对新 head 的最终复审。

当前 diff 仍有 4 个 current AI review threads，主要集中在：

- AgentRuntime / CodeInterpreter node writeback 的测试覆盖；
- `GetSandboxPodInfo` live GET 分支与旧测试 helper；
- 异步 best-effort writeback 的生命周期和 shutdown 语义。

它与我们的两个本地分支存在直接重叠：

| 本地分支 | 重叠文件 | 风险 |
| --- | ---: | --- |
| `compat/agent-sandbox-v052-independent@2d90b07` | 10 / 13 | API、handlers、K8s client、server 和 workload builder 都要语义合并 |
| `cleanup/remove-sandbox-pod-fallback@eefce59` | 4 / 6 | RBAC、K8s client 和测试会发生冲突 |

因此当前价值最高的参与方式是等 exact head 稳定后做 focused review，验证 node affinity 的状态写回、失败重试、删除和 shutdown 路径。现在提交相邻 cleanup PR 会给 reviewer 和我们自己增加无谓的 conflict surface。

### 4.4 其它跟踪项

- #400 已在 final head 后重新获得 `@acsoto /lgtm`，当前主要缺 `approved`，我们的 review 已结束，不再追评。
- #431、#435、#429 没有实质新变化；#435 仍有 DCO failure，#431 仍未完成 proposal 收敛。
- #392 workflow hardening umbrella 已关闭，但本日没有新的技术决定。
- default branch 没有新 merge、release 或 workflow commit；`upstream/main` 仍为 #387 merge commit `146b75fc4b98`，该提交的核心 checks 全绿。

### 4.5 社区任务结论

本轮没有通过以下六个 gate 的直接实现候选：

| Gate | 要回答的问题 | 本轮结果 |
| --- | --- | --- |
| Evidence | 问题是否有日志、源码或合同证据 | #441/#412 有证据 |
| Reachability | 真实生产路径是否可达 | #441 是现有调用路径，#412 是真实生命周期改动 |
| Ownership | 是否已有 assignee / author / active PR | #412/#438 已有人负责 |
| Direction | 维护者是否确定了目标合同 | #441 尚未确定 |
| Scope | 能否形成独立小变更 | #412 与本地工作重叠较大 |
| Validation | 当前环境能否验证核心风险 | 可做 review，但不适合重复实现 |

结论不是“社区没事做”，而是当前高价值工作从写新代码转向：

1. review #412 的最新语义；
2. 为 #441 建立身份和权限矩阵；
3. 等 #438 PR 出现后，对比独立 v0.5.2 adapter；
4. 保持 #439 和其它 review gate 的低噪音观察。

## 5. PR #385 的原始问题

### 5.1 来源与当前状态

来源 Issue：[feat: observe SandboxWarmPool health in CodeInterpreter status #265](https://github.com/volcano-sh/agentcube/issues/265)。

PR：[feat: expose CodeInterpreter warm pool health #385](https://github.com/volcano-sh/agentcube/pull/385)。

| 项目 | 值 |
| --- | --- |
| Issue 创建 | 2026-04-10；open；无 assignee |
| PR 创建 | 2026-06-15 |
| PR base / merge base | `0fd9151d568c6dd96f0bbfb3740e482d2839f3f3` |
| PR exact head | `d885b4e32b903cd6315c938fc5d0372aca25654f` |
| 当前 upstream main | `146b75fc4b98f214988b5d0c5059a55a2bc1f9da` |
| 分叉 | main 侧 56 commits；PR 侧 3 commits |
| diff | 3 files，`+616/-14` |
| merge state | `DIRTY` |
| 真人 review | `@RainbowMango /assign`；没有技术 review、`/lgtm` 或 `/approve` |

最初实现和验证见 [Day10](day10-warmpoolavailable-poc.md)，Gemini event 噪音反馈、DCO 修复和第三个 commit 见 [Day15](day15-upstream-pr-review-and-snapstart-implementation.md)。

### 5.2 通俗解释：父对象说正常，底层容量可能已经没了

用户创建的是 `CodeInterpreter`，并在它的 `spec.warmPoolSize` 中声明希望长期保留多少个预热 sandbox。AgentCube 的 controller 会据此创建 `SandboxTemplate` 和 `SandboxWarmPool`。

但是当前 controller 的 `updateStatus` 只要前面的资源创建/更新没有报错，就直接写：

```text
CodeInterpreter.status.ready = true
Condition Ready = True / Reconciled
```

它没有读取 `SandboxWarmPool.status.readyReplicas`。

因此以下状态可以同时成立：

```text
CodeInterpreter Ready=True
SandboxWarmPool desired=4
SandboxWarmPool readyReplicas=0
```

这不是 Kubernetes 对象创建失败，而是“控制对象已存在，但预热容量不可用”。常见生产原因可能包括镜像拉取失败、错误的 RuntimeClass、Quota 不足、调度失败或底层 sandbox 长时间未 Ready。

> 注释：desired 表示期望容量，readyReplicas 表示当前已经可被 claim 使用的容量。对象存在不等于它提供的容量已经可用。

### 5.3 用户请求为什么会慢或失败

配置 warm pool 后，AgentCube 创建 session 时会创建 `SandboxClaim`。`agent-sandbox` controller 先尝试从 pool 选择并 adopt 一个预热 sandbox；如果没有候选，会继续走 cold-start 路径，创建新的 Sandbox。

当前真实调用链是：

```text
SDK / client
  -> WorkloadManager create CodeInterpreter session
  -> build SandboxClaim
  -> agent-sandbox 尝试 adopt ready warm Sandbox
  -> pool 无候选时退化为 cold start
  -> AgentCube 等 Claim 关联的 Sandbox Ready
  -> 成功返回，或在创建 deadline 内失败/超时
```

#265 最初把外部结果描述成“2 分钟后 500”。这个说法对今天已经不够准确：

- PR 基线已经把内部 sandbox creation timeout 映射为 `504 Gateway Timeout`；
- #387 又重构并强化了 Claim readiness、deadline 和错误分类；
- 真实用户结果可能是更慢的 cold start、504、终态创建失败或其它内部错误，不能固定写成 500。

但是错误码改进没有回答“为什么 warm path 突然变成 cold path”。#385 的价值正是在 session 请求发生之前和发生时提供 pool 健康信号。

## 6. #385 具体改了什么

### 6.1 三个文件的职责

| 文件 | 改动 | 责任 |
| --- | --- | --- |
| `cmd/workload-manager/main.go` | 注入 `GetEventRecorderFor("codeinterpreter-controller")` | 给 controller 提供 Kubernetes Event sink |
| `pkg/workloadmanager/codeinterpreter_controller.go` | 读取 `ReadyReplicas`、生成 condition/event、增加 owned-resource watch | 把底层状态投影到父资源 |
| `pkg/workloadmanager/codeinterpreter_controller_test.go` | condition、错误、事件去重、恢复和 reconcile 测试 | 验证状态映射和边界 |

生产代码约增加 118 行，测试约增加 498 行。`size/XL` 主要由测试体量造成，并不表示它引入了新的 CRD 或跨组件业务协议。

### 6.2 Condition 合同

PR 复用已有的 `CodeInterpreterStatus.Conditions []metav1.Condition`，没有新增 API 字段，因此原始版本不需要生成新的 CRD/client-go。

| 场景 | Condition status | Reason | 含义 |
| --- | --- | --- | --- |
| `warmPoolSize` 未配置或小于等于 0 | `Unknown` | `WarmPoolDisabled` | 没有启用 warm pool，不评价可用性 |
| 已配置但 pool 对象暂时不存在 | `False` | `WarmPoolNotFound` | 依赖对象尚未可见或确实缺失 |
| `readyReplicas == 0` | `False` | `WarmPoolEmpty` | 没有可立即 adopt 的预热容量 |
| `readyReplicas < ceil(desired/2)` | `False` | `WarmPoolBelowWatermark` | 可用容量低于 50% 水位 |
| 达到 50% 水位 | `True` | `WarmPoolReady` | 当前定义下认为 pool available |

这里的 `WarmPoolAvailable=True` 不表示所有副本都 Ready。例如 desired=4、ready=2 时也为 True。这个阈值来自 #265 的提议，尚未得到真人维护者技术确认。

### 6.3 Event 合同

PR 在以下状态第一次出现或 reason 改变时记录 Warning Event：

- `WarmPoolEmpty`；
- `WarmPoolBelowWatermark`。

它不会为 `WarmPoolNotFound` 发 Warning。原因是 controller 在同一次 reconcile 中创建 pool 后，cache 可能短暂还看不到对象；把这种瞬时 `NotFound` 直接写成 Warning 会制造噪音。

这项调整来自 Gemini review，但我们在 Day15 通过源码和单测独立验证后才采纳。AI comment 是发现线索，不是维护者共识。

### 6.4 `Owns(SandboxWarmPool)` 的作用

原 controller 只 watch `CodeInterpreter` 的 generation 变化。pool 的 status 从 0 恢复到 2 时，`CodeInterpreter.spec` 没变，因此父 controller 不一定会再次运行。

加入：

```go
Owns(&extensionsv1alpha1.SandboxWarmPool{})
```

以后 owned pool 的变化可以映射回 owner `CodeInterpreter` 并重新入队，从而更新 `WarmPoolAvailable`。

> 注释：`Owns` 不是把 pool 的控制权从 agent-sandbox 抢走。agent-sandbox 仍然写 `ReadyReplicas`；AgentCube 只是监听自己创建且 ownerReference 指向 CodeInterpreter 的 pool，并更新父资源状态。

### 6.5 它明确不做什么

#385 不会：

- 修复镜像、RuntimeClass、Quota 或调度错误；
- 主动补充 pool 副本；
- 阻止 SandboxClaim 走 cold start；
- 改变 Router 或 Store 行为；
- 让 session create fail fast；
- 把 `CodeInterpreter.status.ready` 改成 false；
- 保证用户请求一定成功。

因此准确定位是 **parent-level dependency health projection**，即父资源级的依赖健康投影，而不是 availability controller。

## 7. 为什么这个能力仍然需要

### 7.1 用户操作的是 CodeInterpreter，而不是底层 pool

`SandboxWarmPool` 属于 AgentCube 为实现 CodeInterpreter warm start 而创建的底层依赖。要求每个用户先找到同名 pool、再解释 desired/ready，意味着上层资源没有完整表达自己的运行状态。

#385 让以下命令直接给出线索：

```bash
kubectl describe codeinterpreter <name>
```

### 7.2 它把被动排错变成主动状态

没有该 condition 时，通常要先等 session 变慢或失败，再跨以下位置排查：

- WorkloadManager request log；
- SandboxClaim status；
- SandboxWarmPool status；
- Sandbox / Pod condition；
- scheduler、image pull、RuntimeClass 或 Quota event。

有 `WarmPoolAvailable=False` 后，可以在请求失败前就发现预热容量退化，并用 Event 时间与延迟/504 开始时间关联。

### 7.3 它没有重复 agent-sandbox 的职责

`agent-sandbox` 已经负责计算并写入 raw `ReadyReplicas`，v0.5.2 还为 `SandboxWarmPool` 提供 Ready/Desired printer columns。

但两层信息的责任不同：

| 层 | 所有者 | 回答的问题 |
| --- | --- | --- |
| `SandboxWarmPool.status.readyReplicas` | agent-sandbox controller | pool 中真实有多少 ready sandbox |
| `CodeInterpreter WarmPoolAvailable` | AgentCube CodeInterpreter controller | 这个依赖状态对 AgentCube 用户意味着什么 |

前者是原始事实，后者是产品/控制面语义。只要映射规则明确，父资源投影不是重复 controller，也没有引入第二个 `ReadyReplicas` writer。

### 7.4 v0.5.2 没有自动解决它

agent-sandbox v0.5.2 的 `extensions/v1beta1.SandboxWarmPoolStatus` 仍然包含：

```go
Replicas      int32
ReadyReplicas int32
Selector      string
```

我们的 blind adapter `compat/agent-sandbox-v052-independent@2d90b07` 只是把 AgentCube 从 alpha API 迁移到 beta API，当前 `CodeInterpreterReconciler.updateStatus` 仍然只写普通 `Ready=True`。

所以：

```text
v0.5.2 upgrade != WarmPoolAvailable feature
```

升级是重新承载 #385 的前置基线，不是替代方案。

## 8. 当前为什么不能直接推 #385

### 8.1 #387 引入了结构冲突

`git merge-tree` 显示当前冲突集中在：

- `pkg/workloadmanager/codeinterpreter_controller.go`；
- `pkg/workloadmanager/codeinterpreter_controller_test.go`。

`cmd/workload-manager/main.go` 可以自动合并。

#387 在 controller 中加入 `NetworkPolicyManagementUnmanaged` 及对应更新逻辑，并修改测试初始化 helper。#385 则在同一常量区、status 函数和测试 fixture 增加 warm-pool health 逻辑，因此文本和语义都需要人工合并。

这不是简单选择 ours/theirs：最终代码必须同时保留 #387 的网络策略修复和 #385 的状态投影。

### 8.2 v0.5.2 会再次改同一文件

#438 需要把 controller 切换到：

- `extensions/api/v1beta1`；
- `SandboxBlueprint`；
- `Replicas *int32`；
- beta `SandboxWarmPool` watch 类型。

现在先把 #385 rebase 到 v0.4.6 main，等 #438 合并后还要再迁移一次。重复解决相同文件的冲突没有收益，也容易在第二次迁移中丢掉 #387 或 #385 的语义。

### 8.3 新发现：Event RBAC 漏配

#385 注入了真实 EventRecorder，但 PR 没有修改：

```text
manifests/charts/base/templates/rbac/workloadmanager.yaml
```

当前标准 WorkloadManager ClusterRole 有 Sandboxes、SandboxClaims、SandboxWarmPools、CodeInterpreters、Pods、TokenReviews 和 Secrets 权限，但没有 core `events` 写权限。

因此标准 Helm ServiceAccount 下：

- `CodeInterpreter.status.conditions` 仍可更新；
- recorder 发出的 Warning Event 可能被 apiserver 以 `Forbidden` 拒绝；
- EventRecorder 是异步 best-effort，reconcile 不一定把这个失败返回给调用者；
- FakeRecorder 单测仍然会通过，形成部署 wiring 的假绿。

这是 source-proven 的部署权限缺口，不是本轮真实集群复现。恢复功能时需要补 core events 的最小写权限，并用标准 ServiceAccount 做一次实际 Event 验证。

### 8.4 现有 watch 测试不证明真实 watch 链路

PR 的 recovery 测试会修改 fake warm pool status，然后手动再次调用 `Reconcile`。它证明第二次 reconcile 会更新 condition，但没有证明 manager 的：

```text
SandboxWarmPool status event -> Owns watch -> owner mapping -> reconcile queue
```

真实生效。

恢复 PR 时至少需要 envtest/controller test 或 live cluster 证据，验证修改 owned pool status 后父 `CodeInterpreter` condition 自动变化。

### 8.5 旧 CI 不能代替新基线验证

`d885b4e` 的 11 个历史 checks 曾通过，但它们证明的是旧依赖和旧 main。

此外，标准 E2E 默认启用 mTLS，而 CodeInterpreter/WarmPool 目标测试会走 `skipIfMTLS`，所以绿色 job 可能只编译了目标代码，没有执行目标生命周期。

后续必须明确记录：

- 安装的 agent-sandbox exact version；
- CRD served/storage version；
- CodeInterpreter warm-pool 用例是 PASS 还是 SKIP；
- Condition、Event、watch、cold fallback 和恢复分别由哪条测试覆盖。

## 9. 重新推进前需要确定的设计问题

### 9.1 `Ready=True` 与 `WarmPoolAvailable=False` 是否允许共存

旧 PR 保留 `Ready=True`，因为 pool 空时仍可能 cold start 成功；`WarmPoolAvailable` 只表达预热能力退化。

但 API comment 把 `Ready` 描述为“ready to serve requests”。后续需要把语义明确成二选一：

- `Ready` 表示 CodeInterpreter 配置和依赖对象已 reconcile，warm capacity 由独立 condition 表达；
- `Ready` 聚合关键 dependency condition，pool 不可用时也变 False。

这会影响自动化消费者，不能由 rebase 时顺手决定。

### 9.2 50% 水位是否有产品合同

`ceil(desired/2)` 是 #265 提议的阈值，不是 agent-sandbox API 合同，也没有 SLO/容量数据支撑。

例如 desired=4、ready=2 会报告 available，但一次并发 3 个 claim 已会让第 3 个进入 cold path。需要确认 condition 要表达：

- 至少有 1 个可用；
- 达到固定百分比；
- 全部 desired 都 Ready；
- 或把 available 与 degraded 拆成不同语义。

在维护者确认前，50% 应写成待定 policy，而不是稳定 API 事实。

### 9.3 `ObservedGeneration` 与依赖状态 freshness

旧实现把 `WarmPoolAvailable.ObservedGeneration` 设置为当前 `CodeInterpreter.Generation`，但读取的 `ReadyReplicas` 可能仍对应旧 template 或旧 pool reconciliation。

特别是 warmPoolSize 或 template 刚改变时，父 generation 已更新，子 controller 可能尚未完成新一轮创建/替换。直接标记当前 generation 可能让消费者误以为 condition 已观察到新配置。

恢复实现时需要测试：

- size 扩容和缩容；
- template change 后 pool replacement；
- pool status cache lag；
- status writer 重启与重复事件。

### 9.4 Event 是否需要恢复信号

旧实现只发 degradation Warning，不发 recovery Normal Event。这个选择可以减少噪音，但会让仅看 Event 时间线的用户缺少恢复点。

需要根据项目现有 event 风格决定，而不是为了对称自动增加事件。

## 10. 推荐的后续处理顺序

### 阶段 A：现在

1. 保持 #385 和 fork branch 不动。
2. 不把旧 checks 描述成当前可合并证据。
3. 等 #438 出现 linked PR，冻结其 exact head。
4. 优先 review #412，避免相邻分支在快速变化的 main 上继续扩张。

### 阶段 B：#438 方案出现后

1. 比较 #438 与 blind adapter `2d90b07` 的 API、Claim、Store、migration 和 E2E 选择。
2. 检查 #438 是否已经包含父资源 warm-pool health；若包含，转为 review，不重复实现。
3. 若未包含，确认维护者是否仍接受 #265 的独立 observability scope。

### 阶段 C：v0.5.2 基线稳定后

基于最新 `upstream/main` 创建本地 validation branch，重新承载而不是盲目 ours/theirs：

1. 把 condition helper 和 watch 类型迁移到 `extensions/v1beta1`。
2. 保留 #387 的 `NetworkPolicyManagementUnmanaged` 行为。
3. 补 WorkloadManager Event RBAC。
4. 重审 `Ready`、threshold 和 freshness 合同。
5. 压缩重复 fake setup，保留有因果力的 table-driven tests。
6. 增加真实 `Owns` watch 和 Event 权限验证。
7. 跑 focused unit/race、Helm render/RBAC、非 mTLS CodeInterpreter lifecycle 和 exact-version runtime E2E。
8. 用 `git range-diff` 对照旧 #385，证明原始可观测性目标没有在迁移中丢失。

完成本地验证后，再让用户确认是否更新现有 upstream PR branch。任何 push 都会通知 reviewer，不能自动执行。

## 11. 验证与未验证项

### 11.1 本轮完成

- GitHub thread brief：#265、#385。
- PR metadata：changed files、commits、comments、review、merge state。
- Git refs：`upstream/main@146b75f`、`upstream/pr-385@d885b4e`。
- ancestry：`56 behind / 3 ahead`。
- structural merge：定位 controller 和 test 冲突。
- source path：当前 Ready writer、Claim cold fallback、2 分钟 create deadline、v0.5.2 `ReadyReplicas` producer。
- deployment wiring：确认标准 WorkloadManager RBAC 没有 core events write rule。
- test truthfulness：确认旧 recovery test 手动调用 reconcile，标准 E2E 存在目标用例默认 skip 风险。

### 11.2 本轮没有完成

- 没有在真实集群重新制造 empty pool。
- 没有用标准 WorkloadManager ServiceAccount 实测 Event `Forbidden`。
- 没有 rebase 或修改 #385。
- 没有读取 #438 assignee 的未公开/未形成 PR 的实现分支。
- 没有发 GitHub 评论、review 或提醒。

> 分析：这里不把“没有重新跑测试”写成偷懒。本轮任务是需求和社区状态回溯，源码已经足以证明旧 patch 的冲突与 RBAC 缺口；在没有确定 v0.5.2 最终基线前跑旧 head 的完整 E2E，不会增加是否应该现在推送的判断质量。

## 12. 工程学习

### 12.1 依赖状态不应只停在依赖对象上

一个高层 CR 如果创建并依赖低层 CR，就应决定哪些依赖健康需要投影到自己的 status。否则用户面对的是高层抽象，排障时却必须手工拆穿抽象。

### 12.2 “条件能写”不等于“事件能发”

FakeRecorder 很容易让 Event 逻辑全绿，但真实 Event 是 apiserver 写操作，需要部署身份的 RBAC。Review controller Event 时必须同时检查：

```text
Recorder injection -> event policy -> core events RBAC -> live persistence
```

### 12.3 绿色 CI 要问目标路径是否实际运行

测试 job 的名字包含 E2E，不代表 CodeInterpreter warm-pool 用例实际执行。依赖版本、auth mode、skip condition 和安装 CRD 都属于同一个验证合同。

### 12.4 冲突是重新审设计的机会，不只是 Git 操作

#385 的业务目标仍成立，但 #387、v0.5.2 和新 review 经验已经改变了正确实现边界。此时最差的处理不是“冲突难”，而是只把旧代码编译通过后就认为完成迁移。

## 13. 最终判断

#385 **值得保留需求，不值得现在直接推旧实现**。

它解决的是一个真实而清晰的观测缺口：AgentCube 的用户资源可以显示 Ready，而为其提供低延迟能力的 warm pool 已经没有足够 ready sandbox。Condition、Event 和 owned-resource watch 能把这个缺口从多组件日志排查变成父资源状态。

但后续版本不能只做 alpha -> beta import 替换。必须同时解决 Event RBAC、watch 的真实证据、`Ready` 与 `WarmPoolAvailable` 的关系、50% threshold 合同、依赖状态 freshness，以及 E2E 默认 skip。等 #438 的 v0.5.2 基线稳定后一次完成这些工作，比现在连续 rebase 两次更小、更清晰，也更容易获得有效 review。

## 14. 当日晚间变化：#438 已出现实现 PR #442

前一轮社区扫描冻结时，#438 只有 assignee，没有公开实现 PR。`2026-07-17 18:13 CST`，`@safiya2610` 创建了 [PR #442](https://github.com/volcano-sh/agentcube/pull/442)，开始升级 agent-sandbox v0.5.2 和 v1beta1 API。

这改变了 #385 的执行策略：

- 不能继续假设“等待中的 beta baseline 不存在”；
- 也不能因为 #442 已出现，就直接把 #385 旧提交 rebase 到它的高速变化 head；
- 应先冻结 exact head，在独立已验证 baseline 上完成 feature patch，再等待 #442 稳定或合并后只移植 feature commit。

本轮先冻结了两个 #442 head：

| 时间 | exact head | 状态 |
| --- | --- | --- |
| 开始实现时 | `f6487b25d45029fb134eef6cfaafb6b7a2e8613e` | 7 commits；DCO、build、codegen 和 E2E 仍有失败 |
| 完成本地 E2E 后 | `396e0e9b3253975f1b1a78ef7c5d01221b84ee2a` | 10 commits；build/lint/coverage/两个 E2E job 已绿，DCO 与 Codegen Check 仍失败 |

#442 的 3 个文件与 #385 全部重叠：

- `cmd/workload-manager/main.go`；
- `pkg/workloadmanager/codeinterpreter_controller.go`；
- `pkg/workloadmanager/codeinterpreter_controller_test.go`。

> 分析：这里的“重叠”不是说两个 PR 功能重复。#442 负责依赖/API baseline，#385 负责把 child WarmPool health 投影到 parent CodeInterpreter。它们的职责不同，但修改落点相同，因此 Git 冲突概率高。

## 15. 本地修复策略与分支门禁

没有直接修改旧 #385 branch，也没有读取 assignee 的私人分支。实现基于此前 blind adapter 的已验证 commit：

```text
upstream/main@146b75f
  -> d70ab94  Go/Kubernetes prerequisite
  -> 2d90b07  agent-sandbox v0.5.2/v1beta1 adapter
  -> bc89af4  PR #385 feature repair
```

本地 worktree 和 branch：

```text
/tmp/agentcube-pr385-v052-validation
fix/pr385-v052-validation
```

feature commit：

```text
bc89af44e3e8d8ca4cdc0f158a0d755fbdc451ff
feat: expose codeinterpreter warm pool health
Signed-off-by: ranxi2001 <ranxi169@163.com>
```

这个 commit 只包含 6 个 feature 文件，但整个 branch 相对 `upstream/main` 是 28 files、3 commits。因此当前 branch 只能作为验证载体，不能直接 force-push 到 #385。

> 注释：feature commit 是可移植单元；branch 不是可发布单元。把两者混为一谈，会把 v0.5.2 adapter 的 27 个文件一起塞进原本只做 observability 的 #385。

## 16. 六文件职责矩阵

| 文件 | 修改原因 | 不属于它的职责 |
| --- | --- | --- |
| `cmd/workload-manager/main.go` | 注入 modern Event recorder | 不决定何时告警 |
| `codeinterpreter_controller.go` | 计算 condition、去重 Event、监听 owned WarmPool | 不修复 warm pool 本身 |
| `workloadmanager.yaml` | 给生产 ServiceAccount 增加 Event write 权限 | 不扩大 Pod 写权限 |
| `codeinterpreter_controller_test.go` | 覆盖 threshold、错误、去重、恢复和 status-before-event | 不冒充真实 manager watch |
| `test/e2e/e2e_test.go` | 在真实 child ready 后等待 parent condition | 不强行制造不稳定的 pool degradation |
| `test/e2e/run_e2e.sh` | 部署后验证 Event create/patch 权限 | 不把 SAR 当作 Event persistence 证据 |

实现继续保留 #387 的两个关键语义：

1. 新建 `SandboxTemplate` 时设置 `NetworkPolicyManagementUnmanaged`；
2. 已有 template 不是 Unmanaged 时进行纠偏更新。

同时适配 v1beta1 的 `SandboxWarmPoolSpec.Replicas *int32`，没有把旧 v1alpha1 value field 写法搬回来。

## 17. Event API 选择：不再搬弃用 recorder

旧 #385 使用：

```text
mgr.GetEventRecorderFor
k8s.io/client-go/tools/record.EventRecorder
core/v1 events RBAC
```

v0.5.2 baseline 已使用 controller-runtime v0.24.1。当前实现改为：

```text
mgr.GetEventRecorder
k8s.io/client-go/tools/events.EventRecorder
events.k8s.io/v1 events RBAC
```

最小权限为：

```yaml
- apiGroups: ["events.k8s.io"]
  resources: ["events"]
  verbs: ["create", "patch"]
```

没有把 Event verbs 合并进 Pod rule，也没有同时授权 core Events 和 events.k8s.io 两套 API。

> 注释：modern recorder 的 singleton Event 首次走 Create；同一 series 后续更新走 Patch。因此只给 `create, patch`，不需要为了方便增加 list/watch/delete。

## 18. 实现时额外发现的边界 bug

旧 #385 用下面公式计算 50% low watermark：

```go
(desired + 1) / 2
```

当合法 int32 输入为 `math.MaxInt32` 时，`desired + 1` 溢出为负数，可能把只有 1 个 ready replica 的巨大 pool 误判为 healthy。

修复后使用：

```go
desired/2 + desired%2
```

它仍表示 `ceil(desired / 2)`，但不会先做可能溢出的加法。单测明确断言最大 int32 的 watermark 为 `1073741824`。

> 分析：这不是为了追求理论边界而扩大 CRD scope。当前 CRD 只有 int32 format，没有 Maximum；既然 API 接受该值，controller 的整数运算就不能静默溢出。

## 19. 测试真实性调整

原 #385 新增约 498 行 test，但 recovery test 在修改 child status 后手工第二次调用 `Reconcile`。它只能证明 reconcile logic，不能证明 `.Owns(&SandboxWarmPool{})` wiring。

本轮保留 fake-client 层的职责：

- disabled / not found / empty / below watermark / ready；
- odd desired count 的 ceil threshold；
- `math.MaxInt32` 无溢出；
- child GET error 向上传递；
- Empty 和 BelowWatermark 才发 Warning；
- NotFound 不发 transient Warning；
- status 写成功后才发 Event；
- status 写失败不发 Event；
- generation 变化但 degradation reason 不变时不重复告警；
- pool recovery 后 condition 变 True 且不发 Warning；
- unchanged status 确实没有调用 status writer。

真实 manager 链路放进现有 `TestCodeInterpreterWarmPool`：

```text
SandboxWarmPool ReadyReplicas changes
  -> Owns watch
  -> CodeInterpreter enqueue
  -> WarmPoolAvailable=True / WarmPoolReady
  -> ObservedGeneration == parent Generation
```

独立非 mTLS matrix 已设置 `E2E_REQUIRE_CODEINTERPRETER=true`，所以目标用例不能因 mTLS 静默 skip。

> 分析：这个 E2E 对 watch 有强证据，但不是形式化证明。它没有先强制观察 False 再手工制造一次 child status-only transition；理论上偶发 parent reconcile 也可能更新 condition。当前没有引入 envtest 基建，真实 Pod readiness 又不可能在首次 API reconcile 内同步完成，因此该证据对本 PR 已足够，但 PR 文案不能夸大成严格 causal proof。

## 20. 验证结果

### 20.1 静态与单元验证

以下均通过：

- `go test` 全部非 E2E Go packages；
- focused workloadmanager tests，关键用例 `-count=100`；
- focused race tests，关键用例 `-count=5`；
- `go test -race ./pkg/workloadmanager`；
- `go vet ./...`；
- `make lint`；
- `make build-all`；
- `make fmt-check`；
- `make helm-template`；
- `make helm-lint`；
- `bash -n test/e2e/run_e2e.sh`；
- `git diff --check`；
- commit 后 `make gen-check`。

本地 workloadmanager package coverage 为 `61.1%`。新增 condition calculator 和 Event policy helper 均为 `100%` statement coverage；真实 `SetupWithManager` wiring 由 E2E 而不是 fake coverage 证明。

### 20.2 完整 v0.5.2 runtime E2E

环境：独立 kind cluster `agentcube-e2e-pr385`，`MTLS_ENABLED=false`，`E2E_REQUIRE_CODEINTERPRETER=true`。

关键结果：

| 验证 | 结果 |
| --- | --- |
| 4 个 agent-sandbox CRD storage version | 全部 `v1beta1` |
| WorkloadManager Event RBAC SAR | events.k8s.io `create=yes`, `patch=yes` |
| `TestCodeInterpreterWarmPool` | PASS，包含新 parent condition 断言 |
| WarmPool load | 100/100 success |
| Basic invocation load | 20/20 success |
| Go E2E suite | PASS，`280.939s` |
| Python CodeInterpreter | 3/3 PASS |
| LangChain sandbox | 4/4 PASS |
| MCP local HTTP | 5/5 PASS |
| MCP stdio | 1/1 PASS |
| MCP in-cluster Pod | 1/1 PASS |

测试结束后删除专用 kind cluster，8080、8081、19446 均无残留 listener。

## 21. 失败过程与根因

### 21.1 多架构镜像导入失败

`kind load docker-image` 对 agent-sandbox controller、Python 和 Redis 镜像出现：

```text
ctr: content digest ... not found
```

这是当前 Docker containerd image store 导出 multi-platform image 的已知环境限制。E2E script 已明确允许该步骤失败，kind node 随后从 registry 拉取镜像；controller、Redis 和所有测试正常运行。

处理方式不是修改产品代码，而是保留 warning、观察实际 Pod rollout，并以最终 runtime 结果校准。

### 21.2 第一次 `make gen-check` 返回 2

第一次在未提交 feature diff 上运行 `make gen-check`，生成命令完成后执行：

```text
git diff --exit-code
```

它把本轮 6 个预期修改也当成 dirty diff，因此返回 2。检查 `git status` 后确认没有新增 CRD、client-go、go.mod 或 go.sum diff。

feature commit 完成后，在 clean worktree 再跑同一命令，`git diff --exit-code` 通过。

> 注释：第一次失败不是 codegen 回归，但也不能直接忽略退出码。必须先比较生成前后文件集合，再在 clean commit 上复验。

## 22. 仍然没有宣称的证据

本轮没有在 live E2E 中查询并断言某一条 Warning Event 已持久化。现有证据拆成两层：

1. FakeRecorder 证明 Empty/BelowWatermark policy、去重和 status-before-event 顺序；
2. live SAR 证明部署身份拥有 events.k8s.io create/patch。

这比旧 PR 完全漏 RBAC 更完整，但仍不等于直接观察 Event object。为了制造 deterministic degradation 而引入坏镜像、状态写竞争或额外 envtest 基建，会明显扩大 scope 和 flake 风险，因此当前不做。

同样，v0.5.2 `SandboxWarmPoolStatus` 仍没有 child `ObservedGeneration`。父 condition 的 ObservedGeneration 只表示“controller 按当前 CodeInterpreter generation 重算”，不能证明 `ReadyReplicas` 一定对应最新 child spec。

## 23. 当前最终判断

功能修复已经在已知绿色 v0.5.2 baseline 上完成，代码和测试没有发现阻塞问题；但 #385 仍不能现在更新。

唯一阻塞是 scope / base gate，而不是功能不完整：

- #442 是 active assignee 的 v0.5.2 实现；
- #442 仍在变化，当前 DCO 和 Codegen Check 未绿；
- 本地 validation branch 包含 27 个额外 adapter 文件；
- 直接 push 会重复 #442 并扩大 #385。

下一步停止条件明确为：等待 #442 稳定并进入 upstream main，然后从最新 `upstream/main` 创建 clean topic branch，只移植 `bc89af4` 的 6-file feature semantics，重新做 range-diff 和目标 E2E，再让用户确认 exact force-with-lease update 与 PR body。
