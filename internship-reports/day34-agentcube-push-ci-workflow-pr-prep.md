# Day 34：AgentCube Push CI 工作流方案与 PR 准备

日期：2026-07-02

## 今日目标

今天的目标不是为了临时跑一次 CI，而是把 AgentCube 的 push CI 方案整理成一个可以提交 upstream 的小 PR：

1. 同步 fork `main` 到最新 `upstream/main`，避免从旧分支或多 commit 分支上继续堆改动。
2. 对比 Karmada 的 push CI 设计，确定 AgentCube 适合采用共享 workflow 的方案，而不是新增一份长期存在的独立 push-only workflow。
3. 在干净 topic branch 上只修改必要的 workflow 文件，并保留社区要求的 Dependabot 注释。
4. 解释为什么 PR 页面看到 11 个 checks，但本次只改 9 个 workflow 文件。
5. 准备英文 upstream PR 文本，等待用户确认后再正式开 PR。

> 注释：这里的 push CI 指 contributor 把代码 push 到自己 fork 的分支后，就能看到与 PR 尽量一致的 CI 检查结果。它不是 release workflow，也不是 publish workflow，更不是为了用 self-PR 临时蹭 CI。

## 结论先行

最终选择的方案是 Karmada-style：给现有验证类 workflow 增加 `push` 触发，而不是新增一个独立的 `branch-push-validation.yml`。

干净 PR 分支：

```bash
ci/enable-push-validation
```

基线：

```bash
upstream/main d3eb47a764e4
```

PR commit：

```bash
bb2a6e558752 ci: run validation workflows on branch push
```

改动范围：

```text
9 files changed, 45 insertions(+)
```

新增到每个验证 workflow 的触发配置：

```yaml
push:
  # Exclude branches created by Dependabot to avoid triggering current workflow
  # for PRs initiated by Dependabot.
  branches-ignore:
    - 'dependabot/**'
```

> 分析：这个方案的核心价值是 push 和 PR 复用同一份 workflow 命令。也就是说，`make e2e`、lint、coverage、codegen、Python 测试等命令不会在两个 workflow 文件里各维护一份，后续 CI 调整不容易出现 push 路径和 PR 路径不一致的问题。

## 为什么不采用单独 push-only workflow

一开始验证过一个单独 workflow 方案：新增 `.github/workflows/branch-push-validation.yml`，只在 fork branch push 时运行集中式验证。这种方案可以工作，也能避免 self-PR，但它有一个明显问题：它会复制现有 PR CI 的命令。

复制命令会带来两个风险：

1. PR workflow 更新后，push-only workflow 可能忘记同步。
2. push CI 绿不代表 PR CI 一定绿，因为两边的 job、环境、命令可能逐渐漂移。

用户指出 Karmada 的方式更好：直接在现有 CI workflow 上增加 `push` 触发。这个判断是对的，所以最终方案改成共享 workflow。

> 注释：临时 fork-only workflow 仍然适合个人验证分支，但不适合作为 upstream 长期方案。upstream 方案应该尽量减少重复定义，让 contributor 看到的 push 结果接近 PR 结果。

## workflow 在分支上的触发规则

之前一个疑问是：workflow 文件不是写在某个分支上吗，如果提交另一个分支，push 还会自动触发吗？

结论如下：

1. 对 `push` 事件来说，GitHub 会看被 push 的那个 ref 里的 `.github/workflows/*.yml`。
2. 如果某个分支本身不包含带 `push` 触发的 workflow，那么 push 这个分支不会凭空触发这些 workflow。
3. 如果 push CI 配置合入 upstream `main`，后续从最新 `main` 创建或 rebase 出来的分支都会包含这些 workflow，因此 push 这些分支时就会触发。
4. 如果只是把配置加到个人 fork 的 `main`，技术上也能让基于该 fork `main` 的后续分支触发，但本仓库约定 `origin/main` 必须保持为 `upstream/main` 的干净镜像，所以不应把私人 CI 配置塞进 fork `main`。

