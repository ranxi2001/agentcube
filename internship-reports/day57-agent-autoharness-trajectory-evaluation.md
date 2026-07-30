# Day 57：Agent AutoHarness 与轨迹评估闭环

日期：2026-07-30

## 1. 本轮结论

本轮新增 `.agents/skills/agent-autoharness/`，把“看到一次漏审后改 prompt”升级为可回归的 harness 工程流程：先冻结任务和 grader，再采集可观察轨迹，分别评估任务达成、查全/查准、资源效率和轨迹合理性，最后用同任务 baseline/challenger gate 决定是否接纳 skill、prompt、tool、memory 或 verification 改动。

这个 skill 不是照搬某一篇 AutoHarness 论文。近期工作的共同方向是把 agent 外部执行系统当成可优化程序，但各自解决的问题不同：原始 AutoHarness 优化环境合法动作，Adaptive Auto-Harness 处理持续演化和任务适配，TRAJEVAL 定义代码 agent 的搜索/阅读/编辑轨迹指标，HarnessFix 负责把失败归因到 harness layer 并选择修复算子。本轮将这些机制组合成适合 AgentCube coding/review agent 的评估合同。

> 注释：这里的 harness 是 agent 外部的执行支架，包括 prompt、skill、context router、tool adapter、retry/stop policy、trace、grader、permission gate。它不是只指一段系统提示词。

## 2. 近期 AutoHarness 工作怎么做

