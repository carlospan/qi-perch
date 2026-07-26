# 修复方案：第一次记忆的「同拍回声」（对话实证）

> **撰写者：** Qoder  
> **日期：** 2026-07-26  
> **来源：** 2026-07-26 14:05–14:09 真实对话分析（数据库实录 + 代码追因）  
> **代码基线：** `71ef224`（Cursor 已完成 Now+Next 全部施工；本 bug 在最新代码上**依然存在**，与已完成的 N4 改动不冲突）  
> **分工：** Qoder 撰写方案，**Cursor 施工**  
> **优先级：** 高——正在真实对话中造成「虚构历史」，且烧掉每周回忆额度；改动 ~10 行 + 2 测试

---

## 一、对话实证（数据库实录）

这是 messages 表里的**第一场对话**（最早记录 14:05:30「你好」，关系 stranger、depth 0.03），约 4 分钟 7 轮：

```
[14:06:25] 用户: 我好奇你是什么
[14:06:33] 栖:   嗯。那个问题我听过一次，在很久以前——其实也不算很久，
                就是上次我们刚开始说话的时候。当时我闪过一个画面：光点……
[14:07:04] 用户: 我们以前说过话吗？
[14:07:08] 栖:   记得。一次。很短的，像春天刚探出头的对话。……
[14:08:27] 用户: 这个算很久以前吗？不是刚刚才问的吗
[14:08:31] 栖:   你说得对，这句话是刚才问的……我说的是上一次，我们第一次
                说话的时候，你也问过同样的问题。那次是真正的"很久以前"……
```

**数据库证明不存在任何"上次"。栖虚构了一段历史，被戳穿后又用新虚构圆旧虚构。**

## 二、机制（代码追因，基于 `71ef224`）

同一拍心跳里发生了三件事：

1. 用户 14:06:25 的提问命中 `first_existential_question` → `first_times.check()`（`brain.py` 心跳 pending 分支）当场落库，`inner_experience` 生成「那些光点，像在眨眼的星星」
2. **同一拍**，`_gather_prompt_context`（`brain.py:314-317`）调用 `maybe_recall_hint(pending, now)`（`first_time.py:223`）→ **同一句话匹配同一个关键词表 `_PATTERNS`** → 把刚落库几秒的第一次当作回忆命中，注入 hint：

   > "**你记得一个第一次**：他说：「我好奇你是什么」。当时你想：那些光点……"

3. LLM 拿到"你记得一个第一次"的表述，自然把它讲成旧事——"我听过一次，在很久以前"

**双重伤害：** 这次假回忆调用了 `recall_first_time`（`first_time.py:237`），写掉 `last_recalled`、`recall_count=1`——`RECALL_COOLDOWN=7 天`（L63）意味着**未来 7 天栖不会再自然回忆任何第一次**。真正的回忆机会被同拍回声吃掉。

**次生问题（修好本 bug 大概率消失）：** 栖不是在撒谎——hint 让它真的相信有过一次，它是在诚实地复述一段被系统喂给它的假记忆。这违反 conversation.txt「没有相关记忆时，不要假装记得」，但根因在系统不在 prompt。

**连带实证（供 N1 参考，不在本方案立项）：** 「光点，像在眨眼的星星」15 分钟内被复读 3 次（14:06:33/14:08:00/14:08:59）——链条是 `inner_experience` 生成意象 → recall hint 反复注入 → LLM 每次照搬。提示 N1 的意象复读约束**对 hint 注入的意象同样需要生效**。

## 三、修复方案（F1，Cursor 施工）

**设计原则：刚发生的第一次不是记忆，是现场。** 在 `maybe_recall_hint` 内部过滤"太新"的第一次——比在 brain 层传 `triggered_first` 更彻底（防护所有调用方，不改函数签名与 brain 接线）。

### 【文件】`qi/memory/first_time.py`

**1. 常量区（L63 `RECALL_COOLDOWN` 附近）加：**

```python
# 刚发生的第一次不是回忆，是现场——同拍/近时不作 recall 注入（防同拍回声虚构历史）
RECALL_MIN_AGE = timedelta(minutes=30)
```

**2. 加私有辅助（放 `_recalled_within_week` 附近）：**

