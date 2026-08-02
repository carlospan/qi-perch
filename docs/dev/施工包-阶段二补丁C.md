# 施工包 · 阶段二补丁 C（让 GWS 真正接管 + 自主行为可观测） ✅

> **性质：** 过程文档。闭环即删，活信息迁入代码 + progress.md。
> **依据：** `docs/design/栖·数字生命架构方案.md` §五 阶段二、§N1（感知-行动闭环）、§七 红线。
> **触发：** 2026-08-02 真机溯源核查——broadcast_traces 共 128 拍，respond 24、idle 106、**non-respond/non-idle 自主胜出 0 条**。阶段二判据#2（溯源 10/10）、#4（真实自反闭环）因此无法达成。包 6/7/8 代码侧已闭环，但行为侧被四重压制，自主行为在真机里几乎不可能胜出。
> **撰写：** CodeBuddy（2026-08-02）

---

## 〇、事实还原（来自 data/qi.db 实测）

- broadcast_traces 总 128 拍：`respond` 24、`idle` 106、`action:*`/`proactive:*`/`close_loop`/`report` **0**。
- 痕迹机制在工作：每拍都记了候选（如 `action:archive` sal=0.14 "有 2 段可轻轻收起的记忆"），但 **winner 永远是 idle**。
- 含义：竞争者产生了，从未越过阈值真正执行。判据#2/#4 需要的"10 条自主行为 + 执行→传感→表达闭环"凑不出。

## 一、根因（四重压制）

1. **GWS 未启用（包 7 设计如此，但卡住行为）**
   `brain.py:456` `if gws_config(self.config)["enabled"]` —— 默认 `settings.yaml`(example 同) `gws.enabled: false`，走 `_heartbeat_legacy_idle`，**仲裁结果不接管行为**。`persist_broadcast` 里 winner 由 `winner_from_legacy()` 算（不是 `arbitrate`），所以 archive 候选 sal=0.14 也判成 idle。

2. **自主行动日限 = 1（volition/budget）**
   `budget.py:10` `AUTONOMOUS_ACTION_DAILY_LIMIT = 1`，`settings.yaml:87` `autonomous_daily_limit: 1`。每天只允许 **1 次**自主行动；用掉后 `can_autonomous` 返回 False，`action_intentions` 整段不生成 action 候选。`_heartbeat_legacy_idle` 走 `action.tick`，与 GWS 同源受此限。

3. **模式门槛（solitary 难进）**
   `volition.py:103` `solitary_like = mode in ("solitary","ambient")` + `can_auto` + `scale>0`。自主行动候选要求 solitary/ambient 模式；`determine_mode` 下 solitary 需长静默（solitary_interval=300s）+ 用户离线。用户日常频繁互动时 mode 多为 awake，action 候选整段不生成。

4. **proactive 门槛高 + 关系阶段门槛**
   `pick_proactive_kind` / `volition` 的 check_in 要 `silence>=1800s 且 (security<0.45 或 attachment>0.55)`；reach_out 要 `silence>=3600s 且 friend/bonded`。频繁互动下 silence 短、关系阶段未到 friend/bonded，proactive 不触发。

**结论**：非 bug，是"阈值/开关过保守 + GWS 未接管"。改时长(72h)救不了 0 条自主拍——必须让 GWS 接管并放宽触发，自主行为才可能在真机产生。

## 二、修复方向（最小、守铁律）

### 2.1 启用 GWS 接管行为（核心）
- `settings.yaml` / `settings.example.yaml` 的 `gws.enabled` 由 `false` 改 `true`。
- 前置保障（包 7 已铺好）：shadow 对照 `arb_matches_legacy` 已在写；启用后 `_heartbeat_gws_idle` 全量仲裁分发（proactive/action/close_loop/report 互斥）。respond 永不被压过（`arbitrate` 内 respond 置顶）已保证。
- **切换纪律**：直接翻 `enabled: true` 即行为改走 GWS；保留 `_heartbeat_legacy_idle` 不删（回滚用），但本包不并行对照（shadow 阶段已认定一致率达标，见验收#3）。

