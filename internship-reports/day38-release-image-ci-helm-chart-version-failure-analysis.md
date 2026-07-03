# Day 38: Release Image CI 中 Helm Chart Version 失败分析

日期：2026-07-02

> 更新：2026-07-03 重新评估后，`main` push 完全停止发布镜像/Chart 的方案不再作为推荐方案。考虑到用户或贡献者可能直接使用 `latest` 镜像体验主分支最新系统，更合理的方向是保留 `main` push 的 latest image 发布，同时把 Docker image tag 和 Helm chart `version` 拆开：image tag 继续用 `latest`，chart `version` 使用固定特殊 SemVer `0.0.0`。下文早期的 tag-only 收敛记录保留为排查过程，最终建议见文末“重新评估后的推荐方案”。2026-07-03 已在 fork `main` 上完成真实 push workflow 验证：latest images、`agentcube-0.0.0.tgz` package 和 GHCR Helm chart push 均成功。

## 结论先行

这次看到的 CI 红点不是 `docs/proposals` PR 本身的验证失败，而是 PR 合并到 `main` 后触发的发布工作流失败。

失败 workflow 是：

- Workflow: `Build and Push Release Images`
- Run: <https://github.com/volcano-sh/agentcube/actions/runs/28582345874>
- Job: <https://github.com/volcano-sh/agentcube/actions/runs/28582345874/job/84745444791>
- Event: `push`
- Branch: `main`
- Head SHA: `7cfeb8c222f82ccbacc3048a6fd66d5bc255fb9f`
- Display title: `Merge pull request #415 from ranxi2001/docs/proposals-management`

根因是 `.github/workflows/build-push-release.yml` 把同一个 `TAG` 同时用于 Docker image tag 和 Helm chart version：

- main 分支 push 时，workflow 设置 `TAG=latest`
- Docker image tag 可以用 `latest`
- Helm chart 的 `Chart.yaml.version` 需要 SemVer，`latest` 不是合法 chart version
- 因此 `helm package ... --version latest` 必然失败

日志中的核心错误是：

```text
Error: validation: chart.metadata.version "latest" is invalid
```

> 注释：这里的 `latest` 对镜像是合法的，例如 `ghcr.io/volcano-sh/workloadmanager:latest`。但 Helm chart 的 `version` 不是镜像标签，它是 chart 包的发布版本号，Helm 会按版本语义校验。

## 这不是 #415 文档 PR 引入的问题

这次 run 的触发 commit 是 #415 merge commit，所以 GitHub 页面上看起来像是 #415 导致 release workflow 红了。

但从失败位置看，#415 的 docs/proposals 改动没有进入 Helm chart 包内容，也没有改 `.github/workflows/build-push-release.yml`。真正失败的是既有发布工作流在 main push 场景下的固定逻辑。

最近多次 `main` merge 都失败在同一个步骤：

| 时间 | Run | SHA | Merge / 标题 | 失败步骤 |
| --- | --- | --- | --- | --- |
| 2026-07-02 10:12 UTC | `28582345874` | `7cfeb8c` | Merge PR #415 | `Package Helm chart` |
| 2026-07-02 07:30 UTC | `28573199105` | `f9c37d5` | Merge PR #411 | `Package Helm chart` |
| 2026-07-02 07:25 UTC | `28572939059` | `a535e0e` | Merge PR #414 | `Package Helm chart` |
| 2026-07-02 02:27 UTC | `28561062823` | `d3eb47a` | Merge PR #399 | `Package Helm chart` |
| 2026-07-01 07:29 UTC | `28501087148` | `14a3f04` | Merge PR #403 | `Package Helm chart` |
| 2026-06-22 04:14 UTC | `27929112223` | `bed6bd4` | Merge PR #367 | `Package Helm chart` |
| 2026-06-18 06:37 UTC | `27741532706` | `a31651e` | Merge PR #391 | `Package Helm chart` |
| 2026-06-12 10:21 UTC | `27409754528` | `0fd9151` | Merge PR #376 | `Package Helm chart` |
| 2026-06-12 06:49 UTC | `27399708570` | `0a839a2` | Merge PR #383 | `Package Helm chart` |
| 2026-06-08 07:42 UTC | `27123151611` | `beadcd7` | Merge PR #378 | `Package Helm chart` |

> 分析：这说明它是 release workflow 的长期系统性问题。它不是某个业务代码测试不稳定，也不是某个 PR 改坏了 Helm chart。

## 失败日志拆解

目标 job 的失败步骤为 `Package Helm chart`。前面的关键步骤都成功：

- `Checkout code`: success
- `Set up Go`: success
- `Set up Docker Buildx`: success
- `Set up Helm`: success
- `Determine release metadata`: success
- `Login to GitHub Container Registry`: success
- `Build and push images`: success
- `Login Helm to GitHub Container Registry`: success
- `Package Helm chart`: failure
- `Push Helm chart`: skipped

