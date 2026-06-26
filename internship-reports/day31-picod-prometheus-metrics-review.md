# Day 31：PR #400 PicoD Prometheus Metrics Review

日期：2026-06-26

今天的目标不是继续等待自己已有的 #387 / #403，而是主动从 upstream 当前 open PR / issue 中找一个可以做出实质产出的 review 目标。最后选定的是 PR [#400 Feat/picod prometheus metrics](https://github.com/volcano-sh/agentcube/pull/400)。

> 注释：这里的“工作量”不是为了凑数量去抢别人的实现，而是找一个能训练源码阅读、测试设计、review 判断和社区协作边界的任务。#400 属于 observability 主线，改动面可控，也没有正式 assignee，适合作为 Day31 的本地 review 任务。

## 结论先行

PR #400 的方向是合理的：它给 PicoD 增加独立 Prometheus registry、`/metrics` endpoint、HTTP request counter / latency histogram，以及 execute outcome counter / active gauge。当前 `go test ./pkg/picod` 和 `go test -race ./pkg/picod` 都通过。

但本地 review 发现至少一个仍然值得 upstream 作者处理的实质问题：

1. `picod_http_requests_total` / `picod_http_request_duration_seconds` middleware 注册在 `maxBodySizeMiddleware()` 后面，因此被 body-size limiter 提前 `Abort()` 的 `413` 请求不会被 HTTP metrics 记录。
2. `picod_active_executions` 这个指标名听起来是“正在执行命令数”，但当前实现从 handler 入口开始计数，包含 JSON 解析、参数校验、working dir 准备等阶段；如果作者坚持这个统计窗口，指标名或 Help 文案应改成 handler in-flight，否则应只包住 `cmd.Run()`。
3. 当前 PR 只让 PicoD 暴露 `/metrics`，没有解决“如何被集群 Prometheus 抓取”的部署层入口。考虑到 PicoD 是 sandbox Pod 内服务，默认 CodeInterpreter 只把 `/` pathPrefix 暴露给 Router，这一点更适合在 PR 说明中标成 scope limitation，而不是要求本 PR 一次做完 ServiceMonitor / scrape annotation。

> 分析：第 1 点是可以用测试证明的行为缺口；第 2 点是指标语义一致性问题；第 3 点是产品范围问题。review 时应把三者分清，避免把所有观察都包装成 blocker。

## 今天为什么选 #400

今天先用 `agentcube-issue-discussion` 和 `agentcube-pr-management` 的流程扫了 upstream 最新状态：

- #387：open，checks 全绿，等待 maintainer review / lgtm / approve / tide。
- #403：open，checks 全绿，等待 maintainer review / lgtm / approve / tide。
- #394 / #395：已经有人 `/assign`，不适合抢实现。
- #405：docs website，改动巨大，已经有较多 Copilot / maintainer review，适合后续做文档准确性 review，但 Day31 不适合从 XXL 文档开始。
- #402：auth proposal 文档，只有一个文件，适合轻量 review，但和今天想补的 observability 主线不如 #400 对齐。
- #400：PicoD metrics，5 个文件，没人 assignee，主题贴合 Agent Infra 的 observability 能力线。

> 注释：Agent Infra 不是只会写 controller 或 sandbox runtime，observability 也很关键。PicoD 是 sandbox 内真正执行代码和文件操作的 data-plane daemon；它有没有可观测指标，直接影响后续排查“代码执行慢、失败、超时、请求量异常”的能力。

## 候选目标筛选矩阵

