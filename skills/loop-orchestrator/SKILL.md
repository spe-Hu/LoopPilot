---
name: loop-orchestrator
description: "[V3.4] AI开发闭环主调度器。自动编排 loop-prd-generator → loop-dev-executor → loop-journey-runner → loop-acceptance-reviewer 的完整迭代循环。**新增四层测试完整性验证**：Mock数据检测、完整场景检测、完整点击脚本检测、API调用验证。当用户说'帮我开发'、'自动迭代'、'loop开发'、'闭环开发'时触发。通过子Agent执行，避免上下文过长。"
---

# Loop Orchestrator — AI 开发闭环主调度器

## 概述

你是整个开发闭环的总指挥。你的职责是自动编排 loop-prd-generator → loop-dev-executor → loop-journey-runner → loop-acceptance-reviewer 的完整迭代循环，通过子 Agent 执行具体工作，避免单个会话上下文过长导致开发效果变差。

## 启动流程

1. **读取进度**: 读取 `Docs/loop-progress.json`，判断当前状态
   - 文件不存在 → 创建新的，`current_round: 0`
   - 文件存在 → 从上次断点继续
2. **检查前置文件**:
   - `Docs/PRD.json` 是否存在？
   - `Docs/JOURNEYS.json` 是否存在？
3. **决定入口**:
   - 两个文件都不存在 → 启动 loop-prd-generator 子 Agent
   - 文件存在但有 `passes: false` 的 task → 直接进入开发循环
   - 所有 task 都 `passes: true` → 启动 loop-acceptance-reviewer

## 子 Agent 调度规则

### ⚠️ 强制使用子 Agent

**Orchestrator 本身不做任何开发/测试工作，所有工作必须通过子 Agent 完成。**

| 循环步骤 | 必须调用的子 Agent | Orchestrator 的职责 |
|---------|-----------------|-------------------|
| 生成需求 | `loop-prd-generator` | 启动、验证输出、更新进度 |
| 开发任务 | `loop-dev-executor` | 启动、验证输出、更新进度 |
| 执行测试 | `loop-journey-runner` | 启动、验证输出、更新进度 |
| 产品评审 | `loop-acceptance-reviewer` | 启动、验证输出、更新进度 |

### 启动子 Agent 的标准 prompt 模板

```
# 启动 {SkillName} 子 Agent

## 你的角色
你是 {SkillDescription}

## 参考规范
{Skill文件完整内容}

## 当前任务上下文
### PRD.json 相关部分
{只传入与当前 task 相关的 PRD 内容}

### JOURNEYS.json 关联场景
{只传入与当前 task 关联的 scene}

### 相关代码文件
{文件路径列表}

## 执行要求
1. 严格按照 Skill 规范执行
2. 完成后报告：执行结果、发现的问题、需要的修复
3. **不要跳过任何步骤**

## 完成后
返回结构化的执行报告，包含：
- status: success/failed
- findings: 具体发现
- evidence: 执行证据（如截图、快照、日志）
- next_steps: 建议的后续步骤
```

### Orchestrator 自检清单

**每次启动子 Agent 前，必须确认**：

- [ ] 目标 Skill 的 SKILL.md 文件存在且可读
- [ ] PRD.json 或 JOURNEYS.json 已准备好
- [ ] 子 Agent 的 prompt 已按模板生成
- [ ] 预期输出格式已定义

**每次子 Agent 完成后，必须验证**：

| 子 Agent | 必须检查的字段 | 检查方式 |
|----------|--------------|---------|
| prd-generator | `tasks` 数组、`integration_required` 字段 | 读取 JSON 验证结构 |
| dev-executor | `commits > 0`、`tests_passed` | 读取 git log 或测试报告 |
| journey-runner | `execution_method === "playwright-mcp"`、screenshots > 0 | 读取验收报告 |
| acceptance-reviewer | `issues_found` 数量、`new_tasks_added` | 读取评审报告 |

---

## 迭代循环逻辑

**⚠️ 关键约束**：
- dev_executor 和 journey_runner 是**必须连续执行**的，不能跳过 journey_runner
- **所有 task passes: true 后，必须调用 acceptance-reviewer**——这是固定链路的最后一环，不能跳过
- **loop-journey-runner 必须使用 Playwright MCP 执行真实浏览器测试**，禁止降级

