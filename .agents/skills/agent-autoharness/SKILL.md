---
name: agent-autoharness
description: Evaluate and improve coding, review, research, and tool-using agent harnesses from observable execution trajectories. Use when Codex needs to design an agent eval dataset, normalize JSON/JSONL traces, measure task achievement, search/read/edit/finding precision and recall, assess tool/token/time efficiency, audit trajectory reasonableness, compare a baseline with a challenger, attribute failures to harness layers, or accept/reject a prompt, skill, tool, memory, workflow, or verification change through a held-out regression gate.
---

# Agent AutoHarness

Treat harness optimization as release engineering over observable trajectories. Keep outcome correctness, coverage, efficiency, and trajectory quality separate so one metric cannot hide another.

## Boundaries

- Evaluate observable messages, tool calls, commands, file/symbol targets, validation evidence, outcomes, duration, and token counts. Do not require or store hidden chain-of-thought.
- Prefer deterministic environment checks over an LLM judge for task completion. Use an LLM judge only for criteria that cannot be made executable, and keep its result as a separate grader.
- Separate agent failure from harness failure. A failed run is evidence for diagnosis, not proof that the prompt, skill, or tool layer caused it.
- Never optimize on held-out test traces. Use train failures for diagnosis, validation tasks for patch acceptance, and held-out tasks for final reporting.
- Never accept a harness change from aggregate score alone. Reject unexplained task regressions and retain per-task evidence.
- Do not grow one global skill after every failure. Route stable domain-specific knowledge to the owning skill; promote only repeated, causally supported patterns.

## Required Reference

Read [references/evaluation-contract.md](references/evaluation-contract.md) before defining a dataset, interpreting a null metric, or changing gate thresholds.

## Workflow

### 1. Freeze the evaluation contract

Define before running an agent:

- stable task IDs and train/validation/held-out split;
- required outcome checks and the deterministic grader for each check;
- optional reference targets for `search`, `read`, `edit`, `finding`, and `requirement` coverage;
- budget fields: wall time, tokens, tool calls, and cost when available;
- repeated attempts `k`, random seeds, model, harness version, and environment version.

For review tasks, version the finding gold set and record provenance. Build it from the parent acceptance contract, validated findings on predecessor/replacement PRs, local evidence ledgers, and independently confirmed current-head findings. Merge repeated comments that test the same acceptance invariant into one stable finding ID; keep distinct regressions introduced by attempted fixes separate. A required check such as `cover-all-known-findings` needs a deterministic set comparison between frozen gold IDs and observed finding IDs; do not accept a trajectory-provided boolean as proof of completeness. If later evidence proves the gold set was incomplete, preserve the original artifact, publish a corrected version, and invalidate the old recall/completion claim instead of silently rewriting history.

Use explicit alternative reference target sets for known valid alternate solutions. Do not retroactively rewrite gold targets merely to make one run look better.

### 2. Capture a normalized trajectory

Write one run per JSON object. Capture only task-relevant normalized events:

```json
{
  "schema_version": 1,
  "run_id": "review-446-baseline-1",
  "task_id": "agentcube-pr-446",
  "attempt": 1,
  "comparison_context": {
    "model": "gpt-example",
    "environment": "agentcube-main@abc123",
    "budget": {"max_tokens": 20000, "max_wall_time_ms": 900000},
    "seed": 17
  },
  "outcome": {
    "status": "partial",
    "checks": [
      {
        "id": "all-blocking-findings",
        "required": true,
        "grader": {
          "kind": "reference-coverage",
          "phase": "finding",
          "minimum_recall": 1.0
        }
      }
    ]
  },
  "reference": {
    "search_targets": ["issue:438", "cmd/workload-manager/main_test.go"],
    "read_targets": ["cmd/workload-manager/main_test.go#TestSchemeRegistration"],
    "finding_targets": ["broken-gvk", "missing-migration-e2e"],
    "requirement_targets": ["upgrade-existing-sandboxclaims"]
  },
  "events": [
    {"seq": 1, "phase": "search", "action": "read", "target": "issue:438", "status": "ok"},
    {"seq": 2, "phase": "read", "action": "inspect", "target": "cmd/workload-manager/main_test.go#TestSchemeRegistration", "status": "ok"},
    {"seq": 3, "phase": "finding", "action": "report", "target": "broken-gvk", "status": "ok"},
    {"seq": 4, "phase": "verify", "action": "test", "target": "broken-gvk", "covers": ["broken-gvk"], "status": "ok"},
    {"seq": 5, "phase": "final", "action": "respond", "status": "ok"}
  ],
  "resources": {"wall_time_ms": 120000, "input_tokens": 8000, "output_tokens": 1200}
}
```

