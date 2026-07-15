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

- `OBS`: directly observed runtime/test behavior; synthetic or fake-test `OBS` proves only the asserted conditional behavior and does not by itself make a scenario an Observed bug;
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

### Green CI must run the target runtime and target scenario

- Trigger: Dependency/API compatibility PR changes `go.mod`, CRD/client behavior, or runtime adapter semantics.
- Hidden assumption: A green e2e job uses the imported dependency's controller/runtime version and actually executes the feature-specific tests.
- Failure mode: Tests compile against the new library but install an old controller, or install the right controller while the target suite is skipped by auth/mTLS/feature gates.
- Evidence source: `CODE` and `OBS`, AgentCube PR #387 used `agent-sandbox v0.4.6` in `go.mod` while the e2e installer defaulted to `v0.1.1`; after aligning the installer, the standard mTLS job was green but skipped every CodeInterpreter/WarmPool test. A focused non-mTLS fork run then executed and passed the claim-adoption path.
- Review question: Which exact controller, CRD, and image versions did the live test install, and which target tests passed rather than skipped?
- Validation: Inspect workflow inputs, install logs, and the PASS/SKIP test list; compare them with dependency versions and the changed behavior.
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

- Trigger: A label derives from URL, raw HTTP method, command, file path, session, error text, or other request input.
- Hidden assumption: Convenient request detail is safe as a metric dimension.
- Failure mode: Unbounded time series increase memory and storage cost and can destabilize monitoring.
- Evidence source: `OBS`, `CODE`, and `DOC`, AgentCube PR #400 metrics review. Arbitrary valid HTTP method tokens created one counter child and one histogram child per value; Prometheus `promhttp` instead normalizes methods outside its finite set to `unknown`.
- Review question: Is every label drawn from a genuinely finite set such as a route template, normalized allow-listed method, or status class?
- Validation: Exercise dynamic paths and many custom HTTP methods, then confirm series count remains bounded and unknown values collapse to one label.
- False-positive guard: High-cardinality detail belongs in logs/traces, not metrics; a truly finite enumerated set is acceptable.

### Histogram buckets must cover the domain operating range

- Trigger: A PR adds a latency or size histogram with library-default buckets.
- Hidden assumption: Generic network-service defaults describe the component's normal workload and timeout range.
- Failure mode: Values above the largest finite bucket become indistinguishable; classic-histogram quantiles that land in the `+Inf` bucket return the second-highest boundary, hiding the real tail.
- Evidence source: `CODE` and `DOC`, AgentCube PR #400 uses Prometheus `DefBuckets` ending at 10 seconds while PicoD execute defaults to 60 seconds and accepts longer timeouts; Prometheus documents the highest-bucket quantile rule.
- Review question: Do finite bucket boundaries cover the component's expected SLO, default timeout, and material tail range?
- Validation: Map default and maximum practical operation durations to bucket boundaries, observe representative short and long values, and verify the intended percentile or threshold queries remain informative.
- False-positive guard: The default buckets are acceptable when the measured handler has a documented sub-10-second contract, or when only count/sum and an explicit over-threshold ratio are required rather than tail quantiles.

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

### Proposal front door must establish actor, outcome, and current vocabulary

- Trigger: A formal proposal introduces a public feature name, API resource, node component, or external runtime integration.
- Hidden assumption: A detailed CRD, state machine, and failure-path design is reviewable even when the opening does not clearly state who needs the feature, which operational outcome they need, or whether names match the current architecture.
- Failure mode: An implementation-oriented name becomes an awkward long-lived feature name, a mechanism name hides component responsibility, deprecated roadmap vocabulary is frozen into APIs/docs, or implementers cannot trace a high-risk external protocol to its authoritative contract.
- Evidence source: `MAINTAINER`, AgentCube PR #431 review by `@RainbowMango` asked the author to remove the redundant double `pool` feature name, rename `placeholder-agent` around its AgentCube pool responsibility, link the containerd Task v2 contract, explain the cluster administrator's co-location need, and stop using the deprecated `node-ctl` name.
- Review question: Can the first 60 lines identify the user/administrator, their concrete problem, the promised outcome, stable feature/component names, current cross-project terminology, and authoritative references for external contracts?
- Validation: Trace actor → pain → outcome back to the parent issue; compare feature and component names with their full responsibilities; search current related discussions for renamed/deprecated concepts; verify protocol links against primary upstream documentation before reviewing implementation detail.
- False-positive guard: Temporary implementation names are acceptable in an explicitly internal spike that cannot become public API, documentation, CLI, metrics, or long-lived component vocabulary.

### Public API fields need a current owner and distinct behavior

