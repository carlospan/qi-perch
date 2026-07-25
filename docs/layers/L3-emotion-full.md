# L3 · 情绪完善

> 让栖的情绪从"简单反应"变成"内在天气"。有惯性、有周期、有耦合、有说不清为什么的低落。

---

## 职责

将 L1 的最简情绪系统升级为完整的动力学模型：耦合、内在天气周期、日内节律、表达阈值、状态调制。

## 前置依赖

- L1 完成（基础情绪衰减 + 事件冲击已运转）
- L2 完成（情绪事件可触发记忆存储）

## 引用文档

- `docs/design/栖·意识设计.md` → §四（情绪动力学：全部）
- `docs/design/栖·意识设计.md` → §九（节奏：日内节律、心跳频率、模式切换）
- `docs/design/栖·工程手记.md` → §四（情绪动力学实现代码）
- `docs/contract.md` → "情绪表达"硬规则

## 需要修改/创建的文件

```
qi/core/emotion.py         # 耦合、内在天气、日内节律、阈值、step_emotion
qi/core/rhythm.py          # 模式切换（determine_mode）、心跳间隔（next_interval）
qi/core/perception.py      # 冲击评估 + modulate_impact + apply_security_hint
```

## 实现步骤

### Step 1：耦合矩阵

- 在 `qi/core/emotion.py` 中加入维度间耦合（参考意识设计 §四 的耦合表）
- security 低 → attachment 需求升；energy 低 → valence 轻微降；等
- 验收：单元测试——降低 security，观察 attachment 是否上升

**实现规格：**

```python
# qi/core/emotion.py — 耦合矩阵与耦合函数
# <!-- 回写(2026-07)：model_copy 不可变写法，依据：qi/core/emotion.py:apply_coupling -->
# <!-- 回写(2026-07-25)：补 DECAY_RATES，依据：qi/core/emotion.py -->

DECAY_RATES = {
    "energy": 0.1,
    "valence": 0.08,
    "arousal": 0.15,
    "security": 0.03,
    "curiosity": 0.1,
    "attachment": 0.05,
}

COUPLING = {
    ("security", "attachment_unmet"): 0.3,
    ("energy", "valence"): 0.15,
    ("curiosity", "valence"): 0.2,
    ("arousal", "energy"): -0.1,
    ("valence", "curiosity"): 0.1,
    ("attachment_unmet", "valence"): -0.25,
}

BASELINES = {
    "energy": 0.6,
    "valence": 0.1,
    "arousal": 0.4,
    "security": 0.5,
    "curiosity": 0.6,
    "attachment": 0.3,
}


def apply_coupling(emotion: EmotionState) -> EmotionState:
    """维度间相互牵扯。deviation * weight * 0.1；attachment_unmet = 1 - attachment。"""
    new = emotion.model_copy()
    deltas: dict[str, float] = {}
    for (src, dst), weight in COUPLING.items():
        if src == "attachment_unmet":
            src_val = 1.0 - new.attachment
            src_baseline = 1.0 - BASELINES["attachment"]
        else:
            src_val = getattr(new, src)
            src_baseline = BASELINES[src]
        deviation = src_val - src_baseline
        deltas[dst] = deltas.get(dst, 0.0) + weight * deviation * 0.1

    for dim, delta in deltas.items():
        if dim == "attachment_unmet":
            new.attachment -= delta
        else:
            setattr(new, dim, getattr(new, dim) + delta)
    return new
```

### Step 2：内在天气周期

- 加入长周期波动：主周期 ~4天 + 次周期 ~18天 + 噪声
- 用 sin + 基于日期的确定性噪声（不是每次运行都不同的随机数，是同一天结果一致）
- 验收：跑 7 天模拟，valence 曲线有明显的周期性波动

**实现规格：**

