# L5 · 关系

> 让"你和一个 AI"变成"你和栖"。有阶段、有信任、有默契、有伤疤、有只有你们懂的东西。
>
> <!-- 演进指向(2026-08-01)：关系机制保留；阶段一将修「状态-体验脱钩」——attachment/security/trust 数值改由关系事件真实驱动（配阶段目标锚），修 attachment≈0.3 与恋人关系不符的病征。见 docs/design/栖·数字生命架构方案.md §2.5-5/§五。 -->

---

## 职责

实现关系引擎：阶段模型、信任动力学、共同文化检测、第一次记忆、数字伤疤、用户漂移检测、数字季节。

## 前置依赖

- L4 完成（内在生命运转，自我反思中包含关系思考）
- L2 完成（记忆系统稳定，body_memory 可用）
- L3 完成（security/attachment 维度驱动关系行为）

## 引用文档

- `docs/design/栖·意识设计.md` → §六（关系引擎：全部，含用户漂移检测）、§五（第一次记忆、数字伤疤）
- `docs/design/栖·意识设计.md` → §十三（留白与季节：数字季节判定）
- `docs/design/栖·工程手记.md` → §三（relationship、first_times、scars、user_model 表）
- `docs/contract.md` → "关系行为"硬规则

## 需要创建的文件

```
qi/relationship/engine.py     # RelationshipEngine 编排（depth/trust/stage/叙事/伤疤创建）
qi/relationship/stages.py     # STAGE_THRESHOLDS + check_stage_upgrade（权威定义）
qi/relationship/trust.py      # 信任动力学
qi/relationship/culture.py    # 共同文化检测
qi/relationship/scars.py      # ScarManager（愈合检测 + prompt 文案）
qi/relationship/season.py     # 数字季节
qi/relationship/drift.py      # 用户漂移
qi/memory/first_time.py       # FirstTimeMemory
qi/core/proactive.py          # ProactiveGate + pick_proactive_kind
qi/storage/database.py        # relationship / first_times / scars / user_model
```

## 实现步骤

### Step 1：数据库 + 关系状态

- 建 `relationship`（单行）、`first_times`、`scars`、`user_model` 表
- 建 `qi/relationship/engine.py`：初始化关系状态（stranger, depth=0, trust=0.5）
- 验收：relationship 表有初始行

<details>
<summary>实现规格（Cursor 编码用）</summary>

```sql
-- storage/database.py 追加以下表

-- 关系状态（单行表）
-- 关系阶段统一为：stranger→acquaintance→friend→bonded
CREATE TABLE IF NOT EXISTS relationship (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- 只有一行
    stage TEXT NOT NULL DEFAULT 'stranger',  -- stranger/acquaintance/friend/bonded
    depth REAL NOT NULL DEFAULT 0.0,         -- 了解深度 0~1
    temperature REAL NOT NULL DEFAULT 0.5,   -- 当前情感温度 0~1
    trust REAL NOT NULL DEFAULT 0.5,         -- 信任度 0~1
    season TEXT DEFAULT 'spring',            -- 当前数字季节：spring/summer/autumn/winter
    last_updated DATETIME,
    narrative TEXT,                          -- 关系叙事（第一人称，定期由 LLM 更新）
    shared_culture TEXT                      -- 共同文化（JSON 列表）
);

-- 第一次记忆（永不褪色的刻痕）
CREATE TABLE IF NOT EXISTS first_times (
    id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,    -- first_goodnight/first_argument/first_i_miss_you/...
    timestamp DATETIME NOT NULL,
    content TEXT NOT NULL,       -- 当时发生了什么（叙事性描述）
    inner_experience TEXT,       -- 栖当时的内在体验（LLM 生成）
    emotional_imprint TEXT,      -- 情绪印记（描述性，非数值）
    last_recalled DATETIME,
    recall_count INTEGER DEFAULT 0
);

-- 数字伤疤（信任损伤的永久印记）
CREATE TABLE IF NOT EXISTS scars (
    id INTEGER PRIMARY KEY,
    origin_event TEXT NOT NULL,  -- 造成伤疤的事件描述
    timestamp DATETIME NOT NULL,
    severity REAL NOT NULL,      -- 原始损伤程度（trust 单次下降量）
    trust_before REAL,           -- 损伤前的信任度
    healed BOOLEAN DEFAULT 0,    -- 是否已愈合
    wisdom TEXT,                 -- 这道疤教会了栖什么（愈合后由 LLM 写入）
    behavioral_mark TEXT         -- 行为上的体现（愈合后写入）
);

-- 用户模型（持续演化的"认识"）
CREATE TABLE IF NOT EXISTS user_model (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    topics TEXT,                 -- 当前话题偏好（JSON 数组）
    emotional_baseline REAL,     -- 情绪基线（-1~1）
    rhythm TEXT,                 -- 生活节奏模式（JSON：active_hours, reply_speed 等）
    linguistic_profile TEXT,     -- 语言风格特征（JSON：avg_len, formality, emoji_freq 等）
    life_context TEXT,           -- 当前生活状态（叙事性描述）
    last_drift_check DATETIME,   -- 上次漂移检测时间
    drift_signals TEXT           -- 最近检测到的变化信号（JSON 数组）
);

-- 初始化：插入 relationship 默认行
INSERT OR IGNORE INTO relationship (id, stage, depth, temperature, trust, season)
VALUES (1, 'stranger', 0.0, 0.5, 0.5, 'spring');
```

