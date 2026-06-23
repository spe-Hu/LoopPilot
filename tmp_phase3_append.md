---

## 九、Phase 3 优化：loop-dev-executor 禁止编写 E2E（V3.x）
### 9.1 问题背景
在 English-Learning 项目中，发现 dev_executor 自己编写了不完整的 E2E 测试，而不是调用 journey_runner 执行 JOURNEYS.json。这导致：
- E2E 测试覆盖率不足（只有部分场景被测试）
- journey_runner 从未被真正执行过
- 职责边界模糊，验收流程不完整

### 9.2 优化内容
**明确 dev_executor 的职责边界**：
- dev_executor **只做开发 + 冒烟闸测试**
- **不得自己编写 E2E 测试文件**
- E2E 验收由 `loop-journey-runner` 负责执行 `Docs/JOURNEYS.json`

**分层测试架构**：

| Agent | 职责 | 测试类型 |
|-------|------|----------|
| dev_executor | 开发 + 冒烟闸 | 单元测试 + 意图一测试 |
| journey_runner | E2E 验收 | 执行 JOURNEYS.json |

### 9.3 修改内容
**loop-dev-executor/SKILL.md 修改**：
1. 冒烟闸章节添加 ⚠️ 警告：
   > **⚠️ 重要**：dev_executor **不得自己编写 E2E 测试文件**。
   > 
   > E2E 验收由 `loop-journey-runner` 负责执行 `Docs/JOURNEYS.json`，不是 dev_executor 的职责。

2. `❌ 不要做的事` 添加：
   > - **不要自己编写 E2E 测试文件**——E2E 验收由 journey_runner 执行 JOURNEYS.json，dev_executor 只做开发

### 9.4 预期效果
- dev_executor 专注开发，不再越界写 E2E 测试
- E2E 验收统一由 journey_runner 负责，保证覆盖率
- 职责边界清晰，验收流程完整

---

## 十、Phase 3 优化：loop-orchestrator 强制调用 journey_runner（V3.x）
### 10.1 问题背景
orchestrator 可能跳过 journey_runner，导致 E2E 验收从未执行。之前 dev_executor 自己写 E2E 测试掩盖了这个问题。

### 10.2 优化内容
**强制 orchestrator 调用 journey_runner**：
- dev_executor 和 journey_runner **必须连续执行**
- 不能跳过 journey_runner
- 必须验证 `scenes_passed > 0`

### 10.3 修改内容
**loop-orchestrator/SKILL.md 修改**：
在启动 journey_runner 步骤添加关键约束：

```markdown
2. 启动 loop-journey-runner 子 Agent
   → prompt: "执行 Docs/JOURNEYS.json 中与 TASK-XXX 关联的 scene，参考 loop-journey-runner Skill 规范"
   → **必须验证 scenes_passed > 0**（不能跳过）
   → 等待完成，读取验收报告
   → 更新 loop-progress.json
```

### 10.4 预期效果
- E2E 验收是每次迭代的必经环节
- `scenes_passed` 记录确保验收可追溯
- 不会再出现 journey_runner 从未执行的情况

---

## 十一、Phase 3 完整实施总结

| Skill | 修改内容 | 核心目标 |
|-------|----------|----------|
| loop-journey-author | 半成品场景拦截机制 | 确保 JOURNEYS.json 可执行 |
| loop-dev-executor | 禁止编写 E2E 测试 | 职责分离，专注开发 |
| loop-orchestrator | 强制调用 journey_runner | 保证 E2E 验收执行 |

**Phase 3 预期效果**：
- 测试覆盖率：19/26 → 26/26
- E2E 验收执行率：0% → 100%
- 职责边界清晰度：模糊 → 明确
