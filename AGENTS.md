# Repository Guidelines

## Project Structure & Module Organization

AgentCube is a Go-first Kubernetes project with Python tooling and docs. Core binaries live under `cmd/`: `workload-manager`, `router`, `picod`, `agentd`, and the Python CLI in `cmd/cli`. Shared Go packages are in `pkg/`, including API types in `pkg/apis/runtime/v1alpha1`, routing in `pkg/router`, lifecycle logic in `pkg/workloadmanager`, and storage in `pkg/store`. Generated clients are under `client-go/`. Deployment assets are in `manifests/charts/base` and `docker/`. The Python SDK is in `sdk-python/`; integrations are under `integrations/`. Tests are colocated as `*_test.go`, with broader scenarios in `test/e2e/`.

## Local Shell Rules

PowerShell is disabled for this workspace. Even if the execution environment reports `shell=powershell`, do not run native PowerShell commands, PowerShell snippets, `.ps1` scripts, or PowerShell-style filesystem operations. Invoke terminal commands through Bash only, using `bash -lc '...'` from the tool layer when needed.

Use Bash/POSIX syntax inside the command body. Prefer repository-relative paths or Git Bash/MSYS-style paths such as `/c/Users/ranxi/Desktop/Project/agentcube/...`; if a Windows program requires Windows paths, convert them inside Bash with `cygpath -w`.

## Build, Test, and Development Commands

- `make build-all`: builds `workloadmanager`, `agentd`, and `agentcube-router` into `bin/`.
- `make test`: runs all Go unit tests with `go test -v ./...`.
- `make lint`: runs `golangci-lint` using the pinned local tool version.
- `make fmt`: formats Go code with `go fmt ./...`.
- `make gen-all`: regenerates CRDs, DeepCopy methods, and client-go code.
- `make e2e`: runs the end-to-end suite in `test/e2e/`.
- `cd docs/agentcube && npm run build`: validates the Docusaurus documentation site.

This workspace has Go `1.26.4` installed as the default system toolchain at `/usr/local/go1.26.4`, with `go` and `gofmt` symlinked from `/usr/local/bin`. Use plain `go`, `gofmt`, and `make fmt`; no per-command `PATH` override is needed.

## Coding Style & Naming Conventions

Use Go standard formatting and idioms; run `make fmt` before review. Keep package names lowercase and concise. Public API-facing Go symbols need clear comments. Kubernetes API changes must update CRD types, manifests, and generated clients with `make gen-all`. Python modules use snake_case and should follow the existing layouts in `sdk-python/` and `cmd/cli/`.

## Testing Guidelines

Add unit tests next to changed Go code using `*_test.go`; table-driven tests are preferred for controllers, routing, auth, and store behavior. Run `make test` for normal changes, `go test -race ./...` for concurrency-sensitive code, and `make e2e` for deployment, SDK, or sandbox lifecycle changes. Python SDK tests live in `sdk-python/tests/`; CLI tests live in `cmd/cli/tests/`.

## Internship Report Guidelines

When updating internship reports under `internship-reports/`, include process blockers and debugging notes, not only the final successful path. Record the command or step that failed, the observed error, the root cause if known, and the workaround or final resolution.

Weekly summaries should emphasize reusable engineering judgment, not only code authored. Treat the internship as training for code review and architecture review: record how requirements were split, what design or clean-architecture boundary was chosen, how code directories map to responsibilities, what review concerns were found, which tests cover which risks, and what CI/CD or open-source process rule was learned. It is acceptable for AI to help draft docs or code; the key record is the human-reviewable reasoning chain from requirement -> design -> implementation boundary -> review -> test evidence.

Do not be stingy with explanatory notes in internship reports, design notes, architecture studies, and review-prep documents. When a report introduces abstract concepts, cross-project terms, protocols, Kubernetes resources, state machines, control-plane/data-plane boundaries, security terms, or engineering inferences, add short Markdown blockquotes such as `> 注释：...` and `> 分析：...` near the relevant paragraph or table. These notes should make the document readable to a future reviewer who has not held the whole conversation in context. This rule is for learning/report documents; code comments should still remain precise and necessary.

For daily reports and review retrospectives, do not create a new day file for the same topic too early. If the topic is still the same investigation or review thread, continue the existing report until it has at least 600 lines before considering a new file. Prefer one substantial, coherent report over many thin fragments.

Name internship report assets so their owner is obvious from the filename. Daily-report images, draw.io sources, exported PNGs, `.url` shortcuts, and companion explainer files should start with the owning day prefix, for example `day33-e2b-architecture-protocol-overview.png` or `day28-agentcube-session-runtime-architecture.drawio`. Weekly report files should start with `weekN-...`, not project-name-first names such as `agentcube week1.md`.

