# Day 6 实习记录：forkd 竞品复现预检

## 基本信息

- 实习项目：AgentCube
- 实习方向：华为公司开源小组 / AgentCube 开源项目研究
- 日期：Day 6
- 今日主题：尝试在同一台机器上跑通 forkd，并准备与 AgentCube 沙箱延迟实测做对比
- 结论状态：当前机器无法完成 forkd microVM 实测，主要 blocker 是没有可用 `/dev/kvm`
- 预检脚本：`internship-reports/benchmarks/forkd_precheck.sh`
- 预检结果：`internship-reports/benchmarks/forkd_precheck_result.txt`

## 今天的目标

Day 5 已经完成了 AgentCube 本地环境下的沙箱延迟测试：

- 顺序 5 次：热池命中时最小总延迟约 `91.95 ms`，p50 `177.14 ms`。
- 并发 10 次：`warmPoolSize=2` 下前两个请求约 `188 ms`、`246 ms`，其余请求排队到 `6-9 s`。

下一步希望跑通竞品项目，在相同环境下测试。第一优先级是 forkd，因为它的公开 benchmark 声称可以从 warm parent fork 100 个 KVM microVM，适合和 AgentCube 的 warm pool 模型做对比。

预期路径：

```text
下载 forkd 官方二进制
-> forkd doctor
-> 拉取或构建 Python 快照
-> fork N 个 sandbox
-> 运行最小 Python 代码
-> 与 AgentCube 的 create/run/delete 延迟做对比
```

## 当前机器环境

我把环境检查整理成了一个可复用脚本：

```bash
bash internship-reports/benchmarks/forkd_precheck.sh | tee internship-reports/benchmarks/forkd_precheck_result.txt
```

后续换机器时可以先跑这个脚本，再决定是否继续执行 `forkd doctor` 和正式 benchmark。

系统信息：

```bash
uname -a
```

输出：

```text
Linux ecs-4b42-0001 4.18.0-348.7.1.el8_5.x86_64 #1 SMP Wed Dec 22 13:25:12 UTC 2021 x86_64 x86_64 x86_64 GNU/Linux
```

发行版：

```bash
cat /etc/os-release
```

输出：

```text
NAME="CentOS Linux"
VERSION="8 (Core)"
VERSION_ID="8"
```

glibc 版本：

```bash
ldd --version
```

输出：

```text
ldd (GNU libc) 2.28
```

虚拟化环境：

```bash
systemd-detect-virt
```

输出：

```text
kvm
```

这说明当前实验环境本身运行在 KVM 虚拟机里，不是裸金属宿主机。

CPU 信息：

```bash
lscpu
```

关键输出：

```text
Architecture:        x86_64
CPU(s):              4
Vendor ID:           GenuineIntel
BIOS Vendor ID:      QEMU
Hypervisor vendor:   KVM
Virtualization type: full
```

检查 CPU flags：

```bash
rg -n "vmx|svm" /proc/cpuinfo | head -n 5
```

没有输出。也就是说当前 VM 没有暴露 Intel VT-x (`vmx`) 或 AMD-V (`svm`) 给 guest。

## forkd 官方二进制安装尝试

查询最新 release：

```bash
curl -L --max-time 20 https://api.github.com/repos/deeplethe/forkd/releases/latest
```

最新版本为：

```text
v0.5.2
```

下载官方二进制：

```bash
curl -L --fail --max-time 60 \
  -o /tmp/forkd-v0.5.2-x86_64-linux.tar.gz \
  https://github.com/deeplethe/forkd/releases/download/v0.5.2/forkd-v0.5.2-x86_64-linux.tar.gz
```

下载官方 SHA256SUMS：

```bash
curl -L --fail --max-time 30 \
  -o /tmp/forkd-SHA256SUMS \
  https://github.com/deeplethe/forkd/releases/download/v0.5.2/SHA256SUMS
```

校验结果：

