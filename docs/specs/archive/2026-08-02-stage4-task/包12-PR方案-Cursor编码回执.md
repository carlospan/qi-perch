# 包 12 实施 PR · Cursor 编码回执

> **用途**：开工前理解确认 + 完工结果；交方案 Agent（CodeBuddy）实施验收。  
> **依据**：`包12-PR方案-Cursor编码请求.md`（内含完整 PR 方案）、主线 v2 包 12。  
> **撰写**：Cursor（2026-08-02）

---

## 【开工前理解确认段】

已读取包 12 编码请求（方案正文同文件）。理解：

### `qi/stasis/ledger.py`
- ResourceLedger：compute / token / storage / income；`balance = income_window − spend_window`（滚动窗口）。
- R3：`credit_income` 白名单 + 显式拒绝；防刷间隔+日帽；`force_balance` 测用。
- body_memory key=`resource_ledger`；snapshot/restore。
- **不**压 energy、不封存、不改 budget.py。

### `brain.py` 接入
- `__init__` 挂 ledger；heartbeat 计时/检索/说话/storage/收入；restore/save 读写 body_memory。
- 全部 try/except 不阻断主流程。
- ActionBudget 旁注释职责边界。

### 自决
- 滚动窗口：维护 deque of (beat, spend/income) 或简化用环形累计 + tick_window 老化。
- storage：`Path(db.db_path).stat().st_size`。
- token：无 usage 字段时用 `max(1, len//4)`；失败模板开口也记（字符估算）。
- 初版收入仅 `effective_interaction`（pending 非空）。

本段写完即继续写码。

---

## 【完工结果段】

### 1. 落地文件清单

| 路径 | 动作 |
|------|------|
| `qi/stasis/__init__.py` | 新增 |
| `qi/stasis/ledger.py` | 新增 `ResourceLedger` |
| `qi/core/brain.py` | 挂 ledger；心跳记账；save/restore body_memory |
| `tests/test_resource_ledger.py` | 新增 |
| `qi/action/budget.py` | **未改** |

### 2. 关键实现决策

| 项 | 决策 |
|----|------|
| 滚动窗口 | `_spend_events` / `_income_events` 为 `(beat, amount)` deque；`tick_window` 按 `WINDOW_BEATS=1000` 老化；`balance = income_window − spend_window` |
| `force_balance` | 清窗口并置 `_forced_balance`；后续真实收支清除强制值 |
| storage | `Path(db.db_path).stat().st_size`，每 50 拍 |
| token | 无 provider usage → `len//4`；空回复 → `ATTEMPT_TOKEN_COST=10` |
| 收入 | 初版仅 `effective_interaction`（pending 非空）；防刷 5s / 日帽 200 |
| compute→spend | `add_compute` 同步 `record_spend(seconds * 1.0)` |

### 3. 测试结果

```
python -m pytest -q tests/test_resource_ledger.py  → 15 passed
python -m pytest -q                               → 386 passed in 61.22s
python -m ruff check qi tests                     → All checks passed!
```

### 4. 与方案偏差

- LLM `usage` 字段当前 gateway 无暴露 → 一律字符估算（方案允许）。
- `online_presence` 白名单已留，brain 初版未每拍刷 online 收入（防刷；方案写可选）。

### 5. 验收关注点

- R3 拒绝列表与防刷单测已钉死。
- 包 13 接 `ledger.balance` / `starving` 占位即可；本包未压 energy。

---

*Cursor 编码回执 · 包 12 · 2026-08-02*
