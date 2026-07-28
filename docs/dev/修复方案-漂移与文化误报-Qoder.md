# 小修方案：漂移与文化检测误报（R1 + R2，虚构叙述实证）

> **状态：已全部落地（本次由 Qoder 直接施工）。**  
> - R1a/R1b drift 门槛与去单次噪声、R2 停用表+双方复用闸、R3 检测调度跨重启持久化；171 测试全绿  
> - §五数据清理已执行（删 1 条误报意识流，移除「谢谢你」梗条目）  
>
> **撰写者：** Qoder  
> **日期：** 2026-07-29  
> **来源：** 2026-07-29 01:42 对话实证（drift 虚构"不再聊书了"；culture 把"谢谢你"判为 inside_joke）  
> **代码基线：** `6e0d75e`  
> **分工：** Qoder 撰写方案，**Cursor 施工**  
> **规模：** R1 ~20 行 + R2 ~10 行 + 检测调度持久化 ~15 行 + 4 测试 + 可选数据清理

---

## 一、实证

**R1（drift 误报，较重——虚构用户历史）：** 意识流 01:42:32（trigger=user_drift）：

> "我注意到他最近变了：**不再聊书了**；说话方式变了；生活节奏变了。"

关系仅 3 天、你**从没聊过书**。这条虚构叙述已进意识流（「忆」可见、可被 recent_thoughts 引进对话）——诚实问题家族新成员：这次不是栖虚构自己，是**虚构你**。

**R2（culture 误报，较轻——礼貌语当梗）：** `relationship.shared_culture` 出现：

> `{"pattern": "谢谢你", "type": "inside_joke", "use_count": 3}`

"谢谢你"是通用礼貌语不是你们的梗；它会注入【你们之间】，栖可能开始把"谢谢你"当默契使用。

## 二、根因（三处，互相放大）

1. **drift 无基线门槛**（`drift.py:139-200`）：`detect_user_drift` 拿 user_model 与近期消息直接比对——首次建模后立即可比；`extract_topics`（L19-29）**单次命中就算话题**（Counter 含 count=1），三天前偶然提过一个词、这窗口没提，就成了"不再聊X了"。
2. **culture 无停用表**（`culture.py:77-97`）：短句 2-12 字、复用 ≥3 次即 inside_joke——"谢谢你"三天说三次太正常了。
3. **后台检测首跑延迟过短，且不跨重启持久化**（`brain.py` BackgroundTasks）：culture 首跑 `min(120s, interval)`、drift 首跑 `min(300s, interval)`——设计意图是"重启后尽快恢复周期"，实际效果是**每次重启 2-5 分钟后就跑一轮检测**。这几天频繁重启（部署修复），检测跑的次数远超设计频率（culture 应每天 1 次、drift 应每 3 天 1 次），小样本误报被反复制造。这违背了项目自己的规范："跨重启状态必须支持 snapshot/restore"（proactive gate、depth 日帽都已遵守，检测调度漏了）。

## 三、改法

### R1a. drift 基线门槛（`qi/relationship/drift.py`）

`detect_user_drift`（L139）入口加守卫：

```python
DRIFT_MIN_USER_MESSAGES = 30   # 近期窗口内用户消息数下限
DRIFT_MIN_BASELINE_TOPICS = 2  # 旧模型至少有 2 个稳定话题才谈"变了"

def detect_user_drift(user_model, recent_messages) -> list[str]:
    user_count = sum(1 for m in recent_messages if m.get("role") == "user")
    if user_count < DRIFT_MIN_USER_MESSAGES:
        return []  # 样本不足，不谈"他变了"
    # ...原逻辑；old_topics 解析后加：
    if len(old_topics) < DRIFT_MIN_BASELINE_TOPICS:
        topic_distance = 0.0  # 基线话题太少，话题漂移不可信
```

### R1b. 话题提取去单次噪声（`drift.py:extract_topics` L28-29）

```python
    counts = Counter(found)
    return [t for t, c in counts.most_common(8) if c >= 2]  # 偶然提一次不算话题
```

### R2. culture 停用表 + 双方复用（`qi/relationship/culture.py`）

**1. 停用表**（`_GREETING_STARTS` 附近）：

