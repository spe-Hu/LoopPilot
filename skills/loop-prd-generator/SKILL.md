---
name: loop-prd-generator
description: "[V3] PRD产品需求文档生成器。支持原型驱动、逆向（已有代码）、正向（从零开始）三种入口生成 PRD.json。当用户说'生成PRD'、'创建需求文档'、'从原型生成PRD'时触发。"
---

# PRD Generator — 产品需求文档生成器

## 概述

生成/更新 `Docs/PRD.json`，支持三种入口：原型驱动、逆向（已有代码）、正向（从零开始）。

## 入口检测（每次执行前先检查）

1. 扫描项目根目录和 `Docs/` 下的所有 `.html` 文件
2. 检查是否已有 `src/` 或 `package.json` 等代码文件

| 检测结果 | 行为 |
|---------|------|
| 0 个 HTML + 有代码 | **逆向分支** |
| 0 个 HTML + 无代码 | **正向分支** |
| 1 个 HTML | 向用户确认："发现 xxx.html，这是原型文件吗？" |
| 多个 HTML | 列出所有让用户选择 |
| 用户主动提供路径 | 直接走**原型驱动分支** |

**原则**: 不猜测，有疑问就问用户。

## 原型驱动分支

原型文件是"真相来源"。执行步骤：

1. **读取原型**: 解析 HTML 结构、CSS 变量、JS 交互逻辑
2. **提取设计资产**: 颜色系统、组件结构、页面路由、交互流程
3. **提问补充**（精简，仅问原型不能覆盖的）:
   - 哪些功能是"样子货"（纯 UI 无逻辑）？
   - 技术栈确认（原型 vs 实际框架）
   - 需要补充的功能？
4. **一次性生成**:
   - `Docs/AGENTS.md`（design tokens + 组件规范）
   - `Docs/PRD.json`（每个功能区块 → 一个 task）
   - `Docs/JOURNEYS.json`（从交互流程推导场景）
   - `Docs/PROTOTYPE_REF.md`（仅原型 >1000 行时生成）

## 逆向分支

扫描代码库 → 推导功能清单 → 判断 passes 状态（已实现且无硬编码→true，缺失/有缺陷→false）→ 生成 PRD.json + JOURNEYS.json。

## 正向分支（借鉴 Brainstorm Skill）

**不直接生成**，先通过结构化提问：

每次只问 1 个问题，优先选择题：
1. 产品定位（核心问题 + 目标用户）
2. 核心功能边界（MVP 必须功能）
3. 技术栈
4. 数据模型（核心实体）
5. 关键用户旅程
6. 约束与非功能需求
7. 成功标准

够了就停，不够就追加。然后一次性生成 AGENTS.md + PRD.json + JOURNEYS.json。

## PRD.json 完整字段规范

### 顶层结构

```json
{
  "project_name": "string (必填)",
  "version": "string (必填)",
  "last_updated": "YYYY-MM-DD (必填)",
  "total_tasks": "number (必填)",
  "summary": {
    "passes_true": "number",
    "passes_false": "number",
    "description": "string"
  },
  "tasks": [ /* Task 对象数组 */ ]
}
```

### Task 对象（14 个字段）

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `id` | string | ✅ | 唯一标识，如 TASK-001 |
| `user_story` | string | ✅ | "作为[角色]，我希望[功能]，以便于[价值]" |
| `description` | string | ✅ | 详细功能描述，指出修改/创建哪些文件 |
| `status` | string | ✅ | "pending" / "in_progress" / "completed" |
| `passes` | boolean | ✅ | 验收是否通过 |
| `supersedes` | string[] | ✅ | 取代的旧 task ID，无则为 [] |
| `superseded_by` | string\|null | ✅ | 被谁取代，无则为 null |
| `integration_mount` | string | ✅ | 核心挂载文件路径 |
| `e2e_target_url` | string | ✅ | E2E 目标页面 URL |
| `integration_assertion` | string | ✅ | 集成验收断言描述 |
| `unit_test_command` | string | ✅ | 单元测试命令 |
| `e2e_test_command` | string | ✅ | E2E 测试命令 |
| `acceptance_criteria` | object[] | ✅ | 结构化验收标准（见下方） |
| `journey_scenes` | string[] | ✅ | 关联的 JOURNEYS scene ID |

