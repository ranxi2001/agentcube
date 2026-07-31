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

已验证：当前 18 个 scorer 单测通过，Python compile 通过，skill structure validation 通过；PR #446 baseline/challenger comparison 的可测 gates 通过，因 comparison context 和效率 telemetry 缺失按预期返回 `INCONCLUSIVE` / exit 1；`git diff --check` 通过。此次没有发布 upstream comment、review、issue、PR、Prow command 或 maintainer mention。

## 8. 后续证据对七项 gold 的修正

`2026-07-31` 的 #446 后续 review 证明，本节 5.1 的七项 gold 不完整。Day55 在 predecessor PR #442 上早已记录 `migration backup` 缺 SandboxTemplate/SandboxWarmPool、exported `Resource()` 从 `GroupVersionResource` 改为 `GroupResource` 的 source break，以及 Kubernetes v0.36.2 / code-generator v0.35.4 skew；replacement #446 `449fb75` 仍保留三项，但它们没有进入 baseline/challenger reference targets。`@acsoto` 后来在 #446 独立指出三项，构成新的 verified evidence。

不回写原 JSONL 伪装成预先冻结的 gold。保留原结果作为“七项不完整 gold 下 scorer 的行为”，另记录 corrected version：finding target 至少由 7 项增至 10 项，challenger observable findings 仍为 7，因此 corrected lower-bound recall 是 `7/10 = 70%`，不是 100%。`cover-all-known-findings=true` 也不成立，因为它来自 trajectory 输入，没有 deterministic grader 对 frozen gold IDs 做集合闭合。

这次 failure attribution 是：最早可阻止问题的 **Context** layer 没有传入 predecessor finding ledger；**Verification** layer 没有验证 gold completeness 和 finding-set closure；**Governance** layer 允许在部分 ledger rows 未关闭时结束。它不提供效率比较证据，manifest URL 与 fixture 的两条后续评论又来自 review 后新增代码，不能回算到旧 head recall。

已把修正规则加入 `agentcube-pr-review` 与 `agent-autoharness`：replacement PR 必须继承未关闭 finding ledger；review gold 需要版本和 provenance；`cover-all-known-findings` 必须由 deterministic set comparison 产生。原 benchmark 继续保持 `INCONCLUSIVE`，并进一步标记为 incomplete-gold evidence，不能用于 promotion。

## 9. #446 全 lineage 复盘与 executable skill 修正

### 9.1 先恢复 review round 的时间事实

`2026-07-31 17:44 CST` 再次只读刷新 #446。作者把此前 `1826e16` 的 16 个 commits squash 成一个 signed commit `e577a5ea1c76c1f72710bf7345c9b215151da868`，base 仍为 `0704bb9`。两个 head 的 tree OID 都是 `a91ae18`，因此代码行为没有随 squash 改变；DCO 已恢复通过，全部 executable checks 已通过，Tide 只等待 `lgtm/approved`。

GitHub 当前 commits endpoint 只剩 squash 后的一个 commit，不能再用它重建旧轮次。公开 PushEvent、review submission、review comment 的 `original_commit_id`、`in_reply_to_id` 和本地 exact-head 记录共同恢复出以下主要 heads：

```text
822dc7b -> 83002f1 -> 2eefda6 -> fd0507f -> 449fb75
         -> f35e458 -> 275f2e4 -> 1826e16 -> e577a5e
```

> 分析：REST 返回的 `comment.commit_id` 不是不可变审计字段。force-push/squash 后，只要评论还能映射到新 diff，GitHub 会把它改写成 current head；thread reply 又可能继承 root comment 的 `original_commit_id`。所以精确归因必须同时保存 comment/review ID、`original_commit_id`、reply parent、timestamp 和发布时 PR head。

### 9.2 不按评论条数数 bug

本轮把 #438 -> #442 -> #446 的技术问题合并成 15 个 stable finding IDs，另有一个 MCP/#448 ancestry/scope process item，不计入技术 finding recall。完整 ledger 位于 [pr446-lineage-finding-ledger-v3.json](benchmarks/day57-agent-autoharness/pr446-lineage-finding-ledger-v3.json)，current-head closure 位于 [pr446-e577a5e-finding-closure-v3.json](benchmarks/day57-agent-autoharness/pr446-e577a5e-finding-closure-v3.json)。

最重要的归并是 existing-claim upgrade lifecycle：

- #438 要求 existing claim migration、adoption、deletion 和 refill；
- 后续评论依次指出 no post-upgrade assertions、cold fixture 不具备 bound identity、对象图不完整、Claim 未达到 Ready；
- 这些都是同一个 acceptance invariant 的逐轮 closure 失败，不是四个独立 bug。

相反，自制 migration patch 同时“漏建 shadow pool”和“失败 apply 后全局删除 claim”，两者触发与后果不同，保留为两个 findings。

