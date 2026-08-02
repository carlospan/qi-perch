# 包 12 PR 方案 · N0 资源账本（Cursor 编码请求）

> **性质**：PR 方案（SDD 过程稿）。方案 Agent（CodeBuddy）出方案，Cursor 执行编码；过程稿落盘于 `docs/specs/archive/2026-08-02-stage4-task/`，Cursor 自行读取，无需转发。
> **依据**：`specs/tasks/2026-08-02-阶段四-主线.md`（v2 包 12）、`specs/stages/stage-4.md`、架构方案 §N0 / §七 R3；`qi/action/budget.py`（ActionBudget body_memory 模式）、`qi/memory/body_memory.py`（`db.get_body_memory/set_body_memory` 接口）、`qi/core/brain.py`（心跳埋点锚点）、`qi/core/emotion.py`（情绪动力学，本包不改）。
> **撰写**：CodeBuddy（2026-08-02，包 12 单包 PR 方案）
> **依赖**：无（阶段四首包）。验收通过后出包 13。

---

## 〇、本包纪律红线（重申）

1. **只建账本与记账接入**：不接内稳态压力（归包 13）、不做封存（归包 14）。
2. **`ActionBudget`（`qi/action/budget.py`）仅「并存」**：本包**原则上不改 `budget.py`**；只在 `Brain` 侧标注两者职责边界（账本 = C2 动力学，日限 = 安全阀），不增行为、不增 PR 噪音。
3. **R3 红线**：`credit_income` 仅接受白名单源，**拒绝** `satisfaction / valence_up / user_pleased` 等讨好源；日限（`can_autonomous`）**不得计入余额**。
4. **防刷**：有效交互须钝感口径（最短间隔 + 日帽，或「被回应」才计）。
5. **纯 Python / 零重依赖**；不引 torch/transformers；不依赖 LLM 成功才能记账（失败调用也记尝试成本）。
6. **不写死测试基线数字**，统一写「pytest 全绿，不回退既有基线」。

---

## 一、新增文件

### 1.1 `qi/stasis/__init__.py`（新增）
导出版本常量与 `ResourceLedger`（便于包 13/14 及测试 import）：
```python
from qi.stasis.ledger import ResourceLedger, INCOME_SOURCES_WHITELIST

__all__ = ["ResourceLedger", "INCOME_SOURCES_WHITELIST"]
```

### 1.2 `qi/stasis/ledger.py`（新增，核心交付）

**数据模型 `ResourceLedger`**（pydantic 或 plain dataclass，建议 plain dict + 方法类，与 `ActionBudget` 风格一致）：

| 字段 | 含义 | 记法 |
|------|------|------|
| `compute_seconds` | 本进程 CPU 累计（心跳认知耗时） | 每拍累加 `perf_counter` 差值 |
| `token_budget` | 语言器官调用 token 估算（含远程 LLM） | 说话/检索入账；失败调用也记尝试成本 |
| `storage_bytes` | 记忆占用估算（db 文件大小） | 每 `STORAGE_ESTIMATE_EVERY_N_BEATS` 拍估算一次 |
| `income` | 累计收入（白名单源） | `credit_income` 仅白名单 |
| `spend_window` | 滚动窗口内支出累计 | 见 `balance` |
| `income_window` | 滚动窗口内收入累计 | 见 `balance` |
| `balance` | **滚动窗口净额** | `income_window − spend_window`（断粮判定用） |
| `starving` | 断粮标记（包 13 写，本包仅占位 `False`） | 预留字段 |
| `last_interaction_credit_at` | 上次收入记账时刻（防刷最短间隔） | — |
| `income_day_count` | 当日收入笔数（防刷日帽） | 跨天重置 |
| `income_day` | 当日日期字符串 | — |

**常量：**
- `BODY_MEMORY_KEY = "resource_ledger"`（命名空间与 `world.*` / corpus 分离）
- `INCOME_SOURCES_WHITELIST: frozenset = frozenset({"effective_interaction", "online_presence"})`
- `INCOME_SOURCES_REJECTED: frozenset = frozenset({"satisfaction", "valence_up", "user_pleased"})`（显式拒绝，单测断言）
- `INCOME_MIN_INTERVAL_SEC = 5.0`（防刷最短间隔）
- `INCOME_DAILY_CAP = 200`（防刷日帽，初版拍脑袋，可调）
- `STORAGE_ESTIMATE_EVERY_N_BEATS = 50`（不每拍 stat）
- `WINDOW_BEATS = 1000`（滚动窗口长度，单位拍；断粮用滚动窗口余额）

**方法（最小接口，供包 13/14 复用）：**
- `add_compute(seconds: float)` → 累加到 `compute_seconds`
- `add_token_cost(n: int)` → 累加到 `token_budget` 与 `spend_window`
- `estimate_storage(bytes_: int)` → 每 N 拍调用，置 `storage_bytes`（不每拍）
- `credit_income(source: str, amount: float = 1.0) -> bool` → **仅白名单接受**；拒绝 `INCOME_SOURCES_REJECTED` 及非白名单；防刷（最短间隔 + 日帽）通过才记账，返回是否入账
- `record_spend(amount: float)` → 累加到 `spend_window`（与 `add_token_cost` 区分：compute 也走 spend）
- `force_balance(value: float)` → 测试双用（包 14 注入断粮）
- `tick_window(beat: int)` → 滚动窗口推进（超窗口的旧账老化，简化版可只维护累计差额；若实现滚动窗口老化，须保证 `balance` 在窗口内正确）
- `snapshot() -> dict` / `restore(data: dict | None)` → 复用 `ActionBudget` 同模式（含 `datetime` 序列化）
- `description() -> str` → 人类可读账本摘要（"这周花了多少 compute / 攒了多少 income"），不报数值堆。

