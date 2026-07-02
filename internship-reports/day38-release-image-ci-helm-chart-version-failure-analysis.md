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

参考：

- <https://helm.sh/docs/topics/charts/>

> 注释：所以修复方向不是简单把 `appVersion` 改掉，而是要拆开 `IMAGE_TAG` 和 `CHART_VERSION`。`latest` 可以继续用于 image tag，但不能用于 chart version。

## 修复方案对比

### 方案 A：main push 只推 latest 镜像，Helm chart 只在 tag release 时打包发布

这是最保守、最清晰的方案。

思路：

- `main` push：构建并推送 `latest` 镜像
- `tag` push：构建并推送版本镜像，同时打包并推送 Helm chart
- Helm chart 相关步骤加 `if: github.ref_type == 'tag'`
- tag 场景使用合法的 chart version

示例逻辑：

```bash
if [[ "${{ github.ref_type }}" == "tag" ]]; then
  IMAGE_TAG="${{ github.ref_name }}"
  CHART_VERSION="${IMAGE_TAG#v}"
else
  IMAGE_TAG="latest"
fi
```

Helm 步骤只在 tag 时执行：

```yaml
- name: Login Helm to GitHub Container Registry
  if: github.ref_type == 'tag'

- name: Package Helm chart
  if: github.ref_type == 'tag'

- name: Push Helm chart
  if: github.ref_type == 'tag'
```

优点：

- 语义最干净
- 避免 main 上每次文档/测试合并都发布 chart
- 避免 `latest` chart version 问题
- 符合 release artifact 通常随 tag 发布的习惯

风险：

- 如果维护者期望 main 分支也持续发布开发版 chart，这个方案会改变现有意图。

### 方案 B：main push 也发布 dev chart，但 chart version 必须使用合法 SemVer

如果社区希望 main 分支每次合并都能推一个开发版 chart，可以保留 main chart 发布，但必须给它一个 SemVer 版本。

示例：

```bash
if [[ "${{ github.ref_type }}" == "tag" ]]; then
  IMAGE_TAG="${{ github.ref_name }}"
  CHART_VERSION="${IMAGE_TAG#v}"
  APP_VERSION="${IMAGE_TAG}"
else
  IMAGE_TAG="latest"
  CHART_VERSION="0.0.0-main.${{ github.run_number }}"
  APP_VERSION="${{ github.sha }}"
fi
```

然后：

```bash
yq e -i '.version = env(CHART_VERSION) | .appVersion = env(APP_VERSION)' "${CHART_PATH}/Chart.yaml"
helm package "${CHART_PATH}" --version "${CHART_VERSION}" --app-version "${APP_VERSION}"
helm push "agentcube-${CHART_VERSION}.tgz" "oci://ghcr.io/${REPOSITORY_OWNER_LOWER}/charts"
```

优点：

- main 分支仍能持续发布 chart
- 每次 run 的 chart version 唯一
- 不再使用非法 `latest`

风险：

- 会产生大量开发版 chart 包
- 用户可能不清楚该安装哪个 dev chart
- 需要明确 chart version 与 image tag 的对应关系

### 方案 C：把 image 发布和 chart 发布拆成两个 workflow

更长期的整理方案：

- `build-push-release.yml`：只负责镜像
- `helm-chart-release.yml`：只负责 chart
- chart release 只监听 tag，或者使用独立的 dev chart 版本策略

优点：

- release artifact 边界清晰
- chart 失败不会让 image release 语义混乱
- 更容易给 chart 加 `helm lint`、`helm template`、OCI push 验证

风险：

- 改动比方案 A 大
- 需要维护者确认发布策略

## 推荐下一步

我建议优先做一个小 PR，采用方案 A：

1. 保留 main push 发布 `latest` images 的能力
2. Helm chart login/package/push 只在 tag push 时执行
3. 拆出 `IMAGE_TAG` 和 `CHART_VERSION`
4. tag 为 `v1.2.3` 时，镜像 tag 可以继续用 `v1.2.3`，chart version 使用 `1.2.3`
5. 在 PR body 中说明这不是 #415 或 #414 引入的问题，而是 release workflow 长期失败

