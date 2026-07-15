# PROGRESS.md

这个文件只保存下一轮 Agent 需要的短记忆，不做日报。详细过程、证据和长分析放在 `internship-reports/` 与 `internship-reports/todo.md`。

## Goal

当前主线：参与 AgentCube upstream 社区，围绕 agent-sandbox compatibility、SandboxPool / slow resource control plane、Sleep/Resume、SnapStart、observability、SDK lifecycle、benchmark 和开源 review 找可验证、低重复的贡献点。

## Current State

- PR #387 body + conflict：2026-07-14 已按确认把 body 从 750 words / 59 lines 压缩为 266 words / 16 lines；随后将 5 个 DCO commits 从旧基线 `bed6bd4` rebase 到 `upstream/main@3de1272`。唯一冲突是 `go.sum`：main 的 agentd 清理与 #387 的 v0.4.6/K8s 0.35.4 依赖整理重叠，已用目标 `go.mod` + Go 1.26.4 `go mod tidy` 生成结果。用户确认后以精确 lease force-push，PR head `c2633c5 -> 401a00e`；GitHub 回读 `mergeable=true`、`rebaseable=true`，新 SHA 11/11 checks 全绿，Tide 不再报 conflict，只等 `approved`/`lgtm`。
- PR #387 E2E version alignment：test-only commits `cf35435`/`e32a463` 保留 mTLS job并新增 focused CodeInterpreter job，对齐 v0.4.6，按 UID 验证 adoption、session cleanup 和 refill；后续 runner/codegen commits 已把 current head 推进到 `9c3402e`。official run `29319618875` 确认两个 job 均为 Ubuntu 24.04 且安装 controller v0.4.6；focused WarmPool、UID cleanup、load、Python、LangChain、MCP 实际 PASS，不是 skip。
- PR #387 runner + reviewer note：单行 DCO `df8eb9b` 已把全仓唯一残留的 E2E `ubuntu-22.04` 对齐到 24.04，并 fast-forward push 到 open PR；fork 9/9、official 12/12 success，两个 E2E job 确认 24.04 且 WarmPool PASS。132-word Mermaid reviewer comment 已按确认发布：https://github.com/volcano-sh/agentcube/pull/387#issuecomment-4966669956 。
- AgentCube PR review skill：独立 `.agents/skills/agentcube-pr-review/` 已完成并用 #387 前向验证；scanner 现在同时识别 dependency/runtime skew 和 target E2E default skip，4 个脚本单测通过。PR management 仍独立负责分支、CI 文案和 upstream 门禁。
- Production reachability learning：已把 Karmada #7623 的方法吸收到 AgentCube PR review / issue discussion skills；bug claim 现在必须区分 observed、source-proven reachable latent 和 mock-only hypothetical，并先证明真实 producer、受支持前置状态与 recovery/self-heal behavior。两个 skill 校验、10 个脚本测试、三场景 fresh-context forward test 和 diff check 均通过；未修改任何 upstream 评论。
- Maintainer review learning：2026-07-14 已抽样 `@RainbowMango` 在 AgentCube/Karmada 2020-2026 的 15 个有效 review PR，排除 reviewer-authored 与 approval-only 噪音；[Day46](internship-reports/day46-rainbowmango-maintainer-review-method-study.md) 总结 problem-first、scope、existing ownership/precedent、shared helper routing、status transition、second-round 方法。`agentcube-pr-review` 新增 history extractor、2 tests、maintainer methods reference 和 4 条 proven patterns。
- Maintainer writing learning：Day46 已追加 `@zhzhuang-zju` 17 个 issue / 12 个 PR 分层样本；确认 issue 常承担 evidence/causal chain/umbrella ledger，PR 聚焦 old -> new behavior、issue relation、compatibility/non-goal。新增 paginated contributor writing extractor 与 4 tests，并把 thin API body、空模板槽位、merge bias 作为反例写入 issue/PR concise references。
- Generic development skills：`/home/Onefly-Dev-Skills` / `ranxi2001/Onefly-Dev-Skills@95e1f72` 已新增通用 `github-code-review`，并升级 issue/proposal/writing-history 与 PR concise/behavior workflow；根 `AGENTS.md` 规定通用仓库只保存跨项目稳定方法，AgentCube 组件/分支/环境规则继续留在本仓库 overlay。
- Upstream writing gates：2026-07-14 已增强 `agentcube-issue-discussion` 与 `agentcube-pr-management`，新增 concise references 和 `draft_metrics.py`。规则把 upstream body/comment 定位为证据索引：普通 PR 目标 100-300 visible words，API/CRD/兼容/安全/benchmark/多组件 PR 目标 200-450；超 450 必须说明 long-form exception。近期样本和前向测试记录在 `internship-reports/open-source-contribution-format-standard.md`；没有发布任何 upstream 文本。
- Branch/workflow：当前本地在 `intern`，该分支保存实习报告、TODO、本地 skills 和中文记录；fork `main` 必须保持 upstream clean mirror。记录类 commit 完成后默认 push `origin intern:intern`；任何 upstream issue/PR/comment/review request/maintainer mention 必须先让用户确认 exact target/body。
- Day45 community screening：2026-07-10 已按 assignee、`/assign`、active PR、scope、环境和当前源码筛选最新 open issues；没有可直接认领的 A 级任务。#432 已由 `avinxshKD` 认领并有 #433；#430 已有 #431 proposal；#365 依赖 #366/#379 和 Kuasar/KVM；#348 已由 merged PR #378 修复但 issue 未关闭。旧 #272 与 open PR #249/release policy 有交叉，需先协调，不能直接接手。详见 `internship-reports/day45-latest-community-issue-task-screening.md`。
- Latest upstream baseline：最新观测 `upstream/main fa254b1`；#387 upstream head `9c3402e` 当前 `1 behind / 9 ahead`。`git merge-tree` 无冲突，临时物化 merged tree 后 `go test ./pkg/workloadmanager -count=1` 通过；临时 worktree 已清理。
- Day44 / PR #431：2026-07-15 latest head `f380208`（作者审计期间再次 force-push/squash），1 个 proposal 文件 `+761/-0`；相对 `upstream/main` 为 `5 behind / 1 ahead`，结构合并干净，10 个 checks + DCO 全绿，Tide 仅缺 `lgtm`/`approved`。`c2f2502..f380208` 为 `+49/-31`：title、containerd link、admin motivation、manifest self-healing、numeric priority、Phase recovery shortcut、orphan GET/error、node conflict 与 status identity boundary 均有实质补充。
- PR #400 latest review：2026-07-15 固定 head `0d4576f` / main `fa254b1`，`5 behind / 3 ahead`，结构合并和 merged-tree `go test ./pkg/picod` 均通过；head unit、race、metrics 100-repeat 通过。旧 413、unmatched path、panic coverage 已修复；新 P1 是 `metrics.go:111-112` 原始 HTTP method 造成无界 counter/histogram label cardinality，P2 是 DefBuckets 最高有限 10s 与 execute 默认 60s 不匹配。用户确认后已发布 review `4700751218`，完整证据在 Day31。
- Day44 输出：`internship-reports/day44-sandbox-pool-management-proposal-review.md` 保存架构剖析和两次回复后的设计迁移；`internship-reports/day44-sandboxpool-pr431-comment-drafts.md` 的 tracker 是唯一索引。当前 `SP-01`/`SP-02`/`SP-09` 已解决；`SP-10` no-process shim 的 `Create`/`Start`/`Wait`/PID/exit contract 已进入本轮 batch review，等待作者定义并在 Phase 2 用 real-node shim spike/e2e 验证。已生成 `day44-sandboxpool-runtimeclass-cri-routing-gap.png`（gpt-image-2，1672x941）及同前缀 prompt。
- #431 后续观察点：GraphQL 在 `f380208` 上显示 85 threads，6 个 current-diff active、3 个 unresolved outdated。Active 为 maintainer 的 component naming、manifest self-healing、Phase explanation、status write scalability，以及我们的 Deferred resize、status RBAC。旧 review 中 Task synthetic contract、heartbeat timer、numeric priority、orphan API semantics、atomic ownership、agent recovery shortcut已进入正文；Deferred 只 `PARTIAL`，status RBAC 只定义方向。
- #431 实现就绪度：proposal 足够启动 CRD/controller happy-path 骨架与 real-node shim feasibility spike，不足以冻结完整 v1alpha1。当前 P1 是新增 staged-resize 表与 manifest-first flow 相冲突、`restart node-ctl` 与“不停止 node-ctl”相冲突、PoolInfo 无 CPU applied value；另有 Phase Ready predicate 漂移、每节点 30s status + controller sweep 的规模预算、per-node identity provisioning 未闭合。
- #431 maintainer review：`@RainbowMango` review 仍未给 `lgtm/approve`。Title、containerd reference、admin motivation 已吸收；`placeholder-agent` 命名被作者暂缓，`node-ctl` 替代名仍未知。Maintainer 继续追问 manifest 被删、Phase/aggregation 和上千节点 status write；后两者尤其未闭合。
- GPT image workflow：本地 `/home/agentcube/.agents/skills/gpt-image-draw/SKILL.md` 已跑通。环境有 `OPENAI_API_KEY`；系统 Python 缺 `openai` 且受 PEP 668 限制，已用 `/tmp/gpt-image-draw-venv` 临时 venv 安装依赖。生成后必须用 `file` / `ls -lh` / `view_image` 复核，实际 PNG 尺寸可能不同于请求尺寸。不要打印或提交任何 key。
- Diagram rule：`AGENTS.md` 已新增 `Diagram and Image Generation Guidelines`。Linux 上架构/控制流/状态机/proposal review 图默认用 Mermaid；draw.io 只在需要可编辑画布或复杂布局时用；GPT image draw 用于精致 raster、中文信息图、banner、报告视觉图。精确架构和 review 推理仍以 Mermaid / prose 为准。
- Weekly report workflow：已迁移到独立本机仓库 `/home/intern-week-mail`，GitHub remote 为 private；唯一 skill source 是该仓库的 `.agents/skills/write-weekly-report-email/`。岗位为“云原生开源实习生”，与真实身份一起只在 ignored `.env` 配置，不得从原始 CCE 示例推断；最终 HTML/subject 允许仅在该 private repo 的 `output/` 版本化。2026-07-10 Week 5 验收稿已按原 Word 六列 `71/350/101/297/79/54pt` 固定网格重新生成，结构校验与 Playwright 截图通过，尚未授权发送邮件。

