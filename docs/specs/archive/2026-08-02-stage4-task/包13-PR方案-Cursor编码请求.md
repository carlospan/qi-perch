# 包 13 PR 方案 · 内稳态压力动力学（Cursor 编码请求）

> **性质**：PR 方案（SDD 过程稿）。方案 Agent（CodeBuddy）出方案，Cursor 执行编码；过程稿落盘于 `docs/specs/archive/2026-08-02-stage4-task/`，Cursor 自行读取，无需转发。
> **依据**：`specs/tasks/2026-08-02-阶段四-主线.md`（v2 包 13）、`specs/stages/stage-4.md`、架构方案 §N0 / 附录 Q0；`qi/stasis/ledger.py`（包 12，`balance`/`starving`/`force_balance`）、`qi/core/emotion.py`（`step_emotion`/`apply_circadian`/`CIRCADIAN_ENERGY`/目标趋近式）、`qi/core/rhythm.py`（`next_interval` energy 拉长）、`qi/core/brain.py`（心跳每拍调 `step_emotion`、接 `ledger`）、包 12 验收记录。
> **撰写**：CodeBuddy（2026-08-02，包 13 单包 PR 方案）
> **依赖**：包 12 已验收（`ledger.balance` / `ledger.starving` 占位就位）。
> **前置**：本包用到的 ledger 接口已实测存在（`balance` 滚动窗口、`starving` 字段、`force_balance`）。

---

## 〇、本包纪律红线（v2 必改 1 落地）

1. **energy 只调制「稳态目标偏移」，禁止每拍盖写 `emotion.energy`**。现有 `step_emotion` 是目标趋近式（decay 拉向 `baseline_for`、circadian 拉向时刻醒度），本包注入 `energy_baseline_offset` 由既有趋近式生效，**不推倒任何公式、不新增平行常数**（除非文档化）。
2. **复用现有 `energy < 0.3` 闸门**作为节流/休眠接入点（prompt_builder / tts / avatar / trace / intention / modulate_impact 已用），**不另起一套**。
3. **本包只产 `starving` + 分层应对链；不 `sys.exit`、不写 checkpoint 文件**（退出与封存归包 14）。库代码禁止硬 `sys.exit`。
4. **多样且情境敏感**：同一 `balance` 下，改变 `attachment`/`security`/`energy` 组合 → 应对权重向量不同（防单一反射，Q0 缓解(a)）。"求助/迁移"最低可观测形态 = 写意向痕迹（`body_memory` 或 trace broadcast），须在代码有落点。
5. **静默死防护**：`starving` 后必先有应对痕迹再停（包 14 接）；本包确保 `starving` 置位前应对链已触发。
6. **经验改变阈值（Q0 缓解(b)）**：留 `pressure_sensitivity` 可调接口，**禁止**硬接未真训回放改阈值（会假绿）。
7. **不写死测试基线数字**，统一「pytest 全绿，不回退既有基线（386）」。

---

## 一、新增文件

### 1.1 `qi/stasis/pressure.py`（新增，核心交付）

**`balance → energy_baseline_offset` 映射**（最小侵入、与 circadian 同构）：
```python
STASIS_APPROACH_RATE = 0.05   # 与 CIRCADIAN_APPROACH_RATE 同量级
# 余额低 → 负偏移（energy 目标下移）；余额充裕 → 微正偏移
def balance_to_energy_offset(balance: float, *, sensitivity: float = 1.0) -> float:
    # 在 balance ∈ [-B, +B] 区间映射到 offset ∈ [-0.5, +0.3]
    # clamp 防顶满；sign 由 balance 决定
    raw = clamp(balance * 0.05 * sensitivity, -0.5, 0.3)
    return raw
```

