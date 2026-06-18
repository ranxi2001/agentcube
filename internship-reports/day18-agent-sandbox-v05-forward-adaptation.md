# Day 18 - agent-sandbox v0.5.x Forward Adaptation Test

日期：2026-06-18

## 任务定位

Day18 单独跟进 `sigs.k8s.io/agent-sandbox v0.5.x` / `v1beta1` 前沿适配测试，不再堆到 upstream PR #387 里。

当前边界：

- #387：只负责 current stable Go module `@latest`，也就是 `agent-sandbox v0.4.6` 的兼容适配。
- Day18：负责预研 `v0.5.0rc1` / 后续正式 `v0.5.0` 的 breaking changes、最小代码适配、运行验证和后续独立 PR 材料。
- upstream 行为：Day18 默认只做 local / fork-only validation。没有用户确认前，不开 upstream PR、不发 issue comment、不 mention maintainer。

## 已知事实

来自 Day17 的源码和 module 审计：

- `go list -m sigs.k8s.io/agent-sandbox@latest` 当前解析到 `v0.4.6`。
- `v0.5.0rc1` 是 Git tag / release candidate，但不是当前 Go module `@latest`；Go 会解析为 pseudo-version。
- `v0.5.0rc1` 已把 AgentCube 使用的 API 从 `v1alpha1` 迁到 `v1beta1`。
- 直接 `go get sigs.k8s.io/agent-sandbox@v0.5.0rc1 && go mod tidy` 会因为 current imports 缺失失败：

```text
sigs.k8s.io/agent-sandbox/api/v1alpha1
sigs.k8s.io/agent-sandbox/extensions/api/v1alpha1
```

- 机械改 import 到 `v1beta1` 后，`pkg/workloadmanager` 编译继续失败在结构字段变化：

```text
unknown field Replicas in .../api/v1beta1.SandboxSpec
unknown field TemplateRef in .../extensions/api/v1beta1.SandboxClaimSpec
```

## 为什么必须拆出 #387

`v0.5.x` 不是 #387 的小补丁，而是语义迁移：

- direct Sandbox 生命周期从 `replicas` 模型切换到 `operatingMode: Running/Suspended`。
- CodeInterpreter warm-pool claim 从 `TemplateRef` / optional warm pool 策略变成 required `WarmPoolRef`。
- claim controller 通过 `WarmPoolRef` 找 `SandboxWarmPool`，再从 warm pool 找 `SandboxTemplate`；不再是 #387 中“claim references template, optionally adopt from warm pool, otherwise cold create”的模型。
- `OperatingMode` 与 #386 中 Sleep/Resume 方向直接相关，但 AgentCube 自身的 session state machine 还没有设计和实现。

因此 Day18 的目标是先证明迁移路径，而不是修改 #387。

## 适配假设

第一版最小适配假设：

- `warmPoolSize == nil/0`：继续创建 direct `Sandbox`，不使用 `SandboxClaim`。
- direct `Sandbox`：用 `SandboxSpec.OperatingMode = Running` 替代 `Replicas = 1`。
- `warmPoolSize > 0`：继续由 AgentCube 创建 `SandboxTemplate` 和 `SandboxWarmPool`；创建 session 时用 `SandboxClaimSpec.WarmPoolRef.Name = codeInterpreter.Name`。
- claim 完成后仍通过 `claim.Status.SandboxStatus.Name` 定位实际 adopted Sandbox。
- `NetworkPolicyManagementUnmanaged` 继续保留，防止 agent-sandbox 默认 network policy 阻断 AgentCube Router / WorkloadManager。
- GC / delete 暂时维持当前 session store 设计，但必须验证 v1beta1 下删除 claim 是否仍能清理 underlying sandbox。

待验证风险：

- warm pool 为空时，v1beta1 claim 是否还能 cold create，还是只返回 dependency/candidate not found。
- claimed sandbox 被 delete / GC 后，claim owner reference、finalizer 和 underlying sandbox 是否与 v0.4.6 一致。
- `OperatingMode=Suspended` 会如何影响 Ready condition、pod annotation、entrypoint 和 router 连接。
- v0.5.x controller manifests / CRDs 是否和 Go module tag 完全一致。

