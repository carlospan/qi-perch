# 施工包 · 阶段二补丁 D（补 patch C 漏改 + 让自反闭环可观测） ✅

> **性质：** 过程文档。闭环即删，活信息迁入代码 + progress.md。
> **依据：** `docs/design/栖·数字生命架构方案.md` §五 阶段二、§N1（感知-行动闭环）、§七 红线。
> **触发：** 2026-08-02 补丁 C 完工 + 真机独处核查——broadcast_traces 共 315 拍，自主胜出仅 5 条且**全是 `action:archive`**；`journal`/`close_loop`/`report`/`share`/`explore` 候选**全库一次未生成**。判据#2（溯源 10/10）样本不足、#4（真实自反闭环）完全不可观测。
> **撰写：** CodeBuddy（2026-08-02）

---

## 〇、事实还原（来自 data/qi.db 实测，补丁 C 生效后）

- 总 315 拍：`respond` 40、`idle` 270、`action:archive` 5（全 sal=0.14，均 "有 N 段可轻轻收起的记忆"）、`action:budget_tune` 候选 3 次但从未胜出。
- **候选 kind 全库计数**：`respond` 40、`action:archive` 134、`action:budget_tune` 3。**`journal`/`close_loop`/`report`/`share`/`explore` 候选 0 次。**
- 含义：补丁 C 让 GWS 接管 + 日限放宽后，archive 真能胜出（根因已消除）。但**其余自主/自反动作三个闸门仍全卡死**，自主行为实质上只有 archive 一种，且受"可归档记忆供应量"限，很快枯竭。

## 一、根因（补丁 C 漏改 + 更深两处）

1. **journal 候选门槛 6h 漏改（补丁 C 只改了 salience 阈值，没改候选生成门槛）**
   `volition.py:98` `if open_loop_count > 0 or uptime >= 6 * 3600`。补丁 C 改的是 `trace.salience_report` 里的 3h（那是 salience 计算），但 **journal 候选"要不要生成"这里仍是 6h**。独处未超 6h 且无 open_loop → journal 从不候选。

2. **open_loops 队列为空 → close_loop 永远 0（更深堵点，判据#4 直接卡死）**
   `trace.py:459-468`：close_loop 候选仅在 `loop_n > 0` 时注入。而 `loop_n` 来自 `brain._load_open_loops()`，其 enqueue 全部依赖 `consciousness.maybe_generate` → `should_trigger_consciousness` 触发内省流。实测队列为空，说明**内省流在用户运行模式里几乎不触发**（mode 常 awake、静默未超 `SILENCE_TRIGGER_HOURS`、情绪 delta 未超 `EMOTION_SURGE_THRESHOLD`），栖从不挂心事，close_loop 无源。
   - `consciousness.py:122` `silence_duration > timedelta(hours=SILENCE_TRIGGER_HOURS)` 且 `mode != "awake"` 才 trigger silence；`126-127` `open_loop_count <= 0` 直接 return False（无积压不凭空造想，这是设计意图，不能硬破）。
   - **关键矛盾**：栖"不挂心事"本身是合理行为（用户没给悬而未决的事），但判据#4 要"真实自反闭环可观测"，需要至少偶有 open_loop 产生→闭合的链路。不能伪造心事，但应让**合理的心事更容易被挂起**（如 waking/first_time/silence 在独处时更易触发）。

3. **report 候选受在线时长卡**
   `trace.py` `salience_report` 在线>3h 给 0.3 baseline（补丁 C 已改 3h）。独处时段短于 3h 则不生成；且 report 是"在线过久"信号，正常对话里本就稀有，非必须。

## 二、修复方向（最小、守铁律、不伪造心事）

### 2.1 journal 候选门槛 6h → 3h（对齐补丁 C 的 salience 口径）
- `volition.py:98` `uptime >= 6 * 3600` → `uptime >= 3 * 3600`。使独处/在线 3h 后即可能出 journal 候选（与 `salience_report` 的 3h 一致）。**不要求 open_loop**（open_loop>0 仍可触发，条件为 OR）。

