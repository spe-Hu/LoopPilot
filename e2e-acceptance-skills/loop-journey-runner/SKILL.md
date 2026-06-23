---
name: loop-journey-runner
description: "验收测试+自动修复闭环。执行 JOURNEYS.json 全量验收，失败时自动诊断、修复代码、重测（最多3轮）。当用户说'跑验收'、'执行测试'、'验收测试'、'全量测试'时触发。"
---

# Journey Runner — 验收测试 + 自动修复闭环

## 概述

执行 `Docs/JOURNEYS.json` 全量验收测试。失败时自动诊断、修复代码、重测，最多 3 轮。用户只需触发一次，全程自动。

## 启动流程

1. 读取 `Docs/JOURNEYS.json`，获取所有 scene
2. 检查 `Docs/loop-progress.json` 是否有上次未完成的进度
   - 有 checkpoint → 从断点继续
   - 无 → 从头开始
3. 确保应用已启动（`npm run dev` 或对应命令）

## Playwright MCP 执行方式

**全程 AI 驱动，不生成 .spec.ts 文件。**

每个 step 映射到 Playwright MCP 工具调用：

| JOURNEYS action | Playwright MCP 调用 |
|----------------|---------------------|
| `goto` | `browser_navigate(url)` |
| `click` | `browser_click(selector)` |
| `type` | `browser_type(selector, text)` |
| `select` | `browser_select_option(selector, values)` |
| `hover` | `browser_hover(selector)` |
| `scroll` | `browser_scroll(direction)` |
| `wait_for` | 循环: `browser_snapshot()` → 检查 payload → sleep(pollingInterval) → 重复 |
| `assert_visible` | `browser_snapshot()` → 检查元素+文本 |
| `assert_not_empty` | `browser_snapshot()` → 检查元素有内容 |
| `assert_min_count` | `browser_snapshot()` → 计算匹配元素数量 |
| `assert_structure` | `browser_snapshot()` → 分析 DOM 结构 |
| `assert_no_placeholder` | `browser_snapshot()` → 正则匹配占位符模式 |
| `assert_no_error` | `browser_snapshot()` → 检查错误文本 |

**断言判断标准**：
- L1: 元素在 snapshot 中可见
- L2: 元素的 textContent 不为空
- L3: 元素数量/结构符合预期
- L4: 内容不包含 `undefined`/`NaN`/`null`/`TODO`/`placeholder`/`[object Object]`/`${...}`/`{{...}}`

## 完整闭环流程

```
results = {}

for scene in scenes:
  for attempt in 1..3:
    # 1. 执行 setup
    setup_result = execute_setup(scene.setup)
    if setup_result.failed:
      diagnose_and_fix(setup_result)  # 最多 3 轮
      if still_failed:
        if scene.fallback?.allowed:
          results[scene.scene_id] = "DEGRADED"
          break
        else:
          results[scene.scene_id] = "FAIL (setup)"
          break

    # 2. 逐步执行 clicks_script
    all_passed = true
    for step in scene.clicks_script:
      result = execute_step(step)
      if result.failed:
        all_passed = false
        # 截图 + snapshot 记录失败上下文
        screenshot(scene_id, step.step)
        failure_info = { step, result, snapshot }
        break

      # checkpoint 保存
      if step.options?.checkpoint:
        save_checkpoint(scene.scene_id, step.step)

    # 3. 执行 teardown
    execute_teardown(scene.teardown)

    # 4. 判断结果
    if all_passed:
      results[scene.scene_id] = "PASS"
      break  # 跳到下一个 scene

    # 5. 失败 → 诊断 + 修复
    diagnosis = diagnose(failure_info)
    # 读源码定位问题根因
    if diagnosis.type == "code_bug":
      fix_code(diagnosis.location, diagnosis.fix)
      wait_hmr()
      browser_navigate(scene 的起始 URL)
      # 继续下一轮 attempt
    elif diagnosis.type == "environment":
      fix_environment(diagnosis)
      # 继续下一轮 attempt
    else:
      results[scene.scene_id] = "FAIL (unfixable)"
      break

  # 3 轮后仍失败
  if scene_id not in results:
    results[scene.scene_id] = "FAIL (max_retries)"

# 输出报告
generate_report(results)
```

## 诊断逻辑

断言失败时执行以下诊断：

1. **截图**: 保存失败步骤的页面截图
2. **Snapshot 分析**: 通过 `browser_snapshot()` 获取当前页面结构
3. **源码定位**: 用 grep/read 找到失败元素的源码位置
4. **分类**:
   - `code_bug`: 组件缺失/未挂载/数据未渲染/逻辑错误 → 修复代码
   - `environment`: API 不通/服务未启动/数据库空 → 修复环境
   - `script_issue`: JOURNEYS.json 的 selector 与实际 DOM 不匹配 → 标记不修

## 修复约束

- **只改失败相关代码**，不引入新依赖，不重构无关代码
- **JOURNEYS.json 不可修改**（它是考官，不是考生）
- 修复后等待 HMR 刷新 + 重新 navigate
- 每轮修复后记录到修复轨迹

## setup 失败处理

1. 尝试执行 setup.steps
2. 如果 `assert_response` 失败:
   - 检查网络连通性（ping API endpoint）
   - 检查请求参数是否正确
   - 检查代码中的 API 接入
3. 代码问题 → 修复 → 重试
4. 环境问题 → 尝试修复 → 重试
5. 最多 3 轮修复
6. 超限 → 如果 `fallback.allowed` → 降级（标记 DEGRADED）→ 否则 FAIL

## 断点续测

- `checkpoint: true` 的步骤完成时，保存状态到 `.journey-state.json`:
```json
{ "scene_id": "SCENE-003", "last_step": 4, "timestamp": "...", "context": {} }
```
- 下次执行时检查此文件，从 checkpoint 恢复

## 输出

### 结构化验收报告

```
# 验收报告
执行时间: YYYY-MM-DD HH:mm
场景总数: N

## 结果汇总
| 场景 | 名称 | 结果 | 轮次 | 修复次数 |
|------|------|------|------|---------|

## 统计
- PASS: X / N
- FAIL: Y / N
- DEGRADED: Z / N

## 断言覆盖率
- L1 (存在性): X/Y 通过
- L2 (非空): X/Y 通过
- L3 (结构): X/Y 通过
- L4 (质量): X/Y 通过

## 修复轨迹
### SCENE-XXX
- 轮次 1: 失败于 Step 4, assert_not_empty → 修复: src/components/Table.tsx 添加数据渲染
- 轮次 2: 通过

## 未通过场景详情
### SCENE-XXX
- 最终失败步骤: Step N
- 预期: ...
- 实际: ...
- 截图: screenshots/SCENE-XXX-step-N.png
```

### 覆盖审计

报告末尾附加：
- PRD 中哪些 task 没有被 JOURNEYS scene 覆盖
- JOURNEYS 中哪些 scene 没有被 PRD task 引用

## 进度更新

```json
"journey_runner": {
  "status": "completed",
  "scenes_passed": 12,
  "scenes_failed": 2,
  "scenes_degraded": 1,
  "auto_fixes": 5,
  "unresolved": ["SCENE-008", "SCENE-015"]
}
```
