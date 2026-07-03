# Day 39: Karmada Image Build 方式与 AgentCube Buildx 性能优化机会

日期：2026-07-03

## 结论先行

Karmada 的多架构镜像发布不是把 Go 编译放在 Dockerfile 的 `linux/arm64` builder stage 里跑，而是先在 GitHub x86 runner 宿主机上用 Go 原生交叉编译生成 `linux/amd64` 和 `linux/arm64` 二进制，然后再用 buildx 把这些预编译二进制复制进对应平台的 runtime image。

这和 AgentCube 当前做法差别很大：

- AgentCube 当前：`docker buildx build --platform linux/amd64,linux/arm64` 进入 Dockerfile builder stage 后，在 arm64 builder 环境里跑 `go build`。
- Karmada 当前：`make target GOOS=linux GOARCH=amd64` 和 `GOARCH=arm64` 先完成 Go cross compile，buildx 只负责多平台镜像组装。

> 分析：Day38 里看到 AgentCube `workloadmanager` 的 `linux/arm64 go build` 用了 `1415.0s`，根因就是 GitHub x86 runner 上通过 buildx/QEMU 运行 arm64 Go compiler。Karmada 避开了这个慢点，所以它的模式对 AgentCube 有直接参考价值。

## 本轮问题背景

PR #416 的主问题是 release workflow 在 `main` push 上把 `TAG=latest` 同时用于 Docker image tag 和 Helm chart version，导致：

```text
Error: validation: chart.metadata.version "latest" is invalid
```

但在验证 `main` push latest image + chart `0.0.0` 的过程中，又看到 `Build and Push Release Images` 长时间停在 `build-and-push` job。

旧 upstream job 的时间拆解已经说明：

| Step | Start | End | Duration | Result |
| --- | --- | --- | ---: | --- |
| `Build and push images` | 10:12:20 UTC | 10:39:20 UTC | 27m00s | success |
| `Package Helm chart` | 10:39:20 UTC | 10:39:20 UTC | <1s | failure |

真正慢点不是 Helm，而是 multi-arch image build。

进一步看日志：

| Image | Approx time | Key slow point |
| --- | ---: | --- |
| `workloadmanager:latest` | ~24m | `linux/arm64` 的 `go build ./cmd/workload-manager` 用了 `1415.0s` |
| `agentcube-router:latest` | ~42s | 复用前一个 buildx cache，`linux/arm64 go build ./cmd/router` 约 `32.9s` |
| `picod:latest` | ~2m18s | `linux/arm64` Ubuntu runtime `apt-get update && apt-get install -y python3` 约 `127.0s` |

> 注释：这里的 `linux/arm64` 不是说 GitHub runner 真的是 arm64，而是 buildx 在 x86 runner 上模拟 arm64 构建环境。QEMU 对 I/O 或简单 shell 命令还能接受，但对 Go 编译这种 CPU 密集型工作会明显变慢。

## Karmada latest image workflow

Karmada 的 latest image workflow 位于：

- <https://github.com/karmada-io/karmada/blob/master/.github/workflows/dockerhub-latest-image.yml>

关键结构：

```yaml
on:
  push:
    branches:
      - master

jobs:
  publish-image-to-dockerhub:
    if: ${{ github.repository == 'karmada-io/karmada' && github.ref == 'refs/heads/master' }}
    strategy:
      matrix:
        target:
          - karmada-controller-manager
          - karmada-scheduler
          - karmada-descheduler
          - karmada-webhook
          - karmada-agent
          - karmada-scheduler-estimator
          - karmada-interpreter-webhook-example
          - karmada-aggregated-apiserver
          - karmada-search
          - karmada-operator
          - karmada-metrics-adapter
    steps:
      - name: build and publish images
        run: make mp-image-${{ matrix.target }}
```

它有几个关键点：

1. 只在官方仓库 master 执行。
2. 使用 matrix 并行构建多个组件镜像。
3. 每个 matrix job 只构建一个 target。
4. workflow 安装 QEMU 和 Buildx，但 Go 编译并不主要依赖 QEMU。
5. `latest` image 和 release image 使用类似的 `make mp-image-*` 路径。