| 候选 | 当前状态 | 是否有人认领 | 与主线关系 | 今日可产出 | 选择判断 |
| --- | --- | --- | --- | --- | --- |
| #387 agent-sandbox v0.4.6 compatibility | open，checks 全绿 | `zhzhuang-zju` assignee，我们是 PR 作者/协作者 | agent-sandbox compatibility 主线 | 只能继续等 review 或准备答辩 | 不作为今天主动工作主线，避免无意义重复 push/comment |
| #403 remove unused agentd | open，checks 全绿 | 无 assignee，但我们是 PR 作者 | PicoD / agentd 边界清理 | 等 review；可准备答辩 | 不主动扩 scope |
| #394 SDK ttl ignored | open | `kavyarathod05`, `vivek41-glitch` | SDK lifecycle 主线 | 可做 review/test feedback | 已有人 `/assign`，不抢实现 |
| #395 AgentRuntimeClient cannot delete | open | `nabrahma`, `vivek41-glitch` | SDK lifecycle 主线 | 可做 API contract review | 已有人 `/assign`，先不抢 |
| #400 PicoD Prometheus metrics | open，checks 绿，tide pending | 无 assignee | observability / PicoD data-plane | 源码 review、测试验证、comment 草稿 | 选为 Day31 主任务 |
| #405 docs website | open，XXL docs | 无 assignee，但已有大量 AI/human comments | docs / contributor onboarding | 文档准确性矩阵 | 可作为 #400 后续备选，不适合今天第一目标 |
| #402 auth proposal update | open，1 file | 无 assignee | auth / Router-PicoD trust model | 设计文档 review | 可后续做，今天不如 #400 贴 observability |

> 分析：选择 #400 的关键不是“它最简单”，而是它的 review 可以训练三个能力：读 data-plane 代码、设计 metrics 语义、用小测试证明 review 观点。相比之下，#405 虽然有大量文档问题，但更容易变成摘录 Copilot 评论；#400 可以做出自己的验证证据。

## Day31 工作边界

今天只做本地 review，不做以下事情：

- 不往 #400 发评论，除非用户确认英文全文。
- 不 fork 作者分支直接提交修复，避免抢作者实现。
- 不把 #400 扩成完整 observability design，例如 ServiceMonitor、PodMonitor、Router scrape proxy 或租户隔离指标方案。
- 不把 #405 文档 review 混入 #400，虽然 #405 也提到了 PicoD metrics。
- 不把 #387 / #403 状态等待写成 Day31 工作量。

今天做的事情：

- 拉取 #400 head 到隔离 worktree。
- 读 PR body、changed files、AI reviewer comments 和当前 CI 状态。
- 跑 focused PicoD tests 和 race tests。
- 用临时测试复现一个 metrics coverage 缺口。
- 用临时顺序调整验证一个可行修复方向。
- 清理临时代码。
- 写本地中文 review 报告和英文 upstream comment 草稿。

## PR #400 快照

来源：

```bash
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 400 \
  --comments-limit 40 \
  --review-comments-limit 40

gh pr view 400 --repo volcano-sh/agentcube \
  --json number,title,state,mergeable,reviewDecision,statusCheckRollup,latestReviews,headRefName,headRepositoryOwner,headRefOid,updatedAt
```

PR 快照：

| 项 | 内容 |
| --- | --- |
| PR | #400 |
| 标题 | `Feat/picod prometheus metrics` |
| 作者 | `@vanshika2720` |
| Head | `vanshika2720:feat/picod-prometheus-metrics` |
| Head SHA | `3e4ac99` |
| Base | `main` |
| 状态 | open |
| mergeable | `MERGEABLE` |
| reviewDecision | 空，尚无真人 approve/lgtm |
| labels | `kind/feature`, `size/L` |
| changed files | 5 |
| CI | GitHub checks 成功，tide pending 等 review gate |

改动文件：

| 文件 | 作用 |
| --- | --- |
| `go.mod` | 将 `github.com/prometheus/client_golang` 从 indirect 提升为 direct dependency |
| `pkg/picod/metrics.go` | 新增 private registry、collector 定义、`/metrics` handler 和 Gin middleware |
| `pkg/picod/server.go` | 在 PicoD server 注册 metrics middleware 与 `/metrics` endpoint，并把 `/metrics` 排除 gzip |
| `pkg/picod/execute.go` | 给 execute handler 增加 active gauge 与 execute outcome counter |
| `pkg/picod/metrics_test.go` | 新增 metrics exposition / registry gather 单测 |

## 社区评论权重

已有评论主要来自自动化工具：

- `gemini-code-assist[bot]`：指出 metrics path label fallback 可能高基数、mkdirSafe 500 被标成 `invalid`。
- `copilot-pull-request-reviewer[bot]`：指出 middleware 顺序、active executions 统计窗口、mkdirSafe status label、测试错误处理、histogram SampleSum 断言等。
- `codecov-commenter`：patch coverage 相关。
- `@vanshika2720`：请求 `@hzxuzhonghu` review。

