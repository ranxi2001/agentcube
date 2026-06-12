# Day 5 实习报告：沙箱延迟测试与竞品分析

## 基本信息

- 实习项目：AgentCube
- 实习方向：华为公司开源小组 / AgentCube 开源项目研究
- 日期：Day 5
- 今日主题：从数学 benchmark 暴露的问题出发，分析 AgentCube 沙箱运行环境、启动延迟和竞品技术路线
- 相关文件：
  - `internship-reports/benchmarks/agentcube_sandbox_latency_benchmark.py`
  - `internship-reports/benchmarks/agentcube_latency_sequential_5_result.json`
  - `internship-reports/benchmarks/agentcube_latency_concurrent_10_result.json`
  - `internship-reports/day4-gaokao-math-benchmark-plan.md`

## 今天的问题

Day 4 用高考数学题测试 `math-agent` 时，第 14 题暴露出一个新的问题：复杂数学题容易诱导模型生成 `sympy` 代码，但当前 `picod` 默认镜像里只有 Python，没有 `sympy`、`numpy`、`scipy`、`pandas` 这类数学库。

这不是一个单纯的 prompt 问题。站在开源项目维护者角度看，它实际指向两个基础设施问题：

1. AgentCube 的沙箱运行环境是如何定义和管理的？
2. 当 agent 频繁创建隔离执行环境时，沙箱启动延迟和并发能力如何？

所以 Day 5 的重点不再是继续做数学题，而是把注意力放到 AgentCube 的基础设施本身：`CodeInterpreter` 的环境配置、warm pool 行为、启动延迟，以及与 forkd、CubeSandbox、cage-bro 这类竞品的技术路线差异。

## 当前 AgentCube 环境

当前本地集群里的 `CodeInterpreter` 是 `my-interpreter`：

```bash
kubectl get codeinterpreter my-interpreter -n default -o yaml
```

关键配置：

```yaml
spec:
  authMode: picod
  maxSessionDuration: 8h
  sessionTimeout: 15m
  template:
    image: ghcr.io/volcano-sh/picod:latest
    imagePullPolicy: IfNotPresent
    args:
      - --workspace=/root
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 500m
        memory: 512Mi
  warmPoolSize: 2
```

几点观察：

- 当前 `runtimeClassName` 没有配置，所以这轮测试测的是 AgentCube 控制面 + k3s Pod + warm pool 路径，不是某个特定 KVM / Kata / Firecracker runtime 的性能。
- `warmPoolSize: 2` 表示系统会维持 2 个预热沙箱。
- 默认镜像是 `ghcr.io/volcano-sh/picod:latest`，镜像里有 Python，但没有常用科学计算库。

验证默认 Python 包：

```bash
kubectl exec -n default my-interpreter-4gvd7 -- python3 -c \
  "import sys, importlib.util; print(sys.version); [print(pkg, bool(importlib.util.find_spec(pkg))) for pkg in ['sympy','numpy','scipy','pandas']]"
```

输出：

```text
3.12.3 ...
sympy False
numpy False
scipy False
pandas False
```

这个结果解释了 Day 4 中 `sympy` 报错的根因：不是 AgentCube SDK 的问题，而是 `CodeInterpreter` 模板镜像没有预装这些依赖。

## CodeInterpreter 与 warm pool 的实现理解

从源码看，`CodeInterpreter` 的运行环境由 CRD 模板和镜像决定，不是 SDK 在运行时动态安装依赖。

相关代码：

```text
pkg/apis/runtime/v1alpha1/codeinterpreter_types.go
pkg/workloadmanager/codeinterpreter_controller.go
pkg/workloadmanager/workload_builder.go
pkg/workloadmanager/handlers.go
```

`CodeInterpreter` 控制器会根据 `warmPoolSize` 管理 `SandboxTemplate` 和 `SandboxWarmPool`：

