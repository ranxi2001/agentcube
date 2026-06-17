# Day 16: Adaptation to the latest kubernetes-sigs/agent-sandbox

日期：2026-06-17

## 任务背景

社区 #386 中 `zhzhuang-zju` 提出：AgentCube 当前 `code-interpreter` warm pool 使用 `kubernetes-sigs/agent-sandbox v0.1.1` 的 `SandboxWarmPool` / `SandboxClaim` 能力，但本地测试发现 AgentCube 已经不能直接兼容最新 `agent-sandbox`。6.17 例会后，这个任务明确由我独立负责。

任务目标不是只把 `go.mod` 里的版本号改掉，而是完成一轮可提交 upstream PR 的兼容性适配：

- 找到 `agent-sandbox` 从 `v0.1.1` 到最新版本的关键 API / 行为变化。
- 直接升级依赖，复现编译失败并做最小代码修复。
- 用测试驱动确认修复不只停留在“编译通过”，还覆盖 warm-pool-backed CodeInterpreter 的关键运行语义。
- 形成 upstream PR 分支，报告清楚 scope、限制和验证结果。

## 分支与工作区

为了避免把实习报告和中文记录混进 upstream PR 分支，代码修复使用独立 worktree。

| 项目 | 路径 / 分支 |
| --- | --- |
| 实习记录主工作区 | `/home/agentcube` |
| 代码修复 worktree | `/home/agentcube-agent-sandbox-latest` |
| feature 分支 | `feat/agent-sandbox-latest` |
| 分支基线 | `upstream/main` |
| 基线 commit | `0fd9151 Merge pull request #376 from vivek41-glitch/fix-duplicate-test` |

创建命令：

```bash
git fetch upstream main
git worktree add -b feat/agent-sandbox-latest /home/agentcube-agent-sandbox-latest upstream/main
```

当前主目录 `/home/agentcube` 保留实习报告、Day15 会议纪要和 `PROGRESS.md` 更新；代码 PR 分支只放 upstream 可 review 的代码、依赖和测试改动。

## 适配策略：两条腿走路

这次任务按两条路线并行推进，最后把证据汇合成 PR scope。

### 路线 A：分析升级历史和变动，分析驱动适配

目标：先理解上游为什么变、变在哪里、会影响 AgentCube 哪些路径，避免只修掉第一个编译错误。

需要输出：

1. `agent-sandbox` 版本矩阵：`v0.1.1`、`v0.2.1`、`v0.3.10`、`v0.4.6`、`v0.5.0rc1`。
2. API / import 差异：例如 `SandboxPodNameAnnotation` 从 `controllers` 内部包迁到公开 API 包。
3. warm pool 行为差异：从 bare Pod adoption 变成 full Sandbox CR adoption。
4. `SandboxClaim` 运行语义：真实 adopted Sandbox 名通过 `claim.Status.SandboxStatus.Name` 或相关 label / annotation 表达，不一定等于 claim 名。
5. AgentCube 影响面：Workload Manager create/wait/store/delete、GC、e2e helper、文档中的 warm pool 描述。

### 路线 B：直接升级、编译跑通、测试驱动适配

目标：在 clean feature branch 上直接升级目标依赖，先复现失败，再小步修复并用测试证明行为。

需要输出：

1. `go get sigs.k8s.io/agent-sandbox@<target>` 后的实际依赖变化。
2. 编译失败日志和最小修复。
3. targeted tests：至少 `go test ./pkg/workloadmanager ./cmd/workload-manager ./cmd/agentd`。
4. 非 e2e 全量测试：`go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test`。
5. 如果没有标准 Kubernetes / kubeconfig 环境，则明确记录 e2e 未验证的原因，不声称完整运行通过。

## 目标版本判断

当前存在两个“最新”的概念，需要区分：

| 版本 | 状态 | 判断 |
| --- | --- | --- |
| `v0.4.6` | Go module `latest` | `go list -m -json sigs.k8s.io/agent-sandbox@latest` 返回 `v0.4.6`，适合作为默认稳定适配目标 |
| `v0.5.0rc1` | GitHub tag / release candidate | Git tag 存在，但不是标准 Go semver prerelease 写法；Go 会解析成 pseudo-version，需要单独评估是否适合作为 upstream PR 依赖目标 |

验证命令：

```bash
/tmp/go-toolchain/go/bin/go list -m -versions sigs.k8s.io/agent-sandbox
/tmp/go-toolchain/go/bin/go list -m -json sigs.k8s.io/agent-sandbox@latest
/tmp/go-toolchain/go/bin/go list -m -json sigs.k8s.io/agent-sandbox@v0.5.0rc1
git ls-remote --tags https://github.com/kubernetes-sigs/agent-sandbox.git 'refs/tags/v0.5.0rc1' 'refs/tags/v0.4.6'
```

已观察到：

```text
sigs.k8s.io/agent-sandbox v0.1.0-rc.0 v0.1.0-rc.1 v0.1.0-rc.2 v0.1.0 v0.1.1 v0.2.0 v0.2.1 v0.3.10 v0.4.0 v0.4.1 v0.4.2 v0.4.3 v0.4.5 v0.4.6
```

`@latest` 结果：

```json
{
  "Path": "sigs.k8s.io/agent-sandbox",
  "Version": "v0.4.6",
  "Query": "latest",
  "GoVersion": "1.26.2"
}
```

`@v0.5.0rc1` 结果：

```json
{
  "Path": "sigs.k8s.io/agent-sandbox",
  "Version": "v0.4.7-0.20260608211546-6af1bbd0cf64",
  "Query": "v0.5.0rc1",
  "GoVersion": "1.26",
  "Origin": {
    "VCS": "git",
    "URL": "https://github.com/kubernetes-sigs/agent-sandbox",
    "Hash": "6af1bbd0cf64256ddf099e5a6ee1cbed17298057"
  }
}
```

判断：

- `v0.5.0rc1` 不是不能测；它可以通过 pseudo-version 拉取。
- 但 upstream PR 默认直接依赖 pseudo-version 风险更高，是否要以 `v0.5.0rc1` 为目标需要维护者确认。
- 当前先以 `v0.4.6` 作为稳定目标做最小兼容 PR，同时把 `v0.5.0rc1` 纳入兼容性矩阵。

## 当前已复现的卡点

### 卡点 1：本机 `go` 不在 PATH

命令：

```bash
go list -m -versions sigs.k8s.io/agent-sandbox
```

现象：

```text
/bin/bash: go: command not found
```

处理：

- 使用已安装的固定工具链路径：`/tmp/go-toolchain/go/bin/go`。
- 当前工具链版本：

```text
go version go1.24.9 linux/amd64
```

注意：升级到 `agent-sandbox v0.4.6` 后，Go 会切到更高工具链要求。