没有真人 maintainer 给出技术结论。

> 注释：AI reviewer 的评论不能当成维护者共识，但可以当成 checklist。今天做的事情是把这些 checklist 逐项映射回源码和本地测试，确认哪些已经修掉，哪些仍然成立。

## 本地工作区

为了不污染 `intern` 分支，创建了隔离 worktree：

```bash
git fetch upstream pull/400/head:refs/remotes/upstream/pr/400
rm -rf /home/agentcube-pr400-review
git worktree add /home/agentcube-pr400-review refs/remotes/upstream/pr/400
```

结果：

```text
HEAD is now at 3e4ac99 feat(picod): add Prometheus metrics endpoint
```

后续所有源码阅读和临时测试都在 `/home/agentcube-pr400-review` 里进行。

## 验证命令

### Focused PicoD test

```bash
go test ./pkg/picod -count=1
```

结果：

```text
ok  	github.com/volcano-sh/agentcube/pkg/picod	4.204s
```

### Metrics test repeat

```bash
go test ./pkg/picod -run TestMetrics_Exposition -count=20
```

结果：

```text
ok  	github.com/volcano-sh/agentcube/pkg/picod	1.885s
```

### Race test

```bash
go test -race ./pkg/picod -count=1
```

结果：

```text
ok  	github.com/volcano-sh/agentcube/pkg/picod	6.837s
```

> 分析：这些测试说明 #400 当前在 PicoD 包层面没有明显编译、单测或 race 问题。后续 review 不应说“PR 不能跑”，而应聚焦更具体的指标语义和覆盖缺口。

## 源码阅读：metrics.go

`pkg/picod/metrics.go` 新增四个 collector：

```go
picod_active_executions
picod_execute_requests_total{status}
picod_http_requests_total{method,path,status_code}
picod_http_request_duration_seconds{method,path}
```

值得肯定的点：

- 使用 `prometheus.NewRegistry()` 创建 private registry，避免污染 default registry，也避免测试间重复注册 panic。
- `path := c.FullPath()`，并在空 path 时使用固定 `"unmatched"`，已避免把任意 404 URL 原样放进 label 造成高基数。
- `/metrics` 与 `/health` 被排除在 HTTP metrics 外，能减少 scrape 自身噪音。

需要注意的点：

- middleware 的观测范围取决于注册顺序；当前它不是最外层 middleware。
- `path` label 用 Gin route pattern，而不是 raw URL，这是对的；但 `unmatched` 行为应补一个单测，因为这是 security / cardinality 相关行为。

> 注释：Prometheus label cardinality 是可观测性系统里很实际的问题。如果把 `/random/<uuid>` 这类原始 path 放进 label，攻击者或误配置流量可以持续创建新 time series，最后把 Prometheus 或进程内 registry 撑爆。

## 源码阅读：server.go

当前 middleware 顺序：

```go
engine.Use(gin.Logger())
engine.Use(gin.Recovery())
engine.Use(maxBodySizeMiddleware())
engine.Use(s.metrics.Middleware())
engine.MaxMultipartMemory = MaxBodySize
engine.Use(gzip.Gzip(...))
```

`maxBodySizeMiddleware()` 在 `ContentLength > MaxBodySize` 时会：

```go
c.JSON(http.StatusRequestEntityTooLarge, ...)
c.Abort()
return
```

因为 metrics middleware 注册在它后面，`413` 请求不会进入 metrics middleware。

> 分析：这不是纯理论问题。body-size rejection 是 PicoD 对外暴露 API 的真实失败路径，而且大请求/恶意请求恰恰是 SRE 想在 HTTP metrics 里看到的异常流量。如果 metrics 只记录 handler 成功进入后的请求，它对边界失败的可观测性是不完整的。

## 临时测试：证明 413 不入 HTTP metrics

我在隔离 worktree 里临时加了一个测试文件 `pkg/picod/metrics_order_temp_test.go`，构造超大请求并检查 registry。临时代码没有保留，最后已删除。

