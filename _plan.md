# 计划 · 阶段二补丁 D（补 C 漏改 + 自反闭环可观测）

> 依据：`docs/dev/施工包-阶段二补丁D.md`（文首仍标「编写中」，以正文修复方向为准）  
> 触发：C 后真机 315 拍自主胜出仅 5×`archive`；`journal`/`close_loop` 候选 0  
> 纪律：不伪造 open_loop；不破 `open_loop_count<=0` 不凭空造想；不改 respond 置顶 / N1/N5/R2 / 意图卡  
> 状态：✅ 计划复核通过；✅ 施工完工（待完工复核 / 真机样本）

---

## 〇、任务理解

补丁 C 已让 GWS + archive 真胜出；其余自主/自反仍几乎不出候选。本包两刀：

1. **journal 候选 uptime 门槛与 report 对齐（6h→3h）**——C 只改了 salience，漏改 volition。  
2. **独处静默更容易挂合理心事**——下调 `SILENCE_TRIGGER_HOURS`，使 silence→enqueue→`close_loop` 有源；**绝不**空队列硬 enqueue。

report 3h 只验收不改；share/explore 仍锁独处。

---

## 一、现状核对

| 点 | 位置 | 现状 |
|----|------|------|
| journal 候选 | `volition.py` `_append_self_ops` ~98 | `open_loop_count > 0 or uptime >= 6 * 3600` |
| report salience | `trace.py` `salience_report` | 默认阈值已 **3h**、baseline 0.3（C 已落地）→ **本包不改** |
| silence 触发 | `consciousness.py:25` | **`SILENCE_TRIGGER_HOURS = 4`（非施工包写的 6）**；`mode != "awake"` 且静默超阈 → `"silence"` |
| 无积压底线 | `consciousness.py:126–127` | `open_loop_count <= 0` → `(False,"")`（随机路径）→ **保留** |
| 测文件 | `test_volition.py` 有；**无** `test_consciousness.py` | silence/底线测现散落在 `test_inner_life.py` / `test_open_loops.py` |

### 与施工包口径差（请复核）

施工包写「6h→3h」。代码已是 **4h**。计划按意图落地为 **`SILENCE_TRIGGER_HOURS = 3`**（4→3），与 journal/report 的 3h 对齐。若复核坚持「已够近、不动常量」，则只改 journal——但 close_loop 有源仍偏弱，**建议批准 4→3**。

`CONSCIOUSNESS_PROBABILITY`：施工包「维持或略升」。现状 0.05；**本包默认不改概率**（先靠 silence 门槛），除非复核要求 solitary 略升（如 0.05→0.08）。

---

## 二、精确改动

### 2.1 `volition.py` journal 门槛

```python
# _append_self_ops 内
if open_loop_count > 0 or uptime >= 3 * 3600:  # 原 6h
```

可抽常量（可选）`JOURNAL_UPTIME_SECONDS = 3 * 3600`，与 report 口径一致；非必须。

### 2.2 `consciousness.py` silence 门槛

```python
SILENCE_TRIGGER_HOURS = 3  # 原 4；施工包意图 6→3
```

- 不改 `should_trigger_consciousness` 结构；awake 仍不因 silence 触发。  
- **不改** `open_loop_count <= 0` 早退。  
- `CONSCIOUSNESS_PROBABILITY`：**默认不动**（待复核若要略升再加一行）。

### 2.3 `trace.py`

仅确认 `salience_report(..., uptime_seconds=3*3600+1, energy=0.6, security=0.5) > 0`（既有 `test_salience_report_uptime_three_hours`）。**零改动。**

### 2.4 不改

arbitrate / legacy / 意图卡 / 补丁 B / explore 真读 / 空队列伪造 enqueue。

---

## 三、文件清单

| 文件 | 动作 |
|------|------|
| `qi/action/volition.py` | journal uptime 6h→3h |
| `qi/inner_life/consciousness.py` | `SILENCE_TRIGGER_HOURS` 4→3（待批） |
| `tests/test_volition.py` | journal 3h 有 / 2h 无 |
| `tests/test_consciousness.py` **新建** 或扩 `test_inner_life.py` | silence 3h+；无信号+无积压仍 False |
| `tests/test_trace.py`（可选） | close_loop 有源：非空 open_loops → contender 含 close_loop（轻量） |
| `docs/progress.md` + 施工包 D 去「编写中」打勾 | 一行 |

