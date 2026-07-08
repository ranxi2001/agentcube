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

### Upstream PR #429 创建与 Gemini 反馈处理

用户确认后，已创建 upstream PR #429：<https://github.com/volcano-sh/agentcube/pull/429>。

- Title: `ci: add scheduled go toolchain update workflow`
- Base: `volcano-sh/agentcube:main`
- Head: `ranxi2001:ci/go-toolchain-update-workflow`
- Initial commit: `733bb4b`
- Updated commit after review feedback: `b6a3156`

Gemini 对 `hack/go-toolchain.py` 提了 4 条健壮性建议：

- workflow regex 不应匹配注释里的 `go-version` / `go-version-file`。
- `str.removeprefix` 对 Python 3.8 不兼容。
- `toolchain` directive 删除逻辑不应只支持普通 release 版本，也要能移除 `go1.xxrc1` 这类格式。
- workflow verification 应同时扫描 `.yml` 和 `.yaml`。

已按用户确认更新 PR 分支，把这些建议吸收进同一个 signed commit：

- `SETUP_GO_RE` 改为匹配 active YAML key，并兼容合法的 `- uses:` step 写法。
- `GO_VERSION_RE` / `GO_VERSION_FILE_RE` 改为行首 active key 匹配，避免注释误报。
- `latest_stable_go` 去掉 `removeprefix`。
- `TOOLCHAIN_LINE_RE` 按整行删除 `toolchain` directive。
- `verify_workflows` 同时扫描 `.yml` 和 `.yaml`。

额外本地验证：

```bash
go run github.com/rhysd/actionlint/cmd/actionlint@latest .github/workflows/go-toolchain-update.yml
python3 hack/go-toolchain.py verify --check-latest
python3 -m py_compile hack/go-toolchain.py
git diff --check upstream/main...HEAD
```

另写了临时 Python fixture 覆盖三类边界：注释中的 `go-version` 不误报、`.yaml` workflow 会被扫描、`toolchain go1.27rc1` 可被移除。验证通过后未把临时 fixture 提交进 PR。

已回复 Gemini：<https://github.com/volcano-sh/agentcube/pull/429#issuecomment-4911119744>。

更新后 #429 普通 CI 全部通过；`tide` 仍 pending，仅因为缺少 `lgtm` / `approved`。

> 注释：这次没有逐条回复 4 个 outdated inline thread，而是用一个短 PR comment 说明 latest push 已覆盖全部建议。这样不会刷屏，也能让 maintainer 看到 review feedback 已处理。

> 分析：这个 PR 可以不绑定具体 issue，也可以 `Refs #386`，因为 #386 是 v0.2.0 / follow-up 类 umbrella issue。不要写 `Fixes #386`，避免关闭大 issue。

实际创建状态：

```text
PR: https://github.com/volcano-sh/agentcube/pull/423
Title: ci: pin GitHub Actions Ubuntu runners
Head: ranxi2001:ci/pin-github-runners-ubuntu-2404
SHA: 387154258f1a0c10c5ba485071facd25a6d52829
Label: kind/cleanup, size/S
State: open, mergeable
Checks: all ordinary CI passed; tide is pending only for lgtm / approved labels
```

## 后续判断

- Day42 的 Docker Dependabot PR 和 Day43 的 runner pinning PR 可以并行，不互相依赖。
- Go toolchain upgrade 不应塞进这两个 PR；如果后续要做，应从最新 `upstream/main` 新开纯净 Go/toolchain branch。
- 如果 runner pinning PR 被接受，以后审 workflow 时优先检查：
  - 是否有 `runs-on: ubuntu-latest`
  - 是否有重复硬编码 Go 版本而不是 `go-version-file: go.mod`
  - 是否有 release / publish workflow 因 runner OS 变化影响系统依赖

## Go Toolchain 长期方案

完成 #423 后，继续看第一个问题：Go 版本升级如何长期治理，而不是每次靠临时判断。

当前项目事实：

- `go.mod` 是 Go 版本 source of truth，当前是 `go 1.26.4`。
- 五个 workflow 使用 `actions/setup-go` + `go-version-file: go.mod`，没有重复硬编码 Go 版本。
- 三个 Dockerfile 的 builder stage 都使用 `golang:1.26.4...`，和 `go.mod` 对齐。
- go.dev 官方下载 JSON 当前最新稳定版本也是 `go1.26.4`。
- #391 已证明一次 Go baseline 升级会同时触达 `go.mod`、CI setup-go 和 Docker builder tag。
- #422 已把 runtime Docker base image Dependabot 拆出来，并刻意 ignore `golang`。

> 注释：这里的长期方案不是“永远不自动化”，而是把自动化拆成两层：机器负责发现和检查，人负责做一次可审阅的 Go baseline PR。Go 版本影响编译器、标准库、module graph normalization、generated code、Docker builder、CI 环境和 e2e，因此不适合被 Docker image updater 当作普通镜像 tag 自动修改。

### 方案目标

