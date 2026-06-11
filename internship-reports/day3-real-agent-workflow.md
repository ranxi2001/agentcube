# Day 3 实习报告：从跑通架构到运行真实 Agent 工作流

## 基本信息

- 实习项目：AgentCube
- 实习方向：华为公司开源小组 / AgentCube 开源项目研究
- 日期：Day 3
- 今日主题：思考并设计如何运行一个真实的 AI Agent，而不是只跑通 Day 1 的基础架构
- 主要参考：`example/browser-agent/`、`example/pcap-analyzer/`、`cmd/cli/examples/math-agent/`、`sdk-python/examples/agent_runtime_usage.py`

## 今天的问题

Day 1 已经把 AgentCube 的最小链路跑起来了：Workload Manager、Router、Redis、agent-sandbox、CodeInterpreter 都能协同工作。Day 2 也从代码目录和技术栈上理解了 AgentCube 的核心组件。

但我今天意识到一个问题：Day 1 的 `CodeInterpreterClient.run_code("print(...)")` 更像 smoke test，只能证明 AgentCube 的基础设施链路可用，还不能证明我们真正运行了一个 AI Agent。

所以今天的核心问题是：

> 如何跑一个真实的 agent，而不是只跑通 Day 1 的架构？

## 我对“真实 Agent”的判断标准

我现在认为，一个更接近真实场景的 Agent 至少应该具备下面几个特征：

| 能力 | 说明 |
| --- | --- |
| LLM 推理 | Agent 能根据用户目标进行理解、规划或决策 |
| 工具调用 | Agent 能选择并调用工具，而不是只返回文本 |
| 沙箱执行 | 工具或代码执行发生在 AgentCube 管理的 sandbox 中 |
| 状态复用 | 多轮请求可以复用同一个 session，而不是每次都从零开始 |
| 结果闭环 | Agent 能读取工具结果，并把结果整理成最终回答 |

按这个标准，Day 1 的 CodeInterpreter 示例只覆盖了“沙箱执行”这一部分，还缺少 LLM 推理、工具选择和多轮闭环。

## 当前仓库里可选的三条路线

### 路线 1：`AgentRuntime` + 简单 HTTP Agent

相关文件：

```text
example/agent-runtime/agent-runtime.yaml
sdk-python/examples/agent_runtime_usage.py
```

这条路线可以验证 `AgentRuntime -> Router -> sandbox HTTP service` 的链路。它比 Day 1 更接近 AgentCube 的 agent runtime 模型，但示例里的 `busybox sleep` 或简单 HTTP server 本身没有智能能力。

我的判断：适合作为 AgentRuntime 的连通性测试，但还不能算真正的 AI Agent。

### 路线 2：`math-agent`：LLM + CodeInterpreter 工具

相关文件：

```text
cmd/cli/examples/math-agent/main.py
cmd/cli/examples/math-agent/requirements.txt
```

`math-agent` 已经有了比较完整的 agent 结构：

```text
用户问题
-> LangChain / LangGraph Agent
-> LLM 判断是否需要工具
-> run_python_code tool
-> CodeInterpreterClient
-> AgentCube Router
-> PicoD sandbox 执行 Python
-> LLM 整理结果
```

这条路线的优点是成本低，最适合作为第一个真实 agent demo。它能展示：LLM 不是直接回答，而是会在需要计算时调用 AgentCube 提供的沙箱执行能力。

我的判断：这是 Day 3 最小可行目标。

### 路线 3：`browser-agent`：LLM 编排器 + Playwright MCP 工具 sandbox

相关文件：

```text
example/browser-agent/README.md
example/browser-agent/browser_agent.py
example/browser-agent/browser-use-tool.yaml
example/browser-agent/deployment.yaml
```

这条路线最能体现 AgentCube 的价值。它不是把整个 Agent 都塞进 CodeInterpreter，而是把 Agent 拆成两层：

