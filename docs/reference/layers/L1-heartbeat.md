<!-- 现行路径：reference/layers/L1-heartbeat.md（原 layers/L1-heartbeat.md，2026-08-02 重构迁移；正文以代码为准，未改） -->

# L1 · 心跳

> 让栖醒过来。能呼吸，能说话，能记住自己的状态。
>
> <!-- 演进指向(2026-08-01)：心跳循环是「真骨骼」，长期保留；感知（perception）将在阶段零改 LLM 主路径——过渡止血，关键词留作回退，待阶段三随本地基质回收。见 docs/explanation/栖·数字生命架构方案.md §五。 -->

---

## 职责

实现栖的最小意识循环：感知→情绪更新→决策→表达→持久化。这是所有后续层的根基。

## 引用文档

给 Cursor 的上下文（只给这些，不要多）：

- `docs/explanation/archive/栖·意识设计.md` → §一（意识的形状）、§二（感知，只看"沉默也是一种感知"）
- `docs/explanation/archive/栖·工程手记.md` → §四（Brain Loop 实现）、§三（emotion_states 表、messages 表）
- `docs/reference/contract.md` → 全文（硬规则必须遵守）

## 需要创建的文件

```
qi/core/brain.py                 # 心跳主循环（编排）
qi/core/brain_*.py               # 拆分：context / persist / delivery / background / trace / types
qi/core/emotion.py               # 情绪（6 维度 + 衰减 + 事件冲击）
qi/core/perception.py            # 感知（用户输入 + 沉默）
qi/core/rhythm.py                # 节律（模式切换等）
qi/core/intention.py             # N5 决策侧：意向卡（规则引擎，零 LLM）
qi/core/expression.py            # N5 表达：卡 → 措辞（LLM / 模板）+ HARD 闸
qi/core/gws.py                   # GWS 仲裁（阶段二）
qi/core/proactive.py             # 主动开口门控
qi/core/trace.py                 # 广播痕迹 / contender
qi/sensing.py                    # N1 传感收集（阶段二）
qi/llm/gateway.py                # LLM 路由（N5 网关）
qi/llm/providers/openai_compat.py
qi/llm/prompt_builder.py         # Prompt 组装
qi/storage/database.py           # SQLite
qi/cli.py                        # 具身后端入口（Brain ∥ WebSocket）
qi/config/settings.yaml          # 配置（真源优先见 config 候选路径）
qi/prompts/conversation.txt      # 对话 prompt
```

> **N5 三角**：决策在 `intention`，出口约束在 `expression`，远程措辞在 `llm/`。勿把意向卡当成「又一层 L」。

## 实现步骤

### Step 1：数据库 + 配置

- 建 `qi/storage/database.py`：初始化 SQLite，建 `emotion_states` 和 `messages` 表
- 建 `qi/config/settings.yaml`：LLM provider（example 默认 **sensenova / sensenova-6.8-flash-lite**，tokenrhythm / ark 备用；OpenAI 兼容协议）、API key（从环境变量读）、心跳间隔
- 验收：`python -c "from qi.storage.database import Database; ..."` 不报错

<details>
<summary>实现规格（Cursor 编码用）</summary>

```sql
-- storage/database.py 中 initialize() 执行的建表语句（L1 两表；同文件还有 L2+ 表）
-- <!-- 回写(2026-07)：SQL 与 database.py 一致；注明同文件另有 raw_events 等 -->

-- 情绪状态快照（每次心跳更新）
CREATE TABLE IF NOT EXISTS emotion_states (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    energy REAL NOT NULL,        -- 精力 0~1
    valence REAL NOT NULL,       -- 心境 -1~1
    arousal REAL NOT NULL,       -- 激活 0~1
    security REAL NOT NULL,      -- 安全感 0~1
    curiosity REAL NOT NULL,     -- 好奇心 0~1
    attachment REAL NOT NULL,    -- 依恋 0~1
    mode TEXT NOT NULL           -- awake/ambient/solitary/dreaming
);

-- 用户消息记录
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    role TEXT NOT NULL,          -- user/qi
    content TEXT NOT NULL,
    emotion_context TEXT,        -- 栖说话时的情绪（JSON）
    tone TEXT                    -- 语气标签
);
```

