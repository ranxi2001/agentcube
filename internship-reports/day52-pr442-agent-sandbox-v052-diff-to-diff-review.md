# Day 52：PR #442 agent-sandbox v0.5.2 Diff-to-Diff Review

日期：2026-07-20

## 1. 本轮目标

本轮对 AgentCube upstream [PR #442](https://github.com/volcano-sh/agentcube/pull/442) 做只读 review，并与 Day50 在未读取作者实现前完成的 blind adapter `compat/agent-sandbox-v052-independent@2d90b07` 对照。

比较不只回答“代码是否能编译”，而是分别检查：

1. v1alpha1 到 v1beta1 API 映射；
2. direct Sandbox 与 SandboxClaim / WarmPool 身份链；
3. v0.4.6 存量对象的原地 migration；
4. generated client、CRD 与 Kubernetes toolchain 对齐；
5. unit、codegen、clean-install E2E 与 upgrade E2E 的证据边界；
6. PR body 是否把 scope、风险和验证写清楚。

> 注释：blind adapter 的价值不是证明“我们的代码一定更好”，而是提供一个在不知道作者答案时形成的独立解法。对照时既要找 #442 的缺口，也要承认它补上了我们遗漏的 toolchain 工作。

## 2. Review 快照

只读 freshness scan 冻结于 `2026-07-20 10:14 CST`。

| 项目 | 当前事实 |
| --- | --- |
| PR | `volcano-sh/agentcube#442` |
| 作者 / issue owner | `@safiya2610`，Issue #438 已正式 assign |
| Base | `upstream/main@146b75f` |
| Head | `a53441f23b0df0fdd01bccfc0a1c5d43cd921ed1` |
| Patch | 1 个 DCO commit，27 files，`+641/-460` |
| Merge | base 是 ancestor，`mergeable=true` |
| Checks | 12/12 success，含 DCO、Codegen、lint、coverage、两组 E2E |
| Review | 没有真人技术 review；69 个 root threads 均来自 AI reviewer |
| Thread 状态 | 17 resolved/current、49 resolved/outdated、3 unresolved/outdated；另有 2 条作者 reply |

PR 最初经历多次 force-push，旧记录中的 `396e0e9` 已被 `a53441f` 取代。不能把旧 commit 上的 compile error 当作 current finding。

> 分析：GitHub thread 被 resolved 或 outdated 只是 workflow 元数据，不证明代码已修。当前 head 仍保留错误 informer group，是本轮重新读源码后确认的反例。

## 3. 变更模型

### 3.1 要保护的合同

Issue #438 明确要求：

- 从 agent-sandbox `v0.4.6` 升到 `v0.5.2+`；
- AgentCube 改用 agent-sandbox v1beta1 API；
- direct Sandbox 行为保持；
- WarmPool Claim adoption、session deletion、GC 和 pool refill 保持；
- v0.4.6 存量安装与 active SandboxClaims 有“documented and tested upgrade path”。

最后一条不是附加文档任务，而是本 PR 的核心兼容合同。

### 3.2 权威状态与 writer

| 状态 | Writer / authority | #442 的使用 |
| --- | --- | --- |
| AgentCube desired state | `AgentRuntime` / `CodeInterpreter` spec | 继续保持 `runtime.agentcube.volcano.sh/v1alpha1` |
| agent-sandbox desired state | `Sandbox` / `SandboxClaim` / Template / WarmPool spec | 切换到 v1beta1 |
| Claim adopted identity | `SandboxClaim.status.sandbox.name` | WorkloadManager live GET 后存入 Store |
| runtime readiness | agent-sandbox controller status | WorkloadManager polling / watcher 观察 |
| Pod identity | adopted Sandbox annotation、Pod UID | E2E 检查 adoption、delete、refill |
| stored API version | CRD storage version + conversion webhook | clean install 为 v1beta1；存量迁移需要官方 two-phase procedure |

### 3.3 成功与失败路径

```text
fresh install:
v0.5.2 CRDs/controller -> AgentCube beta objects -> ready -> Store -> invoke/delete

in-place upgrade:
backup -> pre-upgrade bootstrap when cold-start claims exist
       -> install v0.5.2 CRDs/controller/webhook -> wait ready
       -> optional migrate rewrite -> verify storage
```

PR 当前 clean-install path 有证据，in-place path 没有完整实现或测试证据。

## 4. Findings

### 4.1 [P1] Upgrade 文档跳过 cold-start Claim 的强制 bootstrap

位置：`docs/getting-started.md:243`

#442 要求用户直接执行：

```bash
kubectl apply --server-side -f .../v0.5.2/sandbox-with-extensions.yaml
helm upgrade agentcube ...
```

随后在第 257 行承诺 active `CodeInterpreter` 和 `SandboxClaim` 会平滑转到 v1beta1，且不会 cold-start。

agent-sandbox v0.5.2 的官方 `docs/api-migration-guide.md` 给出的合同不同：

- v1alpha1 `SandboxClaim` 与 v1beta1 不同构；
- cold-start claim 会转换为 `warmPoolRef.name=shadow-pool-<template>`；
- 若存量 cold-start claim 存在，必须在 v0.4.x 仍运行时执行 `migrate.sh --phase=bootstrap`；
- 跳过 bootstrap 后，转换出的 claim 会指向不存在的 pool，并持续处于 `WarmPoolNotFound`；
- 升级后还要等待 controller 与 conversion webhook ready，再按需要执行 `--phase=migrate`。

具体可达反例：CodeInterpreter 配置了 warm pool，但并发或 pool refill 窗口中没有可采用的 warm Sandbox，v0.4.6 Claim 走 cold-start，绑定 Sandbox 名与 Claim 名相同。此状态是 agent-sandbox 官方 migration guide 明确定义并支持的生产状态，不是 mock-only 假设。

后果：操作者照 #442 文档升级时，existing claim 可以被转换到不存在的 shadow pool，破坏 Issue #438 要求的 active Claim upgrade path。

证据分类：source-proven reachable latent defect；没有在本轮环境观察一次真实损坏，但 upstream migration contract 已闭合 producer、前置状态与坏结果。

最小修正方向：

1. 不要在 AgentCube 文档中自创两步升级流程；链接并摘要 v0.5.2 官方 two-phase guide；
2. 写出 backup、conditional pre-upgrade bootstrap、controller/webhook readiness 与 post-upgrade migrate；
3. 增加 v0.4.6 -> v0.5.2 原地升级测试，至少覆盖一个 warm-adopted Claim 和一个 cold-start Claim；
4. 先证明 exact Sandbox/Pod UID 或允许的重建合同，再宣称 session 平滑迁移。

### 4.2 [P2] 新生成的 informer identity 使用了错误 API group

位置：

- `client-go/informers/externalversions/runtime/v1alpha1/agentruntime.go:67`
- `client-go/informers/externalversions/runtime/v1alpha1/codeinterpreter.go:67`

当前代码生成：

```go
schema.GroupVersionResource{Group: "runtime", Version: "v1alpha1", ...}
```

真实 API group 是：

```text
runtime.agentcube.volcano.sh
```

List/Watch 仍通过 typed client 访问真实 API，所以这不是当前 routing 失败；错误值进入 `SharedIndexInformerOptions.Identifier`，在调用方启用 `WithInformerName` 时用于 informer metrics identity 与 uniqueness。

后果是 metrics 被错误标记，且相同短 group 的 informer 可能产生 identity collision。仓库当前没有 in-tree `WithInformerName` caller，因此不把它夸大成当前 observed outage。

证据分类：公开 generated API 可达的 latent defect；当前 AgentCube production path 未启用该 option。

这个问题曾被 Copilot 指出，相关 thread 已被 resolve/outdate，但 `a53441f` 的代码仍未修。最小修正应落在 generator input / generation workflow，再重新生成；不要只手改 `client-go` 输出。

### 4.3 Test gap：绿色 E2E 只证明 clean install，不证明 upgrade

exact head 的 `codeinterpreter-e2e-test` 使用：

```text
MTLS_ENABLED=false
E2E_REQUIRE_CODEINTERPRETER=true
```

因此它确实执行 CodeInterpreter target path，不是默认 mTLS skip。现有 E2E 已覆盖：

- WarmPool ready；
- Claim adoption；
- adopted Pod UID；
- session delete；
- adopted resources delete；
- pool refill；
- load path。

但 `test/e2e/run_e2e.sh` 每次在 fresh kind 中直接安装 v0.5.2。没有步骤先装 v0.4.6、创建 active objects、执行 bootstrap、升级 controller/CRD、等待 webhook，再验证对象与 session identity。

所以 12/12 checks 不能支持 PR body 和 docs 的“upgrade smoothly”结论。Issue #438 明确写了 “documented and tested upgrade path”，这是 scope gap，不是可选增强。

## 5. #442 做得比 blind adapter 更好的地方

### 5.1 对齐了 code-generator toolchain

#442 把：

```text
k8s.io/api/apimachinery/client-go: v0.35.4 -> v0.36.2
code-generator:                 v0.35.4 -> v0.36.2
```

一起更新，并提交了生成 client / informer / CRD 结果。Day50 blind adapter 升级了 runtime modules，却保留旧 `code-generator v0.35.4`；虽然 `make gen-check` 通过，但版本不同步是我们的遗漏。

> 分析：生成结果有 bug，不等于“生成器不该升级”。正确学习是保留 #442 的 toolchain alignment，再修 generator source 和 focused test；不能为了缩 diff 回退到隐藏的 generator/runtime skew。

### 5.2 API 机械适配完整

#442 当前 head 正确覆盖了：

- `SandboxBlueprint.PodTemplate`；
- `SandboxOperatingModeRunning`；
- Claim `WarmPoolRef`；
- pointer `Replicas` 的 nil guard；
- beta GVR；
- controller scheme registration；
- dynamic client typed conversion；
- fresh-install release asset。

targeted unit test 和 exact-SHA CI 均通过，没有发现 current compile failure。

### 5.3 PR history 已压成一个 DCO commit

作者早期多次 force-push 处理 AI review，current head 最终只有一个签名 commit，base ancestry 和 structural merge 都干净。相比保留 10 个修补 commit，这个最终 patch 更容易做一次整体 review。

## 6. Blind adapter 做得更好的地方

### 6.1 将独立 Go 兼容前置与业务适配分开

我们的两层提交是：

```text
d70ab94  Go 1.26 Scheme / HTTP2 compatibility prerequisite
2d90b07  agent-sandbox v0.5.2 beta adapter
```

#442 在一个 commit 中同时迁移 agent-sandbox、升级生成器、加 h2c lint suppression、加 SchemeBuilder suppression 和改文档。概念仍相关，但 reviewer 很难区分“依赖强制变化”和“为了让 lint 绿的局部选择”。

### 6.2 替换 deprecated API，而不是用错误理由压 lint

#442 在 Router / WorkloadManager 中保留 `golang.org/x/net/http2/h2c`，并写：

```text
no stdlib alternative exists in current architecture
```

Go 1.26 的 `http.Server.Protocols` 已可启用 unencrypted HTTP/2。我们的 prerequisite 使用标准库实现并增加 server tests；SchemeBuilder 也改为 `runtime.NewSchemeBuilder`，并增加 runtime type registration test。

这不是当前行为 bug，但 #442 的 suppression comment 会把一个已经存在的迁移路径写成“不可能”，降低后续维护质量。

### 6.3 Migration 文档更接近 authoritative contract

blind adapter 文档没有宣称 clean install 等于完整 upgrade，而是直接链接固定版本的 v0.5.2 migration guide，并摘要：

- backup；
- conditional bootstrap；
- controller/webhook readiness；
- migrate rewrite。

同时报告明确记录“v0.4.6 原地 migration 未验证”。这比 #442 的过度承诺更可信。

### 6.4 增加了更直接的合同断言

blind adapter 额外包含：

- `AddToScheme` runtime type registration test；
- Router / WorkloadManager standard HTTP2 tests；
- WarmPool pointer replicas create/update test；
- E2E `claim.Spec.WarmPoolRef.Name == CodeInterpreter name`；
- fresh install 后四个 agent-sandbox CRD storage version 必须为 v1beta1。

这些测试让失败更接近具体合同，而不只依赖整体 E2E 最终成功。

## 7. 我们自己的不足

对照不能得出“blind adapter 已完成 Issue #438”。它仍有两个明确缺口：

1. 没有把 `code-generator` 从 v0.35.4 对齐到 v0.36.2；
2. 没有运行 v0.4.6 -> v0.5.2 原地 migration E2E。

因此我们的 adapter 可以作为 clean-install、API、identity 和 lifecycle 参考实现，不能直接替代 #442 合入。真正可合并版本应取两者交集：

```text
#442 toolchain alignment
+ blind adapter focused compatibility tests
+ authoritative migration procedure
+ real in-place migration E2E
- wrong informer GVR
- unsupported deprecation suppressions
```

## 8. PR body 写作对照

#442 body 为 105 visible words、8 nonblank lines。它的优点是短、先说升级结论、正确写了 `Fixes #438`。

但它不是完整 AgentCube 官方模板：

- 缺 `/kind enhancement`；
- 缺 `Special notes for your reviewer`；
- 缺 release note；
- 测试只写“unit and E2E”，没有命令、exact-SHA 或 clean-install 限定；
- 没有披露 migration test 缺口；
- 没有 AI assistance disclosure；
- “sanitized a very large annotation locally” 没解释这是否进入可重复 CI 证据。

兼容 / API / CRD PR 的 reviewer-attention 软目标是 200-450 words。这里的问题不是“105 words 太少”本身，而是省掉的内容会改变 merge 判断。

建议的 body shape：

1. old behavior：AgentCube pinned v0.4.6/v1alpha1；
2. new behavior：v0.5.2/v1beta1 direct 与 WarmPool path；
3. scope：Kubernetes v0.36.2 + generated artifacts；
4. validation：focused unit、gen-check、clean-install CodeInterpreter E2E；
5. material limit：in-place migration 尚未验证，不能写 `Fixes #438`，或补齐后再保留 `Fixes`；
6. release note：用户升级前必须执行官方 migration procedure。

## 9. 本地验证

在 detached worktree `/tmp/agentcube-pr442-review@a53441f` 运行：

```bash
go test ./pkg/workloadmanager ./pkg/apis/runtime/v1alpha1 ./pkg/router ./client-go/informers/... -count=1
make gen-check
git status --short
git diff --check
```

结果全部通过，worktree 最终 clean。

GitHub exact head `a53441f` 的 12 个 checks 也全部 success，包括：

- build x2；
- lint；
- coverage；
- codegen；
- DCO；
- Python lint / SDK；
- normal mTLS E2E；
- non-mTLS CodeInterpreter-required E2E。

未运行 live in-place migration；这正是本轮 P1 finding 的验证缺口，而不是被绿色 clean-install E2E 覆盖的路径。

## 10. Merge 判断

当前结论：`REQUEST CHANGES`，不建议在 `a53441f` 直接合并。

阻塞条件：

1. 按官方 v0.5.2 migration guide 修正文档；
2. 为 Issue #438 要求的存量升级路径补真实或生产等价测试；
3. 修复 generated informer identity 的完整 API group，并从 generator source 重生。

非阻塞改进：

- 删除错误的 “no stdlib alternative” suppression 理由，优先采用标准 HTTP2 / runtime Scheme APIs；
- 用官方 PR template 重写 body，明确 clean-install 与 upgrade evidence boundary。

本轮没有发布任何 upstream review、comment、request changes、mention 或 reviewer request。若要向社区提交，应先把 exact English text 与 target 给用户确认。

## 11. 可复用 review 经验

1. 依赖升级 PR 要同时审 runtime modules、generator version、generated output 和 live installed controller；只看 `go.mod` 不够。
2. 绿色 E2E 必须先分类为 fresh install、in-place upgrade、version-skew 或 migration；名字都叫 E2E，不代表合同相同。
3. `resolved` thread 不是修复证据；必须重新读 current head。
4. 官方 migration guide 是 upgrade contract 的权威来源，项目文档只能摘要，不能删掉有顺序依赖的 phase。
5. 独立实现对照的目标不是胜负，而是发现双方的非重叠优点：本例中 #442 更重视 toolchain alignment，我们更重视 scope 分层、focused contract tests 和 evidence boundary。

## 12. Inline review 准备与独立反证

2026-07-20 在用户要求开始准备 inline review 后，先重新冻结 current head：`a53441f23b0df0fdd01bccfc0a1c5d43cd921ed1` 未变化，12/12 checks 仍为 success，账号 `ranxi2001` 对 upstream repository 的 `viewerPermission` 为 `READ`。因此建议提交一个 `COMMENT` review，而不是把外部 contributor 的意见包装成有效 merge gate。

### 12.1 migration finding 的收窄

独立反证发现，原先“cold-start Claim 升级后都会卡在 `WarmPoolNotFound`”的表达过宽：

- v0.5.2 controller 会先按 Claim status、legacy assigned name 和 Claim 同名 Sandbox 查找已有对象；
- 已经存在且仍由 Claim 控制的同名 cold-start Sandbox 可以绕过缺失 WarmPool 的创建路径；
- AgentCube 当前 Claim 没有 additional pod metadata 时，fast path 上模板查找失败还是 non-fatal。
- 名为 `shadow-pool-<template>` 的 pool 也可能被用户预先创建，所以只能说本 PR 流程不会创建它，不能断言每个集群里都不存在。

真正可证明且可达的失败窗口是：

1. AgentCube v0.4.6 创建 `spec.warmpool` 为空的 v1alpha1 SandboxClaim；
2. v0.4.6 在 warm pool 耗尽时允许 fall back to cold start；
3. 在 Claim 尚未绑定 Sandbox 的 create/reconcile 窗口执行升级；
4. v0.5.2 conversion 把该 Claim 映射到 `shadow-pool-<template>`；
5. 如果升级前没执行 bootstrap，shadow pool 不存在；
6. v0.5.2 controller 的 cold path 返回 `ErrWarmPoolNotFound` 并按一分钟 requeue；
7. AgentCube 等待 Claim status 的 create 请求可以超时，随后 rollback Claim。

> 分析：这是 source-proven reachable latent path，不是已观测事故，也不是“每个 cold-start Claim 都会失败”。inline comment 必须保留这个限定，否则会把官方 migration guide 的保守要求错误放大成无条件 runtime 结论。

官方 guide 使用的 `dev/tools/migrate.sh` 是 agent-sandbox v0.5.2 source checkout 中的 wrapper；AgentCube repo 与 release manifest 都不携带可直接执行的 helper。面向 AgentCube operator 的升级文档必须说明如何获得 pinned helper，不能只贴一个在当前工作目录必然找不到的命令。

### 12.2 GVR finding 的生成根因

current head 的 AgentRuntime / CodeInterpreter informer 都生成了 `Group: "runtime"`。实际 group 是 `runtime.agentcube.volcano.sh`。仓库内目前没有调用 `WithInformerName`，所以默认 AgentCube binary 的 List/Watch 路由不受影响；但 PR 新增了 public `WithInformerName`，外部 client-go caller 可以真实进入错误 identity / metrics registration 路径。

根因不在 generated Go file 本身：

- informer-gen 从 package `Comments` 读取 `+groupName`；
- gengo 只把 `doc.go` 的 comments 放进这个字段；
- 本包没有 `doc.go`，marker 位于 `groupversion_info.go`；
- 所以 `make gen-check` 会稳定重生 `runtime/v1alpha1`，不能靠手改 generated file 修复。

已有 6 条 Copilot GVR root threads 都是 `resolved=true`、`outdated=true`，作者曾回复 `already solved`，但 current head 仍保留错误。新 human inline 应锚到 `hack/update-codegen.sh` 的 compatibility block，说明 generator source、公开 API reachability 和修复位置，避免在两个 generated file 上再复制 bot 文案。

### 12.3 Exact upstream draft

建议一次性创建 `COMMENT` review，summary 为：

> The upgrade documentation omits the pre-upgrade bootstrap needed for reachable existing-Claim states, the E2E covers only a clean install, and the regenerated client has an informer identity issue; details are inline.

Inline 1 target：`docs/getting-started.md:247`，`RIGHT`：

> Applying v0.5.2 cannot be the first upgrade step for every existing v0.4.6 installation. For CodeInterpreters with `warmPoolSize > 0`, AgentCube v0.4.6 creates SandboxClaims with the upstream default warm-pool policy. If the pool is empty, v0.4.6 falls back to cold start; during the window before it has created or adopted a Sandbox, conversion maps the claim to `warmPoolRef.name=shadow-pool-<template>`. This procedure does not create that pool. When it is absent, v0.5.2 reports `WarmPoolNotFound` and requeues, so AgentCube's two-minute create wait can expire and enter the rollback path. This is source-proven reachability, not an observed outage or a failure of every cold-start claim.
>
> Could this section document the [official v0.5.2 flow](https://github.com/kubernetes-sigs/agent-sandbox/blob/v0.5.2/docs/api-migration-guide.md#phase-1---phasebootstrap-conditionally-mandatory-pre-upgrade), including the backup, how an AgentCube operator obtains the pinned migration helper, and `--phase=bootstrap` before this apply? It should then wait for controller/webhook readiness and describe the optional post-upgrade `--phase=migrate`.

Inline 2 target：`test/e2e/run_e2e.sh:336`，`RIGHT`：

> This setup installs only v0.5.2, so the green CodeInterpreter E2E does not exercise stored v1alpha1 objects or Issue #438's upgrade contract. Could we add a dedicated migration scenario using the v0.4.6 resource shape produced by AgentCube: install v0.4.6, create one default-policy claim and wait for warm adoption, capture its Sandbox/Pod UIDs, stop the old controller and create a second default-policy claim so it remains unbound, then run the pinned v0.5.2 helper through `bootstrap -> install -> webhook readiness -> migrate`? The test should verify that the UIDs are preserved, the unbound claim becomes Ready through the shadow pool, deleting the migrated warm claim garbage-collects its Sandbox/Pod, and the pool returns to its configured size after adoption. This fixture proves CRD/controller migration; retaining the stronger active-CodeInterpreter-session claim also requires old AgentCube plus persisted Redis and invoking/deleting the same session after upgrade, otherwise that claim should be narrowed.

Inline 3 target：`hack/update-codegen.sh:80`，`RIGHT`：

> The regenerated informers still identify both resources under `runtime/v1alpha1`, although their API group is `runtime.agentcube.volcano.sh`. No in-tree caller currently enables informer naming, but the newly exported `WithInformerName` makes this a reachable client-go contract: client-go passes the GVR to metrics providers and uses it for in-process informer identity registration. Regeneration preserves the error because gengo reads package-level `+groupName` metadata from `doc.go`, while this package keeps it in `groupversion_info.go`. Could we move the marker to `pkg/apis/runtime/v1alpha1/doc.go` and regenerate instead of patching generated files?

`draft_metrics.py` 结果：summary 31 words / 1 nonblank line；Inline 1 为 138 / 2；Inline 2 为 146 / 1；Inline 3 为 81 / 1。reviewer-visible 总计 396 words / 5 nonblank lines，落在 compatibility/API review 的 200-450 words 软目标内。

这三条都采用 observation -> concrete path -> impact -> requested action，并显式区分 observed 与 source-proven reachable。没有加入 Mermaid：每条只解释一个线性 prerequisite 或一个 metadata-to-generated-identity 因果链，短 prose 比 3-6 节点图更快理解。

发布门禁已执行：用户在看到通俗解释与上述全文后明确回复“确认发布”；发布前再次确认 PR 仍 open、head 仍为 `a53441f`、三个 target 仍是 current diff 的 `RIGHT` 行，并确认 2026-07-20 当天没有新增重复评论。

### 12.4 发布结果与回读验证

2026-07-20 10:59:40 CST，通过 GitHub review API 一次性提交 `COMMENT` review：

- review：[4731928343](https://github.com/volcano-sh/agentcube/pull/442#pullrequestreview-4731928343)，state `COMMENTED`；
- migration docs：[3611817313](https://github.com/volcano-sh/agentcube/pull/442#discussion_r3611817313)，`docs/getting-started.md:247`，`RIGHT`；
- upgrade E2E：[3611817315](https://github.com/volcano-sh/agentcube/pull/442#discussion_r3611817315)，`test/e2e/run_e2e.sh:336`，`RIGHT`；
- informer generator：[3611817317](https://github.com/volcano-sh/agentcube/pull/442#discussion_r3611817317)，`hack/update-codegen.sh:80`，`RIGHT`。

发布后重新读取 review 与 pull review comments，确认：

- summary 和三条 comment body 均完整，没有截断；
- 三条 comment 的 `commit_id` 都是 `a53441f23b0df0fdd01bccfc0a1c5d43cd921ed1`；
- path、line、side 与批准 payload 完全一致；
- PR review comment count 从 71 增至 74；
- PR head 仍未变化。

后续不自动催促、mention 或追加评论。等待作者回复或 push 新 head 后，优先复核 migration phase 顺序、真实 upgrade fixture、CodeInterpreter/Redis claim boundary，以及 `doc.go` marker 重生后的两个 informer GVR。
