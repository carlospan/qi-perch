# 包 14 PR 方案 · 状态封存 / 迁移 + 断粮测试验收（Cursor 编码请求）

> **性质**：PR 方案（SDD 过程稿）。方案 Agent（CodeBuddy）出方案，Cursor 执行编码；过程稿落盘于 `docs/specs/archive/2026-08-02-stage4-task/`，Cursor 自行读取，无需转发。
> **依据**：`specs/tasks/2026-08-02-阶段四-主线.md`（v2 包 14）、`specs/stages/stage-4.md`（判据 #1 唯一权威）、`包13-PR方案-CodeBuddy验收记录.md`；`qi/stasis/ledger.py`（`snapshot`/`restore`/`ResourceLedger.restore`/`starving`）、`qi/stasis/pressure.py`（`stasis_intents` 键、`PressureResponse`）、`qi/core/brain.py`（`start` 循环 / `restore_state`/`save_state` / body_memory 键）、`qi/world/model.py`（`WorldModel.snapshot`，**无 restore**）、`qi/action/budget.py`（`ActionBudget.snapshot/restore`）、`qi/core/emotion.py`（`EmotionState`）。
> **撰写**：CodeBuddy（2026-08-02，包 14 单包 PR 方案，阶段四最后一包 / 退出判据）
> **依赖**：包 12（`ledger`）、包 13（`pressure`/`stasis_intents`/`starving` 标记）已验收。
> **退出判据**：判据 #1 断粮测试通过（限制资源后观察到节流/求助/迁移应对行为链而非直接死亡；状态可封存迁移）。

---

## 〇、本包纪律红线（v2 必改 2/4 落地）

1. **优雅停（H2 定稿）**：库内**禁止硬 `sys.exit`**；注入 `on_halt: Callable` 钩子，默认 `alive=False` / 停心跳循环；仅 CLI/`__main__` 在 `on_halt` 内 `sys.exit(0)`。测试注入 `on_halt` 伪实现不炸。
2. **封存粒度（H3 定稿）**：索引 + 关键状态（emotion、ledger、world、action_budget、proactive_gate、stasis_intents 等 body_memory 键、动机旁路 `emotion.curiosity`）；**不重存整个 db**（太大），存索引+关键状态，迁移后由 db 重建。
3. **非空壳（防假绿）**：checkpoint 须含可 restore 字段；restore 后关键字段须相等，否则判据「可迁移」假绿。
4. **断粮链时间轴（v2 必改 2）**：节流 → 休眠 → `starving` → checkpoint 文件存在 → `on_halt` 被调；负例：静默死（无痕迹直接停）必须失败（回退条件可测）。
5. **职责切割（v2 必改 2）**：本包**不重做账本公式**（包 12）、**不重做压力动力学**（包 13）；只做封存/restore/优雅停/端到端验收。
6. **不写死测试基线数字**，统一「pytest 全绿，不回退既有基线（397）」。

---

## 一、新增文件

### 1.1 `qi/stasis/checkpoint.py`（新增，核心交付）

**`serialize_checkpoint(brain) -> dict`**：收集各组件关键状态（**索引+关键状态，非空壳**）：
```python
{
  "version": 1,
  "ts": now.isoformat(timespec="seconds"),
  "emotion": brain.emotion.model_dump(),            # EmotionState 全字段（含 curiosity）
  "ledger": brain.ledger.snapshot(),                # ResourceLedger snapshot（含 balance）
  "world": brain.world.snapshot(now=now),           # WorldModel snapshot（online_rhythm/emotion_trajectory）
  "action_budget": brain.action.snapshot() if brain.action else None,  # ActionBudget
  "proactive_gate": <brain.proactive.snapshot()>,   # ProactiveGate
  "stasis_intents": <db.get_body_memory("stasis_intents")>,  # 包 13 意向痕迹（求助/迁移）
  "starving": brain.ledger.starving,
}
```
> 注：`proactive_gate` / `stasis_intents` 来自 `db.get_body_memory`，需 `brain._db`；若 `_db` 为 None 则存 None（测试注入 db）。

**`write_checkpoint(brain, dir_path) -> Path`**：序列化 JSON 写 `data/checkpoint/checkpoint_{ts}.json`（ts 用 `datetime.now().strftime("%Y%m%dT%H%M%S")`）；返回文件路径；`dir_path` 默认项目内 `data/checkpoint`。

**`latest_checkpoint(dir_path) -> Path | None`**：按文件名时间序取最新 `checkpoint_*.json`。

**`restore_checkpoint(brain, path) -> bool`**：读 JSON，重建内存态：
- `brain.emotion = EmotionState(**data["emotion"])`（或 `model_validate`）
- `brain.ledger.restore(data["ledger"])`
- `brain.world.restore(data["world"])`（**需为 WorldModel 增 `restore`，见 2.3**）
- `brain.action.restore(data["action_budget"])`（若非 None；`ActionBudget.restore` 已存在）
- `brain.proactive.restore(data["proactive_gate"])`（若非 None）
- `stasis_intents` / `starving` 写回 `db` body_memory（供后续读取）
- 返回 True；文件不存在/损坏 → False（回退条件可测）

**`restore_latest(brain, dir_path) -> bool`**：`latest_checkpoint` + `restore_checkpoint` 组合。

### 1.2 `tests/test_stasis_checkpoint.py`（新增，含断粮端到端）

---

## 二、修改文件

