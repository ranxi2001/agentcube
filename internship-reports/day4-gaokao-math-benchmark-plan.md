# Day 4 工作计划：用 2026 高考数学题测试 `math-agent`

## 背景

Day 3 已经用 10 节点最短路径题验证了 `math-agent` 的基础链路：

```text
用户问题 -> LLM 决策 -> Python tool -> AgentCube sandbox -> Python 执行 -> LLM 总结
```

但最短路径题本身太简单，题型单一，主要验证的是图算法和工具调用链路。为了更真实地评估 `math-agent` 的数学能力，Day 4 可以引入 **2026 年高考数学试题** 作为 benchmark 数据源。

这样可以覆盖更多能力：

- 符号推理。
- 函数与导数。
- 数列与不等式。
- 概率统计。
- 解析几何。
- 立体几何。
- 三角函数。
- 综合解答题的多步推理。

## 资料来源

目前可用的公开来源包括：

| 来源 | 作用 |
| --- | --- |
| 教育在线：`2026年全国新一卷数学试题+参考答案` | 可作为全国新一卷题目与答案的公开来源 |
| 教育在线数学试题频道 | 可查看全国新一卷、全国二卷、上海卷等不同卷种 |
| 教育部教育考试院 / 人民网试题评析 | 可作为命题特点、考查方向和题型结构说明 |

注意：教育在线页面的真题主体多为图片，并且页面有版权声明。因此仓库中不建议直接复制整套试题原文。更合适的做法是：

- 仓库里保存 benchmark 脚本、数据格式、题型标签和结果。
- 真题题面放在本地私有 JSONL 文件或运行时输入文件中。
- 报告中只记录来源链接、题号、题型、预期答案和评测结果。

## Benchmark 目标

这次 benchmark 不只是测“能不能算对”，还要测：

| 维度 | 说明 |
| --- | --- |
| 准确性 | 最终答案是否正确 |
| 解题链路 | 是否调用了 Python tool，还是 LLM 直接回答 |
| 工具适配度 | Python 是否适合求解该题，是否需要符号计算或数值验证 |
| 端到端耗时 | 从用户请求到最终回答的总时间 |
| tool-call 时间拆分 | LLM 工具决策、sandbox 执行、最终回答分别耗时多少 |
| 可解释性 | 最终回答是否给出足够的关键步骤 |
| 稳定性 | 同一题多轮运行是否得到一致答案 |

## 题目选择原则

第一轮不必跑完整套试卷，先从 6 到 8 道题开始，覆盖不同题型和难度。

| 类型 | 建议题量 | 选择原因 |
| --- | ---: | --- |
| 选择题 / 填空题 | 2 | 答案短，适合做准确性快速验证 |
| 函数与导数 | 1 | 测试符号推理和极值分析 |
| 数列 / 不等式 | 1 | 测试递推、归纳和代数变形 |
| 概率统计 | 1 | 适合 Python 辅助枚举或数值验证 |
| 解析几何 | 1 | 测试坐标化、方程求解和计算稳定性 |
| 综合解答题 | 1-2 | 测试多步推理、工具使用和最终表达能力 |

## 数据集格式

建议把真题整理成本地 JSONL 文件，例如：

```text
internship-reports/private/gaokao_math_2026.jsonl
```

这个目录不提交到仓库。每行一个题目：

```json
{
  "id": "2026-new1-math-q01",
  "source": "https://gaokao.eol.cn/shiti/zhenti/202606/t20260608_2742417.shtml",
  "paper": "2026全国新一卷数学",
  "question_no": "1",
  "type": "single_choice",
  "topic": ["集合", "基础运算"],
  "difficulty": "easy",
  "prompt": "题面文本放在本地私有文件中，不提交仓库",
  "expected_answer": "A",
  "grading": {
    "mode": "exact",
    "answer": "A"
  }
}
```

对于解答题，可以记录更灵活的评分方式：

```json
{
  "id": "2026-new1-math-q19",
  "source": "https://gaokao.eol.cn/shiti/zhenti/202606/t20260608_2742417.shtml",
  "paper": "2026全国新一卷数学",
  "question_no": "19",
  "type": "proof_or_solution",
  "topic": ["函数", "导数", "不等式"],
  "difficulty": "hard",
  "prompt": "题面文本放在本地私有文件中，不提交仓库",
  "expected_answer": "参考答案摘要或关键结论",
  "grading": {
    "mode": "rubric",
    "required_points": [
      "给出正确的关键转化",
      "得到正确的最终结论",
      "步骤没有明显逻辑断裂"
    ]
  }
}
```

## 评测路径设计

沿用 Day 3 的对比思路，但题目变成高考数学题：

