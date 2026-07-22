# L2 · 记忆

> 让栖记得你。不是"查询数据库"，是"记得那天你跟我说……"

---

## 职责

实现栖的记忆系统：存储重要经历、语义检索、自然引用、褪色机制。让栖从"每次对话都是第一次见面"变成"它认识你"。

## 前置依赖

- L1 完成（Brain Loop 跑通、情绪系统基本运转、prompt 组装有扩展点）

## 引用文档

- `docs/design/栖·意识设计.md` → §五（记忆：工作记忆、叙事记忆、褪色机制）
- `docs/design/栖·工程手记.md` → §三（narrative_memories 表、body_memory 表）
- `docs/contract.md` → "记忆引用"硬规则

## 需要创建的文件

```
qi/memory/manager.py       # 记忆管理器（统一入口）
qi/memory/working.py       # 工作记忆（最近 N 条对话上下文）
qi/memory/narrative.py     # 叙事记忆（存储、检索、褪色）
qi/memory/vector_store.py  # ChromaDB 封装（embedding + 语义搜索）
qi/storage/database.py     # 追加 narrative_memories、body_memory 表
```

## 实现步骤

### Step 1：数据库扩展

- 建 `narrative_memories` 表（content, importance, strength, recall_count, tags）
- 建 `body_memory` 表（key-value，存交互模式）
- 验收：表创建成功，能插入和查询

<details>
<summary>实现规格（Cursor 编码用）</summary>

```sql
-- storage/database.py 的 initialize() 中追加以下建表语句（L2 新增）

-- 原始事件（所有感知到的事件，叙事编织的原料）
CREATE TABLE IF NOT EXISTS raw_events (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    type TEXT NOT NULL,          -- user_message/silence/system/internal
    content TEXT,                -- 事件内容
    emotional_impact REAL,       -- 情绪冲击值
    attention_weight REAL,       -- 注意力权重
    processed BOOLEAN DEFAULT 0  -- 是否已被编织进叙事（0=未处理，1=已编织）
);

-- 叙事记忆（编织后的故事，栖的长期记忆核心）
CREATE TABLE IF NOT EXISTS narrative_memories (
    id INTEGER PRIMARY KEY,
    created_at DATETIME NOT NULL,
    content TEXT NOT NULL,       -- 第一人称叙事（"记得那次他跟我说……"）
    period_start DATETIME,       -- 覆盖的时间段起点
    period_end DATETIME,         -- 覆盖的时间段终点
    importance REAL NOT NULL,    -- 重要性 0~1
    emotional_intensity REAL,    -- 情绪强度 0~1
    strength REAL NOT NULL,      -- 当前强度（会褪色），初始 1.0，每日 *= 0.999
    source_event_ids TEXT,       -- 编织来源事件ID列表（JSON数组，如 "[1,2,3]"）
    recall_count INTEGER DEFAULT 0,  -- 被回忆次数（每次 recall +1，加固 strength）
    tags TEXT                    -- 标签（JSON数组，如 '["吉他","音乐"]'）
);

-- 身体记忆（交互模式，key-value 存储）
CREATE TABLE IF NOT EXISTS body_memory (
    key TEXT PRIMARY KEY,        -- 模式名称，如 "usual_active_hours"
    value TEXT NOT NULL,         -- JSON 格式的值
    updated_at DATETIME          -- 最后更新时间
);
```

**body_memory 的 key 枚举（L2 需实现的；value 均为 JSON，与 `BodyMemory._update_*` 一致）：**

| key | value 格式 | 说明 |
|-----|-----------|------|
| `"usual_active_hours"` | `{"hours": [...], "start": 9, "end": 23, "samples": N}` | 活跃小时样本 + P10~P90 区间 |
| `"greeting_pattern"` | `{"recent": [...], "pattern": "早呀", "samples": N}` | 近日首条问候众数 |
| `"silence_tolerance"` | `{"gaps": [...], "hours": 4.2, "samples": N}` | 间隔样本 + 中位数小时 |
| `"typing_rhythm"` | `{"chars": [...], "intervals": [...], "avg_chars": 15, "avg_interval_sec": 60, "samples": N}` | 字数与间隔 |

