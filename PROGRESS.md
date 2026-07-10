# PROGRESS.md

这个文件只保存下一轮 Agent 需要的短记忆，不做日报。详细过程、证据和长分析放在 `internship-reports/` 与 `internship-reports/todo.md`。

## Goal

当前主线：参与 AgentCube upstream 社区，围绕 agent-sandbox compatibility、SandboxPool / slow resource control plane、Sleep/Resume、SnapStart、observability、SDK lifecycle、benchmark 和开源 review 找可验证、低重复的贡献点。

## Current State

- Branch/workflow：当前本地在 `intern`，该分支保存实习报告、TODO、本地 skills 和中文记录；fork `main` 必须保持 upstream clean mirror。记录类 commit 完成后默认 push `origin intern:intern`；任何 upstream issue/PR/comment/review request/maintainer mention 必须先让用户确认 exact target/body。
- Day45 community screening：2026-07-10 已按 assignee、`/assign`、active PR、scope、环境和当前源码筛选最新 open issues；没有可直接认领的 A 级任务。#432 已由 `avinxshKD` 认领并有 #433；#430 已有 #431 proposal；#365 依赖 #366/#379 和 Kuasar/KVM；#348 已由 merged PR #378 修复但 issue 未关闭。旧 #272 与 open PR #249/release policy 有交叉，需先协调，不能直接接手。详见 `internship-reports/day45-latest-community-issue-task-screening.md`。
- Latest upstream baseline：本轮只执行 `git fetch upstream main`，未切换/rebase `intern`；最新观测 `upstream/main eee8aea`。#420、#422、#423 已合并，#403、#414 也早已合并；不要继续按 open PR 跟踪。
- Day44 / PR #431：latest observed head `b6a784c` (`fix VPA issue`)。作者回复 `discussion_r3557359462` 并明确选择 Static Pod manifest rebuild + custom CRI interception：不走 native `/resize`，不依赖 VPA / `InPlacePodVerticalScaling`，rebuild 期间 node-ctl/node-level cgroup 保持，mirror API gap 的安全设计声称依赖 kubelet local admission。`SP-01` 的设计歧义已解决，不在原 thread 追评；runtime guarantee 仍需 `SP-08` real-node e2e。该 head ordinary checks 全部成功，tide 仍等 review/labels。
- Day44 输出：`internship-reports/day44-sandbox-pool-management-proposal-review.md` 保存架构剖析和回复后的设计迁移；`internship-reports/day44-sandboxpool-pr431-comment-drafts.md` 的 tracker 是唯一索引。当前 `SP-01`/`SP-09` 已解决；`SP-02` RuntimeClass/CRI integration 因 custom CRI interception 成为核心而提升 P0 `READY_LOCAL`；`SP-03`..`SP-08` 暂存或待证据。`SP-02` 草稿指出 RuntimeClass handler 只进入同一 CRI `RunPodSandbox` 请求，不会自动切换到 `/run/sandbox-pool/cri.sock`，需明确 containerd shim/sandboxer/CRI proxy integration。已生成 `day44-sandboxpool-runtimeclass-cri-routing-gap.png`（gpt-image-2，1672x941）及同前缀 prompt，红色缺口准确标在 containerd handler 与独立 agent socket 之间。
- #431 后续观察点：`@acsoto` 已问新 SandboxPool 与现有 WarmPool 路径关系，作者称是 two-generation architecture，但正文似乎还没补 Relationship section。我们此前的 stale/unreachable inline comment 已被 `35d361e` 基本吸收；新增实现仍把 `NodeCtl.LastHeartbeat` 当 agent heartbeat，且 Phase table 的 `PlaceholderAgentHealthy=True → Ready` 未重检其它 Ready 条件。删除超时强制移除 finalizer 还可能遗留无 CRD 对应的 node-local Static Pod manifest。三项先本地保留，不连续堆 upstream 评论。Copilot 已覆盖 endpoint source of truth、SSA conditions list-map、`omitempty`、`<5s` rebuild 和 no-process/no-cgroup，不重复。
- GPT image workflow：本地 `/home/agentcube/.agents/skills/gpt-image-draw/SKILL.md` 已跑通。环境有 `OPENAI_API_KEY`；系统 Python 缺 `openai` 且受 PEP 668 限制，已用 `/tmp/gpt-image-draw-venv` 临时 venv 安装依赖。生成后必须用 `file` / `ls -lh` / `view_image` 复核，实际 PNG 尺寸可能不同于请求尺寸。不要打印或提交任何 key。
- Diagram rule：`AGENTS.md` 已新增 `Diagram and Image Generation Guidelines`。Linux 上架构/控制流/状态机/proposal review 图默认用 Mermaid；draw.io 只在需要可编辑画布或复杂布局时用；GPT image draw 用于精致 raster、中文信息图、banner、报告视觉图。精确架构和 review 推理仍以 Mermaid / prose 为准。

## Active Upstream Threads

