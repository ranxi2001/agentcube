# PROGRESS.md

这个文件只保存下一轮 Agent 需要的短记忆，不做日报。详细过程、证据和长分析放在 `internship-reports/` 与 `internship-reports/todo.md`。

## Goal

当前主线：参与 AgentCube upstream 社区，围绕 agent-sandbox compatibility、SandboxPool / slow resource control plane、Sleep/Resume、SnapStart、observability、SDK lifecycle、benchmark 和开源 review 找可验证、低重复的贡献点。

## Current State

- PR #387 body + conflict：2026-07-14 已按确认把 body 从 750 words / 59 lines 压缩为 266 words / 16 lines；随后将 5 个 DCO commits 从旧基线 `bed6bd4` rebase 到 `upstream/main@3de1272`。唯一冲突是 `go.sum`：main 的 agentd 清理与 #387 的 v0.4.6/K8s 0.35.4 依赖整理重叠，已用目标 `go.mod` + Go 1.26.4 `go mod tidy` 生成结果。用户确认后以精确 lease force-push，PR head `c2633c5 -> 401a00e`；GitHub 回读 `mergeable=true`、`rebaseable=true`，新 SHA 11/11 checks 全绿，Tide 不再报 conflict，只等 `approved`/`lgtm`。
- PR #387 E2E version alignment：用户确认后，test-only commits `cf35435`/`e32a463` 已普通 fast-forward push 到 `origin/feat/agent-sandbox-latest`，PR head 现为 `e32a463`。只改 workflow/E2E 三个文件，不含 #433 auth/RBAC/WM 产品修改；保留 mTLS job并新增 focused CodeInterpreter job，对齐 v0.4.6，按 UID 验证 adoption、session cleanup 和 refill。fork 9/9、official 13/13 checks success；official run `29313632039` 目标 WarmPool 与 load 实际 PASS。
- PR #387 runner follow-up：发现 E2E 是全仓唯一 `ubuntu-22.04` workflow。单行 DCO commit `df8eb9b` 已在 fork-only `ci/pr387-e2e-ubuntu-2404` 验证 9/9 绿；run `29314922163` 两个 job 均确认 `Image: ubuntu-24.04`，WarmPool 目标测试继续 PASS。尚未 push 到 open PR，需用户确认。
- AgentCube PR review skill：独立 `.agents/skills/agentcube-pr-review/` 已完成并用 #387 前向验证；scanner 现在同时识别 dependency/runtime skew 和 target E2E default skip，4 个脚本单测通过。PR management 仍独立负责分支、CI 文案和 upstream 门禁。
- Upstream writing gates：2026-07-14 已增强 `agentcube-issue-discussion` 与 `agentcube-pr-management`，新增 concise references 和 `draft_metrics.py`。规则把 upstream body/comment 定位为证据索引：普通 PR 目标 100-300 visible words，API/CRD/兼容/安全/benchmark/多组件 PR 目标 200-450；超 450 必须说明 long-form exception。近期样本和前向测试记录在 `internship-reports/open-source-contribution-format-standard.md`；没有发布任何 upstream 文本。
- Branch/workflow：当前本地在 `intern`，该分支保存实习报告、TODO、本地 skills 和中文记录；fork `main` 必须保持 upstream clean mirror。记录类 commit 完成后默认 push `origin intern:intern`；任何 upstream issue/PR/comment/review request/maintainer mention 必须先让用户确认 exact target/body。
- Day45 community screening：2026-07-10 已按 assignee、`/assign`、active PR、scope、环境和当前源码筛选最新 open issues；没有可直接认领的 A 级任务。#432 已由 `avinxshKD` 认领并有 #433；#430 已有 #431 proposal；#365 依赖 #366/#379 和 Kuasar/KVM；#348 已由 merged PR #378 修复但 issue 未关闭。旧 #272 与 open PR #249/release policy 有交叉，需先协调，不能直接接手。详见 `internship-reports/day45-latest-community-issue-task-screening.md`。
- Latest upstream baseline：最新观测 `upstream/main fa254b1`；#387 upstream head `401a00e` 当前 `1 behind / 5 ahead`。本地把 5 个 feature commits rebase 到 `fa254b1` 后无冲突，test-only candidate 基于该 rebase head。
- Day44 / PR #431：latest observed force-push head `3d1bd0d`（2026-07-12）。相对 `ef96939` 修改 proposal 72 行，已补独立 agent heartbeat、conditions list-map、optional pointers、Pool immutable fields，并修正 shim/daemon deletion wording；`SP-01`/`SP-02`/`SP-03` resolved。11 checks 全绿，tide 仍缺 `lgtm`/`approved`，没有真人 maintainer review；PR body 仍残留 `<5s` + no-rebuild VPA，已有 Copilot unresolved comment，不重复。
- Day44 输出：`internship-reports/day44-sandbox-pool-management-proposal-review.md` 保存架构剖析和两次回复后的设计迁移；`internship-reports/day44-sandboxpool-pr431-comment-drafts.md` 的 tracker 是唯一索引。当前 `SP-01`/`SP-02`/`SP-09` 已解决；`SP-10` no-process shim 的 `Create`/`Start`/`Wait`/PID/exit contract 已进入本轮 batch review，等待作者定义并在 Phase 2 用 real-node shim spike/e2e 验证。已生成 `day44-sandboxpool-runtimeclass-cri-routing-gap.png`（gpt-image-2，1672x941）及同前缀 prompt。
- #431 后续观察点：`@acsoto` 的 WarmPool relationship 问题仍未进入正文。`SP-10` Task PID/Wait/exit、`SP-11` heartbeat timer、`SP-05` force-finalizer orphan cleanup、`SP-12` atomic per-node Class ownership 已在 [review `4681333180`](https://github.com/volcano-sh/agentcube/pull/431#pullrequestreview-4681333180) 批量发布，绑定 exact head `3d1bd0d`；四条 current-diff thread 分别位于 lines `138/151/535/626`。当前等待作者回复，不追加同类评论。
- #431 实现就绪度：当前 proposal 足够启动本地 CRD/controller happy-path 骨架和 real-node shim feasibility spike，不足以冻结完整 v1alpha1。node-ctl RPC、`EverReady`/Deferred 重启语义、逐 Phase Definition of Done、最小 RBAC/Webhook 依赖先留作内部 implementation gates；作者未回复现有四条前不新增 upstream thread。
- GPT image workflow：本地 `/home/agentcube/.agents/skills/gpt-image-draw/SKILL.md` 已跑通。环境有 `OPENAI_API_KEY`；系统 Python 缺 `openai` 且受 PEP 668 限制，已用 `/tmp/gpt-image-draw-venv` 临时 venv 安装依赖。生成后必须用 `file` / `ls -lh` / `view_image` 复核，实际 PNG 尺寸可能不同于请求尺寸。不要打印或提交任何 key。
- Diagram rule：`AGENTS.md` 已新增 `Diagram and Image Generation Guidelines`。Linux 上架构/控制流/状态机/proposal review 图默认用 Mermaid；draw.io 只在需要可编辑画布或复杂布局时用；GPT image draw 用于精致 raster、中文信息图、banner、报告视觉图。精确架构和 review 推理仍以 Mermaid / prose 为准。
- Weekly report workflow：已迁移到独立本机仓库 `/home/intern-week-mail`，GitHub remote 为 private；唯一 skill source 是该仓库的 `.agents/skills/write-weekly-report-email/`。岗位为“云原生开源实习生”，与真实身份一起只在 ignored `.env` 配置，不得从原始 CCE 示例推断；最终 HTML/subject 允许仅在该 private repo 的 `output/` 版本化。2026-07-10 Week 5 验收稿已按原 Word 六列 `71/350/101/297/79/54pt` 固定网格重新生成，结构校验与 Playwright 截图通过，尚未授权发送邮件。