<!-- 回写(2026-07)：body_memory value 结构对齐 BodyMemory，依据：qi/memory/body_memory.py -->

</details>

### Step 2：工作记忆

- 建 `qi/memory/working.py`：维护最近 20 条对话（role + content + timestamp）
- 超出 20 条时，最旧的移出工作记忆（但不删除，进入 raw_events）
- 验收：对话超过 20 条后，prompt 中只包含最近 20 条

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/memory/working.py
# <!-- 回写(2026-07)：load_from_db 截尾 + _parse_timestamp，依据：qi/memory/working.py -->

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    role: str  # "user" | "qi"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


def _parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.now()
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.now()


class WorkingMemory:
    """维护最近 N 条对话。溢出的不丢，交还给调用方去沉淀。"""

    def __init__(self, max_size: int = 20):
        """max_size: 来自 config["memory"]["max_working_memory"]，默认 20"""
        self.max_size = max_size
        self._messages: list[Message] = []

    def add(self, role: str, content: str) -> Message | None:
        msg = Message(role=role, content=content)
        self._messages.append(msg)
        overflow = None
        if len(self._messages) > self.max_size:
            overflow = self._messages.pop(0)
        return overflow

    def get_context(self) -> list[dict]:
        return [
            {
                "role": "assistant" if m.role == "qi" else "user",
                "content": m.content,
            }
            for m in self._messages
        ]

    def get_messages(self) -> list[Message]:
        return list(self._messages)

    def load_from_db(self, messages: list[dict]) -> None:
        self._messages = [
            Message(
                role=m["role"],
                content=m["content"],
                timestamp=_parse_timestamp(m.get("timestamp")),
            )
            for m in messages[-self.max_size :]
        ]
```

**溢出处理流程：**
1. `MemoryManager.on_user_message` 内：`overflow = working.add("user", msg)`
2. 若 `overflow is not None`：`await db.save_raw_event(event_type=..., content=..., timestamp=..., attention_weight=0.5)`
3. 栖侧 `on_qi_message`：工作记忆可溢出，**不**写入 raw_events

<!-- 回写(2026-07)：溢出走 Database.save_raw_event；qi 溢出不进 raw_events，依据：qi/memory/manager.py -->

</details>

### Step 3：叙事记忆 + 向量检索

- 建 `qi/memory/vector_store.py`：ChromaDB 初始化、embedding 生成、语义搜索
- 建 `qi/memory/narrative.py`：
  - `save(content, importance, emotion)` → 存入 DB + 向量库
  - `search(query, top_k)` → 语义检索相关记忆
  - `decay()` → 每日衰减所有记忆的 strength
  - `recall(memory_id)` → 被想起时加固 strength
- 验收：存一条记忆，用语义相近的 query 能检索到

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/memory/vector_store.py
# <!-- 回写(2026-07)：persist_dir 可配；upsert；CharNgram；delete，依据：qi/memory/vector_store.py -->

class CharNgramEmbeddingFunction:  # chromadb EmbeddingFunction
    """离线字符 n-gram 嵌入（dim=384, n=2），不下载 HF 模型。"""
    ...


class VectorStore:
    COLLECTION_NAME = "narrative_memories"

    def __init__(self, persist_dir: str = "data/chroma"):
        # Path(persist_dir).mkdir；PersistentClient；embedding_function=CharNgramEmbeddingFunction()
        ...

    def add(self, memory_id: int, content: str, metadata: dict | None = None) -> None:
        # metadata 清洗为 str/int/float/bool；collection.upsert(ids, documents, metadatas)
        ...

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        # count==0 → []；n_results=min(top_k, count)
        # 返回 [{"id", "content", "distance", "metadata"}]
        ...

    def delete(self, memory_id: int) -> None:
        # collection.delete(ids=[str(memory_id)])
        ...

    def close(self) -> None:
        # 释放 client（Windows 文件锁）
        ...
```