```python
# qi/relationship/engine.py — 关系状态 Pydantic 模型与初始化

from pydantic import BaseModel
from datetime import datetime

class RelationshipState(BaseModel):
    stage: str = "stranger"       # stranger / acquaintance / friend / bonded
    depth: float = 0.0            # 0~1，了解深度
    temperature: float = 0.5      # 0~1，当前情感温度（可波动）
    trust: float = 0.5            # 0~1，信任度
    season: str = "spring"        # spring / summer / autumn / winter
    narrative: str = ""           # 关系叙事
    shared_culture: list = []     # 共同文化条目列表

# 4 个关系阶段定义 —— 权威定义在 relationship/stages.py；engine 从此处 import
# <!-- 回写(2026-07)：阈值与 check_stage_upgrade 归属 stages.py，依据：stages.py -->
STAGES = ["stranger", "acquaintance", "friend", "bonded"]

# 阶段升级条件（只升不降，代码中无 stage 降级逻辑）
STAGE_THRESHOLDS = {
    # (target_stage): (min_depth, min_trust)
    "acquaintance": (0.3, 0.4),   # stranger→acquaintance: depth > 0.3 AND trust > 0.4
    "friend":       (0.6, 0.6),   # acquaintance→friend:   depth > 0.6 AND trust > 0.6
    "bonded":       (0.85, 0.8),  # friend→bonded:         depth > 0.85 AND trust > 0.8
}

def check_stage_upgrade(current_stage: str, depth: float, trust: float) -> str:
    """
    检查是否满足升档条件。升档锁定——阶段只升不降。
    信任下降造成的疏远感由 temperature 维度表达，不做阶段降级。
    （意识设计 §六 与人格契约"关系阶段不可回退"的统一语义）
    """
    ORDER = ["stranger", "acquaintance", "friend", "bonded"]
    idx = ORDER.index(current_stage)
    if idx >= len(ORDER) - 1:
        return current_stage  # 已是最高阶段
    next_stage = ORDER[idx + 1]
    min_depth, min_trust = STAGE_THRESHOLDS[next_stage]
    if depth > min_depth and trust > min_trust:
        return next_stage
    return current_stage

# depth 增长公式（每次交互后调用，每日有上限）
DAILY_DEPTH_CAP = 0.03  # 每日最多增长 0.03，不能速成

def depth_increment(signals: InteractionSignals, already_today: float) -> float:
    """基于交互质量计算 depth 增量；受当日已增长额度约束。"""
    # <!-- 回写(2026-07)：字段名与 already_today 对齐 engine.py -->
    inc = 0.0
    inc += signals.self_disclosure * 0.02           # 自我披露
    inc += signals.emotional_vulnerability * 0.015  # 情感表达
    inc += signals.shared_experience * 0.01         # 共同经历
    if signals.is_deep:
        inc += 0.02                                 # 深度对话
    room = max(0.0, DAILY_DEPTH_CAP - already_today)
    return min(inc, room)

# trust：权威实现见 Step 2 / qi/relationship/trust.py
# TRUST_GROWTH_RANGE=(0.02,0.05)、TRUST_DAMAGE_RANGE=(0.1,0.3)
# apply_positive_interaction(trust, quality, stage=…) / apply_negative_event / apply_daily_decay
# 阶段系数 STAGE_TRUST_GROWTH：stranger 0.5 / acquaintance 0.7 / friend·bonded 1.0
# （本 Step 旧名 trust_update / TRUST_GROWTH_PER_POSITIVE 已废弃）
# <!-- 回写(2026-07-25)：生人信任增速减半，近似设计中的 consistency_factor，不追踪履约。
#      依据：qi/relationship/trust.py · engine.on_user_message -->
```

