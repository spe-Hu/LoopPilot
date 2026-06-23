---
name: loop-journey-author
description: "[V3.1] 用户旅程脚本编写器。生成/更新 JOURNEYS.json 验收场景脚本，含 L1~L4 分层断言、数据播种、长时间等待。当用户说'生成测试场景'、'编写验收脚本'、'生成 JOURNEYS'时触发。"
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

### ⚠️ 强制参考示例文件

- `Docs/JOURNEYS.json` **必须严格遵循** `skills/loop-journey-author/examples/sample-journeys.json` 的结构
- 顶层是**数组**（不是对象），每个元素是一个 Scene 对象
- 每个 Scene 必须包含：
  - `scene_id`（SCENE-XXX 格式）
  - `clicks_script`（**必填，不能为空**，每个 step 必须有 `action` 字段）
  - `scene_name`（**必填，不能为 null 或空**）
- **禁止**自行设计其他结构（如用 `steps`/`description`/`expected_result` 代替 `clicks_script`）

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
| `scene_name` | string | ✅ | **场景名称，不能为空** |
| `user_goal` | string | ✅ | 用户在此场景的目标 |
| `data_mode` | string | ✅ | "real" / "seeded" / "any" |
| `setup` | object | ✅ | 数据播种配置（见下方） |
| `clicks_script` | object[] | ✅ | **交互步骤数组，每个 step 必须有 action，必填** |
| `teardown` | object | ✅ | 数据清理步骤 |
| `fallback` | object | ❌ | 降级策略配置 |

**⚠️ 关键约束**：
- `clicks_script` 是**必填字段**，不能为空数组 `[]`
- `clicks_script` 必须包含**至少一个**可执行步骤
- `clicks_script` 中每个 step 必须有 `action` 字段
- **文字描述（如 `description`、`steps`、`expected_result`）不能替代 `clicks_script`**

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

生成 JOURNEYS.json 后执行以下检查：

### 必检项（全部通过才能输出）

- [ ] **clicks_script 非空**：每个 scene 的 `clicks_script` 不能为空数组
- [ ] **scene_name 非空**：每个 scene 的 `scene_name` 不能为 null 或空字符串
- [ ] **step.action 必填**：每个 step 必须有 `action` 字段
- [ ] **至少一个断言**：每个 scene 的 `clicks_script` 必须包含至少 1 个 `assert_*` 类型的 action
- [ ] **无文字替代品**：不存在只有 `description`/`steps`/`expected_result` 但没有 `clicks_script` 的 scene

### 可选检查项

- [ ] 每个 PRD task 的 `journey_scenes` 中的 scene_id 都存在
- [ ] 每个 scene 是否都有 setup（至少空对象）和 teardown
- [ ] 每个 scene 的 clicks_script 是否包含 L1~L4 至少各 1 个断言
- [ ] 涉及长时间操作的 scene 是否有 `wait_for` + `checkpoint`
- [ ] `data_mode: "real"` 的 scene 是否有 `fallback` 配置

### 半成品场景识别与拦截

以下情况视为**半成品 scene**，必须修复后才能输出：

| 症状 | 原因 | 修复方式 |
|------|------|----------|
| `clicks_script: []` | 只有描述没有执行脚本 | 为每个 step 添加 `action` |
| `clicks_script` 缺失 | 用 `steps` 数组代替 | 将 `steps` 文字描述转为 clicks_script 格式 |
| `scene_name: null` | 场景命名遗漏 | 补充 scene_name |
| 只有 `expected_result` | 用结果描述代替过程 | 拆解为具体的交互步骤 |
| step 缺少 `action` | 结构不完整 | 为每个 step 补充 action 字段 |

**如果发现半成品 scene，必须修复后再输出 JOURNEYS.json**

## 双向约束

- 每个 scene 的 `scene_id` 必须被至少 1 个 PRD task 的 `journey_scenes` 引用
- 每个 PRD task 的 `journey_scenes` 中的 scene_id 必须存在
- 孤立的 scene 或空的 journey_scenes 都是错误

## 进度更新

```json
"journey_author": {
  "status": "completed",
  "scenes_created": 15,
  "scenes_updated": 3,
  "completeness_check": {
    "clicks_script_non_empty": true,
    "scene_name_non_empty": true,
    "has_assertions": true,
    "no_text_substitutes": true
  }
}
```

**注意**：只有当完整性检查全部通过后，才能更新进度为 `completed`

## ❌ 不要做的事

- 不要基于主观想象写断言——断言必须来自 PRD 的 acceptance_criteria 或实际代码行为
- 不要修改 PRD.json——只写 JOURNEYS.json，两者独立
- 不要写无 setup 或无 teardown 的 scene——每个 scene 必须有完整的生命周期
- 不要写与 PRD task 无关联的 scene——scene 必须服务于某个 task 的验收
- **不要输出半成品 scene**——clicks_script 不能为空，不能用文字描述替代可执行脚本
- **不要跳过 scene_name**——每个 scene 必须有非空的 scene_name