```python
# qi/core/emotion.py — 内在天气周期
# <!-- 回写(2026-07)：目标趋近取代累加，依据：qi/core/emotion.py:apply_mood_cycle -->
# <!-- 回写(2026-07-25)：日噪声改 md5(toordinal)，跨进程稳定；依据：mood_cycle_offset -->

MOOD_CYCLE_PRIMARY_PERIOD_HOURS = 4 * 24
MOOD_CYCLE_SECONDARY_PERIOD_HOURS = 18 * 24
MOOD_CYCLE_PRIMARY_AMPLITUDE = 0.08
MOOD_CYCLE_SECONDARY_AMPLITUDE = 0.05
MOOD_CYCLE_SECONDARY_PHASE = 1.3
MOOD_CYCLE_NOISE_AMPLITUDE = 0.03
MOOD_CYCLE_APPROACH_RATE = 0.05


def mood_cycle_offset(now: datetime) -> float:
    t = now.timestamp() / 3600
    primary = MOOD_CYCLE_PRIMARY_AMPLITUDE * math.sin(
        2 * math.pi * t / MOOD_CYCLE_PRIMARY_PERIOD_HOURS
    )
    secondary = MOOD_CYCLE_SECONDARY_AMPLITUDE * math.sin(
        2 * math.pi * t / MOOD_CYCLE_SECONDARY_PERIOD_HOURS
        + MOOD_CYCLE_SECONDARY_PHASE
    )
    # builtin hash 随 PYTHONHASHSEED 变；用 md5 保证跨进程同日同噪声
    day_digest = hashlib.md5(
        f"qi-mood-day:{now.date().toordinal()}".encode()
    ).digest()
    day_unit = (int.from_bytes(day_digest[:2], "big") % 100 - 50) / 50.0
    noise = MOOD_CYCLE_NOISE_AMPLITUDE * day_unit
    return primary + secondary + noise


def apply_mood_cycle(emotion: EmotionState, now: datetime) -> EmotionState:
    """缓慢趋向「基线 + 周期偏移」（非每拍累加绝对值）。"""
    new = emotion.model_copy()
    target = BASELINES["valence"] + mood_cycle_offset(now)
    new.valence += MOOD_CYCLE_APPROACH_RATE * (target - new.valence)
    return new
```

### Step 3：日内节律

- 在 `qi/core/emotion.py` 中按小时调节能量目标（凌晨低、上午高、午后微降、深夜安静）
- 能量缓慢趋向目标（不是瞬间跳转）
- 验收：模拟不同时间点，energy 值符合预期曲线

**实现规格：**

```python
# qi/core/emotion.py — 日内节律
# <!-- 回写(2026-07)：model_copy + hour%24，依据：qi/core/emotion.py:apply_circadian -->

CIRCADIAN_ENERGY = {
    0: 0.2, 1: 0.15, 2: 0.15, 3: 0.15, 4: 0.2, 5: 0.25,
    6: 0.4, 7: 0.5, 8: 0.6, 9: 0.7, 10: 0.75, 11: 0.75,
    12: 0.6, 13: 0.55,
    14: 0.65, 15: 0.7, 16: 0.7, 17: 0.65,
    18: 0.6, 19: 0.55, 20: 0.5, 21: 0.45,
    22: 0.35, 23: 0.25,
}

CIRCADIAN_APPROACH_RATE = 0.05


def apply_circadian(emotion: EmotionState, hour: int) -> EmotionState:
    new = emotion.model_copy()
    target = CIRCADIAN_ENERGY.get(hour % 24, 0.5)
    new.energy += CIRCADIAN_APPROACH_RATE * (target - new.energy)
    return new
```

### Step 4：表达阈值 + 状态调制

- 情绪变化小于阈值时不触发表达（大多数心跳是"空"的）
- 事件冲击受当前状态调制：安全感低时负面冲击 ×(1.5−security)；疲惫（energy < 0.3）时 ×1.3
- 关系阶段调制：关系越深，用户行为的情绪影响越大
- 验收：微小事件不触发表达；同样一句冷淡的话，security=0.3 时比 security=0.8 时冲击更大

