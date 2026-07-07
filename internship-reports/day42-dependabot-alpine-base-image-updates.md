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
| `docker/Dockerfile` | `golang:1.26.4-alpine` | `alpine:3.19` | 直接命中 Alpine builder/runtime |
| `docker/Dockerfile.router` | `golang:1.26.4-alpine` | `alpine:3.19` | 直接命中 Alpine builder/runtime |
| `docker/Dockerfile.picod` | `golang:1.26.4` | `ubuntu:24.04` | 同在 `/docker` 目录，会被同一 Dependabot Docker entry 覆盖 |

> 分析：Dependabot 的 Docker updater 是按 `package-ecosystem: "docker"` 加 `directory` 扫描，不是按某一个 Dockerfile 或某一个 image name 精准声明。为了覆盖 `docker/Dockerfile.router` 这种非标准 Dockerfile 名，目录级配置是合理的最小改动。

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
```

我保留了 AgentCube 现有的 `chore(deps): ` commit prefix，和 GitHub Actions Dependabot PR 风格一致。

## 为什么没有只限定 Alpine

这次任务标题强调 Alpine，但实际配置选择覆盖 `/docker` 目录下的 Docker base images。

原因：

1. Dependabot Docker updater 的主要配置粒度是目录。
2. `docker/Dockerfile` 和 `docker/Dockerfile.router` 在同一个 `/docker` 目录中。
3. `golang:1.26.4-alpine` 在 Dependabot 语义里依赖名是 `golang`，不是 `alpine`。
4. 如果通过 `ignore` 强行排除 `golang` 或 `ubuntu`，会产生不自然的维护边界，也会漏掉 Alpine variant 的 Go builder image 更新。

所以更清楚的 PR 口径应该是：

```text
This PR enables Dependabot Docker updates for the /docker directory.
The primary motivation is Alpine base image maintenance for workloadmanager and router,
but the configured scope is the Docker base images under /docker.
```

> 分析：这个口径比“只自动更新 Alpine”更准确。因为实际行为会同时发现 `golang` 和 `ubuntu` base image 更新。提前说明 scope，可以降低 reviewer 看到 PicoD 也被覆盖时的疑问。

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
78b608abb29e284c7fc2d725c76c9b966eb9445e chore: enable dependabot docker updates
Signed-off-by: ranxi2001 <ranxi169@163.com>
```

改动范围：

```text
.github/dependabot.yml | 10 ++++++++++
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
    u.get('package-ecosystem') == 'docker' and u.get('directory') == '/docker'
    for u in cfg['updates']
)
print(f'dependabot.yml parsed; docker /docker update present={ok}')
raise SystemExit(0 if ok else 1)
PY
```

结果：

