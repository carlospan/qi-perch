# 修复方案：编织调度缝隙——长睡眠中途积压暴涨不提前醒（W4）

> **撰写者：** Qoder
> **日期：** 2026-08-01
> **代码基线：** `75d1b6e`
> **来源：** 07-31 夜实证 + 维护者"6 小时太长"的体感
> **分工：** 施工方未定（Qoder / Cursor 均可）；**本文供多 agent 交叉检验**
> **审查记录（2026-08-01，Cursor）：** 根因/方向/§六均认同；**指出§三示例代码硬伤**——长睡分支结束后又有 `if wait>0: sleep(wait)`，安静时会变成约 12h 一织（与「平时 6h」承诺相反）。已按 Cursor 修正版重写§三（睡眠只发生在分支内部，织前不再二次 sleep）；§四测试改为 mock sleep 跑真实循环（不抽纯函数）；§五验收期望已对齐（本方案只治「积压≥8 却还在长睡」）。
> **规模：** ~20 行（brain.py）+ 配置 1 项 + 测试；**不改编织逻辑本身**

---

## 一、问题

维护者体感"6 小时太长"。但经核查，**6 小时这个数不是病根，"该织的时候还在睡"才是**。两个症状要分开治：

- **症状 A（真 bug）**：长睡眠（6h）一旦睡下，中途积压暴涨也不会提前醒。
- **症状 B（体感）**：平时没事时，6 小时一织是否太慢。

本方案**只治症状 A**。症状 B 建议先不动（理由见 §六）。

## 二、根因（已定位到行）

`qi/core/brain.py:_background_narrative_weaving`（L743-769）：

```python
while self.alive:
    pending = await self.memory.unprocessed_event_count()
    wait = backlog_interval if pending >= backlog_threshold else interval  # ← 一次性算定
    await asyncio.sleep(wait)   # ← 若 pending<8，睡满 interval(6h)，期间不复查
    ...weave...
```

`wait` 在循环顶部**算定一次**。若此刻积压 < 8，就睡满 6 小时；**这 6 小时里即使积压从 2 涨到 30，它也不知道，照样睡满**。

**实证**：07-31 23:33–23:39 维护者聊了重要的"恐惧化解"对话，但编织睡下去时定了 6h，期间积压涨上来也没提前醒——重要对话要等满 6 小时才被织进叙事。

## 三、改法（`qi/core/brain.py`）——Cursor 修正版

**思路：把长睡眠拆成小段轮询。睡眠只发生在分支内部；织之前不再二次 sleep**（原示例的硬伤已除）。短周期路径（积压≥8 走 900s）逻辑不变。

```python
async def _background_narrative_weaving(self) -> None:
    mem_cfg = self.config.get("memory", {})
    interval = float(mem_cfg.get("narrative_weave_interval", 21600))
    backlog_threshold = int(mem_cfg.get("narrative_weave_backlog_threshold", 8))
    backlog_interval = float(mem_cfg.get("narrative_weave_backlog_interval", 900))
    check_period = float(mem_cfg.get("narrative_weave_check_period", 3600))  # 长睡眠复查粒度
    while self.alive:
        pending = await self._pending_event_count()
        if pending >= backlog_threshold:
            await asyncio.sleep(backlog_interval)      # 积压够：短周期
        else:
            # 积压不够：长睡 interval，但拆成 check_period 小段；
            # 每段醒来复查，积压涨够就提前跳出，不再干等满 6h
            waited = 0.0
            while self.alive and waited < interval:
                chunk = min(check_period, interval - waited)
                await asyncio.sleep(chunk)
                waited += chunk
                if await self._pending_event_count() >= backlog_threshold:
                    break
        # 睡眠已在分支内完成，这里直接织——不再二次 sleep
        if not self.alive or self.memory is None:
            continue
        try:
            if await self.memory.has_unprocessed_events():
                await self.memory.weave_narrative(
                    self.emotion, self.relationship_stage
                )
        except Exception:
            logger.exception("叙事编织后台出错")

async def _pending_event_count(self) -> int:
    if self.memory is None:
        return 0
    try:
        return await self.memory.unprocessed_event_count()
    except Exception:
        logger.exception("统计未编织事件失败")
        return 0
```

