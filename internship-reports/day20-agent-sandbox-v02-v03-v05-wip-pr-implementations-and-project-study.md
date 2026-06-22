# Day 20 - AgentCube Project Study and agent-sandbox v0.2/v0.3/v0.5 WIP PR Implementations

日期：2026-06-22

## 目标

对 AgentCube 做第二轮项目理解，不再只停留在目录结构，而是建立以后改代码、做依赖适配、准备 review 答辩时能复用的 mental model。

本轮重点回答：

- AgentCube 当前 main 的真实实现是什么，不只看 README / design docs 的目标状态。
- 一次 `AgentRuntime` / `CodeInterpreter` invocation 从 Router 到 sandbox 内部怎么走。
- `agent-sandbox`、Kubernetes client-go/codegen、Redis/Valkey、PicoD、OIDC/mTLS 分别卡在哪些边界。
- 后续做 `agent-sandbox v0.4.6` / `v0.5.x` / Sleep-Resume 适配时，应该先看哪些文件，设计哪些测试。
- 记录 `agent-sandbox v0.2.1` / `v0.3.10` / `v0.5.0rc1` 三个 fork WIP PR / validation PR 实现，方便后续比较适配演进和 review 答辩。

## 基线和过程修正

开始 Day20 前先修正了 fork 分支语义：

- `origin/main` 已改成干净 mirror，只同步 `upstream/main`。
- 实习报告、TODO、skills、中文记录改到 `origin/intern`。
- 当前 Day20 文档写在 `intern` 分支，不污染 upstream-facing PR branch。

当前代码基线：

- `upstream/main`：`bed6bd4`，包含 #367 Keycloak/OIDC/RLAC 相关改动，也包含已合并的 Go `1.26.4`。
- `go.mod` 当前 main：`go 1.26.4`。
- `sigs.k8s.io/agent-sandbox` 当前 main 仍是 `v0.1.1`，不是 #387 的 `v0.4.6`，也不是 Day18 的 `v0.5.0rc1`。

过程卡点：

- 第一轮阅读曾在 fork `main` 和 upstream 最新状态还没明确拆分前开始，容易把“实习记录分支上的上下文”和“官方 main 代码状态”混在一起。
- 已先完成分支治理，再重新读当前 main 关键文件，避免 Day20 报告基于过期上下文。

## 一句话模型

AgentCube 不是一个 agent framework，也不是 LLM provider。它是 Kubernetes 上的 agent/code-interpreter session runtime：

```text
Client / SDK
  -> AgentCube Router
  -> WorkloadManager
  -> agent-sandbox CRD: Sandbox / SandboxClaim / SandboxTemplate / SandboxWarmPool
  -> Pod / sandbox runtime
  -> PicoD or user agent process
```

核心抽象是：

- `AgentRuntime` / `CodeInterpreter`：AgentCube 自己的 CRD，描述“要运行什么样的 agent 或 code interpreter”。
- `Session`：用户交互层面的会话，靠 `x-agentcube-session-id` 识别。
- `SandboxInfo`：AgentCube 在 Redis/Valkey 中保存的 session -> sandbox 路由记录。
- `Sandbox` / `SandboxClaim` / `SandboxTemplate` / `SandboxWarmPool`：来自 `kubernetes-sigs/agent-sandbox` 的底层运行资源。
- `PicoD`：sandbox 内部的 HTTP daemon，执行命令和文件操作，依赖 Router 签发的 JWT 鉴权。

> CRD = Custom Resource Definition。Kubernetes 默认只认识 Pod、Service、Deployment 这类内置资源；CRD 的作用是把项目自己的资源类型注册到 Kubernetes API server 里。AgentCube 注册了 `AgentRuntime` / `CodeInterpreter`，agent-sandbox 注册了 `Sandbox` / `SandboxClaim` / `SandboxTemplate` / `SandboxWarmPool`，所以控制器和用户都可以像操作 Pod 一样用 Kubernetes API 操作这些自定义资源。

## 设计文档和当前实现的差异

README 和 architecture docs 都把 AgentCube 描述为 split-plane 架构：WorkloadManager 是 control plane，Router 是 data plane。这个方向和代码一致。

但设计文档中的 `Ready -> Paused -> Ready` sleep/resume 生命周期目前不是 main 的真实实现：

- `pkg/workloadmanager/garbage_collection.go` 当前做的是 idle / TTL 到期后删除 `Sandbox` 或 `SandboxClaim`，不是 pause。
- `pkg/router/session_manager.go` 对已有 session 只从 store 读取 sandbox，不会检查 `Paused` 状态，也不会 resume。
- `pkg/common/types/sandbox.go` 有 `Status string`，但当前状态主要是 `creating` / `ready` / `not-ready` 这一层，没有明确 `PausedAt`、`pauseTimeout`、`Deleted` 状态机。
- `pkg/agentd/agentd.go` 也只是基于 last-activity annotation 删除 sandbox，不是暂停/恢复。

所以 Sleep/Resume 不能只改 GC。它至少要跨：

- API / store：新增状态和 `PausedAt` / `pauseTimeout`。
- WorkloadManager：实现 pause/resume 调用或 CR spec 更新。
- Router：请求进入时如果 session paused，需要 resume before proxy。
- GC：拆成 `Ready -> Paused` 和 `Paused -> Deleted` 两段策略。
- agent-sandbox：确认底层 API 是 `Replicas=0/1`、`OperatingMode`，还是别的 suspend/resume 语义。
- e2e：验证 workspace/context 是否真的保留。

## 目录地图

以后改代码可以先按这个地图定位：