```text
dependabot.yml parsed; docker /docker update present=True
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

因为 Dependabot 的目录扫描会读取 `/docker` 下所有 Dockerfile base images。这样能覆盖 Alpine runtime image，也能覆盖 `golang:*-alpine` builder image。副作用是 PicoD 的 `golang` / `ubuntu` base image 也在同一个维护入口下。这个范围是清晰、可解释、低成本的。

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

With this configuration, Dependabot can scan Dockerfiles under `/docker` and propose PRs when Docker base image tags have newer versions. The primary motivation is Alpine base image maintenance for workloadmanager and router, but the configured scope is the Docker base images under `/docker`, so it also covers PicoD's builder/runtime base images in the same directory.

**Which issue(s) this PR fixes**:

Refs #386

**Special notes for your reviewer**:

This is a configuration-only change. Dependabot's Docker updater discovers Dockerfiles by filename pattern under the configured directory, so `/docker` covers `Dockerfile`, `Dockerfile.router`, and `Dockerfile.picod`.

AI assistance was used to prepare the change rationale and validation notes.

Validation:

- `git diff --check`
- Parsed `.github/dependabot.yml` with PyYAML and verified the Docker `/docker` update entry is present
- Audited Docker base images under `/docker`
- Fork-only validation: after enabling Dependabot version updates on the fork and temporarily scheduling the Docker updater, Dependabot opened `alpine:3.19 -> 3.24` and `ubuntu:24.04 -> 26.04` update PRs for `/docker`

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
- 发现一个需要清理的 fork 分支卫生问题：`origin/main` 曾被临时验证 commit 改过，不是最新 `upstream/main de41b90` 的干净镜像。后续又通过 GitHub Contents API 提交 `cb3ea03 ci: reschedule dependabot docker check`，把 Docker Dependabot schedule 临时改成 `daily / 15:53 / Asia/Shanghai`，只适合 fork 验证，不应留在 fork `main`。

> 分析：fork `main` 的偏差不会改变 upstream 当前状态，但会让 fork 页面产生额外 Dependabot 活动，也违反“fork main 只作为 upstream/main 镜像”的规则。创建 upstream PR 前，建议先把 `origin/main` 恢复为 `upstream/main` 镜像，再把 topic branch rebase 到最新 upstream main。

### 更正与复验：Version updates 开启后已生成 Alpine PR

用户指出：最重要的 Alpine image 反而没有生成升级 PR。这个提醒是对的。根因不是 Docker updater 不支持 Alpine，而是 fork 的 Dependabot **version updates** 当时没有在 Settings 里启用；之前出现的 #9-#16 是 security updates，不是按 `.github/dependabot.yml` schedule 跑出来的 version updates。

复验步骤：

1. 在 fork `ranxi2001/agentcube` 的 Settings / Advanced Security 里手动打开 Dependabot version updates。
2. 将 fork `main` 的 Docker updater schedule 临时改成 `daily / 15:53 / Asia/Shanghai`。
3. 轮询 fork branch / PR，查看是否出现 `dependabot/docker...` 分支。

复验结果：

- [fork PR #17](https://github.com/ranxi2001/agentcube/pull/17)：`chore(deps): bump alpine from 3.19 to 3.24 in /docker`
  - head branch: `dependabot/docker/docker/alpine-3.24`
  - diff: `docker/Dockerfile` 和 `docker/Dockerfile.router` 的 runtime image 从 `alpine:3.19` 改成 `alpine:3.24`
- [fork PR #18](https://github.com/ranxi2001/agentcube/pull/18)：`chore(deps): bump ubuntu from 24.04 to 26.04 in /docker`
  - head branch: `dependabot/docker/docker/ubuntu-26.04`
  - diff: `docker/Dockerfile.picod` 的 runtime image 从 `ubuntu:24.04` 改成 `ubuntu:26.04`

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
- fork topic branch 当前 remote head 是 `1084c7ff79985f523a891f3ed2633436f0b1c2de`。
- fork topic branch 已推送：`https://github.com/ranxi2001/agentcube/tree/chore/dependabot-docker-base-images`。
- fork `main` 已恢复为 `upstream/main de41b90` 的干净镜像；临时 schedule 验证 commit 不再留在 fork `main`。
- 已在 #386 回复 RainbowMango 的 `/help`，说明可以帮助该任务、当前计划和 `/docker` scope：`https://github.com/volcano-sh/agentcube/issues/386#issuecomment-4900995393`。
- RainbowMango 已回复 scope 看起来可以：`https://github.com/volcano-sh/agentcube/issues/386#issuecomment-4901190000`。
- 没有创建 upstream PR。
- 没有在 #386 评论 `/assign`。

建议下一步：

1. 用户确认后，创建 upstream PR，使用上面的 title/body；PR 仍然写 `Refs #386`。
2. PR reviewer notes 可以补一句 fork-only validation：after enabling Dependabot version updates on the fork, Dependabot opened `alpine:3.19 -> 3.24` and `ubuntu:24.04 -> 26.04` Docker update PRs for `/docker`。
3. 如 maintainer 后续要求收窄到 Alpine-only，再评估 Dependabot `ignore` 配置或 Dockerfile 目录结构调整。
