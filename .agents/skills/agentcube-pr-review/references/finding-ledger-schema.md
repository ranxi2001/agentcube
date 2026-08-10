# Carry-Forward Finding Ledger

Use this ledger when a PR replaces an earlier PR, when a final review spans several force-pushes, or when known local findings are not all represented by current GitHub threads.

## 1. Freeze findings before reviewing the new head

Store stable IDs, a one-line summary, evidence provenance, and likely paths:

```json
{
  "schema_version": 1,
  "ledger_id": "agent-sandbox-upgrade",
  "ledger_version": 2,
  "findings": [
    {
      "id": "exported-resource-signature",
      "summary": "Preserve the exported Resource return type for existing callers.",
      "provenance": [
        "predecessor PR review at <sha>",
        "local report section or current-PR review URL"
      ],
      "paths": ["pkg/apis/runtime/v1alpha1/register.go"]
    }
  ]
}
```

Union the parent acceptance contract, predecessor PR findings, local reports, and validated current-PR findings. Do not include speculative questions as gold findings. Do not silently remove a finding because its old thread was resolved or attached to a closed PR.

Keep `ledger_id` stable for one logical lineage and increment `ledger_version` whenever the frozen finding set changes. `schema_version` describes the file format; it is not the gold-set version.

An explicitly supplied ledger must contain at least one finding. If there are no carry-forward findings, pass `--no-carry-forward-findings`; the output records this as `none-declared` / `not-applicable`. An empty ledger or omitted mode must not turn a required closure gate into success: `not-provided` / `not-assessed` remains a failure. The CLI requires exactly one of `--finding-ledger` and `--no-carry-forward-findings`.

## 2. Classify against one exact head

Create a separate closure file after inspecting the target SHA:

```json
{
  "schema_version": 1,
  "ledger_id": "agent-sandbox-upgrade",
  "ledger_version": 2,
  "ledger_digest": "<SHA-256 of canonical finding-ledger JSON>",
  "target": {
    "repository": "volcano-sh/agentcube",
    "pull_request": 446
  },
  "head": "<40-character-current-head-sha>",
  "closures": [
    {
      "id": "exported-resource-signature",
      "status": "fixed",
      "evidence": [
        "pkg/apis/runtime/v1alpha1/register.go keeps schema.GroupVersionResource",
        "generated listers adapt with .GroupResource()"
      ]
    }
  ]
}
```

Allowed statuses:

- `fixed`: current code and tests close the finding;
- `present`: the finding remains and must be reported or tracked;
- `not-applicable`: scope or implementation changed; evidence must explain why;
- `duplicate-on-current-pr`: the same current-PR finding is already public; evidence must point to that thread.
- `accepted-by-maintainer`: a maintainer explicitly accepted the remaining risk or scope; evidence must point to that decision.

A predecessor-PR thread is not a duplicate on a replacement PR. Every status needs current-head evidence. `present` and `duplicate-on-current-pr` close the classification ledger but still block review readiness; only `fixed`, `not-applicable`, or `accepted-by-maintainer` can make a fully classified ledger ready.

## 3. Run the executable gate

```bash
python3 /home/agentcube/.agents/skills/agentcube-pr-review/scripts/final_head_review.py \
  --repo-root /path/to/pr-worktree \
  --base upstream/main --head <exact-sha> \
  --target-repository volcano-sh/agentcube --target-pull-request 446 \
  --acceptance-file /path/to/issue-body.md \
  --scope-closure /path/to/scope-closure.json \
  --finding-ledger /path/to/findings.json \
  --finding-closure /path/to/closure.json \
  --run-go-tests --check-urls --format markdown
```

Compute `ledger_digest` from the parsed ledger object serialized with sorted keys, UTF-8, and compact separators; whitespace-only formatting changes do not alter it. The digest prevents an old closure from being reused after findings, summaries, provenance, or paths change without a version bump. The command-line target is trusted review context; the harness requires the closure `target` and every decision URL to match it, so a closure cannot redefine “current PR.”

```bash
python3 -c 'import hashlib,json,sys; value=json.load(open(sys.argv[1], encoding="utf-8")); print(hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest())' findings.json
```

For `duplicate-on-current-pr`, add `decision.url` pointing to the current PR thread. For `accepted-by-maintainer`, also record `decision.author` and GitHub `decision.author_association`; only `OWNER`, `MEMBER`, or `COLLABORATOR` passes the structural gate. The harness validates the structure and current-PR URL, while the reviewer must still verify the live comment and role.

