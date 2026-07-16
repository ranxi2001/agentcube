# Day 47：OpenSandbox 近期 Release 与 Merged PR 趋势调研

日期：2026-07-16

## 目标

Day21/22 在 2026-06-22 基于 OpenSandbox `3d40414e794d` 完成了源码调研和 Docker runtime
smoke。近一个月 OpenSandbox 合并速度很快，本轮重新回答四个问题：

1. 最近正式 release 真正交付了哪些能力。
2. 最近 merged PR 的投入主要集中在哪些方面。
3. 哪些能力已经发布，哪些只存在于 `main`。
4. 这些变化如何校准 AgentCube 的 runtime/provider、pool、security 和 session lifecycle 判断。

> 注释：这里的 OpenSandbox 指
> [`opensandbox-group/OpenSandbox`](https://github.com/opensandbox-group/OpenSandbox)，不是
> 阿里云 AgentBay 产品。仓库已从旧的 `alibaba/OpenSandbox` 组织路径迁移，旧链接可能仍会
> 重定向，但本报告统一使用当前官方组织。

## 一页结论

OpenSandbox 最近没有把主要精力放在“再增加一个底层 runtime backend”，而是在把已有
Docker/Kubernetes/provider 体系推进成生产级 sandbox platform：

- **execd 内层隔离**：bwrap isolated session 从 create/delete 扩展到 run-once、scoped
  session、list、bind mount、userns 和 `attach(sessionId)`。
- **低延迟与生命周期闭环**：多语言 SDK 补 client-side pool、Redis state、leader election、
  endpoint cache、pool destroy fence/tombstone 和 destroy helper。
- **安全与租户治理**：Credential Vault、egress 强制网络约束、路径规范化、可信代理、secure
  proxy token、禁用 Pod ServiceAccount token 自动挂载，以及 file/HTTP tenant provider。
- **Kubernetes 生产化**：PVC、snapshot、pool capacity、RBAC、Helm scheduling、private
  registry、volume guard 和 diagnostics 可靠性持续修补。
- **可观测与发布治理**：ingress/execd/egress 的 OTel metrics 收敛，release/tag/environment
  gate 明显加强。
- **跨语言 contract 同步**：较大的功能 PR 通常同时修改 OpenAPI/spec、组件、Python/Go/
  JavaScript/Kotlin/C# SDK 和多语言 E2E。

一句话判断：**OpenSandbox 正从“能创建并操作 sandbox”升级为“可池化、可恢复 handle、可观测、
凭据与发布链路更安全”的平台；multi-tenancy 当前只是 `main` 上合入的 Kubernetes namespace
tenancy 首版，还不是跨 provider 的稳定能力。**

> 分析：这不是简单的 feature 数量增长。最近投入开始围绕状态恢复、资源回收、安全默认值、
> 兼容版本矩阵和发布门禁，说明项目重心正在从 API breadth 转向 production correctness。

## 调研基线与统计口径

| 项 | 本轮口径 |
| --- | --- |
| 官方仓库 | <https://github.com/opensandbox-group/OpenSandbox> |
| Day21/22 旧基线 | `3d40414e794d`，2026-06-22 |
| 本轮 `main` 快照 | [`3d91094052bf`](https://github.com/opensandbox-group/OpenSandbox/commit/3d91094052bfb78ccfa77089a9c93c9626a44f44)，2026-07-15 |
| Release 数据 | GitHub Releases API 全量 159 条；`draft=0`、`prerelease=0` |
| 30 天 merge 面 | 2026-06-16 至 2026-07-15，共 116 个 merged PR；105 个人工、11 个自动版本 bump |
| 主题分类样本 | 按合并时间倒序取最近 50 个非机器人 merged PR：`#1292` 至 `#1167`（截止 2026-07-02T02:05:34Z） |
| 数据来源 | GitHub release note、PR body/labels/files、当前代码和 Day21/22 本地记录 |

统计命令采用 GitHub Search 全分页，并对每个 PR 的 files API 继续全分页；目录触达按“一个 PR
是否修改该顶层目录”去重。主题分类以 PR 的主问题为唯一类别，避免一个 full-stack PR 在总数中
重复计算。

> 调试记录：初稿一度得到 95 个 merged PR，是 PR 列表没有取全造成的漏数；改用 Search 全分页
> 后确认是 116 个。files API 也不能只取前 100 项：`#1008` 有 149 个 changed files、`#1090`
> 有 147 个，漏掉第二页会继续少算 `server/`、`sdks/`、`kubernetes/`、`tests/` 和 `specs/`
> 的目录触达。最终表格使用 PR 列表与 files 两层全分页结果。

> 注释：生成客户端会显著放大 changed files 和 LOC，因此本报告按行为合同、组件边界和 PR
> 主问题归类，不按代码行数判断投入优先级。

> 分析：GitHub labels 可以交叉出现，且安全 PR 不一定都带 `security` label。目录/label 统计
> 用于描述 activity surface，语义优先级仍要回到 PR body、release note 和实际文件边界。

## Release 模型：不存在一个统一的“OpenSandbox 最新版”

OpenSandbox 是 monorepo，但采用组件独立 tag：server、execd、ingress、egress、Kubernetes
controller/工具、Helm chart 和各语言 SDK 分别发版。按发布时间看，当前最新 published release 是
[`java/code-interpreter/v1.0.16`](https://github.com/opensandbox-group/OpenSandbox/releases/tag/java/code-interpreter/v1.0.16)，
但它主要用于对齐 Kotlin Sandbox SDK 依赖，并不代表所有 runtime/controller 都到了 1.0.16。

### 最近代表性 release train

| 发布日期（UTC） | 组件 release | 主要交付 | 关键升级边界 |
| --- | --- | --- | --- |
| 2026-07-13 | [Python Sandbox SDK v0.1.14](https://github.com/opensandbox-group/OpenSandbox/releases/tag/python/sandbox/v0.1.14) / [Kotlin Sandbox SDK v1.0.16](https://github.com/opensandbox-group/OpenSandbox/releases/tag/java/sandbox/v1.0.16) | isolation helper/list/binds、pool destroy、Credential Vault placeholders、endpoint cache、extensions | 删除 `CredentialMatch.ports`；自定义 isolation protocol 需适配新方法；Python 修补 21 个依赖告警 |
| 2026-07-12 | [execd v1.0.21](https://github.com/opensandbox-group/OpenSandbox/releases/tag/docker/execd/v1.0.21) | isolated session list、显式 bind mount、bwrap 默认加固、userns UID mode、JDK MITM CA | bind source 受 allowlist 限制；destination 必须存在；OTel 查询需更新 |
| 2026-07-12 | [egress v1.1.4](https://github.com/opensandbox-group/OpenSandbox/releases/tag/docker/egress/v1.1.4) | Credential Vault 强制网络安全、placeholder、nft fallback、CredentialSource | **有 breaking changes**：迁移 `dns+nft`、配置 trusted proxy CIDR、删除 `Match.Ports` |
| 2026-07-12 | [ingress v1.0.10](https://github.com/opensandbox-group/OpenSandbox/releases/tag/docker/ingress/v1.0.10) | 独立 `http.ServeMux`，不再被依赖意外暴露 pprof/expvar；OTel 规范化 | `/debug/pprof/` 变 404；删除冗余指标并改变属性名/temporality |
| 2026-07-08 | [Go Sandbox SDK v1.0.4](https://github.com/opensandbox-group/OpenSandbox/releases/tag/sdks/sandbox/go/v1.0.4) | OSEP-0005 client pool（显式启用）、可选 Redis store、isolation helpers、默认 endpoint cache、`resourceRequests` API/spec 合同 | pool 完全 opt-in；cache 默认 TTL 600s、上限 1024；provider 侧独立 requests threading 尚未交付；Credential Vault ports 字段删除 |
| 2026-07-05 | [image-committer v0.1.1](https://github.com/opensandbox-group/OpenSandbox/releases/tag/k8s/image-committer/v0.1.1) | snapshot commit 可回退查找 stopped container | 只修 image commit race，不代表 controller/Helm 同步发版 |
| 2026-06-29 | [server v0.2.1](https://github.com/opensandbox-group/OpenSandbox/releases/tag/server/v0.2.1) | `resourceRequests` API/spec 合同、egress env routing、bwrap isolation、K8s proxy/sidecar 修复、CVE patch | release note 明确 provider threading 后续再做；7 月多租户、proxy security、Docker reliability 尚未进入 server release |
| 2026-05-15 | [K8s controller v0.2.0](https://github.com/opensandbox-group/OpenSandbox/releases/tag/k8s/controller/v0.2.0) / [Helm controller 0.2.0](https://github.com/opensandbox-group/OpenSandbox/releases/tag/helm/opensandbox-controller/0.2.0) | 当前 controller/chart 正式基线 | 7 月的 Helm/RBAC/PVC/pool 修补大多仍是 main-only |

> 注释：release train 指同一批 commit 上为多个组件分别打 tag。例如 7 月 12 日的 execd、
> ingress、egress tag 指向同一发布快照，但版本号各自维护。

### Release 主轴 1：isolated session 成为一等 SDK 能力

Python/Kotlin/Go release 不再只包装 sandbox create/exec/file：

- `run_once` / `runOnce`：封装 create -> run -> delete，cleanup 不覆盖原始错误。
- scoped `session` / `withSession`：在一个生命周期块中复用 isolated session。
- `list`：枚举 execd 当前内存中的 active isolated sessions。
- `BindMount(source, dest, readonly)`：显式传递 bwrap bind/ro-bind。
- endpoint LRU+TTL cache 和 inflight dedup：降低重复 endpoint resolution roundtrip。

> 注释：isolated session 是 execd 进程内的一层执行隔离。它可以让同一个外层 sandbox/Pod
> 承载多个隔离执行 session，但不等同于新的 VM、Pod 或 Kubernetes Sandbox 资源。

### Release 主轴 2：SandboxPool 从 acquire 走向完整状态机

[Go SDK v1.0.4](https://github.com/opensandbox-group/OpenSandbox/releases/tag/sdks/sandbox/go/v1.0.4)
的 client-side `SandboxPool` 包含 background reconcile、leader election、fill deficit、shrink
excess、warmup exponential backoff 和 near-expiry reuse；可选 Redis module 用 Lua 保证分布式
原子操作。Python/Kotlin release 又补了 FORCE destroy：

```text
ACTIVE -> DESTROYING -> DESTROYED tombstone
```

destroy 中途失败会保留 `DESTROYING`，允许调用者重试，而不是把部分清理误报为完成。

> 注释：tombstone 是“该对象已经终止”的持久状态标记。它防止旧 worker 或延迟请求在删除后
> 把 pool 意外复活。

### Release 主轴 3：Credential Vault/egress 是升级风险最高的区域

[egress v1.1.4](https://github.com/opensandbox-group/OpenSandbox/releases/tag/docker/egress/v1.1.4)
同时包含功能、security 和 breaking changes：

- Credential-bound destination 强制使用 `dns+nft`，防止 direct IP 绕过 DNS 约束。
- 只信任配置 CIDR 内代理提供的 `X-Forwarded-Proto`。
- 在凭据匹配和注入前拒绝 `../`、编码 dot segment 和 encoded separator。
- placeholder 可进入 path/query/header/body，并配套编码、跳过和脱敏规则。
- `CredentialSource` 抽成 provider interface，为 Vault/AWS Secrets Manager 等后端留边界。
- OTel attribute 和 delta temporality 改变，需要同步 dashboard/alert。

> 注释：Credential Vault 的目标不是把 secret 交给 sandbox 代码，而是在受控 egress 代理层
> 匹配目标请求并注入凭据。网络约束、路径规范化和可信代理是安全合同的一部分，不是可选优化。

### Release 主轴 4：server 与 K8s release 节奏落后于 main

最新 server 仍是 6 月 29 日的 `v0.2.1`，controller/Helm 仍是 5 月 15 日的 `v0.2.0`。
因此评估可部署版本时不能把 7 月 merged PR 直接算作正式能力。

`server v0.2.1` 已包含 bwrap 基础层、egress env routing、gVisor 与 OpenSandbox egress-sidecar
`networkPolicy` 组合的冲突拒绝，以及 K8s internal proxy 修复，但之后的 multi-tenancy、
secure-access proxy token、image pull
event-loop fix、Helm scheduling 等仍需等待相应组件发版。

## 最近 merged PR 统计

### 30 天 activity surface

2026-06-16 至 2026-07-15 共 116 个 merged PR，其中 105 个人工 PR、11 个自动 release/image
版本 bump。按 PR 是否触达顶层目录去重：

| 顶层目录 | 触达 PR 数 | 说明 |
| --- | ---: | --- |
| `server/` | 38 | provider、lifecycle、security、Docker/K8s service |
| `sdks/` | 36 | 多语言 API、generated client、pool/cache/isolation |
| `docs/` | 31 | release、security、examples、multi-tenancy、architecture |
| `components/` | 30 | execd、egress、ingress 与 shared telemetry |
| `kubernetes/` | 28 | controller、Helm、RBAC、PVC、snapshot、pool |
| `tests/` | 17 | 多语言 E2E 与跨组件合同验证 |
| `specs/` | 14 | lifecycle、execd、egress API contract |
| `.github/` | 11 | CI、release、publish、label/repository safeguards |

这个分布说明 SDK/server/K8s/components 都很活跃，不是单一 runtime 仓库；`specs/` 和
多语言 tests 的同步触达也说明 contract-first 已成为主要实现方式。

### 最近 50 个非机器人 PR 的主主题

| 主主题 | PR 数 | 占比 | 代表 PR |
| --- | ---: | ---: | --- |
| runtime、K8s/Docker 生命周期与可靠性 | 15 | 30% | [#1246 PVC readonly](https://github.com/opensandbox-group/OpenSandbox/pull/1246)、[#1267 expiration persistence](https://github.com/opensandbox-group/OpenSandbox/pull/1267)、[#1171 nonblocking image pull](https://github.com/opensandbox-group/OpenSandbox/pull/1171) |
| security、egress/Credential Vault、供应链 | 12 | 24% | [#1251 placeholders](https://github.com/opensandbox-group/OpenSandbox/pull/1251)、[#1192 path rejection](https://github.com/opensandbox-group/OpenSandbox/pull/1192)、[#1191 proxy token](https://github.com/opensandbox-group/OpenSandbox/pull/1191) |
| SDK pool、lifecycle、performance、release | 9 | 18% | [#1198 Go pool](https://github.com/opensandbox-group/OpenSandbox/pull/1198)、[#1225 pool destroy](https://github.com/opensandbox-group/OpenSandbox/pull/1225)、[#1133 endpoint cache](https://github.com/opensandbox-group/OpenSandbox/pull/1133) |
| execd isolated session 与 bwrap | 7 | 14% | [#1295 attach](https://github.com/opensandbox-group/OpenSandbox/pull/1295)、[#1269 list](https://github.com/opensandbox-group/OpenSandbox/pull/1269)、[#1264 binds](https://github.com/opensandbox-group/OpenSandbox/pull/1264) |
| multi-tenancy、observability、ingress | 5 | 10% | [#1184 tenant provider](https://github.com/opensandbox-group/OpenSandbox/pull/1184)、[#1181 ingress OTel](https://github.com/opensandbox-group/OpenSandbox/pull/1181)、[#1209 metrics contract](https://github.com/opensandbox-group/OpenSandbox/pull/1209) |
| repository/release governance | 2 | 4% | [#1274 release safeguards](https://github.com/opensandbox-group/OpenSandbox/pull/1274)、[#1197 org migration](https://github.com/opensandbox-group/OpenSandbox/pull/1197) |

> 分析：最近两周的第一名不是新 API，而是 lifecycle/reliability；security 排第二。这是项目
> 进入生产化阶段的强信号。CLI 只有一个 PR 触达，没有形成独立主线。

## Merged PR 深入拆解

### 1. execd：从 command/file daemon 扩成 Pod 内 session runtime

演进链条非常连续：

```text
#1008 bwrap isolated execution
    -> #1226 secure defaults + userns uid_mode
    -> #1222 run_once / withSession
    -> #1264 explicit bind mounts
    -> #1269 list active sessions
    -> #1295 attach(sessionId)
```

[#1295](https://github.com/opensandbox-group/OpenSandbox/pull/1295) 的问题定义很清楚：execd HTTP
endpoint 本来就按 `sessionId` 查内存 map，但 SDK 只有 `create()`；serverless worker 重启或
job runner 从 queue 取回 ID 后，无法重建 client handle。新 `attach(sessionId)` 同步修改
execd HTTP 实现、API spec 和五种 Sandbox SDK。

> 注释：这里的“stateless recovery”是 caller 只凭 session ID 恢复 SDK handle；session 本体
> 仍在 execd 内存 map。execd 或 Pod 重启后 map 丢失，`attach` 不能恢复执行状态。

> 分析：方向上，OpenSandbox 正把“一个 Pod/容器就是一个 session”拆成“外层 sandbox 提供
> 安全/资源边界，execd 在内部提供多个执行 session”。这会减少 control-plane create/delete
> QPS，也接近 AgentCube 后续 AgentSlot/multi-session worker 的思路。

### 2. 两层 pool：client reuse 与 Kubernetes prewarm 分工

OpenSandbox 现在同时存在：

| Pool 层 | 责任 |
| --- | --- |
| SDK client-side pool | runtime-neutral idle inventory refill/acquire、local/Redis state、leader/reconcile/backoff；acquire 后 Sandbox 转为 caller-owned，不提供 return/finalize |
| Kubernetes `Pool` / BatchSandbox | 集群内预热 workload、capacity predicate、snapshot/PVC/runtime 资源管理 |

[#1198](https://github.com/opensandbox-group/OpenSandbox/pull/1198) 补齐 Go client pool；
[#1225](https://github.com/opensandbox-group/OpenSandbox/pull/1225) 加入 destroy fence/tombstone；
[#1176](https://github.com/opensandbox-group/OpenSandbox/pull/1176) 对不存在的 `poolRef` fail fast；
[#1143](https://github.com/opensandbox-group/OpenSandbox/pull/1143) 在 K8s pool assign 中增加 capacity
predicate。

> 分析：SDK pool 管理尚未借出的 Sandbox ID，Kubernetes Pool 管理可分配的预热 workload，
> 并不是两个 reconciler 天然争夺同一份库存。若 AgentCube 同时引入两层 pool，仍要先写 ownership
> matrix，明确 refill、acquire 后的所有权转移、expiry、destroy 与 distributed coordination 如何
> 跨层衔接。

### 3. Credential Vault、安全默认值与 multi-tenancy 已成为主线

安全变化不是孤立补丁，而是从 server 到 egress、SDK、K8s 和 supply chain 的连续收敛：

- [#1136](https://github.com/opensandbox-group/OpenSandbox/pull/1136)：凭据目标必须有强制
  `dns+nft` enforcement。
- [#1138](https://github.com/opensandbox-group/OpenSandbox/pull/1138)：只信任明确 proxy CIDR 的
  forwarded TLS 信息。
- [#1192](https://github.com/opensandbox-group/OpenSandbox/pull/1192)：凭据注入前拒绝歧义路径。
- [#1191](https://github.com/opensandbox-group/OpenSandbox/pull/1191)：server proxy route 强制
  secure-access token。
- [#1227](https://github.com/opensandbox-group/OpenSandbox/pull/1227)：不再向 sandbox Pod 注入
  ServiceAccount，禁用 token automount。
- [#1184](https://github.com/opensandbox-group/OpenSandbox/pull/1184)：file/HTTP tenant provider、
  ContextVar 传播和 Kubernetes namespace 隔离。

> 注释：multi-tenancy provider 位于身份到 namespace 的映射层，不是新的 runtime provider。
> 外层 runtime 仍是 Docker/Kubernetes，K8s workload provider 仍是 BatchSandbox 或
> agent-sandbox。

> 局限：`#1184` 是仅支持 Kubernetes 的 namespace tenancy 首版；Docker 配置 tenants 会拒绝
> 启动，Pool API 仍使用共享默认 namespace，而且该 PR 没有运行 file/HTTP provider 的 Kubernetes
> E2E。这里记录的是已合并方向，不等同成熟的多租户交付。

### 4. Kubernetes/main 最近以正确性和运维为主

近期 K8s 变化包括 PVC readonly、自动 PVC 清理、snapshot stopped-container fallback、pool
capacity、events/RBAC、Helm `nodeSelector`/`securityContext`/annotations/labels/`priorityClass`/
topology spread、private registry `imagePullSecrets` 和空 volume guard。

这说明 Kubernetes 方向仍在推进，但最近主要是 production fit 与正确性修复，没有看到新的
CRD 架构重写或第三种 workload provider。自研 BatchSandbox/Pool/SandboxSnapshot 仍承担高吞吐、
pool 和 pause/resume 主路径；agent-sandbox provider 继续是外部 CRD adapter。

> 分析：这验证了 Day21 的 provider-adapter 判断。OpenSandbox 没有让 agent-sandbox schema
> 散进 SDK/Router，而是集中在 Kubernetes provider；但它目前也没有采用 SandboxClaim/
> SandboxWarmPool adoption，agent-sandbox provider 能力仍小于 BatchSandbox 主路径。

### 5. 可观测性与发布治理开始形成平台合同

[#1181](https://github.com/opensandbox-group/OpenSandbox/pull/1181) 给 ingress 增加 OTel metrics；
[#1209](https://github.com/opensandbox-group/OpenSandbox/pull/1209) 在 shared telemetry 中把属性名从
`.` 规范成 `_`、改用 delta temporality，并删除重复 ingress 指标。这一改动同时影响 ingress、
execd、egress，需要更新 dashboard/alert。

> 注释：delta temporality 上报“本次周期增量”，而 cumulative temporality 上报“进程启动以来
> 累积值”。Collector/backend 查询和告警必须与 temporality 匹配。

[#1274](https://github.com/opensandbox-group/OpenSandbox/pull/1274) 则收紧 repository/release：
required gates 稳定化、release commit 必须可达 main、protected environment、tag 不可复用、
通用 workflow 不再直接 push tag，并要求额外 maintainer approval。

> 分析：release 数量很多且组件独立时，发布治理本身就是产品可靠性的一部分；否则 SDK、
> component image、server 和 chart 很容易形成未验证的组合。

### 6. Contract-first 的跨语言同步成本非常明显

最近 50 个非机器人 PR 中：

- 20 个触达 SDK；
- 16 个触达 server；
- 14 个触达 components；
- 9 个触达 Kubernetes；
- 20 个跨至少两个顶层目录，13 个跨至少三个。

`attach`、isolated list/binds、Credential Vault placeholder 都遵循类似路径：

```text
spec/OpenAPI
  -> execd/egress/server implementation
  -> generated clients
  -> Python/Go/JS/Kotlin/C# public models and helpers
  -> multi-language unit/E2E
```

这说明 OpenSandbox 把 API contract 当作跨组件贯通点。代价是一个字段变化会扩散很多文件，
但收益是各语言不会长期漂移。

## Shipped 与 Main-only 边界

| 能力 | 当前状态 | 判断依据 |
| --- | --- | --- |
| run_once/session/list/binds | **组件级已发布；未进入新 Helm 组合** | Python/Kotlin SDK 7 月 13 日、execd 7 月 12 日 release；Helm 0.2.0 仍引用旧 execd |
| bwrap defaults/userns | **execd 组件已发布；未进入新 Helm 组合** | execd v1.0.21 |
| client-side Go pool/endpoint cache | **SDK package 已发布** | Go SDK v1.0.4；不属于 chart 内组件 |
| pool destroy tombstone | **SDK package 已发布** | Python/Kotlin SDK 7 月 13 日 release |
| Credential Vault security/placeholders | **组件/SDK 已发布；未进入新 Helm 组合** | egress v1.1.4 和最新 SDK train；Helm 0.2.0 仍引用旧 egress |
| `attach(sessionId)` | **main-only** | PR #1295 于 7 月 15 日合并，晚于 7 月 12/13 日 release train |
| file/HTTP multi-tenancy provider | **main-only；Kubernetes-only** | PR #1184 晚于 server v0.2.1；需要后续 server release，Docker 不支持 tenants |
| image pull nonblocking/graceful shutdown | **main-only for server** | PR #1171 晚于 server v0.2.1 |
| Helm scheduling fields/private registry guards | **main-only for Helm artifacts** | 最新 controller/Helm 正式版仍为 0.2.0 |
| snapshot stopped-container fallback | **image 组件已发布；未进入新 Helm 组合** | image-committer v0.1.1；不代表 controller/chart 同步升级 |

> 注释：merged 表示代码进入 `main`，release 表示用户可以从明确 tag/package/image/chart 获取。
> 在组件独立发版仓库中，两者之间可能隔着多个发布列车。

> 版本组合边界：正式 Helm 0.2.0 默认仍引用 server `v0.1.13`、ingress `v1.0.7`、execd
> `v1.0.16`、egress `v1.0.11` 和 `image-committer:dev`。`main` chart 已更新到 server
> `v0.2.1`、ingress `v1.0.10`、execd `v1.0.21`、egress `v1.1.4`、image-committer
> `v0.1.1`，但尚无新的 Helm/controller tag。因此“组件级可取”不能写成“官方 chart 已交付并
> 验证这组版本”。

## 对 Day21/22 旧结论的校准

| Day21/22 判断或覆盖缺口 | 当前校准 |
| --- | --- |
| execd 主要提供 command/file/PTY/code | **已过时**：新增 bwrap isolated-session runtime、list/binds/helpers/attach |
| 首次 Docker image pull 会阻塞 server `/health` | **main 已修复、release 未覆盖**：#1171 把 provision 移出 event loop 并支持 graceful shutdown |
| 旧报告未专项跟踪 OTel | **本轮新增**：ingress/execd/egress metrics 主体已成形；tracing、Python server、稳定 diagnostics 仍有缺口 |
| 旧报告未覆盖 multi-tenancy | **本轮新增、仍有限制**：`main` 合入 Kubernetes file/HTTP tenant provider 与 namespace propagation，但尚未进入 server v0.2.1，Pool namespace 与 E2E 仍有缺口 |
| Credential/egress 会成为重点 | **被近期 PR 强化验证**：安全与供应链占最近语义样本 24% |
| provider adapter 是正确边界 | **限定后继续成立**：provider-specific schema/CRUD 仍集中在 adapter；跨层身份、readiness、删除路由合同仍需贯通 Store/handler |
| BatchSandbox 是高吞吐/pool/snapshot 主路径 | **继续成立**：近期以 capacity、PVC、snapshot、events 正确性收敛为主 |
| cold/warm benchmark 必须分开 | **继续成立**：image pull event-loop fix 不会消除镜像下载本身的冷启动成本 |

## 对 AgentCube 的工程启发

### 1. Provider adapter 是重要边界，但不是唯一 lifecycle 边界

OpenSandbox 的近期演进继续证明：外部 CRD 的 schema、provider-specific CRUD 和版本判断应留在
adapter，不应散入 Router、Store、SDK 和所有 handler。但 #387 也证明 Claim 控制身份、adopted
Sandbox 运行身份、readiness 和删除路由属于跨层稳定合同，合理进入 Store/handler。Docker/local/
OpenSandbox-like backend 目前只是 AgentCube 的设计可能性，不是 upstream 已确认的实现优先级。

### 2. “恢复 handle”与“恢复 runtime state”必须分开命名

`attach(sessionId)` 很实用，但它只恢复 client handle。AgentCube 设计 resume 时至少要区分：

- handle reattach：runtime 仍活着，只丢了调用端对象；
- control-plane resume：Pod/process 被 pause，需要重新变 Ready；
- checkpoint restore：runtime/进程已重建，需要加载 filesystem/memory state。

否则一个 `Resume` API 会把三种完全不同的失败恢复合同混在一起。

### 3. Pool 要先定义 ownership 和 durable state

OpenSandbox client pool 的 leader election、Redis atomic operation、destroy fence/tombstone 提醒我们：
pool 不只是 `warmPoolSize`。AgentCube SandboxPool proposal 至少要定义：

- capacity source of truth；
- refill owner；
- acquire 的所有权转移与幂等性；若设计 return，则单独定义 return 合同；
- expiry 与 GC 竞争；
- destroy 中途失败的可重试状态；
- controller pool 与 SDK/local cache 是否允许并存。

### 4. Security 不能缩成一个 NetworkPolicy 字段

Credential Vault 的近期演进把安全拆成 secret source、request matching、network enforcement、
path canonicalization、trusted proxy、redaction 和 tenant namespace。AgentCube 若进入生产级 Agent
场景，也应把 egress policy、credential injection、audit 和 identity mapping 作为独立能力面。

### 5. 跨语言 contract 需要版本矩阵和 generated/manual 边界

OpenSandbox 的 full-stack PR 经常同时改 spec 和五种 SDK。AgentCube 当前语言面较小，但
Python SDK、CLI、Router API、WorkloadManager types 和 CRD 也会漂移。应维护：

- contract source of truth；
- generated client 边界；
- compatibility/deprecation 规则；
- 每个 release train 的 SDK/server/runtime/chart 版本矩阵；
- feature-specific multi-language E2E。

### 6. 竞品 benchmark 要加入内层 session 维度

后续不应只比较“创建一个 Pod/sandbox 多快”，还要拆：

1. cold image pull；
2. warm outer sandbox acquire；
3. isolated session create/attach/list；
4. first command；
5. endpoint cache hit/miss；
6. destroy/cleanup；
7. execd/Pod restart 后是否可恢复。

这能区分 control-plane 优化、runtime reuse 和真正的 checkpoint restore。

## 局限与风险边界

1. **bwrap 不是外层强隔离替代品**：它是 Pod/容器内 filesystem/session 隔离，需要结合外层
   gVisor/Kata/容器权限判断，不能等同 Firecracker/microVM。
2. **attach 不是 durable recovery**：session map 仍在 execd 内存，跨 execd/Pod restart 失效。
3. **release note 与 main 有时间差**：尤其 server、controller、Helm；评估部署必须锁 tag。
4. **OSEP metadata 有滞后**：multi-tenancy 代码已经合并，但 proposal 索引/status 未完全同步；
   不能只看 OSEP 状态判断实现成熟度。
5. **OTel 仍不完整**：metrics 进展明显，但 tracing、server telemetry 和稳定 diagnostics API 仍是
   可见缺口。
6. **本轮没有重跑 runtime smoke**：本报告是官方 release/PR/current-code 调研，不把 remote
   source evidence 冒充本机实测。

## 下一步

1. 等下一次 server release 后重跑 Day22 Docker smoke，只验证 #1171 的 health/event loop 与
   graceful shutdown 改善。
2. 在 Kubernetes 环境单独验证 file/HTTP TenantProvider、namespace 与 proxy ownership，不能用
   Docker smoke 代替 multi-tenancy E2E。
3. 在合适的 cgroup v2/Kubernetes 环境验证 BatchSandbox/Pool/Snapshot。
4. 设计一组 outer sandbox 与 inner isolated session 分层 benchmark，记录 image cache、endpoint
   cache 和 execd restart 边界。
5. 对 AgentCube SandboxPool/RuntimeProvider proposal 增加 pool ownership、tombstone、attach vs
   resume、component version matrix 检查项。
6. 后续刷新 OpenSandbox 时同时检查 release、main merged PR 和 OSEP 三个面，不用任何单一来源
   代替完整状态。

## 主要官方证据

- [OpenSandbox Releases](https://github.com/opensandbox-group/OpenSandbox/releases)
- [Python Sandbox SDK v0.1.14](https://github.com/opensandbox-group/OpenSandbox/releases/tag/python/sandbox/v0.1.14)
- [execd v1.0.21](https://github.com/opensandbox-group/OpenSandbox/releases/tag/docker/execd/v1.0.21)
- [egress v1.1.4](https://github.com/opensandbox-group/OpenSandbox/releases/tag/docker/egress/v1.1.4)
- [Go Sandbox SDK v1.0.4](https://github.com/opensandbox-group/OpenSandbox/releases/tag/sdks/sandbox/go/v1.0.4)
- [server v0.2.1](https://github.com/opensandbox-group/OpenSandbox/releases/tag/server/v0.2.1)
- [#1295 isolated session attach](https://github.com/opensandbox-group/OpenSandbox/pull/1295)
- [#1198 Go client-side pool](https://github.com/opensandbox-group/OpenSandbox/pull/1198)
- [#1251 Credential Vault placeholders](https://github.com/opensandbox-group/OpenSandbox/pull/1251)
- [#1184 multi-tenancy provider](https://github.com/opensandbox-group/OpenSandbox/pull/1184)
- [#1209 OTel metrics contract](https://github.com/opensandbox-group/OpenSandbox/pull/1209)
- [#1274 release safeguards](https://github.com/opensandbox-group/OpenSandbox/pull/1274)