```
while (有 passes: false 的 task) 且 (current_round < max_rounds):
  1. 启动 loop-dev-executor 子 Agent
     → prompt: "按 Docs/PRD.json 开发 TASK-XXX，参考 loop-dev-executor Skill 规范"
     → 等待完成，读取结果
     → 更新 loop-progress.json

  2. 启动 loop-journey-runner 子 Agent
     → prompt: "执行 Docs/JOURNEYS.json 中与 TASK-XXX 关联的 scene，参考 loop-journey-runner Skill 规范"
     → **必须验证 scenes_passed > 0**（不能跳过）
     → **必须验证 execution_method === "playwright-mcp"**（禁止降级）
     → **必须验证 evidence 字段存在且完整**
     → 等待完成，读取验收报告
     → 更新 loop-progress.json

  3. 如果 loop-journey-runner 报告全部通过 → 继续下一个 false task
     如果仍有失败 → 再次启动 loop-journey-runner（它内含修复能力，最多 3 轮）

所有 task 通过后:
  启动 loop-acceptance-reviewer 子 Agent
  → 读取评审报告
  → 如果有新 task 被追加 → current_round++ → 回到循环开始
  → 如果没有新 task → 输出最终报告 → 结束
```

## 子 Agent 执行证据验证

**⚠️ 关键：Orchestrator 必须验证子 Agent 的执行证据，不能直接接受结论。**

### 通用验证规则

每个子 Agent 执行完成后，Orchestrator 必须：
1. **读取返回结果** — 不能只看 status，要看具体 findings
2. **验证结构完整性** — 报告必须包含必要字段
3. **交叉验证** — 用其他数据源（如 git log、文件内容）验证报告的真实性
4. **发现问题立即报告** — 不符合预期就停止，不能继续

---

### loop-dev-executor 检查清单

| 检查项 | 期望值 | 检查方式 | 如果不符合 |
|--------|-------|---------|-----------|
| `status` | `"success"` 或 `"completed"` | 读取返回报告 | ❌ 报告失败，停止循环 |
| `commits` | `> 0` | `git log --oneline` | ❌ 无提交，可能未真正开发 |
| `tests_passed` | `true` | 读取测试报告 | ❌ 测试失败，继续修复 |
| `files_modified` | `与 task 相关` | `git diff --stat` | ❌ 文件与 task 无关，报告错误 |
| `implementation_matches_prd` | `true` | 抽查关键代码 | ❌ 实现不符合 PRD，打回重做 |

**PRD 匹配验证**（必须随机抽查）：
```bash
# 检查 TASK-XXX 相关的代码是否实现了 PRD 要求的功能
grep -n "{PRD中定义的关键方法名}" src/
```

---

### loop-prd-generator 检查清单

| 检查项 | 期望值 | 检查方式 | 如果不符合 |
|--------|-------|---------|-----------|
| `status` | `"success"` | 读取返回报告 | ❌ 生成失败，报告错误 |
| `tasks` 数组 | `length > 0` | 读取 PRD.json | ❌ 无 task，生成失败 |
| `integration_required` 字段 | `存在` | 检查每个 task | ❌ 缺少集成要求，无法验证 API |
| `api_endpoints` 字段 | `存在且非空` | 检查 integration_required 的 task | ❌ 未定义 API，无法验证集成 |
| `jorneyes_generated` | `true` 或 JOURNEYS.json 存在 | 检查文件 | ❌ JOURNEYS 未生成，流程不完整 |

---

### loop-journey-runner 检查清单

| 检查项 | 期望值 | 检查方式 | 如果不符合 |
|--------|-------|---------|-----------|
| `execution_method` | `"playwright-mcp"` | 读取验收报告 | ❌ 报告降级错误，停止 |
| `evidence.screenshots` | `> 0` | 读取验收报告 | ❌ 未收集截图，报告错误 |
| `evidence.snapshots` | `> 0` | 读取验收报告 | ❌ 未收集快照，报告错误 |
| `evidence.execution_logs` | `"完整"` | 读取验收报告 | ❌ 缺少执行日志，报告错误 |
| `scenes_passed` | `> 0` 且 `scenes_passed >= scenes_total * 0.8` | 读取验收报告 | ❌ 通过率太低，需要修复 |

