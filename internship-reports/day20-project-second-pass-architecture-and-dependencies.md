# Day 20 - AgentCube Project Second-Pass Architecture and Dependency Study

日期：2026-06-22

## 目标

对 AgentCube 做第二轮项目理解，不再只停留在目录结构，而是建立以后改代码、做依赖适配、准备 review 答辩时能复用的 mental model。

本轮重点回答：

- AgentCube 当前 main 的真实实现是什么，不只看 README / design docs 的目标状态。
- 一次 `AgentRuntime` / `CodeInterpreter` invocation 从 Router 到 sandbox 内部怎么走。
- `agent-sandbox`、Kubernetes client-go/codegen、Redis/Valkey、PicoD、OIDC/mTLS 分别卡在哪些边界。
- 后续做 `agent-sandbox v0.4.6` / `v0.5.x` / Sleep-Resume 适配时，应该先看哪些文件，设计哪些测试。

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
