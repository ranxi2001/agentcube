# Day 30 PR #387 Changes Infographic Prompt

生成一张精致、专业的 16:9 中文技术信息图，用于开源项目工程报告和 Pull Request review 复盘。

图片中必须准确出现主标题：
“PR #387：Warm Pool 兼容性升级”

图片中必须准确出现副标题：
“agent-sandbox v0.1.1 → v0.4.6｜真正变化是 runtime 模型”

整体使用暖白或极浅灰背景、清晰深色文字和克制的多色工程配色。AgentCube 控制面使用蓝色，新合同与正确路径使用青绿，真实 runtime 使用琥珀黄，Store 使用低饱和紫色；红色只用于标记旧合同在新版本下不再成立。禁止渐变、装饰光球、玻璃拟态、营销海报构图、吉祥物、无关 logo、密集小字和大圆角卡片。卡片圆角不超过 6px。画面要像严谨的架构 review 产物，不像宣传页。

顶部增加一条醒目的“关键纠偏”横条，必须准确写：
“旧版已经创建 SandboxClaim；#387 适配的是新的 warm-pool runtime contract。”

主体采用从左到右的五组变化，每组都用“更新前 → 更新后”表达，并配紧凑的技术对象图标、箭头和资源关系。重点突出第 2、3、4 组。

1. “依赖合同”
   必须出现：
   “agent-sandbox：v0.1.1 → v0.4.6”
   “Kubernetes：v0.34.1 → v0.35.4”
   “codegen / clients 同步”
   视觉：依赖包、CRD 和 generated client 文档同步升级，不要画成只改一行版本号。

2. “池化单位”
   更新前必须写：
   “SandboxWarmPool → Pod”
   更新后必须写：
   “SandboxWarmPool → Sandbox → Pod”
   视觉：左侧池中是多个 Pod；右侧池中是多个 Sandbox，每个 Sandbox 再拥有一个 Pod。用粗箭头突出这是核心 runtime contract 变化。

3. “adoption 与身份”
   更新前必须写：
   “adopt 预热 Pod”
   “Claim.name = Sandbox.name”
   更新后必须写：
   “adopt 预热 Sandbox”
   “名称 / UID 保持不变”
   “Claim.status.sandbox.name → adopted Sandbox”
   视觉：右侧清楚区分蓝色 SandboxClaim 控制身份与琥珀色 adopted Sandbox 运行身份，中间用 status bridge 连接。

4. “readiness、Pod 与 Store”
   更新前必须写：
   “同名 Sandbox informer watcher”
   “Pod informer cache”
   更新后必须写：
   “live GET Claim → Sandbox → Pod”
   “2m context 覆盖两次 GET”
   “控制身份：Kind / Name = Claim”
   “运行身份：Sandbox UID / Pod EntryPoints”
   视觉：把旧 watcher 画成红色虚线，把新 live GET 链画成蓝绿实线；Store 用一条清晰分隔线区分 control identity 与 runtime identity。

5. “生命周期与验证”
   必须出现共同动作：
   “Delete / GC 仍删除 SandboxClaim”
   更新前必须写：
   “replacement Pod”
   更新后必须写：
   “replacement Sandbox → Pod”
   验证区必须写：
   “E2E：ownerRef / UID / cleanup / refill”
   “CI：ubuntu-24.04 + non-mTLS CodeInterpreter job”
   “exact head 95fae1f：12/12 checks”
   视觉：删除 Claim 后级联清理 adopted Sandbox / Pod，再由 WarmPool 新建 replacement；不要画成把原 Sandbox 归还池中。

底部增加一条“保持不变”信息带，必须准确写：
“保持不变：WorkloadManager 仍创建 SandboxClaim｜Delete / GC 仍删除 Claim｜Router 仍从 Store 读取 EntryPoints”

底部再增加一条较小的范围边界，必须准确写：
“范围外：#433 auth / RBAC 产品修改｜agent-sandbox v0.5.x”

右下角增加一个小型影响表，必须准确写：
“Runtime 合同变化：高”
“公开调用流程：保持”
“验证覆盖：高”

所有可见文字必须是清晰可读的简体中文或上面指定的英文技术标识，拼写准确。必须保留 `AgentCube`、`SandboxWarmPool`、`SandboxClaim`、`Sandbox`、`Pod`、`WorkloadManager`、`Router`、`Store`、`EntryPoints`、`ownerRef`、`UID`、`live GET`、`CodeInterpreter`、`RBAC`、`PR #387` 的原始拼写。不要水印。不要生成二维码。不要添加未在提示词中出现的版本号、PR 编号、性能数字或安全结论。
