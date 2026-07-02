# Day 38: Release Image CI 中 Helm Chart Version 失败分析

日期：2026-07-02

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

本轮已在本地准备 scope correction，尚未推送到 open PR：

- Worktree: `/tmp/agentcube-pr416-scope-fix`
- Local branch: `fix/pr416-preserve-chart-version`
- Candidate commit: `c799198 ci: preserve release chart version tags`
- Commit status: local only, not pushed

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
- 把 tag-only trigger 方案 `bfbcab9` 推到 fork `main` 后，GitHub 只创建了 9 个验证 workflow，没有创建 `Build and Push Release Images` run。这直接验证了 main merge 不再触发镜像发布。候选修正 `c799198` 不改 trigger，只回退 chart version normalization，因此该 fork-main trigger 验证结论仍然适用。
- `bfbcab9` 的 9/9 个验证 workflow 全部成功：Lint、Python SDK Tests、Copyright Check、Codespell、Python Lint、Codegen Check、Agentcube CI Workflow、Test Coverage、Agentcube E2E Tests。

当前工作区的 Git Bash 环境没有 `go`、`helm`、`actionlint`，因此本轮 scope correction 没有重新跑 actionlint 或 Helm package。初版 `bfbcab9` 的旧验证里包含 `actionlint`、`helm lint` 和无 `v` package simulation，但这些 package simulation 已不再代表最终期望行为，应从 PR body 中删除。

> 分析：收敛后的修复只解决一个问题：main merge 下不再发布镜像和 chart，从而避免 `TAG=latest` 进入 Helm chart `version`，也避免 release publish failure 给普通 merge commit 挂红色 X。tag release 的 chart 包命名保持历史兼容。

## PR 文稿草稿

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
- Fork `main` push validation for commit `bfbcab9`: GitHub created the 9 validation workflows, did not create `Build and Push Release Images`, and all 9 validation workflows succeeded. The follow-up scope correction only preserves existing chart tag naming and does not change the tag-only trigger behavior.

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
4. 已创建 upstream PR #416，并在本地准备了候选修正 commit `c799198`；不要自动 push 到 open PR，也不要自动评论。若要更新 PR，先让用户确认 exact diff、PR body 和是否直接 push `c799198`。