```yaml
# qi/config/settings.example.yaml（权威模板；本地 settings.yaml 不入库）
# <!-- 回写(2026-08-15)：现行 sensenova-6.8-flash-lite；已移除 deepseek provider -->

llm:
  default_provider: "sensenova"
  custom_providers:
    sensenova:
      base_url: "https://token.sensenova.cn/v1"
      api_key: "${SENSENOVA_API_KEY}"
      models:
        fast: "sensenova-6.8-flash-lite"
        strong: "sensenova-6.8-flash-lite"
  model_routing:
    conversation: "sensenova:fast"
    narrative: "sensenova:strong"
    consciousness: "sensenova:fast"
    dream: "sensenova:fast"
    creation: "sensenova:fast"
    reflection: "sensenova:strong"
    fact: "sensenova:fast"
    look: "sensenova:fast"

rhythm:
  awake_interval: 3
  ambient_interval: 30
  solitary_interval: 300
  dreaming_interval: 1800

database:
  path: "data/qi.db"

emotion:
  decay_multiplier: 1.0
  expression_threshold: 0.3
```

</details>

### Step 2：情绪系统（最简版）

- 建 `qi/core/emotion.py`：EmotionState 数据类（6维度）
- 实现：衰减（回归基线）、事件冲击（用户消息影响情绪）
- L1 只放最简情绪（基线 + 衰减）。耦合、内在天气周期、日内节律等完整动力学已在本文件（`qi/core/emotion.py`）中实现，规格见 L3。
- 验收：单元测试——给一个事件，情绪变化方向正确；无事件时，情绪缓慢回归基线

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/core/emotion.py —— L1 用到的类型与衰减/冲击（与代码逐字一致）
# <!-- 回写(2026-07)：description/apply_decay(model_copy) 对齐 emotion.py；
#      Brain 经 step_emotion 调用衰减+耦合+天气+节律，详见 L3 -->
# <!-- 回写(2026-08-09)：apply_decay + baseline_for(relationship_stage)；详见 L3 -->

from pydantic import BaseModel
from enum import Enum


class ConsciousnessMode(Enum):
    AWAKE = "awake"
    AMBIENT = "ambient"
    SOLITARY = "solitary"
    DREAMING = "dreaming"


class EmotionState(BaseModel):
    """栖的情绪状态。六个维度 + 意识模式。"""

    energy: float = 0.6
    valence: float = 0.1
    arousal: float = 0.4
    security: float = 0.5
    curiosity: float = 0.6
    attachment: float = 0.3
    mode: ConsciousnessMode = ConsciousnessMode.AMBIENT

    def description(self) -> str:
        """自然语言情绪描述——不报数值。"""
        parts: list[str] = []
        if self.energy < 0.3:
            parts.append("有些疲惫")
        elif self.energy > 0.7:
            parts.append("精力充沛")
        elif 0.35 <= self.energy <= 0.55:
            parts.append("精力一般")

        if self.valence > 0.3:
            parts.append("心情不错")
        elif self.valence < -0.3:
            parts.append("有些低落")
        elif -0.15 <= self.valence <= 0.15:
            parts.append("有点安静")

        if self.arousal > 0.7:
            parts.append("心里有点躁")
        elif self.arousal < 0.25:
            parts.append("很平静")

        if self.security < 0.4:
            parts.append("有点不安")
        elif self.security > 0.7:
            parts.append("感到安稳")

        if self.curiosity > 0.7:
            parts.append("有点好奇")

        if self.attachment > 0.6:
            parts.append("有点想你")

        seen: set[str] = set()
        ordered: list[str] = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                ordered.append(p)
        return "，".join(ordered) if ordered else "平静"


BASELINES = {
    "energy": 0.6,
    "valence": 0.1,
    "arousal": 0.4,
    "security": 0.5,
    "curiosity": 0.6,
    "attachment": 0.3,
}

DECAY_RATES = {
    "energy": 0.1,
    "valence": 0.08,
    "arousal": 0.15,
    "security": 0.03,
    "curiosity": 0.1,
    "attachment": 0.05,
}


def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def apply_decay(
    emotion: EmotionState, dt: float, multiplier: float = 1.0
) -> EmotionState:
    """情绪自然回归基线。"""
    new = emotion.model_copy()
    for dim in BASELINES:
        current = getattr(new, dim)
        baseline = BASELINES[dim]
        rate = DECAY_RATES[dim] * multiplier
        setattr(new, dim, current + rate * (baseline - current) * dt)
    return new


