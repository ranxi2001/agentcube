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

## 当前 fork main 验证结果

当前 fork run 已完成：

- Repo: `ranxi2001/agentcube`
- Run: <https://github.com/ranxi2001/agentcube/actions/runs/28633043101>
- Head: `427e618 ci: use valid chart version for latest releases`
- Purpose: 验证 #416 新方案是否能在 `main` push 下发布 latest image 并用 chart `0.0.0`
- Result: success
- Job duration: `2026-07-03T01:47:11Z` -> `2026-07-03T02:12:20Z`, about 25m09s

关键结论：

1. #416 的 latest image + chart `0.0.0` 方向通过真实 fork workflow 验证。
2. Helm chart packaging 不再失败：
   - `TAG=latest`
   - `CHART_VERSION=0.0.0`
   - `APP_VERSION=latest`
   - generated `agentcube-0.0.0.tgz`
   - pushed `ghcr.io/ranxi2001/charts/agentcube:0.0.0`
3. 真正耗时仍在 `Build and push images`，该 step 用了 `1487.1s`，约 24m47s。

新的分段耗时：

| Step / image | Duration | Key observation |
| --- | ---: | --- |
| `Build and push images` | 1487.1s | success, still dominates the whole job |
| `workloadmanager:latest` | about 21m56s | `linux/arm64 go build ./cmd/workload-manager` took `1291.4s`; `linux/amd64` took `173.2s` |
| `agentcube-router:latest` | about 39s | `linux/arm64 go build ./cmd/router` took `30.0s` |
| `picod:latest` | about 2m12s | `linux/arm64 apt-get update && apt-get install -y python3` took `120.0s`; `linux/arm64 go build ./cmd/picod` took `8.7s` |
| `Package Helm chart` | 0.1s | success |
| `Push Helm chart` | 2.4s | success |

> 分析：这次 run 把两个结论分清了。第一，#416 的 chart version 修复是正确的，`latest` image 发布也保住了。第二，release workflow 的用户体感仍然会很慢，原因不是 Helm，而是 multi-arch image build，尤其是 workloadmanager arm64 Go compiler 仍在 QEMU 里运行。

> 注释：fork `origin/main` 当前仍是临时测试 commit，不是干净 `upstream/main` 镜像。恢复到 `upstream/main` 会触发 upstream 当前旧 workflow，因此要么等 #416 更新并合入后再恢复，要么恢复后准备立即取消对应 release run。

## 本地 Scheme A 验证结果

在本地 clean worktree `/tmp/agentcube-image-build-validation` 中基于 `upstream/main` 创建分支：

```text
ci/native-build-platform-images
```

该分支已按 upstream PR 标准整理成单一 DCO commit，并推送到 fork：

```text
Branch: ranxi2001/agentcube:ci/native-build-platform-images
Commit: a20ab07 ci: build multi-arch images with native Go builder
Base: upstream/main 7f5a730
```

> 注释：这是未来可以直接整理成 upstream PR 的真实 topic branch，只包含 Dockerfile 最小改动。用于跑 GitHub benchmark 的临时 workflow 不应提交到这个分支，避免污染 PR diff。

该分支 push 后触发常规 push CI，9 个 workflow 全部成功。其中常规 Docker build 记录是：

- `Agentcube CI Workflow / build`: <https://github.com/ranxi2001/agentcube/actions/runs/28636134337/job/84922780136>

> 分析：这个 build 记录只能证明常规 CI build 没有被三行 Dockerfile 改动破坏。它不是 release workflow 的 multi-arch `Build and push images` 记录，也不能直接比较 baseline / Scheme A 的多架构构建耗时。后续需要 fork-only benchmark workflow 在 GitHub runner 上专门跑 buildx `cacheonly` 才能形成更有价值的对比数据。

只做三处最小改动：

```diff
- FROM golang:1.26.4-alpine AS builder
+ FROM --platform=$BUILDPLATFORM golang:1.26.4-alpine AS builder
```

对应文件：

```text
docker/Dockerfile
docker/Dockerfile.router
docker/Dockerfile.picod
```

其中 PicoD 使用非 alpine Go image：

```diff
- FROM golang:1.26.4 AS builder
+ FROM --platform=$BUILDPLATFORM golang:1.26.4 AS builder
```

> 注释：`$BUILDPLATFORM` 是 buildx 提供的构建平台变量。在 GitHub x86 runner 上，它通常是 `linux/amd64`。`TARGETOS` / `TARGETARCH` 仍然来自目标镜像平台，所以 Go 仍然输出 `linux/arm64` 二进制，但 Go compiler 自己不再作为 arm64 进程在 QEMU 里运行。

