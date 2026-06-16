# Day 14：更完整的 Kubernetes 环境搭建与测试计划

## 背景

前几天的 AgentCube 测试主要跑在当前测试机的本地 k3s 上。k3s 是兼容 Kubernetes API 的轻量发行版，不是“假 Kubernetes”；但我们当前环境是单节点、本机部署、没有 `/dev/kvm`、CPU 虚拟化 flags 未暴露，因此只能证明 AgentCube 的基础 controller / CRD / session / warm pool 链路可以跑通，不能代表标准 Kubernetes、多节点调度、真实资源竞争或 MicroVM / KVM 场景。

同事提到可以通过多个端口部署多个 Kubernetes 测试实例。这个方向适合补齐“标准 Kubernetes API 环境”和“多集群控制面验证”，避免后续 benchmark 一直停留在残缺环境里。

## 当前环境限制

| 项 | 当前情况 | 对测试结论的影响 |
| --- | --- | --- |
| Kubernetes | 本地 k3s，单节点 | 适合 smoke test；不适合验证多节点调度、节点亲和、跨集群 |
| OS | CentOS Linux 8 | 可以跑基础 Kubernetes / Go 测试；部分新内核 sandbox 能力受限 |
| kernel | `4.18.0-348.7.1.el8_5.x86_64` | 不支持较新的 Landlock；对部分 runtime / sandbox 功能不友好 |
| `/dev/kvm` | 不存在 | 不能验证 KVM / Kuasar / Firecracker / MicroVM 加速路径 |
| CPU flags | 未暴露 `vmx` / `svm` | 不能证明硬件虚拟化相关性能和兼容性 |
| 节点规模 | 单机 | 不能验证真实多节点资源分布、failover、调度压力 |

## Day14 目标

Day14 的重点不是立刻跑更复杂的 Agent benchmark，而是先把测试环境分层建清楚，让后续结论可以标注清楚来源和可信范围。

目标：

1. 建立一个比当前 k3s 更接近标准 Kubernetes 的本地测试环境。
2. 保留当前 k3s 作为快速 smoke test 环境。
3. 明确本机能测什么、不能测什么，避免把环境限制误判成 AgentCube 功能问题。
4. 形成可重复的环境验证 checklist。
5. 为后续多集群、Karmada、AgentCube 调度和 benchmark 工作打基础。

## 实际安装记录：KWOK 多节点模拟

环境探测结果：

| 项 | 结果 |
| --- | --- |
| 当前 Kubernetes | k3s `v1.24.17+k3s1`，context 为 `default` |
| 当前节点 | 1 个真实节点：`ecs-4b42-0001` |
| container runtime | k3s 内置 containerd `1.7.3-k3s1` |
| Docker / Podman / kind / k3d | 初始未安装；本日已补装 Docker Engine `26.1.3` 和 kind `v0.32.0` |
| Helm | 已安装，`v3.21.0` |
| 可用资源 | 4 vCPU，15Gi memory，根分区约 136Gi 可用 |