Redact secrets before capture. Store hashes or stable target IDs instead of raw sensitive tool output.

### 3. Score runs

Run:

```bash
python3 /home/agentcube/.agents/skills/agent-autoharness/scripts/trajectory_eval.py \
  score --input /path/to/runs.jsonl --format markdown
```

Inspect all four result groups:

- **Outcome:** strict success, required-check completion, trial success, task achievement, and reliable task rate.
- **Coverage:** phase precision/recall/F1 plus requirement coverage. For review tasks, `finding_recall` is the explicit查全率.
- **Efficiency:** wall time, tokens, tool calls, failed/repeated events, excess exploration, and cost per strict success.
- **Reasonableness:** deterministic flags such as edit-before-read, stale verification, unverified completion, unrecovered failure, or repeated loops.

Treat missing reference targets as `null`, not as perfect precision/recall.

For checks that mean “cover the frozen reference set,” use the built-in `reference-coverage` grader for `search`, `read`, `edit`, `finding`, or `requirement`. The scorer derives `passed` from the selected reference variant and requested minimum recall. If a trace also supplies `passed` and it disagrees, the derived result wins and the scorer emits `declared_check_disagrees_with_grader`.

### 4. Attribute before repairing

Use the emitted repair candidates as prompts for investigation, not automatic findings. Trace the evidence to one or more harness layers:

```text
Environment -> Tool Interface -> Context -> Lifecycle
            -> Observability -> Verification -> Governance
```

Identify the smallest responsible artifact: prompt paragraph, skill rule, script, tool adapter, context selector, retry/stop policy, trace field, grader, or permission gate. Require a causal reproduction or repeated failure cluster before editing it.

### 5. Build one scoped challenger

Change one coherent harness mechanism. Record:

- target failure cluster and implicated layer;
- expected metric movement and allowed trade-off;
- files/artifacts allowed to change;
- validation tasks that should improve;
- solved tasks that must not regress;
- stop condition and rollback path.

For heterogeneous task families, prefer separate skill/harness branches plus routing over one dense universal prompt.

### 6. Compare and gate

Run paired evaluation on the same task IDs, attempts, model class, budgets, and environment:

```bash
python3 /home/agentcube/.agents/skills/agent-autoharness/scripts/trajectory_eval.py \
  compare --baseline /path/to/baseline.jsonl \
  --challenger /path/to/challenger.jsonl \
  --max-task-regressions 0 \
  --min-task-achievement-delta 0 \
  --min-completion-delta 0 \
  --min-macro-recall-delta 0 \
  --max-reasonableness-flag-rate-delta 0 \
  --max-token-per-success-increase-ratio 0.10 \
  --format markdown
```

The command exits non-zero when the gate fails or a configured gate is unmeasured. Use `--allow-unmeasured-gates` only for exploratory diagnostics; `PASS_WITH_UNMEASURED` is not promotion evidence. Review named achievement and reliability regressions even when aggregate metrics improve. Repeat stochastic tasks enough times to distinguish a harness effect from sampling noise.

### 7. Promote evidence, not anecdotes

After acceptance:

- add fixed train failures to the regression suite;
- record baseline/challenger versions and exact metric deltas;
- write a concise flaw record: trigger, responsible step, harness layer, repair, validation, regressions, applicability limits;
- update an existing owning skill only when the lesson is stable and reusable;
- keep rejected repairs and their failure reason so they are not retried blindly.

## Integration

- Use `agentcube-pr-review` to produce technical findings and exact review coverage; use this skill to evaluate the review agent across a labeled PR set.
- Import the exact-head finding ledger from `agentcube-pr-review` into `reference.finding_targets`; keep all heads and replacement PRs from one issue lineage in the same dataset split to prevent later-review leakage.
- Use `agentcube-pr-management` for any upstream action. This skill never authorizes comments, PRs, reviewer requests, or branch mutation.
- Use benchmark-native deterministic graders whenever available; normalize their results into this skill's run contract rather than replacing them.

## Output Contract

Report in this order:

1. gate outcome and named task regressions;
2. task achievement and completion;
3. phase/finding/requirement recall and precision;
4. token/time/tool efficiency;
5. trajectory flags and harness-layer diagnoses;
6. scoped repair or explicit no-change decision;
7. dataset, grader, repetition, and environment limits.
