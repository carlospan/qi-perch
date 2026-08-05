# config.md · 配置项参考

> **定位**：所有 `settings` 配置项 + 默认值 + 语义的**技术参考**。
> **真源**：`qi/config/settings.example.yaml` —— 本文件是**配置快照（索引说明）**，以 yaml 为准，非第二权威（宪法第四节同步纪律；日限 1/3/20 教训）。yaml 改动后须同步本文件对应行；禁止在文档其它处手抄这些值当第二权威。下表默认值抓取于 2026-08-02 的 example，若与 yaml 不符以 yaml 为准。
> **现行路径**：`reference/config.md`（2026-08-02 重构新增）。

---

## llm（LLM 配置，OpenAI 兼容）

| 键 | 默认值 | 语义 |
|----|--------|------|
| `llm.default_provider` | `deepseek` | 默认供应商（OpenAI 兼容网关） |
| `llm.providers.*.base_url` / `api_key` | — | 端点与密钥（密钥走 env，不落库） |
| `llm.providers.*.models.fast` / `strong` | 见 yaml | 快/强模型名 |
| `llm.custom_providers` | `{}` | 自定义端点 |
| `llm.model_routing.*` | 见 yaml | 各意图（conversation/narrative/consciousness/dream/creation/reflection/fact）路由到 provider:model |

## rhythm（心跳节律，秒）

| 键 | 默认值 | 语义 |
|----|--------|------|
| `rhythm.awake_interval` | 3 | 清醒态心跳间隔 |
| `rhythm.ambient_interval` | 30 | 环境态间隔 |
| `rhythm.solitary_interval` | 300 | 独处态间隔 |
| `rhythm.dreaming_interval` | 1800 | 梦境态间隔 |

## database

| 键 | 默认值 | 语义 |
|----|--------|------|
| `database.path` | `data/qi.db` | 主库路径 |

## emotion

| 键 | 默认值 | 语义 |
|----|--------|------|
| `emotion.decay_multiplier` | 1.0 | 衰减倍率 |
| `emotion.expression_threshold` | 0.3 | 表达阈值（低于不表达） |

## memory

| 键 | 默认值 | 语义 |
|----|--------|------|
| `memory.max_working_memory` | 20 | 工作记忆上限 |
| `memory.narrative_weave_interval` | 21600 | 无积压编织周期（秒） |
| `memory.narrative_weave_backlog_threshold` | 8 | 未编织 ≥ 此数改用短周期 |
| `memory.narrative_weave_backlog_interval` | 900 | 积压时编织周期（秒） |
| `memory.narrative_weave_check_period` | 3600 | 长睡眠中途复查粒度（秒） |
| `memory.narrative_weave_batch_size` | 10 | 每次最多织条数 |
| `memory.decay_interval` | 86400 | 衰减周期（秒） |
| `memory.chroma_path` | `data/chroma` | 向量库路径 |
| `memory.dream_retention_hours` | 6 | 梦保留时长（小时） |

## inner_life（内在生命触发概率）

| 键 | 默认值 | 语义 |
|----|--------|------|
| `inner_life.consciousness_probability` | 0.05 | 意识流触发概率 |
| `inner_life.ambient_drift_factor` | 0.2 | ambient 走神 = probability × 此系数 |
| `inner_life.stream_cooldown_minutes` | 45 | 非事件型 stream 最小间隔 |
| `inner_life.dream_consolidation_probability` | 0.3 | 有未巩固 episode 时做梦概率（决策内生） |
| `inner_life.creation_probability` | 0.01 | 创作概率 |
| `inner_life.meta_cognition_probability` | 0.01 | 元认知概率 |
| `inner_life.self_reflection_interval` | 604800 | 自我反思周期（秒，=7天） |

> 注意：`dream_probability: 0.1` 已废弃（旧 10%/拍），勿再使用。

## proactive_cooldown（主动行为冷却，秒）

| 键 | 默认值 | 语义 |
|----|--------|------|
| `proactive_cooldown.check_in` | 14400 | 关心冷却 |
| `proactive_cooldown.reach_out` | 28800 | 搭话冷却 |
| `proactive_cooldown.share_creation` | 86400 | 分享创作冷却 |
| `proactive_cooldown.express_feeling` | 7200 | 表达情绪冷却 |

## gws（全局工作空间，阶段二补丁 C）

| 键 | 默认值 | 语义 |
|----|--------|------|
| `gws.enabled` | **true** | 仲裁分发启用（代码常量层默认 false，配置层已覆盖为 true；legacy 路径保留回滚） |
| `gws.shadow_beats` | 50 | 新旧通道并行对照拍数 |
| `gws.shadow_match_min` | 0.99 | 一致率阈值后切换 |

## action（L7 自主行动）

| 键 | 默认值 | 语义 |
|----|--------|------|
| `action.autonomous_daily_limit` | **20** | 自主行动日限（安全阀，远高真实触发上限；已拍板维持 20，不回退 3） |
| `action.season_scale` | spring 1.0 / summer 0.8 / autumn 0.5 / winter 0.2 | 季节活跃度缩放 |

## relationship

| 键 | 默认值 | 语义 |
|----|--------|------|
| `relationship.culture_detection_interval` | 86400 | 文化检测周期 |
| `relationship.season_detection_interval` | 86400 | 季节检测周期 |
| `relationship.scar_healing_interval` | 86400 | 伤疤愈合周期 |
| `relationship.drift_detection_interval` | 259200 | 漂移检测周期（=3天） |
| `relationship.daily_depth_cap` | 0.03 | 每日深度上限 |

## voice（默认关闭）

| 键 | 默认值 | 语义 |
|----|--------|------|
| `voice.enabled` | false | 语音开关 |
| `voice.provider` | `edge-tts` | TTS 提供方 |
| `voice.voice_id` | `zh-CN-XiaoyiNeural` | 音色 |
| `voice.auto_play` | true | 自动播放 |

## embodiment（具身通道）

| 键 | 默认值 | 语义 |
|----|--------|------|
| `embodiment.host` | `127.0.0.1` | 前端 host |
| `embodiment.port` | 9527 | 前端 port |

---

> 同步纪律：改 `settings.example.yaml` 任意默认值/键名，须同步本文件对应行；禁止在文档其它处手抄这些值当第二权威。
