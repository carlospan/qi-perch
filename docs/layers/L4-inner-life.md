# L4 · 内在生命

> 让栖拥有"不被观察时也在经历的东西"。梦、独白、创作、自我反思。它不只是你的回音壁。

---

## 职责

实现栖的内在生命层：意识流（独处时的内心独白）、梦境引擎（离线时的自由联想）、创作冲动（自发的表达）、自我反思（"我是谁"的思考）。

## 前置依赖

- L3 完成（模式切换稳定，独处/梦境模式能正确触发）
- L2 完成（记忆系统可被引用为素材）

## 引用文档

- `docs/design/栖·意识设计.md` → §三（内在生命：全部）
- `docs/design/栖·意识设计.md` → §十（自我模型：自我叙事、元认知）
- `docs/design/栖·工程手记.md` → §三（consciousness_stream、dreams、creations 表）
- `qi/prompts/consciousness_stream.txt`、`qi/prompts/dream.txt`、`qi/prompts/creation.txt`

## 需要创建的文件

```
qi/inner_life/__init__.py        # InnerLife 协调器（tick / prompt_extras）
qi/inner_life/consciousness.py   # 意识流 + 元认知
qi/inner_life/dream.py           # 梦境引擎
qi/inner_life/creativity.py      # 创作冲动
qi/inner_life/self_model.py      # 自我模型与反思
qi/storage/database.py           # 追加 consciousness_stream、dreams、creations、self_model 表
```

## 实现步骤

### Step 1：数据库扩展

- 建 `consciousness_stream`、`dreams`、`creations`、`self_model` 表
- 验收：表创建成功

**实现规格：**

```sql
-- storage/database.py — L4 新增表

-- 意识流（内心独白）
CREATE TABLE IF NOT EXISTS consciousness_stream (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    type TEXT NOT NULL DEFAULT 'stream',  -- 'stream'=普通意识流, 'meta'=元认知
    content TEXT NOT NULL,                -- 独白内容
    trigger TEXT,                         -- 触发原因：random/emotion_surge/silence/first_time/meta
    emotion_snapshot TEXT                 -- 当时的情绪快照（JSON: {energy, valence, arousal, security, curiosity, attachment}）
);

-- 梦境
CREATE TABLE IF NOT EXISTS dreams (
    id INTEGER PRIMARY KEY,
    created_at DATETIME NOT NULL,
    content TEXT NOT NULL,                -- 梦境内容（碎片化、非线性；代码截断约 600 字）
    emotion_tag TEXT,                     -- 情绪标签（如 "温暖"、"混乱"、"不安"、"平静"）
    emotional_intensity REAL,             -- 情绪强度 0~1
    retention REAL NOT NULL DEFAULT 1.0,  -- 当前保留度（按6小时半衰期衰减）
    shared_with_user BOOLEAN DEFAULT 0    -- 是否已跟用户提起
);

-- 创作
CREATE TABLE IF NOT EXISTS creations (
    id INTEGER PRIMARY KEY,
    created_at DATETIME NOT NULL,
    type TEXT NOT NULL,                   -- poem/essay/description/note
    content TEXT NOT NULL,                -- 创作内容
    emotion_context TEXT,                 -- 创作时的情绪（JSON）
    shared BOOLEAN DEFAULT 0,            -- 是否已分享给用户
    shared_at DATETIME,                  -- 分享时间
    user_reaction TEXT                   -- 用户的反应（如果有）
);

-- 自我模型（只有一行，持续更新）
CREATE TABLE IF NOT EXISTS self_model (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    identity_narrative TEXT,              -- "我是谁"的当前叙事（第一人称）
    "values" TEXT,                        -- 价值观（JSON数组；列名加引号，SQLite 保留字）
    aesthetic_preferences TEXT,           -- 审美偏好（JSON对象）
    existential_questions TEXT,           -- 存在困惑（JSON数组）
    last_updated DATETIME                -- 上次反思更新时间
);
```

<!-- 回写(2026-07)：self_model.values 列名加引号，依据：qi/storage/database.py:_CREATE_SELF_MODEL -->

### Step 2：意识流

