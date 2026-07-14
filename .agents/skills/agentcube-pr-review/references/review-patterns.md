# AgentCube Review Pattern Library

## Contents

- [How to use this library](#how-to-use-this-library)
- [Promotion gate](#promotion-gate)
- [Pattern entry format](#pattern-entry-format)
- [Seeded patterns](#seeded-patterns)

## How to use this library

Consult patterns as targeted prompts after the change model is understood. They are not automatic findings. Verify reachability, ownership, and consequence in the current PR.

## Promotion gate

Add or revise a pattern only when a real PR, regression test, incident, runtime trace, or maintainer correction proves a reusable lesson. The entry must include a false-positive guard. Merge overlapping entries and remove obsolete assumptions when architecture changes.

Evidence labels:

- `OBS`: directly observed runtime/test behavior;
- `CODE`: source or diff evidence;
- `DOC`: authoritative project/dependency documentation;
- `MAINTAINER`: explicit accepted maintainer decision;
- `INFERENCE`: reasoned but not directly proven.

## Pattern entry format

```markdown
### Short pattern name

- Trigger:
- Hidden assumption:
- Failure mode:
- Evidence source:
- Review question:
- Validation:
- False-positive guard:
```

## Seeded patterns

### Green CI must run the target runtime version

- Trigger: Dependency/API compatibility PR changes `go.mod`, CRD/client behavior, or runtime adapter semantics.
- Hidden assumption: A green e2e job uses the same controller/runtime version as the imported Go dependency.
- Failure mode: Tests compile against the new library but install and exercise an old controller, leaving the changed runtime contract untested.
- Evidence source: `CODE` and `OBS`, AgentCube PR #387 used `agent-sandbox v0.4.6` in `go.mod` while the e2e installer defaulted to `v0.1.1`.
- Review question: Which exact controller, CRD, and image versions did the live test install?
- Validation: Inspect workflow inputs and install logs; compare them with dependency and manifest versions.
- False-positive guard: Version skew may be intentional for compatibility testing when explicitly named and paired with target-version coverage.

### New reads can create hidden RBAC requirements

- Trigger: A request path starts polling or fetching an additional Kubernetes kind through a user-scoped client.
- Hidden assumption: Existing create permission implies permission to read every derived runtime object.
- Failure mode: A permanent `Forbidden` is retried until timeout and returned as a misleading gateway failure.
- Evidence source: `CODE`, AgentCube PR #387 claim readiness added reads for both `SandboxClaim` and adopted `Sandbox`.
- Review question: Which identity executes each GET/LIST/WATCH, and are forbidden errors terminal and tested?
- Validation: Auth-enabled unit/integration test with minimal RBAC and explicit error classification.
- False-positive guard: No defect if the call uses a controller service account with documented RBAC or authorization is guaranteed by the API contract.

### Keep control identity separate from adopted runtime identity

- Trigger: A claim, allocation, or session adopts a pre-existing runtime object.
- Hidden assumption: Control object name and runtime object name are interchangeable.
- Failure mode: Delete targets the wrong object, Store loses session continuity, Router uses a stale endpoint, or cleanup leaks the adopted resource.
- Evidence source: `OBS` and `CODE`, AgentCube PR #387 `SandboxClaim.status.sandbox.name` bridged claim identity to an adopted Sandbox with independent name/UID.
- Review question: Which identity is stored, returned, routed, and deleted at every step?
- Validation: Trace claim/session ID, Sandbox name/UID, Pod UID/IP, ownerRef transfer, routing, and deletion.
- False-positive guard: Direct-create paths may intentionally use one name when the runtime contract guarantees identity equivalence.

### Prove presence before absence in cleanup tests

- Trigger: An async lifecycle test waits only for a resource to disappear.
- Hidden assumption: Absence means successful deletion.
- Failure mode: The test passes because creation never happened or the lookup used the wrong identity.
- Evidence source: General async lifecycle test failure pattern, applicable to AgentCube create/delete/finalizer/GC paths.
- Review question: Did the test first prove that the exact UID/resource entered the expected owned state?
- Validation: Observe presence and identity, trigger cleanup, then observe absence and related Store/index cleanup.
- False-positive guard: Presence proof can come from an earlier causal assertion in the same test/trace.

### Fix generators, not generated output

- Trigger: PR manually edits `client-go`, CRDs, deepcopy code, or generated workflow artifacts.
- Hidden assumption: The checked-in result is the source of truth.
- Failure mode: Regeneration removes the fix or produces recurring drift.
- Evidence source: AgentCube generation workflow and repeated generated-code review practice.
- Review question: Which source type, marker, template, or post-process owns this line?
- Validation: Run the official generator and verify a clean repeat run.
- False-positive guard: A repository-documented post-generation patch may be legitimate when the upstream generator cannot express the required result.

### Middleware observation must wrap abort and recovery paths

- Trigger: Gin/HTTP metrics, tracing, or logging middleware is added or reordered.
- Hidden assumption: Middleware registered after recovery/auth observes all requests.
- Failure mode: Panics, authorization aborts, or early failures are absent from telemetry, creating biased operational data.
- Evidence source: `CODE`, AgentCube PR #400 PicoD Prometheus review.
- Review question: Which middleware frames the full request lifecycle, and which paths abort before it runs?
- Validation: Focused panic, abort, 4xx, and 5xx tests with metric/log assertions.
- False-positive guard: Narrow route-only telemetry is acceptable when its scope is explicitly named and documented.

### Metrics labels need bounded cardinality

- Trigger: A label derives from URL, command, file path, session, error text, or user input.
- Hidden assumption: Convenient request detail is safe as a metric dimension.
- Failure mode: Unbounded time series increase memory and storage cost and can destabilize monitoring.
- Evidence source: `CODE`, AgentCube PR #400 metrics review.
- Review question: Is every label drawn from a small, controlled set such as route template, method, or status class?
- Validation: Exercise dynamic paths and confirm series count remains bounded.
- False-positive guard: High-cardinality detail belongs in logs/traces, not metrics; a truly finite enumerated set is acceptable.

### Do not duplicate lifecycle policy across Router, WorkloadManager, and Store

- Trigger: More than one component begins interpreting session state, retrying transitions, or deciding pause/resume/delete behavior.
- Hidden assumption: Repeating a small state switch near each consumer is harmless.
- Failure mode: Components diverge on valid transitions, timeout ownership, activity updates, or cleanup ordering.
- Evidence source: AgentCube sleep/resume architecture and Store/WorkloadManager/Router review work.
- Review question: Which component owns the transition, which stores state, and which only invokes/observes it?
- Validation: Build a writer/reader matrix and test one authoritative transition path end to end.
- False-positive guard: Multiple readers may map the same stable status to local presentation without becoming writers or policy owners.

### Rebase cleanliness does not prove semantic preservation

- Trigger: A force-push or rebase is presented as resolving conflicts.
- Hidden assumption: `mergeable=true` and green compilation mean the feature patch is unchanged.
- Failure mode: Conflict resolution silently drops base behavior, feature behavior, a test, or generated output.
- Evidence source: PR #387 conflict analysis used ancestry, `git merge-tree`, and `git range-diff` as distinct gates.
- Review question: What changed in the patch series beyond base-context movement?
- Validation: Confirm base ancestry, clean structural merge, then inspect range-diff and hotspot behavior/tests.
- False-positive guard: Patch IDs may legitimately change due to required adaptation; judge preserved intent, not textual identity.