失败步骤运行的命令是：

```bash
yq e -i '.version = env(TAG) | .appVersion = env(TAG)' "${CHART_PATH}/Chart.yaml"
yq e -i '
  .router.image.repository = env(IMAGE_REGISTRY) + "/agentcube-router" |
  .router.image.tag = env(TAG) |
  .workloadmanager.image.repository = env(IMAGE_REGISTRY) + "/workloadmanager" |
  .workloadmanager.image.tag = env(TAG)
' "${CHART_PATH}/values.yaml"
helm package "${CHART_PATH}" --version "${TAG}" --app-version "${TAG}"
```

当时环境变量是：

```text
TAG=latest
CHART_PATH=manifests/charts/base
IMAGE_REGISTRY=ghcr.io/volcano-sh
```

因此实际效果是：

```bash
helm package manifests/charts/base --version latest --app-version latest
```

Helm 报错：

```text
Error: validation: chart.metadata.version "latest" is invalid
```

> 注释：日志报的是 `chart.metadata.version`，不是 `appVersion`。Helm 官方文档中 `appVersion` 是应用版本，允许不是 SemVer；但 chart `version` 是 chart 包版本，必须按 SemVer 规则处理。

## 源码链路

当前 upstream `main` 的 `.github/workflows/build-push-release.yml` 中，触发条件是：

```yaml
on:
  push:
    branches:
      - main
    tags:
      - "v*.*.*"
      - "v*.*.*-*" # Support for pre-release tags like v1.2.3-alpha
```

也就是说，只要有 PR 合并进 `main`，这个 workflow 就会跑。

Release metadata 逻辑是：

```bash
if [[ "${{ github.ref_type }}" == "tag" ]]; then
  echo "TAG=${{ github.ref_name }}" >> "$GITHUB_ENV"
else
  echo "TAG=latest" >> "$GITHUB_ENV"
fi
```

随后镜像构建使用同一个 `TAG`：

```bash
make docker-buildx-push IMAGE_REGISTRY="${IMAGE_REGISTRY}" WORKLOAD_MANAGER_IMAGE="workloadmanager:${TAG}"
make docker-buildx-push-router IMAGE_REGISTRY="${IMAGE_REGISTRY}" ROUTER_IMAGE="agentcube-router:${TAG}"
make docker-buildx-push-picod IMAGE_REGISTRY="${IMAGE_REGISTRY}" PICOD_IMAGE="picod:${TAG}"
```

这部分在 main push 场景下是合理的，因为镜像可以发布为 `latest`。

但 Helm chart 打包也使用同一个 `TAG`：

```bash
yq e -i '.version = env(TAG) | .appVersion = env(TAG)' "${CHART_PATH}/Chart.yaml"
helm package "${CHART_PATH}" --version "${TAG}" --app-version "${TAG}"
```

这就把 Docker image tag 的语义错误复用到了 Helm chart version 上。

当前 chart 本身的默认版本是合法的：

```yaml
apiVersion: v1
name: agentcube
description: A Helm chart for AgentCube
version: 0.1.0
appVersion: "1.0.0"
```

但 CI 中被 `yq` 改成了：

```yaml
version: latest
appVersion: latest
```

`appVersion: latest` 本身不是关键问题；`version: latest` 才是失败点。

## 为什么会“一直报错”

从 workflow 设计看，这个错误在所有 `main` push 上都是必现的：

1. PR merge 到 `main`
2. 触发 `Build and Push Release Images`
3. `github.ref_type` 是 `branch`
4. workflow 设置 `TAG=latest`
5. Docker image 构建和 push 成功
6. Helm login 成功
7. `helm package --version latest` 失败
8. chart push 被跳过

所以它会表现为：

- PR checks 可以是绿的
- PR 合并后 `main` 上 release workflow 变红
- 镜像已经被推到 `latest`
- Helm chart 没有被成功打包/推送

> 分析：这类失败比普通测试失败更隐蔽，因为前面的 image push 已经成功，workflow 最后却红了。结果是发布状态可能变成“镜像更新了，chart 没更新”。

## 和 Day34 Push CI 的关系

Day34 的 push CI PR #414 改的是验证类 workflows，例如 build、lint、codegen、e2e、codespell、copyright、coverage 等，用来让 branch push 也跑和 PR 相同的验证流程。

这次失败的 workflow 是 `.github/workflows/build-push-release.yml`，它原本就监听：

```yaml
on:
  push:
    branches:
      - main
```

所以它不是 #414 新增 push trigger 后才开始跑的。历史 run 也证明它在 #414 合并前就一直失败。

> 注释：验证类 CI 和发布类 CI 要分开看。验证类 CI 失败通常说明代码或测试问题；发布类 CI 失败可能是 tag、权限、registry、artifact version、secret 或发布策略问题。