> 分析：这也是为什么这项工作适合做成 upstream PR。只放在个人 fork 里是个人 workaround；合入 upstream 后，所有 contributor 的新分支都可以继承同一套 push CI 行为。

## 同步上游与干净分支

按照 fork hygiene，先把 fork `main` 同步为 upstream 镜像：

```bash
git status
git fetch upstream main
git switch main
git reset --hard upstream/main
git push --force-with-lease origin main:main
git switch intern
```

然后从最新 upstream `main` 新建干净 worktree 和 topic branch：

```bash
git worktree add -b ci/enable-push-validation /tmp/agentcube-push-ci-clean upstream/main
```

这个分支只包含一个 commit：

```bash
bb2a6e5 ci: run validation workflows on branch push
```

提交带 DCO signoff：

```text
Signed-off-by: ranxi2001 <ranxi169@163.com>
```

## 改动文件

本次只改现有验证类 workflow，共 9 个文件：

| 文件 | 对应 PR / push 检查 | 改动 |
| --- | --- | --- |
| `.github/workflows/main.yml` | Agentcube CI Workflow / build | 增加 branch push 触发 |
| `.github/workflows/e2e.yml` | Agentcube E2E Tests / e2e-test | 增加 branch push 触发 |
| `.github/workflows/codegen-check.yml` | Codegen Check | 增加 branch push 触发 |
| `.github/workflows/codespell.yml` | Codespell | 增加 branch push 触发 |
| `.github/workflows/copyright-check.yml` | Copyright Check | 增加 branch push 触发 |
| `.github/workflows/lint.yml` | Lint / golangci-lint | 增加 branch push 触发 |
| `.github/workflows/python-lint.yml` | Python Lint | 增加 branch push 触发 |
| `.github/workflows/python-sdk-tests.yml` | Python SDK Tests | 增加 branch push 触发 |
| `.github/workflows/test-coverage.yml` | Test Coverage | 增加 branch push 触发 |

`git diff --stat` 结果：

```text
 .github/workflows/codegen-check.yml    | 5 +++++
 .github/workflows/codespell.yml        | 5 +++++
 .github/workflows/copyright-check.yml  | 5 +++++
 .github/workflows/e2e.yml              | 5 +++++
 .github/workflows/lint.yml             | 5 +++++
 .github/workflows/main.yml             | 5 +++++
 .github/workflows/python-lint.yml      | 5 +++++
 .github/workflows/python-sdk-tests.yml | 5 +++++
 .github/workflows/test-coverage.yml    | 5 +++++
 9 files changed, 45 insertions(+)
```

> 注释：每个文件只增加 5 行相同的 `push.branches-ignore` 配置。没有改 CI 命令、runner、权限、依赖版本，也没有改项目代码。

## 为什么不是 11 个 workflow 文件

PR 页面里看到的 successful checks 是 11 个，但这 11 个不是都来自需要修改的验证 workflow 文件。

真正需要 push 触发的验证 workflow 是 9 个，也就是上一节列出的 9 个文件。

剩下两个 checks 不能按同样方式处理：

| PR check | 来源 | 为什么不改 |
| --- | --- | --- |
| `Approve Workflows / Approve workflows based on contributor status` | `.github/workflows/workflows-approve.yml` | 这是 `pull_request_target` 流程 gate，用于按 contributor 状态批准 PR workflow，不是代码验证任务。branch push 没有 PR 上下文，不应该触发它。 |
| `DCO` | 外部 DCO status / GitHub App | 它不是 `.github/workflows/*.yml` 文件，不能通过改 workflow 增加 `push`。它检查 commit signoff，仍然应在 PR 阶段出现。 |

还有一点要注意：GitHub PR UI 里有时会把 workflow 名称和 job 名称组合展示，例如 `Agentcube CI Workflow / build`。这不是说一定有一个同名独立文件需要额外修改，仍然要回到 `.github/workflows/` 目录看真实 workflow 文件。