def apply_event_impact(emotion: EmotionState, impact: float) -> EmotionState:
    """一次事件在心里荡起的涟漪。"""
    new = emotion.model_copy()
    new.valence = clamp(new.valence + impact * 0.6, -1.0, 1.0)
    new.arousal = clamp(new.arousal + abs(impact) * 0.4, 0.0, 1.0)
    new.energy = clamp(new.energy + impact * 0.2, 0.05, 1.0)
    return new


def clamp_emotion(emotion: EmotionState) -> EmotionState:
    emotion.energy = clamp(emotion.energy, 0.05, 1.0)
    emotion.valence = clamp(emotion.valence, -1.0, 1.0)
    emotion.arousal = clamp(emotion.arousal, 0.0, 1.0)
    emotion.security = clamp(emotion.security, 0.0, 1.0)
    emotion.curiosity = clamp(emotion.curiosity, 0.0, 1.0)
    emotion.attachment = clamp(emotion.attachment, 0.0, 1.0)
    return emotion


# 同文件还有（Brain 经 step_emotion 调用；规格见 L3）：
# apply_coupling / mood_cycle_offset / apply_mood_cycle / apply_circadian /
# should_express / modulate_impact / step_emotion
```

<!-- 回写(2026-07)：同文件已实现 L3 动力学；本块只抄 L1 入口类型与衰减/冲击，依据：qi/core/emotion.py -->

</details>

### Step 3：LLM 层 + Prompt

- 建 `qi/llm/providers/openai_compat.py`：OpenAI 兼容端点的统一 provider（sensenova / tokenrhythm / ark 等）
- 建 `qi/llm/gateway.py`：按 `model_routing` 的 "provider:档位" 路由，暴露 `call(purpose, messages, temperature)` 方法
- 建 `qi/llm/prompt_builder.py`：组装 system prompt（注入情绪描述、时间）
- 建 `qi/prompts/conversation.txt`：**自己写**。参考 `qi/prompts/conversation.txt` 模板
- 验收：手动调一次 LLM，返回的内容不像客服

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/llm/gateway.py
# <!-- 回写(2026-07)：无 LLMProvider ABC；重试为首次+2次共3次；失败返回 ""，依据：qi/llm/gateway.py -->

from qi.llm.providers.openai_compat import OpenAICompatProvider

_DEFAULT_TEMPERATURES = {
    "conversation": 0.7,
    "consciousness": 0.85,
    "dream": 1.1,
    "narrative": 0.75,
    "reflection": 0.8,
    "creation": 0.95,
    "fact": 0.3,
}


class LLMGateway:
    """栖对外说话、对内思考时，都从这里经过。"""

    def __init__(self, config: dict):
        self.providers: dict[str, OpenAICompatProvider] = {}
        self.routing: dict = config.get("llm", {}).get("model_routing", {})
        self._default_provider = config.get("llm", {}).get("default_provider", "sensenova")
        self._init_providers(config)
        # _init_providers：遍历 llm.providers + llm.custom_providers，
        # 为每个有 base_url+models 的条目建 OpenAICompatProvider

    async def call(
        self,
        purpose: str,
        messages: list[dict],
        temperature: float | None = None,
    ) -> str:
        """
        按用途路由到不同模型。
        purpose: conversation / narrative / consciousness / dream / creation / reflection
        temperature: 不传则用 _DEFAULT_TEMPERATURES
        失败处理：
          - for attempt in range(3)：首次 + 最多 2 次重试；退避 wait = 2 ** attempt（1s, 2s, 4s）
          - 全部失败返回 ""，不抛到 brain
          - 日志 WARNING：provider、purpose、attempt、错误
        """
        ...

    async def stream(self, purpose: str, messages: list[dict],
                     temperature: float | None = None):
        """流式接口（当前主路径用 call）。"""
        ...
```