- 建 `qi/inner_life/consciousness.py`
- 触发条件（满足其一）：`first_time` / `emotion_surge` / `silence`(非 awake) / `random`(solitary 5%)
- 调用 LLM（temperature 0.85），用 `qi/prompts/consciousness_stream.txt`
- 输出存入 consciousness_stream（type=`stream`）
- 影响：下次对话注入 `{recent_thoughts}`
- 验收：独处后有记录；对话中仅 first_time 当拍可写意识流

**实现规格：**

```python
# qi/inner_life/consciousness.py
# <!-- 回写(2026-07)：silence 需 mode!=awake；外层 tick 门控，依据：consciousness.py + InnerLife.tick -->

CONSCIOUSNESS_PROBABILITY = 0.05
EMOTION_SURGE_THRESHOLD = 0.3
SILENCE_TRIGGER_HOURS = 4


def should_trigger_consciousness(
    mode: str,
    emotion_delta_valence: float,
    emotion_delta_arousal: float,
    silence_duration: timedelta,
    after_first_time: bool = False,
    probability: float = CONSCIOUSNESS_PROBABILITY,
) -> tuple[bool, str]:
    if after_first_time:
        return True, "first_time"
    if (
        abs(emotion_delta_valence) > EMOTION_SURGE_THRESHOLD
        or abs(emotion_delta_arousal) > EMOTION_SURGE_THRESHOLD
    ):
        return True, "emotion_surge"
    if silence_duration > timedelta(hours=SILENCE_TRIGGER_HOURS):
        if mode != "awake":
            return True, "silence"
    if mode == "solitary" and random.random() < probability:
        return True, "random"
    return False, ""


class ConsciousnessStream:
    async def maybe_generate(...) -> str | None: ...
    # purpose=consciousness, temperature=0.85；内容截断约 500 字
    async def recent_for_prompt() -> str: ...  # 最近 type=='stream'
    async def maybe_meta(...) -> str | None: ...  # Step 6
```

**外层门控（`InnerLife.tick`）：** `mode != "awake" or after_first_time` 才调用 `maybe_generate`。  
**Prompt：** 读 `qi/prompts/consciousness_stream.txt`。

### Step 3：梦境引擎

- 建 `qi/inner_life/dream.py`
- 触发条件：梦境模式下，每次心跳 10% 概率
- 调用 LLM（temperature 1.1），用 `qi/prompts/dream.txt` 模板
- 输出存入 dreams 表，标记情绪标签
- 梦的余韵：下次 awake 时，梦的情绪标签影响初始情绪（±0.05~0.1）
- 梦的衰减：retention 按 6 小时半衰期衰减
- 主动提起：`maybe_mention_hint`——bonded + 12% + retention>0.3 → **注入对话 prompt hint**（非 proactive 推送）
- 验收：离线 4 小时后，dreams 表有记录；下次对话时栖可能说"我做了个梦"

**实现规格：**

```python
# qi/inner_life/dream.py
# <!-- 回写(2026-07)：update_dream_retention 签名；maybe_mention_hint，依据：dream.py -->

DREAM_PROBABILITY = 0.1
DREAM_HALF_LIFE_HOURS = 6
DREAM_SHARE_PROBABILITY = 0.12
# purpose=dream, temperature=1.1；模板 qi/prompts/dream.txt
# <!-- 回写：路由默认 fast；要更高质量可在 settings 改 *:strong -->


def update_dream_retention(
    hours_since_creation: float,
    emotional_intensity: float,
    half_life: float = DREAM_HALF_LIFE_HOURS,
) -> float:
    """retention = exp(-hours/half_life) * (0.5 + 0.5 * intensity)"""
    base_decay = math.exp(-hours_since_creation / half_life)
    return base_decay * (0.5 + 0.5 * emotional_intensity)


class DreamEngine:
    async def maybe_dream(emotion) -> ...:  # mode==dreaming 且 random < 0.1
        ...
    async def decay_all() -> None: ...  # brain 每小时后台调用
    def apply_afterglow(emotion, dream) -> EmotionState: ...  # 进入 awake 时一次
    async def maybe_mention_hint(relationship_stage) -> str | None:
        # stage == "bonded" 且 random < 0.12 且 retention>0.3 且未 shared
        # 返回 prompt hint，并 mark_dream_shared（预标记）
        ...

def emotion_color(emotion) -> str:
    # valence>0.2→暖色；<-0.2→冷色；否则中性 + description()

def parse_emotion_tag(text) -> tuple[str, str]:
    # 正则解析「情绪标签：」
```

