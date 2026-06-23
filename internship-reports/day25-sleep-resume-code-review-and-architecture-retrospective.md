# Day 25: Sleep/Resume 代码审查与架构复盘

日期：2026-06-23

## 目标

今天不继续写第三阶段代码，切换到 reviewer 视角，审查 Day24 两层本地实现：

```text
/home/agentcube-sleep-resume-store-state
branch: feat/sleep-resume-store-state
base: upstream/main bed6bd4

3d0427a feat: add sandbox session state CAS store support
cb66c8a feat: add workload manager session lifecycle service
```

审查重点不是“代码能不能编译”，而是：

- 需求拆分是否合理。
- Store / WorkloadManager / Router / RuntimeProvider 的职责边界是否干净。
- 是否符合整洁架构里“核心规则不依赖外部 runtime 细节”的方向。
- 测试是否覆盖真实风险，而不是只覆盖 happy path。
- 如果后续作为 PR 给维护者 review，哪些问题会被问到。
- 第三阶段 GC split 前需要哪些设计 gate。

## 总体结论

当前两阶段实现是合理的阶段性切分，但还不能被描述为完整 Sleep/Resume 功能。

可以接受的部分：

- 第一阶段先补 Store 状态、CAS 和 pause expiry index，是正确的基础层。
- 第二阶段只补 WorkloadManager 内部 lifecycle service 和 fake provider tests，避免过早同时改 GC、Router、真实 agent-sandbox 和 e2e。
- `RuntimeProvider` 抽象方向是对的，能避免把 `agent-sandbox v0.4.6 spec.replicas=0/1` 或 `v0.5.x operatingMode=Suspended/Running` 写死到 Router / Store。
- Store CAS 和 WorkloadManager 并发 resume 测试证明了一个关键设计假设：并发正确性不是优化项，而是 Sleep/Resume 的必要条件。

需要继续保持谨慎的部分：

- 当前 service 尚未接入真实 `Server`、HTTP route、GC 或 Router。
- provider failure 后 `markFailed` 是 best-effort，如果 CAS 失败或 Store 失败，原始 provider error 会返回，但 session 可能停留在 `pausing` / `resuming`。这需要第三阶段前明确恢复策略。
- `PauseModeHard` 当前固定在 constructor 内，适合 MVP，但后续如果支持 soft / snapshot，需要从 config / capability negotiation 进入，而不是散落 if/else。
- `Capabilities(ctx)` 当前只是接口预留，还没有被 service 使用；review 时要说明这是为后续 provider selection / validation 保留，不是已经完成的 capability enforcement。
- `EndpointRevision` 只是递增，没有被 Router 消费；当前只能说“为后续 Router 判断 endpoint refresh 预留”，不能说已经实现了 endpoint consistency。

## 架构边界复盘

### 当前分层

```text
Router
  后续只负责 owner/auth check、resume-before-proxy、proxy。
  不应该知道 replicas、OperatingMode、Pod delete/recreate。

WorkloadManager
  负责 session lifecycle 编排：
  ready -> pausing -> paused
  paused -> resuming -> ready
  provider failure -> failed

Store
  负责持久化 session metadata、状态、索引和 CAS。
  不理解 Kubernetes、agent-sandbox 或 Pod。

RuntimeProvider
  负责屏蔽底层 runtime 差异。
  后续可以接 agent-sandbox v0.4.6 / v0.5.x / soft pause / snapshot pause。

agent-sandbox / Kubernetes
  是外部实现细节。
  不应该直接进入 Router 或 Store。
```

这符合整洁架构的基本方向：核心 lifecycle policy 依赖抽象接口，外部 runtime 通过 provider 实现注入。现在的关键是后续不要破坏这个边界。

### 为什么不继续直接写 GC / Router

如果现在直接写 GC split 或 Router resume-before-proxy，很容易同时遇到：

- `pauseTimeout` 配置从哪里来。
- Router 等待 resume 还是返回 retry。
- 并发 Router 请求如何共享一次 resume。
- owner/auth check 在 resume 前还是后。
- agent-sandbox provider 对 direct Sandbox 和 warm-pool SandboxClaim 是否语义一致。
- pause 后 entrypoint 为空时 Router 如何返回错误。
- provider failure 后 `pausing` / `resuming` 卡住如何恢复。

这些属于架构决策，不是简单代码补丁。先做 Day25 review，是为了在继续写代码前把这些问题列成 gate。

## Code Review Matrix

