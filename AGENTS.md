# Repository Guidelines

## Project Structure & Module Organization

AgentCube is a Go-first Kubernetes project with Python tooling and docs. Core binaries live under `cmd/`: `workload-manager`, `router`, `picod`, `agentd`, and the Python CLI in `cmd/cli`. Shared Go packages are in `pkg/`, including API types in `pkg/apis/runtime/v1alpha1`, routing in `pkg/router`, lifecycle logic in `pkg/workloadmanager`, and storage in `pkg/store`. Generated clients are under `client-go/`. Deployment assets are in `manifests/charts/base` and `docker/`. The Python SDK is in `sdk-python/`; integrations are under `integrations/`. Tests are colocated as `*_test.go`, with broader scenarios in `test/e2e/`.

## Build, Test, and Development Commands

- `make build-all`: builds `workloadmanager`, `agentd`, and `agentcube-router` into `bin/`.
- `make test`: runs all Go unit tests with `go test -v ./...`.
- `make lint`: runs `golangci-lint` using the pinned local tool version.
- `make fmt`: formats Go code with `go fmt ./...`.
- `make gen-all`: regenerates CRDs, DeepCopy methods, and client-go code.
- `make e2e`: runs the end-to-end suite in `test/e2e/`.
- `cd docs/agentcube && npm run build`: validates the Docusaurus documentation site.

## Coding Style & Naming Conventions

Use Go standard formatting and idioms; run `make fmt` before review. Keep package names lowercase and concise. Public API-facing Go symbols need clear comments. Kubernetes API changes must update CRD types, manifests, and generated clients with `make gen-all`. Python modules use snake_case and should follow the existing layouts in `sdk-python/` and `cmd/cli/`.

## Testing Guidelines

Add unit tests next to changed Go code using `*_test.go`; table-driven tests are preferred for controllers, routing, auth, and store behavior. Run `make test` for normal changes, `go test -race ./...` for concurrency-sensitive code, and `make e2e` for deployment, SDK, or sandbox lifecycle changes. Python SDK tests live in `sdk-python/tests/`; CLI tests live in `cmd/cli/tests/`.

## Internship Report Guidelines

When updating internship reports under `internship-reports/`, include process blockers and debugging notes, not only the final successful path. Record the command or step that failed, the observed error, the root cause if known, and the workaround or final resolution.

When a discussion reaches a concrete conclusion, design decision, testing limitation, environment requirement, community-analysis result, or next-step plan, proactively add a concise summary to the relevant internship report, learning record, or TODO file. Do not wait for the user to explicitly ask to "write this into the report" when the content is clearly part of the internship record. If no suitable report exists yet, create or propose a new day-specific report under `internship-reports/` and link it from `internship-reports/todo.md`.

For competitor benchmarks and sandbox/runtime comparisons, keep the raw result files under `internship-reports/benchmarks/` and reference them from the report. Separate data sources clearly as local measured data, upstream official data, and engineering inference. Record the benchmark host environment, including OS, kernel, glibc, CPU/vCPU, `/dev/kvm`, virtualization flags such as `vmx`/`svm`, and Kubernetes/runtime configuration. Add short plain-language notes for OS-level terms that affect the result, for example KVM, `/dev/kvm`, glibc, Landlock, cgroup, and RuntimeClass, so the report is readable by reviewers who are not operating-system specialists. If a test temporarily changes cluster state, such as `warmPoolSize`, port-forward sessions, or test services, restore it before finishing and state the final setting in the report or final response.

## Fork Sync & Upstream PR Workflow

This workspace uses two remotes:

- `origin`: the personal fork, currently `https://github.com/ranxi2001/agentcube.git`.
- `upstream`: the official project, `https://github.com/volcano-sh/agentcube.git`.

Keep internship reports, local benchmark data, Chinese notes, and task tracking on the fork `main` branch. It is acceptable to rebase fork `main` onto `upstream/main` so the fork stays current while preserving internship commits after the latest official history. Before rebasing, make sure the worktree is clean by committing or stashing local edits.

Use this sync flow for the fork `main` branch:

```bash
git status
git fetch upstream main
git rebase upstream/main
git push --force-with-lease origin main:main
```

Use `--force-with-lease`, not plain `--force`, after a rebase. If `--force-with-lease` is rejected, fetch `origin` and inspect the difference before pushing, because someone or something may have updated the fork branch. Do not push to `upstream`; keep its push URL disabled or treat it as read-only.

For official upstream PRs, do not open PRs directly from the fork `main` branch. Create a clean topic branch from the latest `upstream/main`, and include only one focused change:

```bash
git fetch upstream main
git switch -c docs/benchmark-scope upstream/main
# apply or cherry-pick only the minimal PR change
git status
make test
git push origin docs/benchmark-scope
```

Keep official PR branches small and reviewable. Do not include internship reports, raw benchmark logs, Chinese-only notes, local environment files, or unrelated fork-main history unless the PR explicitly targets those files. Link issues with `Fixes #...` or `Refs #...`, list tests run, and mention any environment-specific limitations.

Before drafting or submitting upstream-facing issues, proposal comments, benchmark feedback, or PRs, follow `internship-reports/open-source-contribution-format-standard.md`. Upstream-facing content should be in English, use the official issue/PR templates, disclose AI assistance in PR reviewer notes, and keep Chinese analysis in internship reports.

## Commit & Pull Request Guidelines

Recent history uses scoped commits such as `docs: clarify redis password values`, `test: fix flaky router private key PEM test`, and `manifests: load REDIS_PASSWORD from Secret via secretKeyRef`. Prefer `component: imperative summary`; `feat:` and `fix:` are acceptable. PRs should explain the problem, summarize changes, link issues with `Fixes #...` or `Refs #...`, list tests run, and include logs or screenshots for user-facing behavior. Request review from relevant `OWNERS`.

## Security & Configuration Tips

Do not commit real Redis passwords, API tokens, kubeconfigs, or model credentials. Prefer Kubernetes Secrets and Helm values such as `redis.secretName` for production-style examples. Report sensitive issues privately as described in `CONTRIBUTING.md`.

For local `math-agent` experiments, store OpenAI-compatible LLM settings in `cmd/cli/examples/math-agent/.env`. The root `.gitignore` ignores `.env`, but still keep the file permission restricted with `chmod 600 cmd/cli/examples/math-agent/.env` and never paste real keys into reports, docs, commits, or shell transcripts. A safe template is:

```bash
OPENAI_API_KEY=<YOUR_API_KEY>
OPENAI_API_BASE=<YOUR_OPENAI_COMPATIBLE_BASE_URL>
OPENAI_MODEL=<YOUR_MODEL>
WORKLOAD_MANAGER_URL=http://localhost:18080
ROUTER_URL=http://localhost:18081
PORT=18082
```