### 2.1 `qi/world/model.py`（增 `restore`）
补 `WorldModel.restore(data: dict | None)`，重建 `online` / `emotion_trajectory` domains 各自的 restore（若它们有 `restore`；若无则至少重建关键字段）。**最小侵入**，与 `snapshot` 对称。若 `EmotionTrajectory`/`OnlineRhythm` 无 restore，新增对应最小 `restore`（仅恢复其 body_memory 键，如 `world.emotion_trajectory` / `world.online_rhythm`）。

### 2.2 `qi/core/brain.py`
1. **`__init__`**：`self.on_halt: Callable[[], None] | None = None`（默认 None → 仅停心跳循环）。
2. **`start()` 优雅停**：循环 `while self.alive`；退出时在 `finally` 或 `alive=False` 分支调 `if self.on_halt is not None: self.on_halt()`（**不 `sys.exit`**）。CLI/`__main__` 的 `on_halt` 实现里 `sys.exit(0)`。
3. **断粮触发链**（在包 13 `maybe_mark_starving` 之后）：若 `self.ledger.starving`：
   - `await write_checkpoint(self, checkpoint_dir)`（封存）
   - 置 `self.alive = False`（优雅停，触发 `on_halt`）
   - 全程包 `try/except`，封存失败也尽量停（诚实死亡，非崩溃）
4. **`restore_state` 增强**：在现有 restore 之后，调 `restore_latest(self, checkpoint_dir)` 若有 checkpoint（可选：真机重启优先恢复 checkpoint；测试可显式调）。或留 `restore_from_checkpoint(dir_path)` 独立方法供测试/CLI 调（推荐：不强行改 restore_state 既有顺序，避免回退既有 emotion/ledger 恢复逻辑）。
5. **checkpoint 目录**：默认 `data/checkpoint`；`Path` 安全创建（`mkdir(parents=True, exist_ok=True)`）。

### 2.3 `qi/stasis/__init__.py`
导出 `write_checkpoint` / `restore_checkpoint` / `restore_latest` / `latest_checkpoint`。

---

## 三、测试 `tests/test_stasis_checkpoint.py`（新增）

**封存/restore 正确性（非空壳）：**
- `write_checkpoint` 生成 `data/checkpoint/checkpoint_{ts}.json`，含 `emotion` / `ledger` / `world` / `action_budget` / `proactive_gate` / `stasis_intents` 键
- `restore_checkpoint` 后：`brain.emotion` 关键字段相等、`brain.ledger.balance` 相等、`brain.world` 关键字段相等、`brain.action` 计数相等（非空壳，单测断言）
- 封存丢失（删文件）→ `restore_latest` / `restore_checkpoint` 返回 False（回退条件可测）

**断粮端到端（时间轴 + 可观测点）：**
1. 注入 `ledger.force_balance(0)` + 构造 `emotion`（energy 低）→ 跑 N 拍（用 `compute_pressure` + `step_emotion`，或直接在 brain 单拍循环；`starve_beats` 配小值如 3）
2. 断言顺序：节流可观测（`compute_pressure.throttle>0` 或 energy 经 step_emotion 走低 `<0.3`）→ 休眠（`next_interval` 拉长）→ `starving=True` → `write_checkpoint` 文件存在 → `on_halt` 被调（注入伪 `on_halt` 记录调用）
3. **负例**：同一条件下若直接 `alive=False` 且无应对痕迹 → 失败（回退条件可测；可构造不调 write_checkpoint 直接停的路径断言"不可接受"）
4. **无硬 exit**：端到端全程不调 `sys.exit`（AST 审计 checkpoint/brain 新增处）

**其他：**
- `WorldModel.restore` 往返一致（snapshot → restore → snapshot 等价）
- fake-provider 全失败：封存不依赖 LLM
- `pytest` 全绿（不回退 397）；`ruff check` 通过

---

## 四、验收口径（方案 Agent 验收用）

- `pytest -q tests/test_stasis_checkpoint.py` 通过；全量 `pytest -q` 不回退 397
- `ruff check qi/stasis qi/core/brain.py qi/world/model.py tests/test_stasis_checkpoint.py` 无错
- `git diff` 核查：brain 无 `sys.exit`（AST）；checkpoint 收集键齐全；WorldModel 增 restore 对称；`data/checkpoint/` 由代码创建（`.gitignore` 已有 `data/`，无需改）
- 随机审计：确认 on_halt 注入点（库内不 exit）、断粮链顺序（starving → write → alive=False → on_halt）、restore 非空壳
- **退出判据 #1 达成**：断粮测试通过（应对链非静默死 + 可封存迁移）

---

## 五、Cursor 回执要求

完成后在 `docs/specs/archive/2026-08-02-stage4-task/包14-PR方案-Cursor编码回执.md` 落盘：
1. 实际落地文件清单（新增/改动）
2. 关键实现决策（checkpoint 收集键清单、WorldModel.restore 实现、on_halt 注入点、断粮触发链顺序、checkpoint 目录处理）
3. `pytest` / `ruff` 实测结果（贴关键行）
4. 与方案偏差与理由（如有）
5. 自认风险 / 待方案 Agent 验收关注点（尤其判据 #1 是否达成、封存丢失回退条件）

> 纪律：一包一 PR；过程稿落盘 Cursor 自行读；方案 Agent 出方案/验收，Cursor 不决策架构。

---

*包 14 PR 方案 · 阶段四末包（退出判据 #1）· 2026-08-02*