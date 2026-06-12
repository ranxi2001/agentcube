# Day 7 实习记录：cage-bro 竞品跑通与延迟对比

## 基本信息

- 实习项目：AgentCube
- 实习方向：华为公司开源小组 / AgentCube 开源项目研究
- 日期：Day 7
- 今日主题：在当前机器上跑通 cage-bro，并与 AgentCube 沙箱延迟数据做同机对比
- 相关文件：
  - `internship-reports/benchmarks/cage_bro_latency_benchmark.py`
  - `internship-reports/benchmarks/cage_bro_latency_sequential_5_result.json`
  - `internship-reports/benchmarks/cage_bro_latency_concurrent_10_result.json`
  - `internship-reports/benchmarks/agentcube_latency_sequential_5_result.json`
  - `internship-reports/benchmarks/agentcube_latency_concurrent_10_result.json`

## 今天的问题

Day 6 尝试复现 forkd 时被当前机器环境挡住：

- 官方 forkd 二进制需要比 CentOS 8 自带 `glibc 2.28` 更新的 glibc。
- 当前云 VM 没有 `/dev/kvm`，CPU flags 没有 `vmx` / `svm`。
- forkd 的核心能力依赖 Firecracker microVM，当前机器无法给出有效实测数据。

但竞品分析不能只停在 forkd。我们可以先跑一个当前机器能跑的竞品，拿到同机相对比例，再把 forkd 上游数据作为“非同机公开 benchmark”放进对比框架里。

因此今天选择 cage-bro：

- 它不依赖 KVM。
- 它提供 REST API 和 E2B-compatible sandbox lifecycle。
- 它能在当前机器上通过源码构建运行。
- 它的隔离模型和 AgentCube / forkd 不同，正好可以帮助理解“低延迟来自哪里”。

## cage-bro 定位

仓库：

```text
https://github.com/aeroxy/cage-bro
```

README 对 cage-bro 的定位是：

```text
A sandboxed execution environment for AI agents.
Single Rust binary with browser, shell, code execution, file ops, and MCP server.
```

它不是 microVM runtime，而是进程级 agent tool runtime：

| 能力 | 说明 |
| --- | --- |
| code exec | Python / Node / Jupyter |
| shell | PTY / shell command |
| files | workspace 文件读写 |
| browser | Obscura / CDP |
| API | REST + MCP |
| E2B compatibility | 支持 lifecycle 形态的 `/sandboxes` API |
| isolation | Linux Landlock + rlimit + timeout；非 microVM |

这个隔离模型很重要。cage-bro README 明确说明它不是 microVM，不适合作为真正 adversarial code 的唯一边界。它更像“轻量工具运行时”，可以放在 Docker / VM / microVM 里面提高工具密度。

当前机器内核是 `4.18.0`，低于 Linux Landlock 所需的 `5.13`。所以本次 cage-bro 实测更接近：

```text
process runtime + rlimit/timeout + workspace
```

不能把它当成 KVM 隔离数据。

## 安装与构建过程

### 1. 官方二进制下载与失败

查询 release：

```bash
curl -L --max-time 30 https://api.github.com/repos/aeroxy/cage-bro/releases/latest
```

最新 release：

```text
0.2.0
```

下载 Linux x86_64 包：

```bash
curl -L --fail --max-time 60 \
  -o /tmp/cage-bro-linux-x86_64.tar.gz \
  https://github.com/aeroxy/cage-bro/releases/download/0.2.0/cage-bro-linux-x86_64.tar.gz
```

校验：

```bash
sha256sum /tmp/cage-bro-linux-x86_64.tar.gz
```

输出与 GitHub release metadata 一致：

```text
6f39a06170acd32ed0ed418a21a4361d76daf612abae7def896e5ef0bb9cee76
```

但执行官方二进制失败：