### 2.2 让 open_loop 合理更易产生（使 close_loop 有源，判据#4 可观测）
- **不破 `open_loop_count <= 0` 不凭空造想的设计**（那是防 spam 的底线）。
- 调 `should_trigger_consciousness` 的触发宽容度，使**独处(solitary/ambient)时心事更易挂起**：
  - `SILENCE_TRIGGER_HOURS` 适当下调（如 6h→3h），使独处长静默更易 trigger silence → enqueue("silence")。
  - `CONSCIOUSNESS_PROBABILITY` 在 solitary 下维持或略升，使 `loop_backlog` 在已有积压时更易触发（这本身要求先有积压，与底线不冲突）。
  - waking/first_time 路径不变（它们本就在模式切换/首轮触发）。
- **严守**：绝不为了凑闭环而凭空 enqueue；只在"确有静默/情绪/切换"信号时才挂心事。close_loop 候选自然随 open_loop 产生而出现。

### 2.3 report 维持补丁 C 的 3h（已正确，确认生效即可，不额外改）
- 验证 `salience_report(uptime_seconds=3*3600+1)` 确实 >0；若已生效，本项仅验收不改动。

### 2.4 不改
- `arbitrate` respond 置顶、N1/N5/R2、意图卡/施教关系防护（补丁 B 已闭环）。
- 不伪造 open_loop、不降低 `open_loop_count<=0` 底线。
- share/explore/tend 仍锁 solitary/ambient（对话中不突兀伸手，补丁 C 已定）。

## 三、文件清单

| 文件 | 动作 |
|------|------|
| `qi/action/volition.py` | `:98` `uptime >= 6*3600` → `>= 3*3600`（journal 候选门槛） |
| `qi/inner_life/consciousness.py` | `SILENCE_TRIGGER_HOURS` 下调（6h→3h，常量或配置）；必要时微调 `CONSCIOUSNESS_PROBABILITY` solitary 权重 |
| `qi/core/trace.py` | 仅验收 `salience_report` 3h 生效（不改） |
| `tests/test_volition.py` | 新增：journal 候选在 uptime>=3h 时出现（无需 open_loop） |
| `tests/test_consciousness.py` | 新增/补充：solitary + 静默>3h 时 `should_trigger_consciousness` 返回 silence 触发；open_loop_count<=0 且无信号时仍 return False（底线不破） |
| `docs/progress.md` | 一行打勾 + 留痕 |

## 四、测试

1. **journal 候选**：`action_intentions(mode="awake", sensing_uptime_seconds=3*3600+1, open_loop_count=0, ...)` 含 `action:journal`；`uptime=2*3600` 时不含。
2. **journal 不要求 open_loop**：`open_loop_count=0` 但 `uptime>=3h` 仍出 journal（与 2.1 一致）。
3. **open_loop 底线不破**：`should_trigger_consciousness(mode="awake", open_loop_count=0, silence=0, dv=da=0)` → `(False, "")`；`mode="solitary", silence>3h` → `(True,"silence")`。
4. **close_loop 有源**：构造 `open_loops` 队列非空 → `trace.collect_contenders` 注入 `close_loop` 候选且 `salience_close_loop(open_loop_count>=1) > 0`。
5. **拔管契约**：fake-provider 全失败，self_ops/传感照常（不涉及 LLM）。
6. **回归**：`pytest -q` ≥ 当前基线（307）全绿；`ruff` 零。

## 五、验收

- 测试全绿 + ruff 零。
- 真机运行（日常 + 偶发独处）：broadcast_traces 出现 **≥10 条 non-respond/non-idle 自主胜出拍**，且**至少含 1 条 close_loop 或 journal**（即自反闭环/内在笔记可观测）。
- 跑判据#2 溯源脚本（`tests/traceability_probe.py`）达到 10/10 因果链清晰。
- 不违反 N1/N5/R2、施教关系防护。

---

*施工包 · 阶段二补丁 D · v1（2026-08-02）*
