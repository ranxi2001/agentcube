# Day 37：Docs Proposal 目录设计与提案管理调研

日期：2026-07-02

## 今日目标

当前 AgentCube 仓库没有专门的 `docs/proposals/` 目录。历史提案和设计文档主要放在 `docs/design/`，但该目录没有 README 索引，读者点进目录后很难快速判断：

1. 现在有哪些提案。
2. 每份提案对应哪个模块。
3. 新提案应该放在哪里。
4. 提案应该使用什么模板。
5. 历史设计文档和未来正式 proposal 的关系是什么。

本轮目标是先调研现状，再在 AgentCube 上开一个干净分支，做一个小而清晰的 proposal 管理改进。

> 注释：这类改动虽然只是文档目录管理，但它属于开源协作基础设施。提案目录越清楚，后续像 SandboxPool、E2B facade、Sleep/Resume、benchmark suite 这种设计就越容易被维护者和新人检索、讨论和延续。

## 参考对象：Karmada docs/proposals

参考链接：

- <https://github.com/karmada-io/karmada/tree/master/docs/proposals>
- <https://github.com/karmada-io/karmada/tree/master/docs/proposals/proposal-template>

本地调研方式：

```bash
rm -rf /tmp/karmada-proposals
git clone --depth 1 --filter=blob:none --sparse https://github.com/karmada-io/karmada.git /tmp/karmada-proposals
cd /tmp/karmada-proposals
git sparse-checkout set docs/proposals
find docs/proposals -maxdepth 3 -type f | sort
```

### Karmada 目录结构观察

Karmada 的 proposal 目录大致是：

```text
docs/proposals/
  proposal-template/
    proposal-template.md
  caching/
    README.md
  cleanup-propagated-resources/
    README.md
  scheduling/
    521-scheduler-estimator/
      README.md
    activation-preference/
      lazy-activation-preference.md
  hpa/
    federated-hpa.md
    statics/
      ...
  resource-aggregation-proxy/
    README.md
    *.drawio
    *.svg
```

统计结果：

| 项 | 结果 |
| --- | --- |
| `docs/proposals` 一级子目录数量 | 28 |
| max depth 2 内 Markdown 文件数量 | 31 |
| 其中 `README.md` 数量 | 15 |
| 其他 Markdown proposal 文件数量 | 16 |
| 顶层 `docs/proposals/README.md` | 未发现 |
| 模板位置 | `docs/proposals/proposal-template/proposal-template.md` |

> 分析：Karmada 的优点是把 proposal 从普通 docs 中拆出来，并允许每个大 proposal 形成独立目录，图片和 drawio 资产可以就近存放。缺点是顶层没有 README 索引，点开 `docs/proposals/` 后只能看到文件夹列表，不知道哪些是调度、failover、operator、networking，也不知道哪个 proposal 是当前推荐阅读入口。

### Karmada 模板结构

Karmada 的模板接近 Kubernetes Enhancement Proposal 的简化版，包含：

- front matter：title、authors、reviewers、approvers、creation-date。
- `Summary`
- `Motivation`
- `Goals`
- `Non-Goals`
- `Proposal`
- `User Stories`
- `Notes/Constraints/Caveats`
- `Risks and Mitigations`
- `Design Details`
- `Test Plan`
- `Alternatives`

> 注释：这个结构适合 AgentCube 复用，因为 AgentCube 后续要讨论的 proposal 大多也是跨组件设计：CRD、controller、router、runtime、SDK、benchmark、安全和缓存。模板至少要逼迫作者写清楚目标、非目标、测试计划和替代方案。

## AgentCube 当前提案存放方式

本地调研命令：

```bash
find docs -maxdepth 4 -type f | sort
rg -n "proposal|Proposal|design|Design|方案|提案|architecture|Architecture|roadmap|Roadmap|RFC|rfc" docs README.md README-ZH.md .github CONTRIBUTING.md -g '*.md'
```

关键发现：