由于当前机器没有 Docker / Podman / kind / k3d，也没有额外 VM，不能在本机直接创建多个真实 Kubernetes worker 节点。为了先验证多节点调度语义，同时不破坏现有 k3s 和 AgentCube 环境，Day14 先选择 [KWOK](https://kwok.sigs.k8s.io/) 做 fake-node 多节点模拟。

KWOK 的定位是模拟 Kubernetes Node / Pod 对象，让 scheduler 和 controller 可以看到多个 Ready 节点。它适合测试调度、placement、controller 状态流转、扩缩容语义；但 fake node 不会真的运行容器，所以不能用来验证 AgentCube sandbox 内代码执行、镜像拉取、网络、存储、KVM 或 MicroVM 性能。

执行步骤：

```bash
kubectl apply -f https://github.com/kubernetes-sigs/kwok/releases/download/v0.7.0/kwok.yaml
kubectl apply -f https://github.com/kubernetes-sigs/kwok/releases/download/v0.7.0/stage-fast.yaml
kubectl apply -f internship-reports/manifests/day14-kwok-fake-nodes.yaml
kubectl apply -f internship-reports/manifests/day14-kwok-scheduler-smoke.yaml
kubectl wait --for=condition=Ready node/kwok-node-1 node/kwok-node-2 node/kwok-node-3 --timeout=180s
kubectl rollout status deploy/day14-kwok-scheduler-smoke --timeout=180s
```

卡点记录：

| 步骤 | 现象 | 原因 | 处理 |
| --- | --- | --- | --- |
| `kubectl apply -f .../kwok.yaml` | 命令返回非 0，但 CRD、RBAC、ConfigMap、Service、Deployment 已创建 | KWOK `v0.7.0` manifest 包含 `flowcontrol.apiserver.k8s.io/v1` 的 `FlowSchema`，当前 k3s `v1.24` 只支持 `v1beta2` | 记录为兼容性卡点；主体 controller 资源已创建，继续验证 |
| 第一次 apply `stage-fast.yaml` | 报 `no matches for kind "Stage"` | CRD 刚创建，API discovery 尚未刷新 | 等 CRD 可见后重试，第二次 apply 成功 |
| KWOK Pod 启动 | 镜像拉取耗时约 35s | 首次从 `registry.k8s.io/kwok/kwok:v0.7.0` 拉取镜像 | 等待完成，最终 controller Ready |

安装后状态：

```text
kwok-controller: Ready 1/1, image registry.k8s.io/kwok/kwok:v0.7.0
真实节点: ecs-4b42-0001 Ready
fake 节点: kwok-node-1 / kwok-node-2 / kwok-node-3 Ready
fake 节点 taint: kwok.x-k8s.io/node=fake:NoSchedule
```

调度验证：

```text
day14-kwok-scheduler-smoke replicas=6
nodeAffinity: type=kwok
toleration: kwok.x-k8s.io/node:NoSchedule
结果: 6 个 Pod 成功调度到 kwok-node-2 / kwok-node-3 并显示 Running
清理: 已删除 day14-kwok-scheduler-smoke Deployment，确认 default namespace 无测试 Pod 残留
```

当前集群状态已经变为：

```text
1 个真实 k3s 节点 + 3 个 KWOK fake nodes
```

fake nodes 已保留，方便后续做 scheduler、node affinity、taint/toleration、控制器 status 相关测试。普通 workload 不会误调度到 fake nodes，因为 fake nodes 带有 `NoSchedule` taint；只有显式添加 toleration 和 node affinity 的测试负载才会上去。

复现文件：

- [day14-kwok-fake-nodes.yaml](manifests/day14-kwok-fake-nodes.yaml)
- [day14-kwok-scheduler-smoke.yaml](manifests/day14-kwok-scheduler-smoke.yaml)

这个结果补齐的是“多节点调度语义环境”，不是“真实多节点执行环境”。后续 AgentCube 的真实 session / sandbox benchmark 仍应继续跑在真实节点上；如果要验证 sandbox 在不同节点上的实际启动、网络和资源表现，仍然需要真实 worker 节点或支持容器的多节点集群。

## 实际安装记录：Docker + kind 标准 Kubernetes 尝试

为了解决“仍然只是在 k3s 上测试”的问题，继续安装 Docker 和 kind，尝试在同一台机器上创建独立的上游 Kubernetes 测试集群。

安装结果：

| 项 | 结果 |
| --- | --- |
| Docker repo | 已添加 `https://download.docker.com/linux/centos/docker-ce.repo` |
| Docker Engine | 已安装并启动，版本 `26.1.3` |
| Docker containerd | `1.6.32` |
| Docker storage driver | `overlay2` |
| Docker cgroup | 当前恢复为 `cgroupfs`，宿主机为 `cgroup v1` |
| kind | 已安装 `/usr/local/bin/kind`，版本 `v0.32.0` |
| Docker 验证 | `docker run --rm hello-world` 成功 |
| k3s 影响 | Docker 安装和重启后，原 k3s 仍为 `active`，现有 AgentCube Pod 正常 |

尝试过的 kind 配置：

| 尝试 | 配置 | 结果 |
| --- | --- | --- |
| 1 | kind 默认 node image `kindest/node:v1.36.1`，1 control-plane + 2 worker | control-plane kubeadm init 超时，kind 自动清理 |
| 2 | 固定 `kindest/node:v1.33.12`，1 control-plane + 2 worker | control-plane、CNI、StorageClass 成功，但 worker join 阶段 kubelet healthz 超时，kind 自动清理 |
| 3 | Docker 改为 `native.cgroupdriver=systemd` 后重试 `v1.33.12` | control-plane bootstrap 阶段超时，回滚 Docker 配置 |
| 4 | 固定 `kindest/node:v1.29.14`，1 control-plane + 1 worker | control-plane kubelet healthz 超时，kind 自动清理 |
| 5 | 单 control-plane debug，`--retain` 保留容器 | 进入容器确认 kubelet 反复失败 |
| 6 | 在 kind kubelet config 中显式设置 `cgroupDriver: cgroupfs` | 仍然失败 |

关键错误：

```text
failed to initialize top level QOS containers:
root container [kubelet kubepods] doesn't exist
```

以及：

```text
The kubelet is not healthy after ...
curl http://localhost:10248/healthz: connect: connection refused
```

debug 容器中的 kubelet 日志显示，它能启动 containerd 并进入初始化流程，但最终在 kubelet cgroup / QoS 容器初始化阶段退出。结合宿主机信息：

```text
Docker CgroupDriver=cgroupfs
Docker CgroupVersion=1
kernel=4.18.0-348.7.1.el8_5.x86_64
CentOS Linux 8
```

当前判断：这台 CentOS 8 / cgroup v1 / Docker 26 的组合不适合继续强行用 kind 搭标准 Kubernetes。kind 已经提示 `cgroup v1 is deprecated in Kubernetes and will not be supported in a future kind release`，而实际错误也集中在 kubelet cgroup 初始化。继续换 kind 镜像版本收益不高。

清理结果：

```text
kind get clusters -> No kind clusters found
docker ps -a -> 无 kind 容器残留
Docker 服务 active
k3s 服务 active
当前 kubeconfig context 仍为 default
```

复现文件：

- [day14-kind-agentcube-config.yaml](manifests/day14-kind-agentcube-config.yaml)
- [day14-kind-single-node-debug.yaml](manifests/day14-kind-single-node-debug.yaml)

结论：Docker/kind 工具已装好，但本机没有跑通标准 kind Kubernetes。Day14 不能把 L1 标准 Kubernetes 标记为完成；当前真实完成的是 L0 k3s、L0.5 k3s + KWOK fake nodes，以及 Docker/kind 安装预检。要完成 L1，建议换一台 cgroup v2 / 新内核机器，或使用云厂商标准 Kubernetes / 裸 VM 重新搭 kubeadm。

## 环境分层

| 层级 | 环境 | 目的 | 能验证 | 不能验证 |
| --- | --- | --- | --- | --- |
| L0 | 当前单节点 k3s | 快速 smoke test、脚本调试、日报实验 | CRD、controller、router、workload-manager、session 基础链路 | 标准 K8s 差异、多节点调度、KVM/MicroVM |
| L1 | 标准单节点 Kubernetes，例如 kind / kubeadm | 更接近上游 Kubernetes API 和 controller 行为 | Helm/manifests、CRD、controller、CodeInterpreter、warm pool、基础 benchmark | 真实多机资源竞争、硬件虚拟化 |
| L2 | 本机多集群 / 多 API server 端口 | 验证多集群控制面、Karmada 学习、未来跨集群 AgentCube 设计 | 多 kubeconfig、多 context、多 control plane 接入、跨集群资源分发 | 真实物理隔离、真实网络延迟、KVM |
| L3 | 支持 `/dev/kvm` 的标准 K8s 节点 | 验证 Kuasar / MicroVM / SnapStart / CubeSandbox / forkd | 硬件隔离、snapshot restore、MicroVM benchmark | 当前机器无法完成，需要新机器 |

## 推荐优先路线

优先做 L1，再考虑 L2。

原因：

- L1 能先回答“AgentCube 在更标准 Kubernetes 环境里是否正常部署和运行”。
- L2 更适合 Karmada 或未来 AgentCube 跨集群验证，但它仍然共享同一台机器资源，不等于真实多节点性能。
- L3 才能解决 KVM / MicroVM / SnapStart 真实性能问题，但当前机器没有硬件条件。

## L1 标准 Kubernetes 验证项

建议先选择 kind 或 kubeadm 之一。若当前机器已有 Docker/containerd 条件，kind 更轻量；如果希望贴近生产节点，kubeadm 更标准但成本更高。

必须记录：

- Kubernetes 发行版和版本。
- container runtime。
- kubeconfig context。
- 节点数量。
- API server 地址和端口。
- 是否存在 `RuntimeClass`。
- AgentCube 部署方式和 commit。
- 测试前后的 `CodeInterpreter.spec.warmPoolSize`。

验证 checklist：

```text
1. kubectl cluster-info 可用
2. kubectl get nodes 正常
3. AgentCube CRD 成功安装
4. workload-manager / router / Redis 等组件 Ready
5. CodeInterpreter 创建成功
6. warm pool 达到预期 ready 数
7. 创建 session 成功
8. 执行最小 Python 代码成功，例如 print("ok")
9. 删除 session 后 Sandbox / SandboxClaim / Pod 无异常残留
10. warmPoolSize=0/2 的基础延迟测试可重复
```

## L2 多端口 / 多集群验证思路

“多个端口”可以理解为在同一台机器上运行多个 Kubernetes control plane，每个集群暴露不同 API server 端口，并通过不同 kubeconfig context 访问。

适合验证：

- Karmada host cluster + member cluster 的基础形态。
- 多 kubeconfig / 多 context 操作流程。
- 未来 AgentCube 是否可能跨集群管理 sandbox runtime。
- 控制面对象是否能清楚标注目标 cluster。

不适合直接作为性能结论：

- 所有集群共享同一台物理/虚拟机资源。
- 网络、磁盘、CPU 不是真实多机隔离。
- 没有 `/dev/kvm`，仍然不能测 MicroVM 硬件路径。

## AgentCube 最小测试矩阵

| 测试项 | k3s L0 | 标准 K8s L1 | 多集群 L2 | KVM L3 |
| --- | --- | --- | --- | --- |
| CRD 安装 | 必测 | 必测 | 必测 | 必测 |
| controller Ready | 必测 | 必测 | 必测 | 必测 |
| CodeInterpreter session | 必测 | 必测 | 可选 | 必测 |
| warmPoolSize=0/2 | 必测 | 必测 | 可选 | 必测 |
| 并发 2/5/10 | 可测 | 必测 | 可选 | 必测 |
| p50/p95/p99 | 可测 | 必测 | 可选 | 必测 |
| 资源残留检查 | 必测 | 必测 | 必测 | 必测 |
| RuntimeClass | 记录 | 记录 | 记录 | 必测 |
| KVM / MicroVM | 不能测 | 不能测，除非节点支持 | 不能测，除非节点支持 | 必测 |
| SnapStart restore | 不能测 | 不能测，除非 runtime 支持 | 不能测，除非 runtime 支持 | 必测 |

## 后续产出

Day14 应产出：

1. 一份标准 Kubernetes 环境安装记录。
2. 一份环境能力表：哪些能力已具备，哪些能力仍阻塞。
3. 一组最小 AgentCube smoke test 命令和结果。
4. 一组 warm pool 基础 benchmark 结果。
5. 一份资源残留检查记录。
6. 明确说明：当前结果是否可以和前几天 k3s 结果对比，哪些对比不公平。

## 今日结论

后续不应该只依赖当前单节点 k3s 环境继续做所有判断。k3s 可以保留为快速验证环境，但 Day14 需要补一个更标准的 Kubernetes 测试环境，把 AgentCube 的基础部署、session、warm pool、benchmark 和清理流程跑成可重复 checklist。

完整验证仍然需要一台支持 `/dev/kvm` 和 `vmx` / `svm` 的机器。当前机器能补齐 Kubernetes 控制面测试，但补不齐 MicroVM / KVM / SnapStart 的硬件路径测试。
