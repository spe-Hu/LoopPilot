# Loop V3.0 — AI 开发闭环验收测试 Skill 体系

AI 开发闭环验收测试方法论，通过模块化的 6 个 Skill 实现从需求到验收的完整流程。

## 核心问题

| 痛点 | V1/V2 问题 | V3 解决方案 |
|------|------------|-------------|
| 断言浅表化 | 只验证 UI，核心业务逻辑无覆盖 | 两层断言模型（PRD + JOURNEYS） |
| 长时间流程无覆盖 | 异步任务、等待场景无法验证 | wait_for action + 断点续测 |
| 提示词过大规则逃逸 | 500+ 行提示词，规则相互冲突 | 模块化 6 个独立 Skill |
| V1/V2 并行冲突 | 开发冒烟 vs 全量验收打架 | 双轨制（开发冒烟 + 全量验收） |
| 真实数据只有口号 | 测试数据 Hardcode，无真实性验证 | 数据播种 + 诊断优先降级 |

## Skills 清单

| Skill | 职责 | 触发词 |
|-------|------|--------|
| loop-orchestrator | 主调度器，编排完整迭代循环（max_rounds=5） | "帮我开发"、"闭环开发" |
| loop-prd-generator | PRD+JOURNEYS 生成器，支持三种入口 | "生成PRD"、"从原型生成" |
| loop-dev-executor | 开发执行器，单元+E2E 双重验证 | "执行开发"、"按 PRD 开发" |
| loop-journey-runner | 验收测试+自动修复闭环（最多3轮） | "验收测试"、"全量测试" |
| loop-journey-author | JOURNEYS.json 场景脚本编写器 | "生成 JOURNEYS"、"编写验收脚本" |
| loop-acceptance-reviewer | 产品评审+迭代规划（6阶段评审） | "产品评审"、"帮我评审" |

## 快速开始

1. 安装 Skills 到 Qoder：
   ```bash
   cp -r e2e-acceptance-skills/* ~/.agents/skills/
   ```

2. 在 Qoder 中使用：
   ```
   /loop-orchestrator
   帮我开发这个功能
   ```

## 文档

- [V3 完整方法论](./loop-v3-full.md)
- [Skills 源码](./e2e-acceptance-skills/)

## 版本历史

- V1.0: https://my.feishu.cn/wiki/Xs8kwucm1iVmN2k6IHwcD6oynRh
- V2.0: https://my.feishu.cn/wiki/Ufx1wM1kriqH3Ukec96cXRpDnzh
- V3.0: https://my.feishu.cn/wiki/W7JMw6VveikmRrkP706cyCQXncf