1. 发现：能及时知道官方 Go stable release 有新版本。
2. 同步：升级时一次性同步 `go.mod`、Docker builder tags、CI setup-go 入口。
3. 防漂移：任何人单独改 Dockerfile 或 workflow 时，CI 能发现和 `go.mod` 不一致。
4. 可审阅：Go baseline PR 不自动合并，必须带完整测试证据。
5. 不混 scope：runtime base image、Go module dependency、Go compiler baseline 三类更新分开。

### 方案矩阵

| 方案 | 能解决什么 | 不能解决什么 | 结论 |
| --- | --- | --- | --- |
| Dependabot Docker updater 同时 bump `golang` | 能发现 Dockerfile 中 `golang:*` tag 新版本 | 不会同步 `go.mod` 和测试矩阵；会制造 Docker builder 与项目 Go baseline 漂移 | 不采用，#422 已 ignore `golang` |
| Dependabot `gomod` updater | 能更新 Go module dependencies | 不等同于 Go toolchain baseline updater；不能保证改 Docker builder tag | 可作为 module dependency updater，但不是本问题答案 |
| Dependabot multi-ecosystem group | 能把多个 ecosystem 的依赖更新分组 | 仍无法表达“改 go directive + Dockerfile + workflow + 测试矩阵”的完整语义 | 不推荐作为主方案 |
| Renovate | 可以通过 manager / custom manager 统一更多文件 | 引入新 bot 和配置治理成本；会和现有 Dependabot 重叠 | 作为未来可选项，不作为当前第一步 |
| Repo-owned verify script + CI | 能防止 `go.mod` / Dockerfile / workflow 漂移 | 不会自动发现新 Go 版本或创建 PR | 第一阶段推荐 |
| Scheduled Go toolchain check workflow | 能定期查 go.dev stable release，并生成可审阅 PR | 需要维护脚本、token 权限和 PR 创建逻辑 | 第二阶段推荐 |

官方参考：

- Go toolchain selection: <https://go.dev/doc/toolchain>
- Go releases JSON endpoint: <https://go.dev/dl/?mode=json>
- Dependabot multi-ecosystem updates: <https://docs.github.com/en/code-security/dependabot/working-with-dependabot/configuring-multi-ecosystem-updates>
- Dependabot options reference: <https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference>
- Renovate Go modules manager: <https://docs.renovatebot.com/modules/manager/gomod/>
- Renovate Dockerfile manager: <https://docs.renovatebot.com/modules/manager/dockerfile/>

### 推荐路径

第一阶段：防漂移。

- 加一个 repo-owned verifier，例如 `hack/verify-go-toolchain.sh` 或 `hack/verify-go-toolchain.py`。
- 检查：
  - `go.mod` 的 `go` directive。
  - `docker/Dockerfile*` 中所有 `golang:<version>` builder tag。
  - workflow 中 `actions/setup-go` 是否都使用 `go-version-file: go.mod`。
- 把 verifier 接入轻量 CI 或现有 lint/check workflow。
- 这一步不改变升级节奏，只保证以后不会无意间漂移。

第二阶段：半自动发现。

- 新增 scheduled workflow，例如每周或每月跑一次。
- 读取 `https://go.dev/dl/?mode=json` 中最新 stable Go。
- 如果 latest stable 与 `go.mod` 不同，创建一个 issue 或 PR 草稿，标题类似：

  ```text
  chore: update Go toolchain to 1.xx.y
  ```

- PR 只修改：
  - `go.mod`
  - 可能由 `go mod tidy` 产生的 `go.sum`
  - 三个 Docker builder image tag
  - 必要时 workflow setup-go 入口
- PR 不自动合并，等待 maintainer review。

第三阶段：完整 validation。

Go baseline PR 的固定测试矩阵：

```bash
python3 .agents/skills/agentcube-pr-management/scripts/audit_go_toolchain_alignment.py --repo-root . --check-latest
go list ./... | grep -v '^github.com/volcano-sh/agentcube/test/e2e$' | xargs go test -count=1
go test -race -v -coverprofile=coverage.out -coverpkg=./pkg/... ./pkg/...
make build-all
make lint
make gen-check
docker build -f docker/Dockerfile -t agentcube-go<version>-workloadmanager:test .
docker build -f docker/Dockerfile.router -t agentcube-go<version>-router:test .
docker build -f docker/Dockerfile.picod -t agentcube-go<version>-picod:test .
```

> 分析：如果只是 patch 版本，例如 `1.26.4 -> 1.26.5`，通常风险较低，但仍要跑完整 Go / codegen / Docker build。minor 版本，例如 `1.26 -> 1.27`，还需要额外关注 `go mod tidy`、lint 规则、generated code 和依赖最低 Go 版本变化。

### 本地原型验证

为了让长期方案可复用，我在本地 PR skill 增加了一个审计脚本：

```text
.agents/skills/agentcube-pr-management/scripts/audit_go_toolchain_alignment.py
```

运行：

