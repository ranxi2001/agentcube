# Agent AutoHarness Evaluation Contract

## Contents

1. Evidence model
2. Input schema
3. Metric definitions
4. Trajectory reasonableness
5. Harness-layer attribution
6. Regression-gate rules
7. Research basis and limits

## 1. Evidence Model

Keep three objects distinct:

```text
task contract -> observable trajectory -> environment outcome
                         |
                         +-> harness-layer diagnosis
```

An outcome says whether the task succeeded. A trajectory explains what the agent did. A diagnosis proposes why a step failed. Only the first two are direct evidence; the diagnosis needs causal validation before changing the harness.

Do not collect private chain-of-thought. A sufficient event contains:

- monotonic `seq`;
- `phase`: `search`, `read`, `edit`, `finding`, `verify`, `tool`, or `final`;
- observable `action` and stable `target` when applicable;
- `status`: `ok`, `completed`, `failed`, `timed_out`, or `skipped`;
- optional `covers` IDs, duration, token count, tool name, and non-sensitive metadata.

## 2. Input Schema

Required run fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer schema version; current value is `1` |
| `run_id` | Unique trial ID |
| `task_id` | Stable ID shared by baseline and challenger |
| `attempt` | Positive integer trial ID paired across baseline and challenger |
| `outcome.status` | `passed`, `partial`, `failed`, or `blocked` |
| `outcome.checks` | Deterministic task checks with `id`, `required`, and `passed` |
| `events` | Observable trajectory events |

Promotion comparisons also require `comparison_context.model`, `comparison_context.environment`, `comparison_context.budget`, and `comparison_context.seed`. Missing fields make the gate `INCONCLUSIVE`; unequal fields make it `FAIL`.

Optional reference fields:

| Field | Gold set used for |
| --- | --- |
| `search_targets` | File, issue, document, or source localization |
| `read_targets` | Symbol, section, function, or evidence comprehension |
| `edit_targets` | Expected modification locations |
| `finding_targets` | Defects or requirements the agent should identify |
| `requirement_targets` | Acceptance items that verification evidence must cover |
| `alternatives` | Explicit alternative valid reference sets |

Alternative target sets are allowed only when independently known to be valid. The scorer selects the best declared variant and reports its index.

JSON arrays, one JSON object, `{"runs": [...]}`, and JSONL are accepted.

## 3. Metric Definitions

### Outcome

For required check set G and passed required checks P:

```text
completion_rate = |P| / |G|
strict_success = outcome.status == passed AND completion_rate == 1
trial_success_rate = successful trials / all trials
task_achievement_rate = task IDs with at least one successful trial / all task IDs
reliable_task_rate = task IDs whose every trial succeeds / all task IDs
```

When no required checks exist, `passed` maps to completion 1, `partial` to 0.5, and other statuses to 0.

### Phase precision and recall

For observed unique targets O and declared gold targets G:

```text
precision = |O intersect G| / |O|
recall = |O intersect G| / |G|
F1 = 2 * precision * recall / (precision + recall)
```

Return `null` when G is absent. If G exists but O is empty, precision and recall are 0. Duplicates do not increase coverage, but they do affect repetition and efficiency counters.

Interpretation:

- low search recall: relevant source was never localized;
- high search recall, low read recall: source was found but the necessary symbol/evidence was not examined;
- high read recall, low edit recall: the agent understood context but changed the wrong or incomplete location;
- high finding recall, low precision: broad review found the expected defects but produced excessive unsupported candidates;
- high precision, low recall: efficient but incomplete investigation;
- low precision, high recall: exhaustive but expensive investigation.

`macro_recall` averages only declared phase/reference metrics. It must not turn missing gold data into a perfect score.

### Requirement coverage

Requirement recall uses IDs in `verify` events' `covers` arrays or verify targets. It measures whether trajectory evidence closed the acceptance contract, independently from an outcome grader's final result.

### Efficiency

Always report raw denominators:

- total and mean wall time;
- total and mean tokens;
- tool/event count;
- failed-event rate;
- repeated-event count;
- tokens, wall time, and tool calls per strict success;
- phase excess ratio `unique observed targets / gold targets` when gold exists.

Keep unmeasured token, duration, tool-call, and cost fields as `null`; never convert missing telemetry to zero. A tool-call count may be derived from explicit `tool` events, but not from generic search/read/edit events. Compute per-success resource metrics only over successful trials that contain that measurement, and report the measured-trial count.

Do not combine these into one unexplained efficiency score. Compare a challenger using paired task outcomes and per-success resource cost.

