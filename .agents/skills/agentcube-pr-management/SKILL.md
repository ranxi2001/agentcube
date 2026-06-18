---
name: agentcube-pr-management
description: >-
  Use when preparing, validating, submitting, updating, or reviewing AgentCube
  upstream pull requests: enforce fork/upstream branch hygiene, fill the official
  PR template, map files to OWNERS, run appropriate tests, disclose AI
  assistance, track review state, read other contributors' PR code/proposals
  before commenting, and avoid mixing internship reports with upstream PR
  branches.
---

# AgentCube PR Management Skill

Use this skill for AgentCube upstream PR work: branch prep, template filling, issue linking, test selection, OWNERS mapping, review tracking, and update strategy.

## Required Context

- Follow `AGENTS.md` fork/upstream workflow.
- Follow `internship-reports/open-source-contribution-format-standard.md`.
- Use the community role table there to separate human reviewer guidance from automation bot, CI, merge gate, and AI reviewer comments.
- Upstream PRs must use English.
- Use clean topic branches from `upstream/main`; do not open PRs from fork `main`.
- Do not open an upstream PR, draft PR, WIP PR, issue, or upstream review/comment without explicit user confirmation immediately before posting. Prepare the branch, diff, tests, and exact body/comment locally first, then ask for approval.
- Prefer fork-only validation for CI experiments. Use fork branches, fork PRs, local Actions, or local tests to validate uncertain fixes before involving `volcano-sh/agentcube`.
- Open upstream PRs only when the change is ready for community review or the user explicitly asks to involve upstream. Do not create upstream PRs merely to trigger CI for a private validation path.
- Keep internship reports, raw benchmark results, and Chinese-only notes out of upstream PRs unless explicitly intended.
- For other contributors' PRs, do not draft comments, conclusions, or review suggestions until you have read the PR body, changed files, proposal/design docs, key implementation/tests, and existing human review discussion.
- For read-only analysis of another PR or issue, keep notes local unless a maintainer response is genuinely needed and the user approves posting.
- Prefer script-first PR analysis. If status checks, file summaries, review comment filtering, CI state, or branch hygiene checks are repeated across PRs, improve `.agents/skills/agentcube-pr-management/scripts/` and update this skill instead of redoing the same manual analysis.

## Upstream Posting Gate

Before any upstream-facing action, stop and ask the user to approve the exact action:

- Creating an upstream PR, including draft or WIP PRs.
- Opening an issue or proposal.
- Posting an issue comment, PR comment, review comment, `/assign`, `/lgtm`, reviewer request, or maintainer mention.
- Pushing to an upstream-facing PR branch when the push will notify reviewers or update an open upstream PR.

Approval request must include:

- Target repo and branch.
- Whether it is upstream-facing or fork-only.
- Title and full body/comment, using the official template when applicable.
- Diff summary and tests run.
- Why upstream attention is needed now.