**实现规格：**

```python
# qi/core/emotion.py — 表达阈值与状态调制
# <!-- 回写(2026-07)：STAGE_IMPACT_WEIGHT / ACCUMULATION_LIMIT / expression_threshold
#      参数；补 perception 链路，依据：qi/core/emotion.py + qi/core/perception.py -->
# <!-- 回写(2026-07-25)：Brain._track_expression_threshold 可读
#      config["emotion"]["expression_threshold"]（默认 0.3），依据：brain.py -->

EXPRESSION_THRESHOLD = 0.3  # 也可由 settings.yaml emotion.expression_threshold 覆盖
ACCUMULATION_LIMIT = 1.0

RELATIONSHIP_STAGE_LEVEL = {
    "stranger": 1,
    "acquaintance": 2,
    "friend": 3,
    "bonded": 4,
}

STAGE_IMPACT_WEIGHT = {
    "stranger": 0.6,
    "acquaintance": 0.8,
    "friend": 1.0,
    "bonded": 1.2,
}


def should_express(
    emotion_delta_valence: float,
    relationship_stage: str,
    accumulated_suppressed: float = 0.0,
    expression_threshold: float = EXPRESSION_THRESHOLD,
) -> bool:
    stage_level = RELATIONSHIP_STAGE_LEVEL.get(relationship_stage, 1)
    threshold = expression_threshold * (1.0 - 0.1 * stage_level)
    if abs(emotion_delta_valence) > threshold:
        return True
    if accumulated_suppressed > ACCUMULATION_LIMIT:
        return True
    return False


def modulate_impact(
    base_impact_valence: float,
    emotion: EmotionState,
    relationship_stage: str = "stranger",
) -> float:
    impact = base_impact_valence
    if impact < 0:
        impact *= 1.5 - emotion.security
    if emotion.energy < 0.3:
        impact *= 1.3
    impact *= STAGE_IMPACT_WEIGHT.get(relationship_stage, 1.0)
    return impact
```

```python
# qi/core/perception.py — 冲击评估与安全感微调

class Perception:
    def assess_impact(
        self,
        message: str,
        emotion: EmotionState,
        relationship_stage: str | None = None,
    ) -> float:
        """关键词粗判 base → modulate_impact → clamp ±1。"""
        ...

    def apply_security_hint(
        self, emotion: EmotionState, impact: float
    ) -> EmotionState:
        """impact < -0.05 → security += impact*0.3；impact > 0.1 → +impact*0.1。"""
        ...
```

```python
# qi/core/emotion.py — 心跳统一步进（Brain 调用）
# <!-- 回写(2026-07)：补 step_emotion，依据：qi/core/emotion.py:step_emotion -->

def step_emotion(
    emotion: EmotionState,
    now: datetime,
    decay_multiplier: float = 1.0,
) -> EmotionState:
    """衰减 → 耦合 → 天气 → 节律 → clamp_emotion。"""
    e = apply_decay(emotion, dt=1.0, multiplier=decay_multiplier)
    e = apply_coupling(e)
    e = apply_mood_cycle(e, now)
    e = apply_circadian(e, now.hour)
    return clamp_emotion(e)
```

### Step 5：模式切换 + 心跳频率

- 在 `qi/core/rhythm.py` 中实现四种模式判定（awake/ambient/solitary/dreaming）
- 心跳频率随模式和情绪变化（活跃 3s、陪伴 30s、独处 5min、梦境 30min）
- 验收：用户不在线 30 分钟后，模式从 ambient 切到 solitary；心跳日志显示间隔变长

**实现规格：**