```text
CodeInterpreter
-> SandboxTemplate
-> SandboxWarmPool
-> 预热 Sandbox / Pod
```

当 `warmPoolSize > 0` 时，Workload Manager 创建新 session 时走的是 `SandboxClaim` 路径：

```text
SDK 创建 CodeInterpreterClient
-> Workload Manager /api/v1/codeinterpreter/session
-> buildSandboxByCodeInterpreter
-> 创建 SandboxClaim
-> 等待 Sandbox 进入 Running
-> Router 通过 session 路由到 picod
```

这说明 AgentCube 当前的核心优化方式是“池化预热”：提前准备一批可用沙箱，请求来时从池里 claim 一个。这个模型和 forkd 的“从一个预热父 VM fork 出大量子 VM”不是同一种原语。

## 延迟 benchmark 设计

为了避免 LLM API 时间干扰，我写了一个只测基础设施路径的脚本：

```text
internship-reports/benchmarks/agentcube_sandbox_latency_benchmark.py
```

测试内容：

```text
create session -> run tiny Python code -> delete session
```

执行的代码只有：

```python
print('ok')
```

这样可以把 benchmark 聚焦到三个阶段：

| 阶段 | 含义 |
| --- | --- |
| `create_session_ms` | SDK 请求 Workload Manager，创建 / claim sandbox，并等待可用 |
| `run_code_ms` | Router 到 picod，执行最小 Python 代码 |
| `delete_session_ms` | 删除 session 和对应 sandbox claim |

运行命令：

```bash
python3 -m py_compile internship-reports/benchmarks/agentcube_sandbox_latency_benchmark.py

cmd/cli/examples/math-agent/.venv/bin/python \
  internship-reports/benchmarks/agentcube_sandbox_latency_benchmark.py \
  --mode sequential \
  --count 5 \
  --output internship-reports/benchmarks/agentcube_latency_sequential_5_result.json

cmd/cli/examples/math-agent/.venv/bin/python \
  internship-reports/benchmarks/agentcube_sandbox_latency_benchmark.py \
  --mode concurrent \
  --count 10 \
  --concurrency 10 \
  --output internship-reports/benchmarks/agentcube_latency_concurrent_10_result.json
```

## 实测结果

### 顺序 5 次

结果文件：

```text
internship-reports/benchmarks/agentcube_latency_sequential_5_result.json
```

汇总：

| 指标 | create session | run code | delete session | total |
| --- | ---: | ---: | ---: | ---: |
| mean | 671.79 ms | 41.11 ms | 8.38 ms | 721.28 ms |
| p50 | 100.22 ms | 40.33 ms | 6.93 ms | 177.14 ms |
| p95 | 2617.17 ms | 66.85 ms | 11.32 ms | 2652.83 ms |
| min | 59.29 ms | 25.99 ms | 6.67 ms | 91.95 ms |
| max | 2617.17 ms | 66.85 ms | 11.32 ms | 2652.83 ms |

单次明细：

| index | create session | run code | delete session | total |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 66.04 ms | 43.62 ms | 6.93 ms | 116.58 ms |
| 1 | 100.22 ms | 66.85 ms | 10.08 ms | 177.14 ms |
| 2 | 516.23 ms | 40.33 ms | 11.32 ms | 567.88 ms |
| 3 | 2617.17 ms | 28.76 ms | 6.91 ms | 2652.83 ms |
| 4 | 59.29 ms | 25.99 ms | 6.67 ms | 91.95 ms |

观察：

- warm pool 命中时，总延迟可以到 100ms 级别。
- `run_code_ms` 很稳定，基本在 25-67ms。
- 波动主要来自 `create_session_ms`，说明瓶颈在创建 / claim / 等待 sandbox 可用，不在 Python 执行本身。

### 并发 10 次

结果文件：

```text
internship-reports/benchmarks/agentcube_latency_concurrent_10_result.json
```

汇总：