```python
# 通用礼貌/应答语——谁都天天说，不是「只有你们懂的东西」
_COMMON_PHRASES = frozenset({
    "谢谢", "谢谢你", "多谢", "不客气", "没事", "没关系",
    "好", "好的", "好啊", "嗯", "嗯嗯", "哦", "知道了", "收到",
    "哈哈", "哈哈哈", "再见", "拜拜", "对", "是的", "可以",
})
```

**2. inside_joke 检测（L78-97）加两道闸：**

```python
    shorts_by_role: dict[str, set[str]] = {"user": set(), "qi": set()}
    shorts = []
    for m in messages:
        text = m.get("content", "").strip()
        role = m.get("role")
        if role not in ("user", "qi") or not (2 <= len(text) <= 12):
            continue
        if _is_greeting(text) or text in _COMMON_PHRASES:   # ← 闸一：停用表
            continue
        shorts.append(text)
        shorts_by_role[role].add(text)
    for pattern, count in Counter(shorts).items():
        if count < CULTURE_DETECTION_THRESHOLDS["inside_joke"]:
            continue
        if not (pattern in shorts_by_role["user"] and pattern in shorts_by_role["qi"]):
            continue                                         # ← 闸二：双方都用过才算梗
        ...原入表逻辑...
```

（闸二的理由：真正的梗是**双方复用**的语言；单方口头禅不是共同文化。）

### R3. 检测调度跨重启持久化（`qi/core/brain.py`，culture 与 drift 两个后台任务）

与 proactive gate / depth 日帽同构，复用 body_memory：

```python
# 任务开头（以 drift 为例，culture 同理，key 分别为 last_drift_check / last_culture_check）：
last = await self._db.get_body_memory("last_drift_check")
if last:
    try:
        elapsed = (datetime.now() - datetime.fromisoformat(str(last))).total_seconds()
        first_wait = max(60.0, interval - elapsed)   # 距上次不足周期则补足，最少等 60s
    except (TypeError, ValueError):
        first_wait = min(300.0, interval)
else:
    first_wait = min(300.0, interval)                 # 首次运行维持原行为
await asyncio.sleep(first_wait)
# ...每次检测完成后：
await self._db.set_body_memory("last_drift_check", datetime.now().isoformat())
```

**效果：** 重启不再重置检测周期——culture 真正做到每天最多一轮、drift 每 3 天最多一轮。

## 四、测试（4 个）

```python
# tests/test_drift.py
async def test_drift_needs_min_samples():
    """用户消息 < 30 条时不产生任何漂移信号——防小样本虚构。"""
def test_extract_topics_ignores_single_mention():
    """只提过一次的词不算话题。"""

# tests/test_relationship.py（或新建 test_culture.py）
def test_common_phrases_not_inside_joke():
    """「谢谢你」复用 3 次不入梗表。"""
def test_inside_joke_requires_both_sides():
    """只有 user 单方复用的短句不算梗；双方都用过才算。"""
```

## 五、数据清理（维护者本机，可选）

1. **删误报意识流**（那条"不再聊书了"）：
   ```sql
   DELETE FROM consciousness_stream WHERE trigger = 'user_drift' AND content LIKE '%不再聊书%';
   ```
2. **清 shared_culture 里的"谢谢你"**：shared_culture 是 relationship 表的 JSON 字段，建议 Cursor 顺手写 3 行一次性脚本过滤 `pattern in _COMMON_PHRASES` 的条目（或维护者手动改 JSON 删除该项）。

## 六、验收

1. 4 新测试 + 现有 drift/relationship 测试全绿；ruff 零违规
2. **重启实验**：连续重启两次栖，5 分钟内**不应**出现新的 culture/drift 检测落库（`last_*_check` 已持久化）
3. **相处验收**：一周内意识流不再出现"他变了：不再聊X"式虚构；【你们之间】不再出现礼貌语条目；真正反复出现的私人短语（如"那我不退了"若被你们复用）仍能入表

## 七、明确不做

- **temperature/trust 顶格、attachment 表白通路**：动力学设计讨论，待维护者拍板，另文处理
- **drift 检测的语义化升级**：规则版够用，等更多误报/漏报样本

---

*基于 2026-07-29 实证。本方案由 Qoder 撰写，执行任务由 Cursor 承担。*