```text
Browser Agent Deployment
-> LLM 负责规划和总结
-> AgentCube Router
-> AgentRuntime sandbox
-> Playwright MCP Tool
-> 浏览器自动化工具调用
```

这个例子里，AgentCube 管理的是“工具运行时”，而不是普通的一次性代码执行。Router 负责根据 session 创建或复用 Playwright MCP sandbox，Agent 通过 MCP 协议调用浏览器工具。

我的判断：这是最值得最终展示的真实 AgentCube demo。

## 推荐执行顺序

我认为应该按下面顺序推进，不要一开始就上最复杂的 browser-agent：

```text
Step 1: 确认 Day 1 基础组件仍然可用
Step 2: 跑 math-agent，证明 LLM 能通过 AgentCube 调用 CodeInterpreter 工具
Step 3: 跑 AgentRuntime 简单 HTTP demo，证明 AgentRuntime 转发链路可用
Step 4: 跑 browser-agent，展示 LLM 编排器 + AgentCube 工具 sandbox
Step 5: 如果时间允许，再跑 pcap-analyzer 这种领域型多 agent workflow
```

这样做的好处是每一步都只增加一个变量。如果直接跑 browser-agent，一旦失败，可能同时涉及 LLM API、镜像构建、AgentRuntime、Router、MCP 协议、Playwright 镜像拉取等多个问题，排查成本会比较高。

## 当前环境预检

今天先检查了 Day 1 部署出来的 AgentCube 组件是否还在运行：

```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods,svc -n agentcube
```

观察结果：

```text
pod/redis-8456b6957d-ppt9f              1/1 Running
pod/agentcube-router-69db9687b9-vtflm   1/1 Running
pod/workloadmanager-697f9fc656-kgbjl    1/1 Running

service/redis              ClusterIP   6379/TCP
service/workloadmanager    ClusterIP   8080/TCP
service/agentcube-router   ClusterIP   8080/TCP
```

这说明 Day 1 的基础控制面和数据面还可用。

然后检查当前已有的 AgentCube CR：

```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get agentruntime,codeinterpreter -A
```

观察结果：

```text
NAMESPACE   NAME                                                          AGE
default     codeinterpreter.runtime.agentcube.volcano.sh/my-interpreter   4h17m
```

这说明当前只有 `CodeInterpreter`，还没有真正创建 `AgentRuntime`。

## 卡点和调试记录

### 卡点 1：当前机器没有 Docker

检查命令：

```bash
command -v docker
command -v ctr
command -v kubectl
command -v helm
```

观察结果是机器上没有 `docker`，但有：

```text
/usr/local/bin/ctr
/usr/local/bin/kubectl
/usr/local/bin/helm
```

原因分析：

- Day 1 使用的是 k3s，底层有 containerd。
- 但本机没有 Docker CLI 和 Docker daemon。
- `browser-agent` 和 `pcap-analyzer` 的 README 默认使用 `docker build`，这一步在当前机器上不能直接执行。

处理思路：

- 短期可以先跑不需要自定义镜像构建的 `math-agent`。
- 如果必须跑 `browser-agent`，需要选择一种镜像构建方式：
  - 安装 Docker。
  - 使用 nerdctl/buildkit 构建并导入 k3s containerd。
  - 在外部机器构建镜像并推到 registry。
  - 改用 k3s/containerd 可直接拉取的远端镜像。

### 卡点 2：真实 Agent 需要 LLM API key

`math-agent`、`browser-agent` 和 `pcap-analyzer` 都依赖 OpenAI-compatible API：

```text
OPENAI_API_KEY
OPENAI_API_BASE
OPENAI_MODEL
```

如果没有配置 API key，Agent 服务即使启动，也只能在调用时返回配置错误。

处理方式：

- 本地测试 `math-agent` 时通过环境变量配置。
- Kubernetes 内运行 `browser-agent` 时通过 Secret 注入，例如：

