# PROGRESS.md

这个文件是给 Agent 循环用的短记忆，不是日报。每次开始工作先读这里，每次结束只更新关键状态，避免下一轮从零开始。

## Goal

当前主线：参与 AgentCube upstream 社区，跟进 PR #385，并围绕 SnapStart / warm pool / sandbox benchmark 找可验证、低重复的贡献点。

## Last Run

- Day15 报告已补入 2026-06-17 14:30 线上会议任务：和 `FAUST-BENCHOU` 讨论 AgentCube 下一步计划，重点围绕 v0.2.0 umbrella issue #386。
- `internship-reports/todo.md` 已新增 P0 任务“讨论 AgentCube v0.2.0 下一步计划”，下一步是整理 #386 中文内部总结并明确会后是否发英文 proposal / review / test plan。
- 已核查 #386 中 `zhzhuang-zju` 的 agent-sandbox 适配提案：AgentCube 确实依赖 `sigs.k8s.io/agent-sandbox v0.1.1`；临时升级到 `v0.4.6` 会因 `controllers.SandboxPodNameAnnotation` 缺失编译失败，但 `SandboxWarmPool` / `SandboxClaim` 类型和核心字段仍存在。
- 已溯源 agent-sandbox 编译失败：`v0.2.1` 可编译，`v0.3.10+` 失败；直接原因是 `SandboxPodNameAnnotation` 从 `controllers` 包迁到公开 API 包 `api/v1alpha1`，深层背景是 warm pool 从 bare Pod adoption 重构为 full Sandbox CR adoption。
- Day15 报告已更新更强版 #386 英文 comment 草稿：最小常量修复 + 依赖升级可让 `v0.3.10`/`v0.4.6` 非 e2e 测试通过，但不保证运行；新版 warm pool 可能 adopt generated-name Sandbox，AgentCube 当前按 claim/sandboxName watch Ready 事件，存在漏通知/超时风险。
- #386 评论已发布：https://github.com/volcano-sh/agentcube/issues/386#issuecomment-4725375092；当前暂无 maintainer 回复。
- 已固化“issue/PR 分析优先脚本化”的偏好：`AGENTS.md`、`agentcube-issue-discussion`、`agentcube-pr-management` 都已加入脚本优先和持续优化 skill 的规则。
- 新增 `.agents/skills/agentcube-issue-discussion/scripts/thread_brief.py`，用于输出 compact Markdown 版 issue/PR 摘要；已用 #386 和 #385 验证，能捕捉 PR review 中的 `/assign` 信号。
- 已对 #386 中 FAUST-BENCHOU 的 Sandbox Sleep/Resume 提案做代码级分析并写入 Day15：当前实现是 idle/TTL 直接删除式 GC，不是 Ready -> Paused -> Ready；最小实现也要跨 API/CRD、store state、GC、WorkloadManager pause/resume、Router resume-before-proxy、agent-sandbox replicas=0/1 语义和 e2e。
- 已补充 #386 两个提案关系：agent-sandbox 适配是 Sleep/Resume 的底层兼容性 foundation；如果先按 v0.1.1 实现 Sleep/Resume，后续升级到 v0.3.10+/v0.4.6 可能因 SandboxClaim / warm pool / Ready condition 语义变化返工。
- PR #385 已按 Gemini 建议更新：`WarmPoolNotFound` condition 保留，但不再记录 Warning Event。
- PR #385 最新 commit `d885b4e` 已 push，DCO 漏签已用 `git commit --amend --no-edit --signoff` 修复。
- PR #385 Gemini thread 已回复，附了 focused tests、`go test ./pkg/workloadmanager` 和 `git diff --check`。
- PR #379 已读实现范围：CRD、controller、agentd Kuasar driver、artifact store、CodeInterpreter restore intent。
- PR #379 找到一个非重复 review 点：promotion 重置 `ReadyAt` 后，可能因 `snapshotStatusEqual` 不比较 `ReadyAt` 而没有持久化，导致 `RebuildAfter` 继续触发 rebuild。

## Current Blockers

- 当前机器没有 `/dev/kvm`，CPU 虚拟化 flags 未暴露，不能实测 Kuasar / MicroVM / forkd / CubeSandbox 的真实虚拟化路径。
- kind 标准 Kubernetes 在本机 kubelet cgroup/QoS 初始化处失败；KWOK 只能用于调度语义，不等同完整 K8s 实测。
- PR #385 当前主要等待 maintainer review、`/lgtm`、`/approve` 和 tide 合并门禁。

## Ruled Out

- 不再把 `WarmPoolNotFound` 当成需要 Warning Event 的稳定故障；它可能只是 controller 创建 warm pool 后 cache 尚未同步。
- 不重复评论 #379 里 Copilot 已经指出的 `ctrl.SetupSignalHandler()` 双调用问题。
- 不声称本机跑通过真实 SnapStart restore；当前只能做代码阅读、controller/unit test 级验证。

## Next

- 2026-06-17 14:30 参加线上会议前，整理 #386 中文内部总结：当前 v0.2.0 proposal、FAUST-BENCHOU 的 Sandbox Sleep/Resume、agent-sandbox 适配提案、可承担产出。
- 与 FAUST-BENCHOU 讨论 Sleep/Resume 时优先确认第一版语义：是否接受基于 `Sandbox.spec.replicas=0/1` 的 stop/recreate，`context` 是否仅指 workspace/PVC，是否新增 `pauseTimeout`，warm-pool-backed CodeInterpreter 是否纳入第一版。
- 建议把 #386 两个方向作为同一 v0.2.0 epic 的两个子任务讨论：先定 agent-sandbox target version / compatibility foundation，再做 AgentCube Sleep/Resume lifecycle。
- 跟踪 #386 maintainer 是否 triage agent-sandbox 适配为 dedicated sub-issue；有明确方向后再准备 compatibility audit PR 或最小修复 PR。
- 后续看 issue/PR 时先跑 `thread_brief.py <number>`；看 PR 再配合 `pr_status.py <number>`，如果流程重复就继续补脚本而不是手工重做。
- 优先把 #379 的 `ReadyAt` status equality 评论发到 PR，或先在临时分支补最小 controller unit test 验证。
- 继续跟踪 #385 的 CI、Codecov、tide、maintainer review，有反馈再小步处理。
- 如果继续做 benchmark，只跑当前环境能支撑的 AgentCube / k3s / controller 层测试，并明确“不包含真实 MicroVM/KVM restore”。

## Stop Conditions

- 同一个环境问题连续失败 3 次，例如 kind kubelet cgroup/QoS 或 `/dev/kvm` 缺失，不再硬调，转为记录 BLOCKED 并换机器/环境。
- 同一个 upstream PR 已有人明确认领并正在改同一问题，不开重复 PR，只做 review、复现或测试反馈。
- 如果只能基于推测发社区评论，先停止，补代码证据、测试证据或引用具体文件行后再发。