1. `CONTRIBUTING.md` 当前写着：major design decisions go through design docs in `docs/design/`。
2. `README-ZH.md` 说明 AgentCube 仍处于提案和早期设计阶段，并指向 Volcano 初始 issue。
3. Docusaurus 架构文档里的 `Architecture Overview` 指向 `docs/design/agentcube-proposal.md`。
4. 现有设计文档主要集中在 `docs/design/`，但没有 README。
5. 文件命名不统一：有 `*-proposal.md`，也有 `*-Design.md`，还有普通的 `router-proposal.md` / `picod-proposal.md`。

### AgentCube 现有设计文档列表

基于最新 `upstream/main f9c37d5`，当前 `docs/design/` 下的 Markdown 文档为：

| 文件 | 标题 / 主题 | 观察 |
| --- | --- | --- |
| `docs/design/agentcube-proposal.md` | AgentCube Design Proposal | 有完整 front matter，是总体架构入口 |
| `docs/design/runtime-template-proposal.md` | Sandbox Template for Agent and CodeInterpreter Runtimes | 有 proposal 风格 front matter |
| `docs/design/picod-proposal.md` | PicoD Design Document | 设计文档风格，无 proposal front matter |
| `docs/design/PicoD-Plain-Authentication-Design.md` | Picod Plain Authentication Design | 设计文档风格，标题大小写略不统一 |
| `docs/design/router-proposal.md` | Router Submodule Design Document | 设计文档风格 |
| `docs/design/auth-proposal.md` | AgentCube Authentication and Authorization Design | 有 front matter，内容是 proposal |
| `docs/design/keycloak-proposal.md` | Keycloak Integration Design | proposal 内容，但无统一 front matter |
| `docs/design/AgentRun-CLI-Design.md` | AgentCube CLI Design | 设计文档风格，文件名使用大写 |

> 分析：AgentCube 不是没有 proposal，而是 proposal 和 design doc 混在 `docs/design/` 下，缺少面向读者的历史入口。直接搬迁这些文件会破坏现有链接，因此第一步不应该大规模移动文件，而应该先新增 `docs/proposals/README.md` 做统一入口，并只索引遗留在 `docs/design/` 的旧设计文档。

## 设计取舍

### 不直接搬迁 `docs/design`

我没有把历史文件从 `docs/design/` 移到 `docs/proposals/`，原因是：

1. 现有 README、Docusaurus 页面和外部链接已经指向 `docs/design/agentcube-proposal.md`。
2. 文件搬迁会制造较大的 diff，但真正解决的问题只是“入口和索引不清晰”。
3. docs-only 小 PR 更容易 review，也更适合作为 proposal 管理的第一步。

### 新增 proposal 入口

建议新增：

```text
docs/proposals/
  README.md
  proposal-template.md
```

其中：

- `README.md` 解释 proposal 目录用途、推荐布局、状态值、review guidance，并索引现有 `docs/design` 历史提案。
- `proposal-template.md` 提供统一 proposal 模板。
- `CONTRIBUTING.md` 更新为：新重大设计进入 `docs/proposals/`，历史设计文档仍保留在 `docs/design/`，并从 proposal README 索引。

> 注释：这是一个兼容式迁移方案。它先建立新入口，不破坏历史链接；后续如果社区同意，新 proposal 直接放进 `docs/proposals/`，但不要求每次新增 proposal 都同步维护 README 索引，避免让 README 变成长期手工目录。

## 已创建的 AgentCube 分支

干净工作树：

```text
/tmp/agentcube-proposals-index
```

分支：

```text
docs/proposals-management
```

基线：

```text
upstream/main f9c37d5fee30134230470366ee1ec13e562440a0
```

提交：

```text
504bf34 docs: add proposal index and template
```

已推送到 fork：

```text
origin docs/proposals-management
```

### 分支改动

```text
CONTRIBUTING.md                     |   4 +-
docs/proposals/README.md            | 103 ++++++++++++++++++
docs/proposals/proposal-template.md |  99 ++++++++++++++++++
```

具体变更：

1. 新增 `docs/proposals/README.md`。
   - 说明 proposal 目录用途。
   - 明确 README 不维护 `docs/proposals/` 下新增 proposal 的全量索引，后续新增 proposal 不需要额外更新 README。
   - 规定新 proposal 统一采用 `docs/proposals/<proposal-name>/README.md` 目录式布局。
   - 索引 `docs/design/` 中的历史设计文档。
   - 定义 `draft / provisional / implemented / deferred / rejected / obsolete` 状态值。
   - 给出 review guidance。