```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl create secret generic browser-agent-secrets \
  --from-literal=openai-api-key='<YOUR_API_KEY>'
```

### 卡点 3：示例里的 Router Service 名称需要核对

Day 1 当前环境里的 Router Service 名称是：

```text
agentcube-router.agentcube.svc.cluster.local
```

但 `example/pcap-analyzer/deployment.yaml` 里写的是：

```text
http://router.agentcube.svc.cluster.local:8080
```

这在当前环境里可能会导致 Agent 服务启动后无法访问 Router。

处理方式：

- 运行前先执行：

```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get svc -n agentcube
```

- 以真实 Service 名称为准，把环境变量统一成：

```text
ROUTER_URL=http://agentcube-router.agentcube.svc.cluster.local:8080
WORKLOAD_MANAGER_URL=http://workloadmanager.agentcube.svc.cluster.local:8080
```

## Day 3 最小实验：跑通 `math-agent`

我先用 `math-agent` 做第一个真实 agent 实验，因为它最小，但已经具备 LLM + 工具调用 + sandbox 执行闭环。

### 1. 准备端口转发

为了避免和本地已有进程冲突，我没有继续使用 `8080/8081`，而是把 Workload Manager 和 Router 分别转发到本地 `18080/18081`：

```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl port-forward -n agentcube svc/workloadmanager 18080:8080
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl port-forward -n agentcube svc/agentcube-router 18081:8080
```

### 2. 设置环境变量

为了不把 LLM API key 写进命令历史或报告正文，我在 `cmd/cli/examples/math-agent/.env` 里保存配置。该文件权限设置为 `600`，并且根目录 `.gitignore` 已经忽略 `.env`。

```bash
cd /home/agentcube/cmd/cli/examples/math-agent

cat > .env <<'EOF'
OPENAI_API_KEY=<YOUR_API_KEY>
OPENAI_API_BASE=<YOUR_OPENAI_COMPATIBLE_BASE_URL>
OPENAI_MODEL=<YOUR_MODEL>
WORKLOAD_MANAGER_URL=http://localhost:18080
ROUTER_URL=http://localhost:18081
PORT=18082
EOF

chmod 600 .env
```

### 3. 启动 `math-agent`

当前机器系统默认 `python3` 是 3.6，不满足 SDK 要求，所以实际使用已有的 `python3.11` 和 `uv` 创建虚拟环境：

```bash
cd /home/agentcube/cmd/cli/examples/math-agent
uv venv --python /root/.local/bin/python3.11 .venv
uv pip install -r requirements.txt -e /home/agentcube/sdk-python

set -a
. .env
set +a
.venv/bin/python main.py
```

健康检查：

```bash
curl -s http://localhost:18082/health
```

返回：

```json
{
  "status": "healthy",
  "agent": "math-agent"
}
```

### 4. 先做不消耗 LLM 的 SDK smoke test

在真正调用 LLM 之前，我先直接用 `CodeInterpreterClient` 跑一个最小 Python 代码，确认 AgentCube 的 sandbox 执行链路是通的。这个步骤不消耗 LLM API 额度。

```bash
set -a
. .env
set +a

.venv/bin/python - <<'PY'
from agentcube import CodeInterpreterClient

with CodeInterpreterClient(verbose=False, ttl=600) as client:
    print("session", client.session_id[:8])
    print(client.run_code("python", "print(2+2)", timeout=10).strip())
PY
```

观察结果：

```text
Session created: 156db1fb-1e2c-49a1-96cc-960b03b984a8
session 156db1fb
4
Deleting session 156db1fb-1e2c-49a1-96cc-960b03b984a8...
```

这个结果说明：即使不通过本机 Python 直接算题，也可以通过 AgentCube 创建远端 CodeInterpreter sandbox，并在 sandbox 里执行 Python 代码。

### 5. 第一次真实 agent 调用：最小加法验证

