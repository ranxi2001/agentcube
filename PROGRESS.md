# PROGRESS.md

这个文件只保存下一轮 Agent 需要的短记忆，不做日报。详细过程、证据和长分析放在 `internship-reports/` 与 `internship-reports/todo.md`。

## Goal

当前主线：参与 AgentCube upstream 社区，围绕 agent-sandbox compatibility、SandboxPool / slow resource control plane、Sleep/Resume、SnapStart、observability、SDK lifecycle、benchmark 和开源 review 找可验证、低重复的贡献点。

## Current State

- PR #387 current：单个 DCO commit `95fae1f`，`MERGEABLE`，exact SHA official 12/12 checks 全绿；普通 E2E 7m53s、CodeInterpreter E2E 9m28s，Tide 只缺 `approved`/`lgtm`。Claim in-flight GET deadline bug 已修复。经用户确认已删除 11 条零回复、共 27,583 字符的自发 file-rationale inline comments；只保留 4 条 reviewer 回复（3 current、1 structurally outdated），没有 resolve、重发或新增评论。完整证据见 Day30 和 benchmark `15-*`。
- AgentCube PR review skill：独立 `.agents/skills/agentcube-pr-review/` 已完成并用 #387 前向验证；scanner 同时识别 dependency/runtime skew 和 target E2E default skip。2026-07-15 follow-up 将 live/cache freshness、真实 `%w` chain、progress-marker commit point 和“timer 不会自动约束 blocking I/O”纳入 checks、architecture map 与 pattern library；skill schema、6 个脚本单测、diff check 和 fresh-context raw-source review 通过。PR management 仍独立负责分支、CI 文案和 upstream 门禁。
- Production reachability learning：已把 Karmada #7623 的方法吸收到 AgentCube PR review / issue discussion skills；bug claim 现在必须区分 observed、source-proven reachable latent 和 mock-only hypothetical，并先证明真实 producer、受支持前置状态与 recovery/self-heal behavior。两个 skill 校验、10 个脚本测试、三场景 fresh-context forward test 和 diff check 均通过；未修改任何 upstream 评论。
- Maintainer review learning：2026-07-14 已抽样 `@RainbowMango` 在 AgentCube/Karmada 2020-2026 的 15 个有效 review PR，排除 reviewer-authored 与 approval-only 噪音；[Day46](internship-reports/day46-rainbowmango-maintainer-review-method-study.md) 总结 problem-first、scope、existing ownership/precedent、shared helper routing、status transition、second-round 方法。`agentcube-pr-review` 新增 history extractor、2 tests、maintainer methods reference 和 4 条 proven patterns。
- Maintainer writing learning：Day46 已追加 `@zhzhuang-zju` 17 个 issue / 12 个 PR 分层样本；确认 issue 常承担 evidence/causal chain/umbrella ledger，PR 聚焦 old -> new behavior、issue relation、compatibility/non-goal。新增 paginated contributor writing extractor 与 4 tests，并把 thin API body、空模板槽位、merge bias 作为反例写入 issue/PR concise references。
- Generic development skills：`/home/Onefly-Dev-Skills` / `ranxi2001/Onefly-Dev-Skills@95e1f72` 已新增通用 `github-code-review`，并升级 issue/proposal/writing-history 与 PR concise/behavior workflow；根 `AGENTS.md` 规定通用仓库只保存跨项目稳定方法，AgentCube 组件/分支/环境规则继续留在本仓库 overlay。
- Upstream writing gates：2026-07-14 已增强 `agentcube-issue-discussion` 与 `agentcube-pr-management`，新增 concise references 和 `draft_metrics.py`。规则把 upstream body/comment 定位为证据索引：普通 PR 目标 100-300 visible words，API/CRD/兼容/安全/benchmark/多组件 PR 目标 200-450；超 450 必须说明 long-form exception。近期样本和前向测试记录在 `internship-reports/open-source-contribution-format-standard.md`；没有发布任何 upstream 文本。
- Branch/workflow：当前本地在 `intern`，该分支保存实习报告、TODO、本地 skills 和中文记录；fork `main` 必须保持 upstream clean mirror。记录类 commit 完成后默认 push `origin intern:intern`；任何 upstream issue/PR/comment/review request/maintainer mention 必须先让用户确认 exact target/body。
- Day45 community screening：2026-07-10 已按 assignee、`/assign`、active PR、scope、环境和当前源码筛选最新 open issues；没有可直接认领的 A 级任务。#432 已由 `avinxshKD` 认领并有 #433；#430 已有 #431 proposal；#365 依赖 #366/#379 和 Kuasar/KVM；#348 已由 merged PR #378 修复但 issue 未关闭。旧 #272 与 open PR #249/release policy 有交叉，需先协调，不能直接接手。详见 `internship-reports/day45-latest-community-issue-task-screening.md`。
- Latest upstream baseline：最新观测 `upstream/main fa254b1`；#387 head `95fae1f` 是 merge base `3de1272` 上的单个 DCO commit，GitHub 当前判定 `MERGEABLE`；本地 non-live-E2E all-Go、unit/race/lint/vet/gen-check/build/E2E compile 与 official 12/12 checks 成功。`make test` 的 live E2E 因本机无 kubeconfig/部署失败，属于已记录环境限制。
- Day44 / PR #431：2026-07-15 latest head `f380208`（作者审计期间再次 force-push/squash），1 个 proposal 文件 `+761/-0`；相对 `upstream/main` 为 `5 behind / 1 ahead`，结构合并干净，10 个 checks + DCO 全绿，Tide 仅缺 `lgtm`/`approved`。`c2f2502..f380208` 为 `+49/-31`：title、containerd link、admin motivation、manifest self-healing、numeric priority、Phase recovery shortcut、orphan GET/error、node conflict 与 status identity boundary 均有实质补充。
- PR #400 latest review：作者在 review `4700751218` 后快速 force-push/rebase 到 `b8c4ed5`，当前 `0 behind / 4 ahead`。P1 method cardinality 已完整修复；60s bucket residual scope 已记录但按用户判断不阻塞本 PR。感谢/review-complete 评论已发布为 `4977532327`；`/lgtm` 被 Prow 拒绝，因为只有 collaborators 可改 label。新 head unit/race/focused 100-repeat、tidy、merge-tree 和 12/12 checks 均通过。
- Day44 输出：主报告与 comment tracker 已同步 #431 最新 8-thread review；新增 3 页可编辑 draw.io：review 收敛、API current-vs-direction、RuntimeClass node contract。源为 `day44-pr431-latest-review-api-runtime-map.drawio`，三个 `*.drawio.png` 均内嵌源数据并完成结构/视觉检查。
- #431 后续观察点：GraphQL 在 `f380208` 上显示 93 threads，8 个 current-diff active、1 个 unresolved outdated；8 条 active 均来自 `@RainbowMango`。作者只回复 NodeSelector 冗余、ResourcePolicy 命名和 RuntimeClass/kubelet 3 条，其余 5 条未回复；11 个 checks 全绿但仍无 `lgtm/approve`。唯一 unresolved-outdated 是新增 containerd Task v2 dead link。
- #431 最新 review 重点：阻止 v1alpha1 API/部署合同过早冻结。当前高价值问题是 Selector/Node label 成员生命周期、ResourceList 与 percentage mode、inert NodeCtlEndpoint、字段 ownership/default/mutability，以及 RuntimeClass 的 daemon/shim/containerd bootstrap 与 readiness 证据。Maintainer 建议 heartbeat 考虑 Lease，作者 15:29 CST 回复 `good suggestion` 但尚无新 commit；manifest loss 会先释放 reservation并造成恢复 admission gap，对应 thread 已 resolve但语义仍是 residual constraint，不能当作测试证明或 observed bug。
- #431 fresh-context 深审：在完整 93 threads duplicate audit 后新增 `SP-28..SP-38`。可证明的 reachable latent design defects 是 status webhook 阻断 controller writer、253-char name 复制到 63-char label/255-char filename、Ready 不检查 current generation、同名 Node 缺 UID incarnation fence、组合 Phase priority 遮蔽 5min Unready、SSA 1.18 compatibility 错误；agent `endpoints (full)` 是独立 least-privilege 缺口。Cleanup ack、runtime v2 crash/rebuild、Static Pod overhead 双视图和 stale resize operation 仍是 risk/question，不宣称 observed bug。
- #431 实现就绪度：可以继续 CRD/controller happy-path 骨架和 real-node shim feasibility spike；完整 schema 与 Phase 2 runtime contract 暂不 freeze。模板 Class→Pool/agent/manifest 传播、generic applied-resource status、bootstrap failure/recovery 和真实 kubelet+containerd spike 仍未闭合。
- GPT image workflow：本地 `/home/agentcube/.agents/skills/gpt-image-draw/SKILL.md` 已跑通。环境有 `OPENAI_API_KEY`；系统 Python 缺 `openai` 且受 PEP 668 限制，已用 `/tmp/gpt-image-draw-venv` 临时 venv 安装依赖。生成后必须用 `file` / `ls -lh` / `view_image` 复核，实际 PNG 尺寸可能不同于请求尺寸。不要打印或提交任何 key。
- Diagram rule：`AGENTS.md` 已新增 `Diagram and Image Generation Guidelines`。Linux 上架构/控制流/状态机/proposal review 图默认用 Mermaid；draw.io 只在需要可编辑画布或复杂布局时用；GPT image draw 用于精致 raster、中文信息图、banner、报告视觉图。精确架构和 review 推理仍以 Mermaid / prose 为准。
- Draw.io skill sync：2026-07-15 已将 Karmada intern worktree `58761535f08a` 的 `drawio-skill` 精确镜像到本仓库，共 62 个文件；skill metadata、Python compile、JSON/gzip、CLI help、workflow import、现有图校验和 Draw.io -> Mermaid 冒烟均通过。本机缺可选 Graphviz `dot`。持久容器 `agentcube-drawio-pr431` 已安装 draw.io CLI `30.3.11` + xvfb/libasound2，并按用户要求保留供后续导出，不要删除。
- Project Mermaid skill sync：2026-07-15 已从 Karmada intern worktree `8803dc6` 安装 `.agents/skills/project-mermaid/`，共 8 个文件；仅规范化两个模板的多余 EOF 空行以通过 `git diff --check`，其余内容与源一致。Renderer Python compile/CLI help 通过；使用固定 `@mermaid-js/mermaid-cli@11.16.0` 的显式 npx backend，data-flow 与 sequence 两个模板实际渲染和视觉检查均通过。后续数据流、时序、重试和小型生命周期图优先使用该 skill 的 canonical `.mmd` + PNG 工作流。
- PR #387 Mermaid：Day30 canonical `.mmd` + 白底 PNG 精确比较 `3de1272d` / agent-sandbox v0.1.1 与 `95fae1f8` / v0.4.6；按 7 组同编号节点横向标明池化、adopt、身份、就绪、Pod 读取、Store 和补池差异，并分离共同流程；PNG 已完成原图视觉检查。
- Weekly report workflow：已迁移到 private repo `/home/intern-week-mail`；身份只从 ignored `.env` 注入。2026-07-15 新增 Week 4/5 双层总结：第一层用于公司成果提炼，第二层保留工程学习、失败和证据；Week 5 源数据已按 GitHub 回读把 #431 从 2/2 校准为 3/3 review 点，并区分已验证的默认 AgentRuntime mTLS 与未验证的 direct WorkloadManager harness。现有 HTML 尚未按新源重渲染，也未授权发送。

