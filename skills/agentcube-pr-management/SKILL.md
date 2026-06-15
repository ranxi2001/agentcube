---
name: agentcube-pr-management
description: >-
  Use when preparing, validating, submitting, updating, or reviewing AgentCube
  upstream pull requests: enforce fork/upstream branch hygiene, fill the official
  PR template, map files to OWNERS, run appropriate tests, disclose AI
  assistance, track review state, and avoid mixing internship reports with
  upstream PR branches.
---

# AgentCube PR Management Skill

Use this skill for AgentCube upstream PR work: branch prep, template filling, issue linking, test selection, OWNERS mapping, review tracking, and update strategy.

## Required Context

- Follow `AGENTS.md` fork/upstream workflow.
- Follow `internship-reports/open-source-contribution-format-standard.md`.
- Use the community role table there to separate human reviewer guidance from automation bot, CI, merge gate, and AI reviewer comments.
- Upstream PRs must use English.
- Use clean topic branches from `upstream/main`; do not open PRs from fork `main`.
- Keep internship reports, raw benchmark results, and Chinese-only notes out of upstream PRs unless explicitly intended.

## Branch Workflow

```bash
git fetch upstream main
git switch -c <kind>/<short-topic> upstream/main
```

Examples:

```bash
git switch -c fix/token-cache-exp upstream/main
git switch -c docs/snapstart-benchmark-scope upstream/main
```

After changes:

```bash
git status
git diff --stat
git push origin <branch>
```

Do not push to `upstream`.

## PR Planning Checklist

Before editing code:

- Identify issue number or discussion link.
- Check if issue has assignee, `/assign` comment, or active PR; record it as `PR 认领 @`.
- If the issue is actively assigned to someone else, do not start an overlapping PR; choose review/testing feedback, ask whether help is needed, or pick another issue.
- Check whether change touches API/CRD/generated code.
- Check whether change touches Helm, SDK, docs, tests, or e2e.
- Pick one PR kind:
  - `/kind bug`
  - `/kind cleanup`
  - `/kind enhancement`
  - `/kind security`
  - `/kind documentation`
  - `/kind feature`

## Test Selection

Use the smallest relevant test set first, then broader checks if needed.

| Change area | Minimum tests |
| --- | --- |
| `pkg/workloadmanager` bugfix | `go test ./pkg/workloadmanager` |
| `pkg/router` | `go test ./pkg/router` |
| `pkg/store` | `go test ./pkg/store` |
| API / CRD | `make gen-all` or `make gen-check`, plus relevant Go tests |
| Helm chart | `make helm-template` and `make helm-lint` if available |
| Python SDK | `cd sdk-python && python -m pytest tests/ -v` |
| Broad Go change | `make test` |
| Race/concurrency | `go test -race ./...` or targeted package |

If a test cannot run locally, record the command and exact blocker.

## OWNERS Mapping

Use `OWNERS` by changed path:

| Path | OWNER file |
| --- | --- |
| `pkg/workloadmanager/` | `pkg/workloadmanager/OWNERS` |
| `pkg/router/` | `pkg/router/OWNERS` |
| `pkg/apis/` | `pkg/apis/OWNERS` |
| `docs/` | `docs/OWNERS` |
| `manifests/` | `manifests/OWNERS` |
| `test/` | `test/OWNERS` |

Let the bot guide exact approval requirements; do not over-tag reviewers unless needed.

## PR Template

Use this structure:

````md
**What type of PR is this?**

/kind bug

**What this PR does / why we need it**:

<problem and change summary>

**Which issue(s) this PR fixes**:
Fixes #<issue>

**Special notes for your reviewer**:

- Scope:
- Tests:
- AI assistance: Used Codex to help inspect code, draft tests, and prepare this PR. I reviewed and validated the changes.

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
````

For partial work use `Refs #<issue>` instead of `Fixes #<issue>`.

## Local Validation Record

Keep a local record in internship reports:

```md
## PR Validation

- Branch:
- Issue:
- Changed files:
- Tests run:
- Results:
- Blockers:
- Reviewer notes:
```

## Review Management

When review comments arrive:

1. Read all comments first.
2. Classify commenters by role: human maintainer/reviewer, PR author, contributor, automation bot, CI bot, merge gate, or AI reviewer.
3. Group actionable comments by category: correctness, tests, style, docs, generated code, scope.
4. Prioritize human maintainer/reviewer comments; use AI reviewer comments as a checklist only after validating the issue yourself.
5. Treat bot comments as process or validation state, such as missing `approved`, `lgtm`, failed CI, or OWNER requirements.
6. Apply fixes in small commits.
7. Reply directly and specifically.
8. Do not use AI-generated reviewer replies verbatim; author should respond.

Useful response format:

```md
Thanks, updated in the latest push.

Change:
- ...

Validation:
- ...
```

For disagreement:

```md
Thanks for pointing this out. My understanding is ...

I considered ...

Would you prefer ...?
```

## PR Status Script

Use the script to inspect a PR:

```bash
python3 skills/agentcube-pr-management/scripts/pr_status.py 379
```

It prints title, state, labels, files, commits, comments count, and review comments summary.

## Guardrails

- Do not merge unrelated formatting with behavior changes.
- Do not include benchmark raw JSON unless upstream asked for it.
- Do not add new dependencies casually.
- Do not change CRDs without generated files.
- Do not mark an issue fixed unless the PR fully addresses it.
- Do not duplicate work on an issue with an active `PR 认领 @`; record the owner and switch to review/test feedback unless the maintainer asks for a separate PR.
- Do not treat AI reviewer or automation bot comments as maintainer consensus.
- If a first-time contributor workflow needs `ok-to-test`, mention it in local notes; do not spam maintainers.