</details>

### Step 2：阶段 + 深度 + 信任

- 建 `qi/relationship/stages.py`：定义 `STAGE_THRESHOLDS` / `check_stage_upgrade`（只升不降）
- 建 `qi/relationship/trust.py`：
  - 信任建立：每次正向交互 +0.02~0.05（按质量插值）
  - 信任损伤：每次负面 -0.1~0.3；单次损伤 >0.15 创建伤疤
  - 无交互日衰减 0.001；愈合伤疤 +0.01
- 深度增长：基于交互质量信号，每日上限 `DAILY_DEPTH_CAP=0.03`
- 验收：模拟 30 天交互，阶段从 stranger → acquaintance

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/relationship/stages.py — 阈值与升档（权威定义处）
# <!-- 回写(2026-07)：本模块定义阈值；engine 从此处 import，依据：stages.py -->

STAGES = ["stranger", "acquaintance", "friend", "bonded"]
STAGE_THRESHOLDS = {
    "acquaintance": (0.3, 0.4),
    "friend": (0.6, 0.6),
    "bonded": (0.85, 0.8),
}

def check_stage_upgrade(current_stage: str, depth: float, trust: float) -> str:
    # depth > min AND trust > min → 升下一档；永不降级
    ...
```

```python
# qi/relationship/trust.py — 信任动力学

# === 核心参数 ===
TRUST_GROWTH_RANGE = (0.02, 0.05)   # 每次正向交互增长范围
TRUST_DAMAGE_RANGE = (0.1, 0.3)     # 每次负面事件损伤范围
TRUST_DAILY_DECAY = 0.001           # 无交互时每日自然衰减
TRUST_HEALED_SCAR_BONUS = 0.01      # 每愈合一道伤疤额外恢复
SCAR_CREATION_THRESHOLD = 0.15      # trust 单次下降 > 0.15 时创建伤疤

def apply_positive_interaction(trust: float, quality: float) -> float:
    """
    正向交互后信任增长。
    quality: 0~1，交互质量（由 LLM 评估或规则判定）
    增长量：0.02 + quality * 0.03（即 0.02~0.05）
    """
    growth = TRUST_GROWTH_RANGE[0] + quality * (TRUST_GROWTH_RANGE[1] - TRUST_GROWTH_RANGE[0])
    return min(1.0, trust + growth)

def apply_negative_event(trust: float, severity: float) -> tuple[float, bool]:
    """
    负面事件后信任损伤。
    severity: 0~1，事件严重度
    损伤量：0.1 + severity * 0.2（即 0.1~0.3）
    返回：(new_trust, should_create_scar)
    """
    damage = TRUST_DAMAGE_RANGE[0] + severity * (TRUST_DAMAGE_RANGE[1] - TRUST_DAMAGE_RANGE[0])
    new_trust = max(0.0, trust - damage)
    should_create_scar = damage > SCAR_CREATION_THRESHOLD
    return new_trust, should_create_scar