2. 新增 `docs/proposals/proposal-template.md`。
   - 包含 title、authors、reviewers、approvers、creation-date、last-updated、status、tracking-issue。
   - 包含 Summary、Motivation、Goals、Non-Goals、Proposal、User Stories、Design Details、Risks and Mitigations、Test Plan、Alternatives、Implementation Plan。
3. 更新 `CONTRIBUTING.md`。
   - 从 “Major design decisions go through design docs in `docs/design/`”
   - 改为 “Major design decisions go through proposals in `docs/proposals/`”
   - 同时说明历史 `docs/design/` 文件仍保留并由 README 索引。

## 验证

在 proposal 管理分支执行：

```bash
git diff --cached --check
```

提交前结果：通过。

本次是 docs-only 变更，没有运行 Go 测试、Docusaurus build 或 e2e。

> 分析：这个变更不触碰 Docusaurus 站点源码和项目代码，因此不需要 Go 测试。后续如果把 `docs/proposals` 接入 Docusaurus sidebar，再需要运行 `cd docs/agentcube && npm run build`。

## 可以准备的 upstream PR 文本

当前还没有创建 upstream PR。若后续要提交，可以使用这个方向：

```text
Title: docs: add proposal index and template
```

PR 说明要点：

````markdown
**What type of PR is this?**

/kind documentation

**What this PR does / why we need it**:

This PR adds a dedicated `docs/proposals/` entry point for AgentCube design proposals.

AgentCube already has several design and proposal documents under `docs/design/`,
but there is no proposal index or template that helps contributors discover the
existing proposal surface or start a new proposal consistently.

This PR:

- adds `docs/proposals/README.md` with proposal layout guidance, status values,
  review guidance, and an index of existing legacy `docs/design/` documents;
- adds `docs/proposals/proposal-template.md`;
- updates `CONTRIBUTING.md` to point major design decisions to `docs/proposals/`
  while keeping existing historical design documents under `docs/design/`.

**Which issue(s) this PR fixes**:

NONE

**Special notes for your reviewer**:

- Scope: docs-only proposal management.
- Existing `docs/design/` files are not moved, so current links remain stable.
- The README intentionally does not maintain a full index of future proposals
  under `docs/proposals/`; it only indexes legacy `docs/design/` documents.
- New proposals use a directory-based layout such as
  `docs/proposals/sandbox-pool-control-plane/README.md`, so images and
  supporting assets can be added later without changing the proposal path.
- Tests: `git diff --check`
- AI assistance: Used Codex to inspect existing docs structure, compare Karmada's proposal layout, and draft this PR. I reviewed and validated the changes.

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
````

> 注释：创建 upstream PR 前仍需要用户确认 exact title / body / target。当前只完成了 fork 分支准备，不进行 upstream-facing 动作。

## 今日结论

AgentCube 当前“以前的提案”主要存放在 `docs/design/`，但缺少目录索引和统一模板。Karmada 的 `docs/proposals/` 证明了 proposal 独立目录的价值，但它缺少顶层 README，所以 AgentCube 可以在借鉴它的同时补上更好的入口体验。

最稳妥的第一步不是搬迁历史文件，而是：

1. 新增 `docs/proposals/README.md`。
2. 新增 `docs/proposals/proposal-template.md`。
3. 在 README 中索引现有 `docs/design/` 历史提案，但不维护未来新增 proposal 的全量列表。
4. 更新 `CONTRIBUTING.md`，让新重大设计以后进入 `docs/proposals/`。

这样既解决“点开目录不知道有哪些提案”的问题，也避免一次性重构文档路径带来的链接风险。

## 用户反馈后的修正

用户指出：`README.md` 不需要维护新增提案的索引，否则每次新增 proposal 都要顺手改 README，长期维护成本很高。因此 proposal 分支已修正为：