| 文件 / 区域 | 职责 | 为什么存在 | Review 风险 | 测试覆盖 | Reviewer 可能问什么 | 当前回答 |
| --- | --- | --- | --- | --- | --- | --- |
| `pkg/common/types/sandbox.go` | Store session metadata 和状态常量 | Sleep/Resume 需要 `paused` / `pausing` / `resuming` / failure reason / pause timestamps / endpoint revision | `SandboxInfo` 字段变多，可能被质疑是否一次性加太多；`RuntimeProvider` / `SandboxName` / `SandboxClaimName` 尚未被真实路径消费 | Store 和 lifecycle tests 间接覆盖 JSON 字段；未覆盖 API 兼容性 | 这些字段哪些是当前阶段必需，哪些是后续预留？ | `PausedAt` / `PauseExpiresAt` / `FailureReason` / status 是当前必需；runtime/name fields 是为 provider 和 warm-pool identity 预留，正式 PR 可考虑按阶段减少 |
| `pkg/store/interface.go` | Store 抽象 | 增加 CAS 和 pause-expired listing | 所有 fake store 都要补方法；接口扩展影响面较大 | fake store 编译覆盖，Redis/Valkey 实现测试覆盖 | 为什么不用普通 Update？ | 并发 resume 必须原子检查状态；普通 read-update-write 会双赢 |
| `pkg/store/error.go` | 统一错误类型 | 区分 not found 和 status conflict | 错误语义是否足够细；是否需要 typed conflict 包含 current status | Redis/Valkey conflict tests | Router/WorkloadManager 如何处理 conflict？ | 当前 WorkloadManager 包装成 `ErrSessionStateConflict`；后续 Router 可据此返回 retry/409 |
| `pkg/store/store_redis.go` | Redis session JSON、expiry index、pause index、Lua CAS | Redis 是当前主要持久化后端；CAS 必须在 Store 层原子执行 | Lua 只检查 `status`，不检查 `EndpointRevision`；pause index 更新和 JSON 写入绑在同一个 Lua 内，但 expiry/last_activity 不更新 | CAS success/conflict/not-found/concurrent，pause index，delete cleanup | 为什么 CAS 不检查 revision？ | 当前状态机只需要 expected status；如果后续要防止更细粒度覆盖，可引入 revision CAS |
| `pkg/store/store_valkey.go` | Valkey 与 Redis 语义对齐 | AgentCube 已支持 Valkey，不能只改 Redis | 两份 Lua / index 逻辑重复，后续维护要同步 | 与 Redis 对等测试 | 是否可以抽公共逻辑？ | 当前先保持两后端已有风格；抽象可后续做，不混入 feature |
| Store tests | 证明 Store 层语义 | CAS 和 pause index 是后续 GC/Router 的基础 | Redis 测试里有一处 `got` 复读变量小瑕疵，但 Valkey 已正确重读；不影响主要意图但正式 PR 前应修 | Redis/Valkey 都覆盖核心路径 | 是否测了 delete 清理 pause index？ | 已测 |
| `pkg/workloadmanager/session_lifecycle.go` | WorkloadManager 内部 pause/resume 编排 | 把 lifecycle policy 放在 WorkloadManager，不让 Router/Store 理解 runtime 细节 | 尚未接 Server；`Capabilities` 未使用；`markFailed` best-effort；final CAS conflict after provider success 可能留下真实 runtime 与 Store 状态不一致 | fake provider unit tests + race | provider 成功但 final CAS 失败怎么办？ | 当前会返回 conflict，但真实 runtime 已变化；第三阶段前需要补 reconciliation / retry strategy |
| `pkg/workloadmanager/session_lifecycle_test.go` | fake provider 测 lifecycle policy | 不依赖 Kubernetes，先验证控制面语义 | fake provider 不能证明真实 agent-sandbox pause/resume；没有测 final CAS 失败 after provider success | success/failure/concurrency/wrong state | 这些测试能证明功能能跑吗？ | 只能证明 WorkloadManager policy；真实 runtime 还需要 provider/e2e/math-agent |
| `pkg/workloadmanager/sandbox_helper.go` | 创建 sandbox 时使用状态常量 | 避免新增状态常量后继续散落裸字符串 | 小改动容易被认为 drive-by cleanup | 现有 workloadmanager tests 编译覆盖 | 为什么要改这个文件？ | 这是让新增状态常量成为单一来源，属于本 feature 的一致性维护 |
| `pkg/router/session_manager_test.go` / `handlers_test.go` / `garbage_collection_test.go` | fake store 补接口 | Store 接口扩展后保持旧测试编译 | 没有行为变化，容易被问是否只是机械改动 | 编译覆盖 | 为什么这些测试文件变了？ | 只是 fake store 满足新接口，不改变 Router/GC 行为 |

## 当前 Review 风险分级

### 高风险：provider 成功后 final CAS 失败

路径：

```text
pauseSession:
ready -> pausing CAS 成功
provider.Pause 成功
pausing -> paused CAS 失败
```

或者：

```text
resumeSession:
paused -> resuming CAS 成功
provider.Resume 成功
resuming -> ready CAS 失败
```

这时真实 runtime 可能已经变了，但 Store 没有进入目标状态。当前代码只返回错误，不做补偿。第三阶段接真实 provider 前必须回答：

- 是否允许后台 reconciler 修复这种状态。
- 是否应该 retry final CAS。
- 是否需要 provider 操作 idempotent。
- 是否需要 Store 记录 provider operation id。
- Router 看到 `pausing` / `resuming` 卡住时如何处理。

审查结论：这不是第二阶段必须解决的问题，但必须作为第三阶段 gate。

### 中风险：失败状态过于粗

当前 provider failure 后统一进入 `failed`，记录 `FailureReason`。问题是：

- pause 失败和 resume 失败是否都应该进入 terminal failed？
- pause 失败是否可以回滚到 `ready`？
- resume 失败是否应该保留 `paused`，让用户稍后重试？
- `failed` 是否会被 GC 清理？

审查结论：第二阶段用 `failed` 收敛错误是合理的测试起点，但产品语义还要再设计。

### 中风险：状态字段可能一次性加太多