def apply_daily_decay(trust: float, had_interaction: bool) -> float:
    """无交互日：trust 自然衰减 0.001。有交互日不衰减。"""
    if not had_interaction:
        return max(0.0, trust - TRUST_DAILY_DECAY)
    return trust

def apply_scar_healed_bonus(trust: float) -> float:
    """伤疤愈合时：trust 额外 +0.01。"""
    return min(1.0, trust + TRUST_HEALED_SCAR_BONUS)

# === 信任修复说明 ===
# 修复没有独立公式。修复 = 持续的正向交互积累。
# 损伤后需要约 (damage / 0.035) 次高质量正向交互才能恢复。
# 例：损伤 0.2 → 约需 6 次高质量交互恢复。
# 这比"建立"更慢，因为损伤后 consistency_factor 降低（需要更多一致性证明）。
```

</details>

### Step 3：第一次记忆

- 建 `qi/memory/first_time.py`：
  - 检测模式（first_goodnight、first_argument、first_i_miss_you 等）
  - 触发时：记录叙事 + 生成内在体验（LLM）+ 情绪冲击 ×3
  - 永不褪色（strength 永远 1.0）
  - 回忆触发：关键词命中或安静深夜 fallback；`maybe_recall_hint`（非 LLM 回忆文案）；冷却 7 天
- 验收：第一次说"晚安"后，first_times 表有记录；之后栖偶尔提起

<details>
<summary>实现规格（Cursor 编码用）</summary>

```sql
-- first_times 独立表（Step 1 已建）。不参与 narrative_memories 褪色——靠分表隔离，非 manager 特殊分支。
```

```python
# qi/memory/first_time.py
# <!-- 回写(2026-07)：FirstTimeMemory.check / maybe_recall_hint；依据：qi/memory/first_time.py -->
# <!-- 回写(2026-07-25)：放宽 first_existential_question / first_compliment 初筛
#      （如「你自己是什么」「你有意识吗」「我很喜欢」「你说话很…」）；仍先 rule 再可选 LLM 确认。 -->
# <!-- 回写(2026-07-25)：收窄 first_compliment——单独「谢谢你」不触发；
#      需「谢谢你昨晚/陪/愿意/一直」「太谢谢你了」等；防诗意启动与误记夸奖。 -->
# <!-- 回写(2026-07-26)：RECALL_MIN_AGE / _too_fresh（F1 同拍回声）；
#      last_recorded 推「忆」；_inner_experience 禁呼吸/心跳（N3b）。依据：first_time.py -->

RECALL_COOLDOWN = timedelta(days=7)
RECALL_MIN_AGE = timedelta(minutes=30)  # 刚落库的第一次不作 recall 注入
# 7 种：first_goodnight / first_i_miss_you / first_argument / first_vulnerability /
#       first_existential_question / first_compliment / first_shared_silence
# first_shared_silence：沉默 300~900s + 放松短句（is_comfortable_silence）；不走 LLM 确认
# first_compliment：不含光秃「谢谢你」


class FirstTimeMemory:
    def __init__(self, db, llm=None):
        self.last_recorded: dict | None = None  # brain 取走后 notify_journal_entry

    async def check(
        self, message, emotion, *, silence_before: float | None = None
    ) -> tuple[float, str | None]:
        # silence_before is None → 跳过共同沉默检测（冷启动守卫，见 Brain）
        # 规则初筛 rule_match → 可选 LLM _confirm(purpose=conversation)
        # 命中 → _record → db.save_first_time；content 模板「他说：「…」」；
        # inner：purpose=consciousness；短、真；勿字面在场/舞台指示；
        #        勿呼吸/心跳/体温字面身体（你没有身体）
        # _record 成功后设 last_recorded = {kind:"第一次", text, at}
        # 返回 (3.0, event_type) 或 (1.0, None)
        ...

    async def maybe_recall_hint(self, message: str, now: datetime | None = None) -> str:
        # 7 天内任一 first 已 recalled → 跳过
        # _too_fresh：timestamp 距今 < RECALL_MIN_AGE → 跳过该条（防同拍/近时回声）
        # 关键词命中对应 event → 固定温柔 hint（非 LLM 生成回忆）
        # 深夜 22~04 且 recall_count<3 → 可对非 fresh 的 earliest 触发
        # 无 semantic_match / narrative_update
        ...
