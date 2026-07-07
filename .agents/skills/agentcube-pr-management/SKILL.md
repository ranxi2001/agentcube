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
- Treat fork `main` as a clean mirror of `upstream/main`. Keep internship reports, local benchmark records, Chinese notes, and local skills on fork `intern`, not on `main`.
- Do not open an upstream PR, draft PR, WIP PR, issue, or upstream review/comment without explicit user confirmation immediately before posting. Prepare the branch, diff, tests, and exact body/comment locally first, then ask for approval.
- Prefer fork-only validation for CI experiments. Use fork branches, any push-triggered fork Actions/checks that actually exist, local Actions when available, or local tests to validate uncertain fixes before involving `volcano-sh/agentcube`.
- Do not create PRs against the personal fork just to run CI. This creates noisy self-PR history and can hurt contribution-quality signals. After upstream PR #414, ordinary fork topic branch pushes can trigger the core validation workflows, but always check the actual commit SHA status because release, publish, approval, and other special workflows may still require different events. Record any missing coverage and compensate with local tests or the eventual upstream PR checks after user-approved submission.
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
- Body/comment formatting check: normal prose should use natural GitHub Markdown paragraphs, without manual hard-wrapping inside sentences.
- Diff summary and tests run.
- Why upstream attention is needed now.

If the goal is only to run CI, use local tests and any fork branch push checks that exist first. Do not ask maintainers to validate work that can be validated before upstream review.

## Branch Workflow

Fork branch roles:

- `origin/main`: clean mirror of `upstream/main`; reset it to `upstream/main` with `git reset --hard upstream/main` and push with `--force-with-lease` when syncing.
- `origin/intern`: internship reports, local benchmark evidence, Chinese notes, local skills, and task tracking; rebase this branch onto `upstream/main` when it needs current project code.
- Upstream PR topic branches: clean branches from `upstream/main` containing one focused change; never branch them from `intern`.

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

For open-source review hygiene, prefer smaller, focused PRs over one long-running PR that accumulates review fixes, CI infrastructure changes, unrelated cleanup, and follow-up features. If a fix is only used to validate a path before rebasing back into the original PR, keep the validation in a fork branch and record it in the local internship report so later reviewers can reconstruct why the branch existed.

### Fork Branch CI Validation

Use a fork branch push when the goal is to see whether available GitHub Actions run without notifying upstream maintainers. This may now trigger the core AgentCube validation workflows, but it still does not guarantee every workflow or permission-sensitive path.

- Push the validation head branch to `origin`.
- Watch the commit SHA checks after the push, not only branch status.
- Prefer the local `check_push_ci.py` helper for push-triggered Actions runs.
- If CI fails, inspect the job logs and uploaded artifacts before changing code.
- Do not open a PR against `ranxi2001/agentcube` just to trigger `pull_request` workflows.
- If the needed workflow is `pull_request`-only, state that push validation did not cover it and rely on local tests plus the eventual upstream PR checks after explicit user approval.

Example:

```bash
git push origin <head-branch>:<head-branch>
python3 .agents/skills/agentcube-pr-management/scripts/check_push_ci.py \
  --repo ranxi2001/agentcube \
  --branch <head-branch> \
  --sha "$(git rev-parse HEAD)" \
  --watch \
  --interval 60
```

### Dependabot Version Update Validation

When validating a Dependabot version-update configuration in the personal fork, do not treat Dependabot security update PRs as proof that scheduled version updates are enabled. Security updates and version updates are separate mechanisms.

For fork-only Dependabot Docker validation:

1. Check the fork setting first: `https://github.com/ranxi2001/agentcube/settings/security_analysis`.
2. Ensure `Dependabot version updates` is enabled. `Dependabot security updates` alone is not enough for `.github/dependabot.yml` schedules.
3. Check the UI status at `Insights -> Dependency graph -> Dependabot`, including configured updates, last checked state, and the manual `Check for updates` control.
4. If a quick fork-only check is needed, temporarily schedule the relevant updater on fork `main`, wait for Dependabot, then restore fork `main` to the upstream mirror before upstream PR work. Do not carry temporary schedule commits into upstream PR branches.
5. Verify output by looking for `dependabot/docker...` branches and Dependabot PRs, not just generic `dependabot/go_modules...` or pip security PRs.
6. Treat `golang:*` Docker builder images as Go toolchain baseline inputs, not ordinary runtime base images. If the project keeps Go version centralized in `go.mod`, do not let a Docker-only Dependabot PR update `golang` by itself; either ignore `golang` in the Docker updater or handle it in a focused Go/toolchain PR that also updates `go.mod`, CI setup, and Docker builder tags.