为了控制 LLM API 额度，我只发了一次很小的请求，要求 Agent 使用 Python tool 计算 `2+3`：

```bash
curl -s http://localhost:18082/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"Use the Python tool once to compute 2+3. Reply with only the number.","thread_id":"quota_safe_test"}'
```

返回：

```json
{
  "response": "5",
  "thread_id": "quota_safe_test",
  "agent": "math-agent"
}
```

`math-agent` 日志里能看到它确实创建了 CodeInterpreter session：

```text
Received query: Use the Python tool once to compute 2+3. Reply with only the number. (thread_id: quota_safe_test)
Creating new session...
Session created: b7ffbae7-54a7-4f24-a194-f9d22cda86c8
Agent response: 5
```

这一步证明：LLM Agent 可以通过工具调用触发 AgentCube sandbox，而不是只能由人手动调用 SDK。

### 6. 第二次真实 agent 调用：10 节点最短路径

为了验证它不是只能完成简单加法，我又给了一个 10 个节点的带权无向图，让 Agent 用 Python tool 求从 `A` 到 `J` 的最短路径：

```bash
curl -s http://localhost:18082/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"Use the Python tool once to solve this shortest path problem. Graph has 10 nodes A,B,C,D,E,F,G,H,I,J and undirected weighted edges: A-B 4, A-C 2, B-C 1, B-D 5, C-D 8, C-E 10, D-E 2, D-F 6, E-F 2, E-G 3, F-H 1, G-H 4, G-I 6, H-I 2, I-J 3, F-J 9, B-G 12. Find the shortest path from A to J. Reply concisely with path and total weight.","thread_id":"shortest_path_10_nodes"}'
```

返回：

```json
{
  "response": "Shortest path: `A -> C -> B -> D -> E -> F -> H -> I -> J`\n\nTotal weight: `18`",
  "thread_id": "shortest_path_10_nodes",
  "agent": "math-agent"
}
```

`math-agent` 日志：

```text
Received query: Use the Python tool once to solve this shortest path problem...
Creating new session...
Session created: e824d469-8122-410e-9823-b609f25110bf
Agent response: Shortest path: `A -> C -> B -> D -> E -> F -> H -> I -> J`

Total weight: `18`
```

这个结果说明：我们已经成功跑通了“Agent 不借助本机 Python，而是调用 AgentCube 管理的 sandbox Python 来解决复杂计算题”的最小闭环。

实际调用链路是：

```text
用户自然语言题目
-> math-agent HTTP API
-> LangChain / LangGraph Agent
-> LLM 判断需要调用 run_python_code
-> CodeInterpreterClient 创建 session
-> Workload Manager 创建/分配 CodeInterpreter sandbox
-> Router 转发代码执行请求
-> PicoD 在 sandbox 内运行 Python
-> Python 返回最短路径结果
-> LLM 整理成最终回答
```

### 7. 清理临时 session 和本地进程

由于 `math-agent` 示例里的 `run_python_code()` 每次会创建一个新的 `CodeInterpreterClient()`，但没有显式调用 `stop()`，所以工具调用完成后会留下短暂的 sandbox session。为了不浪费集群资源，我手动通过 Workload Manager 删除了 session：

```bash
curl -sS -X DELETE \
  http://localhost:18080/v1/code-interpreter/sessions/e824d469-8122-410e-9823-b609f25110bf
```

返回：

```json
{"message":"Sandbox deleted successfully"}
```

最后停止了：

- `math-agent` 本地进程。
- `kubectl port-forward` 到 Workload Manager 的进程。
- `kubectl port-forward` 到 Router 的进程。

再次检查本地端口：

```bash
ss -ltn sport = :18080
ss -ltn sport = :18081
ss -ltn sport = :18082
```

没有监听结果，说明本地临时进程已经停止。

## 这次实验观察到的问题

### 问题 1：`math-agent` 工具函数没有自动清理 session