- Trigger: A proposal adds overlapping selectors, duplicate configuration paths, informational-only spec fields, or fields reserved for unspecified future behavior.
- Hidden assumption: Keeping an extra field is cheap and future flexibility justifies an input that no current component consumes.
- Failure mode: The API gains two sources of truth, undefined precedence, inert desired state, and compatibility obligations before a supported behavior exists.
- Evidence source: `MAINTAINER` and `CODE`, AgentCube PR #431 asked why both `Selector` and `NodeSelector` existed and whether users should provide `NodeCtlEndpoint` when the runtime actually obtains it from host startup configuration; the author acknowledged that `NodeSelector` was redundant.
- Review question: Who sets, reads, validates, and reconciles this field today, what distinct supported behavior does it enable, and how do related fields compose or conflict when both are set?
- Validation: Build a field-to-writer-to-consumer matrix, trace unset and conflicting values through the actual control path, and remove fields that have no authoritative consumer.
- False-positive guard: Separate fields are valid when they model orthogonal axes with explicit owners, defaults, precedence, and current supported behavior. Keep hypothetical future modes in non-normative design notes until their contract is ready.

### Open Kubernetes dimensions should use native extensible types

- Trigger: A Kubernetes-facing API hardcodes CPU/memory, device classes, topology keys, conditions, selectors, or another dimension whose valid names can expand.
- Hidden assumption: The first supported members form a closed set and adding another field later is harmless.
- Failure mode: GPU, hugepages, vendor resources, or future platform values require schema/client/version changes and parallel conversion logic even though Kubernetes already defines an extensible representation.
- Evidence source: `CODE` and `DOC`, AgentCube PR #431 hardcoded CPU and memory in `ResourcePolicy`; a live maintainer review proposed `corev1.ResourceList`, whose contract is a map from `ResourceName` to `resource.Quantity`. The PR-level design decision remains pending.
- Review question: Is this dimension intentionally closed, or will every new Kubernetes value require an API change, and does a native Kubernetes type already preserve the required validation and extension model?
- Validation: Exercise at least one non-default native value such as an extended resource key, then apply project-specific validation only where the current implementation truly lacks support.
- False-positive guard: Explicit typed fields are preferable for a genuinely closed set whose members have different semantics, ownership, or validation. Do not replace a clear contract with an arbitrary map merely for hypothetical extensibility.

### Self-healing must preserve invariants through the recovery window

- Trigger: A design claims self-healing by periodically recreating a manifest, control object, reservation, lock, route, or runtime process after deletion or failure.
- Hidden assumption: Eventual restoration of desired state means the protected invariant remained true throughout recovery.
- Failure mode: During detection and repair, capacity or ownership becomes visible to another actor; that actor consumes it, and the recreated resource can no longer be admitted or can conflict with the new state.
- Evidence source: `CODE` and `INFERENCE`, a live maintainer review on AgentCube PR #431 traced how manifest self-healing could recreate a deleted Static Pod manifest only after kubelet had stopped the Pod and freed scheduler-visible reservation. The author classified the mutation as an unsupported constraint, so the PR-level guarantee remains unresolved.
- Review question: Between failure detection and recovery completion, what state becomes visible or free, who may act on it, and can recovery still succeed after that competing action?
- Validation: Inject the supported failure, introduce the realistic competing action during the gap, assert the invariant at each stage, and verify convergence or a clearly surfaced terminal/degraded state.
- False-positive guard: If privileged destructive mutation is explicitly outside the supported contract, document that limitation and stop claiming continuity for it. Simple recreation is sufficient when an independent reservation or admission fence remains intact throughout the gap.

### Validate the problem before accepting the patch

- Trigger: A PR is labeled as a bug/regression or adds a test for a claimed failure.
- Hidden assumption: The issue's diagnosis and expected behavior are correct because the patch looks harmless or defensive.
- Failure mode: The project merges an unnecessary production change, codifies the wrong expected behavior, or expands a focused cleanup into an unrelated fix.
- Evidence source: `MAINTAINER`, Karmada #7395 showed that the caller could not observe the alleged slice mutation and reclassified the change as cleanup; Karmada #7640 challenged a panic claim because omitted value-typed placement should remain valid; AgentCube #357 kept a sensible adjacent improvement out of a typo-only PR.
- Review question: What exact caller observes the behavior, which contract says it is wrong, and does the correction belong to this PR's stated scope?
- Validation: Trace the value to its consumer, reproduce the claimed behavior or write the smallest causal test, and compare the result with the API/issue contract before reviewing implementation detail.
- False-positive guard: Defensive tests and cleanup remain useful when named honestly; do not require a runtime reproduction for a defect already proven by type/API semantics.

### Fault injection does not prove production reachability