## Active Upstream Threads

- #431 SandboxPool proposal：两个用户确认的 `COMMENT` review 均为 `POSTED_WAITING`：[review `4681333180`](https://github.com/volcano-sh/agentcube/pull/431#pullrequestreview-4681333180) 和 [review `4693432020`](https://github.com/volcano-sh/agentcube/pull/431#pullrequestreview-4693432020)。`@RainbowMango` 的 maintainer [review `4692780216`](https://github.com/volcano-sh/agentcube/pull/431#pullrequestreview-4692780216) 仍在进行，先等待其完成和作者更新，不自动追评。
- #429 Go toolchain update workflow：已创建 upstream PR，普通 CI 绿，`tide` pending 等 review/labels；不要自动 push/comment。
- #400 PicoD Prometheus metrics：当前 `MERGEABLE`，已有 `lgtm`，checks/DCO 绿，Tide 只缺 `approved`。P1/P2 已作为一次 `COMMENT` review 发布：https://github.com/volcano-sh/agentcube/pull/400#pullrequestreview-4700751218；等待作者回复或新 push，不自动追评。
- #387 agent-sandbox v0.4.6 compatibility：current head `9c3402e`，`mergeable=true`，可执行 checks 全绿；Tide pending 仅因无 `lgtm`/`approved`。最终架构 review 未发现 lifecycle/store/delete/GC 新缺陷；保留一个 cross-PR 中风险：auth caller client 对 Claim/Sandbox 的永久 GET 错误会重试 2 分钟并误报 504。NetworkPolicy `Unmanaged` 是保持既有连通性的已知安全设计债务。详见 Day30；不自动追加 upstream 评论。
- #385 WarmPoolAvailable PoC：主要等 maintainer review / `lgtm` / `approve` / tide。
- #433 WorkloadManager chart auth：2026-07-14 最新 head 仍是 `fe295b6`，3 个 chart 文件 `+32/-0`，没有作者承诺 rework 后的新 push。当前代码仍给 Router cluster-wide Sandbox/SandboxClaim `create/delete`，未包含 #387 Claim readiness 所需 `get`；maintainer 质疑 auth 与 credential delegation 耦合，作者口头计划改为 Router token 只认证、WM 用自身 ServiceAccount，但最终 permission contract 尚未确定。用户明确要求不与其冲突；只有 head 变化或 maintainer 明确设计后才重新审计。

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