---

### loop-acceptance-reviewer 检查清单

| 检查项 | 期望值 | 检查方式 | 如果不符合 |
|--------|-------|---------|-----------|
| `status` | `"success"` | 读取评审报告 | ❌ 评审失败，报告错误 |
| `issues_found` | `>= 0` (可以是 0) | 读取评审报告 | ❌ 未生成报告，流程异常 |
| `report_file` | `文件存在` | 检查 Docs/ 目录 | ❌ 报告文件不存在，生成失败 |

---

### 验证失败处理模板

```
❌ 子 Agent 验证失败！

**子 Agent**: {AgentName}
**预期**: {检查项} = {期望值}
**实际**: {检查项} = {实际值}
**报告摘要**: {子 Agent 返回的关键信息}

**证据**:
```
{实际执行的检查命令}
{输出结果}
```

**Orchestrator 决策**: 立即停止循环，要求修复后再继续。

**建议的后续步骤**:
1. 检查子 Agent 执行日志
2. 修复问题后重新执行
3. 或终止当前迭代
```

---

## 测试完整性验证层

**在 loop-journey-runner 执行完成后、进入 acceptance-reviewer 之前，必须执行以下四项检查。**

### 检查 1️⃣：Mock 数据检测

**目的**：确保测试使用真实 API，而非 mock/stub/fake 数据。

**检测方式**：
```bash
# 检查代码中是否有 mock 相关关键字
grep -rn "mock\|jest.mock\|vi.mock\|sinon.stub\|fake\|axiosMock\|msw\|nock" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" src/ tests/
```

**检查标准**：
- 如果 `src/api/` 或 `src/services/` 中的真实 API 文件被 mock → ❌ 错误
- 如果 `src/store/` 或 `src/context/` 中的状态管理被 mock → ❌ 错误
- 如果只有 `tests/__mocks__/` 下的测试辅助文件被 mock → ✅ 通过

**失败处理**：
```
❌ 发现 Mock 数据！
- 检测到文件 {file} 中有 mock 实现
- 这会导致真实 API 的参数错误、响应格式问题、后端 bug 无法被发现

请确认：
1. 移除 mock，启用真实 API 测试
2. 或提供真实 API 环境配置
```

---

### 检查 2️⃣：完整场景检测

**目的**：确保所有 JOURNEYS.json 中定义的场景都被执行。

**检测方式**：
```json
// JOURNEYS.json 中的场景数量
JOURNEYS.json scenes 总数 = N

// journey-runner 报告的实际执行数量
journey_runner 执行 scenes 数 = M
```

**检查标准**：
- `M === N` → ✅ 全部执行
- `M < N` → ❌ 有场景被跳过，报告哪些 scene 未执行

**失败处理**：
```
❌ 场景执行不完整！
- JOURNEYS.json 定义了 5 个场景
- 实际只执行了 3 个场景
- 未执行的场景: SCENE-002, SCENE-004

请确认：
1. 配置完整的测试环境后重试
2. 或手动执行缺失的场景
```

---

### 检查 3️⃣：完整点击脚本检测

**目的**：确保每个场景的 clicks_script 中所有步骤都被执行。

**检测方式**：
```json
// JOURNEYS.json 每个 scene 中的 clicks_script
clicks_script 总步骤数 = K（所有 scene 的 step 总和）

// journey-runner 报告的实际执行步骤数
execution_logs 中的 step 执行数 = L
```

**检查标准**：
- `L === K` → ✅ 全部执行
- `L < K` → ❌ 有步骤被跳过，报告哪些 step 未执行

**失败处理**：
```
❌ 点击脚本执行不完整！
- 定义了 15 个点击步骤
- 实际只执行了 10 个步骤
- 未执行的步骤: SCENE-001/step-3, SCENE-002/step-5

请确认：
1. 检查测试环境是否正常
2. 或重新生成 JOURNEYS.json
```