## 4. Trajectory Reasonableness

The deterministic scorer emits leads, not semantic proof:

| Flag | Meaning |
| --- | --- |
| `passed_with_incomplete_required_checks` | Final status contradicts required checks |
| `passed_without_verification` | Success is claimed without a verify event |
| `edit_without_prior_read` | Existing target edited before observable inspection |
| `verification_precedes_last_edit` | Evidence is stale relative to the final edit |
| `missing_final_event` | Trace ended without an observable finalization event |
| `action_after_final` | Work continued after finalization |
| `unrecovered_failure` | Failed action has no later successful retry for the same target |
| `repeated_action_loop` | Same phase/action/target exceeds the repetition threshold |

Allow `metadata.new_target=true` for intentionally created files. A flag must be checked against task semantics before becoming a harness flaw.

## 5. Harness-Layer Attribution

Use the ETCLOVG-style ownership map:

| Layer | Typical evidence | Scoped repair examples |
| --- | --- | --- |
| Environment | missing binary, network, credential, sandbox state | environment preflight, dependency provisioning |
| Tool Interface | malformed arguments, hidden exit status, unsupported operation | schema, adapter, error propagation |
| Context | low search/read recall, irrelevant context overload | source routing, retrieval, concise skill rule |
| Lifecycle | loops, bad retry/stop, stale state, incomplete cleanup | retry budget, state transition, stop condition |
| Observability | missing command output, no provenance, failure cannot be replayed | normalized events, result capture, stable IDs |
| Verification | stale or absent validation, grader mismatch | deterministic check, post-edit rerun, coverage map |
| Governance | premature completion, forbidden mutation, permission bypass | completion gate, allowlist, confirmation gate |

If evidence implicates multiple layers, name the earliest layer that can prevent the failure and the downstream layer that detects it.

## 6. Regression-Gate Rules

Use the same task IDs and equivalent model/environment budgets. Default acceptance requires:

- identical `(task_id, attempt)` sets and comparison context on both sides;
- zero task-level regressions;
- non-negative task-achievement delta;
- non-negative required-check completion delta;
- non-negative macro-recall delta when both sides have gold labels;
- no increase in reasonableness-flag rate;
- no more than 10% increase in tokens per strict success when both sides have successes.

If a configured gate lacks comparable measurements, the default result is `INCONCLUSIVE` and the CLI exits non-zero. `--allow-unmeasured-gates` is only for exploratory diagnostics; it produces `PASS_WITH_UNMEASURED` and must never be used to promote a harness change.

Adjust a threshold only before seeing challenger results or with an explicit product trade-off. Never hide a named regression behind a mean improvement.

Use at least three attempts for stochastic high-value tasks when practical. Report both any-pass task achievement and all-pass reliable task rate.

## 7. Research Basis and Limits

- [AutoHarness](https://arxiv.org/abs/2603.03329) treats harness synthesis as program search: an LLM mutates code, environment feedback acts as critic, and Thompson sampling balances exploration and exploitation. Its direct metric is legal-action accuracy/reward, not general coding-agent trajectory quality.
- [Adaptive Auto-Harness](https://arxiv.org/abs/2606.01770) stores `(task, reward, trajectory)` history, separates evolution loss from task-adaptation loss, evolves through Analyze/Research/Build/Verify roles, and routes tasks to specialized harness branches.
- [TRAJEVAL](https://arxiv.org/abs/2603.24631) motivates separate search/read/edit precision and recall. Its reported reference-patch metrics are most reliable when canonical fix locations exist; explicit alternatives are required for valid divergent solutions.
- [HarnessFix](https://arxiv.org/abs/2606.06324) motivates normalized trace evidence, harness-layer attribution, scoped repair operators, and held-out regression-aware acceptance.
- [agent-eval-harness](https://github.com/plaited/agent-eval-harness) provides a useful observable JSONL pattern for messages, tool calls, commands, timing, failures, graders, and baseline/challenger comparison.
- [auto-harness](https://github.com/neosigmaai/auto-harness) demonstrates the operational loop `benchmark -> analyze -> improve -> regression suite -> full validation -> promote fixed cases`, with train traces visible and test traces hidden from the optimizer.

These sources do not establish one universal trajectory score. This skill deliberately preserves separate outcome, coverage, resource, and reasonableness metrics.

The scorer consumes check results produced by external deterministic graders; it does not execute those graders or prove the semantic validity of their booleans and target IDs. Store grader ID/version and evidence provenance with the benchmark, and audit them before treating a gate as release evidence.