Useful checks:

```bash
gh pr list -R ranxi2001/agentcube --state all --limit 100 \
  --json number,title,state,headRefName,baseRefName,author,url \
  --jq '.[] | select((.headRefName|ascii_downcase|test("dependabot/docker|alpine|ubuntu")) or (.title|ascii_downcase|test("alpine|ubuntu|docker base|base image"))) | [(.number|tostring), .state, .baseRefName, .headRefName, .author.login, .title, .url] | @tsv'

gh api repos/ranxi2001/agentcube/branches --paginate \
  --jq '.[] | select(.name|test("dependabot/docker|alpine|ubuntu"; "i")) | .name'
```

Known AgentCube Day42 result: after enabling fork Dependabot version updates and temporarily scheduling the `/docker` Docker updater, Dependabot opened fork PR #17 for `alpine:3.19 -> 3.24` and fork PR #18 for `ubuntu:24.04 -> 26.04`. The final upstream PR configuration intentionally ignores `golang` so Docker runtime base image maintenance does not drift from the Go toolchain baseline established by PR #391.

### Fork-Only Push CI Workflow

If ordinary branch push has no useful checks and the user wants CI confidence before opening a real upstream PR, use the fork-only push validation workflow template. This workflow is local/fork infrastructure only. Do not include `.github/workflows/fork-push-validation.yml` in an upstream PR diff.

Known AgentCube state after upstream PR #414: the core build/lint/codegen/e2e/codespell/copyright/coverage/Python workflows include `push` triggers, and Day43 verified a normal fork topic branch push running 9/9 workflows successfully. The check script can only observe workflow runs that GitHub created; it cannot make event-restricted release, publish, approval, or permission-sensitive workflows run on branch push. For paths without useful push checks, the validation branch must contain a push-triggered workflow file.

Technically, adding the push workflow to the fork default branch would make future fork branches that contain that workflow trigger on push. Do not use `origin/main` for that in this workspace, because fork `main` is reserved as a clean mirror of `upstream/main`. If a permanent fork-only base is needed, use a dedicated branch such as `ci/base` or continue installing the workflow only on disposable `ci/<topic>-validation` branches.

Safe flow:

```bash
git fetch upstream main
git switch -c <topic-branch> upstream/main
# apply the actual code change and commit it normally
git switch -c ci/<topic>-validation
git show intern:.agents/skills/agentcube-pr-management/scripts/install_fork_push_ci.sh | bash
git push origin ci/<topic>-validation:ci/<topic>-validation
python3 .agents/skills/agentcube-pr-management/scripts/check_push_ci.py \
  --repo ranxi2001/agentcube \
  --branch ci/<topic>-validation \
  --sha "$(git rev-parse HEAD)" \
  --watch \
  --interval 60
```

`check_push_ci.py` exit codes:

- `0`: all matching runs are terminal and non-failing.
- `1`: at least one matching run failed, timed out, was cancelled, or ended in an unknown terminal state.
- `2`: at least one matching run is still queued or running.
- `3`: no matching Actions run was found. Check whether the workflow file was installed before push, whether the branch matches `ci/**`, `test/**`, `feat/**`, `fix/**`, `chore/**`, or `docs/**`, and whether Actions are enabled in the fork.

After CI passes, continue upstream preparation from the clean topic branch that does not contain the fork-only workflow commit:

```bash
git switch <topic-branch>
git log --oneline
git diff upstream/main...
```

