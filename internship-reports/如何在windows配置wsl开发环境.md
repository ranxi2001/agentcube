# 如何在 Windows 配置 WSL 开发环境

本文记录 2026-07-02 在本机把 AgentCube 开发环境迁到 WSL 的配置过程。目标不是只让命令能跑，而是把日常开发入口从 Windows 文件系统迁到 WSL ext4 文件系统里，之后用 VS Code Remote - WSL 打开项目。

> 注释：WSL ext4 路径指的是 Linux 里的 `/home/ranxi/...`，不是 Windows 挂载进来的 `/mnt/c/...`。Go、Kubernetes、Docker、Helm 这类工具在 `/home` 下跑更接近 Linux CI，也能减少路径转换、换行、权限和性能问题。

## 当前已配置状态

本机当前已完成以下配置：

```text
WSL distro: Ubuntu 24.04.2 LTS
WSL version: 2
Linux user: ranxi
Home: /home/ranxi
VS Code: 1.126.0
VS Code extension: ms-vscode-remote.remote-wsl
```

WSL 里已经验证到的主要工具：

```text
git 2.43.0
go 1.26.4 linux/amd64
make 4.3
gcc/g++ 13.3.0
jq 1.7
python3 3.12.3
pip 24.0
docker 29.1.3
helm v4.2.2
kubectl v1.36.2
```

Git 全局配置已写入 WSL 用户：

```bash
git config --global user.name "ranxi2001"
git config --global user.email "ranxi169@163.com"
git config --global core.autocrlf input
git config --global init.defaultBranch main
```

`~/.bashrc` 已追加 Go workspace PATH：

```bash
export GOPATH="$HOME/go"
export PATH="$HOME/go/bin:$PATH"
```

> 分析：`core.autocrlf=input` 是 Linux/WSL 侧更合适的选择。它提交时规范为 LF，但不会像 Windows `true` 那样把工作区文件改成 CRLF，能减少 shell 脚本、Go 生成文件和 CI diff 的噪音。

## 推荐目录结构

以后不要在这个路径里长期开发：

```text
/mnt/c/Users/ranxi/Desktop/Project/agentcube
```

推荐在 WSL 里使用：

```text
/home/ranxi/projects/agentcube
```

创建项目目录：

```bash
mkdir -p ~/projects
```

首次迁移时 clone 仓库：

```bash
cd ~/projects
git clone https://github.com/ranxi2001/agentcube.git
cd agentcube
git remote add upstream https://github.com/volcano-sh/agentcube.git
git fetch --all --prune
git switch intern
```

如果 `upstream` 已存在，就不用重复添加：

```bash
git remote -v
```

> 注释：`origin` 是个人 fork，`upstream` 是官方仓库。实习报告、中文记录和本地技能继续放 `intern`；上游 PR topic branch 仍然从 `upstream/main` 单独创建。

## VS Code 使用方式

Windows 侧已安装 Remote - WSL 扩展：

```bash
code --install-extension ms-vscode-remote.remote-wsl
```

以后打开项目的推荐方式是在 WSL 终端里执行：

```bash
wsl -d Ubuntu
cd ~/projects/agentcube
code .
```

也可以从 Windows Git Bash 调用：

```bash
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash -lc 'cd ~/projects/agentcube && code .'
```

> 注释：从 Git Bash 调 `wsl.exe` 时加 `MSYS_NO_PATHCONV=1`，是为了防止 Git Bash 把 `/mnt/c/...` 或 Linux 参数误转换成 Windows 路径。

## Docker Desktop 集成检查

Docker CLI 已在 WSL 里可见：

```bash
docker --version
```

后续如果 `docker ps` 失败，先打开 Docker Desktop，然后检查：

```bash
docker ps
```

如果仍然失败，到 Docker Desktop 设置里确认：

```text
Settings -> Resources -> WSL integration -> Ubuntu enabled
```

> 分析：WSL 里的 `docker` 通常连接 Docker Desktop 提供的 daemon，不等于 WSL 自己启动了一个 dockerd。AgentCube 本地镜像构建可以复用这个 daemon。

## 安装过程记录

本轮安装使用 root 用户进入 WSL 执行系统级安装，因为默认用户 `ranxi` 的 `sudo -n true` 不能免密执行：

```bash
wsl.exe -d Ubuntu -u root -- bash <script>
```

基础包安装：

```bash
apt-get update
apt-get install -y \
  build-essential \
  ca-certificates \
  curl \
  gcc \
  g++ \
  git \
  gnupg \
  jq \
  make \
  pkg-config \
  python3 \
  python3-pip \
  python3-venv \
  unzip \
  wget
```

Go 按本仓库要求安装为 1.26.4：

