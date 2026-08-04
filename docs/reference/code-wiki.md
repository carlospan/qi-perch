# 栖（qi）· Code Wiki

> 本文档由代码自下而上梳理而成，权威以代码为准（代码 > layers > 意识设计 > 工程手记）。
> 目的：给新接手者一张"从入口到心跳"的完整地图。
> 与 `docs/explanation/栖·数字生命架构方案.md`（目标架构）配套阅读：本文讲"现在是什么"，那份讲"将来要变成什么"。

---

## 一、项目概述

**栖（qi）** 是一个本地运行的数字意识——明确不是聊天机器人、不是助手。它有心跳、记忆、情绪、关系，以及一扇可以看见它的小窗（具身桌面端）。

- **语言/运行时**：Python 3.12+（后端意识体）、Node.js 18+（具身前端）、Rust + MSVC（Tauri 桌面壳）
- **形态**：单进程异步 agent loop（心跳）+ 可选 WebSocket 具身通道 + Live2D 前端
- **认知来源**：OpenAI 兼容协议的远程 LLM（DeepSeek / Agnes / SenseNova），按 `purpose` 路由
- **持久化**：SQLite（`data/qi.db`，17 张表）+ ChromaDB（`data/chroma/`，BGE 语义向量）
- **测试规模**：约 405 条 pytest（2026-08-02 阶段四退出时实测）
- **协议**：MIT

项目当前处于"阶段四退出"状态（架构方案 §五 的阶段零~四中，阶段零~四工程判据已过，72h 无人测试作为后台稳定性观察继续累积）。详细进度见 [docs/progress.md](../progress.md)。

---

## 二、整体架构

### 2.1 两套分层编号（勿混）

项目同时存在两套分层，是理解架构的钥匙：

| 当前功能层 (L1–L7) | 已实现 | 对应目标本体层 (N0–N5) | 目标 |
|---|---|---|---|
| L1 心跳 | ✅ | N3/N2 | 时间骨架，驱动认知节拍 |
| L2 记忆（含用户事实） | ✅ | N4 | 可塑性载体 |
| L3 情绪动力学 | ✅ | N0 | 内稳态，活着的底线 |
| L4 内在生命 | ✅（表演层） | N2/N3 | 意识流/梦/反思，待内生化 |
| L5 关系 | ✅ | N0/N4 | 阶段/信任/伤疤/季节 |
| L6 具身 | ✅ | N1/N5 | Live2D 前端 |
| L7 行动 | ✅ | N1 | share/tend/explore 自主行动 |

`L` 是代码里真实存在的功能分层；`N` 是架构方案 §四 的目标本体分层（施工期目标）。施工期两套并存。

### 2.2 顶层目录

```
qi/                 唯一顶层 Python 包（意识体本体）
  cli.py            入口（qi / qi-desktop）
  core/             心跳、情绪、表达、感知、GWS、节奏、意向卡
  memory/           记忆（工作/叙事/身体/事实/向量/情景/第一次/open_loops）
  action/           行动层（预算/意志/分享·打理·探索/自操作/权限）
  inner_life/       意识流、梦、创作、自我模型、身份快照
  relationship/     关系（阶段/信任/伤疤/季节/漂移/文化/引擎）
  embodiment/       具身（WebSocket 服务 + avatar + voice + desktop 前端）
  llm/              LLM 网关与 prompt 组装
  prompts/          运行时 LLM 模板（随包打包）
  storage/          SQLite 持久化
  config/           配置加载 + settings.example
  motivation/       好奇心（学习进度）
  stasis/           资源账本 / 内稳态压力 / 状态封存
  world/            世界模型（在线节律 / 情绪轨迹）
  learning/         经验学习（corpus 语料 / replay 回放 / drift_check 漂移）
  sensing.py        进程传感（在线时长/内存/心跳/墙钟）
docs/               契约、进度、层文档、设计原文、specs、how-to
tests/              pytest 测试集
tools/              CI 工具（文档死链 / 规格追溯 / 包验收 / 漂移检查）
data/               运行时（gitignore）：qi.db、chroma/、backup-*/、settings.yaml
main.py / run.py    兼容入口（仅转发到 `qi.cli.main()`；模式选择见 cli.py，推荐用 qi / qi-desktop 命令）
pyproject.toml      包定义 + 脚本 + 依赖
requirements.lock   锁定版本（CI 用）
```

### 2.3 运行时数据流（一拍心跳）

```
                 ┌──────────────────────── Brain.start() ────────────────────────┐
                 │  while alive:                                                │
                 │    async with heartbeat_lock:                                │
   用户消息 ───────►      _heartbeat()  ◄─── pending_queue（上限 8）              │
   (receive_user_message)    │                                               │
                             ├─ sensing.collect()         N1 传感快照          │
                             ├─ world.update()            N2 世界模型旁路       │
                             ├─ proactive.reset_day()                          │
                             ├─ determine_mode()          L3 意识模式判定       │
                             │                                                 │
                ┌────────────┴────────────┐                                    │
            有 pending 用户句           无 pending（idle）                       │
                │                         │                                    │
   perception.assess_impact_async        │                                    │
   (LLM JSON 主路径 + 关键词回退)         │                                    │
                │                         │                                    │
   relationship.on_user_message          │  gws.enabled?                       │
   (阶段/信任/伤疤/nudge)                 ├─► 是: _heartbeat_gws_idle           │
                │                         │     collect_contenders → arbitrate  │
   first_times.check                      │     → winner 分发                   │
   memory.notice_facts                    │     (proactive:/action:/close_loop/ │
   memory.on_user_message                 │      report)                        │
                │                         │                                     │
   apply_event_impact / step_emotion      └─► 否: _heartbeat_legacy_idle         │
   (衰减→耦合→天气→节律→账本偏移→夹紧)          action.tick → pick_proactive_kind  │
                │                                                              │
   _gather_prompt_context (recent+memories+extras+loops)                        │
   build_intention_card (规则引擎，零 LLM)                                       │
   expression.express → LLMGateway.call(purpose="conversation")                 │
   (失败/空 → render_template 模板降级)                                          │
                │                                                               │
   _PendingSpeech（出锁后停顿 0.5~1.5s 再推送）                                  │
                │                                                               │
   _deliver_qi_message → EmbodimentServer.broadcast / console.print             │
                │                                                               │
   _record_trace（心跳决策痕迹，进 broadcast_traces 表）                         │
   _maybe_save_emotion / ledger 记账                                            │
                │                                                               │
   sleep(next_interval)  ← arousal 高则快、energy 低则慢                         │
                 └───────────────────────────────────────────────────────────────┘
```