| 改动类型 | 先看文件 | 原因 |
| --- | --- | --- |
| AgentCube CRD 字段 | `pkg/apis/runtime/v1alpha1/*_types.go` | `AgentRuntime` / `CodeInterpreter` API 源头 |
| CRD / client-go 生成物 | `Makefile`, `hack/update-codegen.sh`, `client-go/`, `manifests/charts/base/crds/` | API 类型变更后必须生成 DeepCopy、client、informer、lister、CRD YAML |
| invocation 路由 | `pkg/router/handlers.go`, `pkg/router/session_manager.go` | Router 创建/复用 session、反向代理到 sandbox |
| session store | `pkg/common/types/sandbox.go`, `pkg/store/*.go` | Redis/Valkey 中保存的 session JSON 和索引语义 |
| sandbox 创建 | `pkg/workloadmanager/handlers.go`, `pkg/workloadmanager/workload_builder.go` | WorkloadManager 收请求、构造 Sandbox/SandboxClaim、写 store |
| agent-sandbox API 适配 | `pkg/workloadmanager/informers.go`, `k8s_client.go`, `workload_builder.go`, `codeinterpreter_controller.go` | GVR、scheme、Sandbox/SandboxClaim/SandboxWarmPool 字段都在这里 |
| warm pool | `pkg/workloadmanager/codeinterpreter_controller.go`, `workload_builder.go`, `test/e2e/e2e_test.go` | CodeInterpreter 的 warm pool 模板、claim 和 e2e 验证 |
| sandbox 内执行 | `pkg/picod/server.go`, `auth.go`, `execute.go`, `files.go` | PicoD 执行命令、文件操作和 JWT 鉴权 |
| auth / identity | `pkg/router/oidc.go`, `pkg/router/auth.go`, `pkg/workloadmanager/identity.go`, `pkg/mtls/` | 外部 OIDC、RLAC owner、Router->WM mTLS、PicoD JWT |
| 部署配置 | `manifests/charts/base/values.yaml`, `templates/` | Router/WM/Redis/SPIRE/OIDC/Keycloak 配置入口 |
| 端到端验证 | `test/e2e/run_e2e.sh`, `test/e2e/e2e_test.go`, `test/e2e/test_*.py` | runtime 行为、Python SDK、MCP、OIDC 的真实路径 |

## 核心对象

### AgentRuntime

源头：`pkg/apis/runtime/v1alpha1/agent_type.go`

关键字段：

- `spec.targetPort`：Router 转发时用来匹配 path 和端口。
- `spec.podTemplate`：最终变成 `agent-sandbox` 的 `Sandbox.spec.podTemplate`。
- `spec.sessionTimeout`：当前语义是 idle 后可被清理。
- `spec.maxSessionDuration`：当前语义是最大 TTL，到期删除。

AgentRuntime 更接近“用户自带 agent server”，AgentCube 主要负责创建 sandbox 和把 HTTP 请求转进去。

### CodeInterpreter

源头：`pkg/apis/runtime/v1alpha1/codeinterpreter_types.go`

关键字段：

- `spec.template`：CodeInterpreter sandbox 镜像、环境变量、命令、资源限制。
- `spec.ports`：默认未配置时 WorkloadManager 会用 `8080` / HTTP / `/`。
- `spec.warmPoolSize`：大于 0 时走 warm pool / `SandboxClaim` 路径。
- `spec.authMode`：默认 `picod`，WorkloadManager 会注入 `PICOD_AUTH_PUBLIC_KEY`。

CodeInterpreter 更接近标准 code execution runtime，默认对接 PicoD，所以它和 Router JWT、public key Secret、warm pool 的耦合更强。

### SandboxInfo

源头：`pkg/common/types/sandbox.go`

它是 AgentCube 自己的 session record，不是 Kubernetes CRD。关键字段：

- `Kind`：当前可能是 `Sandbox` 或 `SandboxClaim`，决定 GC/delete 删除哪个 K8s 资源。
- `Name` / `SandboxNamespace`：保存要删除或路由的对象名。
- `EntryPoints`：Router 反向代理需要的 path/protocol/endpoint。
- `SessionID`：外部请求 header 使用。
- `OwnerID`：OIDC/RLAC 用来判断已有 session 是否属于当前用户。
- `CreatedAt` / `ExpiresAt` / `IdleTimeout` / `LastActivityAt`：GC 和 TTL 的基础。
- `Status`：当前只支撑 ready/not-ready/creating 这类状态，尚未承载 Paused 状态机。

Store 中还有两个重要索引：

- `session:expiry`：按 `ExpiresAt` 排序，GC 找 TTL 到期对象。
- `session:last_activity`：按最近访问时间排序，GC 找 idle 对象。

## 请求链路

> invocation 在这里不是“函数调用”那么窄，而是一次用户对 agent 或 code interpreter 的运行请求。比如调用 `/v1/namespaces/{ns}/code-interpreters/{name}/invocations/run` 执行一段代码，或者调用 `/agent-runtimes/{name}/invocations/echo` 让某个 agent server 处理请求。Router 会根据有没有 `x-agentcube-session-id` 决定是创建新 session，还是复用已有 session。

### 新 session

一次没有 `x-agentcube-session-id` 的请求大致这样走：

1. Client 请求 Router：
   - `POST /v1/namespaces/{ns}/agent-runtimes/{name}/invocations/*path`
   - 或 `POST /v1/namespaces/{ns}/code-interpreters/{name}/invocations/*path`
2. `pkg/router/handlers.go` 的 `handleInvoke` 读取 session header。
3. `pkg/router/session_manager.go` 的 `GetSandboxBySession` 发现 sessionID 为空，调用 `createSandbox`。
4. Router 通过 `WORKLOAD_MANAGER_URL` 调 WorkloadManager：
   - `/v1/agent-runtime`
   - `/v1/code-interpreter`
5. WorkloadManager `handleSandboxCreate` 从 informer cache 读取 `AgentRuntime` 或 `CodeInterpreter`。
6. `workload_builder.go` 构造：
   - AgentRuntime/direct CodeInterpreter：`Sandbox`
   - warm-pool CodeInterpreter：`SandboxClaim` + 一个用于占位/等待的 simple `Sandbox`