```bash
sha256sum /tmp/forkd-v0.5.2-x86_64-linux.tar.gz
cat /tmp/forkd-SHA256SUMS
```

输出一致：

```text
786371cd10f75f7a24b44a9fae803569872f2cd45b7b2b19ded24a4c2d945102  forkd-v0.5.2-x86_64-linux.tar.gz
```

解压：

```bash
tar -xzf /tmp/forkd-v0.5.2-x86_64-linux.tar.gz -C /usr/local/bin
ls -l /usr/local/bin/forkd*
```

输出：

```text
/usr/local/bin/forkd
/usr/local/bin/forkd-controller
```

执行：

```bash
forkd --version
forkd doctor
```

失败：

```text
forkd: /lib64/libc.so.6: version `GLIBC_2.29' not found (required by forkd)
forkd: /lib64/libc.so.6: version `GLIBC_2.30' not found (required by forkd)
forkd: /lib64/libc.so.6: version `GLIBC_2.32' not found (required by forkd)
forkd: /lib64/libc.so.6: version `GLIBC_2.33' not found (required by forkd)
forkd: /lib64/libc.so.6: version `GLIBC_2.34' not found (required by forkd)
forkd: /lib64/libc.so.6: version `GLIBC_2.38' not found (required by forkd)
forkd: /lib64/libc.so.6: version `GLIBC_2.39' not found (required by forkd)
```

结论：官方预编译二进制是在更新的 Linux 用户态上构建的，当前 CentOS 8 的 `glibc 2.28` 无法直接运行。

## 尝试旧版本二进制

为了确认是不是新版本才有 glibc 要求，我又尝试了旧版本：

```bash
curl -L --fail --max-time 60 \
  -o /tmp/forkd-v0.3.4-x86_64-linux.tar.gz \
  https://github.com/deeplethe/forkd/releases/download/v0.3.4/forkd-v0.3.4-x86_64-linux.tar.gz

curl -L --fail --max-time 60 \
  -o /tmp/forkd-v0.1.4-x86_64-linux.tar.gz \
  https://github.com/deeplethe/forkd/releases/download/v0.1.4/forkd-v0.1.4-x86_64-linux.tar.gz
```

执行旧版本 `forkd --version` 仍然失败，错误同样是缺少 `GLIBC_2.29` 到 `GLIBC_2.39`。

结论：换旧 release 没有解决当前系统的 glibc 不兼容问题。

## KVM 能力预检

forkd 的核心能力依赖 Firecracker microVM，也就是必须能访问 KVM。

检查设备：

```bash
ls -l /dev/kvm /dev/net/tun 2>&1 || true
```

输出：

```text
ls: cannot access '/dev/kvm': No such file or directory
crw-rw-rw- 1 root root 10, 200 Jun 10 15:25 /dev/net/tun
```

说明：

- `/dev/net/tun` 存在，网络 tap/tun 设备基础能力有。
- `/dev/kvm` 不存在，KVM 设备不可用。

检查内核配置：

```bash
grep -E 'CONFIG_KVM|CONFIG_KVM_INTEL|CONFIG_USERFAULTFD|CONFIG_VHOST_NET' \
  /lib/modules/$(uname -r)/config