```bash
python3 .agents/skills/agentcube-pr-management/scripts/audit_go_toolchain_alignment.py \
  --repo-root /tmp/agentcube-go-toolchain-probe \
  --check-latest
```

结果：

```text
go.mod go directive: 1.26.4
go.mod toolchain directive: <none>
Docker builder: docker/Dockerfile: golang:1.26.4-alpine
Docker builder: docker/Dockerfile.picod: golang:1.26.4
Docker builder: docker/Dockerfile.router: golang:1.26.4-alpine
setup-go workflow: .github/workflows/build-push-release.yml: go-version-file=True inline-go-version=False
setup-go workflow: .github/workflows/codegen-check.yml: go-version-file=True inline-go-version=False
setup-go workflow: .github/workflows/e2e.yml: go-version-file=True inline-go-version=False
setup-go workflow: .github/workflows/lint.yml: go-version-file=True inline-go-version=False
setup-go workflow: .github/workflows/test-coverage.yml: go-version-file=True inline-go-version=False
latest stable Go release: 1.26.4
Go toolchain alignment: OK
```

这个脚本先留在本地 skill，不直接作为 upstream diff。后续如果 maintainer 接受方向，可以把它改成 upstream `hack/verify-go-toolchain.*`，再接入 CI。

### 自动 PR 演练与权限边界

用户要求按“自动创建 PR”的标准在 fork 仓库做真实测试。我先犯了一个判断错误：手工创建了 fork PR #19，虽然它复刻了 #391 的 9 文件升级面，但 author 是 `ranxi2001`，不符合“自动 PR”证据标准，不能作为最终证据引用。该 PR 是 fork-only，后续已处于 merged 状态，但不要在 upstream 方案中引用它作为 automation evidence。

> 分析：自动化证据不能只看 diff 是否像自动生成，还要看创建者身份、触发来源和权限链路。手工用 `gh pr create` 创建的 PR，哪怕 body 写了自动化，也仍然是用户身份 PR。

随后改为 fork-only workflow 演练：

- workflow 分支：`ci/go-toolchain-bot-simulation`
- 成功 run：<https://github.com/ranxi2001/agentcube/actions/runs/28862855744>
- 自动 PR：<https://github.com/ranxi2001/agentcube/pull/20>
- PR author：`app/github-actions`
- PR head：`bot/go-toolchain-auto-pr-1264-28862855744`
- PR base：`bot/go-toolchain-old-1244-28862855744`
- head commit：`96c68fe`

为了让 `GITHUB_TOKEN` 能创建 PR，我通过 GitHub API 打开了 fork 仓库的 Actions 设置：

```text
can_approve_pull_request_reviews: true
default_workflow_permissions: read
```

> 注释：GitHub UI 中对应的是 Settings -> Actions -> General -> Workflow permissions 里的 “Allow GitHub Actions to create and approve pull requests”。这里默认权限仍保持 `read`，具体 job 权限由 workflow 里的 `permissions: contents: write, pull-requests: write` 显式声明。

这个 workflow 做了以下动作：

1. 读取 `https://go.dev/dl/?mode=json`，解析最新 stable Go。
2. 从 `upstream/main` 创建一个旧 Go baseline base branch。
3. 从 base branch 生成自动升级 head branch。
4. 运行 `go mod tidy`、`git diff --check`。
5. 校验 changed file list 必须精确等于预期文件列表。
6. 校验生成后的 head tree 与 `upstream/main` 一致。
7. 用 `GITHUB_TOKEN` 创建 fork PR #20。

PR #20 的 diff 是 4 个文件：

```text
docker/Dockerfile
docker/Dockerfile.picod
docker/Dockerfile.router
go.mod
```

这是“未来常规 Go baseline 更新”的合理形态，因为 #391 已经把 workflow 里的 `actions/setup-go` 都改成了 `go-version-file: go.mod`。因此后续从 `1.26.4` 升到 `1.26.5` 或 `1.27.x` 时，正常不需要再改 `.github/workflows/*`。

> 注释：`go-version-file: go.mod` 的意义是 GitHub Actions 不再单独写死 Go 版本，而是从 `go.mod` 读取。这样常规 Go baseline 更新只需要改 `go.mod` 和 Docker builder image tag。

### 9 文件版本为什么困难

#391 的真实升级改了 9 个文件：

```text
.github/workflows/build-push-release.yml
.github/workflows/codegen-check.yml
.github/workflows/e2e.yml
.github/workflows/lint.yml
.github/workflows/test-coverage.yml
docker/Dockerfile
docker/Dockerfile.picod
docker/Dockerfile.router
go.mod
```

我也尝试用 workflow 复刻这个历史迁移面：base branch 写成 #391 前的状态，包括 `go.mod go 1.24.4`、`toolchain go1.24.9`、workflow inline `go-version`、旧 Docker builder tag。结果 GitHub 在 push base branch 时拒绝：

```text
refusing to allow a GitHub App to create or update workflow `.github/workflows/build-push-release.yml` without `workflows` permission
```

