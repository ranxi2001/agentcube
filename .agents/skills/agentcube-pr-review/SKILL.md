---
name: agentcube-pr-review
description: Review AgentCube pull requests and local diffs with repository-specific architectural depth. Use for substantive code, design, compatibility, conflict-resolution, final-head, or test reviews that must assess component ownership, duplicated behavior, control/data-plane boundaries, lifecycle and failure paths, Go type and pointer semantics, Kubernetes API consistency, clean code, changed-test CI discovery, test validity, and whether a change fits the project's overall direction. Also use to turn proven review misses into reusable AgentCube review patterns and executable review harnesses. Pair with agentcube-pr-management for branch hygiene, CI state, PR wording, and any upstream-facing action.
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
- Read [references/finding-ledger-schema.md](references/finding-ledger-schema.md) for replacement PRs, repeated final-head rounds, or recall comparisons across different heads.

## Review Workflow

### 1. Establish the exact review surface

Identify:

- repository, base ref, head ref, merge base, and current commit SHA;
- changed files, generated files, dependency changes, manifests, tests, and CI files;
- whether the head contains the latest base and whether conflict resolution changed PR intent;
- issue, proposal, PR conversation, and maintainer constraints when they are authoritative.

For local refs, run the intern-owned skill script against the code worktree explicitly. Official topic worktrees do not contain the intern-only `.agents/` tree:

```bash
python3 /home/agentcube/.agents/skills/agentcube-pr-review/scripts/review_surface.py \
  --repo-root /path/to/pr-worktree \
  --base upstream/main --head HEAD --format markdown
```

Treat script output as leads. Verify every suspected defect in source, diff, tests, or runtime evidence.
When a test is gated by an environment default, resolve the complete workflow path before calling it skipped: bind job-level and step-level env to the step that actually runs the test, expand that job's matrix values, follow `${{ matrix.* }}` assignments, and inspect the target job's PASS/SKIP log. A script default or another job/step's env is not the effective value for the target execution.

For a PR declared ready after repeated patching, rebasing, force-pushing, or squashing, also run the final-head evidence harness. Supply the parent Issue/proposal body or explicit acceptance notes; do not silently omit the contract. When using `--run-go-tests`, run from a clean temporary worktree whose `HEAD` equals `--head`; the harness rejects tracked or untracked changes before testing:

```bash
python3 /home/agentcube/.agents/skills/agentcube-pr-review/scripts/final_head_review.py \
  --repo-root /path/to/pr-worktree \
  --base upstream/main --head HEAD \
  --acceptance-file /path/to/issue-body.md \
  --finding-ledger /path/to/findings.json \
  --finding-closure /path/to/closure.json \
  --run-go-tests --check-urls --format markdown
```

Use repeatable `--acceptance-note` arguments when the authoritative contract is already available as concise text. The harness must expose, at minimum:

- every acceptance candidate from the parent Issue/proposal;
- every hand-written changed file requiring reviewer-owned rationale and evidence;
- every changed Go test package and the exact workflow command, if any, that covers it;
- direct results for changed Go test packages not proven by CI, without rerunning CI-proven or live E2E packages locally;
- added external URLs, lexicographic version comparisons, personal absolute paths, removed validation calls, exported Go signature changes, and Kubernetes library/code-generator minor-version skew.

When the PR replaces, supersedes, or reimplements an earlier PR, build a carry-forward finding ledger before reviewing the new head. Union the parent acceptance contract with unresolved findings from the predecessor PR, local review reports, and validated review threads. Give each finding a stable ID and classify it on the new head as `fixed`, `present`, `not-applicable`, `duplicate-on-current-pr`, or `accepted-by-maintainer`, with code or test evidence. A comment on a closed predecessor PR is not a duplicate on the replacement PR, and an old resolved thread is not evidence that the replacement fixed the code. Bind the closure to the ledger ID, logical version, canonical content digest, current PR, and exact head. Use the dedicated `--finding-ledger` and `--finding-closure` inputs; do not downgrade known findings into free-form acceptance notes.

