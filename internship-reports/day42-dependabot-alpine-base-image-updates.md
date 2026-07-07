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

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
````

> 注释：PR body 里用 `Refs #386`，不写 `Fixes #386`。因为这个 PR 只完成 umbrella issue 的一个 checklist task。

## 当前状态与下一步

当前状态：

- 上游候选代码已在本地 clean topic branch 完成。
- 没有 push fork topic branch。
- 没有创建 upstream PR。
- 没有在 #386 评论 `/assign` 或 `/help`。

建议下一步：

1. 用户确认后，先推送 `chore/dependabot-docker-base-images` 到 fork。
2. 创建 upstream PR，使用上面的 title/body。
3. 如果需要认领任务，可以在 #386 或 PR 中由用户确认后补 `/assign`。
