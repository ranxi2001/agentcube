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