## 执行计划

### Phase 1：版本和源码审计

- 用 `audit_go_module_version.py` 检查：
  - `sigs.k8s.io/agent-sandbox@latest`
  - `sigs.k8s.io/agent-sandbox@v0.5.0rc1`
  - 后续正式 `v0.5.0`
  - package presence：`api/v1alpha1`、`extensions/api/v1alpha1`、`api/v1beta1`、`extensions/api/v1beta1`
- 对比 `v0.4.6` 和 `v0.5.0rc1` 的：
  - `SandboxSpec`
  - `SandboxClaimSpec`
  - `SandboxWarmPoolSpec`
  - claim controller `getTemplate()` / adoption / cold-create path
  - annotations / labels / conditions
  - release manifests / CRD versions

### Phase 2：fork-only 编译适配分支

从最新 `upstream/main` 或 #387 合并后的 `main` 创建本地 / fork-only 分支：

```bash
git fetch upstream main
git switch -c test/agent-sandbox-v05-forward upstream/main
```

先做最小代码改动：

- `api/v1alpha1` imports -> `api/v1beta1`
- `extensions/api/v1alpha1` imports -> `extensions/api/v1beta1`
- dynamic GVR version -> `v1beta1`
- `SandboxSpec.Replicas` -> `SandboxSpec.OperatingMode`
- `SandboxClaimSpec.TemplateRef` -> `SandboxClaimSpec.WarmPoolRef`
- 更新 workload builder / controller tests 的断言。

### Phase 3：本地测试

最小验证：

```bash
go test ./pkg/workloadmanager -count=1
make lint
go test -race ./pkg/workloadmanager -count=1
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
make gen-check
make build-all
git diff --check
```

如果 codegen 或 CRD 版本变化触发生成差异，记录具体文件和原因，不把生成差异混成手工改动。

### Phase 4：真实 runtime 验证

只有编译通过不算完成。需要在安装 v0.5.x agent-sandbox CRDs/controller 后验证：

- direct CodeInterpreter e2e
- warm pool e2e
- warm pool load test
- session delete / GC resource cleanup
- Python SDK
- LangChain sandbox
- MCP HTTP / stdio
- math-agent LLM e2e

每次测试记录：

- agent-sandbox module version / manifest source
- AgentCube branch / commit
- cluster environment
- commands
- pass/fail
- root cause / workaround

## 和 Sleep/Resume 的关系

Day18 只把 `OperatingMode` 接入现有生命周期，不实现 AgentCube Sleep/Resume。

Sleep/Resume 后续应单独设计：

- store 增加 `Ready / Paused / Deleted` 和 `PausedAt`
- GC 从单一 delete 改成 `Ready -> Paused`、`Paused -> Deleted`
- WorkloadManager idle 后 patch Sandbox `OperatingMode=Suspended`
- Router 收到 session 请求时先 resume，再 proxy
- 新增 `pauseTimeout`，并明确与 `sessionTimeout` / `maxSessionDuration` 的关系

这个功能依赖 v0.5.x 的接口更自然，但不是兼容性适配 PR 的一部分。

## 当前产出目标

Day18 的阶段性产出不是 upstream PR，而是：

- 一份 v0.5.x 适配差异表。
- 一个已推送到 fork 的编译适配分支。
- 一组本地和 e2e 测试结果。
- 一个后续独立 upstream PR 的英文材料草稿。

停止条件：

- 如果 `v0.5.0` 尚未正式发布，且 rc1 行为仍可能变化，则不向 upstream 提交正式 PR。
- 如果 runtime 失败来自 release manifests / controller 与 Go module 不匹配，先记录并等待正式 release 或 maintainer 指示。
- 如果连续三次卡在同一个环境问题，例如 cluster / CRD 安装 / kind cgroup，则停止硬调，改为记录 BLOCKED 和所需环境。

## 编译测试驱动适配记录

本轮不再只做源码分析，而是在 `/home/agentcube-agent-sandbox-latest` 上创建 fork-only 实验分支做最小编译适配：

```bash
git switch -C test/agent-sandbox-v05-forward HEAD
```

基线：