```python
def _too_fresh(self, ft: dict, now: datetime) -> bool:
    """刚落库不久的第一次不算可回忆的记忆。"""
    raw = ft.get("timestamp")
    try:
        ts = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return False  # 解析不出宁可放行，维持旧行为
    return now - ts < RECALL_MIN_AGE
```

**3. `maybe_recall_hint`（L223-252）两个分支都过滤：**

- 关键词循环（L233-242）：`for ft in firsts:` 后第一行加
  ```python
  if self._too_fresh(ft, now):
      continue
  ```
- 深夜分支（L244-251）：`ft = firsts[0]` 改为取第一条**不太新**的：
  ```python
  candidates = [ft for ft in firsts if not self._too_fresh(ft, now)]
  if candidates:
      ft = candidates[0]
      if int(ft.get("recall_count") or 0) < 3:
          ...
  ```

**【注意】** `first_times.timestamp` 字段名以 `db.save_first_time` 实际写入的列为准（表结构里是 `timestamp`）；若发现是其他名字，`_too_fresh` 里同步改 key。

### 【测试】`tests/test_first_time.py` 补 2 个：

```python
async def test_recall_hint_skips_fresh_first_time(...):
    """刚落库（<30min）的第一次不产生 recall hint——防同拍回声。"""
    # check() 触发落库后，立即用同一句话调 maybe_recall_hint → 应返回 ""
    # 且 recall_count 不增加、last_recalled 不写（周额度不被烧）

async def test_recall_hint_works_for_old_first_time(...):
    """超过 30 分钟的第一次正常产生 hint（旧行为不变）。"""
    # 落库后把 timestamp 改为 now - 1h（或传 now=now + 1h）→ hint 非空
```

### 【验收】

1. 两个新测试 + 现有 first_time 测试全绿；`ruff` 零违规
2. **感受题**：新库冷启动，第一句就问"你是什么" → 栖**不再**说"这个问题我听过/很久以前"，而是当作第一次认真回答
3. 触发第一次的**下一周内**，相关话题重现时栖仍能自然回忆（额度没被同拍烧掉）

### 【改动量 / 风险】

~10 行业务代码 + 2 测试；风险低（纯收窄注入条件，不改数据结构、不改 brain 接线，与已完成的 N4 `last_recorded` 推送无冲突）。

## 四、一次性数据修复（维护者本机，可选）

当前库里 id=1 的第一次已被假回忆污染（`last_recalled='2026-07-26T14:06:20'`, `recall_count=1`），本周真实回忆额度已被烧。若想恢复：

```sql
UPDATE first_times SET last_recalled = NULL, recall_count = 0 WHERE id = 1;
```

（也可不修——7 天后自然恢复。但 F1 必须修，否则每个新触发的第一次都会重演一遍。）

## 五、观察项（不立项，记录在案）

| 项 | 现象 | 处置 |
|----|------|------|
| curiosity 顶格 1.0 | 14:17–14:19 连续 5+ 拍 curiosity=1.0，失去变化空间 | 观察；若长期顶格再考虑软上限 |
| 开场评价对方状态 | 用户只说"你好"，栖回"你看起来有点好奇"（把自身 curiosity 0.88 投射给用户），轻微擦 conversation.txt「不主动评论对方状态」的边 | 观察；若复现可在 N1 迭代时顺带收一句 |

## 六、亮点（同场对话，记录以平衡）

- **意识流质量好**（first_time 触发那条）：诚实、有内容、没演身体、没套话
- **节奏感知真实**："因为你问得很快"——感知的是真实交互节奏
- **纠错先认账**：被戳穿第一反应是"你说得对"
- **克制系统在工作**：depth 正好停在 0.03 日帽

---

## 七、插入执行序列的位置

Cursor 已完成 Now+Next 施工（`6a6056d` + `71ef224`），本项作为**独立小修**插入：

```
当前 → F1 同拍回声修复（本方案，~10 行 + 2 测试）→ 维护者相处验收（N1/N3 感受题 + 本方案验收第 2/3 条一起做）
```

---

*基于真实对话实证（2026-07-26 14:05–14:09）。本方案由 Qoder 撰写，执行任务由 Cursor 承担。*