```bash
go_version="1.26.4"
go_dir="/usr/local/go${go_version}"
curl -fsSL "https://go.dev/dl/go${go_version}.linux-amd64.tar.gz" -o "/tmp/go${go_version}.linux-amd64.tar.gz"
rm -rf "$go_dir"
mkdir -p "$go_dir"
tar -C "$go_dir" --strip-components=1 -xzf "/tmp/go${go_version}.linux-amd64.tar.gz"
ln -sfn "${go_dir}/bin/go" /usr/local/bin/go
ln -sfn "${go_dir}/bin/gofmt" /usr/local/bin/gofmt
```

kubectl 安装：

```bash
kubectl_version="$(curl -fsSL https://dl.k8s.io/release/stable.txt)"
rm -f /usr/local/bin/kubectl
curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${kubectl_version}/bin/linux/amd64/kubectl"
chmod +x /usr/local/bin/kubectl
kubectl version --client=true
```

Helm 本轮通过官方 release 二进制安装。当前机器实际安装到 `v4.2.2`：

```bash
helm version --short
```

如果后续 AgentCube chart 或 CI 复现需要固定 Helm 3，可以用同样方式覆盖成 Helm 3 的具体版本：

```bash
helm_version="v3.15.4"
tmp_dir="$(mktemp -d)"
curl -fsSL "https://get.helm.sh/helm-${helm_version}-linux-amd64.tar.gz" -o "${tmp_dir}/helm.tgz"
tar -C "$tmp_dir" -xzf "${tmp_dir}/helm.tgz"
install -m 0755 "${tmp_dir}/linux-amd64/helm" /usr/local/bin/helm
rm -rf "$tmp_dir"
```

> 分析：这里记录 Helm 3 fallback 是因为不少 Kubernetes 项目的文档和 CI 历史上默认 Helm 3。当前 Helm 4 能执行常规 `helm lint/package/push`，但如果遇到 chart 行为差异，先切回 Helm 3 复现 CI 更稳。

## 本轮遇到的问题和修复

### NVIDIA apt 源缺 GPG key

`apt-get update` 最初失败在 NVIDIA container toolkit 源：

```text
NO_PUBKEY DDCAE044F796ECB0
```

修复方式是把 NVIDIA key 放到 keyring，并让源文件使用 `signed-by`：

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
sed -i 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#' \
  /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update
```

> 注释：这是 apt 安全校验问题，不是 AgentCube 代码问题。没有修好时，后续 `apt-get install` 会被源校验失败打断。

### Helm 官方安装脚本失败

第一次用：

```bash
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

结果脚本返回：

```text
Failed to install helm
```

最终改成直接下载 `https://get.helm.sh/helm-<version>-linux-amd64.tar.gz` 并 `install` 到 `/usr/local/bin/helm`。

> 分析：脚本失败时不必纠缠脚本内部逻辑。Helm 的 release tarball 是稳定入口，直接安装二进制更可控，也更容易在文档里复现。

### kubectl 写入失败

安装 kubectl 时遇到：

```text
curl: (23) Failure writing output to destination
```

原因是 `/usr/local/bin/kubectl` 原本是 Docker Desktop 留下的 symlink：

```text
/usr/local/bin/kubectl -> /mnt/wsl/docker-desktop/cli-tools/usr/local/bin/kubectl
```

这个目标不适合直接覆盖写入。修复方式：

```bash
rm -f /usr/local/bin/kubectl
curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${kubectl_version}/bin/linux/amd64/kubectl"
chmod +x /usr/local/bin/kubectl
```

### VS Code Server 首次初始化很慢

第一次在 WSL 里执行：

```bash
code --version
```

会触发：

```text
Installing VS Code Server for Linux x64
Downloading...
Unpacking...
```

这属于 Remote - WSL 首次初始化。完成后再 `code .` 会快很多。

## 迁移后的日常工作流

进入 WSL：

```bash
wsl -d Ubuntu
```

打开项目：

```bash
cd ~/projects/agentcube
code .
```

同步 upstream：

```bash
git fetch upstream main
git switch intern
git rebase upstream/main
```

记录类工作提交到 fork `intern`：

```bash
git status
git add internship-reports PROGRESS.md
git commit -m "docs: update internship records"
git push --force-with-lease origin intern:intern
```

准备 upstream PR 时，从最新 upstream main 创建干净分支：

```bash
git fetch upstream main
git switch -c <topic-branch> upstream/main
```

## 验证清单

迁移后先跑这些轻量检查：

```bash
go version
gofmt -h
make --version
gcc --version
helm version --short
kubectl version --client=true
docker --version
git remote -v
git status --short --branch
```

进入 AgentCube 仓库后，按改动范围选择测试：

```bash
make fmt
go test ./pkg/workloadmanager -count=1
helm lint manifests/charts/base
git diff --check
```

完整构建可以后续再跑：

```bash
make build-all
```

> 分析：刚迁移环境时先用轻量检查确认工具链、路径、Git remote 和工作区状态。不要一上来跑最重的 e2e，否则环境问题和项目问题容易混在一起。