At the start of each new Agent work loop, read root `PROGRESS.md` before diving into reports or code. At the end of the loop, update it only with short state needed for the next run: last work, current blockers, ruled-out paths, next step, and stop conditions. Keep long-form daily records in `internship-reports/` and task inventory in `internship-reports/todo.md`; do not let `PROGRESS.md` become a second report.

## Knowledge Capture Guidelines

At the end of each task, classify any useful conversation outcome before stopping:

- Stable project rules, user preferences, repo conventions, environment facts, and recurring constraints go into `AGENTS.md`.
- Temporary loop state that only helps the next few runs goes into root `PROGRESS.md`.
- Evidence, debugging process, benchmark context, community analysis, and mentor-facing records go into `internship-reports/` or `internship-reports/todo.md`.
- Repeatable workflows with five or more steps, or workflows likely to be reused for issues, PRs, benchmarks, deployments, or reviews, go into `.agents/skills/<skill-name>/SKILL.md`.
- For repeated issue/PR analysis, prefer adding or improving scripts under `.agents/skills/<skill-name>/scripts/` and updating the skill workflow, so future runs can fetch compact evidence instead of redoing long manual analysis.

Do not store everything. Avoid copying raw chat history into long-term files. If a fact is one-off, speculative, already obsolete, or only useful inside the current turn, leave it out. If an existing skill or rule is contradicted by a new verified workflow, patch the old rule immediately instead of letting the next run repeat the same mistake.

When a discussion reaches a concrete conclusion, design decision, testing limitation, environment requirement, community-analysis result, or next-step plan, proactively add a concise summary to the relevant internship report, learning record, or TODO file. Do not wait for the user to explicitly ask to "write this into the report" when the content is clearly part of the internship record. If no suitable report exists yet, create or propose a new day-specific report under `internship-reports/` and link it from `internship-reports/todo.md`.

For competitor benchmarks and sandbox/runtime comparisons, keep the raw result files under `internship-reports/benchmarks/` and reference them from the report. Separate data sources clearly as local measured data, upstream official data, and engineering inference. Record the benchmark host environment, including OS, kernel, glibc, CPU/vCPU, `/dev/kvm`, virtualization flags such as `vmx`/`svm`, and Kubernetes/runtime configuration. Add short plain-language notes for OS-level terms that affect the result, for example KVM, `/dev/kvm`, glibc, Landlock, cgroup, and RuntimeClass, so the report is readable by reviewers who are not operating-system specialists. If a test temporarily changes cluster state, such as `warmPoolSize`, port-forward sessions, or test services, restore it before finishing and state the final setting in the report or final response.

For external sandbox runtime smoke tests such as OpenSandbox or Agent Substrate, use `.agents/skills/sandbox-runtime-smoke/SKILL.md` and keep the workflow scriptable: capture host environment, store raw logs, pre-pull known images when measuring runtime behavior, classify infrastructure bootstrap failures separately from product behavior, and verify cleanup before stopping.

## Fork Sync & Upstream PR Workflow

This workspace uses two remotes:

- `origin`: the personal fork, currently `https://github.com/ranxi2001/agentcube.git`.
- `upstream`: the official project, `https://github.com/volcano-sh/agentcube.git`.

Keep the fork `main` branch as a clean mirror of `upstream/main`. Do not commit internship reports, local benchmark data, Chinese notes, task tracking, or local-only skills to fork `main`. Keep that work on the fork `intern` branch instead. Before rebasing or resetting either branch, make sure the worktree is clean by committing or stashing local edits.

Use this sync flow for the fork `main` mirror:

```bash
git status
git fetch upstream main
git switch main
git reset --hard upstream/main
git push --force-with-lease origin main:main
```

Use this sync flow for internship records:

```bash
git status
git fetch upstream main
git switch intern
git rebase upstream/main
git push --force-with-lease origin intern:intern
```

For fork-only internship reports, TODO updates, local skills, and other `intern` branch record-keeping work, push to `origin intern:intern` in the same work loop after committing unless the user explicitly asks not to push. This automatic push preference applies only to the personal fork / `intern` branch workflow; upstream-facing PRs, issues, comments, review requests, maintainer mentions, and official topic branches still require explicit user confirmation.

Use `--force-with-lease`, not plain `--force`, after a rebase or mirror reset. If `--force-with-lease` is rejected, fetch `origin` and inspect the difference before pushing, because someone or something may have updated the fork branch. Do not push to `upstream`; keep its push URL disabled or treat it as read-only.

For official upstream PRs, do not open PRs directly from the fork `main` branch. Create a clean topic branch from the latest `upstream/main`, and include only one focused change:

```bash
git fetch upstream main
git switch -c docs/benchmark-scope upstream/main
# apply or cherry-pick only the minimal PR change
git status
make test
git commit -s -m "docs: ..."
git push origin docs/benchmark-scope
```