## Active Upstream Threads

- #431 SandboxPool proposal：旧的两个用户确认 `COMMENT` review threads 已从 active 列表退出；残余实现风险继续记在 tracker，但不再称 `POSTED_WAITING`。当前 8 条 active 均为 `@RainbowMango` 最新 API/runtime review；先等待作者新 push 或逐条回复，不自动追评。
- #429 Go toolchain update workflow：已创建 upstream PR，普通 CI 绿，`tide` pending 等 review/labels；不要自动 push/comment。
- #400 PicoD Prometheus metrics：current head `b8c4ed5`，`MERGEABLE`，12 checks/DCO 绿。我们的 review 已公开完成：https://github.com/volcano-sh/agentcube/pull/400#issuecomment-4977532327；Prow 因 collaborator-only 权限拒绝 `/lgtm`，label 仍需 maintainer/collaborator 添加。不重复命令、不自动追评。
- #387 agent-sandbox v0.4.6 compatibility：current head `95fae1f`，1 commit，`MERGEABLE`，official 12/12 checks 成功；Tide 只缺 `lgtm`/`approved`。maintainer 两条 readiness finding 与二次审计的 Claim deadline finding 均已修复。review surface 已清掉 11 条无回复的文件说明，只保留 4 条真实 reviewer 回复；等待 maintainer review，不自动评论/resolve/request review。NetworkPolicy `Unmanaged` 仍是已知安全设计债务，详见 Day30。
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