本地环境和工具：

| Item | Value |
| --- | --- |
| Worktree | `/tmp/agentcube-image-build-validation` |
| Base | `upstream/main` |
| Branch | `ci/native-build-platform-images` |
| Buildx builder | `agentcube-day39` |
| Buildx driver | `docker-container` |
| Buildx version | `0.30.1` |
| Output mode | `--output=type=cacheonly` |
| Platforms | `linux/amd64,linux/arm64` |
| Cache mode | `--no-cache` for normal layer cache, cache mounts still used by Dockerfile |

原始日志已归档：

```text
internship-reports/benchmarks/day39-release-image-build/scheme-a-workloadmanager-buildx.txt
internship-reports/benchmarks/day39-release-image-build/scheme-a-router-buildx.txt
internship-reports/benchmarks/day39-release-image-build/scheme-a-picod-buildx.txt
```

执行命令：

```bash
docker buildx build -f docker/Dockerfile \
  --platform linux/amd64,linux/arm64 \
  --progress=plain \
  --no-cache \
  --output=type=cacheonly \
  .

docker buildx build -f docker/Dockerfile.router \
  --platform linux/amd64,linux/arm64 \
  --progress=plain \
  --no-cache \
  --output=type=cacheonly \
  .

docker buildx build -f docker/Dockerfile.picod \
  --platform linux/amd64,linux/arm64 \
  --progress=plain \
  --no-cache \
  --output=type=cacheonly \
  .
```

结果汇总：

| Image / Dockerfile | Result | Total time | amd64 Go build | arm64 target Go build | Key observation |
| --- | --- | ---: | ---: | ---: | --- |
| `docker/Dockerfile` / workloadmanager | success | `553.93s` | `377.4s` | `380.0s` | arm64 target builder label changed to `linux/amd64->arm64 builder` |
| `docker/Dockerfile.router` / router | success | `339.75s` | `265.7s` | `266.0s` | arm64 target builder label changed to `linux/amd64->arm64 builder` |
| `docker/Dockerfile.picod` / picod | success | `1160.87s` | `85.9s` | `86.4s` | Go build fixed, but arm64 Ubuntu runtime `apt-get install python3` took `1111.1s` |

关键日志证据：

```text
#26 [linux/amd64->arm64 builder 8/8] RUN ... GOARCH=arm64 go build ... ./cmd/workload-manager
#26 DONE 380.0s

#25 [linux/amd64->arm64 builder 8/8] RUN ... GOARCH=arm64 go build ... ./cmd/router
#25 DONE 266.0s

#19 [linux/amd64->arm64 builder 6/6] RUN ... GOARCH=arm64 go build ... ./cmd/picod
#19 DONE 86.4s
```

进程观察也能佐证方向正确：在 workloadmanager 和 router 的编译阶段，本机看到的是 `/usr/local/go/pkg/tool/linux_amd64/compile` 和 `/usr/local/go/pkg/tool/linux_amd64/link`，而不是 arm64 Go compiler 通过 QEMU 运行。

> 分析：这说明 Scheme A 的核心目标已经验证通过：三个 Go builder stage 都从“目标平台执行 Go compiler”变成了“构建平台执行 Go compiler + `GOARCH` 交叉输出”。本地绝对耗时不能直接和 GitHub Actions 比，但 builder label 和进程架构足以证明慢路径已经被切掉。

同时，PicoD 暴露了另一个独立瓶颈：

```text
#10 [linux/arm64 stage-1 2/4] RUN apt-get update && apt-get install -y python3
#10 DONE 1111.1s
```

本机进程检查时看到：

```text
/usr/libexec/qemu-binfmt/aarch64-binfmt-P /usr/bin/python3.12 ...
/usr/libexec/qemu-binfmt/aarch64-binfmt-P /usr/bin/apt-get apt-get install -y python3
```

> 分析：这和 Go builder platform 修复是两个问题。Scheme A 能避免 QEMU 执行 Go compiler，但不能避免 target-platform runtime layer 中的 `RUN apt-get install python3`。PicoD 后续如果要继续优化，应该单独讨论 runtime image 方案，例如预制 base image、换更轻 runtime base、减少 package install、或避免在多平台 build 时执行重型目标平台安装脚本。

本地 Scheme A 结论：

