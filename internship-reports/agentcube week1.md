# AgentCube Week 1 工作计划与 Mentor 交流纪要

## 背景

本周 mentor 主要介绍了 AgentCube 第一阶段的工作方向：围绕 **独立 Agent 沙箱** 展开调研、测试和开源贡献。

我对这次交流的理解是：第一周不只是把项目跑起来，还要开始从“使用者”和“开源参与者”两个角度进入项目。一方面要通过 benchmark 量化 AgentCube 沙箱的启动和执行性能，另一方面要学习如何在开源社区中发现问题、提出改进、提交 PR，并参与项目讨论。

## 本周核心目标

| 方向 | 目标 |
| --- | --- |
| 独立 Agent 沙箱 | 理解 AgentCube 如何创建、路由、复用和回收 sandbox |
| 性能测试 | 测量 sandbox 启动时延、执行时延、并发启动表现和端到端 agent 调用时间 |
| Benchmark 方法 | 用可复现脚本记录时间、准确性、成功率和环境信息 |
| 开源贡献 | 阅读项目、发现问题、提交无争议 PR，并尝试参与 issue 讨论 |
| 社区理解 | 理解维护者视角、项目路线、文档国际化和开发者关系 |

## 技术工作：独立 Agent 沙箱测试

### 1. 测试对象

本周测试重点放在 AgentCube 的 sandbox 能力上，主要包括：

- CodeInterpreter sandbox 的创建、执行和删除。
- Router 到 sandbox 的请求转发链路。
- Workload Manager 创建 session 的控制面时延。
- LLM Agent 调用工具时，AgentCube sandbox 在整体耗时中的占比。
- 并发创建 sandbox 时的时延和成功率。

### 2. 核心指标

| 指标 | 含义 |
| --- | --- |
| `create_session_ms` | Workload Manager 创建 sandbox session 的耗时 |
| `run_code_ms` | Router 转发到 sandbox 并执行代码的耗时 |
| `delete_session_ms` | 删除 session / 回收 sandbox 的耗时 |
| `total_ms` | 一次完整调用的总耗时 |
| `p50 / p95 / p99` | 多次 benchmark 下的延迟分位数 |
| success rate | 并发或重复测试中的成功率 |
| error type | 失败时属于 LLM、Router、Workload Manager、Redis、sandbox 还是环境问题 |
| resource usage | Pod 数量、CPU、内存、启动过程中的资源变化 |

### 3. Benchmark 场景

第一周优先做下面几类测试：

| 场景 | 目的 |
| --- | --- |
| 本机 Python 直接计算 | 作为性能上限基线，只看本机算法执行时间 |
| 大模型直接回答 | 对比不使用工具时的 LLM 推理耗时和准确性 |
| LLM tool call + 本机 Python | 对比“有工具调用但不使用 AgentCube”的端到端耗时 |
| AgentCube SDK 直连 sandbox | 测量 AgentCube 基础设施成本，不包含 LLM 思考时间 |
| LLM tool call + AgentCube SDK | 公平测量 LLM 工具决策 + AgentCube sandbox 执行 + LLM 最终回答 |
| `math-agent` 端到端 | 测量真实 agent 服务形态下的整体耗时 |
| 并发创建 sandbox | 测量多个 session 同时创建时的延迟、成功率和资源压力 |

### 4. 已完成的初步验证

目前已经完成了一个 10 节点最短路径 benchmark，评测脚本和结果保存在：

```text
internship-reports/benchmarks/shortest_path_benchmark.py
internship-reports/benchmarks/shortest_path_benchmark_result.json
```

初步结果：

| 方法 | 时间 | 准确性 |
| --- | ---: | --- |
| 本机 Python 直接算 | `0.0332 ms` | 正确 |
| 大模型直接回答 | `5887.03 ms` | 正确 |
| AgentCube SDK 直连 sandbox | `143.45 ms` | 正确 |
| LLM tool call + 本机 Python | `9374.52 ms` | 正确 |
| LLM tool call + AgentCube SDK | `9637.90 ms` | 正确 |
| `math-agent` 端到端 | `10835.66 ms` | 正确 |

关键结论：

```text
LLM tool call + 本机 Python:      9374.52 ms
LLM tool call + AgentCube SDK:   9637.90 ms
差距:                              263.38 ms
```

这说明在当前实验里，主要耗时来自 LLM，而不是 AgentCube。AgentCube 增加的是百毫秒级 sandbox/session/路由开销，但换来的是隔离、远端执行、资源回收和更适合生产的安全边界。

### 5. 待补充测试

接下来需要继续补充：

- 多轮重复测试，计算 p50、p95、p99。
- 冷启动和 warm pool 场景对比。
- 并发创建 5、10、20 个 sandbox 的延迟和成功率。
- sandbox 删除后是否有残留 Pod、Sandbox CR 或 Redis 状态。
- `math-agent` 工具函数自动清理 session 的修复验证。
- 更复杂计算题或文件处理任务，测试稳定性和准确性。

## 开源工作方向

Mentor 提到的第二条主线是开源参与。我的理解是，开源工作不只是写代码，还包括阅读、沟通、维护和推动项目发展。

### 1. 阅读项目和代码

第一周要继续熟悉：

