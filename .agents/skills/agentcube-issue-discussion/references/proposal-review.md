# Proposal Review Workflow

Use this reference for AgentCube formal proposal PRs and architecture discussion reviews.

## Review Posture

Treat a proposal as a design manuscript, not as code to mechanically nitpick. The first goal is to reconstruct the author's model accurately. Only draft an upstream comment after the reviewer can explain the proposal's motivation, non-goals, object model, control/data flow, failure handling, test plan, and relation to existing issues.

Good proposal review contributions are often text improvements:

- making scope boundaries explicit;
- asking for missing assumptions;
- separating goals from implementation details;
- clarifying API semantics before code exists;
- improving test plans and rollout/migration plans;
- pointing out where a term, diagram, state machine, or field would mislead future implementers.

## Understand-First Pass

Before proposing changes:

1. Fetch the full PR/issue context with `thread_brief.py`; fetch full JSON only if exact review comments, commits, or timeline details are needed.
2. Read the proposal body as a whole before line-level notes.
3. Identify the parent issue, previous proposals, linked PRs, and whether this proposal should close or only reference them.
4. Write a Chinese internal summary with:
   - motivation;
   - goals and non-goals;
   - proposed API/object model;
   - lifecycle/state machine;
   - component ownership;
   - failure and recovery paths;
   - test and rollout plan;
   - open questions.
5. Compare the proposal against the project template in `docs/proposals/proposal-template.md`.
6. Compare the proposal against existing AgentCube API groups, controllers, runtime concepts, and prior internship reports only after the proposal's own model is clear.

Do not draft upstream feedback until the internal summary can be stated without relying on vague phrases like "seems risky" or "maybe inconsistent".

## CNCF-Style Proposal Review Checklist

Proposal review is different from code review. The core question is not whether the code is correct, but whether the design is worth doing, fits the project, and can be maintained long term.

Use this checklist before reviewing details:

| Check | Review question |
| --- | --- |
| Problem | Why should the project solve this? Is it a real user problem, not only an edge case? Is there user feedback, benchmark data, incident history, or a concrete scenario? |
| Goals | Are the goals and non-goals explicit? Is the proposal expanding beyond the stated scope? |
| Alternatives | Which alternatives were considered? Why not reuse the current API, controller, interface, or implementation? |
| Design | Are API names, interfaces, data flow, component responsibilities, ownership, and state transitions simple and consistent? |
| Backward compatibility | Will existing users, API clients, CRDs, Helm values, SDKs, or configs break? |
| Migration | How do existing users upgrade? Is there a deprecation, conversion, defaulting, or migration path? |
| Performance | Does the proposal add latency, memory, CPU, storage, API-server load, controller churn, or scheduling pressure? Is there a benchmark or validation plan? |
| Security | Does it add new HTTP endpoints, credentials, RBAC, TLS, secrets, node-local sockets, tenant boundaries, or privilege assumptions? |
| Maintainability | Does it add another code path, controller, abstraction, or long-term support burden? Can logic be shared with existing components? |
| Test plan | Are unit, integration, e2e, benchmark, rollback, and failure-path tests mapped to the design risks? |

For the design section, inspect these subareas:

- API: breaking changes, naming consistency, defaults, validation, examples, and versioning.
- Interfaces: whether a new interface is necessary or an existing abstraction can be extended.
- Data flow: user request path, controller path, runtime path, duplicate writes, loops, and unnecessary hops.
- Ownership: which component reads and writes each field, and whether responsibilities are mixed.
- State machine: valid transitions, retries, terminal states, stale states, and observability.

## Review Matrix

Use this matrix to classify findings:

| Category | Question |
| --- | --- |
| Problem fit | Does the proposal solve the parent issue's actual problem? |
| Scope | Are goals, non-goals, and `Fixes`/`Refs` links consistent? |
| Terminology | Are names, API groups, and concepts aligned with AgentCube conventions? |
| API contract | Are fields, defaults, mutability, validation, status ownership, and versioning clear? |
| State machine | Are phase transitions, stale states, retries, and terminal states unambiguous? |
| Ownership | Is each field/component written by one clear owner? |
| Failure modes | Are node loss, controller restart, stale heartbeat, partial apply, deletion, and rollback handled? |
| Security | Are credentials, RBAC, node-local sockets, tenant boundaries, and privilege assumptions explicit? |
| Compatibility | Are Kubernetes version gates, feature gates, migration, and upgrade paths clear? |
| Testability | Can each risky claim be verified by unit, integration, e2e, or targeted spike tests? |
| Implementation slices | Can the proposal be implemented in small reviewable PRs? |

## AgentCube Historical Review Patterns