Keep official PR branches small and reviewable. Do not include internship reports, raw benchmark logs, Chinese-only notes, local environment files, `intern` branch history, or unrelated fork history unless the PR explicitly targets those files. Link issues with `Fixes #...` or `Refs #...`, list tests run, and mention any environment-specific limitations. Upstream PR commits must include DCO signoff; use `git commit -s` by default. If a PR branch commit is missing signoff and the branch is only yours, repair it with `git commit --amend --no-edit --signoff` or `git rebase HEAD~N --signoff`, then push with `git push --force-with-lease`.

Before any upstream-facing action, including creating a PR, draft PR, WIP PR, issue, review comment, issue comment, `/assign`, reviewer request, or maintainer mention, get explicit user confirmation on the exact title/body/comment and target. Do not use upstream PRs or self-fork PRs as disposable CI runners. Validate uncertain fixes with local tests and any push-triggered fork Actions/checks that actually exist. In this repository, most full CI workflows are `pull_request`-triggered for `main` / `release-*`, so a standalone `feat/*` push usually will not run full CI. If CI confidence is needed before upstream review, use the fork-only push workflow template under `.agents/skills/agentcube-pr-management/` on a `ci/<topic>` validation branch, and keep `.github/workflows/fork-push-validation.yml` out of upstream PR diffs. Open upstream PRs only when the change is ready for community review or the user explicitly asks to involve upstream. For unfinished upstream work, use the community-style `[WIP]` title prefix, not `[DO NOT MERGE]`, and still use the official PR template.

When an open upstream PR receives review comments or CI failures, do not automatically keep stacking commits on that PR branch. First classify whether the fix belongs to the PR scope. This is not a blanket ban on updating an existing PR: fixes introduced by that PR can be validated on a temporary fork branch and then cleanly ported back after user approval. Independent prerequisites or repository-wide compatibility changes, such as a Go/toolchain upgrade needed before a dependency upgrade, should be split into a pure branch from latest `upstream/main`; prove the original project builds/tests under that prerequisite, then rebase the dependent feature PR after the prerequisite merges. For general repo problems such as CI toolchain drift, flaky shared tests, unrelated cleanup, or follow-up features, prefer fork validation first and open a separate focused upstream PR from `upstream/main` only after user approval.

Before taking a feature or dependency-compatibility PR into maintainer review, prepare a code rationale matrix and a feature-specific test plan. Every touched file needs a clear reason, including small isolated changes that only modify a few lines. Do not rely only on existing CI; design focused tests for the new behavior, failure paths, and lifecycle cleanup introduced by the PR.

Before drafting or submitting upstream-facing issues, proposal comments, benchmark feedback, or PRs, follow `internship-reports/open-source-contribution-format-standard.md`. Upstream-facing content should be in English, use the official issue/PR templates, disclose AI assistance in PR reviewer notes, and keep Chinese analysis in internship reports.

## Commit & Pull Request Guidelines

Recent history uses scoped commits such as `docs: clarify redis password values`, `test: fix flaky router private key PEM test`, and `manifests: load REDIS_PASSWORD from Secret via secretKeyRef`. Prefer `component: imperative summary`; `feat:` and `fix:` are acceptable. PRs should explain the problem, summarize changes, link issues with `Fixes #...` or `Refs #...`, list tests run, and include logs or screenshots for user-facing behavior. Request review from relevant `OWNERS`.

## Security & Configuration Tips

Do not commit real Redis passwords, API tokens, kubeconfigs, or model credentials. Prefer Kubernetes Secrets and Helm values such as `redis.secretName` for production-style examples. Report sensitive issues privately as described in `CONTRIBUTING.md`.

For local GitHub PR/API automation, a personal token may be stored in `.agents/.env` as `GITHUB_TOKEN` / `GH_TOKEN`. This file is ignored by git and must stay `chmod 600`. Load it only for API/CLI calls, never print the value, paste it into reports, or include it in commits/log transcripts.

For local `math-agent` experiments, store OpenAI-compatible LLM settings in `cmd/cli/examples/math-agent/.env`. The root `.gitignore` ignores `.env`, but still keep the file permission restricted with `chmod 600 cmd/cli/examples/math-agent/.env` and never paste real keys into reports, docs, commits, or shell transcripts. A safe template is:

```bash
OPENAI_API_KEY=<YOUR_API_KEY>
OPENAI_API_BASE=<YOUR_OPENAI_COMPATIBLE_BASE_URL>
OPENAI_MODEL=<YOUR_MODEL>
WORKLOAD_MANAGER_URL=http://localhost:18080
ROUTER_URL=http://localhost:18081
PORT=18082
```