`SandboxInfo` 新增字段比较多。对于本地实验这没问题，但如果将来提 upstream PR，reviewer 可能要求：

- 只加入当前阶段实际消费的字段。
- 把 provider identity / claim name / pod name 延后到真实 provider PR。
- 对 JSON 兼容性和旧 session 反序列化做说明。

审查结论：正式 PR 应考虑拆字段，至少在 PR body 解释哪些是当前必需，哪些是后续 provider identity 预留。

### 中风险：RuntimeCapabilities 尚未参与决策

`RuntimeProvider.Capabilities(ctx)` 当前没有被 service 调用。后续需要决定：

- service 是否在 pause 前检查 `HardPause`。
- 如果 provider 不支持 pause，返回 501 / unsupported 还是降级 delete。
- warm-pool session 是否要求 `AdoptedSandbox`。

审查结论：接口方向对，但后续要把 capability 从“描述”变成“gate”。

### 低风险：测试 fake store 比真实 Store 简单

`lifecycleMemoryStore` 只模拟 CAS 和基本读写，不模拟 pause index、expiry index、Redis Lua 错误等。这是合理的，因为 Store 细节已有独立测试。

审查结论：fake store 不应膨胀成第二个 Redis；保持 WorkloadManager 测试聚焦 lifecycle policy。

## 测试矩阵：风险到测试

| 风险 | 当前测试 | 是否充分 | 后续需要 |
| --- | --- | --- | --- |
| Store CAS 双写 | `TestRedisStore_UpdateSandboxStatusCAS_ConcurrentConflict` / `TestValkeyStore_UpdateSandboxStatusCAS_ConcurrentConflict` | 对 Store 层充分 | 后续 Router 并发 resume e2e |
| pause index 返回非 paused 脏数据 | `ListPauseExpiredSandboxes` 过滤 status | 基础充分 | GC split 后测 ready session 不会被 pause-expired delete |
| delete 后 pause index 残留 | Redis/Valkey delete cleanup tests | 充分 | e2e cleanup 检查 CR/Pod/Store |
| WorkloadManager pause success | `TestSessionLifecycleServicePauseSession` | 对 fake provider 充分 | real provider hard pause e2e |
| WorkloadManager resume success | `TestSessionLifecycleServiceResumeSession` | 对 fake provider 充分 | Router resume-before-proxy e2e |
| provider pause failure | `TestSessionLifecycleServicePauseProviderFailureMarksFailed` | 初步充分 | 产品语义决定后可能改为 rollback ready |
| provider resume failure | `TestSessionLifecycleServiceResumeProviderFailureMarksFailed` | 初步充分 | 产品语义决定后可能改为 stay paused / retry |
| concurrent resume | `TestSessionLifecycleServiceResumeConcurrentConflict` | WorkloadManager 层充分 | Router 并发请求是否等待同一个 resume 尚未测 |
| wrong initial state | `TestSessionLifecycleServiceRejectsWrongInitialState` | 覆盖 resume-on-ready | 还应补 pause-on-paused / delete-on-transitioning 策略 |
| final CAS after provider success 失败 | 当前没有测试 | 不充分 | 第三阶段前补 fake store 注入 final CAS failure |
| capability unsupported | 当前没有测试 | 不充分 | provider capability gate 后补 |
| owner/auth before resume | 当前没有测试 | 不充分 | Router 阶段必须补 |
| math-agent session preservation | 当前没有测试 | 不充分 | real e2e 阶段补 |

## 第三阶段前置 Gate

### Gate 1: GC split 语义

继续写 `garbage_collection.go` 前必须明确：

- `sessionTimeout` 是否从 `Ready -> Deleted` 改成 `Ready -> Paused`。
- `pauseTimeout` 从哪里来：新增 CRD / config，还是暂时默认等于 `sessionTimeout`。
- `maxSessionDuration` 是否对 `ready` / `paused` / `pausing` / `resuming` / `failed` 都生效。
- `failed` session 是立即 delete，还是保留一段时间便于排障。
- GC 遇到 `pausing` / `resuming` 超时如何处理。

建议先写 GC decision table，不要直接改代码。

### Gate 2: Router resume-before-proxy

继续写 Router 前必须明确：

- owner/auth check 必须在 resume 前完成，避免未授权请求触发资源恢复。
- Router 看到 `paused` 是同步等待 resume，还是返回 retry。
- Router 看到 `resuming` 是等待已有操作，还是返回 `409/Retry-After`。
- resume 成功后 Router 应重新读取 Store，确保拿到新 `EntryPoints` / `EndpointRevision`。
- 如果 resume 失败，用户看到的错误码和错误体是什么。

建议先补 Router 行为表，再写 handler tests。

### Gate 3: RuntimeProvider 真实实现

接 `agent-sandbox` 前必须按版本拆：

| agent-sandbox 版本 | hard pause 字段 | Review 注意点 |
| --- | --- | --- |
| `v0.4.6` | `Sandbox.spec.replicas=0/1` | 当前 stable latest；和 #387 兼容基础一致 |
| `v0.5.x` | `Sandbox.spec.operatingMode=Suspended/Running` | v1beta1 API，不能混进 v0.4.6 PR |

还必须区分 direct Sandbox 和 warm-pool SandboxClaim：

- Direct CodeInterpreter 可以先支持。
- Warm-pool-backed session 要确认 pause adopted Sandbox、delete claim、或让 warm pool refill 的语义。
- 如果第一版不支持 warm pool pause，必须显式返回 unsupported，而不是 silently delete。