1. 只改 3 个 Dockerfile 的 builder `FROM --platform=$BUILDPLATFORM` 可以通过三镜像 multi-arch buildx smoke。
2. Go 编译阶段已经确认从 QEMU arm64 Go compiler 切换为宿主 amd64 Go compiler 交叉编译。
3. workloadmanager 是最直接收益点，因为 GitHub baseline 中它的 arm64 Go build 曾达到 `1291.4s` / `1415.0s`。
4. PicoD 的剩余慢点不在 Go builder，而在 arm64 Ubuntu runtime Python 安装，应作为 follow-up 记录。
5. 真实 PR 分支已经按 DCO commit 推到 fork，可用于避免别人抢同一小修点。
6. 下一步适合用 fork-only benchmark workflow 在 GitHub runner 上比较 baseline / Scheme A / Scheme B。临时 benchmark workflow 不应进入 upstream PR 分支。

## Fork CI 分支策略

为了让 GitHub Actions 上的数据更有说服力，同时避免创建无效 self-PR，可以把验证拆成两类分支：

| Branch type | Purpose | Should become upstream PR? | Contains fork-only workflow? |
| --- | --- | --- | --- |
| `ci/native-build-platform-images` | 真实 Scheme A 改动，保持 PR diff 干净 | Yes, after issue / maintainer direction is clear | No |
| `ci/image-build-baseline-benchmark` | GitHub runner baseline benchmark | No | Yes |
| `ci/image-build-scheme-a-benchmark` | GitHub runner Scheme A benchmark | No | Yes |
| optional `ci/image-build-scheme-b-benchmark` | Karmada-style prototype benchmark | No, unless later cleaned | Yes |

> 分析：普通 branch push 现在会跑 #414 引入的常规 push CI，但它不会跑 `Build and Push Release Images`，也不会提供 multi-arch image build 分段数据。因此 benchmark 分支需要带 fork-only workflow，专门执行 `docker buildx build --platform linux/amd64,linux/arm64 --progress=plain .` 并上传日志 artifact。workflow 不登录 GHCR、不 push image、不 package Helm chart；不指定输出时 BuildKit 会把结果保留在 build cache 中，适合只测构建路径和耗时。这个 workflow 是验证工具，不应进入 upstream PR。

建议 fork-only benchmark workflow 做到：

1. 不登录 GHCR。
2. 不 push image。
3. 不 package / push Helm chart。
4. 使用 `ubuntu-24.04`，`docker/setup-qemu-action`，`docker/setup-buildx-action`。
5. 顺序构建 workloadmanager、router、picod，输出 `real` time 和 BuildKit plain log。
6. 上传三份日志 artifact。

> 注释：这里不发布镜像，因为我们只比较构建路径和耗时，不需要把结果写入 registry。这样既能获得 GitHub runner 上的数据，又不会污染 GHCR。

### 2026-07-03 fork-only benchmark 分支

已按上述策略创建两个测评分支：