临时测试逻辑：

1. 启动 `NewServer`。
2. 对 `/api/execute` 发送 `ContentLength > MaxBodySize` 的 body。
3. 确认 HTTP status 是 `413`。
4. 从 `server.metrics.Registry.Gather()` 查找 `picod_http_requests_total{path="/api/execute",status_code="413"}`。

先用“当前没有记录 413”的断言运行，测试通过，说明缺口存在：

```text
=== RUN   TestTempMetricsDoesNotRecordMaxBodyRejection
[GIN] 2026/06/26 - 17:17:10 | 413 | 45.009µs | 127.0.0.1 | POST "/api/execute"
--- PASS: TestTempMetricsDoesNotRecordMaxBodyRejection
```

再反向写成期望存在 413 metrics，当前 PR 失败：

```text
=== RUN   TestTempMetricsRecordsMaxBodyRejection
[GIN] 2026/06/26 - 17:17:33 | 413 | 43.954µs | 127.0.0.1 | POST "/api/execute"
    metrics_order_temp_test.go:54: missing picod_http_requests_total sample for POST /api/execute 413
--- FAIL: TestTempMetricsRecordsMaxBodyRejection
```

临时把 middleware 顺序改成：

```go
engine.Use(gin.Logger())
engine.Use(gin.Recovery())
engine.Use(s.metrics.Middleware())
engine.Use(maxBodySizeMiddleware())
```

同一个反向测试通过：

```text
=== RUN   TestTempMetricsRecordsMaxBodyRejection
[GIN] 2026/06/26 - 17:17:44 | 413 | 76.5µs | 127.0.0.1 | POST "/api/execute"
--- PASS: TestTempMetricsRecordsMaxBodyRejection
```

最后恢复 worktree：

```bash
git checkout -- pkg/picod/server.go
rm -f pkg/picod/metrics_order_temp_test.go
git status --short
```

`git status --short` 无输出，说明临时验证代码已清理。

## Finding 1：HTTP metrics 漏掉 body-size rejection

严重程度：中。

位置：

- `pkg/picod/server.go:81-85`
- `pkg/picod/server.go:114-125`
- `pkg/picod/metrics.go:93-113`

问题：

`picod_http_requests_total` 和 `picod_http_request_duration_seconds` 的目标是记录 HTTP request behavior，但 metrics middleware 注册在 `maxBodySizeMiddleware()` 后面。超过 `MaxBodySize` 的请求会被 body-size middleware 直接返回 413 并 `Abort()`，后续 metrics middleware 没有机会执行。

影响：

- 413 请求不会出现在 `picod_http_requests_total`。
- Prometheus 无法看到一类很重要的异常/攻击/误用流量。
- 当前 tests 只覆盖正常 `/api/execute` 200，没有覆盖 early rejection。

建议：

把 metrics middleware 放在 body-size limiter 之前，并补一个测试：

- 发送 oversized `/api/execute` 请求。
- 确认 response 是 413。
- 确认 registry 中有 `picod_http_requests_total{method="POST",path="/api/execute",status_code="413"}`。

是否需要放在 `gin.Recovery()` 之前：

- Copilot 原评论建议放在 `Recovery` 前，以便 panic 也被记录。
- 这要更谨慎：如果 metrics middleware 在 Recovery 前，`c.Next()` 内部 panic 时，metrics middleware 后半段能否在 panic 后继续执行取决于 Gin recovery / panic unwinding 行为，最好用专门 panic route 测试确认。
- 当前可以先解决确定的 `maxBodySizeMiddleware()` early abort；panic metrics 作为单独增强验证。

> 分析：review comment 应避免过度声称“必须放在 Recovery 前”。本地已经证明的是“必须放在 maxBodySizeMiddleware 前才能覆盖 413”。panic 场景还需要构造测试，不宜只凭框架直觉断言。

## Finding 2：active_executions 指标语义不清

严重程度：低到中。

位置：

- `pkg/picod/execute.go:55-57`
- `pkg/picod/execute.go:120-121`
- `pkg/picod/metrics.go:41-44`

当前实现：