### Gate 4: E2E / math-agent 验证

真实 runtime provider 合入前，最低测试证据应包含：

- Direct CodeInterpreter create -> ready -> pause -> resume -> request succeeds。
- pause 后 Pod 释放或状态进入 Suspended。
- resume 后 session id 不变。
- resume 后 entrypoint 刷新，旧 endpoint 不再被 Router 使用。
- explicit delete 清理 Store、Sandbox/Claim、Pod。
- math-agent 多轮请求：pause/resume 后同一个 session 继续可用。
- 资源残留检查：Pod、Sandbox CR、SandboxClaim、Redis/Valkey index。

## 作为 reviewer 应该问的问题

如果以后只负责 review，不写代码，这组改动应该问：

1. 这个 PR 是否只解决一个阶段，还是混入了 GC、Router、provider 和 API 设计？
2. Store CAS 是否真的原子，还是 read-update-write？
3. 状态机有没有明确非法转移？
4. provider 成功但 Store 更新失败时如何恢复？
5. pause 后旧 endpoint 是否可能被继续使用？
6. resume 是否刷新 entrypoint，Router 是否重新读取 Store？
7. owner/auth 是否在恢复资源前检查？
8. `pauseTimeout` 和 `sessionTimeout` 是否语义清楚？
9. warm-pool session 是否支持，不支持时是否显式报错？
10. 测试是否覆盖失败路径、并发路径、cleanup，而不只是 success path？

## 当前最佳下一步

不建议马上写大量第三阶段代码，也不另开 Day26。

同一主题继续在 Day25 文件内扩写，直到这份复盘至少达到 600 行，再考虑切换到新文件。这样做的原因是：当前仍然围绕同一个审查对象，也就是 `feat/sleep-resume-store-state` 两层 commit；如果 200 多行就换文件，后续会把审查结论、行为表、测试计划和 PR 材料拆散，不利于复盘。

本文件继续补充：

- GC decision table。
- Router status handling table。
- 错误码 / retry 语义。
- owner/auth 前置规则。
- provider failure 后的 rollback / failed / retry 策略。
- 哪些行为第一版不支持。
- 第三阶段如果要写代码，应先满足哪些 review gate。

## 文件续写规则

从这次开始，同一个日报 / 复盘文件如果还在同一主题内，不应该过早切换到新 day 文件。

当前执行规则：

```text
同一主题文件至少写到 600 行，再考虑换新文件。
```

对 Day25 来说，主题是：

```text
Sleep/Resume 代码审查与架构复盘
```

所以 GC decision table、Router status handling table、RuntimeProvider gate、测试设计、PR review 问题，都应该继续写在 Day25，而不是新开 Day26。

## GC Decision Table 草案

第三阶段如果要修改 `pkg/workloadmanager/garbage_collection.go`，不能只把 delete 改成 pause。GC 是生命周期策略的集中入口，必须先把状态和时间条件列清楚。

### 当前 GC 语义

当前 main 的真实行为可以简化为：

| 条件 | 当前行为 |
| --- | --- |
| session 超过 `maxSessionDuration` / `ExpiresAt` | delete |
| session idle 超过 `IdleTimeout` / `sessionTimeout` | delete |
| Store 找不到 session | 跳过或返回 not found |
| delete sandbox 失败 | 记录错误，下轮继续 |

这个模型简单，但和 Sleep/Resume 目标不一致。Sleep/Resume 需要把 idle 处理拆成两段：

```text
Ready idle -> Paused
Paused timeout -> Deleted
```

### 目标 GC 语义

建议第三阶段先按下面表格实现，不要直接扩展更多策略。

| 当前状态 | 时间条件 | 目标行为 | 说明 |
| --- | --- | --- | --- |
| `ready` | `now >= ExpiresAt` | delete | max session duration 仍然优先 |
| `ready` | `now - LastActivityAt >= IdleTimeout` | pause | 这是 Sleep/Resume 的核心变化 |
| `ready` | 未过期且未 idle | keep | 不做动作 |
| `paused` | `now >= ExpiresAt` | delete | 绝对 TTL 仍然优先 |
| `paused` | `now >= PauseExpiresAt` | delete | pause timeout 后清理资源 |
| `paused` | 未过期且 pause 未超时 | keep | 等 Router resume |
| `pausing` | transition 超时 | mark failed 或 retry | 需要单独策略 |
| `resuming` | transition 超时 | mark failed 或 retry | 需要单独策略 |
| `failed` | 保留窗口超时 | delete | 便于排障后清理 |
| `deleted` | 任意 | ignore | Store 中理想情况下不应长期保留 |
| unknown status | 任意 | log + ignore 或 mark failed | 防止误删 |

### 关键优先级

GC 判断顺序建议如下：

1. 先判断绝对过期：`ExpiresAt` / `maxSessionDuration`。
2. 再判断状态。
3. 对 `ready` 判断 idle pause。
4. 对 `paused` 判断 pause timeout delete。
5. 对 transition 状态判断是否卡死。
6. 对 unknown 状态只记录，不直接删除。

原因：

