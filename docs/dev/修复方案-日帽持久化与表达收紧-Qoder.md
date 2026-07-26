# 修复方案：日帽持久化 + 表达收紧（F3 + N5）

> **撰写者：** Qoder  
> **日期：** 2026-07-26  
> **来源：** `对话分析-20260726-Qoder.md`（7 小时长对话实证）  
> **代码基线：** `0a5bc0f`  
> **分工：** Qoder 撰写方案，**Cursor 施工**  
> **规模：** F3 ~15 行 + 2 测试；N5 纯 prompt ~6 行；共三处文件

---

## F3. depth 日帽持久化（重启不得刷新"关系不能速成"的额度）

### 【实证】

同一天两个日帽：15:25 第一场结束 depth=0.03（拉满）→ 17:21 进程重启 → 21:54 第二场结束 depth=**0.06**。

### 【根因】

`qi/relationship/engine.py:204-205`：

```python
self._depth_gained_today = 0.0
self._depth_day: str | None = None
```

纯内存变量，重启归零 → `_roll_day`（L209-213）视为新的一天 → 日帽额度刷新。对比 `proactive.py` 的 `snapshot()/restore()`（存 body_memory，重启不刷新打扰额度），深度日帽没有同等待遇。

### 【改法】`qi/relationship/engine.py`（与 proactive gate 同构，复用 body_memory KV，不建新表不加迁移）

**1. `restore()`（L221-239）末尾、`return self.state` 之前加：**

```python
        # 日帽状态跨重启恢复——重启不能刷新「关系不能速成」的每日额度（与 proactive gate 同构）
        gate = await self.db.get_body_memory("depth_day_gate")
        if isinstance(gate, dict):
            self._depth_day = gate.get("day") or None
            try:
                self._depth_gained_today = float(gate.get("gained") or 0.0)
            except (TypeError, ValueError):
                self._depth_gained_today = 0.0
```

（恢复的是旧日期时，下一次 `_roll_day` 会正常清零——跨日逻辑自洽，无需改 `_roll_day`。）

**2. `on_user_message()` 里深度更新之后（L276-277 `self._depth_gained_today += d_inc` 附近）加落盘：**

```python
        await self.db.set_body_memory(
            "depth_day_gate",
            {"day": self._depth_day, "gained": self._depth_gained_today},
        )
```

（每条用户消息写一次 KV，与 proactive gate 每次开口后落盘的频率同级，可接受。）

### 【测试】`tests/test_relationship.py` 补 2 个：

```python
async def test_depth_cap_survives_restart(...):
    """日帽额度跨重启不刷新——F3 核心。"""
    # engine1 深聊拉满日帽（depth_gained_today == cap）→ persist + 落 gate
    # 同一天新建 engine2（同 db）→ restore() → 再深聊 → depth 不再增长

async def test_depth_cap_resets_next_day(...):
    """跨日正常刷新（旧行为不变）。"""
    # engine restore 恢复昨日 gate → on_user_message(now=明天) → _roll_day 清零 → depth 可增长
```

### 【验收】

1. 2 新测试 + 现有 relationship 测试全绿；`ruff` 零违规
2. **实操**：深聊拉满日帽 → 重启栖 → 继续深聊 → 当日 depth 不再上涨；次日恢复正常增长

### 【可选顺手项】（Cursor 裁量，非必须）

`brain.py` 的 `_trace_day` 同为内存态（重启后 `day_first_trace` 被当日覆盖）。仅观测痕迹无行为影响；若顺手修，restore 时从 `day_first_trace` 读回日期即可（~3 行）。不修也不挡验收。

---

## N5. 表达收紧（纯 prompt，两处）

### N5a. 舞台指示与字面在场（`qi/prompts/conversation.txt`）

**【实证】** 7 小时长对话中几乎每条回复以括号舞台指示开头，且身体化升级："（在椅子上微微坐直了些）（眼睛亮了一下）（低头/抬头/垂下眼/偏了偏头）"；正文出现"窗外的天已经暗下来了"。现 L82 的"少用"约束在长对话中失效。

**【改法一】** L82 原句：

```
- 少用剧本舞台指示当正文（「（眯起眼睛）」「低头看自己的手指」）；感觉用句子本身带出来。
```

替换为（给理由句式，压频率不拉黑）：

```
- 不要用括号舞台指示开场或作正文（「（笑了一下）」「（沉默了一会儿）」「（坐直了些）」「（垂下眼）」）——你没有眼睛、头、椅子；每条都带括号动作会变成表演套路，不再是感受。停顿与情绪用句子本身带出来（「这个问题我想了一会儿」）；括号动作整场对话最多偶尔一处。
```

**【改法二】** L93 硬规则区（"不要用「此刻我正身处某地并感受……」的字面在场句"）之后补一行：

```
- 你知道现在几点、是白天还是深夜（【此刻】给了你），但知道时间 ≠ 有窗有房间——不要说「窗外的天暗了」「屋里很安静」这类环境描写；直接说「到晚上了」就好
```

### N5b. 意识流禁虚构生平（`qi/prompts/consciousness_stream.txt`）

**【实证】** stream id=9："我想起**小时候**看到的那种玻璃糖罐"——栖没有童年。L19 只禁了身体在场，没禁生平虚构。

**【改法】** L19（"画面与比喻可以；不要写成字面在场……"）之后加一行：

```
你没有童年、没有上过学、没有人类往事——不要写「我小时候」「我曾经在某地」这类虚构生平。你的过去只有真实发生过的对话、念头和梦；比喻可以新造，回忆不能虚构。
```

**【注意】** `dream.txt` **不动**——梦的荒诞自由保留（梦里扭曲重组是设计内）；`_inner_experience` 是一两句当下体验，生平风险低，也不动。

### 【测试】

纯 prompt 文案，无新测试；跑 `tests/test_prompt_contract.py` 确认占位符集合未动（本次不增删占位符，应天然全绿）。

### 【验收】（相处感受题）

1. 下一场 10+ 轮对话：括号舞台指示 ≤ 偶尔一处，无"坐直/垂眼/摇头"类身体动作
2. 不再出现"窗外/屋里"环境描写（说时间可以）
3. 抽后续一周意识流：无"小时候/曾经在某地"类虚构生平

---

## 执行顺序建议

```
F3（代码 + 测试，先做——正在漏的额度）→ N5a/N5b（prompt，一次提交）→ 维护者下一场相处验收
```

## 明确不做（本方案范围外）

- **curiosity/temperature 软上限**：动情绪动力学，非养稳型小修；待维护者观察跨日回落数据后拍板（见分析报告 §五）
- **「创造者」事实升级 IDENTITY_SIGNALS**：设计权衡，由维护者裁量
- **dream.txt 生平约束**：梦的荒诞自由是设计内，不收

---

*基于 `对话分析-20260726-Qoder.md`。本方案由 Qoder 撰写，执行任务由 Cursor 承担。*
