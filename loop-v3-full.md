# Loop V3.0 — AI 开发闭环验收测试 Skill 体系

更新时间：2026-06-22

## 一、核心问题与解决方案

| 痛点 | V1/V2 问题 | V3 解决方案 |
|------|------------|-------------|
| 断言浅表化 | 只验证 UI，核心业务逻辑无覆盖 | 两层断言模型（PRD + JOURNEYS） |
| 长时间流程无覆盖 | 异步任务、等待场景无法验证 | wait_for action + 断点续测 |
| 提示词过大规则逃逸 | 500+ 行提示词，规则相互冲突 | 模块化 6 个独立 Skill |
| V1/V2 并行冲突 | 开发冒烟 vs 全量验收打架 | 双轨制（开发冒烟 + 全量验收） |
| 真实数据只有口号 | 测试数据 Hardcode，无真实性验证 | 数据播种 + 诊断优先降级 |

## 二、Skills 清单

| Skill | 职责 | 触发词 |
|-------|------|--------|
| loop-orchestrator | 主调度器，编排完整迭代循环（max_rounds=5） | "帮我开发"、"闭环开发" |
| loop-prd-generator | PRD+JOURNEYS 生成器，支持三种入口 | "生成PRD"、"从原型生成" |
| loop-dev-executor | 开发执行器，单元+E2E 双重验证 | "执行开发"、"按 PRD 开发" |
| loop-journey-runner | 验收测试+自动修复闭环（最多3轮） | "验收测试"、"全量测试" |
| loop-journey-author | JOURNEYS.json 场景脚本编写器 | "生成 JOURNEYS"、"编写验收脚本" |
| loop-acceptance-reviewer | 产品评审+迭代规划（6阶段评审） | "产品评审"、"帮我评审" |

## 三、loop-orchestrator 主调度器

### 为什么需要主调度器
- 5 个 Skill 单独调用时需要用户手动切换，流程割裂
- 单个 AI 会话上下文过长会导致开发效果变差
- 子 Agent 模式：每个子 Agent 只加载相关 Skill + 必要上下文

### 自动迭代循环
```
while 有 passes: false 的 task 且 迭代次数 < 5:
  1. 启动 dev-executor 子 Agent → 开发下一个 false task
  2. 开发完成后，启动 journey-runner 子 Agent → 验收
  3. 如果 journey-runner 报告全部通过 → 跳出循环
  4. 如果仍有失败 → 回到步骤 1

循环结束后:
  启动 acceptance-reviewer 子 Agent → 产品评审
  如果追加了新 task → 回到循环开始
  如果没有新 task → 结束
```

### 进度跟踪文件 Docs/loop-progress.json
```json
{
  "current_round": 2,
  "rounds": [
    {
      "round": 1,
      "prd_generator": { "status": "completed", "tasks_created": 12, "scenes_created": 15 },
      "dev_executor": { "status": "completed", "tasks_completed": ["TASK-001"] },
      "journey_runner": { "status": "completed", "scenes_passed": 10, "scenes_failed": 5 }
    }
  ]
}
```

## 四、prd-generator：PRD+JOURNEYS 生成器

### 三种入口检测逻辑

| 检测结果 | 行为 |
|---------|------|
| 发现 0 个 HTML + 有代码 | 走逆向分支 |
| 发现 0 个 HTML + 无代码 | 走正向分支 |
| 发现 1 个 HTML | 向用户确认是否原型文件 |
| 发现多个 HTML | 列出所有让用户选择 |
| 用户主动提供原型路径 | 直接走原型驱动分支 |

### 原型驱动分支（核心）
原型文件是设计和交互的"真相来源"，PRD 和 JOURNEYS 都从它推导。

执行步骤：
1. 读取原型文件：解析 HTML 结构、CSS 变量、JS 交互逻辑
2. 提取设计资产：颜色系统、组件结构、页面路由、交互流程
3. 提问补充：原型不能覆盖的部分
4. 一次性生成：AGENTS.md、PRD.json、JOURNEYS.json、PROTOTYPE_REF.md

### 正向分支（从零开始）
不直接生成 PRD，而是先通过 7 轮结构化提问充分理解需求：
1. 产品定位 → 2. 核心功能边界 → 3. 技术栈 → 4. 数据模型 → 5. 关键用户旅程 → 6. 约束与非功能需求 → 7. 成功标准

### PRD.json Schema（增强版）
```json
{
  "id": "TASK-001",
  "user_story": "作为[角色]，我希望[功能]，以便于[价值]",
  "description": "详细描述",
  "status": "pending",
  "passes": false,
  "acceptance_criteria": ["L1: 基础存在", "L2: 交互正常", "L3: 数据正确", "L4: 边界情况"],
  "journey_scenes": ["SCENE-001"],
  "supersedes": [],
  "unit_test_command": "npx vitest run src/components/xxx.test.ts",
  "e2e_test_command": "npx playwright test tests/e2e/xxx.spec.ts"
}
```

### 三层安全网
- 层 1：PRD 生成时自检（CRUD、路由、scene 覆盖）
- 层 2：dev-executor 开发时发现遗漏 → 追加 task + scene + 标记 [DISCOVERED]
- 层 3：journey-runner 验收后审计 → 输出未覆盖 task 和孤立 scene

## 五、journey-author：JOURNEYS.json 场景脚本编写器

