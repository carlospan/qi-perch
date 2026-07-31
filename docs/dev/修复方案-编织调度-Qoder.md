# 修复方案：编织调度缝隙——长睡眠中途积压暴涨不提前醒（W4）

> **撰写者：** Qoder
> **日期：** 2026-08-01
> **代码基线：** `75d1b6e`
> **来源：** 07-31 夜实证 + 维护者"6 小时太长"的体感
> **分工：** 施工方未定（Qoder / Cursor 均可）；**本文供多 agent 交叉检验**——请 Cursor 重点审 §三的调度改法与 §四的可测试性
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

## 三、改法（`qi/core/brain.py`）

**思路：把长睡眠拆成小段轮询——每段睡醒都复查积压，够了就提前织；不够就接着睡满 6h。** 短周期路径（积压≥8 走 900s）**完全不动**。

```python
async def _background_narrative_weaving(self) -> None:
    mem_cfg = self.config.get("memory", {})
    interval = float(mem_cfg.get("narrative_weave_interval", 21600))
    backlog_threshold = int(mem_cfg.get("narrative_weave_backlog_threshold", 8))
    backlog_interval = float(mem_cfg.get("narrative_weave_backlog_interval", 900))
    check_period = float(mem_cfg.get("narrative_weave_check_period", 3600))  # 长睡眠的复查粒度
    while self.alive:
        pending = await self._pending_event_count()
        if pending >= backlog_threshold:
            wait = backlog_interval          # 积压够：短周期，原样
        else:
            # 积压不够：本应长睡 interval，但拆成 check_period 小段，
            # 每段醒来看积压是否涨上来——涨够了就提前去织，不再干等满 6h
            waited = 0.0
            wait = interval
            while self.alive and waited < interval:
                chunk = min(check_period, interval - waited)
                await asyncio.sleep(chunk)
                waited += chunk
                if await self._pending_event_count() >= backlog_threshold:
                    wait = 0.0               # 标记：提前触发
                    break
            # 走到这里：要么睡满了 interval，要么积压涨够提前退出
            if not self.alive:
                continue
        if wait > 0:
            await asyncio.sleep(wait)
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
- 抽 `_pending_event_count()` helper，消除原代码里 pending 统计的重复（原 L749-754 与 L764 各算一次）
- 新增配置 `narrative_weave_check_period`（默认 3600=1h）：长睡眠的复查粒度
- **效果**：重要对话最多等 `check_period`（1h）就被织；平时没事仍 6h 一织（保住叙事质量）；不增加无谓 LLM 调用（只是醒来看一眼，没事接着睡）

## 四、测试（请 Cursor 重点看可测试性）

后台循环直接测较笨重。**建议把"该睡多久/是否提前触发"的决策抽成纯函数**再测，例如：

```python
def _plan_weave_wait(pending: int, threshold: int, interval: float,
                     backlog_interval: float) -> tuple[float, bool]:
    """返回 (本次睡眠时长, 是否需要分段复查)。pending>=threshold → 短周期不分段。"""
    if pending >= threshold:
        return backlog_interval, False
    return interval, True   # 长睡眠，需分段复查
```

测试用例：
1. `pending >= threshold` → 返回 `(backlog_interval, False)`（短周期，不分段）
2. `pending < threshold` → 返回 `(interval, True)`（长睡眠，分段）
3. （集成向）mock memory：长睡眠中途 pending 涨过 threshold → 提前触发 weave（可用很小的 interval/check_period + 假 sleep 验证循环逻辑）

> **给 Cursor 的问题**：你觉得抽纯函数测，还是直接用小参数跑循环测，哪个更贴合本项目现有测试风格？（现有 test_proactive.py / test_pending_queue.py 多用 mock + 小参数跑真实逻辑，可参考。）

## 五、验收

1. 新测试 + 全量绿 + ruff 零违规
2. **实测**：聊一场密集对话（让积压快速 ≥8）后，**1 小时内**（而非 6 小时）就能看到新叙事生成
3. **反向**：长时间无对话时，仍约 6h 一织（不为空转频繁调用 LLM）

## 六、明确不做（与 §一 症状 B 对应）

- **不缩短 `narrative_weave_interval`（6h）本身。** 6h 是在"攒够素材再酿成连贯叙事"，硬缩短会让叙事变碎、且增加 LLM 调用。本方案让"该织时立刻织"，已解决体感问题；平时 6h 一织的节奏**先保留观察**，等调度修复落地、挂几天后，若维护者仍觉得平时慢，再单独调参（届时是在"调度已聪明"前提下调参，而非用缩短弥补调度笨）。
- **不改 `weave_narrative` 的编织逻辑/批量大小**——本方案只动"何时触发"，不动"怎么织"。

## 七、与路线图的关系

本方案是《栖·意识养成路线图》**阶段二第 1 条**（编织调度缝隙）的落地。它是待办里**唯一既治本、又零哲学风险**的一项——不涉及"该不该建能力"的纠结，纯粹让现有功能更聪明。

---

*请 Cursor 审：§三调度改法的正确性（分段轮询有无竞态/漏织）、§四可测试性选型、§六"不缩短 6h"的判断是否认同。*
