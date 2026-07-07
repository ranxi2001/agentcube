# Day 43：Go Toolchain 升级边界与 GitHub Runner 固定

日期：2026-07-07

今天继续 Day42 的 Dependabot / CI hardening 方向，但把问题拆成两个不同层级：

1. `golang:*` builder image 不是普通 Docker runtime base image，Go 升级必须和 `go.mod`、CI、Docker builder tag 一起审。
2. `.github/workflows` 里的 `runs-on: ubuntu-latest` 不应长期保留，当前可以固定为 `ubuntu-24.04`，避免未来 GitHub 迁移 latest label 时突然改变 CI 环境。

> 注释：这两个问题都属于“自动化更新”和“稳定 CI 环境”的边界判断。看起来都只是版本字符串，但一个影响 Go 编译语义，一个影响 GitHub runner OS 语义。如果把它们当成普通依赖 bump，很容易得到能自动开 PR、但不一定能稳定合并的结果。

## 纠正后的问题范围

一开始我把第二个问题误判成 Day39 release image build 的 follow-up。用户纠正后，第二个问题实际是 `.github/workflows` 中 `runs-on: ubuntu-latest` 的写法。

正确范围：

- 问题一：Go toolchain / `golang` builder image 的升级该如何和 Dependabot 平衡。
- 问题二：GitHub Actions runner label 不要使用浮动的 `ubuntu-latest`，先固定到 `ubuntu-24.04`。

## 问题一：Go 版本升级不能只靠 Docker Dependabot

PR #391 是当前最直接的项目证据：[chore: update Go toolchain to 1.26.4](https://github.com/volcano-sh/agentcube/pull/391)。它不是只改 `docker/Dockerfile` 的 `golang` tag，而是同时改了：

- `go.mod`
- `docker/Dockerfile`
- `docker/Dockerfile.router`
- `docker/Dockerfile.picod`
- `.github/workflows/build-push-release.yml`
- `.github/workflows/codegen-check.yml`
- `.github/workflows/e2e.yml`
- `.github/workflows/lint.yml`
- `.github/workflows/test-coverage.yml`

本地核对：

```bash
sed -n '1,80p' go.mod
rg -n 'golang:[0-9][^[:space:]]*|go-version-file|go-version:' docker .github/workflows
```

当前状态：

```text
go.mod: go 1.26.4
docker/Dockerfile:        FROM golang:1.26.4-alpine AS builder
docker/Dockerfile.router: FROM golang:1.26.4-alpine AS builder
docker/Dockerfile.picod:  FROM golang:1.26.4 AS builder
workflow setup-go:        go-version-file: go.mod
```

> 分析：`go.mod` 是 Go 语言版本基线，GitHub Actions 通过 `actions/setup-go` 的 `go-version-file: go.mod` 读取它；Dockerfile 没法自动读取 `go.mod`，所以 builder image tag 必须人工或脚本同步。只让 Docker ecosystem 的 Dependabot bump `golang`，会造成 Docker builder 使用的新 Go 版本和项目声明的 Go 版本不一致。

### Dependabot 能否单独做 Go 组件

GitHub Dependabot 确实支持多个 ecosystem，例如 `gomod` 和 `docker` 可以分别配置；官方 Dependabot options reference 也把 `package-ecosystem` 作为每个 updater 的核心字段：<https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference>。

但这里要区分两件事：

- `gomod` updater：适合更新 Go module 依赖。
- Go toolchain baseline：需要选择 Go 版本，并同时更新 `go.mod`、Docker builder tag、CI 入口和测试证据。

我查了当前 `dependabot-core` 的 Go modules 实现：

- Go modules parser 会读取 `go.mod` 中的 `go` 版本，用作 ecosystem language 元数据。
- File updater spec 有一个明确用例：当 `go.mod` 是 pre-1.21，但依赖需要 Go 1.21 时，Dependabot 不会自动添加 `toolchain` directive。
- 代码搜索能看到独立的 `rust_toolchain` updater，但没有同等的 Go toolchain updater。

相关源码：

- <https://github.com/dependabot/dependabot-core/blob/d893020c1901b289b5a9bc42622d354402e204e2/go_modules/lib/dependabot/go_modules/file_parser.rb>
- <https://github.com/dependabot/dependabot-core/blob/d893020c1901b289b5a9bc42622d354402e204e2/go_modules/spec/dependabot/go_modules/file_updater_spec.rb>
- <https://github.com/dependabot/dependabot-core/blob/d893020c1901b289b5a9bc42622d354402e204e2/rust_toolchain/lib/dependabot/rust_toolchain.rb>

> 注释：这里不是说 Dependabot 对 Go 没用，而是说它不等于“完整 Go baseline upgrade manager”。Go module dependency PR 可以让 Dependabot 开；Go toolchain baseline PR 应该单独准备和验证。