> 分析：这里的判断标准不是“PR 页面有几个绿勾”，而是“哪些 checks 是验证代码质量的 workflow，且适合在普通分支 push 时运行”。DCO 和 pull_request_target approval gate 都不属于这个集合。

## 为什么不改 release / publish workflow

`.github/workflows/` 目录下还有一些 workflow 没有改：

| 文件 | 原因 |
| --- | --- |
| `.github/workflows/build-push-release.yml` | 这是 release image / Helm chart 发布 workflow，已有 `push` 到 `main` 和 tag 的触发，且包含 `packages: write` 和 push 镜像逻辑。它不是普通 contributor branch validation。 |
| `.github/workflows/python-sdk-publish.yml` | PyPI 发布 workflow，只应由 tag 或手动触发，不应在任意 branch push 上运行。 |
| `.github/workflows/python-cli-publish.yml` | Python CLI 发布 workflow，不属于代码验证。 |
| `.github/workflows/dify-plugin-publish.yml` | 插件发布 workflow，不属于代码验证。 |
| `.github/workflows/workflows-approve.yml` | PR approval gate，使用 `pull_request_target`，不适合 branch push。 |

> 注释：release / publish workflow 的关键词是“产生外部副作用”：推镜像、推 chart、发 PyPI、发布插件。这类 workflow 和 contributor push validation 应该严格分开。

## 验证记录

静态验证：

```bash
git -C /tmp/agentcube-push-ci-clean diff --check upstream/main...HEAD
```

结果：无 whitespace error。

YAML 解析验证：

```bash
python3 - <<'PY'
import yaml
files = [
    '.github/workflows/main.yml',
    '.github/workflows/e2e.yml',
    '.github/workflows/codegen-check.yml',
    '.github/workflows/codespell.yml',
    '.github/workflows/copyright-check.yml',
    '.github/workflows/lint.yml',
    '.github/workflows/python-lint.yml',
    '.github/workflows/python-sdk-tests.yml',
    '.github/workflows/test-coverage.yml',
]
for f in files:
    with open('/tmp/agentcube-push-ci-clean/' + f, 'r', encoding='utf-8') as fh:
        yaml.safe_load(fh)
print('parsed', len(files), 'workflow files')
PY
```

结果：

```text
parsed 9 workflow files
```

push 验证：

```bash
git push origin ci/enable-push-validation:ci/enable-push-validation
```

之后用本地 helper 查询 fork branch push workflow：

```bash
python3 .agents/skills/agentcube-pr-management/scripts/check_push_ci.py \
  --repo ranxi2001/agentcube \
  --branch ci/enable-push-validation \
  --sha bb2a6e5 \
  --show-jobs failed
```

截至 `2026-07-02 10:59:04 CST` 复查，clean branch push run 最终 9/9 成功：

| Workflow | 状态 | Run |
| --- | --- | --- |
| Python SDK Tests | success | https://github.com/ranxi2001/agentcube/actions/runs/28561821332 |
| Codegen Check | success | https://github.com/ranxi2001/agentcube/actions/runs/28561821290 |
| Agentcube CI Workflow | success | https://github.com/ranxi2001/agentcube/actions/runs/28561821301 |
| Lint | success | https://github.com/ranxi2001/agentcube/actions/runs/28561821312 |
| Copyright Check | success | https://github.com/ranxi2001/agentcube/actions/runs/28561821311 |
| Codespell | success | https://github.com/ranxi2001/agentcube/actions/runs/28561821279 |
| Python Lint | success | https://github.com/ranxi2001/agentcube/actions/runs/28561821321 |
| Test Coverage | success | https://github.com/ranxi2001/agentcube/actions/runs/28561821275 |
| Agentcube E2E Tests | success | https://github.com/ranxi2001/agentcube/actions/runs/28561821316 |

补充证据：在用户指出共享 workflow 更好之后，旧验证分支 `ci/branch-push-validation` 上的同形方案 commit `9516ee5` 曾触发 9 个 push workflow 并全部成功。当前 clean branch 基于更新的 `upstream/main d3eb47a764e4` 重新制作，PR 应以 clean branch 为准。