```go
func (s *Server) ExecuteHandler(c *gin.Context) {
    s.metrics.ActiveExecutions.Inc()
    defer s.metrics.ActiveExecutions.Dec()

    var req ExecuteRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        ...
    }
    ...
    err := cmd.Run()
}
```

指标名：

```text
picod_active_executions
```

Help 文案：

```text
Number of execute handler invocations currently in flight (including validation).
```

问题：

- 指标名像是在表达“active command executions”。
- Help 文案实际表达的是“execute handler invocations in flight，包括 validation”。
- PR body 里写的是 “Gauge tracking in-flight execute requests”，与指标名也有轻微不一致。

这会影响 operator 解读：

- 如果 malformed JSON 流量很多，gauge 会升高，但实际上没有任何命令进程在跑。
- 如果要看 sandbox 内真正并发执行压力，这个指标不够精确。

两种可接受修法：

1. 如果指标要表达 active command executions：把 `Inc()` / `Dec()` 移到参数校验、working dir 准备之后，只包住 `cmd.Run()`。
2. 如果指标要表达 active execute handler requests：保留当前统计窗口，但建议改名或至少统一文案，例如 `picod_active_execute_requests`。

> 注释：这里不是说当前代码一定错，而是指标名称、Help 文案、PR body、operator 预期需要一致。可观测性指标一旦发布，后面改名会影响 dashboard 和 alert rule，因此最好在首次合入前定清楚。

## Finding 3：metrics endpoint 暴露不等于集群可 scrape

严重程度：信息提示 / scope question。

位置：

- `pkg/picod/server.go:104-108`
- `test/e2e/e2e_code_interpreter.yaml`
- `test/e2e/e2e_code_interpreter_warmpool.yaml`
- `pkg/apis/runtime/v1alpha1/codeinterpreter_types.go`

当前 PR 做的是：

```go
engine.GET("/metrics", s.metrics.Handler())
```

但 CodeInterpreter 的默认端口暴露是：

```yaml
spec:
  ports:
    - pathPrefix: "/"
      port: 8080
      protocol: "HTTP"
```

这意味着：

- PicoD Pod 内确实有 `/metrics`。
- Router 路由层可能可以转发到 sandbox `/metrics`，但这不等于 Prometheus 能自动 scrape sandbox Pod。
- 当前 PR 没有新增 Pod annotation、Service、ServiceMonitor、PodMonitor 或 docs。

我的判断：

- 不应要求 #400 一次解决完整 Prometheus discovery，因为 sandbox Pod 是动态 session runtime，scrape 设计可能牵涉安全、租户、metrics 暴露边界和 label cardinality。
- 但 PR body 应明确 scope：本 PR 只添加 PicoD process-local Prometheus endpoint；集群级 scrape / ServiceMonitor / Router metrics exposure 是后续工作。

> 分析：这个点适合写在 report 或 PR body，不一定适合作为 blocking review comment。因为 feature 的第一步可以只是 endpoint，但 reviewer 需要知道它不是“完整 observability integration”。

## Line-level review matrix