If the goal is only to run CI, use fork CI first. Do not ask maintainers to validate work that can be validated in the fork.

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
git commit -s -m "<kind>: <summary>"
git push origin <branch>
```

Do not push to `upstream`.

All upstream PR commits must satisfy DCO. Use `git commit -s` by default. If a commit is missing `Signed-off-by` and the branch is only used by the author, repair it with `git commit --amend --no-edit --signoff` for the latest commit or `git rebase HEAD~N --signoff` for multiple commits, then update the PR branch with `git push --force-with-lease`.

## Follow-up Fix Branching

When an open PR receives CI failures, AI review comments, or maintainer feedback, do not automatically keep adding commits to that PR branch. First classify the requested change by dependency direction and repository cleanliness. The goal is not to avoid all updates to an existing PR; the goal is to keep the upstream branch graph clean and prove independent prerequisites on `upstream/main` before feature branches depend on them.

| Feedback type | Preferred action |
| --- | --- |
| Fixes code introduced by the current PR and is required for that PR to be correct | Create a temporary fork validation branch from the PR head, implement and validate there, then port the cleaned fix back into the original PR branch with a rebase/squash/cherry-pick after tests pass and the user approves updating the upstream PR. |
| Independent prerequisite or repository-level compatibility change that the original project should support on its own, such as a Go/toolchain upgrade required before a dependency upgrade | Create a pure branch from latest `upstream/main` containing only that prerequisite. Prove the original project builds/tests under the new prerequisite. After that focused PR merges, rebase the dependent feature PR onto the updated `main`. |
| Exposes a general repo issue not caused by the PR, such as CI toolchain drift, flaky shared test infrastructure, or unrelated cleanup | Validate in the fork first. Create a separate focused upstream PR from `upstream/main` only after the user approves that upstream review is needed; after it merges, rebase the original PR. |
| Adds a new feature, broad refactor, or follow-up improvement beyond the PR scope | Open a new issue/PR or record as follow-up; do not expand the existing PR. |
| Human maintainer explicitly asks for a change inside the current PR | Follow the maintainer request, but still keep commits clean and avoid unrelated work. |

Validation branch flow for fixes that belong to the current PR:

```bash
git fetch origin upstream main
git switch <original-pr-branch>
git pull --ff-only origin <original-pr-branch>
git switch -c fix/<pr-number>-review-feedback
# edit and test on the temporary branch
git commit -s -m "fix: address <pr-number> review feedback"
```

Only after the fix is validated, update the original PR branch in a clean way:

```bash
git switch <original-pr-branch>
# port the validated fix commit(s), then squash/rebase as appropriate for review clarity
git cherry-pick <validated-fix-commit>
git push --force-with-lease origin <original-pr-branch>
```

Separate PR flow for fixes that should stand on their own:

```bash
git fetch upstream main
git switch -c fix/<short-independent-issue> upstream/main
# apply only the independent fix
git commit -s -m "fix: <summary>"
git push origin fix/<short-independent-issue>
```

After the separate PR merges:

```bash
git switch <original-pr-branch>
git fetch upstream main
git rebase upstream/main
git push --force-with-lease origin <original-pr-branch>
```

For prerequisite upgrades, keep the branch minimal. Example: if `agent-sandbox` requires a newer Go version, first create a standalone Go/toolchain upgrade branch from `upstream/main`, update only the project/toolchain files needed for the original project to build and test, and prove the unmodified original project works with the new Go version. Do not inherit the dependency-upgrade feature branch just to test the prerequisite. Once the prerequisite PR merges, rebase the dependency-upgrade PR onto `main`.

For open-source review hygiene, prefer smaller, focused PRs over one long-running PR that accumulates review fixes, CI infrastructure changes, unrelated cleanup, and follow-up features. If a fix is only used to validate a path before rebasing back into the original PR, keep the validation in the fork and record it in the local internship report so later reviewers can reconstruct why the branch existed.

### Open PR Rebase Validation

When a prerequisite PR has merged and an open dependent PR needs rebasing, do not immediately force-push the open PR branch. First create a local or fork-only validation branch from the current PR head and test the rebased result:

```bash
git fetch origin upstream main
git switch -C rebase/<pr-number>-on-main origin/<original-pr-branch>
git rebase upstream/main
# Resolve conflicts in favor of the merged prerequisite when appropriate.
```

Classify the outcome before updating the open PR:

- If conflicts only remove prerequisite drift and tests pass, the original PR branch can be rebased cleanly after user approval.
- If rebase fixes toolchain or baseline failures but lint/tests still fail on code introduced by the PR, add a local validation fix commit and test it before asking to update the original PR branch.
- If rebase exposes a new independent repo issue, split it into a separate branch from `upstream/main` instead of hiding it inside the dependent PR.

Recommended validation sequence for a dependency or sandbox lifecycle PR after rebase:

```bash
go test ./pkg/workloadmanager -count=1
make lint
go test -race ./pkg/workloadmanager -count=1
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
make gen-check
go test ./test/e2e -run '^$' -count=1
make build-all
git diff --check
git diff --exit-code
```

`make gen-check` intentionally fails on any uncommitted diff because it ends with `git diff --exit-code`. If the only diff is the intended local fix, commit it on the validation branch first, then rerun `make gen-check` to detect real generator drift.

Only after validation is complete and the user approves the exact upstream-facing update should you rebase/squash/cherry-pick the cleaned commits back onto the original PR branch and push with `--force-with-lease`.

### Go / Toolchain Upgrade Pattern

For Go version upgrades, do not blindly choose the minimum version required by a dependency. Check the current stable Go release from the official Go release feed, then choose a stable patch version that is defensible for the project.

Keep the Go version source centralized:

- Prefer `go.mod` as the source of truth for GitHub Actions Go setup.
- In workflows, use `actions/setup-go` with `go-version-file: go.mod` instead of repeating `go-version: "..."` across multiple files.
- Keep Docker builder image tags aligned with the chosen Go version, because Dockerfiles cannot read `go.mod` automatically.
- Run `go mod tidy` with the target Go version and keep its normalization result unless it introduces unrelated dependency drift.

Recommended validation for a pure Go/toolchain prerequisite PR:

```bash
export GOTOOLCHAIN=go<version>
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
make build-all
make lint
make gen-check
docker build -f docker/Dockerfile -t agentcube-go<version>-workloadmanager:test .
docker build -f docker/Dockerfile.router -t agentcube-go<version>-router:test .
docker build -f docker/Dockerfile.picod -t agentcube-go<version>-picod:test .
```

Validate the branch in the fork first. If replacing an earlier trial PR, open a new clean fork PR and mark the old fork PR as superseded so reviewers and CI evidence do not point at the wrong Go patch version.

### Dependency Release / RC Triage

When a reviewer asks why a PR targets one dependency version instead of a newer tag, answer from source and module evidence, not from memory.

1. Check Go module resolution for both the stable target and the requested tag:

```bash
go list -m -json <module>@latest
go list -m -json <module>@<tag>
go list -m -versions <module>
```

For repeated checks, use:

```bash
python3 .agents/skills/agentcube-pr-management/scripts/audit_go_module_version.py \
  sigs.k8s.io/agent-sandbox latest v0.5.0rc1 \
  --show-versions \
  --packages api/v1alpha1 extensions/api/v1alpha1 api/v1beta1 extensions/api/v1beta1