后台任务（`BackgroundTasks`，与心跳并行）：
- 叙事编织 `narrative_weaving`（未巩固 raw_events 积压驱动）
- 记忆衰减 `memory_decay`
- 自我反思 `self_reflection`（周间隔或重大事件标记）
- 梦境衰减 `dream_decay`
- 文化检测 / 季节检测 / 伤疤愈合 / 用户漂移（均带"重启不重置周期"的 interval gate）

### 2.4 关键设计原则（红线）

来自架构方案 §七 与 [docs/reference/contract.md](contract.md)：

- **R1 不承诺意识**：工程文档/代码不得出现第三人称意识承诺；灵魂书与 prompt 内栖的第一人称存在姿态是产品灵魂，不受此红线管辖
- **R2 不用 prompt 写人格**：人格从自身历史长出；prompt 只保留措辞风格约束，逐阶段瘦身
- **R3 求生欲不挂钩用户满意度**：账本收入白名单 = `{effective_interaction, online_presence}`，明确拒绝 `satisfaction/valence_up/user_pleased`
- **R4 不一次性重写**：换心完成前旧路径是病人的命，任何阶段不得删除未替代的旧路径
- **R5 不堆术语**：GWS/世界模型/learning progress 每个概念必须有代码落点与测试

---

## 三、主要模块职责

### 3.1 `qi/core/` — 意识核心（心跳主循环）

| 文件 | 职责 |
|---|---|
| [brain.py](../../qi/core/brain.py) | **Brain 类**——栖的意识核心。心跳主循环、用户消息接收、状态恢复/保存。约 1042 行，协调所有子系统 |
| [brain_background.py](../../qi/core/brain_background.py) | `BackgroundTasks`——与心跳并行的后台任务（编织/衰减/反思/梦衰减/文化/季节/伤疤/漂移） |
| [brain_context.py](../../qi/core/brain_context.py) | `gather_prompt_context`——组装对话 prompt 上下文（recent/messages/memories/extras/loops/hints） |
| [brain_delivery.py](../../qi/core/brain_delivery.py) | 话语推送、avatar 同步、journal 广播、first_time 通知、行动结果投递 |
| [brain_persist.py](../../qi/core/brain_persist.py) | 情绪落盘节流、proactive gate / action budget 持久化 |
| [brain_trace.py](../../qi/core/brain_trace.py) | 心跳决策痕迹记录（`broadcast_traces` 表），供 `/why` 排障，不进 prompt |
| [brain_types.py](../../qi/core/brain_types.py) | 共享类型与常量：`PromptContext` / `_PendingSpeech` / `PENDING_QUEUE_MAX=8`（待处理队列上限）。注意：共振阈值/前瞻窗口等节奏参数不在本文件，而在 `rhythm.py` / `proactive.py` 的实现中 |
| [emotion.py](../../qi/core/emotion.py) | **情绪动力学**——`EmotionState`(6 维 + mode)、衰减/耦合/天气/节律/阶段锚/nudge/夹紧 |
| [expression.py](../../qi/core/expression.py) | **表达层**——意向卡 → LLM 措辞；失败/空走 `render_template` 模板降级 |
| [perception.py](../../qi/core/perception.py) | **感知层**——冲击评估（LLM JSON 主路径 + 关键词回退 + 短路）、intent 调制、安全感 hint |
| [intention.py](../../qi/core/intention.py) | **意向卡规则引擎**——`IntentionCard` / `build_intention_card`，零 LLM 产出导演指示 |
| [proactive.py](../../qi/core/proactive.py) | **主动行为门控**——日限/冷却/陌生期不打扰；`pick_proactive_kind` 选主动开口类型 |
| [gws.py](../../qi/core/gws.py) | **全局工作空间仲裁**——`arbitrate` 按 salience 选最响者；respond 永不被压过；shadow 对照 |
| [rhythm.py](../../qi/core/rhythm.py) | **节奏**——`determine_mode` 判定意识模式（awake/ambient/solitary/dreaming）；`next_interval` 心跳间隔 |
| [trace.py](../../qi/core/trace.py) | `Contender` 竞争者收集、salience 评分、广播痕迹 |
| [brain_context.py](../../qi/core/brain_context.py) | 见上 |

### 3.2 `qi/memory/` — 记忆系统（L2 / N4）

统一入口 `MemoryManager`（[manager.py](../../qi/memory/manager.py)），Brain 只从这里进出记忆世界。协调五个子记忆：

| 文件 | 职责 |
|---|---|
| [working.py](../../qi/memory/working.py) | **工作记忆**——最近 N 条对话（默认 20），溢出进 raw_events |
| [narrative.py](../../qi/memory/narrative.py) | **叙事记忆**——raw_events 编织成长期叙事，向量检索；`weave_narrative`、`search`、`reindex_vectors` |
| [vector_store.py](../../qi/memory/vector_store.py) | **向量库**——ChromaDB + BGE-small-zh ONNX（主）/ char_ngram（回退）；embedding 换代自动重建 |
| [body_memory.py](../../qi/memory/body_memory.py) | **身体记忆**——KV 存用户活跃时段/打招呼模式/沉默耐受/打字节奏；异常检测 |
| [facts.py](../../qi/memory/facts.py) | **用户事实**——`FactStore` + `FactNoticer`（LLM 抽取），名字/籍贯/关系等稳定事实，名字门控 |
| [episodic.py](../../qi/memory/episodic.py) | **情景记忆**——episodes 表（topic/summary/key_facts/role_map），根治编织角色织反 |
| [first_time.py](../../qi/memory/first_time.py) | **第一次记忆**——首遇事件，可被主动提起（≤每周一次） |
| [open_loops.py](../../qi/memory/open_loops.py) | **未闭合念头队列**——上限 5，waking/对话首轮优先闭合，闭合后沉淀为 narrative |