## 本地复现尝试

本地尝试直接用 Helm 复现：

```bash
set -e
if command -v helm >/dev/null 2>&1; then
  tmpdir=$(mktemp -d)
  cp -R manifests/charts/base "$tmpdir/base"
  helm version --short
  helm package "$tmpdir/base" --version latest --app-version latest
else
  echo "helm not installed"
fi
```

结果：

```text
helm not installed
```

本地没有 `helm`，所以没有继续做本地二次复现。这里的根因判断主要来自：

- GitHub Actions job 日志中的明确错误
- workflow 源码中 `TAG=latest` 到 `helm package --version "${TAG}"` 的直接链路
- Helm 官方 chart 文档对 chart version 的要求

## 官方规则依据

Helm 官方 chart 文档说明：

- 每个 chart 都必须有 version
- chart version 应遵循 SemVer
- 非 SemVer 名称会被拒绝
- `appVersion` 和 chart `version` 不是同一个东西，`appVersion` 不需要是 SemVer
- Helm 文档还说明，带前导 `v` 的版本会尝试被 coercion 成合法语义版本；这和 `latest` 这种完全非版本字符串不是同一类问题

参考：

- <https://helm.sh/docs/topics/charts/>

> 注释：`latest` 可以作为 image tag，但不能作为 chart `version`。初版修复曾考虑拆出 `CHART_VERSION`，但这会顺手改变 release tag 下的 chart package / OCI tag 命名；收敛后的 #416 不做这个迁移，只通过移除 `main` release publishing 来避免 `latest` 进入 chart version。

## 修复方向再次收敛：只修 main 误发布

用户复核后指出：不能把 Helm chart package / OCI tag 从 `vX.Y.Z` 改成 `X.Y.Z`。这会改变已经对外可见的 chart 包命名和安装方式，不应夹在一个 release workflow bugfix 里。

因此本次 PR #416 的收敛原则调整为：

1. Release artifacts 只由 release tag 触发。
2. `main` merge 只触发验证类 CI，不触发镜像和 Helm chart 发布。
3. tag release 下继续沿用当前已有命名约定：Docker image tag、Helm chart `version`、Helm chart `appVersion`、`.tgz` 文件名和 GHCR chart tag 都使用原始 Git tag，例如 `v1.2.3`。
4. 不在 #416 中引入 `CHART_VERSION=${TAG#v}`，也不把 `agentcube-v1.2.3.tgz` 改成 `agentcube-1.2.3.tgz`。

> 分析：这次失败的直接原因是 `main` push 下 `TAG=latest` 被写入 chart `version`，不是 tag release 下的 `vX.Y.Z` 已经被证明失败。当前 GHCR package 历史已经有 `v0.1.0` / `v0.1.0-rc.0` 这类 chart tag，说明 `v` 前缀至少是现有发布兼容面的一部分。是否要把 Helm chart 版本全面迁移到无 `v` SemVer，是独立的发布兼容性决策，需要文档、release note 和迁移说明，不属于 #416 的最小修复范围。

## 为什么只修一个点

这次 bugfix 应该只消除 `main` merge 触发 release artifact 发布的问题。

原 workflow 的失败链路是：

```text
main push -> TAG=latest -> helm package --version latest -> invalid chart.metadata.version
```

只要删除 `push.branches: [main]`，这个链路就不存在了。tag push 仍然设置：

```text
TAG=v1.2.3
```

并继续用于：

```text
Docker image tag: v1.2.3
Chart.yaml version: v1.2.3
Chart.yaml appVersion: v1.2.3
Chart package file: agentcube-v1.2.3.tgz
GHCR chart tag: charts/agentcube:v1.2.3
```

> 注释：如果社区后续确实需要持续发布开发版镜像，更合适的方式是单独设计 nightly / manual / scheduled dev-image workflow，或者明确只在特定分支发布。不要把 release artifact publish 和普通 main merge 绑定在一起。

## 最终实现记录

用户确认采用“main merge 不发布镜像”的方向后，先创建了 PR #416：

- Worktree: `/tmp/agentcube-release-chart-fix`
- Branch: `ci/fix-release-chart-version`
- Base: `upstream/main` at `7cfeb8c`
- Initial commit: `bfbcab9 ci: publish release artifacts only for tags`
- Changed file: `.github/workflows/build-push-release.yml`
- Fork branch: <https://github.com/ranxi2001/agentcube/tree/ci/fix-release-chart-version>
- Upstream PR: <https://github.com/volcano-sh/agentcube/pull/416>

初版 `bfbcab9` 同时做了两件事：删除 `main` trigger，并把 Helm chart version 从 `vX.Y.Z` 规范化为 `X.Y.Z`。用户复核后认为第二点会改变 chart package / GHCR chart tag，不希望包含在 #416 中。