> 注释：stable finding ID 的目标不是减少数字，而是让“新 defect”和“旧 defect 没修完整”使用不同指标。前者影响新-head regression rate，后者影响 closure rate；混在一起会虚高 bug count，也会错误训练 skill。

### 9.3 公平的 finding 指标

对我们明确声明为 final-head review 的 `449fb75`，same-head lower-bound gold 是 6 项：migration helper mirror、existing-claim lifecycle、Router h2c scope、backup coverage、exported `Resource()` signature、Kubernetes/code-generator skew。我们发布了前三项，后三项在同一 head 已存在但漏报，因此：

| Metric | Result | 边界 |
| --- | ---: | --- |
| finding recall | `3/6 = 50%` | lower bound；只计 `449fb75` 已存在的 findings |
| observed precision | `3/3 = 100%` | 三条发布 finding 均经后续代码/维护者反馈确认 |
| later manifest 404 | 不计旧 recall | `2592301` 在 review 后引入 |
| 两条后续 fixture 评论 | 不新增 gold ID | 都是 existing-claim lifecycle 的 closure follow-up |

对 `2eefda6` 的旧 post-hoc challenger，version-2 gold 从 7 项修正为 10 项。新 artifact [pr446-finding-closure-correction-v2.json](benchmarks/day57-agent-autoharness/pr446-finding-closure-correction-v2.json) 保留轨迹原先自报的 `cover-all-known-findings=true`，但使用 built-in `reference-coverage` grader 重新计算后得到：finding recall `7/10 = 70%`、required-check completion `0%`、strict success `false`，并产生 `declared_check_disagrees_with_grader`。这次不再依赖人工在报告里推翻 scorer 的错误 pass。

当前 `e577a5e` 不应计算新的 review recall，因为两个未关闭项都已在此前 maintainer comments 中公开；这只是 closure replay，不是独立 blind review。current stable technical ledger 为 `13/15 fixed`，仍有：

1. `F09-existing-claim-upgrade-lifecycle`：E2E 仍用固定 sleep，successful log 中 `upgrade-bound-claim` 的 `READY` 为空，且没有证明 migrated claim deletion 与 pool refill；
2. `F16-kubernetes-codegen-version`：`go.mod` 的 `k8s.io/api`、`apimachinery`、`client-go` 是 `v0.36.2`，`hack/update-codegen.sh` 仍 pin `code-generator v0.35.4`。

### 9.4 为什么维护者的查全率更高

经验的实际作用可以拆成可复用 review operators，而不是抽象地说“他更熟”：

| Operator | #446 直接收益 |
| --- | --- |
| 每个 final head 从 parent Issue 重建 acceptance matrix | existing-claim upgrade 不能降级成 residual limitation |
| predecessor/replacement finding union | backup、`Resource()`、codegen 三项不丢失 |
| 每个 hand-written file 都要 rationale/contract/evidence | codegen、Router scope、自制 migration 进入审查面 |
| changed test package -> CI command mapping | 发现 green CI 没运行错误的 manager scheme assertions |
| baseline boundary diff | empty-name validation、h2c default、exported signature |
| 外部 URL 与 mirrored docs 执行检查 | 三轮 migration helper/manifest URL 闭环 |
| 构造边界反例 | `v0.10.0` 揭示字典序比较 |
| lifecycle state matrix | cold/bound、ownerRef、Sandbox/Pod UID、Ready、delete、refill 不再混成“资源存在” |
| dependency-family coherence | green codegen 不能掩盖 v0.36/v0.35 skew |
| author `done` 后继续按 current artifact 验证 | 不把 commit subject、resolved thread 或 green check name 当 closure |

我们的主要问题不是发现能力完全不足，而是 stop condition 太早：找到三条 blocker 后就发布，未要求所有 carry-forward rows 分类；同时比较 fork adapter 让注意力锚定在“我们的实现与他的差异”，没有重新审计 #446 每个额外 hand-written file。维护者的优势体现为覆盖顺序与 closure discipline 更稳定。

### 9.5 本轮 skill/harness 修改

| Artifact | Executable change | 防止的 #446 失误 |
| --- | --- | --- |
| `final_head_review.py` | 新增 `--finding-ledger` / `--finding-closure`，绑定 ledger ID/version/content digest、current PR 与 exact head；缺项或 mismatch 时 exit non-zero | predecessor finding 静默丢失或旧 closure 错配新 gold |
| `final_head_review.py` | base/head exported Go function signature leads | 仓内 regenerated callers 通过却破坏外部 source contract |
| `final_head_review.py` | Kubernetes libraries 与 code-generator minor alignment lead | green codegen 只证明旧 generator 可重复 |
| `pr_status.py` | preview 从最早 20 条改为最新 20 条；输出 exact base/head、comment/review/reply/head provenance；`0` 可取全部 | freshness scan 截掉最新 maintainer feedback，或被 rewritten `commit_id` 误导 |
| `trajectory_eval.py` | `reference-coverage` derived checks 覆盖 finding/search/read/edit/requirement | 轨迹自报 `cover-all-known-findings=true` |
| Review skill/reference | 固定 same-head miss、new-head regression、same-finding follow-up、distinct finding 四类 | raw comment count 被当成 recall |