| 文件 / 行 | 观察 | 风险类型 | 本地证据 | 建议 |
| --- | --- | --- | --- | --- |
| `pkg/picod/server.go:81-85` | metrics middleware 注册在 `maxBodySizeMiddleware()` 后面 | HTTP metrics coverage gap | 临时测试确认 413 不进入 `picod_http_requests_total` | 把 metrics middleware 放到 body-size limiter 前，并补 413 测试 |
| `pkg/picod/server.go:107-108` | `/metrics` 无鉴权，与 `/health` 一样公开 | scope / security clarification | PicoD 当前 API group 才加 JWT auth，health/metrics 都在外层 | PR body 说明 endpoint scope；后续再讨论 scrape 暴露与网络策略 |
| `pkg/picod/metrics.go:96-99` | unmatched path 使用固定 `"unmatched"` | cardinality protection | 当前源码已修 AI reviewer 指出的 raw path fallback | 补 regression test，避免后续改回 raw URL path |
| `pkg/picod/metrics.go:100-104` | `/metrics` 与 `/health` 不记录 HTTP metrics | observability scope | 源码明确 skip | 可以接受，避免 scrape noise；PR body 可说明 |
| `pkg/picod/metrics.go:110-112` | status code 在 `c.Next()` 后读取 | 正常路径可记录最终状态 | 成功 `/api/execute` 测试已有 200 sample | early abort 取决于 middleware 顺序 |
| `pkg/picod/execute.go:55-57` | active gauge 包住整个 handler | metric semantics | invalid request 也会短暂计入 gauge | 明确 rename/help 或把 gauge 移到 `cmd.Run()` 窗口 |
| `pkg/picod/execute.go:60-90` | bind/empty command/timeout invalid 都计入 `invalid` | label taxonomy | 源码可读，但新增测试未覆盖这些 status | 增加 invalid label tests |
| `pkg/picod/execute.go:127-150` | timeout/success/error outcome 分类 | label taxonomy | 源码按 context deadline 和 process exit 分类 | 增加 timeout/non-zero exit tests |
| `pkg/picod/execute.go:162-185` | working dir invalid/error 分类 | label taxonomy | mkdirSafe 500 已改成 `error` | 可补 server error path 或至少保留源码说明 |
| `pkg/picod/metrics_test.go:33-100` | test 只覆盖 exposition + success path | test coverage | `go test` 和 `-count=20` 通过 | 增加 negative path tests，不只看 coverage 百分比 |
| `pkg/picod/metrics_test.go:152-153` | histogram `SampleSum > 0` | flake risk | 本地 `-count=20` 未复现，但 AI reviewer 指出合理 | 更稳妥改为 `SampleCount > 0` + `SampleSum >= 0` |

> 注释：line-level matrix 的目的不是给作者施压，而是让自己能解释“为什么这个 review 点是真问题”。比如 middleware 顺序有本地失败测试；active gauge 是语义一致性；scrape scope 是产品边界。三者证据强度不同，review 语气也应不同。

## Metrics 语义拆解

### HTTP request metrics

`picod_http_requests_total{method,path,status_code}` 应回答的问题：

- PicoD 收到了多少请求？
- 哪些 API path 流量最大？
- 哪些 status code 异常升高？

因此它最好覆盖：

- auth failure，例如 401。
- request validation failure，例如 400。
- body-size rejection，例如 413。
- handler success，例如 200。
- unmatched route，例如 404，但 path label 应固定成 `unmatched`。

当前 #400 能覆盖正常进入 metrics middleware 的请求；不能覆盖在它之前被拦截的请求。

### Execute outcome metrics

`picod_execute_requests_total{status}` 应回答的问题：

- execute 请求是成功、失败、超时还是请求无效？
- 失败是用户代码非零退出、PicoD server-side error，还是 timeout？

当前分类大体合理：

- `invalid`：JSON / empty command / bad timeout / invalid working dir。
- `timeout`：context deadline exceeded。
- `success`：process exit code 0。
- `error`：non-zero exit、process state abnormal、server-side working dir create failure。

需要注意：

- PicoD 当前对用户命令非零退出仍返回 HTTP 200，并在 JSON body 中返回 `exit_code`。因此 `picod_http_requests_total{status_code="200"}` 不能代表命令成功，必须结合 `picod_execute_requests_total{status="error"}`。
- 如果 future dashboard 只看 HTTP 5xx，会漏掉用户代码执行失败。

> 分析：这也是为什么 #400 的 execute outcome counter 有价值。PicoD 的 HTTP status 和命令 exit status 是两层语义，不能混为一谈。

### Active gauge

这里有两个可选定义：

| 定义 | 指标名建议 | 统计窗口 | 适合回答的问题 |
| --- | --- | --- | --- |
| active execute requests | `picod_active_execute_requests` | handler 入口到响应返回 | 当前 PicoD 同时处理多少 execute HTTP 请求 |
| active command executions | `picod_active_executions` | `cmd.Run()` 开始到结束 | sandbox 内真正同时跑多少命令进程 |

当前代码是第一种，名字更像第二种。

## 如果要补测试，建议顺序

优先级从高到低：

1. `TestMetricsMiddleware_RecordsBodySizeRejection`
   - 发送 oversized `POST /api/execute`。
   - 期望 HTTP 413。
   - 期望 `picod_http_requests_total{method="POST",path="/api/execute",status_code="413"}` 存在。

