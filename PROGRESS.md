# PROGRESS.md

这个文件只保存下一轮 Agent 需要的短记忆，不做日报。详细过程、证据和长分析放在 `internship-reports/` 与 `internship-reports/todo.md`。

## Goal

当前主线：参与 AgentCube upstream 社区，围绕 agent-sandbox compatibility、SandboxPool / slow resource control plane、Sleep/Resume、SnapStart、observability、SDK lifecycle、benchmark 和开源 review 找可验证、低重复的贡献点。

## Current State

- PR #387 merged：2026-07-16 `@acsoto` `/lgtm` 后，`@RainbowMango` 于 08:35:56 UTC `/approve`，Tide 在 08:37:15 UTC 合并；merge commit `146b75f` 的两个 parent 是旧 main `fa254b1` 与 exact head `95fae1f`。`tide/merge-method-squash` 在批准前被移除，因此最终是 two-parent merge，不是 squash；feature head 本身仍只有一个 DCO commit。完整证据见 Day30。
- Day48 post-merge / OWNERS：Pod cleanup branch `cleanup/remove-sandbox-pod-fallback@eefce59` 与 RainbowMango OWNERS branch `owners/add-rainbowmango@63bea7a` 已 push 到 fork，upstream PR 均未创建。用户澄清这是 formalize existing duties，不是新成员晋升；公开记录支持 23 个 reviewed PR / 19 个 `APPROVED` review，并以 #386 版本 proposal 台账、#430/#431 提案推进、#396 scope/trade-off 和 #419/#420 根因确认说明质量。因此不新建 membership issue，PR 使用 `NONE`。
- AgentCube PR review skill：独立 `.agents/skills/agentcube-pr-review/` 已完成并用 #387 前向验证；scanner 同时识别 dependency/runtime skew 和 target E2E default skip。2026-07-15 follow-up 将 live/cache freshness、真实 `%w` chain、progress-marker commit point 和“timer 不会自动约束 blocking I/O”纳入 checks、architecture map 与 pattern library；skill schema、6 个脚本单测、diff check 和 fresh-context raw-source review 通过。PR management 仍独立负责分支、CI 文案和 upstream 门禁。
- Review communication learning：2026-07-16 从 Karmada PR #7764 作者明确“难理解”的真实 miss 提炼 standalone comprehension 与 visualization gates。非平凡 finding 必须自包含 observation/counterexample/reasoning/action，并区分 signal 与 claim；3+ actor/state/step、竞争原因、retry/cleanup/recovery 或 current/proposed 默认比较 4-10 节点 inline Mermaid。`agentcube-pr-management` 已接入 exact-text/render gate；两场 fresh-context teach-back 经一次 sequence `Note` 分号 parse failure 修正后均实际渲染并视觉通过，不复制 Karmada 专属结论。
- Production reachability learning：已把 Karmada #7623 的方法吸收到 AgentCube PR review / issue discussion skills；bug claim 现在必须区分 observed、source-proven reachable latent 和 mock-only hypothetical，并先证明真实 producer、受支持前置状态与 recovery/self-heal behavior。两个 skill 校验、10 个脚本测试、三场景 fresh-context forward test 和 diff check 均通过；未修改任何 upstream 评论。
- Maintainer review learning：2026-07-14 已抽样 `@RainbowMango` 在 AgentCube/Karmada 2020-2026 的 15 个有效 review PR，排除 reviewer-authored 与 approval-only 噪音；[Day46](internship-reports/day46-rainbowmango-maintainer-review-method-study.md) 总结 problem-first、scope、existing ownership/precedent、shared helper routing、status transition、second-round 方法。`agentcube-pr-review` 新增 history extractor、2 tests、maintainer methods reference 和 4 条 proven patterns。
- Maintainer writing learning：Day46 已追加 `@zhzhuang-zju` 17 个 issue / 12 个 PR 分层样本；确认 issue 常承担 evidence/causal chain/umbrella ledger，PR 聚焦 old -> new behavior、issue relation、compatibility/non-goal。新增 paginated contributor writing extractor 与 4 tests，并把 thin API body、空模板槽位、merge bias 作为反例写入 issue/PR concise references。
- Generic development skills：`/home/Onefly-Dev-Skills` / `ranxi2001/Onefly-Dev-Skills@95e1f72` 已新增通用 `github-code-review`，并升级 issue/proposal/writing-history 与 PR concise/behavior workflow；根 `AGENTS.md` 规定通用仓库只保存跨项目稳定方法，AgentCube 组件/分支/环境规则继续留在本仓库 overlay。
- Upstream writing gates：2026-07-14 已增强 `agentcube-issue-discussion` 与 `agentcube-pr-management`，新增 concise references 和 `draft_metrics.py`。规则把 upstream body/comment 定位为证据索引：普通 PR 目标 100-300 visible words，API/CRD/兼容/安全/benchmark/多组件 PR 目标 200-450；超 450 必须说明 long-form exception。近期样本和前向测试记录在 `internship-reports/open-source-contribution-format-standard.md`；没有发布任何 upstream 文本。
- Branch/workflow：当前本地在 `intern`，该分支保存实习报告、TODO、本地 skills 和中文记录；fork `main` 必须保持 upstream clean mirror。记录类 commit 完成后默认 push `origin intern:intern`；任何 upstream issue/PR/comment/review request/maintainer mention 必须先让用户确认 exact target/body。
- Day45 community screening：2026-07-10 已按 assignee、`/assign`、active PR、scope、环境和当前源码筛选最新 open issues；没有可直接认领的 A 级任务。#432 已由 `avinxshKD` 认领并有 #433；#430 已有 #431 proposal；#365 依赖 #366/#379 和 Kuasar/KVM；#348 已由 merged PR #378 修复但 issue 未关闭。旧 #272 与 open PR #249/release policy 有交叉，需先协调，不能直接接手。详见 `internship-reports/day45-latest-community-issue-task-screening.md`。
- Latest upstream baseline：最新观测 `upstream/main 146b75f`，即 #387 merge commit；PR 的 18-file `+1189/-312` patch 和 exact head `95fae1f` 已进入 main。`origin/main` 当前落后 upstream 7 commits，本轮只读观察，未自动重置或推送 fork mirror。
- Day44 / PR #431：2026-07-15 latest head `49576e8`（2 commits，`7 behind / 2 ahead`），1 个 proposal 文件；11 个普通 checks + DCO 成功，Tide pending 等 `lgtm`/`approved`。`f380208..49576e8` 为 `+60/-50`：采用 event-driven status + Lease heartbeat、`corev1.ResourceList`，删除冗余 `NodeSelector`，扩展 selector/字段合同与 shim/bootstrap 说明；新文本仍误称 Lease cluster-scoped，proposal 尚未 ready。
- PR #400 latest review：作者在 review `4700751218` 后快速 force-push/rebase 到 `b8c4ed5`，当前 `0 behind / 4 ahead`。P1 method cardinality 已完整修复；60s bucket residual scope 已记录但按用户判断不阻塞本 PR。感谢/review-complete 评论已发布为 `4977532327`；`/lgtm` 被 Prow 拒绝，因为只有 collaborators 可改 label。新 head unit/race/focused 100-repeat、tidy、merge-tree 和 12/12 checks 均通过。
- Day44 输出：主报告与 comment tracker 已同步 #431 最新 8-thread review；新增 3 页可编辑 draw.io：review 收敛、API current-vs-direction、RuntimeClass node contract。源为 `day44-pr431-latest-review-api-runtime-map.drawio`，三个 `*.drawio.png` 均内嵌源数据并完成结构/视觉检查。
- #431 后续观察点：GraphQL 在 `49576e8` 上显示 95 threads，5 个 current-diff active、6 个 unresolved outdated；current active 中 3 条来自 `@RainbowMango`（字段合同、RuntimeClass 前置、validation comment ownership），2 条来自 Copilot（Lease namespace 与 required/omitempty）。11 个 checks 全绿但仍无 `lgtm/approve`。
- #431 最新 review 重点：阻止 v1alpha1 API/部署合同过早冻结。作者已采纳单一 Selector、`ResourceList`、Lease heartbeat 和更完整字段/shim contract；仍需校准 percentage mode、inert `NodeCtl` 信息字段、Lease namespace/RBAC、RuntimeClass 节点 bootstrap、manifest recovery admission gap 和真实 shim/kubelet spike。采纳建议不等于 proposal 已通过。
- #431 fresh-context 深审：在完整 93 threads duplicate audit 后新增 `SP-28..SP-38`。可证明的 reachable latent design defects 是 status webhook 阻断 controller writer、253-char name 复制到 63-char label/255-char filename、Ready 不检查 current generation、同名 Node 缺 UID incarnation fence、组合 Phase priority 遮蔽 5min Unready、SSA 1.18 compatibility 错误；agent `endpoints (full)` 是独立 least-privilege 缺口。Cleanup ack、runtime v2 crash/rebuild、Static Pod overhead 双视图和 stale resize operation 仍是 risk/question，不宣称 observed bug。
- #431 实现就绪度：可以继续 CRD/controller happy-path 骨架和 real-node shim feasibility spike；完整 schema 与 Phase 2 runtime contract 暂不 freeze。模板 Class→Pool/agent/manifest 传播、generic applied-resource status、bootstrap failure/recovery 和真实 kubelet+containerd spike 仍未闭合。
- GPT image workflow：本地 `/home/agentcube/.agents/skills/gpt-image-draw/SKILL.md` 已跑通。环境有 `OPENAI_API_KEY`；系统 Python 缺 `openai` 且受 PEP 668 限制，已用 `/tmp/gpt-image-draw-venv` 临时 venv 安装依赖。生成后必须用 `file` / `ls -lh` / `view_image` 复核，实际 PNG 尺寸可能不同于请求尺寸。不要打印或提交任何 key。
- Diagram rule：`AGENTS.md` 已新增 `Diagram and Image Generation Guidelines`。Linux 上架构/控制流/状态机/proposal review 图默认用 Mermaid；draw.io 只在需要可编辑画布或复杂布局时用；GPT image draw 用于精致 raster、中文信息图、banner、报告视觉图。精确架构和 review 推理仍以 Mermaid / prose 为准。
- Draw.io skill sync：2026-07-15 已将 Karmada intern worktree `58761535f08a` 的 `drawio-skill` 精确镜像到本仓库，共 62 个文件；skill metadata、Python compile、JSON/gzip、CLI help、workflow import、现有图校验和 Draw.io -> Mermaid 冒烟均通过。本机缺可选 Graphviz `dot`。持久容器 `agentcube-drawio-pr431` 已安装 draw.io CLI `30.3.11` + xvfb/libasound2，并按用户要求保留供后续导出，不要删除。
- Project Mermaid skill sync：2026-07-16 已更新到 Karmada clean commit `462c6acd8`，共 10 个文件；新增 inline GitHub review mode、current/proposed 颜色/证据边界规则和 `proposal-change-template.mmd + PNG`，继续保留两个旧模板的 EOF 空行规范化。Schema、renderer compile/help、data-flow/sequence/proposal 三模板官方 CLI 11.16.0 npx render 通过；proposal `1531x554` preview 重渲染 byte-identical 并完成原图检查。
- PR #387 visuals：Day30 canonical Mermaid 精确比较 `3de1272d` / v0.1.1 与 `95fae1f8` / v0.4.6，按 7 组同编号节点横向标明差异；另用 gpt-image-2 生成 `1672x941` changes 信息图，覆盖依赖、池化、身份、readiness/Store、生命周期/验证与 scope boundary。两张 PNG 均完成原图视觉检查，Mermaid/源码仍是精确真源。
- Day47 OpenSandbox refresh：基于官方 159 个 component releases、2026-06-16 至 07-15 的 116 个 merged PR 和最近 50 个非机器人语义样本完成报告。主线是 execd isolated session/bwrap、client pool 生命周期、安全/Credential Vault/multi-tenancy、K8s 运维、OTel 与 release governance；server/controller 正式版明显落后 main，必须区分 shipped 与 merged。详见 `internship-reports/day47-opensandbox-releases-and-merged-pr-trends.md`。
- Weekly report workflow：已迁移到 private repo `/home/intern-week-mail`；身份只从 ignored `.env` 注入。2026-07-15 新增 Week 4/5 双层总结：第一层用于公司成果提炼，第二层保留工程学习、失败和证据；Week 5 源数据已按 GitHub 回读把 #431 从 2/2 校准为 3/3 review 点，并区分已验证的默认 AgentRuntime mTLS 与未验证的 direct WorkloadManager harness。现有 HTML 尚未按新源重渲染，也未授权发送。