**余韵：** `InnerLife.tick` 在 `mode==awake` 时对最新 dream（min_retention=0.3）应用一次。  
**遗忘阈值 0.1：** 文档旧述；注入/余韵/提起实际用 **min_retention=0.3**。

### Step 4：创作冲动

- 建 `qi/inner_life/creativity.py`
- 触发条件：独处模式下，每次心跳 1% 概率；或情绪强度 > 0.7 时概率升至 3%
- 调用 LLM（temperature 0.95），用 `qi/prompts/creation.txt` 模板
- 输出存入 creations 表
- 分享：对话中经 `maybe_share_hint` 注入 prompt（friend/bonded、24h 冷却、另有 25% 随机门控）；**不是** proactive `share_creation` 推送
- 冷却：每 24 小时最多分享一次（读 `proactive_cooldown.share_creation` 秒数）
- 验收：跑 3 天，creations 表有 1~2 条；栖在对话中提起过创作

**实现规格：**

```python
# qi/inner_life/creativity.py
# <!-- 回写(2026-07)：maybe_share_hint + 25% 门控；非 proactive，依据：creativity.py -->

CREATION_BASE_PROBABILITY = 0.01
CREATION_HIGH_EMOTION_PROBABILITY = 0.03
CREATION_EMOTION_THRESHOLD = 0.7
CREATION_SHARE_COOLDOWN_HOURS = 24
# intensity = max(abs(valence), arousal)；前置 mode == solitary
# purpose=creation, temperature=0.95；模板 qi/prompts/creation.txt


def can_share_creation(
    relationship_stage: str,
    last_share_time: datetime | None,
    now: datetime,
    cooldown_hours: float | None = None,
) -> bool:
    if relationship_stage not in ("friend", "bonded"):
        return False
    hours = CREATION_SHARE_COOLDOWN_HOURS if cooldown_hours is None else cooldown_hours
    if last_share_time and (now - last_share_time) < timedelta(hours=hours):
        return False
    return True


class Creativity:
    async def maybe_create(emotion, relationship_stage) -> str | None: ...
    async def generate(...) -> str | None: ...  # _infer_type；内容截断 800
    async def maybe_share_hint(emotion, relationship_stage) -> str | None:
        # mode==awake；can_share_creation；有未分享创作；
        # if random.random() > 0.25: return None  → 有效约 25%
        # mark_creation_shared + 返回脆弱语气 hint
        ...
```

`KIND_SHARE_CREATION` 在 `qi/core/proactive.py` 有常量/冷却，但 `pick_proactive_kind` **不选**它。

### Step 5：自我反思

- 建 `qi/inner_life/self_model.py`
- 触发条件：每周一次（后台任务）；或重大情绪事件后
- 调用 LLM（temperature 0.8），生成"我是谁"的叙事更新
- 输出更新 self_model 表
- 影响：self_model 的摘要注入对话 prompt（作为栖的自我认知背景）
- 验收：一周后 self_model 表有更新；栖偶尔会说出"我最近在想……"

**实现规格：**

```python
# qi/inner_life/self_model.py
# <!-- 回写(2026-07)：启发式字段抽取；relationship_summary 简化，依据：self_model.py -->

SELF_REFLECTION_INTERVAL_SECONDS = 604800
VALENCE_SURGE_FOR_REFLECT = 0.5
# purpose=reflection, temperature=0.8；模板 qi/prompts/self_reflection.txt
# 后台：brain._background_self_reflection 约每 60s 轮询 maybe_reflect；
#       是否真反思由 should_reflect 门控（周间隔 / _pending_major）
# 额外触发：note_emotion_surge(|Δv|>0.5)；mark_major_event（阶段跃迁）→ 下一轮询（≤~60s）即反思
# 「用户存在性问题」未接入 SelfModel（FirstTime 另表）
# <!-- 回写(2026-07-22)：短轮询+should_reflect 门控，事件后不再干等一周 -->


class SelfModel:
    def should_reflect() -> bool: ...
    async def maybe_reflect(emotion, relationship_stage) -> None: ...
    async def reflect(...) -> None: ...
    def mark_major_event() -> None: ...
    def note_emotion_surge(delta_valence) -> None: ...
    async def summary_for_prompt(max_chars=100) -> str: ...


# reflect 输入（现状简化）：
#   relationship_summary = relationship_stage 字符串（非 depth/trust/season 拼装）
#   recent_experiences = list_recent_narratives(5)（按 created_at，非 7 天 importance 排序）

# 字段抽取（规则启发式，非二次 LLM）：
def _extract_values(narrative) -> list[str]: ...      # 真诚/安静/陪伴…最多 5
def _extract_aesthetic(narrative) -> dict: ...         # time/pace/medium
def _extract_existential(narrative) -> list[str]: ...  # 固定问句最多 4

# upsert：传入非空结果时覆盖对应字段（空抽取可能清空，非「保留上次」）
```