> 分析：这次验证证明 clean branch 上的 9 个现有验证 workflow 都会被 branch push 事件创建出来，并且最终全部成功。正式 PR 文本可以写明 fork branch push validation 9/9 passed。

## Reviewer 可能关心的问题

### 这会不会增加 CI 成本

会增加 fork branch push 上的 CI 运行次数，尤其是 E2E workflow。这个 PR 的取舍是优先保证 contributor 在发 PR 前可以看到接近 PR 的验证结果，减少 self-PR 和无效 PR。

如果 maintainer 认为成本过高，可以讨论把 E2E 保持为 PR-only，或者用 path filter / branch filter 限制部分重型 job。但这样会损失 push 和 PR 的严格一致性。

### 这会不会触发 Dependabot 重复 CI

不会。每个新增 push trigger 都带了：

```yaml
branches-ignore:
  - 'dependabot/**'
```

这样 Dependabot 创建的分支不会因为 push 事件额外触发当前 workflow，避免和 Dependabot PR 自身的 checks 重复。

### 这会不会影响 release

不会。本次没有修改 release / publish workflow，也没有扩大它们的触发范围。

### 这会不会改变 PR CI 行为

不会。现有 `pull_request`、`merge_group`、`workflow_call` 配置被保留，workflow 内部 job 命令也没有变化。变化只是在同一 workflow 上增加 `push` 入口。

## PR 文本草稿

> 注释：以下是 upstream PR 草稿。还没有创建 PR，也不会在用户确认前发布到 upstream。

Title:

```text
ci: run validation workflows on branch push
```

Body:

```md
**What type of PR is this?**

/kind enhancement

**What this PR does / why we need it**:

This enables branch push validation for the existing CI workflows, so contributors can see the same validation workflows on fork branch pushes before opening or updating a PR.

The change adds a `push` trigger to the existing validation workflows and excludes Dependabot branches, following the same contributor pre-check pattern used by Karmada. It does not change the existing `pull_request`, `merge_group`, or `workflow_call` triggers, and it does not change any workflow job commands.

Changed validation workflows:

- `.github/workflows/main.yml`
- `.github/workflows/e2e.yml`
- `.github/workflows/codegen-check.yml`
- `.github/workflows/codespell.yml`
- `.github/workflows/copyright-check.yml`
- `.github/workflows/lint.yml`
- `.github/workflows/python-lint.yml`
- `.github/workflows/python-sdk-tests.yml`
- `.github/workflows/test-coverage.yml`

Not changed:

- Release and publish workflows, because branch validation should not publish images, charts, Python packages, or plugins.
- `.github/workflows/workflows-approve.yml`, because it is a `pull_request_target` approval gate for PR workflow approval.
- DCO, because it is not a GitHub Actions workflow file.

**Which issue(s) this PR fixes**:

NONE

**Special notes for your reviewer**:

Scope:

- CI trigger-only change.
- No runtime code changes.
- No workflow job command changes.
- No release or publish workflow changes.

Validation:

- `git diff --check`
- Parsed the 9 changed workflow YAML files with PyYAML.
- Pushed `ranxi2001/agentcube:ci/enable-push-validation` at `bb2a6e5`; all 9 existing validation workflows were triggered by `push` and passed.

AI assistance:

- I used Codex to compare the Karmada trigger pattern, prepare the workflow trigger edits, validate the fork push runs, and draft this PR text. I reviewed the final diff and validation result.

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
```

## 下一步

1. 用户确认 exact title / body / target 后，再创建 upstream PR：`ranxi2001:ci/enable-push-validation` -> `volcano-sh:main`。
2. 开 PR 前再跑一次 status 查询，确认 commit `bb2a6e5` 对应的 9 个 push workflow 仍可作为证据引用。
3. 如果 maintainer 质疑 CI 成本，优先解释本方案的目标是 push / PR 复用同一 workflow；如果社区希望降低成本，再讨论是否把 E2E 保持为 PR-only。