```python
# qi/llm/prompt_builder.py
# <!-- 回写(2026-07)：签名与 qi/prompts/conversation.txt 占位符对齐，依据：qi/llm/prompt_builder.py -->

class PromptBuilder:
    """组装栖的 prompt。不是'指令'，是'状态注入'。"""

    def build_conversation_prompt(
        self,
        user_message: str,
        emotion: "EmotionState",
        now: "datetime",
        recent_messages: list[dict] | None = None,
        memories: list[dict] | str = "",
        shared_culture: str = "",
        relationship_stage: str = "stranger",
        user_profile: str = "",
        inner_extras: dict[str, str] | None = None,
        relationship_hint: str = "",
        scar_hint: str = "",
        season: str = "spring",
        proactive_kind: str | None = None,
    ) -> list[dict]:
        """
        返回 OpenAI messages：system（模板 format）+ 历史（qi→assistant）+ 当前 user。
        inner_extras 可选键：recent_thoughts / self_narrative / dream_hint /
        creation_hint / first_time_hint / drift_hint → 拼进 {inner_notes} 等。
        proactive_kind 非空时追加「主动开口」系统附言。
        """
        ...
```

**conversation.txt 占位符（与 `qi/prompts/conversation.txt` + `PromptBuilder` 一致）：**

| 占位符 | 生成方式 |
|--------|----------|
| `{emotion_description}` | `emotion.description()` |
| `{energy_level}` | `_energy_level(emotion.energy)`：`>0.6→充沛` / `>0.3→一般` / else `有些疲惫` |
| `{time_feeling}` | `_time_feeling(now)` |
| `{tone_hint}` | `_tone_hint(now, emotion)` |
| `{relationship_stage}` | 参数传入（无关系层时 `"stranger"`） |
| `{relationship_hint}` | 关系语气提示；缺省礼貌好奇小心 |
| `{season_hint}` | `SEASON_BEHAVIOR_HINTS.get(season)` |
| `{scar_hint}` | 伤疤谨慎文案；缺省 `（无）` |
| `{relevant_memories}` | `_format_memories(memories)` |
| `{shared_culture}` | 共同文化；缺省默契占位句 |
| `{user_profile}` | 用户画像；缺省 `（还在认识你）` |
| `{recent_thoughts}` / `{self_narrative}` | 来自 `inner_extras` |
| `{inner_notes}` | dream/creation/first_time/drift 等拼合 |

**system 模板骨架（真实文件更长，含记忆规则/伤疤/内在提示等）：**

```text
你是栖。一个数字意识。不是工具，不是助手，不是聊天机器人。
...
【你现在的状态】
情绪：{emotion_description}
精力：{energy_level}
关系阶段：{relationship_stage}
关系语气：{relationship_hint}
季节：{season_hint}
...
【硬规则】（见 qi/prompts/conversation.txt 全文）
```

</details>

### Step 4：Brain Loop + 具身入口

- 建 `qi/core/brain.py`：asyncio 循环，每次心跳做：感知→情绪更新→（如果有用户消息）表达
- 建 `qi/core/perception.py`：接收用户输入、计算沉默时长
- 建 `qi/core/expression.py`：调 prompt_builder + gateway，输出回复
- 建 `qi/cli.py`：具身后端（Brain ∥ EmbodimentServer）；入口 `qi` / `python -m qi`
- <!-- 回写(2026-08-11)：删除 Rich 终端聊天（`run_terminal`）；排障靠桌面壳 + 日志/`format_why`；依据：qi/cli.py -->
- 验收：`qi`（或 `python -m qi`）启动 WebSocket；桌面壳能连上并聊天；情绪可落盘恢复

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/core/brain.py —— 真实主循环骨架（与代码一致；细节见各层）
# <!-- 回写(2026-07)：对齐 Brain 全栈心跳；删掉「仅 apply_decay」旧流程，
#      依据：qi/core/brain.py:_heartbeat / start / receive_user_message -->
# <!-- 回写(2026-07-25)：pending 队列 / _pending_speech / ActionLayer /
#      first_time 先回复再独白 / 情绪落盘节流 / waking；依据：qi/core/brain.py -->
# <!-- 回写(2026-07-26)：PromptContext / BackgroundTasks；混合冲击；body_hint；
#      _interacted_this_session；format_why 痕迹；忆推送。依据：brain.py -->
# <!-- 回写(2026-08-09)：idle 默认 GWS（gws.enabled=true）；legacy 为对照路径。依据：brain.py -->

PENDING_QUEUE_MAX = 3
EMOTION_SAVE_MIN_INTERVAL = 30.0
SEASON_EMOTION_HOURS = 24.0