### 当前建议

短期：

- Day42 PR #422 继续让 Docker updater 管 runtime base images。
- 在 Docker updater 里继续 ignore `golang`，避免 Docker-only PR 单独升级 Go builder image。
- 如果未来新增 `gomod` Dependabot updater，它也应和 Docker updater 分开，不应让一个 PR 同时混 module dependency、Go baseline 和 runtime image。

中期：

- Go 版本升级走独立 PR：`go.mod` 为 source of truth，Docker builder tag 同步，workflow 继续用 `go-version-file: go.mod`。
- 每次 Go baseline PR 至少跑：非 e2e Go tests、race coverage、`make build-all`、`make lint`、`make gen-check`、三个 Docker image build。
- 可以补一个轻量脚本或 CI check，验证 `go.mod` 的 Go 版本和三个 Dockerfile 的 `golang:<version>` 一致。

长期：

- 如果想让自动化主动发现 Go 新版本，更适合写一个独立 scheduled workflow / script：读取官方 Go release feed，生成一个“Go toolchain upgrade”分支，统一修改 `go.mod` 和 Dockerfile，并运行对应测试。
- Renovate 也可以用 regex manager 协调多个文件，但这是引入新依赖治理工具，需要单独评估，不应混进 Day42 Dependabot Docker runtime PR。

## 问题二：`ubuntu-latest` 应固定到 `ubuntu-24.04`

GitHub 官方 runner-images 仓库明确维护了 `ubuntu-latest` 这种浮动 label。当前文档显示：

- `ubuntu-latest` 当前对应 Ubuntu 24.04。
- `ubuntu-24.04` 是明确的版本 label。
- 如果不希望 OS 被 GitHub 自动迁移，应使用具体 label。

来源：

- GitHub-hosted runners 文档：<https://docs.github.com/en/actions/reference/runners/github-hosted-runners>
- GitHub Actions runner-images：<https://github.com/actions/runner-images>

> 注释：`ubuntu-latest` 的问题不是“今天错了”，而是“未来某一天可能被 GitHub 迁移”。CI 的价值在于稳定复现，尤其是 Go / Python / Docker / Helm 混合项目，runner OS 小版本变化可能带来系统包、Docker、Python、OpenSSL、glibc 或 action cache 行为变化。

### 本地审计

审计命令：

```bash
rg -n 'runs-on:\s*ubuntu-latest|runs-on:\s*ubuntu-[0-9]+' .github/workflows
```

在 `upstream/main de41b90` 上，已有：

- `.github/workflows/main.yml`: `ubuntu-24.04`
- `.github/workflows/lint.yml`: `ubuntu-24.04`
- `.github/workflows/e2e.yml`: `ubuntu-22.04`

仍使用 `ubuntu-latest` 的文件共 11 个：

- `.github/workflows/build-push-release.yml`
- `.github/workflows/codegen-check.yml`
- `.github/workflows/codespell.yml`
- `.github/workflows/copyright-check.yml`
- `.github/workflows/dify-plugin-publish.yml`
- `.github/workflows/python-cli-publish.yml`
- `.github/workflows/python-lint.yml`
- `.github/workflows/python-sdk-publish.yml`
- `.github/workflows/python-sdk-tests.yml`
- `.github/workflows/test-coverage.yml`
- `.github/workflows/workflows-approve.yml`

### PR 分支准备

已创建干净 topic branch：

```text
worktree: /tmp/agentcube-day43-runner-pinning
branch: ci/pin-github-runners-ubuntu-2404
base: upstream/main de41b90
commit: 387154258f1a0c10c5ba485071facd25a6d52829
remote: origin/ci/pin-github-runners-ubuntu-2404
```

改动范围：

```text
11 files changed, 11 insertions(+), 11 deletions(-)
```

每个文件只做同一种替换：

```diff
-    runs-on: ubuntu-latest
+    runs-on: ubuntu-24.04
```

> 分析：这里没有改 `e2e.yml` 的 `ubuntu-22.04`，因为它已经是明确版本，是否升级到 24.04 是另一个测试兼容性问题。Day43 这个 PR 只消除浮动 latest label。

## 验证记录

本地验证：

```bash
git diff --check HEAD~1..HEAD
rg -n 'runs-on:\s*ubuntu-latest' .github/workflows || true
python3 - <<'PY'
from pathlib import Path
import yaml
for p in sorted(Path('.github/workflows').glob('*.yml')):
    with p.open() as f:
        yaml.safe_load(f)
print('parsed workflow yaml files:', len(list(Path('.github/workflows').glob('*.yml'))))
PY
go run github.com/rhysd/actionlint/cmd/actionlint@latest
```

结果：

