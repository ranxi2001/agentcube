---
name: agentcube-issue-discussion
description: >-
  Use when working with AgentCube GitHub issues, discussions, proposals, or
  issue comments: fetch full issue/PR conversation context, summarize community
  discussion in Chinese, draft concise English issues and replies, cross-link
  related issues/PRs, and prepare benchmark/proposal comments that follow
  AgentCube community format.
---

# AgentCube Issue Discussion Skill

Use this skill for AgentCube upstream issue/discussion work: reading full thread context, extracting consensus, translating to Chinese for internship notes, drafting English comments, and linking related issues/PRs.

## Required Context

- Follow `internship-reports/open-source-contribution-format-standard.md` before drafting upstream-facing text.
- Use its “社区角色与评论权重” section to classify human maintainers, contributors, automation bots, merge gates, CI bots, and AI reviewers.
- Upstream comments must be in English.
- Chinese analysis belongs in `internship-reports/`.
- Search for related issues/PRs before proposing a new direction.
- Do not invent maintainer consensus; distinguish explicit maintainer comments from inference.
- For formal design/proposal PR review, read `references/proposal-review.md` before drafting comments.
- Treat reviewer-facing text as an index to evidence, not a copy of the internship report. Read `references/concise-issue-writing.md` before drafting a new issue or non-trivial comment.
- When learning from a contributor's public writing history, compare multiple artifact types and read `references/concise-issue-writing.md` for the evidence/limitation gate; do not turn one person's template usage into a repository rule.
- Do not post an issue, comment, `/assign`, reviewer request, or maintainer mention without explicit user approval of the exact text and target.

## Workflow

1. Identify target issue/PR numbers and related links.
2. Fetch compact thread context first:
   - issue/PR title, body, state, labels, assignees
   - `/assign` comments and current `PR 认领 @` owner
   - issue comments
   - if PR: review comments, changed files, commits
3. Fetch full JSON only when the compact brief is insufficient for quoting, code review, or exact timeline checks.
4. Extract:
   - problem statement
   - proposed solutions
   - participant roles and comment weight
   - maintainer guidance
   - open questions
   - blocked/duplicate/conflicting work
   - related issue/PR graph
5. If an issue has an active assignee or linked open PR, recommend review/testing feedback instead of duplicate implementation.
6. Produce Chinese internal summary first when the user is planning or discussing.
7. Produce English upstream comment only when asked to draft or post.
8. Run the concise-first publishing gate below before presenting exact text for approval.
9. Include cross-links using GitHub `#123` references and short context.
10. If the same issue/PR analysis requires repeated API calls, version matrices, log extraction, or manual filtering, add or improve a script under this skill before the next similar run.

## Concise-First Publishing Gate

Before presenting an issue or comment for approval:

1. Select the artifact type first: enhancement, bug, question, proposal, benchmark, ordinary comment, or review finding.
2. Lead with the outcome, bounded impact, or exact maintainer decision needed; do not recap the full thread.
3. Keep one decisive evidence item per material claim and explain why each link matters.
4. Keep chronology, complete logs/JSON, full benchmark tables, and broad source-reading notes in `internship-reports/` unless they change an upstream decision.
5. Measure reviewer-visible text after hidden template comments are removed:

```bash
python3 .agents/skills/agentcube-issue-discussion/scripts/draft_metrics.py <draft.md> --limit 250
```

Use soft review triggers:

- Enhancement/question: 80-250 visible words.
- Reproducible bug: usually 120-400 visible words before irreducible logs/manifests.
- Ordinary comment/review: 40-180 visible words; review again above 250.

Proposal, benchmark, API/CRD, security, and cross-component reviews may be longer when the structure remains scan-first and the extra evidence changes the decision. When requesting posting approval, include visible word/nonblank-line counts and name the long-form reason when the draft exceeds the ordinary trigger.

## Proposal Review

Use `references/proposal-review.md` when the target is a formal proposal under `docs/proposals/`, a large design PR, or a discussion where the user asks how to review a proposal. It defines the understand-first review workflow, comment thresholds, and proposal text improvement patterns.

## AgentCube Prow Commands

- For `kind/*` labels on AgentCube issues or PRs, use a Prow comment such as `/kind enhancement`, `/kind feature`, `/kind bug`, or `/kind documentation`.
- Do not use `gh issue edit --add-label` unless the token has upstream label permissions; fork contributors normally get `AddLabelsToLabelable` permission errors.
- Do not use `/label kind/enhancement` for kind labels. In this repository, `/label` may be restricted to labels configured in Prow, while `/kind enhancement` correctly maps to `kind/enhancement`.
- Use `/assign` when taking ownership of an issue or PR, then verify assignee state from the issue metadata or timeline.

## Fetching Thread Context

Use the compact briefing script first:

```bash
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 386
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 379 --repo volcano-sh/agentcube
```

It prints a token-efficient Markdown brief with metadata, assignees, `/assign` signals, body snippet, issue comments, and PR files/commits/review comments when applicable. For PRs, it also uses GraphQL to summarize active review threads separately from unresolved-but-outdated threads; this requires `GITHUB_TOKEN` and degrades to an explicit unavailable notice when the token is absent.

Use the full JSON script when exact raw context is needed:

```bash
python3 .agents/skills/agentcube-issue-discussion/scripts/fetch_thread.py 365
python3 .agents/skills/agentcube-issue-discussion/scripts/fetch_thread.py 366 --repo volcano-sh/agentcube
```

The script prints JSON with the issue/PR object, comments, PR files, PR commits, and PR review comments.

For a sampled cross-repository study of one contributor's issue/PR writing, use:

```bash
python3 .agents/skills/agentcube-issue-discussion/scripts/contributor_writing_history.py \
  --author <login> owner/repo#123 owner/other-repo#456
```

The script removes hidden template comments and known generated-summary blocks, reports body structure/size, records outcome, and shows the first external human response. Select samples before running it: include bugs, features/proposals, umbrella trackers, maintenance work, different years, and at least one cross-repository item. Treat merged/closed outcome as context rather than proof that every writing choice was good.

If network/API fails, use `curl` against:

```text
https://api.github.com/repos/volcano-sh/agentcube/issues/<number>
https://api.github.com/repos/volcano-sh/agentcube/issues/<number>/comments
https://api.github.com/repos/volcano-sh/agentcube/pulls/<number>
https://api.github.com/repos/volcano-sh/agentcube/pulls/<number>/files
https://api.github.com/repos/volcano-sh/agentcube/pulls/<number>/comments
https://api.github.com/repos/volcano-sh/agentcube/pulls/<number>/commits
```

## Chinese Summary Format

```md
## Issue / PR 概览

- 编号：
- 标题：
- 状态：
- 标签：
- PR 认领 @：
- 相关链接：

## 讨论脉络

1. ...

## 参与者与评论权重

- 真人维护者 / reviewer：
- PR 作者 / issue 作者：
- 其他贡献者：
- 自动化 bot / CI：
- AI reviewer：

## 维护者明确意见

- @user: ...

## 当前共识

- ...

## 尚未解决的问题

- ...

## 对我们的影响

- ...

## 建议下一步

1. ...
```

## English Comment Draft Format

Use this compact default for upstream comments:

```md
I verified <scenario> at `<sha>`.

- Observation: <result>
- Evidence: <test, log, code path, or benchmark case>
- Impact: <bounded behavior>

Suggested next step: <one action or question>.
```

Use the longer benchmark structure only when the environment and percentile fields materially affect comparison. Otherwise keep the complete record local and publish a compact result, limitation, and next step.

```md
## Benchmark scope

- What is measured:
- What is not measured:

## Environment

- OS:
- Kernel:
- glibc:
- CPU / vCPU:
- Kubernetes:
- Runtime / RuntimeClass:
- `/dev/kvm`:
- virtualization flags:

## Results / observations

| Case | p50 | p95 | p99 | success rate | notes |
| --- | ---: | ---: | ---: | ---: | --- |

## Suggested next step

- ...
```

## Cross-Linking Rules

- Use `#267`, `#365`, `#366` for same-repo references.
- Explain why each link is relevant; do not dump links.
- For compound discussions, state relationship:
  - “aligned with #366”
  - “benchmark tracker for #365”
  - “motivated by #267”
  - “blocked by #379 implementation direction”

## Example Interpretation Pattern

For a maintainer comment like:

> The Firecracker proposal is useful as motivation, but near-term implementation should align with #366 SnapStart.

Summarize as:

- Explicit maintainer guidance: do not start a competing direct Firecracker backend now.
- Near-term direction: validate Kubernetes-native SnapStart design in #366/#379.
- Useful contribution path: benchmark scenarios from #267/#365, fallback behavior, N-way fan-out metrics.

## Guardrails

- Never claim we will implement something unless user asks to commit to it.
- Do not post comments without explicit user instruction.
- Do not treat automation bot or AI reviewer comments as maintainer consensus.
- Always report assignee state as `PR 认领 @` in planning tables or summaries.
- If someone is assigned or an active PR exists, recommend review/test feedback instead of duplicate implementation.
- Mention AI assistance in PR reviewer notes when used for upstream PR prep.
- Do not paste file inventories, complete test matrices, chronological work logs, bot summaries, raw benchmark JSON, or dynamic CI status into an ordinary issue/comment.
- Do not shorten away benchmark comparability, API/CRD compatibility, a security boundary, or a proposal decision merely to hit a word target.