### 卡点 2：`agent-sandbox v0.4.6` 要求 Go 1.26.2

命令：

```bash
cd /home/agentcube-agent-sandbox-latest
/tmp/go-toolchain/go/bin/go get sigs.k8s.io/agent-sandbox@v0.4.6
```

现象：

```text
go: sigs.k8s.io/agent-sandbox@v0.4.6 requires go >= 1.26.2; switching to go1.26.4
go: upgraded go 1.24.4 => 1.26.2
go: removed toolchain go1.24.9
...
go: upgraded sigs.k8s.io/agent-sandbox v0.1.1 => v0.4.6
go: upgraded sigs.k8s.io/controller-runtime v0.22.2 => v0.23.3
go: upgraded k8s.io/api v0.34.1 => v0.35.4
go: upgraded k8s.io/apimachinery v0.34.1 => v0.35.4
go: upgraded k8s.io/client-go v0.34.1 => v0.35.4
```

影响：

- 这不是单一依赖升级；它会带动 Go version、Kubernetes libraries、controller-runtime 和 OpenTelemetry 等一批依赖升级。
- PR scope 需要明确写出 Go version bump 是否可接受。
- 如果维护者不希望 v0.2.0 立刻升级 Go / K8s 依赖，需要考虑退而求其次：先适配 `v0.3.10`，或等待 `agent-sandbox` 发布更合适的稳定版本。

### 卡点 3：直接升级到 `v0.4.6` 后编译失败

命令：

```bash
cd /home/agentcube-agent-sandbox-latest
/tmp/go-toolchain/go/bin/go test ./pkg/workloadmanager ./cmd/workload-manager ./cmd/agentd
```

现象：

```text
# github.com/volcano-sh/agentcube/pkg/workloadmanager
pkg/workloadmanager/handlers.go:246:63: undefined: controllers.SandboxPodNameAnnotation
FAIL	github.com/volcano-sh/agentcube/pkg/workloadmanager [build failed]
FAIL	github.com/volcano-sh/agentcube/cmd/workload-manager [build failed]
FAIL	github.com/volcano-sh/agentcube/cmd/agentd [build failed]
FAIL
```

根因：

- AgentCube 当前在 `pkg/workloadmanager/handlers.go` 和 `pkg/workloadmanager/handlers_test.go` 里导入 `sigs.k8s.io/agent-sandbox/controllers`。
- 旧版本 `v0.1.1 / v0.2.1` 中，`SandboxPodNameAnnotation` 位于 controller 内部包。
- 新版本中该常量迁到公开 API 包：`sandboxv1alpha1.SandboxPodNameAnnotation`。

最小修复方向：

- 删除 `sigs.k8s.io/agent-sandbox/controllers` 导入。
- 将 `controllers.SandboxPodNameAnnotation` 替换为 `sandboxv1alpha1.SandboxPodNameAnnotation`。

但这个修复只能解决编译问题，不能证明运行语义正确。

## 已发现的运行语义风险

### 风险 1：新版 warm pool 可能 adopt generated-name Sandbox

`agent-sandbox v0.4.6` 中的 warm pool controller 会创建完整 `Sandbox` CR：

```go
// createPoolSandbox creates a full Sandbox CR (with pod template, service, etc.) for the warm pool.
func (r *SandboxWarmPoolReconciler) createPoolSandbox(...)
```

它使用 `GenerateName` 创建 pool sandbox。`SandboxClaim` adopt 后，真实 serving sandbox 名可能是 warm pool 预创建的 generated name，而不是 AgentCube 生成的 claim 名。

### 风险 2：AgentCube 当前只按 claim/sandboxName watch Ready

当前 AgentCube `handleSandboxCreate` 中的逻辑是：

```go
sandboxName := sandbox.Name
resultChan := s.sandboxController.WatchSandboxOnce(c.Request.Context(), namespace, sandboxName)
```

在旧路径中，claim 名和最终 Sandbox 名基本一致，所以这个 watcher 可以收到 Ready 事件。

在新路径中，claim 可能 adopt 一个已有 Sandbox，真实名字在：

```go
claim.Status.SandboxStatus.Name
```

因此如果 AgentCube 仍然只 watch claim 名，就可能漏掉 adopted Sandbox 的 Ready 事件，最终创建请求超时。

### 风险 3：store 不能简单保存 adopted Sandbox 名

删除路径中，AgentCube 根据 store 里的 `Kind` 和 `Name` 删除资源：

```go
if sandbox.Kind == types.SandboxClaimsKind {
    err = deleteSandboxClaim(ctx, dynamicClient, sandbox.SandboxNamespace, sandbox.Name)
} else {
    err = deleteSandbox(ctx, dynamicClient, sandbox.SandboxNamespace, sandbox.Name)
}
```

如果 warm-pool-backed CodeInterpreter 创建成功后，store 记录被改成 adopted Sandbox 名，而 `Kind` 仍是 `SandboxClaim`，后续 GC / delete 会拿 adopted Sandbox 名去删 SandboxClaim，可能删不到真正 claim，造成资源泄漏。

因此修复不能只是“用 createdSandbox 构建 store”：

- 等待和取 Pod IP 时需要使用真实 adopted Sandbox。
- store 里用于删除的 `Name` 仍应保留 SandboxClaim 名。
- 返回给 Router / 用户的 `SandboxName` 也要明确是 claim 名还是 serving sandbox 名，避免后续 delete / GC 语义混乱。

### 风险 4：e2e helper 的旧假设可能失效

当前 e2e helper 有旧语义假设：

- 通过 `SandboxClaim` owner 找到 `Sandbox`。
- 通过 `Pod.OwnerReferences.Kind == Sandbox` 找 Pod。
- 部分 warm pool 统计可能仍按 `SandboxWarmPool` owning Pods 的方式理解。

新版 `agent-sandbox` 里 warm pool 先拥有 `Sandbox`，claim adopt 后再转移 ownership。e2e helper 需要检查是否应改为优先通过 `SandboxClaim.Status.SandboxStatus.Name` 定位 adopted Sandbox。

## 初步实现方向

先做一个小而明确的兼容 PR，避免一次性把 Sleep/Resume 或 E2B API 方向混进来。

代码层面计划：

1. 升级 `sigs.k8s.io/agent-sandbox` 到 `v0.4.6`，并接受由其带来的 Go / K8s dependency bump，除非维护者要求换目标版本。
2. 替换 `SandboxPodNameAnnotation` 的 import 来源，使用公开 API 包常量。
3. 对 warm-pool-backed `SandboxClaim` 路径新增等待真实 adopted Sandbox 的逻辑：
   - 创建 claim 后轮询 / 读取 `SandboxClaim.Status.SandboxStatus.Name`；
   - 注册或等待该真实 Sandbox Ready；
   - 用真实 Sandbox annotation / pod name 获取 Pod IP。