The command exits non-zero when a supplied ledger lacks a closure, an ID is unclassified, the closure binds a different ledger version/content digest, the closure head is stale, or a finding remains `present` / `duplicate-on-current-pr`. With `--run-go-tests`, it also rejects tracked or untracked worktree changes so local edits cannot contaminate exact-head evidence. It emits leads for exported Go signature changes and Kubernetes library/code-generator minor-version skew. Leads still require reviewer judgment and an explicit false-positive check.

## 4. Compare review rounds fairly

Record the SHA reviewed by every human review. Classify later comments before calculating recall:

- `same-head miss`: the defect existed on the reviewed SHA and was absent from that review's finding set;
- `new-head regression`: a later patch introduced it;
- `same-finding follow-up`: a patch attempted the original fix but did not close the same acceptance invariant;
- `independent current-head finding`: distinct from the earlier finding and present on the compared SHA.

Only same-head misses belong in the earlier review's recall denominator. New-head regressions measure patch monitoring, while same-finding follow-ups measure closure quality.

Do not collapse different capabilities into one recall number:

- **correctness discovery:** a distinct same-head behavioral defect absent from the earlier finding set;
- **scope discovery:** a distinct same-head `remove` / `separate` topic absent from the earlier record;
- **known-item closure:** an already recorded actionable topic that survived the readiness decision;
- **maintainer-policy calibration:** an authoritative placement, sequencing, or project-direction decision
  that was not derivable as a technical defect from the public contract.

Repeated inline anchors for one invariant count once. A known scope item that survives `/lgtm` is a
closure failure, not a new discovery by the later reviewer.

## 5. Bind PR-scope closure to the exact review surface

The carry-forward finding ledger tracks known defects across heads. The scope closure answers a
different question: does every hand-written file and material hunk belong in this exact merge unit?
Supply one file entry for every hand-written changed path:

```json
{
  "schema_version": 1,
  "target": {
    "repository": "volcano-sh/agentcube",
    "pull_request": 446
  },
  "base": "<40-character-base-tip-sha>",
  "head": "<40-character-current-head-sha>",
  "merge_base": "<40-character-merge-base-sha>",
  "ci_tests": [
    {
      "package": "./pkg/workloadmanager",
      "status": "passed",
      "command": "go test -race -coverprofile=coverage.out ./pkg/...",
      "job_url": "https://github.com/volcano-sh/agentcube/actions/runs/123/job/456",
      "evidence": ["Job log at the declared head reached PASS without a skip gate."]
    }
  ],
  "boundary_leads": [
    {
      "key": "lexicographic-version-comparison:<key emitted by the harness>",
      "status": "resolved",
      "rationale": "The implementation now parses semantic versions before comparison.",
      "evidence": ["Focused boundary test covers v0.4.10 versus v0.5.0."]
    }
  ],
  "external_urls": [
    {
      "url": "https://example.com/releases/${VERSION}/artifact.yaml",
      "status": "resolved",
      "rationale": "The runtime value expands to the supported release tag.",
      "evidence": ["The concrete v0.5.3 URL returned HTTP 200 during exact-head review."]
    }
  ],
  "files": [
    {
      "path": "hack/update-codegen.sh",
      "group": "code-generator prerequisite",
      "disposition": "mixed",
      "acceptance": "Keep generated clients compatible with Kubernetes v0.36.2.",
      "owning_surface": "repository code-generation tooling",
      "independently_mergeable": true,
      "rationale": "The version pin is required; the remaining tooling rewrite is independent.",
      "evidence": ["Clean regeneration succeeds with the upstream helper."],
      "hunks": [
        {
          "label": "CODEGEN_VERSION v0.36.2",
          "disposition": "keep",
          "acceptance": "Match the Kubernetes dependency minor version.",
          "owning_surface": "hack/update-codegen.sh version pin",
          "rationale": "The generated client toolchain must match the imported libraries.",
          "evidence": ["go.mod imports k8s.io modules at v0.36.2."]
        },
        {
          "label": "manual generator and platform rewrite",
          "disposition": "separate",
          "acceptance": "No parent-Issue acceptance item requires this rewrite.",
          "owning_surface": "independent code-generation portability work",
          "rationale": "It can be tested and merged without the feature migration.",
          "evidence": ["The version-only counterfactual regenerates a clean tree."]
        }
      ]
    }
  ]
}
```