> 分析：这是 GitHub 平台权限边界，不是脚本 bug。默认 `GITHUB_TOKEN` 即使声明了 `contents: write` 和 `pull-requests: write`，也不能创建或修改 workflow 文件。这样设计是为了防止一个 workflow 自我修改 CI 权限或注入新的 workflow。

因此，9 文件版本只有几种可行方式：

- 人工 PR：最简单，但不是自动 PR。
- GitHub App / PAT：token 需要 `workflow` 权限，可以推送 `.github/workflows/*`，但引入 secret 管理、权限审计和身份归属问题。
- Renovate 等专用依赖机器人：能力更强，但需要维护者接受新工具和配置复杂度。
- 拆分迁移：先人工完成一次 workflow 迁移，然后后续自动 PR 只做 4 文件 baseline 更新。

当前项目已经通过 #391 完成了这次拆分里的“人工 workflow 迁移”部分，所以长期自动化不应再追求每次都 9 文件。

### 方案优缺点对比

| 方案 | 能自动创建 PR | 能覆盖 9 文件历史迁移 | 安全/权限成本 | 优点 | 缺点 |
| --- | --- | --- | --- | --- | --- |
| 只加 verifier，不自动 PR | 否 | 可检查 | 低 | 最安全，先防漂移；适合 upstream 首个 PR | 不能自动提出升级 |
| Dependabot Docker updater 包含 `golang` | 是 | 否 | 低 | 配置最简单 | 只能改 Dockerfile，不能同步 `go.mod` / workflow；会制造 Go baseline drift |
| Dependabot gomod updater | 是 | 否 | 低 | 适合 Go module dependencies | 不是完整 Go compiler baseline 方案，不能同步 Docker builder tag |
| GitHub Actions + 默认 `GITHUB_TOKEN` | 是 | 否 | 中低 | 可以由 `github-actions[bot]` 开 PR；适合 #391 之后的 4 文件常规更新 | 需要仓库允许 Actions 创建 PR；不能改 workflow 文件；`GITHUB_TOKEN` 创建的 PR 不会递归触发其它 workflow |
| GitHub Actions + PAT / GitHub App token | 是 | 是 | 高 | 可以覆盖 `.github/workflows/*`，也可能触发后续 CI | 需要 secret / App 治理；token 泄漏风险；author 身份可能不是 `github-actions[bot]` |
| Renovate | 是 | 通常可配置覆盖 | 中 | 依赖升级能力成熟，可管 Docker / gomod / custom manager | 引入新机器人和配置；需要维护者维护规则，初始学习成本高 |
| 手工 Go toolchain PR | 否 | 是 | 低 | 最可控，适合少量低频升级或历史迁移 | 不能解决长期自动发现问题 |

> 分析：如果目标是“长期解决方案”，最佳顺序不是先追求全自动开 PR，而是先保证 baseline 不漂移。自动 PR 可以作为第二阶段，而且应限制为 post-#391 的常规 4 文件更新。

### 建议结论

短期建议：

1. 不把 `golang` 放回 Docker Dependabot。
2. 先提一个 verifier PR，检查：
   - `go.mod` Go directive；
   - Docker `golang:<version>` builder tag；
   - `actions/setup-go` 是否使用 `go-version-file: go.mod`。
3. verifier 合入后，再讨论 scheduled auto PR。

中期建议：

- 用 GitHub Actions 默认 `GITHUB_TOKEN` 做 4 文件常规更新 PR：
  - `go.mod`
  - `go.sum`（如果 `go mod tidy` 需要）
  - `docker/Dockerfile`
  - `docker/Dockerfile.router`
  - `docker/Dockerfile.picod`
- PR 不自动 merge。
- PR body 写清楚 creator workflow 已做的验证。
- 由于 `GITHUB_TOKEN` 创建的 PR 不递归触发其它 workflows，完整 CI 可以通过 maintainer 手动触发、merge queue / PR review 后触发，或在创建 workflow 内跑一组必要验证。

长期可选：

- 如果维护者希望自动化也覆盖 `.github/workflows/*` 迁移，单独讨论 GitHub App / Renovate。不要在第一版 verifier PR 中引入高权限 token。

### 英文 upstream issue 草稿

建议新开 focused enhancement issue，而不是直接发到 #386。#386 是 v0.2.0 umbrella，Go toolchain automation 涉及 Dependabot、workflow 权限和 bot PR 安全边界，单独讨论更容易收敛。

标题：

```text
Automate Go toolchain baseline drift checks and update proposals
```

正文：

````md
**What would you like to be added**:

I would like to add a lightweight maintenance path for the project Go toolchain baseline.

The first step can be a verifier that checks whether the Go baseline stays aligned across:

- the `go.mod` Go directive,
- Docker `golang:<version>` builder image tags under `docker/Dockerfile*`,
- and GitHub Actions `actions/setup-go` usage.

After that verifier is in place, we can optionally add a scheduled workflow that reads the latest stable Go release from the official Go release feed and opens a focused, reviewable PR when the project baseline is behind.