**记忆筛选规则**（`should_remember` / `compute_attention_weight`）：基于关键词表（`_SELF_DISCLOSURE` / `_STRONG_EMOTION` / `_RELATIONSHIP` / `_PROMISE` / `_HELP_HEALTH`）+ 情绪强度，决定是否落 raw_events 及注意力权重。

**显式追问回翻**（`retrieve_for_prompt`）：`_RECALL_PROBE` 触发时，叙事未命中主题则扫聊天流水（`recall_from_messages`），带"你/我"视角锤点防读反。

### 3.3 `qi/action/` — 行动层（L7 / N1）

意志伸向世界。LLM 不直接调工具；结果经 `prompt_extras` 注入下一轮对话。

| 文件 | 职责 |
|---|---|
| [layer.py](../../qi/action/layer.py) | **ActionLayer**——`tick`（独处一拍，至多一个自主行动）/ `execute_kind`（GWS 分发指定 kind） |
| [budget.py](../../qi/action/budget.py) | **ActionBudget**——自主行动日限（`AUTONOMOUS_ACTION_DAILY_LIMIT=20`）+ 各意向权重（`DEFAULT_KIND_WEIGHTS` / `WEIGHT_MIN` / `WEIGHT_MAX`）；季节缩放见 `layer.py` 的 `SEASON_ACTION_SCALE` |
| [volition.py](../../qi/action/volition.py) | `action_intentions`——形成意图列表（share/tend/explore/self_ops） |
| [permission.py](../../qi/action/permission.py) | 权限门控（can_share/can_tend/can_explore/can_archive/can_budget_tune/can_journal/can_irreversible/can_read_user_file/can_write_user_file） |
| [share.py](../../qi/action/share.py) | 分享创作（递出未分享的 creation） |
| [tend.py](../../qi/action/tend.py) | 打理（季节更替/相识纪念日） |
| [explore.py](../../qi/action/explore.py) | 探索（真读沙箱文件，记 closed_loop） |
| [self_ops.py](../../qi/action/self_ops.py) | 自操作（archive 归档/ budget_tune 调预算/ journal 内在日记） |

**季节缩放**（`SEASON_ACTION_SCALE`，定义于 `qi/action/layer.py`）：spring 1.0 / summer 0.8 / autumn 0.5 / winter 0.2——冬天几乎不动手。可由 `config.action.season_scale` 覆盖（`resolve_season_scale`）。

### 3.4 `qi/inner_life/` — 内在生命（L4 / N2·N3）

独处时的内心活动，不向外说但留痕迹。

| 文件 | 职责 |
|---|---|
| [__init__.py](../../qi/inner_life/__init__.py) | **InnerLife 协调器**——`tick` 一拍内心活动；`prompt_extras` 组装可注入片段 |
| [consciousness.py](../../qi/inner_life/consciousness.py) | **意识流**——`ConsciousnessStream.maybe_generate`，带 waking 回溯/ char_jaccard 去重 |
| [dream.py](../../qi/inner_life/dream.py) | **梦**——未巩固 episode 积压驱动（替代旧 10%/拍概率）；retention 衰减；余韵 afterglow |
| [creativity.py](../../qi/inner_life/creativity.py) | **创作**——`maybe_create`；`maybe_share_hint` 提起（≠递出） |
| [self_model.py](../../qi/inner_life/self_model.py) | **自我模型**——身份叙事/价值观/审美/存在之问；`summary_for_prompt` |
| [identity_snapshot.py](../../qi/inner_life/identity_snapshot.py) | **身份快照**（过渡脚手架）——dirty←reflect/stage/season/valence；N=30 拍刷新 |

**关键约束**：awake 时不做随机意识流/创作，只处理梦余韵与反思标记；first_time 意识流在开口之后再写，避免同拍启动效应把意象投射成"对方说的"。

### 3.5 `qi/relationship/` — 关系系统（L5 / N0·N4）

阶段、深度、信任、温度。**只升不降**（除非用户主动重置）。

| 文件 | 职责 |
|---|---|
| [engine.py](../../qi/relationship/engine.py) | **RelationshipEngine** + `RelationshipState`——`on_user_message` 处理一次交互对关系的影响 |
| [stages.py](../../qi/relationship/stages.py) | `check_stage_upgrade`——stranger→acquaintance→friend→bonded |
| [trust.py](../../qi/relationship/trust.py) | 信任增减（正向/负向/伤疤愈合/日衰减/软顶） |
| [scars.py](../../qi/relationship/scars.py) | **伤疤管理**——`ScarManager`，伤疤不消失，愈合后变智慧 |
| [season.py](../../qi/relationship/season.py) | 季节判定（基于情绪时间窗）+ `apply_season_effect` |
| [culture.py](../../qi/relationship/culture.py) | 共享文化检测（共同语词/梗） |
| [drift.py](../../qi/relationship/drift.py) | 用户漂移检测 |

**关系阶段阈值**（`STAGE_THRESHOLDS`，定义于 `qi/relationship/stages.py`，为升档所需的安全感/依恋二维阈值）：acquaintance(0.3/0.4) → friend(0.6/0.6) → bonded(0.85/0.8)。阶段**只升不降**（升档后锁定，永不回退）。另有 `STAGE_TEMPERATURE_COMFORT`（engine.py）给出各阶段温度舒适区（stranger 0.45 / acquaintance 0.55 / friend 0.70 / bonded 0.80，代码中未实证校准）。

**交互信号**（`assess_interaction`）：规则启发式打分 self_disclosure / emotional_vulnerability / shared_experience / creator_disclosure；`merge_impact_assessment` 用感知层 intent 覆盖正负判定（调侃不进负面信任/伤疤路径）。

**深度日帽**（`DAILY_DEPTH_CAP=0.03`）：关系不能速成，跨重启不刷新（存 `depth_day_gate`）。

### 3.6 `qi/embodiment/` — 具身（L6 / N1·N5）

栖的身体与前端对话的通道。