## Active Upstream Threads

- #431 SandboxPool proposal：[review `4681333180`](https://github.com/volcano-sh/agentcube/pull/431#pullrequestreview-4681333180) 已按用户确认作为一个 `COMMENT` review 发出，含 line 138 Task lifecycle、line 151 heartbeat timer、line 535 orphan cleanup、line 626 atomic per-node Class ownership；状态 `POSTED_WAITING`。等待作者逐条回复或提交新 commit，不自动追评。
- #429 Go toolchain update workflow：已创建 upstream PR，普通 CI 绿，`tide` pending 等 review/labels；不要自动 push/comment。
- #387 agent-sandbox v0.4.6 compatibility：current head `e32a463`，`mergeable=true`/`rebaseable=true`，相对 latest main `1 behind / 7 ahead`；test-only 双 job 已进入 PR，fork 9/9 与 official 13/13 checks 全绿。labels 仅 `kind/feature,size/XXL`，等待 `lgtm`/`approved`；不自动评论或请求 review。
- #385 WarmPoolAvailable PoC：主要等 maintainer review / `lgtm` / `approve` / tide。
- #433 WorkloadManager chart auth：`avinxshKD` 已认领并提交 PR。用户明确要求不与其冲突；#387 candidate 不得加入认证、RBAC、user-scoped client 或 WorkloadManager 产品逻辑，只做测试/版本适配。

## Durable Constraints

- Bash only. Do not run PowerShell snippets or `.ps1` in this workspace.
- Before upstream-facing actions, follow `internship-reports/open-source-contribution-format-standard.md`; upstream text is English, Chinese analysis stays in reports.
- Before presenting an upstream draft, run the relevant concise-first gate and report visible words/nonblank lines. Word budgets trigger review; they never justify removing API/CRD upgrade contracts, security boundaries, benchmark comparability, or material residual risk.
- For issue/PR context, prefer `.agents/skills/agentcube-issue-discussion/scripts/thread_brief.py <number>` first; for PR status use the local PR scripts when useful.
- Keep fork `main` as clean mirror of `upstream/main`; do not commit internship reports, local benchmark data, Chinese notes, or local skills there.
- Use `--force-with-lease`, not plain `--force`, after rebases or mirror resets.
- For official upstream PR branches: clean topic branch from latest `upstream/main`, small scope, DCO signoff, no internship/local artifacts.
- Do not use upstream PRs or self-fork PRs as disposable CI runners. Use local tests or approved fork-only validation branches.