7. WorkloadManager 先在 Store 写 placeholder，状态是 `creating`。
8. WorkloadManager 用 dynamic client 创建 `Sandbox` 或 `SandboxClaim`。
9. `SandboxReconciler` watch `Sandbox` Ready condition，通知等待中的 HTTP handler。
10. WorkloadManager 找到 Pod IP，检查 entrypoint 可连通，更新 Store 为完整 `SandboxInfo`。
11. WorkloadManager 返回 `sessionId`、`sandboxId`、`sandboxName`、`entryPoints`。
12. Router 反向代理请求到 sandbox entrypoint，并在响应 header 写回 `x-agentcube-session-id`。

### 复用 session

有 `x-agentcube-session-id` 时：

1. Router 从 Store 读取 `SandboxInfo`。
2. 如果启用了 OIDC，Router 检查 `OwnerID` 是否匹配当前 token subject；admin role 可绕过。
3. Router 在请求前后更新 `last_activity`。
4. Router 根据 `EntryPoints` 选择目标地址并 reverse proxy。

注意：当前没有 “session 存在但 sandbox paused，先 resume” 的逻辑。已有 session 被 GC 删除后，Router 只会返回 session not found，不会自动重建同一个 session。

### 删除 session

删除由 WorkloadManager internal API 或 GC 触发：

- 如果 `SandboxInfo.Kind == SandboxClaim`，删除 `SandboxClaim`。
- 否则删除 `Sandbox`。
- 成功后删除 Store 中 session JSON、expiry index、last_activity index。

这个设计解释了 #387 里为什么 warm pool path 要小心保存 claim 名：删除 warm-pool-backed session 时，AgentCube 应删除 claim，而不是误删被 claim adopt 出来的实际 sandbox 名。

## Control Plane: WorkloadManager

WorkloadManager 同时做 HTTP API server 和 controller-runtime manager。

关键职责：

- 提供 Router 内部调用的 `/v1/agent-runtime`、`/v1/code-interpreter` 创建 API。
- 运行 `SandboxReconciler`，等待 `agent-sandbox` 把 `Sandbox` 变成 Ready。
- 运行 `CodeInterpreterReconciler`，维护 `SandboxTemplate` 和 `SandboxWarmPool`。
- 运行 GC，删除 idle 或 expired session。
- 通过 informer cache 读取 AgentCube CRD 和 Pod。

几个实现点值得记住：

- `NewServer` 会初始化 K8s client、public key cache、informers、Store。
- `RunAndWaitForCacheSync` 当前只等 AgentRuntime、CodeInterpreter、Pod informer 同步。
- `createSandbox` 先写 Store placeholder 再创建 K8s CR，失败时 rollback，避免 orphaned store entry。
- 创建完成后还会 dial sandbox entrypoint，不能只看 `Sandbox Ready` condition。
- `GetSandboxPodIP` 先按 podName 找，再按 `runtime.agentcube.io/sandbox-name` label 和 ownerRef 找。

对依赖适配的影响：

- `agent-sandbox` API 版本变了，必须检查 `informer.go` 的 GVR、scheme 注册、dynamic client create/delete、builder 字段、Ready condition、Pod annotation。
- warm pool 行为变了，必须检查 `SandboxClaim` status 如何指向实际 `Sandbox`，否则 WorkloadManager 可能永远等错对象。

## Data Plane: Router

Router 是用户请求入口，负责：

- OIDC token 校验。
- RBAC role 检查。
- RLAC owner 检查。
- session create/reuse。
- Router -> WorkloadManager mTLS。
- Router -> sandbox reverse proxy。
- 给 PicoD 签发内部 JWT。

关键点：

- `handleInvoke` 是 AgentRuntime 和 CodeInterpreter 共享入口。
- Router 对新 session 不直接操作 Kubernetes，只调用 WorkloadManager。
- Router 对已有 session 只读 Store；因此 Store 中的 `EntryPoints` 必须准确。
- Router 会在请求前后更新 last activity，GC 依赖这个信号。
- `generateSandboxJWT` 会把 `session_id` 和可选 OIDC user 信息放进给 PicoD 的 token。

这意味着任何改动如果影响 entrypoint、session 状态、owner、JWT claim，都不能只改 WorkloadManager；Router 测试也要跟上。

## Sandbox 内部: PicoD

PicoD 是默认 code interpreter runtime 的 HTTP daemon：

- `/health` 不需要鉴权。
- `/api/execute` 执行命令。
- `/api/files` 上传、列目录、下载。
- API 路径都需要 `Authorization: Bearer <jwt>`。

PicoD 启动时必须从 `PICOD_AUTH_PUBLIC_KEY` 读 Router public key。这个 key 的来源链路是：

```text
Router creates/loads key Secret
  -> WorkloadManager caches public.pem
  -> CodeInterpreter template or direct sandbox env injects PICOD_AUTH_PUBLIC_KEY
  -> PicoD validates Router-signed JWT
```

所以如果 CodeInterpreter 走 `authMode: picod`，WorkloadManager 创建 sandbox 前需要 public key 已缓存；如果 custom image 不使用 PicoD，可以用 `authMode: none`。

## Store: Redis / Valkey

Store 是 Router replicas 和 WorkloadManager 之间的 session truth：

- `GetSandboxBySessionID`：Router 复用 session 时读。
- `StoreSandbox`：WorkloadManager 创建 placeholder 时写。
- `UpdateSandbox`：Sandbox Ready 后写完整 entrypoints。
- `UpdateSessionLastActivity`：Router 每次请求更新。
- `ListExpiredSandboxes` / `ListInactiveSandboxes`：GC 查询。

Redis 和 Valkey 语义基本保持一致，但实现不同：

- Redis 用 pipeline 和 Lua script 更新 last activity。
- Valkey 用 `DoMulti` 和 `EXISTS + ZADD`。

后续新增 session state 时，要同时更新：

- `pkg/common/types.SandboxInfo`
- Redis store
- Valkey store
- store tests
- GC tests
- Router session tests

## agent-sandbox 依赖边界

当前 main 使用：

- `sigs.k8s.io/agent-sandbox v0.1.1`
- `agents.x-k8s.io/v1alpha1` `Sandbox`
- `extensions.agents.x-k8s.io/v1alpha1` `SandboxClaim` / `SandboxTemplate` / `SandboxWarmPool`