4. 更新 store 构建逻辑：
   - `Kind == SandboxClaim` 时，store `Name` 继续保存 claim 名；
   - `SandboxID`、`EntryPoints`、`Status` 可来自真实 serving Sandbox；
   - `ExpiresAt` 优先保留 AgentCube 创建 claim 时根据 `MaxSessionDuration` 得到的值，避免 adopted Sandbox 的时间字段覆盖用户 session TTL。
5. 补 focused unit tests：
   - `SandboxPodNameAnnotation` 从公开 API 包读取。
   - claim 名和 adopted Sandbox 名不一致时，store 仍保存 claim 名。
   - claim status 指向 adopted Sandbox 时，创建流程不会只等待旧 claim 名。

测试层面计划：

```bash
/tmp/go-toolchain/go/bin/go test ./pkg/workloadmanager
/tmp/go-toolchain/go/bin/go test ./pkg/workloadmanager ./cmd/workload-manager ./cmd/agentd
/tmp/go-toolchain/go/bin/go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs /tmp/go-toolchain/go/bin/go test
```

e2e 当前预计仍受本机环境限制：

- 当前机器没有完整标准 Kubernetes / kubeconfig 环境。
- 之前 kind 标准集群在 kubelet cgroup/QoS 初始化处失败。
- 本地不能声称 warm-pool-backed CodeInterpreter 真实 runtime path 已通过，只能提交 unit / non-e2e validation，并在 PR notes 中说明。

## 第一轮代码修复结果

代码 worktree：`/home/agentcube-agent-sandbox-latest`

分支：`feat/agent-sandbox-latest`

当前已完成第一轮最小可测修复，改动范围如下：

| 文件 | 改动 |
| --- | --- |
| `go.mod` / `go.sum` | 升级 `sigs.k8s.io/agent-sandbox` 到 `v0.4.6`；该版本要求 Go `1.26.2`，并带动 `k8s.io/*`、`controller-runtime`、OpenTelemetry 等依赖升级 |
| `pkg/workloadmanager/handlers.go` | 删除对 `sigs.k8s.io/agent-sandbox/controllers` 内部包的依赖；改用 `sandboxv1alpha1.SandboxPodNameAnnotation`；普通 Sandbox 继续用原 watcher；SandboxClaim 路径改为等待 `SandboxClaim.Status.SandboxStatus.Name` 指向的真实 adopted Sandbox Ready |
| `pkg/workloadmanager/k8s_client.go` | 新增 dynamic client helper：`getSandbox` 和 `getSandboxClaim` |
| `pkg/workloadmanager/sandbox_helper.go` | placeholder 记录 `CreatedAt`；warm pool adopted Sandbox 路径会保留 placeholder 的 `CreatedAt` / `ExpiresAt`，避免被 pool Sandbox 的创建时间污染用户 session 生命周期 |
| `pkg/workloadmanager/handlers_test.go` | 新增 focused unit test：claim 名和 adopted Sandbox 名不一致时，创建流程使用 adopted Sandbox 获取 Pod IP / entrypoint，但 store 仍保存 SandboxClaim 名用于后续 delete / GC |

关键修复语义：

1. 解决直接编译失败：

```go
createdSandbox.Annotations[sandboxv1alpha1.SandboxPodNameAnnotation]
```

不再引用 `controllers.SandboxPodNameAnnotation`。

2. 处理新版 warm pool adopted Sandbox：

```go
claim.Status.SandboxStatus.Name
```

作为真实 serving Sandbox 名来源，而不是假设 claim 名等于 Sandbox 名。

3. 保持 delete / GC 语义不变：

```go
if sandboxClaim != nil {
    storeCacheInfo.Name = sandboxClaim.Name
    storeCacheInfo.SandboxNamespace = sandboxClaim.Namespace
}
```

这点很关键：如果 store 保存 adopted Sandbox 名，而 `Kind` 仍是 `SandboxClaim`，后续 `deleteSandboxClaim(namespace, name)` 会拿 adopted Sandbox 名删 claim，可能删不到真正 claim 并造成泄漏。

### 本轮测试结果

已通过：

```bash
/tmp/go-toolchain/go/bin/go test ./pkg/workloadmanager -run TestServerCreateSandboxClaimUsesAdoptedSandboxButStoresClaimName -count=1 -v
```

结果：

```text
=== RUN   TestServerCreateSandboxClaimUsesAdoptedSandboxButStoresClaimName
--- PASS: TestServerCreateSandboxClaimUsesAdoptedSandboxButStoresClaimName (0.00s)
PASS
ok  	github.com/volcano-sh/agentcube/pkg/workloadmanager	0.021s
```

已通过：

```bash
/tmp/go-toolchain/go/bin/go test ./pkg/workloadmanager
```

已通过：

```bash
/tmp/go-toolchain/go/bin/go test ./pkg/workloadmanager ./cmd/workload-manager ./cmd/agentd
```

结果：

```text
ok  	github.com/volcano-sh/agentcube/pkg/workloadmanager	0.206s
?   	github.com/volcano-sh/agentcube/cmd/workload-manager	[no test files]
?   	github.com/volcano-sh/agentcube/cmd/agentd	[no test files]
```

已通过非 e2e 全量 Go 测试：

```bash
/tmp/go-toolchain/go/bin/go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs /tmp/go-toolchain/go/bin/go test
```

结果：

```text
ok  	github.com/volcano-sh/agentcube/pkg/agentd
ok  	github.com/volcano-sh/agentcube/pkg/api
ok  	github.com/volcano-sh/agentcube/pkg/common/types
ok  	github.com/volcano-sh/agentcube/pkg/mtls
ok  	github.com/volcano-sh/agentcube/pkg/picod
ok  	github.com/volcano-sh/agentcube/pkg/router
ok  	github.com/volcano-sh/agentcube/pkg/store
ok  	github.com/volcano-sh/agentcube/pkg/workloadmanager
```

也已通过：

```bash
git diff --check
```

### 本轮仍未覆盖

- 没有跑 `test/e2e`，原因仍是本机没有稳定标准 Kubernetes / kubeconfig 环境。
- 没有验证真实 `agent-sandbox v0.4.6` controller 在集群中创建 / adopt warm pool Sandbox 的 runtime path。
- 没有处理 `v0.5.0rc1` / pseudo-version 作为 PR 目标的问题；当前实现按 Go module `latest` 的稳定版本 `v0.4.6` 做。
- 没有更新文档和 e2e helper。后续需要决定这个 PR 是否只做代码兼容，还是同时修正文档中“warm pool pod adoption”的旧描述。

## 当前状态