2. `TestMetricsMiddleware_UsesUnmatchedPathForUnknownRoutes`
   - 请求 `/random/<uuid>`。
   - 期望 404。
   - 期望 path label 是 `unmatched`。

3. `TestExecuteMetrics_RequestOutcomes`
   - invalid JSON -> `invalid`。
   - empty command -> `invalid`。
   - `sh -c 'exit 7'` -> `error`。
   - short timeout + sleep -> `timeout`。

4. `TestMetricsEndpoint_NotGzipped`
   - 请求 `/metrics`，带 `Accept-Encoding: gzip`。
   - 确认没有 gzip。
   - 这个测试重要性较低，因为 gzip exclude 已在源码显式列出。

5. `TestActiveExecutionsGauge_Window`
   - 如果决定只统计 `cmd.Run()`，用 blocking command 验证 gauge 在命令运行期间为 1，invalid request 后仍为 0。
   - 如果决定统计 handler in-flight，则改测试名和指标文案，不强求这个测试。

> 注释：测试应服务于指标契约，而不是单纯提高 coverage。最关键的是防止 label taxonomy 和 cardinality 这种运维契约被无意破坏。

## 与 AgentCube 后续 observability 的关系

PicoD metrics 是 data-plane observability 的底层一环，但 AgentCube 未来真正有用的观测面至少有四层：

| 层 | 指标对象 | 例子 | #400 覆盖情况 |
| --- | --- | --- | --- |
| SDK / client | 用户端请求、重试、超时 | SDK create/run/delete latency | 未覆盖 |
| Router | session route、auth、proxy latency | Router -> PicoD proxy duration、resume-before-proxy | 未覆盖 |
| WorkloadManager / Store | session lifecycle、create/delete/GC | session create latency、store CAS conflict | 未覆盖 |
| PicoD | sandbox 内 HTTP / execute / file ops | `/api/execute` outcome、active executions | #400 开始覆盖 |

> 分析：这说明 #400 是必要但不完整的一步。后续做 Sleep/Resume 或 benchmark 时，只有 PicoD metrics 还不够，还需要 Router 和 WorkloadManager 的状态转移指标。Day31 先把 PicoD 这一层审清楚。

## 不作为 blocking 的观察

以下观察今天先不建议发成 blocking comment：

1. `/metrics` 未鉴权。
   - 当前 `/health` 也未鉴权，`/metrics` 常见部署也是无鉴权但由网络策略限制。
   - 是否需要 auth 取决于 sandbox Pod 网络模型和 Prometheus scrape 设计。

2. 没有 ServiceMonitor / PodMonitor。
   - 这属于部署集成，不一定在 #400 scope 内。
   - 可以让 PR body 写清楚 limitation。

3. `go.mod` direct dependency 变化。
   - 既然生产代码直接 import `prometheus/client_golang`，从 indirect 变 direct 是合理的。

4. 没有 e2e 验证 `/metrics`。
   - PicoD process-level endpoint 用 package test 足够覆盖第一阶段。
   - 真正 e2e scrape 要等部署设计明确。

## 已确认修复的 AI reviewer 点

### 高基数 path label

AI reviewer 担心 `c.FullPath()` 为空时 fallback 到 raw URL path。当前代码已经是：

```go
path := c.FullPath()
if path == "" {
    path = "unmatched"
}
```

结论：这个问题在当前 head `3e4ac99` 已修。

建议补测试：

- 请求随机不存在路径，例如 `/does-not-exist/<uuid>`。
- 确认 metrics 里 path label 是 `unmatched`，不是 raw path。

### mkdirSafe 500 被标成 invalid

AI reviewer 担心 server-side mkdir 失败被标成 `invalid`。当前 `prepareWorkingDir` 里已经是：

```go
s.metrics.ExecuteRequestsTotal.WithLabelValues("error").Inc()
c.JSON(http.StatusInternalServerError, ...)
```

结论：这个问题在当前 head `3e4ac99` 已修。

## 测试覆盖评价

当前新增 `TestMetrics_Exposition` 覆盖了：