| 指标 | create session | run code | delete session | total |
| --- | ---: | ---: | ---: | ---: |
| mean | 6242.27 ms | 33.30 ms | 11.06 ms | 6286.63 ms |
| p50 | 7278.76 ms | 28.52 ms | 7.37 ms | 7315.21 ms |
| p95 | 9268.41 ms | 67.22 ms | 29.56 ms | 9299.62 ms |
| min | 91.64 ms | 24.71 ms | 6.24 ms | 188.42 ms |
| max | 9268.41 ms | 67.22 ms | 29.56 ms | 9299.62 ms |

单次明细：

| index | create session | run code | delete session | total |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 8079.99 ms | 25.72 ms | 11.17 ms | 8116.88 ms |
| 1 | 8479.23 ms | 24.71 ms | 6.66 ms | 8510.61 ms |
| 2 | 91.64 ms | 67.22 ms | 29.56 ms | 188.42 ms |
| 3 | 182.22 ms | 43.70 ms | 19.84 ms | 245.76 ms |
| 4 | 7278.76 ms | 29.90 ms | 6.54 ms | 7315.21 ms |
| 5 | 9268.41 ms | 24.97 ms | 6.24 ms | 9299.62 ms |
| 6 | 6068.59 ms | 28.52 ms | 8.29 ms | 6105.40 ms |
| 7 | 8853.41 ms | 25.42 ms | 7.37 ms | 8886.20 ms |
| 8 | 7657.73 ms | 32.58 ms | 8.52 ms | 7698.82 ms |
| 9 | 6462.72 ms | 30.28 ms | 6.43 ms | 6499.42 ms |

观察：

- `warmPoolSize` 是 2，并发 10 时前两个请求明显更快，分别约 188ms 和 246ms。
- 其余请求基本排队到 6-9 秒。
- `run_code_ms` 仍然很稳定，说明并发场景下主要问题仍然是 sandbox 分配 / 补池 / 等待可用。
- 这轮结果不能说明 AgentCube 本身只能做到 9 秒级并发，只能说明当前配置 `warmPoolSize=2` 不适合 10 并发突发。

## 结果解读

这轮 benchmark 给我的直接结论是：

> AgentCube 的单次热池命中路径已经能做到 100ms 级别，但当前配置下的并发突发能力强依赖 warm pool 容量。

拆开看：

| 现象 | 解释 |
| --- | --- |
| 单次最快 91.95ms | warm pool 命中时，SDK -> Workload Manager -> Router -> picod 的路径比较短 |
| `run_code_ms` 稳定在几十毫秒 | Python 最小代码执行和 HTTP 转发不是主要瓶颈 |
| 并发 10 的 p50 到 7.3s | warm pool 只有 2，剩余请求需要等待 sandbox 补位或调度 |
| p95 接近 9.3s | 当前配置没有为 10 并发预留足够隔离环境 |

所以不能只看“最快一次”。对真实 agent 系统来说，更重要的是：

- pool hit ratio。
- pool miss 后的补位时间。
- 高并发下的排队策略。
- 每个用户请求是否需要独占 sandbox。
- session 是否能复用，还是每次 tool call 都新建 sandbox。

## 与 Day 4 数学 agent 的关系

Day 4 的数学题评测里，真正耗时的大头通常是 LLM 推理，单次可能是几秒到十几秒。相比之下，AgentCube 热池命中时的 100-200ms 沙箱开销并不明显。

但在下面几类场景中，沙箱延迟会变成核心指标：

- 一个 agent 需要大量短代码执行。
- 评测系统要并发跑很多题。
- SWE-bench 或类似任务需要大量隔离环境。
- 多 agent 系统需要并行探索多个分支。
- 每次 tool call 都创建新 session，而不是复用 session。

这也是为什么 forkd 和 CubeSandbox 会把“100 个沙箱”“几十毫秒启动”“低内存开销”作为卖点：它们瞄准的不是单个用户慢慢调用工具，而是 agent fan-out 和高并发隔离执行。

