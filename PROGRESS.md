# PROGRESS.md

这个文件只保存下一轮 Agent 需要的短记忆，不做日报。详细过程、证据和长分析放在 `internship-reports/` 与 `internship-reports/todo.md`。

## Goal

当前主线：参与 AgentCube upstream 社区，围绕 agent-sandbox compatibility、SandboxPool / slow resource control plane、Sleep/Resume、SnapStart、observability、SDK lifecycle、benchmark 和开源 review 找可验证、低重复的贡献点。

## Current State

- Branch/workflow：当前本地在 `intern`，该分支保存实习报告、TODO、本地 skills 和中文记录；fork `main` 必须保持 upstream clean mirror。记录类 commit 完成后默认 push `origin intern:intern`；任何 upstream issue/PR/comment/review request/maintainer mention 必须先让用户确认 exact target/body。
- Day44 / PR #431：正式 proposal PR `https://github.com/volcano-sh/agentcube/pull/431`，latest observed head `9f03cca`，title `[Proposal] add sandbox-pool management proposal`，关联 discussion #430。PR body 已从 `Fixes #430` 改为 `Refs #430`，front matter 已补 `tracking-issue: "#430"`，DCO success，普通 checks 包括 e2e 已绿；`tide` pending 是缺 `approved` / `lgtm` labels。#430 仍 open。无需回复已解决的 scope 线程。
- Day44 输出：`internship-reports/day44-sandbox-pool-management-proposal-review.md` 已补 proposal review 方法论、#430 原始讨论问题拆分、#431 架构剖析、从未来开发 owner 视角整理的待问问题、Mermaid 图、GPT image 视觉版 `day44-sandboxpool-gpt-image-architecture.png`、可编辑 draw.io 源 `day44-sandboxpool-architecture.drawio`。核心理解：#431 不是完整 session lifecycle，而是 slow resource track 的 K8s-native capacity/control-plane；对象模型是 `SandboxPoolClass` 全局策略、per-node `SandboxPool` policy snapshot/status、Static Pod/mirror Pod 资源锁、host-level `placeholder-agent`、黑盒 `node-ctl`。
- #431 后续观察点：先等作者是否更新 proposal 正文和真人 maintainer review。最新 Copilot comments 已覆盖 `<5s` mirror pod rebuild、`pause:3.9` vs no-process/no-cgroup、SSA conditions list-map schema、node-ctl endpoint source of truth；不要重复发 omnibus 评论。若用户确认，再考虑单点英文评论：placeholder-agent stale heartbeat / Phase correctness、validation plan、或尚未被正文修复的 API/source-of-truth 问题。不承诺实现。
- GPT image workflow：本地 `/home/agentcube/.agents/skills/gpt-image-draw/SKILL.md` 已跑通。环境有 `OPENAI_API_KEY`；系统 Python 缺 `openai` 且受 PEP 668 限制，已用 `/tmp/gpt-image-draw-venv` 临时 venv 安装依赖。生成后必须用 `file` / `ls -lh` / `view_image` 复核，实际 PNG 尺寸可能不同于请求尺寸。不要打印或提交任何 key。
- Diagram rule：`AGENTS.md` 已新增 `Diagram and Image Generation Guidelines`。Linux 上架构/控制流/状态机/proposal review 图默认用 Mermaid；draw.io 只在需要可编辑画布或复杂布局时用；GPT image draw 用于精致 raster、中文信息图、banner、报告视觉图。精确架构和 review 推理仍以 Mermaid / prose 为准。

## Active Upstream Threads

- #431 SandboxPool proposal：review / observe only，暂不继续发评论，除非用户确认具体英文文本。
- #429 Go toolchain update workflow：已创建 upstream PR，普通 CI 绿，`tide` pending 等 review/labels；不要自动 push/comment。
- #423 runner pinning：open，普通 CI 绿，等 review/labels；不要自动 rebase/push/comment。
- #422 Dependabot Docker base images：open，普通 CI 绿，已解释 `golang` ignore；等 review/labels，不自动改。
- #414 branch push validation：open，普通 CI 绿，等 review/labels，不自动改。
- #403 remove unused agentd：open，等 review/labels；若 reviewer 质疑 Dockerfile scope，按 Day29 口径解释或拆 follow-up。
- #387 agent-sandbox v0.4.6 compatibility：保持 current stable compatibility 口径，不把 v0.5.x / Sleep/Resume / PicoD cleanup 混入；有 review 再小步处理并先确认。
- #385 WarmPoolAvailable PoC：主要等 maintainer review / `lgtm` / `approve` / tide。

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

- For #431: wait for maintainer review. If action is needed, draft one focused English comment at a time and get user confirmation before posting.
- If validating #431 technically, start with a narrow Static Pod resource-accounting / manifest-resize spike: scheduler accounting, mirror Pod rebuild, skip-cgroup metrics/eviction/QoS, kubelet events, CRI `UpdateContainerResources`.
- For Sleep/Resume: keep as design/fake-provider/test-plan unless maintainers clarify ownership. Next useful local work remains Router resume-before-proxy tests or API contract, not broad upstream PR.
- For agent-sandbox v0.5.x: keep separate from #387. Clean follow-up only after official scope decision; disclose clean-install evidence and old CRD storedVersions migration gap.
- For benchmark work: only run tests current environment supports; record OS/kernel/glibc/CPU/K8s/runtime and distinguish local measured data from inference.
- For diagrams/reports: prefer Mermaid in Markdown; use GPT image draw for presentation visuals and store reusable prompts with day prefix.

## Stop Conditions

- Same environment blocker fails three times in a row, such as kind kubelet/cgroup/QoS or `/dev/kvm` absence: stop debugging, record BLOCKED, switch task or machine.
- An upstream PR/issue already has an active assignee working on the same change: do not open duplicate PR; offer review, reproduction, or test feedback instead.
- If a community comment would be speculative without source, code evidence, official docs, or local test evidence: stop and gather evidence first.
