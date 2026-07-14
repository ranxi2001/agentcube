# Concise AgentCube Issue And Comment Writing

Use this reference for AgentCube issues, comments, and review summaries. Select the artifact type before drafting; benchmark/proposal evidence should not force ordinary comments into the same long format.

## Local Evidence Snapshot

On 2026-07-14, the 20 most recent AgentCube issues with non-empty bodies had a median of 192 reviewer-visible words after hidden HTML comments were removed. The 61-771 word range reflects small bugs at one end and architecture/CI discussions at the other.

## Soft Budgets

- Enhancement or question: aim for 80-250 visible words.
- Reproducible bug: aim for 120-400 visible words before irreducible logs/manifests.
- Ordinary issue/PR comment: aim for 40-180 visible words; review again above 250.
- Proposal, benchmark, API/CRD, security, or cross-component review: longer text is allowed when the result remains scan-first and each environment/contract field changes the decision.

Above 400 words for an ordinary issue or 250 for an ordinary comment, perform a compression pass and name the long-form reason.

## Type-Specific Shapes

### Enhancement Or Question

Use the repository template. State one concrete capability/question, first-phase boundary, user impact, and the exact maintainer decision needed. Keep alternatives to two or three real choices.

### Bug

Use `What happened -> Expected -> Minimal reproduction -> Decisive evidence -> Relevant environment`. Label an unproven cause as a hypothesis.

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