## 竞品分析

下面的竞品信息来自 2026-06-12 对公开 GitHub 仓库和 README 的核验。由于没有在同一台机器上复现，竞品数字只作为上游公开指标，不和本地 AgentCube 数据做严格横向排名。

### forkd

仓库：

```text
https://github.com/deeplethe/forkd
```

forkd 的核心思路是把进程级 `fork()` 的 copy-on-write 思路迁移到 microVM 层：

```text
预热 parent VM
-> parent 里 import Python / numpy / torch 等依赖
-> 暂停并保存内存快照
-> child VM 通过 mmap + MAP_PRIVATE 共享 parent 内存
-> 写入时再触发 CoW
```

上游 README 给出的关键指标：

| 指标 | 上游公开数字 |
| --- | ---: |
| fork 100 个 microVM | 101 ms |
| 每个 child 增量内存 | 0.12 MiB |
| live BRANCH pause p50 | 56 ms |
| forkd 对 CubeSandbox 的 N=100 对比 | forkd 101 ms，CubeSandbox 1.06s |

forkd 的优势是非常适合 agent fan-out：

- 父 VM 已经加载好运行时和依赖。
- 子 VM 从内存快照 fork，避免重复冷启动。
- 每个 child 仍然是独立 Firecracker microVM，保留 KVM 隔离边界。
- 支持从运行中的 sandbox 做 BRANCH，适合多分支探索。

但它和 AgentCube 当前路径不是同层产品：

| 维度 | forkd | AgentCube 当前测试 |
| --- | --- | --- |
| 核心原语 | VM snapshot CoW fork | Kubernetes CRD + warm pool claim |
| 调度范围 | 单机 daemon 为主 | Kubernetes 控制面和多组件协作 |
| 优化目标 | 高频 fan-out、快速 fork | Agent runtime / tool sandbox 的 Kubernetes 化管理 |
| 本轮数字是否可直接比较 | 不可直接比较 | 本地 k3s + warmPoolSize=2 |

forkd 的存在说明：如果 AgentCube 未来要在“高频创建隔离环境”这个维度上竞争，需要考虑更底层的 snapshot / fork 能力，单纯依赖固定 warm pool 可能不够。

### CubeSandbox

仓库：

```text
https://github.com/TencentCloud/CubeSandbox
```

CubeSandbox 是腾讯开源的 AI Agent 沙箱项目，README 中描述为基于 RustVMM 和 KVM 的高性能沙箱服务，支持 E2B SDK 兼容接口。

上游 README 给出的关键指标：

| 指标 | 上游公开数字 |
| --- | ---: |
| 单实例 fully serviceable sandbox | under 60ms |
| 内存开销 | less than 5MB |
| 50 并发创建 avg | 67ms |
| 50 并发创建 P95 | 90ms |
| 50 并发创建 P99 | 137ms |

CubeSandbox 的技术路线更接近 AgentCube 可以参考的方向：

- 仍然强调硬件级隔离。
- 使用资源池预分配和 snapshot cloning 降低启动延迟。
- 暴露 E2B 兼容接口，降低迁移成本。
- 有网络隔离和 eBPF 相关组件。

和 AgentCube 对比时要注意：

- CubeSandbox 自身就是 sandbox runtime。
- AgentCube 是更上层的 agent runtime / router / workload manager 系统，可以挂不同 sandbox 后端或 runtime class。
- 本地 AgentCube 没有配置特定 `runtimeClassName`，所以不能把这轮本地数字当成 AgentCube 在 KVM microVM 模式下的最终能力。

对 AgentCube 的启发：

- warm pool 要有明确的容量规划和观测指标。
- 如果目标是高并发 code interpreter，需要把 pool hit / miss 作为一等指标。
- 如果未来接入 KVM / Kata / Kuasar / Firecracker 类 runtime，需要单独测 runtime 冷启动、模板恢复、网络准备和 AgentCube 控制面开销。