本轮已按用户要求把 open PR 分支重写为单 commit，并 force-with-lease 推送：

- Worktree: `/tmp/agentcube-pr416-scope-fix`
- Local branch: `fix/pr416-preserve-chart-version`
- Final PR commit: `a6c4a82 ci: publish release artifacts only for tags`
- Push result: `bfbcab9...a6c4a82 HEAD -> ci/fix-release-chart-version (forced update)`
- PR body: 已通过 REST `PATCH /repos/volcano-sh/agentcube/issues/416` 更新为本节下方最终文稿
- 线上复核：2026-07-02 再次用 GitHub API / raw URL 确认 PR head 为 `a6c4a8231829921ee235f63a752fca4932be948a`，raw workflow 中只包含 `TAG=${RELEASE_TAG}`、`helm package --version "${TAG}"` 和 `helm push "agentcube-${TAG}.tgz"`，没有 `CHART_VERSION` 或 `${RELEASE_TAG#v}`。

收敛后的目标改动内容：

1. 从 `Build and Push Release Images` workflow 中移除 `push.branches: [main]`。
2. 保留 release tag 触发：`v*.*.*` 和 `v*.*.*-*`。
3. tag push 时设置 `TAG=${github.ref_name}`，例如 `v1.2.3`。
4. 不生成 `CHART_VERSION`。
5. Docker image tag、Helm `version`、Helm `appVersion` 和 chart package filename 都继续使用 `TAG`，也就是当前已有的 `vX.Y.Z` 命名。

核心 diff 逻辑：

```yaml
on:
  push:
    tags:
      - "v*.*.*"
      - "v*.*.*-*"
```

```bash
RELEASE_TAG="${{ github.ref_name }}"
echo "TAG=${RELEASE_TAG}" >> "$GITHUB_ENV"
```

```bash
helm package "${CHART_PATH}" --version "${TAG}" --app-version "${TAG}"
helm push "agentcube-${TAG}.tgz" "oci://ghcr.io/${REPOSITORY_OWNER_LOWER}/charts"
```

本轮本地验证结果：

```text
git -C /tmp/agentcube-pr416-scope-fix diff --check
PASS

git -C /tmp/agentcube-pr416-scope-fix diff upstream/main --check
PASS
```

Fork `main` 验证：

- 临时把旧方案 `dd7cb96` 推到 fork `main` 后，GitHub 创建了 10 个 push runs：9 个验证 workflow 加 `Build and Push Release Images`。9 个验证 workflow 已成功，release workflow 长时间停在 `Build and push images`，后续已取消，避免继续消耗资源。
- 把 tag-only trigger 方案 `bfbcab9` 推到 fork `main` 后，GitHub 只创建了 9 个验证 workflow，没有创建 `Build and Push Release Images` run。这直接验证了 main merge 不再触发镜像发布。最终单 commit `a6c4a82` 保留同一个 tag-only trigger 行为，只移除了 chart version normalization，因此该 fork-main trigger 验证结论仍然适用。
- `bfbcab9` 的 9/9 个验证 workflow 全部成功：Lint、Python SDK Tests、Copyright Check、Codespell、Python Lint、Codegen Check、Agentcube CI Workflow、Test Coverage、Agentcube E2E Tests。

当前工作区的 Git Bash 环境没有 `go`、`helm`、`actionlint`，因此本轮 scope correction 没有重新跑 actionlint 或 Helm package。初版 `bfbcab9` 的旧验证里包含 `actionlint`、`helm lint` 和无 `v` package simulation，但这些 package simulation 已不再代表最终期望行为，应从 PR body 中删除。

> 分析：收敛后的修复只解决一个问题：main merge 下不再发布镜像和 chart，从而避免 `TAG=latest` 进入 Helm chart `version`，也避免 release publish failure 给普通 merge commit 挂红色 X。tag release 的 chart 包命名保持历史兼容。

## 旧方案 PR 文稿草稿（已废弃）

> 更新：这一版文稿对应 tag-only 方案。2026-07-03 收到 reviewer 反馈后，该方案已废弃；最新推荐方案和新 PR 文稿见下文“2026-07-03 重新评估后的推荐方案”。

Upstream PR:

<https://github.com/volcano-sh/agentcube/pull/416>

Title:

```text
ci: publish release artifacts only for tags
```

Body:

````md
**What type of PR is this?**

/kind bug

**What this PR does / why we need it**:

The current `Build and Push Release Images` workflow runs on both `main` branch pushes and release tag pushes. On `main` pushes it sets `TAG=latest`, then reuses the same value as the Helm chart version. Docker image tags may use `latest`, but Helm chart `version` must be a valid SemVer value, so recent `main` merge commits repeatedly fail at `helm package --version latest`.

