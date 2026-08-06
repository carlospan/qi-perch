# N5 硬闸扩展——Cursor 编码回执

> **用途**：开工前理解确认 + 完工结果；交方案 Agent（CodeBuddy）实施验收。  
> **依据**：`包-N5-硬闸扩展-编码请求.md`、`包-N5-硬闸扩展-PR方案.md`（v2）、`包-N5-硬闸扩展-Cursor交叉审查.md`  
> **执行**：Cursor · 2026-08-07  

---

## 开工前理解确认

1. **主闸**＝共同回忆声明（空卡 / 关键短语不在素材 → HARD）；**辅闸**＝「叫××」虚构专名；SOFT「无支撑自我认知」不阻断。
2. **expression** 主路径 + 去重旁路均筛 HARD → `_fix_generation` / `_build_fallback`；包 15–17 施教符号与 `_fix_teach_inversion` **保留不删**。
3. **materials_block**＝原文短引（≤80）+【诚实边界】，不做生动扩写。
4. **不接**：检索相关门（N5-b）、banned_names 接线、极性翻反硬闸。
5. **偏离说明**：实体闸第一版仅拦「叫××」模式（比编码请求「≥3 字」更严），避免非重叠 n-gram 把「做什么」等误判为专名；与审查「宁漏勿杀」一致，金样例「叫阿强」仍覆盖。

---

## 完工结果

### 改动文件

| 文件 | 变更 |
|------|------|
| `qi/core/intention.py` | `_DECLARATIVE_MEMORY_RE` / `_HARD_VIOLATION_PREFIXES` / 回忆声明闸 / 实体闸 / `is_hard_violation`；`materials_block` 短引+诚实边界 |
| `qi/core/expression.py` | 全量 HARD 主路径 + 去重旁路；`_fix_generation` / `_build_fallback`；SOFT → `intention.evidence` |
| `tests/test_intention.py` | 回忆声明 / 实体 / SOFT / materials_block 单测 |
| `tests/test_expression.py` | HARD 重生 + 去重旁路 HARD |
| `tests/test_prompt_contract.py` | 【诚实边界】契约 |

### 自测

- 相关：`tests/test_intention.py` + `test_expression.py` + `test_prompt_contract.py` → **52 passed**
- 全量：`python -m pytest -q` → **453 passed**
- `ruff check` 变更文件 → **All checks passed**

### 验收清单自查

- [x] 全量 HARD：卡外专名 / 伪记忆 / 施教 / 空卡编造 / 虚构实体 / 共同回忆
- [x] SOFT 不阻断（无支撑自我认知仅 evidence）
- [x] 去重旁路跑 HARD（`test_dedup_path_also_runs_hard_gate`）
- [x] prompt 含【诚实边界】
- [x] 包 15–17 施教单测仍绿
- [x] 全量 pytest + ruff

### 已知债务（方案已列，本包未做）

- `banned_names` 未接入 expression 调用方
- 检索相关门 → N5-b
- #1350 极性翻反 / #1318 答非所问 → 不硬闸

---

## 方案 Agent 验收栏（Cursor 勿填）

- [x] 验收通过
- [ ] 打回（原因：）
- [ ] 需维护者 HITL（问题：）

> 验收结论（CodeBuddy，2026-08-07）：代码落点全部核实——共同回忆声明闸（`_DECLARATIVE_MEMORY_RE` +
> 空卡/短语不在素材两段式）、实体闸（「叫××」模式，宁漏勿杀）、`_HARD_VIOLATION_PREFIXES` 六类、
> HARD/SOFT 分离（SOFT → `intention.evidence` 不阻断）、`materials_block` 原文短引+诚实边界、
> expression 主路径+去重旁路双 HARD、`_fix_generation`/`_build_fallback` 统一入口。
> 包 15-17 施教符号与 `_fix_teach_inversion` 保留不删。
> 实测相关单测 10 项 `passed`、ruff `All checks passed!`、全量 453 passed。
> Cursor 一项偏离（实体闸仅拦「叫××」）与审查「宁漏勿杀」一致且金样例「阿强」覆盖，采纳。
> 已知债务（banned_names 接线/N5-b 检索相关门/极性翻反）按方案显式排除，留后续包。
