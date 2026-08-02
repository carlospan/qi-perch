# 包 12 实施验收记录 · CodeBuddy（方案 Agent）

> **用途**：方案 Agent 对 Cursor 编码回执的实测验收结论。
> **依据**：`包12-PR方案-Cursor编码请求.md`（方案）、`包12-PR方案-Cursor编码回执.md`（回执）、代码实测（git diff / pytest / ruff）。
> **撰写**：CodeBuddy（2026-08-02）
> **结论**：✅ **验收通过**（实测核对，非仅信回执）。

---

## 一、实测清单

| 项 | 结果 |
|----|------|
| `git diff --stat` 改动范围 | 仅 `qi/core/brain.py`（+69 行）；`qi/action/budget.py` **未改** ✅ 符合红线 |
| `pytest tests/test_resource_ledger.py` | **15 passed** ✅ |
| `pytest` 全量 | **386 passed**（基线 371 + 新增 15）✅ 不回退 |
| `ruff check qi/stasis tests/test_resource_ledger.py qi/core/brain.py` | **All checks passed!** ✅ |
| R3 拒绝列表（`satisfaction`/`valence_up`/`user_pleased`） | 单测参数化钉死，拒绝且不改 `income` ✅ |
| 防刷（间隔 5s + 日帽 200） | 单测断言 ✅ |
| 日限不掺余额（`ActionBudget` 隔离） | 单测断言 `ledger.balance` 不受 `budget.record` 影响 ✅ |
| 拔管（FailLLM）仍记账 | `test_brain_heartbeat_ledger_no_llm_dependency` 断言 compute/token 仍增、snapshot/restore 往返一致 ✅ |
| balance 滚动窗口趋负 / `force_balance(0)` | 单测断言 ✅ |
| storage 每 N 拍估算 | `test_brain_storage_estimate_on_nth_beat` 断言第 N 拍才写 ✅ |

## 二、代码核查（随机审计）

- `ledger.py`：`balance = income_window − spend_window`（滚动 deque，`WINDOW_BEATS=1000` 老化）；`credit_income` 先判 `INCOME_SOURCES_REJECTED` 再判白名单，拒绝/防刷/日帽齐全；`snapshot`/`restore` 含 datetime 序列化，与 `ActionBudget` 同构；`force_balance` 清窗口置 `_forced_balance`（包 14 注入断粮接口已就位）。
- `brain.py` 埋点：心跳开头 `tick_window` + `t0`；记忆检索/说话/主动开口 `add_token_cost`；`effective_interaction` 仅 `pending is not None`；storage 每 N 拍；末尾 `add_compute(perf_counter 差值)`；`restore_state`/`save_state` 接 `body_memory` key=`resource_ledger`。**全部 `try/except` 不阻断主流程**，未改既有情绪/行为逻辑。
- `budget.py` 确认未改，仅 `brain.py` 加职责边界注释。

## 三、与方案偏差（可接受）

| 偏差 | 处置 |
|------|------|
| LLM `usage` 字段 gateway 未暴露 → 一律字符估算（`len//4`，空回复 `ATTEMPT_TOKEN_COST=10`） | 方案已允许 ✅ |
| `online_presence` 白名单已留，brain 初版未每拍刷 online 收入 | 方案写"可选"，防刷考量合理 ✅ |

## 四、小瑕疵（不卡验收，建议后续顺手）

- `brain.py` 顶部将 `from qi.stasis.ledger import (...)` 拆成两个分离 import 块（常量 + `BODY_MEMORY_KEY`）。功能无碍（ruff 未报），建议合并为一处 import 提升整洁度（可在包 13 顺手改，或独立小 PR）。

## 五、验收结论

**包 12（N0 资源账本）验收通过。** 账本地基成立：记账接入完整、R3 红线+防刷+日限隔离已落成断言、拔管友好、可持久化。未压 energy（归包 13）、未封存（归包 14），红线守全。

**下一包**：出包 13 PR 方案（内稳态压力动力学），接 `ledger.balance` / `starving` 占位，按 v2 必改 1 调制 `energy_baseline_offset`（禁盖写）。

---

*CodeBuddy 验收记录 · 包 12 · 2026-08-02*