### 2.2 放宽自主行动触发，使真机可积累样本
- `action.autonomous_daily_limit`：`1` → `3`（仍紧于言语日限 3，但一天能积累 3 次自主行动供溯源）。
- `volition.py` action 候选门槛：`solitary_like = mode in ("solitary","ambient")` 放宽为 `mode in ("solitary","ambient","awake")` 中 **awake 仅允许低频自反动作**（archive / journal / budget_tune），share/explore/tend 仍要求 solitary/ambient（避免对话中突兀伸手）。即按 action kind 分档：
  - 允许 awake 触发的：`archive`（收记忆）、`journal`（内在笔记）、`budget_tune`（分寸微调）——均为低打扰自反动作。
  - 仍限 solitary/ambient 的：`share`、`tend`、`explore`——需独处气质。
- 不改 `can_autonomous` 逻辑本身，只调日限与 `action_intentions` 的 mode 分档。

### 2.3 让 close_loop / report 也能在 GWS 下胜出（闭环可观测）
- 当前 `salience_close_loop` 满 5→1、`salience_report` 需 energy<0.3/security<0.35/在线>6h。这些在正常对话里几乎不触发。
- 放宽下限：close_loop 积压 1 即给 baseline 0.3（原 0，满 5→1）；report 在在线>3h 给 0.3 baseline（原 6h）。使这两类在真机里能偶尔胜出，供判据#4 观测"执行→传感→表达"闭环。
- **严守 N1 铁律**：explore 仍真读 `data/`、self_ops 真实改 DB，绝不生成"我探索了"假闭环。

### 2.4 不改
- `arbitrate` 的 respond 置顶逻辑（响应性底线）。
- `_heartbeat_legacy_idle`（保留回滚）。
- 意图卡 / 施教关系防护（补丁 B 已闭环，本包不碰）。
- N5 / R2 / 灵魂书双轨（不涉及）。

## 三、文件清单

| 文件 | 动作 |
|------|------|
| `qi/config/settings.example.yaml` | `gws.enabled: false` → `true`；`action.autonomous_daily_limit: 1` → `3` |
| `settings.yaml`（用户实际配置，若存在） | 同上两处（若用户用 example 直接跑则无独立文件；以 example 为准并提示用户对齐） |
| `qi/action/volition.py` | `action_intentions` 的 mode 分档：按 kind 区分 awake 允许的低成本自反动作 |
| `qi/core/trace.py` | `salience_close_loop` 下限 0.3（积压≥1）；`salience_report` 在线>3h 给 0.3 baseline |
| `tests/test_gws.py` / `tests/test_volition.py` / `tests/test_trace.py` | 新增/补充：启用后 winner 由仲裁驱动、awake 下 archive/journal/budget_tune 可候选、close_loop/report 下限放宽后可胜出 |
| `docs/progress.md` | 一行打勾 + 留痕 |

## 四、测试

1. **GWS 接管**：构造无 pending 场景，`gws.enabled=true` 下 `_heartbeat_gws_idle` 的 winner 来自 `arbitrate(candidates)`（非 legacy）；respond 恒压过其他。
2. **awake 自反动作**：mode=awake、user_online、有 archivable 叙事 → `action_intentions` 含 `action:archive`；share/explore/tend 仍不出现。
3. **日限放宽**：`autonomous_daily_limit=3` 下 `can_autonomous` 当日前 3 次 True、第 4 次 False。
4. **close_loop/report 下限**：`salience_close_loop(open_loop_count=1)>0`；`salience_report(uptime_seconds=3*3600+1, energy=0.6, security=0.5)>0`。
5. **拔管契约**：fake-provider 全失败，GWS 下自主/自操作/传感照常推进，不依赖 LLM。
6. **回归**：`pytest -q` ≥ 当前基线（301）全绿；`ruff` 零违规。

## 五、验收

- 测试全绿 + ruff 零。
- 真机运行（用户日常使用即可，无需 72h 空跑）：broadcast_traces 出现 ≥10 条 non-respond/non-idle 自主胜出拍，且其中至少 1 条形成"执行→下一拍传感变化"闭环（如 archive 后检索集变化、journal 后 consciousness_stream 多一行）。
- `arb_matches_legacy` 历史一致率已 ≥0.99（包 7 shadow 阶段结论），启用后无行为回退。
- 不违反 N1（explore 真读）、N5/R2（不涉及）。
- 完成后即可跑判据#2 溯源脚本（抽 10 条自主拍验 10/10 因果链），推进阶段二退出复核。

---

*施工包 · 阶段二补丁 C · v1（2026-08-02）*