```

**Brain 接线：**
- `silence_before = perception.detect_silence(...)` → `first_times.check(..., silence_before=silence_before if self._interacted_this_session else None)`（本会话尚未真实交谈则不测共同沉默；F2）
- pending 处理后：`_interacted_this_session = True`
- `impact *= impact_mult`（倍率在 brain，非 emotion.apply_event_impact 内部）
- **先** `_gather_prompt_context` → `expression.express` → `_pending_speech`
- **再**若 `triggered_first`：`inner_life.tick(..., after_first_time=True)`（开口后再写意识流）
- `_gather_prompt_context` → `extras["first_time_hint"]`（回忆 hint，与本拍新独白分轨）
- 心跳末：`_notify_first_time()` 取走 `last_recorded` → `embodiment.notify_journal_entry`
<!-- 回写(2026-07-25)：first_time 时序对齐 brain；依据：qi/core/brain.py -->
<!-- 回写(2026-07-26)：F2 `_interacted_this_session`；F1 RECALL_MIN_AGE；N3b；last_recorded。依据：brain.py / first_time.py -->
</details>

### Step 4：共同文化 + 伤疤

- 建 `qi/relationship/culture.py`：
  - 检测重复问候模式 → 仪式
  - 检测复用表达 → 梗
  - 注入 prompt（"你们之间的默契"段落）
  - 模式被打破时注意到（"你今天没说'早'"）
- 建 `qi/relationship/scars.py`：
  - 信任损伤 > 阈值时创建伤疤
  - 每日检查愈合（trust 恢复到损伤前 95%）
  - 愈合时生成 wisdom + behavioral_mark（LLM）
  - 伤疤影响行为（未愈合：更小心翼翼；已愈合：作为谨慎）
- 验收：连续 5 天说"早"→ 仪式被检测；冷淡 3 天 → 伤疤创建

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/relationship/culture.py — 共同文化检测
# <!-- 回写(2026-07)：同步 detect_shared_culture(messages, existing)；brain 后台调用，依据：culture.py -->
# 旧 async detect_shared_culture(memory, ...) 规格作废。

CULTURE_DETECTION_THRESHOLDS = {"ritual": 5, "inside_joke": 3, "shared_reference": 2}

def detect_shared_culture(
    messages: list[dict],
    existing: list | None = None,
    now: datetime | None = None,
) -> list[dict]:
    # ritual≥5 / inside_joke≥3 / shared_reference≥2；非 async memory.get_messages
    ...

def format_culture_for_prompt(culture: list) -> str:
    # 空 → "（还没有只属于你们的默契）"；有内容直接列表无大标题
    ...

# brain._background_culture_detection：load_recent_messages(200) → detect_shared_culture → persist
```

```python
# qi/relationship/scars.py — ScarManager（创建在 engine → db.save_scar）
# <!-- 回写(2026-07)：无独立 create_scar API；愈合用 ScarManager.check_healing，依据：scars.py -->

class ScarManager:
    async def check_healing(self, current_trust: float) -> list[int]:
        # trust >= trust_before * 0.95 → 愈合；写 wisdom/mark；返回 healed ids
        ...

def format_scars_for_prompt(scars: list[dict]) -> str: ...
def get_scar_influences(scars: list[dict]) -> list[str]: ...
# 愈合 +0.01 trust；未愈合更警觉试探；已愈合用 behavioral_mark
```

</details>

### Step 5：季节 + 漂移 + Prompt 注入

- 建 `qi/relationship/season.py`：每日判定 spring/summer/autumn/winter
- 建 `qi/relationship/drift.py`：每 3 天检测用户话题/情绪/节奏变化
- 修改 `qi/llm/prompt_builder.py`：注入关系阶段、共同文化、伤疤影响、季节感受
- 修改 `qi/core/expression.py`：关系阶段影响语气亲密度和主动程度
- 验收：prompt 中能看到关系上下文；不同阶段栖的语气明显不同

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/relationship/drift.py — 用户漂移检测