### cage-bro

仓库：

```text
https://github.com/aeroxy/cage-bro
```

cage-bro 的定位和前两个不同。它是一个单 Rust 二进制的 agent 执行环境，内置：

- browser。
- shell。
- code execution。
- file ops。
- MCP server。
- REST API。
- dashboard。

README 中给出的卖点包括：

| 指标 | 上游公开描述 |
| --- | --- |
| init time | about 1ms |
| memory | about 100MB per sandbox |
| density | 1c1g VM 上 20+ sandboxes |
| isolation | Linux Landlock + rlimit + timeout |

但它的隔离模型和 microVM 类产品不同。cage-bro README 明确说明它是 shared kernel 上的 process-level isolation，不是 microVM；对于真正 adversarial code，建议把 cage-bro 放在 VM 或 microVM 内运行。

因此，看到“1ms init”这类数字时，不能直接和 AgentCube / CubeSandbox / forkd 的 KVM 隔离路径比较。它牺牲的是一部分隔离强度，换来更轻量的本地工具运行环境和更高密度。

对 AgentCube 的启发是另一类：

- AgentCube 不一定只需要“隔离沙箱”能力，也需要好用的 agent tool runtime。
- 浏览器、文件、shell、Jupyter、MCP 这些能力如果能标准化，会比只提供 `run_code` 更接近真实 agent 需求。
- 运行环境能力要在文档里说清楚：哪些依赖默认有，哪些需要自定义镜像，哪些安全边界由 runtime 提供。

## 横向对比

| 项目 | 核心定位 | 隔离模型 | 启动优化方式 | 对 AgentCube 的启发 |
| --- | --- | --- | --- | --- |
| AgentCube 当前本地配置 | Kubernetes-native agent / tool sandbox 管理 | 当前未配置 runtimeClass，走 k3s Pod 路径 | `warmPoolSize` 预热池 | 需要明确 pool hit/miss 指标和调优方法 |
| forkd | AI agent microVM fan-out runtime | Firecracker + KVM | parent VM snapshot + CoW fork | 对高频 fan-out，snapshot fork 比固定 warm pool 更激进 |
| CubeSandbox | KVM sandbox service for AI agents | RustVMM + KVM + eBPF 网络隔离 | 资源池预分配 + snapshot cloning | 可作为 AgentCube 底层 sandbox runtime 的参考 |
| cage-bro | 单机 agent tool runtime | Landlock + rlimit，shared kernel | 单进程内快速创建 workspace / sandbox | 工具体验强，但安全边界不同，适合放进更强隔离层内 |

我的判断：

> AgentCube 不应该只追求“谁的启动数字最小”，而应该先明确自己的系统边界：它更像 Kubernetes-native agent runtime 编排层，而不是单机 sandbox runtime。真正需要优化的是 AgentCube 控制面开销、warm pool 命中率、runtime 后端可插拔能力和可观测性。

## 维护者视角的问题清单

### 1. 运行环境可配置性需要更清晰

Day 4 的 `sympy` 问题说明用户很容易以为 CodeInterpreter 是“完整 Python 科学计算环境”，但默认镜像实际上很轻。

建议：

- 文档中明确默认 `picod` 镜像包含哪些依赖。
- 提供 `python-basic`、`python-science`、`python-browser` 等示例镜像。
- 在 Helm values 或 CRD 示例中展示如何替换 image。
- 在 math-agent system prompt 里根据运行环境约束说明“只能使用标准库”或“可以使用 numpy/sympy”。

### 2. benchmark 需要拆阶段

现在只测总耗时还不够。应该拆成：

```text
client request time
Workload Manager build object time
K8s resource create time
SandboxWarmPool claim wait time
Pod / Sandbox ready wait time
Router route ready time
picod execution time
cleanup time
```