| 方法 | 目的 |
| --- | --- |
| LLM 直接回答 | 测模型裸能力和幻觉风险 |
| LLM tool call + 本机 Python | 性能对照，不作为安全方案 |
| LLM tool call + AgentCube SDK | 公平测工具调用 + sandbox 执行 |
| `math-agent` 端到端 | 测真实 agent 服务形态 |

对于每道题记录：

```text
direct_llm_total_ms
local_tool_total_ms
agentcube_tool_total_ms
math_agent_total_ms
tool_decision_ms
tool_execution_ms
final_answer_ms
accurate
used_tool
error
```

## 准确性评分

不同题型需要不同评分方式：

| 题型 | 评分方式 |
| --- | --- |
| 单选题 | 精确匹配选项 |
| 多选题 | 集合匹配，顺序无关 |
| 填空题 | 数值等价或表达式等价 |
| 概率 / 统计 | 分数、小数、百分数归一化比较 |
| 解析几何 | 关键方程、坐标、范围或最终结论匹配 |
| 解答题 | rubric 评分，记录关键步骤是否出现 |

第一阶段可以先做自动评分容易的题：选择、填空、数值计算题。综合解答题先做人工复核，后续再设计 rubric 自动化。

## 对 `math-agent` 的改进点

高考题测试会暴露 `math-agent` 的几个不足：

1. 当前 tool 只接受一段 Python code，缺少题目结构化信息。
2. tool call 每次创建新的 `CodeInterpreterClient()`，需要确认是否自动清理 session。
3. 对符号数学支持有限，可能需要引入 `sympy` 或在 sandbox 镜像中安装数学库。
4. 解答题需要更强的最终解释能力，不能只返回一个数值。
5. 需要记录每一步耗时，便于区分 LLM 慢、tool 慢还是 sandbox 慢。

## 建议实验步骤

### Step 1：整理题库

先选 6 到 8 道题，覆盖不同题型。题面放本地私有 JSONL，不提交仓库。

### Step 2：扩展 benchmark 脚本

在现有 `shortest_path_benchmark.py` 基础上抽象出通用 runner：

```text
load_cases(jsonl)
run_direct_llm(case)
run_local_tool(case)
run_agentcube_tool(case)
run_math_agent(case)
grade(case, response)
write_result(json)
```

当前已落地一个 runner 草稿：

```text
internship-reports/benchmarks/gaokao_math_benchmark.py
internship-reports/benchmarks/gaokao_math_2026_cases.json
```

设计方式：

- 题面从 `benchmark-data/2026-gaokao-math-questions.md` 解析，不把答案混在无答案数据集里。
- `gaokao_math_2026_cases.json` 只保存题号、题型、topic、难度、评分方式和预期答案。
- 默认执行 `dry_run`，只检查题面解析和 case 选择，不调用 LLM，也不创建 AgentCube sandbox。
- 可选方法包括 `direct_llm`、`llm_tool_local_python`、`llm_tool_agentcube`、`math_agent`。
- 输出统一为 JSON，包含每题耗时、response、grade、tool timing 和 usage metadata。

常用命令：

```bash
# 只检查前 3 题解析，不消耗 API
python3 internship-reports/benchmarks/gaokao_math_benchmark.py --limit 3

# 只检查第 13 题解析和评分配置
python3 internship-reports/benchmarks/gaokao_math_benchmark.py --case 13 --methods dry_run

# 小样本直接 LLM，对 API 有消耗
python3 internship-reports/benchmarks/gaokao_math_benchmark.py \
  --case 1,4,8,13 \
  --methods direct_llm \
  --output internship-reports/benchmarks/gaokao_math_direct_llm_result.json

# 公平 tool-call 对比，对 API 和 sandbox 都有消耗
python3 internship-reports/benchmarks/gaokao_math_benchmark.py \
  --case 1,8,13 \
  --methods llm_tool_local_python,llm_tool_agentcube \
  --output internship-reports/benchmarks/gaokao_math_tool_compare_result.json
```

调试记录：

- 初版脚本使用了 `from __future__ import annotations`、`dict[str, Any]`、`Path | None`、`subprocess.run(capture_output=True, text=True)` 等新语法。
- 当前环境的 `python3` 是 `Python 3.6.8`，执行 `python3 -m py_compile internship-reports/benchmarks/gaokao_math_benchmark.py` 时直接报错：

```text
SyntaxError: future feature annotations is not defined
```

- 处理方式：移除 `future annotations`，改用 `typing.Dict/List/Optional/Tuple`，并把 `subprocess.run` 改为 `stdout=subprocess.PIPE`、`stderr=subprocess.PIPE`、`universal_newlines=True`。
- 修复后已通过：