- Branch：`test/agent-sandbox-v05-forward`
- Base：#387 当前验证 head `5867183`
- 实验 commit：`ee1aecf test: adapt agent-sandbox v05 rc api`
- 目标 dependency：`sigs.k8s.io/agent-sandbox v0.4.7-0.20260608211546-6af1bbd0cf64`，即 `v0.5.0rc1` 的 Go pseudo-version。
- 分支状态：已推送到 fork `origin/test/agent-sandbox-v05-forward`，未更新 #387，未创建 upstream PR。

### 实际遇到的问题

第一步直接升级：

```bash
go get sigs.k8s.io/agent-sandbox@v0.5.0rc1
go mod tidy
go test ./pkg/workloadmanager -count=1
```

失败点 1：`v1alpha1` 包已经不存在。

```text
package sigs.k8s.io/agent-sandbox/api/v1alpha1 provided by sigs.k8s.io/agent-sandbox at latest version v0.4.6 but not at required version v0.4.7-0.20260608211546-6af1bbd0cf64
package sigs.k8s.io/agent-sandbox/extensions/api/v1alpha1 provided by sigs.k8s.io/agent-sandbox at latest version v0.4.6 but not at required version v0.4.7-0.20260608211546-6af1bbd0cf64
```

处理：把 agent-sandbox imports 机械迁移到：

```text
sigs.k8s.io/agent-sandbox/api/v1beta1
sigs.k8s.io/agent-sandbox/extensions/api/v1beta1
```

失败点 2：机械 import 迁移后，`pkg/workloadmanager` 编译只剩 3 类真实 API 差异：

```text
unknown field Replicas in .../api/v1beta1.SandboxSpec
unknown field TemplateRef in .../extensions/api/v1beta1.SandboxClaimSpec
claim.Spec.TemplateRef undefined
```

处理：

- direct `Sandbox` path：`SandboxSpec.Replicas = ptr.To[int32](1)` 改为 `SandboxSpec.OperatingMode = SandboxOperatingModeRunning`。
- `SandboxClaim` path：`SandboxClaimSpec.TemplateRef{Name: ...}` 改为 `SandboxClaimSpec.WarmPoolRef{Name: ...}`。
- dynamic GVR：`SandboxGVR` / `SandboxClaimGVR` 的 version 从 `v1alpha1` 改为 `v1beta1`。
- tests：`claim.Spec.TemplateRef.Name` 断言改为 `claim.Spec.WarmPoolRef.Name`。

一个重要发现：`SandboxWarmPoolSpec.Replicas` 和 `SandboxWarmPoolSpec.TemplateRef` 在 rc1 的 `extensions/api/v1beta1` 中仍然存在，所以 `CodeInterpreterReconciler.ensureSandboxWarmPool()` 不需要因为 rc1 做字段级改动。真正变化的是 `SandboxClaim` checkout 语义和 direct `Sandbox` lifecycle 字段。

### 当前通过的本地测试

本轮最小适配后，以下命令通过：

```bash
go test ./pkg/workloadmanager -count=1
go test ./cmd/workload-manager ./cmd/agentd ./pkg/agentd -count=1
go test ./test/e2e -run '^$' -count=1
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
make build-all
go test -race ./pkg/workloadmanager -count=1
make lint
make gen-check
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
git diff --check
```

结果：

- `pkg/workloadmanager`：通过。
- `cmd/workload-manager` / `cmd/agentd` / `pkg/agentd`：通过。
- `test/e2e` 空编译检查：通过。
- 非 e2e Go 全量测试：通过。
- `make build-all`：通过。
- `go test -race ./pkg/workloadmanager`：通过。
- `make lint`：通过。
- `make gen-check`：通过，没有 AgentCube 自身 generated code drift。
- race coverage 命令：通过，`pkg/workloadmanager` coverage `26.3%`。

一个命令错误也记录下来：第一次跑非 e2e 全量测试时用了：

```bash
PATH=/root/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.4.linux-amd64/bin:$PATH go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
```

失败：

```text
xargs: go: No such file or directory
```

原因是 `PATH=...` 只作用在管道左侧的 `go list`，没有传给 `xargs go test`。修正为：

```bash
export PATH=/root/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.4.linux-amd64/bin:$PATH
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
```

