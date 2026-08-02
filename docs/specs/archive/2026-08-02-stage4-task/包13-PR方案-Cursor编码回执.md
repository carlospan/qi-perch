# 包 13 实施 PR · Cursor 编码回执

> **用途**：开工前理解确认 + 完工结果；交方案 Agent（CodeBuddy）实施验收。  
> **依据**：`包13-PR方案-Cursor编码请求.md`（内含完整 PR 方案）、主线 v2 包 13、包 12 ledger。  
> **撰写**：Cursor（2026-08-02）

---

## 【开工前理解确认段】

已读取包 13 编码请求。理解：

### `qi/stasis/pressure.py`
- `balance_to_energy_offset` → 负余额压 energy 目标；`pressure_sensitivity` 可调。
- `compute_pressure` → throttle/rest/seek_help/migrate 权重（attachment/security 调制多样性）。
- `maybe_mark_starving`：连续 `balance<=0` 超 `starve_beats` → 先写 `stasis_intents` 再置 `ledger.starving`；不 exit。
- `_low_balance_streak` 维护在 pressure 模块或 ledger 旁路。

### `emotion.py`
- `step_emotion(..., energy_baseline_offset=0.0)`：circadian 后对 `(CIRCADIAN_ENERGY[h]+offset)` 趋近；本地 `STASIS_APPROACH_RATE=0.05`；不盖写。

### `brain.py`
- 算 offset → 注入 step_emotion；compute_pressure + maybe_mark_starving + leave_intent_trace；无 sys.exit。

本段写完即继续写码。

---

## 【完工结果段】

### 1. 落地文件清单

| 路径 | 动作 |
|------|------|
| `qi/stasis/pressure.py` | 新增 |
| `qi/stasis/__init__.py` | 导出 pressure API |
| `qi/core/emotion.py` | `step_emotion` 增 `energy_baseline_offset` 趋近；`STASIS_APPROACH_RATE` |
| `qi/core/brain.py` | offset 注入 + `compute_pressure` / `maybe_mark_starving` |
| `tests/test_stasis_pressure.py` | 新增 11 用例 |
| `budget.py` | **未改**；无 `sys.exit`；无 checkpoint 文件 |

### 2. 关键实现决策

| 项 | 决策 |
|----|------|
| offset 映射 | `clamp(balance * 0.05 * sensitivity, -0.5, 0.3)` |
| starve_beats | 默认 30；config `stasis.starve_beats` / `pressure_sensitivity` 可调 |
| streak | 模块级 `_low_balance_streak`（`reset_low_balance_streak` 测用） |
| 意向痕迹 | `body_memory` key=`stasis_intents`（seek_help/migrate/balance/beat） |
| 节流/休眠 | 权重产出 + 既有 `energy<0.3` / `next_interval`；不另起闸门 |
| starving 顺序 | **先** `leave_intent_trace` **再** `ledger.starving=True` |

### 3. 测试结果

```
python -m pytest -q tests/test_stasis_pressure.py  → 11 passed
python -m pytest -q                               → 397 passed in 46.63s
python -m ruff check qi tests                     → All checks passed!
```

### 4. 偏差

- 无重大偏差；`sys.exit` 审计改为 AST 查调用（docstring 曾含字面量）。

### 5. 验收关注点

- energy 仅趋近、无盖写。
- 包 14 应收集 `stasis_intents` + `ledger.starving`；本包不 halt。

---

*Cursor 编码回执 · 包 13 · 2026-08-02*