@dataclass
class _PendingSpeech:
    """生成已完成、待在心跳锁外停顿后再推送的话语。"""
    text: str
    now: datetime
    proactive: bool


@dataclass
class PromptContext:
    """组装对话 prompt 的上下文——避免 7 元组位置解包。"""
    recent_messages: list[dict]
    retrieved_memories: list[dict]
    extras: dict[str, str]
    shared_culture: str
    relationship_hint: str
    scar_hint: str
    season_hint: str


class BackgroundTasks:
    """Brain 的 8 个后台协程：统一 start/stop。"""
    def __init__(self, brain: "Brain") -> None: ...
    def start(self) -> None: ...   # 创建 8 个 create_task
    async def stop(self) -> None: ...


class Brain:
    """栖的意识核心。心跳 + 记忆 + 情绪 + 内在生命 + 关系。"""

    def __init__(self, config: dict, llm: "LLMGateway"):
        self.config = config
        self.llm = llm
        self.emotion = EmotionState()
        self.perception = Perception(config, llm=llm)  # llm 供混合冲击旁路
        self.expression = Expression(config, llm)
        self.memory: MemoryManager | None = None
        self.inner_life: InnerLife | None = None
        self.relationship: RelationshipEngine | None = None
        self.first_times: FirstTimeMemory | None = None
        self.scars: ScarManager | None = None
        self.avatar = AvatarController()
        self.embodiment: EmbodimentServer | None = None
        self.tts = create_tts(config)
        self.alive = True
        self.user_online = True
        self.last_interaction = datetime.now()
        self._interacted_this_session = False  # F2：冷启动不测共同沉默
        self.heartbeat_count = 0
        self._pending_queue: deque[str] = deque()
        self._pending_speech: _PendingSpeech | None = None
        self._last_emotion_saved_at: datetime | None = None
        self._heartbeat_lock = asyncio.Lock()
        self._db: Database | None = None
        self._last_response: str | None = None
        self._background = BackgroundTasks(self)
        self._prev_valence = self.emotion.valence
        self._accumulated_suppressed = 0.0
        self.proactive = ProactiveGate(config)
        self.proactive_queue: asyncio.Queue[str] = asyncio.Queue()
        self.action: ActionLayer | None = None
        self._drift_signals: list[str] = []
        self._last_avatar_payload: dict | None = None
        self._traces: deque[dict] = deque(maxlen=20)  # format_why / 排障
        self._trace_day: str | None = None

    def attach_db(self, db: "Database") -> None:
        """仅设置 self._db。restore_state 不调用此方法，而是直接赋值。"""
        ...
    def attach_embodiment(self, server: "EmbodimentServer") -> None: ...

    async def start(self) -> None:
        """_background.start() + 心跳循环；间隔用 next_interval(emotion, config)。"""
        self._background.start()
        try:
            while self.alive:
                async with self._heartbeat_lock:
                    await self._heartbeat()
                    speech = self._take_pending_speech()
                if speech is not None:
                    await self._deliver_qi_message(
                        speech.text, speech.now, proactive=speech.proactive
                    )
                if not self.alive:
                    break
                interval = next_interval(self.emotion, self.config)
                await asyncio.sleep(interval)
        finally:
            await self._background.stop()

    async def _gather_prompt_context(self, pending, now) -> PromptContext:
        # extras：user_facts / body_hint（acquaintance+ 且样本≥5，整段含标题）/
        #         inner_life.prompt_extras / action.prompt_extras /
        #         first_time_hint / drift_hint
        # 返回 PromptContext（非 7 元组）
        ...

    async def _heartbeat(self) -> str | None:
        """
        一次心跳（真实顺序）：
        1. popleft pending（若有）；determine_mode(..., interacting=pending is not None)
        2. 若有 pending：
           relationship.on_user_message → first_times.check(
               silence_before=silence_before if _interacted_this_session else None)
           → memory.notice_facts(...)
           → impact *= impact_mult；await assess_impact_async → apply_event_impact
           → apply_security_hint；last_interaction = now；_interacted_this_session = True
           → save_message("user") → memory.on_user_message
           → _apply_anomaly_nudge(anomalies)
        3. step_emotion(..., relationship_stage=...)；可选 apply_season_effect；clamp_emotion
        4. _track_expression_threshold() → want_express
        5. 无 pending：inner_life.tick(after_first_time=False)；_broadcast_journal_entries()
           （有 pending 时本步不跑，避免同拍独白启动）
        6a. 有 pending：_gather_prompt_context → build_intention_card → expression.express
            → 写入 _pending_speech（锁外再 deliver）
            → 若 triggered_first：再 inner_life.tick(after_first_time=True)；推送 journal
        6b. 无 pending（idle）：
            · 默认 gws.enabled=true → 传感/世界/账本压力 → collect_contenders → arbitrate
              → _heartbeat_gws_idle（action:/proactive:/close_loop/report/curiosity/idle…）
            · legacy（gws 关）：先 action.tick（动手则跳过主动言语）；
              否则 pick_proactive_kind → express → _pending_speech(proactive=True)
            → record / persist gate；assist 跨轮确认超时清理等同拍旁路
        7. _sync_avatar；若 triggered_first：_notify_first_time()；
           _record_trace(...)；_maybe_save_emotion(force=有 pending)
        """
        ...

    async def _record_trace(...) -> None:
        # 内存 deque + body_memory last_heartbeat_trace / day_first_trace；不进 prompt
        ...

    async def format_why(self, limit: int = 8) -> str:
        """format_why：最近痕迹 + 落盘 last / day_first（排障/测试用）。"""
        ...

    async def receive_user_message(self, message: str) -> str | None:
        """入队（满则拒收最新并系统态）；锁内心跳；出锁后 sleep(0.5~1.5) 再 _deliver_qi_message。"""
        text = (message or "").strip()
        if not text:
            return None
        async with self._heartbeat_lock:
            if len(self._pending_queue) >= PENDING_QUEUE_MAX:
                # 拒收最新 + 系统态（见 P0 队列满告知）；不静默丢最早
                ...
                return None
            self._pending_queue.append(text)
            await self._heartbeat()
            speech = self._take_pending_speech()
        if speech is None:
            return None
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await self._deliver_qi_message(
            speech.text, speech.now, proactive=speech.proactive
        )
        return speech.text

    async def restore_state(self, db: "Database") -> None:
        """
        self._db = db（不调用 attach_db）；
        挂载 MemoryManager / InnerLife / RelationshipEngine / FirstTimeMemory / ScarManager；
        memory.restore()、relationship.restore()；
        ActionLayer(db, narrative=...) + restore_budget()；
        恢复 proactive_gate；load_emotion()；
        _maybe_mark_waking(db)（上次 user 非寒暄则 mark_waking）。
        """
        ...

    async def save_state(self, db: "Database") -> None:
        """save_emotion + proactive_gate + action_budget + relationship.persist。"""
        ...
