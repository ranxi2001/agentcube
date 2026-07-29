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