- `maxSessionDuration` 是用户或系统给 session 的绝对上限，优先级应高于 pause/resume。
- idle pause 是优化资源使用，不应覆盖 max TTL。
- paused session 仍然占 Store / CR / PVC 等资源，必须有 pause timeout。
- transition 状态如果没有超时策略，会让 session 永久卡在 `pausing` / `resuming`。

### GC 不应该做的事

第三阶段 GC 不应该直接做这些：

- 不应该自己理解 agent-sandbox `replicas` 或 `OperatingMode`。
- 不应该直接 patch Kubernetes Sandbox。
- 不应该绕过 WorkloadManager lifecycle service 去改 Store 状态。
- 不应该在 owner/auth 未知的情况下做 Router 语义。
- 不应该在失败时直接清空 Store，导致排障信息丢失。

GC 应该调用 WorkloadManager lifecycle service 或同层内部接口，让状态机保持单一入口。

### GC review 问题

审 GC split 时应该问：

1. idle delete 是否真的变成 idle pause？
2. max TTL 是否仍然能删除 `ready` 和 `paused`？
3. `paused` 是否有独立 pause timeout？
4. `pausing` / `resuming` 卡死是否有出路？
5. GC 是否绕过了 lifecycle service？
6. delete 是否清理 Store index 和 runtime resource？
7. GC 测试是否覆盖 ready idle、paused expired、max TTL、transition stuck？

## Router Status Handling Table 草案

Router 是用户请求进入 sandbox 的入口。Sleep/Resume 对 Router 的影响很大，因为 Router 看到同一个 session id 时，不能再假设 sandbox 一定 ready。

### Router 当前语义

当前 Router 大致是：

```text
request with x-agentcube-session-id
  -> load sandbox from Store
  -> owner check
  -> proxy to current entrypoint
  -> update last activity
```

如果 sandbox 已经暂停，entrypoint 可能为空或旧 Pod 已不存在。此时继续 proxy 会得到连接失败、timeout 或 sandbox unreachable。

### Router 目标语义

建议目标表：

| Store status | Router 行为 | 是否调用 WorkloadManager | 用户响应 |
| --- | --- | --- | --- |
| `ready` | 正常 proxy | 否 | sandbox response |
| `paused` | owner/auth 通过后 resume，再重新读取 Store，再 proxy | 是 | sandbox response 或 resume error |
| `resuming` | 等待已有 resume 或返回 retry | 可选 | `409` / `202` / `Retry-After` 待定 |
| `pausing` | 不应 proxy，返回 retry | 否 | `409` / `Retry-After` |
| `failed` | 不应自动恢复，返回明确错误 | 否 | `500` 或 domain error |
| `deleted` | session 不存在或已结束 | 否 | `404` |
| unknown | 不 proxy | 否 | `500` + log |

### owner/auth 前置规则

owner/auth 必须在 resume 前执行。

原因：

- resume 会恢复资源，可能消耗 CPU/memory。
- 如果未授权请求能触发 resume，就存在资源滥用风险。
- 当前 AgentCube 已经有 owner check，Sleep/Resume 不应该绕过它。

目标顺序应该是：

```text
load session
check owner/auth
if status == paused:
  call WorkloadManager resume
  reload session
  proxy using refreshed entrypoint
```

不能这样做：

```text
load session
resume paused session
check owner/auth
proxy
```

### Router 等待还是 retry

这里需要产品决策。

方案 A：Router 同步等待 resume。

优点：

- 用户体验简单。
- SDK 不需要处理额外 retry。
- 对短 resume latency 友好。

缺点：

- Router handler 会被阻塞。
- resume 慢或失败时请求延迟高。
- 多个并发请求需要共享同一个 resume，否则会出现大量 conflict。

方案 B：Router 返回 retry。

优点：

- Router 不长时间阻塞。
- 实现更简单。
- 对慢 resume 更安全。

缺点：

- SDK / client 必须处理 retry。
- 用户第一次请求会失败或需要轮询。
- 对交互式 agent 体验不如同步等待。

方案 C：Router 等待短时间，超时返回 retry。

优点：

- 兼顾低延迟 resume 和慢路径保护。
- 可以设置较小 wait budget，例如 5s 或 10s。

缺点：

- 实现最复杂。
- 需要明确 `resuming` 状态下多个请求的等待机制。

当前建议：

```text
MVP 可先用方案 C 的简化版：
paused -> 调 WorkloadManager resume 并等待；
resuming -> 返回 409 + Retry-After；
后续再优化为等待已有 resume。
```

### Router 必须重新读取 Store

resume 成功后，Router 不能继续使用 resume 前读到的 `SandboxInfo`。

原因：

- pause 时 `EntryPoints` 已清空。
- resume 后 Pod IP / endpoint 可能变化。
- `EndpointRevision` 会递增。
- provider 可能更新 `PodName`、`SandboxName` 或其他 runtime metadata。

目标流程：

```text
oldInfo := store.Get(sessionID)
if oldInfo.Status == paused:
  workloadManager.Resume(sessionID)
newInfo := store.Get(sessionID)
proxy(newInfo.EntryPoints)
```

review 时要特别检查这一点：resume 后是否 reload Store。

## Error / Retry 语义草案

错误码不能随意返回，否则 SDK 和用户体验会混乱。建议先按内部错误分类，不急着定最终 HTTP code。