This PR changes the release publishing workflow to run only for release tags. A merge into `main` should run validation workflows such as build, lint, codegen, coverage, and e2e, but it should not publish release images or Helm charts for every merge commit. Keeping artifact publishing tag-driven avoids unnecessary runner and registry usage, and prevents unrelated `main` merge commits from showing a red failed release workflow after their PR checks have already passed.

For tag releases, this PR preserves the existing release artifact naming. A tag such as `v1.2.3` is still used as the Docker image tag, Helm chart `version`, Helm chart `appVersion`, chart package filename, and GHCR chart tag. A broader migration from `vX.Y.Z` chart tags to `X.Y.Z` chart tags is intentionally out of scope for this bugfix.

**Which issue(s) this PR fixes**:

Fixes #417

**Special notes for your reviewer**:

- Scope: only `.github/workflows/build-push-release.yml` is changed.
- `main` pushes no longer trigger release artifact publishing.
- Release tags matching `v*.*.*` and `v*.*.*-*` still build and push images and Helm charts using the existing `vX.Y.Z` tag naming.
- AI assistance: Used Codex to inspect the failing workflow, validate the GitHub Actions behavior on a fork, and draft this PR text. I reviewed and validated the changes.

Validation:

- `git diff --check`
- `git diff upstream/main --check`
- Earlier fork `main` push validation for the same tag-only trigger behavior: GitHub created the 9 validation workflows, did not create `Build and Push Release Images`, and all 9 validation workflows succeeded. The current PR commit keeps that trigger behavior and preserves the existing `vX.Y.Z` chart tag naming.

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
````

## 本次排查命令记录

查看目标 job 元数据：

```bash
gh api repos/volcano-sh/agentcube/actions/jobs/84745444791 \
  --jq '{id: .id, run_id: .run_id, name: .name, status: .status, conclusion: .conclusion, steps: [.steps[] | {name: .name, conclusion: .conclusion}]}'
```

查看 run 元数据：

```bash
gh run view 28582345874 \
  --repo volcano-sh/agentcube \
  --json name,event,headBranch,headSha,displayTitle,status,conclusion,createdAt,updatedAt,url,jobs
```

查看失败日志：

```bash
gh run view 28582345874 \
  --repo volcano-sh/agentcube \
  --job 84745444791 \
  --log-failed
```

查看 workflow 源码：

```bash
rg -n "Build and Push Release Images|Package Helm chart|helm package|CHART_PATH|TAG|appVersion|Chart.yaml|latest" \
  .github/workflows manifests/charts/base -S
```

同步 upstream main：

```bash
git fetch upstream main
```

查看当前 upstream workflow：

```bash
git show upstream/main:.github/workflows/build-push-release.yml | sed -n '1,110p'
```

查看最近失败 run：

```bash
gh run list \
  --repo volcano-sh/agentcube \
  --workflow build-push-release.yml \
  --limit 50 \
  --json databaseId,displayTitle,event,headBranch,headSha,conclusion,status,createdAt,url
```

## 卡点和注意事项

1. 本地没有 `helm`，所以没有直接在本机复现 `helm package --version latest` 的报错。
2. 旧 run 的 `gh run view --log-failed` 不是每次都能稳定吐出日志细节，但 run/job metadata 能稳定证明失败步骤都是 `Package Helm chart`。
3. 这个 workflow 有 `packages: write` 权限，修复前不应随意在 fork 或 upstream 上反复触发发布路径。
4. upstream PR #416 已 force-with-lease 更新到单 commit `a6c4a82`，PR body 已同步修正；后续等待 CI、maintainer review、`/lgtm`、`/approve` 和 tide。不要自动追加 commit 或评论，若 review 反馈需要改 release 策略，先确认 exact diff/comment。

## 2026-07-03 重新评估后的推荐方案

用户进一步指出：完全取消 `main` push 的 release artifact 发布并不理想。AgentCube 仍然可能需要持续发布 `latest` 镜像，方便用户、贡献者或集成测试直接体验主分支最新系统。

因此新的判断是：

1. 不应把 `main` push 发布路径直接删掉。
2. `latest` 仍然可以作为 Docker image tag。
3. `latest` 不能作为 Helm chart `version`。
4. 需要把 image tag、chart version、app version 拆成三个变量。
5. `main` push 的 chart version 使用固定特殊 SemVer：`0.0.0`。

> 分析：这次失败不是“不能发布 latest 镜像”，而是“不能把 latest 镜像标签复用为 Helm chart version”。修复点应该落在元数据拆分，而不是直接移除 main 发布能力。

### Karmada 参考

Karmada 的 `dockerhub-latest-chart.yml` 保留了 master 分支 push 后发布 latest chart 的路径，但它没有使用 `latest` 作为 chart version，而是在 package 和 push 时设置：