- `cmd/`：各核心进程入口，例如 `workload-manager`、`router`、`picod`。
- `pkg/workloadmanager/`：sandbox 创建、session 管理、controller 逻辑。
- `pkg/router/`：请求路由、session 查找、代理转发。
- `sdk-python/`：用户侧 SDK、`CodeInterpreterClient` 和 `AgentRuntimeClient`。
- `example/`：真实 agent 示例，例如 `browser-agent`、`pcap-analyzer`。
- `manifests/charts/base`：Helm 部署和运行配置。

### 2. 无争议 PR

适合第一周尝试的 PR 应该尽量“小、清晰、低争议”，例如：

- 文档错别字、命令修正、路径修正。
- README 或 tutorial 中 service 名称不一致的问题。
- 示例中的环境变量说明补充。
- benchmark 脚本或实验说明文档。
- `math-agent` 中 `CodeInterpreterClient()` 未自动 `stop()` 的资源清理改进。
- 测试用例补充，例如 session 清理、错误提示、配置校验。

这类 PR 的目标是熟悉项目贡献流程，降低 review 成本，先建立一次完整开源贡献经验。

### 3. 有争论的 issue / 讨论

除了无争议 PR，也要开始观察真正有价值的问题讨论，例如：

- sandbox 冷启动时延如何优化。
- warm pool 应该如何配置和暴露给用户。
- AgentRuntime 与 CodeInterpreter 的边界如何划分。
- Router、Workload Manager 和 SDK 的错误信息是否足够清晰。
- 是否需要官方 benchmark suite。
- AgentCube 与 Volcano 的长期关系和 demo 方向。

这类 issue 不一定马上提交代码，但可以通过补充实验数据、复现步骤、设计建议参与讨论。

### 4. 维护者视角

Mentor 提到要理解“维护者”视角。我理解维护者不只是合并 PR，还要考虑：

- 项目路线和里程碑。
- API 是否稳定。
- 文档是否能帮助新用户快速上手。
- 新功能是否增加维护成本。
- 社区问题是否有人响应。
- demo 是否能展示项目价值。
- 开源贡献者是否容易参与。

所以本周的报告和 benchmark 不只是个人学习记录，也应该逐渐变成能帮助项目发展的材料。

## 文档与社区工作

### 1. 国际化文档

可以关注：

- 英文文档和中文说明是否一致。
- Getting Started 是否缺少中文解释。
- 示例命令是否适合国内网络和本地 k3s 环境。
- API key、Redis password、KUBECONFIG 等敏感配置是否有安全提示。

### 2. Demo 与 Volcano 方向

Mentor 提到 Volcano demo，我的理解是需要思考：

- AgentCube 如何展示 Volcano 在 AI Agent workload 上的价值。
- demo 应该突出 sandbox 生命周期管理、资源调度、并发启动、session 复用。
- 真实 agent demo 可以优先考虑 `math-agent`、`browser-agent` 或 `pcap-analyzer`。
- demo 不应只展示 `print("hello")`，而要展示 LLM 如何通过 AgentCube 调用工具完成真实任务。

### 3. 开源社区参与

第一周可以先做：

- 阅读已有 issue 和 PR。
- 关注维护者讨论的问题。
- 记录自己遇到的文档问题和复现步骤。
- 准备一个小 PR。
- 在有把握的问题下补充复现结果或 benchmark 数据。

## 第一周建议节奏

| 时间 | 重点 |
| --- | --- |
| Day 1 | 跑通 Getting Started，记录环境和部署卡点 |
| Day 2 | 阅读项目结构和技术栈，理解 Go / Python / Kubernetes 分层 |
| Day 3 | 跑通真实 `math-agent`，完成最短路径 benchmark |
| Day 4 | 扩展 benchmark：重复测试、并发启动、冷启动/warm pool |
| Day 5 | 整理报告，选择一个低争议 PR 或 issue 参与方向 |

## 本周预期产出

- Day 1 到 Day 3 的实习报告。
- 一份真实 agent workflow 报告。
- 一份最短路径 benchmark 脚本和结果。
- 一份 sandbox 性能测试计划。
- 至少一个可提交的文档或代码改进点。
- 一份下周继续推进的 TODO 列表。

## 风险与注意事项

| 风险 | 应对 |
| --- | --- |
| LLM API 额度消耗过快 | benchmark 控制调用次数，先用 SDK smoke test，再做少量 LLM 调用 |
| 本地执行 LLM 生成代码不安全 | 本机 Python tool-call 只作为性能对照，真实方案应使用 AgentCube sandbox |
| 环境中没有 Docker | 优先跑不需要构建镜像的 `math-agent`，复杂 demo 再考虑 registry 或 containerd 构建 |
| session 未清理导致资源残留 | 每次实验后检查 `kubectl get sandbox -A`，必要时手动删除 session |
| benchmark 口径不公平 | 明确区分基础设施耗时、LLM 推理耗时和 agent 端到端耗时 |
| PR 范围过大 | 第一周优先选择文档修正、示例修正、测试补充等小 PR |

## 一句话总结

第一周的重点是从“跑通 AgentCube”推进到“量化 AgentCube sandbox 的真实价值”，同时开始以开源贡献者的身份理解项目：发现问题、记录证据、补充文档、准备 PR，并逐步参与社区讨论。