### 当前结论

从编译和本地单测角度看，`v0.5.0rc1` 的最小 API 迁移比最初担心的范围更窄：

- import / scheme / GVR 必须迁到 `v1beta1`。
- direct sandbox 必须切到 `OperatingMode=Running`。
- warm-pool claim 必须切到 `WarmPoolRef`。
- warm pool controller 的 `SandboxWarmPoolSpec.Replicas` / `TemplateRef` 暂时还能沿用。

但这还不能说明 runtime 完成。最大未验证点仍然是 controller 行为：

- `SandboxClaimSpec.WarmPoolRef` 现在要求引用一个具体 `SandboxWarmPool`，claim controller 会先取 warm pool，再从 warm pool 取 template。
- pool empty 时是否能 cold create、如何 cold create，需要真实 rc1 controller / CRD 验证。
- claim delete / GC 是否仍能按 AgentCube 当前“store 保存 claim name”模型清理 underlying sandbox，需要 e2e 验证。
- `OperatingMode=Running` 编译通过，但后续 Sleep/Resume 的 `Suspended` 语义、Ready condition、pod annotation 和 router 连通性还没有测。

### 下一步

下一步进入 runtime-driven validation：

1. 确认 `v0.5.0rc1` 是否有匹配的 release manifests / CRDs，不能只用 Go module。
2. 在 k3s 环境安装 rc1 agent-sandbox controller / CRDs。
3. 用实验分支镜像跑 direct CodeInterpreter e2e。
4. 跑 warm pool e2e，重点观察 `SandboxClaim.spec.warmPoolRef`、`status.sandbox.name`、assigned sandbox annotation、underlying sandbox ownership。
5. 验证 session delete / GC 是否清理 claim 和 adopted sandbox。
6. 再跑 SDK / MCP / math-agent LLM e2e。

## Runtime-driven validation 记录

本轮在编译适配通过后继续做真实 controller/runtime 验证。结论先写在前面：

- 在干净 `v1beta1` 集群上，`v0.5.0rc1` 最小适配可以运行。
- direct CodeInterpreter、warm-pool CodeInterpreter、session delete/cleanup、Python SDK、LangChain sandbox、MCP HTTP/stdio、math-agent LLM e2e 都通过。
- 现有已安装 `v1alpha1` agent-sandbox CRD 的集群不能直接 apply rc1 manifest；这是 CRD 存储版本升级路径问题，不是 AgentCube Go 代码编译问题。

### Release manifest 和现有集群预检

下载的 rc1 release manifest：

```text
/tmp/agent-sandbox-v050rc1/manifest.yaml
/tmp/agent-sandbox-v050rc1/extensions.yaml
```

manifest 里只包含 `v1beta1` CRD 版本，controller image 为：

```text
registry.k8s.io/agent-sandbox/agent-sandbox-controller:v0.5.0rc1
```

当前默认 k3s 集群的 agent-sandbox 仍是旧状态：

```text
sandboxes.agents.x-k8s.io                         v1alpha1:true:true  stored=["v1alpha1"]
sandboxclaims.extensions.agents.x-k8s.io          v1alpha1:true:true  stored=["v1alpha1"]
sandboxtemplates.extensions.agents.x-k8s.io       v1alpha1:true:true  stored=["v1alpha1"]
sandboxwarmpools.extensions.agents.x-k8s.io       v1alpha1:true:true  stored=["v1alpha1"]
agent-sandbox-controller image: registry.k8s.io/agent-sandbox/agent-sandbox-controller:v0.1.1
```

先备份了当前资源：

```text
/tmp/agent-sandbox-v050rc1/current-agentcube-agent-sandbox-backup.yaml
```

没有把备份内容写入 repo，因为里面包含运行时环境生成的身份材料。

server dry-run 失败：

```bash
kubectl apply --dry-run=server \
  -f /tmp/agent-sandbox-v050rc1/manifest.yaml \
  -f /tmp/agent-sandbox-v050rc1/extensions.yaml
```

关键错误：