## Current Blockers / Environment Limits

- Current machine has no `/dev/kvm`; CPU virtualization flags are not exposed. Do not claim real MicroVM / KVM / forkd / CubeSandbox virtualization validation here.
- Standard kind Kubernetes has failed on this host at kubelet/cgroup/QoS initialization. Use existing k3s or record KWOK/kind limitations clearly; do not describe kind environment failure as AgentCube code failure.
- Full `go test ./...` can fail in `test/e2e` when Router/WorkloadManager/kubeconfig are not running. For ordinary code changes prefer targeted packages or non-e2e all-Go tests; document exclusions.
- Go 1.26.4 下 `pkg/store/TestInitStore/return_error_when_initRedisStore_fails` 的 gomonkey patch 未生效，会落到真实 Redis 初始化并报 `missing env var REDIS_ADDR`；已在纯 `upstream/main@3de1272` 同样复现。#387 不修这个独立基线问题。
- OpenSandbox / Agent Substrate runtime smoke tests are not yet deployed locally; use `.agents/skills/sandbox-runtime-smoke/SKILL.md` if resuming that work.
- Do not run `make gen-check` and `make build-all` concurrently; both can touch generated/tidy state.
- Weekly report evidence is local-first. Use `/home/intern-week-mail` for the workflow, keep identity configuration untracked, keep rendered identity output only in that verified private repo, and use GitHub only for authoritative PR/Issue/review state.

## Ruled Out / Do Not Repeat

- Do not treat `WarmPoolNotFound` as a stable Warning Event requirement; it may be normal controller cache timing.
- Do not repeat #379 comments already covered by Copilot, especially duplicate `ctrl.SetupSignalHandler()` observations.
- Do not simplify `agent-sandbox v0.5.0rc1` incompatibility to “pseudo-version”; the real issues were v1alpha1 package removal, `Sandbox.spec.replicas` -> `OperatingMode`, and claim `TemplateRef` -> required `WarmPoolRef`.
- Do not call AgentCube “E2B-compatible” based only on E2B-like behavior; Day33 split compatibility into SDK, REST lifecycle, envd process/filesystem RPC, template/snapshot/network/volume.

## Next

- For #387: test-only update 已推送并通过 official checks；runner 单行 follow-up `df8eb9b` 已完成 fork 验证，下一步经用户确认后 fast-forward 到 open PR，再观察 official checks。不要追加 #433 auth/RBAC 修改，也不要自动评论或请求 review。
- Community tasks：本轮不 `/assign`。下一次先刷新 open issue/PR；只有新的 focused unowned issue，或 maintainer 将 #386/#272 拆成 dedicated sub-issue，才进入认领准备。#433 若做协作，先在临时 worktree 完成 Helm render/lint 和 auth/RBAC focused validation，再向用户提交 exact review draft。
- For #431: 4-comment batch review 已发布并完成 server-side 回读。不要回复已解决的 resize/RuntimeClass threads，也不要重复最新 Copilot 的 PR-body mismatch；先等待作者回复或新 commit，再逐 thread 判断 `RESOLVED`、窄追问或 Phase 2 spike/e2e gate。node-ctl RPC、`EverReady`、test DoD 和 RBAC/Webhook 顺序先写在 Day44，不立即追加评论；任何新的 upstream 回复仍需用户确认 exact body。
- If validating #431 technically, focus on `SP-10` containerd Task lifecycle mapping plus kubelet admission/scheduler accounting for the rebuild window. Keep native `/resize` out of the design; require a real-node shim spike covering task PID/wait/exit, rebuild-vs-delete discrimination, node-ctl continuity, mirror gap, and conflicting Pod admission.
- For Sleep/Resume: keep as design/fake-provider/test-plan unless maintainers clarify ownership. Next useful local work remains Router resume-before-proxy tests or API contract, not broad upstream PR.
- For agent-sandbox v0.5.x: keep separate from #387. Clean follow-up only after official scope decision; disclose clean-install evidence and old CRD storedVersions migration gap.
- For benchmark work: only run tests current environment supports; record OS/kernel/glibc/CPU/K8s/runtime and distinguish local measured data from inference.
- For diagrams/reports: prefer Mermaid in Markdown; use GPT image draw for presentation visuals and store reusable prompts with day prefix.
- For the Week 5 email: review `/home/intern-week-mail/output/week5/week5-weekly-report-email.html`; do not send until recipients, CC, subject, final body, and attachments receive explicit approval.

## Stop Conditions

- Same environment blocker fails three times in a row, such as kind kubelet/cgroup/QoS or `/dev/kvm` absence: stop debugging, record BLOCKED, switch task or machine.
- An upstream PR/issue already has an active assignee working on the same change: do not open duplicate PR; offer review, reproduction, or test feedback instead.
- If a community comment would be speculative without source, code evidence, official docs, or local test evidence: stop and gather evidence first.