> 注释：Karmada 仍然安装 QEMU，是因为 buildx 组装多平台 runtime image 时可能需要执行目标平台的 Dockerfile `RUN` 命令。但它没有把最重的 Go 编译放进 arm64 Dockerfile builder stage，这是关键差异。

## Karmada Makefile 如何 build image

Karmada Makefile 位于：

- <https://github.com/karmada-io/karmada/blob/master/Makefile>

多平台镜像 target 的核心逻辑：

```makefile
MP_TARGET=$(addprefix mp-image-, $(TARGETS))
.PHONY: $(MP_TARGET)
$(MP_TARGET):
	set -e;\
	target=$$(echo $(subst mp-image-,,$@));\
	make $$target GOOS=linux GOARCH=amd64;\
	make $$target GOOS=linux GOARCH=arm64;\
	VERSION=$(VERSION) REGISTRY=$(REGISTRY) \
		OUTPUT_TYPE=registry \
		BUILD_PLATFORMS=linux/amd64,linux/arm64 \
		hack/docker.sh $$target
```

这段流程分成两步：

1. 先构建二进制：
   - `make target GOOS=linux GOARCH=amd64`
   - `make target GOOS=linux GOARCH=arm64`
2. 再构建镜像：
   - `BUILD_PLATFORMS=linux/amd64,linux/arm64 hack/docker.sh target`

也就是说，多平台镜像构建前，两个平台的 Go 二进制已经存在。

> 分析：Go 对 `CGO_ENABLED=0` 的二进制有成熟的交叉编译能力。对于这类纯 Go 控制面组件，在 x86 runner 上直接 `GOARCH=arm64 go build` 通常远快于在 QEMU arm64 环境里运行 Go compiler。

## Karmada build.sh 如何生成二进制

Karmada 的二进制构建脚本：

- <https://github.com/karmada-io/karmada/blob/master/hack/build.sh>

关键逻辑：

```bash
CGO_ENABLED=0 GOOS=${os} GOARCH=${arch} go build \
    -ldflags "${LDFLAGS:-}" \
    -o "_output/bin/${platform}/$target" \
    "${gopkg}"
```

输出路径形如：

```text
_output/bin/linux/amd64/karmada-controller-manager
_output/bin/linux/arm64/karmada-controller-manager
```

> 注释：这一步是在 GitHub runner 宿主环境执行的 Go cross compile，不是在 Dockerfile 的 arm64 builder stage 里执行。因此它绕开了 AgentCube 当前日志里最慢的 `linux/arm64 go build` QEMU 路径。

## Karmada docker.sh 如何组装镜像

Karmada 的 Docker 构建脚本：

- <https://github.com/karmada-io/karmada/blob/master/hack/docker.sh>

关键逻辑：

```bash
docker buildx build --output=type="${output_type}" \
        --platform "${platforms}" \
        --build-arg BINARY="${target}" \
        --tag "${image_name}" \
        --file "${REPO_ROOT}/cluster/images/buildx.Dockerfile" \
        "${REPO_ROOT}/_output/bin"
```

它的 build context 是：

```text
_output/bin
```

不是整个源码仓库。

对应多平台 Dockerfile：

- <https://github.com/karmada-io/karmada/blob/master/cluster/images/buildx.Dockerfile>

核心内容：

```dockerfile
FROM alpine:3.24.1

ARG BINARY
ARG TARGETPLATFORM

RUN apk add --no-cache ca-certificates
RUN apk add --no-cache tzdata

COPY ${TARGETPLATFORM}/${BINARY} /bin/${BINARY}
```

这里没有 `go build`，只有 runtime layer 和 `COPY`。

> 分析：这就是 Karmada 快的本质。多架构镜像构建仍然存在，但镜像构建阶段不再负责编译源码，只把预编译的 `linux/amd64` / `linux/arm64` 二进制放进对应平台镜像。

## AgentCube 当前做法

AgentCube Makefile 当前在三个 target 中直接调用 buildx：