1. `docs/proposals/README.md` 明确说明不维护 `docs/proposals/` 下新提案的全量索引。
2. 新提案依靠目录树本身发现，不要求额外更新 README。
3. README 中的表格只用于标注遗留在 `docs/design/` 的旧设计文档。
4. 远端 fork 分支已 force-with-lease 更新：`50116ca` 被 amend 为 `21f9159`。

随后用户继续指出：如果 README 同时允许 `docs/proposals/<proposal-name>.md`
和 `docs/proposals/<proposal-name>/README.md`，会形成两套 proposal 存放形态。
这种“小提案用文件、大提案用目录”的分类虽然轻量，但长期会出现路径迁移问题：
一份原本只有文字的 proposal 后续增加图片、manifest 或 benchmark 数据时，需要从
`.md` 文件改成目录，历史链接和 review 上下文都可能受到影响。

因此分支已再次修正为统一目录式布局，但不在初始阶段规划 `<area>/` 二级目录：

```text
docs/proposals/
  README.md
  proposal-template.md
  <proposal-name>/
    README.md
    images/
```

示例：

```text
docs/proposals/sandbox-pool-control-plane/README.md
docs/proposals/e2b-compatible-sdk-facade/README.md
```

> 分析：统一目录式的价值不只是“更像 Karmada”，而是让 proposal 从创建第一天就有稳定路径。即使早期只有一个 `README.md`，后续也可以就近加入图片、drawio、manifest、benchmark 原始数据或示例 YAML，不需要搬迁文件。

用户进一步指出：`<area>/` 也不适合初始阶段强行规划，因为 AgentCube
现在 proposal 数量还少，领域边界也未稳定。过早把提案分成 `sandbox/`、
`runtime/`、`sdk/` 等目录，会让作者先纠结分类，而不是先把 proposal 写清楚。
因此最终版本保留“一提案一目录”，但直接放在 `docs/proposals/` 下；等未来
proposal 数量明显增加、领域边界自然形成后，再讨论是否引入二级目录。

当前远端 fork 分支已再次 force-with-lease 更新：`21f9159` 被 amend 为
`59ac668`，随后 `59ac668` 又被 amend 为 `504bf34`。本次只改 proposal layout
文档，验证命令为 `git diff --check`。

## Proposal 模板为什么不完全照搬 Karmada

用户对比了当前 AgentCube proposal template 和 Karmada proposal template：

- AgentCube：
  <https://github.com/ranxi2001/agentcube/blob/docs/proposals-management/docs/proposals/proposal-template.md>
- Karmada：
  <https://github.com/karmada-io/karmada/blob/master/docs/proposals/proposal-template/proposal-template.md>

两者结构相似，但不是一比一复制。这个差异需要在 PR 里解释清楚，因为 reviewer
很可能会问：既然参考 Karmada，为什么模板字段和章节不同？

### 保留的共同骨架

AgentCube 模板保留了 Karmada / Kubernetes Enhancement Proposal 风格里最关键的
review 骨架：

1. front matter 元信息。
2. `Summary`。
3. `Motivation`。
4. `Goals` / `Non-Goals`。
5. `Proposal`。
6. `User Stories`。
7. `Design Details`。
8. `Risks and Mitigations`。
9. `Test Plan`。
10. `Alternatives`。

> 分析：这些章节解决的是“设计评审最小信息集”问题。AgentCube 后续的
> SandboxPool、E2B-compatible facade、Sleep/Resume、benchmark suite 等 proposal，
> 都需要说明动机、目标、非目标、设计细节、风险、测试和替代方案。

### 没有照搬的部分

#### 1. 不引入 KEP number / proposal number

Karmada 的一些正式 proposal 会有 `kep-number`，但 AgentCube 当前还没有
KEP 编号分配流程，也没有 proposal approver 负责发号。

所以本次模板不增加 `kep-number` 或 `proposal-number`。

> 分析：编号看起来规范，但它背后需要治理流程。现在提前强加编号，会让第一个
> proposal PR 变成“谁分配编号、编号怎么递增、冲突怎么办”的流程讨论，偏离本次
> 只建立 proposal 入口和模板的目标。

#### 2. 增加 `status` 和 `last-updated`

AgentCube 的 `docs/proposals/README.md` 明确不维护未来新增 proposal 的全量索引。
因此每个 proposal 自己需要携带最基本的生命周期信息：

