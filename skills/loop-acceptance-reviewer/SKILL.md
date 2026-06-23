---
name: loop-acceptance-reviewer
description: "[V3.1] 产品评审+迭代规划。6阶段全面评审：黑盒探索、白盒审查、UX问题分级、竞品Gap、**PRD/JOURNEYS强制追加**（第5阶段）、人类反馈整合。当用户说'产品评审'、'做验收'、'帮我评审'时触发。"
---

# Acceptance Reviewer — 产品评审 + 迭代规划

## 概述

对当前版本进行全面产品评审，发现 UX 问题、追加新任务到 PRD/JOURNEYS，整合人类反馈。

## 前置条件

- 应用已启动（`npm run dev`）
- `Docs/PRD.json` 和 `Docs/JOURNEYS.json` 存在且所有 task `passes: true`

## 第一阶段：真实浏览器黑盒探索

用 Playwright MCP 逐路由走过每个页面：

1. **导航**: `browser_navigate(url)`，观察加载过程
   - 有 Loading 状态？骨架屏？纯白屏？
2. **空状态**: 无数据时的引导是否友好？
3. **交互触发**: 点击所有按钮、展开/折叠、切换 Tab、打开/关闭 Modal
4. **错误场景**: 输入无效数据、断开网络，观察错误提示
5. **响应式**: 缩放视口到 375px / 768px / 1440px，`browser_snapshot()` 检查布局
6. **截图**: 每个路由截 3 张（默认/交互/错误状态）

**原型对比**（如有 PROTOTYPE_REF.md）：
- 将当前页面 snapshot 与原型做视觉对比
- 标记偏差：颜色不一致、间距偏差、缺少交互效果

## 第二阶段：代码级白盒审查

黑盒探索后，辅以源码审查：
- **孤岛组件**: `export` 但全项目无 `import` 的文件 → FAIL
- **死代码**: 未使用的 CSS class、未调用的函数
- **API 规范**: 是否统一使用 fetch wrapper（如 `apiFetch`）
- **错误处理**: 是否统一使用 `toast.error` 而非 `console.error`

## 第三阶段：UX 问题清单

按严重程度分级输出：

| 级别 | 定义 | 示例 |
|------|------|------|
| P0 阻断 | 功能不可用 | 页面白屏、数据丢失、按钮点击无响应 |
| P1 严重 | 交互断裂 | 提交后无反馈、数据不一致、路由跳转错误 |
| P2 体验 | 体验差 | 无 Loading 状态、错误提示不友好、响应式坍塞 |
| P3 美化 | 视觉问题 | 间距不一致、字体层级混乱、颜色不统一 |

每个问题包含：
```
- 位置: 路由 + 组件
- 截图: 文件路径
- 问题描述: 具体现象
- 建议修复: 具体方案（修改哪个文件、改什么）
```

## 第四阶段：竞品 Gap 分析（可选）

如用户要求，对比同类成熟应用：
- 功能完整度对比
- 核心竞争力差距（如高阶过滤、批量操作等）
- 输出缺失功能清单

## 第五阶段：PRD + JOURNEYS 同步追加（强制执行）

**⚠️ 这是必须执行的阶段，不允许跳过或只输出报告不写入文件！**

将所有发现的问题转化为新 task，**同时写入文件**：

### 问题分类处理规则

| 问题类型 | 处理方式 |
|---------|---------|
| P0 阻断 | **必须**追加到 PRD.json（`passes: false`） |
| P1 严重 | **必须**追加到 PRD.json（`passes: false`） |
| P2 体验 | **必须**追加到 PRD.json（`passes: false`） |
| P3 美化 | 记录在报告中，**不强制**追加 |
| 生产部署前清单 | **必须**追加到 PRD.json（`passes: false`） |
| 竞品 Gap 建议功能 | **必须**追加到 PRD.json（`passes: false`） |

### 原子操作（必须同时完成）

1. **追加 task 到 `Docs/PRD.json` 末尾**
   - `passes: false`、`status: "pending"`
   - 包含完整的 `acceptance_criteria`（L1~L4）
   - 如有冲突，通过 `supersedes` 声明取代