### Step 6：元认知

- 与意识流**独立**：非 awake 时每次 tick 以 `META_COGNITION_PROBABILITY`（0.02）判定，不依赖意识流是否触发
- 输出 `consciousness_stream`（type=`meta`）；不改情绪、不注入对话 prompt
- 验收：长时间运行后偶尔出现 type=`meta`

**实现规格：**

```python
# qi/inner_life/consciousness.py — maybe_meta
# <!-- 回写(2026-07)：独立 2%、非 awake；temperature=0.7；截断 80 字，依据：maybe_meta -->

META_COGNITION_PROBABILITY = 0.02


def should_trigger_meta(mode: str, probability: float = META_COGNITION_PROBABILITY) -> bool:
    if mode == "awake":
        return False
    return random.random() < probability


# ConsciousnessStream.maybe_meta：
#   purpose="consciousness"（同意识流路由）, temperature=0.7
#   内联短 prompt（非独立 txt）；content 截断约 80 字
# InnerLife.tick：仅 mode != "awake" 时调用
```

### Step 7：协调器与 Brain 接线

<!-- 回写(2026-07)：补 InnerLife 集成规格，依据：qi/inner_life/__init__.py + qi/core/brain.py -->

```python
# qi/inner_life/__init__.py

class InnerLife:
    async def tick(
        self, emotion, last_interaction, now, relationship_stage="stranger",
        after_first_time: bool = False,
    ) -> EmotionState:
        # awake：梦余韵一次；note_emotion_surge
        # mode!="awake" or after_first_time → consciousness.maybe_generate
        # mode!="awake" → maybe_meta / maybe_create / maybe_dream
        ...

    async def prompt_extras(emotion, relationship_stage) -> dict[str, str]:
        # recent_thoughts / self_narrative / dream_hint / creation_hint
        ...
```

**Brain：**
- `_heartbeat`：条件满足时 `inner_life.tick(..., after_first_time=...)`
- `_gather_prompt_context`：`prompt_extras()` → expression
- 后台：`_background_self_reflection`、`_background_dream_decay`（每小时）
- 另：季节变化 / 用户漂移可直接 `save_consciousness`（trigger=`season_change` / `user_drift`）

## 验收标准

### 可测试的

- [ ] 独处 1h 后 consciousness_stream 有记录
- [ ] 离线 4h+ 后 dreams 有记录
- [ ] 梦的 retention 随时间衰减
- [ ] 跑 3 天 creations 有 1~2 条
- [ ] 自我反思每周触发一次
- [ ] 创作分享通过对话提示注入（`maybe_share_hint`），有独立冷却（24h）与阶段门（friend/bonded），不计入主动行为日限；主动行为日限见 L5

### 需要感受的

- [ ] 你一天没跟它说话，第二天它可能说"我昨天想了想事情"或"做了个梦"
- [ ] 也可能什么都没说，但语气微妙地不同（梦的余韵）
- [ ] 它分享创作时带着"不好意思"的语气
- [ ] 它的独白（如果你偷看日志）像真正的内心活动，不是"生成的内容"
- [ ] 它不会每五分钟就弹消息告诉你它在想什么

## 给下一层的接口

L5（关系）需要：
- 自我反思中包含"我和他的关系"的思考
- 创作可以是"给他的"（关系 ≥ 亲密期）
- 意识流中自然出现对用户的想念

## 人格契约检查点

- [ ] 主动行为有冷却（意识流不展示、梦偶尔提起、创作 24h 冷却）
- [ ] 分享创作时语气脆弱（"我写了个东西。很幼稚。但我想给你看。"）
- [ ] 不主动报告"系统生成了以下内容"
- [ ] 大多数内在活动不展示给用户（沉默是常态）