- For #387：代码与 exact-SHA CI 已闭环，下一步只等待 maintainer `lgtm` / approver；有新 comment 或 push 时再按当前 head 复核，不自动评论、resolve、request review，也不要追加 #433 auth/RBAC 修改。
- Community tasks：本轮不 `/assign`。下一次先刷新 open issue/PR；只有新的 focused unowned issue，或 maintainer 将 #386/#272 拆成 dedicated sub-issue，才进入认领准备。#433 若做协作，先在临时 worktree 完成 Helm render/lint 和 auth/RBAC focused validation，再向用户提交 exact review draft。
- For #431: 当前固定 head `f380208`；不新增评论。等待 8 个 active thread 收敛；新 push 后先复核单一 Selector、ResourceList/percentage、template/NodeCtlEndpoint/field comments/RuntimeClass bootstrap，再重验 `SP-28` status caller-to-field matrix、`SP-29` name/label/path budget 和 `SP-30` generation freshness。任何 upstream 回复仍需用户确认 exact body。
- For #400: 我们的 review 已结束。保留 Python SDK `120s`、LangChain `1800s`、server 无 max 的 residual scope 供后续设计使用，但不继续扩张本 PR；等待 collaborator `lgtm` / approver，不重复 `/lgtm` 或自动 mention。
- For future reviews: 先填 `Claimed problem / Observable caller / Expected contract / PR scope` problem card；shared helper 先画 kind/scope/destination/owner matrix；大型 PR 明确 Round 1 architecture 与 Round 2 semantic-preservation，不以评论已回复代替 ready。
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
