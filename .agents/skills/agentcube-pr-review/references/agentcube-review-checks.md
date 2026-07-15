# AgentCube Review Checks

## Contents

- [Scope and conflict integrity](#scope-and-conflict-integrity)
- [Design and responsibility](#design-and-responsibility)
- [Go type and pointer semantics](#go-type-and-pointer-semantics)
- [Kubernetes API consistency](#kubernetes-api-consistency)
- [Lifecycle and concurrency](#lifecycle-and-concurrency)
- [Errors, context, and resources](#errors-context-and-resources)
- [Clean code and repository style](#clean-code-and-repository-style)
- [Tests and CI truthfulness](#tests-and-ci-truthfulness)
- [Dependencies and compatibility](#dependencies-and-compatibility)
- [Limitations and review confidence](#limitations-and-review-confidence)

## Scope and conflict integrity

- Compare issue/proposal intent, PR body, commits, and actual diff.
- Identify unrelated refactors, generated churn, local artifacts, and hidden prerequisites.
- Verify base ancestry and structural mergeability.
- Use `git range-diff` across old/new patch series after rebase or conflict resolution.
- Inspect conflict hotspots in shared manifests, generated files, dependency locks, API types, and tests.
- Verify both sides' intent survived; compiling code can still drop a new default, test, or cleanup path.
- Separate PR-introduced defects from pre-existing repository problems.

## Design and responsibility

- State the invariant and its single owning component.
- Search for existing helpers, controllers, adapters, state transitions, and retry loops before accepting new ones.
- Flag duplication only when behavior or ownership overlaps, not merely similar syntax.
- Check control-plane/data-plane direction and dependency direction.
- Reject circular policy: Router should not become a second lifecycle controller; Store should not perform Kubernetes operations; data-plane services should not decide global session policy.
- Compare the chosen method with at least one plausible alternative for high-impact changes.
- Prefer the repository's established abstraction unless it cannot preserve the required invariant.
- Check alignment with planned adjacent work so a local fix does not close off the intended architecture.

## Go type and pointer semantics

### Values, pointers, and optionality

- Does `nil` mean absent, inherit, auto, unknown, or disabled? Is that distinct from the zero value?
- Is a pointer needed for optional Kubernetes/JSON fields, or does it create unnecessary mutation and nil handling?
- Are pointer fields deep-copied before mutation?
- Does a value receiver copy locks, large structs, caches, or mutable state?
- Does a pointer receiver imply mutation that callers can observe?
- Are slices/maps shared across goroutines or API objects without cloning?
- Does returning `*Struct` expose internal mutable state that should be copied?
- Are typed nils stored in interfaces and then compared incorrectly?

### Definitions and contracts

- Is one concept represented by one stable type across API, Store, Router, WorkloadManager, SDK, and manifests?
- Are IDs, names, UIDs, endpoints, statuses, durations, and timestamps consistently typed?
- Are enums/constants used instead of repeated string literals?
- Do interface methods preserve error and context semantics across implementations and fakes?
- Are constructor defaults equivalent to zero-value behavior, tests, and serialized defaults?
- Does a conversion lose optionality, precision, timezone, duration unit, UID, or status meaning?

## Kubernetes API consistency

- Keep desired user input in `spec` and controller observation in `status`.
- Define the authoritative status writer and use `observedGeneration` when required.
- Verify GVK, GVR, pluralization, namespace scope, and TypeMeta/ObjectMeta handling.
- Check JSON tags, `omitempty`, pointer optionality, validation/default markers, list/map semantics, and enum values.
- Check finalizers, owner references, controller/block-owner flags, and deletion timestamp behavior.
- Use UID for object continuity and generation/resourceVersion for freshness/concurrency where names are insufficient.
- API type changes normally require `make gen-all`, CRD manifests, deepcopy/client updates, RBAC review, and compatibility tests.
- Do not hand-edit generated output to hide a generator/source mismatch.
- Confirm user-scoped dynamic clients possess every new read/write/watch permission on every path.

## Lifecycle and concurrency

Trace:

- create and readiness;
- partial create rollback;
- invoke and endpoint refresh;
- pause/resume or other intermediate states;
- timeout and cancellation;
- delete, finalizer, owner-reference GC, and Store/index cleanup;
- controller/process restart and reconciliation;
- duplicate, delayed, or reordered events.

Concurrency checks:

- Identify every writer to the same Store entry, CR spec/status, cache, index, or channel.
- Check compare-and-swap/resourceVersion conflicts, retry boundaries, and lost updates.
- Ensure locks are not held across network/Kubernetes calls.
- Verify goroutine ownership, channel close ownership, wait groups, and termination on context cancellation.
- Check timer/ticker stop and drain behavior.
- Ensure idempotency under retries and duplicate reconciliation.
- Distinguish fresh API reads from semantically fresh observations; a GET can still return status for an old generation.

## Errors, context, and resources

- Preserve causes with `%w` where callers use `errors.Is/As`.
- Classify terminal errors such as forbidden/invalid separately from transient retryable errors.
- Avoid retrying permanent authorization errors until a generic timeout.
- Give one layer clear timeout ownership; nested arbitrary timeouts create misleading failures.
- Propagate request context into Kubernetes, Store, network, and process calls.
- Map internal errors to stable API status codes without leaking secrets or internals.
- Close bodies, files, pipes, watchers, processes, and temporary resources on every return path.
- Make cleanup idempotent and preserve the primary failure while reporting cleanup failure appropriately.

## Clean code and repository style

- Use concise lowercase package names and existing package boundaries.
- Prefer clear domain names over generic `manager`, `helper`, `data`, or boolean-heavy APIs.
- Keep functions at one level of abstraction where practical.
- Extract an abstraction only when it removes real duplication or centralizes a genuine invariant.
- Avoid wrapper layers that merely rename an existing interface.
- Keep error, logging, context, and test style consistent with neighboring code.
- Public API-facing symbols need useful comments; internal code should be self-explanatory rather than narrated.
- Remove dead branches, obsolete compatibility shims, unused CI steps, and duplicated test setup when the PR makes them unnecessary and removal is in scope.
- Prefer table-driven tests for state, routing, auth, store, and lifecycle matrices.
- Run `gofmt`; inspect `go vet`/lint concerns relevant to the changed surface.

## Tests and CI truthfulness

### Behavior coverage

- Positive behavior proves the intended path.
- Negative behavior covers validation, unauthorized/forbidden, not found, conflict, and dependency failure.
- Boundary behavior covers nil/zero/empty, timeout edge, version skew, and state-transition boundaries.
- Lifecycle behavior covers rollback and cleanup, including presence before absence.
- Concurrency-sensitive changes use focused race tests.
- Public API/manifests/SDK changes include contract or integration coverage where unit tests cannot prove wiring.

### Causal strength

- A regression test should fail without the patch and pass with it when feasible.
- Assertions must observe the invariant, not only an HTTP code, log line, or final absence.
- Fakes must preserve the production behavior being tested; check fake clients, clocks, Store implementations, and reactors.
- Separate trigger reachability from post-trigger consequence. A fake reactor can prove the latter while leaving the former unproven.
- For an unobserved finding, identify the production entry point or writer, the interface contract that permits the trigger, supported preconditions, and whether retry/resync/restart/cleanup self-heals.
- Prefer production-equivalent regressions over arbitrary errors. For Kubernetes optimistic-concurrency paths, create a real Conflict with stale `resourceVersion` or concurrent writers when feasible; use generic injection only after that error class is shown reachable at the boundary.
- A compile-only e2e package check does not validate a live lifecycle.

### CI environment

- Inspect workflow inputs, setup scripts, defaults, environment variables, installed CRDs/controller/image, and feature flags.
- Compare `go.mod` dependency version with the actual runtime/controller version used by e2e.
- Verify the changed test is discovered and runs, rather than merely compiling.
- Distinguish core validation from release, publish, approval, or optional jobs.
- Remove useless or misleading CI evidence from reviewer-facing summaries; keep only checks that change confidence.

## Dependencies and compatibility

- Review API/library version, installed controller/runtime version, CRDs, image, manifests, and e2e as one system.
- Read release notes or migration docs for the exact version range when behavior changed.
- Check minimum Kubernetes/Go/Python versions and pinned CI runners.
- Verify old stored state and old clients when backward compatibility is claimed.
- Confirm generated code and lock files came from the intended toolchain.
- Keep prerequisite upgrades separate when they are independently valuable or repository-wide.
- Do not let test scripts silently install an older version than the code imports.

## Limitations and review confidence

Record what was not verified:

- unavailable cluster/provider/credentials;
- unrun race/e2e/upgrade path;
- uncertain external dependency behavior;
- incomplete issue or maintainer context;
- platform-specific behavior not reproduced.

Label conclusions:

- **Finding:** observed or source-proven reachable defect with concrete consequence and evidence; name which class applies.
- **Risk:** non-blocking concern with partial reachability evidence; state the missing producer, precondition, recovery, or consequence link.
- **Question:** missing contract or intent that changes correctness.
- **Nit:** small maintainability issue; omit unless useful.

Keep mock-only or constructed-state scenarios as questions, evidence gaps, or test-hardening ideas. Do not convert uncertainty into confidence through forceful wording.