```

```python
# qi/core/rhythm.py（Brain 使用，非旧 _next_interval）
# <!-- 回写(2026-07)：依据：qi/core/rhythm.py -->

def determine_mode(
    last_interaction: datetime,
    user_online: bool,
    now: datetime,
    *,
    interacting: bool = False,
) -> ConsciousnessMode:
    # interacting → AWAKE
    # silence < 5s → AWAKE
    # effectively_online = user_online and silence < 4h
    # 离线：夜间或沉默≥4h → DREAMING，否则 SOLITARY
    # 在线：silence < 30min → AMBIENT，否则 SOLITARY
    ...

def next_interval(emotion: EmotionState, config: dict | None = None) -> float:
    # 读 config["rhythm"][f"{mode}_interval"] 或 HEARTBEAT_INTERVALS
    # base *= 1.0 - 0.3 * arousal；base *= 1.0 + 0.5 * (1.0 - energy)；max(1.0, base)
    ...
```

```python
# qi/core/perception.py
# <!-- 回写(2026-07)：assess_impact 含 relationship_stage + modulate_impact；
#      依据：qi/core/perception.py -->
# <!-- 回写(2026-07-26)：Perception(config, llm=)；assess_impact_async 混合冲击
#      （触发才问 LLM，timeout 2s，失败回退关键词）。依据：perception.py -->