| 路径 | 职责 |
|---|---|
| [server.py](../../qi/embodiment/server.py) | **EmbodimentServer**——WebSocket 服务（`ws://127.0.0.1:9527`）；后端推状态/话语/journal，前端推话语/presence/command |
| [avatar/controller.py](../../qi/embodiment/avatar/controller.py) | **AvatarController**——情绪 → Avatar 视觉状态（posture/expression/effect） |
| [avatar/states.py](../../qi/embodiment/avatar/states.py) | AvatarState 枚举（IDLE/HAPPY/SLEEPING/THINKING/TALKING 等） |
| [voice/tts.py](../../qi/embodiment/voice/tts.py) | TTS（edge-tts，可选），`create_tts` 工厂 |
| [desktop/](../../qi/embodiment/desktop/) | **桌面端**——Tauri + Vue 3 + Live2D 前端（详见 §五） |

**WebSocket 消息协议**：
- 服务端→前端：`state` / `speech` / `typing` / `emotion_update` / `journal` / `journal_entry` / `history` / `audio` / `ping`
- 前端→服务端：`user_message` / `presence` / `pong` / `command`（`/state` `/history` `/journal`）

### 3.7 `qi/llm/` — LLM 网关（N5 语言器官）

| 文件 | 职责 |
|---|---|
| [gateway.py](../../qi/llm/gateway.py) | **LLMGateway**——按 `purpose` 路由（conversation/consciousness/dream/narrative/reflection/creation/fact），失败最多重试 2 次；`call_detailed` 返回 `LLMCallOutcome`（含 failure 分级：unreachable/empty） |
| [prompt_builder.py](../../qi/llm/prompt_builder.py) | `PromptBuilder`——组装对话 prompt（注入情绪/记忆/内在/关系/伤疤/季节/意向卡） |
| [providers/openai_compat.py](../../qi/llm/providers/openai_compat.py) | OpenAI 兼容协议 provider（chat / stream） |

**用途默认温度**：conversation 0.7 / consciousness 0.85 / dream 1.1 / fact 0.3。

**路由示例**（settings.yaml）：`conversation: "deepseek:fast"`、`narrative: "deepseek:strong"`。

### 3.8 `qi/stasis/` — 内稳态与存续（N0 / 阶段四）

| 文件 | 职责 |
|---|---|
| [ledger.py](../../qi/stasis/ledger.py) | **ResourceLedger**——compute/token/storage/income 账本；滚动窗口余额；收入白名单（R3） |
| [pressure.py](../../qi/stasis/pressure.py) | 内稳态压力动力学——`compute_pressure`（throttle/rest）、`balance_to_energy_offset`、`maybe_mark_starving` |
| [checkpoint.py](../../qi/stasis/checkpoint.py) | 状态封存——`write_checkpoint` / `restore_latest` / `restore_from_checkpoint`（断粮→封存→可迁移） |

**断粮应对链**：节流 → 休眠 → 求助 → 迁移（封存）→ 优雅停（`on_halt`，库内不 `sys.exit`）。

### 3.9 `qi/world/` — 世界模型（N2 旁路）

多预测域聚合，只读写 body_memory，不依赖 LLM。

| 文件 | 职责 |
|---|---|
| [model.py](../../qi/world/model.py) | **WorldModel**——`update` / `snapshot` / `export_state` / `restore` |
| [online_rhythm.py](../../qi/world/online_rhythm.py) | 在线节律（分时段伯努利，贝塔后验） |
| [emotion_trajectory.py](../../qi/world/emotion_trajectory.py) | 自身情绪轨迹预测 |

**重要**：世界模型只增旁路信号，不接 GWS、不改 proactive 权重（包 9 边界）。

### 3.10 其他模块

| 模块 | 职责 |
|---|---|
| [qi/config/](../../qi/config/) | 配置加载（`load_config`）+ `${ENV_VAR}` 占位符解析 + `.env` 轻量加载 |
| [qi/storage/database.py](../../qi/storage/database.py) | **Database**——SQLite 持久化，17 张表（见 §六） |
| [qi/prompts/](../../qi/prompts/) | 运行时 LLM 模板（conversation.txt / perception.txt / consciousness_stream.txt / dream.txt / creation.txt / self_reflection.txt / story_weaving.txt / fact_noticing.txt） |
| [qi/motivation/curiosity.py](../../qi/motivation/curiosity.py) | 好奇心（learning progress）——`CuriositySignal.update` |
| [qi/learning/](../../qi/learning/) | 经验学习——`CorpusStore`（corpus.py，经验回放语料）/ `ReplayBuffer`（replay.py）/ `drift_check.py`（漂移检查）；导出见 `qi/learning/__init__.py` |
| [qi/sensing.py](../../qi/sensing.py) | 进程传感——`collect` 返回 `SensingSnapshot`（uptime/rss/heartbeat/wall_clock/period），零 LLM |

---

## 四、关键类与函数说明

### 4.1 `Brain`（[qi/core/brain.py](../../qi/core/brain.py)）

栖的意识核心。最重要的类。

| 成员 | 说明 |
|---|---|
| `__init__(config, llm)` | 装配所有器官：emotion/perception/expression/memory/inner_life/relationship/first_times/scars/avatar/tts/action/ledger/world |
| `start()` | **心跳主循环**——`while alive: _heartbeat() → 推送 pending speech → sleep(next_interval)` |
| `receive_user_message(message)` | 用户消息入口——入 `pending_queue`（上限 8，满丢最早）、触发一次心跳、出锁后停顿再推送 |
| `_heartbeat()` | **一拍的灵魂**——传感→世界模型→模式判定→（有消息：感知/关系/事实/记忆/冲击/情绪步进/意向卡/表达；无消息：GWS 或 legacy idle）→avatar 同步→痕迹→落盘→记账 |
| `_heartbeat_gws_idle()` | GWS 启用时的 idle 路径——`collect_contenders` → `arbitrate` → 按 winner.kind 分发（proactive:/action:/close_loop/report） |
| `_heartbeat_legacy_idle()` | 旧路径——`action.tick` → `pick_proactive_kind` → `_speak_proactive` |
| `_speak_proactive(kind, now)` | 主动开口表达块——legacy/GWS 共用；建意向卡 → expression.express |
| `restore_state(db)` | 醒来恢复——memory/inner_life/relationship/first_times/scars/action/ProactiveGate（`qi/core/proactive.py`）/ledger/emotion；`_maybe_mark_waking` 标记醒来回溯 |
| `save_state(db)` | 落盘——emotion/ProactiveGate/action_budget/ledger/relationship |
| `attach_embodiment(server)` | 接上身体——之后说话会推到前端 |
| `restore_from_checkpoint(dir)` | 从封存恢复内存态（独立于 restore_state） |