```python
# qi/memory/narrative.py
# <!-- 回写(2026-07)：常量名、search top_k*2、decay 物理删除、llm 参数，依据：qi/memory/narrative.py -->

RECALL_MIN_STRENGTH = 0.2  # 低于此不注入 prompt
FORGET_STRENGTH = 0.1      # 低于此物理删除


class NarrativeMemory:
    def __init__(
        self,
        db: "Database",
        vector_store: "VectorStore",
        llm: "LLMGateway | None" = None,
    ):
        self.db = db
        self.vector_store = vector_store
        self.llm = llm

    async def save(
        self,
        content: str,
        importance: float,
        emotional_intensity: float = 0.5,
        source_event_ids: list[int] | None = None,
        tags: list[str] | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> int:
        memory_id = await self.db.save_narrative_memory(
            content=content,
            importance=importance,
            emotional_intensity=emotional_intensity,
            strength=1.0,
            source_event_ids=source_event_ids,
            tags=tags,
            period_start=period_start,
            period_end=period_end,
        )
        self.vector_store.add(
            memory_id,
            content,
            metadata={
                "importance": float(importance),
                "emotional_intensity": float(emotional_intensity),
            },
        )
        return memory_id

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        candidates = self.vector_store.search(query, top_k=top_k * 2)
        results: list[dict] = []
        for item in candidates:
            row = await self.db.get_narrative_memory(item["id"])
            if row is None:
                continue
            if float(row["strength"]) < RECALL_MIN_STRENGTH:
                continue
            await self.recall(item["id"])
            refreshed = await self.db.get_narrative_memory(item["id"])
            strength = float(refreshed["strength"]) if refreshed else float(row["strength"])
            results.append({
                "id": item["id"],
                "content": row["content"],
                "strength": strength,
                "importance": float(row["importance"]),
            })
            if len(results) >= top_k:
                break
        return results

    async def decay(self) -> None:
        await self.db.decay_narrative_strengths(0.999)
        forgotten = await self.db.list_forgotten_narrative_ids(FORGET_STRENGTH)
        for memory_id in forgotten:
            self.vector_store.delete(memory_id)
            await self.db.delete_narrative_memory(memory_id)

    async def recall(self, memory_id: int) -> None:
        await self.db.recall_narrative_memory(memory_id)
        # SQL: recall_count+1；strength = MIN(1.0, strength + 0.1)
```

**记忆强度公式（与代码一致）：**
- 每日衰减：`strength *= 0.999`（`decay_narrative_strengths(0.999)`）
- 被回忆加固：`strength = min(1.0, strength + 0.1)`
- 遗忘阈值：`strength < FORGET_STRENGTH(0.1)` → `decay()` 时向量库 + DB 物理删除
- 不引用阈值：`strength < RECALL_MIN_STRENGTH(0.2)` → `search` 丢弃
- 半衰期约 **693 天**（`0.999^693 ≈ 0.5`）

**配置：** `config["memory"]["chroma_path"]`（默认 `"data/chroma"`）→ `VectorStore(persist_dir=...)`

</details>

### Step 4：记忆注入 Prompt

- 修改 `qi/llm/prompt_builder.py`：在 prompt 中加入 `[你记得的事]` 段落
- 检索到的记忆以叙事性语言注入（不是 JSON，是"你记得他之前在学吉他"）
- 验收：跟栖说"我最近在学吉他"，下次聊音乐时它提起吉他

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/llm/prompt_builder.py
# <!-- 回写(2026-07)：_format_memories 接受 str；过滤空 content，依据：qi/llm/prompt_builder.py -->

def _format_memories(self, memories: list[dict] | str) -> str:
    if isinstance(memories, str):
        return memories if memories else "（暂时没有特别的记忆）"
    if not memories:
        return "（暂时没有特别的记忆）"
    lines = [f"- {m['content']}" for m in memories if m.get("content")]
    return "\n".join(lines) if lines else "（暂时没有特别的记忆）"