```text
cage-bro: /lib64/libm.so.6: version `GLIBC_2.29' not found
cage-bro: /lib64/libc.so.6: version `GLIBC_2.29' not found
cage-bro: /lib64/libc.so.6: version `GLIBC_2.30' not found
```

原因和 forkd 类似：当前 CentOS 8 的 `glibc 2.28` 太旧，不能直接运行上游预编译包。

### 2. 源码构建

先检查源码要求：

```bash
curl -L https://raw.githubusercontent.com/aeroxy/cage-bro/main/Cargo.toml
```

关键配置：

```text
edition = "2021"
rust-version = "1.89"
```

当前机器没有 Rust，因此安装 rustup：

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup-init.sh
sh /tmp/rustup-init.sh -y --profile minimal
. "$HOME/.cargo/env"
```

安装后：

```text
rustc 1.96.0
cargo 1.96.0
```

克隆源码：

```bash
git clone --depth 1 https://github.com/aeroxy/cage-bro.git /tmp/cage-bro-src
```

第一次构建失败：

```bash
cargo build --release -p cage-bro
```

错误：

```text
failed to find tool "c++": No such file or directory
```

原因：`zmq-sys` 构建依赖 C++ 编译器。

修复：

```bash
dnf install -y gcc-c++
```

第二次构建又失败：

```text
#[derive(RustEmbed)] folder '/tmp/cage-bro-src/crates/cage-bro/dashboard/dist/' does not exist
```

原因：源码中没有预构建 dashboard 静态资源，`RustEmbed` 需要 `dashboard/dist`。

修复：

```bash
cd /tmp/cage-bro-src/crates/cage-bro/dashboard
npm install
npm run build
```

然后重新构建：

```bash
cd /tmp/cage-bro-src
cargo build --release -p cage-bro
```

最终成功：

```text
Finished `release` profile [optimized]
```

## 跑通最小服务

启动 cage-bro：

```bash
/tmp/cage-bro-src/target/release/cage-bro serve --host 127.0.0.1 --port 18090
```

服务日志：

```text
Starting cage-bro host=127.0.0.1 port=18090
Listening on 127.0.0.1:18090
```

测试原生 code API：

```bash
curl -sS -i -X POST http://127.0.0.1:18090/v1/code/python \
  -H 'Content-Type: application/json' \
  -d '{"code":"print(\"ok\")"}'
```

返回：

```json
{"duration_ms":14,"exit_code":0,"stderr":"","stdout":"ok\n"}
```

测试 E2B-compatible lifecycle：

```text
POST /sandboxes
POST /sandboxes/{id}/exec
DELETE /sandboxes/{id}
```

这里有一个小坑：`/sandboxes/{id}/exec` 内部通过 `sh -c` 执行 command，直接写嵌套引号容易变成 `print(ok)`。最终使用：

```bash
printf 'print("ok")\n' | python3
```

这样能稳定得到：

```json
{"durationMs":16,"exitCode":0,"stderr":"","stdout":"ok\n"}
```

## Benchmark 设计

新增脚本：

```text
internship-reports/benchmarks/cage_bro_latency_benchmark.py
```

为了和 AgentCube Day 5 的测法对齐，cage-bro 不只测 `/v1/code/python`，而是走 E2B-compatible lifecycle：

```text
create sandbox -> exec Python -> delete sandbox
```

阶段：

| 阶段 | cage-bro API |
| --- | --- |
| `create_session_ms` | `POST /sandboxes` |
| `run_code_ms` | `POST /sandboxes/{id}/exec` |
| `reported_exec_duration_ms` | cage-bro 返回的内部执行时间 |
| `delete_session_ms` | `DELETE /sandboxes/{id}` |
| `total_ms` | create + run + delete |

运行命令：

```bash
python3 -m py_compile internship-reports/benchmarks/cage_bro_latency_benchmark.py

python3 internship-reports/benchmarks/cage_bro_latency_benchmark.py \
  --mode sequential \
  --count 5 \
  --output internship-reports/benchmarks/cage_bro_latency_sequential_5_result.json

python3 internship-reports/benchmarks/cage_bro_latency_benchmark.py \
  --mode concurrent \
  --count 10 \
  --concurrency 10 \
  --output internship-reports/benchmarks/cage_bro_latency_concurrent_10_result.json
```