- `feat/agent-sandbox-latest` 已从 `upstream/main` 建好。
- `agent-sandbox v0.4.6` 直接升级已复现编译失败，且第一轮最小修复已完成。
- `v0.5.0rc1` 已确认可通过 pseudo-version 拉取，但不是 Go module `latest`。
- targeted tests、非 e2e Go 测试、真实 k3s runtime e2e、Python SDK、LangChain sandbox、MCP HTTP/stdio、math-agent LLM e2e 均已补充验证。
- kind 标准集群创建仍受本机 kubelet/cgroup 环境限制；本轮真实运行验证改用已有 k3s 集群完成。

## 第二轮真实集群验证

第一轮结果只能证明“编译和 unit/non-e2e 通过”。根据导师反馈，继续补了真实 k3s runtime 路径，重点验证：

- 直接 CodeInterpreter 是否能创建 Sandbox、执行命令、上传/下载文件。
- warm-pool-backed CodeInterpreter 是否能在 `agent-sandbox v0.4.6` 下 adopt pool Sandbox 并被 Router 调用。
- 压力场景下 warm pool replenishment 是否能保持成功率。
- Python SDK、LangChain wrapper、MCP server、math-agent 是否能跑通，避免只覆盖 Go e2e。

### 集群与组件环境

验证环境：

| 项目 | 值 |
| --- | --- |
| Kubernetes | k3s `v1.24.17+k3s1` |
| OS | CentOS Linux 8 |
| Kernel | `4.18.0-348.7.1.el8_5.x86_64` |
| container runtime | containerd `1.7.3-k3s1` |
| AgentCube namespace | `agentcube` |
| Workload namespace | `agentcube-day16` |
| WorkloadManager image | `workloadmanager:day16-v046` |
| Router image | `agentcube-router:day16-v046` |
| PicoD image | `picod:day16-v046` / `picod:latest` imported into k3s containerd |
| agent-sandbox controller | `registry.k8s.io/agent-sandbox/agent-sandbox-controller:v0.4.6` |

测试前保存了集群快照到：

```text
internship-reports/benchmarks/day16-agent-sandbox-k3s-validation/
```

包含 agent-sandbox controller、CRDs、AgentCube deployments、nodes、pods 和 default namespace 资源状态，用于回滚和复盘。

### kind 路径失败

尝试直接跑标准 kind e2e：

```bash
MTLS_ENABLED=false AGENT_SANDBOX_VERSION=v0.4.6 timeout 35m ./test/e2e/run_e2e.sh
```

失败点在创建 kind 集群阶段，不在 AgentCube 业务逻辑：

```text
kubeadm init timed out
cannot create ClusterRoleBinding
rate limiter deadline exceeded
```

又尝试指定较旧 node image：

```bash
kind create cluster --image kindest/node:v1.30.13 --wait 180s
```

仍超时。因此本轮不继续硬调 kind，改用已有 k3s 做真实 controller/runtime 验证，并在 PR notes 里说明 kind 不是本轮通过路径。

### CRD 与 Helm 卡点

应用当前分支生成的 CRD 时，普通 client-side apply 遇到 annotation 过大：

```bash
kubectl apply -f manifests/charts/base/crds
```

现象：

```text
metadata.annotations: Too long: must have at most 262144 bytes
```

根因是 CRD schema 很大，`kubectl.kubernetes.io/last-applied-configuration` annotation 超限。处理方式：

```bash
kubectl annotate crd codeinterpreters.runtime.agentcube.volcano.sh \
  kubectl.kubernetes.io/last-applied-configuration-
kubectl apply --server-side --force-conflicts --validate=false \
  -f manifests/charts/base/crds
```

之后 Helm 升级到本地 day16 镜像：

```bash
helm upgrade agentcube manifests/charts/base -n agentcube --reuse-values \
  --set redis.addr=redis.agentcube.svc.cluster.local:6379 \
  --set redis.password="" \
  --set workloadmanager.image.repository=workloadmanager \
  --set workloadmanager.image.tag=day16-v046 \
  --set workloadmanager.image.pullPolicy=IfNotPresent \
  --set router.image.repository=agentcube-router \
  --set router.image.tag=day16-v046 \
  --set router.image.pullPolicy=IfNotPresent \
  --set-json 'workloadmanager.extraEnv=[{"name":"REDIS_PASSWORD_REQUIRED","value":"false"}]' \
  --set-json 'router.extraEnv=[{"name":"REDIS_PASSWORD_REQUIRED","value":"false"}]' \
  --wait --timeout=10m
```

### 新发现：`v0.4.6` 默认 NetworkPolicy 会阻断 AgentCube

第一次真实 warm pool e2e 在 `agentcube-day16` namespace 失败：

```text
create session failed with status 504: {"message":"request timed out"}
```

进一步检查 `agent-sandbox v0.4.6` 的 `SandboxTemplate` 行为，发现它默认 `networkPolicyManagement: Managed`，并自动生成严格 NetworkPolicy：

- Pod selector：`agents.x-k8s.io/sandbox-template-ref-hash=<hash>`。
- Ingress：只允许同 namespace 且 `app=sandbox-router` 的 Pod。
- Egress：默认屏蔽私网地址段。

而 AgentCube 当前组件标签是：

```text
agentcube-router: app=agentcube-router
workloadmanager: app=workloadmanager
```

并且 WorkloadManager 会在创建 session 时先直连 Sandbox PodIP 做 entrypoint probe。结果是：

- 单次直接 Sandbox 路径没有 `SandboxTemplate` NetworkPolicy，因此能过。
- warm pool 路径通过 `SandboxTemplate -> SandboxWarmPool -> Sandbox -> Pod` 创建 Pod，会被默认 NetworkPolicy 选择。
- 跨 namespace workload 下，WorkloadManager / Router 都不满足 `app=sandbox-router` 规则，导致 probe / proxy 超时。

最小兼容修复是让 AgentCube 创建的 CodeInterpreter `SandboxTemplate` 显式保留旧行为：

```go
NetworkPolicyManagement: extensionsv1alpha1.NetworkPolicyManagementUnmanaged
```

并且更新已有模板时也把 `Managed` 修正为 `Unmanaged`。这个修复避免把 agent-sandbox 的“默认 Sandbox Router 安全策略”误套到 AgentCube 自己的 Router/WorkloadManager 架构上。后续如果社区希望保留 managed NetworkPolicy，需要另开设计：AgentCube 应该显式生成允许 `agentcube-router` / `workloadmanager` 的 namespaceSelector + podSelector，而不是依赖 agent-sandbox 默认值。

新增 focused unit tests：

```text
TestEnsureSandboxTemplateDisablesAgentSandboxDefaultNetworkPolicy
TestEnsureSandboxTemplateUpdatesManagedNetworkPolicyToUnmanaged
```

### 最终代码变更范围

截至本轮验证，feature 分支主要改动：