```text
CustomResourceDefinition.apiextensions.k8s.io "sandboxtemplates.extensions.agents.x-k8s.io" is invalid:
status.storedVersions[0]: Invalid value: "v1alpha1": must appear in spec.versions

CustomResourceDefinition.apiextensions.k8s.io "sandboxwarmpools.extensions.agents.x-k8s.io" is invalid:
status.storedVersions[0]: Invalid value: "v1alpha1": must appear in spec.versions
```

client dry-run 可以通过，说明 YAML 本身可解析；server dry-run 失败说明阻塞点是 apiserver 对现有 CRD `status.storedVersions` 的校验。也就是说，当前集群不能把只声明 `v1beta1` 的 rc1 CRD 原地覆盖到仍记录 `v1alpha1` storedVersions 的 CRD 上。

这条证据很重要：后续如果要支持从 AgentCube 已有部署升级到 `agent-sandbox v0.5.x`，需要单独考虑 CRD migration / 清理重装 / conversion strategy，而不是只改 Go imports。

### 隔离集群方案

为了不破坏当前默认 k3s，先尝试 `kind create cluster --name agentcube-v05-rc1 --wait 120s`，但仍卡在本机 kubeadm / cgroup 环境，失败后自动删除节点，没有残留。

随后安装并使用 `k3d` 创建隔离 k3s 集群：

```bash
GOBIN=/root/go/bin go install github.com/k3d-io/k3d/v5@latest
/root/go/bin/k3d cluster create agentcube-v05-rc1 \
  --servers 1 \
  --agents 0 \
  --wait \
  --timeout 180s \
  --k3s-arg '--disable=traefik@server:0' \
  --kubeconfig-update-default=false \
  --kubeconfig-switch-context=false
/root/go/bin/k3d kubeconfig get agentcube-v05-rc1 > /tmp/agentcube-v05-rc1-kubeconfig.yaml
```

验证环境：

```text
Node: k3d-agentcube-v05-rc1-server-0
Kubernetes: v1.32.5+k3s1
Kernel: 4.18.0-348.7.1.el8_5.x86_64
Container runtime: containerd://2.0.5-k3s1.32
```

在隔离集群 apply rc1 manifest 成功：

```bash
KUBECONFIG=/tmp/agentcube-v05-rc1-kubeconfig.yaml kubectl apply \
  -f /tmp/agent-sandbox-v050rc1/manifest.yaml \
  -f /tmp/agent-sandbox-v050rc1/extensions.yaml
```

CRD 状态：

```text
sandboxes.agents.x-k8s.io                         v1beta1:true:true  stored=["v1beta1"]
sandboxclaims.extensions.agents.x-k8s.io          v1beta1:true:true  stored=["v1beta1"]
sandboxtemplates.extensions.agents.x-k8s.io       v1beta1:true:true  stored=["v1beta1"]
sandboxwarmpools.extensions.agents.x-k8s.io       v1beta1:true:true  stored=["v1beta1"]
```

### AgentCube 实验镜像和部署

实验分支：

```text
repo: /home/agentcube-agent-sandbox-latest
branch: test/agent-sandbox-v05-forward
commit: ee1aecf test: adapt agent-sandbox v05 rc api
remote: https://github.com/ranxi2001/agentcube/tree/test/agent-sandbox-v05-forward
```

Fork CI validation PR：

```text
PR: https://github.com/ranxi2001/agentcube/pull/5
base: release-agent-sandbox-v05-base -> 5867183
head: test/agent-sandbox-v05-forward -> c0122da
```

构建镜像：

```bash
make docker-build WORKLOAD_MANAGER_IMAGE=workloadmanager:v05-rc1
make docker-build-router ROUTER_IMAGE=agentcube-router:v05-rc1
make docker-build-picod PICOD_IMAGE=picod:v05-rc1
docker tag picod:v05-rc1 picod:latest
```

导入 k3d：

```bash
/root/go/bin/k3d image import \
  workloadmanager:v05-rc1 \
  agentcube-router:v05-rc1 \
  picod:v05-rc1 \
  picod:latest \
  -c agentcube-v05-rc1
```

部署方式：

- Helm 部署 AgentCube 到 `agentcube` namespace。
- `spire.enabled=false`，先验证非 mTLS 的 sandbox control/data path。
- Redis 使用 `redis:7-alpine`，由 k3d 集群直接拉取。
- WorkloadManager 和 Router 分别用本地实验镜像 `workloadmanager:v05-rc1`、`agentcube-router:v05-rc1`。