推荐 PR 标题：

```text
ci: avoid packaging Helm chart with latest version
```

推荐最小验证：

```bash
git diff --check
```

如果本地安装 Helm，还可以补：

```bash
helm lint manifests/charts/base
helm package manifests/charts/base --version 0.0.0-main.1 --app-version latest
helm package manifests/charts/base --version 1.2.3 --app-version v1.2.3
```

> 分析：这类修复适合单独开 PR，不应该混进 #414 push CI 或 #415 docs/proposals。它属于 release workflow bugfix，reviewer 关注点是发布语义，不是普通 CI 验证语义。

## 最小修复实现记录

用户确认可以尝试最小修复后，已在干净 worktree 中实现并验证：

- Worktree: `/tmp/agentcube-release-chart-fix`
- Branch: `ci/fix-release-chart-version`
- Base: `upstream/main` at `7cfeb8c`
- Commit: `dd7cb96 ci: avoid packaging Helm chart with latest version`
- Changed file: `.github/workflows/build-push-release.yml`
- Fork branch: <https://github.com/ranxi2001/agentcube/tree/ci/fix-release-chart-version>
- Compare view: <https://github.com/volcano-sh/agentcube/compare/main...ranxi2001:agentcube:ci/fix-release-chart-version>

最小改动内容：

1. tag push 时保留 Docker image tag 为原始 tag，例如 `v1.2.3`
2. 额外生成 `CHART_VERSION=${RELEASE_TAG#v}`，例如 `v1.2.3 -> 1.2.3`
3. main branch push 时仍设置 `TAG=latest`，继续发布 latest 镜像
4. Helm registry login / chart package / chart push 三个步骤只在 `github.ref_type == 'tag'` 时执行
5. chart package 使用 `CHART_VERSION` 作为 Helm chart version，使用 `TAG` 作为 appVersion 和 image tag

核心 diff 逻辑：

```yaml
if [[ "${{ github.ref_type }}" == "tag" ]]; then
  RELEASE_TAG="${{ github.ref_name }}"
  echo "TAG=${RELEASE_TAG}" >> "$GITHUB_ENV"
  echo "CHART_VERSION=${RELEASE_TAG#v}" >> "$GITHUB_ENV"
else
  echo "TAG=latest" >> "$GITHUB_ENV"
fi
```

```yaml
- name: Package Helm chart
  if: github.ref_type == 'tag'
```

```bash
helm package "${CHART_PATH}" --version "${CHART_VERSION}" --app-version "${TAG}"
helm push "agentcube-${CHART_VERSION}.tgz" "oci://ghcr.io/${REPOSITORY_OWNER_LOWER}/charts"
```

本地验证结果：

```text
git diff --check upstream/main...HEAD
PASS

actionlint -ignore 'too old to run on GitHub Actions' .github/workflows/build-push-release.yml
PASS

helm lint manifests/charts/base
1 chart(s) linted, 0 chart(s) failed

TAG=v1.2.3 CHART_VERSION=1.2.3 helm package ...
v1.2.3 -> agentcube-1.2.3.tgz

TAG=v1.2.3-alpha CHART_VERSION=1.2.3-alpha helm package ...
v1.2.3-alpha -> agentcube-1.2.3-alpha.tgz
```

`actionlint` 原始运行会提示当前 workflow 已存在的 `actions/checkout@v3`、`actions/setup-go@v4`、`docker/setup-buildx-action@v2` 版本过旧问题。该提示在 `upstream/main` 原文件上同样存在，不是本次修复引入；为了保持最小 PR，本次没有顺手升级 action 版本。

> 分析：这个修复让 main merge 后不再尝试用 `latest` 发布 Helm chart，因此能解决当前反复失败的 release CI；tag release 仍会发布镜像和 chart，并保证 chart version 是合法 SemVer。

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
4. 如果要开 upstream PR，需要先确认社区期望：main 是否应该发布 Helm chart，还是 chart 只在 tag release 发布。
