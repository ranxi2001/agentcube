# Day 54: Issue #444 Router -> PicoD mTLS design screening

日期：2026-07-21

目标：只读分析 [Issue #444](https://github.com/volcano-sh/agentcube/issues/444) 是否方向成立、是否可以直接认领实现，以及它与当前认证模型、既有维护者决定和相邻工作的关系。

代码基线：`upstream/main@58422c02b673daf1cb7991f22e4e1476e97ea1f3`

社区快照：`2026-07-21 16:44 CST`

## 1. 结论先行

Issue #444 识别出的现状是对的：Router -> PicoD 当前仍是明文 HTTP 加 Router 签名 JWT，并没有 mTLS。复用现有 `pkg/mtls`、SPIRE 和 `spiffe-helper` 也确实是合理的技术起点。

但它现在只能作为设计讨论，不能直接当成可认领的实现任务。主要原因不是代码量，而是四个安全与 ownership 合同尚未闭合：

1. PicoD 身份应该是全局、namespace 级还是 Pod 级；
2. mTLS 私钥能否交给执行不可信代码的 PicoD 容器；
3. transport policy 是 operator 全局策略，还是允许每个 CodeInterpreter 选择；
4. JWT 是否继续承担 session/user binding，而当前 PicoD 实际并不验证这些 claims。

此外，#444 直接受已认领的整体认证模型 [#441](https://github.com/volcano-sh/agentcube/issues/441) 约束，且没有解释为何可以推翻已合并 PR [#293](https://github.com/volcano-sh/agentcube/pull/293) 中撤回 PicoD mTLS 的明确维护者决定。因此当前建议是等待/参与设计对齐，不 `/assign`，不开始 Helm、CRD、PicoD listener 或 WorkloadManager 注入实现。

> 注释：这里的“不能直接实现”不是否定 mTLS 的价值，而是说认证边界本身还没有确定。先写代码会把尚未决定的安全策略固化进 API、SPIFFE ID 和集群 RBAC。

## 2. Issue 与 ownership 状态

| 项目 | 当前证据 | 判断 |
| --- | --- | --- |
| #444 | open，`kind/enhancement`，0 comment，0 assignee，无 `/assign`，无 cross-reference | 没有 formal owner |
| Issue 作者 | `@MregXN` 写明“once consensus lands”后愿意开 focused PR | 条件性 prospective ownership，不能当作完全无人负责 |
| #243 | 旧 umbrella 已列出 Router -> PicoD mTLS 与 hybrid auth checkpoints | #444 是旧问题的 focused revival，不是全新 greenfield |
| #441 | `@acsoto` 创建，当前由 `@0YHR0` 认领；要求先统一“谁认证谁、谁授权、谁拿 Kubernetes credential 执行” | #444 的直接上游设计 blocker |
| #293 | merged；维护者要求撤回全部 PicoD 相关 mTLS 变更 | 当前最强的实现范围 precedent |
| #402 | open docs PR，主张 PicoD 保持 HTTP + JWT、只给 Router <-> WM mTLS；37 commits behind，无 human review | 相反方向的未决提案，不是共识，但必须交叉说明 |
| #352 | open/dirty，处理 shared JWT 导致的 cross-sandbox replay，已有 human security review | #444 所依赖的 JWT session identity 仍未解决 |
| #374 | `spiffe-helper` 首次证书就绪/CrashLoop 问题，已由 `@avinxshKD` 认领 | 证书启动生命周期已有 owner |
| #397/#398 | 默认 `authMode` parity 已认领且 PR 已 `/lgtm` | 新增 auth mode 会与当前 API 语义工作重叠 |

没有发现隐藏的公开 mTLS 实现分支、`PicoDSPIFFEID` 代码或同题 PR。空 assignee 仍不足以证明 #444 可以直接接手，因为 #441 已经拥有更高层合同，且 #444 作者自己表达了后续实现意愿。

## 3. 当前代码合同

### Router -> PicoD

- `pkg/router/handlers.go:377-399` 为 AgentRuntime 和 CodeInterpreter 共用 `forwardToSandbox`；它使用同一个 `Server.httpTransport`，并为 sandbox 请求附加 Router JWT。
- `pkg/router/server.go:87-99` 创建全局复用的 plain `http.Transport`，`IdleConnTimeout` 为 0，因此连接可长期复用。
- `pkg/common/types/sandbox.go:26-46` 的持久 `SandboxInfo` 只有 runtime resource kind、endpoint、session 和 owner；没有原始 AgentRuntime/CodeInterpreter kind，也没有 auth/transport mode。
- `pkg/router/handlers.go:153-179` 根据 `SandboxEntryPoint.Protocol` 构建 `http://` 或 `https://` URL。

> 分析：因此不能简单“给共享 transport 加 TLS 后强制所有 endpoint 改成 https”。TLS 配置本身可以与 HTTP endpoint 共存，但协议选择和 mode 必须从 CodeInterpreter 配置可靠传播到 Store/Router，且不能误改 AgentRuntime 或 `authMode:none` 的 custom image。

### JWT application authentication

- `pkg/router/handlers.go:277-306` 生成的 JWT 包含 `session_id`，启用 OIDC 时还可能包含 `user_sub` / `user_email`。
- `pkg/picod/auth.go:83-132` 只校验 RSA signature、过期时间和 issued-at；没有验证 `iss`、`aud`、`session_id` 或 user claim。
- 所有 PicoD 都读取同一个 Router public key，因此当前任意有效 Router JWT 在 5 分钟有效期内可被另一个 PicoD 接受。

> 分析：#444 写“JWT 负责区分具体 sandbox/user”超过了当前实现能证明的范围。JWT 携带这些字段不等于 PicoD 消费并约束这些字段；open PR #352 正是在处理这个缺口。

### CodeInterpreter auth mode

- `pkg/apis/runtime/v1alpha1/codeinterpreter_types.go:77-83` 把 `authMode` 定义为 sandbox application authentication；当前枚举只有 `picod` 和 `none`。
- `pkg/workloadmanager/workload_builder.go:311-337` 的行为是根据该字段注入/检查 `PICOD_AUTH_PUBLIC_KEY`。
- `TargetPort.Protocol` 已独立表达 HTTP/HTTPS transport。

因此 #444 同时提出 per-workload `AuthModeType: mtls` 和 global `--picod-auth-mode` 是两个互相冲突的 ownership 模型。若 mTLS 与 JWT 要 stack，transport 与 application auth 应先被建模为两个正交维度，不能让 `mtls` 同时意味着“TLS + JWT”，而 `picod` 只意味着 JWT key injection。

## 4. 已有维护者方向

在 merged PR #293 中，`@hzxuzhonghu` 明确要求：

> Please revert all the picod related change, router -> agent or codeinterpreter, this path is special, we cannot fully control it

证据：[review 4249934500](https://github.com/volcano-sh/agentcube/pull/293#pullrequestreview-4249934500)。更早的评论还直接询问：PicoD/CodeInterpreter 由 end user 声明时，证书如何交付。

这不是“永远禁止 PicoD mTLS”的最终判决，但它建立了当前 scope precedent：任何重新引入方案都必须先证明平台为什么现在能够安全控制这条用户 workload 路径。#444 目前只说 CodeInterpreter 比 AgentRuntime 更受控，还没有回答私钥暴露、ServiceAccount 冒用、custom image、warm pool 和 permission ownership。

#441 的时间更近，且由 maintainer 创建。它明确要求在继续 auth/RBAC 变化前先统一：

- external API boundary；
- authenticated identity 与 Kubernetes execution identity 的区别；
- namespace/session ownership authorization 应由谁负责。

因此 #444 最合理的关系应是 #441 对齐后的 focused child，而不是平行地冻结一套新模型。

## 5. 阻断设计问题

### 5.1 私钥会暴露给用户执行的代码

#444 的方案让 `spiffe-helper` 把 cert/key/bundle 写入 shared `emptyDir`，再把该卷挂到 PicoD。

当前 PicoD 的现实边界是：

- `docker/Dockerfile.picod:30-32` 明确以 root 运行；
- `pkg/picod/execute.go:91-125` 用 `exec.CommandContext` 原样执行任意用户命令，没有降 UID；
- 当前 `spiffe-helper` 模式把 key 写成 `0640`，供同 Pod app container 读取。

所以用户可以通过 PicoD execute API 读取并导出本 Pod 的 SVID private key。SPIRE 会给每个 workload 生成不同 key/cert，但 #444 让所有证书携带同一个 namespace-less PicoD SPIFFE URI；未过期的泄漏 SVID 因而可以冒充任意 PicoD class identity。

这里不能把“跨 sandbox 攻击已发生”写成事实：最终攻击还需要错误路由、网络重定向或另一个可达 endpoint。但 credential exfiltration 本身由当前 PicoD 执行模型与拟议挂载方式直接证明。

可选设计需要先由 maintainer 决定，例如：

- TLS 在独立 proxy sidecar 终止，私钥卷不挂给执行用户命令的容器；
- 或先让 user command 运行在不能读服务器凭据的独立 UID/隔离边界。

直接把 private key 挂给当前 PicoD 不应成为首版实现。

### 5.2 ServiceAccount 不是防冒用门禁

#444 继承旧 auth proposal 的说法：固定 `agentcube-sandbox` ServiceAccount 能阻止其他 workload 获得同一身份，admission policy 只是 defense in depth。

Kubernetes 官方 [RBAC good practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/#workload-creation) 明确说明：能在 namespace 创建 workload 的主体，通常也能让 Pod 使用该 namespace 的任意 ServiceAccount，从而隐式获得其身份/权限。Kubernetes 没有通用的 `use serviceaccount` RBAC gate。

因此 namespace-less SPIFFE ID 加 `app=picod` 和固定 SA 并不足以防伪。Admission enforcement 或更强的 namespace/identity model 是安全前置，不是可选加固。

Issue 还把 actor 写成“只允许 WorkloadManager 创建带 label 的 Pod”，但实际 Pod 是 agent-sandbox controller 根据 Sandbox/SandboxTemplate 创建；策略必须按真实 creator/owner chain 设计。

### 5.3 现有 server helper 不验证 Router SPIFFE ID

`pkg/mtls/loader.go:25-30,43-52,94-132` 明确接受任意由受信 CA 签发的 client certificate。它只验证 chain 和 clientAuth usage，不验证 URI SAN。

Router client 侧 `LoadClientConfig` 会验证 server exact SPIFFE ID，但 PicoD 若直接复用 `LoadServerConfig`，不会验证 caller 是 Router。这与 #444 sequence diagram 中“双方验证 URI SAN”以及 zero-trust workload identity 的叙述不一致。

若安全合同要求只有 Router 能调用 PicoD，需要新的 server-side peer authorizer/expected-client-ID API，或在 PicoD application layer 校验 peer identity。若决定任何受信 workload 都能连接，则必须明确 JWT 才是 caller authorization，而不能宣称 TLS 层完成 Router identity 验证。

### 5.4 JWT 当前不承担 session binding

由于 PicoD 不检查 `session_id` / `user_sub`，mTLS 与现有 JWT 简单叠加仍不能证明请求属于当前 sandbox。至少需要先决定：

- PicoD 是否接收并持有 expected session/audience；
- warm-pool Pod 在 adoption 前没有 session，binding 何时建立、如何防重放；
- 还是由 per-Pod SPIFFE identity 绑定 endpoint，用户授权完全留在 Router。

这与 #352 的 per-session JWT work 直接相邻，不能各自独立实现后再拼接。

### 5.5 global policy 与 workload choice 冲突

#444 一边提议新增 `CodeInterpreter.Spec.AuthMode=mtls`，另一边又说使用 single global switch、不要 per-workload branching。

如果 tenant 能写 CodeInterpreter，per-workload `jwt` / `none` 会成为 operator mTLS policy 的 downgrade 开关。反过来，如果 operator 全局开启 mTLS，custom `authMode:none` image、direct SDK override 和 AgentRuntime path 的兼容边界都需要显式定义。

正确的第一个问题不是 flag 名字，而是谁拥有 transport security policy。任何 fallback 都必须 fail closed，不能在 TLS handshake 失败后静默回退到明文 HTTP。

### 5.6 生命周期与 latency 证据不足

- WorkloadManager 在 Pod 调度前不知道目标 node，不能按 #444 所写直接检查该 node 的 SPIRE socket path；应由 scheduling/node prerequisite、sidecar readiness 或 Pod failure contract 负责。
- #374 已证明初始 SVID 文件存在启动 race，且该问题已有 owner；#444 不能复制一套未协调的 wait/probe 逻辑。
- 证书轮换只影响新 TLS handshake，既有 keep-alive connection 不会自动重新认证。Router transport 当前 `IdleConnTimeout: 0`，因此 SVID 到期/撤销与最大连接寿命需要明确。
- `20-50ms` handshake 与 `200-500ms` attestation 是文档估计，不是当前 AgentCube benchmark。Router transport 会复用连接，成本主要落在每个 sandbox 的首个 connection，而不是每次 invocation。

默认开/关决策应基于 cold/warm、direct/warm-pool、连接复用和 rotation 后重连的可复现实测，而不是只引用旧设计数字。

## 6. Discovery card

- Surface: current authentication boundary + dependency evolution + configuration fan-out.
- Observable trigger: #444 proposes bringing PicoD into mTLS mesh.
- Actual behavior: Router -> PicoD is HTTP + shared Router JWT; only Router <-> WorkloadManager uses mTLS.
- Expected contract: unresolved; #241 aspirational design、#293 implementation scope、#402 current-state rewrite 和 #441 umbrella 尚未收敛成一个方向。
- Producer -> transport -> consumer -> owner: Router -> HTTP(S) reverse proxy -> PicoD; Router owns routing/RLAC/JWT signing，PicoD owns request verification，WorkloadManager owns sandbox desired state，agent-sandbox controller owns Pod creation。
- Supported path: CodeInterpreter direct and warm-pool sessions; AgentRuntime shares Router proxy code but uses user-defined runtime endpoints.
- Recovery/lifecycle: cert startup/rotation、warm-pool adoption、session deletion 和 connection re-authentication 均未在 #444 闭合。
- Decisive evidence: merged #293 maintainer scope decision; main source showing root arbitrary execution、generic client cert acceptance 和 missing JWT claim checks。
- Related work: #243、#293、#352、#374、#397/#398、#402、#441。
- Current owner: #444 no formal assignee；#441 `@0YHR0`；#374/#397 `@avinxshKD`；#444 author offers conditional follow-up PRs。
- Artifact class: enhancement/design discussion, not observed bug.
- Smallest next change: first resolve the four security contracts; no production code should be selected yet.
- Focused validation after consensus: correct/wrong client URI, correct/wrong server URI, JWT wrong session/audience, SPIRE unavailable, rotation/reconnect, direct/warm pool, `picod`/`none`, AgentRuntime unaffected, connection-reuse latency.
- Compatibility/non-goals: do not silently remove direct/custom HTTP modes; do not make agent-sandbox controller or #374 work part of an unbounded first PR.
- Unknowns requiring maintainer decision: identity granularity、key isolation、policy owner、JWT binding/future。

Gate result:

| Gate | Result | Reason |
| --- | --- | --- |
| Evidence | partial pass | current missing mTLS and code surface are proven; performance claims are not measured |
| Reachability | risk proven | key exposure and SA spoof preconditions follow supported workload creation/execute paths |
| Ownership | fail | #441 assigned; adjacent #374/#397 owners; #444 author has prospective intent |
| Direction | fail | #293 precedent, #402 opposite proposal, #441 unresolved umbrella |
| Scope | fail | API, Router, PicoD, WM, SPIRE, RBAC/admission, SDK and E2E are coupled |
| Validation | partial | unit tests feasible; live SPIRE/security/latency matrix needs a suitable cluster |

## 7. Recommended participation

当前不 `/assign` #444，也不从它列出的 `PicoDSPIFFEID -> PicoD listener -> Router transport -> SPIRE wiring -> WM auth mode` 顺序开始写代码。

更合理的社区动作是等待 maintainer 回应，或准备一条很短的 design clarification，集中问四件事：

1. #444 是否应成为 #441/#243 的 child，并明确推翻/修订 #293 的 PicoD scope；
2. TLS private key 是否必须与 code-execution container 隔离；
3. PicoD identity 粒度与 server-side Router identity verification；
4. transport mode owner 与 JWT session binding 的最终关系。

任何 upstream comment 仍需用户确认 exact English text 和 target。当前没有发布、认领、mention 或编辑 #444。

## 8. Evidence limits

- 本轮读取了 issue/PR 全线程、当前 main 源码、Helm/RBAC 与官方 Kubernetes RBAC 文档。
- 未在 live SPIRE cluster 运行 Router -> PicoD mTLS；因此没有宣称 handshake latency、rotation/revocation SLA 或完整攻击链已经观测。
- #402 没有人类 review 且落后 main，记录它只为证明方向冲突，不把它当维护者共识。
- #352 dirty/stale 但仍 open；记录它为相邻 owner/security contract，不宣称其实现已被接受。

## 9. Upstream comment publication

用户确认 exact English text 后，于 `2026-07-21 17:02 CST` 发布 [Issue #444 design comment](https://github.com/volcano-sh/agentcube/issues/444#issuecomment-5032085711)。发布前回读确认 issue 仍为 open、无 assignee、无既有评论，讨论前提没有变化。

评论以 `main@58422c` 为证据锚点，用 234 visible words / 6 nonblank lines 压缩为四个 implementation contract：private-key isolation、peer/session binding、ServiceAccount attestation 和 transport-policy ownership；结尾建议先把工作定位为 #441 的 focused child，并对齐 #293 与 #352。GitHub API 回读确认发布账号为 `ranxi2001`、正文与确认稿一致；没有附加 `/assign`、Prow 命令、label、review request 或额外 mention。

下一步只等待作者或 maintainer 回应这些合同。没有新回复或新设计证据时，不自动追评、认领或启动实现。
