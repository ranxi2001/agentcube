# 开源贡献与社区讨论格式标准

日期：2026-06-15

这个文档用于固定我们后续参与 AgentCube upstream 社区时的格式标准，避免 issue、proposal、PR 或 review comment 因为格式不符合社区习惯而返工。

依据来源：

- `CONTRIBUTING.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/bug-report.md`
- `.github/ISSUE_TEMPLATE/enhancement.md`
- `.github/ISSUE_TEMPLATE/question.md`
- `.github/ISSUE_TEMPLATE/good-first.md`
- `docs/design/*.md`
- 各目录 `OWNERS`

## 总原则

- upstream issue、PR、proposal、review comment 使用英文；中文分析和实习过程记录放在 `internship-reports/`。
- 先搜索已有 issue / PR / discussion，并记录 `PR 认领 @`，避免重复提案或重复实现。
- 大功能先讨论设计，小修复直接走 issue + PR。
- PR 必须来自干净 topic 分支，不从 fork `main` 直接提交。
- 每个 PR 只做一个主题，避免把实习报告、原始 benchmark 日志、中文-only 笔记混进 upstream PR。
- 使用 AI 工具辅助可以，但作者必须理解每一处改动，并在 PR 的 `Special notes for your reviewer` 中披露。
- 回复 review comment 时应由作者自己直接回复，不依赖 AI 生成回复。

## 社区角色与评论权重

读长 issue / PR 时，先判断说话者角色，不要把 bot 提示或 AI review 当成维护者结论。以下是 #366 中观察到的 AgentCube 社区运行方式：

| 类型 | 常见账号 / 标识 | 真人/自动化 | 作用 | 阅读方式 |
| --- | --- | --- | --- | --- |
| PR 作者 | @lyuyun | 真人 | 提案、解释设计、按 review 修改分支 | 代表当前 PR 方案，不等于维护者最终共识 |
| 贡献者 | @Abhinav-kodes、@HarshitPal25、@Sanchit2662 | 真人 | 提 issue、认领任务、补充方案或复现 | 可作为上下文和协作信号；先查是否已 `/assign` |
| 维护者 / reviewer | @acsoto、@RainbowMango、@hzxuzhonghu | 真人 | 提架构、正确性、范围和社区方向意见 | 权重高；明确技术意见应优先进入我们的总结 |
| approver | 例如 bot 提示 docs/OWNERS 需要 @kevin-wangzefeng | 真人 | 用 `/approve` 满足 OWNER 审批 | 需要按 bot 提示等待或请求，不要随意打扰 |
| 社区流程 bot | @volcano-sh-bot | 自动化 | 请求 reviewer、加 label、提示 OWNER 审批状态 | 流程信号；不是技术判断 |
| merge gate | `tide` check | 自动化 | 检查是否具备 `approved`、`lgtm`、CI 通过等合并条件 | 合并门禁；不是 reviewer 意见 |
| CI / 覆盖率 bot | @codecov-commenter、GitHub Actions checks | 自动化 | 报告 coverage、lint、test、e2e、codegen 状态 | 当作验证证据；失败要看具体日志 |
| AI reviewer | @gemini-code-assist[bot]、@copilot-pull-request-reviewer[bot] / Copilot | AI 自动化 | 自动审查文档/代码，指出潜在问题 | 可作为检查清单；不能当作维护者共识，采纳前必须人工验证 |

评论权重建议：

1. 真人维护者 / reviewer 的明确意见最高。
2. OWNER approve、`/lgtm`、`/approve` 和 `tide` 状态决定能否合并。
3. PR 作者回复说明当前方案如何调整。
4. 其他贡献者评论说明社区需求和协作关系。
5. 自动化 bot 说明流程状态。
6. AI reviewer 只作为辅助发现问题。

## 选择正确的社区入口

| 场景 | 使用入口 | 标准格式 |
| --- | --- | --- |
| 复现明确的 bug | GitHub Bug Report issue | `What happened`、`Expected`、`Reproduce`、`Environment` |
| 新能力或增强 | Enhancement issue | `What would you like to be added`、`Why is this needed` |
| 设计问题或方向讨论 | GitHub Discussions 或 design proposal | Motivation、Goals、Non-Goals、Use Cases、Design Details、Alternatives |
| 小代码修复 | PR | 官方 PR template + 测试结果 + 关联 issue |
| benchmark / 实验反馈 | Issue comment 或 proposal 附录 | 测试口径、环境、结果、限制、下一步 |
| 首次贡献任务 | good first issue | 先 `/assign`，确认无人重复做 |

## Bug Issue 格式

使用 `.github/ISSUE_TEMPLATE/bug-report.md`。