```yaml
env:
  VERSION: 0.0.0
```

同时它通过 job-level `if` 限制只有官方仓库 master 分支执行，避免 fork 缺少 secret 或无意义消耗 Actions 时间。

参考：

- <https://github.com/karmada-io/karmada/blob/master/.github/workflows/dockerhub-latest-chart.yml>

> 注释：Karmada 的设计说明了一个关键点：所谓 latest chart 不一定要在 Helm `version` 字段里写 `latest`。可以用一个固定特殊 SemVer 表示“开发版/主分支版”，再通过发布通道或文档说明它代表最新构建。

### 为什么不用 run number

曾考虑过用：

```text
0.0.0-main.<github.run_number>
```

它的优点是每次 main 构建都有唯一 chart version，便于追踪具体 run。

但用户复核后指出这会造成不必要的 registry 侧版本堆积。这个判断是合理的：

- 它不会污染 git 仓库。
- 但它会让 GHCR chart package 中持续出现 `0.0.0-main.N` 这类临时版本。
- 这些版本不是正式 release，也不是用户真正需要长期引用的版本。
- 对“latest 体验入口”来说，固定 `0.0.0` 已经足够。

> 分析：`run_number` 适合 nightly snapshot 或需要追踪每次构建产物的场景。当前目标只是让 main/latest 发布不失败，并提供一个可复用的 latest chart 入口，所以固定 `0.0.0` 更干净。

### 推荐 workflow 语义

新的 release metadata 语义应为：

| 场景 | Docker image tag | Helm chart version | Helm appVersion | 说明 |
| --- | --- | --- | --- | --- |
| `main` push | `latest` | `0.0.0` | `latest` | 主分支开发版/latest 入口 |
| release tag `v1.2.3` | `v1.2.3` | `v1.2.3` | `v1.2.3` | 保留现有 tag release 命名 |
| pre-release tag `v1.2.3-alpha` | `v1.2.3-alpha` | `v1.2.3-alpha` | `v1.2.3-alpha` | 保留现有 pre-release 命名 |

核心实现逻辑：

```bash
if [[ "${{ github.ref_type }}" == "tag" ]]; then
  RELEASE_TAG="${{ github.ref_name }}"
  echo "TAG=${RELEASE_TAG}" >> "$GITHUB_ENV"
  echo "CHART_VERSION=${RELEASE_TAG}" >> "$GITHUB_ENV"
  echo "APP_VERSION=${RELEASE_TAG}" >> "$GITHUB_ENV"
else
  echo "TAG=latest" >> "$GITHUB_ENV"
  echo "CHART_VERSION=0.0.0" >> "$GITHUB_ENV"
  echo "APP_VERSION=latest" >> "$GITHUB_ENV"
fi
```

Helm package / push 使用 `CHART_VERSION`：

```bash
yq e -i '.version = env(CHART_VERSION) | .appVersion = env(APP_VERSION)' "${CHART_PATH}/Chart.yaml"
helm package "${CHART_PATH}" --version "${CHART_VERSION}" --app-version "${APP_VERSION}"
helm push "agentcube-${CHART_VERSION}.tgz" "oci://ghcr.io/${REPOSITORY_OWNER_LOWER}/charts"
```

镜像仍使用 `TAG`：

```bash
make docker-buildx-push IMAGE_REGISTRY="${IMAGE_REGISTRY}" WORKLOAD_MANAGER_IMAGE="workloadmanager:${TAG}"
make docker-buildx-push-router IMAGE_REGISTRY="${IMAGE_REGISTRY}" ROUTER_IMAGE="agentcube-router:${TAG}"
make docker-buildx-push-picod IMAGE_REGISTRY="${IMAGE_REGISTRY}" PICOD_IMAGE="picod:${TAG}"
```

> 注释：这里继续保留 tag release 下的 `vX.Y.Z` chart version / package / OCI tag 命名，因为用户已经明确不希望 #416 顺手把 release chart 从 `vX.Y.Z` 改成 `X.Y.Z`。是否要做 chart version 规范化，是另一个发布兼容性问题。

### 新 PR 文稿方向

旧标题：

```text
ci: publish release artifacts only for tags
```

已经不适合新方案，因为新方案会保留 `main` push 发布。

推荐标题：

```text
ci: use semver chart version for latest releases
```

推荐 PR body：

````md
**What type of PR is this?**

/kind bug

**What this PR does / why we need it**:

The `Build and Push Release Images` workflow publishes artifacts for both `main` branch pushes and release tag pushes. On `main` pushes it uses `TAG=latest`. That value is valid for Docker image tags, but the workflow also reused it as the Helm chart `version`, and Helm chart versions must be valid SemVer values. As a result, recent `main` merge commits repeatedly failed during chart packaging with `chart.metadata.version "latest" is invalid`.