The generated PR should not be auto-merged.

**Why is this needed**:

PR #391 showed that the Go compiler/toolchain baseline is a coordinated project setting, not just a Docker base image update. It updated `go.mod`, Docker builder image tags, and GitHub Actions Go setup together.

In #422, the Docker Dependabot updater intentionally ignores `golang` builder images, because a Docker-only Dependabot PR would update Dockerfiles without updating `go.mod` and the CI source of truth. That avoids drift, but it leaves us without a clear long-term path for future Go baseline updates.

**Possible implementation direction**:

1. Add a verifier, for example `hack/verify-go-toolchain.*`, that checks:
   - `go.mod` has a parseable Go directive,
   - every `docker/Dockerfile*` `golang:<version>` builder tag matches that Go version,
   - every workflow using `actions/setup-go` uses `go-version-file: go.mod` instead of an inline `go-version`.
2. Run the verifier in CI.
3. Later, add a scheduled workflow that:
   - reads `https://go.dev/dl/?mode=json`,
   - compares the latest stable Go release with `go.mod`,
   - updates `go.mod` and Docker builder tags,
   - runs `go mod tidy`,
   - opens a PR with the exact validation result.

For regular future updates after #391, the generated PR should usually only need to change:

- `go.mod`,
- `go.sum` if `go mod tidy` changes it,
- `docker/Dockerfile`,
- `docker/Dockerfile.router`,
- `docker/Dockerfile.picod`.

**Fork-only validation**:

I tested the future-standard workflow in a fork:

- workflow run: https://github.com/ranxi2001/agentcube/actions/runs/28862855744
- generated PR: https://github.com/ranxi2001/agentcube/pull/20
- PR author: `app/github-actions`
- generated diff: `go.mod` plus the three Docker builder Dockerfiles

This validates the normal post-#391 path. I also tested a historical 9-file migration shape that modifies `.github/workflows/*`; GitHub rejected that push when using the default `GITHUB_TOKEN` because workflow files require `workflows` permission. That means workflow-file migrations should remain human-reviewed or use a separately approved GitHub App / PAT / Renovate setup.

**Alternatives considered**:

- Let Dependabot's Docker updater manage `golang:*`: this is simple, but it can only update Dockerfiles and can drift from `go.mod`.
- Use Dependabot's gomod updater: useful for Go module dependencies, but it does not keep Docker builder image tags aligned with the compiler baseline.
- Use a GitHub Actions workflow with the default `GITHUB_TOKEN`: this can create future 4-file Go baseline PRs, but it cannot create or update `.github/workflows/*` files and GitHub-token-created PRs do not recursively trigger all workflows.
- Use a PAT or GitHub App token with workflow-file permission: this can cover historical 9-file migrations that touch `.github/workflows/*`, but it adds secret management and security review overhead.
- Use Renovate: more powerful and configurable, but it introduces a new dependency management bot and configuration surface.

**Compatibility / security notes**:

The first PR should only add verification and should not introduce a high-privilege token.

If maintainers want an auto-PR workflow later, we should keep it review-only, avoid auto-merge, and document what validation runs inside the creator workflow versus what still requires normal PR CI.

**Related issues / PRs**:

- #391 updated the Go toolchain baseline to Go 1.26.4.
- #422 adds Docker Dependabot updates for runtime base images and intentionally excludes `golang`.
- #386 is the broader v0.2.0 tracking issue where the maintenance problem was originally noticed.
````

### 当前建议

- 不改 #422，不把 `golang` 放回 Docker Dependabot。
- 不改 #423，它已经是独立 runner pinning PR。
- 下一步先向 maintainer 提出长期方案，再根据反馈决定：
  - 只加 verifier；
  - verifier + scheduled issue；
  - verifier + scheduled PR；
  - 或者未来改用 Renovate 统一治理。

## 讨论复盘：为什么这个 issue 方向成立

用户进一步复盘后，对这个 issue 方向的总体判断是：这是一个偏高级的 CI/CD 工程问题，不是简单“加个 Dependabot”级别的问题。核心原因是它抓住了一个容易被忽略的边界：

> 分析：Go toolchain version bump 不是普通 dependency update，而是一个跨文件、跨环境的一致性变更。它同时影响本地开发、GitHub Actions CI、Docker builder stage、标准库、编译器行为、`go mod tidy` 结果、generated code 和 race/codegen/lint 等验证链路。

做得好的地方：

1. 把 Go toolchain 和 Go module dependency 分开处理。
   - `require github.com/foo/bar v1.2.3` 这类 library dependency 主要影响代码 API 和 module graph。
   - `go 1.26.4` / Docker `golang:1.26.4-*` 这类 compiler baseline 影响编译器、stdlib、语言版本和构建环境。
   - 因此不应让 Dependabot gomod 或 Docker updater 单独承担完整 Go baseline upgrade。

