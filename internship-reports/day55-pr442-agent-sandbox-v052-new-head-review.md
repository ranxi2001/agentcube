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
