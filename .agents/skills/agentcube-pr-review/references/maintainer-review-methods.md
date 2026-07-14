# Maintainer-Calibrated Review Methods

This reference distills repeated public review methods, not a maintainer's personality. Use it to calibrate review order and evidence quality; always verify the current repository contract.

## Evidence Base

The initial corpus sampled public reviews by `@RainbowMango` across:

- AgentCube PRs #357, #366, #396, and #431;
- Karmada foundational PRs #4, #6, #34, #59, #62, #84, and #93 from 2020;
- Karmada PRs #7395, #7613, #7640, and #7732 from 2026.

Excluded from method inference:

- PRs authored by the reviewer, because their comments are author replies;
- approval-only reviews with no rationale, because they show a gate outcome but not the reasoning;
- isolated wording preferences unless they protect a public feature/component contract.

Use `scripts/maintainer_review_history.py` to refresh or expand the corpus. Read the PR problem, diff, comment, author response, and outcome together.

## Review Order

### 1. Verify the problem classification

Before reviewing the patch, ask whether the reported behavior is actually observable and whether it violates the expected contract.

- Karmada #7395: an `append` beyond slice length did not mutate state observed by the caller, so the change was cleanup rather than a bug fix.
- Karmada #7640: omitted value-typed placement was expected to decode to an empty value; the reviewer challenged the bug label and expected the request to remain allowed.
- AgentCube #357: a nearby improvement was sensible but explicitly rejected as out of scope for a typo-only PR.

### 2. Establish actor, outcome, and current vocabulary

For proposals, make the first 60 lines explain the user/administrator, their pain, the promised outcome, stable feature/component names, current roadmap terminology, and authoritative external references. See the `Proposal front door` pattern in `review-patterns.md`.

### 3. Search for existing ownership and precedent

Before accepting a new helper, controller rule, or configuration shape:

- search for an equivalent helper or constant in the repository;
- compare a mature sibling project's configuration when the projects intentionally share conventions;
- ask why a new grouping or abstraction is needed, and accept it when the author gives a coherent trade-off.

Evidence: Karmada #59 found an existing readiness helper and duplicate finalizer; AgentCube #396 reused Karmada's predictable Dependabot schedule and asked the author to justify grouping.

### 4. Trace shared helpers by domain type and destination

Generic helpers can erase meaningful differences. Enumerate each caller's resource kind, namespace semantics, queue/worker, status writer, and cleanup owner.

Karmada #7613 showed the concrete failure: a helper shared by `ResourceBinding` and `ClusterResourceBinding` always selected the namespaced worker, causing the cluster-scoped lookup to use an empty namespace and silently leave resources unevicted.

### 5. Review reconciliation as state transitions

For controllers, check:

- error versus unhealthy-state handling;
- requeue ownership and timing;
- condition transition semantics;
- finalizer ownership;
- whether status is written only when semantically changed;
- whether logs contain the identity needed to debug delayed or failed reconciliation.

Karmada #59 and #62 repeatedly applied these checks to status, finalizer, error, log, and delayed-readiness paths.

### 6. Require comments and names to explain responsibility

Reject stale copy-paste comments, misleading names, and logs without namespace/object identity. Delete comments that merely restate syntax; require a short algorithm or invariant note where the control flow is otherwise hard to recover.

This is not cosmetic when the name becomes a feature, API, metric, finalizer, controller, or operational log contract.

### 7. Use explicit review rounds

When a large patch still has structural problems, say that another review round is required. Do not let dozens of local fixes imply approval. Karmada #84 and #93 explicitly required a second round; #84 was closed in favor of a cleaner replacement path.

## Interaction Method

- Ask a narrow question when author intent can change the judgment.
- Give a minimal correction when the invariant is already clear.
- Accept a reasonable author explanation explicitly instead of defending the initial suggestion.
- Keep unrelated improvements out of a focused PR.
- Approve concisely once the evidence and scope are sufficient; do not invent extra comments to display effort.

## Adaptation Guardrails

- Do not imitate terse early comments without enough context for a new contributor.
- Do not treat the reviewer's preferred wording as a universal rule.
- Do not infer reasoning from `/lgtm` or `/approve` alone.
- Do not count author replies as review evidence.
- Do not copy a Karmada convention unless AgentCube intentionally shares that operational model.
- Historical comments predate current APIs and style; preserve the method, then re-verify the fact.