When there is no predecessor or earlier review finding to carry forward, pass `--no-carry-forward-findings`. The final-head harness deliberately rejects an omitted finding mode so that “no prior findings” is a reviewer-owned decision rather than an accidental default.

For every review round, record the exact reviewed SHA. Before comparing another reviewer or learning from later comments, classify each comment as a same-head miss, a later-head regression, a follow-up on the same acceptance invariant, or a distinct current-head finding. Count only same-head findings in that round's recall denominator. Rerun boundary checks on every new head because URL, API, generator, fixture, and workflow evidence from an earlier head is stale after those lines change.

Treat the output as an evidence ledger, not a finding generator. Close each row against code, runtime evidence, or an explicit out-of-scope rationale. A green check name does not close a changed test package unless the mapped command includes it. Do not publish or declare completion while a supplied finding ledger is missing a closure, contains an unclassified ID, was closed against another ledger version/head, or still has `present` / `duplicate-on-current-pr` rows. A maintainer-accepted residual must use `accepted-by-maintainer` with decision evidence instead of weakening the gate.

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

#### Review Comment Comprehension Gate

A technically correct finding still fails review quality when the author needs the reviewer's private report or follow-up chat to understand it. Treat a line anchor as location, not explanation. Before finalizing a non-trivial finding, hide the local investigation and check whether a reader with only the diff and thread can answer:

1. What exact behavior, statement, or conclusion is under review?
2. What concrete input, event order, or counterexample exposes the issue?
3. What does the observed signal prove, and what stronger claim does it not prove?
4. Why does that distinction matter to correctness, diagnosis, compatibility, or maintenance?
5. What is the smallest requested code, text, or test change?

Draft in `observation -> counterexample -> reasoning -> action` order without requiring literal labels. Translate identifiers and domain terms into their roles before listing them. Put polite wording such as `Could ...?` on the action; politeness does not replace the causal bridge.

When challenging an inference, state the contrast directly, for example `signal = one log match; claim = no runtime retry`. If an author says a comment is hard to understand, treat that as a review-quality miss. Rewrite from one plain-language counterexample instead of adding more jargon or links.

#### Review Visualization Gate

Use a visualization when it materially reduces the relationship the author must reconstruct. Default to comparing a compact inline Mermaid diagram against prose when a finding contains:

- three or more actors, state layers, or dependent transitions;
- ordering, retry, cleanup, race, or recovery behavior;
- one signal with multiple plausible causes;
- current-versus-proposed flow whose invariant is difficult to scan in prose.

Use `flowchart` for branching causes or decision logic, `sequenceDiagram` for actor order and retries, and `stateDiagram-v2` for lifecycle transitions. Keep one question and usually 4-10 nodes. Structure the comment as one plain-language finding, the smallest useful diagram, then one evidence-boundary and action sentence. Follow `project-mermaid` for syntax, labels, and local rendering.

For current/proposed comparisons, preserve node order and stable labels. Keep unchanged/current nodes neutral, accent changed/new nodes, use amber for open questions and red only for material risk, and repeat color meaning in labels, borders, or line styles.

Do not diagram a single local condition that is clearer in one or two sentences. Keep a prose conclusion for accessibility, label hypotheses explicitly, and cite evidence for consequential arrows. When synthesizing meeting, log, experiment, or research evidence, say what the source supports, what it does not establish, and its provenance limits. A diagram must not turn inference into fact.

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

When comparing repeated review runs or changing this review harness, use `agent-autoharness` with a frozen labeled task set. Report outcome, finding recall, resource efficiency, and trajectory flags separately; do not infer improvement from one newly discovered finding or from a single post-hoc reconstruction.

Promote a lesson only when supported by a real PR, test, incident, or maintainer decision. Record the trigger, hidden assumption, evidence, review question, and false-positive guard. Merge overlapping patterns instead of growing a pile of aliases.

The goal is not self-modification after every review. The goal is evidence-driven improvement that makes future reviews faster, more architectural, and less repetitive.