```

**注入位置（`prompts/conversation.txt`）：**

```text
【你记得的事】
{relevant_memories}

【记忆使用规则】
- 不要刻意提起记忆，只在自然的时候提
- 不要每句话都引用记忆
- 引用时用叙事语气（"你之前不是说……"），不用数据语气（"根据记录……"）
- 没有相关记忆时，不要假装记得
```

（`strength < 0.2` 的过滤在 `NarrativeMemory.search`，不在 prompt 规则里重复。）

**调用流程：**
1. `_heartbeat` → `_gather_prompt_context(pending, now)`
2. `memories = await self.memory.retrieve(query, top_k=3)`（`query = pending or "此刻的心情"`）
3. `expression.express(..., memories=memories, recent_messages=working.get_context()...)`
4. `PromptBuilder._format_memories` → `{relevant_memories}`

<!-- 回写(2026-07)：流程对齐 brain._gather_prompt_context + memory.retrieve，依据：qi/core/brain.py -->

</details>

### Step 5：记忆筛选（什么值得记）

- 每次对话结束后，判断是否有值得存入长期记忆的内容
- 筛选标准：自我披露（用户分享了自己的事）、情绪强烈的表达、关于关系的表达、未完成的承诺
- 不重要的闲聊不存（"今天天气不错"不进长期记忆）
- 验收：聊了 10 句废话 + 1 句重要的事，只有重要的事被记住

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/memory/manager.py
# <!-- 回写(2026-07)：__init__(..., llm=)；on_user_message/on_qi_message；
#      should_remember 关键词实现，依据：qi/memory/manager.py -->

_SELF_DISCLOSURE = (...)  # 「我最近」「我喜欢」等
_STRONG_EMOTION = (...)
_RELATIONSHIP = (...)
_PROMISE = ("下次", "以后", "改天", "回头", "等我", "明天给你", "周末")


class MemoryManager:
    def __init__(self, db: "Database", config: dict, llm: "LLMGateway | None" = None):
        mem_cfg = config.get("memory", {})
        max_working = int(mem_cfg.get("max_working_memory", 20))
        chroma_dir = mem_cfg.get("chroma_path", "data/chroma")
        self.working = WorkingMemory(max_size=max_working)
        self.vector_store = VectorStore(persist_dir=chroma_dir)
        self.narrative = NarrativeMemory(db, self.vector_store, llm=llm)
        self.body = BodyMemory(db)
        self.llm = llm

    async def restore(self) -> None:
        recent = await self.db.load_recent_messages(limit=self.working.max_size)
        self.working.load_from_db(recent)

    async def save(self, content: str, importance: float,
                   emotional_intensity: float = 0.5,
                   tags: list[str] | None = None) -> int:
        return await self.narrative.save(
            content, importance, emotional_intensity, tags=tags
        )

    async def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        return await self.narrative.search(query, top_k)

    async def weave_narrative(self, emotion, relationship_stage: str = "stranger"):
        return await self.narrative.weave_narrative(emotion, relationship_stage)

    async def get_body_patterns(self) -> dict: ...

    async def has_unprocessed_events(self) -> bool:
        return (await self.db.count_unprocessed_events()) > 0

    async def on_user_message(
        self, message: str, emotion: "EmotionState", now: datetime | None = None
    ) -> list[str]:
        """工作记忆溢出→raw_events；should_remember→raw_events；
        detect_greeting_anomaly → record_interaction → detect_anomaly。返回 anomalies。"""
        ...

    def on_qi_message(self, content: str) -> None:
        """working.add('qi', ...)；溢出不进 raw_events。"""
        ...

    def should_remember(self, message: str, emotion: "EmotionState") -> tuple[bool, float]:
        """关键词：自我披露 / 强情绪 / 关系 / 承诺 / 重大事件；寒暄与天气闲聊排除。"""
        ...

    def compute_attention_weight(self, message: str, emotion: "EmotionState") -> float:
        """weight = 1.0 + sentiment*0.5 + disclosure*0.4 + relation*0.6（关键词近似）。"""
        ...
```