| 文件 | 改动 |
| --- | --- |
| `go.mod` / `go.sum` | 升级 `sigs.k8s.io/agent-sandbox` 到 `v0.4.6`，Go 到 `1.26.2`，同步 K8s / controller-runtime 依赖 |
| `docker/Dockerfile*` | builder image 升级到 Go `1.26.2`，否则容器构建无法满足 `go.mod` |
| `pkg/workloadmanager/handlers.go` | SandboxClaim 路径等待 `claim.Status.SandboxStatus.Name` 指向的 adopted Sandbox；store 仍保存 claim 名 |
| `pkg/workloadmanager/k8s_client.go` | 新增 `getSandbox` / `getSandboxClaim` dynamic helper |
| `pkg/workloadmanager/sandbox_helper.go` | 处理 placeholder 时间字段，避免 pool Sandbox 创建时间污染 session TTL |
| `pkg/workloadmanager/codeinterpreter_controller.go` | CodeInterpreter 生成的 `SandboxTemplate` 显式设置 `networkPolicyManagement: Unmanaged` |
| `pkg/workloadmanager/*_test.go` | 覆盖 adopted Sandbox store 语义和 NetworkPolicyManagement 修复 |
| `test/e2e/e2e_test.go` | warm pool e2e helper 同时兼容旧 direct Pod ownership 和新版 `SandboxWarmPool -> Sandbox -> Pod` 结构 |

当前 diff 统计：

```text
13 files changed, 555 insertions(+), 236 deletions(-)
```

### Go / Docker / Helm 验证结果

已通过：

```bash
/tmp/go-toolchain/go/bin/gofmt -w ...
git diff --check
/tmp/go-toolchain/go/bin/go test ./pkg/workloadmanager -count=1
/tmp/go-toolchain/go/bin/go test -race ./pkg/workloadmanager -count=1
/tmp/go-toolchain/go/bin/go list ./... | rg -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs /tmp/go-toolchain/go/bin/go test
PATH=/tmp/go-toolchain/go/bin:$PATH make build-all
make helm-template
make helm-lint
```

Docker build 卡点与修复：

- 初始 Dockerfile 使用旧 Go builder，无法构建升级后的 `go.mod`。
- 改成 `golang:1.26.2-alpine` / `golang:1.26.2` 后通过。

已通过：

```bash
make docker-build WORKLOAD_MANAGER_IMAGE=workloadmanager:day16-v046
make docker-build-router ROUTER_IMAGE=agentcube-router:day16-v046
make docker-build-picod PICOD_IMAGE=picod:day16-v046
```

本地镜像导入 k3s：

```bash
docker save workloadmanager:day16-v046 | k3s ctr images import -
docker save agentcube-router:day16-v046 | k3s ctr images import -
docker save picod:day16-v046 | k3s ctr images import -
docker tag picod:day16-v046 picod:latest
docker save picod:latest | k3s ctr images import -
```

### Go e2e 结果

直接 CodeInterpreter：

```bash
TOKEN=$(kubectl create token e2e-test -n agentcube --duration=24h)
PATH=/tmp/go-toolchain/go/bin:$PATH \
KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
MTLS_ENABLED=false \
API_TOKEN="$TOKEN" \
WORKLOAD_NAMESPACE=agentcube-day16 \
/tmp/go-toolchain/go/bin/go test -v ./test/e2e \
  -run 'TestCodeInterpreter(BasicInvocation|FileOperations)$' -count=1
```

结果：

```text
PASS
ok  	github.com/volcano-sh/agentcube/test/e2e	3.729s
```

warm pool 单次路径：

```bash
PATH=/tmp/go-toolchain/go/bin:$PATH \
KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
MTLS_ENABLED=false \
API_TOKEN="$TOKEN" \
WORKLOAD_NAMESPACE=agentcube-day16 \
/tmp/go-toolchain/go/bin/go test -v ./test/e2e \
  -run 'TestCodeInterpreterWarmPool$' -count=1
```

结果：

```text
--- PASS: TestCodeInterpreterWarmPool (7.10s)
PASS
ok  	github.com/volcano-sh/agentcube/test/e2e	7.115s
```

warm pool load：

```bash
PATH=/tmp/go-toolchain/go/bin:$PATH \
KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
MTLS_ENABLED=false \
API_TOKEN="$TOKEN" \
WORKLOAD_NAMESPACE=agentcube-day16 \
/tmp/go-toolchain/go/bin/go test -v ./test/e2e \
  -run 'TestCodeInterpreterWarmPoolLoad$' -count=1
```

结果：

```text
Total requests: 100
Successful: 100
Failed: 0
Success rate: 100.00%
Total elapsed time: 1m46.450837305s
Average response time: 45.605159181s
Min response time: 1.10546509s
Max response time: 1m37.650579234s
Actual rate: 0.94 req/sec
--- PASS: TestCodeInterpreterWarmPoolLoad (112.55s)
```

解释：

- 功能成功率是 100%。
- 但单节点 k3s 下 10 QPS / 100 session 会触发大量 `SandboxClaim -> Sandbox -> Pod` churn，实际吞吐只有 0.94 req/s，平均耗时 45.6s。
- 这说明本 PR 可以声明兼容性通过，但不能声称 `v0.4.6` warm pool 高并发性能已经优化。

### Python SDK / LangChain / MCP 验证结果

Python 环境：

```bash
/root/.local/bin/python3.11 -m venv /tmp/agentcube-day16-venv
/tmp/agentcube-day16-venv/bin/python -m pip install --upgrade pip setuptools wheel
/tmp/agentcube-day16-venv/bin/python -m pip install \
  -e ./sdk-python \
  -e ./integrations/code-interpreter-mcp \
  -e ./integrations/langchain-agentcube
/tmp/agentcube-day16-venv/bin/python -m pip install \
  -r cmd/cli/examples/math-agent/requirements.txt
```

系统默认 `python3` 是 `3.6.8`，不满足 SDK / MCP / LangChain integration 要求；实际使用 `/root/.local/bin/python3.11` 创建 venv。

Python SDK：

```bash
cd test/e2e
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
MTLS_ENABLED=false \
API_TOKEN="$TOKEN" \
AGENTCUBE_NAMESPACE=agentcube-day16 \
/tmp/agentcube-day16-venv/bin/python test_codeinterpreter.py
```

结果：

```text
Ran 3 tests in 3.208s
OK
```

LangChain AgentCube sandbox：

```bash
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
MTLS_ENABLED=false \
API_TOKEN="$TOKEN" \
AGENTCUBE_NAMESPACE=agentcube-day16 \
/tmp/agentcube-day16-venv/bin/python test_langchain_agentcube_sandbox.py
```

结果：

```text
Ran 4 tests in 3.976s
OK
```