端口转发：

```bash
KUBECONFIG=/tmp/agentcube-v05-rc1-kubeconfig.yaml \
  kubectl port-forward svc/workloadmanager -n agentcube 18080:8080

KUBECONFIG=/tmp/agentcube-v05-rc1-kubeconfig.yaml \
  kubectl port-forward svc/agentcube-router -n agentcube 18081:8080
```

health check：

```text
http://127.0.0.1:18080/health       -> {"status":"healthy"}
http://127.0.0.1:18081/health/live  -> {"status":"alive"}
```

一个调试失误也记录下来：第一次 port-forward 用后台 `&` 放在一次性 shell 里，shell 退出后转发进程也没稳定保留，Go e2e 报 `connect: connection refused`。后续改成长期 exec session 保持 port-forward，问题消失。

### Go e2e 结果

direct CodeInterpreter：

```bash
KUBECONFIG=/tmp/agentcube-v05-rc1-kubeconfig.yaml \
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
MTLS_ENABLED=false \
API_TOKEN=<created serviceaccount token> \
AGENTCUBE_NAMESPACE=agentcube \
WORKLOAD_NAMESPACE=agentcube \
go test -v ./test/e2e/... -run '^TestCodeInterpreterBasicInvocation$' -count=1
```

结果：

```text
PASS
ok github.com/volcano-sh/agentcube/test/e2e 2.514s
```

warm-pool CodeInterpreter：

```bash
KUBECONFIG=/tmp/agentcube-v05-rc1-kubeconfig.yaml \
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
MTLS_ENABLED=false \
API_TOKEN=<created serviceaccount token> \
AGENTCUBE_NAMESPACE=agentcube \
WORKLOAD_NAMESPACE=agentcube \
go test -v ./test/e2e/... -run '^TestCodeInterpreterWarmPool$' -count=1
```

结果：

```text
PASS
ok github.com/volcano-sh/agentcube/test/e2e 7.115s
```

说明：

- 原始 warm-pool YAML 默认 namespace 是 `default`；Go e2e helper 会按 `WORKLOAD_NAMESPACE` 渲染 namespace。
- 手工 apply 原始 YAML 时曾落到 `default`，这不是测试失败，而是需要区分“e2e 渲染资源”和“手工验证资源”。

### 留存式字段检查

普通 e2e 会自动删除 session，所以测试结束后看不到 Sandbox。为了证明 v1beta1 字段真的生效，额外做了留存式手工 session 检查。

direct session 创建返回：

```text
kind=Sandbox
sessionId=a054e5b0-1a90-41dd-a3c5-0f27121629c6
sandboxName=e2e-code-interpreter-epwdb3ar
entryPoint=10.42.0.17:8080
```

对应 Sandbox：

```text
apiVersion=agents.x-k8s.io/v1beta1
name=e2e-code-interpreter-epwdb3ar
spec.operatingMode=Running
Ready=True, reason=DependenciesReady
metadata.annotations["agents.x-k8s.io/pod-name"]=e2e-code-interpreter-epwdb3ar
pod owner=Sandbox/e2e-code-interpreter-epwdb3ar
pod image=picod:v05-rc1
```

warm-pool session 创建返回：

```text
kind=SandboxClaim
sessionId=040b553e-d842-405f-99e3-0cba78bba224
sandboxName=e2e-code-interpreter-warmpool-ttim9uzq
entryPoint=10.42.0.15:8080
```

对应 SandboxClaim / Sandbox / Pod：

```text
SandboxClaim apiVersion=extensions.agents.x-k8s.io/v1beta1
SandboxClaim spec.warmPoolRef.name=e2e-code-interpreter-warmpool
SandboxClaim status.sandbox.name=e2e-code-interpreter-warmpool-fxzth
SandboxClaim owner=CodeInterpreter/e2e-code-interpreter-warmpool
SandboxClaim labels.runtime.agentcube.io/session-id=040b553e-d842-405f-99e3-0cba78bba224

Sandbox apiVersion=agents.x-k8s.io/v1beta1
Sandbox name=e2e-code-interpreter-warmpool-fxzth
Sandbox Ready=True, reason=DependenciesReady
Sandbox annotation agents.x-k8s.io/pod-name=e2e-code-interpreter-warmpool-fxzth
Sandbox owner=SandboxClaim/e2e-code-interpreter-warmpool-ttim9uzq

Pod name=e2e-code-interpreter-warmpool-fxzth
Pod ready=true
Pod owner=Sandbox/e2e-code-interpreter-warmpool-fxzth
```