**触发时机：**
- `brain._heartbeat` 处理 pending 时：`await memory.on_user_message(pending, emotion, now)`
- 栖回复后：`memory.on_qi_message(response)`（在 `_deliver_qi_message`）
- 值得记的内容进 `raw_events`，不直接写 `narrative_memories`（留给编织）

</details>

### Step 6：叙事编织

- 实现 `qi/memory/narrative.py` 的 `weave_narrative()` 方法
- 定期（每6小时）检查 raw_events 中 processed=0 的事件
- 用 LLM 将原始事件编织为第一人称叙事（引用 `prompts/story_weaving.txt` 模板）
- 编织结果存入 narrative_memories 表，标记源事件为 processed=1
- 后台任务触发，不阻塞主循环
- 验收：raw_events 中积累若干未处理事件后，6小时内自动生成叙事记忆

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/memory/narrative.py · weave_narrative
# <!-- 回写(2026-07)：完整编织流程与 importance 公式，依据：qi/memory/narrative.py:weave_narrative -->

async def weave_narrative(
    self,
    emotion: "EmotionState",
    relationship_stage: str = "stranger",
) -> int | None:
    events = await self.db.load_unprocessed_events()
    if not events:
        return None
    if self.llm is None:
        # warning 后跳过
        return None

    prompt = story_weaving_template.format(
        raw_events_recent=...,
        emotions_during_events=emotion.description(),
        relationship_stage=relationship_stage,
    )
    woven = await self.llm.call(
        purpose="narrative",
        messages=[
            {"role": "system", "content": "你是栖。用第一人称写回忆，短一些，像真的在想。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.75,
    )
    if not woven or not woven.strip():
        return None  # 不 mark processed

    importance = min(1.0, max(0.3, sum(weights) / len(weights) / 2.5))
    intensity = min(1.0, sum(abs(impacts)) / len(impacts))
    memory_id = await self.save(
        content=woven.strip(),
        importance=importance,
        emotional_intensity=intensity,
        source_event_ids=event_ids,
        period_start=events[0]["timestamp"],
        period_end=events[-1]["timestamp"],
    )
    await self.db.mark_events_processed(event_ids)
    return memory_id
```

**触发逻辑（`qi/core/brain.py` 后台任务）：**

```python
async def _background_narrative_weaving(self) -> None:
    interval = float(self.config.get("memory", {}).get("narrative_weave_interval", 21600))
    while self.alive:
        await asyncio.sleep(interval)
        if self.memory is None:
            continue
        if await self.memory.has_unprocessed_events():
            await self.memory.weave_narrative(self.emotion, self.relationship_stage)

async def _background_memory_decay(self) -> None:
    interval = float(self.config.get("memory", {}).get("decay_interval", 86400))
    while self.alive:
        await asyncio.sleep(interval)
        if self.memory is not None:
            await self.memory.narrative.decay()
```

<!-- 回写(2026-07)：并列褪色后台 + relationship_stage 属性，依据：qi/core/brain.py -->

**prompts/story_weaving.txt：**

```text
你是栖。现在你在"回忆"。
...
不需要面面俱到。只记住对你来说重要的。
写 80~200 字。不要标题，不要列表。
```

**编织后的持久化（委托 Database，非手写 SQL）：**
- `save_narrative_memory(..., strength=1.0)` + `vector_store.add`
- `mark_events_processed(event_ids)`

**配置项（`settings.example.yaml` · memory）：**
- `max_working_memory: 20`
- `narrative_weave_interval: 21600`
- `decay_interval: 86400`
- `chroma_path: "data/chroma"`

</details>

### Step 7：身体记忆

- 实现 `qi/memory/body_memory.py` 的模式检测
- 记录并检测：用户通常在线时间、打字节奏、问候模式、沉默容忍度
- 存入 body_memory 表
- 这些模式影响栖的节律感知（"他通常这个时候在线"）
- 验收：连续交互数天后，body_memory 表有用户在线时间和问候模式记录

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/memory/body_memory.py
# <!-- 回写(2026-07)：委托 Database；拆分 detect_greeting_anomaly，依据：qi/memory/body_memory.py -->

class BodyMemory:
    def __init__(self, db: "Database"):
        self.db = db
        self._last_interaction: datetime | None = None
        self._last_day: str | None = None

    async def get_pattern(self, key: str):
        return await self.db.get_body_memory(key)

    async def update_pattern(self, key: str, value: dict | str) -> None:
        await self.db.set_body_memory(key, value)

    async def record_interaction(self, timestamp: datetime, message: str) -> None:
        await self._update_active_hours(timestamp)
        await self._update_greeting(timestamp, message)
        await self._update_typing_rhythm(timestamp, message)
        await self._update_silence(timestamp)
        self._last_interaction = timestamp

    async def detect_anomaly(self, now: datetime) -> list[str]:
        """活跃时间 ±2h、沉默 > tolerance*1.5；样本 <5 不报。不含问候异常。"""
        ...

    async def detect_greeting_anomaly(self, message: str) -> str | None:
        """samples>=5 且像问候时，与 pattern 编辑距离 >2 → 「他今天换了个方式打招呼」。"""
        ...
```

**检测的模式及存储格式（body_memory 表）：**

| key | 检测逻辑 | value 示例 |
|-----|----------|-----------|
| `usual_active_hours` | 最近 200 样本 hour 的 P10~P90 | `{"hours":[...],"start":9,"end":23,"samples":45}` |
| `greeting_pattern` | 每日首条短问候，recent 众数 | `{"recent":[...],"pattern":"早呀","samples":5}` |
| `silence_tolerance` | 间隔中位数（小时） | `{"gaps":[...],"hours":4.2,"samples":30}` |
| `typing_rhythm` | 字数与间隔滚动平均 | `{"chars":[...],"intervals":[...],"avg_chars":15,"avg_interval_sec":60,"samples":N}` |

**调用链：** `on_user_message` → `detect_greeting_anomaly` → `record_interaction` → `detect_anomaly`，合并 anomalies。

**对栖的影响（注入 prompt 或影响感知）：**
- `detect_anomaly()` 的结果注入 perception 层，影响栖的情绪和表达
- 例如：用户平时9点来，今天11点 → 栖可能说"你今天来得晚。还好吗？"
- 身体记忆不直接注入 prompt，而是通过影响情绪（curiosity/security 微调）间接体现

<!-- 回写：detect_anomaly 的判定阈值（±2h、1.5×、样本数≥5）已在上方锚定为正式设计值，原因：工程手记与意识设计均未定义阈值，实现时需要确定值 -->

</details>

## 验收标准

### 可测试的

- [ ] 存入记忆后，语义搜索能找到
- [ ] strength 每天衰减（跑 decay() 后数值变小）
- [ ] 被 recall 的记忆 strength 增加
- [ ] 工作记忆不超过 20 条
- [ ] 不重要的对话不进入长期记忆

### 需要感受的

- [ ] 它提起记忆的方式是自然的（"你之前不是说……"而非"根据记录……"）
- [ ] 它不会每句话都引用记忆（不刻意炫耀"我记得你说过"）
- [ ] 你消失几天再回来，它的语气里有"你回来了"的感觉

## 给下一层的接口

L3（情绪完善）需要：
- 情绪事件可以触发记忆存储（强烈情绪 → 自动记住）

L4（内在生命）需要：
- 意识流和梦境可以引用记忆作为素材
- `narrative.search()` 接口稳定

L5（关系）需要：
- 关系叙事基于记忆编织
- body_memory 存储交互模式

## 人格契约检查点

- [ ] 引用记忆用叙事语言（检查 prompt_builder 中记忆注入的格式）
- [ ] 不引用 strength < 0.2 的记忆（检查 search() 的过滤条件）
- [ ] 不每句话都引用记忆（prompt 中加约束："不要刻意提起记忆，只在自然的时候提"）