AgentCube 对 agent-sandbox 的依赖不是一个单纯 module import：

- Go types：`sandboxv1alpha1.Sandbox`、`extensionsv1alpha1.SandboxClaim`。
- GVR：`SandboxGVR`、`SandboxClaimGVR`。
- Scheme：controller-runtime manager 需要 AddToScheme。
- Status condition：WorkloadManager 通过 `SandboxConditionReady` 判断 ready。
- Pod annotation：当前 main 还从 `controllers.SandboxPodNameAnnotation` 读 warm-pool pod name。
- Warm pool ownership：CodeInterpreter controller 创建 `SandboxTemplate` 和 `SandboxWarmPool`。
- Runtime behavior：SandboxClaim 到底创建/绑定哪个 Sandbox，Pod ownerRef 怎么连，NetworkPolicy 默认是什么。

这解释了为什么 #387 不应该只说“编译修复”。真正风险在 runtime 语义：

- compile pass 只能证明 import 和字段存在。
- unit test pass 只能证明本地逻辑拼装没错。
- e2e pass 才能证明 SandboxClaim、actual Sandbox、Pod、Router proxy、PicoD/JWT、Store/GC 能连起来。

## agent-sandbox 0.2 / 0.3 / 0.4 分段适配实验

为了避免把 `v0.1.1 -> v0.4.6` 的所有变化揉成一个大 diff，今天按版本演进补了两个干净实验分支：

- `/home/agentcube-agent-sandbox-v02`：branch `test/agent-sandbox-v02-adaptation`，commit `a4506d6`，目标 `sigs.k8s.io/agent-sandbox v0.2.1`。
- `/home/agentcube-agent-sandbox-v03`：branch `test/agent-sandbox-v03-adaptation`，head `142c56e`，目标 `sigs.k8s.io/agent-sandbox v0.3.10`。其中 `02cfae5` 是 runtime-aware 适配，`44f473c` 是 codegen 闭环修复，`142c56e` 是 fork CI 暴露后的 lint 最小修复。

两个分段实验已推到 fork 并创建 fork-only 归档 PR，用于保留阶段性 diff 和触发 fork CI，不作为 upstream review 请求：