delete/cleanup 验证：

```text
DELETE /v1/code-interpreter/sessions/a054e5b0-1a90-41dd-a3c5-0f27121629c6
-> {"message":"Sandbox deleted successfully"}

DELETE /v1/code-interpreter/sessions/040b553e-d842-405f-99e3-0cba78bba224
-> {"message":"Sandbox deleted successfully"}
```

后置检查：

```text
direct session leftovers: No resources found
warm-pool claim leftover: NotFound
warm-pool pool after delete: READY=2
```

这证明当前 store 仍保存 claim name 的 delete 模型在 rc1 下可以工作；delete claim 后，agent-sandbox 会释放 claimed sandbox，并由 warm pool controller refilling 到 2 个 warm sandbox。

### SDK / LangChain / MCP / math-agent

Python 环境：

```text
Python: /root/.local/bin/python3.11
Venv: /tmp/agentcube-v05-rc1-llm-e2e-venv
Installed: sdk-python, integrations/code-interpreter-mcp, integrations/langchain-agentcube, math-agent requirements
```

SDK direct：

```bash
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
API_TOKEN=<created serviceaccount token> \
/tmp/agentcube-v05-rc1-llm-e2e-venv/bin/python - <<'PY'
from agentcube import CodeInterpreterClient
import os
with CodeInterpreterClient(
    name="e2e-code-interpreter",
    namespace="agentcube",
    workload_manager_url=os.environ["WORKLOAD_MANAGER_URL"],
    router_url=os.environ["ROUTER_URL"],
    auth_token=os.environ.get("API_TOKEN"),
) as client:
    print(client.run_code("python", "print(6*7)").strip())
PY
```

结果：

```text
42
```

math-agent tool layer 初次失败：

```text
404 Client Error: Not Found for url: http://127.0.0.1:18080/v1/code-interpreter
Server response: {"message":"code interpreter not found"}
```

根因：`cmd/cli/examples/math-agent/main.py` 里的 `run_python_code()` 当前直接调用 `CodeInterpreterClient()`，SDK 默认目标是 `default/my-interpreter`。`CODE_INTERPRETER_NAME` / `CODE_INTERPRETER_NAMESPACE` 这类环境变量不会自动改变 SDK 默认值。

处理：在隔离集群创建 `default/my-interpreter` CodeInterpreter 后重跑 tool layer。

结果：

```text
42
```

完整 math-agent HTTP LLM e2e：

```text
Provider base URL: https://api.ai.tosky.top/v1
Model: gpt-5.5
Secret handling: OPENAI_API_KEY 只从进程环境读取，未写入 repo / 报告 / 日志
```

请求：

```bash
curl --max-time 240 -sS \
  -X POST http://127.0.0.1:18082/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"Use the run_python_code tool to calculate 6*7. Return only the final number.","thread_id":"v05-rc1-llm-e2e"}'
```

结果：

```json
{
  "response": "42",
  "thread_id": "v05-rc1-llm-e2e",
  "agent": "math-agent"
}
```

Python SDK e2e：

```bash
WORKLOAD_MANAGER_URL=http://127.0.0.1:18080 \
ROUTER_URL=http://127.0.0.1:18081 \
MTLS_ENABLED=false \
API_TOKEN=<created serviceaccount token> \
AGENTCUBE_NAMESPACE=agentcube \
/tmp/agentcube-v05-rc1-llm-e2e-venv/bin/python test/e2e/test_codeinterpreter.py
```

结果：

```text
Ran 3 tests in 3.339s
OK
```

LangChain sandbox e2e：

```text
Ran 4 tests in 3.744s
OK
```

MCP streamable HTTP e2e：