```bash
python3 -m py_compile internship-reports/benchmarks/gaokao_math_benchmark.py
python3 internship-reports/benchmarks/gaokao_math_benchmark.py --limit 3
python3 internship-reports/benchmarks/gaokao_math_benchmark.py --case 13 --methods dry_run
```

离线评分自测结果：

- 单选题：能从 `最终答案：B` 中抽取选项。
- 多选题：能从 `最终答案：A、C、D` 中做集合匹配。
- 填空题：能识别常见 LaTeX 形式，例如 `\sqrt{\frac{11}{6}}`、`\frac{3\pi}{2}`、`\sqrt[3]{\frac32}`。
- 解答题、证明题先标记为 `manual`，只记录参考结论摘要，避免伪自动评分。

### Step 3：跑小样本

先每题跑 1 次，控制 LLM API 消耗，确认链路和评分逻辑。

已完成第一轮最小真实评测：前 5 道单选题，方法为 `direct_llm`，不调用 tool，不启动 AgentCube sandbox。

运行命令：

```bash
cmd/cli/examples/math-agent/.venv/bin/python internship-reports/benchmarks/gaokao_math_benchmark.py \
  --case 1,2,3,4,5 \
  --methods direct_llm \
  --max-tokens 600 \
  --output internship-reports/benchmarks/gaokao_math_direct_llm_q01_q05_result.json
```

结果摘要：

| 题号 | 预期 | 模型答案 | 耗时 ms | tokens |
| --- | --- | --- | ---: | ---: |
| 1 | B | B | 2960.87 | 187 |
| 2 | A | A | 6497.57 | 275 |
| 3 | C | C | 4254.81 | 428 |
| 4 | D | D | 4314.58 | 295 |
| 5 | D | D | 6036.76 | 449 |

汇总：

- 自动评分：5 / 5 正确。
- 准确率：100%。
- 平均耗时：4812.92 ms。
- p50 耗时：4314.58 ms。
- 最大耗时：6497.57 ms。
- 结果文件：`internship-reports/benchmarks/gaokao_math_direct_llm_q01_q05_result.json`。

这轮只建立裸模型基线，不能说明 AgentCube 对复杂数学题的收益。下一轮应选 2 到 3 道更适合工具的题，例如第 8 题期望、第 13 题三角函数、第 14 题数列，跑 `llm_tool_local_python` 与 `llm_tool_agentcube` 对比。

已完成第二轮标准对比：第 8、13、14 题，覆盖期望、三角函数、数列三类更适合工具辅助的题型。

对比方法：

| 方法 | 说明 |
| --- | --- |
| `direct_llm` | 裸 LLM，单次模型调用，不使用工具 |
| `llm_tool_call_local_python` | LLM 工具决策 + 本机 Python + LLM 最终回答 |
| `llm_tool_call_agentcube` | LLM 工具决策 + AgentCube sandbox Python + LLM 最终回答 |
| `math_agent` | HTTP math-agent 端到端调用 |

运行中遇到的环境问题：

- 第一次跑 `llm_tool_agentcube` 时失败：`localhost:18080` 连接被拒绝。
- 原因：Kubernetes 内的 `workloadmanager` 和 `agentcube-router` Pod 正常运行，但本地没有 port-forward。
- 修复命令：

```bash
kubectl -n agentcube port-forward svc/workloadmanager 18080:8080
kubectl -n agentcube port-forward svc/agentcube-router 18081:8080
```

- 第 14 题本机 tool-call 曾生成 `import sympy as sp`，本机环境没有 `sympy`，工具输出 `ModuleNotFoundError: No module named 'sympy'`，但模型最终仍给出正确答案。
- AgentCube runner 初版遇到 sandbox 执行错误时会直接把整条评测标记为异常；已修复为把 sandbox 错误作为 `tool_output` 交给 LLM 最终回答，这样才能公平观察“工具环境缺库”对最终答案的影响。

标准对比结果文件：

```text
internship-reports/benchmarks/gaokao_math_compare_q08_probe_result.json
internship-reports/benchmarks/gaokao_math_compare_q13_q14_result.json
internship-reports/benchmarks/gaokao_math_agentcube_q08_probe_result.json
internship-reports/benchmarks/gaokao_math_agentcube_q13_q14_result.json
internship-reports/benchmarks/gaokao_math_agentcube_q14_retry_result.json
internship-reports/benchmarks/gaokao_math_math_agent_q08_q13_q14_result.json
internship-reports/benchmarks/gaokao_math_standard_compare_q08_q13_q14_result.json
```

逐题结果：

