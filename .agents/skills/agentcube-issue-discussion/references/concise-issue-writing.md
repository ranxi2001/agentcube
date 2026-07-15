# Concise AgentCube Issue And Comment Writing

Use this reference for AgentCube issues, comments, and review summaries. Select the artifact type before drafting; benchmark/proposal evidence should not force ordinary comments into the same long format.

## Local Evidence Snapshot

On 2026-07-14, the 20 most recent AgentCube issues with non-empty bodies had a median of 192 reviewer-visible words after hidden HTML comments were removed. The 61-771 word range reflects small bugs at one end and architecture/CI discussions at the other.

## Soft Budgets

- Enhancement or question: aim for 80-250 visible words.
- Observed or source-proven reachable bug: aim for 120-400 visible words before irreducible logs/manifests.
- Ordinary issue/PR comment: aim for 40-180 visible words; review again above 250.
- Proposal, benchmark, API/CRD, security, or cross-component review: longer text is allowed when the result remains scan-first and each environment/contract field changes the decision.

Above 400 words for an ordinary issue or 250 for an ordinary comment, perform a compression pass and name the long-form reason.

## Evidence-To-Work Shape

Public Karmada/AgentCube samples from `@zhzhuang-zju` show a useful progression that is stronger than merely filling a template:

1. Anchor the observation with one runnable symptom, CI run, metric, or immutable code link.
2. Trace only the ownership/data path needed to explain the impact; label root cause as confirmed or hypothesized.
3. State the bounded expected contract or exact maintainer decision.
4. For umbrella work, turn the body into a live ledger: one independently reviewable task per checkbox, with owner/PR/outcome updated in place.
5. Put implementation detail in a follow-up comment when it is still being negotiated; split deferred lifecycle behavior into a separate issue instead of hiding it in the initial fix.

Do not copy the weaknesses in the corpus: empty environment fields, a preselected implementation presented before the contract is agreed, stale checklists, or links without relevance notes. Repository templates explain some headings; they are not evidence that the author intentionally chose that structure.

## Type-Specific Shapes

### Enhancement Or Question

Use the repository template. State one concrete capability/question, first-phase boundary, user impact, and the exact maintainer decision needed. Keep alternatives to two or three real choices.

### Bug

Use `What happened -> Expected -> Minimal reproduction -> Decisive evidence -> Relevant environment`. For controller/data-path bugs, add the shortest causal chain from source state to user-visible failure. Label an unproven cause as a hypothesis and keep the issue valid even if the proposed fix changes.

Classify the evidence before drafting. For an observed bug, name the log, CI, or realistic end-to-end occurrence. For a reachable latent bug, name the production producer, supported preconditions, permitted trigger, persistent consequence, and explicitly state that no occurrence was observed. A fault-injected test alone is not production evidence; if no real producer or reachable state is proven, use a question or test-hardening request instead of the bug template.

### Proposal

Use `references/proposal-review.md`. Put the conclusion or open design decision first; keep full architecture and state-machine detail in the proposal or local report.

### Benchmark

Keep environment and method fields that affect comparability. Publish a compact result/limitation/next-step summary and link raw artifacts instead of pasting them.

### Comment Or Review

```md
I verified <scenario> at `<sha>`.

- Observation: <result>
- Evidence: <test, log, code path, or benchmark case>
- Impact: <bounded behavior>

Suggested next step: <one action or question>.
```

## Remove By Default

- A recap of the entire thread or proposal.
- Every failed command or intermediate hypothesis.
- Full raw logs/JSON when one decisive excerpt plus a stable link is sufficient.
- Bot/AI conclusions, contributor biographies, or broad implementation promises.
- Multiple links without one-line relevance notes.

Measure visible size with:

```bash
python3 .agents/skills/agentcube-issue-discussion/scripts/draft_metrics.py <draft.md> --limit 250
```