MCP streamable HTTP：

```bash
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
MTLS_ENABLED=false \
API_TOKEN="$TOKEN" \
AGENTCUBE_NAMESPACE=agentcube-day16 \
MCP_E2E_PORT=19245 \
/tmp/agentcube-day16-venv/bin/python test_mcp_code_interpreter.py
```

结果：

```text
Ran 5 tests in 5.741s
OK
```

MCP stdio：

```bash
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
MTLS_ENABLED=false \
API_TOKEN="$TOKEN" \
AGENTCUBE_NAMESPACE=agentcube-day16 \
/tmp/agentcube-day16-venv/bin/python test_mcp_code_interpreter_stdio.py
```

结果：

```text
Ran 1 test in 2.331s
OK
```

### math-agent LLM e2e

目标：验证不只是 CodeInterpreter 能执行 Python，而是完整链路：

```text
LLM agent -> run_python_code tool -> AgentCube CodeInterpreter -> sandbox execution -> final answer
```

安全处理：

- API key 只通过环境变量传入。
- 不写入 `.env`、报告或 git。
- 日志展示前用 `sed -E 's/sk-[A-Za-z0-9_-]+/<redacted>/g'` 脱敏。

第一层：math-agent tool layer 直接调用：

```bash
cd cmd/cli/examples/math-agent
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
API_TOKEN="$TOKEN" \
/tmp/agentcube-day16-venv/bin/python - <<'PY'
from main import run_python_code
result = run_python_code.invoke({"code": "print(6*7)"})
print(result)
PY
```

结果：

```text
42
```

第二层：math-agent HTTP health：

```bash
PORT=18082 /tmp/agentcube-day16-venv/bin/python main.py
curl http://127.0.0.1:18082/health
```

结果：

```json
{
  "status": "healthy",
  "agent": "math-agent"
}
```

第三层：完整 LLM query。

先用用户提供的 OpenAI-compatible gateway 原始 base URL：

```text
OPENAI_API_BASE=https://api.ai.tosky.top
OPENAI_MODEL=gpt-5.5
```

结果失败：

```text
HTTP 500
Internal Processing Error: 'str' object has no attribute 'model_dump'
```

判断：这不是 AgentCube sandbox 失败。tool layer 已经能创建 session 并执行 `print(6*7)`；错误发生在 LangChain/OpenAI 客户端解析模型响应时。

随后改为 OpenAI SDK / LangChain chat-completions 预期的 API root：

```text
OPENAI_API_BASE=https://api.ai.tosky.top/v1
OPENAI_MODEL=gpt-5.5
```

命令：

```bash
OPENAI_API_KEY=<redacted> \
OPENAI_API_BASE=https://api.ai.tosky.top/v1 \
OPENAI_MODEL=gpt-5.5 \
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
API_TOKEN="$TOKEN" \
PORT=18082 \
/tmp/agentcube-day16-venv/bin/python main.py

curl --max-time 180 -sS -X POST http://127.0.0.1:18082/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"Use the run_python_code tool to calculate 6*7. Return only the final number.","thread_id":"day16-live-v1"}'
```

结果：

```json
{
  "response": "42",
  "thread_id": "day16-live-v1",
  "agent": "math-agent"
}
```

结论：

- math-agent 完整 LLM e2e 已跑通。
- 该 example 当前依赖 OpenAI-compatible gateway 的 `/v1` base URL。
- 如果用户只给 `https://api.ai.tosky.top`，会得到 LangChain/OpenAI 解析错误；后续文档或 example 可以提示 `OPENAI_API_BASE` 应包含 `/v1`。
- `run_python_code` 工具函数内部 `CodeInterpreterClient()` 使用默认 `default/my-interpreter`，不是 `agentcube-day16/e2e-code-interpreter`。本轮 default/my-interpreter 也已在 `v0.4.6` + `Unmanaged` 模板下成功执行，但未来如果要让 math-agent 更易测，建议支持 `CODE_INTERPRETER_NAME` / `AGENTCUBE_NAMESPACE` 环境变量。

### 新增复用 skill

根据本轮 LLM e2e 流程，新增本地 skill：

```text
/home/agentcube/.agents/skills/llm-e2e-test/SKILL.md
```

用途：

- 运行 AgentCube math-agent / OpenAI-compatible LLM 端到端测试。
- 三层区分：SDK/direct CodeInterpreter、math-agent tool layer、完整 HTTP LLM query。
- 固化密钥安全处理：不落盘、不入报告、不打印真实 key。
- 记录 provider base URL `/v1` 排错经验，避免下次把 LLM gateway 解析错误误判成 sandbox 失败。

验证：

```bash
python3 /root/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  /home/agentcube/.agents/skills/llm-e2e-test
```

结果：

```text
Skill is valid!
```

## 环境恢复记录

测试结束后已恢复 k3s 环境，避免影响后续实验。

执行动作：

```bash
# 停止 day16 port-forward 持续会话
helm rollback agentcube 2 -n agentcube --wait --timeout=10m
kubectl -n agent-sandbox-system delete deployment agent-sandbox-controller --ignore-not-found=true
kubectl -n agent-sandbox-system scale statefulset agent-sandbox-controller --replicas=1
kubectl -n agent-sandbox-system rollout status statefulset/agent-sandbox-controller --timeout=300s
kubectl delete ns agentcube-day16 --ignore-not-found=true --timeout=180s
kubectl delete clusterrolebinding e2e-test-day16-binding --ignore-not-found=true
kubectl -n default delete sandbox --all --ignore-not-found=true
kubectl apply --server-side --force-conflicts --validate=false -f /home/agentcube/manifests/charts/base/crds
rm -f /tmp/day16-* /tmp/agentcube-math-agent*
```

恢复后状态：

```text
AgentCube Helm revision: 4 (Rollback to 2)
workloadmanager image: ghcr.io/volcano-sh/workloadmanager:latest
agentcube-router image: ghcr.io/volcano-sh/agentcube-router:latest
agent-sandbox controller: StatefulSet, image registry.k8s.io/agent-sandbox/agent-sandbox-controller:v0.1.1
agentcube-day16 namespace: deleted
default/my-interpreter warm pool: READY 2, back to v0.1.1 bare Pod shape
active port-forward / math-agent processes: none
```

说明：

- Docker 本地镜像 `workloadmanager:day16-v046`、`agentcube-router:day16-v046`、`picod:day16-v046` 仍可能存在于本机 Docker / k3s image store，但不再被 running deployment 引用。
- default namespace 中 v0.4.6 测试产生的 `Sandbox` CR 已删除；保留原本存在的 `CodeInterpreter my-interpreter`、`SandboxWarmPool my-interpreter`、`SandboxTemplate my-interpreter` 和旧 warm pool Pods。
- CRDs 已用主工作区版本 server-side apply 回写。