```yaml
last-updated: yyyy-mm-dd
status: draft
```

这样读者打开单个 proposal 时就能知道它是草稿、已接受、已实现、延期、拒绝还是过期。

> 分析：这是对“不维护全量索引”的补偿。既然顶层 README 不承担持续更新目录的职责，
> proposal 文档自身就应该保存状态和最后更新时间。

#### 3. 增加 `tracking-issue`

AgentCube 当前很多设计讨论来自 GitHub issues、Discussions 和 PR review。
因此模板增加：

```yaml
tracking-issue: ""
```

这不是强制字段，但给作者一个固定位置链接 issue、discussion 或 umbrella task。

> 分析：AgentCube 现阶段还在快速形成架构边界，proposal 很可能和 issue / PR
> 互相引用。把 tracking issue 放在 front matter 中，比散落在正文里更容易追踪。

#### 4. 去掉 Karmada 模板里的示例机器人账号

Karmada 模板里有 `@robot` 这类示例 reviewer / approver。AgentCube 模板使用
`@your-github-id` 和 `TBD`，避免贡献者复制无效账号。

> 分析：这是降低误用概率。模板中的示例账号经常会被直接复制到真实 proposal，
> 所以 AgentCube 使用更明确的占位符。

#### 5. `Notes/Constraints/Caveats` 不单独设为固定章节

Karmada 模板有 `Notes/Constraints/Caveats (Optional)`。AgentCube 模板没有把它
固定为一级或二级标题，而是把这类内容放入 `Design Details` 或
`Risks and Mitigations` 中。

> 分析：AgentCube 初始模板应该保持轻量。约束、注意事项和 caveat 可以在具体
> proposal 中按需要加小节，不必要求每份 proposal 都保留一个空章节。

#### 6. `Test Plan` 提升为顶层章节

Karmada 把 `Test Plan` 放在 `Design Details` 下。AgentCube 模板把它作为独立
`## Test Plan`。

原因是 AgentCube 的 proposal 很多会涉及 Kubernetes 控制器、CRD、Router、
SDK、runtime lifecycle、sandbox cleanup、e2e 和 benchmark。测试计划不是实现后
才补的附属内容，而是设计能否被接受的重要评审依据。

> 分析：这和我们近期参与 PR review 的经验一致。很多 AgentCube 变更的风险不在
> 单个函数，而在跨组件生命周期、异常恢复、清理语义和 e2e 行为。因此 PR 早期就
> 要把验证路径写清楚。

#### 7. 增加 `Implementation Plan`

AgentCube 模板比 Karmada 多了可选 `Implementation Plan`。

原因是 AgentCube 后续的大设计通常不适合一个 PR 一次做完。例如：

- 先写 proposal。
- 再加 CRD skeleton。
- 再加 controller reconcile。
- 再加 Router / SDK 行为。
- 最后补 e2e / benchmark。

`Implementation Plan` 可以帮助 reviewer 判断 proposal 是否能被拆成小 PR，而不是
形成不可 review 的大改动。

> 分析：这个字段服务于开源协作节奏，不是要求每个 proposal 都写详细排期。

### 可以放进 PR 的英文解释

```markdown
The proposal template intentionally follows the Karmada/Kubernetes enhancement
proposal structure, but it is not a direct copy.

AgentCube does not currently have a proposal numbering process, so the template
does not introduce a `kep-number` or `proposal-number` field. Instead, it keeps
the metadata lightweight and adds `status`, `last-updated`, and
`tracking-issue` so each proposal can carry its own lifecycle state and link
back to the related issue or discussion.

The template also keeps `Test Plan` as a top-level section because many
AgentCube design changes involve Kubernetes controllers, CRDs, router behavior,
runtime lifecycle, SDK behavior, cleanup semantics, and e2e validation. Making
the validation strategy visible early helps reviewers evaluate the proposal
before implementation starts.

Compared with the Karmada template, optional notes and caveats are folded into
`Design Details` or `Risks and Mitigations` to keep the initial AgentCube
template smaller. An optional `Implementation Plan` is included because larger
AgentCube proposals are expected to be implemented across multiple focused PRs.
```