- #431 SandboxPool proposal：review / observe only，暂不继续发评论，除非用户确认具体英文文本。
- #429 Go toolchain update workflow：已创建 upstream PR，普通 CI 绿，`tide` pending 等 review/labels；不要自动 push/comment。
- #387 agent-sandbox v0.4.6 compatibility：保持 current stable compatibility 口径，不把 v0.5.x / Sleep/Resume / PicoD cleanup 混入；有 review 再小步处理并先确认。
- #385 WarmPoolAvailable PoC：主要等 maintainer review / `lgtm` / `approve` / tide。
- #433 WorkloadManager chart auth：`avinxshKD` 已认领并提交 PR；普通 checks 通过、tide 等 labels。只可考虑 Helm/RBAC/auth 验证协作，不开重复实现。

## Durable Constraints

- Bash only. Do not run PowerShell snippets or `.ps1` in this workspace.
- Before upstream-facing actions, follow `internship-reports/open-source-contribution-format-standard.md`; upstream text is English, Chinese analysis stays in reports.
- For issue/PR context, prefer `.agents/skills/agentcube-issue-discussion/scripts/thread_brief.py <number>` first; for PR status use the local PR scripts when useful.
- Keep fork `main` as clean mirror of `upstream/main`; do not commit internship reports, local benchmark data, Chinese notes, or local skills there.
- Use `--force-with-lease`, not plain `--force`, after rebases or mirror resets.
- For official upstream PR branches: clean topic branch from latest `upstream/main`, small scope, DCO signoff, no internship/local artifacts.
- Do not use upstream PRs or self-fork PRs as disposable CI runners. Use local tests or approved fork-only validation branches.

## Current Blockers / Environment Limits

- Current machine has no `/dev/kvm`; CPU virtualization flags are not exposed. Do not claim real MicroVM / KVM / forkd / CubeSandbox virtualization validation here.
- Standard kind Kubernetes has failed on this host at kubelet/cgroup/QoS initialization. Use existing k3s or record KWOK/kind limitations clearly; do not describe kind environment failure as AgentCube code failure.
- Full `go test ./...` can fail in `test/e2e` when Router/WorkloadManager/kubeconfig are not running. For ordinary code changes prefer targeted packages or non-e2e all-Go tests; document exclusions.
- OpenSandbox / Agent Substrate runtime smoke tests are not yet deployed locally; use `.agents/skills/sandbox-runtime-smoke/SKILL.md` if resuming that work.
- Do not run `make gen-check` and `make build-all` concurrently; both can touch generated/tidy state.

## Ruled Out / Do Not Repeat

- Do not treat `WarmPoolNotFound` as a stable Warning Event requirement; it may be normal controller cache timing.
- Do not repeat #379 comments already covered by Copilot, especially duplicate `ctrl.SetupSignalHandler()` observations.
- Do not simplify `agent-sandbox v0.5.0rc1` incompatibility to “pseudo-version”; the real issues were v1alpha1 package removal, `Sandbox.spec.replicas` -> `OperatingMode`, and claim `TemplateRef` -> required `WarmPoolRef`.
- Do not call AgentCube “E2B-compatible” based only on E2B-like behavior; Day33 split compatibility into SDK, REST lifecycle, envd process/filesystem RPC, template/snapshot/network/volume.

## Next

- Community tasks：本轮不 `/assign`。下一次先刷新 open issue/PR；只有新的 focused unowned issue，或 maintainer 将 #386/#272 拆成 dedicated sub-issue，才进入认领准备。#433 若做协作，先在临时 worktree 完成 Helm render/lint 和 auth/RBAC focused validation，再向用户提交 exact review draft。
- For #431: resize question is resolved by `b6a784c`; do not reply in that thread. If continuing review, only `SP-02` is ready: show the user the exact RuntimeClass/CRI integration inline draft and obtain explicit confirmation before posting. Do not stack `SP-03`..`SP-08` while `SP-02` is under consideration.
- If validating #431 technically, focus on containerd handler integration and kubelet admission/scheduler accounting for the rebuild window. Keep native `/resize` out of the design: Static Pods remain unsupported by KEP-1287; `b6a784c` now correctly uses rebuild + custom CRI semantics.
- For Sleep/Resume: keep as design/fake-provider/test-plan unless maintainers clarify ownership. Next useful local work remains Router resume-before-proxy tests or API contract, not broad upstream PR.
- For agent-sandbox v0.5.x: keep separate from #387. Clean follow-up only after official scope decision; disclose clean-install evidence and old CRD storedVersions migration gap.
- For benchmark work: only run tests current environment supports; record OS/kernel/glibc/CPU/K8s/runtime and distinguish local measured data from inference.
- For diagrams/reports: prefer Mermaid in Markdown; use GPT image draw for presentation visuals and store reusable prompts with day prefix.

## Stop Conditions

- Same environment blocker fails three times in a row, such as kind kubelet/cgroup/QoS or `/dev/kvm` absence: stop debugging, record BLOCKED, switch task or machine.
- An upstream PR/issue already has an active assignee working on the same change: do not open duplicate PR; offer review, reproduction, or test feedback instead.
- If a community comment would be speculative without source, code evidence, official docs, or local test evidence: stop and gather evidence first.