| Branch | Base | Commit | Benchmark workflow run | Scope |
| --- | --- | --- | --- | --- |
| [`ci/image-build-baseline-benchmark`](https://github.com/ranxi2001/agentcube/tree/ci/image-build-baseline-benchmark) | `upstream/main` `7f5a730` | `4e737fc ci: add image build benchmark workflow` | <https://github.com/ranxi2001/agentcube/actions/runs/28636642514> | 只新增 fork-only benchmark workflow |
| [`ci/image-build-scheme-a-benchmark`](https://github.com/ranxi2001/agentcube/tree/ci/image-build-scheme-a-benchmark) | `ci/native-build-platform-images` | `60e5849 ci: add image build benchmark workflow` | <https://github.com/ranxi2001/agentcube/actions/runs/28636642076> | Scheme A 三行 Dockerfile 改动 + fork-only benchmark workflow |

这两个分支都会因为 push CI 配置额外触发常规验证 workflow，例如 build、lint、e2e、coverage 等。性能分析只使用 `Image Build Benchmark` workflow 的 job log / artifact，不用普通 push CI 的 Docker build 结果。

> 分析：这里没有创建 self-PR，避免 fork 仓库产生无效 PR 记录。benchmark workflow 只存在于 `ci/image-build-*-benchmark` 临时分支里；真正可能用于 upstream PR 的 `ci/native-build-platform-images` 仍然保持干净，只包含 3 个 Dockerfile 的最小改动。

### GitHub runner benchmark 结果

两个 fork-only benchmark run 都已完成，且两个分支各自的 10 个 push checks 全部成功。

原始日志已归档：

- Baseline：`internship-reports/benchmarks/day39-release-image-build/github-benchmark/baseline-28636642514/`
- Scheme A：`internship-reports/benchmarks/day39-release-image-build/github-benchmark/scheme-a-28636642076/`
- 摘要：`internship-reports/benchmarks/day39-release-image-build/github-benchmark/summary.md`

同口径结果如下：

| Image | Baseline elapsed | Scheme A elapsed | Speedup | Reduction |
| --- | ---: | ---: | ---: | ---: |
| workloadmanager | 1423s | 182s | 7.82x | 87.2% |
| router | 33s | 4s | 8.25x | 87.9% |
| picod | 132s | 122s | 1.08x | 7.6% |
| 三个 buildx 命令合计 | 1588s | 308s | 5.16x | 80.6% |
| benchmark job wall time | 1610s | 331s | 4.86x | 79.4% |

关键 BuildKit step：

| Step | Baseline | Scheme A | Speedup | Reduction |
| --- | ---: | ---: | ---: | ---: |
| workloadmanager arm64 Go build | 1404.5s | 169.4s | 8.29x | 87.9% |
| router arm64 Go build | 32.5s | 3.4s | 9.56x | 89.5% |
| picod arm64 Go build | 9.6s | 0.9s | 10.67x | 90.6% |
| picod arm64 `apt-get install python3` | 128.8s | 119.1s | 1.08x | 7.5% |

> 分析：这组 GitHub runner 数据证明 Scheme A 的方向不是本地环境偶然现象。只改 Dockerfile builder platform 后，`workloadmanager` 的 arm64 Go build 从 `linux/arm64 builder` 下的 1404.5s 降到 `linux/amd64->arm64 builder` 下的 169.4s。也就是说，真正被切掉的是 QEMU 执行 Go compiler 的慢路径。

PicoD 是一个重要边界：Scheme A 让 PicoD arm64 Go build 从 9.6s 降到 0.9s，但 PicoD 总耗时仍是 122s，因为它的主耗时来自 arm64 Ubuntu runtime layer 中的 `apt-get update && apt-get install -y python3`，Scheme A 不改变 runtime stage 的目标平台执行方式。

> 分析：这说明第一阶段 PR 应该保持最小，只解决 Go builder platform 问题。PicoD runtime 镜像优化属于第二阶段，例如预制 Python runtime base image、减少 apt 安装、或调整 runtime base，但这会改变镜像构建策略和运行时基础层，review 成本更高，不应和三行 builder 修复混在一个 PR 中。

## 先验证不同方案，再开 issue

这里更适合先做数据型 issue，而不是直接提性能优化 PR。

原因有三点：

1. 现象和修复点跨了 CI、Dockerfile、Makefile 和 release workflow，不只是单行 Dockerfile 改动。
2. 当前仓库已有 open PR [#264](https://github.com/volcano-sh/agentcube/pull/264) 在调整 workloadmanager build / image build 入口，虽然它不是 multi-arch 性能优化，但会碰到 Makefile 和 Docker image target 命名。直接提 PR 容易和 #264 的变更方向交叉。
3. 性能优化 PR 最重要的是证明收益。如果没有 baseline / 方案 A / 方案 B 的耗时对比，reviewer 很难判断这是不是值得改的 CI 复杂度。

> 分析：#416 修的是 release workflow 的正确性，Day39 讨论的是 release workflow 的性能。两者可以关联，但不应该混成同一个 PR。正确顺序是先让 #416 恢复 latest image + chart 发布能力，再用独立 issue 讨论 image build 耗时和优化方案。

### 已搜索到的相关 upstream 记录

按 `buildx`、`image build`、`release workflow`、`arm64` 搜索后，暂时没有看到专门讨论 buildx / arm64 构建性能的 open issue。

相关但不完全同题的记录：

| Link | State | Relevance |
| --- | --- | --- |
| [#264 make workloadmanager build more explicit](https://github.com/volcano-sh/agentcube/pull/264) | open | 调整 Makefile 和 workloadmanager image build 入口；后续性能 PR 需要避开或基于它 rebase |
| [#285 Build and push helm oci charts](https://github.com/volcano-sh/agentcube/issues/285) | closed | Helm OCI chart 发布能力背景，不是 build 性能问题 |
| [#288 push helm chart in release workflow](https://github.com/volcano-sh/agentcube/pull/288) | merged | 引入 Helm chart push，和 #416 的 chart version 问题相关，不是性能问题 |
| [#416 ci: publish release artifacts only for tags](https://github.com/volcano-sh/agentcube/pull/416) | open | 当前正在修 latest image + chart version 正确性，build 慢是在验证中暴露的后续问题 |

> 注释：这里说“暂时没有看到”是基于 GitHub issue / PR 关键词搜索，不等于社区一定没人关心。开 issue 前还应再按最终标题关键词搜一次，避免重复。

### 建议验证矩阵

issue 里最好放对比数据，而不是只放推断。

| Case | Scope | What to measure | Expected value |
| --- | --- | --- | --- |
| Baseline | 当前 upstream workflow | `Build and push images` 总耗时，三个 image 的分段耗时，`linux/arm64 go build` 耗时 | 证明现状慢点在哪里 |
| Scheme A | `FROM --platform=$BUILDPLATFORM` | 同样三镜像 multi-arch buildx，总耗时和 arm64 Go build 是否明显下降 | 已完成本地 smoke 和 GitHub runner benchmark，证明三镜像 Go builder 都进入 `linux/amd64->arm64 builder`，三镜像 buildx 命令合计从 1588s 降到 308s |
| Scheme B | Karmada-style prebuild + runtime-only Dockerfile | 宿主机 `GOARCH=amd64/arm64 go build` 耗时、runtime-only buildx 耗时、总耗时 | 判断是否值得后续大改 Makefile / script |
| Scheme C | workflow matrix | 三镜像并行后 wall-clock 时间和 runner minute 成本 | 判断是否值得牺牲 cache 复用换并行 |
| Scheme D | buildx cache | cache miss / hit 下的耗时 | 判断是否作为 follow-up，而不是第一修复 |

第一轮不一定要把 B/C/D 都实现成完整 PR。至少要完成：

1. Baseline：使用 upstream 旧 job、fork release run `28633043101` 和 fork-only benchmark run `28636642514` 提供真实 workflow 数据。
2. Scheme A：本地 buildx smoke 和 GitHub benchmark run `28636642076` 均已验证最小 Dockerfile 改动。
3. Scheme B：可以先做局部 prototype，证明 Karmada-style 的方向是否比 Scheme A 还有明显收益。

> 注释：本地 buildx 数据和 GitHub Actions 数据不能直接硬比绝对值，因为机器、网络、registry push、cache 状态不同。issue 中应该把它们分开：GitHub Actions baseline 证明线上痛点，本地验证证明改动方向，fork workflow 数据证明线上近似收益。

### Upstream issue 草稿（待用户确认后发布）

这个问题更像 enhancement issue，而不是 bug report。建议标题：

```text
Optimize multi-arch image build time in the release workflow
```

issue body：

```md
**What would you like to be added**:

I would like to optimize the multi-arch image build path used by the `Build and Push Release Images` workflow. The workflow currently builds `linux/amd64` and `linux/arm64` images with Docker buildx, but the Go build runs inside the target-platform builder stage. On x64 GitHub-hosted runners, this means the `linux/arm64` Go compiler runs through QEMU.

A minimal first step would be to run the Go builder stage on `$BUILDPLATFORM` while continuing to use `TARGETOS` / `TARGETARCH` for cross-compilation. This keeps the image output multi-arch, but avoids executing the Go compiler under arm64 emulation.

**Why is this needed**:

Recent release workflow runs spent about 25-27 minutes in the image publishing step. In one older upstream run, the workflow then failed at Helm chart packaging because `latest` was used as the chart version. In the fork validation run for #416, Helm packaging and chart push succeeded, but image publishing still took `1487.1s`.

The slowest part is the `workloadmanager` `linux/arm64` Go build. It took `1291.4s` in the fork release-validation run and `1415.0s` in the older upstream run.

I also ran two fork-only GitHub runner benchmarks that do not push images or charts. The baseline branch used the current Dockerfiles. The Scheme A branch changed only the three Go builder stages to `FROM --platform=$BUILDPLATFORM ... AS builder`.

**Observed evidence**:

| Source | Observation |
| --- | --- |
| Upstream workflow run | `Build and push images` took about 27 minutes before Helm chart packaging failed |
| Fork validation run for #416 | `Build and push images` took `1487.1s`; Helm chart `0.0.0` packaging and push succeeded |
| Workloadmanager image | `linux/arm64 go build ./cmd/workload-manager` took `1291.4s` in the fork run and `1415.0s` in the older upstream run |
| Fork-only baseline benchmark | three multi-arch buildx commands took `1588s` in total; workloadmanager alone took `1423s`; workloadmanager arm64 Go build took `1404.5s` |
| Fork-only Scheme A benchmark | three multi-arch buildx commands took `308s` in total; workloadmanager took `182s`; workloadmanager arm64 Go build took `169.4s` |
| Scheme A speedup | total buildx command time improved by `5.16x`; workloadmanager arm64 Go build improved by `8.29x` |
| Router image | arm64 Go build improved from `32.5s` to `3.4s` |
| PicoD image | arm64 Go build improved from `9.6s` to `0.9s`, but total image time changed only from `132s` to `122s` because the remaining cost is the target-platform Ubuntu/Python runtime package installation |

**Possible implementation directions**:

1. Minimal Dockerfile change: run the Go builder stage on `$BUILDPLATFORM` and keep using `TARGETOS` / `TARGETARCH` for cross compilation.
2. Karmada-style image pipeline: prebuild `linux/amd64` and `linux/arm64` binaries on the host runner, then use a runtime-only multi-platform Dockerfile to assemble images.
3. PicoD runtime-layer follow-up: avoid running the heavy arm64 Ubuntu/Python installation path through QEMU during multi-platform builds.
4. Follow-up workflow improvements: split images into a matrix and/or add buildx cache after the builder-platform issue is fixed.

**Related work**:

- #264 adjusts workloadmanager build / image build entrypoints, so any implementation should avoid conflicting with that Makefile cleanup.
- #416 fixes the release workflow chart-version failure while keeping latest image publishing enabled.

**Validation / limitations**:

- The fork-only benchmark workflow ran on GitHub-hosted `ubuntu-24.04` runners and did not push images or Helm charts. It measured buildx build time only.
- Both benchmark branches also passed the regular push validation workflows.
- The minimal `$BUILDPLATFORM` Dockerfile change was also validated locally with multi-arch buildx smoke builds for workloadmanager, router, and picod.
- The PicoD runtime layer is intentionally left as a follow-up because its remaining cost comes from target-platform Ubuntu/Python package installation, not Go compilation.
```

> 分析：issue body 里不应该直接承诺“我会实现方案 B”。更稳妥的说法是先讨论 optimization direction，并提供可验证数据。这样即使维护者更喜欢 #264 的 Makefile 方向，也可以把我们的数据变成 review 输入，而不是冲突 PR。

## 初步 upstream PR 价值判断

这个性能优化值得作为独立贡献，因为它满足几个条件：

1. 问题有明确证据：旧 job 日志中 `linux/arm64 go build` 用了 `1415.0s`。
2. 修复点小：第一版只改 Dockerfile builder platform。
3. 风险低：三个 Go 二进制当前都使用 `CGO_ENABLED=0`，适合 Go cross compile。
4. 用户可感知：main/latest release workflow 更快，减少 runner time 和发布等待。
5. 社区可接受：不改变功能语义，不改变 artifact naming，不改变 chart 发布策略。

推荐下一步：

1. 等 #416 latest chart 修复方向稳定，避免同时改 release workflow 和 Dockerfile 性能。
2. 本地验证分支 `ci/native-build-platform-images` 已完成 Scheme A smoke，并已按 DCO commit 推到 fork。
3. fork-only benchmark 分支已完成 GitHub runner baseline / Scheme A 对比，证明最小 Dockerfile 改动有明确收益。
4. 准备 upstream issue 文稿，说明问题、数据、候选方案和 #264 / #416 关系，并由用户确认后再发布。
5. issue 获得方向认可后，再把 `ci/native-build-platform-images` 整理成独立 PR。
6. 如果维护者认为 image build pipeline 需要统一，再做 Karmada-style prebuild prototype。

## 参考来源

- Karmada latest image workflow: <https://github.com/karmada-io/karmada/blob/master/.github/workflows/dockerhub-latest-image.yml>
- Karmada released image workflow: <https://github.com/karmada-io/karmada/blob/master/.github/workflows/dockerhub-released-image.yml>
- Karmada Makefile image targets: <https://github.com/karmada-io/karmada/blob/master/Makefile>
- Karmada Go build script: <https://github.com/karmada-io/karmada/blob/master/hack/build.sh>
- Karmada Docker build script: <https://github.com/karmada-io/karmada/blob/master/hack/docker.sh>
- Karmada multi-platform image Dockerfile: <https://github.com/karmada-io/karmada/blob/master/cluster/images/buildx.Dockerfile>
- AgentCube release workflow slow job: <https://github.com/volcano-sh/agentcube/actions/runs/28582345874/job/84745444791>