| 场景 | 内部错误 | 建议 HTTP 语义 | 是否 retry |
| --- | --- | --- | --- |
| session 不存在 | `store.ErrNotFound` | `404` | 否，除非用户新建 session |
| owner mismatch | auth error | `403` | 否 |
| paused resume 成功 | nil | `200` / proxy response | 不需要 |
| paused resume provider 失败 | provider error | `500` 或 `503` | 可 retry，但需要 backoff |
| concurrent resume conflict | `ErrSessionStateConflict` | `409` | 是 |
| resuming in progress | status `resuming` | `409` 或 `202` | 是 |
| pausing in progress | status `pausing` | `409` | 是 |
| failed session | status `failed` | `500` 或 domain error | 视策略 |
| deleted session | status `deleted` | `404` | 否 |
| no entrypoint after resume | validation error | `503` | 可能 |

### 为什么不全部返回 500

如果所有状态异常都返回 500，SDK 无法区分：

- session 已不存在。
- 当前正在 resume，可以重试。
- 用户无权限。
- runtime provider 失败。
- Router 读到了旧 endpoint。

这些对自动化 agent 很关键。agent 需要知道是否应该重试、重建 session、还是直接报错给用户。

## Provider Success But Final CAS Failure

这是 Day25 发现的最高风险。

### 问题本质

WorkloadManager 的 pause/resume 有两个阶段：

```text
1. Store 状态 CAS 到 transition 状态
2. runtime provider 执行外部动作
3. Store 状态 CAS 到 final 状态
```

第 2 步是外部副作用，不能简单回滚。

如果第 3 步失败：

- Store 仍可能是 `pausing` / `resuming`。
- runtime 可能已经暂停或恢复。
- Router / GC 看到 Store 状态时无法知道 runtime 真实状态。

### 可选处理策略

策略 A：retry final CAS。

适合：

- Store 临时错误。
- CAS expected status 仍然是 transition。

问题：

- 如果 CAS conflict 是因为别的 actor 修改了状态，retry 可能不正确。

策略 B：记录 operation id。

适合：

- 长期演进。
- 可以区分本次 pause/resume 操作。

问题：

- 需要 Store schema 新字段。
- 实现复杂度增加。

策略 C：reconciler 修复。

适合：

- Kubernetes controller 风格。
- 可以通过 runtime provider 查询真实状态。

问题：

- 当前 WorkloadManager 未必有持续 reconciler。
- 查询 runtime 状态需要 provider 增加 `GetStatus` 或类似接口。

策略 D：best-effort mark failed。

适合：

- MVP。
- 让 session 不继续被当成 ready。

问题：

- runtime 可能实际已经 ready，但 Store 是 failed。
- 用户可能需要重建 session。

### 当前建议

第三阶段前先补一个 fake store 测试，用来暴露这个问题，而不是马上设计复杂 reconciler。

测试名可以是：

```text
TestSessionLifecycleServicePauseProviderSuccessFinalCASConflict
TestSessionLifecycleServiceResumeProviderSuccessFinalCASConflict
```

测试目的：

- 明确当前行为。
- 让 reviewer 看到我们知道这个风险。
- 后续接真实 provider 前再决定是 retry、failed、还是 reconciler。

## Failure State 语义拆分

当前实现里 pause failure 和 resume failure 都进入 `failed`。这能让测试收敛，但产品语义可能不够细。

### pause failure

场景：

```text
ready -> pausing CAS 成功
provider.Pause 失败
mark failed
```

可能策略：

| 策略 | 优点 | 缺点 |
| --- | --- | --- |
| 回滚到 `ready` | 用户 session 还能继续用 | 如果 provider 部分暂停成功，ready 可能是假的 |
| 标记 `failed` | 不会误 proxy 到不确定状态 | 可能让可用 session 变不可用 |
| 保持 `pausing` 并 retry | 可能自动恢复 | 可能永久卡住 |

当前第二阶段选 `failed` 是保守策略。

### resume failure

场景：

```text
paused -> resuming CAS 成功
provider.Resume 失败
mark failed
```

可能策略：

| 策略 | 优点 | 缺点 |
| --- | --- | --- |
| 回滚到 `paused` | 用户稍后可重试 | 如果 provider 部分恢复，paused 可能是假的 |
| 标记 `failed` | 状态明确，不继续误用 | 用户不能自动 retry |
| 保持 `resuming` 并 retry | 自动恢复机会大 | 需要 transition timeout 和重试上限 |

对用户体验来说，resume failure 可能更适合回滚到 `paused` 或保持 retryable 状态。但这要求 provider 操作具备可查询性或幂等性。

### reviewer 结论

第二阶段可以先用 `failed`，但 PR 说明必须写清楚：

```text
This phase uses Failed as a conservative terminal state for provider errors.
The retry/rollback policy is intentionally left for the Router/GC/provider integration phase.
```

## RuntimeProvider Capability Gate 设计草案

当前 `RuntimeCapabilities` 只是结构体，还没有影响逻辑。下一阶段不能让这个接口长期闲置。

### 建议 capability 字段解释

| 字段 | 含义 | 后续用途 |
| --- | --- | --- |
| `HardPause` | 支持释放 Pod/runtime 资源但不保留进程内存 | Sleep/Resume MVP |
| `SoftPause` | 支持降低资源但保留 running runtime | 后续优化 |
| `SnapshotPause` | 支持 checkpoint/snapshot restore | SnapStart 方向 |
| `WarmPool` | 支持 warm-pool-backed session | 判断 CodeInterpreter warm pool 是否可 pause |
| `AdoptedSandbox` | 支持 claim -> adopted Sandbox 语义 | agent-sandbox v0.3+ / v0.4+ |
| `ManagedNetwork` | runtime 管理 NetworkPolicy | 决定是否需要 allow policy |