`cmd/cli/examples/math-agent/main.py` 里的 `run_python_code()` 当前写法是：

```python
ci_client = CodeInterpreterClient()
return ci_client.run_code("python", code)
```

这样每次 tool call 都会创建一个 session，但函数结束时不会自动删除。短期实验可以手动删除 session；长期运行应该改成 context manager：

```python
with CodeInterpreterClient() as ci_client:
    return ci_client.run_code("python", code)
```

这样 tool call 结束后会自动调用 `stop()`，避免留下临时 sandbox。

### 问题 2：本机和 sandbox 的 Python 要区分清楚

这次本机 Python 只承担两个角色：

- 启动 `math-agent` 这个 HTTP 服务。
- 运行 SDK 客户端代码。

真正执行计算题的 Python 不在本机进程里，而是在 AgentCube 创建的 CodeInterpreter sandbox 里，由 Router 转发到 PicoD 执行。这个区分很重要，因为 AgentCube 的价值不在于本机能不能运行 Python，而在于它能把工具执行放到可管理、可隔离、可回收的 Kubernetes sandbox 中。

## 性能与准确性对比

为了进一步理解整体系统性能，我又做了一个小型 benchmark。评测文件保存在：

```text
internship-reports/benchmarks/shortest_path_benchmark.py
internship-reports/benchmarks/shortest_path_benchmark_result.json
```

这个 benchmark 使用同一张 10 节点最短路径图，对比六种方式：

| 方法 | 含义 |
| --- | --- |
| 本机 Python 直接算 | 在本机 Python 进程里直接跑 Dijkstra 算法 |
| 大模型直接回答 | 不使用工具，只让 LLM 根据题目直接输出答案 |
| AgentCube SDK 直连 sandbox | 不经过 LLM，直接通过 `CodeInterpreterClient` 在 sandbox 中运行 Python；这只代表 AgentCube 基础设施成本 |
| LLM tool call + 本机 Python | LLM 先决定调用工具，然后在本机 Python 执行工具代码，最后 LLM 根据工具结果输出答案 |
| LLM tool call + AgentCube SDK | LLM 先决定调用工具，再由 AgentCube sandbox 执行 Python，最后 LLM 根据工具结果输出答案 |
| `math-agent` 端到端 | 用户请求 -> LLM 决策 -> tool call -> AgentCube sandbox Python -> LLM 整理回答 |

运行前仍然需要先准备端口转发和启动 `math-agent`：

```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl port-forward -n agentcube svc/workloadmanager 18080:8080
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl port-forward -n agentcube svc/agentcube-router 18081:8080

cd /home/agentcube/cmd/cli/examples/math-agent
set -a
. .env
set +a
.venv/bin/python main.py
```

然后在仓库根目录运行：

```bash
set -a
. cmd/cli/examples/math-agent/.env
set +a
cmd/cli/examples/math-agent/.venv/bin/python internship-reports/benchmarks/shortest_path_benchmark.py
```

本次单次测量结果如下：

| 方法 | 时间 | 准确性 | 说明 |
| --- | ---: | --- | --- |
| 本机 Python 直接算 | 单次 `0.0332 ms`；10000 次均值 `0.0160 ms` | 正确 | 只包含本机算法执行时间 |
| 大模型直接回答 | `5887.03 ms` | 正确 | 包含网络请求和模型推理时间，不包含工具调用 |
| AgentCube SDK 直连 sandbox | `143.45 ms` | 正确 | 只代表 AgentCube 基础设施成本，不包含 LLM 思考 |
| LLM tool call + 本机 Python | `9374.52 ms` | 正确 | 包含 LLM 工具决策、本机 Python 执行、LLM 最终回答 |
| LLM tool call + AgentCube SDK | `9637.90 ms` | 正确 | 包含 LLM 产生工具调用、AgentCube sandbox 执行、LLM 最终回答 |
| `math-agent` 端到端 | `10835.66 ms` | 正确 | 在上一项基础上还包含 `math-agent` HTTP 服务和框架编排开销 |