- Trigger: A bug claim or blocking review finding relies on a fake client, mock error, or manually constructed state.
- Hidden assumption: Showing bad behavior after an injected trigger also proves that a production component can emit the trigger under supported operations.
- Failure mode: Reviewers classify an impossible or unproven scenario as a production bug, request the wrong fix, or overstate an unobserved latent defect as an incident.
- Evidence source: `CODE` and Kubernetes API semantics from Karmada PR #7623. An injected `Status().Update` error proved the broken retry consequence; the real API write boundary, independent status writer, and permitted Conflict/timeout errors separately proved reachability. No production occurrence was observed.
- Review question: Which real producer and interface contract create the trigger, are its preconditions reachable despite validation/locking/ownership/order, and do retry, resync, restart, later events, or cleanup repair the state?
- Validation: Establish the producer and supported state first, then use the closest production-equivalent trigger. For optimistic status writes, prefer a real Conflict from stale `resourceVersion` or concurrent writers over an arbitrary injected error; trace the retry to the final invariant.
- False-positive guard: Fault injection remains valid for the consequence and counterfactual once reachability is independently proven. Source-proven but unobserved cases are reachable latent bugs; mock-only cases remain non-blocking questions or test gaps.

### Shared helpers must preserve domain routing

- Trigger: One helper handles namespaced and cluster-scoped resources, multiple kinds, multiple workers/queues, or multiple status/cleanup destinations.
- Hidden assumption: Similar input shapes imply the same downstream route and ownership semantics.
- Failure mode: A resource is sent to the wrong worker, looked up with invalid namespace semantics, silently skipped, or cleaned up by the wrong owner.
- Evidence source: `MAINTAINER` and `CODE`, Karmada #7613 found that a helper shared by `ResourceBinding` and `ClusterResourceBinding` always selected the namespaced eviction worker, causing empty-namespace lookup and leaving cluster-scoped bindings unevicted.
- Review question: For every caller kind, which queue, client scope, status writer, and cleanup owner receives the item?
- Validation: Build a kind-to-destination matrix and add one focused test per distinct route, including the cluster-scoped or optional path most likely to collapse into a default.
- False-positive guard: A shared route is correct when all callers intentionally share scope, identity, retry, and ownership semantics and tests prove that contract.

### Field ownership is not status authorization

- Trigger: Multiple controllers, node agents, or external actors write disjoint status fields using SSA field managers.
- Hidden assumption: Non-overlapping managed fields prevent one writer from changing another writer's fields and therefore form a security boundary.
- Failure mode: Admission rejects a legitimate writer, or an authenticated but compromised writer uses a different field manager, force apply, or ordinary Patch to modify fields outside its authority.
- Evidence source: `CODE` and `DOC`, AgentCube PR #431 assigned `phase` and two Conditions to the controller while its proposed status webhook allowed only node-bound agents to update status. The same rule did not restrict an allowed agent to agent-owned fields.
- Review question: For every authenticated caller, which exact status fields and condition types may change, and does admission compare old/new objects independently of the client-supplied field manager?
- Validation: Build a caller-to-field matrix; test legitimate controller and own-node agent writes, cross-node writes, agent changes to controller fields, forged field-manager names, non-apply patches, force conflicts, and webhook failure policy.
- False-positive guard: SSA remains the right merge/concurrency mechanism. It is sufficient without field-level admission only when all status writers are inside the same trust boundary and broader status write permission is intentional.

### Derived identifiers need a budget for every representation

- Trigger: An object name or external identifier is copied into a label, annotation, filename, metric label, DNS label, socket name, URL path, or generated child name.
- Hidden assumption: Validation of the source identifier makes every derived representation valid.
- Failure mode: A source-valid value exceeds a smaller downstream limit, changes allowed characters, collides after truncation, or fails only at a later API/runtime/filesystem boundary.
- Evidence source: `CODE` and Kubernetes validation contracts, AgentCube PR #431 supported a 253-character Pool object name, copied full Class/Node/Pool names into 63-character label values, and embedded the Pool name in a manifest basename that can exceed Linux `NAME_MAX=255`.
- Review question: What are the maximum length, character set, uniqueness, collision, and reversibility requirements at every transformation boundary?
- Validation: Create a representation budget table and test immediately below/at/above each limit. Use bounded deterministic hashes for selectable identifiers and keep full lossless identity in a field or annotation whose contract permits it.
- False-positive guard: Reusing a value is safe when the destination has equal or broader constraints and the same uniqueness scope; do not hash human-readable identifiers without a demonstrated budget or privacy need.

### Readiness must be generation-fresh and incarnation-bound