```md
**What happened**:

Describe the observed behavior. Include the exact error message, status code, log line, or command output when possible.

**What you expected to happen**:

Describe the expected behavior.

**How to reproduce it (as minimally and precisely as possible)**:

1. ...
2. ...
3. ...

**Anything else we need to know?**:

Add related logs, screenshots, suspected root cause, or workaround.

**Environment**:

- agentcube version:
- Kubernetes version:
- Others:
```

我们的补充要求：

- 复现步骤必须能被 reviewer 执行。
- 不贴真实 token、kubeconfig、API key、Redis password。
- 如果是 benchmark 或环境兼容问题，要写 OS、kernel、glibc、CPU、`/dev/kvm`、Kubernetes 版本。

## Enhancement Issue 格式

使用 `.github/ISSUE_TEMPLATE/enhancement.md`。

```md
**What would you like to be added**:

Describe the requested capability or behavior.

**Why is this needed**:

Explain the user pain, operational gap, or design motivation.
```

建议额外补充：

```md
**Possible implementation direction**:

**Alternatives considered**:

**Compatibility / migration impact**:

**Related issues / PRs**:
```

## Question / Discussion 格式

使用 `.github/ISSUE_TEMPLATE/question.md` 或 Discussions。

```md
**Please provide an in-depth description of the question you have**:

**What do you think about this question?**:

**Environment**:

- agentcube version:
- Kubernetes version:
- Others:
```

我们的标准：

- 不只问“能不能做”，要先写自己的理解和初步判断。
- 如果问题来自实验，要附测试口径和已排除的原因。
- 如果希望维护者拍板，要列出 2-3 个可选方案和 tradeoff。

## Design Proposal 格式

大功能或架构方向应参考 `docs/design/agentcube-proposal.md`、`docs/design/auth-proposal.md`、`docs/design/runtime-template-proposal.md`。

推荐结构：

```md
---
title: <Proposal Title>
authors:
  - "@your-github-id"
reviewers:
  - TBD
approvers:
  - TBD
creation-date: YYYY-MM-DD
---

# <Proposal Title>

## Motivation

## Goals

## Non-Goals

## Use Cases

## Proposal

## Design Details

## API / CRD Changes

## Compatibility

## Security Considerations

## Observability

## Testing Plan

## Alternatives Considered

## Open Questions
```

注意：

- 只要涉及 CRD、API、认证、调度、SnapStart、RuntimeClass、Kubernetes controller 行为，都应说明兼容性和测试计划。
- 如果只是 benchmark 设计，可以不新建完整 design doc，先在相关 issue 中用结构化 comment 对齐口径。

## Benchmark / 实验反馈格式

适用于 #365 这类 benchmark issue，或 SnapStart / warm pool 讨论。

```md
## Benchmark scope

- What is measured:
- What is not measured:

## Environment

- OS:
- Kernel:
- glibc:
- CPU / vCPU:
- Kubernetes:
- Runtime / RuntimeClass:
- `/dev/kvm`:
- virtualization flags:

## Method

- Script / command:
- Iterations:
- Concurrency:
- Warm pool / cold start setting:

## Results

| Case | p50 | p95 | p99 | success rate | notes |
| --- | ---: | ---: | ---: | ---: | --- |

## Interpretation

## Limitations

## Suggested next step
```

关键要求：

- 明确区分 LLM / Agent 端到端耗时和 sandbox 基础设施耗时。
- 明确区分本机实测、官方数据、工程推断。
- 不同机器数据只能做相对参考，不能直接硬比绝对值。

## PR 格式

使用 `.github/PULL_REQUEST_TEMPLATE.md`。

````md
**What type of PR is this?**

/kind bug

**What this PR does / why we need it**:

**Which issue(s) this PR fixes**:
Fixes #

**Special notes for your reviewer**:

**Does this PR introduce a user-facing change?**:

```release-note
NONE
```
````

`What type of PR` 只能选合适的一类或少数几类：

- `/kind bug`
- `/kind cleanup`
- `/kind enhancement`
- `/kind security`
- `/kind documentation`
- `/kind feature`

`Special notes for your reviewer` 至少说明：

- 影响范围。
- 是否改 CRD / generated clients / Helm chart。
- 是否用了 AI 工具辅助。
- 是否有已知限制或没有覆盖的测试。

`release-note`：

- 无用户可见变化写 `NONE`。
- 有用户可见变化时，用一句话说明变化。

## PR 提交前检查清单

