# Concise AgentCube PR Writing

Use this reference when drafting or shortening an AgentCube PR body. Keep the detailed code rationale, benchmark record, and investigation history local; make the upstream body a reviewer index.

## Local Evidence Snapshot

On 2026-07-14, the 26 most recent non-bot AgentCube PRs with non-empty bodies had a median of 211.5 reviewer-visible words and 22 nonblank lines after hidden HTML comments were removed. The range was 87-503 words. This supports a one-screen default while leaving room for API, proposal, CI, and compatibility changes.

## Soft Budgets

- Ordinary code, test, cleanup, or docs PR: aim for 100-300 visible words and at most 35 nonblank lines.
- API/CRD, compatibility, security, benchmark, or multi-component PR: aim for 200-450 visible words and at most 55 nonblank lines.
- Above 450 words: perform another compression pass and state why the remaining detail must be in the body.

These are review triggers, not hard correctness limits. Do not remove an upgrade contract, security boundary, benchmark environment fact, or material residual risk merely to hit a number.

## Keep

1. One short problem/behavior summary.
2. The exact `Fixes #N` or `Refs #N` relationship.
3. At most three decision-relevant reviewer notes: scope/compatibility, validation, and a material limit or risk.
4. One-sentence AI disclosure and human-validation statement.
5. A concrete release note, or `NONE`.

## Problem-To-Behavior Shape

Cross-year Karmada samples from `@zhzhuang-zju` show that the strongest PR bodies do four things in order:

1. Name the old observable failure or operational risk, not just the edited symbol.
2. Explain the new behavior at contract level; leave file narration to the diff.
3. Link the exact issue relationship (`Fixes`, `Part of`, or `Refs`) and state one deliberate non-goal when lifecycle or compatibility work is deferred.
4. For performance work, include workload scale, before/after measurement, and a stable evidence link; for API/deprecation work, include the migration/skew contract in the body or release note.

This is a calibrated pattern, not a personal template. Some merged samples had thin API-change bodies, blank test notes, incomplete issue links, or empty release notes. Merge outcome does not make those omissions reusable. AgentCube still requires its own official template, validation evidence, AI disclosure, and upgrade/security details.

## Remove By Default

- The local code rationale matrix or a file-by-file diff narration.
- Complete test-case and command inventories; give the main command and result.
- Chronological debugging or implementation logs.
- Dynamic CI status/counts and links that will become stale.
- Bot/AI summaries, repeated non-goals, and full proposal text.
- Raw benchmark JSON; link the stable report or issue and summarize the decision-relevant numbers.

## Long-Form Exceptions

- Proposal PR: keep the body to an executive summary and link the proposal document.
- API/CRD or compatibility migration: retain old/new behavior, skew/upgrade impact, generated artifacts, and the required user action.
- Security change: retain the threat boundary and negative-path validation.
- Benchmark PR: retain the environment dimensions that materially affect interpretation, but keep full methodology/results in the issue or report.

## Compression Pass

- Can a reviewer state the problem, behavior, risk, and validation after one screen?
- Does each paragraph change a review decision?
- Is any detail already in the issue, proposal, diff, or local report?
- Will every CI/test claim remain accurate next week?

Measure visible size with:

```bash
python3 .agents/skills/agentcube-issue-discussion/scripts/draft_metrics.py <draft.md> --limit 300
```
