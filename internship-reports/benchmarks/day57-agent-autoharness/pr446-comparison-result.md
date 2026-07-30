# Agent AutoHarness Comparison

- Gate: `INCONCLUSIVE`
- Common tasks: `1`
- Improvements: `agentcube-pr-446-final-head-review`
- Reliability improvements: `agentcube-pr-446-final-head-review`
- Regressions: `none`
- Reliability regressions: `none`
- Unmeasured gates: `comparison_context, tokens_per_strict_success`

## Metrics

| Metric | Baseline | Challenger | Delta |
| --- | --- | --- | --- |
| task achievement | 0.0% | 100.0% | 100.0% |
| trial success | 0.0% | 100.0% | 100.0% |
| reliable task rate | 0.0% | 100.0% | 100.0% |
| completion | 50.0% | 100.0% | 50.0% |
| finding recall | 28.6% | 100.0% | 71.4% |
| requirement recall | 50.0% | 100.0% | 50.0% |
| macro recall | 33.9% | 100.0% | 66.1% |
| reasonableness flags per trial | 0.0000 | 0.0000 | 0.0000 |
| tokens per success | n/a | n/a | n/a |
| wall time per success (ms) | n/a | n/a | n/a |
| tool calls per success | n/a | n/a | n/a |
| observable events per success | n/a | 23.0000 | n/a |
| failed event rate | 0.0% | 0.0% | 0.0% |

## Gate Evidence

- All measurable configured regression gates passed.
- INCONCLUSIVE: no comparable measurement for comparison_context, tokens_per_strict_success.
- WARNING: missing comparison context for: agentcube-pr-446-final-head-review@1 (model, environment, budget, seed)