## Active Upstream Threads

- #431 SandboxPool proposal：latest head `49576e8` 已吸收一批 maintainer API/Lease/runtime 建议；当前 5 条 current active、6 条 unresolved outdated，仍无 review decision。先等待作者继续收敛，不自动追评。
- #429 Go toolchain update workflow：已创建 upstream PR，普通 CI 绿，`tide` pending 等 review/labels；不要自动 push/comment。
- #400 PicoD Prometheus metrics：current head `b8c4ed5`，`MERGEABLE`，12 checks/DCO 绿。我们的 review 已公开完成：https://github.com/volcano-sh/agentcube/pull/400#issuecomment-4977532327；Prow 因 collaborator-only 权限拒绝 `/lgtm`，label 仍需 maintainer/collaborator 添加。不重复命令、不自动追评。
- #385 WarmPoolAvailable PoC：主要等 maintainer review / `lgtm` / `approve` / tide。
- #433 WorkloadManager chart auth：作者于 2026-07-16 关闭 PR；`@acsoto` 指出当前 `EnableAuth` 把 caller authentication 与 credential delegation 耦合，作者在 permission model 未明确前停止推进。该意见不是 `@RainbowMango` review。不要复活旧分支；等待新的 auth/RBAC contract 或 replacement PR。

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

