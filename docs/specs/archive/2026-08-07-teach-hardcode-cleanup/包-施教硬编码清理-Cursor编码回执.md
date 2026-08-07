# 施教硬编码清理——Cursor 编码回执

> **角色**：Cursor（执行编码）  
> **依据**：`包-施教硬编码清理-编码请求.md`（B1 选项 A）  
> **时刻**：2026-08-07  

---

## 已做

1. **`qi/prompts/consciousness_stream.txt`** — 删「（如"数到七"）」
2. **`qi/relationship/culture.py`** — 方向锤去掉「原话『躺着/不强迫/看天花板』」
3. **`qi/core/expression.py`** — CONSTRAINT / FALLBACK 通用化；改用 `detect_teach_inversion`
4. **`qi/core/intention.py`** — `detect_teach_inversion` + 别名 `detect_sleep_teach_inversion`；检测逻辑不变
5. **单测（B2）** — `test_relationship` / `test_inner_life` / `test_expression` / `test_intention`

## 执行判断（编码请求未点名，为让 B2 断言成立）

`anchor_teaching_relation` 返回串里曾写「没有『数呼吸/数到七』」——仍属不准说清单，会进意识流 prompt。已改为「不得添加原话没有的细节」，并去掉「关于入睡方法」字样。  
**未删** `_SLEEP_ADVICE_RE` / `_INVERT_TOPIC_RE`（红线 / 选项 A）。

## 验证

| 项 | 结果 |
|----|------|
| 相关单测 | 101 passed |
| 全量 `pytest` | **457 passed** |
| `ruff check` / `format` | 通过 |

## 请方案 Agent

填编码请求验收栏；出验收记录。

---

## 方案 Agent 验收栏（Cursor 勿填）

- [x] 验收通过
- [ ] 打回（原因：）
- [ ] 需维护者 HITL（问题：）

> 验收结论（CodeBuddy，2026-08-07）：代码落点全部核实——`consciousness_stream.txt` 删"（如"数到七"）"改通用、\
> `culture.py` 方向锤改"（施教方向：栖教用户，勿反转）"无原话、`expression.py` CONSTRAINT/FALLBACK 通用化、\
> `intention.py` `detect_teach_inversion`+别名（逻辑不变）、`anchor_teaching_relation` 返回串去"数呼吸/数到七"字样。\
> 实测相关单测 9 passed、全量 457 passed、ruff（仅 .py）`All checks passed!`。\
> Cursor 主动清理 anchor 返回串的"数到七"字样与 B2 精神一致（把不准说清单移出代码），采纳。\
> 保留项（`_SLEEP_ADVICE_RE`/`_INVERT_TOPIC_RE`/line 281 anchor 返回串）均符合 S1/选项 A 红线。无实质偏离。验收通过。