Allowed file dispositions are `keep`, `remove`, `separate`, `unresolved`, and `mixed`. A `mixed` file
must list its material hunks, each with a non-`mixed` disposition and evidence. Every changed
hand-written path must appear exactly once; unknown paths, duplicate paths, empty rationale/evidence,
and stale base/head/merge-base surfaces are invalid. If an independently mergeable item would
otherwise be ready (`keep`, or `mixed` with all hunks kept), add an `atomicity` field explaining why
it still belongs in this merge unit.

Only a complete exact-head closure containing `keep` items (or a `mixed` item whose hunks are all
`keep`) is ready. `remove`, `separate`, and `unresolved` remain blocking until a new head removes or
splits them. When a maintainer explicitly changes the merge-unit decision, record the decision in the
rationale/evidence and classify the resulting exact-head item according to that decision; do not use
an out-of-scope note to bypass the gate.

The harness extracts workflow commands as discovery candidates only. It excludes statically disabled
jobs/steps and quoted/commented command text. Only a single control-flow-free, full-package direct
`go test` command in a uniquely named, non-matrix job and uniquely named step is `CI-waivable`.
The job must use an allowed concrete GitHub-hosted runner, an exact clean checkout through an
immutable pinned setup-action chain, and no preceding shell step or mutable execution context. Only
explicitly allowed full-execution flags are accepted; unknown build/test flags fail closed.
Filtering/skip/compile/dry-run/overlay forms such as `-run`, `-skip`, `-short`, `-list`, `-c`,
`-count=0`, `-n`, and `-overlay`, dynamic flags, injected `GOFLAGS`, `continue-on-error`, non-root
working directories, custom shells, prior `$GITHUB_ENV` / `go env -w` mutation, `true || go test`,
`if`, `exit`, pipelines, multiple commands, Makefile targets, and shell scripts remain lead-only.
Workflow, job, step, and job-container environments are all part of this check. This is deliberately
conservative because a successful enclosing step does not prove that the exact-head complete package
tests ran or that their exit status controlled the step. To waive a direct package run, add one
`ci_tests` row whose package and command match an eligible candidate and whose `job_url` targets the
current repository. The harness queries GitHub and requires a successful `push` or
`workflow_dispatch` run at the exact head, the same workflow path and exact static job name, and
success at the candidate's exact YAML step ordinal and name. `pull_request` runs are rejected because
their default checkout is a synthetic merge ref rather than the PR head. API failure,
duplicate/dynamic identity, or a lead-only candidate cannot degrade to free-form evidence; run the
package directly from a clean input worktree at the declared head with `--run-go-tests --go-binary
/reviewed/absolute/path/to/go`. Direct runs materialize regular tracked files from exact-head Git blobs
into a fresh temporary tree, so ignored files and checkout filters cannot change execution. They clear
ambient Go/compiler/loader overrides, set `GOENV=off` and `GOTOOLCHAIN=local`, use a controlled `PATH`,
require the reviewed Go host to be Linux/amd64, and select the nearest governing `go.work` tracked at
HEAD (or `GOWORK=off` only when none governs that module). Every workspace use, workspace replace,
main module, and local module replacement resolved by the Go module graph must remain inside the
materialized tree. Root-module wildcards do not cover nested modules or Go-ignored directory segments;
changed GOOS/GOARCH/build-constrained tests require explicit compatible execution and cannot receive a
generic Linux/amd64 CI waiver.

Run once without boundary closure to obtain deterministic lead keys. Then classify every emitted
lead as `resolved`, `not-applicable`, `present`, or `accepted-by-maintainer`, with rationale and
current-surface evidence. `present` blocks readiness. `accepted-by-maintainer` additionally requires
the same structured current-PR decision evidence used by finding closure. Missing, duplicate,
unknown, or stale lead closure is invalid; a heuristic match is a review lead, not an automatic bug.

Literal external URLs can close automatically when `--check-urls` succeeds. Variable or otherwise
non-probeable URLs must appear in `external_urls` with the original exact string, one of the same four
statuses, rationale, and concrete resolution evidence. Missing entries and `present` block; unknown
or duplicate URLs are invalid. This prevents both unchecked links from passing and valid `${...}`
URLs from becoming permanent false blockers.

The final gate also requires `git merge-tree --write-tree <base> <head>` to succeed. A complete scope
ledger does not make a textually conflicted review surface ready.