## cage-bro 实测结果

### 顺序 5 次

结果文件：

```text
internship-reports/benchmarks/cage_bro_latency_sequential_5_result.json
```

汇总：

| 指标 | create | run code | internal exec | delete | total |
| --- | ---: | ---: | ---: | ---: | ---: |
| mean | 1.22 ms | 16.92 ms | 15.80 ms | 0.71 ms | 18.85 ms |
| p50 | 0.62 ms | 16.99 ms | 16.00 ms | 0.72 ms | 18.41 ms |
| p95 | 3.65 ms | 17.25 ms | 16.00 ms | 0.78 ms | 21.41 ms |
| min | 0.59 ms | 16.55 ms | 15.00 ms | 0.65 ms | 17.87 ms |
| max | 3.65 ms | 17.25 ms | 16.00 ms | 0.78 ms | 21.41 ms |

观察：

- create sandbox 几乎是 1ms 级别。
- 主要耗时来自启动 Python 进程并执行代码。
- 总延迟 p50 约 18ms。

### 并发 10 次

结果文件：

```text
internship-reports/benchmarks/cage_bro_latency_concurrent_10_result.json
```

汇总：

| 指标 | create | run code | internal exec | delete | total |
| --- | ---: | ---: | ---: | ---: | ---: |
| mean | 7.03 ms | 45.08 ms | 37.00 ms | 7.13 ms | 59.24 ms |
| p50 | 4.69 ms | 49.16 ms | 41.00 ms | 3.71 ms | 58.48 ms |
| p95 | 13.27 ms | 54.75 ms | 47.00 ms | 14.47 ms | 67.60 ms |
| min | 2.72 ms | 20.42 ms | 17.00 ms | 2.20 ms | 39.34 ms |
| max | 13.27 ms | 54.75 ms | 47.00 ms | 14.47 ms | 67.60 ms |

观察：

- 并发 10 时没有出现 AgentCube 那种 6-9 秒排队。
- create 和 delete 在并发下变成个位数到十几毫秒。
- run code p50 上升到 49ms，主要是多个 Python 进程并发启动和执行。
- 总延迟 p50 约 58ms，p95 约 68ms。

## 与 AgentCube 同机对比

AgentCube 数据来自 Day 5：

```text
internship-reports/benchmarks/agentcube_latency_sequential_5_result.json
internship-reports/benchmarks/agentcube_latency_concurrent_10_result.json
```

注意：这不是安全等价对比。

| 项目 | 本轮隔离模型 | 当前机器可运行性 |
| --- | --- | --- |
| AgentCube | k3s Pod + AgentCube Workload Manager / Router + SandboxWarmPool；未配置 microVM runtimeClass | 可运行 |
| cage-bro | 进程级 runtime；当前内核低于 Landlock 要求，主要视作 rlimit/timeout 路径 | 可运行 |
| forkd | Firecracker + KVM microVM snapshot fork | 当前机器不可运行，用上游公开数字 |

### 顺序 5 次

| 项目 | create p50 | run p50 | delete p50 | total p50 | total min |
| --- | ---: | ---: | ---: | ---: | ---: |
| AgentCube | 100.22 ms | 40.33 ms | 6.93 ms | 177.14 ms | 91.95 ms |
| cage-bro | 0.62 ms | 16.99 ms | 0.72 ms | 18.41 ms | 17.87 ms |

比例估算：

```text
AgentCube sequential total p50 / cage-bro sequential total p50
= 177.14 / 18.41
= 9.62x
```

如果只看最快值：

```text
AgentCube min / cage-bro min
= 91.95 / 17.87
= 5.15x
```

### 并发 10 次

