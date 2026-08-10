# Day 55：PR #442 agent-sandbox v0.5.2 新 Head 复审

日期：2026-07-27

## 1. 本轮目标

本轮对 AgentCube upstream [PR #442](https://github.com/volcano-sh/agentcube/pull/442) 的最新 exact head `4f9d4f3265c722b367dcf4e0430eb59aa0ff7d6e` 做第三轮只读 review。

Day52 最后审查的 `73b451b` 只剩 migration/docs/codegen scaffolding，生产依赖仍是 agent-sandbox v0.4.6。当前 head 已重新恢复：

- `sigs.k8s.io/agent-sandbox v0.5.2`；
- agent-sandbox v1beta1 types、GVR 和生成物；
- fresh-install v0.5.2 E2E；
- 一段 opt-in migration test；
- 两份 operator upgrade guide。

因此本轮不能复用 Day52 的“target adapter 不在 tree”结论，而要重新回答：

1. 恢复后的 production adapter 是否保留 direct Sandbox 与 warm-pool 行为；
2. 绿色 E2E 是否真的执行 v0.4.6 -> v0.5.2 migration；
3. upgrade guide 是否可直接执行；
4. 新增启动、health/readiness 和 codegen 改动是否带来独立回归；
5. 作者标记 resolved 的旧 thread 是否已由 current artifact 证明修复。

> 注释：exact head 指本轮审查绑定的精确 Git commit。PR 经多次 force-push 后，不能把旧 SHA 的结论、测试或 thread 状态直接继承到新 tree。

## 2. Freshness 与 PR 快照

### 2.1 社区只读扫描

本轮 freshness scan 冻结于 `2026-07-27 21:55 CST`，起点为上次记录的 `2026-07-23 15:36 CST`。

决策相关变化只有：

| 项目 | 新状态 | 对本轮影响 |
| --- | --- | --- |
| PR #442 | 作者在 2026-07-24 force-push 到 `4f9d4f3` 并重新请求 review | 必须对 current tree 做完整新 review |
| PR #445 | Dependabot GitHub Actions 更新已于 2026-07-27 合并 | `upstream/main` 前移到 `87e6e37`；只改 workflow action pins |
| PR #157 | 旧 PR 只有 Tide 状态刷新，无代码或讨论变化 | 不影响 #442 scope |
| 新 Issue | 无 | 没有新的同题 ownership 或 competing implementation |

Issue #438 仍 open，assignee 仍是 `@safiya2610`，同题实现 PR 仍只有 #442。

### 2.2 Current PR surface

| 项目 | 当前事实 |
| --- | --- |
| PR | `volcano-sh/agentcube#442` |
| Title | `Upgrade agent sandbox v0.5.2` |
| Base | `c16e4744ca540458fa6de9aa2025533b665b9b5c` |
| Head | `4f9d4f3265c722b367dcf4e0430eb59aa0ff7d6e` |
| Commit | 1 个 DCO signed commit，parent 正是 base |
| Diff | 38 files，`+924/-710` |
| Merge structure | `mergeable=true`，与最新 `upstream/main@87e6e37` 的 merge-tree clean |
| Labels | `size/XXL`；没有 `lgtm` / `approved` |
| Review decision | 无真人 APPROVED / CHANGES_REQUESTED；已有真人 review 都是 COMMENTED |
| Policy state | Tide pending，原因是缺 `lgtm` 与 `approved` |

`73b451b` 之后作者先追加 19 个 commits 到 `d9a2cd9`，再于 2026-07-24 force-push 为单 commit `4f9d4f3`。`d9a2cd9` 与 `4f9d4f3` tree SHA 相同，最后一次 force-push 是 squash，不是新的代码变化。

> 分析：当前 patch 结构上已经干净，DCO 与 merge ancestry 也正常。后续 finding 都是行为、测试合同或兼容问题，不能再归因于旧 merge commit。

### 2.3 Checks 与 discussion state

exact head 有 12 个成功 checks：

- DCO；
- Approve workflows；
- build；
- `e2e-test`；
- `codeinterpreter-e2e-test`；
- Codegen Check；
- Codespell；
- Copyright；
- golangci-lint；
- Python Lint；
- Python SDK tests；
- Coverage。

两组绿色 E2E 都明确设置：

```text
AGENT_SANDBOX_VERSION=v0.5.2
E2E_RUN_AGENT_SANDBOX_UPGRADE_TEST=false
```

所以它们证明 fresh v0.5.2 installation，不证明 migration。

GraphQL 全分页读取到 176 个 review threads：

| 状态 | 数量 |
| --- | ---: |
| resolved + outdated | 162 |
| unresolved + outdated | 7 |
| resolved + current | 6 |
| unresolved + current | 1 |

唯一 current/unresolved thread 是 Docusaurus 与 root getting-started 文本重复。current `register.go` 的 `Resource()` breaking signature thread 已被作者 resolve，并回复 `already resolved`，但代码仍未改变。

REST review comments 一共 181 条。旧本地脚本只读第一页 100 条，本轮已修复 `Link` pagination 并以两个脚本交叉得到完整 181 条。

## 3. 变更模型与文件责任

### 3.1 Issue #438 的合同

本 PR 不只是“能编译到新 module”，而要同时满足：

- AgentCube production path 改用 agent-sandbox v0.5.2 / v1beta1；
- direct Sandbox create/readiness/delete 保持；
- WarmPool Claim adoption、session delete、GC 和 refill 保持；
- existing v0.4.6 installation 与 active SandboxClaims 有 documented and tested upgrade path。

> 注释：fresh install 是把空集群直接装到 v0.5.2；migration 是先存在 v0.4.6 CRD、controller 和 v1alpha1 stored objects，再按顺序经过 bootstrap、CRD/controller upgrade、conversion webhook readiness 和可选 storage rewrite。二者不是同一个测试。

### 3.2 Code rationale matrix

| 文件组 | 责任 | 本轮判断 |
| --- | --- | --- |
| `go.mod` / `go.sum` | agent-sandbox、Kubernetes、controller-runtime dependency baseline | target v0.5.2 已恢复；Kubernetes 升到 v0.36.2 |
| `pkg/workloadmanager/*` | direct Sandbox、Claim/WarmPool、readiness、Store 与 lifecycle | 主 v1beta1 mapping 可编译且 focused tests 通过；`Server.Start` 引入独立 readiness 回归 |
| `pkg/apis/runtime/v1alpha1/*` / `client-go/*` | AgentCube 自身 API registration 与 generated clients | full group marker 已修；exported `Resource()` 仍 source-break |
| `hack/update-codegen.sh` | 生成 client/lister/informer | deterministic，但仍 pin `code-generator v0.35.4`，与 Kubernetes v0.36.2 skew |
| `docs/getting-started.md` 与 Docusaurus copy | fresh install、upgrade、cleanup operator contract | migration helper URL 404，backup/readiness/phase 语义不完整 |
| `.github/workflows/e2e.yml` | required validation entrypoint | fresh v0.5.2 进入 required CI；migration 被明确关闭 |
| `test/e2e/run_e2e.sh` | cluster setup、SDK/integration tests、migration fixture | migration 无可达配置；同时删除既有 OIDC/LangChain/MCP execution blocks |

### 3.3 已确认正确或收敛的部分

当前 head 已正确处理：

- `SandboxGVR` 与 `SandboxClaimGVR` 使用 v1beta1；
- direct Sandbox 使用 `SandboxBlueprint.PodTemplate`；
- Claim 使用 `WarmPoolRef`；
- `SandboxWarmPool.spec.replicas` pointer nil handling；
- ready condition 使用 v1beta1 typed status；
- `pkg/apis/runtime/v1alpha1/doc.go` 保存 full `+groupName` marker；
- fresh v0.5.2 E2E 的 CodeInterpreter target job 实际通过；
- `make gen-check` 可重复生成且 worktree clean。

因此不再重复 Day52 中“production adapter 缺失”或旧 informer group marker finding。

## 4. Findings

### 4.1 [P1] Migration E2E 没有任何配置能走完真实升级

位置：

- `.github/workflows/e2e.yml:58-67`
- `test/e2e/run_e2e.sh:20-42`
- `test/e2e/run_e2e.sh:258-278`
- `test/e2e/run_e2e.sh:349-359`
- `test/e2e/run_e2e.sh:537-665`

两个配置分支的实际结果是：

| 输入 | setup 后状态 | migration block 的实际含义 |
| --- | --- | --- |
| 默认 / CI：`AGENT_SANDBOX_VERSION=v0.5.2` | 一开始已安装 v0.5.2 | 后面只是再次 apply v0.5.2，不存在旧 v1alpha1 stored object |
| 手工：`AGENT_SANDBOX_VERSION=v0.4.6` + flag=true | 安装 v0.4.6 后，line 359 的 validator 强制要求 CRD 暴露 v1beta1 并 exit | migration fixture 永远到不了 |

脚本还从未执行官方：

```text
--phase=bootstrap
install v0.5.2
wait conversion webhook
--phase=migrate
```

所以“打开 opt-in flag”与“执行 migration”仍是两个不同事实。

> 分析：这不是因为本机没有 cluster 才无法验证。两个入口分别在 source 中确定为 fresh reapply 或 setup-time exit，属于 source-proven reachable defect。

最小修正方向：把 migration 从普通 fresh E2E 中拆成 dedicated required job，并分别提供 `FROM_VERSION=v0.4.6` 与 `TO_VERSION=v0.5.2`；old setup 不能调用 beta-only validator；fixture、helper、webhook probe 和 assertions 必须在同一 blocking path。

### 4.2 [P1] Migration fixture 的第一个资源就无效，而且不会创建 Claim

位置：

- `test/e2e/run_e2e.sh:542-569`
- `pkg/apis/runtime/v1alpha1/codeinterpreter_types.go:53-57`
- `manifests/charts/base/crds/runtime.agentcube.volcano.sh_codeinterpreters.yaml:409-410`
- `pkg/workloadmanager/codeinterpreter_controller.go:64-79`
- `pkg/workloadmanager/handlers.go:171-175`

fixture apply 的 `CodeInterpreter` 只有：

```yaml
spec:
  warmPoolSize: 1
  minReplicas: 0
  maxReplicas: 2
```

但 current CRD 要求 `spec.template`。脚本有 `set -euo pipefail`，因此 admission reject 会直接终止。

即使补上 template，`CodeInterpreterReconciler` 只负责创建 `SandboxTemplate` 与 `SandboxWarmPool`。真正的 `SandboxClaim` 是调用 WorkloadManager `/v1/code-interpreter` session create path 后由 `handlers.go` 创建的，而 migration block 没有 session request，也没有 raw v1alpha1 Claim fixture。

因此 line 554 等待所谓“1st CodeInterpreter claim”并不对应真实 producer。

> 注释：producer 是真正创建某个资源的组件或请求路径。测试先声明父对象，不代表 controller 一定会创建测试随后断言的所有子对象。

最小修正方向：通过 old AgentCube request path 创建真实 active session/Claim，或明确构造 tagged v0.4.6 raw resources。无论哪种，都要先证明 exact Claim/Sandbox/Pod presence 与 identity，再进入 upgrade。

### 4.3 [P1] 两份 operator upgrade guide 都无法按原文执行

位置：

- `docs/getting-started.md:41-69`
- `docs/agentcube/docs/getting-started.md:36-64`

文档要求：

```bash
wget https://github.com/kubernetes-sigs/agent-sandbox/releases/download/v0.5.2/migrate.sh
```

实际 HTTP 响应是 404。v0.5.2 release assets 只有三份 YAML manifest，没有 `migrate.sh`。tagged upstream migration guide 要从 source checkout 运行 `dev/tools/migrate.sh`；该文件又只是 `helm/files/migrate.sh` 的 wrapper，单独下载 wrapper 也不完整。

另外还有三个 operator gap：

1. backup 只含 Sandbox、SandboxClaim、CodeInterpreter，漏掉 migration 会读取/改写的 SandboxTemplate 与 SandboxWarmPool；
2. readiness 只等待 controller Deployment rollout，没有 probe conversion webhook responsiveness；
3. 文档把 post-upgrade migrate 全部写成 mandatory，但 upstream v0.5.2 guide 定义它在 v0.5.2 上 optional，未来移除 alpha 前才 mandatory。

最小修正方向：直接链接 exact tagged upstream guide，或写出可执行的 pinned source-checkout command；backup 四个 agent-sandbox kinds；在 migrate 前验证 beta list/webhook；准确区分 conditional bootstrap 与 optional storage rewrite。

### 4.4 [P1] WorkloadManager 在 cache 与 Store 就绪前被标记 Ready

位置：

- `pkg/workloadmanager/server.go:135-201`
- `pkg/workloadmanager/handlers.go:108-113`
- `manifests/charts/base/templates/workloadmanager.yaml:89-110`

PR 将 listener 提前到 informer cache sync 与 Store ping 之前：

```text
listener starts
  -> /health always returns 200
  -> RunAndWaitForCacheSync
  -> Store Ping
```

Helm chart 的 readiness probe 在非 SPIRE 模式访问同一 `/health`，SPIRE 模式只做 TCP probe。两者都会在 listener 建立后立即成功，而不是等待 cache 与 Store。

可达后果：Deployment rollout 把 Pod 加入 Service endpoints，Router 或用户请求进入尚未 sync 的 lister 或不可用 Store，得到 startup-window NotFound、内部错误或不完整行为。

此外，初始化结束后 `Start` 只对 `startupErr` 做一次 non-blocking select 并返回 nil。之后 listener 的 fatal error 只会写入无人消费的 buffered channel，main process 不会收到错误。

> 分析：liveness 回答“进程是否还活着”，readiness 回答“是否能安全接收业务流量”。提前暴露 liveness 可以解决慢启动重启问题，但不能让同一信号同时表示依赖已就绪。

最小修正方向：保留 early liveness，但新增由 cache sync + Store ping 控制的 readiness state/endpoint；ready 前阻止业务 route；`Serve` error 需要在整个 process lifetime 被持续 supervision。

### 4.5 [P2] 新 migration block 替换掉既有 OIDC、LangChain 与 MCP E2E

位置：`test/e2e/run_e2e.sh:523-534`

base 在 Python CodeInterpreter tests 后继续执行：

- optional Keycloak/OIDC auth；
- LangChain `AgentcubeSandbox`；
- local MCP streamable HTTP；
- MCP stdio；
- setup 未被跳过时 build/load/deploy in-cluster MCP，并执行 K8s MCP tests。

current head 在 Python CodeInterpreter tests 后直接进入 migration block，然后退出。上述 test files、依赖安装、README 说明和部分 cleanup variables 仍在，但实际 invocation 全部删除。

后果：绿色 E2E 对与 v0.5.2 migration 无关的既有 integration coverage 变弱；“checks green”不能表示这些 paths 在 current head 仍通过。

最小修正方向：恢复等价 invocations，不在同一大段 shell replacement 中交换 migration 与既有 suite；migration 使用独立 job/script。

### 4.6 [P2] `Resource()` exported signature 仍是 source-breaking change

位置：`pkg/apis/runtime/v1alpha1/register.go:41-43`

base：

```go
func Resource(resource string) schema.GroupVersionResource
```

current：

```go
func Resource(resource string) schema.GroupResource
```

仓内 regenerated listers 可编译，不代表 downstream callers 兼容。任何读取 `.Version`、赋值给 GVR 或交给 dynamic client 的 caller 都会 source-break。

Copilot 已在 current code 对应 thread `3631523674` 提出同一问题；作者回复 `already resolved` 并 resolve，但 current artifact 仍是 GroupResource。公开 review 不应再发重复 inline，本地结论仍保留为未修 defect。

最小修正方向：保留原 `Resource()` GVR contract，另加明确命名的 GroupResource helper，或调整生成器入口而不是把 downstream break 隐藏在 generated-code migration 中。

### 4.7 [P2] Migration assertions 还不能证明 Claim/Pod identity

位置：`test/e2e/run_e2e.sh:554-639`

即使前面两个 P1 修复，assertion 仍有三个独立问题：

1. v0.5.2 `kubectl get sandboxclaim` columns 是 `Ready`、`Sandbox`、`Reason`、`Age`，没有 `Bound`；
2. Sandbox name 的 JSON path 是 `.status.sandbox.name`，不是 `.status.sandboxName`；
3. Pod name 可能等于 Sandbox name，warm adoption 时应从 `agents.x-k8s.io/pod-name` annotation 取得；`${SB_NAME}-0` 不是 API contract。

当前 Pod lookup 失败会变成空字符串，之后 mismatch check 只在 old UID 非空时执行。old/new 都空时脚本仍打印 `Pod UID preserved successfully.`，形成 false positive。

最小修正方向：使用 typed JSON/JSONPath condition 与 real status field；从 Sandbox annotation 解析 exact Pod；先 assert old UID 非空，再比较 new UID；增加 pool refill assertion。

### 4.8 机械与维护性问题

这些不单独阻塞，但应在提交 review 前记录：

- `git diff --check HEAD^..HEAD` 发现 6 处 trailing whitespace；
- Kubernetes dependencies 已到 v0.36.2，`hack/update-codegen.sh` 仍 pin `code-generator v0.35.4`；
- root getting-started fresh install 用 v0.5.2 combined manifest，但 cleanup 仍删除 v0.1.1 的旧 `manifest.yaml` + `extensions.yaml`；
- `Server.Start`、mTLS wait 120s、Router HTTP protocol 和 PicoD test timeout 等修改扩大了 dependency upgrade scope，需要各自 rationale/test；
- `test/e2e` 新 preflight 用一个 `sync.Once` 服务不同 `requireKubeConfig` caller，第一次调用决定后续检查集合，设计上容易漏 probe。

## 5. Duplicate audit 与 second-round 判断

### 5.1 不重复的公开 finding

全量 181 条 REST comments 与 176 threads 对照后，以下两项没有现有 human/bot thread：

1. `CodeInterpreter` fixture 无 `spec.template`，且 parent apply 不会创建 Claim；
2. WorkloadManager listener 提前导致 readiness 与 dependency initialization 分离，并丢失 late Serve errors。

existing E2E suites 被整体删除也没有 current/old thread 精确指出。

### 5.2 已有人提过但 artifact 仍错误

| 问题 | Existing thread | Current artifact |
| --- | --- | --- |
| release asset `migrate.sh` 404 | `3630869702` / `3630869754` | 仍引用 404 URL；threads resolved/outdated |
| `Resource()` type break | `3631523674` | current/resolved，但签名仍是 GroupResource |
| migration required CI | 旧 human `3611817315` 与若干 bot comments | old thread resolved/outdated；current workflow 仍明确 false |
| migration docs lifecycle | 旧 human `3611817313` | 文档增加了步骤，但 helper/backup/webhook/phase semantics 未闭环 |

> 分析：resolved 是作者的 workflow 操作，不是代码正确性的证据。second-round review 应重新读取 artifact，同时避免把同一句 bot comment再发一遍。

## 6. 验证证据

在 detached worktree `/tmp/agentcube-pr442-day55` 对 exact `4f9d4f3` 执行：

| 命令 / 检查 | 结果 | 证据边界 |
| --- | --- | --- |
| `go test ./pkg/workloadmanager ./pkg/apis/runtime/v1alpha1 ./pkg/router ./pkg/mtls ./pkg/picod -count=1` | PASS | focused production/unit paths |
| `go test -race ./pkg/workloadmanager -count=1` | PASS | WorkloadManager race instrumentation |
| `go test ./test/e2e -run '^$' -count=1` | PASS | 只证明 E2E package compile |
| `bash -n test/e2e/run_e2e.sh` | PASS | 只证明 shell syntax |
| `go mod verify` | PASS | module cache checksums |
| `make gen-check` | PASS，worktree clean | generated output reproducible |
| `make lint` | PASS | repository linter |
| `make build-all` | PASS | WorkloadManager 与 Router binaries build |
| v0.5.2 `migrate.sh` release URL | HTTP 404 | operator command observed failure |
| `git diff --check HEAD^..HEAD` | FAIL，6 处 trailing whitespace | mechanical quality |
| `npm run build` in Docusaurus | BLOCKED：`docusaurus: not found` | 本地未安装 node dependencies，不归因于 PR |

GitHub exact-head 的 12 个 checks 全绿，是额外 CI 证据。但 migration flag 为 false，且 current script 已删除部分旧 integration calls，所以 checks 的 coverage boundary 必须写清楚。

本轮没有运行 live v0.4.6 -> v0.5.2 cluster migration。原因不是把未知当失败，而是 source path 在 setup 与 fixture 阶段已证明不可达；后续 real cluster validation 应在这些 blocking errors 修复后执行。

## 7. Upstream draft 设计

本轮准备 1 个普通 `COMMENT` review，包含 4 条 inline：

1. migration 没有可达配置，fixture 也不会产生 Claim；
2. operator guide 的 helper URL/backup/webhook/phase contract 不可执行；
3. WorkloadManager readiness 在 cache/Store 前变 True；
4. migration replacement 删除既有 OIDC/LangChain/MCP coverage。

不重复发 `Resource()` inline，因为 exact current thread 已存在；review summary 可以说明仍未解决，但不制造第二个 thread。

本轮未使用 Mermaid。四个 comment 分别是一条线性因果链或两个配置分支，二列表格/短 prose 比 4-10 节点图更快扫描。没有多 actor 并发、循环 retry 或难以在文本中保留的 current/proposed topology。

exact draft 保存在 [Day55 review drafts](day55-pr442-review-drafts.md)。任何发布仍需用户确认 exact target、event 和全文。

## 8. 可复用工程判断

### 8.1 测试必须经过真实 producer

声明一个 parent CR 并不自动证明 child lifecycle。审查异步 E2E 时要逐项问：

```text
谁创建目标对象？
哪个事件触发创建？
测试是否真的触发了该事件？
是否先证明对象存在和 identity，再断言迁移/删除？
```

本例中 `CodeInterpreterReconciler` 管 Template/Pool，session request 才创建 Claim。fixture 跳过 request，后面的 Claim wait 从根上没有 producer。

### 8.2 Early liveness 不能冒充 readiness

把 listener 提前可以避免慢 cache sync 触发 liveness restart，但必须拆开：

- liveness：process/listener alive；
- readiness：cache synced、Store reachable、business path safe；
- fatal supervision：listener failure 始终能通知 main lifecycle。

只移动 `ListenAndServe` 的顺序会同时改变 traffic admission 与 error ownership。

### 8.3 Conversation helper 必须全分页

#442 已有 181 条 review comments。`per_page=100` 但不跟 `Link: rel="next"` 会漏掉 81 条，造成错误 duplicate audit。已为两个本地脚本增加 REST Link pagination、focused tests 和 live #442 regression。

## 9. 当前结论与停止条件

结论：`THIRD ROUND / REQUEST CHANGES RECOMMENDED`。

值得保留的正向证据是：production v0.5.2 adapter 已恢复，focused unit/race/lint/build/gen-check 与 exact-head fresh E2E 均通过，结构 merge clean。

阻塞 merge 的优先顺序是：

1. 建立真正可达、required/fatal 的 v0.4.6 -> v0.5.2 migration job；
2. 修复 invalid fixture，并通过真实 producer 建 Claim；
3. 让 operator guide 使用存在的 pinned helper 与完整 backup/webhook contract；
4. 修复 WorkloadManager readiness/error supervision；
5. 恢复被删除的 integration E2E；
6. 处理已存在 thread 中的 `Resource()` compatibility。

### 9.1 Review comment 发布安排

2026-07-27 用户明确决定：今天先把 findings、证据、影响和 exact draft 保存在 Day55 本地记录中，不向 PR #442 发布 review comment；计划在 2026-07-28 再继续处理 review comment。

“明天再提”表示下一轮恢复 review 发布流程，不是无人值守或预授权发布。2026-07-28 发布前仍需：

1. 重新读取 PR #442 current head、checks 和新增 conversation；
2. 如果 head 不再是 `4f9d4f3`，停止使用当前行号和 draft，对新 diff 重做验证；
3. 如果 head 未变，重新做 duplicate audit，并让用户确认 exact target、`COMMENT` event、review body 与 4 条 inline 全文后再提交。

> 注释：PR 可以在两次工作循环之间 force-push 或新增 review thread。延期一天后重新检查不是重复劳动，而是保证评论仍绑定 current artifact、没有被新提交修复、也不重复他人刚发布的意见。

本轮没有发布 review/comment、resolve thread、mention maintainer、执行 `/lgtm` 或 `/approve`。当前停止条件是保持本地草稿，等到 2026-07-28 完成 freshness 与 exact-text confirmation 后再决定发布。

## 10. 2026-07-29：#442 关闭后的 #446 replacement 复核

### 10.1 社区与 review surface

PR #442 已于 `2026-07-29T00:59:16Z` 关闭。原作者随后以 [PR #446](https://github.com/volcano-sh/agentcube/pull/446) replacement 形式升级到 agent-sandbox v0.5.3；本轮检查的 exact head 是 `822dc7bd5a088d4ccc283bbeca4368ee76a2d570`。

| 项目 | 当前事实 |
| --- | --- |
| PR 状态 | open、non-draft、29 files、`+754/-361`、`size/XXL` |
| Base / head | current base ref `upstream/main@87e6e37`；merge base `146b75f`；head `822dc7b`；分叉后 base 侧 6 commits、PR 侧 4 commits |
| 结构合并 | `git merge-tree` 无 conflict，但 current `upstream/main` 不是 head ancestor |
| Checks | exact head 的 check history 为 16 success、6 failure、1 action-required；当前主要失败面为 Codegen、E2E、CodeInterpreter E2E 与 DCO |
| 作者状态 | 作者明确暂停，原因包括 `VolumeClaimTemplates` API 重构、MCP transport 变化和 generated schema cascade |
| Review threads | 0 个 current active thread；本轮 finding 不重复现有 review comment |

社区 freshness scan 最后刷新于 `2026-07-29 15:10 CST`。#446 仍是 exact head `822dc7b`，0 条 review comments / current threads，inline anchor `pkg/workloadmanager/sandbox_controller.go:46` 未变化；#429 仍是 remote head `b6a3156`。相对 `11:04 CST` 没有新的 upstream issue/PR 更新，`upstream/main` 仍为 `87e6e37`，默认分支该 head 的核心 push checks 全部通过。

> 注释：CI failure 说明当前 head 尚未通过验证，但不自动证明下面的 scheme finding。该 finding 使用 production binary wiring、reconciler 类型和独立定向测试闭合因果。

### 10.2 [P1] Production scheme 与 reconciler API version 不一致

位置：`cmd/workload-manager/main.go:32-33,47-51,187-191`、`pkg/workloadmanager/sandbox_controller.go:29,41-47`、`pkg/workloadmanager/codeinterpreter_controller.go:146-172`

PR 将 `SandboxReconciler`、`SandboxTemplate` builder 和 request handlers 切到 `v1beta1`，但 production `schemeBuilder` 仍只调用：

```text
sandbox v1alpha1 AddToScheme
extensions v1alpha1 AddToScheme
```

同时，Sandbox controller 仍以 `v1alpha1.Sandbox` 建立 watch，reconciler 收到 key 后却用同一个 manager client 读取 `v1beta1.Sandbox`。CodeInterpreter reconcile 也会用该 client 读取和创建 `v1beta1.SandboxTemplate`。

因此 production path 是：

```text
WorkloadManager manager
  -> alpha-only scheme / alpha Sandbox watch
  -> beta Sandbox GET or beta SandboxTemplate GET/Create
  -> scheme cannot resolve beta GVK
  -> reconcile returns an error before normal readiness/lifecycle handling
```

在 detached worktree `/tmp/agentcube-pr446-focused-review` 增加未提交的 binary-wiring regression，并执行：

```bash
go test ./cmd/workload-manager \
  -run TestProductionSchemeRegistersAgentSandboxV1beta1 -count=1
```

结果为 FAIL：

```text
production scheme cannot resolve Sandbox:
no kind is registered for the type v1beta1.Sandbox

production scheme cannot resolve SandboxTemplate:
no kind is registered for the type v1beta1.SandboxTemplate

production scheme cannot resolve SandboxWarmPool:
no kind is registered for the type v1beta1.SandboxWarmPool
```

这是 **source-proven reachable defect**：触发者是正常的 CodeInterpreter reconcile 或 Sandbox readiness event，不依赖 mock-only 异常状态；当前没有把它描述为已观察到的线上事故。

为证明修复边界，在同一临时 worktree 只做了 counterfactual，不提交也不推送：把 `cmd/workload-manager/main.go` 的 sandbox/extensions imports、两个 `AddToScheme` 和 Sandbox controller `For(...)` 全部对齐到 `v1beta1`。随后结果为：

```text
go test ./cmd/workload-manager -run TestProductionSchemeRegistersAgentSandboxV1beta1 -count=1
PASS

go test ./cmd/workload-manager -count=1
PASS

go test ./pkg/workloadmanager -count=1
PASS
```

> 分析：红测同时覆盖 `Sandbox`、`SandboxTemplate` 和 `SandboxWarmPool`，绿测只改变 production wiring。这样可以把失败归因到 binary scheme/watch 装配，而不是 v0.5.3 类型本身、fake client 或 controller 业务逻辑。

最小修正方向：

1. 在 production scheme 注册 reconcilers/builders 使用的 agent-sandbox 与 extensions `v1beta1` types；
2. 让 Sandbox controller watch 与 reconciler GET 使用同一个 intended API version；
3. 在 `cmd/workload-manager` 增加 production scheme regression，避免 package-level fake scheme 同时注册 alpha/beta 后掩盖 binary wiring 漏项；
4. 若仍需 alpha compatibility，明确双版本注册/监听合同，而不是由不同层隐式混用。

> 分析：package unit tests 可以自行构造同时包含 alpha/beta 的 scheme，因此即使 controller/builder tests 通过，也不能证明 `cmd/workload-manager/main.go` 的真实装配完整。dependency upgrade review 需要把 binary scheme、controller watch、typed object 和安装 CRD 当作一个兼容面检查。

### 10.3 本周推进判断

1. **优先完成 #446 focused review。** 先把上面的 finding 压成一条 standalone inline/comment draft，再复核 current head 和 duplicate audit；任何发布仍需用户确认 exact target/body/event。
2. **维护本人 PR #429。** `ci/go-toolchain-update-workflow@b6a3156` 相对 current main 为 13 commits behind / 1 ahead，结构合并无冲突，exact head 11 checks success；本周可 rebase 到 `87e6e37`，重跑 workflow/script validation，再准备简短 reviewer follow-up。
3. **保留 Pod lookup cleanup，但不竞争 #413。** fork `cleanup/remove-sandbox-pod-fallback@eefce59` 已采用 maintainer 最新建议的 Sandbox-name live Pod GET，且不依赖将被移除的 pod-name annotation；但 #413 仍是 active same-topic PR，应先等原作者响应或只提供 review/test evidence。
4. **暂不安排本机 benchmark。** 当前 `kubectl` 没有 current context，并回退访问 `localhost:8080` 失败；冷启动、p99 和并发 5/20 测试需要先恢复可用 cluster，不能把它当成本周立即可执行的 0.5 天任务。

截至 10.3 的只读分析阶段，没有发布 upstream comment/review、没有 `/assign`、没有 reviewer request，也没有修改 #446、#429 或 #413 的远端分支；后续经用户 exact confirmation 执行的动作记录如下。

### 10.4 Focused review 已发布

用户确认 exact target/body/event 后，于 `2026-07-29 15:20:11 CST` 在 #446 exact head `822dc7b` 提交 `COMMENT` review：

- Review：<https://github.com/volcano-sh/agentcube/pull/446#pullrequestreview-4805118919>
- Inline thread：<https://github.com/volcano-sh/agentcube/pull/446#discussion_r3671892415>
- Anchor：`pkg/workloadmanager/sandbox_controller.go:46`，right side
- Root body：empty
- Inline metrics：103 visible words / 1 nonblank line / 798 characters

发布后 API 回读确认 `state=COMMENTED`、`commit_id=822dc7bd5a088d4ccc283bbeca4368ee76a2d570`，正文与批准文本一致。未附带 `/lgtm`、`/approve`、maintainer mention 或额外 root comment。

> 注释：作者已暂停并不等于 finding 无效；这条评论只提供 production binary wiring 的独立红绿测试证据，供作者恢复工作时处理，不要求立即响应。

## 11. 2026-07-29：#446 `4ced4ea` second-round freshness

### 11.1 社区增量

`2026-07-29 19:30 CST` 从 `15:10 CST` 快照开始做增量扫描。`upstream/main` 仍为 `87e6e37`，这段时间没有新 issue、merge、close 或 default-branch push；实质变化集中在 #446。作者把 head 从 `83002f1` 推进到 `4ced4eabd12be667ca3509328ccbaaa8c29ea24d`，PR 现为 9 commits、38 files、`+894/-460`。

原 inline finding 已被代码处理：commit `27517d0` 把 `cmd/workload-manager/main.go` 的 sandbox/extensions scheme、`AddToScheme` 和 Sandbox controller watch 全部迁移到 `v1beta1`，并新增 `cmd/workload-manager/main_test.go::TestSchemeRegistration`。这与本地 red/green counterfactual 的最小修正方向一致，因此 production alpha/beta scheme mismatch 不再是 current-head finding。GitHub thread 仍显示 active，作者最后回复仍是 `yes sure doing..`；本轮没有替作者 resolve，也没有追加确认评论。

> 分析：review 是否被处理应按 current code 判断，不能只看 thread 是否 resolve。这里可以把原 finding 标为 code-addressed，但还不能据此给整个 38-file dependency upgrade `/lgtm`。

### 11.2 新增 MCP workaround 与 #448 的关系

`83002f1..4ced4ea` 又叠加三个 MCP commits：为 deployment 设置 `MCP_TRANSPORT=sse` / `MCP_HOST=0.0.0.0`，把 dependency pin 到 `mcp>=1.8.0,<2.0.0`，并把 E2E client 改为 v1 `sse_client`。这四个 MCP-related files 与独立 [#448](https://github.com/volcano-sh/agentcube/pull/448) 的 maintainer-approved v2 migration scope 重叠，但方向相反：#448 保持 Streamable HTTP `/mcp` 并采用 `mcp>=2,<3`，且 exact head `1286b3a` 的 upstream 13/13 checks 全绿。

#446 run [`30446047184`](https://github.com/volcano-sh/agentcube/actions/runs/30446047184) 已直接证明当前 SSE workaround 未闭环：server 以 SSE transport 启动，测试仍把 `MCP_K8S_MCP_URL` 设置为 `/mcp`，`sse_client` 对 `http://127.0.0.1:19446/mcp` 得到 `404 Not Found`。Python Lint 同时因两个遗留 `httpx` imports 报 `F401`。因此这不是仅等待 #448 的动态冲突，current #446 head 自身也没有通过它引入的 transport path。

> 注释：`mcp<2` pin 是同一官方 SDK 的 v1 compatibility workaround，不是 agent-sandbox v0.5.3 适配本身的依赖要求。等 #448 合入后，#446 更干净的集成方式是 rebase 并删除重复的 MCP pin/SSE/client 补丁，而不是继续维护第二套 transport migration。

### 11.3 Upgrade fixture 的独立失败链

同一 E2E run 的 `e2e-test` 在 upgrade scenario 第一步失败：脚本向 AgentCube `CodeInterpreter` CR 写入不存在的 `spec.minReplicas` / `spec.maxReplicas`，API server 返回 strict-decoding `BadRequest`；fixture 同时缺少 CRD 标记为 required 的 `spec.template`。

即使只修 manifest，下一层 producer contract 仍不成立：`CodeInterpreterReconciler` 只管理 `SandboxTemplate` / `SandboxWarmPool`，`SandboxClaim` 由 WorkloadManager session-create handler 的 `buildSandboxByCodeInterpreter -> createK8sResources` 路径创建。当前脚本只 `kubectl apply CodeInterpreter`，随后轮询 owner 为该 CR 的 `SandboxClaim`，没有调用真实 session producer。因此它不能验证所声称的 warm-adoption upgrade lifecycle。

> 分析：CI 的 strict-decoding error 是 observed failure；“修完字段后仍不会产生 claim”是由 current production ownership path 证明的 reachable test-design gap。下一版应使用 admission-valid `CodeInterpreter`，再通过真实 WorkloadManager create-session API 生成 claim，先证明 claim/Sandbox/Pod presence 与 identity，之后才进入 controller stop、migration、UID preservation 和 cleanup assertions。

### 11.4 当前 gate 与动作

exact `4ced4ea` 快照的 checks 为 8 success、3 failure、DCO `action_required`：两个 E2E 和 Python Lint 失败，最早四个 commits `dd6239e`、`26c8de8`、`1e5eb90`、`822dc7b` 缺 signoff。Tide 仍缺 `lgtm` / `approved`。

本轮只做只读 second-round review，没有发布 comment、reply、resolve、review event、Prow command 或 reviewer request。作者仍在频繁补丁阶段；下一步等待 head 稳定，再复核是否已移除与 #448 重叠的 MCP workaround，并优先验证 upgrade fixture 是否真正经过 session producer。没有必要现在用 CI 可见事实追评。

### 11.5 扫描期间的连续 push 与 force-push

上述 `4ced4ea` 记录尚未提交时，作者又连续推送 `9928ed7` 与 `7f603c5`；随后在 `2026-07-29 19:37 CST` force-push 删除 `7f603c5`，current head 回到 `9928ed789df9cd3f3547250fa627c5212bc76fe5`，现为 10 commits、41 files、`+937/-498`。`9928ed7` 把 #448 的 v2 migration 内容重新落进 #446，但留下了互相矛盾的 transport wiring：CLI choices 只有 `stdio` / `sse`，实际仅在 `args.transport == "streamable-http"` 时启动 HTTP；deployment 传 `sse` 会进入 `else` 并运行 stdio，因此不会监听 readiness probe 和 E2E 所需的 8000 端口。

更重要的是，`9928ed7` 不是具有两个 parents 的 Git merge，而是以 `4ced4ea` 为唯一 parent 的新 commit：author 显示 `ranxi2001`，committer 为 `safiya2610`，正文只有 `fix: migrate code interpreter MCP to SDK v2 (merge)` 且没有保留 source commit 的 signoff。DCO 因而把它连同原先四个 unsigned commits 一起列为 5 个 failure entries。该 commit 还意外删除了 `pkg/router/server.go` 的 `Start` 函数声明、`addr` / `h2cHandler` 初始化与 imports，却留下后半个函数体。被 force-push 丢弃的 `7f603c5` run `30447971445` 已在相同 tree 内容上观察到 `server.go:183:2: expected declaration, found s`；这不是 #448 原 7-file diff 的内容。

current `9928ed7` 从 19:38 到 19:47 CST 连续约 9 分钟没有再次变化；8 checks success、Python Lint 与 DCO 失败，两个 E2E 尚在运行。Python Lint 仍因 local MCP test 的一个 unused `httpx` import 失败。即使暂不等待 E2E，impossible transport condition、malformed Router source、invalid upgrade fixture 和 DCO authorship/signoff state 已足以判定 current head 不可 review-ready。

> 分析：此时最有价值的动作不是逐个指出作者已能从 CI 看到的 lint/compile error，而是等待作者停止叠加补丁。下一轮应先核对 commit topology、authorship/signoff、`upstream/main...head` scope 和 Router source 是否恢复，再审 agent-sandbox migration 本身；不要把 #448 的 clean commit evidence自动套用到这次手工重落后的树。

### 11.6 2026-07-30：作者回复与 #448 去重措辞

`2026-07-30 01:19 CST` 从 `2026-07-29 19:47 CST` 继续做只读增量扫描。`upstream/main` 仍为 `87e6e37`，没有新 issue、merge、close 或 default-branch push；唯一更新仍是 #446。作者再次 force-push，把 current head 回退到 `83002f159532e587187e1dca8e55678ab07e5479`：6 commits、36 files、`+858/-426`。这删除了后续手工重落 #448 时引入的 Router source 破坏和错误 authorship，但 current tree 仍保留独立 SSE workaround；两个 E2E、Code Interpreter E2E 和 DCO 仍失败。

作者在既有 scheme review thread 中补充了 MCP 失败原因：无上界的 `mcp>=1.8.0` 在 clean CI 中解析到 v2，旧 `FastMCP` import 因而导致容器启动失败。这与 #447 / #448 已记录并验证的 shared dependency drift 是同一根因。#448 仍为 open PR，exact head `1286b3a` 的 MCP server、HTTP/stdio client 与 in-cluster E2E 迁移 checks 均通过，但尚未合入 `main`。

> 分析：回复应写成 “opened #448 to address it”，而不是 “fixed it at #448”。前者准确表达修复已提交且验证通过、但仍等待 merge；后者容易被理解为 upstream 默认分支已经修复。为保持 #446 的 agent-sandbox upgrade scope，建议作者在 #448 合入后 rebase，并删除重复 MCP workaround，而不是在 #446 继续维护第二套 migration。

推荐回复为 55 visible words / 1 nonblank line：

```markdown
Thanks, the v1beta1 manager wiring and binary-level scheme test now address my original comment. I also ran into the same MCP SDK v2 compatibility issue and opened #448 with the full v2 migration. Once it merges, #446 can rebase on `main` and drop the overlapping MCP changes, keeping this PR focused on the agent-sandbox upgrade.
```

用户随后确认 exact target/body。`2026-07-30 01:28:33 CST` 在既有 inline thread 发布 [reply 3676642917](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3676642917)；API 回读确认 author 为 `ranxi2001`、`in_reply_to_id=3671892415`，正文与 55-word 确认稿逐字一致。发布前 #446 / #448 head、目标评论与 checks 未变化，自 01:19 CST 也没有新的 issue、merge、close 或 main push。本轮没有 resolve thread、提交 review event、Prow command 或 maintainer mention。

## 12. 2026-07-30：独立 v0.5.3 adapter 与 #446 实现对照

### 12.1 目标和分支边界

为避免 review 只停留在 diff 观感，本轮把已验证的 fork-only v0.5.2 adapter 升级到 agent-sandbox v0.5.3。新分支 `compat/agent-sandbox-v053-independent` 从最新 `upstream/main@0704bb9` 重放原有两个 signed commits，再追加单独的 v0.5.3 commit；最终 exact head 为 `595731413424fc12b38e128c6f9456aa1bd0a78e`。

`git range-diff` 证明前两个 patch 的语义没有在 rebase 中变化：

```text
d70ab94 = 428a40d refactor: use standard HTTP and scheme APIs
2d90b07 = e5b6402 compat: adapt agent-sandbox v0.5.2
f5a3b00 ! 5957314 compat: adapt agent-sandbox v0.5.3
```

第三个 patch 只涉及 5 个文件：`go.mod`、`go.sum`、`docs/getting-started.md`、`test/e2e/run_e2e.sh` 和 `test/e2e/e2e_test.go`。它没有修改 AgentCube production controller，因为 v0.5.2 adapter 已经完成 alpha -> beta 的 GVR、scheme、watch、OperatingMode、SandboxBlueprint、WarmPoolRef 和 pointer replicas 切换；v0.5.3 没有再次破坏这些 Go type contracts。

> 分析：这说明“升级到 v0.5.3”和“完成 v0.5.x beta API migration”是两层工作。前者在已经正确适配 v0.5.2 的 baseline 上是很小的增量；不能因为 #446 总 diff 很大，就把所有 generated code、MCP 或跨平台脚本改动都解释成 v0.5.3 必需项。

### 12.2 v0.5.3 的 AgentCube 可见增量

模块升级将 `sigs.k8s.io/agent-sandbox` 从 `v0.5.2` 提到 `v0.5.3`，MVS 同步带入 `github.com/go-logr/logr v1.4.4`、Prometheus client/common/procfs 和 JWT `v5.3.1` 等 transitive 更新。安装、卸载、migration-guide link 和 E2E 默认 manifest version 均改为 `v0.5.3`；“从 v0.4.x 应直接升到 v0.5.2 或更高版本”仍保留，因为它描述的是 v0.5.2 已修复 warm claim migration 的历史下限，不应机械改成 v0.5.3。

官方 v0.5.3 对 AgentCube 最直接的新 API contract 是 `Sandbox.spec.volumeClaimTemplates` 创建后不可修改。另一个 extension API marker 放宽了 `SandboxClaim` annotation 对 `cluster-autoscaler.kubernetes.io/safe-to-evict` 的限制，但 AgentCube 当前适配没有新增或改写该 annotation，因此不需要 production patch。

> 注释：CEL 是 Kubernetes CRD 的 Common Expression Language 校验规则。它由 API Server 在写入对象时执行；只在 Go 内存里构造一个字段，无法证明发布清单真的包含并执行该规则。

### 12.3 因果测试和真实失败链

新增 `TestSandboxVolumeClaimTemplatesImmutable` 使用真实 controller-runtime client：先在 `agentcube` namespace 创建 Suspended Sandbox，再读取最新对象、尝试追加有效 PVC template，并要求 API Server 返回 `apierrors.IsInvalid` 且包含 `volumeClaimTemplates is immutable`。测试 cleanup 接受 `NotFound`，避免失败路径留下对象。

第一次在隔离集群运行时，测试没有直接到达 CEL，而是失败为：

```text
Operation cannot be fulfilled on sandboxes.agents.x-k8s.io ...:
the object has been modified; please apply your changes to the latest version and try again
```

根因是 agent-sandbox controller 在测试 `Get` 与 `Update` 之间更新了同一 Sandbox 的 resourceVersion，API Server 先返回 `409 Conflict`。修正采用 client-go `retry.RetryOnConflict`：每次冲突后重新读取对象，只有最终返回 `Invalid` 才算通过；不能把任意 update error 当作 immutability success。修正后 focused E2E 在 0.13 秒内通过。

隔离环境为 k3d + k3s `v1.32.5+k3s1`，只安装官方 v0.5.3 `sandbox.yaml` / `extensions.yaml`。controller image 回读为 `registry.k8s.io/agent-sandbox/agent-sandbox-controller:v0.5.3`，rollout 成功；CRD 中实际回读到：

```json
{"message":"volumeClaimTemplates is immutable","rule":"has(self.volumeClaimTemplates) == has(oldSelf.volumeClaimTemplates) && (!has(self.volumeClaimTemplates) || self.volumeClaimTemplates == oldSelf.volumeClaimTemplates)"}
```

测试后确认 namespace 中没有残留 Sandbox，再删除 k3d cluster 和临时 kubeconfig。

### 12.4 调试过程与验证证据

本轮保留了以下过程问题，而不是只记录最终绿测：

1. 第一轮 targeted compile 命令误写 `./cmd/agentd`，该目录在当前 baseline 不存在；改用实际的 `cmd/picod` / `cmd/router` 后通过。这是测试清单错误，不是 v0.5.3 incompatibility。
2. 新增测试时一度漏掉 `SandboxBlueprint` literal 的 closing brace，`gofmt` 立即报语法错误；补齐后再进入编译和运行验证。
3. 一次 `make gen-check` 在生成期间报 lister package 暂时不可见。单独 `go mod tidy` 正常，确认没有残留 generator 进程后严格串行重跑两次，均完成 client/lister/informer generation 且 `git diff --exit-code` 为零。该瞬时失败未稳定复现，因此不能把原因强行归到 code-generator 版本；最终也没有修改 `hack/update-codegen.sh`。
4. 固定的旧 k3d binary 默认选择 k3s `v1.21.7`，不足以验证当前 CEL contract；立即中止并清理，显式使用 `rancher/k3s:v1.32.5-k3s1` 重建。
5. 第一次真实 API 测试命中 controller 并发导致的 `409 Conflict`；采用 `RetryOnConflict` 后才稳定到达 CEL `Invalid` 结果。

最终本地验证：

```text
make lint                                                    PASS
make gen-check                                               PASS, zero diff
make build-all                                               PASS
all non-E2E Go packages, -count=1                            PASS
go test -race ./pkg/workloadmanager -count=1                 PASS
go test ./test/e2e -run '^$' -count=1                        PASS
isolated v0.5.3 TestSandboxVolumeClaimTemplatesImmutable     PASS
```

fork branch `compat/agent-sandbox-v053-independent@5957314` 的 9 个 push workflows 全部通过：Agentcube CI、Agentcube E2E、Codegen、Coverage、Lint、Python Lint、Python SDK、Codespell 和 Copyright。该分支只用于独立实现与 review 证据，没有创建 self-PR 或 upstream PR。

### 12.5 对 #446 current head 的新增 review 结论

本轮开始时 #446 为 `83002f1`；实现和 fork CI 期间，作者又以 merge commit `c0fc500` 合入 `upstream/main@0704bb9`。current PR 仍是 7 commits / 36 files，merge state `UNSTABLE`。

独立实现证明两项具体 review finding：

1. #446 的 `TestSandboxVolumeClaimTemplatesImmutability` 只构造 Go `Sandbox` struct，然后断言 slice length 和 name。它没有创建对象、没有 update、没有 API Server，也没有读取 v0.5.3 CRD；即使删除 CEL marker，该测试仍会通过。我们的真实 API 测试则会因规则缺失而失败，因此覆盖的是 release behavior，而不是类型可构造性。
2. #446 的 `hack/update-codegen.sh` 硬编码 `/c/Program Files/Go/bin:/c/Users/safiy/go/bin`，复制并 patch module cache source、删除整个 `client-go`，再手工逐个执行三个 generator。我们的 branch 在 Linux 上用 upstream 原脚本连续通过 `make gen-check` 且 zero diff，说明这套个人 Windows PATH 和 generator rewrite 不是 v0.5.3 的必要适配；它扩大 portability 和 maintenance risk。

`c0fc500` 也没有按此前建议 rebase 后删除与 #448 的重叠，而是在 merge conflict resolution 中把已合入 main 的 MCP v2 client 再次破坏：两份测试正确保留了 v2 使用的 `httpx2`，却错误保留旧 `sse_client` import，并调用未 import 的 `streamable_http_client`。Python Lint run `30511568113` 观察到 2 个 F401 和 2 个 F821。

E2E run `30511568062` 随后两个 jobs 都失败。local MCP 测试等待 `127.0.0.1:19245` 一分钟后连接仍被拒绝，server process exit code 为 0；in-cluster MCP Deployment rollout 等待五分钟后超时。current CLI 仍接受/传入 `sse`，但 merge 后的 server 分支只在值为 `streamable-http` 时启动 HTTP，否则进入 stdio；因此这两条失败与 current transport wiring 一致。DCO 仍为 action-required。

> 分析：这里不能把 `c0fc500` 简单视为“已经吸收 #448”。Git topology 确实包含 #448，但 conflict resolution 后的工作树没有保留 #448 的有效行为。review 必须按 current tree 和 exact-head checks 判断，而不是按 merge parent 推断。

截至本节写入，没有向 #446 发布新 review、comment、reply、resolve、Prow command 或 reviewer request。作者仍在连续补丁阶段；下一轮先刷新 exact head 和 E2E 终态，再决定是否把 immutability test validity 与 non-portable codegen 压成 focused review draft，发布前仍需用户确认 exact target/body/event。

### 12.6 `2eefda6` “Everything is done” 复核

作者在 `2026-07-30T08:07:52Z` 评论 `@acsoto @ranxi2001 Please check. Everything is done.`。`2026-07-30 17:13 CST` 回读确认 #446 已 force-push/squash 为 exact head `2eefda6bd88a00fe217a0c154536d5883d46209b`：单个 signed commit、33 files、`upstream/main@0704bb9` 是其直接祖先，GitHub 判定 `MERGEABLE`。build、Codegen、Codespell、Go/Python lint、Python SDK、Coverage、两个 E2E 和 DCO 共 11 项实际检查全部通过；只有 Tide 因尚缺 `lgtm` / `approved` 保持 pending。

这次补丁已经处理旧 head 的两个动态问题：MCP 工作树保留 #448 合入后的 Streamable HTTP 行为，#446 对 `integrations/code-interpreter-mcp/pyproject.toml` 只剩无语义的文件末尾换行差异；此前错误的 v0.4.6 upgrade fixture 也已删除。因此不能继续用 `c0fc500` 的 Python Lint / E2E failure 评价 current head。

但 “done” 只说明作者认为补丁和 CI 已完成，不等于 focused code review 已无问题。exact current tree 仍保留两项有证据的 finding：

1. `pkg/workloadmanager/codeinterpreter_controller_test.go:144-168` 的 `TestSandboxVolumeClaimTemplatesImmutability` 只构造内存 Go struct，并断言 PVC slice 长度和名称。它没有 CREATE/GET/UPDATE，没有 API Server，也不执行 v0.5.3 CRD CEL；focused `go test` 在无 cluster/CRD 环境中 0.00 秒通过，证明该测试即使删除 immutability rule 仍会绿。PR body 关于“test the new immutability behavior”的表述因此缺少因果覆盖。fork `5957314` 已证明可行测试形态：真实创建 Sandbox、重新读取、`RetryOnConflict` 更新 `spec.volumeClaimTemplates`，并要求 API 返回 `Invalid`。
2. `hack/update-codegen.sh:7` 仍硬编码作者个人 `/c/Users/safiy/go/bin`，`:59-74` 复制并用 GNU `sed -i` patch generator source、安装 binaries，`:77` 删除整个 `client-go` 后手工生成。exact `2eefda6` 的 `make gen-check` 在本机确实通过且 zero diff，所以不能称它当前 Linux CI 失败；准确风险是脚本把 v0.5.3 dependency upgrade 扩大成个人路径、GNU/BSD portability 和生成器维护变更，而 fork adapter 使用 upstream 原 codegen flow 已同样通过。

另有两项非阻断清理：`integrations/code-interpreter-mcp/pyproject.toml` 只删除末尾换行；两份 getting-started 文档各有一处 trailing whitespace。升级文档描述 mandatory migration，但 current E2E 只验证 fresh v0.5.3 install；v0.4.6 persisted objects / storedVersions 的原地 migration 仍应作为未验证限制，而不是冒充已覆盖。

本节没有向 #446 发布 review/comment、resolve thread、Prow command、reviewer request 或 maintainer mention。若要公开反馈，优先把前两项拆成 focused inline comments，发布前必须再次核对 exact head/anchor/duplicate，并让用户确认 exact target/body/event。

## 13. 为什么 `@acsoto` 在 final head 找到更多问题

`2026-07-30 17:42 CST` 对 #438、#446 exact `2eefda6`、当前 workflows 和 `@acsoto` 的 6 条意见做了复盘。结论不是简单的“maintainer 更熟”，而是两轮 review 的入口和停止条件不同：我们最后做的是基于历史 head 与 fork adapter 差异的 focused residual review；`@acsoto` 作为 #438 作者，从 Issue 验收合同重新审了一遍完整 final diff。

> 分析：maintainer 对需求背景更熟是客观优势，但 #438 的验收条件是公开文本。没有把它重新转成 final-head acceptance matrix，仍然是我们的流程缺口，不能用角色差异解释掉。

### 13.1 Finding 对照

| `@acsoto` finding | 他使用的 review 入口 | 我们为什么漏掉或降级 |
| --- | --- | --- |
| 必须测试 v0.4.6 active SandboxClaim 到 v0.5.x 的 migration、adoption、deletion、GC 和 pool refill | 直接逐句对照 #438 acceptance contract | 我们知道两个分支都没有验证 persisted objects / storedVersions，却把它写成 residual limitation；#438 原文明确要求 `documented and tested upgrade path`，因此这里应是 blocker，不是可接受限制 |
| 文档引用的 `v0.5.3/migrate.sh` release asset 不存在 | 验证用户会执行的每一个外部 artifact | 我们检查了 fresh-install manifest 名称，却没有枚举 upgrade guide 的全部 URL；官方 release 实际只有 `extensions.yaml`、`sandbox.yaml` 和 `sandbox-with-extensions.yaml` |
| `cmd/workload-manager/main_test.go` 的 5 个 hard-coded GVK 全错 | 直接运行新增测试所在 package | 我们确认“有 binary-level scheme test”后没有在 final `2eefda6` 重跑 `go test ./cmd/workload-manager -count=1`；本轮真实复现 5 个 assertion 全失败 |
| `handleSandboxCreate` 绕过 `CreateSandboxRequest.Validate()`，空 name 不再返回 400 | 对比修改前后的 request validation boundary | 我们把注意力放在 v1beta1 types、readiness 和 migration，没有把原有 `Validate()` 的 kind/namespace/name 矩阵逐项映射到新代码；current tests 只补 namespace case，没有 empty-name regression |
| `[[ v0.10.0 < v0.5.0 ]]` 是字典序而不是 semver | 检查新增 shell 分支的边界值 | 我们只确认旧 invalid migration fixture 被删除、fresh v0.5.3 能安装，没有对版本条件做 `v0.10.0` counterexample |
| `hack/update-codegen.sh` 含个人 Windows PATH | 逐行检查共享工具脚本 | 这一项我们也发现，并且还有 GNU-only `sed -i` / source patch / global install 的更广证据；发布 guard 发现 maintainer 已先评论，因此主动去重 |

我们额外找到而 `@acsoto` 当前评论未覆盖的是 immutability test causality：#446 的 test 只构造内存 struct，不执行 API Server CEL；fork `5957314` 的真实 CREATE/GET/UPDATE/Invalid E2E 提供了 counterexample 和修正方向。因此评论数量不是 review 质量的完整度量，但 final-head 覆盖面上，他这轮明显更完整。

### 13.2 为什么 green CI 没保护住新增测试

exact `2eefda6` 的 GitHub checks 全绿，但 workflow-to-command 映射是：

- build job 执行 Docker build，不运行 Go unit tests；
- coverage job 只执行 `go test ... ./pkg/...`，不包含 `cmd/workload-manager`；
- E2E job 执行 `make e2e`，也不会发现 `cmd/workload-manager/main_test.go` 的错误 GVK。

因此 `go test ./cmd/workload-manager -count=1` 在本机稳定失败，与 checks 全绿并不矛盾。我们的错误不是“不相信 CI”，而是没有先回答“哪个 check 实际执行了这个新增测试”。

> 注释：编译生产 binary 时，Go 不会执行 `_test.go`。所以 Docker image 能 build 成功，只证明生产源码可编译，不能证明同目录新增 test 的断言正确。

### 13.3 根因与修正规则

1. **需求锚点漂移。** 多轮 force-push/MCP CI 处理占用了注意力，最后没有回到 #438 重建 acceptance matrix。
2. **比较式 review 产生锚定。** fork adapter 证明了 minimal v0.5.3 路径，但我们只用它验证 immutability/codegen，没有反向追问 #446 每个额外 hand-written file 为什么存在、由哪个测试覆盖。
3. **增量 review 没有 final-head reset。** 作者 squash 为单 commit 并说 `Everything is done` 后，我们仍主要验证已知旧问题是否消失，而不是把 `2eefda6` 当全新 PR 从 body/issue/files/tests 重新审。
4. **把 checks 状态当成测试发现证据。** 没有建立 changed `*_test.go` package 到 workflow command 的映射。
5. **边界清单不完整。** 文档 URL、request validation matrix、shell version comparison 这些普通但高收益的检查没有进入最后一轮。

以后 dependency/API PR 在 final head 进入“ready for review”状态时，固定执行：父 Issue acceptance matrix -> hand-written file rationale -> 每个 changed test package 直接运行 -> workflow command coverage map -> external asset/version boundary audit -> focused runtime/lifecycle evidence。旧 head 的结论只能作为线索，不能替代这一轮 reset。

本复盘没有新增 upstream comment、reply、resolve、Prow command、reviewer request 或 maintainer mention。

### 13.4 从 checklist 固化为 executable harness

本轮把上述规则落到 `.agents/skills/agentcube-pr-review/scripts/final_head_review.py`，避免下一次仍靠 reviewer 临时记忆。它在 exact base/head 上生成五块 evidence ledger：父 Issue/proposal acceptance candidates、全部 hand-written changed files、changed Go test package 到 workflow command 的覆盖映射、diff boundary leads，以及可选的 direct Go test / external URL 结果。

> 分析：harness 不替 reviewer 判断 blocker，也不会因为正则命中就生成 upstream finding。它解决的是“有没有看、哪个 check 真跑了、外部 artifact 是否验证过”这类可机械证明的问题；组件责任、生命周期正确性和 finding 严重性仍由 review skill 的 point -> line -> surface 与 production reachability gates 判断。

对 #446 exact `2eefda6` 的 forward validation 已完成，结果如下：

- workflow command tracing 证明 `./pkg/...` 和 `./test/e2e/...` 有执行证据，但 `./cmd/workload-manager` 不在任何 CI Go test scope；
- `--run-go-tests` 因此只直接运行 `go test ./cmd/workload-manager -count=1`，复现 5 个 scheme assertion failures，没有误触发需要 Kind 集群的 E2E；
- URL checker 实测 `v0.5.3/migrate.sh` 为 `404`，同 release 的 `sandbox-with-extensions.yaml` 为 `200`；含 `${AGENT_SANDBOX_VERSION}` 的 URL 被标为 `unresolved-variable`，不会伪装成 404；
- diff boundary checks 同时命中 lexicographic version comparison、personal absolute PATH 和 removed `Validate()` call；
- skill 目录的 14 个 Python 单测、`py_compile`、`quick_validate.py` 和 `git diff --check` 通过。

harness 在真实缺陷存在时以 exit 1 结束，同时保留完整 ledger；这证明此次复盘已经进入可重复工具链，而不只是一段事后解释。

## 14. 2026-07-31：#446 `449fb75` final-head review

### 14.1 最新 review 与 PR 状态

`2026-07-31 09:31 CST` 从上次 `2026-07-30 18:00 CST` 做只读 freshness scan，decision-relevant 更新只有 #446。作者在旧 head `2eefda6` 后追加 10 个 commits，current exact head 为 `449fb752fdded85fffd81b96d4554972f0eb8260`，base 仍是已合入 #448 的 `upstream/main@0704bb9`；PR 现为 35 files、`+814/-410`、open、non-draft、structurally mergeable。

最新 human review 仍是 `@acsoto` 在 `2026-07-30 21:04 CST` 针对 `fd0507f` 提交的 4 个 inline comments：自制 migration bootstrap 没创建 shadow pools、recreate/delete flow 会丢数据、upgrade E2E 缺少 post-upgrade assertions、文档 helper URL 仍为 404。此后作者又追加 6 个 commits，但截至本次扫描，没有 maintainer 对 `449fb75` 提交新的 review、`/lgtm` 或 `/approve`。

GitHub 当前把 11 个 review threads 中 10 个标记为 resolved，只留下我们较早的 production scheme thread active；但 thread state 不是代码证据。`449fb75` 的 11 个实际 Actions checks 全部通过，包括两个 E2E matrix job；DCO 单独失败，原因是首个 commit 有 `Signed-off-by`，后续 10 个 commits 都没有 signoff。Tide 仍等待 `lgtm` 和 `approved` labels。

### 14.2 上一轮 comments 的代码闭环

| Review concern | `449fb75` 状态 | 证据 |
| --- | --- | --- |
| Production manager 没注册 v1beta1 scheme/watch | 已修 | `main.go` 注册 core/extension beta scheme，并 `For(&v1beta1.Sandbox{})`；binary-level scheme test 通过 |
| Scheme test 使用错误 group strings | 已修 | 改用 exported `SchemeGroupVersion.WithKind(...)`；本机 `go test ./cmd/workload-manager -count=1` 通过 |
| Empty name validation regression | 已修 | 恢复 `CreateSandboxRequest.Validate()` 并新增 missing-name case |
| `volumeClaimTemplates` test 不经过 API Server | 已修 | test 移到 E2E，执行真实 Create/Update，并要求 `apierrors.IsInvalid`；exact-head CodeInterpreter E2E 日志显示该 test 通过 |
| 字典序版本比较 | 已修 current target | 改为 `v0.4.*` regex，其他版本走 combined manifest；不再把 `v0.10.0` 判成旧版 |
| Personal PATH in codegen | 已修原问题 | 删除个人 Windows paths；codegen workflow 通过，但 PR 同时扩大为一套新的 generator install/source-patch 流程 |
| 自制 migration 会漏建 pool / 删除 claim | 已修 | 删除自制脚本，改用 upstream v0.5.3 tagged `helm/files/migrate.sh` 的 bootstrap/migrate phases |
| Upgrade E2E 没有迁移后断言 | 部分修复 | CI 真实执行 bootstrap/migrate，确认 seeded cold claim 存活和 shadow pool 存在；fresh v1beta1 warm-pool adoption/delete/refill test 也通过，但没有覆盖 active v1alpha1 claim 的 binding identity |
| 两份文档使用不存在的 release asset | 仅修一份 | root guide 改为 tagged raw URL；Docusaurus mirror 仍请求不存在的 `releases/download/v0.5.3/migrate.sh` |

### 14.3 Current final-head findings

#### [P1] 没有测试 #438 点名的 active/warm SandboxClaim 升级风险

`test/e2e/run_e2e.sh:345-356` 只创建一个没有 `status.sandbox.name`、没有既有 Sandbox/Pod、也没有 binding identity 的 v1alpha1 SandboxClaim，源码注释也明确称它是 cold-start fixture。迁移后 shell 只检查 claim 仍存在和 shadow pool 已创建。

这不能覆盖 #438 等待 v0.5.2 的核心原因。上游 agent-sandbox #1124 修的是 warm-started claim 在 controller upgrade 时因 optimistic-lock/transient lookup error 丢失 bound sandbox status 并错误 cold-restart；其 migration test 会构造已绑定的 warm claim，并验证升级后仍绑定到原 sandbox。#446 后续运行的 `TestCodeInterpreterWarmPool` 虽然证明升级后的 fresh v1beta1 claim 可以 adoption/delete/refill，但它创建的是新对象，无法证明旧 v1alpha1 active claim 的 `status.sandbox.name` 和 sandbox identity 在 conversion/controller restart 后保留。

修正测试应至少在 v0.4.6 阶段创建真实 Sandbox + SandboxClaim，补齐 owner references/status binding，记录原 Sandbox name/UID；升级后断言同一 claim 仍指向同一 Sandbox，而不是只断言非空或资源存在。若要完整关闭 #438，再把该旧 claim 接入 deletion/refill lifecycle，或者明确拆开“旧 binding preservation”和“新 beta lifecycle”两组因果断言。

> 分析：这里不是要求复制 upstream 全部 migration suite，而是要求测试命中本次 release prerequisite 的故障状态。cold claim 验证 shadow bootstrap，warm/active claim 验证 status/binding preservation；两者不是可互换样本。

#### [P1] agent-sandbox upgrade 无关地关闭了 Router 默认 h2c

`pkg/router/server.go:185-199` 把原来始终使用的 `h2c.NewHandler` 改成 `EnableH2C` 条件分支，而 `cmd/router/main.go` 新 flag 默认值是 `false`。Helm `agentcube-router` Deployment 没有传 `--enable-h2c`，`values.yaml` 也没有相应设置，因此标准安装升级后会静默从默认 h2c 变成 HTTP/1 handler。

Router h2c 是从历史 PR `c65ef24` 引入并在 `docs/design/router-proposal.md` 明确描述为 default-enabled 的既有能力；本 PR 的 #438 / agent-sandbox API migration 不需要改变该 contract，也没有 h2c compatibility test。使用 HTTP/2 cleartext prior knowledge 的现有客户端不会自动得到原行为。应从 #446 删除 `cmd/router/main.go`、`pkg/router/config.go`、`pkg/router/server.go` 的这组变化；如果确实要改变安全默认值，应单开 PR，说明 threat model、backward compatibility、Helm exposure 和协议测试。

#### [P1] Docusaurus 镜像升级指南仍在第 2 步返回 404

`docs/agentcube/docs/getting-started.md:46` 仍写 `https://github.com/kubernetes-sigs/agent-sandbox/releases/download/v0.5.3/migrate.sh`。v0.5.3 release 只有 `sandbox.yaml`、`extensions.yaml`、`sandbox-with-extensions.yaml` 三个 assets；实测该 helper URL 返回 404。root `docs/getting-started.md` 已使用可用的 tagged raw URL，因此只需同步同一 URL 和 `-O migrate.sh` 到 Docusaurus mirror。当前 resolved thread 不能覆盖这个仍可复现的用户阻塞。

### 14.4 验证与当前结论

本轮运行 `final_head_review.py` 对齐 `upstream/main@0704bb9...449fb75` 和 #438 acceptance contract。ledger 识别 35 个 changed files，证明 CI 没覆盖新增的 `./cmd/workload-manager` test package，并自动补跑成功；新增外部 URL 检查同时得到 tagged raw migration helper `200`、combined manifest `200`、Docusaurus release-asset helper `404`。

本机额外验证：

- `go test ./cmd/workload-manager -count=1`：通过；
- `go test ./pkg/router ./pkg/workloadmanager ./pkg/picod -count=1`：通过；
- exact-head CI `codeinterpreter-e2e-test` 日志：bootstrap/migrate 均成功，cold claim/shadow pool assertions、`TestCodeInterpreterWarmPool`、API immutability test 均实际执行并通过；
- `git diff --check upstream/main...HEAD`：失败，两个 docs 行和 `run_e2e.sh` 多处 trailing whitespace；属于机械清理项，不替代上述 contract findings；
- 本机没有 current Kubernetes context，因此没有重复运行完整 E2E；使用 exact-head 官方 CI 日志作为 live-cluster evidence。

当前判断为 **NOT READY**：旧 comments 的主要实现缺陷已大幅收敛，但 active claim acceptance、Router h2c regression、镜像文档 404 和 DCO 仍阻塞进入 approval。

### 14.5 Final-head review 发布记录

用户确认 exact target、head、review body 和三条 inline comment 后，已于 `2026-07-31 10:15 CST` 对 `449fb75` 发布 [COMMENT review](https://github.com/volcano-sh/agentcube/pull/446#pullrequestreview-4824881370)，没有使用 `REQUEST_CHANGES`、`/lgtm`、Prow command 或 maintainer mention：

- [active/warm v1alpha1 binding fixture](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3687580741)，锚点 `test/e2e/run_e2e.sh:345`；
- [Router h2c scope regression](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3687580746)，锚点 `pkg/router/server.go:189`；
- [Docusaurus migration helper 404](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3687580749)，锚点 `docs/agentcube/docs/getting-started.md:46`。

发布后通过 REST 与 GraphQL 复核：review state 为 `COMMENTED`，commit id 仍为 `449fb75`；三个 threads 均 `isOutdated=false`、`isResolved=false`，行号分别为 345、189、46。下一步只在作者 push 新 head 后重新验证实现和 tests，不根据 thread resolve 状态直接判定修复。

## 15. 为什么 `@acsoto` 又比我们找到更多问题

### 15.1 先按 reviewed head 校准数量

我们在 `2026-07-31 10:15 CST` review 的是 `449fb75`。作者随后提交 `2592301` 到 `1826e16`；`@acsoto` 在 `2026-07-31 15:50-17:16 CST` 发布 6 条评论。因此不能把 6 条全部计为旧 review 的漏检：

| 评论 | `449fb75` 是否已有 | 判断 |
| --- | --- | --- |
| root guide 的 tagged `deploy/sandbox-with-extensions.yaml` 404 | 否 | `2592301` 把原本可用的 release asset URL 改坏，是 review 后的新回归 |
| backup 漏 SandboxTemplate / SandboxWarmPool | 是 | 同-head 真实漏检 |
| `Resource()` 从 GVR 改成 GR，破坏外部 client-go caller | 是 | 同-head 真实漏检 |
| Kubernetes libraries v0.36.2，code-generator 仍 pin v0.35.4 | 是 | 同-head 真实漏检 |
| 新 bound fixture 没 ownerRef/template/pool/Pod UID，也没证明新 controller reconcile | 否 | 作者按我们 active-claim finding 新增 fixture 后的 follow-up；是同一 finding 的实现验收，不是旧 head 新 bug |
| fixture 补齐对象图和 UID 后仍没等待 Claim Ready | 否 | 后续 fixture 的第二轮验收；继续证明同一 warm-start finding 尚未闭环 |

按当前已确认集合，`449fb75` 的公开 final-head findings 至少有 6 个：我们找到 3 个，漏 3 个，lower-bound finding recall 是 `3/6 = 50%`；三条均有效，所以 precision 仍是 `3/3`。这个分母仍可能不完整，不能把 50% 当总体能力定值。

### 15.2 真正根因是 finding ledger 丢失

三个漏检都不是第一次见。本文审 #442 时已经明确写过：operator backup 缺两个会被 migration 处理的 kind，`Resource()` exported return type 是 source-breaking，以及 Kubernetes v0.36.2 与 code-generator v0.35.4 存在 cross-minor skew。replacement #446 继承了同样代码，但 final-head reset 只重建了 #438 acceptance 与七项当轮 gold，没有把 #442 未关闭的本地 finding ledger 合并进来。

因此发生了一个反向错误：旧 PR 的 duplicate/resolved 语境被记住了，旧 PR 的未修技术结论却没有被带到 replacement PR。`final_head_review.py` 虽然列出了两个 docs 文件和 `register.go`，但 row 没有 machine-readable `fixed/present/not-applicable` closure；仓内编译通过也不能证明 exported Go API 对仓外 caller 兼容。

AutoHarness 的 Context layer 首先漏掉 predecessor ledger，Verification layer 又直接信任 trace 中的 `cover-all-known-findings=true`，Governance layer 最后允许在 3 个 blocker 后结束。原 Day57 七项 gold 因此不是“全部已知 finding”；加入这三项后，那个 post-hoc challenger 的 corrected lower-bound recall 是 `7/10 = 70%`，不是 100%。

### 15.3 可复用修正

review skill 现已要求 replacement/superseding PR 使用稳定 finding ID 合并 `parent acceptance + predecessor PR/local report + current-head findings`，逐项标记 `fixed/present/not-applicable/duplicate-on-current-pr`。AutoHarness 也要求 versioned gold provenance，并用 deterministic set comparison 验证 `cover-all-known-findings`，不再接受轨迹自报 boolean。

当前 PR 已推进到 `1826e16`。`275f2e4` 从源码上修复了 manifest URL、backup kinds 和 `Resource()` GVR signature；后续 commits 继续扩充 warm fixture，但 code-generator 仍为 v0.35.4，且最新 successful E2E 还没有证明 migrated Claim 达到 Ready。作者仍在高频补丁阶段，下一轮必须等 head 稳定后重新执行完整 carry-forward ledger，不能根据 commit message 或 resolved thread 判定完成。本节没有发布 upstream 内容。

## 16. `e577a5e` squash head 与 lineage closure

`2026-07-31 17:44 CST` 刷新确认作者已把 `1826e16` squash 为单个 signed commit `e577a5e`。两个 commits 的 tree OID 同为 `a91ae18`，所以旧 head 的 source/runtime 判断仍适用于当前 tree；DCO 与全部 executable checks 已通过，Tide 只等待 `lgtm/approved`。

全 lineage 复盘不再按评论条数计 finding。existing-claim fixture 的 object graph、UID、Ready 三轮反馈合并为同一个 #438 lifecycle invariant；review 后引入的 bad manifest URL 单独记为 new-head regression。最终技术 ledger 有 15 个 stable IDs，current closure 是 13 fixed / 2 present：

- existing bound claim 仍未被等待到 Ready，也没有证明 migrated-claim deletion/refill；
- Kubernetes libraries 为 v0.36.2，code-generator 仍为 v0.35.4。

详细 finding provenance、review recall、skill 修改与 dataset leakage 边界见 [Day57 Section 9](day57-agent-autoharness-trajectory-evaluation.md#9-446-全-lineage-复盘与-executable-skill-修正)。本轮仍未向 upstream 发布任何内容。

## 17. `a0f4882` exact-head reset 与新增回归

`2026-07-31 21:51 CST` 再次做只读 freshness scan。#446 仍是 open、non-draft、structurally mergeable，current exact head 为 `a0f48828b642f7005da46324d1dfaa528033b8b7`，base 为 `upstream/main@0704bb96502af32f2bd90d47f1e11b4c8099959e`。PR 现为单个 signed commit、35 files、`+1049/-455`；12 个 executable/DCO checks 全部通过，Tide 只等待 `lgtm/approved`。从上一快照开始没有新增 human review，decision-relevant change 只有作者把 `e577a5e` 推进到当前 head。

`e577a5e..a0f4882` 只改 6 个文件：`hack/update-codegen.sh` 把 code-generator 从 v0.35.4 对齐到 v0.36.2，并重新生成 5 个 client/informer 文件。因此旧 `F16-kubernetes-codegen-version` 已关闭；clean detached worktree 中 `make gen-check` 通过且没有 drift。这个小 delta 没有修改 upgrade fixture、鉴权创建链、AgentRuntime CRD 或两份升级文档，所以这些区域必须按完整 final tree 而不是按最后 6-file delta 复核。

> 注释：绿色 Codegen Check 只证明默认 CI 环境可以重复生成当前输出。它不自动证明所有合法 Go 环境变量组合都使用同一套 generator，也不覆盖前面 hand-written 代码的 runtime contract。

### 17.1 `[P1]` authenticated owner 没有进入 Store

base 的 `pkg/workloadmanager/handlers.go` 在 builder 返回后执行：

```go
if ownerID != "" {
    sandboxEntry.OwnerID = ownerID
}
```

current head 删除了这段赋值。`resolveSandboxOwnerID` 仍在 `handlers.go:173` 得到 subject，并把它传给两个 builder；但 builder 只把 owner 写到 Sandbox / SandboxClaim annotation 与 label，`workload_builder.go:302-307` 和 `347-352` 返回的 `sandboxEntry` 都没有 `OwnerID`。随后 placeholder、最终 Store record 和 create response 都从这个空 entry 复制 owner。

Router 的 existing-session RLAC 不读 Kubernetes annotation，而在 `pkg/router/handlers.go:107-116` 读取 Store record 并 fail closed。可达结果是：非管理员第一次不带 session ID 创建成功，拿到 session ID 后由同一个 subject 再次请求，却确定性收到 `403 sandbox has no owner record`。AgentRuntime、cold CodeInterpreter 和 warm-pool claim 三条创建路径都经过这段代码。

隔离 exact-head test 用真实 create handler 注入 `user-123` 并捕获 Store entry，结果为 `expected "user-123", actual ""`；只恢复上述 assignment 后，同一个 test 通过。现有测试只检查 Kubernetes metadata，或直接向 helper 注入一个已经带 OwnerID 的 entry；E2E 默认 `KEYCLOAK_ENABLED=false`，没有覆盖 non-admin create -> reuse。这是当前 public thread 中没有重复项的新 finding。

> 分析：这里不是 annotation 少写一次，而是 authorization decision record 丢失。只给 builder metadata 增加断言会继续 false green；修复测试必须捕获 Store write，并让同一 non-admin subject 复用返回的 session。

### 17.2 `[P1]` existing bound claim lifecycle 仍是 false green

`test/e2e/run_e2e.sh` 手工把 `upgrade-bound-claim` 绑定到 standalone `upgrade-bound-sandbox`，却没有构造真实 warm pool producer。v0.5.3 conversion 会从 sandbox name 推导 `warmPoolRef.name=upgrade-bound`，而 fixture 没有这个 pool；另行检查的 `shadow-pool-e2e-upgrade-template` 不是该 bound claim 的来源。

升级后脚本固定 `sleep 10`，只验证 Claim 仍存在、Sandbox/Pod UID 不变、status binding 未空以及另一个 shadow pool 存在。它没有要求 migrated Claim 达到 `Ready`，也没有删除该 Claim、验证原 Sandbox/Pod 被 GC，或证明 source pool refill。因此 controller 持续 `WarmPoolNotFound` 时测试仍可打印 “lifecycle verified”。

这仍是 `F09-existing-claim-upgrade-lifecycle`，不是新 defect ID；#438 的 adoption/deletion/refill contract 和 #446 既有 [discussion r3689367077](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3689367077) 已经公开指出它。不要重复发布相同评论。正确 fixture 应由真实 v0.4.6 warm pool 生产 bound Sandbox，再验证 upgrade 后 Ready、同一 identity、delete/GC 和 refill。

### 17.3 `[P2]` non-empty `GOBIN` 会让 codegen 删除输出后失败

`hack/update-codegen.sh:58-83` 固定从 `$(go env GOPATH)/bin` 执行 generator，但 `go install` 在 `GOBIN` 非空时会把二进制安装到 `GOBIN`。脚本随后先删除整个 `client-go`，再尝试执行不存在的 `GOPATH/bin/client-gen`。

隔离复现为 `GOPATH=/tmp/agentcube-pr446-gopath`、`GOBIN=/tmp/agentcube-pr446-gobin` 运行 `bash hack/update-codegen.sh`。三个 v0.36.2 binaries 都正确落在 GOBIN，脚本却以 exit 127 报 `.../gopath/bin/client-gen: No such file or directory`，并把 25 个 tracked generated files 留在 deleted 状态。若 GOPATH/bin 恰有旧 binary，则会更隐蔽地运行错误版本。该问题影响 `make gen-client`、`make gen-all` 和 `make gen-check`；当前 CI 没设置 GOBIN。

最小修正是以 `go env GOBIN` 为首选、空时 fallback GOPATH/bin，或给三项 install 显式设置隔离 GOBIN 并从那里执行；应在工具路径/版本验证完成后才替换 generated tree。这与旧 Windows personal PATH 评论相关，但触发与后果不同，不是 duplicate。

### 17.4 `[P2]` embedded `PodSpec` 升级移除了 `workloadRef`

base 使用 `k8s.io/api v0.35.4`，其 `corev1.PodSpec` 含 `workloadRef`；AgentRuntime CRD 因嵌入 `corev1.PodSpec` 也公开服务该字段。current v0.36.2 把 protobuf tag 42 tombstone，并用 shape 不同的 `schedulingGroup` 替代。生成后的 current CRD 删除 `workloadRef`、增加 `schedulingGroup`。

focused JSON counterexample 把旧 payload `{"workloadRef":{"name":"batch-a"}}` 解码到 current typed `PodSpec`，round trip 只剩 containers，`workloadRef` 被静默丢弃。`buildSandboxByAgentRuntime` 又从 typed informer 对象 DeepCopy 该 PodSpec 到新 Sandbox，所以已有 AgentRuntime 的 workload-aware scheduling intent 不会到达新 runtime object；用户更新旧 CR 时也受新 schema 约束。PR 没有 migration note、versioned conversion 或 compatibility test。

> 分析：这是 dependency-generated API surface，不只是 `go.mod` 内部实现变化。影响范围限定在实际使用 Kubernetes GenericWorkload / `workloadRef` 的 AgentRuntime；没有该字段的对象不受影响。修复需明确支持边界，并在保留旧 intent 或正式 breaking migration 之间做显式选择。

### 17.5 `[P2]` mandatory upgrade docs 没验证 conversion webhook

两份 getting-started guide 都在 apply v0.5.3 后只执行 controller Deployment `rollout status`，随后立即运行 `./migrate.sh --phase=migrate`。rollout 只能证明 Pod availability，不能证明 conversion webhook Service/endpoints 已传播且 API Server 可调用。

dependency v0.5.3 的 `docs/api-migration-guide.md` 明确要求 rollout 后循环执行 `kubectl get sandboxwarmpools.extensions.agents.x-k8s.io -A`，本 PR 的 E2E 在 `run_e2e.sh:423-437` 也加入同一 probe，理由正是 kube-proxy endpoint sync。mandatory operator docs 应带 bounded timeout 地保留这一步；否则 storage rewrite 可能在 webhook 短暂不可用时中途失败。

### 17.6 CI discovery 与其余 residual risk

新增 `cmd/workload-manager/main_test.go` 当前直接执行通过，但 GitHub coverage 只运行 `go test -race ... ./pkg/...`，E2E 只运行 `go test ./test/e2e/...`，Docker build 不执行 `_test.go`。因此全部 checks 绿色仍不保护 scheme registration；旧 head 已经出现过 green checks + direct package failure。`F21-scheme-test-ci-discovery` 保持 present，至少应在 CI 加 `go test ./cmd/workload-manager`，或统一执行全部非 live Go packages。

另有两个不提升为独立 defect 的 residual risk：

- `UserK8sClient.CreateSandbox` / `CreateSandboxClaim` 的 exported parameter 从 dependency v1alpha1 变为 v1beta1，静态上会破坏仓外 Go caller；但 GitHub code search 没找到仓外 import，且 `pkg/workloadmanager` 没有明确 supported SDK contract，所以只保留为兼容性假设。
- garbage-collection fake test 对 DELETE 返回 NotFound，只断言 Store 删除；TTL E2E 在 session 未消失时也不会失败。它们不能证明真实 claim GVR/GC，但本轮没有从 production source 建立新的 GC bug，风险继续由 F09 live lifecycle E2E 关闭。

### 17.7 验证与 closure

exact `a0f4882` 的本地结果：

- `go test ./cmd/workload-manager ./pkg/workloadmanager ./pkg/router ./pkg/picod ./client-go/... -count=1`：通过；
- `go test -race ./pkg/workloadmanager -count=1`：通过；
- `go test ./test/e2e -run '^$' -count=1`：编译通过，但没有执行 live tests；
- `bash -n test/e2e/run_e2e.sh`：通过；
- `make gen-check`：clean worktree 通过且 zero diff；
- non-empty GOBIN codegen：exit 127，且 `client-go` 被删除；
- authenticated handler owner persistence：exact head red，恢复单项 assignment 后 green；
- old `workloadRef` typed decode：exact head red，round trip 丢字段；
- `git diff --check upstream/main...HEAD`：两份 docs 与 `run_e2e.sh` 仍有 trailing whitespace；这是机械清理，不作为 blocker。

lineage ledger 已从 v3 的 15 项扩为 v4 的 20 项，current closure 是 **14 fixed / 6 present / 0 unclassified**。present IDs 为 `F09`、`F17`、`F18`、`F19`、`F20`、`F21`；结构 closure complete，但 merge readiness 仍 blocked。Docusaurus build 未运行，因为 exact worktree 没有 `node_modules`；本轮没有新建 live cluster，current Actions 只作为现有 runtime evidence，不能替代缺失场景。

### 17.8 Final-head file rationale closure

| 文件组 | 修改理由与 current-head 结论 | 证据 / 风险映射 |
| --- | --- | --- |
| `cmd/workload-manager/main.go`、`main_test.go` | production manager 注册 core/extension v1beta1 types，并增加 scheme regression | 直接 package test 通过；CI discovery 缺口记为 `F21` |
| `pkg/workloadmanager/*.go` 与相邻 tests | 把 Sandbox、Claim、WarmPool、condition、GVR 和 informer/controller path 从 alpha 迁到 beta，并适配 pointer/OperatingMode/WarmPoolRef | focused unit/race 通过；owner Store regression 为 `F17`，exported beta signatures 保留为 residual assumption |
| `go.mod`、`go.sum` | agent-sandbox v0.5.3 要求 Kubernetes/controller-runtime dependency family 升级 | module verify/tidy 与 compile 通过；embedded PodSpec API break 为 `F19` |
| `pkg/apis/runtime/v1alpha1/doc.go`、`groupversion_info.go` | 把 generator package markers 放到标准 `doc.go`，并抑制新 dependency 的 `scheme.Builder` deprecation | `make gen-check` 通过；`Resource()` source contract 已由 `F15` closure 证明保留 |
| `hack/update-codegen.sh`、`client-go/**`、AgentRuntime CRD | 对齐 code-generator v0.36.2，并重新生成 client/informer/schema | 默认 clean regeneration 通过；GOBIN 失败为 `F18`，CRD schema drift为 `F19` |
| 两份 getting-started guide | 安装 v0.5.3，并记录 v0.4.6 backup/bootstrap/apply/migrate 顺序 | tagged URLs 均为 200；webhook readiness 缺口为 `F20` |
| `test/e2e/e2e_test.go`、`run_e2e.sh` | 建立真实 alpha -> beta setup、API immutability 与 post-upgrade assertions | current Actions 运行；bound Claim fixture 的 producer/Ready/delete/refill 缺口为 `F09` |
| `pkg/router/server.go` | 新 `x/net` 把 h2c 标为 deprecated，PR 用 scoped nolint 保留既有 HTTP/2 cleartext behavior | source 与 router tests 通过；此前 h2c scope regression 已由 `F12` closure 关闭 |
| `pkg/picod/execute_test.go`、`files_test.go` | Windows 下跳过需要 symlink privilege 的 tests | 不改变 production behavior，但与 dependency upgrade 无直接关系；属于可拆出的低风险 scope noise |
| `integrations/code-interpreter-mcp/pyproject.toml` | 只删除文件末尾 newline | 无语义、无测试价值；应从 diff 移除，但不提升为 correctness finding |

> 分析：generated files 不需要逐行重新发明 rationale，但必须回溯到 generator/source 并通过 clean regeneration。无语义 newline 与独立 Windows test skip 也不能因 PR 很大而自动获得 scope 正当性；这里明确记录它们，但不让机械清理淹没 runtime blockers。

本节没有发布 upstream review/comment、没有 resolve thread、没有 `/lgtm`、Prow command、reviewer request 或 maintainer mention。新增 findings 若要公开，必须先按 current head 做 duplicate/anchor guard，并让用户确认 exact target/body/event。

## 18. 2026-08-03：`353f1df` latest-head closure

### 18.1 Head、公开线程与 CI

本轮只读扫描锁定 PR #446 exact head `353f1dfa60759e5f2e0bbbac239adb93f1ae2650`，base 仍为 `upstream/main@0704bb96502af32f2bd90d47f1e11b4c8099959e`。相对我们已发布四条 review findings 的 `a0f4882`，作者先提交 `a524029` / `c46f3d9` 修复主体，再追加 `da4140d` 与 `353f1df` 处理 migrated Claim Ready wait。PR 当前 36 files、`+1140/-468`。

全部 executable Actions checks 通过，包括 build、lint、coverage、Codegen、`e2e-test` 与 `codeinterpreter-e2e-test`。DCO 单独失败：`a524029`、`c46f3d9` 有 `Signed-off-by`，新增的 `da4140d`、`353f1df` 没有；Tide 还等待 `lgtm` 与 `approved`。没有新的 maintainer review 或 accepted-risk 决定。

### 18.2 已真实关闭

Ready wait 已真实关闭旧 subcondition。exact-head CI 在 `17:07:32Z` 先显示 `upgrade-bound-claim` 的 `READY` 为空，随后于 `17:07:42Z` 出现 `condition met`，源码才继续比较 Sandbox UID、Pod UID 和 binding。这不是固定 sleep 或立即读取形成的 false green。

此前公开的两项实现缺陷也已修：

- direct 与 warm-pool builders 都把认证主体写入返回的 Store entry `OwnerID`，相邻测试断言该值；
- codegen 脚本读取 `GOBIN`，为空才回退 `GOPATH/bin`，先验证三个 binaries 再删除 `client-go`；Kubernetes libraries 与 code-generator 同为 `v0.36.2`。

因此 v4 ledger 的 `F17-auth-owner-store-persistence` 与 `F18-codegen-gobin-install-path` 可从 present 变为 fixed。线程是否仍 unresolved 不影响代码 closure。

### 18.3 五项仍 present

| Severity | Stable ID | Current-head evidence | 修正方向 |
| --- | --- | --- | --- |
| P1 | `F09-existing-claim-upgrade-lifecycle` | `run_e2e.sh:345-397` 没有创建原始 SandboxWarmPool；`:465-507` 只验证 Ready、UID、binding 和 `DESIRED=0` shadow pool 存在。没有删除同一 migrated Claim，也没有验证其 Sandbox/Pod GC 与同一 pool refill；后面的 warm-pool test 使用 fresh v1beta1 lineage | 在 v0.4.6 阶段创建真实 pool/bound Sandbox；迁移后删除同一 Claim，等待原 UIDs 消失，并证明同一 pool 以新 UID 补回 desired capacity |
| P2 | `F19-embedded-podspec-workloadref` | base CRD 的 `workloadRef{name,podGroup,podGroupReplicaKey}` 被 shape 不同的 `schedulingGroup{podGroupName}` 替代；root guide 只写一句 transition，mirror 缺失；所谓 compatibility test 只构造新 PodSpec 并断言 image | 由 maintainer 明确选择 preserve/migrate 或 accepted break；两份文档与旧 serialized object test 对齐这个决定 |
| P2 | `F20-conversion-webhook-readiness-docs` | 两份 guide 现在加了 probe，但都是无 timeout、无诊断退出的 `until ...; sleep 2`；webhook 永久不可用时 mandatory upgrade 永久挂起 | 使用 bounded retry 或 `timeout`，耗尽后打印诊断并非零退出；两份 copy 保持一致 |
| P2 | `F21-scheme-test-ci-discovery` | exact-head `go test ./cmd/workload-manager` 通过，但 coverage 只跑 `./pkg/...`，E2E 只跑 `./test/e2e/...`；新增 manager scheme regression 仍未被任何 CI command 执行 | 在现有 Go test workflow 纳入 `./cmd/workload-manager`，或统一运行全部非 live Go packages |
| P2 | `F22-e2e-webhook-wait-fail-open` | `run_e2e.sh:438-449` 第 30 次 webhook probe 失败只打印日志，`:451-452` 仍调用 mutating migration helper | exhaustion branch 明确 `exit 1`；补 probe 永远失败时 migration marker 不可达的 shell regression |

> 分析：生命周期 acceptance 必须沿同一对象 lineage。`旧 Claim -> Ready/UID 保留` 与 `新 Claim -> delete/refill` 分别通过，不能拼成 `旧 Claim -> migrate -> delete -> GC -> refill` 的完整证据。

`F22` 是新的 current-head finding，不是 docs thread `r3691344808` 的重复。旧 thread 把 E2E probe 当成文档应复制的参考，只要求两份 operator guide bounded/fail on timeout；本轮才验证 E2E probe 自身会 fall through。最小 shell counterexample 把 `kubectl` 固定为失败、`sleep` 置空，30 次失败后仍输出 `MIGRATE_REACHED` 并 exit 0。上游 helper 会按四类 CRD 继续处理，累计 failure 后才返回，因此等待边界应在 mutation 前 fail closed。

> 注释：`workloadRef` 不是可机械替换的字段名。Kubernetes v0.35.4 的类型有 `Name`、`PodGroup`、`PodGroupReplicaKey`，v0.36.2 的 `PodSchedulingGroup` 只有 `PodGroupName *string`；“upstream 删除了旧字段”解释了来源，但没有定义 AgentCube 对现有 `v1alpha1` AgentRuntime 的兼容承诺。

### 18.4 验证、ledger 与发布边界

本地 exact-head 验证：

```text
bash -n test/e2e/run_e2e.sh hack/update-codegen.sh             PASS
go test ./cmd/workload-manager ./pkg/workloadmanager \
  ./pkg/picod ./pkg/router -count=1                            PASS
go test ./test/e2e -run '^$' -count=1                          PASS
final_head_review.py --run-go-tests --check-urls               BLOCKED, expected
```

v5 ledger 有 21 个 stable IDs，exact-head closure 为 `16 fixed / 5 present / 0 unclassified`。harness 判定 changed-test execution passed、carry-forward closure complete、finding readiness blocked，并以 exit 1 结束。三个 literal upgrade URLs 返回 200；含 shell variable 的 URL保留为 unresolved-variable。`git diff --check` 另发现 docs 与 E2E shell 多处 trailing whitespace，只记为非阻断清理。

本轮没有本地 live cluster，因此没有重复执行完整 E2E；使用 exact-head upstream 两个 E2E job 的实际日志作为 cluster evidence。没有向 #446 发布新 review/comment、reply、resolve、Prow command、reviewer request 或 maintainer mention。

### 18.5 Scope gate 与 review 发布

发布前重新区分了两条未公开 finding 的 ownership。`F22-e2e-webhook-wait-fail-open` 位于本 PR 新增的 upgrade E2E migration path，最小修复仅是在第 30 次 probe 失败并打印诊断后返回非零，属于本 PR correctness scope。`F21-scheme-test-ci-discovery` 虽由本 PR 暴露，但修正需要修改仓库级 workflow；本轮不把它作为 #446 的 inline request，继续留在 ledger 作为独立 CI 后续。

> 分析：scope gate 不能按“问题是在 review 中发现的”判断，而应看责任和依赖方向。本 PR 新增失败分支的 fail-closed 修复应留在本 PR；通用 test discovery policy 应从 `upstream/main` 独立处理，避免 dependency upgrade 继续吸收 CI infrastructure 变化。

用户确认 exact target/body/event 后，发布前 fail-closed 核对 #446 仍为 open、non-draft、head `353f1dfa60759e5f2e0bbbac239adb93f1ae2650`，且 `test/e2e/run_e2e.sh` 没有同义新线程。`2026-08-03 10:35 CST` 提交 1 个 [`COMMENT` review `4840435164`](https://github.com/volcano-sh/agentcube/pull/446#pullrequestreview-4840435164)，其中只有 1 条 [inline comment `3701010868`](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3701010868)，锚定 `test/e2e/run_e2e.sh:452`，只请求 timeout diagnostics 后 `exit` non-zero。API 回读确认 review/comment 均绑定 exact head，path、line、正文和数量与确认稿一致；没有发布 `REQUEST_CHANGES`、`/lgtm`、Prow command、maintainer mention 或 resolve 操作。

### 18.6 `d7333cc` 增量 closure

作者先在 inline thread 回复 `ok, doing..`，随后于 `2026-08-03 11:19 CST` 回复 [`done.`](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3701126915)，并把 #446 推进到 exact head `d7333cc2fcc78ff923e45a9e4ed5d9e714359baa`。相对评论时的 `353f1df`，新增 diff 只有 `test/e2e/run_e2e.sh` 一行：第 30 次 webhook probe 失败并打印 controller logs 后执行 `exit 1`，其后的 `/tmp/migrate.sh --phase=migrate` 不再可达。

增量验证同时覆盖两个循环边界：probe 连续 30 次失败时返回码为 1 且输出不含 `MIGRATE_REACHED`；第 30 次刚好成功时返回码为 0 且 migration marker 可达。exact-head shell syntax check、`git diff --check` 均通过，GitHub build、lint、coverage、Codegen、Python checks、两个 E2E 等全部 executable checks 通过。

> 分析：作者的 `done.` 对 `F22-e2e-webhook-wait-fail-open` 是准确的 closure 信号，但它只回答这条 inline finding。它不能替代对整个 PR 的 readiness 判断，也不能自动关闭其他公开线程。

本轮没有重跑 v5 全量 ledger，因此只记录 `F22` 从 present 到 fixed 的增量结论。migrated Claim deletion/GC/refill、`workloadRef` 兼容边界、两份文档的无界 webhook wait 和仓库级 scheme-test CI discovery 不因这一行改动而改变。DCO 仍为 `ACTION_REQUIRED`：检查明确列出 `da4140d` 与 `353f1df` 两个缺少 `Signed-off-by` 的 commits；Tide 仍等待合并标签。本轮没有发布 reply、resolve、review、Prow command 或 maintainer mention。

### 18.7 `/lgtm` go/no-go

`2026-08-03 11:48 CST` 再次刷新 #446 后，head 仍为 `d7333cc`，`upstream/main` 仍为 PR base `0704bb9`，全部 executable checks 通过。当前结论是 **NO `/lgtm`**，不是因为刚修的 timeout finding，而是至少还有两个独立硬门槛：DCO 明确失败；Issue #438 要求同一 existing active SandboxClaim 在升级后继续完成 deletion、Sandbox/Pod GC 和 source-pool refill，当前脚本只等待 Ready 并校验 UID/binding，没有删除 `upgrade-bound-claim` 或验证 refill。

`workloadRef` 兼容边界和两份文档的无界 webhook probe 也仍存在。相关 GitHub threads 被标记 resolved，但没有 `OWNER` / `MEMBER` / `COLLABORATOR` 给出 accepted-risk 决定；作者解释“上游删除字段”和回复 `ok` 不能代替项目兼容承诺。仓库级 scheme-test CI discovery 继续作为独立 follow-up，不加入本次 PR 的最小阻断集合。

> 分析：`/lgtm` 表示 reviewer 认为当前 diff 在既定 scope 内已经可合并；它不是“我最后一条评论修了”的确认按钮。绿色 CI、作者 `done.` 和 resolved thread 都是输入信号，不能覆盖仍未满足的 parent-Issue acceptance 或 DCO gate。

本轮只读核对，没有发布 `/lgtm`、reply、resolve、review、Prow command 或 maintainer mention。

### 18.8 `2026-08-05` reviewer-request 全量复核

作者于 `2026-08-03 13:23:44 CST` 重新请求 `ranxi2001` review；GitHub timeline event 与 PR `updatedAt` 精确同秒。此后没有新 commit、issue comment、review comment、submitted review、label 或 force-push，因此本轮复核对象仍是 exact head `d7333cc2fcc78ff923e45a9e4ed5d9e714359baa`。这次 activity 只是 reviewer request，不是新的代码修复或 maintainer decision。

`upstream/main` 已因 #452 从 PR merge-base `0704bb9` 前进到 `939abb5`。该 merge 只把 Go directive 和三个 Docker builder tag 从 `1.26.4` 升到 `1.26.5`；`git merge-tree --write-tree upstream/main upstream/pr-446` 成功生成 tree `bb6df1f`，没有文本冲突，也没有关闭或新增 #446 的技术 finding。现有 PR checks 均早于这次 base advance，最终 rebase/merge head 仍应重跑 CI。

#### 18.8.1 Findings first

| Severity / ownership | Stable ID | `d7333cc` current evidence | 结论 |
| --- | --- | --- | --- |
| P1 / PR blocker | `F09-existing-claim-upgrade-lifecycle` | `run_e2e.sh:466-509` 只等待同一 migrated `upgrade-bound-claim` Ready，并验证 Sandbox/Pod UID、binding 和 shadow pool 存在；没有删除该 Claim、按原 UID 验证 Sandbox/Pod GC，也没有验证同一 source pool refill。`e2e_test.go:813-858` 使用新建 v1beta1 CodeInterpreter/session，是另一条 lineage | Issue #438 明确要求 existing active Claim 的升级路径以及 adoption、session deletion、GC、refill；新对象通过不能替代迁移对象闭环，仍 present |
| P2 / PR blocker pending maintainer policy | `F19-embedded-podspec-workloadref` | base AgentRuntime CRD 暴露 `workloadRef{name,podGroup,podGroupReplicaKey}`；head 只剩 shape 不同的 `schedulingGroup{podGroupName}`。生产 builder 继续复制 typed `corev1.PodSpec`，所谓 compatibility test 只构造新 PodSpec 并检查 image；root guide 只有一句 transition，mirror 无说明 | 作者的 `intentional` 解释说明了依赖来源，但没有提供旧 payload migration/rejection test，也不是 maintainer accepted-risk，仍 present |
| P2 / PR blocker | `F20-conversion-webhook-readiness-docs` | 两份 mandatory upgrade guide 分别在 `docs/getting-started.md:69` 和 mirror `:62` 使用无界 `until kubectl get ...; do sleep 2; done` | webhook 永久不可达时 operator 永久挂起，无诊断和 non-zero exit；E2E 自身的 bounded gate 不能关闭文档路径，仍 present |
| P2 / repository follow-up | `F21-scheme-test-ci-discovery` | 新 `cmd/workload-manager/main_test.go` 不在 coverage 的 `./pkg/...` 或 E2E 的 `./test/e2e/...` 命令内 | 技术上仍 present；修复归属仓库级 test discovery，不扩进 #446 的最小 PR blocker 集合 |

上一轮唯一新增的 `F22-e2e-webhook-wait-fail-open` 已真实关闭：`run_e2e.sh:447` 在第 30 次失败的诊断后 `exit 1`，mutation 不再可达。21 项 v5 ledger 的 exact-head closure 因此为 **17 fixed / 4 present / 0 unclassified**；新 closure 保存于 [`pr446-d7333cc-finding-closure-v5.json`](benchmarks/day57-agent-autoharness/pr446-d7333cc-finding-closure-v5.json)。独立 final-tree falsification 没有发现 `F09/F19/F20` 之外的新 current-head P1/P2。

#### 18.8.2 Review state 与验证边界

24 个 review threads 中 23 个由 PR 作者自行 resolve，剩余未 resolved thread 正是已由代码关闭的 `F22`。当前仍是 30 个 `COMMENTED` reviews、0 `APPROVED`、0 `CHANGES_REQUESTED`；没有 maintainer 对 `F09`、`F19` 或 `F20` 给出 accepted-risk decision。resolved metadata、作者 `done.` 和 reviewer request 都不能代替 current-tree closure。

验证结果：

```text
review_surface.py, base 0704bb9 / head d7333cc              36 changed files; structurally mergeable
final_head_review.py --check-urls                            expected exit 1; 17 fixed / 4 present
carry-forward finding closure                               COMPLETE
literal v0.4.6 / v0.5.3 migration URLs                      HTTP 200
bash -n test/e2e/run_e2e.sh hack/update-codegen.sh           PASS
git merge-tree latest main@939abb5 + PR head                 PASS, no conflict
git diff --check base..head                                  FAIL, 19 trailing-whitespace lines
local --run-go-tests replay                                  NOT COUNTED, host resource contention
```

本轮 Go replay 遇到共享主机负载接近 200、可用内存约 1.3 GiB、无 swap，linker 十多分钟未完成；主动中止后不把它记成 PASS 或 AgentCube failure。`d7333cc` 相对已完成 direct Go tests 的 `353f1df` 只增加一行 shell `exit 1`，且 current head 的 build、lint、coverage、Codegen、Python 和两个 upstream E2E jobs 全部通过。没有新建 live cluster。19 处 trailing whitespace 是机械清理，不提升为 correctness blocker。

DCO 仍因 `da4140d` 与 `353f1df` 缺少 `Signed-off-by` 而 `action_required`；Tide 仍等待 `lgtm/approved`。综合结论继续是 **NO `/lgtm`**。本轮没有向 upstream 发布 review/comment、reply、resolve、Prow command、reviewer request 或 maintainer mention。

### 18.9 `d7333cc` 一次性复核发布

发布前于 `2026-08-05 10:08 CST` 再次刷新 GitHub：#446 仍为 open、non-draft，exact head 仍是 `d7333cc2fcc78ff923e45a9e4ed5d9e714359baa`，此前的 `updatedAt=2026-08-03T05:23:44Z` 只对应作者重新请求 `ranxi2001` review。30 个既有 reviews 全为 `COMMENTED`，没有 `APPROVED` 或 `CHANGES_REQUESTED`；24 个 threads 中 23 个由 PR 作者 resolve，唯一未 resolve 的 `F22` 已由 current code 技术关闭。没有新的 commit、review、comment 或 maintainer accepted-risk 决定。

重复评论守卫确认 `F09`、`F19`、`F20` 都已有 current-PR 公开证据：migrated Claim lifecycle 对应 maintainer thread [`r3682886443`](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3682886443)，`workloadRef` 对应 [`r3691344811`](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3691344811)，两份文档的 bounded webhook gate 对应 [`r3691344808`](https://github.com/volcano-sh/agentcube/pull/446#discussion_r3691344808)。因此没有重新创建三条 inline threads，而是把 exact-head closure 作为一个顶层 review 汇总；仓库级 `F21-scheme-test-ci-discovery` 没有扩进本 PR 的最小 blocker 集合。

用户确认 exact target、head、event 和完整正文后，于 `2026-08-05 10:24:10 CST` 一次性发布 [`COMMENT` review `4860469530`](https://github.com/volcano-sh/agentcube/pull/446#pullrequestreview-4860469530)。GitHub API 回读确认 reviewer 为 `ranxi2001`、state 为 `COMMENTED`、commit 为 exact `d7333cc`，正文只汇总上述三项 PR-scope residual，并明确已修复 webhook fail-closed thread、没有新增 current-head P1/P2、当前仍不应 `/lgtm`。没有发布新 inline comment、`REQUEST_CHANGES`、Prow command、maintainer mention、thread resolve 或 reviewer request。

> 分析：在同一 finding 已有公开 thread、但作者自行 resolve 后 current tree 仍未关闭时，新的 review round 应引用原 thread 并补充 exact-head closure，而不是复制相同 inline finding。这样既保留 blocker，也让 reviewer 能区分“GitHub resolved metadata”和“技术上已关闭”。

### 18.10 `3882157` main merge 与 #453 cross-reference

作者于 `2026-08-05 11:48:45 CST` 把 `main@939abb5` 直接 merge 进 #446，head 从 `d7333cc2fcc78ff923e45a9e4ed5d9e714359baa` 变为 `3882157b92d9fe2f5c9f112ebdaf872093fcc7f5`。该 commit 的两个 parents 正是 `d7333cc` 与 `939abb5`；first-parent diff 只有 `go.mod` 的 Go `1.26.4 -> 1.26.5` 和三个 Docker builder 镜像的对应 patch，未修改 migrated lifecycle、AgentRuntime CRD/typed `PodSpec`、两份 migration guide 或相关 tests。

新 commit tree 为 `bb6df1fa92216702967bff3faff777c29b6ea660`，与 18.8 在发布 review 前对 `main@939abb5 + d7333cc` 预计算并审查的 merge tree 完全相同。所有新 head executable checks 已通过，因此此前“checks 早于 main advance”的限制关闭；但 `F09`、`F19`、`F20` 的代码证据逐字未变，17 fixed / 4 present 的技术分类不变。旧 closure JSON 仍严格绑定 `d7333cc`，不能冒充 `3882157` 的 exact-head closure；由于当前 merge commit 违反仓库历史规则并预期被 rebase，不为这个瞬态 SHA 新造一份正式 closure。

Prow 随即添加 `do-not-merge/contains-merge-commits`，并在 [评论 `5187308245`](https://github.com/volcano-sh/agentcube/pull/446#issuecomment-5187308245) 要求用 rebase 重放 commits。DCO 仍只列出 `da4140d` 与 `353f1df` 缺少 signoff；Tide 仍等待 `lgtm/approved`。这使当前 head 比 `d7333cc` 多一个明确的流程 blocker，并没有更接近 `/lgtm`。

GitHub 于 `2026-08-05 15:02:54 CST` 显示“acsoto mentioned this pull request”，实际是 #453 产生的 cross-reference。`@acsoto` 在 [#453 评论 `5188629285`](https://github.com/volcano-sh/agentcube/pull/453#issuecomment-5188629285) 说明暂不需要把 getting-started 从 agent-sandbox v0.1.1 调到 v0.4.6，因为 #446 正在完成升级。该 MEMBER 意见证明 #446 是当前 canonical upgrade path，也是拒绝 #453 重复文档改动的 scope 决定；它不是 #446 的 review、`/lgtm`、approval，也没有接受 `F09/F19/F20` 的剩余风险。

本轮只做 latest timeline、first-parent diff、tree identity、CI/DCO/Prow 与 cross-reference 原文核对，没有发布新 review、reply、resolve、Prow command、reviewer request 或 maintainer mention。下一次正式 review 应等待作者按 bot 要求 rebase/squash，或提交触及剩余 findings 的实质 patch，再绑定新的 exact head。

### 18.11 `86e45ab` 新 reviewer request 与补丁验收

作者没有先清理 merge history，而是在 `3882157` 之后追加 5 个 signed commits，于 `2026-08-06 05:07:44 CST` 在 exact head `86e45ab45318a72df75b0a457aa6f102b1dbf92f` 重新请求 `ranxi2001` review。review-request event 之后没有新 commit、comment、review、label 或 head 变化，因此该 SHA 是本轮稳定审查对象。相对 `3882157` 的增量只改 4 个文件：两份 getting-started guide、`pkg/workloadmanager/workload_builder_test.go` 与 `test/e2e/run_e2e.sh`。

#### 18.11.1 已关闭：文档 webhook gate

两份 mandatory upgrade guide 都把无界 `until` 改成最多 30 次的 probe，并在耗尽时 `exit 1`，之后才允许执行 `./migrate.sh --phase=migrate`。这准确满足原 thread 对 bounded、fail-closed webhook gate 的要求，`F20-conversion-webhook-readiness-docs` 从 present 变为 fixed。没有因为缺少 controller logs 而移动验收目标；原评论只要求 bounded probe 和 timeout failure。

#### 18.11.2 仍未关闭：把另一条 cold lineage 的首次 fill 当成 refill

新增 E2E 确实被 exact-head 两个 upstream jobs 执行并通过，但日志反而把 lineage 分离直接打印出来：

```text
claim agentcube/upgrade-bound-claim: warm-started (...); no shadow needed
creating shadow pool agentcube/shadow-pool-e2e-upgrade-template
Bootstrap summary: scanned=2 warmstart_skipped=1 ... created=1
shadow-pool-e2e-upgrade-template           READY=<empty> DESIRED=0
upgrade-bound-claim deleted
shadow-pool-e2e-upgrade-template patched   replicas: 0 -> 1
Shadow pool successfully refilled!
```

`upgrade-bound-claim` 的 Sandbox 是手工创建并绑定的 standalone object；v0.5.3 conversion 按 `stripRandomSuffix(upgrade-bound-sandbox)` 给 warm-started claim 推导 pool identity，并不会给它创建 `shadow-pool-e2e-upgrade-template`。后者由另一条 cold claim `shadow-pool-e2e-code-interpreter` 触发 bootstrap，且 desired replicas 明确为 0。脚本删除前者后再把后者从 0 扩到 1，只证明一个无关 pool 可以首次填充，不能证明 migrated active claim 的 source pool 在 checkout / deletion 后 refill。

此外，脚本只把 `kubectl get sandbox` 的任意非零退出都当作删除成功，没有区分 NotFound 与 API 错误；此前捕获的 `BOUND_POD_UID` 也没有参与删除后的 GC assertion，脚本更没有捕获同一 source pool 的 replacement Sandbox UID。`F09-existing-claim-upgrade-lifecycle` 因此仍 present。最小闭环仍是：在 v0.4.6 中让真实 SandboxWarmPool 生产并交出一个 Sandbox，捕获 Claim/Sandbox/Pod/pool identity；迁移；删除同一 Claim；只在明确 NotFound 时确认原 Sandbox 与 Pod UID 消失；再要求同一 pool 回到原 desired capacity 且出现不同 Sandbox UID。

> 分析：CI 运行了断言并不等于断言证明了标题中的因果关系。这里不是 flaky timing，而是 producer ownership 错了：被删除对象和被观测 refill 的 pool 从未属于同一 lifecycle。

#### 18.11.3 仍未关闭：旧对象 test 只把静默丢字段写成 green

`TestAgentRuntime_OldObjectCompatibility` 最终修正了 `spec.podTemplate` JSON key，确实进入 current typed `corev1.PodSpec`。但 fixture 的 `workloadRef` 只有 `name`；base AgentRuntime CRD 明确要求 `name` 与 `podGroup`，所以它不是一个可由旧 schema 接受并存入 etcd 的 v0.4.6 object。测试随后接受 unknown field 被 `json.Unmarshal` 丢弃，只断言 container image 仍能被 builder 复制；它没有证明 scheduling intent 被保留或映射，也没有显式拒绝不兼容对象。

两份 guide 现在都说把 `workloadRef` “transition” 到 `schedulingGroup`，但两者并非字段改名：旧 shape 是 `name + podGroup + optional podGroupReplicaKey`，新 shape 只有 `podGroupName`。文档没有说明哪个旧值映射到 `podGroupName`，以及其余值没有等价表示。生产 informer 也先解码到同一个 typed AgentRuntime，再由 builder DeepCopy，所以测试实际复现的是生产静默丢失路径，而不是 compatibility closure。`F19-embedded-podspec-workloadref` 保持 present；这仍在 PR 自己引入的 Kubernetes/CRD upgrade scope 内。

> 注释：如果项目明确选择 breaking boundary，最小可审查结果不是实现完整 conversion webhook；可以使用 schema-valid legacy payload，明确断言旧 scheduling intent 的处理方式，并在两份 guide 中给出可执行 mapping 或清楚说明哪些语义不能迁移。当前测试连旧输入前提都不成立。

#### 18.11.4 Checks、流程门槛与 closure

exact head 的 11 个 executable checks 全部通过，包括 coverage、Codegen、lint、build 与两个 E2E。E2E 日志证明新增 lifecycle block 在两个 jobs 中实际执行。`bash -n test/e2e/run_e2e.sh` 通过；`git diff --check base..head` 仍报告 docs 与 E2E shell 的 trailing whitespace，作为机械清理记录，不提升为 correctness blocker。focused `go test ./pkg/workloadmanager` 在共享主机 load average 超过 150、无 swap、可用内存约 1 GiB 时持续编译 6 分钟后中止，不计为 PASS 或代码失败；exact-head coverage workflow 的 `go test -race ... ./pkg/...` 已成功执行该 package。

v5 21-item ledger 的新 immutable closure 保存为 [`pr446-86e45ab-finding-closure-v5.json`](benchmarks/day57-agent-autoharness/pr446-86e45ab-finding-closure-v5.json)，分类为 **18 fixed / 3 present / 0 unclassified**。present IDs 为 PR-scope `F09`、`F19` 与 repository-level follow-up `F21`；相较 `d7333cc`，`F20` 已关闭。`final_head_review.py --check-urls` 验证 ledger digest、target 与 exact head 一致，carry-forward closure complete，5 个 literal migration URLs 为 HTTP 200；因三项 present、`cmd/workload-manager` changed test 未被 CI 发现且本轮未完成 direct replay，harness 按预期以 exit 1 报 finding readiness blocked / changed-test execution not-run，没有把结构 closure complete 误写成 merge ready。

流程上仍是 NO-GO：history 继续包含 merge commit `3882157`，`do-not-merge/contains-merge-commits` 未移除；DCO 精确列出 `da4140d` 与 `353f1df` 缺 signoff；Tide 等待 `lgtm/approved`。31 个 submitted reviews 全为 `COMMENTED`，没有 maintainer 在新 5 commits 后接受 F09/F19 风险。review request 之后没有新活动。

本轮没有发布 GitHub review/comment、reply、resolve、`/lgtm`、Prow command、reviewer request 或 maintainer mention。若要向 upstream 反馈，应只提交一个绑定 `86e45ab` 的新 review，说明 F20 已关闭并给出 F09/F19 的 exact counterexample；发布前仍需用户确认 exact body 与 event。

### 18.12 `8a528f1` 再次 reviewer request 与 final-head closure

作者在上一轮 `COMMENT` review 后新增两个 signed commits：`5bf231a` 修改两份 getting-started guide、`workload_builder_test.go` 与 migration E2E，`8a528f1` 只对 Go test 做 `gofmt`。作者于 `2026-08-06 17:54:00 CST` 再次请求 `ranxi2001` review；本轮审查绑定 exact head `8a528f1d67fe5615ea04b9eb34903af53ed8a4ea`。父 Issue #438 没有新的 scope 或 accepted-risk 决定。

#### 18.12.1 `F19` 已关闭

`TestAgentRuntime_OldObjectCompatibility` 现在使用旧 CRD 可接受的完整 `workloadRef`：必填 `name`、`podGroup` 和可选 `podGroupReplicaKey`。测试显式断言 v0.36 typed decode 会丢弃该 legacy field，且不会无依据地合成 `SchedulingGroup`。两份 guide 同步声明这是一条 breaking compatibility boundary：旧 `workloadRef` scheduling intent 不受 v0.36+ 支持，需要 pod-group 语义的用户必须迁移到 `schedulingGroup.podGroupName`。这满足上一轮给出的两种可接受方向之一，即使用 schema-valid payload 并明确测试、记录不兼容语义，因此 `F19-embedded-podspec-workloadref` 从 present 变为 fixed。

focused command `go test ./pkg/workloadmanager -run 'TestAgentRuntime_(OldObjectCompatibility|PodSpec_K8s36CompatibilityBoundary)$' -count=1` 通过，`gofmt -d pkg/workloadmanager/workload_builder_test.go` 无输出。

#### 18.12.2 `F09` 仍是 false green

新 E2E 确实创建了 `e2e-upgrade-warmpool`，但 `upgrade-bound-sandbox` 仍由脚本独立创建，没有该 pool 的 owner reference、`agents.x-k8s.io/warm-pool-sandbox` label 或 pool-generated name；随后脚本把它手工绑定给 `upgrade-bound-claim`。这两条资源线没有成为同一条 lifecycle：

```text
e2e-upgrade-warmpool -> pool-created Sandbox A (already Ready, pool label)

upgrade-bound-claim -> manually-created upgrade-bound-sandbox B -> Pod B
```

v0.5.3 conversion webhook 对 warm-started claim 执行 `stripRandomSuffix(status.sandbox.name)`。因此 `upgrade-bound-sandbox` 会转换成 `warmPoolRef.name=upgrade-bound`，不是 `e2e-upgrade-warmpool`。删除 claim B 后，脚本读取的是 pool A 已经为 1 的 `status.readyReplicas`，再用只有 key、没有 pool hash value 的通用 label selector 取任意 pool Sandbox。Sandbox A 从测试开始就满足 `UID != BOUND_SANDBOX_UID`，所以即使删除 claim B 完全没有触发 pool refill，断言也能立即通过。

正确闭环需要让 v0.4.6 controller 从真实 pool 生产 Sandbox，记录该 pool 的 name/hash 与 member Sandbox/Pod UID，再让同一 claim 真正 adopt 该 member。迁移后删除同一 claim，必须先确认原 Sandbox/Pod UID 消失，再确认同一 pool 回到原 desired capacity，并出现属于该 pool 的不同 Sandbox UID。当前 `F09-existing-claim-upgrade-lifecycle` 仍是唯一 PR-scope correctness blocker。

#### 18.12.3 Harness、checks 与流程 gate

`final_head_review.py` 在 clean detached worktree 对 21-item v5 ledger 重跑。新 immutable closure 保存为 [`pr446-8a528f1-finding-closure-v5.json`](benchmarks/day57-agent-autoharness/pr446-8a528f1-finding-closure-v5.json)，结果为 **19 fixed / 2 present / 0 unclassified**。present IDs 是 PR-scope `F09` 和 repository-level follow-up `F21-scheme-test-ci-discovery`。harness 直接执行此前未被 CI discovery 覆盖的 `go test ./cmd/workload-manager -count=1`，91.224 秒通过；changed-test execution 因而为 passed。literal v0.4.6/v0.5.3 URLs 仍返回 HTTP 200，带版本变量的 URL 保持 unresolved-variable lead 而不是失败。

附加验证：`bash -n test/e2e/run_e2e.sh` 通过，exact-head 两个 E2E jobs、coverage、Codegen、lint、build 和 Python checks 全部通过。`git diff --check 86e45ab..8a528f1` 只报告 `run_e2e.sh:525` 一处 trailing whitespace，不提升为 correctness finding。

DCO 仍精确列出 `da4140d`、`353f1df` 两个 unsigned commits；history 仍含 merge commit `3882157`，Prow label `do-not-merge/contains-merge-commits` 未移除；Tide 等待 `lgtm/approved`。综合结论仍是 **NO `/lgtm`**。本轮没有发布 review/comment、reply、resolve、Prow command、reviewer request 或 maintainer mention。

### 18.13 `7a17302` real member 补丁复核

作者在上一轮 review 后新增 signed commit `7a17302efae3a5b9d3a8b68751de378457a1dc8a`，增量只修改 `test/e2e/run_e2e.sh`，并于 `2026-08-07 03:38 CST` 回复已改用 `e2e-upgrade-warmpool` 的实际 member。#446 仍为 open、non-draft，base 与 current `main` 均为 `939abb5`，结构上可合并；父 Issue #438 与 upstream #1124 没有新的 accepted-risk 或 scope 变化。

#### 18.13.1 已修正：producer/name lineage

新脚本不再独立创建 `upgrade-bound-sandbox`。它会从 v0.4.6 pool 选出实际 member，捕获该 Sandbox 与 Pod 的 exact UID，迁移后检查同一 binding/UID，删除 Claim 后要求两个对象明确返回 `NotFound`。因为 pool-generated name 形如 `e2e-upgrade-warmpool-xxxxx`，v0.5.3 conversion 的 suffix stripping 现在会得到正确的 `warmPoolRef=e2e-upgrade-warmpool`。上一轮的 producer/name mismatch 已真实关闭，不能继续复用旧 counterexample。

#### 18.13.2 `F09` 仍未关闭：测试手工伪造 adoption

当前 fixture 在同一次 apply 中创建 Template、replicas=1 的 pool、一个 cold fixture Claim 和 `upgrade-bound-claim`；两个 Claim 都省略 `spec.warmpool`，因此在 v0.4.6 下都使用 default policy。脚本随后从 pool 中选一个 member，却不是等待 Claim controller 交出它，而是在 `run_e2e.sh:410-411` 直接覆盖该 member 的 controller owner，并写入 Claim status。

这有一条 source-proven 的可达误判路径：

1. `upgrade-bound-claim` 可在 pool member Ready 前先 cold-create 自己的 Sandbox，或与另一 default-policy Claim 竞争 member。
2. 脚本再把另一个 pool member 的 owner/status 强行改给同一 Claim，使 fixture 可能短暂拥有两条 Sandbox lineage。
3. v0.4.6 pool controller 会忽略仍带 pool label、但已由 Claim 控制的 member，并立即把 replicas=1 的缺口补出 replacement；这个 replacement 可以早于 migration 存在。
4. 迁移后的 `readyReplicas >= 1` 与 namespace-wide generic warm-pool label 查询会接受这个旧 replacement，因此不足以证明 current controller 对 exact source pool 完成了预期 lifecycle。

v0.4.6 的真实 adoption 会写 Claim assigned-Sandbox label、移除 pool labels、转移 ownership 并传播 Claim identity；其 status fast path 会接受脚本伪造的 owner/status 而跳过这些步骤。focused upstream pool-controller test 也确认 foreign controller owner 会触发 replacement 逻辑。最小修正是先只创建并 ready Template/Pool，捕获 exact member，再创建指定该 pool 的 bound Claim 并等待生产 controller 报告同一 UID 与 ownership；cold fixture 应在之后创建并显式设为 `warmpool: none`。迁移后应把 bound Sandbox/Pod GC 与 exact named-pool replacement 分开验证，后者使用 pool owner/hash 和新 UID，而不是 namespace-wide generic selector。

> 分析：pool 正常会在 member 被 adopt、离开 pool ownership 时补池，而不是在 Claim 删除时才补池。这里的 blocker 不是要求错误的“删除触发 refill”时点，而是 fixture 没有证明真实 adoption，并且最终断言没有绑定补池对象、source pool 和 controller version 的因果边界。

#### 18.13.3 Exact-head checks 与流程 gate

新 exact head 没有任何 GitHub Actions run；GitHub rollup 只有 DCO `action_required` 和 Tide `pending`。上一 head `8a528f1` 的 build、lint、coverage、Codegen 与两个 E2E 绿色结果不覆盖这次 shell 增量。direct exact-head 验证通过：

```text
bash -n test/e2e/run_e2e.sh                                  PASS
git diff --check 8a528f1..7a17302                            PASS
go test ./test/e2e -run '^$' -count=1                        PASS (compile-only)
go test ./cmd/workload-manager -count=1                      PASS
focused v0.4.6 pool-controller ownerRef test                 PASS
live migration E2E                                           NOT RUN (no usable local cluster)
```

21-item v5 ledger 的 exact-head closure 保存为 [`pr446-7a17302-finding-closure-v5.json`](benchmarks/day57-agent-autoharness/pr446-7a17302-finding-closure-v5.json)，结果仍为 **19 fixed / 2 present / 0 unclassified**。PR-scope blocker 是 `F09-existing-claim-upgrade-lifecycle`；`F21-scheme-test-ci-discovery` 仍是 repository-level follow-up，因为 CI 只执行 `./pkg/...` 与 `./test/e2e/...`，没有发现 `cmd/workload-manager/main_test.go`。direct scheme test 通过不等于 CI 已守住该回归。harness 验证 carry-forward closure complete、changed-test execution passed；5 个 literal migration URLs 返回 HTTP 200，3 个含 shell variable 的 URL 保持 unresolved-variable，最终因两项 present finding 按预期 exit 1。

DCO 继续明确列出 `da4140d` 与 `353f1df` 缺 signoff；history 仍含 merge commit `3882157` 和 `do-not-merge/contains-merge-commits` label；Tide 仍需 `lgtm/approved`。综合结论继续是 **NO `/lgtm`**。本轮没有发布 GitHub review/comment、reply、resolve、Prow command、reviewer request 或 maintainer mention。

### 18.14 fork-only same-lineage 参考实现与真实验证

`2026-08-07 11:14 CST` 再次刷新 GitHub，#446 仍为 open、non-draft，exact head 仍是 `7a17302efae3a5b9d3a8b68751de378457a1dc8a`，current `main` 仍是 `939abb5b1f52a2d8f841ac1dbdc03fc96269bb5e`；没有新的 upstream commit、Actions run、review 或 accepted-risk 决定。为回答“如何修复并验证”，从该 exact head 创建 fork-only branch `fix/pr446-lineage-reference`，落下 signed-off commit [`13e6f443a4660636daf841c233989578b9aee074`](https://github.com/ranxi2001/agentcube/commit/13e6f443a4660636daf841c233989578b9aee074)。没有创建 upstream PR、comment、review、reply、Prow command 或 maintainer mention。

#### 18.14.1 参考修复的因果边界

fixture 现在按四个阶段运行：

1. 只创建 v0.4.6 Template 与 replicas=1 的 named Pool，等待 `status.selector` 对应的唯一 Ready Sandbox，并要求 controller owner kind/name/UID 精确指向该 Pool；在创建 Claim 前捕获 Sandbox 与 Pod UID，记为 A。
2. 创建显式 `warmpool: e2e-upgrade-warmpool` 的 bound Claim，等待 v0.4.6 controller 自己完成 adoption。通过条件同时包含 Claim assigned label/status binding、Sandbox owner 转移、pool label 删除、claim UID label 写入以及 A/Pod UID 不变；脚本不再 patch Sandbox owner 或 Claim status。adoption 后等待同一 selector/Pool owner 下出现不同 UID 的 Ready replacement B，再创建 `warmpool: none` 的隔离 cold fixture。
3. v0.5.3 storage migration 后，不先相信旧 `Ready=True`。脚本要求 A 与 B 都出现 v0.5.3-only `agents.x-k8s.io/launch-type=warm` marker，同时检查 Claim `warmPoolRef`、binding/UID、A owner、Pool UID/selector 和 B owner/UID 全部保持一致。
4. 删除 Claim 只验证 A 与 Pod 的精确 GC，并确认独立的 B 未受影响。随后显式删除 B，只有同一 selector、同一 Pool owner UID 下出现不同 name/UID、Ready 且 `launch-type=warm` 的 C 才算 current-controller refill 成功。

这把旧 fixture 混在一起的三个命题拆开：真实 adoption、Claim-owned lineage GC、Pool-owned lineage refill。namespace-wide generic label 与“任意 UID 不等于 A”的弱断言均已删除。

#### 18.14.2 focused k3d live migration

本机 standard kind 仍处于既有 kubelet/cgroup stop condition，因此使用隔离的 `k3d` v1.32.5 集群，只安装官方 agent-sandbox v0.4.6 与 v0.5.3 manifests，并执行真实 bootstrap/storage migration。live 结果为：

```text
A Sandbox UID  6d9bf37d-aee1-4f7b-8edc-9428183dc99b
A Pod UID      99a7ef9a-7e8a-47de-a880-a58390a211e3
B Sandbox UID  c05d0d21-7e7a-4bce-a86d-a64ea598e91d
C Sandbox UID  c968a8e7-ee19-4477-b8cb-1210a7186752
Pool UID       e1af6b2b-6f87-4a62-923a-af1b91a03565
Claim UID      bd988108-913c-4519-81ce-4def3aaa0dd2
result         PASS
```

测试观察到 A 的真实 v0.4.6 adoption、A/B 的 v0.5.3 marker、A/Pod GC、B 在 Claim GC 后继续存在，以及显式删除 B 后同一 Pool 补出 C。临时 `pr446-lineage-ref` 集群、network、volume 与 standalone kubeconfig 已删除；未影响主机上其他容器。

#### 18.14.3 fork CI 与终态

fork push 精确绑定 `13e6f44`，9 个 workflows 全部成功：[Agentcube E2E run `31143151561`](https://github.com/ranxi2001/agentcube/actions/runs/31143151561)、Go CI、Coverage、Lint、Codegen、Codespell、Copyright、Python Lint 与 Python SDK。E2E 两个独立 matrix job 都实际执行 same-lineage block：

| Job | A | v0.4.6 replacement B | v0.5.3 refill C | Result |
|---|---|---|---|---|
| `e2e-test` | `qclmc / 531408c7` | `xpfkq / 50df5d53` | `jq5lt / 78de2aa4` | success |
| `codeinterpreter-e2e-test` | `z4674 / 53609a4d` | `shr6f / 4647232b` | `x8wjr / 233b77bd` | success |

本地 `bash -n`、`git diff --check`、`go test ./test/e2e -run '^$' -count=1`、`go test ./cmd/workload-manager -count=1`、全部 non-E2E Go packages、v0.5.3 conversion 与 focused controller tests 均通过。裸 `go test ./...` 会执行需要 Router/WorkloadManager 端口转发与 kubeconfig 的 live E2E，因本地服务已清理而按预期失败；这项结果没有被伪装成代码失败或通过。

该 fork commit 证明 `F09-existing-claim-upgrade-lifecycle` 有可运行的修复路径，但 upstream PR head 仍是未包含该 commit 的 `7a17302`，所以 upstream closure 继续保持 19 fixed / 2 present，结论仍是 **NO `/lgtm`**。流程 gate 也未变化：DCO 仍列出两个旧 unsigned commits，history 仍含 merge commit，Tide 仍等待 `lgtm/approved`。

## 19. 2026-08-10：RainbowMango same-head review 与能力升级

### 19.1 证据边界与权威性

`2026-08-10 16:30 CST` 最终只读刷新 #446：PR 仍为 open、non-draft，exact base
`939abb5b1f52a2d8f841ac1dbdc03fc96269bb5e`、exact head
`624c875bcfa29282d0b6b4ea5171867ad4913202`，没有作者回复或新提交。RainbowMango 在
`2026-08-10 06:55-07:13 UTC` 提交的 7 条 inline comments，其 `commit_id` 与
`original_commit_id` 全部等于 `624c875`；PR `updatedAt` 仍停在最后一条维护者评论，没有作者
reply 或新 commit，因此这次比较没有 later-head regression 或 squash 映射歧义。

根 `OWNERS` 同时把 RainbowMango 列为 reviewer 和 approver，GitHub association 为
`COLLABORATOR`。这使其对 AgentCube 的 PR 范围、文档承载位置和合入顺序具有权威性，但不把
所有简短意见自动变成可跨项目复用的技术定律。

### 19.2 7 条评论应归并为 5 个稳定主题

| Stable topic | RainbowMango 的结论 | 我们在同一 tree 前已有的证据 | 公平分类 |
|---|---|---|---|
| upgrade guide placement | 两份 Getting Started 都不应承载 upgrade guide；第二条 `ditto` 是同一主题 | 我们完整审过 migration 文档的 URL、备份 kinds、webhook fail-closed 与双份一致性，但没有先问 Getting Started 是否是 owning surface | 同一 acceptance invariant 上的 maintainer information-architecture decision；不是新增 correctness finding |
| codegen merge-unit scope | 先问为何改 `hack/update-codegen.sh`，再明确只有 `CODEGEN_VERSION` 行需要 | 12.5 已用 clean `make gen-check` zero diff 证明整套 Windows/manual-generator rewrite 不是 v0.5.3 必需；之后却继续修 rewrite 内部的 GOBIN 失败 | 已知 stable topic 的 same-head closure/governance miss；不是 discovery miss |
| MCP no-op churn | `pyproject.toml` 不需要修改 | 12.6 与 17.8 已记录 current diff 只剩 EOF newline、无语义且“应从 diff 移除” | 已知 stable topic 的 same-head closure/reporting miss |
| PicoD Windows test scope | `pkg/picod/files_test.go` 与升级无关 | 17.8 已把 `files_test.go` 和 `execute_test.go` 两处 skip 记为可拆出的 scope noise，覆盖面比单条 anchor 更完整 | 已知 stable topic 的 same-head closure/reporting miss |
| dependency prerequisite split | 先独立 bump Kubernetes/controller-runtime，再让 #446 只保留 agent-sandbox v0.5.3 | 我们已证明 v0.36.2/controller-runtime v0.24.1 是强制且广泛的 compatibility surface，但没有要求把它变成 prerequisite PR | maintainer merge sequencing decision；普通 reviewer 可提前提出高价值拆分问题，但不能把精确两步策略伪装成公开合同 |

两份 docs 与两条 codegen anchors 各自只算一个 topic。公平结果不是“维护者新发现 7 个、我们
发现 0 个”，而是：

- same-head technical correctness discovery miss：**0**；这 7 条没有新增 P1/P2 correctness defect；
- 已被我们明确发现的 stable scope topics：**3/5**；
- 已知 actionable scope topic 仍穿过最终 readiness decision：**3**；
- 需要维护者定调、但我们可以更早提出 open question 的 project-policy topics：**2**；
- “no remaining P1/P2” 的字面结论仍成立，但“review complete”加 `/lgtm` 对整个 diff 的 readiness
  表达过度。

#438 明确要求已有 v0.4.6 安装与 active SandboxClaims 具备 documented and tested upgrade
path。维护者否定的是 Getting Started 的承载位置，不是 acceptance requirement 本身；后续修改
不能据此直接删除 upgrade documentation 或相关安全性验证。

### 19.3 能力差异不是单一的“谁更懂代码”

我们的优势仍然是深层 correctness：API/storage migration、producer ownership、UID lineage、
adoption/GC/refill、auth owner persistence、generated schema、CI discovery 和 causal E2E 都有源码、
red/green 或 live evidence。RainbowMango 本轮 7 条没有推翻这些 closure。

维护者本轮更强的是 review economics 和 merge-unit judgment：先问为什么触碰一个 surface、依赖
必要性是否等于同 PR 必要性、信息应由哪个文档承载，再投入细节审查。我们虽然看见了三项
scope noise，却有明显的 fix-it bias：codegen 整块已经被证明不需要后，仍继续修它内部的 GOBIN
问题；MCP/PicoD 被降为“非 P2 清理”后，从最终 gate 中消失。point/line correctness 很强，surface
层的 keep/remove/separate 决策不够坚决。

这也暴露了 completion vocabulary 的问题：finding severity 只描述行为后果，不能替代 merge
readiness。一个 PR 可以没有 P1/P2 correctness finding，同时仍因已知 `remove` / `separate` 项而
不适合 `/lgtm`。

### 19.4 `agentcube-pr-review` 升级

本轮将这条教训固化为 scope-first gate，而不是追加若干只匹配 #446 文件名的启发式：

1. 深审前先把 diff 分为 direct acceptance、forced prerequisite、generated consequence、validation、
   docs/ops artifact 和 independent cleanup/no-op；对每个 hand-written file 与 material hunk 记录
   owning surface、independent mergeability 和 `keep/remove/separate/unresolved/mixed`。
2. 必要 dependency 不再自动等于同一 merge unit；可独立构建、测试、合入的 repository-wide
   prerequisite 默认拆分，除非中间 tree 无法编译或无法保持同一 atomic compatibility invariant。
3. 已知 `remove` / `separate` topic 即使不是 correctness defect，也必须保留在 final readiness
   ledger；review-induced scope 需要重新证明，不能因“是 reviewer 要求的”自动获得正当性。
4. final head 增加 anchor-free scope pass，防止旧 finding ledger 把注意力锁在历史 blocker。
5. maintainer 对 placement/sequencing 的决定单独记为 policy calibration；改变 artifact location 不会
   静默删除 Issue acceptance。

`final_head_review.py` 新增 exact-head `--scope-closure` JSON gate。它要求每个 hand-written path
恰好出现一次，校验 target PR/head、非空 acceptance/owner/rationale/evidence、未知/重复路径、
independent `keep` 的 atomicity 说明，以及 `mixed` 文件的 hunk-level disposition。缺文件、stale
head 或任一 `remove/separate/unresolved` 项都会 non-zero exit；只有完整 `keep` closure 才能 ready。

回归用 exact #446 `939abb5...624c875` 运行时，harness 枚举 27 个 hand-written paths，维护者
comments 涉及的 6 个不同路径全部出现；未提供 scope closure 时结果为 `not-provided` 并 exit 1。
旧 harness 在同样 27 项全未关闭时仍会 exit 0，这正是本轮修掉的流程漏洞。

独立 code audit 继续找到四条历史 fail-open：ready scope 下缺 acceptance contract 仍可 exit 0、
changed Go test 未被 CI 覆盖且未 direct-run 仍可 exit 0、Git quoted path 会让 Unicode/tab path
逃出测试与 scope 识别、宽松的 generated substring 会误排除手写文件。现在 CLI 同时 gate
acceptance 和 uncovered-test execution；changed-path 解析改为 NUL-delimited + surrogateescape；
generated detection 只接受 canonical comment header。另补齐 `mixed` 全 `keep` 时不能绕过
independent-item atomicity。

第二轮 audit 继续沿 path/dataflow 找到：literal external URL 未执行 `--check-urls` 仍可 ready、
NUL-safe changed-file list 的下游 `changed_lines` 仍会丢 Unicode path、canonical generated comment
若出现在 `package` 后仍会误排除手写文件、`_test.go -> .go` rename 会逃出 package ledger、首尾
空白文件名会被 scope parser `.strip()` 改写。最终实现改为按 canonical path 单独解析 hunk body，
external URL 未通过网络或人工 exact-surface closure 即阻塞，只允许 generated marker 出现在
comment-only preamble，按 HEAD 是否仍有 Go files 追踪 rename-away/cross-package test，并为 path
使用不 strip 的 NUL-free identity validator。

第三轮独立 audit 又找到三个 material false-ready：禁用 workflow 内的 `echo "go test ..."`
静态文本会被误算成 CI coverage、deterministic boundary lead 只展示不 gate、以及
`git merge-tree` 已证明冲突时 CLI 仍可能 exit 0。最终 closure 现在绑定 exact
base/head/merge-base；workflow 命令只作为 candidate，必须补 exact-head PASS job 证据或 direct
run；每个 boundary lead 用稳定 key 分类为 `resolved/not-applicable/present/accepted-by-maintainer`，
其中缺失或 `present` 都阻塞；structural merge conflict 也直接阻塞。新增端到端回归分别构造
`if: false + echo` workflow、未闭环 lexical-version lead 和双分支同一行真实冲突，三者均确认
不能 false ready。

随后 adversarial replay 证明 CI closure 的自由文本 `source="trust me"` 仍可配合 disabled
`echo "go test ..."` candidate 伪造 ready；#446 实跑也说明 `${VERSION}` URL 若只有 HEAD probe 会
形成无法人工闭环的永久 false block。最终 workflow discovery 改为结构化 YAML job/step，排除
statically disabled 和 `echo/printf` 文本；CI closure 必须给出 current-repository Actions job URL，
harness 通过 GitHub API 核对 exact head、successful run、workflow path、job 与 named successful
step。自由文本不再参与 coverage，API 不可用时只能 direct-run。URL 则增加 exact-string
`resolved/not-applicable/present/accepted-by-maintainer` closure，网络 2xx/3xx 可自动闭环，变量 URL
用具体展开值的验证证据闭环，缺项和 `present` 仍阻塞。

最终稳定 diff 的 adversarial audit 又复现两条 CI false-ready：`true || go test ./pkg/...` 的 step
整体 success 不能证明测试执行；同一 job 内目标同名 step skipped、另一个同名 step success 会被
错误匹配。另有一条 ref race：入口虽记录旧 SHA，后续 diff/merge/object reads 仍使用可移动 ref。
最终只允许 uniquely identified static non-matrix job 中，单一 control-flow-free direct `go test`
整步成为 CI-waivable；Makefile、script、multi-command、pipeline、`if/exit/true ||` 都只作 lead。
remote closure 同时精确核对 workflow、static job name、YAML step ordinal/name 和 success，重复或
dynamic identity 不可 waiver。`review_surface.py` 先一次性解析 base/head SHA，之后 merge-base、
merge-tree、diff、object reads、test discovery 与 direct test 全部只使用冻结 SHA。对应负向 tests
覆盖 control-flow bypass、同名错配和 ref movement。

最后的定点复测确认上述三个反例已经关闭，但又构造出 `go test -run '^$' ./pkg/...` 配合绿色
Actions step 的 false-ready，并指出 `continue-on-error: true` 会让 step success 与测试退出码脱钩。
最终 eligibility 再收紧为完整 package 执行：`-run/-skip/-short/-list/-c/-count<=0/-exec/-tags`、
动态 flags、command/workflow/job/step `GOFLAGS` 与非 false `continue-on-error` 全部 lead-only，不能
用 API PASS waiver。正常的 coverage flags、race 和正数 count 仍可在其余 identity 条件满足时闭环。

第二次复测确认这两条串通路径关闭后，又用 `go test -n` 证明按危险参数黑名单仍会漏掉“绿色但
不执行”，并用 `-overlay` 证明 exact-head source 也可能被替换；`container.env.GOFLAGS` 与前序写入
`$GITHUB_ENV` 同样能绕过只检查三层 `env` 的实现。最终不再扩充黑名单，而改成 safe execution
allowlist：未知 build/test flag 一律 lead-only；同时检查 container env、前序 `$GITHUB_ENV` /
`go env -w`、effective working directory 与 shell。#446 的 `-race -v -coverprofile -coverpkg` 只在
command/flag 层满足 allowlist；不可静态证明的执行上下文统一回退 direct-run。

继续复核真实 #446 coverage replay 后，发现此前把 Actions API 的 `head_sha=624c875` 等同于
“worktree checkout 了 624c875”是错误的。`run 31167804353 / job 92832553795` 的 event 是
`pull_request`，默认执行的 synthetic merge commit 为 `fc885104`，其两个 parent 是当时的 main
`4b38a442` 与 PR head `624c875`，tree 也与 PR head 不同；workflow 的 checkout 又没有显式绑定
exact head。因此当前 harness 将该 candidate 记为 `ci_waivable=false`、
`exact_head_checkout=false`，即使 workflow/job/step 都 success 也只能作 lead。remote waiver 现在只
接受 immutable 40-hex setup actions、唯一 clean exact-head checkout、受控 Ubuntu runner、无前序
shell/env 注入，以及 `push` / `workflow_dispatch` exact-head run；`pull_request` event 一律拒绝。

direct fallback 的对抗检查又复现三条环境 false-pass：`PATH` 首位的假 `go` 可直接 `exit 0`，强制
`GOWORK=off` 可绕过仓库 workspace 而测试旧 `replace` 依赖，带 BOM 或前导空白的 build constraint
可让 Linux job 静默跳过新增测试。最终 direct gate 要求调用者显式传入受审绝对 `--go-binary`，
不再从 `PATH` 发现工具；清除 Go/CGO/compiler/loader 注入、固定 `GOENV=off` 与受控 `PATH`，并按
package 选择 HEAD 中最近的 governing `go.work`，只有没有适用 workspace 时才 `GOWORK=off`。
GOOS/GOARCH suffix 与含 BOM/缩进的 source build constraints 均要求显式兼容平台/tag execution。

随后 adversarial replay 进一步覆盖普通空格、Tab、vertical tab、form feed、NBSP 与 UTF-8 BOM；
这些 changed test 均无法获得 workflow waiver，direct gate 返回阻断码 2。当轮 focused harness tests
**50/50**、`agentcube-pr-review` 三个 test scripts **79/79**、本轮涉及的七个 skill test scripts
**107/107** 全部通过；`py_compile`、`git diff --check` 与 skill `quick_validate.py` 也通过。

另一轮独立 code review 随后仍找到两项 P1 与一项 P2：Git ignored 的 `_test.go` 可以加入
`TestMain` 后 `os.Exit(0)`，而普通 `git status` 继续 clean；tracked `go.work` 的 `use/replace` 或
`go.mod replace` 可以指向 repository 外的本地模块；direct gate 又把执行平台固定假设成
Linux/amd64，却没有核对显式 Go binary 的 host，因而在 macOS/arm64 上可能跳过 suffix test。

最终 direct-run 不再在输入 worktree 中执行，而是用 `git ls-tree` 与 `git cat-file blob` 把 exact
head 的 regular tracked files 逐项物化到新 temporary tree；Git ignored files、smudge/filter 后的
worktree 内容均不能参与。执行前用 `go work edit -json` 和 `go list -m -json all` 绑定 workspace
use/replace、main modules 与 local replacements，任一 resolved path 越出 materialized tree 都拒绝；
显式工具同时必须报告 Linux/amd64 host，环境固定 `GOOS=linux`、`GOARCH=amd64`、`GOENV=off` 与
`GOTOOLCHAIN=local`。ignored `TestMain`、`go.work use ../external`、darwin/arm64 fake tool 三条原始
PoC 均已反向通过，focused suite 为 **52/52**，review skill 三套为 **81/81**。

两名独立代理随后在同一行为版本上完成限定 P1/P2 终局审查，额外覆盖 external `go.work replace`、
external `go.mod replace` 与 vendor 组合，结论均为 clean。最终七套 skill tests
**109/109** 全部通过，`py_compile`、`git diff --check` 与 skill `quick_validate.py` 再次通过；最后仅
校正了包含 list 字段的 package/workflow row 类型标注，没有改变执行路径。

升级后的 exact #446 `939abb5...624c875` 回归仍枚举 36 changed files / 27 hand-written paths，
Rainbow 六个不同 comment paths 覆盖 6/6。该 surface 结构可合并，但因没有 exact-surface scope
closure、两个 exported-signature boundary leads 未分类、四个 changed Go test packages 没有 PASS
closure/direct result、七个 URL 未检查，harness 按预期 exit 1。coverage 的 direct command 是
checkout/event 不可 waiver 的 lead-only candidate；经 Makefile/script 到达的 E2E command 也是
lead-only，两者都没有再被静态文本或绿色 PR run 自动当成 exact-head 执行成功。

skill-creator fresh-context forward test 在 #446 上先于 correctness 重建出三个公开证据可支持的
scope topic（codegen rewrite、PicoD Windows skips、MCP EOF churn），把 upgrade-guide placement
与 dependency sequencing 分离为 maintainer-policy questions，并没有制造新的 blocking correctness
finding；harness 也拒绝在缺 scope closure 和 `./cmd/workload-manager` direct test 时 ready。这个结果
仍受训练泄漏限制，因为 required reference 已包含 #446 证据，不能单独当 held-out improvement。

因此又用未写入新 pattern 证据的 #450 `0704bb9...0b646d8` 做 held-out 式 false-positive pass。
fresh agent 把 ownership validation、`OwnershipConflict` status、`AlreadyExists` retry、UID/RV delete
preconditions 与相邻 causal tests 保持为一个 coherent merge unit，判定 **0 remove / 0 separate /
0 unresolved**；没有因跨四个文件或包含 race hardening 就机械拆 PR。这说明新 gate 至少同时通过
#446 的 scope recall 检查与 #450 的 focused-PR precision 检查，但仍不是多任务统计结论。

本轮没有修改 #446、发布评论、回复、resolve、发送 `/lgtm`、request review 或 mention maintainer。
最新 upstream 状态仍是等待作者按维护者意见调整或解释；旧的“review 已结束，只等 merge”状态已经
失效。
