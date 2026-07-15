---
name: agentcube-pr-review
description: Review AgentCube pull requests and local diffs with repository-specific architectural depth. Use for substantive code, design, compatibility, conflict-resolution, or test reviews that must assess component ownership, duplicated behavior, control/data-plane boundaries, lifecycle and failure paths, Go type and pointer semantics, Kubernetes API consistency, clean code, test validity, and whether a change fits the project's overall direction. Also use to turn proven review misses into reusable AgentCube review patterns. Pair with agentcube-pr-management for branch hygiene, CI state, PR wording, and any upstream-facing action.
---

# AgentCube PR Review

Review from changed symbols outward to call chains, state ownership, component contracts, and whole-system lifecycle. Prefer a small number of evidence-backed findings over a large checklist dump.

## Boundaries

This skill owns review judgment. It does not own GitHub posting, branch mutation, PR-body editing, reviewer requests, or maintainer commands. Use `agentcube-pr-management` for those actions and preserve its explicit-confirmation gates.

Do not modify the reviewed branch unless the user asks for a fix. A review request authorizes read-only inspection and focused validation only.

## Required References

Read the references needed for the changed surface:

- Always read [references/agentcube-architecture-review.md](references/agentcube-architecture-review.md) for component ownership and point-to-line-to-surface analysis.
- Always read [references/agentcube-review-checks.md](references/agentcube-review-checks.md) for language, API, lifecycle, test, and conflict checks.
- Read [references/review-patterns.md](references/review-patterns.md) before finalizing findings and when deciding whether a reusable lesson is proven.
- Read [references/maintainer-review-methods.md](references/maintainer-review-methods.md) when reviewing a proposal, controller, shared helper, or when calibrating review quality against maintainer history.

## Review Workflow

### 1. Establish the exact review surface

Identify:

- repository, base ref, head ref, merge base, and current commit SHA;
- changed files, generated files, dependency changes, manifests, tests, and CI files;
- whether the head contains the latest base and whether conflict resolution changed PR intent;
- issue, proposal, PR conversation, and maintainer constraints when they are authoritative.

For local refs, run:

```bash
python3 .agents/skills/agentcube-pr-review/scripts/review_surface.py \
  --repo-root . --base upstream/main --head HEAD --format markdown
```

Treat script output as leads. Verify every suspected defect in source, diff, tests, or runtime evidence.

When studying a maintainer's repeated review method, fetch a bounded, diverse PR sample with:

```bash
python3 .agents/skills/agentcube-pr-review/scripts/maintainer_review_history.py \
  --repo volcano-sh/agentcube --reviewer RainbowMango --exclude-authored \
  299 326 366 391 393 414 420 431
```

Read each sampled PR's problem, diff, reviewer comment, author response, and merge outcome before promoting a pattern. Do not infer reviewer intent from isolated quotes or approval counts.

When a force-push or rebase claims to resolve conflicts, use all three views:

1. ancestry: does the head contain the intended base;
2. structural merge: does `git merge-tree` report a clean merge;
3. semantic preservation: does `git range-diff` show the feature patches still express the same behavior.

A clean merge proves only structural compatibility. It does not prove behavior was preserved.

### 2. Build a change model before judging code

Summarize the change in six parts:

- problem and invariant being protected;
- authoritative state and writers;
- observations used by each decision and their freshness domains;
- changed call paths and component contracts;
- progress or commit markers and the side effects they certify;
- expected success, failure, rollback, deletion, and recovery behavior.

For each material resource, trace:

```text
request -> validation -> desired state -> reconciliation/execution
        -> observation/cache -> decision snapshot -> persisted identity -> routing/use
        -> required side effects -> progress/commit marker
        -> timeout/cancel -> cleanup/finalizer/GC
```

Name the actor that writes each transition. Distinguish authoritative, cached, derived, and reflected state. Track Kubernetes `UID`, `generation`, `resourceVersion`, owner references, and status writers when identity or freshness matters.

### 3. Expand from point to line to surface

Review in three passes:

- **Point:** changed expression, type, function, test, manifest, or workflow step.
- **Line:** caller/callee chain, data transformation, state transition, error propagation, and cleanup path.
- **Surface:** cross-component responsibility, public contract, operational lifecycle, upgrade path, and project direction.

Do not stop at the diff if the defect can only be seen in consumers, controllers, generated clients, RBAC, Helm values, or runtime installation scripts.

### 4. Apply architectural and design gates

Ask:

- Does the change belong to this component, or duplicate policy owned elsewhere?
- Does it introduce a second source of truth, writer, retry loop, lifecycle controller, identity mapping, or protocol adapter?
- Does it preserve control-plane versus data-plane boundaries?
- Does its design fit the issue/proposal and nearby repository direction, or solve a local symptom by weakening a global invariant?
- Are limitations explicit: unsupported modes, compatibility floor, permissions, concurrency assumptions, cache freshness, and operational prerequisites?
- Does one decision combine live reads, informer caches, or reflected status, and who owns convergence before a stale observation can trigger rollback or another destructive action?
- Is the abstraction proportional to the problem and consistent with existing repository patterns?

Use the component map in `agentcube-architecture-review.md`. A responsibility overlap is not automatically a defect; prove duplicated ownership or divergent semantics.

### 5. Apply implementation gates

Use `agentcube-review-checks.md` to inspect:

- Go value versus pointer semantics, `nil` versus zero values, aliasing, mutation, deep copy, receiver choice, and interface contracts;
- Kubernetes spec/status boundaries, GVK/GVR, JSON tags, markers, defaults, validation, CRDs, generated clients, and RBAC;
- error classification through the exact production wrapping chain, context propagation, timeout ownership, retries, goroutines, channels, locks, timers, and cleanup;
- ordering between required side effects and `lastSeen`, processed-generation, cached-executor, completion, or similar progress markers;
- naming, package boundaries, code duplication, unnecessary abstraction, syntax/style consistency, and clean-code readability;
- manifests, CLI/SDK/integration compatibility, dependency versions, and installed runtime versions.