```text
Ran 5 tests in 5.919s
OK
```

MCP stdio e2e：

```text
Ran 1 test in 2.731s
OK
```

## Fork PR CI Validation

只 push `test/agent-sandbox-v05-forward` 分支不会触发仓库里按 `pull_request` 配置的完整 CI。为了让 fork 仓库跑完整 checks，本轮创建了 fork-only PR：

```text
PR: https://github.com/ranxi2001/agentcube/pull/5
base: release-agent-sandbox-v05-base -> 5867183
head: test/agent-sandbox-v05-forward -> c0122da
```

第一次 CI（head `ee1aecf`）结果：

- 通过：approve workflows、codespell、Codegen Check、Python Lint、两个 build、coverage、golangci-lint、python-sdk-tests。
- 失败：`Agentcube E2E Tests / e2e-test`。

失败根因不是 v1beta1 代码编译问题，而是 CI e2e setup 仍默认安装旧 agent-sandbox manifest。workloadmanager 日志显示：

```text
unable to retrieve the complete list of server APIs: agents.x-k8s.io/v1beta1: no matches for agents.x-k8s.io/v1beta1
failed to get SandboxWarmPool: no matches for kind "SandboxWarmPool" in version "extensions.agents.x-k8s.io/v1beta1"
```

Router 随后在 AgentRuntime invocation 中收到 workloadmanager 500：

```text
Failed to get or create sandbox info: Internal error occurred: workload manager returned status 500
```

修复：

```text
c0122da test: align e2e agent-sandbox version with v05
```

该 commit 将 `make e2e` / `test/e2e/run_e2e.sh` 默认安装的 agent-sandbox release manifest 对齐到 `v0.5.0rc1`，并更新 `test/e2e/README.md` 的环境变量说明。

第二次 CI（head `c0122da`）全绿：

```text
Approve workflows based on contributor status: success
Check for spelling errors: success
Codegen Check: success
Python Lint: success
build: success
build: success
coverage: success
e2e-test: success
golangci-lint: success
python-sdk-tests: success
```

### 清理

已执行：

```bash
kill <math-agent pid>
DELETE /v1/code-interpreter/sessions/<math-agent session>
Ctrl-C workloadmanager/router port-forward sessions
/root/go/bin/k3d cluster delete agentcube-v05-rc1
```

最终状态：

- k3d `agentcube-v05-rc1` 集群已删除。
- 当前默认 Kubernetes context 仍是 `default`。
- 当前默认 k3s 没有被清理、重装或升级 agent-sandbox CRD。
- 临时 kubeconfig、manifest、venv、日志仍在 `/tmp`，不写入 repo。

## Day18 当前结论

`v0.5.0rc1` 适配从代码和 runtime 看都比预期可控：

- 必要代码迁移集中在 API version、GVR、direct Sandbox `OperatingMode`、warm-pool claim `WarmPoolRef`。
- e2e/CI 安装的 agent-sandbox manifest 版本也必须随依赖升级同步，否则集群没有 v1beta1 CRD，会在 runtime 阶段返回 500。
- `SandboxWarmPoolSpec.Replicas` / `SandboxWarmPoolSpec.TemplateRef` 在 rc1 仍可沿用。
- 在干净 `v1beta1` agent-sandbox controller 上，direct / warm-pool / delete / SDK / MCP / math-agent 都跑通。

但还有两个不能忽视的 PR 边界：

- rc1 不是当前 `go list -m @latest`，正式 upstream PR 最好等 `v0.5.0` release 或 maintainer 明确要求 rc support。
- 现有 `v1alpha1` CRD 集群不能原地 apply v1beta1-only manifest，后续如果要宣称“升级兼容”，必须补 CRD migration / clean-install 说明；不能只说 AgentCube 代码已适配。

未覆盖范围：

- 没测 `OperatingMode=Suspended` / Sleep-Resume 语义。
- 没测从已有 `v1alpha1` CRD 和资源到 `v1beta1` 的正式迁移流程。
- 没测 rc1 warm pool 为空时 claim 是否 cold create；本轮验证的是 warm pool ready 后 checkout/refill。
- 没测 SPIRE/mTLS 模式；本轮为非 mTLS runtime 验证。