- `git diff --check`：通过。
- `rg ubuntu-latest`：无匹配。
- Python YAML parse：14 个 workflow YAML 均可解析。
- `actionlint`：通过。

Fork push validation：

```text
repo: ranxi2001/agentcube
branch: ci/pin-github-runners-ubuntu-2404
sha: 387154258f1a0c10c5ba485071facd25a6d52829
```

push 后触发了 9 个 Actions：

- Agentcube CI Workflow: success, <https://github.com/ranxi2001/agentcube/actions/runs/28855465082>
- Codespell: success, <https://github.com/ranxi2001/agentcube/actions/runs/28855465006>
- Copyright Check: success, <https://github.com/ranxi2001/agentcube/actions/runs/28855465187>
- Codegen Check: success, <https://github.com/ranxi2001/agentcube/actions/runs/28855465154>
- Python Lint: success, <https://github.com/ranxi2001/agentcube/actions/runs/28855465083>
- Python SDK Tests: success, <https://github.com/ranxi2001/agentcube/actions/runs/28855465089>
- Agentcube E2E Tests: success, <https://github.com/ranxi2001/agentcube/actions/runs/28855465160>
- Test Coverage: success, <https://github.com/ranxi2001/agentcube/actions/runs/28855465091>
- Lint: success, <https://github.com/ranxi2001/agentcube/actions/runs/28855465115>

最终结果：fork push CI 9/9 success。

> 注释：这是 Day34/#414 合入后的收益。现在普通 fork branch push 能跑主要验证 workflow，不需要再开 self-fork PR 当 CI runner。

## 过程中的小问题

1. 在当前 `intern` 分支运行：

   ```bash
   rg -n 'golang:[0-9][^[:space:]]*|go-version-file|go-version:' docker .github/workflows .github/dependabot.yml
   ```

   看到错误：

   ```text
   rg: .github/dependabot.yml: No such file or directory (os error 2)
   ```

   原因：`.github/dependabot.yml` 还在 Day42 upstream PR #422 分支中，尚未合入当前 `upstream/main` / `intern`。解决方式是只把 #422 当作上下文，不在当前树里假设该文件已存在。

2. 第一次查 `dependabot-core` 代码时使用了：

   ```bash
   gh search code 'toolchain' --repo dependabot/dependabot-core --path go_modules
   ```

   当前 `gh` 版本没有 `--path` flag。改用 GitHub code search 语法：

   ```bash
   gh search code 'toolchain path:go_modules' --repo dependabot/dependabot-core
   ```

   解决后能看到 Go modules parser / specs 和 Rust toolchain updater 的差异。

## PR 草稿

Title:

```text
ci: pin GitHub Actions Ubuntu runners
```

Body:

````md
**What type of PR is this?**

/kind cleanup

**What this PR does / why we need it**:

This pins GitHub Actions jobs that still use `ubuntu-latest` to `ubuntu-24.04`.

`ubuntu-latest` is a moving label and may point to a different Ubuntu image when GitHub migrates the hosted runner default. Pinning the runner image keeps CI behavior stable while preserving the current Ubuntu 24.04 environment used by `ubuntu-latest`.

**Which issue(s) this PR fixes**:
Refs #386

**Special notes for your reviewer**:

- Scope: only updates workflow runner labels from `ubuntu-latest` to `ubuntu-24.04`.
- Existing explicit labels are left unchanged, including `e2e.yml` on `ubuntu-22.04`.
- Tests:
  - `git diff --check HEAD~1..HEAD`
  - `rg -n 'runs-on:\s*ubuntu-latest' .github/workflows || true`
  - Python YAML parse for `.github/workflows/*.yml`
  - `go run github.com/rhysd/actionlint/cmd/actionlint@latest`
- AI assistance: Used Codex to inspect workflows, prepare the branch, and draft this PR. I reviewed and validated the changes.

**Does this PR introduce a user-facing change?**:
```release-note
NONE
```
````

> 分析：这个 PR 可以不绑定具体 issue，也可以 `Refs #386`，因为 #386 是 v0.2.0 / follow-up 类 umbrella issue。不要写 `Fixes #386`，避免关闭大 issue。

## 后续判断

- Day42 的 Docker Dependabot PR 和 Day43 的 runner pinning PR 可以并行，不互相依赖。
- Go toolchain upgrade 不应塞进这两个 PR；如果后续要做，应从最新 `upstream/main` 新开纯净 Go/toolchain branch。
- 如果 runner pinning PR 被接受，以后审 workflow 时优先检查：
  - 是否有 `runs-on: ubuntu-latest`
  - 是否有重复硬编码 Go 版本而不是 `go-version-file: go.mod`
  - 是否有 release / publish workflow 因 runner OS 变化影响系统依赖