Repository style is supporting evidence, not a substitute for a behavioral argument.

### 6. Attack non-happy paths

At minimum, inspect:

- malformed or unauthorized input;
- not found, already exists, forbidden, conflict, timeout, cancellation, and partial success;
- stale cache, delayed status, duplicate event, restart, and concurrent writer behavior;
- divergent live/cache observations used by one decision, and wrapped transient/permanent errors reaching a retry classifier;
- a late side-effect failure followed by an identical retry with no new event or desired-state change;
- creation rollback, deletion, finalizer, garbage collection, leaked goroutine/resource, and repeated cleanup;
- old/new version skew and optional feature disabled paths.

For async lifecycle changes, verify the sequence itself. A final absence check can pass even if the resource was never created; require presence before absence where appropriate.

### 7. Validate evidence in proportion to risk

Prefer this evidence ladder:

- **E0:** intuition or plausible mechanism;
- **E1:** source/diff supports the mechanism;
- **E2:** existing test or static check covers it;
- **E3:** focused reproduction or regression test shows the behavior;
- **E4:** causal validation shows the behavior fails without the fix and passes with it.

Evidence strength and production reachability are separate axes. A synthetic E3/E4 test can prove what happens after an injected trigger without proving that production can create that trigger. Conversely, source plus an API contract can prove a reachable latent bug without an observed incident.

Classify a bug as observed only when logs, CI, or a realistic end-to-end environment records the qualifying trigger and impact. E3/E4 strengthen causal proof but do not change the reachability class unless the reproduction itself is production-realistic. Permit a source-proven latent finding only when the production trigger, reachable preconditions, recovery behavior, and concrete consequence are all closed; state explicitly that no qualifying occurrence was observed.

Tests must exercise the behavior they claim to validate. Check the installed controller/runtime/dependency version, feature flags, auth mode, and cleanup path rather than trusting a green job name.

Test at the boundary the production code actually sees. Feed retry classifiers the wrapped errors produced by real helpers, construct divergent live/cache views when freshness matters, and for progress markers run two reconciles: fail a required late side effect first, then prove the identical retry performs the missing work before committing success.

For high-risk claims, perform an independent falsification pass: attempt to disprove the finding through another call path, test, documentation contract, or runtime observation.

#### Production Reachability Gate

Apply this gate before calling an unobserved scenario a bug or using it as a blocking finding:

1. Define the exact trigger and bad outcome separately, including input, error, timing, concurrency, and prior state.
2. Identify the real producer. Require either an observed occurrence or `CODE`/`DOC` proving that a production component or interface may produce the trigger. An arbitrary mock return is not a producer.
3. Prove the preconditions are reachable through supported operations. Check validation, locks, ownership, controller ordering, feature gates, and every writer of the affected Store entry or Kubernetes spec/status.
4. Trace retry, resync, restart, later events, rollback, and cleanup. Determine whether the consequence persists or self-heals within the contract.
5. Run a counterfactual or regression test only after reachability is established, and inject an error or state that the real boundary is allowed to produce.
6. Classify the result accurately:
   - **Observed bug:** the trigger and impact occurred in logs, CI, or a realistic end-to-end environment.
   - **Reachable latent bug:** source or contract evidence proves that production can reach the trigger and bad outcome, but no qualifying occurrence has been observed.
   - **Hypothetical scenario:** only a mock, manually constructed state, or imagined ordering creates the trigger; production reachability remains unproven.

Fault injection proves conditional control flow, not production reachability. A reachable latent bug may still block when the trigger is a routine external failure mode and the consequence violates a correctness or safety invariant. Reachability is necessary but not sufficient for blocking: also prove that the current PR introduces or modifies the path, the correction is in scope, and the consequence is material. Keep a hypothetical scenario non-blocking and present it as a question, evidence gap, or realistic-test request rather than a bug.

### 8. Write findings reviewer-first

Order findings by severity. Each finding must include:

1. concise title with severity;
2. precise file and line;
3. trigger or execution path;
4. concrete consequence;
5. reachability class, evidence, and confidence;
6. smallest direction for correction or missing test.

Do not report:

- pure style preference without repository evidence or material maintenance cost;
- hypothetical failures with no reachable path;
- pre-existing defects unrelated to the change, except as clearly separated residual risk;
- generated-file differences whose real cause belongs in the generator;
- CI state as a code finding.

If no defects are proven, say so clearly and list remaining test gaps or unverified assumptions.

## Output Shape

Use this order:

```markdown
## Findings

- [severity] Finding title — `path/file.go:line`
  Trigger, consequence, evidence, and correction direction.

## Open Questions

Only questions that materially change correctness or scope.

## Review Coverage

Base/head, major paths traced, tests run, and limits.
```

Keep summaries secondary. Do not bury findings under a walkthrough of every changed file.

## Learning Loop

After a completed review, classify the outcome:

- new proven miss or maintainer correction: update `references/review-patterns.md`;
- stable AgentCube architecture knowledge: update `references/agentcube-architecture-review.md`;
- reusable five-step review workflow: update this skill or its script;
- one-off uncertainty: leave it out.

Promote a lesson only when supported by a real PR, test, incident, or maintainer decision. Record the trigger, hidden assumption, evidence, review question, and false-positive guard. Merge overlapping patterns instead of growing a pile of aliases.

The goal is not self-modification after every review. The goal is evidence-driven improvement that makes future reviews faster, more architectural, and less repetitive.