```makefile
docker buildx build -f docker/Dockerfile --platform linux/amd64,linux/arm64 \
  -t $(IMAGE_REGISTRY)/$(WORKLOAD_MANAGER_IMAGE) \
  --push .
```

Router 和 PicoD 也是同样方式：

```makefile
docker buildx build -f docker/Dockerfile.router --platform linux/amd64,linux/arm64 ...
docker buildx build -f docker/Dockerfile.picod --platform linux/amd64,linux/arm64 ...
```

对应 Dockerfile 在 builder stage 中编译：

```dockerfile
FROM golang:1.26.4-alpine AS builder

ARG TARGETOS=linux
ARG TARGETARCH

RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -ldflags="-s -w" -o workloadmanager ./cmd/workload-manager
```

这会导致：

```text
buildx platform = linux/arm64
  -> builder stage = arm64
  -> go compiler = arm64 process
  -> GitHub x86 runner 通过 QEMU 执行 arm64 Go compiler
  -> workloadmanager go build 用 1415s
```

> 注释：`TARGETOS` / `TARGETARCH` 本身不是问题。问题是 builder stage 的平台也跟着 target platform 走了，导致 Go compiler 自己也跑在模拟的 arm64 环境里。

## 两个项目 build 模型对比

| 维度 | Karmada | AgentCube 当前 |
| --- | --- | --- |
| latest image 触发 | master push，官方仓库 guard | main push |
| 多镜像构建 | matrix 并行，每个 target 一个 job | 单 job 顺序构建 3 个镜像 |
| Go 编译位置 | Docker 外，宿主 runner 上交叉编译 | Dockerfile builder stage 内 |
| arm64 Go 编译 | `GOARCH=arm64 go build` 原生交叉编译 | QEMU arm64 builder stage 中执行 Go compiler |
| Docker build context | `_output/bin` | repo 根目录 |
| multi-arch Dockerfile | runtime-only，COPY prebuilt binary | builder + runtime multi-stage |
| 主要慢点 | runtime layer / push / 每 target 编译 | 第一个 arm64 Go build 极慢 |

## AgentCube 可以怎么优化

### 方案 A：最小 PR，只修 Dockerfile builder platform

最小可行优化是让 builder stage 总是在 GitHub runner 的 native platform 上运行：

```dockerfile
FROM --platform=$BUILDPLATFORM golang:1.26.4-alpine AS builder

ARG TARGETOS=linux
ARG TARGETARCH

RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -ldflags="-s -w" -o workloadmanager ./cmd/workload-manager
```

对 Router 和 PicoD 同理。

这样 buildx 仍然会为 `linux/amd64` 和 `linux/arm64` 生成不同镜像，但 Go compiler 会运行在 x86 runner 原生环境中，只通过 `GOARCH=arm64` 输出 arm64 二进制。

优点：

- 改动小，预计只改 3 个 Dockerfile。
- 不需要新增脚本或大改 Makefile。
- 保持现有 `make docker-buildx-push*` 接口。
- 不改变镜像 tag、workflow、registry、chart 逻辑。
- 可以作为独立性能优化 PR，不和 #416 混在一起。

风险：

- 需要确认三个二进制都是 `CGO_ENABLED=0` 可交叉编译。
- 需要验证 `linux/amd64` 和 `linux/arm64` 镜像内二进制架构正确。
- 如果 Dockerfile 中未来加入 target-platform 依赖的 build step，要注意 builder platform 和 target platform 的区别。

> 分析：这是最适合第一版 upstream PR 的方案。它只解决明确证据指向的问题：避免在 QEMU arm64 环境里跑 Go compiler。

### 方案 B：Karmada-style 预编译二进制 + runtime-only Dockerfile

更彻底的方案是模仿 Karmada：

1. 新增或改造 Makefile：
   - `make workloadmanager GOOS=linux GOARCH=amd64`
   - `make workloadmanager GOOS=linux GOARCH=arm64`
   - 输出到 `_output/bin/linux/amd64/workloadmanager`
   - 输出到 `_output/bin/linux/arm64/workloadmanager`