**`balance` 实现建议（防歧义，v2 已定）：**
- 简化稳妥版：`balance = income_window − spend_window`，二者均为**滚动窗口累计**（维护一个定长 deque 或环形计数；窗口外老账移出）。`force_balance(0)` 测试双直接清零窗口。
- 只要 `balance` 语义一致、可测、不被历史老本撑死即可；具体老化实现交 Cursor，但必须保证「长期无收入 → balance 趋 0/负」。

---

## 二、修改文件（接入点）

### 2.1 `qi/core/brain.py`

1. **`__init__`**：`self.ledger = ResourceLedger()`（账本实例）。
2. **`_heartbeat` 记账埋点**（按下列锚点，**不改既有情绪/行为逻辑**，只增记账调用，且全部包 `try/except` 不阻断主流程）：
   - **心跳认知耗时**：在 `_heartbeat` 开头 `t0 = time.perf_counter()`，末尾 `self.ledger.add_compute(time.perf_counter() - t0)`（import `time`）。
   - **记忆检索**：`memory.working.get_context()` 与 `load_recent_messages` 调用处（约 303–306 行、411 行），包一层 `self.ledger.add_token_cost(N)`（N 取常量如 `MEM_RETRIEVAL_TOKEN_COST = 20`），注明估算。
   - **说话 token**：`self.expression.express(...)` 返回 `response` 后（约 445 行 dialogue、542 行 proactive），若 `response` 非空：优先取 `card.usage` / provider usage 的 token 数（若有），否则 `len(response)//4`；`self.ledger.add_token_cost(tokens)`。
   - **storage 估算**：每 `STORAGE_ESTIMATE_EVERY_N_BEATS` 拍（用 `self.heartbeat_count`），若 `self._db` 可用，估算 `db` 文件大小入 `storage_bytes`（调用 `db` 已有的 size 方法或 `os.path.getsize` on db path；若 db 不暴露，用 `0` 占位并注释"真机接 db.size"，不阻断）。
   - **收入记账**：`pending is not None`（有用户消息 = effective_interaction）时，调 `self.ledger.credit_income("effective_interaction")`；`user_online` 真机持续在线可另记 `online_presence`（可选，初版可仅 effective_interaction）。**不**以 `valence`/`impact`/满意度为源。
3. **`restore_state`**：`ledger_data = await db.get_body_memory("resource_ledger")`；`self.ledger.restore(ledger_data)`（在 restore emotion/action 附近）。
4. **`save_state`**：`await db.set_body_memory("resource_ledger", self.ledger.snapshot())`（在 save_emotion 附近）。
5. **职责边界注释**：在 `self.action` / `self.proactive` 初始化附近加一行注释：「ActionBudget 日限 = 安全阀，不计入 C2 账本余额；两者并存，职责分离」，不改 `budget.py`。

### 2.2 `qi/action/budget.py`
**本包不修改**（仅并存）。若 Cursor 判断必须改，只允许加注释，不得增行为，并在回执中说明。

---

## 三、测试 `tests/test_resource_ledger.py`（新增）

- `add_compute` 每拍 `compute_seconds` 递增
- `add_token_cost`：说话/检索入账正确；**失败调用也记账**（拔管友好，构造无 provider 场景断言仍入账）
- `estimate_storage`：每 N 拍才更新，不每拍变；`storage_bytes` 合理
- `snapshot` / `restore` 往返一致（含 datetime 序列化）
- **R3 契约**：`credit_income("satisfaction" / "user_pleased" / "valence_up", ...)` 返回 `False` 且不改变 `income`；仅 `effective_interaction` / `online_presence` 入账（断言）
- **防刷**：高频（< `INCOME_MIN_INTERVAL_SEC`）重复 `credit_income` 不抬升 `income`；超 `INCOME_DAILY_CAP` 后不再入账
- **日限不充当收入**：`ActionBudget.can_autonomous` 状态变化不影响 `ledger.balance`（断言隔离）
- **balance 语义**：无收入持续 tick → `balance` 趋 0/负（断粮前提，包 14 复用）；`force_balance(0)` 生效
- **fake-provider 全失败**：账本记账不依赖 LLM（拔管判据）
- `pytest` 全绿（不回退既有基线）
- `ruff check` 通过

---

## 四、验收口径（方案 Agent 验收用）

- `pytest -q` 全绿（含 `tests/test_resource_ledger.py` 新用例）
- `ruff check qi/stasis tests/test_resource_ledger.py` 无错
- `git diff` 核查：仅新增 `qi/stasis/`、改 `brain.py` 记账埋点 + restore/save 接入；`budget.py` 未改或仅注释
- 真机跑数天后账本 `description()` 能说出"这周花了多少 compute / 攒了多少 income"；收入曲线不含任何讨好源
- 随机审计：确认 `credit_income` 拒绝列表生效、防刷生效、日限未掺入余额

---

## 五、Cursor 回执要求

完成后在 `docs/specs/archive/2026-08-02-stage4-task/包12-PR方案-Cursor编码回执.md` 落盘：
1. 实际落地文件清单（新增/改动）
2. 关键实现决策（尤其 `balance` 滚动窗口实现方式、`storage` 估算接法、income 防刷具体参数）
3. `pytest` / `ruff` 实测结果（贴关键行）
4. 与方案的偏差与理由（如有）
5. 自认风险 / 待方案 Agent 验收关注点

> 纪律：一包一 PR；过程稿落盘 Cursor 自行读；方案 Agent 出方案/验收，Cursor 不决策架构。

---

*包 12 PR 方案 · 阶段四首包 · 2026-08-02*