If the validation branch needs a code fix, either fix it first on `ci/<topic>-validation` and cherry-pick only the code fix back to `<topic-branch>`, or fix `<topic-branch>` and recreate the validation branch. Never cherry-pick the fork-only workflow commit into the upstream PR branch.

### Upstreamable Push CI Proposal

It is technically possible to submit an upstream PR that adds Karmada-style branch push CI. Treat it as a contributor-experience CI feature, not a private CI workaround.

If the goal is for fork branch pushes and PRs to use the same CI logic, prefer adding a `push` trigger to the existing validation workflows instead of creating a separate permanent push-only workflow. A separate workflow is acceptable for fork-only temporary validation, but upstream should avoid two long-lived CI definitions that can drift.

Recommended upstream shape:

- Add `push.branches-ignore: ["dependabot/**"]` to existing validation workflows such as `main.yml`, `lint.yml`, `codegen-check.yml`, `e2e.yml`, `codespell.yml`, `copyright-check.yml`, `python-lint.yml`, `python-sdk-tests.yml`, and `test-coverage.yml`.
- Preserve the existing `pull_request`, `merge_group`, and `workflow_call` configuration so PR behavior and merge-queue behavior do not change.
- Do not add branch push triggers to release, publish, or workflow-approval workflows such as image publishing, PyPI publishing, plugin publishing, or `pull_request_target` approval automation.
- Keep the workflow commands identical between push and PR paths. This is the main reason to prefer Karmada-style trigger sharing over a second push-only workflow.
- Avoid secrets, package publishing, or deployment permissions in branch push validation paths.
- If maintainers worry about cost, discuss whether heavy jobs such as e2e should remain PR-only; the tradeoff is lower cost versus losing exact push/PR parity.
- If codespell and copyright run in the same job, restore any files temporarily removed before codespell before running `make gen-copyright`; otherwise copyright verification can fail on the deletion diff rather than a real header problem.

Before opening such a PR, prepare the exact workflow diff, local validation, and PR body, then ask the user to approve the upstream-facing action.

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

Validate the branch locally and, if useful, by pushing a fork validation branch and checking any push-triggered commit checks. If replacing an earlier trial branch, record the old branch as superseded in the local report so later evidence does not point at the wrong Go patch version.

Do not treat Docker `golang:*` image updates as ordinary runtime base-image updates. In AgentCube, `golang:*` builder images are part of the Go toolchain baseline and must stay aligned with `go.mod`, `actions/setup-go`, and Docker build validation. If Dependabot is used for Docker runtime images, ignore `golang` there and handle Go baseline changes in a separate Go/toolchain PR. A `gomod` Dependabot updater may still be useful for module dependencies, but it is not a substitute for a coordinated Go baseline upgrade that updates Docker builder tags and runs the Go/toolchain test matrix.

### GitHub Actions Runner Pinning

When hardening AgentCube GitHub Actions workflows, avoid `runs-on: ubuntu-latest` unless the goal is explicitly to track GitHub's moving default runner image. Prefer a concrete runner label such as `ubuntu-24.04` so CI does not change OS images unexpectedly when GitHub migrates `ubuntu-latest`.

Use this audit before preparing workflow PRs:

```bash
rg -n 'runs-on:\s*ubuntu-latest|runs-on:\s*ubuntu-[0-9]+' .github/workflows
```

For a runner-pinning PR, keep the branch narrow:

1. Start from latest `upstream/main`.
2. Replace only `runs-on: ubuntu-latest` with the chosen concrete label, currently `ubuntu-24.04`.
3. Leave already explicit labels such as `ubuntu-22.04` unchanged unless the PR is specifically about upgrading that workflow's runner.
4. Validate with `git diff --check`, a no-hit `rg 'runs-on:\s*ubuntu-latest' .github/workflows`, YAML parsing, and `actionlint`.
5. If fork push CI is available, push the topic branch and record the workflow run links; otherwise state that full PR CI will run after user-approved upstream PR creation.

For Go toolchain drift checks, use the helper script:

```bash
python3 .agents/skills/agentcube-pr-management/scripts/audit_go_toolchain_alignment.py \
  --repo-root . \
  --check-latest
```