2. 新增 runtime-only buildx Dockerfile：
   - `COPY ${TARGETPLATFORM}/workloadmanager /app/workloadmanager`
3. buildx context 改成 `_output/bin`。

优点：

- 最接近 Karmada。
- Docker build context 更小。
- 编译和镜像组装边界更清楚。
- 后续可以更容易做二进制 release 和镜像 release 复用。

风险：

- 改动范围更大：Makefile、Dockerfile、可能还要新增 hack 脚本。
- AgentCube 当前已有 `make build-all` / `bin/` 输出约定，是否改成 `_output/bin` 需要社区接受。
- PicoD runtime 还涉及 Python/Ubuntu layer，不能只用 Go 二进制解决全部慢点。

> 分析：这个方案更像 Karmada，但作为第一版 PR 可能 scope 过大。建议先做方案 A，用最小改动证明耗时下降；后续再讨论是否统一 image build pipeline。

### 方案 C：workflow matrix 并行三个镜像

可以把 AgentCube 的三个镜像拆成 matrix：

```yaml
strategy:
  matrix:
    image:
      - workloadmanager
      - agentcube-router
      - picod
```

优点：

- wall-clock 可能下降。
- 每个镜像失败点更清楚。

风险：

- 可能失去当前单 job 中 router 复用 workloadmanager build cache 的收益。
- 并行 job 会消耗更多 runner minutes。
- chart packaging 需要等待所有镜像 job 完成，workflow 结构要改成 `needs`。

> 分析：matrix 是流程优化，不是根因优化。当前最慢点是 QEMU arm64 Go 编译，先修 Dockerfile builder platform 更直接。

### 方案 D：buildx cache

可以给 buildx 加：

```bash
--cache-from type=gha
--cache-to type=gha,mode=max
```

或 registry cache。

优点：

- 对频繁 main push 有帮助。
- 可以减少重复依赖下载和重复 Go build。

风险：

- cache key、权限、容量和失效策略要设计。
- release image 使用 `packages: write`，cache 是否放 GHCR 需要单独确认权限。
- cache miss 时仍然慢。

> 分析：cache 是锦上添花，不应替代 builder platform 修复。先避免 QEMU 编译，再加 cache 才合理。

## 推荐 PR 切分

### PR 1：优化 Go builder platform

推荐标题：

```text
ci: build multi-arch images with native Go builder
```

预期改动：

```text
docker/Dockerfile
docker/Dockerfile.router
docker/Dockerfile.picod
```

核心 diff：

```dockerfile
- FROM golang:1.26.4-alpine AS builder
+ FROM --platform=$BUILDPLATFORM golang:1.26.4-alpine AS builder
```

PicoD：

```dockerfile
- FROM golang:1.26.4 AS builder
+ FROM --platform=$BUILDPLATFORM golang:1.26.4 AS builder
```

预期收益：

- `workloadmanager` 的 `linux/arm64 go build` 不再通过 QEMU 执行。
- release workflow 的 main/latest 发布耗时应明显下降。
- 不改变发布策略，不改变 image tag，不改变 chart 行为。

建议 PR kind：

```text
/kind cleanup
```

或如果强调 CI 耗时和资源消耗：

```text
/kind enhancement
```

### PR 2：可选后续，Karmada-style image pipeline

如果 PR 1 合并后社区仍希望继续优化，再考虑：

- 新增 `hack/docker.sh` 或 `hack/image.sh`。
- 统一 `_output/bin/<platform>/<binary>` 输出。
- runtime-only buildx Dockerfile。
- workflow matrix 化。
- buildx cache。

这应该作为独立 follow-up，不和 PR 1 混在一起。

## 验证计划

本地最小验证：

```bash
docker buildx build -f docker/Dockerfile \
  --platform linux/amd64,linux/arm64 \
  --progress=plain \
  -t agentcube-workloadmanager:buildplatform-test .

docker buildx build -f docker/Dockerfile.router \
  --platform linux/amd64,linux/arm64 \
  --progress=plain \
  -t agentcube-router:buildplatform-test .

docker buildx build -f docker/Dockerfile.picod \
  --platform linux/amd64,linux/arm64 \
  --progress=plain \
  -t picod:buildplatform-test .
```