如果没有这些指标，我们只能看到 `create_session_ms` 很大，却不知道到底慢在 K8s API、warm pool、sandbox controller、镜像启动，还是 store / router 同步。

### 3. warm pool 需要可观测和可调优

本轮并发 10 的结果很直观：`warmPoolSize=2` 不适合 10 并发突发。

建议暴露：

- 当前 warm pool ready 数量。
- busy 数量。
- pending 数量。
- claim wait time。
- pool hit / miss count。
- pool refill time。
- 每个 CodeInterpreter 的并发请求数。

这样才能回答：

- 应该配多大的 `warmPoolSize`？
- 什么时候需要扩容？
- 为什么某个请求等了 9 秒？
- 是资源不够、镜像慢，还是 pool controller 慢？

### 4. AgentCube 与底层 sandbox runtime 的边界要讲清楚

竞品里有三种路线：

```text
process sandbox: cage-bro
microVM pool: CubeSandbox
microVM fork-from-warm: forkd
```

AgentCube 可以不和它们做同一层竞争，但需要说明自己负责哪一层：

```text
AgentCube: agent runtime / workload manager / router / session / Kubernetes integration
Sandbox runtime: Pod / Kata / Kuasar / Firecracker / CubeSandbox-like backend
Tool runtime: picod / browser MCP / shell / Jupyter / custom HTTP service
```

这能避免用户误解：AgentCube 的价值不是单个 sandbox runtime 的启动数字，而是把 agent 工具运行时放进 Kubernetes 工作负载模型里统一管理。

### 5. 高并发评测要和真实业务形态对齐

forkd 的 N=100 benchmark 很适合 fan-out 场景，但不是所有 AgentCube 使用场景都需要每次请求创建新 sandbox。

AgentCube 应该分别测试：

| 场景 | 应测指标 |
| --- | --- |
| 单用户长 session | session 复用、tool latency、状态保持 |
| 多用户短 session | pool hit ratio、session create p50/p95/p99 |
| 评测平台 fan-out | N 并发创建、吞吐、失败率、队列时间 |
| 自定义镜像 | 冷启动、镜像拉取、预热耗时 |
| 高安全 runtime | runtimeClass 下的创建延迟和隔离成本 |

## 调试记录

### 问题 1：benchmark JSON 字段名冲突

初版 `agentcube_sandbox_latency_benchmark.py` 的 summary 里同时用了两个 `total` 字段：

```python
{
    "total": len(results),
    ...
    "total": summarize([...]),
}
```

JSON 对象里后一个 `total` 会覆盖前一个，导致结果结构不清楚。

修复：

```text
total -> case_count
total -> total_latency
```

修复后重新跑了顺序 5 次和并发 10 次，覆盖结果文件。

### 问题 2：本地 port-forward 不存在时 AgentCube SDK 会连接失败

Day 4 跑 `llm_tool_agentcube` 时遇到：

```text
localhost:18080 connection refused
```

原因不是集群里的 `workloadmanager` 或 `agentcube-router` 挂了，而是本地没有启动端口转发。

修复命令：

```bash
kubectl -n agentcube port-forward svc/workloadmanager 18080:8080
kubectl -n agentcube port-forward svc/agentcube-router 18081:8080
```

这个问题也提醒我：benchmark 报告里必须写清楚 `WORKLOAD_MANAGER_URL` 和 `ROUTER_URL` 的来源，否则复现实验时很容易误判。

### 问题 3：外部资料不能只看二手文章

最开始讨论 forkd 时，输入材料来自一篇介绍文章。为了避免把二手表述直接写进报告，我重新核验了公开仓库：

```bash
curl -L https://raw.githubusercontent.com/deeplethe/forkd/main/README.md
curl -L https://raw.githubusercontent.com/aeroxy/cage-bro/main/README.md
curl -L https://raw.githubusercontent.com/TencentCloud/CubeSandbox/main/README.md
```