2. 明确识别 `go.mod`、Dockerfile 和 CI 之间的漂移风险。
   - 当前一致状态是 `go.mod go 1.26.4`、三个 Docker builder stage 使用 `golang:1.26.4...`、workflow 通过 `go-version-file: go.mod` 读取 Go baseline。
   - 如果有人只把 Dockerfile 改到 `golang:1.27-alpine`，Docker build 可能仍然成功，但本地、CI、Docker builder 会进入不同 Go 版本。
   - 这种隐性差异常见表现是“本地没问题，CI 或镜像里行为不同”，所以 verifier / scheduled check 的价值不是替代 review，而是防止环境漂移长期存在。

3. 不追求盲目自动合并 Go 升级 PR。
   - Go 升级可能影响 compiler behavior、standard library、build constraints、CGO、race detector、generated code 和 third-party modules。
   - 合理流程应是自动发现或自动创建 review-only PR，然后由 CI 和人工 review 决定是否合并。

4. 同时考虑 GitHub runner pinning，说明问题不是只盯 Go 版本号，而是在追求 reproducible build。
   - `ubuntu-latest` 是浮动 label，未来从 `ubuntu-24.04` 迁移到更新版本时，可能连带改变 gcc、glibc、Docker、kernel features 和系统包行为。
   - 因此 #423 的 runner pinning 和 Go baseline 方案属于同一类 CI 环境稳定性治理，但应拆成不同 PR。

可以继续加强的地方：

1. 避免长期维护脆弱的 ad hoc 解析逻辑。
   - 简单 `grep "golang:"` 容易漏掉 `FROM --platform=$BUILDPLATFORM golang:1.26.4-alpine`、`ARG GO_VERSION=...`、`FROM golang:${GO_VERSION}` 等写法。
   - 更稳的选择是 Dockerfile parser、Renovate regex/custom manager，或把项目约束成统一可解析的版本声明。

2. 可以讨论 single source of truth，但不必强行引入新文件。
   - `.go-version` 作为统一入口可以让 CI、Docker 和本地工具读取同一文件。
   - 但 Go 官方生态中 `go.mod` 本身就是合理的 project baseline source of truth；当前 workflow 已经使用 `go-version-file: go.mod`，所以第一版继续以 `go.mod` 为准更贴合现有项目。

3. 自动 PR 应标准化为低噪音维护流程。
   - 定时读取 Go stable release。
   - 比较项目 baseline。
   - 只在落后时更新 `go.mod` 和 Docker builder tags。
   - 创建 review-only PR，不自动 merge。

评分记录：

| 维度 | 评分 | 说明 |
| --- | ---: | --- |
| 问题识别 | 9/10 | 抓住 Go baseline 是跨环境一致性问题，而不是普通依赖 bump |
| 工程方向 | 9/10 | 先分清 module dependency、runtime base image、compiler baseline 三类更新 |
| 自动化设计 | 8/10 | scheduled review-only PR 比 push/PR 强制检查更低噪音；后续仍可补 parser / Renovate 等能力 |
| 可维护性 | 8/10 | 以 `go.mod` 为 source of truth 符合现状；需注意脚本解析不要过度依赖字符串匹配 |

> 注释：这个复盘的价值是形成 review 口径。后续如果把 Go toolchain automation 提成 upstream issue 或 PR，重点不是说“我们想自动升级 Go”，而是说“我们需要保证开发、CI、Docker 三个环境的 Go baseline 一致，并用低噪音自动化提醒维护者处理新版本”。

## PR 级生产分支：最终收敛为每周定时检查

用户进一步判断后，正式方案不再加入 push / pull_request 的降级拦截。原因是这类检查会在普通 PR 上增加一次外网 release feed 请求和一个额外失败面，而 Go baseline 升级本身是低频维护任务。和 Docker Dependabot 一样，正式版本只保留每周一次的定时检查：发现最新稳定 Go 高于项目 baseline 时，由 workflow 创建一个 review-only PR。

> 分析：这里的目标不是让每个 PR 都强制追最新 Go，而是把“是否有新 Go baseline”变成低频维护信号。Go 编译器升级影响面较大，发现后也不应自动 merge；定时 PR 足够提醒维护者，同时避免普通开发 PR 被外部 release feed 状态影响。

最终 PR 分支：

- Worktree: `/tmp/agentcube-go-toolchain-update-pr`
- Branch: `ci/go-toolchain-update-workflow`
- Remote branch: `https://github.com/ranxi2001/agentcube/tree/ci/go-toolchain-update-workflow`
- Base: `upstream/main` `fdb862b`
- Current commit: `b6a3156 ci: add scheduled go toolchain update workflow`
- Initial validated commit before Gemini feedback: `733bb4b`
- Changed files:
  - `.github/workflows/go-toolchain-update.yml`
  - `hack/go-toolchain.py`

最终 workflow 形态：

| Job | 触发事件 | 权限 | 作用 |
| --- | --- | --- | --- |
| `update-go-toolchain` | `schedule`，每周一 UTC 00:00（北京时间每周一 08:00），与 Dependabot weekly schedule 对齐 | job-level `contents: write`、`pull-requests: write` | 读取 go.dev 最新稳定版本；如果项目落后，更新 `go.mod` 和 Docker builder tags，并创建 review-only PR |

