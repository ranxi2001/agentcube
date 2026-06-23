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

不建议马上写大量第三阶段代码。更稳的下一步是先写一个短设计补充：

```text
Day26: GC split and Router resume-before-proxy behavior table
```

内容只需要确定：

- GC decision table。
- Router status handling table。
- 错误码 / retry 语义。
- owner/auth 前置规则。
- provider failure 后的 rollback / failed / retry 策略。
- 哪些行为第一版不支持。

等这些表格清楚后，再继续写第三阶段代码，review 成本会低很多。
