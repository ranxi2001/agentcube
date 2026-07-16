**What type of PR is this?**

/kind cleanup

**What this PR does / why we need it**:

This adds `@RainbowMango` to the root reviewers and approvers, formalizing responsibilities already exercised across AgentCube. As of July 16, 2026, GitHub indexes 23 distinct non-authored AgentCube PRs reviewed by RainbowMango (19 human-authored and four Dependabot PRs); 19 carry an `APPROVED` review and 18 of those are merged. Deeper reviews include 28 inline comments: 20 original threads and eight follow-up replies. The examples below show the quality behind those numbers:

- Organizes release and proposal work through two authored issues: created #386 as the v0.2.0 umbrella for proposal triage, ownership, and merge tracking; it currently records eight completed work items. Framed the long-term boundary between Kubernetes-owned resource pools and AgentCube-owned session lifecycle in #430 and opened it for community design work.
- Keeps changes focused and requires rationale for exceptions: [split](https://github.com/volcano-sh/agentcube/pull/250#issuecomment-4429092718) PicoD request-body hardening into #326; in #396 requested a [predictable schedule](https://github.com/volcano-sh/agentcube/pull/396#discussion_r3517204392) and accepted [grouping](https://github.com/volcano-sh/agentcube/pull/396#discussion_r3517411007) after the author explained the noise-reduction trade-off.
- Across 17 original threads in the ongoing #431 review, challenged [API extensibility](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3584314319), [field contracts](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3584355665), [status-write scaling](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3579040898), and [manifest recovery](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3585155189). The author removed `NodeSelector` and adopted `corev1.ResourceList` and Lease heartbeat; remaining contract questions stay open.
- Confirmed the multi-architecture build bottleneck against Docker's `FROM --platform` contract in [#419](https://github.com/volcano-sh/agentcube/issues/419#issuecomment-4901072888), before #420 merged the `$BUILDPLATFORM` fix.

**Which issue(s) this PR fixes**:

NONE

**Special notes for your reviewer**:

- Scope/validation: only root `OWNERS` changes; runtime behavior and APIs are unchanged. The entries are case-insensitively sorted; YAML parsing, ordering, and uniqueness checks pass.
- AI assistance: Codex helped audit the public contribution history; I reviewed the two-line change and this text.

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