> 注释：multi-platform build 默认不一定把镜像载入本地 Docker daemon，但它足以观察 builder stage 是否仍然在 arm64 QEMU 下跑 Go compiler，以及 build 总耗时是否下降。

如果需要真实 push 验证：

```bash
docker buildx build -f docker/Dockerfile \
  --platform linux/amd64,linux/arm64 \
  --progress=plain \
  -t ghcr.io/ranxi2001/workloadmanager:buildplatform-test \
  --push .
```

Fork workflow 验证：

1. 基于 `upstream/main` 创建 clean branch。
2. 只改 3 个 Dockerfile。
3. 推到 fork validation branch 或临时 fork `main`。
4. 观察 `Build and Push Release Images` 中 `Build and push images` 的耗时。
5. 验证结束后恢复 fork `main` 镜像状态。

> 分析：因为 release workflow 只监听 `main` push 和 tag push，普通 branch push 不会触发完整 release image publish。若要复用真实 workflow，仍然需要临时 fork `main` 或新增 fork-only workflow。这个操作会触发 GHCR image publish，必须提前确认成本和恢复方式。

## 当前 fork main 验证状态

当前仍有一个 fork run 在执行：

- Repo: `ranxi2001/agentcube`
- Run: <https://github.com/ranxi2001/agentcube/actions/runs/28633043101>
- Head: `427e618 ci: use valid chart version for latest releases`
- Purpose: 验证 #416 新方案是否能在 `main` push 下发布 latest image 并用 chart `0.0.0`
- State when writing: `build-and-push` still in progress

它还没有进入 Helm chart step。结合 upstream 旧 job，当前等待大概率仍是 multi-arch image build，而不是 chart 方案问题。

> 注释：fork `origin/main` 当前是临时测试 commit，不是干净 `upstream/main` 镜像。恢复到 `upstream/main` 会再次触发旧 broken release workflow，所以恢复前要先判断是否需要等待验证结果，或者恢复后立刻取消对应 run。

## 初步 upstream PR 价值判断

这个性能优化值得作为独立贡献，因为它满足几个条件：

1. 问题有明确证据：旧 job 日志中 `linux/arm64 go build` 用了 `1415.0s`。
2. 修复点小：第一版只改 Dockerfile builder platform。
3. 风险低：三个 Go 二进制当前都使用 `CGO_ENABLED=0`，适合 Go cross compile。
4. 用户可感知：main/latest release workflow 更快，减少 runner time 和发布等待。
5. 社区可接受：不改变功能语义，不改变 artifact naming，不改变 chart 发布策略。

推荐下一步：

1. 等 #416 latest chart 修复方向稳定，避免同时改 release workflow 和 Dockerfile 性能。
2. 新建 clean branch：`ci/native-build-platform-images`。
3. 只改 3 个 Dockerfile 的 builder `FROM --platform=$BUILDPLATFORM`。
4. 本地跑 buildx smoke。
5. 用 fork main 或 fork-only workflow 对比 `Build and push images` 耗时。
6. 准备 upstream PR body，明确引用 Karmada-style prebuild 思路，但本 PR 采用更小的 native builder stage 优化。

## 参考来源

- Karmada latest image workflow: <https://github.com/karmada-io/karmada/blob/master/.github/workflows/dockerhub-latest-image.yml>
- Karmada released image workflow: <https://github.com/karmada-io/karmada/blob/master/.github/workflows/dockerhub-released-image.yml>
- Karmada Makefile image targets: <https://github.com/karmada-io/karmada/blob/master/Makefile>
- Karmada Go build script: <https://github.com/karmada-io/karmada/blob/master/hack/build.sh>
- Karmada Docker build script: <https://github.com/karmada-io/karmada/blob/master/hack/docker.sh>
- Karmada multi-platform image Dockerfile: <https://github.com/karmada-io/karmada/blob/master/cluster/images/buildx.Dockerfile>
- AgentCube release workflow slow job: <https://github.com/volcano-sh/agentcube/actions/runs/28582345874/job/84745444791>