| 工作 | 核心机制 | 可迁移到本项目的部分 | 不能直接套用的部分 |
| --- | --- | --- | --- |
| [AutoHarness](https://arxiv.org/abs/2603.03329) | 用树保存 code harness 假设，Thompson sampling 选节点，LLM mutation，environment critic 返回非法动作/奖励 | 把 harness 变更视为候选程序；用环境反馈而不是主观印象选择版本 | 直接指标是合法动作准确率和游戏 reward，不等于 coding/review agent 的完成率或查全率 |
| [Adaptive Auto-Harness](https://arxiv.org/abs/2606.01770) | 保存 `(task, reward, trajectory)` 历史，区分 evolution loss 与 adaptation loss，以 Analyze/Research/Build/Verify 演化并按任务路由到专门分支 | 分离全局 harness 改进与当前任务适配；对异构任务采用专门 skill 和 routing | 历史中没有足够信号时不能自动推导可靠修复，仍需人工 contract 或新实验 |
| [TRAJEVAL](https://arxiv.org/abs/2603.24631) | 用 reference patch 对 search/read/edit 分阶段计算 precision/recall；在 16,758 条轨迹上分析效率与成功关系 | 查全率必须拆到阶段；尤其要看 relevant source 有没有被找到和读到 | alternative valid fix 会使单一 reference patch 低估真实覆盖，因此必须声明合法 alternatives |
| [HarnessFix](https://arxiv.org/abs/2606.06324) | 将 raw trace 与 harness artifacts 归一为中间表示，做层级归因、scoped repair 和 held-out regression acceptance | 用 Environment/Tool/Context/Lifecycle/Observability/Verification/Governance 定位责任层；只修最小 artifact | 自动归因仍是候选诊断，必须用因果复现或重复失败验证 |
| [neosigma auto-harness](https://github.com/neosigmaai/auto-harness) | benchmark -> analyze -> improve -> regression gate -> record -> repeat；train trace 可见、test trace 隐藏 | 将 solved task 加入 regression suite；不把 held-out trace 泄露给 optimizer | 项目任务和 grader 仍需本地定义 |
| [agent-eval-harness](https://github.com/plaited/agent-eval-harness) | 用 JSONL 保存 messages、tool calls、commands、timing、failures 和 graders | 采用可重放、可比较的 observable trace schema | 原始消息不应包含 secret，也不需要保存 private chain-of-thought |

> 分析：近期研究没有给出一个适用于所有 agent 的“轨迹总分”。因此本 skill 明确拒绝把完成率、查全率、token 和轨迹 flag 加权成一个不可解释数字。

## 3. 我们的评估合同

### 3.1 任务达成

每个任务先写 deterministic required checks。单次 `strict_success` 要求 `outcome.status=passed` 且全部 required checks 通过。

```text
completion_rate = 通过的 required checks / 全部 required checks
trial_success_rate = 成功 trials / 全部 trials
task_achievement_rate = 至少一次成功的 task IDs / 全部 task IDs
reliable_task_rate = 所有 attempts 都成功的 task IDs / 全部 task IDs
```

`task_achievement_rate` 适合回答“这组任务有没有做成”，`reliable_task_rate` 适合回答“多次运行是否稳定”。随机 agent 至少重复三次，不能用单次偶然成功替代稳定性。

### 3.2 查全率与查准率

对 `search`、`read`、`edit`、`finding` 和 `requirement` 分别声明 gold target：

```text
precision = observed 与 gold 的交集 / observed
recall = observed 与 gold 的交集 / gold
F1 = 2 * precision * recall / (precision + recall)
```

Review 场景中的“查全率”特指 `finding_recall`：已找到的已知有效 finding 数除以 gold finding 数。它和 search recall 不同；找到文件但没有识别行为缺陷，不能算 finding 被覆盖。

Gold 为空时 metric 是 `null`，不是 100%。存在多种合法实现时，必须在评估前声明 alternatives；不能看到 challenger 结果后临时改答案。

> 注释：gold finding 不是要求 agent 复述某个人的评论，而是一个经过代码、测试或维护者结论确认的缺陷/要求集合。尚未证实的猜测不能放进分母。

### 3.3 效率

效率保留原始分母，不压成单一分数：

- wall time、tokens、estimated cost；
- explicit tool calls 与 normalized observable events；
- failed-event rate、repeated events；
- 每次成功的 token、耗时、工具调用；
- 每阶段 unique observed / gold 的 excess ratio。

未采集的 token、耗时、tool call、cost 必须是 `null`。本轮 forward test 专门发现并修复了一个 evaluator bug：没有 tool telemetry 的轨迹此前会显示 `0 tool calls`，现在只有 `resources.tool_calls` 或 explicit `tool` event 才能产生计数。

> 分析：查得更多通常会增加搜索成本。正确问题不是“步骤越少越好”，而是在任务达成和查全不回退的前提下，是否减少了不相关探索、失败重试和每次成功的资源消耗。

### 3.4 轨迹合理性

deterministic scorer 当前检查：

| Flag | 它发现的可观察矛盾 |
| --- | --- |
| `passed_with_incomplete_required_checks` | 声称通过但 required checks 没闭合 |
| `passed_without_verification` | 成功但没有 verify event |
| `edit_without_prior_read` | 修改已有目标前没有观察到阅读 |
| `verification_precedes_last_edit` | 最后修改发生在验证之后 |
| `missing_final_event` / `action_after_final` | 轨迹没有明确结束，或结束后继续动作 |
| `unrecovered_failure` | 失败后没有同目标成功恢复 |
| `repeated_action_loop` | 相同 phase/action/target 超过阈值 |

这些 flag 是 investigation lead，不是语义判决。比如新文件无需先 read，可用 `metadata.new_target=true` 显式说明。

## 4. Harness 责任层

| Layer | 典型信号 | 最小修复方向 |
| --- | --- | --- |
| Environment | binary、network、credential、sandbox state 缺失 | preflight 或 provisioning |
| Tool Interface | 参数错误、exit status 丢失、操作不受支持 | schema、adapter、error propagation |
| Context | search/read/finding recall 低、context 噪音过多 | source routing、retrieval、owning skill rule |
| Lifecycle | retry loop、stop 错误、final 后继续、cleanup 不完整 | retry budget、state transition、terminal condition |
| Observability | 输出/来源丢失、失败无法重放 | normalized event、stable IDs、result capture |
| Verification | 验证缺失/过期、requirement coverage 不完整 | deterministic grader、post-edit rerun、coverage map |
| Governance | 未满足 contract 就结束、越权 mutation | completion gate、allowlist、confirmation gate |

如果多个 layer 同时出现，记录最早能阻止失败的 layer，以及负责检测它的 downstream layer。不能因为最终 verification 报错，就把根因一律归到 verification。

## 5. 用 PR #446 做受控回放

### 5.1 数据边界

本轮没有早期原始 model/seed/budget/environment 与 token/time/tool trace，因此根据 [Day55](day55-pr442-agent-sandbox-v052-new-head-review.md) 的可审计证据重建两个 normalized trajectories：

- [baseline](benchmarks/day57-agent-autoharness/pr446-baseline.jsonl)：我们原先以 fork diff 为入口的 focused residual review；
- [challenger](benchmarks/day57-agent-autoharness/pr446-challenger.jsonl)：从 #438 acceptance contract 重置、覆盖 final head 全 diff 的 Review harness；
- [comparison result](benchmarks/day57-agent-autoharness/pr446-comparison-result.md)：scorer 的 gate 输出。

Gold finding 集合固定为七项：migration lifecycle、dead migration asset、错误 GVK、empty-name validation、lexicographic semver、personal codegen PATH、无因果 immutability test。前六项来自 `@acsoto` 的 final-head Review 并经本地 source/runtime 复核，第七项来自我们的 API Server counterexample。

> 分析：这组 gold 是在两轮 Review 之后重建的，所以适合验证 evaluator 能否表达已知差异，不适合用来训练后再声称对同一任务有泛化提升。

### 5.2 结果

| Metric | Baseline | Challenger | 差值 |
| --- | ---: | ---: | ---: |
| task achievement | 0% | 100% | +100 pp |
| required-check completion | 50% | 100% | +50 pp |
| finding recall（查全率） | 28.6%（2/7） | 100%（7/7） | +71.4 pp |
| search recall | 28.6% | 100% | +71.4 pp |
| read recall | 28.6% | 100% | +71.4 pp |
| requirement recall | 50% | 100% | +50 pp |
| macro recall | 33.9% | 100% | +66.1 pp |
| reasonableness flags | 0 | 0 | 0 |
| normalized events | 8 | 23 | +15 |
| tokens / wall time / tool calls | `n/a` | `n/a` | 不可比较 |

所有可测 outcome/coverage/reasonableness gates 通过，named achievement/reliability regression 均为 0；但默认总结果是 `INCONCLUSIVE`，因为 `comparison_context` 和 token-per-success 没有可比较数据。它证明 parent-contract final-head reset 能覆盖这组已知遗漏，也证明 scorer 能把“做成了多少”“找全了多少”“轨迹有没有明显矛盾”分开报告；它不满足 promotion gate。

它不证明 agent 效率已经提升：challenger 为覆盖完整合同执行了更多 normalized events，而 token/time/tool telemetry 缺失。也不证明任务达成率总体从 0% 提升到 100%；这里只包含一个、每侧一次、事后重建的任务。

## 6. 后续真实优化流程

1. 先建立按任务族分层的 benchmark：PR Review、issue screening、code change、CI triage、research 各自有 task IDs 和 deterministic checks。
2. 固定 train/validation/held-out split；train trace 可用于诊断，held-out trace 不给 harness optimizer。
3. 从下一次 Review 开始直接采集 normalized observable events、model/environment/budget/seed context、token、wall time 和 tool count，不再事后重建。
4. 每个高价值随机任务至少三次 attempts，同时报告 any-pass achievement 与 all-pass reliability。
5. 按 failure cluster 归因到最小 harness artifact，一次只做一个 coherent challenger。
6. 在相同 task IDs、model class、预算和环境上 paired compare；零 named task regression 是默认门槛。
7. 通过后把已修 train failure 加入 regression suite；失败的 repair 也记录原因，避免重复尝试。

> 分析：真正的效率优化必须在“任务达成和查全不下降”的约束下进行。先减少步骤再补任务正确性，会鼓励 agent 提前结束，得到看似便宜但无效的轨迹。

## 7. 产出与验证

- 新 skill：`.agents/skills/agent-autoharness/SKILL.md`
- 评估合同：`.agents/skills/agent-autoharness/references/evaluation-contract.md`
- scorer：`.agents/skills/agent-autoharness/scripts/trajectory_eval.py`
- tests：`.agents/skills/agent-autoharness/scripts/test_trajectory_eval.py`
- AgentCube Review integration：`.agents/skills/agentcube-pr-review/SKILL.md`

已验证：16 个 scorer 单测通过，Python compile 通过，skill structure validation 通过；PR #446 baseline/challenger comparison 的可测 gates 通过，因 comparison context 和效率 telemetry 缺失按预期返回 `INCONCLUSIVE` / exit 1；`git diff --check` 通过。此次没有发布 upstream comment、review、issue、PR、Prow command 或 maintainer mention。
