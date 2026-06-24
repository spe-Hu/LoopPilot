# LoopPilot — AI 开发闭环验收测试框架

**用 AI 开发 AI-ready 的产品，通过闭环验收确保每个 Task 真正可用。**

---

## 核心问题

当你用 AI 开发产品时，是否遇到过这些问题？

| 痛点 | 后果 |
|------|------|
| AI 写完代码，但没测过核心逻辑 | 上线后频繁出 Bug |
| AI 只验证 UI，不验证业务逻辑 | 功能看着能用，实际跑不通 |
| 异步任务、等待场景无法验证 | 签收流程、邮件发送等场景无法测试 |
| 测试数据都是假的 | "测试通过，生产挂掉" |
| AI 自己开发、自己测试、自己验收 | 循环自证，缺乏独立验证 |

---

## 解决方案

LoopPilot 是一个**模块化的 AI 开发闭环框架**，核心思想：

1. **双层断言模型**：PRD.json 定义"要做什么"，JOURNEYS.json 定义"怎么验证"
2. **独立验收**：谁开发，谁验收，职责分离
3. **真实数据**：验收数据必须真实，不能 Hardcode
4. **自动迭代**：发现问题 → 写回需求 → 继续开发，直到验收通过

---

## 工作流程

```
用户需求 → loop-prd-generator (生成 PRD + JOURNEYS)
                    ↓
         loop-dev-executor (按 PRD 开发)
                    ↓
         loop-journey-runner (跑验收测试)
                    ↓
       loop-acceptance-reviewer (评审，发现问题)
                    ↓
         问题写回 PRD.json ← 关键！
                    ↓
              继续迭代 (最多 5 轮)
```

---

## Skills 清单

| Skill | 职责 |
|-------|------|
| **loop-orchestrator** | 主调度器，编排完整迭代循环 |
| **loop-prd-generator** | PRD + JOURNEYS 生成器 |
| **loop-dev-executor** | 按 PRD 逐 Task 开发 |
| **loop-journey-runner** | 执行验收测试，失败自动修复 |
| **loop-journey-author** | 编写验收场景脚本 |
| **loop-acceptance-reviewer** | 产品评审，发现问题并写回 PRD |

---

## 安装

```bash
# 克隆仓库
git clone https://github.com/spe-Hu/LoopPilot.git

# 安装 Skills (适用于 Qoder)
cp -r LoopPilot/skills/* ~/.agents/skills/
```

---

## 使用

在 Qoder 中，直接说：

```
/loop-orchestrator
帮我开发文章收藏功能
```

框架会自动：
1. 生成 PRD 和验收场景
2. 开发功能
3. 运行验收测试
4. 评审发现问题
5. 把问题写回 PRD，继续迭代

---

## 文档

- [完整方法论文档](https://my.feishu.cn/wiki/W7JMw6VveikmRrkP706cyCQXncf)

---

## 目录结构

```
LoopPilot/
├── skills/                  # 核心 Skills
│   ├── loop-orchestrator/   # [V3.3] 主调度器（含测试完整性验证）
│   ├── loop-prd-generator/   # [V3.3] PRD 生成器
│   ├── loop-dev-executor/    # [V3.3] 开发执行器
│   ├── loop-journey-runner/  # [V3.3] 验收测试（强制Playwright MCP）
│   ├── loop-journey-author/  # [V3.3] 场景编写器
│   └── loop-acceptance-reviewer/ # [V3.3] 产品评审（含强制写入PRD）
└── README.md
```

---

## ChangeLog

### [V3.3] - 2026-06-22

#### loop-orchestrator: 测试完整性验证层

在 journey-runner 完成后、进入 acceptance-reviewer 之前，新增四层完整性检查：

| 检查项 | 检测内容 | 失败处理 |
|--------|---------|---------|
| Mock 数据检测 | 代码中是否有 mock/stub/fake | ❌ 要求移除 mock |
| 完整场景检测 | JOURNEYS.json scenes vs 实际执行数 | ❌ 要求补测 |
| 完整点击脚本检测 | clicks_script steps vs 实际执行数 | ❌ 要求补测 |
| API 调用验证 | PRD.integration_required task 触发 API | ❌ 要求修复集成 |

**任何一层失败都阻断流程**，确保前后端真正集成测试通过才能继续。

---

### [V3.2] - 2026-06-22

#### Phase 2 优化：dim9 反例与黑名单章节

为 6 个 Skills 全部添加了 `## ❌ 不要做的事` 反例章节，明确职责边界：

| Skill | 核心边界 |
|-------|----------|
| loop-orchestrator | 只调度不修改代码、固定链路顺序 |
| loop-prd-generator | 只产出文档不触碰实现、生成即锁定 |
| loop-dev-executor | 严格按 PRD.tasks 执行、不跳过测试 |
| loop-journey-runner | 小范围 targeted fix、不修改 JOURNEYS.json |
| loop-journey-author | 断言来自 PRD/代码、不写无关联 scene |
| loop-acceptance-reviewer | 只发现问题不修复、强制追加 PRD/JOURNEYS |

**预期效果**：dim9 评分从 0 → 3-4 分，平均分 64 → 66-67

---

#### loop-journey-runner: 强制 Playwright MCP 执行

- 禁止降级为源码审查或 curl
- 必须收集截图、快照顾、执行日志
- 子 Agent 执行证据验证

---

## License

MIT