| 题号 | 方法 | 正确 | 总耗时 ms | tool 执行 ms |
| --- | --- | --- | ---: | ---: |
| 8 | `direct_llm` | 是 | 4407.49 | - |
| 8 | `llm_tool_call_local_python` | 是 | 6686.50 | 28.05 |
| 8 | `llm_tool_call_agentcube` | 是 | 5711.91 | 127.04 |
| 8 | `math_agent` | 是 | 5335.21 | 未暴露 |
| 13 | `direct_llm` | 是 | 21687.94 | - |
| 13 | `llm_tool_call_local_python` | 是 | 28529.73 | 31.66 |
| 13 | `llm_tool_call_agentcube` | 是 | 36469.45 | 132.56 |
| 13 | `math_agent` | 是 | 20134.58 | 未暴露 |
| 14 | `direct_llm` | 是 | 32752.43 | - |
| 14 | `llm_tool_call_local_python` | 是 | 40399.15 | 28.49 |
| 14 | `llm_tool_call_agentcube` | 是 | 57442.16 | 126.47 |
| 14 | `math_agent` | 是 | 25017.86 | 未暴露 |

汇总：

| 方法 | 题数 | 正确率 | 平均总耗时 ms | 平均 tool 执行 ms |
| --- | ---: | ---: | ---: | ---: |
| `direct_llm` | 3 | 100% | 19615.95 | - |
| `llm_tool_call_local_python` | 3 | 100% | 25205.13 | 29.40 |
| `llm_tool_call_agentcube` | 3 | 100% | 33207.84 | 128.69 |
| `math_agent` | 3 | 100% | 16829.22 | 未暴露 |

解释：

- 这 3 道题上四条路径都正确，说明小样本下准确性还不能拉开差距。
- `llm_tool_call_agentcube` 比 `llm_tool_call_local_python` 平均多约 `99.29 ms` 的工具执行开销，这部分主要来自 session create/run/delete 和 router/sandbox 调用。
- 端到端耗时主要由 LLM 决策与最终回答主导，而不是 Python 执行本身。
- `math_agent` 当前只暴露 HTTP 端到端耗时，没有 tool decision、sandbox run、final answer 的细分 hooks，所以它的总耗时只能作为真实服务形态参考，不能直接和 SDK tool-call 的阶段拆分做完全公平比较。
- 第 14 题暴露了数学工具环境问题：复杂数学题容易诱导模型调用 `sympy`，后续需要决定是在 sandbox 镜像中预装 `sympy`，还是在 system prompt 中明确“仅使用标准库”。

### Step 4：跑多轮稳定性

对每题跑 3 次，记录：

- 是否每次都调用工具。
- 是否每次答案一致。
- 是否有 session 残留。
- p50 / p95 延迟。

### Step 5：形成 Day 4 报告

报告重点不是“模型能不能做高考题”，而是：

- AgentCube 在复杂数学 agent 任务中承担什么角色。
- 工具调用相比 LLM 直接回答是否提高可靠性。
- sandbox 执行相比本机 Python 增加多少成本。
- 哪些题型适合 Python tool，哪些题型更依赖符号推理或人类式证明。

## 风险与注意事项

| 风险 | 应对 |
| --- | --- |
| 真题版权问题 | 仓库不提交完整题面，只记录来源、题号、标签和结果 |
| OCR 题面错误 | 手工校对少量题目，优先选择文本清晰题 |
| LLM API 消耗过多 | 每题先跑 1 次，小样本验证后再扩展 |
| 评分标准复杂 | 先做选择/填空/数值题，解答题人工复核 |
| sandbox 缺少数学库 | 先用标准库和纯 Python，必要时记录需要扩展镜像 |
| 本机 tool-call 不安全 | 只作为性能对照，真实方案仍使用 AgentCube sandbox |

## Day 4 预期产出

- 一份高考数学 benchmark 题库格式说明。
- 一个可复用的高考数学 benchmark runner 草稿。
- 6 到 8 道题的小样本测试结果。
- 一份按题型分析的准确性和耗时报告。
- 一个 `math-agent` 改进点列表。

## 初步结论

2026 高考数学题比最短路径题更适合测试 `math-agent` 的真实能力。它能同时考察 LLM 的题意理解、工具调用决策、Python/sandbox 的计算能力，以及最终答案组织能力。

但为了保证实验可信，Day 4 应该先小样本、可追溯、可评分地做，而不是一次性把整套真题丢给模型。真正有价值的结果不是单题是否做对，而是不同题型下：

```text
LLM 直接回答是否可靠？
使用工具后是否更稳定？
AgentCube sandbox 相比本机 Python 增加多少成本？
这些成本是否换来了更安全可控的执行环境？
```