- `v0.2.1`：fork PR [ranxi2001/agentcube#6](https://github.com/ranxi2001/agentcube/pull/6)，base `main`，head `test/agent-sandbox-v02-adaptation`。
- `v0.3.10`：fork PR [ranxi2001/agentcube#7](https://github.com/ranxi2001/agentcube/pull/7)，base `main`，head `test/agent-sandbox-v03-adaptation`。

版本来源：

```bash
go list -m -versions sigs.k8s.io/agent-sandbox
```

当前可见 release 序列是：

```text
v0.1.0-rc.0 v0.1.0-rc.1 v0.1.0-rc.2 v0.1.0 v0.1.1 v0.2.0 v0.2.1 v0.3.10 v0.4.0 v0.4.1 v0.4.2 v0.4.3 v0.4.5 v0.4.6
```

所以本轮选择：

- 0.2 系列最新：`v0.2.1`
- 0.3 系列最新：`v0.3.10`
- 0.4 系列当前 stable latest：`v0.4.6`，也就是 #387 的范围

### v0.2.1：静态上基本是 dependency-only

执行：

```bash
go get sigs.k8s.io/agent-sandbox@v0.2.1
go mod tidy
```

变更结果：

```text
go.mod | 12 ++++++------
go.sum | 30 ++++++++++++++----------------
2 files changed, 20 insertions(+), 22 deletions(-)
```

关键观察：

- `api/v1alpha1` 和 `extensions/api/v1alpha1` 仍存在。
- `SandboxPodNameAnnotation` 仍能被当前代码引用的路径覆盖，所以不会触发 `controllers.SandboxPodNameAnnotation` 编译失败。
- `SandboxClaim.Status.SandboxStatus.Name` 已经存在。
- `SandboxTemplate.Spec.NetworkPolicyManagement` 已经存在，默认 `Managed`、可设 `Unmanaged`。
- Kubernetes 依赖栈仍和当前 main 对齐在 `k8s.io/* v0.34.1`、`controller-runtime v0.22.2`，不需要升级 generated client 或 CRD schema。

测试结果：

```bash
go test ./pkg/workloadmanager ./cmd/workload-manager ./cmd/agentd -count=1
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
go test ./test/e2e -run '^$' -count=1
make build-all
make gen-check
git diff --check
```

结果均通过。

结论：`v0.2.1` 对当前 main 的源码级适配成本很低，基本可以作为 dependency-only 阶段理解。但这不等于 runtime 完全验证，因为 0.2 已经引入了 `NetworkPolicyManagement` 和 claim status name，编译通过不能证明 Router / WorkloadManager 到 sandbox Pod 的数据路径一定可达。

### v0.3.10：开始出现真实 warm pool 语义断点

先做最小依赖 bump：

```bash
go get sigs.k8s.io/agent-sandbox@v0.3.10
go mod tidy
go test ./pkg/workloadmanager ./cmd/workload-manager ./cmd/agentd -count=1
```

复现到的第一处编译失败：

```text
pkg/workloadmanager/handlers.go:272:63: undefined: controllers.SandboxPodNameAnnotation
```

源码确认：

- `v0.3.10/api/v1alpha1/sandbox_types.go` 里公开了 `sandboxv1alpha1.SandboxPodNameAnnotation`。
- `v0.3.10/controllers/sandbox_controller.go` 已经使用 `sandboxv1alpha1.SandboxPodNameAnnotation`。
- `v0.3.10/extensions/controllers/sandboxwarmpool_controller.go` 的 warm pool 不再只是管理 bare Pod，而是创建/管理 `Sandbox` 对象。
- `SandboxClaim` controller 会把实际采用的 sandbox 写入 `claim.Status.SandboxStatus.Name`。

这说明 `v0.3.10` 的问题不是简单换一个 import 就结束。仅修常量可以让代码继续编译，但 warm-pool-backed CodeInterpreter 仍可能等错对象：

```text
AgentCube old path:
create SandboxClaim named <session-name>
watch Sandbox with same <session-name>

agent-sandbox v0.3.10 path:
create SandboxClaim named <claim-name>
claim adopts or creates actual Sandbox named <status.sandbox.name>
Pod belongs to actual Sandbox
```

因此 0.3 实验分支做了 runtime-aware 最小适配：

- `handlers.go`
  - direct Sandbox 仍使用 `WatchSandboxOnce`。
  - SandboxClaim path 改成轮询 `SandboxClaim.Status.SandboxStatus.Name`。
  - 找到实际 adopted Sandbox 后，再按它的 `Ready` condition 和 annotation 查 Pod。
  - Store 仍保存 `SandboxClaim` 的名字，保证 delete / GC 删除 claim，而不是误删 adopted Sandbox。
- `k8s_client.go`
  - 增加 `getSandboxClaim` 和 `getSandbox`，用于 dynamic client 读取 claim 和 actual sandbox。
- `sandbox_helper.go`
  - placeholder 补 `CreatedAt`，claim path 最终 store 回写时保留 placeholder 的创建/过期时间，避免 adopted Sandbox 的时间字段覆盖 session TTL。
- `codeinterpreter_controller.go`
  - `SandboxTemplate.Spec.NetworkPolicyManagement` 显式设为 `Unmanaged`，避免 agent-sandbox 默认管理的 NetworkPolicy 阻断 AgentCube Router / WorkloadManager 到 sandbox Pod 的路径。
- `handlers_test.go`
  - 新增测试覆盖：claim 指向 adopted Sandbox，路由使用 adopted Sandbox / adopted Pod，Store 仍保存 claim name。
  - 新增测试覆盖：direct watcher nil / closed / empty sandbox 的失败路径。
- `codeinterpreter_controller_test.go`
  - 新增测试覆盖：新建和更新 `SandboxTemplate` 时都把 network policy 设为 `Unmanaged`。

补齐 codegen 后的最终 diff：

```text
client-go/clientset/versioned/fake/clientset_generated.go          |  17 +-
client-go/informers/externalversions/factory.go                    |   3 +-
client-go/informers/externalversions/runtime/v1alpha1/agentruntime.go | 4 +-
client-go/informers/externalversions/runtime/v1alpha1/codeinterpreter.go | 4 +-
go.mod                                                            |  43 ++---
go.sum                                                            | 141 +++++-----------
hack/update-codegen.sh                                            |   6 +-
manifests/charts/base/crds/...agentruntimes.yaml                  |  71 +++++++-
pkg/workloadmanager/codeinterpreter_controller.go                 |  15 +-
pkg/workloadmanager/codeinterpreter_controller_test.go            |  86 ++++++++++
pkg/workloadmanager/handlers.go                                   | 186 +++++++++++++++------
pkg/workloadmanager/handlers_test.go                              | 164 +++++++++++++++++-
pkg/workloadmanager/informers_test.go                             |   3 +-
pkg/workloadmanager/k8s_client.go                                 |  28 ++++
pkg/workloadmanager/sandbox_helper.go                             |   5 +
pkg/workloadmanager/workload_builder_test.go                      |  22 ++-
16 files changed, 590 insertions(+), 208 deletions(-)
```

其中手写生产代码是 4 个文件：`handlers.go`、`k8s_client.go`、`sandbox_helper.go`、`codeinterpreter_controller.go`。测试 4 个文件，依赖 2 个文件，codegen 脚本 1 个文件，generated files 5 个文件。`informers_test.go` / `workload_builder_test.go` 的新增改动来自 fork CI 的 `golangci-lint`：Kubernetes 官方 fake client 从 `NewSimpleClientset` 切到 `NewClientset`，AgentCube 自己生成的 fake client 暂无 `NewClientset`，所以集中封装并在 helper 上加局部 `nolint:staticcheck` 说明原因。

测试结果：

```bash
go test ./pkg/workloadmanager -count=1
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
go test ./test/e2e -run '^$' -count=1
make build-all
make gen-check
make lint
git diff --check
```

结果均通过。

fork PR #7 第一次 CI 暴露了本地静态验证未覆盖的 lint 问题：

```text
pkg/workloadmanager/workload_builder_test.go:393: SA1019: cubefake.NewSimpleClientset is deprecated
pkg/workloadmanager/workload_builder_test.go:353: SA1019: cubefake.NewSimpleClientset is deprecated
pkg/workloadmanager/informers_test.go:70: SA1019: cubefake.NewSimpleClientset is deprecated
pkg/workloadmanager/informers_test.go:66: SA1019: fake.NewSimpleClientset is deprecated
pkg/workloadmanager/handlers.go:96: cyclomatic complexity 16 of func `(*Server).handleSandboxCreate` is high (> 15)
```

修复方式：

- 官方 `k8s.io/client-go/kubernetes/fake` 改用 `fake.NewClientset()`。
- AgentCube generated fake client 只有 `NewSimpleClientset`，没有 `NewClientset`，因此封装 `newCubeClientset` 并在 helper 处写局部 `nolint:staticcheck`，避免在每个调用点重复豁免。
- `handleSandboxCreate` 抽出 `resolveSandboxOwnerID`，只降低复杂度，不改变身份解析语义。

修复后本地补跑：

```bash
go test ./pkg/workloadmanager -count=1
make lint
go test ./cmd/workload-manager ./cmd/agentd -count=1
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
go test ./test/e2e -run '^$' -count=1
make gen-check
make build-all
git diff --check
git diff --exit-code
```

结果均通过，commit 为 `142c56e test: fix v0.3 adaptation lint`。

过程卡点：第一次跑 `make gen-check` 失败，失败原因不是业务代码，而是旧 `hack/update-codegen.sh` 固定 `CODEGEN_VERSION="v0.34.1"`，并执行：

```bash
go get -d "k8s.io/code-generator@${CODEGEN_VERSION}" || true
```

在 0.3 分支上，这会扰动依赖解析：

```text
go: downgraded k8s.io/apiextensions-apiserver v0.35.0 => v0.34.1
go: downgraded k8s.io/code-generator v0.35.0 => v0.34.1
go: downgraded sigs.k8s.io/agent-sandbox v0.3.10 => v0.2.1
go: downgraded sigs.k8s.io/controller-runtime v0.23.3 => v0.22.4
```

修复方式：`44f473c` 把 `CODEGEN_VERSION` 改为从当前 `go.mod` 中的 `k8s.io/client-go` 读取，并用 `go mod download -json` 找 module cache 目录，不再用 `go get -d` 修改依赖选择。修复后 `make gen-check` 通过。

另一个过程注意：`make gen-check` 和 `make build-all` 都会触发 `generate` / `controller-gen` / `go mod tidy`，不能在同一个 worktree 并行跑。并行执行时曾出现过本地 module resolution 读到生成中间态的临时失败；串行重跑 `make gen-check`、`make build-all` 后均通过。

结论：从 0.3 开始，只改业务逻辑不够。只要目标版本带来 Kubernetes 0.35 依赖栈，就必须同时闭合 codegen 脚本和 generated files。

### 不同版本适配需要改动的部分

下面按“如果要把当前 AgentCube main 适配到该 agent-sandbox 版本”来拆改动面：

| 目标版本 | 必改部分 | 原因 | 本轮验证 |
| --- | --- | --- | --- |
| `v0.2.1` | `go.mod`、`go.sum` | API 仍是 `v1alpha1`，K8s 依赖仍是 `v0.34.1`，当前源码可直接编译 | 目标包、非 e2e 全量、e2e static、`make build-all`、`make gen-check` 均通过 |
| `v0.3.10` | `go.mod`、`go.sum` | `agent-sandbox` 升到 0.3 后带动 K8s 到 `v0.35.0`、controller-runtime 到 `v0.23.3` | 已通过 |
| `v0.3.10` | `pkg/workloadmanager/handlers.go` | `SandboxPodNameAnnotation` 迁到公开 API 包；warm pool claim 不再等同名 Sandbox，而要等 `SandboxClaim.Status.SandboxStatus.Name` 指向的 adopted Sandbox | `TestServerCreateSandboxClaimUsesAdoptedSandboxButStoresClaimName` 覆盖 |
| `v0.3.10` | `pkg/workloadmanager/k8s_client.go` | WorkloadManager 需要通过 dynamic client 读取 `SandboxClaim` 和实际 `Sandbox`，不能只靠 watcher 等同名对象 | workloadmanager 单测和非 e2e 全量通过 |
| `v0.3.10` | `pkg/workloadmanager/sandbox_helper.go` | warm-pool path 需要保留 placeholder 的 `CreatedAt` / `ExpiresAt`，避免 adopted Sandbox 时间字段覆盖 AgentCube session TTL | claim path 单测覆盖 |
| `v0.3.10` | `pkg/workloadmanager/codeinterpreter_controller.go` | 0.3 已有 `NetworkPolicyManagement`，默认 `Managed` 可能阻断 AgentCube Router / WorkloadManager 到 sandbox Pod 的访问路径；当前 AgentCube 需要显式 `Unmanaged` | SandboxTemplate 单测覆盖 |
| `v0.3.10` | `pkg/workloadmanager/*_test.go` | 新增行为不是语法迁移，必须固定 claim/adopted Sandbox、delete name、NetworkPolicy opt-out、watcher failure 语义；Kubernetes 0.35 lint 还要求处理 `NewSimpleClientset` deprecation | 新增单测和 `make lint` 通过 |
| `v0.3.10` | `hack/update-codegen.sh` | 旧脚本固定 `code-generator@v0.34.1` 且用 `go get -d`，会把 `agent-sandbox v0.3.10` 降级到 `v0.2.1` | 修复后 `make gen-check` 通过 |
| `v0.3.10` | `client-go/...`、`manifests/charts/base/crds/...` | Kubernetes 0.35 generator 和 OpenAPI schema 变化导致 generated diff；正式 PR 必须提交生成结果 | `make gen-check` 通过 |
| `v0.4.6` | 继承 0.3 的全部 runtime-aware 改动 | 0.4.6 仍是 `v1alpha1`，warm pool adoption / claim status / NetworkPolicy 问题同类 | #387 已验证 |
| `v0.4.6` | `go.mod`、`go.sum` 继续到 K8s `v0.35.4`，`hack/update-codegen.sh` 对齐 `code-generator v0.35.4`，generated files 重新生成 | 0.4.6 module 依赖栈比 0.3.10 更新，正式 PR 需要生成链路闭合 | #387 `make gen-check`、build、unit、runtime e2e 已验证 |
| `v0.4.6` | `test/e2e/e2e_test.go` | 需要验证新版 owner chain：warm pool 从旧的 `SandboxWarmPool -> Pod` 变为 `SandboxWarmPool -> Sandbox -> Pod` | #387 warm-pool e2e / fork CI 已覆盖 |
| `v0.5.0rc1` | imports / scheme / GVR 从 `v1alpha1` 迁到 `v1beta1` | rc1 已移除当前使用的 `api/v1alpha1` / `extensions/api/v1alpha1` package | Day18 已验证 |
| `v0.5.0rc1` | direct Sandbox builder：`Replicas -> OperatingMode` | `SandboxSpec.Replicas` 不再是 direct lifecycle 字段 | Day18 已验证 |
| `v0.5.0rc1` | warm-pool claim builder：`TemplateRef -> WarmPoolRef` | `SandboxClaimSpec.TemplateRef` 语义变化，claim 需要引用 warm pool | Day18 已验证 |
| `v0.5.0rc1` | e2e install manifest / clean cluster CRD 策略 | rc1 manifest 是 v1beta1-only，已有 v1alpha1 CRD 集群存在 `storedVersions` 原地升级问题 | Day18 clean k3d 验证通过，原地升级未覆盖 |

本轮 0.2 / 0.3 的“跑通”范围是本地静态、生成、构建和单元级验证；没有重新跑真实 k3s/k3d runtime e2e。真实 runtime e2e、SDK、MCP、math-agent 的完整证据目前主要来自 #387 的 `v0.4.6` 和 Day18 的 `v0.5.0rc1` 实验。

2026-06-22 又补了 fork PR 存档：#6 / #7 的目的不是合并到 fork `main`，而是让 GitHub Actions 对两个 checkpoint 独立跑一遍，形成可链接的 CI 证据。PR title 使用 `[WIP]`，避免误合并这些中间态适配分支。

最终 fork CI 结果：

- [ranxi2001/agentcube#6](https://github.com/ranxi2001/agentcube/pull/6)：head `a4506d6`，9/9 checks 全部通过，包括 build、coverage、e2e-test、golangci-lint、Codegen Check。
- [ranxi2001/agentcube#7](https://github.com/ranxi2001/agentcube/pull/7)：第一次 fork CI 失败在 `golangci-lint`，已由 `142c56e` 修复；最终 head `142c56e`，10/10 checks 全部通过，包括 build、coverage、e2e-test、golangci-lint、Codegen Check。

### 与 #387 v0.4.6 的对比

#387 当前 `v0.4.6` 适配分支 changed files 是 15：

```text
15 files changed, 672 insertions(+), 273 deletions(-)
```

和 0.3 实验相比，核心业务逻辑没有大一个数量级。主要增加来自：

- `agent-sandbox v0.4.6` 带动 Kubernetes 依赖到 `v0.35.4`，而 0.3 是 `v0.35.0`。
- #387 修了 `hack/update-codegen.sh`，否则 `make gen-check` 会反向降级依赖。
- #387 包含 `client-go` generated files 和 CRD generated files，用于保证正式 PR 的生成链路闭合。
- #387 扩展了 e2e warm-pool Pod ownerRef 检查，使测试覆盖新版 `SandboxWarmPool -> Sandbox -> Pod` 链路。

分段适配带来的价值不是让最终 PR 一定更小，而是把演进原因拆清楚：

| 阶段 | 主要变化 | 文件数量 | 结论 |
| --- | --- | --- | --- |
| `v0.1.1 -> v0.2.1` | 依赖更新，API 仍兼容 | 2 | 静态适配几乎无代码改动 |
| `v0.2.1 -> v0.3.10` | warm pool 改为 full Sandbox adoption；annotation 常量迁公开 API；NetworkPolicy default 风险出现；K8s 0.35 生成链路变化；lint 开始暴露 fake client deprecation / handler complexity | 16 | 开始需要 runtime-aware 代码适配、单测、codegen 脚本、generated files 和 lint 闭环 |
| `v0.3.10 -> v0.4.6` | 依赖 patch 继续升级；正式 PR 需要 codegen / generated / e2e 闭环 | 15 | review 重点是生成链路和运行证据，不只是业务代码 |
| `v0.4.6 -> v0.5.0rc1` | `v1alpha1 -> v1beta1`、`TemplateRef -> WarmPoolRef`、`Replicas -> OperatingMode` | 另见 Day18 | 不应混入 #387，应该独立 follow-up |

对下周 #387 review 的帮助：

- 可以解释为什么 `v0.2.1` 编译通过不代表 `v0.4.6` 只需要一个 import fix。
- 可以解释为什么 `go.mod` 的 K8s stack 更新是 agent-sandbox 版本驱动，不是随意 cleanup。
- 可以解释为什么小文件 `k8s_client.go` / `sandbox_helper.go` 必须改：claim path 需要读 actual Sandbox，同时 Store 仍要保留 claim name。
- 可以解释为什么 generated files 和 `hack/update-codegen.sh` 在正式 PR 中是必要的：0.3 实验证明旧脚本会把目标依赖降回旧版本。

## Codegen 和 generated files

AgentCube 有自己的 CRD API 类型，因此有生成代码：

- `pkg/apis/runtime/v1alpha1/zz_generated.deepcopy.go`
- `client-go/clientset/versioned/...`
- `client-go/informers/externalversions/...`
- `client-go/listers/runtime/v1alpha1/...`
- `manifests/charts/base/crds/runtime.agentcube.volcano.sh_*.yaml`

`make gen-all` 做两类生成：

- `controller-gen`：CRD YAML + DeepCopy。
- `hack/update-codegen.sh` / `k8s.io/code-generator`：typed client、fake client、informer、lister。

`make gen-check` 的含义不是“编译”，而是重新生成后要求 git diff 为空。它用来保证提交里的 generated files 和当前 API types / generator version 一致。

后续原则：

- 不手工修 generated file 的小注释或格式，除非改 generator 或 API 类型后重新生成。
- 如果升级 Kubernetes / code-generator，必须解释 generated diff 来源。
- 如果 generated diff 和功能无关，要拆分或说明它是依赖升级必然结果。

## Auth 和身份链路

> auth 在代码和文档里经常混用，最好拆成三层理解：authentication 是“你是谁”，authorization 是“你能不能做这件事”，request signing 是“Router 转发到 sandbox 时证明这条内部请求可信”。AgentCube 里 OIDC/JWT token 校验解决 authentication，role/RLAC owner 检查解决 authorization，Router 给 PicoD 签 JWT 解决 request signing。

目前有三层身份：

1. 外部用户 -> Router：
   - `pkg/router/oidc.go` 校验 OIDC token、issuer、audience、exp、nbf、roles。
   - `requireRole` 做 role gate。
2. Router -> WorkloadManager：
   - 可用 mTLS。
   - Router 还会把用户 subject 签成 `X-AgentCube-User-Identity`，WorkloadManager 解出 ownerID。
3. Router -> PicoD：
   - Router 用内部私钥签 JWT。
   - PicoD 用 `PICOD_AUTH_PUBLIC_KEY` 验证。

RLAC owner 语义：

- 新建 session 时，WorkloadManager 把 ownerID 写入 K8s resource annotation/label 和 `SandboxInfo.OwnerID`。
- 复用已有 session 时，Router 对比当前 OIDC subject 和 `SandboxInfo.OwnerID`。
- admin role 可绕过。
- 如果启用了 OIDC 但旧 sandbox 没有 owner record，当前 Router fail-closed。

后续改 session / store / migration 时，这个 owner 字段不能丢。

## 当前测试分层

适配类工作不能只看一个测试命令。推荐按风险分层：

| 层级 | 覆盖内容 | 典型命令 |
| --- | --- | --- |
| L0 编译/生成 | API、client-go、CRD、binary | `make gen-check`, `make build-all` |
| L1 单元测试 | builder、store、router auth/proxy、GC | `go test ./pkg/...` 或重点 package |
| L2 race/coverage | 并发 watcher、store、controller helper | `go test -race ./pkg/workloadmanager`, coverage workflow 命令 |
| L3 e2e static compile | e2e package 可编译 | `go test ./test/e2e -run '^$'` |
| L4 runtime e2e | k3s/k3d 真实 Router/WM/sandbox/Store | `make e2e` 或 `test/e2e/run_e2e.sh` |
| L5 SDK / agent | Python SDK、LangChain、MCP、math-agent LLM | `test/e2e/test_*.py`, math-agent quick validate |

对 #387 / agent-sandbox 适配，至少需要：

- direct CodeInterpreter e2e。
- warm-pool CodeInterpreter e2e。
- Router session reuse。
- delete / GC cleanup。
- Python SDK or MCP path。
- math-agent LLM e2e，证明用户级 agent workflow 没断。

## 以后改代码的阅读顺序

### 改 Router / invocation

先读：

1. `pkg/router/server.go`
2. `pkg/router/handlers.go`
3. `pkg/router/session_manager.go`
4. `pkg/common/types/sandbox.go`
5. `pkg/store/*`

然后设计测试：

- 无 session 创建。
- 有 session 复用。
- session not found。
- owner mismatch。
- target entrypoint 不可达。
- request/response header 是否保留 `x-agentcube-session-id`。

### 改 WorkloadManager / sandbox lifecycle

先读：

1. `pkg/workloadmanager/handlers.go`
2. `pkg/workloadmanager/workload_builder.go`
3. `pkg/workloadmanager/sandbox_controller.go`
4. `pkg/workloadmanager/k8s_client.go`
5. `pkg/workloadmanager/sandbox_helper.go`
6. `pkg/workloadmanager/garbage_collection.go`

然后设计测试：

- create failure rollback。
- watcher nil/closed/timeout。
- entrypoint probe failure。
- direct Sandbox path。
- SandboxClaim / warm-pool path。
- Store placeholder -> ready update。
- delete `Sandbox` vs delete `SandboxClaim`。

### 改 agent-sandbox 版本

先做源码审计：

1. `go list -m -json sigs.k8s.io/agent-sandbox@latest`
2. `go list -m -versions sigs.k8s.io/agent-sandbox`
3. 检查 package 是否存在：`api/v1alpha1`、`extensions/api/v1alpha1`、`api/v1beta1`、`extensions/api/v1beta1`
4. 对比 `SandboxSpec`、`SandboxClaimSpec`、`SandboxTemplateSpec`、`SandboxWarmPoolSpec`
5. 对比 manifests 安装的 CRD versions 和 storedVersions 行为

再改代码：

- import / scheme / GVR。
- direct Sandbox builder。
- SandboxClaim builder。
- CodeInterpreter controller warm pool。
- Pod IP / ownerRef / annotation lookup。
- e2e install manifest 版本。

最后跑：

- WorkloadManager 单测。
- `make gen-check`。
- `make build-all`。
- runtime direct + warm-pool e2e。
- SDK / MCP / math-agent。

### 改 Sleep/Resume

不要从 GC 单点切入。先设计状态机：

```text
Ready -> Paused -> Ready
Paused -> Deleted
Any active state -> Deleted by maxSessionDuration
```

需要回答：

- `Paused` 是 AgentCube store 状态，还是 agent-sandbox CR status？
- pause 底层动作是什么：`replicas=0`、`OperatingMode`、API call，还是删除 Pod 但保留 PVC/workspace？
- workspace/context 如何保存？
- Router 遇到 Paused session 等多久？失败返回什么状态码？
- `sessionTimeout` 和 `pauseTimeout` 是否分开配置？
- warm-pool-backed CodeInterpreter 首版是否支持 pause？

测试必须包含：

- idle 后进入 paused，但 Store 不删除 session。
- paused 后新请求能 resume 并保持 workspace 文件。
- pauseTimeout 后删除。
- maxSessionDuration 到期删除。
- 多 Router replica 下 last_activity 和状态一致。

## 当前理解盲区

仍需后续补读或实测：

- agent-sandbox controller 内部完整状态机，特别是 `SandboxClaim` adopt / warm pool / NetworkPolicy 逻辑。
- v0.5.x `v1beta1` 的正式 release 后 API 是否继续变化。
- Kuasar / MicroVM / RuntimeClass 在有 `/dev/kvm` 的真实机器上的行为。
- Volcano scheduler 与 AgentCube 当前 runtime path 的实际耦合程度，目前主链路更多是 Kubernetes + agent-sandbox。
- Python SDK 的完整 auth/session 封装还需要单独深读。

## 结论

以后看 AgentCube 改动，最重要的是先判断改动落在哪条边界：

- CRD API 边界：类型、CRD、generated clients。
- Control plane 边界：WorkloadManager、agent-sandbox CR、Store。
- Data plane 边界：Router、session、reverse proxy、PicoD JWT。
- Runtime 边界：Pod/sandbox、PicoD、workspace、entrypoint。
- Auth 边界：OIDC/RLAC、mTLS、PicoD JWT。

#387 这类依赖适配看起来像 `go.mod` bump，但本质是跨 Control plane、generated code、warm pool runtime、network policy、e2e setup 的兼容工作。后续 review 和 PR 材料必须持续用“源码依据 + 运行验证 + 最小修改范围”来解释，而不能只复述提案。