- For #387: test-only update、Ubuntu 24.04 runner、codegen guidance、Mermaid reviewer note 和最终 architecture review 均完成。下一步只等待 maintainer review/labels；不要追加 #433 auth/RBAC 修改。观察 #433 head 是否离开 `fe295b6`，新 push 后重点检查 WM ServiceAccount、Claim/Sandbox GET、Forbidden terminal classification、rollback 与 auth-enabled warm-pool tests。
- Community tasks：本轮不 `/assign`。下一次先刷新 open issue/PR；只有新的 focused unowned issue，或 maintainer 将 #386/#272 拆成 dedicated sub-issue，才进入认领准备。#433 若做协作，先在临时 worktree 完成 Helm render/lint 和 auth/RBAC focused validation，再向用户提交 exact review draft。
- For #431: 当前固定 head `f380208`；不新增评论。等待 6 个 active thread 收敛，优先复核 resize 实际调用顺序/node-ctl continuity、Phase aggregate predicate、status QPS budget 与 per-node identity provisioning。任何 upstream 回复仍需用户确认 exact body。
- For #400: review 已发布；下一步只在作者回复或新 push 后复核 method normalization、bounded-cardinality test、bucket range 和 long-running test。新 upstream 回复仍需用户确认 exact text。
- For future reviews: 先填 `Claimed problem / Observable caller / Expected contract / PR scope` problem card；shared helper 先画 kind/scope/destination/owner matrix；大型 PR 明确 Round 1 architecture 与 Round 2 semantic-preservation，不以评论已回复代替 ready。
- For future writing: issue 先填 observable problem、decisive evidence、expected contract/decision、independent tasks、unknowns；PR 先填 old/new behavior、issue relation、validation、compatibility/non-goal。个人历史只用于校准，仍以 AgentCube 官方模板和 concise gate 为准。
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