### JOURNEYS.json Schema（增强版）
```json
[
  {
    "scene_id": "SCENE-001",
    "scene_name": "用户典型场景名称",
    "user_goal": "用户在此场景下的核心业务目标",
    "setup": { "method": "api", "endpoint": "POST /api/bindings", "payload": {} },
    "data_mode": "real",
    "data_validation": { "type": "assert_schema" },
    "fallback": { "strategy": "skip" },
    "teardown": { "method": "api", "endpoint": "DELETE /api/bindings/:id" },
    "clicks_script": [
      { "step": 1, "action": "goto", "selector": "N/A", "payload": "/", "checkpoint": false },
      { "step": 2, "action": "type", "selector": "#input", "payload": "测试数据" },
      { "step": 3, "action": "click", "selector": "#submit", "payload": "N/A" },
      { "step": 4, "action": "wait_for", "selector": ".result", "options": { "timeout": 5000 } },
      { "step": 5, "action": "assert_visible", "selector": ".result", "payload": "预期文本" }
    ]
  }
]
```

### Action 类型扩展
| Action | 层级 | 说明 |
|--------|------|------|
| goto | - | 导航到页面 |
| click/type/select | L1 | 基础交互 |
| wait_for | - | 等待条件达成 |
| assert_visible | L1 | 断言元素可见 |
| assert_not_empty | L2 | 断言非空 |
| assert_min_count/structure | L3 | 断言数量/结构 |
| assert_no_placeholder/error | L4 | 断言无占位符/错误 |

## 六、journey-runner：验收测试+自动修复闭环

### 完整闭环流程
```
for 每个 scene:
  for attempt 1..3:
    执行 setup → clicks_script → teardown
    如果全通过 → PASS，跳到下一个 scene
    如果失败:
      1. 截图 + browser_snapshot 获取失败上下文
      2. 诊断: 读源码定位问题
      3. 修复: 直接修改业务代码（不改 JOURNEYS.json）
      4. 等待 HMR 刷新 + 重新 navigate
      5. 重测整个 scene
  3 轮后仍失败 → 标记 FAIL，继续下一个 scene
```

### 关键设计原则
- 不需要单独的修复 Skill：修复能力内建在 journey-runner 中
- 用户只需触发一次：测试 → 修复 → 重测全自动
- JOURNEYS.json 不可修改：失败时只改业务代码
- 错误隔离：单 scene 失败不阻断后续 scene

### Playwright MCP 工具映射
| Action | Playwright MCP |
|--------|---------------|
| goto | browser_navigate(url) |
| click | browser_click(selector) |
| type | browser_type(selector, text) |
| wait_for | browser_snapshot() + sleep 循环 |
| assert_* | browser_snapshot() + AI 分析 |

## 七、acceptance-reviewer：产品评审+迭代规划

### 6 阶段评审流程

| 阶段 | 名称 | 说明 |
|------|------|------|
| 阶段 1 | 黑盒探索 | Playwright MCP 逐路由走过，触发所有交互 |
| 阶段 2 | 白盒审查 | 孤岛组件检测、死代码扫描 |
| 阶段 3 | UX 问题分级 | P0 阻断 / P1 严重 / P2 体验 / P3 美化 |
| 阶段 4 | 竞品 Gap 分析 | 对比同类成熟应用 |
| 阶段 5 | PRD+JOURNEYS 同步追加 | 同时更新两个文件 |
| 阶段 6 | 人类反馈整合 | 用户新想法 → 原子 task |

### 黑盒探索检查项
1. 导航到该路由，观察加载过程（Loading？骨架屏？）
2. 观察空状态（无数据时引导是否友好）
3. 触发所有交互：点击、展开/折叠、切换 Tab、打开/关闭 Modal
4. 触发错误场景：输入无效数据、断开网络
5. 响应式测试：375px / 768px / 1440px
6. 截图留证：每个路由三种状态各截一张

## 八、dev-executor：开发执行器

### 核心规则
- 检查 PROTOTYPE_REF.md 是否存在：存在 → 对照原型实现
- 锁定 PRD.json 中 ID 最前的 passes: false task
- 开发代码 → 单元测试（白盒闸）→ e2e_test_command（冒烟闸）
- 冒烟闸: L1+L2 断言即可，快速确认基本功能没挂
- 双闸通过后: passes: true + git commit + 更新 PRD.json
- 遇到 superseded_by 的 task → 跳过

## 九、质量约束

| 约束 | 说明 |
|------|------|
| 零跳过 | 所有场景必须全部尝试执行 |
| 零伪造 | 每个断言必须在真实环境中验证 |
| 截图存证 | 失败场景即时截图 |
| 错误隔离 | 单个场景失败不影响后续场景 |
| 修复安全 | 必须通过编译，无新 lint 警告 |
| 超时兜底 | 单步骤超过 30 秒标记超时失败 |

## 十、执行模式

### 全自动模式（通过 loop-orchestrator）
```
用户: "帮我开发这个功能"
  → loop-orchestrator 启动:
    1. 调用 prd-generator → 生成 PRD + JOURNEYS
    2. 进入迭代循环: dev-executor → journey-runner
    3. 调用 acceptance-reviewer → 产品评审
    4. 有新 task？→ 继续循环
    5. 没有新 task？→ 输出最终报告
```

### 手动模式
| 场景 | 流程 |
|------|------|
| 有原型文件 | prd-generator [原型驱动] → dev-executor → journey-runner |
| 从零开始 | prd-generator [正向: 7轮提问] → dev-executor → journey-runner |
| 已有代码库 | prd-generator [逆向] → dev-executor → journey-runner |

## 相关资源
- V1.0: https://my.feishu.cn/wiki/Xs8kwucm1iVmN2k6IHwcD6oynRh
- V2.0: https://my.feishu.cn/wiki/Ufx1wM1kriqH3Ukec96cXRpDnzh
- Skills 源码: e2e-acceptance-skills/