这里要注意比较口径：

| 对比对象 | 是否公平 | 原因 |
| --- | --- | --- |
| 本机 Python 直接算 vs AgentCube SDK 直连 sandbox | 公平但只比较执行环境 | 两者都不包含 LLM，只比较“在哪里执行 Python” |
| 大模型直接回答 vs LLM tool call + AgentCube SDK | 公平 | 两者都包含 LLM 端到端耗时，只是一个不使用工具，一个使用 sandbox 工具 |
| LLM tool call + 本机 Python vs LLM tool call + AgentCube SDK | 最公平的工具路径对比 | 两者都包含 LLM 工具决策和最终回答，只替换工具执行位置 |
| AgentCube SDK 直连 sandbox vs 大模型直接回答 | 不公平 | 前者没有 LLM 思考时间，后者主要就是 LLM 推理时间 |

AgentCube SDK 直连 sandbox 的时间拆分：

```text
create_session_ms: 94.22
run_code_ms:       42.69
delete_session_ms:  6.54
total_ms:         143.45
```

公平的 tool-call 路径需要把 LLM 时间也算进去，拆分如下：

本机 Python tool-call：

```text
tool_decision_ms: 7842.66
local_tool_ms:     30.02
final_answer_ms: 1501.84
total_ms:        9374.52
```

AgentCube sandbox tool-call：

```text
tool_decision_ms:  8123.97
agentcube_tool_ms:  110.94
  create_session_ms: 56.49
  run_code_ms:       46.64
  delete_session_ms:  7.81
final_answer_ms:   1402.99
total_ms:          9637.90
```

这组数据说明：

- 对这种很小的图，本机 Python 直接算最快，因为它没有网络、没有容器、没有控制面和数据面开销。
- AgentCube SDK 直连 sandbox 不能和大模型直接回答做公平端到端比较，它只说明 AgentCube 执行基础设施本身大约是百毫秒级。
- 更公平的工具调用对比是 `LLM tool call + 本机 Python` 和 `LLM tool call + AgentCube SDK`。这次两者分别约 9.37 秒和 9.64 秒，差距约 263 ms。
- 两条 tool-call 路径的主要耗时都来自 LLM 生成工具调用和最终回答；本机 Python 工具执行约 30 ms，AgentCube sandbox 工具执行约 111 ms。
- 大模型直接回答虽然这次正确，且耗时约 5.9 秒，但准确性依赖模型推理，不适合把它当成可靠计算引擎。
- `math-agent` 端到端约 10.8 秒，比直接 LangChain tool-call 稍慢，差额主要来自 HTTP agent 服务和框架编排开销。
- AgentCube 的价值不是让小算法比本机更快，而是把执行环境从本机转移到可隔离、可复用、可回收、可审计的 sandbox 中。对于 LLM 生成的不可信代码、依赖复杂工具、长会话状态、浏览器工具或多用户隔离，这个额外百毫秒级成本是有意义的。
- `LLM tool call + 本机 Python` 只适合作为性能对照，不适合作为生产安全方案。它等价于让 LLM 生成的代码在本机执行，即使加了简单过滤，也不能替代真正的隔离环境。

从准确性角度看，本次六种方法都返回了正确答案：

```text
A -> C -> B -> D -> E -> F -> H -> I -> J
total weight = 18
```

但可靠性含义不同：

| 方法类型 | 准确性来源 | 风险 |
| --- | --- | --- |
| 本机 Python 直接算 | 确定性算法 | 没有隔离，不适合执行 LLM 生成的不可信代码 |
| 大模型直接回答 | 模型推理 | 题目变复杂后可能算错或编造路径 |
| LLM tool call + 本机 Python | LLM 负责理解，Python 负责计算 | 计算可靠，但执行环境不安全 |
| LLM tool call + AgentCube SDK | LLM 负责理解，sandbox Python 负责计算 | 计算可靠，并且执行环境隔离、可回收 |
| `math-agent` 端到端 | Agent 编排 + sandbox 工具执行 | 更接近真实产品形态，但有框架和服务开销 |

