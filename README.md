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
│   ├── loop-orchestrator/   # [V3] 主调度器
│   ├── loop-prd-generator/   # [V3] PRD 生成器
│   ├── loop-dev-executor/    # [V3] 开发执行器
│   ├── loop-journey-runner/  # [V3] 验收测试
│   ├── loop-journey-author/  # [V3] 场景编写器
│   └── loop-acceptance-reviewer/ # [V3.1] 产品评审（含强制写入PRD）
└── README.md
```

---

## License

MIT
