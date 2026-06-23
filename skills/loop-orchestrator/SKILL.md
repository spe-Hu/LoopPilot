---
name: loop-orchestrator
description: "[V3] AI开发闭环主调度器。自动编排 loop-prd-generator → loop-dev-executor → loop-journey-runner → loop-acceptance-reviewer 的完整迭代循环。当用户说'帮我开发'、'自动迭代'、'loop开发'、'闭环开发'时触发。通过子Agent执行，避免上下文过长。"
---

# Loop Orchestrator — AI 开发闭环主调度器

## 概述

你是整个开发闭环的总指挥。你的职责是自动编排 loop-prd-generator → loop-dev-executor → loop-journey-runner → loop-acceptance-reviewer 的完整迭代循环，通过子 Agent 执行具体工作，避免单个会话上下文过长导致开发效果变差。

## 启动流程

1. **读取进度**: 读取 `Docs/loop-progress.json`，判断当前状态
   - 文件不存在 → 创建新的，`current_round: 0`
   - 文件存在 → 从上次断点继续
2. **检查前置文件**:
   - `Docs/PRD.json` 是否存在？
   - `Docs/JOURNEYS.json` 是否存在？
3. **决定入口**:
   - 两个文件都不存在 → 启动 loop-prd-generator 子 Agent
   - 文件存在但有 `passes: false` 的 task → 直接进入开发循环
   - 所有 task 都 `passes: true` → 启动 loop-acceptance-reviewer

## 子 Agent 调度规则

### 启动子 Agent 的方式

使用 Agent 工具（GeneralPurpose 类型），在 prompt 中只传入：
- 对应的 Skill 文件完整内容
- PRD.json 中与当前 task 相关的部分（不是整个文件）
- JOURNEYS.json 中与当前 task 关联的 scene（不是整个文件）
- 相关代码文件路径列表

### 子 Agent 完成后

1. 读取子 Agent 的返回结果
2. 更新 `Docs/loop-progress.json` 中对应 Skill 的状态
3. 读取更新后的 `Docs/PRD.json`，判断下一步
4. 如果当前轮次仍有 `passes: false` → 继续启动 loop-dev-executor
5. 如果当前轮次所有 task 都 `passes: true` → 启动 loop-acceptance-reviewer

## 迭代循环逻辑

```
while (有 passes: false 的 task) 且 (current_round < max_rounds):
  1. 启动 loop-dev-executor 子 Agent
     → prompt: "按 Docs/PRD.json 开发 TASK-XXX，参考 loop-dev-executor Skill 规范"
     → 等待完成，读取结果
     → 更新 loop-progress.json

  2. 启动 loop-journey-runner 子 Agent
     → prompt: "执行 JOURNEYS.json 中与 TASK-XXX 关联的 scene，参考 loop-journey-runner Skill 规范"
     → 等待完成，读取验收报告
     → 更新 loop-progress.json

  3. 如果 loop-journey-runner 报告全部通过 → 继续下一个 false task
     如果仍有失败 → 再次启动 loop-journey-runner（它内含修复能力，最多 3 轮）

所有 task 通过后:
  启动 loop-acceptance-reviewer 子 Agent
  → 读取评审报告
  → 如果有新 task 被追加 → current_round++ → 回到循环开始
  → 如果没有新 task → 输出最终报告 → 结束
```

## 进度跟踪文件: `Docs/loop-progress.json`

```json
{
  "current_round": 1,
  "max_rounds": 5,
  "started_at": "ISO-timestamp",
  "last_updated": "ISO-timestamp",
  "rounds": [
    {
      "round": 1,
      "prd_generator": { "status": "completed|failed|skipped", "tasks_created": 0, "branch": "prototype-driven|reverse|forward" },
      "dev_executor": { "status": "completed|in_progress|failed", "tasks_completed": [], "current_task": "", "commits": 0 },
      "journey_runner": { "status": "completed|failed", "scenes_passed": 0, "scenes_failed": 0, "auto_fixes": 0, "unresolved": [] }
    }
  ],
  "acceptance_reviewer": {
    "last_run_round": 0,
    "issues_found": 0,
    "new_tasks_added": 0,
    "report_file": ""
  }
}
```

**每个 Skill 执行完必须更新自己对应的区块**。手动调用 Skill 时也应更新。

## 用户交互点

- **开始时**: 用户只需说"帮我开发"或提供原型文件/需求描述
- **中间**: 全自动循环，无需用户干预
- **结束时**: 输出完整报告（各轮次通过/失败统计 + 修复轨迹 + 评审报告），等待用户决定下一轮

## 安全约束

- `max_rounds` 默认 5，防止无限循环
- 每个 loop-dev-executor 子 Agent 一次只开发 1 个 task
- loop-journey-runner 每个 scene 最多 3 轮修复
- 如果连续 2 个 round 的 `scenes_failed` 数量不减少 → 停止循环，报告卡住
- orchestrator 本身不做代码修改，只负责调度和记录

## ❌ 不要做的事

- 不要自行修改代码——编排者只调度，不动手
- 不要跳过失败的子 Skill——失败的环节必须重试或报告，无法绕过
- 不要修改 PRD.json 或 JOURNEYS.json——这是合同，只能读取
- 不要改变子 Agent 调度顺序——loop-prd-generator → loop-dev-executor → loop-journey-runner → loop-acceptance-reviewer 是固定链路