This PR keeps the `main` push publishing behavior so users can continue to consume latest images from the main branch, but separates image tags from Helm chart versions. For `main` pushes, Docker images still use `latest`, while the Helm chart uses the fixed development version `0.0.0` and `appVersion=latest`. For release tags, the workflow preserves the existing `vX.Y.Z` artifact naming behavior.

**Which issue(s) this PR fixes**:

Fixes #417

**Special notes for your reviewer**:

- Scope: only `.github/workflows/build-push-release.yml` is changed.
- `main` pushes continue to publish latest images.
- `main` pushes now package/push the Helm chart as version `0.0.0` instead of `latest`.
- Release tags matching `v*.*.*` and `v*.*.*-*` keep the existing `vX.Y.Z` image tag, chart version, appVersion, package filename, and OCI chart tag behavior.
- This follows the same idea as Karmada's latest chart workflow, where the latest chart is represented by a special SemVer value instead of `latest`.
- AI assistance: Used Codex to inspect the failing workflow, compare the Karmada latest chart workflow, and draft this PR text. I reviewed and validated the changes.

Validation:

- `git diff upstream/main --check`
- Local shell simulation of the release metadata branch logic:
  - `main` push: `TAG=latest`, `CHART_VERSION=0.0.0`, `APP_VERSION=latest`
  - `v1.2.3` tag: `TAG=v1.2.3`, `CHART_VERSION=v1.2.3`, `APP_VERSION=v1.2.3`
  - `v1.2.3-alpha` tag: `TAG=v1.2.3-alpha`, `CHART_VERSION=v1.2.3-alpha`, `APP_VERSION=v1.2.3-alpha`

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
````

### 当前本地状态

已在新的干净临时工作树中准备本地单 commit，但尚未推送 open PR #416：

- Worktree: `/tmp/agentcube-pr416-final`
- Local branch: `ci/fix-release-chart-version-final`
- Base head: `upstream/main` at `7cfeb8c`
- Local commit: `427e618 ci: use valid chart version for latest releases`
- Changed file: `.github/workflows/build-push-release.yml`
- Current decision: do not push until the exact diff, PR body, and reviewer reply are confirmed, because pushing this branch 会更新已经打开的 upstream PR #416。

当前验证：

```text
git diff upstream/main --check
PASS

actionlint -ignore 'too old to run on GitHub Actions' .github/workflows/build-push-release.yml
PASS

helm lint manifests/charts/base
PASS

helm package simulation for main/latest:
PASS: agentcube-0.0.0.tgz

helm package simulation for release tag v1.2.3:
PASS: agentcube-v1.2.3.tgz

helm package simulation for pre-release tag v1.2.3-alpha:
PASS: agentcube-v1.2.3-alpha.tgz
```

Fork `main` 真实 workflow 验证：

- Repo: `ranxi2001/agentcube`
- Run: <https://github.com/ranxi2001/agentcube/actions/runs/28633043101>
- Job: <https://github.com/ranxi2001/agentcube/actions/runs/28633043101/job/84913711568>
- Event: `push`
- Branch: `main`
- Head SHA: `427e618eaec0749736a430ce8adcf7f9d075b783`
- Result: success
- Job duration: `2026-07-03T01:47:11Z` -> `2026-07-03T02:12:20Z`, about 25m09s

关键日志：

```text
TAG: latest
CHART_VERSION: 0.0.0
APP_VERSION: latest
Successfully packaged chart and saved it to: /home/runner/work/agentcube/agentcube/agentcube-0.0.0.tgz
Pushed: ghcr.io/ranxi2001/charts/agentcube:0.0.0
```

> 分析：这次验证说明 GHCR 接受固定 `0.0.0` 作为 Helm chart OCI tag，且 `latest` image 发布没有被破坏。它还没有额外验证“重复 push 同一个 `0.0.0` tag 是否总是可覆盖”，但不建议为了这个再主动跑一次完整 release workflow，因为每次都会支付 25 分钟级 multi-arch image build 成本。如果后续 main push 重复失败，再考虑 `0.0.0-main.N` 等 snapshot version 方案。

### Reviewer 反馈与回复草稿

Reviewer `zhzhuang-zju` 在 #416 中指出：

```text
We should not remove this trigger condition, because the latest image still needs to be uploaded.
```

这条反馈确认了旧 tag-only 方案的问题：它修掉了红色 X，但也误删了主分支 latest image 发布能力。

建议回复：

```md
Thanks, agreed. I updated the approach to keep the `main` push trigger and continue publishing `latest` images.

The fix now separates the Docker image tag from the Helm chart metadata. On `main` pushes, images still use `TAG=latest`, while the chart uses `CHART_VERSION=0.0.0` and `APP_VERSION=latest`. On release tags, the workflow keeps the existing `vX.Y.Z` values for image tags, chart version, appVersion, package filename, and OCI chart tag.

This avoids `helm package --version latest` without removing latest image publishing.
```