默认 workflow 权限仍是：

```yaml
permissions:
  contents: read
```

只有真正创建 PR 的 job 显式申请写权限。

本地验证：

```bash
go run github.com/rhysd/actionlint/cmd/actionlint@latest .github/workflows/go-toolchain-update.yml
python3 hack/go-toolchain.py verify --check-latest
git diff --check upstream/main...HEAD
```

结果：当时全部通过。后续 2026-07-08 的 schedule run 证明 go.dev 最新稳定版本已经变为 `1.26.5`，因此 `--require-latest` 应只作为生成的升级 PR 完成更新后的验证，不应作为“只新增定时 workflow”这个 PR 本身的长期本地校验命令。

2026-07-08 最终 PR 分支更新时，又做了一次正式验证：

- `go run github.com/rhysd/actionlint/cmd/actionlint@latest .github/workflows/go-toolchain-update.yml`
- `python3 hack/go-toolchain.py verify --check-latest`
- `git diff --check upstream/main...HEAD`
- Fork push CI for commit `733bb4b`: 9/9 success
  - Agentcube CI Workflow: <https://github.com/ranxi2001/agentcube/actions/runs/28914172116>
  - Agentcube E2E Tests: <https://github.com/ranxi2001/agentcube/actions/runs/28914172121>
  - Test Coverage: <https://github.com/ranxi2001/agentcube/actions/runs/28914172141>
  - Lint: <https://github.com/ranxi2001/agentcube/actions/runs/28914172112>
  - Codespell: <https://github.com/ranxi2001/agentcube/actions/runs/28914172128>
  - Python Lint: <https://github.com/ranxi2001/agentcube/actions/runs/28914172184>
  - Python SDK Tests: <https://github.com/ranxi2001/agentcube/actions/runs/28914172119>
  - Copyright Check: <https://github.com/ranxi2001/agentcube/actions/runs/28914172138>
  - Codegen Check: <https://github.com/ranxi2001/agentcube/actions/runs/28914172166>

> 注释：正式分支最后把 `workflow_dispatch` 移除，只保留 `schedule`。同时把 `actions/setup-go` 移到 `hack/go-toolchain.py update` 之后，避免先按旧 `go.mod` 安装旧 Go，再用旧 Go 执行新 `go.mod` 的 `go mod tidy`。

### 降级检查试验与废弃原因

中间曾试过把 push / PR verifier 加进正式 workflow，并让 verifier 使用 `--require-latest`。在 fork-only 测试分支里，`go.mod` 和三个 Docker builder tag 一起从 `1.26.4` 降到 `1.26.3` 后，push run 确实失败：

- Branch: `ci/go-toolchain-update-old-baseline-test`
- Run: https://github.com/ranxi2001/agentcube/actions/runs/28865686938
- Failure: `project Go 1.26.3 differs from latest stable Go 1.26.4`

后来又把 fork `main` 临时降级测试默认分支行为：

- Temporary fork `main` commit: `21e6b27 test: lower go baseline on fork main`
- Push run: https://github.com/ranxi2001/agentcube/actions/runs/28866194716
- Result: push verifier 失败，证明降级可以被发现
- Cleanup: fork `main` 已恢复到 `upstream/main` `fdb862b`；恢复 main 触发的无关 in-progress fork Actions 已取消

这些试验证明“PR/push 降级检查能发现旧版本”，但也证明它会制造额外 CI 负担。最终不把它放进正式 PR。

> 注释：这不是说降级检查完全无价值，而是当前项目更需要低噪音的维护提醒。真正升级 Go 时，workflow 生成的 PR 仍会在 creator job 内运行 `go mod tidy`、`verify --require-latest` 和 `git diff --check`；普通 PR 不再承担这个检查。

剩余限制：