When reviewing AgentCube proposals, compare against prior design PR discussion patterns before drafting comments:

- PR #28 showed that CLI proposals are reviewed as user-facing contracts: command semantics, provider-specific behavior, validation, credentials, and status/wait behavior must be precise.
- PR #29 showed that component proposals must keep role boundaries clear. PicoD could not be described as a sandbox manager if its real role was code execution inside a sandbox.
- PR #38 showed that resource-pool proposals must separate user API, admin API, and apiserver/controller internal details. Do not expose raw Kubernetes namespaces, paths, sockets, or pool internals unless the API boundary is intentional.
- PR #44 showed that new API proposals should answer "why a new API instead of reusing the existing resource?" and keep docs consistent with Go API types when both are present.
- PR #80 showed that system-level proposals are mainly reviewed for product model and component boundaries: user entrypoint, Router vs WorkloadManager, session meaning, and why separate resource concepts exist.
- PR #114 showed that security proposals need source-of-truth, atomicity, recovery, token/key rotation, and follow-up issue boundaries.
- PR #241 showed that security/performance trade-offs must map to exact paths and latency budgets, for example user identity propagation, mTLS/JWT choice, certificate rotation, and low-latency runtime bootstrap.

Use these local patterns to turn vague concerns into precise questions:

- "Should this be user/admin-facing API, or an implementation detail behind AgentCube?"
- "What existing AgentCube or agent-sandbox resource was considered, and why is a new API needed?"
- "Which component owns this field, and is there a second source of truth?"
- "What happens after partial success or stale status?"
- "Which risky claim needs a targeted spike instead of only a controller unit test?"
- "Is the proposal mixing installation guide, future work, and the core design contract?"

## Comment Threshold

Prefer no upstream comment when the finding is:

- only personal preference;
- already covered by an active maintainer discussion;
- only a spelling/style issue unless it affects meaning;
- based on speculation without source, code, or test evidence;
- too broad to be actionable.

Prefer an upstream PR comment when the finding is:

- a scope/closure issue such as `Fixes #x` closing a broader discussion too early;
- a missing assumption that could cause incompatible implementations;
- an API/status/state-machine ambiguity;
- a test-plan gap for a risky mechanism;
- a text inconsistency that would mislead implementers;
- a missing compatibility, rollout, security, or observability section.

Ask questions before suggesting rewrites when the author may have unstated context. Suggest concrete text changes only when the intended direction is clear.

## Comment Shape

Keep proposal review comments short and structured:

```md
Thanks for putting this proposal together. My understanding is that this PR covers <scope>, while <out-of-scope area> remains in #<issue>.

I have one question about <topic>:

- <specific ambiguity or risk>
- Why it matters: <effect on implementation/review/testing>
- Suggested clarification: <small text or test-plan addition>
```

Use concrete review language instead of vague preference:

- Problem: "Could you elaborate on the user scenario this proposal is addressing? Do we have benchmark data, user feedback, or an issue showing this is a recurring problem?"
- Scope: "This seems to expand beyond the original goals. Could we narrow the first version to <scope> and leave <future area> as a non-goal?"
- Alternatives: "Why introduce a new interface/API here instead of extending the existing <abstraction>?"
- Trade-off: "What are the trade-offs between this approach and reusing the current implementation?"
- Compatibility: "Could you describe the migration path for existing users? Is there a compatibility strategy for <API/config/CRD/SDK>?"
- Maintainability: "This appears to introduce another code path to maintain. Can this logic be shared with the existing implementation?"
- Test plan: "Could the proposal map this risk to a focused unit/integration/e2e/benchmark test?"

If there are several unrelated points, split them into separate comments or group them under clear headings. Avoid long omnibus comments unless the user explicitly asks for a full review draft.

## Text Improvement Patterns

Useful proposal text patches often add:

- `tracking-issue: "#123"` in front matter;
- `Refs #123` instead of `Fixes #123` for broad discussions;
- a "Source of truth" table for status/spec fields;
- a "Failure and recovery" table;
- an explicit "Version / feature gate compatibility" table;
- a "Validation plan" with targeted spike tests;
- an "Open questions" section for unresolved design choices;
- a phased implementation plan that maps phases to reviewable PRs.

## Proposal Comment Draft Checklist

Before showing a draft to the user:

1. Confirm the target PR/issue number and current assignee/reviewer state.
2. State whether the comment is a question, suggestion, or blocking concern.
3. Include only facts you can cite from the proposal, repo, official docs, or local test evidence.
4. Keep Chinese reasoning in `internship-reports/`; upstream text must be English.
5. Do not post or mention maintainers without explicit user confirmation.