```

2. If a tag resolves to a pseudo-version, do not stop there. Treat it as a module-version signal and then inspect the actual source API and controller behavior.
3. Compare the exact source definitions used by the PR: public API structs, CRD group versions, generated clients, GVR constants, controller state transitions, and e2e install manifests.
4. Run a minimal local bump experiment before claiming incompatibility:

```bash
go get <module>@<tag>
go mod tidy
go test ./<affected-package> -count=1
```

5. If the first failure is missing packages, confirm whether they moved to a new API version. If a mechanical import migration then fails on removed fields, record the exact field errors; they are stronger evidence than a broad "large refactor" statement.
6. Separate "current stable latest compatibility" from "future RC / beta API compatibility" in PR scope. A current PR may target `@latest` while a follow-up tracks a prerelease API migration, especially when the newer tag changes CRD versions, required spec fields, or runtime lifecycle semantics.
7. If the PR body mentions why a newer tag is not targeted, keep the wording precise: pseudo-version resolution is only one reason. State the concrete incompatibility step, such as `go mod tidy` missing packages, removed fields, changed GVR versions, or changed controller behavior.

### Agent-Sandbox Runtime Validation

For agent-sandbox dependency updates, compile-only validation is not enough. Prefer a clean, isolated runtime cluster before touching the long-lived local k3s cluster:

```bash
GOBIN=/root/go/bin go install github.com/k3d-io/k3d/v5@latest
/root/go/bin/k3d cluster create agentcube-sandbox-test \
  --servers 1 \
  --agents 0 \
  --wait \
  --timeout 180s \
  --k3s-arg '--disable=traefik@server:0' \
  --kubeconfig-update-default=false \
  --kubeconfig-switch-context=false
/root/go/bin/k3d kubeconfig get agentcube-sandbox-test > /tmp/agentcube-sandbox-test-kubeconfig.yaml
```

Use `KUBECONFIG=/tmp/agentcube-sandbox-test-kubeconfig.yaml` explicitly for every command. Do not rely on the default context. Delete the cluster at the end:

```bash
/root/go/bin/k3d cluster delete agentcube-sandbox-test
```

Before installing a prerelease manifest over an existing cluster, always check CRD served/storage versions and storedVersions:

```bash
kubectl get crd sandboxes.agents.x-k8s.io sandboxclaims.extensions.agents.x-k8s.io \
  sandboxtemplates.extensions.agents.x-k8s.io sandboxwarmpools.extensions.agents.x-k8s.io \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{range .spec.versions[*]}{.name}:{.served}:{.storage}{","}{end}{"\tstored="}{.status.storedVersions}{"\n"}{end}'