### pause 前的 gate

伪代码：

```go
cap := provider.Capabilities(ctx)
if mode == PauseModeHard && !cap.HardPause {
    return unsupported
}
```

但要注意：

- 如果不支持 hard pause，是 fallback delete 还是直接 unsupported？
- fallback delete 会改变用户语义，不能悄悄发生。
- Router / SDK 需要知道 session 是 paused 失败还是 deleted。

当前建议：

```text
MVP 不做 silent fallback delete。
provider 不支持 pause 时返回 explicit unsupported。
```

## Store Schema Review

### 当前新增字段分组

可以把 `SandboxInfo` 新字段分成四类：

| 分类 | 字段 | 当前阶段是否必需 |
| --- | --- | --- |
| lifecycle status | `Status` constants | 必需 |
| pause metadata | `PauseMode`, `PausedAt`, `PauseExpiresAt`, `ResumedAt`, `FailureReason` | 必需 |
| runtime identity | `RuntimeProvider`, `SandboxName`, `SandboxClaimName`, `PodName` | 部分预留 |
| endpoint consistency | `EndpointRevision` | 预留给 Router，但第二阶段已递增 |

### review 建议

如果正式拆 PR，可以考虑：

1. Store/CAS PR 只加 lifecycle status、pause metadata、EndpointRevision。
2. RuntimeProvider PR 再加 runtime identity 字段。
3. Router PR 再正式消费 EndpointRevision。

这样 review 会更容易。

### JSON 兼容性

由于新增字段都是 `omitempty` 或可空字段，旧 JSON session 理论上可以反序列化。

但需要注意：

- 旧 session 的 `Status` 可能是旧字符串，比如 `"running"`。
- 新逻辑如果只接受 `ready`，旧数据可能无法 pause。
- 需要 migration 或兼容判断。

review 问题：

```text
Existing sessions created before this change use what status value?
Will they be treated as Ready, NotReady, or unknown?
```

这点需要在正式 PR 前核对当前 main 创建 sandbox 时写入的 status。

## Test Case Design: GC Split

第三阶段 GC 单测应该先设计，不要边写边补。

### 测试 1：ready idle -> pause

输入：

- status: `ready`
- `LastActivityAt` 早于 idle threshold
- `ExpiresAt` 未过期

期望：

- GC 调用 lifecycle pause。
- Store 最终状态进入 `paused`。
- 不调用 delete。

### 测试 2：ready max TTL expired -> delete

输入：

- status: `ready`
- `ExpiresAt` 已过期
- idle 也可能过期

期望：

- delete 优先。
- 不调用 pause。

### 测试 3：paused pause timeout expired -> delete

输入：

- status: `paused`
- `PauseExpiresAt` 已过期
- `ExpiresAt` 未过期

期望：

- delete。
- 清理 pause index。

### 测试 4：paused max TTL expired -> delete

输入：

- status: `paused`
- `ExpiresAt` 已过期
- `PauseExpiresAt` 未过期

期望：

- delete。
- 证明 max TTL 优先于 pause timeout。

### 测试 5：paused not expired -> keep

输入：

- status: `paused`
- `PauseExpiresAt` 未来时间

期望：

- 不 pause。
- 不 delete。

### 测试 6：pausing stuck -> failed or retry

输入：

- status: `pausing`
- transition timestamp 超时

期望：

- 取决于设计：mark failed 或 retry。
- 当前还没有 transition timestamp 字段，需要先设计。

### 测试 7：unknown status -> no destructive action

输入：

- status: unknown

期望：

- log。
- 不 delete，除非 max TTL expired。

## Test Case Design: Router Resume

### 测试 1：ready session 直接 proxy

目标：

- 确认未破坏现有 ready path。

期望：

- 不调用 WorkloadManager resume。
- 正常 proxy。
- 更新 last activity。

### 测试 2：paused session owner mismatch

目标：

- 确认未授权请求不会触发 resume。

期望：

- 返回 forbidden。
- 不调用 resume。
- Store 状态仍为 paused。

### 测试 3：paused session resume success

目标：

- 验证 resume-before-proxy。

期望：

- 调 WorkloadManager resume。
- resume 后重新读取 Store。
- 使用新 entrypoint proxy。
- 更新 last activity。

### 测试 4：paused session resume returns conflict

目标：

- 并发 resume 场景。

期望：

- Router 返回 retryable response。
- 不 proxy 到旧 endpoint。

### 测试 5：resuming session

目标：

- 状态已经在恢复中。

期望：

- MVP 可以返回 `409` + `Retry-After`。
- 不启动第二次 resume。

### 测试 6：resume success but no entrypoint

目标：

- provider 返回 ready 但 entrypoint 为空。

期望：

- 不 proxy。
- 返回 clear error。
- 记录日志。

## Test Case Design: RuntimeProvider

### Direct Sandbox hard pause

验证点：

- pause 前 Sandbox ready。
- provider 将 Sandbox scale 到 0 或 operatingMode suspended。
- Pod 被删除或不再 running。
- Store entrypoints 被清空。