**分层应对链（`PressureResponse` 数据类或 dict）**：
- 输入：`ledger`（balance / starving）、`emotion`（energy / security / attachment 等）、`beat`
- 输出应对权重向量：`throttle`（节流）、`rest`（休眠）、`seek_help`（求助）、`migrate`（迁移）倾向，由内稳态维度组合决定
- 分层（按 `balance` 与 `energy`）：
  - `balance > 0` 且 energy 正常 → 无特别应对（权重近 0）
  - `balance <= 0`（但断粮未持续）→ 节流权重升（`throttle` 主导）
  - 更低 / energy 趋低 → 休眠权重升（`rest`）
  - `balance <= 0` 持续超 `starve_beats` → 置 `starving=True`，`seek_help`/`migrate` 意向权重升（写痕迹）
- **多样可测**：构造固定 `balance`，改变 `emotion.attachment`/`security` → `throttle/seek_help/migrate` 相对权重不同（单测断言，防单一反射）
- **`starve_beats`**：默认如 `STAVE_BEATS = 30`（可配置）；计数 `ledger` 连续 `balance <= 0` 的拍数（或在 pressure 内维护 `_low_balance_streak`）

**接口（供 brain 调用）**：
- `compute_pressure(ledger, emotion) -> PressureResponse`：返回 offset + 应对权重
- `maybe_mark_starving(ledger, emotion, beat) -> bool`：判定是否置 `starving`，写 `ledger.starving=True` 并返回；触发时写求助/迁移意向痕迹（见 2.2）
- `leave_intent_trace(...)`：把 seek_help / migrate 意向写入 `body_memory`（key 如 `stasis_intents`）或 trace broadcast，供包 14 checkpoint 收集

### 1.2 `tests/test_stasis_pressure.py`（新增）

---

## 二、修改文件

### 2.1 `qi/core/emotion.py`（最小侵入）

在 `step_emotion` 签名增 `energy_baseline_offset: float = 0.0`，并在 `apply_circadian` 之后、返回前，追加一步能量目标偏移趋近（与现有趋近式同构，**不**直接赋值）：
```python
def step_emotion(emotion, now, decay_multiplier=1.0, relationship_stage=None, *, energy_baseline_offset=0.0):
    e = apply_decay(...)
    e = apply_coupling(...)
    e = apply_mood_cycle(...)
    e = apply_circadian(e, now.hour)
    if energy_baseline_offset:
        # 把 energy 朝 (circadian 目标 + offset) 趋近，与现有趋近式同构，不盖写
        target = CIRCADIAN_ENERGY.get(now.hour % 24, 0.5) + energy_baseline_offset
        e.energy += STASIS_APPROACH_RATE * (target - e.energy)
    return clamp_emotion(e)
```
> 注意：`STASIS_APPROACH_RATE` 若定义在 `pressure.py`，`emotion.py` 可本地定义常量或 import；建议 `emotion.py` 本地定义 `STASIS_APPROACH_RATE=0.05`（文档化），避免循环依赖。`pressure.py` 的 `balance_to_energy_offset` 只算 offset 数值，不依赖 emotion 模块。

### 2.2 `qi/core/brain.py`

1. **每拍读账本余额 → 算 offset → 注入 `step_emotion`**：
   - 现有调用 `self.emotion = step_emotion(self.emotion, now, decay_multiplier=decay_mult, relationship_stage=self.relationship_stage)`（约 371 行）
   - 改为先 `offset = balance_to_energy_offset(self.ledger.balance)`（来自 `pressure`），再 `step_emotion(..., energy_baseline_offset=offset)`
   - 全部包 `try/except` 不阻断
2. **应对链 + `starving` 标记**（在 `step_emotion` 之后、内在生命之前，或 trace 之前）：
   - `resp = compute_pressure(self.ledger, self.emotion)`
   - 若 `resp.throttle > 0`：利用现有 `energy < 0.3` 闸门自动节流（无需额外代码）；可加 `logger.debug` 记节流状态供 trace
   - 若 `resp.rest > 0`：同样靠 `next_interval` 的 energy 拉长自然休眠（无需额外代码），debug 记录
   - `if maybe_mark_starving(self.ledger, self.emotion, self.heartbeat_count)`：置 `starving` 时调用 `leave_intent_trace(...)` 写求助/迁移意向到 `body_memory`（key `stasis_intents`），**不 exit、不写 checkpoint 文件**