## 下一步

1. 准备 PR 描述，明确：
   - target 是 `agent-sandbox v0.4.6`，不是 `v0.5.0rc1` pseudo-version；
   - 依赖升级会带来 Go `1.26.2` / K8s `0.35.4`；
   - 修复范围包含 adopted Sandbox 语义和 `SandboxTemplate` NetworkPolicyManagement；
   - 本地验证覆盖 unit、race、non-e2e Go、build、Docker、Helm、k3s Go e2e、Python SDK、LangChain、MCP、math-agent LLM e2e；
   - kind 环境仍受本机限制，性能测试结果只作为单节点 k3s 参考。
2. 决定 PR 是否包含文档更新：
   - e2e helper 已更新。
   - 可能还需要文档说明 `agent-sandbox v0.4.6` warm pool 是 `SandboxWarmPool -> Sandbox -> Pod`，不是旧 bare Pod 模型。
   - math-agent 可另起 follow-up：支持 `CODE_INTERPRETER_NAME` / `AGENTCUBE_NAMESPACE`，并提示 OpenAI-compatible `OPENAI_API_BASE` 通常需要 `/v1`。
3. 与维护者确认是否接受当前 PR 同时包含 Go/K8s dependency bump、Docker Go builder bump 和 NetworkPolicyManagement 兼容策略；如果希望缩小 PR，可拆成 compatibility audit comment + smaller code PR。

## PR 准备材料

### 当前 PR 状态

- 代码 worktree：`/home/agentcube-agent-sandbox-latest`
- 分支：`feat/agent-sandbox-latest`
- 基线：`upstream/main` commit `0fd9151`
- 当前状态：commit `5316358` 已创建并 push 到 `origin/feat/agent-sandbox-latest`；代码 worktree clean。
- Issue：#386 是 v0.2.0 umbrella issue，无 assignee、无 `/assign` 信号；本 PR 建议写 `Refs #386`，不要写 `Fixes #386`。
- 建议 PR title：`fix: adapt code interpreter warm pool to agent-sandbox v0.4.6`
- 建议 PR kind：`/kind bug`
- 已提交 commit：`5316358 fix: adapt code interpreter warm pool to agent-sandbox v0.4.6`，包含 DCO signoff。
- PR 创建状态：已创建 upstream PR #387。
- PR URL：`https://github.com/volcano-sh/agentcube/pull/387`
- PR compare URL：`https://github.com/volcano-sh/agentcube/compare/main...ranxi2001:agentcube:feat/agent-sandbox-latest?expand=1`
- 额外尝试：用户提供一次性 GitHub token 后用 API 创建 PR，返回 `401 Bad credentials`；未创建 PR。token 未写入文件，临时 PR body 文件已删除，workspace 文件中未发现 GitHub token pattern。
- 第二次使用新 token 通过 GitHub API 创建成功：PR #387。token 通过隐藏 stdin 注入，未写入文件或环境变量；创建后已删除临时 PR body 文件，并确认 workspace 文件中未发现 GitHub token pattern。应尽快在 GitHub 设置中 revoke / rotate 本轮明文暴露过的 token。
- PR 初始状态：open、非 draft、label `kind/bug` / `size/XL`，DCO success；Python lint、codespell、python-sdk-tests 等部分检查已成功，coverage / golangci-lint / build / e2e-test / codegen check 仍在跑；tide pending。`volcano-sh-bot` 提示当前未 approve，review 获得 `lgtm` 后再 assign `hzxuzhonghu` approval。

### 变更分组

| 范围 | 文件 | 说明 |
| --- | --- | --- |
| dependency / toolchain | `go.mod`, `go.sum` | `sigs.k8s.io/agent-sandbox v0.1.1 -> v0.4.6`，Go 版本升到 `1.26.2`，同步升级 Kubernetes / controller-runtime 依赖。 |
| WorkloadManager runtime path | `pkg/workloadmanager/handlers.go`, `k8s_client.go`, `sandbox_helper.go` | 适配新版 `SandboxClaim -> adopted Sandbox -> Pod` warm pool 语义；使用公开 `SandboxPodNameAnnotation`；store 仍保存 claim name 用于 delete / GC。 |
| CodeInterpreter controller | `pkg/workloadmanager/codeinterpreter_controller.go` | 创建和更新 `SandboxTemplate` 时显式设置 `networkPolicyManagement: Unmanaged`，避免 agent-sandbox v0.4.6 默认 NetworkPolicy 阻断 AgentCube Router / WorkloadManager。 |
| tests | `pkg/workloadmanager/*_test.go`, `test/e2e/e2e_test.go` | 新增 adopted Sandbox / claim store 语义测试、NetworkPolicyManagement 测试，并更新 warm pool e2e Pod discovery 兼容新旧所有权链。 |
| generated code / codegen | `client-go/...`, `manifests/charts/base/crds/runtime.agentcube.volcano.sh_agentruntimes.yaml`, `hack/update-codegen.sh` | 依赖升级后 controller-gen / Kubernetes code-generator 再生成差异；同时把 `hack/update-codegen.sh` 从 `code-generator v0.34.1` 对齐到 `v0.35.4`，并改用 `go mod download`，避免 `go get -d` 在生成过程中降级依赖。 |
| Docker | `docker/Dockerfile`, `docker/Dockerfile.router`, `docker/Dockerfile.picod` | builder 升级到 Go `1.26.2`；Picod 镜像安装 Python 时补 `--no-install-recommends`、清理 apt lists、补末尾换行。 |

### OWNER 影响

- root `OWNERS`：`go.mod`, `go.sum`
- root `OWNERS`：`client-go/...`, `hack/update-codegen.sh`
- `pkg/workloadmanager/OWNERS`：核心 WorkloadManager 逻辑和单测
- `manifests/OWNERS`：CRD manifest
- `docker/OWNERS`：三个 Dockerfile
- `test/OWNERS`：e2e helper

不需要在 PR body 中主动 tag 所有人，等 bot 根据 OWNERS 提示即可。

### 安全检查

- 本轮已用 `rg` 检查 PR diff 和 tracked files 中没有出现真实 API key 或 OpenAI-style key literal。
- PR body 和测试记录只写 `<redacted>` / OpenAI-compatible provider 行为，不写真实 token。

### 可复制 PR body

````md
**What type of PR is this?**

/kind bug

**What this PR does / why we need it**:

This PR adapts AgentCube's CodeInterpreter warm pool integration to `sigs.k8s.io/agent-sandbox v0.4.6`.

AgentCube currently depends on `agent-sandbox v0.1.1`. With newer agent-sandbox releases, a direct dependency bump no longer works:

- compilation fails because `SandboxPodNameAnnotation` moved out of the internal `controllers` package and is now exposed from the public sandbox API package;
- warm pool adoption changed from the old direct/bare Pod shape to `SandboxWarmPool -> Sandbox -> Pod`, and `SandboxClaim` reports the serving Sandbox through status;
- after the compile fix, runtime creation can still time out because AgentCube was waiting/probing by the claim/template Sandbox name instead of the adopted Sandbox name;
- `agent-sandbox v0.4.6` defaults `SandboxTemplate.networkPolicyManagement` to managed NetworkPolicy, which blocks AgentCube's current Router / WorkloadManager data path unless AgentCube opts out or provides matching allow rules.

This PR:

- bumps `sigs.k8s.io/agent-sandbox` to `v0.4.6` and updates the required Go / Kubernetes dependencies;
- uses the public `sandboxv1alpha1.SandboxPodNameAnnotation` constant instead of importing an internal agent-sandbox controller package;
- waits for `SandboxClaim.Status.SandboxStatus.Name`, fetches the adopted Sandbox, waits until it is Ready, and uses that Sandbox for Pod IP / entrypoint probing;
- keeps the `SandboxClaim` name in the AgentCube session store when the request kind is `SandboxClaim`, so delete / GC still operate on the claim resource;
- sets CodeInterpreter-created `SandboxTemplate` objects to `networkPolicyManagement: Unmanaged` to preserve the existing AgentCube Router / WorkloadManager traffic path;
- updates warm pool e2e discovery to support both the old direct Pod ownership shape and the newer `SandboxWarmPool -> Sandbox -> Pod` ownership shape;
- regenerates the CRD and client-go code with the matching Kubernetes `v0.35.4` generator stack;
- updates `hack/update-codegen.sh` so code generation uses `k8s.io/code-generator v0.35.4` without mutating project dependencies through `go get -d`;
- updates Docker builder images to Go `1.26.2`.

**Which issue(s) this PR fixes**:

Refs #386

**Special notes for your reviewer**:

- Target version: `agent-sandbox v0.4.6`, which is the current Go module `@latest`. I did not target `v0.5.0rc1` because Go resolves that tag to a pseudo-version rather than the stable latest release.
- Dependency impact: `agent-sandbox v0.4.6` requires Go `1.26.2` and pulls Kubernetes / controller-runtime forward. Please confirm this dependency bump is acceptable for the v0.2.0 compatibility work.
- NetworkPolicy compatibility: `networkPolicyManagement: Unmanaged` keeps the behavior AgentCube had with `agent-sandbox v0.1.1`. If reviewers prefer to keep agent-sandbox managed NetworkPolicies, the alternative is to add explicit allow rules for `agentcube-router` and `workloadmanager`.
- Generated code: CRD manifest and client-go changes are generated from the dependency / Kubernetes OpenAPI update; this PR does not intentionally change the AgentRuntime API surface. `hack/update-codegen.sh` was also aligned to the new Kubernetes minor version because the old `code-generator v0.34.1` path downgraded `agent-sandbox` during generation.
- Local kind validation is blocked on this host during cluster creation before AgentCube resources are installed. Runtime validation below used an existing k3s cluster.
- AI assistance: I used Codex to inspect the agent-sandbox API changes, implement focused tests, run local / k3s validation, and prepare this PR description. I reviewed and validated the changes.

Tests run:

- `git diff --check`
- `/tmp/go-toolchain/go/bin/go test ./pkg/workloadmanager -count=1`
- `/tmp/go-toolchain/go/bin/go test -race ./pkg/workloadmanager -count=1`
- `/tmp/go-toolchain/go/bin/go list ./... | rg -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs /tmp/go-toolchain/go/bin/go test`
- `PATH=/tmp/go-toolchain/go/bin:$PATH make gen-all`
- `PATH=/tmp/go-toolchain/go/bin:$PATH make gen-check`
- `PATH=/tmp/go-toolchain/go/bin:$PATH make build-all`
- `PATH=/tmp/go-toolchain/go/bin:$PATH make helm-template`
- `PATH=/tmp/go-toolchain/go/bin:$PATH make helm-lint`
- `make docker-build WORKLOAD_MANAGER_IMAGE=workloadmanager:day16-v046`
- `make docker-build-router ROUTER_IMAGE=agentcube-router:day16-v046`
- `make docker-build-picod PICOD_IMAGE=picod:day16-v046`
- after commit `5316358`: `make docker-build WORKLOAD_MANAGER_IMAGE=workloadmanager:day16-v046-final`
- after commit `5316358`: `make docker-build-router ROUTER_IMAGE=agentcube-router:day16-v046-final`
- after commit `5316358`: `make docker-build-picod PICOD_IMAGE=picod:day16-v046-final`
- k3s: `go test ./test/e2e -run 'TestCodeInterpreter(BasicInvocation|FileOperations)$' -count=1` passed
- k3s: `go test ./test/e2e -run 'TestCodeInterpreterWarmPool$' -count=1` passed
- k3s: `go test ./test/e2e -run 'TestCodeInterpreterWarmPoolLoad$' -count=1` passed with 100 / 100 successful requests
- Python e2e with a Python 3.11 venv:
  - `test/e2e/test_codeinterpreter.py`: 3 tests OK
  - `test/e2e/test_langchain_agentcube_sandbox.py`: 4 tests OK
  - `test/e2e/test_mcp_code_interpreter.py`: 5 tests OK
  - `test/e2e/test_mcp_code_interpreter_stdio.py`: 1 test OK
- math-agent live LLM e2e with an OpenAI-compatible `/v1` endpoint returned the expected final answer `42`

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
````

### 提交前 checklist

在 `/home/agentcube-agent-sandbox-latest` 执行：

```bash
git status
git diff --stat
git diff --check
/tmp/go-toolchain/go/bin/go test ./pkg/workloadmanager -count=1
/tmp/go-toolchain/go/bin/go test -race ./pkg/workloadmanager -count=1
PATH=/tmp/go-toolchain/go/bin:$PATH make gen-all
PATH=/tmp/go-toolchain/go/bin:$PATH make gen-check
PATH=/tmp/go-toolchain/go/bin:$PATH make build-all
git commit -s -m "fix: adapt code interpreter warm pool to agent-sandbox v0.4.6"
git push origin feat/agent-sandbox-latest
```

说明：

- `make gen-check` 在 dirty worktree 中会因为最终执行全仓 `git diff --exit-code` 而失败；本轮先用 `make gen-all` 验证生成路径并检查 diff，commit 后在 clean tree 上已重跑 `make gen-check` 且通过。
- 如果提交前没有再改代码，可以不重复跑全量 k3s / Python / math-agent，只在 PR body 中保留本轮完整验证矩阵；如果 maintainer 对 dependency bump 或 NetworkPolicy 策略有疑问，再追加 focused follow-up commit。