### Direct Sandbox resume

验证点：

- provider 将 Sandbox scale 到 1 或 operatingMode running。
- 等待 Ready condition。
- 读取新 Pod / endpoint。
- Store entrypoints 更新。

### Warm-pool-backed session

必须先明确策略。

可能策略：

1. 不支持 warm-pool pause，返回 unsupported。
2. pause adopted Sandbox，保留 SandboxClaim。
3. delete SandboxClaim，让 warm pool refill。

review 观点：

```text
MVP 可以先只支持 direct Sandbox，但必须显式说明 warm-pool sessions are unsupported for pause/resume MVP。
```

不能 silently 退化成 delete。

## PR 拆分建议

如果未来要把这组实验变成 upstream PR，不建议一次性提交 13 个文件。

更适合拆成：

### PR 1: Store lifecycle state and CAS

包含：

- `pkg/common/types/sandbox.go`
- `pkg/store/interface.go`
- `pkg/store/error.go`
- Redis/Valkey CAS 和 pause index。
- Store tests。
- fake store 编译适配。

不包含：

- WorkloadManager lifecycle service。
- Router。
- GC。
- real provider。

PR 目标：

```text
Introduce the Store primitives required by session sleep/resume.
```

### PR 2: WorkloadManager lifecycle service

包含：

- `pkg/workloadmanager/session_lifecycle.go`
- `pkg/workloadmanager/session_lifecycle_test.go`

依赖：

- PR 1 的 Store CAS。

PR 目标：

```text
Add an internal lifecycle service that coordinates pause/resume through Store CAS and RuntimeProvider.
```

### PR 3: GC split

包含：

- `garbage_collection.go`
- GC tests。
- pause timeout config 初步来源。

依赖：

- PR 2。

PR 目标：

```text
Change idle Ready sessions from delete to pause, and delete Paused sessions after pause timeout.
```

### PR 4: Router resume-before-proxy

包含：

- Router session handling。
- owner/auth before resume。
- Router tests。

依赖：

- PR 2 或 PR 3。

### PR 5: agent-sandbox hard pause provider

包含：

- real provider for direct Sandbox。
- e2e。
- cleanup checks。

依赖：

- #387 / agent-sandbox compatibility。

## PR Body 需要提前准备的解释

如果提 PR，body 不能只写 “add sleep/resume”。应该解释：

```text
This PR is one layer of the Sleep/Resume implementation.
It does not expose the feature to users yet.
```

必须列 Scope：

- Added Store CAS.
- Added pause expiry index.
- Added WorkloadManager internal lifecycle service.
- Added fake provider tests.

必须列 Non-goals：

- No Router resume-before-proxy.
- No GC behavior change.
- No real agent-sandbox pause provider.
- No API/CRD pauseTimeout yet.
- No user-facing release note.

必须列 Tests：

- Store unit tests。
- WorkloadManager lifecycle tests。
- race tests。
- lint。
- non-e2e Go tests。
- build-all。

必须列 AI assistance：

```text
AI assistance was used to inspect code, draft tests, and prepare review notes.
The changes and test results were reviewed before submission.
```

## 对 mentor 的汇报口径

这部分可以用于周会，不发 upstream。

简短版：

```text
我没有继续直接堆第三阶段代码，而是把已经实现的 Store/CAS 和 WorkloadManager lifecycle service 当成 PR 来审了一遍。
结论是拆分方向是对的：Store 只做状态和原子性，WorkloadManager 做生命周期编排，RuntimeProvider 屏蔽底层 agent-sandbox 差异，Router 后续只做 auth/resume/proxy。
当前最大风险是 provider 成功后 final CAS 失败，可能导致 runtime 和 Store 状态不一致；这需要第三阶段前明确 retry/reconcile/failed 策略。
我已经把 GC decision table、Router status handling、测试矩阵和 PR 拆分建议继续写在 Day25 里。
```

详细版：

- 第一阶段是 Store primitive，不是用户功能。
- 第二阶段是 WorkloadManager execution layer，不是用户功能。
- 当前实现价值是验证架构假设，不是抢完整 feature。
- 后续任何代码前都要先过 Day25 的 gate。
- 如果 FAUST-BENCHOU 或维护者推进实现，我们可以用 Day25 做 design review / test plan 反馈。

## 审代码训练总结

这次最大的训练点是：review 不等于挑语法问题。

更有价值的 review 是：

- 看 PR 是否拆对层次。
- 看核心状态机是否有并发保护。
- 看外部副作用失败后是否有恢复策略。
- 看抽象是否隔离了 runtime 细节。
- 看测试是否映射真实风险。
- 看 PR body 是否诚实说明 scope 和 non-goals。

对 Sleep/Resume 这种生命周期特性，reviewer 的重点应该是状态一致性，而不是某个函数写法是否漂亮。

## Day25 后续仍可继续补充的内容

在达到 600 行之后，如果还继续同一主题，可以继续补：

- 真实 `garbage_collection.go` 当前代码逐行审查。
- Router `session_manager.go` / `handlers.go` 当前代码逐行审查。
- agent-sandbox provider 可能目录设计。
- Store schema 字段是否要拆 PR 的最终建议。
- 英文 design review comment 草稿。
- PR 模板草稿。
- 维护者可能提出的反对意见和回应。