2. **追加对应 scene 到 `Docs/JOURNEYS.json`**
   - 包含 L1~L4 断言
   - 必须与 PRD task 一一对应
3. **更新 PRD.json 顶层元信息**
   - `last_updated`、`total_tasks`、`summary.passes_false`

### 生产部署前清单（必须追加的 Task）

以下内容**必须**从报告中的"下一步提示 → 生产部署前"部分提取，**全部转为 Task**：

```json
{
  "id": "TASK-XXX",
  "user_story": "...",
  "description": "...",
  "status": "pending",
  "passes": false,
  "priority": "P0-production",
  "acceptance_criteria": [...]
}
```

示例清单（根据实际项目调整）：
- 集成真实 LLM 服务（OpenAI/Anthropic API keys）
- 部署 TTS 本地服务或使用云服务
- 实现 PDF 解析后端逻辑
- 配置定时任务（文章自动抓取）
- 添加错误监控（Sentry）
- 配置环境变量（生产密钥）
- 数据库迁移到 PostgreSQL（生产环境）
- 添加 Rate Limiting（API 保护）

### 竞品 Gap 建议功能（必须追加的 Task）

从报告中的"竞品差距分析 → 建议功能"部分提取，**全部转为 Task**：
- 高级过滤器（按难度、标签、学习状态组合筛选）
- 批量操作（批量标记掌握、批量删除）
- 学习成就系统扩展
- 社交功能（学习小组、排行榜）
- 移动端适配

### 老 task 保护

已 `passes: true` 的 task **不可修改** passes 和 status。

## 第六阶段：人类反馈整合

当用户提出新想法/Bug/需求时：
1. 分析在现有架构下如何落地
2. 拆解为原子 task 追加到 PRD.json（`passes: false`）
3. 同步追加 JOURNEYS scene
4. 如与已有 task 冲突 → `supersedes` 声明

## 输出

### 验收报告: `Docs/Acceptance_Report_V[X.0].md`

报告**必须**包含以下章节，且内容必须与 PRD.json/JOURNEYS.json 实际写入的内容**完全一致**：

```markdown
# 产品验收报告 V[X.0]
执行时间: YYYY-MM-DD
原型对比: 有/无

## 执行摘要
- PRD 任务: X/Y 完成 (Z%)
- 新增 Task: N 个（全部已写入 PRD.json）

## UX 问题清单
### P0 阻断 (N 个) → 全部追加到 PRD
### P1 严重 (N 个) → 全部追加到 PRD
### P2 体验 (N 个) → 全部追加到 PRD
### P3 美化 (N 个) → 记录（不强制追加）

## 生产部署前清单（已追加到 PRD）
- [ ] TASK-XXX: ...
- [ ] TASK-YYY: ...

## 竞品差距分析（已追加到 PRD）
- [ ] TASK-XXX: 高级过滤器
- [ ] TASK-YYY: 批量操作

## 新增 Task 清单
### 已写入 PRD.json
- TASK-XXX: ... → 对应 JOURNEYS scene: SCENE-XXX
- TASK-YYY: ... → 对应 JOURNEYS scene: SCENE-YYY

## 覆盖完整性检查
- PRD task 总数: X
- 新增 task 数: N
- passes_false: M（必须 > 0 才能触发下一轮迭代）

## 下一步提示
- 新增了 N 个 task，passes_false = M
- 请触发 loop-orchestrator 继续开发
```

### 文件更新（必须验证）

完成评审后，**必须验证**以下文件已被修改：
- `Docs/PRD.json` — 新增 task 已写入，`passes_false` > 0
- `Docs/JOURNEYS.json` — 对应 scene 已写入
- `Docs/Acceptance_Report_V[X.0].md` — 报告已生成

**验证命令**：
```bash
# 检查 passes_false 是否 > 0
grep '"passes_false":' Docs/PRD.json
# 应该看到 passes_false: N（其中 N > 0）
```

## 进度更新

```json
"acceptance_reviewer": {
  "last_run_round": 1,
  "issues_found": 8,
  "new_tasks_added": 5,
  "report_file": "Docs/Acceptance_Report_V1.0.md"
}
```
