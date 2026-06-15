# Week 1 周会汇报：AgentCube 调研、测评与 Codex 协作

日期：2026-06-15

## 上周工作概览

上周主要围绕 AgentCube 的独立 Agent 沙箱能力展开，目标是先把项目跑通，再用可复现 benchmark 理解它在 AI Agent 执行场景中的价值和边界。

完成的主要工作：

- 跑通 AgentCube Getting Started、本地 k3s 部署、Redis、Workload Manager、Router、CodeInterpreter 和 Python SDK 调用链路。
- 梳理 AgentCube 的 Go / Python / Kubernetes 技术栈，理解 Workload Manager、Router、PicoD、CRD、SDK 的分层关系。
- 跑通 `math-agent`，完成最短路径任务和高考数学题小样本 benchmark。
- 编写 CodeInterpreter sandbox 延迟测试脚本，区分 `create_session`、`run_code`、`delete_session` 和总耗时。
- 做 warm pool 参数实验，测试 `warmPoolSize=2/5/10/20` 对并发 10 请求的影响。
- 调研 forkd、CubeSandbox、cage-bro 等竞品，建立隔离等级、OS 兼容性、部署难度、安全能力、云原生支持和性能数据矩阵。
- 分析 AgentCube GitHub 当前 open issues / PRs，开始从维护者和贡献者视角理解社区方向。
- 建立实习 TODO 管理文档和 fork/upstream git 工作流规范。

## 关键测评结论

AgentCube 当前测试主要测的是 CodeInterpreter sandbox 基础设施链路，不包含 LLM 推理、Agent 规划和工具选择。

本机 AgentCube sandbox 顺序 5 次测试中，`total` p50 约 `177.14 ms`，其中创建 session 是主要开销。并发 10 且 `warmPoolSize=2` 时，p50 升到约 `7315.21 ms`，主要原因是预热池不够，发生 pool miss。

调整 warm pool 后，并发 10 明显改善：

- `warmPoolSize=5`：p50 约 `503-528 ms`，但仍出现长尾和一次 504。
- `warmPoolSize=10`：p50 约 `436-565 ms`，p95 控制在约 `804-933 ms`。
- `warmPoolSize=20`：p50 约 `672-698 ms`，没有继续变好，说明不是越大越优。

同机 cage-bro 基础延迟更低，顺序 p50 约 `18.41 ms`，并发 10 p50 约 `58.48 ms`，但它和 AgentCube 不是同一隔离等级：cage-bro 更偏本地进程/系统调用限制，AgentCube 是 Kubernetes 管理的 sandbox 生命周期，两者不能简单按倍率判断优劣。

forkd 当前机器没有跑通，原因不是操作问题，而是环境不满足：CentOS 8 glibc 2.28、kernel 4.18、无 `/dev/kvm`、CPU 未暴露 `vmx/svm`。这也说明后续 MicroVM / KVM 类竞品需要单独准备机器环境。

## 竞品和生态理解

目前看到的趋势是：Agent 基础设施正在从“只调度模型推理”扩展到“调度可执行、可隔离、可快速复制状态的代码运行环境”。

- forkd / CubeSandbox 更偏底层 MicroVM、KVM、快照和快速 fork。
- cage-bro 更偏轻量本地沙箱和工具集合。
- AgentCube 更偏 Kubernetes / Volcano 体系下的 Agent workload 管理、调度、生命周期和云原生集成。

所以 AgentCube 的价值不只是单次执行快，而是把 sandbox 作为集群资源管理起来：可预热、可回收、可调度、可观测，并和后续 SnapStart、warm pool、multi-AgentCube、E2B API 兼容等方向衔接。

## 如何使用 Codex 提效

这周我主要把 Codex 当作“结对工程师 + 实验记录助手”使用，而不是只让它写代码。

具体协作方式：

- 让 Codex 先读仓库结构、README、日报和 benchmark 脚本，再基于现有项目风格修改文档或脚本。
- 让 Codex 帮我生成可复现 benchmark 脚本，并在本机运行、保存 JSON 结果、整理 p50/p95 和失败原因。
- 遇到环境问题时，让 Codex 一边跑命令一边记录失败命令、错误现象、根因和解决方案，减少手工整理成本。
- 对 forkd、CubeSandbox、cage-bro 这类竞品，让 Codex 帮我区分“本机实测数据、官方数据、工程推断”，避免把不同机器的数据直接硬比。
- 让 Codex 把临时讨论沉淀成正式文档，例如 Day5-Day9 报告、竞品矩阵、TODO 看板、fork/upstream git 规范。
- 对 git 操作，让 Codex 辅助检查 ahead/behind、rebase、force-with-lease 和 upstream PR 分支策略，降低误操作风险。

实际效果是：我可以把精力集中在判断测试口径、解释结果和选择下一步方向上，Codex 帮我承担了大量重复的资料整理、脚本调整、命令执行和报告归档工作。

## 下周计划

下周建议优先做三件事：

1. 阅读社区 #365、#366、#379、#265，重点关注 SnapStart、warm pool 和 benchmark 口径，选择一个适合参与的 issue 或小 PR。
2. 补 Agent 端到端 benchmark，明确区分 LLM 推理、Agent 规划、tool call 和 AgentCube sandbox 基础设施耗时。
3. 补充 `warmPoolSize=0`、并发 5/20、p99 和资源残留检查，让性能结论更完整。