**要点：**
- **睡眠只在分支内**：积压够→睡 `backlog_interval`；不够→分段睡满 `interval` 或提前跳出。织前绝不再 sleep（防 12h 硬伤）。
- 抽 `_pending_event_count()` helper，消除原代码 pending 统计重复（原 L749-754 与 L764）。
- 新增配置 `narrative_weave_check_period`（默认 3600=1h）：长睡眠复查粒度。`settings.example.yaml` 的 `memory:` 节补一行：
  ```yaml
  narrative_weave_check_period: 3600        # 长睡眠中途复查积压的粒度（秒）
  ```
- **竞态/漏织（Cursor 核实）**：单后台任务读 DB 计数，无实质竞态；提前醒后下一轮若仍 ≥8 会走短周期，不会漏织。
- **效果**：积压一旦 ≥8，最多等 `check_period`（1h）就被织；平时没事仍约 6h 一织（保住叙事质量）；不增加无谓 LLM 调用。

## 四、测试（采纳 Cursor 意见：mock sleep 跑真实循环，不抽纯函数）

~~原拟抽 `_plan_weave_wait` 纯函数~~ —— Cursor 指出它几乎只是 `if pending>=threshold`，**测不出「提前醒」**。采纳其建议：按 `test_pending_queue.py` 那套，**mock `asyncio.sleep` + 很小的 interval/check_period + 跑真实循环**。

重点断言：
1. **提前醒（核心）**：长睡中途 pending 涨过 threshold → `weave_narrative` 在**总等待 < interval** 时就被调用。
2. **安静时仍约 6h**：pending 始终 < threshold → 总等待 ≈ interval（不是 12h！防回归硬伤）后织一次。
3. **积压够走短周期**：pending ≥ threshold → 睡 `backlog_interval` 后织。

> mock 提示：用累加器记录 sleep 总时长；`unprocessed_event_count` 用 side_effect 模拟「中途涨过阈值」。参考 `test_pending_queue.py` 的 `patch("qi.core.brain.asyncio.sleep")` 写法。

## 五、验收（期望已按 Cursor 意见对齐）

1. 新测试 + 全量绿 + ruff 零违规
2. **实测（本方案真正解决的）**：让积压快速 ≥8（一场密集对话）后，**1 小时内**（而非等满 6h）就看到新叙事生成
3. **反向**：长时间无对话、积压始终 <8 时，仍约 6h 一织（不为空转频繁调 LLM，也不是 12h）

> **期望边界（Cursor 提醒，务必别写错）**：本方案**只治「积压 ≥8 却还在长睡」**。若那场「重要对话」事件数 **<8**，修完后**仍要等满约 6h**。若维护者体感主要来自「重要但条数少」，需另开「重要性/会话结束唤醒」——**不要**把验收写成「重要对话必 1h 内织」。

## 六、明确不做（与 §一 症状 B 对应）

- **不缩短 `narrative_weave_interval`（6h）本身。** 6h 是在"攒够素材再酿成连贯叙事"，硬缩短会让叙事变碎、且增加 LLM 调用。本方案让"该织时立刻织"，已解决体感问题；平时 6h 一织的节奏**先保留观察**，等调度修复落地、挂几天后，若维护者仍觉得平时慢，再单独调参（届时是在"调度已聪明"前提下调参，而非用缩短弥补调度笨）。
- **不改 `weave_narrative` 的编织逻辑/批量大小**——本方案只动"何时触发"，不动"怎么织"。

## 七、与路线图的关系

本方案是《栖·意识养成路线图》**阶段二第 1 条**（编织调度缝隙）的落地。它是待办里**唯一既治本、又零哲学风险**的一项——不涉及"该不该建能力"的纠结，纯粹让现有功能更聪明。

---

*审查闭环：Cursor 已审（2026-08-01），根因/方向/§六认同；§三二次-sleep 硬伤、§四测试选型、§五期望边界均按其意见修正。施工方由维护者定。*