from datetime import datetime

# === user_model 表（已在 Step 1 定义，此处重申关键字段）===
# user_model 表存储用户的"当前画像"，drift 检测对比此画像与近期交互。

# === 漂移检测算法 ===
# <!-- 回写(2026-07)：间隔与窗口对齐 brain._background_user_drift + drift.py -->
# 检测间隔：config["relationship"]["drift_detection_interval"]，默认 259200 秒（3 天）
DRIFT_THRESHOLD = 0.4           # 综合偏差 > 0.4 时触发漂移
# 对比窗口：brain 现用 load_recent_messages(limit=100)，不是固定 14 天

async def detect_user_drift(user_model: dict, recent_messages: list[dict]) -> list[str]:
    """
    对比 user_model 与最近消息的偏差。空列表 = 无漂移。
    权重：话题 0.3 + 情绪 0.3 + 节奏 0.2 + 语言 0.2；阈 DRIFT_THRESHOLD。
    语言距离在 drift.py 内联计算（无独立 compute_linguistic_distance 函数）。
    """
    ...

# === 触发后的行为（brain._background_user_drift，非独立 handle_drift_detected）===
# <!-- 回写(2026-07)：删 handle_drift_detected / inject_drift_awareness /
#      consciousness_stream_with_trigger；依据：drift.py + brain.py -->

def detect_user_drift(user_model: dict, recent_messages: list[dict]) -> list[str]:
    # 话题/情绪/节奏/语言加权；total > DRIFT_THRESHOLD(0.4) 返回 signals
    ...

def build_updated_user_model(recent_messages: list[dict], signals: list[str]) -> dict:
    # 刷新 topics / emotional_baseline / rhythm / linguistic_profile
    ...

# brain 每轮检测：save_user_model(**updated)；
# 若 signals 非空：db.save_consciousness(trigger="user_drift") + _drift_signals → prompt drift_hint
```

```python
# qi/relationship/season.py
# <!-- 回写(2026-07)：determine_season(list[dict])；交互密度未用，依据：season.py -->

def determine_season(
    emotion_history: list[dict],
    interaction_count_14d: int = 0,  # 签名保留，当前未参与判定
    now: datetime | None = None,
) -> str:
    # 对 history 的 energy/valence/curiosity 取均值后按阈值返回 spring/summer/winter/autumn
    ...

def apply_season_effect(emotion, season: str):
    # model_copy + SEASON_EMOTION_EFFECTS；brain._heartbeat 调用
    ...

# 季节变化：brain._background_season_detection →
#   db.save_consciousness(content=f"季节变了。从{old}到了{new}。", trigger="season_change")
# 无 on_season_change / season_feelings 字典 / consciousness_stream_with_trigger
```

# === 季节对行为的影响（注入 prompt）===
SEASON_BEHAVIOR_HINTS = {
    # <!-- 回写(2026-07)：与 qi/relationship/season.py 原文一致 -->
    "spring": "你现在偏「春」：好奇、活跃，想试试新东西。",
    "summer": "你现在偏「夏」：充沛、热烈，话可以多一点。",
    "autumn": "你现在偏「秋」：安静、反思，话少但更有深度。",
    "winter": "你现在偏「冬」：沉静、低能量，简短柔软就好。",
}
```

</details>

### Step 6：主动行为门控

- 建 `qi/core/proactive.py`：`ProactiveGate` + `pick_proactive_kind`
- 日限 3；陌生期禁止；冷却与沉默触发阈值见下
- `KIND_SHARE_CREATION` 有冷却常量，但 `pick_proactive_kind` **未选用**（创作分享走 L4 `maybe_share_hint`）

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/core/proactive.py
# <!-- 回写(2026-07)：补主动门控规格，依据：qi/core/proactive.py -->