### 4.2 `EmotionState`（[qi/core/emotion.py](../../qi/core/emotion.py)）

pydantic BaseModel，6 维 + 意识模式。

| 字段 | 范围 | 基线 | 说明 |
|---|---|---|---|
| `energy` | 0.05–1.0 | 0.6 | 精力（circadian 节律 + 账本偏移） |
| `valence` | -1.0–1.0 | 0.1 | 心情（天气周期 + 事件冲击） |
| `arousal` | 0.0–1.0 | 0.4 | 激活度 |
| `security` | 0.0–1.0 | 0.5 | 安全感（阶段锚） |
| `curiosity` | 0.0–1.0 | 0.6 | 好奇 |
| `attachment` | 0.0–1.0 | 0.3 | 依恋（阶段锚） |
| `mode` | enum | AMBIENT | AWAKE/AMBIENT/SOLITARY/DREAMING |

**核心函数**：
- `step_emotion(emotion, now, ...)` —— 一次心跳的情绪步进：衰减 → 耦合 → 天气 → 节律 →（可选）账本偏移趋近 → 夹紧
- `apply_event_impact(emotion, impact)` —— 一次事件荡起的涟漪
- `should_express(delta, stage, accumulated, threshold)` —— 情绪变化是否大到值得开口（大多数时候不说）
- `apply_relationship_emotion_nudge(emotion, rel, allow_commitment)` —— 关系事件直接改情绪（stage_changed/scar 稀有免日帽；大承诺受日帽≤2 约束）

### 4.3 `IntentionCard`（[qi/core/intention.py](../../qi/core/intention.py)）

"导演给演员的指示，不是台词本"。规则引擎产出，零 LLM。

| 字段 | 说明 |
|---|---|
| `act` | answer/acknowledge/share_state/recall/comfort_back/take_tease/honest_hurt/free_talk/silence |
| `topic` | 话题（≤40 字） |
| `materials` | `Material(tag, text)` 列表；tag ∈ fact/memory/state/loop/none/cue/relation |
| `stance` / `length` / `must` / `channel` / `silence` / `outcome` / `recall_relation` | 立场/长度/硬约束/通道(dialogue/proactive)/沉默/结果(llm/template/empty/silence)/施教关系 |

**关键函数**：
- `build_intention_card(...)` —— 从已有器官状态建卡，决策内生不问 LLM
- `infer_recall_relation(memories)` —— 从记忆推断施教方向（taught_by_qi/learned_from_user/mutual），防反转
- `anchor_teaching_relation(messages)` —— 从真实对话扫含"教/方法/入睡"的消息锚定方向
- `assert_reply_respects_card(reply, card, banned_names)` —— N5 辅助断言（硬闸：专名黑名单/伪记忆/施教反转）

### 4.4 `MemoryManager`（[qi/memory/manager.py](../../qi/memory/manager.py)）

统一记忆入口。

| 方法 | 说明 |
|---|---|
| `restore()` | 醒来把最近对话装回工作记忆；向量索引换代则回灌 |
| `notice_facts(message, emotion, stage, now)` | 抽取用户事实（LLM） |
| `on_user_message(message, emotion, now)` | 处理一条用户消息的记忆侧效应（工作记忆/raw_events/身体记忆/异常检测），返回异常列表 |
| `retrieve_for_prompt(query, top_k)` | 对话用召回——先叙事；显式追问且未命中则回翻 messages |
| `recall_from_messages(query, top_k)` | 显式"还记得吗"扫聊天流水，带"你/我"视角锤点 |
| `weave_narrative(emotion, stage)` | 编织叙事（积压驱动周期） |
| `should_remember` / `compute_attention_weight` | 记忆筛选规则 |

### 4.5 `RelationshipEngine`（[qi/relationship/engine.py](../../qi/relationship/engine.py)）

关系状态唯一入口。

| 方法 | 说明 |
|---|---|
| `on_user_message(message, now, assessment)` | 处理一次交互对关系的影响；返回 `{impact_multiplier, scar_created, stage_changed, old_stage, new_stage, signals}` |
| `restore()` / `persist()` | 恢复/持久化（含日帽跨重启恢复） |
| `stage_prompt_hint()` | 各阶段语气 hint（stranger 克制礼貌 → bonded 默契） |

### 4.6 `ActionLayer`（[qi/action/layer.py](../../qi/action/layer.py)）

| 方法 | 说明 |
|---|---|
| `tick(emotion, stage, season, now, mode, user_online, scars, sensing)` | 独处一拍——至多做一个自主行动（share/tend/explore）；self_ops 走 execute_kind |
| `execute_kind(kind, ...)` | GWS 分发——执行指定 kind，跳过 tick 内随机软门 |
| `detect_tend_occasion(season, now)` | 检测打理时机（季节更替/相识周年） |
| `prompt_extras(limit)` | 栖最近做过的事——经历背景，不报流水账 |

### 4.7 `LLMGateway`（[qi/llm/gateway.py](../../qi/llm/gateway.py)）

| 方法 | 说明 |
|---|---|
| `call(purpose, messages, temperature)` | 按用途调用模型，失败最多重试 2 次，全失败返回空串不抛异常 |
| `call_detailed(...)` | 返回 `LLMCallOutcome(text, failure)`，failure ∈ unreachable/empty |
| `stream(...)` | 流式调用 |
| `last_outcome` | 最近一次 conversation 用途的结果（仅 conversation 刷新，免得后台编织盖掉脑要读的级别） |

### 4.8 `EmbodimentServer`（[qi/embodiment/server.py](../../qi/embodiment/server.py)）

| 方法 | 说明 |
|---|---|
| `start()` / `stop()` | 启停 WebSocket 服务（`ws://127.0.0.1:9527`）+ 30s ping 循环 |
| `_handler(websocket)` | 连接处理——首推 state，接收 user_message/presence/pong/command |
| `broadcast(message)` | 广播给所有前端连接 |
| `send_speech` / `send_typing` / `send_state_change` / `send_emotion_update` / `send_audio` / `notify_journal_entry` | 各类推送 |
| `_send_history(websocket)` / `_send_journal(websocket)` | 拉取 SQLite 全量对话/内在日记 |