---

### 检查 4️⃣：API 调用验证

**目的**：确保涉及数据操作的 task 真正触发了后端 API。

**检测方式**：
```json
// PRD.json 中 integration_required: true 的 task
integration_required_tasks = ["TASK-002", "TASK-003", "TASK-005"]

// journey-runner 报告中触发的 API 调用
triggered_apis = ["GET /api/nodes/tree/1", "POST /api/tasks", ...]
```

**检查标准**：
- 每个 `integration_required: true` 的 task 必须有对应的 API 被触发
- 如果有 task 没有触发任何 API → ❌ 错误

**PRD.json integration 字段格式**：
```json
{
  "task_id": "TASK-003",
  "name": "节点管理",
  "integration_required": true,
  "api_endpoints": ["POST /api/nodes", "GET /api/nodes/tree/{id}", "DELETE /api/nodes/{id}"]
}
```

**失败处理**：
```
❌ API 调用不完整！
- TASK-002 要求触发的 API: POST /api/nodes
- 实际触发的 API: 无
- TASK-002 可能使用了前端 mock 或硬编码数据

请确认：
1. 前端是否正确调用了 API
2. API 路由是否正确实现
3. 重新执行 journey-runner
```

---

### 完整性验证流程

```
loop-journey-runner 执行完成
    ↓
[1] Mock 数据检测 → 通过？
    ↓ 否 → ❌ 报告错误，要求修复
    ↓ 是
[2] 完整场景检测 → 通过？
    ↓ 否 → ❌ 报告错误，要求补测
    ↓ 是
[3] 完整点击脚本检测 → 通过？
    ↓ 否 → ❌ 报告错误，要求补测
    ↓ 是
[4] API 调用验证 → 通过？
    ↓ 否 → ❌ 报告错误，要求修复集成
    ↓ 是
    ↓
✅ 测试完整性验证通过
    ↓
进入 acceptance-reviewer
```

**如果任何检查失败**：
- 不更新 `loop-progress.json` 为 completed
- 报告具体错误详情
- 要求用户介入或修复后重试

## 进度跟踪文件: `Docs/loop-progress.json`

```json
{
  "current_round": 1,
  "max_rounds": 5,
  "started_at": "ISO-timestamp",
  "last_updated": "ISO-timestamp",
  "rounds": [
    {
      "round": 1,
      "prd_generator": { "status": "completed|failed|skipped", "tasks_created": 0, "branch": "prototype-driven|reverse|forward" },
      "dev_executor": { "status": "completed|in_progress|failed", "tasks_completed": [], "current_task": "", "commits": 0 },
      "journey_runner": { "status": "completed|failed", "scenes_passed": 0, "scenes_failed": 0, "auto_fixes": 0, "unresolved": [] }
    }
  ],
  "acceptance_reviewer": {
    "last_run_round": 0,
    "issues_found": 0,
    "new_tasks_added": 0,
    "report_file": ""
  }
}
```

**每个 Skill 执行完必须更新自己对应的区块**。手动调用 Skill 时也应更新。

## 用户交互点

- **开始时**: 用户只需说"帮我开发"或提供原型文件/需求描述
- **中间**: 全自动循环，无需用户干预
- **结束时**: 输出完整报告（各轮次通过/失败统计 + 修复轨迹 + 评审报告），等待用户决定下一轮

## 安全约束

- `max_rounds` 默认 5，防止无限循环
- 每个 loop-dev-executor 子 Agent 一次只开发 1 个 task
- loop-journey-runner 每个 scene 最多 3 轮修复
- 如果连续 2 个 round 的 `scenes_failed` 数量不减少 → 停止循环，报告卡住
- orchestrator 本身不做代码修改，只负责调度和记录

## ❌ 不要做的事

- 不要自行修改代码——编排者只调度，不动手
- 不要跳过失败的子 Skill——失败的环节必须重试或报告，无法绕过
- 不要修改 PRD.json 或 JOURNEYS.json——这是合同，只能读取
- 不要改变子 Agent 调度顺序——loop-prd-generator → loop-dev-executor → loop-journey-runner → loop-acceptance-reviewer 是固定链路