所以这次 benchmark 的结论不是“AgentCube 比本机更快”，而是：

```text
AgentCube 在 tool-call 端到端链路里只增加了百毫秒级执行环境成本，
但换来了 sandbox 隔离、session 管理、远端执行和资源回收能力。
对于真实 Agent 场景，这比直接在本机执行 LLM 生成代码更安全、更可控。
```

从工程角度看，最有说服力的对比是：

```text
LLM tool call + 本机 Python:      9374.52 ms
LLM tool call + AgentCube SDK:   9637.90 ms
差距:                              263.38 ms
```

也就是说，在这次实验里，把工具执行从本机 Python 换成 AgentCube sandbox，并没有改变秒级耗时的主要来源；主要耗时仍然是 LLM。AgentCube 增加的是可接受的隔离和调度成本，而不是主要瓶颈。

## 建议的最终展示实验：跑 `browser-agent`

如果 `math-agent` 成功，下一步建议跑 `browser-agent`，因为它更能体现 AgentCube 的定位。

### 1. 创建 Playwright MCP 工具 runtime

```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl apply -f example/browser-agent/browser-use-tool.yaml
```

这个资源会创建一个 `AgentRuntime` 模板，但不会马上创建 sandbox。真正的 sandbox 会在 Router 收到调用时由 Workload Manager 创建。

### 2. 创建 LLM API Secret

```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl create secret generic browser-agent-secrets \
  --from-literal=openai-api-key='<YOUR_API_KEY>'
```

### 3. 构建并部署 Browser Agent

如果有 Docker：

```bash
docker build -t browser-agent:latest -f example/browser-agent/Dockerfile .
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl apply -f example/browser-agent/deployment.yaml
```

当前环境没有 Docker，所以这一步需要先解决镜像构建问题。可以考虑改用 containerd/nerdctl，或者在外部构建后推送到镜像仓库。

### 4. 调用真实任务

```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl port-forward deploy/browser-agent 8000:8000

curl -s http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Search for the latest Kubernetes release notes and summarize the key changes"}'
```

预期现象：

```text
用户请求
-> browser-agent 规划浏览器任务
-> Router 收到对 browser-use-tool 的调用
-> Workload Manager 创建 AgentRuntime sandbox
-> Playwright MCP 工具在 sandbox 中执行浏览器操作
-> browser-agent 总结结果并返回
```

如果返回里有 `session_id`，后续请求可以传回同一个 `session_id`，验证 sandbox 会话复用。

## 验收标准

我认为不能只用 Pod `Running` 作为验收标准。真实 agent 的验收标准应该包括：

- 用户输入是自然语言任务，而不是手写 Python 代码。
- 日志里能看到 Agent 发起工具调用。
- AgentCube 中能看到新建的 sandbox 或 AgentRuntime 相关资源。
- 返回结果来自工具执行，而不是 LLM 直接编造。
- 第二次请求能复用同一个 `x-agentcube-session-id`。
- 失败时能定位失败发生在 LLM、Agent 服务、Router、Workload Manager、sandbox 还是工具本身。

## 今天的结论

Day 1 的价值是证明 AgentCube 基础设施能跑通，但它不是完整的真实 Agent demo。

我认为后续应该先完成 `math-agent`，把 LLM + CodeInterpreter 工具调用闭环跑通；然后再推进 `browser-agent`，展示 AgentCube 对工具 runtime 和 session 的管理能力。

一句话总结今天的判断：

```text
真实 Agent 不是“我手动调用 CodeInterpreter 执行代码”，
而是“LLM Agent 根据任务自主选择工具，并通过 AgentCube 创建、复用和管理工具 sandbox”。
```
