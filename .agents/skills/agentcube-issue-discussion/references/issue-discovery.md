# AgentCube Issue Discovery

Use this reference when the task is to find useful issue/PR work rather than analyze a known issue.

The objective is not to invent features or maximize issue count. Find a concrete mismatch between an observable path and its intended contract, prove it is reachable, and verify that nobody already owns the same work.

## Discovery Surfaces

Choose one surface per focused investigation. Do not skim every surface shallowly.

| Surface | What to compare | High-signal probe |
| --- | --- | --- |
| Merged PR residual scope | What the PR fixed vs explicitly deferred | Extract `follow-up`, `future`, `separate`, version pins, review leftovers, and non-goals; revisit when the dependency releases |
| Runnable user journey | README/example promise vs clean execution | Run an example exactly as documented; check image, service DNS, health probes, payload, response, and cleanup |
| TODO / fallback | Reachable placeholder vs documented capability | Search `TODO`, `FIXME`, `placeholder`, `not implemented`, and fallback logs; prove the path is user-selectable before treating it as work |
| Field propagation | Producer field vs every consumer | Trace SDK argument -> JSON -> server DTO -> builder/controller -> Store/status; use a sentinel value different from the default |
| Parallel-path parity | Equivalent paths with different behavior | Compare direct/warm, AgentRuntime/CodeInterpreter, SDK/CLI, create/adopt, and clean-install/upgrade paths for defaults and validation |
| Lifecycle symmetry | Resource acquisition vs release | Build a create/attach/invoke/close/stop/delete/context-exit matrix and distinguish owned from attached resources |
| Cache invalidation | Cache identity vs mutable inputs | List key, frozen value fields, expiry, invalidation, and rotation triggers; rotate token/config while keeping the key stable |
| Configuration fan-out | Flag/default vs deploy/runtime behavior | Trace flag -> Helm values -> template args/env -> middleware -> downstream identity/RBAC; include TLS, auth, timeout, and feature gates |
| CI truth | Green/red conclusion vs executed contract | Inspect failed logs, skipped steps, suspiciously short jobs, path filters, event types, and command dependency closure |
| Workflow variable fan-out | One variable consumed by incompatible formats | Trace branch/tag/PR values into image tags, SemVer, artifact names, cache keys, and publication decisions |
| CI latency | Successful run vs avoidable long tail | Record top-three step durations; split dominant steps and run a one-variable A/B experiment |
| Algorithm boundaries | Happy path vs order/tie/boundary inputs | Test input permutation, overlapping prefixes, exact boundary, adjacent strings, empty/root/default, and deterministic ties |
| Architecture hot path | One request cost vs target scale | Count API calls, persisted objects, reconciles, scheduling hops, and status writes; multiply by burst/QPS and lifecycle duration |
| Dependency evolution | Pinned integration vs latest stable contract | Compare release notes, migration guide, API/storage versions, upgrade behavior, and lifecycle regressions; keep migration separate from a minimal compatibility patch |

## Evidence-First Loop

1. **Refresh community state.** Read issues and PRs created or materially updated since the last scan. Check assignees, `/assign`, same-topic branches/PRs, cross-references, and maintainer blockers.
2. **Pick one real surface.** Start from a failed run, working feature, example, merged PR, public field, cache, configuration path, or dependency release. Do not start from a desired PR title.
3. **Capture the observation.** Preserve the exact command, input, log, duration, response, or source invariant that raised suspicion.
4. **Trace the contract end to end.** Identify the producer, transport/type, consumer, state owner, cleanup path, and documented expectation. Compare sibling paths when they should be symmetric.
5. **Prove reachability and impact.** Apply the Bug Reachability Gate. Check defaults, validation, admission, locks, retries, resync, restart, self-healing, feature gates, and supported user operations.
6. **Search for ownership and precedent.** Search issue text, PR bodies, branches, commits, discussions, release notes, and umbrella tasks. An empty assignee is not proof that work is unowned.
7. **Choose the artifact.** Use a bug for observed or source-proven reachable wrong behavior, an enhancement for a missing accepted capability, a discussion for an unmeasured architecture direction, and review/test evidence when someone already owns implementation.
8. **Bound the first change.** Name the smallest behavior change, focused tests, compatibility/non-goals, and residual follow-ups. Reject candidates that require an unresolved product or security contract.
9. **Record locally first.** Save the discovery card and evidence in the relevant internship report/TODO. Upstream issue, comment, `/assign`, or PR creation still requires exact user confirmation.

## Discovery Card

Fill this before recommending a new issue or PR:

```md
### Candidate

- Surface:
- Observable trigger:
- Actual behavior:
- Expected contract and source:
- Producer -> transport/type -> consumer -> state owner:
- Supported production path:
- Recovery / retry / cleanup behavior:
- Decisive evidence:
- Related issue / PR / commit search:
- Current owner / assignee / active branch:
- Artifact class: observed bug / reachable latent bug / enhancement / discussion / review evidence
- Smallest change:
- Focused validation:
- Compatibility and non-goals:
- Unknowns requiring maintainer decision:
```

## Decision Gates

Recommend implementation only when all gates pass:

- **Evidence:** at least one decisive source, runtime, CI, or contract observation exists.
- **Reachability:** a supported producer/path can create the precondition; a mock alone is insufficient.
- **Ownership:** no assignee, active same-topic PR, or maintainer-designated owner is already implementing it.
- **Direction:** the change does not silently decide an unresolved security, API, ownership, or architecture contract.
- **Scope:** the first PR can be focused, reviewed, and validated independently.
- **Validation:** focused success, failure, boundary, and cleanup tests are feasible in the available environment.

If ownership fails, switch to review, reproduction, missing tests, or second-round semantic validation. If direction fails, ask a bounded design question. If evidence or reachability fails, keep investigating and do not publish a bug claim.

## Cadence

- At every substantive work loop: refresh recent issues/PRs and default-branch CI, then select at most one discovery surface.
- After every merged or reviewed PR: extract residual scope and inspect whether the review exposed a general repository issue.
- Weekly: run one clean example journey, one public-field or lifecycle matrix, one CI truth/latency audit, and one dependency-release check.
- Prefer a few proven candidates over a quota. A week with no new issue is valid when all visible work is owned or evidence gates fail.

## Interpretation Guardrail

Public timelines can prove the triggering signal, code mismatch, issue/PR timing, and later discussion. They usually cannot prove the author's private thought process or exact search command. Describe reconstruction as an inference unless the author explicitly states how the problem was found.