- Trigger: A controller aggregates Ready from conditions written asynchronously by another component, especially across spec updates or delete/recreate of the referenced object.
- Hidden assumption: A True condition and fresh heartbeat describe the current desired generation and current object instance.
- Failure mode: Generation N remains Ready after spec advances to N+1, or a new object with the same name inherits status from the deleted object's UID until heartbeat expiry.
- Evidence source: `CODE` and Kubernetes object semantics, AgentCube PR #431 exposed `lastAppliedGeneration` but did not use it in the Ready predicate, and bound Pools to `nodeName` without a Node UID/incarnation fence.
- Review question: Which desired generation and referenced-object UID produced each condition, and what resets or gates status when either changes?
- Validation: Test Ready N -> spec N+1 before writer acknowledgement, rapid N+2, writer failure, object UID A deletion, and same-name UID B recreation. Require current `observedGeneration` plus the intended identity fence before Ready.
- False-positive guard: Generation checks are unnecessary for observations intentionally independent of spec. UID checks are unnecessary when owner references or mandatory recreation guarantee that old status cannot survive a new incarnation; prove that lifecycle rather than assuming it.

### State-machine priorities must compose under simultaneous failures

- Trigger: A phase is computed by an ordered list of boolean conditions or early returns.
- Hidden assumption: Only one failure predicate is true at a time, so each row can be reviewed independently.
- Failure mode: An earlier, less severe predicate permanently shadows a later timeout or terminal state, making a documented transition unreachable under combined failures.
- Evidence source: `CODE`, AgentCube PR #431 placed `agent unhealthy + Pod ready -> Degraded` before `node-ctl unhealthy >=5m -> Unready`; when both were true, the documented five-minute Unready transition could not execute.
- Review question: For every pair or meaningful combination of simultaneously true predicates, which state wins, and does that result match the transition table and severity/recovery contract?
- Validation: Generate a condition matrix or table-driven tests for combinations, boundary times, sticky history flags, recovery, and unknown/stale inputs; assert one canonical compute function rather than separate diagram/table shortcuts.
- False-positive guard: Explicit priority is valid when the earlier predicate intentionally dominates and the documentation explains why. The defect is unexplained shadowing or contradiction, not the existence of ordered checks.

### Status reconciliation should write only meaningful transitions

- Trigger: A controller periodically probes health or derives status/conditions from an external system.
- Hidden assumption: Rewriting status every reconcile is harmless and error handling can share the unhealthy-state path.
- Failure mode: API-server churn, noisy watches, lost error distinction, incorrect transition timestamps, or a controller that waits/requeues without an explainable state contract.
- Evidence source: `MAINTAINER`, Karmada #59 required error paths to return/requeue separately, unhealthy paths to update only the needed condition, status comparison before write, and explanation for finalizer waiting; Karmada #62 required logs for delayed readiness and useful resource identity. A live AgentCube #431 review questioned per-node 30-second CR status writes at thousand-node scale and asked whether to reuse kubelet's Lease-based heartbeat model. The author acknowledged the suggestion, but the concrete Lease/status contract is not yet in the proposal.
- Review question: Which observation is an error versus a valid unhealthy state, what transition changes durable status, who owns requeue timing, is freshness better represented by a compact Lease, what is the `object count / interval` write rate, and can an operator identify the affected object from logs/events?
- Validation: Table-test unchanged, changed, unhealthy, transient-error, deletion, and restart cases; assert status writes and transition times only change when intended. For liveness, validate Lease renewal, expiry detection, RBAC/identity, jitter, and the target-scale API write budget.
- False-positive guard: Periodic status heartbeats may be correct at bounded scale or when the complete status must be renewed atomically and the load is measured. Lease carries freshness, not durable conditions or full observed state.

### Search for existing ownership before adding mechanism

- Trigger: A PR introduces a helper, finalizer, controller loop, configuration convention, or reusable abstraction.
- Hidden assumption: A locally clean implementation is preferable without checking repository or sibling-project precedent.
- Failure mode: Duplicate helpers/finalizers diverge, two components own the same lifecycle rule, or configuration loses an established operational convention.
- Evidence source: `MAINTAINER`, Karmada #59 found an existing readiness helper and duplicate finalizer; Karmada #84 requested a common helper for repeated controller logic; AgentCube #396 pointed to Karmada's Dependabot schedule and asked the author to justify grouping before accepting it.
- Review question: Where does the repository already express this invariant, and if a new mechanism is still needed, what responsibility or semantics make it distinct?
- Validation: Search definitions and call sites, compare field/owner/error semantics, and ask for the smallest rationale when choosing a new path over reuse.
- False-positive guard: Similar syntax is not duplication when ownership, lifecycle, API surface, or failure semantics materially differ.