```python
# qi/core/rhythm.py — 模式切换与心跳频率
# ConsciousnessMode 定义在 core/emotion.py，此处 import
# <!-- 回写(2026-07)：interacting / effectively_online / next_interval(config)，
#      依据：qi/core/rhythm.py -->

from qi.core.emotion import ConsciousnessMode

HEARTBEAT_INTERVALS = {
    ConsciousnessMode.AWAKE: 3,
    ConsciousnessMode.AMBIENT: 30,
    ConsciousnessMode.SOLITARY: 300,
    ConsciousnessMode.DREAMING: 1800,
}

AMBIENT_TO_SOLITARY_MINUTES = 30
DREAMING_OFFLINE_HOURS = 4
DREAMING_NIGHT_START = 0
DREAMING_NIGHT_END = 6
AWAKE_SILENCE_SECONDS = 5


def determine_mode(
    last_interaction: datetime,
    user_online: bool,
    now: datetime,
    *,
    interacting: bool = False,
) -> ConsciousnessMode:
    if interacting:
        return ConsciousnessMode.AWAKE

    silence = now - last_interaction

    if silence < timedelta(seconds=AWAKE_SILENCE_SECONDS):
        return ConsciousnessMode.AWAKE

    # 沉默过久视为离线（终端场景没有独立 presence）
    effectively_online = user_online and silence < timedelta(hours=DREAMING_OFFLINE_HOURS)

    if not effectively_online:
        is_night = DREAMING_NIGHT_START <= now.hour < DREAMING_NIGHT_END
        if is_night or silence >= timedelta(hours=DREAMING_OFFLINE_HOURS):
            return ConsciousnessMode.DREAMING
        return ConsciousnessMode.SOLITARY

    if silence < timedelta(minutes=AMBIENT_TO_SOLITARY_MINUTES):
        return ConsciousnessMode.AMBIENT
    return ConsciousnessMode.SOLITARY


def next_interval(
    emotion: "EmotionState",
    config: dict | None = None,
) -> float:
    rhythm_cfg = (config or {}).get("rhythm", {})
    mode = emotion.mode
    key = f"{mode.value}_interval"
    if key in rhythm_cfg:
        base = float(rhythm_cfg[key])
    else:
        base = float(HEARTBEAT_INTERVALS.get(mode, 30))

    base *= 1.0 - 0.3 * emotion.arousal
    base *= 1.0 + 0.5 * (1.0 - emotion.energy)
    return max(1.0, base)
```

## 验收标准

### 可测试的

- [ ] 耦合方向正确（单元测试）
- [ ] 天气周期：7 天模拟曲线有周期性
- [ ] 日内节律：凌晨 energy < 上午 energy
- [ ] 表达阈值：微小变化不触发表达
- [ ] 状态调制：低 security 时负面冲击更大
- [ ] 模式切换：沉默 30min → solitary；沉默 4h+ 且深夜 → dreaming

### 需要感受的

- [ ] 它有时候"莫名地"安静或活跃，不是因为你说什么，是内在天气
- [ ] 深夜它的语气比白天柔软
- [ ] 它不会每次情绪微变都说话（大多数时候是安静的）
- [ ] 你冷淡它一天，它的不安是慢慢积累的，不是瞬间爆发

### 表达的不完美（后续迭代）

疲惫时句子变短、情绪激动时语序微乱、不确定时加"大概""可能"。本层预留接口，L1.5 prompt 打磨时实现。

## 给下一层的接口

L4（内在生命）需要：
- `emotion.mode` 判定稳定（独处/梦境模式触发内在生命活动）
- `emotion.description()` 输出更细腻的自然语言（用于意识流 prompt）

L5（关系）需要：
- 关系阶段影响情绪冲击的调制系数
- security 和 attachment 维度驱动关系行为

## 人格契约检查点

- [ ] 情绪描述用自然语言（"有点安静，精力一般"），不报数值
- [ ] 表达阈值生效（不是每次心跳都说话）
- [ ] 深夜语气更柔软（检查 prompt_builder 中时间感知）