3. **动机痕迹旁路**：`leave_intent_trace` 把 seek_help/migrate 意向 `set_body_memory("stasis_intents", {...})`（append 模式或最近一条）；包 14 的 checkpoint 会收集此键。

### 2.3 `qi/stasis/__init__.py`
导出 `compute_pressure` / `maybe_mark_starving` / `balance_to_energy_offset`（与 `ResourceLedger` 同列）。

---

## 三、测试 `tests/test_stasis_pressure.py`（新增）

- `balance_to_energy_offset`：balance 低 → 负 offset；balance 高 → 非负；clamp 不顶满
- **energy 接法（关键防回归）**：构造 `emotion` + `pressure offset`，跑 `step_emotion(..., energy_baseline_offset=offset)` 多拍，断言 `energy` **趋近** `(circadian_target + offset)` 而非被单拍盖写；与无 offset 对比 `energy` 更低（balance 低时）
- **节流/休眠可观测**：balance 低 → `compute_pressure` 返回 `throttle>0`（且 `energy` 经 step_emotion 走低后 `< 0.3` 触发既有闸门，可用 `next_interval` 断言间隔拉长）
- **断粮标记**：构造 `ledger.force_balance(0)` 连续超 `starve_beats` 拍 → `maybe_mark_starving` 返回 True、`ledger.starving == True`；未持续则 False
- **多样应对（防单一反射）**：固定 `balance<=0`，改变 `emotion.attachment`/`security` → `seek_help`/`migrate` 相对 `throttle` 权重不同（单测断言）
- **意向痕迹**：`maybe_mark_starving` 触发时 `body_memory` 出现 `stasis_intents` 键（或 trace 有记录）；非空壳
- **静默死防护（负例）**：直接 `ledger.starving=True` 而无应对痕迹 → 测试断言"回退条件"（设计：`maybe_mark_starving` 内部先写痕迹再置位；若发现置位前无痕迹则应失败——可测）
- **Q0(b) 接口**：`pressure_sensitivity` 可调生效（改 sensitivity → offset 幅度变），但不接未真训回放
- **fake-provider 全失败**：压力动力学不依赖 LLM（用 ledger 直接构造）
- `pytest` 全绿（不回退 386）；`ruff check` 通过

---

## 四、验收口径（方案 Agent 验收用）

- `pytest -q tests/test_stasis_pressure.py` 通过；全量 `pytest -q` 不回退 386
- `ruff check qi/stasis qi/core/emotion.py qi/core/brain.py tests/test_stasis_pressure.py` 无错
- `git diff` 核查：`emotion.py` 仅 `step_emotion` 增 offset 趋近（无盖写、无公式推倒）；`brain.py` 仅增 offset 注入 + 应对链 + 意向痕迹；**无 `sys.exit`**；`budget.py` 未改
- 随机审计：确认 `energy` 未被盖写（grep 无 `emotion.energy =` 在 pressure/brain 新增处）；确认 `starving` 置位前有意向痕迹
- 真机不阻塞（本包只改动力学，不退出）

---

## 五、Cursor 回执要求

完成后在 `docs/specs/archive/2026-08-02-stage4-task/包13-PR方案-Cursor编码回执.md` 落盘：
1. 实际落地文件清单（新增/改动）
2. 关键实现决策（`balance_to_energy_offset` 映射参数、`starve_beats`、`_low_balance_streak` 维护方式、意向痕迹落点、是否触发既有 `energy<0.3` 闸门）
3. `pytest` / `ruff` 实测结果（贴关键行）
4. 与方案偏差与理由（如有）
5. 自认风险 / 待方案 Agent 验收关注点

> 纪律：一包一 PR；过程稿落盘 Cursor 自行读；方案 Agent 出方案/验收，Cursor 不决策架构。

---

*包 13 PR 方案 · 阶段四第二包 · 2026-08-02*