---
name: loop-dev-executor
description: "[V3] 开发执行器。按 PRD.json 逐 task 开发，通过单元测试和 E2E 冒烟测试双重验证。当用户说'开发任务'、'执行开发'、'按 PRD 开发'时触发。"
---

# Dev Executor — 开发执行器

## 概述

按 `Docs/PRD.json` 逐 task 开发，通过单元测试（白盒闸）和 E2E 冒烟测试（用户闸）双重验证。

## 启动流程

1. 读取 `Docs/PRD.json`，找到 ID 最前的 `passes: false` 且 `status: pending` 的 task
2. 跳过 `superseded_by` 不为 null 的 task（已被取代）
3. 检查 `Docs/PROTOTYPE_REF.md` 是否存在：
   - 存在 → 开发时对照原型对应区块的 UI/交互实现
   - 不存在 → 纯按 PRD description 开发
4. 将 task 的 `status` 改为 `"in_progress"`

## 标准单步循环

对每个 task 严格执行以下步骤：

### 1. 理解需求
- 读取 task 的 `description`、`acceptance_criteria`、`integration_mount`
- 如有原型引用（PROTOTYPE_REF.md），读取对应区块的设计规范
- 对照 `Docs/AGENTS.md` 确认技术栈约束和命名规范

### 2. 开发代码
- 编写/修改 `integration_mount` 指定的文件及相关依赖
- 确保新组件挂载到活跃路由（零孤岛原则）
- 遵循项目已有代码风格

### 3. 白盒闸：单元测试
- 编写/更新 `unit_test_command` 对应的测试文件
- 运行 `unit_test_command`，必须退出码 0
- 如有 lint/tsc 检查，一并运行通过
- 失败 → 读取错误信息 → 修复 → 重跑，直到全绿

### 4. 冒烟闸：E2E 快速验证
- 编写/更新 `e2e_test_command` 对应的测试文件
- E2E 测试必须以 `page.goto(task.e2e_target_url)` 为起点
- 断言层次：L1（元素存在）+ L2（内容非空）即可
- 运行 `e2e_test_command`，必须退出码 0
- 失败 → 修复前端代码 → 重跑

### 5. 落盘
- 更新 PRD.json：`passes: true`、`status: "completed"`
- Git commit：`feat: implement [TASK-ID] - [user_story 简述]`
- 更新 `Docs/loop-progress.json`

### 6. 发现遗漏
如果开发过程中发现依赖功能不在 PRD 中：
- 追加新 task 到 PRD.json 末尾（`passes: false`）
- 同步追加对应 scene 到 JOURNEYS.json
- 在 description 中标记 `[DISCOVERED by TASK-XXX]`

## 工程约束

- **单 task 开发**: 一次只开发 1 个 task，禁止同时改多个不相关功能
- **零孤岛**: 新组件必须挂载到活跃路由，无引用 = 未交付
- **编译期阻断**: `npm run build` 必须通过，不允许有 unused export 警告
- **禁止带错提交**: 有 lint/tsc/测试报错时不允许 git commit
- **原型对齐**: 有原型时，UI 实现必须与原型视觉一致（颜色、间距、布局）

## 进度更新

每个 task 完成后更新 `Docs/loop-progress.json`:
```json
"dev_executor": {
  "status": "in_progress",
  "tasks_completed": ["TASK-000", "TASK-001"],
  "current_task": "TASK-002",
  "commits": 2
}
```

## ❌ 不要做的事

- 不要修改 PRD.json 中的任何内容——它是合同，只读
- 不要跳过单元测试或 E2E 冒烟测试——测试是验收的门槛，不是可选项
- 不要基于「我觉得合理」修改实现方案——严格按 PRD.tasks 执行
- 不要忽略编译/构建错误继续下一步——错误必须被修复
