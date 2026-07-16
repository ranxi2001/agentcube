**What type of PR is this?**

/kind cleanup

**What this PR does / why we need it**:

`GetSandboxPodIP` now resolves an empty Pod name to the Sandbox name and always reads that exact Pod from the live Kubernetes API. The label-selector fallback is no longer used by AgentCube's supported Sandbox paths after #387, but it kept a cluster-wide Pod informer running and required unnecessary `list` and `watch` permissions.

This removes the unused Pod lister, informer, and cache-sync dependency, and narrows WorkloadManager's Pod RBAC to `get`. Explicit warm-pool Pod names and the direct Sandbox-name fallback retain their supported behavior.

**Which issue(s) this PR fixes**:

Refs #387

**Special notes for your reviewer**:

- Compatibility/scope: the `GetSandboxPodIP` signature and HTTP/CRD contracts are unchanged, and Claim polling is not modified. The exported `Informers.PodInformer` field is removed; there are no repository callers, but out-of-repository source users would need to stop referencing it.
- Tests: `go test ./pkg/workloadmanager`, uncached package race tests, repeated focused tests, `make lint`, and Helm template/lint passed. Helm used the existing local `v3.18.4` binary via an explicit `PATH`.
- AI assistance: Codex helped trace the call path and prepare the cleanup and tests; I reviewed the diff and validation results.

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