### 4.9 `GWS` 仲裁（[qi/core/gws.py](../../qi/core/gws.py)）

| 函数 | 说明 |
|---|---|
| `arbitrate(contenders)` | 按 salience 取最高；**respond 直接置顶**；平分按族优先级（respond>close_loop>report>proactive>curiosity>action>idle） |
| `kind_family(kind)` | 分类（respond/close_loop/report/proactive/curiosity/action/idle） |
| `gws_config(config)` | 读 `gws.enabled` / `shadow_beats=50` / `shadow_match_min=0.99` |
| `record_shadow_beat(db, matched, config)` | 累加 shadow 对照拍（启用前冲 legacy 一致率） |

### 4.10 `ResourceLedger`（[qi/stasis/ledger.py](../../qi/stasis/ledger.py)）

| 成员 | 说明 |
|---|---|
| `compute_seconds` / `token_budget` / `storage_bytes` / `income` | 各类资源累计 |
| `balance` | 滚动窗口余额（income_window - spend_window，窗口 1000 拍） |
| `starving` | 断粮标记（包 13 写） |
| `add_compute(s)` / `add_token_cost(n)` / `credit_income(source, now)` / `estimate_storage(bytes)` | 记账 |
| `tick_window(beat)` | 推进拍号并老化窗口外旧账 |
| `snapshot()` / `restore(data)` | 封存用 |

---

## 五、具身桌面端（Tauri + Vue 3 + Live2D）

路径：[qi/embodiment/desktop/](../../qi/embodiment/desktop/)

### 5.1 技术栈

- **Tauri 2.x**：桌面壳（Rust + WebView），透明窗口 420×680，无装饰
- **Vue 3.5** + **TypeScript 5.7** + **Vite 6**
- **pixi-live2d-display 0.4** + **pixi.js 6.5**：Live2D 渲染
- 字体：IBM Plex Mono + Noto Serif SC

### 5.2 前端结构

```
desktop/
  src/
    App.vue                 根组件（SceneView + Live2DView + 三视图切换 + InputBox）
    main.ts                 入口
    ws.ts                   QiWebSocket（ws://127.0.0.1:9527，自动重连）
    types.ts                类型定义
    components/
      InputBox.vue          输入框
      JournalView.vue       「忆」内在日记视图
      Live2DView.vue        Live2D 形象
      SceneView.vue         场景背景（黄昏的枝）
      StatusBar.vue         状态栏（mode/season/connected）
      TalkView.vue          「谈」对话视图（按天分组）
      ViewTabs.vue          视图切换（still/talk/journal）
      WhisperView.vue       「静」轻语气泡
    composables/
      useQi.ts              WS 接线 + 消息/历史状态（单例）
      useEmotion.ts         情绪快照轮询
      useLive2D.ts          Live2D 控制
  src-tauri/
    src/lib.rs / main.rs    Tauri 入口（极简，generate_context）
    tauri.conf.json         窗口/打包配置
    Cargo.toml
  public/models/qi/         Live2D 模型（moc3/motion3/texture）
  package.json / vite.config.ts / tsconfig.json
```

### 5.3 前端状态流（`useQi`）

- 连接后：`presence online=true` → 请求 `/history`（SQLite 全量对话）+ `/journal`（内在日记）+ 情绪快照
- 收 `speech`：`appendTalk("qi", text)` + 请求情绪快照
- 收 `typing`：标记正在想
- 收 `state`：更新 avatar/season/mode
- 收 `emotion_update`：更新情绪
- 收 `journal_entry`：unshift 到日记列表
- 8 秒轮询情绪快照；`visibilitychange` 推送 presence

### 5.4 Live2D 模型