The script verifies that `go.mod`, Docker `golang:<version>` builder tags, and `actions/setup-go` workflow inputs remain aligned. Treat a latest-release mismatch as a notice, not an automatic reason to open a PR; a Go baseline update still needs a focused branch and the Go/toolchain validation matrix above.

For a fork-only rehearsal of an automatically generated Go/toolchain PR, first decide whether the rehearsal is testing a normal post-#391 Go baseline update or a historical migration that also touches workflow files.

For normal post-#391 updates, use the updater helper on an intentionally old baseline branch:

```bash
python3 .agents/skills/agentcube-pr-management/scripts/update_go_toolchain_baseline.py \
  --repo-root . \
  --latest
python3 .agents/skills/agentcube-pr-management/scripts/audit_go_toolchain_alignment.py \
  --repo-root . \
  --check-latest
```

The updater changes only the Go baseline surfaces: `go.mod`, Docker `golang:*` builder tags, and any workflow inline `go-version` entries. It defaults to removing an existing `toolchain` directive because the current AgentCube baseline keeps `go.mod`'s `go` directive as the single source of truth; use `--toolchain-mode align` only if the project later decides to track both directives.

Automation boundary learned from fork testing:

- A hand-created PR is not proof of an automatically generated PR, even if the diff and body look like automation. Check the PR author and event source.
- A GitHub Actions workflow using the default `GITHUB_TOKEN` can create/update ordinary branches and PRs only if repository settings allow Actions to create pull requests. In the fork this setting is visible through `repos/<owner>/<repo>/actions/permissions/workflow` as `can_approve_pull_request_reviews`.
- The default `GITHUB_TOKEN` cannot create or update `.github/workflows/*` files. GitHub rejects such pushes with an error like `refusing to allow a GitHub App to create or update workflow ... without workflows permission`.
- Therefore a #391-style historical 9-file migration that changes workflow files cannot be fully generated by the default `github-actions[bot]` token. It requires a human PR, a GitHub App token, a PAT with workflow permission, or a dedicated tool such as Renovate, all of which need explicit maintainer/security approval.
- After #391, regular future Go baseline updates should normally be 4 or 5 files: `go.mod`, optional `go.sum`, and the three Docker builder Dockerfiles. Workflows should already read `go-version-file: go.mod`.
- PRs created with `GITHUB_TOKEN` do not reliably trigger recursive downstream workflows. Treat the creator workflow's validation as evidence, but do not claim normal PR CI ran unless checks actually exist on the generated PR.

For an upstreamable Go toolchain auto-update workflow, prefer a low-noise scheduled updater first:

- Keep the PR-creating updater job limited to `schedule`, with job-level `contents: write` and `pull-requests: write` permissions. The workflow default should stay `contents: read`.
- Use a weekly cadence similar to Dependabot runtime base-image checks. The purpose is to raise a reviewable maintenance PR when go.dev has a newer stable Go release, not to make every ordinary PR depend on the current external release feed.
- Do not add push / pull_request latest-version enforcement by default. It can detect a branch that consistently lowers `go.mod` and all Docker builder tags, but it adds CI cost and an external-network failure surface to normal development PRs.
- Keep `verify --check-latest --require-latest`, `go mod tidy`, and `git diff --check` inside the scheduled PR creator path so generated PRs prove they updated the baseline correctly.
- Remember that GitHub Actions `schedule` runs only from the repository default branch. A topic-branch test can validate the helper script and workflow syntax, but it cannot prove cron behavior until the workflow is merged into the default branch.

Known fork-only evidence from Day43:

- `https://github.com/ranxi2001/agentcube/actions/runs/28862855744` successfully created bot PR `https://github.com/ranxi2001/agentcube/pull/20` as `app/github-actions`.
- That PR validates the future-standard 4-file path: `go.mod`, `docker/Dockerfile`, `docker/Dockerfile.router`, and `docker/Dockerfile.picod`.
- A prior 9-file workflow attempt failed at the GitHub platform permission boundary when trying to push `.github/workflows/build-push-release.yml` with `GITHUB_TOKEN`.
- A push / PR verifier experiment did detect an old 4-file baseline, but the final Day43 upstream PR branch intentionally removed that verifier to avoid normal PR CI noise. Use that experiment as a design tradeoff note, not as the preferred workflow shape.

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