```

If a v1beta1-only CRD manifest is applied to a cluster whose CRD status still has `storedVersions=["v1alpha1"]`, the apiserver can reject it with:

```text
status.storedVersions[0]: Invalid value: "v1alpha1": must appear in spec.versions
```

Treat that as an upgrade-path / CRD migration finding, not as an AgentCube code failure. Validate clean-install behavior separately, and do not claim in-place upgrade support unless the migration path was actually tested.

For runtime evidence, capture more than "e2e passed":

- Direct CodeInterpreter creates `agents.x-k8s.io/v1beta1` Sandbox with `spec.operatingMode=Running`.
- Warm-pool CodeInterpreter creates `extensions.agents.x-k8s.io/v1beta1` SandboxClaim with `spec.warmPoolRef.name=<CodeInterpreter name>`.
- Claim `status.sandbox.name` points to the adopted Sandbox.
- Pod owner chain is `Pod -> Sandbox -> SandboxClaim` for warm-pool sessions.
- DELETE session removes direct Sandbox or SandboxClaim, and warm pool refills to the configured size.
- Python SDK, LangChain sandbox, MCP streamable HTTP, MCP stdio, and math-agent should be rerun when the dependency changes runtime semantics.

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

## Read-Before-Reply Workflow For Existing PRs

Use this workflow before analyzing, reviewing, replying to, or building on someone else's PR.

1. Read the PR body and identify the stated scope, linked issues, PR kind, author, assignees, reviewers, labels, and CI / merge-gate state.
2. Read the full proposal or design document if the PR adds one. For long proposals, first map section headings, then read the sections relevant to the user's question end to end before drawing conclusions.
3. Read `Files changed`, not only the conversation. For code PRs, inspect the implementation files, API/CRD changes, generated files, tests, and manifests touched by the PR.
4. Read human review comments and author replies before bot comments. Distinguish maintainer decisions from AI reviewer suggestions, CI noise, Codecov output, and approval-gate messages.
5. Check whether later commits or force-pushes already addressed an earlier review comment. Do not repeat stale feedback.
6. Compare the PR's actual text/code against any proposed comment. If our comment conflicts with the PR's current wording, update our comment first.
7. Record the evidence locally before posting: PR number, commit SHA, files/sections read, key observations, unresolved questions, and whether the comment is a review suggestion, benchmark evidence, or implementation request.

Useful commands:

```bash
git fetch upstream pull/<pr-number>/head:refs/remotes/upstream/pr-<pr-number>
git show --stat --oneline upstream/pr-<pr-number>
git show upstream/pr-<pr-number>:<path-to-file> | sed -n '<start>,<end>p'
git diff upstream/main...upstream/pr-<pr-number> -- <path>
```

For GitHub metadata, prefer the local PR script when available:

```bash
python3 .agents/skills/agentcube-pr-management/scripts/pr_status.py <pr-number>
```

If the script is insufficient, use the GitHub UI/API, but still read the changed files locally when possible.

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

Always use the repository's official `.github/PULL_REQUEST_TEMPLATE.md` exactly as the base for upstream PRs, including draft and WIP PRs. Do not replace it with a self-designed style. Fill every section; use `NONE` inside the release-note block when there is no user-facing change.

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

If a PR is intentionally unfinished, use the community-conventional title prefix `[WIP]`, not `[DO NOT MERGE]`. A WIP PR still needs user approval before creation and must still use the official PR template. Prefer fork-only PRs for WIP validation unless upstream maintainers explicitly need to see the work.

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
6. Decide whether each fix belongs in the current PR, a temporary validation branch, or a separate PR from `upstream/main`; do not keep stacking unrelated fixes onto the open PR branch.
7. Apply fixes in small local commits on the chosen branch, validate them, then update the PR with a clean history.
8. Reply directly and specifically.
9. Do not use AI-generated reviewer replies verbatim; author should respond.

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
python3 .agents/skills/agentcube-pr-management/scripts/pr_status.py 379
python3 .agents/skills/agentcube-issue-discussion/scripts/thread_brief.py 379
```

`pr_status.py` prints title, state, labels, files, commits, comments count, and review comments summary. `thread_brief.py` gives the broader discussion timeline, assignee signals, body snippet, and PR review surface. Use both before manual review when the question depends on conversation context.

## Guardrails

- Do not create upstream PRs, draft PRs, WIP PRs, issues, or comments without immediate user approval of the exact title/body/comment.
- Do not use upstream PRs as disposable CI runners. Validate in the fork first when maintainer review is not needed.
- Do not ignore the official PR template, even for draft or WIP PRs.
- Use `[WIP]` for unfinished upstream PRs when the user approves posting one; do not use `[DO NOT MERGE]`.
- Do not comment on or mention maintainers in read-only PR analysis unless the user approves and upstream input is genuinely needed.
- Do not merge unrelated formatting with behavior changes.
- Do not treat "avoid updating one PR forever" as a blanket rule. Update the existing PR for fixes that belong to that PR; split out independent prerequisites or repository-wide compatibility changes from `upstream/main`.
- Do not let one upstream PR accumulate unrelated review fixes, independent prerequisites, CI/toolchain repairs, broad cleanup, and new feature work.
- Do not patch an open PR branch directly for every comment by default; use a temporary fix branch or separate PR when that keeps review scope clearer.
- Do not include benchmark raw JSON unless upstream asked for it.
- Do not add new dependencies casually.
- Do not change CRDs without generated files.
- Do not mark an issue fixed unless the PR fully addresses it.
- Do not duplicate work on an issue with an active `PR 认领 @`; record the owner and switch to review/test feedback unless the maintainer asks for a separate PR.
- Do not treat AI reviewer or automation bot comments as maintainer consensus.
- If a first-time contributor workflow needs `ok-to-test`, mention it in local notes; do not spam maintainers.
