# Day 58：AgentCube PR #450 CodeInterpreter 子资源 ownership Review

日期：2026-08-03

目标：只读审查 `volcano-sh/agentcube#450`，确认它是否完整满足 Issue #449 的安全边界；本轮不修改 PR 分支，不发布 upstream comment。

## 1. Review Surface

| 项目 | 结果 |
| --- | --- |
| PR | `volcano-sh/agentcube#450` `fix(workloadmanager): check CodeInterpreter child ownership` |
| Parent Issue | `volcano-sh/agentcube#449` |
| Base | `0704bb96502af32f2bd90d47f1e11b4c8099959e` |
| Head | `f722b51302e58c25036d46f5e2ad0169cd228023` |
| Merge base | `0704bb96502af32f2bd90d47f1e11b4c8099959e` |
| Changed files | 2 |
| Diff | `+165/-16` |
| Commits | 2，均有 DCO signoff |
| Human review | 0 条 |
| CI | executable checks 全部通过；Tide 只等待 `lgtm/approved` |

改动文件：

| 文件 | 变化目的 | Review 证据 |
| --- | --- | --- |
| `pkg/workloadmanager/codeinterpreter_controller.go` | 对已有 Template/WarmPool 做 controller UID ownership 检查；冲突时写 `Ready=False/OwnershipConflict`；create race 不再吞掉 `AlreadyExists` | Issue #449 contract、controller-runtime Delete 实现、Kubernetes delete preconditions |
| `pkg/workloadmanager/codeinterpreter_controller_test.go` | 增加未归属 Template/WarmPool 的 update/delete 拒绝测试和 status 断言 | exact-head coverage workflow 确实执行 `./pkg/...` |

> 注释：这里的 ownership 指 Kubernetes controller owner reference。`metav1.IsControlledBy(child, ci)` 会按 controller reference 的 UID 判断 child 是否由当前 `CodeInterpreter` 控制，而不是只比较同名对象。

## 2. Issue Contract

Issue #449 给出的可观察问题是：

1. 同 namespace/name 的 standalone `SandboxTemplate` 会被 CodeInterpreter controller 当作自己的 child。
2. `warmPoolSize > 0` 时，controller 可能覆盖未归属 Template/WarmPool 的 spec。
3. `warmPoolSize == 0` 或 nil 时，controller 可能删除未归属的同名资源。
4. 修复后只允许 update/delete 当前 CodeInterpreter 控制的 child；碰撞需要失败并报告 condition 或 event。

本轮采用的核心不变量：

```text
controller 对 child 做 update/delete 时，API Server 最终执行操作的对象
必须仍然是通过 ownership 检查的同一对象版本。
```

> 分析：只在 GET 返回后检查一次 owner reference，还不能自动把这个判断绑定到稍后的 DELETE。Review 必须继续检查 API Server 收到的写请求是否携带 UID/resourceVersion 等并发条件。

## 3. Change Model

### 3.1 Update path

```text
GET child -> IsControlledBy(child, ci) -> mutate fetched object -> Update(child)
```

`Update(child)` 携带 GET 得到的 `metadata.resourceVersion`。如果 child 在检查后被修改、删除或同名重建，API Server 会返回 Conflict；旧检查结果不会直接覆盖新对象。

结论：PR 对 steady-state update path 的 ownership 修复成立。

### 3.2 Create collision path

```text
GET NotFound -> Create owned child -> AlreadyExists -> return error -> controller retry -> GET + ownership check
```

PR 不再把 `AlreadyExists` 当成功，因此并发 name collision 会进入下一次 reconcile 并重新检查现存对象。

结论：create collision 的方向正确。

### 3.3 Delete path

```text
GET child A -> IsControlledBy(A, ci) -> Delete(child A)
```

PR 的两处 Delete 调用都没有传 `client.DeleteOption`：

- `deleteSandboxWarmPool`：`codeinterpreter_controller.go:295`
- `deleteSandboxTemplate`：`codeinterpreter_controller.go:318`

controller-runtime v0.23.3 的 typed client 只从对象提取 GVK、namespace 和 name；只有调用者显式传入 `client.Preconditions` 时，`metav1.DeleteOptions.preconditions` 才非空。

## 4. Finding

### [High] ownership 检查没有绑定到最终 DELETE 对象

触发顺序：

1. controller GET 到由 CodeInterpreter 控制的 child A，并通过 `IsControlledBy`。
2. 在 DELETE 到达 API Server 前，另一个有权限的 actor 修改 A 的 owner reference，或删除 A 并创建同名未归属 child B。
3. 当前 `r.Delete(ctx, child)` 发出的是 name-only DELETE；没有 UID/resourceVersion precondition。
4. API Server 可以删除当前同名对象 B，PR 宣称保护的未归属资源仍会被删除。