### Staged Agent-Sandbox Compatibility Experiments

When a direct jump from the project baseline to the latest agent-sandbox tag produces a large diff, split the investigation by release train before deciding PR scope.

1. Create clean worktrees from `upstream/main` for the latest patch in each minor line, for example `v0.2.1`, `v0.3.10`, and `v0.4.6`.
2. In each worktree run the minimal bump first:

```bash
go get sigs.k8s.io/agent-sandbox@<version>
go mod tidy
go test ./pkg/workloadmanager ./cmd/workload-manager ./cmd/agentd -count=1
```

3. Record the first exact failure before fixing it. For agent-sandbox, common breakpoints include moved public constants, `SandboxClaim.Status.SandboxStatus.Name` adoption semantics, `NetworkPolicyManagement` defaults, GVR/API version changes, and `SandboxSpec`/`SandboxClaimSpec` field removals.
4. Separate compile-only fixes from runtime-aware fixes. A constant import migration may make tests compile while warm-pool sessions still wait for the wrong Sandbox or delete the wrong resource.
5. After the runtime-aware minimal fix, run:

```bash
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
go test ./test/e2e -run '^$' -count=1
make build-all
make lint
git diff --check
```

6. Run `make gen-check` in a temporary detached worktree before committing conclusions. If `hack/update-codegen.sh` is pinned to an older Kubernetes code-generator, it can mutate `go.mod` and even downgrade `agent-sandbox`; record that as a codegen/tooling requirement, not as a business-logic failure.
7. Do not run generator targets concurrently in the same worktree. `make gen-check`, `make build-all`, and other targets that depend on `generate` may all run `controller-gen` and `go mod tidy`; parallel execution can read a transient generated-code state and produce a misleading failure.
8. After fixing codegen drift, rerun `make gen-check` and update the local report from "blocked by codegen" to the final pass/fail state. Keep the original failure as a process note, not the final validation status.
9. Compare changed file counts by category: dependency files, hand-written production code, tests, generated files, and scripts. Use this to explain why a final upstream PR is larger than an intermediate compile fix.

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
- For feature PRs or dependency-compatibility PRs, prepare a code rationale matrix before review. Every touched file needs a one-line reason, the upstream/dependency behavior that required it, and the test that covers it. Small files with only a few changed lines still need an explanation, because reviewers often ask why those isolated changes were necessary.
- Do not rely only on existing CI for feature validation. Design feature-specific tests for the behavior introduced or changed by the PR, including the negative/failure path when relevant, and record why the chosen tests cover the risk.
- Pick one PR kind:
  - `/kind bug`
  - `/kind cleanup`
  - `/kind enhancement`
  - `/kind security`
  - `/kind documentation`
  - `/kind feature`
- For `kind/*` labels, use `/kind ...` after user confirmation. Do not rely on GitHub label API permissions from the fork, and do not use `/label kind/...` unless the repository's Prow config explicitly allows that label command.

### Code Rationale Matrix

Before asking for maintainer review, prepare a local table that the author can use to explain the PR live:

| File / area | Why it changed | Evidence | Test coverage | Reviewer explanation |
| --- | --- | --- | --- | --- |
| `go.mod` / `go.sum` | Dependency stack required by the target compatibility change | `go mod graph`, upstream module `go.mod`, compile failure, release notes | build, unit, codegen, e2e | Explain what is prerequisite vs feature-scope dependency change |
| Small isolated file changes | Exact API/name/import or behavior drift that forced the edit | Source diff or compiler error | Targeted unit/e2e check | Explain why a small change is not drive-by cleanup |

Use this matrix for dependency and lifecycle work such as agent-sandbox adaptation, where review questions often focus on why a file was touched at all.

Useful collection commands:

```bash
python3 .agents/skills/agentcube-pr-management/scripts/pr_status.py <pr-number>
git fetch upstream main '+pull/<pr-number>/head:refs/remotes/upstream/pr-<pr-number>'
git diff --name-status <base>..<head>
git diff --stat <base>..<head>
git grep -n -e '<symbol-or-behavior>' <head> -- <path>
git show <head>:<path> | nl -ba | sed -n '<start>,<end>p'
```

For dependency PRs, prove whether version bumps are project requirements or local workaround:

```bash
git worktree add --detach /tmp/<repo>-pr-<number>-review <head>
cd /tmp/<repo>-pr-<number>-review
go mod graph | rg '^(<module>@<version>|<repo-module>) '
git worktree remove /tmp/<repo>-pr-<number>-review
```

### Feature Test Plan

For a feature PR, add or update tests that validate the feature's new behavior directly. Existing CI passing is necessary but not sufficient.

- Identify the behavior change and its failure mode.
- Add focused unit tests for local controller/router/store logic when possible.
- Add e2e or integration tests for cross-component behavior, such as CRD/controller/runtime compatibility.
- Include at least one cleanup/delete or error-path check when the feature changes lifecycle semantics.
- Keep a local mapping from risk to test command so the PR author can explain why the test set is complete enough for review.

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

Format PR bodies and upstream comments for GitHub rendering, not terminal width. Do not hard-wrap normal prose at 80 columns or split a sentence only because it is long. Use line breaks for paragraph boundaries, headings, bullet items, tables, code fences, and release-note blocks. For long bullets, prefer rewriting the sentence or splitting the idea into separate bullets instead of adding continuation lines purely for column width. Before asking the user to approve exact upstream text, review the raw Markdown and collapse accidental line breaks inside ordinary paragraphs.

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

## Requesting Reviewer Attention

Asking someone to review a PR is an upstream-facing action. Do it only after the user approves the exact target and exact text. Prefer a short PR comment over a formal GitHub reviewer request unless the repository workflow or maintainer explicitly expects reviewer assignment.

Use this sequence:

1. Confirm the PR is ready for review: the branch contains the intended scope only, DCO is passing, and either CI is green or any remaining blocker is clearly unrelated and documented.
2. Identify why the person is appropriate: they scoped the issue, already participated in the discussion, are listed by OWNERS/bot guidance, or previously asked to review this area.
3. Check whether bot guidance says to wait. For Kubernetes/Prow-style flow, if the bot says "once this PR has lgtm, assign <approver>", do not mention the approver early just to speed things up.
4. Keep the comment short and low-pressure. Do not attach long rationale, CI logs, or multiple requests unless the reviewer needs that context.
5. Ask one person or one small relevant group at a time. Avoid broad maintainer tagging.
6. Record the posted link in the local report / `PROGRESS.md` when it affects the current work state.

Good default comments:

```md
cc @Reviewer Could you please take a look when you have time? Thanks!
```

```md
cc @Reviewer PTAL when you have time. Thanks!
```

If CI is still running or has a known failure, do not hide that fact. Either wait, or use a short explicit note:

```md
cc @Reviewer Could you please take a look when you have time? One unrelated CI job is still pending.
```

Avoid comments that sound like a merge request, contain several asks, or imply urgency without reason:

```md
cc @Reviewer Could you review, approve, and merge this? All checks are green and tide is only waiting for labels.
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
- Do not manually hard-wrap PR bodies, issue bodies, or upstream comments. Keep ordinary prose as natural Markdown paragraphs unless a list, table, code block, or template block requires line breaks.
- Use `[WIP]` for unfinished upstream PRs when the user approves posting one; do not use `[DO NOT MERGE]`.
- Do not comment on or mention maintainers in read-only PR analysis unless the user approves and upstream input is genuinely needed.
- Do not merge unrelated formatting with behavior changes.
- For fix, feature, or compatibility PRs, treat the upstream base project as the stable baseline by default. Change as few files as possible, and include only edits required to solve the stated problem. Do not include code cleanliness, formatting, image hygiene, dependency tidying, comment polishing, or unrelated refactors just because they look safe. If the target tests/builds pass without an isolated cleanup, remove it from the PR; propose it later as a separate cleanup PR only if it is worth upstream review.
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
