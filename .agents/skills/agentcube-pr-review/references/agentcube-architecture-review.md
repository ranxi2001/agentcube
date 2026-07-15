# AgentCube Architecture Review Map

## Contents

- [Review scale](#review-scale)
- [System boundaries](#system-boundaries)
- [Component ownership](#component-ownership)
- [State and identity](#state-and-identity)
- [Cross-component review paths](#cross-component-review-paths)
- [Architecture decision questions](#architecture-decision-questions)

## Review scale

Use three linked views:

| Scale | Question | Evidence |
|---|---|---|
| Point | Is the changed symbol locally correct? | Diff, types, unit tests |
| Line | Is its call/state path correct? | Callers, consumers, errors, lifecycle tests |
| Surface | Does it preserve system ownership and contracts? | Component boundaries, API, manifests, e2e, proposal |

A reviewer becomes architecture-capable by repeatedly connecting these views, not by applying a larger style checklist.

## System boundaries

AgentCube is a session-oriented control plane around sandbox runtimes.

- **Control plane:** Router, WorkloadManager, Store, CRDs/controllers, desired state, identity, ownership, routing decisions, and lifecycle policy.
- **Data plane:** sandbox workload, PicoD execution/file/process endpoints, AgentD runtime behavior, and workload network traffic.
- **Adapters:** SDK, CLI, integrations, manifests, and dependency-specific runtime translation.

Review any change that moves policy across these boundaries. Convenience calls are acceptable; competing ownership is not.

## Component ownership

### Router (`cmd/router`, `pkg/router`)

Owns request authentication/authorization integration, session lookup, routing decisions, proxy behavior, and request-facing protocol semantics. It may trigger lifecycle operations through WorkloadManager contracts.

Watch for:

- direct Kubernetes lifecycle orchestration that bypasses WorkloadManager;
- copied Store ownership or TTL policy;
- unsafe proxy-before-owner-check ordering;
- retries/timeouts that conflict with downstream ownership;
- auth middleware ordering and unbounded metric labels.

### WorkloadManager (`cmd/workload-manager`, `pkg/workloadmanager`)

Owns sandbox lifecycle orchestration, translation to runtime resources, readiness observation, create/delete/pause/resume coordination, and Store updates needed to expose a usable session.

Watch for:

- mixing request protocol or proxy transport into lifecycle logic;
- confusing a control object such as `SandboxClaim` with the adopted runtime `Sandbox`;
- treating informer observation as authoritative state without freshness reasoning;
- rollback gaps after partial resource creation;
- user-scoped clients gaining hidden RBAC requirements.

### Store (`pkg/store`)

Owns persisted session/control identity, lookup, ownership metadata, activity/expiry indexes, and concurrency semantics for stored entries.

Watch for:

- Kubernetes side effects inside persistence code;
- multiple writers applying different lifecycle policy;
- unconditional overwrite where compare-and-swap or version checks are needed;
- stale expiry indexes and status transitions that diverge from the primary entry;
- storing derived runtime identity without preserving control identity.

### PicoD (`cmd/picod`, related packages)

Owns sandbox-local data-plane APIs such as file, execution, and process operations.

Watch for:

- control-plane scheduling, session ownership, or global lifecycle policy;
- middleware that fails to observe recovery/abort paths;
- request metrics whose labels are attacker-controlled or unbounded;
- process/file cleanup that does not survive cancellation or errors.

### AgentD (`cmd/agentd`, related packages)

Owns agent-runtime behavior and runtime-local signaling required by the control plane.

Watch for overlap with PicoD execution APIs or WorkloadManager lifecycle authority. Define whether AgentD reports state, executes a transition, or owns the transition; do not leave that implicit.

### API types and controllers (`pkg/apis`, controller packages)

Own declarative contracts, reconciliation, status conditions, finalizers, defaults, validation, and observed state.

Watch for:

- spec fields with no authoritative reconciler;
- status written by multiple actors;
- finalizers without every deletion escape path;
- API changes without CRDs, deepcopy, clients, RBAC, and compatibility analysis;
- using names where UID/generation/resourceVersion is required.

### SDK, CLI, and integrations (`sdk-python`, `cmd/cli`, `integrations`)

Own client ergonomics, serialization, user-facing commands, and framework adapters.

Watch for hidden lifecycle policy, defaults inconsistent with server behavior, duplicated protocol models, incompatible optionality, or retries that mask server errors.

### Manifests, Helm, Docker, and CI

Own deployment wiring and validation environments, not product semantics.

Watch for chart/default drift, missing RBAC, secret exposure, moving runner labels, image/controller version skew, and CI jobs that do not exercise the claimed configuration.

### Generated code (`client-go`, generated CRDs/deepcopy)

Generated output reflects source contracts. Fix generators, API definitions, or post-processing steps rather than hand-maintaining generated drift.

### External runtime dependencies

AgentCube adapts resources supplied by projects such as `agent-sandbox`; it does not own their controller internals. Review dependency API version, installed controller version, CRDs, runtime image, and adapter assumptions as one compatibility surface.

## State and identity

Classify every important field:

| Class | Examples | Review concern |
|---|---|---|
| Authoritative desired state | CR spec, Store ownership/session intent | writer and concurrency policy |
| Authoritative observed state | controller status/conditions | writer, generation, transition time |
| Cached observation | informer/lister result | staleness and read-after-write |
| Progress/commit marker | last-seen target, processed generation/hash, cached executor version | exact completion meaning and commit point after required side effects |
| Derived state | ready counts, endpoint, expiry index | invalidation and rebuild |
| Control identity | session ID, claim name, store key | API/delete/ownership continuity |
| Runtime identity | adopted Sandbox name/UID, Pod UID/IP | routing and runtime continuity |

Names are not always identity. Track UID across adoption/recreation, generation across spec changes, and resourceVersion across optimistic updates.

## Cross-component review paths

Trace the paths relevant to the PR:

```text
Create:
SDK/CLI -> Router/API -> WorkloadManager -> runtime CR -> controller
        -> status/informer -> Store -> response

Invoke:
client -> Router -> auth/owner check -> Store -> lifecycle readiness
       -> refreshed endpoint -> PicoD/AgentD -> activity update

Delete:
client/GC -> WorkloadManager -> control resource -> finalizer/ownerRef GC
          -> runtime resources disappear -> Store/index cleanup

Upgrade:
go.mod/API client -> installed CRDs/controller/image -> manifests/CI/e2e
```

For each arrow, ask who owns timeout, retry, error translation, and cleanup. Verify that the timeout owner's deadline is carried into the blocking call; a nearby timer is not an I/O cancellation mechanism.

## Architecture decision questions

1. What invariant does this design protect?
2. Which component is the single owner of that invariant?
3. Does another component already implement the same policy or transformation?
4. Is shared code truly shared mechanism, or an abstraction hiding different semantics?
5. Does the change add a second writer or source of truth?
6. Are control identity and runtime identity deliberately separated?
7. Does the design remain correct under stale observation, retry, restart, and duplicate delivery?
8. Are compatibility and migration behavior explicit?
9. Does the solution fit the issue/proposal and adjacent planned work?
10. Is there a smaller design that preserves the same invariant with fewer ownership changes?
11. Do all observations used by one decision have compatible freshness, or an explicit convergence owner?
12. What does each progress marker certify, and which late failures must remain retryable before it advances?