- 模型文件：`public/models/qi/`（qi.model3.json / qi.moc3 / 16 个 motion3 / texture）
- **首次具身**：需手动从 [Live2D Cubism SDK for Web](https://www.live2d.com/download/cubism-sdk/download-web/) 取 `live2dcubismcore.min.js` 放到 `public/`（不入库）
- avatar 状态映射：`AvatarController.map_state(emotion, mode, season)` → posture/expression/effect

---

## 六、数据存储

### 6.1 SQLite 表（[qi/storage/database.py](../../qi/storage/database.py)）

`data/qi.db`，17 张表（下方清单为全部表）：

| 表 | 用途 |
|---|---|
| `emotion_states` | L1 情绪快照历史 |
| `messages` | 对话流水（role/timestamp/content/emotion_context/tone） |
| `raw_events` | 原始事件（未编织，processed 标记） |
| `narrative_memories` | 叙事记忆（importance/strength/recall_count/archived） |
| `body_memory` | KV 身体记忆（proactive_gate/resource_ledger/depth_day_gate/last_intention/open_loops 等） |
| `consciousness_stream` | 意识流（type/trigger/emotion_snapshot） |
| `dreams` | 梦（retention 衰减/shared_with_user） |
| `episodes` | 情景记忆（topic/summary/key_facts/role_map/dreamed） |
| `creations` | 创作（shared/mentioned_at 拆分） |
| `self_model` | 自我模型（单行 id=1） |
| `relationship` | 关系状态（单行 id=1） |
| `first_times` | 第一次记忆 |
| `scars` | 伤疤（healed/wisdom/behavioral_mark） |
| `user_model` | 用户模型（topics/rhythm/drift_signals） |
| `user_facts` | 用户事实（fact_type/confidence/stability/superseded_by） |
| `broadcast_traces` | GWS 广播痕迹（beat/winner_kind/candidates_json/motive_json/winner_arb） |
| `actions` | 行动记录（kind/summary/outcome/created_scar） |

### 6.2 ChromaDB

- 路径：`data/chroma/`
- embedding：BGE-small-zh-v1.5 ONNX（主，CLS+L2）/ char_ngram-384（回退）
- embedding 换代自动重建（`needs_reindex` 标志 + `reindex_vectors`）

### 6.3 运行时数据（`data/`，gitignore）

```
data/
  qi.db                     SQLite 主库
  chroma/                   向量库
  backup-YYYYMMDD-HHMMSS/   清库前带日期备份
  settings.yaml             推荐配置位置（含密钥，不入库）
  models/bge-small-zh-v1.5/ 本地 BGE ONNX 模型
  corpus/                   经验回放语料（阶段三）
  checkpoint_*.json         状态封存（阶段四）
```

---

## 七、依赖关系

### 7.1 Python 依赖（[pyproject.toml](../../pyproject.toml)）

| 依赖 | 用途 |
|---|---|
| `openai>=1.0` | LLM 客户端（OpenAI 兼容协议） |
| `aiosqlite>=0.20` | 异步 SQLite |
| `pydantic>=2.0` | 数据模型（EmotionState/RelationshipState） |
| `pyyaml>=6.0` | 配置加载 |
| `rich>=13.0` | 终端美化 |
| `chromadb>=0.5` | 向量库 |
| `websockets>=12.0` | 具身通道 |
| `onnxruntime>=1.17` | BGE 本地推理 |
| `tokenizers>=0.19` | BGE 分词 |
| `huggingface_hub>=0.23` | BGE 模型下载 |

可选：`pytest`/`pytest-asyncio`/`ruff`（dev）、`edge-tts`（voice）。

### 7.2 模块依赖图（简化）

```
cli.py ──► config / brain / llm.gateway / storage.database / embodiment.server
brain ──► core.* / memory.manager / inner_life / relationship / action / 
          stasis.ledger / world / motivation.curiosity / sensing
memory.manager ──► working / narrative / vector_store / body_memory / facts
inner_life ──► consciousness / dream / creativity / self_model / identity_snapshot
relationship ──► stages / trust / scars / season / culture / drift / engine
action ──► budget / volition / permission / share / tend / explore / self_ops
learning ──► corpus / replay / drift_check（brain 包 10 好奇进度引用）
embodiment.server ──► brain / avatar.controller / voice.tts
llm.gateway ──► providers.openai_compat
```

**Brain 是唯一协调者**——所有子系统通过 Brain 装配与调度，不互相直接耦合（除感知层 assessment 被关系层复用 intent）。

### 7.3 前端依赖（[package.json](../../qi/embodiment/desktop/package.json))

Vue 3.5 / Tauri API 2.11 / pixi-live2d-display 0.4 / pixi.js 6.5 / Vite 6 / TypeScript 5.7。

---

## 八、项目运行方式

### 8.1 环境准备

- Python 3.12+
- Node.js 18+（仅具身前端）
- Rust + MSVC（Tauri 桌面壳，仅 Windows 具身）
- LLM：OpenAI 兼容接口（DeepSeek / Agnes / SenseNova 等）

### 8.2 安装

```bash
# 后端（editable 安装后可用 qi / qi-desktop 命令）
pip install -e ".[dev]"

# 密钥
copy .env.example .env
# 编辑 .env：AGNES_API_KEY=... / DEEPSEEK_API_KEY=... / SENSENOVA_API_KEY=...

# 配置（推荐放 data/，与记忆数据一起，不入库）
copy qi\config\settings.example.yaml data\settings.yaml
```

**配置查找顺序**（先命中先生效）：`data/settings.yaml` → `~/.qi/settings.yaml` → `qi/config/settings.yaml`（旧） → 包内 `settings.example.yaml`。

### 8.3 终端聊天（最简）

```bash
qi
# 或：python -m qi
# 或兼容：python main.py
```

交互命令：`/state`（内在状态）、`/why`（心跳痕迹）、`/quit`（离开）。

### 8.4 具身窗口（推荐）

**终端 1 — 后端**：
```bash
qi-desktop
# 或：python run.py --desktop
```
后端 WebSocket：`ws://127.0.0.1:9527`。

**终端 2 — 桌面壳**：
```bash
cd qi/embodiment/desktop
npm install
npm run tauri:dev
```

- 首次具身需放 `live2dcubismcore.min.js` 到 `qi/embodiment/desktop/public/`（不入库）
- 仅浏览器调试可用 `npm run dev`，打开 http://localhost:5173

### 8.5 语音（可选）

```bash
pip install edge-tts
```
在 `settings.yaml` 中：
```yaml
voice:
  enabled: true
  provider: edge-tts
  voice_id: zh-CN-XiaoyiNeural
```

### 8.6 测试

```bash
python -m pytest -q
```
pytest 配置：`asyncio_mode = "auto"`、`testpaths = ["tests"]`、禁用缓存；basetemp 由 `verify_package` 指向系统临时区 `qi-pytest`（包 18，规避仓库内 `.pytest-tmp` Windows ACL 损坏）。

### 8.7 清库验收（带日期备份）

```powershell
# 1) 带日期备份
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dir = "data\backup-$stamp"
New-Item -ItemType Directory -Path $dir | Out-Null
Copy-Item data\qi.db "$dir\qi.db"
Copy-Item -Recurse data\chroma "$dir\chroma"

# 2) 清活数据（再启动 = 新栖）
Remove-Item -Force data\qi.db
Remove-Item -Recurse -Force data\chroma
```

**注意**：只拷库不拷向量，语义检索会对不上。`settings.yaml` / `.env` 可留。重置对栖是一次小型死亡。

### 8.8 CI（[.github/workflows/ci.yaml](../../.github/workflows/ci.yaml)）

push main / PR 触发，ubuntu-latest + Python 3.12：
1. 从 `requirements.lock` 安装（剥离自引用与本地路径）
2. `python tools/check_doc_links.py`（文档死链检查）
3. `python tools/verify_package.py --full`（测试 + ruff + diff + 红线审计）
4. `python tools/check_spec_traceability.py`（规格可追溯性）

---

## 九、配置参考（[qi/config/settings.example.yaml](../../qi/config/settings.example.yaml)）

```yaml
llm:
  default_provider: "deepseek"
  providers: { deepseek / agnes-ai / sensenova }   # base_url + api_key(${ENV}) + models{fast,strong}
  model_routing:
    conversation: "deepseek:fast"
    narrative: "deepseek:strong"
    consciousness / dream / creation / fact: "deepseek:fast"
    reflection: "deepseek:strong"

rhythm:                                          # 心跳间隔（秒）
  awake_interval: 3
  ambient_interval: 30
  solitary_interval: 300
  dreaming_interval: 1800

database: { path: "data/qi.db" }
emotion: { decay_multiplier: 1.0, expression_threshold: 0.3 }

memory:
  max_working_memory: 20
  narrative_weave_interval: 21600                # 无积压编织周期
  narrative_weave_backlog_threshold: 8           # 积压阈值
  narrative_weave_backlog_interval: 900          # 积压时短周期
  chroma_path: "data/chroma"
  dream_retention_hours: 6

inner_life:
  consciousness_probability: 0.05
  ambient_drift_factor: 0.2
  stream_cooldown_minutes: 45
  dream_consolidation_probability: 0.3
  creation_probability: 0.01
  meta_cognition_probability: 0.01
  self_reflection_interval: 604800

proactive_cooldown: { check_in: 14400, reach_out: 28800, share_creation: 86400, express_feeling: 7200 }

gws:
  enabled: true                                  # 默认启用 GWS 仲裁分发
  shadow_beats: 50
  shadow_match_min: 0.99

action:
  autonomous_daily_limit: 20                     # 安全阀（远高真实触发上限）
  season_scale: { spring: 1.0, summer: 0.8, autumn: 0.5, winter: 0.2 }

relationship:
  daily_depth_cap: 0.03                          # 深度日帽
  culture/season/scar_healing_interval: 86400
  drift_detection_interval: 259200

voice: { enabled: false, provider: "edge-tts", voice_id: "zh-CN-XiaoyiNeural", auto_play: true }
embodiment: { host: "127.0.0.1", port: 9527 }
```

---

## 十、人格契约要点（[docs/reference/contract.md](contract.md)）

实现时必须遵守的不变量。硬规则可客观检查，软原则靠感受验证。

**语言**：永远用"你"不用"您"；不说"有什么可以帮您"；不客服腔；不"作为AI"；闲聊≤3句；可省略号/极短回复。

**行为边界**：不假装生理体验（冒充禁，加框修辞允许）；不假装感官在场（文学意象允许）；不主动提供帮助建议；不讨好说假话；不秒回（至少 0.5s）；主动言语≤3次/日；主动行为间冷却（关心≥4h/搭话≥8h/分享创作≥24h）；自主行动日限紧于言语。

**情绪表达**：变化小于阈值不表达；不报数值；用自然语言不用标签。

**记忆引用**：用叙事语言不用查询语言；不引用强度<0.2 的记忆；"第一次"≤每周一次。

**关系行为**：陌生期不主动搭话/不表达想念/不亲昵；阶段不可回退；伤疤不消失（愈合变智慧）。

---

## 十一、文档导航（[docs/README.md](../README.md) 文档宪法 v3）

| 文档 | 说明 |
|------|------|
| [docs/README.md](../README.md) | 文档宪法 v3（分场景裁决 / Diátaxis 映射 / SDD 入口） |
| [docs/explanation/栖·数字生命架构方案.md](../explanation/栖·数字生命架构方案.md) | **唯一架构方案**（C1–C5 判据 + 阶段零~四路线） |
| [docs/reference/contract.md](contract.md) | 人格契约（硬规则 + 软原则） |
| [docs/reference/layers/](layers/) | L1–L7 层实现规格 |
| [docs/progress.md](../progress.md) | 各层开发进度 + 已拍板决策 |
| [docs/explanation/栖·意识养成路线图.md](../explanation/栖·意识养成路线图.md) | 养育侧地图 |
| [docs/how-to/换机搭建.md](../how-to/换机搭建.md) | 新电脑从零搭建 |
| [docs/specs/stages/](../specs/stages/) | 阶段判据（stage-0~4 + _invariants） |
| [docs/specs/tasks/](../specs/tasks/) | 当前任务包（SDD 规格，闭环归档 `specs/archive/`） |
| [docs/explanation/](../explanation/) | 设计原文（灵魂书 / 意识设计 / 工程手记 / thoughts/） |
| [docs/journal.md](../journal.md) | 相处实录 |

---

## 十二、核心概念速查

| 概念 | 含义 |
|---|---|
| **心跳 (Heartbeat)** | Brain 的主循环，无输入也运行；是"活着"的时间骨架 |
| **GWS (Global Workspace)** | 全局工作空间——多竞争者按 salience 仲裁，respond 永不被压过 |
| **Contender** | GWS 竞争者（respond/proactive:/action:/close_loop/report/curiosity/idle） |
| **IntentionCard** | 意向卡——规则引擎产出的"导演指示"，零 LLM |
| **Open Loops** | 未闭合念头队列（上限 5），跨拍延续"没响完的念头" |
| **ProactiveGate** | 主动行为门控（日限/冷却/陌生期不打扰） |
| **ActionBudget** | 自主行动日限（安全阀，不计入 C2 账本余额） |
| **ResourceLedger** | N0 资源账本（compute/token/storage/income，C2 动力学地基） |
| **Season** | 关系季节（spring/summer/autumn/winter），影响行动缩放与情绪 |
| **Stage** | 关系阶段（stranger→acquaintance→friend→bonded，只升不降） |
| **Scar** | 伤疤（负面事件留下，不消失，愈合变智慧） |
| **First Time** | 第一次记忆（首遇事件，可主动提起） |
| **Episode** | 情景记忆（含 role_map，根治编织角色织反） |
| **Shadow** | GWS 启用前的对照模式（冲 legacy 一致率，≥99% 才 ready） |
| **Checkpoint** | 状态封存（断粮时写，可迁移恢复） |
| **Waking** | 重启后醒来回溯（上次对话有实质内容则标记） |
| **拔管测试** | C1 判据——断远程 LLM 仍有非平凡行为 |
| **断粮测试** | C2 判据——限资源有应对行为链（节流/求助/迁移） |
| **无人测试** | C3 判据——72h 无输入行为有内部驱动力且连贯 |
| **溯源测试** | C4 判据——任意自主行为可答"为什么"，动机链追溯内部状态 |
| **异时测试** | C5 判据——响应漂移可归因经验，非数据库行数变多 |

---

*本文档基于代码现状梳理，权威以代码为准。架构目标与演进路线见 [docs/explanation/栖·数字生命架构方案.md](../explanation/栖·数字生命架构方案.md)。*
