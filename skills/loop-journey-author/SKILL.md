---
name: loop-journey-author
description: "[V3] 用户旅程脚本编写器。生成/更新 JOURNEYS.json 验收场景脚本，含 L1~L4 分层断言、数据播种、长时间等待。当用户说'生成测试场景'、'编写验收脚本'、'生成 JOURNEYS'时触发。"
---

# Journey Author — 用户旅程脚本编写器

## 概述

生成/更新 `Docs/JOURNEYS.json`，为每个 PRD task 创建对应的验收场景脚本。

## 启动流程

1. 读取 `Docs/PRD.json`，获取所有 task
2. 检查 `Docs/PROTOTYPE_REF.md` 是否存在：
   - 存在 → 交互步骤从原型的 JS 交互逻辑推导，断言目标从原型 DOM 结构推导
   - 不存在 → 纯按 PRD + 代码推导
3. 检查已有 JOURNEYS.json：
   - 不存在 → 全新生成
   - 存在 → 只为新增/修改的 task 补充 scene

## Scene 编写原则

- 每个 scene 对应 PRD.json 中至少 1 个 task 的 `journey_scenes`
- 场景必须从根路由 `/` 出发（除非 task 明确指定其他入口）
- 使用真实数据，不使用 Mock
- 断言必须覆盖 L1~L4 四个层次

## JOURNEYS.json 完整字段规范

### 顶层结构

```json
[
  /* Scene 对象数组 */
]
```

### Scene 对象

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `scene_id` | string | ✅ | 唯一标识，如 SCENE-001 |
| `scene_name` | string | ✅ | 场景名称 |
| `user_goal` | string | ✅ | 用户在此场景的目标 |
| `data_mode` | string | ✅ | "real" / "seeded" / "any" |
| `setup` | object | ✅ | 数据播种配置（见下方） |
| `clicks_script` | object[] | ✅ | 交互步骤数组（见下方） |
| `teardown` | object | ✅ | 数据清理步骤 |
| `fallback` | object | ❌ | 降级策略配置 |

### setup / teardown 结构

```json
{
  "description": "准备测试数据",
  "steps": [
    { "action": "seed_api", "params": { "endpoint": "POST /api/items", "body": {...} }, "assert_response": { "status": [200, 201] } },
    { "action": "seed_local_files", "params": { "path": "./test-data", "files": ["test.md"] } }
  ]
}
```

### clicks_script Step 结构

```json
{
  "step": 1,
  "action": "action_type",
  "selector": "CSS选择器或N/A",
  "payload": "值/文本/URL",
  "options": { /* 仅 wait_for 使用 */ },
  "message": "断言失败时的说明（仅 assert_* 使用）"
}
```

### 所有 Action 类型

| action | 说明 | selector | payload |
|--------|------|----------|---------|
| `goto` | 导航到 URL | N/A | URL 路径 |
| `click` | 点击元素 | CSS 选择器 | N/A |
| `type` | 输入文本 | CSS 选择器 | 输入内容 |
| `select` | 下拉选择 | CSS 选择器 | 选项值 |
| `hover` | 鼠标悬停 | CSS 选择器 | N/A |
| `scroll` | 滚动页面 | N/A | "down"/"up" |
| `wait_for` | 等待条件满足 | CSS 选择器 | 预期文本/状态 |

### wait_for 的 options

```json
{
  "timeout": 900,
  "strategy": "polling",
  "pollingInterval": 30,
  "checkpoint": true,
  "completionPattern": "completed"
}
```

### 断言 Action 类型（L1~L4）

| action | 层次 | 说明 | payload |
|--------|------|------|---------|
| `assert_visible` | L1 | 元素存在且可见 | 预期文本（可选） |
| `assert_not_empty` | L2 | 元素有内容 | 无 |
| `assert_min_count` | L3 | 匹配元素数量 >= N | 最小数量（数字字符串） |
| `assert_structure` | L3 | 内容结构完整 | 结构描述 |
| `assert_no_placeholder` | L4 | 无占位符/乱码 | 无 |
| `assert_no_error` | L4 | 无错误指示文本 | 无 |

### fallback 结构

```json
{
  "allowed": true,
  "strategy": "seeded_data",
  "report_as": "DEGRADED"
}
```

### Scene 完整示例

```json
{
  "scene_id": "SCENE-003",
  "scene_name": "文件同步到飞书知识库",
  "user_goal": "将本地文件推送到飞书 Wiki 并确认同步成功",
  "data_mode": "real",
  "setup": {
    "description": "创建本地测试文件和 API 绑定",
    "steps": [
      { "action": "seed_local_files", "params": { "path": "./test-data/sync", "files": ["readme.md", "report.html"] } },
      { "action": "seed_api", "params": { "endpoint": "POST /api/bindings", "body": { "name": "测试同步", "localPath": "./test-data/sync" } }, "assert_response": { "status": [200, 201] } }
    ]
  },
  "clicks_script": [
    { "step": 1, "action": "goto", "selector": "N/A", "payload": "/bindings" },
    { "step": 2, "action": "assert_not_empty", "selector": "#binding-list", "message": "绑定列表不能为空" },
    { "step": 3, "action": "click", "selector": "[data-testid='sync-btn']", "payload": "N/A" },
    { "step": 4, "action": "wait_for", "selector": "#sync-status", "payload": "completed", "options": { "timeout": 60, "strategy": "polling", "pollingInterval": 5, "checkpoint": true } },
    { "step": 5, "action": "assert_min_count", "selector": "#sync-log li", "payload": "1", "message": "同步日志至少 1 条" },
    { "step": 6, "action": "assert_no_error", "selector": "body", "message": "页面不得出现错误文本" },
    { "step": 7, "action": "assert_no_placeholder", "selector": "#sync-result", "message": "同步结果不得包含占位符" }
  ],
  "teardown": {
    "steps": [
      { "action": "cleanup_api", "params": { "endpoint": "DELETE /api/bindings/{id}" } }
    ]
  },
  "fallback": { "allowed": true, "strategy": "seeded_data", "report_as": "DEGRADED" }
}
```

## 完整性自检

生成 JOURNEYS.json 后执行：
- [ ] 每个 PRD task 的 `journey_scenes` 中的 scene_id 都存在？
- [ ] 每个 scene 是否都有 setup（至少空对象）和 teardown？
- [ ] 每个 scene 的 clicks_script 是否包含 L1~L4 至少各 1 个断言？
- [ ] 涉及长时间操作的 scene 是否有 `wait_for` + `checkpoint`？
- [ ] `data_mode: "real"` 的 scene 是否有 `fallback` 配置？

## 双向约束

- 每个 scene 的 `scene_id` 必须被至少 1 个 PRD task 的 `journey_scenes` 引用
- 每个 PRD task 的 `journey_scenes` 中的 scene_id 必须存在
- 孤立的 scene 或空的 journey_scenes 都是错误

## 进度更新

```json
"journey_author": {
  "status": "completed",
  "scenes_created": 15,
  "scenes_updated": 3
}
```

## ❌ 不要做的事

- 不要基于主观想象写断言——断言必须来自 PRD 的 acceptance_criteria 或实际代码行为
- 不要修改 PRD.json——只写 JOURNEYS.json，两者独立
- 不要写无 setup 或无 teardown 的 scene——每个 scene 必须有完整的生命周期
- 不要写与 PRD task 无关联的 scene——scene 必须服务于某个 task 的验收
