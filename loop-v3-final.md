# Loop 核心提示词 V3.0

> 更新时间：2026-06-22

## 核心变更

将提示词体系升级为 **Qoder Skills 技能包**，实现模块化、可复用、可触发的智能体技能系统。

---

## 一、V1 → V2 → V3 演进

| 版本 | 痛点 | 解决方案 |
|------|------|----------|
| V1.0 | AI 刷孤立测试，主业务流未实现 | 提出"双环进化模型" |
| V2.0 | Token 消耗大，效果差 | 强化 JOURNEYS.json + Playwright MCP |
| **V3.0** | 提示词无法自动识别调用 | **Qoder Skills 体系** |

---

## 二、架构图

<whiteboard token="CaqCwRns9hwbZ0brrk9cn0PqnSb"/>

---

## 三、Skills 清单

| Skill | 职责 | 触发词 |
|-------|------|--------|
| `loop-orchestrator` | 主调度器（max_rounds=5） | "帮我开发"、"闭环开发" |
| `loop-prd-generator` | 生成 PRD.json + JOURNEYS.json | "生成PRD"、"从原型生成" |
| `loop-dev-executor` | 单元测试 + E2E 冒烟双重验证 | "执行开发"、"按 PRD 开发" |
| `loop-journey-runner` | 全量验收 + 自动修复闭环 | "验收测试"、"全量测试" |
| `loop-journey-author` | 编写 JOURNEYS.json 场景剧本 | "生成 JOURNEYS"、"编写验收脚本" |
| `loop-acceptance-reviewer` | 产品评审 + 迭代规划 | "产品评审"、"帮我评审" |

---

## 四、核心文件

### 4.1 PRD.json
```json
{
  "id": "TASK-001",
  "user_story": "作为[角色]，我希望[功能]，以便于[价值]",
  "description": "详细描述",
  "status": "pending",
  "passes": false,
  "unit_test_command": "npx vitest run src/components/xxx.test.ts",
  "e2e_test_command": "npx playwright test tests/e2e/xxx.spec.ts"
}
```

### 4.2 JOURNEYS.json
```json
[
  {
    "scene_id": "SCENE-001",
    "scene_name": "场景名称",
    "user_goal": "用户业务目标",
    "clicks_script": [
      { "step": 1, "action": "goto", "payload": "/" },
      { "step": 2, "action": "type", "selector": "#input", "payload": "数据" },
      { "step": 3, "action": "click", "selector": "#submit", "payload": "N/A" },
      { "step": 4, "action": "assert_visible", "selector": ".result", "payload": "预期文本" }
    ]
  }
]
```

---

## 五、迭代流程

```
┌────────────────────────────────────────────────────────┐
│                    第 N 轮迭代（最多 5 轮）              │
├────────────────────────────────────────────────────────┤
│  ① PRD Generator → 生成/更新 PRD.json + JOURNEYS.json │
│  ② Dev Executor  → 单元测试 + E2E 冒烟双重验证         │
│  ③ Journey Runner → 全量验收 + 自动修复                 │
│  ④ Acceptance Reviewer → 产品评审 + 迭代规划           │
│  ⑤ 判断：还有未完成项？→ 继续下一轮 / 结束              │
└────────────────────────────────────────────────────────┘
```

### 断点续跑
使用 `loop-progress.json` 跟踪进度，支持中断后恢复：
```json
{
  "current_round": 2,
  "max_rounds": 5,
  "phases": {
    "prd_generator": { "completed": true },
    "dev_executor": { "completed": false, "current_task": "TASK-003" }
  }
}
```

---

## 六、质量约束

1. **零跳过**：所有场景必须全部尝试执行
2. **零伪造**：每个断言必须在真实环境中验证
3. **截图存证**：失败场景即时截图
4. **错误隔离**：单个场景失败不影响后续场景

---

## 七、Skills 安装位置

```
~/.agents/skills/
├── loop-orchestrator/
├── loop-prd-generator/      (含 examples/)
├── loop-dev-executor/
├── loop-journey-author/     (含 examples/)
├── loop-journey-runner/
└── loop-acceptance-reviewer/
```

---

## 八、相关资源

- V1.0：[Loop 核心提示词 V1.0](https://my.feishu.cn/wiki/Xs8kwucm1iVmN2k6IHwcD6oynRh)
- V2.0：[Loop 核心提示词 V2.0](https://my.feishu.cn/wiki/Ufx1wM1kriqH3Ukec96cXRpDnzh)
- Skills 源码：e2e-acceptance-skills/