其中 CubeSandbox 第一次请求返回：

```text
404: Not Found
```

原因是 CubeSandbox 默认分支是 `master`，不是 `main`。

修正：

```bash
curl -L https://raw.githubusercontent.com/TencentCloud/CubeSandbox/master/README.md
```

最终报告中的竞品信息只采用能在公开仓库 README 或 GitHub metadata 中核验到的内容。

### 问题 4：`kubectl get sandbox,sandboxclaim,pod -A` 不能完整展示 warm pool 状态

第一次只看：

```bash
kubectl get sandbox,sandboxclaim,pod -A
```

输出主要显示 Pod，没有直观看到 warm pool 资源。后来用：

```bash
kubectl get sandboxwarmpool,sandboxtemplate,sandboxclaim,sandbox -A -o wide
```

确认当前存在：

```text
default sandboxwarmpool.extensions.agents.x-k8s.io/my-interpreter READY 2
default sandboxtemplate.extensions.agents.x-k8s.io/my-interpreter
```

这说明观察 warm pool 不能只看 Pod，要直接看 `SandboxWarmPool` 和 `SandboxTemplate`。

## 下一步计划

我认为后续可以分三条线推进。

### 1. 做 AgentCube warm pool 参数实验

固定同一个 benchmark，分别测试：

```text
warmPoolSize = 0
warmPoolSize = 1
warmPoolSize = 2
warmPoolSize = 5
warmPoolSize = 10
```

每组跑：

```text
sequential count=10
concurrent count=10 concurrency=10
concurrent count=20 concurrency=20
```

记录 p50 / p95 / p99 / failure rate，观察 warm pool 规模和并发延迟的关系。

### 2. 增加阶段级 instrumentation

当前 SDK 侧只能看到总的 `create_session_ms`。下一步应该在 Workload Manager 或 benchmark 中拿到更多阶段数据：

```text
request_received_at
k8s_resource_created_at
sandbox_claim_bound_at
sandbox_running_at
router_route_ready_at
response_returned_at
```

这样可以把 9 秒等待拆开，而不是只知道“创建 session 慢”。

### 3. 做自定义数学镜像

为 Day 4 的数学 benchmark 准备一个 `python-science` CodeInterpreter 镜像：

```text
python3
sympy
numpy
scipy
matplotlib optional
```

然后对比：

```text
默认 picod 镜像
python-science 镜像
system prompt 禁止第三方库
system prompt 允许 sympy
```

这样可以把“模型是否会调用工具”“工具是否可执行”“沙箱环境是否足够”三个问题拆开。

## 今天的结论

今天最大的收获是：AgentCube 的性能问题不能只看一个端到端数字，要先分清楚它在系统中的层次。

本地实测说明：

- AgentCube 在 warm pool 命中时，CodeInterpreter 最小调用可以达到 100ms 级别。
- 当前 `warmPoolSize=2` 下，并发 10 会出现明显排队，p50 到 7.3s，p95 到 9.3s。
- Python 执行本身不是瓶颈，瓶颈主要在 session 创建 / sandbox claim / warm pool 容量。
- 默认 `picod` 镜像没有科学计算库，数学 agent 需要自定义镜像或 prompt 约束。

竞品分析说明：

- forkd 代表 microVM fork-from-warm 路线，适合极端 fan-out。
- CubeSandbox 代表高性能 KVM sandbox runtime 路线，强调池化、snapshot 和 E2B 兼容。
- cage-bro 代表轻量 agent tool runtime 路线，工具体验强，但隔离边界不是 microVM。

对 AgentCube 来说，更合理的方向不是简单追逐某个竞品的启动数字，而是把自身定位讲清楚：作为 Kubernetes-native agent runtime 和 tool sandbox 编排层，应该提供清晰的运行环境管理、warm pool 调优、阶段级可观测性，以及接入不同底层 sandbox runtime 的能力。
