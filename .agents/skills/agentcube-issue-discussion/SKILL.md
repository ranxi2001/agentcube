---
name: agentcube-issue-discussion
description: >-
  Use when working with AgentCube GitHub issues, discussions, proposals, or
  issue comments: fetch full issue/PR conversation context, summarize community
  discussion in Chinese, draft English replies, cross-link related issues/PRs,
  and prepare benchmark/proposal comments that follow AgentCube community format.
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
8. Include cross-links using GitHub `#123` references and short context.
9. If the same issue/PR analysis requires repeated API calls, version matrices, log extraction, or manual filtering, add or improve a script under this skill before the next similar run.

## Fetching Thread Context

Use the compact briefing script first:

```bash
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 386
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 379 --repo volcano-sh/agentcube
```

It prints a token-efficient Markdown brief with metadata, assignees, `/assign` signals, body snippet, issue comments, and PR files/commits/review comments when applicable.

Use the full JSON script when exact raw context is needed:

```bash
python3 .agents/skills/agentcube-issue-discussion/scripts/fetch_thread.py 365
python3 .agents/skills/agentcube-issue-discussion/scripts/fetch_thread.py 366 --repo volcano-sh/agentcube
```

The script prints JSON with the issue/PR object, comments, PR files, PR commits, and PR review comments.

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

Use this when drafting upstream comments:

```md
Thanks for the discussion here. My understanding is:

- ...

Based on #<related>, I think this issue is aligned with ...

Proposed next step:

1. ...
2. ...
3. ...

I can help with:

- ...
```

For benchmark comments:

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