| 检查项 | 要求 |
| --- | --- |
| 分支 | 基于最新 `upstream/main` 的干净 topic 分支 |
| 范围 | 一个 PR 一个主题，不混入实习报告 |
| Issue | 有对应 issue 时写 `Fixes #...`；讨论或部分工作写 `Refs #...` |
| PR 认领 @ | PR 前确认 issue assignee、`/assign` 评论和已打开 PR；如果已有活跃认领人，优先做 review / 复现反馈，不重复实现 |
| 测试 | bugfix / feature 必须有单测或说明为什么无法加 |
| Go 格式 | 运行 `make fmt` 或相关 gofmt |
| 单测 | 至少跑相关包测试；通用命令是 `make test` |
| 代码生成 | 改 API / CRD 后跑 `make gen-all` 或 `make gen-check` |
| Helm | 改 chart 后跑 `make helm-template` / `make helm-lint`，如果本地目标可用 |
| 文档 | 用户可见行为变化要更新 docs / README / example |
| 安全 | 不提交 token、password、kubeconfig、真实 `.env` |
| AI 披露 | 使用 Codex / ChatGPT 辅助时，在 reviewer notes 中披露 |

## 自动化 Bot / CI 反馈处理

PR 提交后要先读自动化反馈，再等真人 review。不同 bot 的权重不同：

| 类型 | 示例 | 含义 | 处理方式 |
| --- | --- | --- | --- |
| 流程 bot | `volcano-sh-bot` | 加 label、请求 reviewer、提示 OWNERS / approval 状态 | 按提示补 label、等 reviewer，或请求合适 approver |
| 合并门禁 | `tide` | 检查是否满足 `lgtm`、`approved`、CI 通过等条件 | 不直接回复，先解决缺失条件 |
| CI checks | GitHub Actions | build、lint、codegen、e2e、DCO 等结果 | 失败要打开具体 job log，定位是代码问题还是环境问题 |
| 覆盖率 bot | `codecov-commenter` | 报告 project coverage、patch coverage、missing lines | 重点看 patch coverage 和 missing lines；仓库安装提示通常不是 PR 作者能修 |
| AI reviewer | Copilot / Gemini | 自动指出潜在问题 | 当作检查清单，采纳前要人工验证 |

Codecov 处理原则：

1. `Patch coverage` 低或有 missing lines 时，优先补小范围单测覆盖新增逻辑、错误分支和边界行为。
2. `Project coverage` 只是全仓覆盖率，不一定要求本 PR 独立修复。
3. `Please install Codecov app`、报告落后 main 等提示通常是仓库配置或基准报告问题，不要误判成代码 bug。
4. 本地不能跑完整 e2e 时，要在 PR 描述中明确说明环境缺口，例如缺少 kubeconfig、router / workload-manager 未启动。
5. 补测试后推到同一个 PR 分支，并在实习记录中保存 commit、测试命令和 bot 反馈。

## Reviewer / OWNER 规则

根据改动目录查 `OWNERS`：

| 目录 | 常见 reviewer / approver 来源 |
| --- | --- |
| `pkg/workloadmanager/` | `pkg/workloadmanager/OWNERS` |
| `pkg/router/` | `pkg/router/OWNERS` |
| `pkg/apis/` | `pkg/apis/OWNERS` |
| `docs/` | `docs/OWNERS` |
| `manifests/` | `manifests/OWNERS` |
| `test/` | `test/OWNERS` |

PR 中不必手动猜所有 reviewer，但要根据 bot 提示响应。机器人通常会提示需要哪些目录的 approver。维护者通过 `/lgtm` 和 `/approve` 完成 review 流程。

## Review Comment 格式

我们在别人 PR 下评论时，避免泛泛评价。使用：

```md
I tested / reviewed <area>.

Observation:
- ...

Concern:
- ...

Suggestion:
- ...

Evidence:
- command:
- result:
- environment:
```

如果只是提问：

```md
Question:

My understanding is ...

Would it be better to ... because ...?
```

## Issue 评论格式：认领任务

认领前先确认：

- issue 没有已打开的重复 PR。
- issue 没有活跃 assignee 正在做。
- 本地任务表已经记录 `PR 认领 @`；无人认领写 `待认领`，已有认领写具体 GitHub 用户名。
- 自己能在 1-3 天内给出初版。

评论格式：

```md
/assign

I would like to work on this.

My planned approach:
- ...

Initial test plan:
- ...
```

如果 issue 已有人 `/assign` 或有 open PR，优先做 review / 测试反馈，不要重复实现。

## 我们后续固定流程

1. 先在 `internship-reports/` 写中文分析和实验记录。
2. 再把可公开部分整理成英文 issue / comment / PR。
3. upstream PR 使用干净 topic 分支。
4. PR 前按本文档检查格式。
5. PR 后把链接、测试结果、review 反馈记录回日报。