finding closure harness 已在 current `e577a5e` 上读取 15 项 ledger，得到 `13 fixed / 2 present / 0 unclassified`。结构 closure 为 `complete`，但独立的 finding-readiness gate 为 `blocked` 并 exit 1；机器接口不再把“分类完了”混成“PR ready”。`present` findings 必须解决，或由 maintainer 明确接受并以 `accepted-by-maintainer` + decision evidence 关闭。

### 9.6 数据集边界

#446 已经看过所有后续 comments 和 patches，不能再拆成 train/validation/held-out 来证明泛化。整个 `#438 -> #442 -> #446` lineage 只进入 train/regression；同一 issue 的 replacement PR、force-pushed heads 和 fix patches 必须放在同一 split，避免未来评论泄漏到“held-out”。

真正的 validation 要选择另一条未用于本轮 skill 调整的 frozen AgentCube PR lineage，只暴露 cutoff 前的 issue、base/head、diff 和 checks；held-out 则保留未来 PR 的后续 pushes 与 maintainer findings，直到 agent 输出后再揭示。当前仍缺原始 token/time/tool telemetry，所以本轮能证明查全和轨迹 gate 修正，不能证明效率已经提高。

本节只修改 `intern` 分支上的 skills、harness、tests 和学习记录，没有向 #446 发布 comment/review、resolve thread、`/lgtm`、`/approve`、Prow command 或 maintainer mention。

### 9.7 前向回放同时审查 harness 自身

在不提供本节人工结论的情况下，让独立 reviewer 使用修改后的 skills 重放 current `e577a5e`。它只留下与 ledger 一致的两项 current findings：existing-claim lifecycle 和 Kubernetes/code-generator skew；其余 13 项均有 fixed evidence，0 项未分类。在全新 clean detached worktree 上，`final_head_review.py --run-go-tests --check-urls` 把结构 closure 判为 complete，同时因两项 present 将 finding readiness 判为 blocked / exit 1；direct `go test ./cmd/workload-manager -count=1` 通过，四个 literal URLs 返回 200，含变量的 URL 只标记为 unresolved，没有伪装成已验证。

这次回放也找到一个 harness 自身的 false positive：`review_surface.py` 只读取 `run_e2e.sh` 的 `MTLS_ENABLED=true` 默认值和 workflow 的 literal env override，因此声称 warm-pool E2E 默认被 skip。实际 `.github/workflows/e2e.yml` 通过 `matrix.mtls_enabled` 同时提供 `true` / `false`，`codeinterpreter-e2e-test` 使用 `false`，当前 CI 日志中的 `TestCodeInterpreterWarmPool` 与 load test 都实际执行并通过。

修复后，coverage lead 会把 job-level / step-level env 绑定到实际执行 E2E 的 step，再沿该 job 的 `MTLS_ENABLED -> matrix.<key> -> <key>: false` 解析 disabled path；回归测试覆盖 direct env、inline shell assignment、matrix include/block list/exclude、跨 job 同名字段、同 job 不同步骤 env 泄漏，以及没有 E2E command 的 false env 反例。closure gate 还覆盖空 ledger、orphan closure、ledger version/content mismatch、schema/status 类型错误，以及“分类 complete 但 present/duplicate 仍阻塞 readiness”；decision 型 status 必须提供 current-PR comment URL，maintainer acceptance 还需 `OWNER/MEMBER/COLLABORATOR` association。调用者必须在 versioned ledger 与显式 `--no-carry-forward-findings` 之间二选一；输出将后者记为 `none-declared` / `not-applicable`，而真正漏传仍是 `not-provided` / `not-assessed` 并失败。`--run-go-tests` 会拒绝 tracked/untracked dirty worktree。PR Review scripts 共 40 个单测通过。

对应 skill 的 false-positive guard 现在明确要求：不能从 shell 默认值或别的 job/step 单独推导 workflow 有效值，必须核对 target execution 的 matrix/env dataflow 与 PASS/SKIP 日志。digest 和 decision association 是 structural evidence，不替代 reviewer 对 live comment、author role 和 finding 语义的复核。

> 调试记录：验证时直接执行 `python3 -m unittest .agents/.../test_review_surface.py` 报 `ValueError: Empty module name`，原因是 `unittest` 把以 `.agents` 开头的文件路径当作模块名。改用既有的 `python3 -m unittest discover -s ... -p 'test_review_surface.py'` 后目标用例通过；这不是 harness 行为失败。

> 分析：这证明前向回放不仅要问“新 skill 找到了什么”，还要问“新 skill 发出了哪些错误 leads”。但 #446 lineage 已被完整观察，这仍是 train/regression 自审，不是 held-out promotion evidence；任务达成率、跨任务查全率和效率提升仍需独立 frozen PR 样本验证。