- `/metrics` endpoint 返回 200。
- 成功执行一次 `/api/execute`。
- registry 中存在四类 metrics。
- `picod_execute_requests_total{status="success"}` 为 1。
- `picod_http_requests_total{method="POST",path="/api/execute",status_code="200"}` 为 1。
- latency histogram 有 sample。
- active gauge 最终回到 0。

不足：

- 没覆盖 invalid JSON / empty command / invalid timeout 的 `invalid` label。
- 没覆盖 command non-zero exit 的 `error` label。
- 没覆盖 timeout 的 `timeout` label。
- 没覆盖 working dir server error 的 `error` label。
- 没覆盖 unmatched route 的 fixed path label。
- 没覆盖 early abort，例如 body-size 413。
- `SampleSum > 0` 曾被 Copilot 指出可能 flake；当前我本地 `-count=20` 过了，但更稳妥是只断言 `SampleCount > 0` 且 `SampleSum >= 0`。

> 注释：coverage percentage 高不代表语义完整。metrics 这种代码更重要的是 label 是否稳定、失败分类是否正确、异常路径是否能被观测到。

## 可选 upstream review 草稿

以下草稿今天不发。若后续用户确认，可以作为 #400 review comment 或 issue comment 的基础。

```md
I did a local pass over the current head (`3e4ac99`) and the PicoD package tests pass for me:

- `go test ./pkg/picod -count=1`
- `go test -race ./pkg/picod -count=1`
- `go test ./pkg/picod -run TestMetrics_Exposition -count=20`

One issue still looks worth fixing before merge:

`s.metrics.Middleware()` is currently registered after `maxBodySizeMiddleware()` in `pkg/picod/server.go`. Requests rejected by the body-size middleware return `413` and abort before the metrics middleware runs, so they are missing from `picod_http_requests_total` and `picod_http_request_duration_seconds`.

I verified this locally with a temporary test that sends an oversized `POST /api/execute` request. The response is `413`, but there is no `picod_http_requests_total{method="POST", path="/api/execute", status_code="413"}` sample. Moving the metrics middleware before `maxBodySizeMiddleware()` makes the same test pass.

Suggested focused test coverage:

1. Send an oversized `POST /api/execute`.
2. Assert the response status is `413`.
3. Assert `picod_http_requests_total` includes `method="POST", path="/api/execute", status_code="413"`.

Two smaller follow-ups:

- `picod_active_executions` currently counts the whole execute handler, including JSON parsing and validation. If the intended metric is active command executions, the gauge should wrap only the `cmd.Run()` window; otherwise the name/help text should make it clear that this is active execute handler requests.
- It would be useful to add a regression test for unmatched routes to ensure the path label stays fixed as `unmatched` and never uses the raw URL path.
```

## 今天的产出

1. 确认 #400 是适合 Day31 的 review 目标，而不是继续等待 #387 / #403。
2. 建立 `/home/agentcube-pr400-review` 隔离 worktree。
3. 跑通 `go test ./pkg/picod -count=1`。
4. 跑通 `go test -race ./pkg/picod -count=1`。
5. 跑通 `go test ./pkg/picod -run TestMetrics_Exposition -count=20`。
6. 用临时测试证明 `413` early rejection 不进入 HTTP metrics。
7. 临时调整 middleware 顺序并证明该修法可以让 `413` 进入 metrics。
8. 删除所有临时测试和临时代码，保持 PR worktree clean。
9. 形成可选 upstream review 草稿，等待用户确认后才可能发布。

## 下一步

建议今天后续有两条路线：

1. 如果用户希望参与 #400 review：先把英文草稿压缩成一个 focused review comment，只发 middleware 顺序和测试建议，不把所有想法都塞进去。
2. 如果用户希望继续积累 Day31 工作量：可以继续 review #405 文档准确性，重点核对 PicoD auth、SDK ttl、file API response、Redis troubleshooting 等已经被 Copilot 指出的文档偏差，并形成“文档与源码对齐矩阵”。

暂不建议：

- 不抢 #394 / #395 实现，因为已有 assignee。
- 不直接给 #400 提 PR，先让作者自己处理 review feedback。
- 不把 `/metrics` scrape discovery 设计混进 #400，除非 maintainer 明确要求扩 scope。
