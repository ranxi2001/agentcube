**What type of PR is this?**

/kind cleanup

**What this PR does / why we need it**:

This nominates `RainbowMango` as a root reviewer and approver based on repository-wide stewardship already being performed:

- Turns broad project needs into reviewable work: the v0.2.0 tracker (#386) triages focused tasks, while #430 defines the boundary between Kubernetes-owned resource pools and AgentCube-owned session lifecycle.
- Keeps changes focused and requires rationale for exceptions: [split](https://github.com/volcano-sh/agentcube/pull/250#issuecomment-4429092718) PicoD request-body hardening into #326; in #396 requested a [predictable schedule](https://github.com/volcano-sh/agentcube/pull/396#discussion_r3517204392) and accepted [grouping](https://github.com/volcano-sh/agentcube/pull/396#discussion_r3517411007) after the author explained the noise-reduction trade-off.
- In the ongoing #431 review, challenged [API extensibility](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3584314319), [field contracts](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3584355665), [status-write scaling](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3579040898), and [manifest recovery](https://github.com/volcano-sh/agentcube/pull/431#discussion_r3585155189). The current head removes `NodeSelector` and adopts `corev1.ResourceList` and Lease heartbeat; the proposal and several public-contract threads remain open.
- Confirmed the multi-architecture build bottleneck against Docker's `FROM --platform` contract in [#419](https://github.com/volcano-sh/agentcube/issues/419#issuecomment-4901072888), before #420 merged the `$BUILDPLATFORM` fix.

**Which issue(s) this PR fixes**:

NONE

**Special notes for your reviewer**:

- Scope/validation: the two entries are case-insensitively sorted; YAML parsing, ordering, and uniqueness checks pass.
- Governance: this nominates both roles together; existing root approvers should confirm the applicable [Volcano membership, sponsorship, and role-tenure requirements](https://github.com/volcano-sh/community/blob/master/community-membership.md).
- AI assistance: Codex helped audit the public contribution history; I reviewed the two-line change and this text.

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