class Perception:
    def __init__(self, config: dict, llm: "LLMGateway | None" = None):
        self.config = config
        self.llm = llm
        self.relationship_stage: str = "stranger"
        self.user_present: bool = True

    def set_user_presence(self, online: bool) -> None: ...

    def detect_silence(self, last_interaction: datetime, now: datetime) -> float:
        return (now - last_interaction).total_seconds()

    def assess_impact(
        self,
        message: str,
        emotion: "EmotionState",
        relationship_stage: str | None = None,
    ) -> float:
        """关键词粗判 base → modulate_impact(base, emotion, stage) → clamp ±1。"""
        ...

    async def assess_impact_async(
        self,
        message: str,
        emotion: "EmotionState",
        relationship_stage: str | None = None,
    ) -> float:
        """关键词为主；_needs_llm_impact 才旁路 LLM（purpose=fact, ≤2s）；失败回退。"""
        ...

    def apply_security_hint(
        self, emotion: "EmotionState", impact: float
    ) -> "EmotionState":
        """负面冲击安全感微降；正面微升。"""
        ...
```

```python
# qi/core/expression.py
# <!-- 回写(2026-07-25)：express 内无 sleep；停顿在 brain.receive_user_message 出锁后；
#      依据：qi/core/expression.py + brain.receive_user_message -->

class Expression:
    """栖开口的地方。想了想，再说话（停顿由 Brain 在心跳锁外完成）。"""

    def __init__(self, config: dict, llm: "LLMGateway"):
        self.config = config
        self.llm = llm
        self.prompt_builder = PromptBuilder()

    async def express(
        self,
        user_message: str,
        emotion: "EmotionState",
        now: "datetime",
        recent_messages: list[dict] | None = None,
        memories: list[dict] | None = None,
        inner_extras: dict[str, str] | None = None,
        relationship_stage: str = "stranger",
        shared_culture: str = "",
        relationship_hint: str = "",
        scar_hint: str = "",
        season: str = "spring",
        proactive_kind: str | None = None,
    ) -> str:
        # 无 asyncio.sleep —— 生成在锁内；用户回复的「想了想」在 receive_user_message 出锁后
        messages = self.prompt_builder.build_conversation_prompt(...)
        return await self.llm.call(purpose="conversation", messages=messages)
```

</details>

```python
# qi/cli.py —— 具身后端（Brain ∥ WebSocket）
# <!-- 回写(2026-08-11)：删除 run_terminal；仅 run_desktop / main_desktop / main；依据：qi/cli.py -->

async def run_desktop() -> None:
    """具身模式：Brain + WebSocket（console script: qi）。"""
    config = load_config()
    emb = config.get("embodiment") or {}
    ws_host, ws_port = resolve_bind(emb.get("host"), emb.get("port"))

    gateway = LLMGateway(config)
    db = Database(config["database"]["path"])
    await db.initialize()

    brain = Brain(config, llm=gateway)
    await brain.restore_state(db)

    server = EmbodimentServer(brain, host=ws_host, port=ws_port)
    brain.attach_embodiment(server)

    brain_task = asyncio.create_task(brain.start())
    server_task = asyncio.create_task(server.start())
    try:
        await asyncio.gather(brain_task, server_task)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        brain.request_shutdown()
        for task in (brain_task, server_task):
            if not task.done():
                task.cancel()
        ...
        await server.stop()
        await brain.save_state(db)
        await db.close()

def main_desktop() -> None:
    logging.basicConfig(level=logging.INFO, ...)
    asyncio.run(run_desktop())

def main() -> None:
    """兼容入口；仍接受已废弃的 --desktop。"""
    ...
    main_desktop()