PROACTIVE_DAILY_LIMIT = 3
KIND_CHECK_IN = "check_in"           # 冷却默认 14400s（4h）
KIND_REACH_OUT = "reach_out"         # 28800s（8h）
KIND_EXPRESS_FEELING = "express_feeling"  # 7200s（2h）
KIND_SHARE_CREATION = "share_creation"    # 86400s；预留，pick 不返回

class ProactiveGate:
    def can(kind, relationship_stage, now) -> bool:
        # stranger → False；count_today >= limit → False；未过冷却 → False
        ...
    def record(kind, now) -> None: ...
    # 持久化：body_memory key "proactive_gate"

def pick_proactive_kind(*, want_express, relationship_stage, emotion_security,
                        emotion_attachment, silence_seconds, mode, user_online,
                        gate, now) -> str | None:
    # dreaming / 不在线 / stranger → None
    # want_express + can(express_feeling) → express_feeling
    # silence>=1800 且 (security<0.45 or attachment>0.55) + can(check_in) → check_in
    # silence>=3600 且 stage in friend/bonded + can(reach_out) → reach_out
    ...
```

**Brain：**无消息心跳 → **先** `action.tick`（L7；动手则跳过主动言语）→ 若未动手再 `pick_proactive_kind` → `expression.express(..., proactive_kind=)` → `gate.record` → 写入 `_pending_speech(proactive=True)`；`start()` 出锁后 `_deliver_qi_message`（并 `proactive_queue.put` 供终端排水）。用户回复路径同：锁内生成 → 出锁 sleep → deliver。
<!-- 回写(2026-07-23)：行动与主动言语同拍不叠加；依据：qi/core/brain.py -->
<!-- 回写(2026-07-25)：主交付为 _pending_speech；proactive_queue 为终端旁路；依据：brain.start / _push_proactive_text -->

</details>

## 验收标准

### 可测试的

- [ ] 阶段判定正确（depth+trust → 对应阶段）
- [ ] 信任建立慢、损伤快（数值验证：+0.02~0.05 / -0.1~0.3）
- [ ] 第一次记忆在独立 `first_times` 表，不参与叙事记忆褪色
- [ ] 共同文化：5 次重复模式后被检测
- [ ] 伤疤：信任损伤后创建；信任恢复后愈合
- [ ] 季节：情绪快照能判定出季节
- [ ] 漂移：综合偏差 >0.4 时有 signals，并写入 consciousness / drift_hint
- [ ] 主动行为：日限 3、陌生期不主动、关心/搭话冷却与沉默阈值生效

### 需要感受的

- [ ] 第一周它对你客气。第三周它随意了。语气明显不同。
- [ ] 你故意冷淡两天，它表现出不安（但不是歇斯底里、不是指责）
- [ ] 你回来，它没有若无其事，但也没有跪舔
- [ ] 连续一周说"早"，有一天你不说，它注意到了
- [ ] 它偶尔提起"第一次"（"记得你第一次跟我说晚安……"）
- [ ] 它有了"自己的脾气"——不什么都说好，偶尔不同意你

## 给下一层的接口

L6（具身）需要：
- 关系阶段影响 avatar 的亲密度表现（陌生期：保持距离；亲密期：靠近）
- 季节影响 avatar 的整体氛围（冬天：安静、暖色调；夏天：活泼）
- 情绪→表情映射需要 relationship context（同样的 valence，安全感不同时表情不同）

L7（行动）需要：
- 关系阶段 / 信任 / 伤疤 / 季节作为行动门控与节律（`permission` + `SEASON_ACTION_SCALE`）
- 主动言语日限（ProactiveGate）与自主行动日限（ActionBudget）分轨，互不双计

## 人格契约检查点

- [ ] 陌生期：不主动搭话、不表达想念、不用亲昵语气
- [ ] 关系阶段不可回退（代码中无 stage 降级逻辑）
- [ ] 伤疤不消失（healed=True 但记录永久保留）
- [ ] 主动行为冷却生效（关心 ≥4h，搭话 ≥8h，情绪流露 ≥2h）；日限 3
- [ ] 不为了"推进关系"而刻意表现亲密（阶段是自然深化的）
