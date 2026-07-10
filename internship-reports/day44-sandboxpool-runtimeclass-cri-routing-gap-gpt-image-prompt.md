# Day44 SandboxPool RuntimeClass / CRI Routing Gap - GPT Image Prompt

生成一张 16:9 横版中文技术信息图，主题是解释 AgentCube discussion #430 与 proposal PR #431 中，RuntimeClass / CRI 路由缺口发生在哪里。

图片必须直接由 gpt-image-2 原生生成全部图形和文字，不要后期贴字。画面必须专业、清晰、适合放进开源架构 review 报告。使用浅灰白背景、深海军蓝标题、Kubernetes 蓝、AgentCube 绿色，以及红色/橙色风险高亮。扁平化系统架构风格，清晰箭头和分区，不要渐变背景，不要装饰性插画，不要无关 logo，不要代码编辑器截图。

画面标题必须清晰写成：
“SandboxPool 的 CRI 路由缺口发生在哪里？”

副标题：
“#430 快慢资源分层 → #431 节点侧实现”

整体构图分上下两层。

上层占约 28%，标题“原始 #430：职责分层没有问题”。画成两个并列区域：

左侧蓝色区域：
“Kubernetes 慢资源层”
“管理节点、容量与 SandboxPool”
流程：
“SandboxPoolClass” → “SandboxPool CRD” → “节点资源预留”

右侧绿色区域：
“AgentCube 快资源层”
“管理会话，不让每个 session 都经过 Kubernetes API”
流程：
“创建 / 调用请求” → “选择资源池” → “node-ctl 创建 sandbox”

在两区下方用一句居中的总结：
“Kubernetes owns the pool；AgentCube owns the sessions”

下层占约 72%，标题“问题发生在 #431 的节点侧落地”。画一个大号“工作节点 Node”容器。

节点内从左到右画出真实 Kubernetes 链路：

1. 蓝色组件“kubelet”
2. 箭头上的请求文字：
“RunPodSandbox”
“runtime_handler = placeholder”
3. 深蓝组件“节点唯一 CRI endpoint”
组件内写：
“/run/containerd/containerd.sock”
“containerd 总机”
4. containerd 向上分出一条正常绿色支路：
“普通 handler” → “runc / 常规 Pod”
5. containerd 向右分出一条橙色支路：
“placeholder handler”

在“placeholder handler”与右侧 placeholder-agent 之间放置最醒目的红色虚线断点框，标题必须写：
“缺失的集成层 ？”

断点框内只列三个简短候选：
“containerd shim / sandboxer”
“CRI dispatch proxy”
“节点全局 CRI proxy”

断点框右侧画独立红橙色组件：
“placeholder-agent”
“/run/sandbox-pool/cri.sock”
“自定义 CRI interception”

placeholder-agent 再向右连接两个组件：

- “Static Pod manifest”
  小字：“锁定 scheduler 资源”
- “node-ctl”
  小字：“管理 sandbox 与 node-level cgroup”

节点区域左下角放一个小型错误示意，红色叉号：
“误解”
“RuntimeClass 会让 kubelet 直接切换 CRI socket”

节点区域右下角放一个小型事实说明，绿色对号：
“事实”
“RuntimeClass 只把 handler 名称传给同一个 CRI runtime”

底部使用红色警示横条，必须清晰写：
“没有这层转接，placeholder-agent 收不到 RunPodSandbox / CreateContainer，自定义资源调整不会执行。”

视觉要求：

- 关键问题必须明确定位在 containerd 的 placeholder handler 与 `/run/sandbox-pool/cri.sock` 之间，不要把红色断点放在 #430 控制平面、SandboxPool CRD 或 node-ctl 上。
- 箭头方向明确，组件不重叠，文字不压线。
- 中文必须清晰可读，英文代码词保持准确，尤其是 `RuntimeClass`、`runtime_handler`、`RunPodSandbox`、`CreateContainer`、`containerd`、`placeholder-agent`、`node-ctl`。
- 不要把 kubelet 画成能针对单个 RuntimeClass 直接选择另一个 CRI socket。
- 不要把问题描述成 native VPA 或 Static Pod resize 问题；那是已经澄清的上一个问题。本图只解释 RuntimeClass / CRI integration contract。
- 避免过多小字，保持报告级信息密度和留白。