- GitHub Actions 的 `schedule` 只会从默认分支运行。这个 PR 分支合入前，无法在 topic branch 上真实证明 weekly cron 会触发。
- 2026-07-08 补充验证：本机没有 `gh` CLI，使用 GitHub API 等价检查 workflow 列表。`Go Toolchain Update` 只有在 fork 默认分支 `main` 实际包含 `.github/workflows/go-toolchain-update.yml` 时才显示为 `active`；当 fork `main` 恢复到 `upstream/main fdb862b` 后，该 workflow 状态变为 `deleted`，因此不会触发 `schedule`。
- 2026-07-08 补充验证：曾短暂把测试 workflow 放到 fork `main`，把 cron 调到 `58 15 * * *`，并从 2026-07-07 15:58 UTC 等到约 16:06 UTC。GitHub API 没有出现任何 `event=schedule` 的 `Go Toolchain Update` run。结论是 GitHub cron 不适合作为即时验证信号；它只能证明“默认分支 active 后，未来某次 best-effort schedule 可能触发”，不能保证几分钟内入队。
- 2026-07-08 补充验证：一次手动 `workflow_dispatch` 失败 run `28878103452` 的根因不是调度，而是 workflow 先按旧 `go.mod` 安装 Go `1.26.1`，随后把 `go.mod` 更新到 `1.26.4` 后执行 `go mod tidy`，在 `GOTOOLCHAIN=local` 下报 `go.mod requires go >= 1.26.4`。修正方式是先执行 `hack/go-toolchain.py update` 修改 `go.mod`，再用 `actions/setup-go` 根据更新后的 `go.mod` 安装目标 Go。
- 2026-07-08 补充验证：后续按用户要求把 fork `main` 保持在测试 commit `37dc2bc`，workflow 同时包含 `schedule: "*/5 * * * *"` 和临时 `workflow_dispatch`。`gh workflow list -R ranxi2001/agentcube --all` 显示 `Go Toolchain Update active`，`gh workflow view --yaml` 也能看到 5 分钟 cron；但截至 2026-07-07 16:50 UTC，`gh run list --workflow "Go Toolchain Update" --event schedule` 仍为空。手动触发 run `28883380628` 成功，日志显示 `Go toolchain update needed: 1.26.1 -> 1.26.4`、`Go toolchain alignment: OK`，并创建 fork PR #22：<https://github.com/ranxi2001/agentcube/pull/22>。这证明 job 逻辑和 PR 创建权限正常；剩余问题集中在 GitHub `schedule` 事件没有及时入队，而不是 updater 脚本或 GITHUB_TOKEN 权限。
- 2026-07-08 最终验证：按用户要求把 fork `main` 的测试 workflow 改成 `schedule: "17 */6 * * *"` 后，GitHub 在 2026-07-07 20:17:51 UTC 自动触发 `event=schedule` run：<https://github.com/ranxi2001/agentcube/actions/runs/28895821751>。换算为北京时间是 2026-07-08 04:17:51。该 run 成功执行 `update-go-toolchain`，并由 `app/github-actions` 创建 fork PR #23：<https://github.com/ranxi2001/agentcube/pull/23>，标题为 `chore: update Go toolchain to 1.26.5`，head branch 为 `chore/go-toolchain-1265`，改动文件只有 `go.mod`、`docker/Dockerfile`、`docker/Dockerfile.router`、`docker/Dockerfile.picod`。diff 证明它把四处 baseline 从 `1.26.1` 升到 `1.26.5`。这说明 schedule-only 方案可以真实自动触发并创建 PR；此前没有及时入队是 GitHub cron best-effort 延迟问题，不是 workflow 逻辑不可用。
- 2026-07-08 cleanup：拿到 #23 证据后，已把 fork `main` 从临时测试 commit `dce5662` 恢复到 `upstream/main fdb862b`，并取消恢复 push 触发的无关 fork Actions。#23 暂时保留 open，方便人工查看证据。
- 如果未来 `schedule` 创建的 PR 使用默认 `GITHUB_TOKEN`，该 PR 不一定递归触发所有 downstream workflows；所以 creator workflow 里的 `verify`、`go mod tidy`、`git diff --check` 仍然必须保留。
- 如果维护者希望自动化也能修改 `.github/workflows/*`，仍然需要 GitHub App / PAT / Renovate 或人工 PR；默认 `GITHUB_TOKEN` 不应承担 workflow 文件迁移。

### PR 文本草稿

标题：

```text
ci: add scheduled go toolchain update workflow
```

正文：

````md
**What type of PR is this?**

/kind cleanup

**What this PR does / why we need it**:

Adds a repository-owned Go toolchain maintenance workflow and helper script.

The scheduled workflow checks the latest stable Go release from the official Go release feed once per week and opens a focused, reviewable PR only when the project baseline is behind. It does not auto-merge.

The schedule is aligned with the existing Dependabot weekly cadence: Monday 00:00 UTC.

This keeps Docker Dependabot focused on runtime base images while preventing `golang:*` builder images from drifting away from the project Go baseline.

**Which issue(s) this PR fixes**:

NONE

**Special notes for your reviewer**:

- The workflow uses read-only permissions by default.
- Write permissions are scoped only to the scheduled job that creates or updates the generated PR branch.
- PRs created by `GITHUB_TOKEN` may not recursively trigger every downstream workflow, so the creator workflow keeps its own validation steps.
- Validation:
  - `go run github.com/rhysd/actionlint/cmd/actionlint@latest .github/workflows/go-toolchain-update.yml`
  - `python3 hack/go-toolchain.py verify --check-latest`
  - `git diff --check upstream/main...HEAD`
- Fork branch push validation for commit `733bb4b`: 9/9 checks passed.
- Fork schedule validation:
  - schedule run: https://github.com/ranxi2001/agentcube/actions/runs/28895821751
  - generated PR: https://github.com/ranxi2001/agentcube/pull/23
- AI assistance: Used Codex to inspect the existing Go baseline surfaces, prepare the workflow/script, and validate the branch. I reviewed and validated the changes.

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
````