```

输出：

```text
CONFIG_USERFAULTFD=y
CONFIG_VHOST_NET=m
CONFIG_KVM=m
CONFIG_KVM_INTEL=m
CONFIG_KVM_AMD=m
```

说明内核有 KVM 模块，但这不代表当前 VM 暴露了硬件虚拟化能力。

尝试加载模块：

```bash
modprobe kvm || true
modprobe kvm_intel || true
lsmod | rg '^kvm' || true
ls -l /dev/kvm 2>/dev/null || true
dmesg | tail -n 40
```

关键输出：

```text
modprobe: ERROR: could not insert 'kvm_intel': Operation not supported
kvm                   880640  0
kvm: no hardware support
```

结论：

- `kvm` 通用模块能加载。
- `kvm_intel` 无法加载。
- dmesg 明确显示 `kvm: no hardware support`。
- CPU flags 里没有 `vmx` / `svm`。

这说明当前 VM 没有开启 nested virtualization 或没有把硬件虚拟化能力透传给 guest。forkd 即使通过源码构建解决了 glibc 问题，也无法真正启动 Firecracker microVM。

## 为什么没有继续源码构建

当前机器没有 Rust 工具链：

```bash
command -v cargo rustc
```

没有输出。

理论上可以安装 Rust，然后从源码构建 forkd，以绕过官方二进制的 glibc 版本问题。但这只能解决用户态二进制兼容问题，不能解决 `/dev/kvm` 缺失。

forkd 的实测目标是运行 microVM。如果没有 KVM，源码构建成功也无法完成最小 sandbox，更无法得到有效 benchmark 数字。因此当前阶段不继续投入源码构建，避免把时间花在已知无法完成的路径上。

## 与 AgentCube 实测的对比边界

这次还没有得到 forkd 实测数字，所以不能做“同环境性能对比”。目前能得出的只是环境可运行性对比：

| 项目 | 当前机器是否可运行 | 原因 |
| --- | --- | --- |
| AgentCube 当前配置 | 可以 | k3s + Pod + `SandboxWarmPool`，未配置 KVM runtimeClass |
| forkd 官方二进制 | 不可以 | 当前系统 `glibc 2.28`，官方二进制需要更高 glibc |
| forkd 源码构建后 | 仍预计不可以跑 microVM | `/dev/kvm` 不存在，dmesg 显示 `kvm: no hardware support` |

这也说明 Day 5 的 AgentCube 数据并不是 KVM microVM 数据，而是当前 k3s Pod/warm pool 路径的数据。如果要公平比较 forkd 和 AgentCube 的微 VM 能力，需要换到同一台支持 KVM 的机器，并且最好让 AgentCube 也配置对应的 runtimeClass。

## 后续需要的环境

要继续 forkd 实测，需要满足：

```text
x86_64 Linux
Ubuntu 22.04+ 或 glibc 足够新的发行版
/dev/kvm 可用
CPU flags 有 vmx 或 svm
支持创建 tap / netns
有 root 权限或足够的 CAP_NET_ADMIN / CAP_SYS_ADMIN 能力
```

推荐环境：

1. 裸金属 Linux 机器。
2. 支持 nested virtualization 的云主机，并确认 guest 内有 `/dev/kvm`。
3. 本地开发机启用 nested virtualization 后启动 Linux VM。

预检命令：

```bash
ls -l /dev/kvm
egrep -o 'vmx|svm' /proc/cpuinfo | head
systemd-detect-virt
ldd --version
```

只有这些通过后，再执行：

```bash
forkd doctor
forkd quickstart
forkd pull deeplethe/langgraph-react
forkd fork --tag langgraph -n 3 --per-child-netns
```

## 下一步计划

当前这台机器上继续做的价值不大。下一步应该二选一：

1. 换一台支持 `/dev/kvm` 的机器跑 forkd，并把结果带回来写进 Day 6 后半部分。
2. 如果不能换机器，就先跑 cage-bro 这类不依赖 KVM 的竞品，做工具运行时维度的对比；forkd 保持为“环境预检失败，等待 KVM 环境”的状态。

在真正跑通 forkd 后，建议用和 AgentCube 相同的测试粒度：

```text
create/spawn sandbox
run print('ok')
delete/cleanup sandbox
sequential count=5
concurrent count=10
concurrent count=100
```

并且报告中必须明确：

- forkd 是否使用预热 snapshot。
- AgentCube 是否使用 warm pool。
- 两边是否都是 KVM 隔离。
- 是否包含 LLM 时间。
- 是否包含网络和 cleanup 时间。

这样才能避免把不同层次、不同隔离强度、不同 warm 状态的数字混在一起比较。
