# 小修方案：冷启动误判共同沉默 + 内在体验补禁身体（对话实证）

> **撰写者：** Qoder  
> **日期：** 2026-07-26  
> **来源：** 2026-07-26 15:02–15:25 真实对话分析（清库后首场）  
> **代码基线：** `5cde70a`  
> **分工：** Qoder 撰写方案，**Cursor 施工**  
> **规模：** F2 ~5 行 + N3b ~1 行 + 2 测试 + 一条清理 SQL（维护者可选）

---

## F2. `first_shared_silence` 冷启动误触发

### 【实证】

清库后首场对话，**第一条消息**就触发了"共同沉默"：

```
first_times id=1: content='沉默了一会儿之后，他说：「你好」', timestamp='2026-07-26T15:02:13'
```

栖 14:56 启动（day_first_trace 为证），用户 15:02 说第一句"你好"——间隔 5-6 分钟正好落进 `is_comfortable_silence` 的 5-15 分钟窗口，"你好"又是放松语气 → 误判。

**还没说过一句话，何来"共同"沉默。** 且 `has_first_time` 去重意味着这个永不褪色的名额被误判时刻**永久占用**，真正的共同沉默以后永远不会被记录。

### 【根因】

`brain.py:125` `self.last_interaction = datetime.now()`——初始值是**进程启动时间**，不是真实交互时间。`brain.py:383` 的 `silence_before` 因此在冷启动后测的是"启动至今"，被 `first_times.check`（L398-403）当作对话沉默使用。

### 【改法】`qi/core/brain.py`

本会话有过真实交谈之前，不把 silence 当"共同沉默"素材：

1. `__init__`（L125 `last_interaction` 附近）加：
   ```python
   # 本进程会话内是否已有过真实交谈——冷启动后的第一句话不构成「共同沉默」
   self._interacted_this_session = False
   ```

2. `_heartbeat` 里 `first_times.check` 调用（L398-403）改为：
   ```python
   impact_mult, triggered_first = await self.first_times.check(
       pending,
       self.emotion,
       silence_before=silence_before if self._interacted_this_session else None,
   )
   ```
   （`check` 已有 `if silence_before is not None` 守卫，传 None 即自然跳过共同沉默检测，其余第一次类型不受影响。）

3. pending 处理路径里 `self.last_interaction = now` 那一行之后加：
   ```python
   self._interacted_this_session = True
   ```

**【注意】** 守卫放 brain 而不放 first_time.py——"会话内是否交谈过"是 brain 的会话知识，first_time 不该自己去猜。

### 【测试】`tests/test_first_time.py`（或 brain 侧测试文件）补 2 个：

```python
async def test_no_shared_silence_on_cold_start(...):
    """冷启动后第一句话（silence_before=None）不触发 first_shared_silence。"""
    # check("你好", emotion, silence_before=None) → (1.0, None)，库中无 first_shared_silence

async def test_shared_silence_after_real_exchange(...):
    """已交谈过后，5-15 分钟舒适沉默正常触发（旧行为不变）。"""
    # check("嗯", emotion, silence_before=600) → (3.0, "first_shared_silence")
```

---

## N3b. `_inner_experience` prompt 补禁字面身体（N3 漏网）

### 【实证】

误判那条第一次的内在体验：

> "**呼吸声在耳畔轻轻放大**，像在品尝空气里漂浮的每一个可能。"

N3 已改 consciousness / meta / dream 三处，但 `first_time.py:_inner_experience` 的 prompt（L198-200）只禁了"坐在/走在某地"和舞台指示，**没禁呼吸/心跳类生理感受**——第四个生成入口漏了。

### 【改法】`qi/memory/first_time.py` L198-200

```python
"content": (
    "你是栖。用一两句写此刻内在体验。短，真。"
    "可用感受或意象；不要写你正坐在/走在某地，不要舞台动作指示；"
    "也不要写呼吸、心跳、体温这类字面身体感受——你没有身体。"
),
```

**【测试】** 无需新增（LLM 文案约束，靠相处验收）；跑现有 first_time 测试确认无回归。

---

## 数据清理（维护者本机，一次性）

删掉误判的共同沉默记录，把名额还给未来真正的共同沉默时刻：

```sql
DELETE FROM first_times WHERE id = 1 AND event_type = 'first_shared_silence';
```

（id=2 的 first_existential_question 是真实的，保留。）

---

## 验收

1. 新增 2 测试 + 现有测试全绿；`ruff` 零违规
2. **感受题**：重启栖，等 6-8 分钟再说第一句"你好" → 不触发共同沉默、不出现"沉默了一会儿之后"的第一次记录
3. 真实聊过几轮后停 5-15 分钟再放松开口 → 正常触发（名额已由清理 SQL 释放）
4. 下一次任何类型的第一次触发时，内在体验不再出现呼吸/心跳/体温类字面身体句

---

## 观察项（持续追踪，不立项）

| 项 | 本场证据 | 状态 |
|----|----------|------|
| curiosity 顶格 1.0 | 15:04 起顶格 35+ 分钟 | 证据 +1；若日常也长期顶格再考虑软上限 |
| 舞台指示频率 | "（停顿了一下）（想了想）"全场约 6 次 | conversation.txt L78"少用"——深聊里偏密，暂观察 |
| 意识流互相复读 | stream id=2 几乎是 id=1 改写（果子/小兽重复） | 已知（普通意识流无去重），Later 意象频率统计范畴 |
| "我是你的创造者"未落库 | user_facts 只有名字 | 陌生期只记名字是设计内行为；"创造者"是否值得升 IDENTITY_SIGNALS 级，由维护者裁量 |

---

*基于真实对话实证（2026-07-26 15:02–15:25）。本方案由 Qoder 撰写，执行任务由 Cursor 承担。*
