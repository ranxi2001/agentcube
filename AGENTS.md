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

## Commit & Pull Request Guidelines

Recent history uses scoped commits such as `docs: clarify redis password values`, `test: fix flaky router private key PEM test`, and `manifests: load REDIS_PASSWORD from Secret via secretKeyRef`. Prefer `component: imperative summary`; `feat:` and `fix:` are acceptable. PRs should explain the problem, summarize changes, link issues with `Fixes #...` or `Refs #...`, list tests run, and include logs or screenshots for user-facing behavior. Request review from relevant `OWNERS`.

## Security & Configuration Tips

Do not commit real Redis passwords, API tokens, kubeconfigs, or model credentials. Prefer Kubernetes Secrets and Helm values such as `redis.secretName` for production-style examples. Report sensitive issues privately as described in `CONTRIBUTING.md`.