- For #387：已合并，不再请求 review/approval 或修改该 PR。stable v0.4.6 compatibility 前置已解除；v0.5 adapter 必须作为独立 scope 基于新 main 重新验证。#433 已关闭，auth/RBAC 等新合同，不混入 #387 follow-up。
- For RainbowMango OWNERS：fork branch `owners/add-rainbowmango@63bea7a` 已 push，当前按 formalize existing review/approval responsibilities 处理，不关联新 issue。等待用户确认更新后的 exact target/title/body、两行 diff 与 YAML/order/DCO validation 后创建 PR；不得把 approval 数量替代为唯一能力证据，正文继续保留 issue/review/outcome 样本。
- For Pod informer cleanup：fork branch `cleanup/remove-sandbox-pod-fallback@eefce59` 已 push。等待用户单独确认 title、208-word body、6-file `+45/-231` diff、unit/race/repeat/lint/qualified-Helm evidence 后再创建独立 PR；默认 PATH 无 Helm，必须准确写已有 `v3.18.4` binary 的 PATH-qualified 验证。
- Community tasks：本轮不 `/assign`。下一次先刷新 open issue/PR；只有新的 focused unowned issue，或 maintainer 将 #386/#272 拆成 dedicated sub-issue，才进入认领准备。#433 已关闭，不基于旧实现另开重复 auth PR。
- For #431: 当前固定 head `49576e8`；不新增评论。等待 5 个 current active 和 6 个 outdated thread 收敛；新 push 后先复核 Lease namespace/RBAC、required ResourceList serialization、字段 comments/RuntimeClass bootstrap，再重验 `SP-28` status caller-to-field matrix、`SP-29` name/label/path budget 和 `SP-30` generation freshness。任何 upstream 回复仍需用户确认 exact body。
- For #400: 我们的 review 已结束。保留 Python SDK `120s`、LangChain `1800s`、server 无 max 的 residual scope 供后续设计使用，但不继续扩张本 PR；等待 collaborator `lgtm` / approver，不重复 `/lgtm` 或自动 mention。
- For future reviews: 先填 `Claimed problem / Observable caller / Expected contract / PR scope` problem card；shared helper 先画 kind/scope/destination/owner matrix；大型 PR 明确 Round 1 architecture 与 Round 2 semantic-preservation。评论发布前做 standalone teach-back；关系达到 3+ nodes、竞争原因或时序时优先 inline Mermaid，不以评论已回复代替 ready。
- For future writing: issue 先填 observable problem、decisive evidence、expected contract/decision、independent tasks、unknowns；PR 先填 old/new behavior、issue relation、validation、compatibility/non-goal。个人历史只用于校准，仍以 AgentCube 官方模板和 concise gate 为准。
- If validating #431 technically, focus on `SP-10` containerd Task lifecycle mapping plus kubelet admission/scheduler accounting for the rebuild window. Keep native `/resize` out of the design; require a real-node shim spike covering task PID/wait/exit, rebuild-vs-delete discrimination, node-ctl continuity, mirror gap, and conflicting Pod admission.
- For Sleep/Resume: keep as design/fake-provider/test-plan unless maintainers clarify ownership. Next useful local work remains Router resume-before-proxy tests or API contract, not broad upstream PR.
- For agent-sandbox v0.5.x: keep separate from #387. Clean follow-up only after official scope decision; disclose clean-install evidence and old CRD storedVersions migration gap.
- For benchmark work: only run tests current environment supports; record OS/kernel/glibc/CPU/K8s/runtime and distinguish local measured data from inference.
- For diagrams/reports: 数据流、时序、重试和小型生命周期图使用 `$project-mermaid`，保留 canonical `.mmd` 与生成 PNG；复杂架构/泳道/精确布局使用 draw.io，presentation visuals 使用 GPT image draw，并按 day prefix 保存资产。
- For the Week 5 email: 先按已校准源数据重新渲染并 review `/home/intern-week-mail/output/week5/week5-weekly-report-email.html`；未逐项确认 recipients、CC、subject、final body 和 attachments 前不得发送。

## Stop Conditions

- Same environment blocker fails three times in a row, such as kind kubelet/cgroup/QoS or `/dev/kvm` absence: stop debugging, record BLOCKED, switch task or machine.
- An upstream PR/issue already has an active assignee working on the same change: do not open duplicate PR; offer review, reproduction, or test feedback instead.
- If a community comment would be speculative without source, code evidence, official docs, or local test evidence: stop and gather evidence first.