### acceptance_criteria 结构

```json
[
  { "level": "L1-existence", "rule": "元素 .xxx 必须存在且可见" },
  { "level": "L2-nonempty", "rule": "表格 tbody 必须有数据行" },
  { "level": "L3-structure", "rule": "列表至少 3 项" },
  { "level": "L4-quality", "rule": "内容不得包含占位符/乱码/undefined" }
]
```

### Task 对象完整示例

```json
{
  "id": "TASK-003",
  "user_story": "作为用户，我希望看到数据分析报告，以便于了解业务趋势",
  "description": "实现报告页面，包含数据表格和图表组件。需创建 src/components/ReportTable.tsx 和 src/components/Chart.tsx，挂载到 src/app/reports/page.tsx。",
  "status": "pending",
  "passes": false,
  "supersedes": [],
  "superseded_by": null,
  "integration_mount": "src/app/reports/page.tsx",
  "e2e_target_url": "/reports",
  "integration_assertion": "报告页面成功渲染，表格和图表组件可见可交互",
  "unit_test_command": "npx vitest run src/components/ReportTable.test.ts",
  "e2e_test_command": "npx playwright test tests/e2e/reports.spec.ts",
  "acceptance_criteria": [
    { "level": "L1", "rule": "#report-table 和 #chart 元素必须存在" },
    { "level": "L2", "rule": "#report-table tbody 必须有数据行" },
    { "level": "L3", "rule": "表格至少 3 行数据，图表至少渲染 1 个数据点" },
    { "level": "L4", "rule": "数据不得为 NaN/undefined/占位符" }
  ],
  "journey_scenes": ["SCENE-005", "SCENE-006"]
}
```

## 完整性保障（3 层安全网）

### 层 1：生成时自检

生成 PRD.json 后立即执行以下检查，未通过 → 自动补充 → 再检：
- [ ] 每个数据实体是否有 CRUD 四个操作的 task？
- [ ] 每个页面路由是否至少被一个 task 覆盖？
- [ ] 每个 task 是否有对应的 JOURNEYS scene（journey_scenes 非空）？
- [ ] 核心用户旅程是否完整（从打开 app 到完成主任务）？
- [ ] 错误处理场景是否有 task（空状态、网络错误等）？
- [ ] 基础设施 task 是否存在（TASK-000 测试环境 + TASK-001 测试桩）？

### 层 2：开发中发现

dev-executor 开发时发现依赖功能遗漏 → 追加 task + scene + 标记 `[DISCOVERED]`。

### 层 3：验收后覆盖审计

journey-runner 执行后输出未覆盖的 task 和孤立 scene 清单。

## 冲突解决

- 新旧 task 冲突时，通过 `supersedes` 显式声明，以最新 task 为准
- 被取代的旧 task 标记 `superseded_by`，保留但不参与开发
- 每个 task 必须引用至少 1 个 JOURNEYS scene

## 进度更新

执行完成后更新 `Docs/loop-progress.json`:
```json
"prd_generator": {
  "status": "completed",
  "tasks_created": 12,
  "scenes_created": 15,
  "branch": "prototype-driven"
}
```

## ❌ 不要做的事

- 不要修改已有代码文件——PRD 生成器只产出文档，不触碰实现
- 不要基于主观想象添加功能——所有功能必须有原型/代码/用户输入作为来源
- 不要在 PRD.json 生成后追加额外功能——生成即锁定，如需补充走新的一轮迭代
- 不要修改 JOURNEYS.json——这是 journey-author 的职责，不是 prd-generator 的