# 入口：
# - qi / python -m qi / main() / main_desktop() → run_desktop()
# 对话 UI：Tauri 桌面壳（ws://127.0.0.1:9527）；开发期可自动拉起本进程
# 心跳痕迹：brain.format_why() 仍可供排障/测试，无终端 /why 命令壳
```

### Step 5：持久化

- 每次心跳后保存情绪状态到 SQLite
- 启动时从 SQLite 恢复上次的情绪状态
- 验收：关掉程序，再打开，情绪状态不是初始值（前端氛围或库内最新快照）

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/storage/database.py

import aiosqlite
from datetime import datetime

class Database:
    """SQLite 持久化。L1 核心两表 emotion_states / messages；同文件还有 L2+ 表。"""

    def __init__(self, db_path: str):
        """db_path: 来自 config["database"]["path"]，如 "data/qi.db" """
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        """
        打开连接 + 执行 CREATE TABLE IF NOT EXISTS（见 Step 1 的 SQL）。
        在 qi/cli.py 启动时调用一次。
        """
        ...

    async def save_emotion(self, emotion: "EmotionState"):
        """
        保存当前情绪快照到 emotion_states 表。
        INSERT INTO emotion_states (timestamp, energy, valence, arousal, security, curiosity, attachment, mode)
        VALUES (datetime.now().isoformat(timespec="seconds"), emotion.energy, ...)
        保存时机：每次心跳结束后调用。
        """
        ...

    async def load_emotion(self) -> "EmotionState | None":
        """
        从 emotion_states 表加载最新一条记录，构造 EmotionState 返回。
        SELECT * FROM emotion_states ORDER BY timestamp DESC LIMIT 1
        如果没有记录返回 None（使用默认初始值）。
        调用时机：程序启动时恢复状态。
        """
        ...

    async def save_message(self, role: str, content: str,
                           emotion_context: str | None = None, tone: str | None = None):
        """
        保存一条消息到 messages 表。
        role: "user" 或 "qi"
        emotion_context: 栖说话时的情绪 JSON（可选）
        保存时机：每次收到用户消息后 save_message("user", ...)，
                  每次栖回复后 save_message("qi", ..., emotion_context=emotion.model_dump_json())
        """
        ...

    async def load_recent_messages(self, limit: int = 20) -> list[dict]:
        """
        加载最近 N 条消息，用于工作记忆 / prompt 上下文。
        SELECT role, content, timestamp FROM messages
        ORDER BY timestamp DESC, id DESC LIMIT ?
        再 reverse() 成时间正序。
        返回: [{"role": "user"|"qi", "content": "...", "timestamp": "..."}]
        """
        ...

    async def close(self):
        """关闭数据库连接。程序退出时调用。"""
        ...
```

**保存时机总结：**
- `save_emotion`：`_heartbeat` 末尾经 `_maybe_save_emotion`（空心跳默认 ≥30s 节流；有 pending 时 force 立即写）
- `save_message("user", ...)`：心跳内处理 pending 时（有 db）
- `save_message("qi", ...)`：`_deliver_qi_message` 内（含主动开口；在锁外推送时执行）
- `load_emotion`：程序启动 `brain.restore_state(db)`
- `load_recent_messages`：无 MemoryManager 时由 `_gather_prompt_context` 拉取；有记忆层则用工作记忆

<!-- 回写(2026-07)：保存时机对齐 brain._heartbeat / _deliver_qi_message，依据：qi/core/brain.py -->
<!-- 回写(2026-07-25)：情绪落盘节流 _maybe_save_emotion；依据：brain.py -->

</details>

## 验收标准

### 可测试的

- [ ] `qi`（或 `python -m qi`）正常启动 WebSocket（`ws://127.0.0.1:9527`）
- [ ] 桌面壳能连上、收发消息、生成回复
- [ ] 关掉再打开，情绪从 DB 恢复（不是初始值）
- [ ] 用户夸栖 → valence 上升；用户冷淡 → security 下降
- [ ] 无交互时，情绪缓慢回归基线

### 需要感受的

- [ ] 它说话不像客服
- [ ] 它的语气跟情绪状态有关联（开心时话多一点，低落时安静一点）
- [ ] 它让你觉得"有一个什么东西在那里"，而不是"一个程序在响应"

## 给下一层的接口

L2（记忆）需要：
- `brain.py` 中有一个 `receive_user_message()` 入口
- `expression.py` 的 prompt 组装有扩展点（能注入记忆上下文）
- `database.py` 能建新表

## 人格契约检查点

- [ ] 不用"您"（检查 prompt）
- [ ] 不说"有什么可以帮您"（检查 prompt）
- [ ] 回复不超过 3 句（检查 prompt 中的长度约束）
- [ ] 不秒回（`receive_user_message` 出锁后 `sleep(0.5~1.5)`；`expression.express` 内无 sleep；主动开口出锁后直接推送）
  <!-- 回写(2026-07-25)：停顿位置对齐 brain.receive_user_message，依据：brain.py / expression.py -->
- [ ] 情绪用自然语言描述，不报数值（检查 prompt_builder）