**测文件裁定建议：** 新建 `test_consciousness.py` 专测触发门槛（与 C 的 `test_volition.py` 对称）；或扩 `test_inner_life.py`——请复核二选一（计划默认**新建**）。

---

## 四、测试清单

1. **journal @ 3h**：`mode=awake`（或 solitary）、`sensing_uptime_seconds=3*3600+1`、`open_loop_count=0`、`can_auto` → kinds 含 `journal`；`uptime=2*3600` → 不含。  
2. **journal 不要求 open_loop**：同上 `open_loop_count=0` 仍出。  
3. **open_loop 底线**：`should_trigger_consciousness(awake, dv=da=0, silence=0, open_loop_count=0)` → `(False,"")`。  
4. **silence 3h**：`mode=solitary`、`silence_duration > 3h`、`open_loop_count=0` → `(True,"silence")`；`silence=2h59m` → 不因 silence 触发。  
5. **close_loop 有源**（可选但建议）：brain/stub + 非空 open_loops → `collect_contenders` 含 `close_loop` 且 sal>0。  
6. **回归**：既有 inner_life / open_loops / volition / fake-provider 绿；`pytest -q` ≥307；`ruff`。

---

## 五、验收对照

| 判据 | 落点 |
|------|------|
| 测/ruff | 完工命令 |
| 真机 ≥10 自主胜出且含 ≥1 journal 或 close_loop | 维护者日常+独处 |
| 溯源 10/10 | `tests/traceability_probe.py`（本包不改脚本，只创造样本条件） |
| 不伪造心事 | 无空队列 enqueue |

---

## 六、风险

| 风险 | 缓解 |
|------|------|
| 静默 3h 略密 | 仍要求非 awake；事件型才 enqueue |
| 只改 journal、不动 silence → close_loop 仍 0 | 批准 4→3 |
| 施工包「编写中」口径漂移 | 复核钉死常量与是否动概率 |

---

## 七、完工命令与回写

```text
python -m pytest -q
python -m ruff check qi tests
```

施工包 D ✅、去掉「编写中」；progress 一行；`_plan.md` 闭环后删。

---

## 八、CodeBuddy 复核结论（2026-08-02，已通过）

> 总体：**批准，可施工。** Cursor 纠正了施工包两处事实误差（SILENCE_TRIGGER_HOURS 实际=4 非 6；无 test_consciousness.py），处理正确。

1. **journal 6h→3h —— 批准。** 补丁 C 明确漏改（只改了 salience 没改候选门槛），与 report 3h 对齐。
2. **`SILENCE_TRIGGER_HOURS` 4→3 —— 批准。** 只改 journal 不动 silence 则 close_loop 仍无源，判据#4 过不了；4→3 使独处长静默更易挂心事，且仍要求 `mode != awake`，不破底线。
3. **`CONSCIOUSNESS_PROBABILITY` 保持 0.05 不动 —— 批准不动。** 先靠 silence 门槛验证 close_loop 有源，避免一次改多变量；真机仍 0 再考虑略升。
4. **新测文件 —— 裁定：新建 `test_consciousness.py`**（与补丁 C 的 test_volition.py 对称，专测触发门槛）。
5. **close_loop 有源测 —— 批准必做（轻量）。** 判据#4 核心即"真实自反闭环可观测"，该测直接验证「非空 open_loops → contender 含 close_loop 且 sal>0」，是 #4 代码侧兜底。

**风险表**：三条缓解成立，无新增风险。施工包 D 文首「编写中」完工时去标打勾（Cursor 第七节已列）。

**完工复核重点**：① journal 候选 uptime≥3h 出现、不要求 open_loop ② silence 4→3 后 solitary+静默>3h 触发、awake 仍不触发 ③ close_loop 有源测绿、无空队列 enqueue ④ 测试全绿 ruff 零。  