| 项目 | create p50 | run p50 | delete p50 | total p50 | wall clock |
| --- | ---: | ---: | ---: | ---: | ---: |
| AgentCube | 7278.76 ms | 28.52 ms | 7.37 ms | 7315.21 ms | 9308.16 ms |
| cage-bro | 4.69 ms | 49.16 ms | 3.71 ms | 58.48 ms | 71.91 ms |

比例估算：

```text
AgentCube concurrent total p50 / cage-bro concurrent total p50
= 7315.21 / 58.48
= 125.09x
```

这个比例不能简单解释为“AgentCube 慢 125 倍”。更准确的解释是：

- AgentCube 当前 `warmPoolSize=2`，并发 10 时只有前两个请求吃到热池，其余请求等待 sandbox 补位。
- cage-bro 是进程级 sandbox，不需要 Kubernetes 调度、SandboxClaim、Router session、Pod ready 等流程。
- AgentCube 的隔离和编排边界更重；cage-bro 的延迟优势来自更轻的进程级模型。

## 引入 forkd 上游数据做估算

forkd 当前无法在这台机器上运行，所以只能使用上游 README 的公开 benchmark，并明确标注为“非同机实测”。

上游数字：

| 项目 | 场景 | 数字 |
| --- | --- | ---: |
| forkd | fork 100 microVM from warm parent | 101 ms wall-clock |
| forkd | memory delta per child | 0.12 MiB |
| forkd | live BRANCH pause p50 | 56 ms |

如果粗略把 forkd 的 100 个 microVM / 101ms 看成“每个 child 摊销约 1.01ms”，它和 cage-bro 的关系大概是：

```text
cage-bro concurrent total p50 / forkd amortized child spawn
= 58.48 / 1.01
= 57.90x
```

但这个估算只用于建立量级感，不能作为正式性能结论，因为：

- forkd 上游数字是 100 并发 fan-out，不是本机 count=10。
- forkd benchmark 主要测 spawn，不一定包含 exec 和 delete。
- forkd 是 KVM microVM，cage-bro 是进程级 sandbox。
- forkd 使用 warm parent snapshot，AgentCube 当前使用 warm pool，原语不同。

更合理的比较方式应该是：

```text
forkd:
  spawn/fork child
  exec print('ok')
  cleanup
  count=10 / count=100

AgentCube:
  create CodeInterpreter session
  run print('ok')
  delete session
  warmPoolSize=10 / warmPoolSize=100
  如果有 runtimeClass，开启相同隔离强度

cage-bro:
  create process sandbox
  exec print('ok')
  delete sandbox
```

只有这样才能区分：

- 编排层开销。
- sandbox 原语开销。
- Python 进程启动开销。
- 隔离强度带来的成本。
- warm 状态带来的收益。

## 今天的结论

1. cage-bro 在当前机器上可以跑通，但需要源码构建，官方二进制被 CentOS 8 的 glibc 版本卡住。
2. cage-bro 顺序 5 次总延迟 p50 约 `18.41 ms`，并发 10 次总延迟 p50 约 `58.48 ms`。
3. AgentCube 当前配置下，顺序 p50 约为 cage-bro 的 `9.62x`，并发 10 p50 约为 cage-bro 的 `125.09x`。
4. 这个差距主要来自模型不同：AgentCube 是 Kubernetes + Workload Manager + Router + warm pool，cage-bro 是单进程内的 process sandbox。
5. forkd 当前只能引用上游公开数字，不能做同机实测；它代表的是另一个方向：microVM 级隔离下用 snapshot CoW 把 fan-out 成本压低。

下一步更有价值的实验是：

- 调大 AgentCube `warmPoolSize` 到 10，重跑并发 10，看排队是否消失。
- 尝试跑 CubeSandbox；如果同样需要 KVM，则记录为和 forkd 同类 blocker。
- 在支持 `/dev/kvm` 的机器上复现 forkd，把上游数据替换为本机数据。
- 如果继续比较 cage-bro，补测 `/v1/code/python` 原生 API 和 Jupyter 长 session，观察是否能进一步降低 Python 启动成本。