这是 `Reachable latent bug`：

- `CODE`：两处 Delete 调用没有 options。
- `CODE`：controller-runtime `typedClient.Delete` 默认构造空 `DeleteOptions`，按 name 发请求。
- `DOC/CODE`：`client.Preconditions` 支持 UID 和 ResourceVersion，不满足时返回 409 Conflict。
- 生产可达性：Issue 本身假设其他用户/controller 可以管理同类 standalone 资源；Kubernetes update/delete/create 是实际 producer。
- 未观察到真实运行时 occurrence，因此不能写成 observed incident。

最小修复方向：

1. 从已经验证的 child 保存 UID 和 ResourceVersion。
2. Delete 时传 `client.Preconditions{UID: ..., ResourceVersion: ...}`。
3. 将 409 Conflict 交给 reconcile retry；下一次 GET 对当前对象重新做 ownership 判断。
4. 对 Template 和 WarmPool 各补一个 race regression：在 GET/validation 后、Delete 前修改 owner reference 或替换同名对象，断言 replacement 保留且 delete 返回 Conflict。

> 注释：UID 防止“旧对象删除、同名新对象被误删”；ResourceVersion 还防止同一 UID 的对象在 ownership 检查后被修改。两者同时使用，才把最终 DELETE 绑定到已验证的对象版本。

## 5. Falsification Pass

为排除 false positive，额外检查了以下路径：

1. `Update` 是否也有同样问题：没有。它携带对象 ResourceVersion，变更后会 Conflict。
2. controller-runtime 是否会从传入对象自动填 Delete UID：不会。v0.23.3 `typed_client.go` 只使用 name，preconditions 仅来自显式 DeleteOption。
3. `IsControlledBy` 是否只比较 name：不会。它使用 controller owner reference UID。
4. create `AlreadyExists` 是否仍会被吞掉：不会。PR 已改为返回 error，让 controller retry 后检查 ownership。
5. 冲突状态能否恢复：ownership conflict 返回 error 会触发 rate-limited retry；冲突资源移除后可重新 reconcile 并把 Ready 设回 True。

因此本轮只保留一个 finding，不把永久 error retry、PR body 的 Markdown 星号或 patch coverage 76.67% 单独升级为 correctness finding。

## 6. Validation Evidence

### 6.1 Exact-head GitHub checks

`f722b51302e58c25036d46f5e2ad0169cd228023`：

- DCO：通过。
- build：通过。
- golangci-lint：通过。
- Codegen Check：通过。
- coverage：通过。
- e2e-test：通过。
- codeinterpreter-e2e-test：通过。
- Python lint / SDK tests / spelling：通过。
- Tide：pending，仅缺 `lgtm` 和 `approved`。

changed test package 的 CI discovery：

```bash
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
```

该命令来自 `.github/workflows/test-coverage.yml`，会执行 `pkg/workloadmanager`，因此新测试不是只编译未运行。

### 6.2 Local static checks

- `review_surface.py`：base ancestor=true，structurally mergeable=true，无 heuristic lead。
- `git diff --check base...head`：通过。
- `git merge-tree`：clean。
- 当前 `upstream/main` 与 PR base 相同；PR head 仅领先 2 commits。

### 6.3 Local test limitation

尝试命令：

```bash
go test ./pkg/workloadmanager -count=1
go test -race ./pkg/workloadmanager -run 'Test(Ensure|Delete)Sandbox(Template|WarmPool)' -count=1
go test -v ./pkg/workloadmanager -run 'Test(...ownership cases...)' -count=1
```

观察到的问题：多个误并发启动的 Go test 进程同时编译 Kubernetes dependency graph，随后在 linker 长时间低 CPU 停滞；为避免继续占用共享主机资源，已显式终止这些进程及 orphan linker。

结论：本地测试结果是 `INCONCLUSIVE`，不能写成通过；本轮动态证据来自 exact-head GitHub coverage/race job。这个环境问题不改变上述 DeleteOptions 源码证据。

## 7. Review Decision

- Readiness：`CHANGES REQUESTED`。
- Blocking finding：1 个 High，位于 Delete ownership 的 TOCTOU 边界。
- 其它代码路径：未证明第二个 correctness defect。
- Upstream action：本轮未发布 comment、review、`/lgtm`、reviewer request 或 maintainer mention。
- 下一步：如需发布，先把 finding 压缩成 standalone English inline comment，并由用户确认 exact target/body。
