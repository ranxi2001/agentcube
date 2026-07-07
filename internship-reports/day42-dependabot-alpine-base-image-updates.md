# Day 42：Dependabot 自动更新 Alpine / Docker base image

日期：2026-07-07

今天先处理 AgentCube v0.2.0 umbrella issue [#386](https://github.com/volcano-sh/agentcube/issues/386) 里 RainbowMango 新增的任务：

> Automate Alpine base image updates with Dependabot.

这个任务看起来只是改 `.github/dependabot.yml`，但 review 里最容易被问到的是两个边界：

1. Dependabot 的 Docker updater 到底会扫描哪些 Dockerfile。
2. 这个任务说的是 Alpine，但配置按目录生效，会不会把其他 base image 也纳入更新范围。

## 上游任务背景

[#386](https://github.com/volcano-sh/agentcube/issues/386) 是 v0.2.0 planning umbrella issue。2026-07-07 最新新增的任务在 `Security & Auth` 下：

```text
- [ ] Automate Alpine base image updates with Dependabot.
```

issue 里给出的上下文是：

- `docker/Dockerfile` 和 `docker/Dockerfile.router` 使用 Alpine runtime base image。
- 这些 base image 版本长期不更新会增加安全维护压力。
- 建议引入自动机制，尤其是 Alpine image。
- 参考 Karmada 的 Dependabot Docker image update 配置。

> 注释：这是 umbrella issue 的一个 checklist task，不是一个独立 bug issue。因此后续 PR 不能写 `Fixes #386`，否则可能把整个 v0.2.0 planning issue 关闭。正确写法是 `Refs #386`。

## 当前仓库状态

最新 `upstream/main` 是：

```text
7242754 Merge pull request #421 from volcano-sh/dependabot/github_actions/github-actions-4dfd9f9ba8
```

当前 `.github/dependabot.yml` 只配置了 GitHub Actions：

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "00:00"
      timezone: "UTC"
    commit-message:
      prefix: "chore(deps): "
    groups:
      github-actions:
        patterns:
          - "*"
```

`/docker` 目录当前 base images：

```text
docker/Dockerfile:2:FROM golang:1.26.4-alpine AS builder
docker/Dockerfile:30:FROM alpine:3.19
docker/Dockerfile.picod:2:FROM golang:1.26.4 AS builder
docker/Dockerfile.picod:25:FROM ubuntu:24.04
docker/Dockerfile.router:2:FROM golang:1.26.4-alpine AS builder
docker/Dockerfile.router:30:FROM alpine:3.19
```

这里可以分成两类：

| 文件 | build environment | runtime image | 和任务的关系 |
| --- | --- | --- | --- |
| `docker/Dockerfile` | `golang:1.26.4-alpine` | `alpine:3.19` | runtime Alpine 是这次任务的核心目标 |
| `docker/Dockerfile.router` | `golang:1.26.4-alpine` | `alpine:3.19` | runtime Alpine 是这次任务的核心目标 |
| `docker/Dockerfile.picod` | `golang:1.26.4` | `ubuntu:24.04` | 同在 `/docker` 目录，runtime Ubuntu 也会被同一 Docker updater 覆盖 |

> 分析：Dependabot 的 Docker updater 是按 `package-ecosystem: "docker"` 加 `directory` 扫描，不是按某一个 Dockerfile 或某一个 image name 精准声明。为了覆盖 `docker/Dockerfile.router` 这种非标准 Dockerfile 名，目录级配置是合理的最小改动。但 `golang:*` builder image 不是普通 runtime base image，它代表项目 Go toolchain baseline，需要单独治理。

## 关键确认：非标准 Dockerfile 名能否被扫描

一开始需要确认 `Dockerfile.router` 是否会被 Dependabot 扫到。否则只加 `directory: "/docker"` 可能只更新 `docker/Dockerfile`，漏掉 router。

查询当前 `dependabot-core` 的 Docker file fetcher 后，结论是可以覆盖。当前实现使用文件名正则：

```ruby
DOCKER_REGEXP = /dockerfile|containerfile/i
```

并在配置的目录中筛选：

```ruby
repo_contents(raise_errors: false)
  .select { |f| f.type == "file" && f.name.match?(self.class.filename_regex) }
```

因此 `/docker` 目录下文件名包含 `Dockerfile` 的文件都会被作为候选 Dockerfile：

- `Dockerfile`
- `Dockerfile.router`
- `Dockerfile.picod`

> 注释：这也是为什么不需要为 `Dockerfile.router` 单独建立目录或改名。这个发现应写进 reviewer notes，避免 reviewer 担心非标准文件名不生效。

## Karmada 参考

Karmada 的参考配置本质也是增加 Docker ecosystem entry：

```yaml
- package-ecosystem: docker
  directory: /cluster/images/
  schedule:
    interval: "weekly"
    day: "monday"
    time: "00:00"
    timezone: "UTC"
```

AgentCube 的最小对应改法就是在现有 Dependabot 配置中新增：

```yaml
  - package-ecosystem: "docker"
    directory: "/docker"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "00:00"
      timezone: "UTC"
    commit-message:
      prefix: "chore(deps): "
    ignore:
      - dependency-name: "golang"
```

我保留了 AgentCube 现有的 `chore(deps): ` commit prefix，和 GitHub Actions Dependabot PR 风格一致。

同时显式忽略 `golang` Docker image。原因是 `golang:1.26.4-alpine` / `golang:1.26.4` 不是单纯 runtime base image：它们需要和 `go.mod`、GitHub Actions Go setup、开发机默认 Go 版本保持一致。上游 [#391](https://github.com/volcano-sh/agentcube/pull/391) 就是一次完整 Go toolchain baseline 升级：同时改 `go.mod`、Actions 的 `go-version-file: go.mod` 和三个 Docker builder image。让 Dependabot 单独 bump `golang` Docker tag 会制造新的漂移。

## 为什么没有只限定 Alpine

这次任务标题强调 Alpine，但最终配置选择覆盖 `/docker` 目录下的 runtime Docker base images，并显式排除 `golang` builder image。

原因：

1. Dependabot Docker updater 的主要配置粒度是目录。
2. `docker/Dockerfile` 和 `docker/Dockerfile.router` 在同一个 `/docker` 目录中。
3. `docker/Dockerfile.picod` 也在同一个目录中，所以 PicoD 的 runtime `ubuntu` image 会被同一 updater 覆盖。
4. `golang:1.26.4-alpine` 在 Dependabot 语义里依赖名是 `golang`，不是 `alpine`。它虽然带 `alpine` variant，但本质是 Go builder image，应随 Go toolchain baseline 一起升级，而不是随 runtime base image 自动 bump。

所以更清楚的 PR 口径应该是：

```text
This PR enables Dependabot Docker updates for the /docker directory.
The primary motivation is Alpine base image maintenance for workloadmanager and router,
but the configured scope is runtime Docker base images under /docker.
The Go builder image is intentionally ignored because Go toolchain upgrades
must stay aligned with go.mod and CI.
```

> 分析：这个口径比“只自动更新 Alpine”更准确，也比“所有 Docker base images 都自动更新”更安全。实际行为会发现 Alpine 和 Ubuntu runtime image 更新；`golang` builder image 则留给专门的 Go/toolchain PR，避免破坏 #391 建立的版本一致性。

## 已完成实现

临时 clean worktree：

```text
/tmp/agentcube-day42-dependabot-alpine
```

上游候选分支：

```text
chore/dependabot-docker-base-images
```

本地 commit：

```text
0d4e33037a3eac07b0f5bec936dd7cb01afb46da chore: enable dependabot docker updates
Signed-off-by: ranxi2001 <ranxi169@163.com>
```

改动范围：

```text
.github/dependabot.yml | 12 ++++++++++++
```

diff：

```diff
+  - package-ecosystem: "docker"
+    directory: "/docker"
+    schedule:
+      interval: "weekly"
+      day: "monday"
+      time: "00:00"
+      timezone: "UTC"
+    commit-message:
+      prefix: "chore(deps): "
+    ignore:
+      - dependency-name: "golang"
```

## 验证记录

### YAML 与 diff 检查

```bash
git diff --check
```

结果：通过。

```bash
python3 - <<'PY'
import yaml
cfg = yaml.safe_load(open('.github/dependabot.yml', encoding='utf-8'))
ok = any(
    u.get('package-ecosystem') == 'docker'
    and u.get('directory') == '/docker'
    and u.get('ignore') == [{'dependency-name': 'golang'}]
    for u in cfg['updates']
)
print(f'dependabot.yml parsed; docker /docker update present and golang ignored={ok}')
raise SystemExit(0 if ok else 1)
PY
```

结果：

```text
dependabot.yml parsed; docker /docker update present and golang ignored=True
```

### Dockerfile 覆盖范围

```bash
git grep -n -E '^FROM ' -- docker
```

结果：

```text
docker/Dockerfile:2:FROM golang:1.26.4-alpine AS builder
docker/Dockerfile:30:FROM alpine:3.19
docker/Dockerfile.picod:2:FROM golang:1.26.4 AS builder
docker/Dockerfile.picod:25:FROM ubuntu:24.04
docker/Dockerfile.router:2:FROM golang:1.26.4-alpine AS builder
docker/Dockerfile.router:30:FROM alpine:3.19
```

没有运行 `make test` 或镜像构建，因为这是 GitHub Dependabot 配置变更，不改变 Go 代码、Dockerfile 内容或 runtime 镜像内容。可执行的本地验证主要是 YAML parse、diff check 和 scope audit。

## Reviewer 可能会问的问题

### 为什么这能自动更新 Alpine

Dependabot 支持 Docker ecosystem。配置 `package-ecosystem: "docker"` 和 `directory: "/docker"` 后，Dependabot 会定期扫描该目录下 Dockerfile 中的 `FROM` image references，并在发现新版本时创建 dependency update PR。

### 为什么 `/docker` 会覆盖 `Dockerfile.router`

当前 Dependabot Docker fetcher 匹配文件名里的 `dockerfile` 或 `containerfile`，大小写不敏感。因此 `Dockerfile.router` 和 `Dockerfile.picod` 都会被扫描。

### 为什么 PR 不只覆盖 `alpine:3.19`

因为 Dependabot 的 Docker updater 是目录级扫描。`/docker` 下除了 workloadmanager/router 的 Alpine runtime image，还有 PicoD 的 Ubuntu runtime image。最终配置让 runtime base image 自动更新，但通过 `ignore` 排除了 `golang` builder image。

### 为什么忽略 `golang`

`golang:*` Docker image 是编译器环境，不只是 runtime base image。它应该和项目 Go baseline 一起变更：`go.mod`、CI `go-version-file`、本地开发版本和 Docker builder image 需要保持一致。#391 的做法就是这个标准：一个 focused PR 同步升级 Go toolchain baseline，而不是让 Docker updater 单独改 builder image。

### 为什么不用 group

当前最小实现先不增加 Docker group，保持和 Karmada 参考更接近。这样 Dependabot 可以按 dependency 分别开 PR，reviewer 更容易判断单个 base image 更新的影响。如果维护者希望减少 PR 数量，可以后续再加 Docker group。

## PR 草稿

Title:

```text
chore: enable Dependabot Docker base image updates
```

Body:

````markdown
**What type of PR is this?**

/kind enhancement

**What this PR does / why we need it**:

This PR adds a Docker ecosystem entry to `.github/dependabot.yml` for the `/docker` directory.

AgentCube already uses Dependabot for GitHub Actions updates. The v0.2.0 planning issue also calls out that Alpine runtime base images in `docker/Dockerfile` and `docker/Dockerfile.router` can become outdated over time, which increases security maintenance burden.

With this configuration, Dependabot can scan Dockerfiles under `/docker` and propose PRs when runtime Docker base image tags have newer versions. The primary motivation is Alpine base image maintenance for workloadmanager and router, and the configured directory scope also covers PicoD's Ubuntu runtime image in the same directory.

The `golang` Docker image is intentionally ignored. The Go builder image should stay aligned with the project's Go toolchain baseline in `go.mod` and CI, so Go toolchain upgrades should remain focused PRs rather than Docker-only Dependabot bumps.

**Which issue(s) this PR fixes**:

Refs #386

**Special notes for your reviewer**:

This is a configuration-only change. Dependabot's Docker updater discovers Dockerfiles by filename pattern under the configured directory, so `/docker` covers `Dockerfile`, `Dockerfile.router`, and `Dockerfile.picod`.

The Docker updater ignores `golang` because Go builder image updates need to stay coordinated with `go.mod` and GitHub Actions Go setup. This keeps Go toolchain baseline upgrades separate from runtime base image maintenance.

AI assistance was used to prepare the change rationale and validation notes.

Validation:

- `git diff --check`
- Parsed `.github/dependabot.yml` with PyYAML and verified the Docker `/docker` update entry is present and `golang` is ignored
- Audited Docker base images under `/docker`
- Fork-only validation: after enabling Dependabot version updates on the fork and temporarily scheduling the Docker updater, Dependabot opened [`alpine:3.19 -> 3.24`](https://github.com/ranxi2001/agentcube/pull/17) and [`ubuntu:24.04 -> 26.04`](https://github.com/ranxi2001/agentcube/pull/18) update PRs for `/docker`

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
````

> 注释：PR body 里用 `Refs #386`，不写 `Fixes #386`。因为这个 PR 只完成 umbrella issue 的一个 checklist task。

## 维护者确认与 fork PR 页面核对

2026-07-07 15:20（Asia/Shanghai），RainbowMango 在 #386 回复：

```text
Thanks, and looks good by the way.
```

这说明 `/docker` 目录级 scope 已经得到 maintainer 初步认可；后续不再需要等待 scope 方向确认。

同时核对了 fork PR 页面 `https://github.com/ranxi2001/agentcube/pulls`：

- 没有以 `chore/dependabot-docker-base-images` 为 head branch 的 fork PR。
- 当前 fork PR #9-#16 是 Dependabot 自动创建的安全更新 PR，base 都是 fork `main`，head 是 `dependabot/...` 分支；它们不是本次准备提交到 upstream 的 Docker base image 配置 PR。
- upstream open PR 列表里没有看到重复的 Dependabot Docker base image PR。
- 发现一个需要清理的 fork 分支卫生问题：`origin/main` 曾被临时验证 commit 改过，不是最新 `upstream/main de41b90` 的干净镜像。后续远端 `main` 上出现 `cb3ea03 ci: reschedule dependabot docker check`，把 Docker Dependabot schedule 临时改成 `daily / 15:53 / Asia/Shanghai`。这只适合 fork 验证，不应留在 fork `main`。

> 分析：fork `main` 的偏差不会改变 upstream 当前状态，但会让 fork 页面产生额外 Dependabot 活动，也违反“fork main 只作为 upstream/main 镜像”的规则。本轮验证完成后已把 `origin/main` 恢复为 `upstream/main de41b90` 镜像，并把 topic branch rebase 到最新 upstream main。

### 更正与复验：Version updates 开启后已生成 Alpine PR

用户指出：最重要的 Alpine image 反而没有生成升级 PR。这个提醒是对的。根因不是 Docker updater 不支持 Alpine，而是 fork 的 Dependabot **version updates** 当时没有在 Settings 里启用；之前出现的 #9-#16 是 security updates，不是按 `.github/dependabot.yml` schedule 跑出来的 version updates。

复验步骤：

1. 在 fork `ranxi2001/agentcube` 的 Settings / Advanced Security 里手动打开 Dependabot version updates。
2. 将 fork `main` 的 Docker updater schedule 临时改成 `daily / 15:53 / Asia/Shanghai`。
3. 轮询 fork branch / PR，查看是否出现 `dependabot/docker...` 分支。

复验结果：

- [fork PR #17](https://github.com/ranxi2001/agentcube/pull/17)：`chore(deps): bump alpine from 3.19 to 3.24 in /docker`
  - head branch: `dependabot/docker/docker/alpine-3.24`
  - 创建时抓取的 diff: `docker/Dockerfile` 和 `docker/Dockerfile.router` 的 runtime image 从 `alpine:3.19` 改成 `alpine:3.24`
- [fork PR #18](https://github.com/ranxi2001/agentcube/pull/18)：`chore(deps): bump ubuntu from 24.04 to 26.04 in /docker`
  - head branch: `dependabot/docker/docker/ubuntu-26.04`
  - 创建时抓取的 diff: `docker/Dockerfile.picod` 的 runtime image 从 `ubuntu:24.04` 改成 `ubuntu:26.04`

> 注释：复验完成后 `origin/main` 已恢复为 upstream mirror，因此 GitHub PR 页面现在会额外显示 `.github/dependabot.yml` 差异；上面的文件范围是 PR 刚生成时用 `gh pr view` / `gh pr diff` 抓取的原始证据。

这和 Karmada 的真实历史 PR 行为一致，例如 Karmada 会生成 `dependabot/docker/cluster/images/alpine-...` 分支和 `build(deps): bump alpine ... in /cluster/images` PR。

> 分析：这个复验说明 `/docker` 目录级 Docker ecosystem 配置确实会覆盖 Alpine runtime image，并且也会同时覆盖同目录下的 Ubuntu runtime image。后续 upstream PR 可以说“fork-only validation confirmed Dependabot creates an Alpine update PR after version updates are enabled on the fork”，但要说明这是个人 fork 验证，不是 upstream 仓库已经生成 PR。

### 后续检查入口

以后检查 Dependabot Docker updater 是否真的跑起来，按这个顺序看：

1. Fork 设置入口：`https://github.com/ranxi2001/agentcube/settings/security_analysis`
   - 检查 `Dependabot version updates` 是否 enabled。
   - 注意：`Dependabot security updates` enabled 只代表安全告警更新，不代表 `.github/dependabot.yml` 的定时 version updates 会跑。
2. Dependabot 状态入口：GitHub UI 进入 `Insights -> Dependency graph -> Dependabot`。
   - 这里能看 configured version updates、last checked 状态，并可在 UI 里手动 `Check for updates`。
3. PR 页面：
   - `https://github.com/ranxi2001/agentcube/pulls?q=is%3Apr+author%3Aapp%2Fdependabot+alpine`
   - `https://github.com/ranxi2001/agentcube/pulls?q=is%3Apr+author%3Aapp%2Fdependabot+docker`
4. 分支页面：
   - `https://github.com/ranxi2001/agentcube/branches/all?query=dependabot%2Fdocker`

命令行检查：

```bash
gh pr list -R ranxi2001/agentcube --state all --limit 100 \
  --json number,title,state,headRefName,baseRefName,author,url \
  --jq '.[] | select((.headRefName|ascii_downcase|test("dependabot/docker|alpine|ubuntu")) or (.title|ascii_downcase|test("alpine|ubuntu|docker base|base image"))) | [(.number|tostring), .state, .baseRefName, .headRefName, .author.login, .title, .url] | @tsv'

gh api repos/ranxi2001/agentcube/branches --paginate \
  --jq '.[] | select(.name|test("dependabot/docker|alpine|ubuntu"; "i")) | .name'
```

参考文档：

- [Configuring Dependabot version updates - Enabling version updates on forks](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-version-updates#enabling-version-updates-on-forks)
- [Dependabot security updates](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-security-updates)

## 当前状态与下一步

当前状态：

- 上游候选代码已在本地 clean topic branch 完成，并已 rebase 到最新 `upstream/main de41b90`。
- fork topic branch 当前 remote head 是 `0d4e33037a3eac07b0f5bec936dd7cb01afb46da`。
- fork topic branch 已推送：`https://github.com/ranxi2001/agentcube/tree/chore/dependabot-docker-base-images`。
- fork `main` 已恢复为 `upstream/main de41b90` 的干净镜像；临时 schedule 验证 commit 不再留在 fork `main`。
- 已在 #386 回复 RainbowMango 的 `/help`，说明可以帮助该任务、当前计划和 `/docker` scope：`https://github.com/volcano-sh/agentcube/issues/386#issuecomment-4900995393`。
- RainbowMango 已回复 scope 看起来可以：`https://github.com/volcano-sh/agentcube/issues/386#issuecomment-4901190000`。
- 已创建 upstream PR [#422](https://github.com/volcano-sh/agentcube/pull/422)：`chore: enable Dependabot Docker base image updates`。
- PR #422 当前是 open、非 draft、mergeable，label 已有 `kind/enhancement`；DCO、Approve workflows、golangci-lint、Python Lint、Python SDK Tests 已成功，build / e2e / Codegen / Codespell / Copyright / Coverage 创建后仍在运行。
- 没有在 #386 评论 `/assign`。

建议下一步：

1. 跟踪 PR #422 CI 和 review；不要自动 push 新 commit 或评论，除非有明确失败或 reviewer 反馈。
2. 如果后续要自动化 Go toolchain 升级，另开独立方案：不能只让 Docker updater bump `golang`，需要同时更新 `go.mod`、CI 和 Docker builder image。
3. 如 maintainer 后续要求收窄到 Alpine-only，再评估 Dependabot `ignore` 配置或 Dockerfile 目录结构调整。