### 为什么 Build and Push Release Images 看起来卡住

针对旧失败 job：

- Job: <https://github.com/volcano-sh/agentcube/actions/runs/28582345874/job/84745444791>
- Run: <https://github.com/volcano-sh/agentcube/actions/runs/28582345874>
- Head SHA: `7cfeb8c222f82ccbacc3048a6fd66d5bc255fb9f`

GitHub Actions API 显示，这个 job 总耗时约 27 分 19 秒：

| Step | Start | End | Duration | Result |
| --- | --- | --- | ---: | --- |
| `Build and push images` | 10:12:20 UTC | 10:39:20 UTC | 27m00s | success |
| `Package Helm chart` | 10:39:20 UTC | 10:39:20 UTC | <1s | failure |

也就是说，job 不是卡在 Helm chart 打包；Helm 失败是最后瞬间发生的。真正耗时在前面的三镜像多架构 build/push。

进一步拆日志：

| Image | Approx time | Key slow point |
| --- | ---: | --- |
| `workloadmanager:latest` | ~24m | `linux/arm64` 的 `go build ./cmd/workload-manager` 用了 `1415.0s` |
| `agentcube-router:latest` | ~42s | 大量复用前一个 buildx 缓存，`linux/arm64` `go build ./cmd/router` 约 `32.9s` |
| `picod:latest` | ~2m18s | `linux/arm64` Ubuntu runtime `apt-get update && apt-get install -y python3` 约 `127.0s` |

新的 fork 验证 run `28633043101` 也呈现同样瓶颈，但这次最终成功：

| Step / image | Duration | Result / observation |
| --- | ---: | --- |
| `Build and push images` | 1487.1s, about 24m47s | success |
| `workloadmanager:latest` | about 21m56s | `linux/arm64 go build ./cmd/workload-manager` took `1291.4s`; `linux/amd64` took `173.2s` |
| `agentcube-router:latest` | about 39s | `linux/arm64 go build ./cmd/router` took `30.0s` |
| `picod:latest` | about 2m12s | `linux/arm64 apt-get update && apt-get install -y python3` took `120.0s`; `linux/arm64 go build ./cmd/picod` took `8.7s` |
| `Package Helm chart` | 0.1s | success, generated `agentcube-0.0.0.tgz` |
| `Push Helm chart` | 2.4s | success, pushed `ghcr.io/ranxi2001/charts/agentcube:0.0.0` |

核心慢点是第一个镜像的 arm64 Go 编译。当前 Makefile 三个 push target 都使用：

```bash
docker buildx build --platform linux/amd64,linux/arm64 --push .
```

而 Dockerfile 的 builder stage 写法是：

```dockerfile
FROM golang:1.26.4-alpine AS builder
ARG TARGETOS=linux
ARG TARGETARCH
RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} go build ...
```

在 GitHub 的 `ubuntu-latest` x86 runner 上，`linux/arm64` platform 的 builder stage 会通过 buildx/QEMU 跑 arm64 环境。对 Go 编译这种 CPU 密集型步骤来说，QEMU emulation 会非常慢，所以 `workloadmanager` 的 arm64 `go build` 被拉长到二十多分钟。

> 分析：这解释了为什么 fork `main` 验证同样会“看起来卡住”。它不是新 chart version 方案导致的，而是原 release workflow 本来就要先构建并推送三个 multi-arch 镜像。只要保留 latest image 发布，这个路径就会先支付 multi-arch build 成本。

可以考虑的后续优化方向：

1. 让 Go builder stage 使用 native build platform：

   ```dockerfile
   FROM --platform=$BUILDPLATFORM golang:1.26.4-alpine AS builder
   ARG TARGETOS
   ARG TARGETARCH
   RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} go build ...
   ```

   这样 Go 编译在 x86 runner 上原生执行，只输出 arm64 二进制，避免用 QEMU 跑 Go compiler。

2. 增加跨 workflow 的 buildx cache，例如 GitHub Actions cache 或 registry cache，避免每次 main push 都冷构建第一个镜像。

3. 如果社区接受成本优化，可以讨论 `main` push 只发布 `latest` amd64 镜像，release tag 再发布 multi-arch 镜像。不过这会改变 latest image 的平台覆盖，需要 maintainer 明确同意。

4. `picod` 的 runtime stage 可以考虑预装 Python 的基础镜像或更轻量的 package 策略，减少 arm64 Ubuntu `apt-get install python3` 的 2 分钟级开销。

> 注释：这些优化不应混入当前 #416。#416 的最小修复目标仍是让 Helm chart version 合法，同时保留 latest image 发布。buildx 加速可以作为后续单独 CI 性能 PR。
