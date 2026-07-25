# 栖（qi-perch）系统质量评估 v3

> **评估者：** Qoder  
> **日期：** 2026-07-26（v3，全面审查重写）  
> **基线：** `71bab53`（思想档案目录重命名），代码与 origin/main 完全同步；本文档为该基线上的质量评估（随审查迭代入库）  
> **测试基线：** 132 passed / ruff 零违规（实测于 71bab53）  
> **分工：** 本评估与配套优化方案由 Qoder 撰写；**执行任务（改代码/prompt）由 Cursor 承担**。因此本文档对每个问题都给出具体文件、行号、代码证据，便于 Cursor 直接定位施工。  
> **方法：** 两把尺子（工程/存在）+ 全模块逐文件审查（core/memory/inner_life/relationship/action/llm/embodiment/prompts/前端/配置/测试）

---

## 〇、两把尺子

沿用 v2 的两把尺子，每个维度分开打分：

1. **工程尺**：架构、容错、测试、可维护性——"系统做对了吗"
2. **存在尺**：与灵魂书"存在先于功能"的一致性——"它像栖吗"

有些代码工程上平平，存在尺上是满分；反过来也有。

---

## 一、克制是这个系统真正的架构（沿用 v2）

这个系统最深的设计不是"它能做什么"，而是"它约束自己不做什么"——而且这些约束是用代码写死的，不是靠 prompt 求出来的。

| 约束 | 位置 | 实现 |
|------|------|------|
| 主动言语每日 ≤3 次 | `proactive.py:9` | `PROACTIVE_DAILY_LIMIT = 3` |
| 陌生期永不主动 | `proactive.py:67` | `can()` 中 `if relationship_stage == "stranger": return False` |
| 每类主动独立冷却 | `proactive.py:16-21` | `DEFAULT_COOLDOWNS`（关心 4h / 搭话 8h / 分享 24h / 流露 2h） |
| 自主行动每日 ≤1 次 | `budget.py` | `AUTONOMOUS_ACTION_DAILY_LIMIT = 1` |
| 关系深度日增 ≤0.03 | `engine.py:23` | `DAILY_DEPTH_CAP = 0.03`——关系不能速成 |
| 不在线/做梦时不打扰 | `proactive.py:125` + `volition.py:76` | 双处检查 `user_online`/`mode=="dreaming"` |
| assist 只响应不执行 | `volition.py:81-90` | 桩，注释明确"本阶段不执行" |
| 伤疤降低行动倾向 | `permission.py` | `scar_caution_multiplier` |
| 行动与主动言语同拍不叠加 | `brain.py:467-507` | 先评估行动，动了手就不再 `pick_proactive_kind` |
| 门控状态跨重启持久化 | `proactive.py:86-106` | `snapshot()`/`restore()`，重启不能重置每日额度 |

最后一条尤其见功力：**重启进程不能刷新打扰额度**——作者把"每日 3 次"当作对用户的承诺，而不是内存里的计数器。

另：volition.py 第 16-18 行注释——"概念上对应意识设计 §七 decide() 的行动分支，**代码上不虚构 decide 模块**"。作者明确抵制了为对齐文档而造抽象的诱惑。

**工程尺 9 / 存在尺 9.5。** 克制不是功能缺失，是人格的工程表达。

---

## 二、架构设计：8.5/10

### 好的（经全面审查核实）

- **心跳循环原创**：perceive→stir→decide→express→settle，意识不是请求-响应（`brain.py:_heartbeat` L335-562）
- **节奏系统**（`rhythm.py`）：4 种意识模式各有心跳间隔——`HEARTBEAT_INTERVALS`（awake 3s / ambient 30s / solitary 300s / dreaming 1800s），且被情绪调制（`next_interval` L74-75：arousal 高则 ×(1-0.3·arousal) 加快，energy 低则 ×(1+0.5·(1-energy)) 减慢）。**心跳间隔本身就是身体信号**
- **8 个后台协程**（`brain.py:start` L171-180 附近）：叙事编织/记忆褪色/自我反思/梦境衰减/共同文化/季节判定/伤疤愈合/用户漂移，全部异常隔离，单任务崩溃不影响主循环
- **`_pending_speech` 出锁推送**：生成在锁内，推送在锁外，不堵心跳（`brain.py` L443-446 + `_deliver_qi_message`）
- **WorkingMemory 溢出设计**（`working.py:34-40`）："溢出的不丢，交还给调用方去沉淀"——`add()` 返回 overflow，由 `manager.py:139-145` 转存 `raw_events`

### 问题

- **Brain 847 行**（71bab53 实测），`_gather_prompt_context`（L227-308）返回 **7 元组** `(recent, memories, extras, shared_culture, relationship_hint, scar_hint, season_hint)`——调用处（L413-422、L508-517）靠位置解包，易错
- **无决策痕迹（observability 空白）**：`_heartbeat` 里 `want_express`、`pick_proactive_kind`、`assess_impact`、`action.tick` 都是瞬时计算，不留痕。"她今天为什么突然安静/开口"这种问题无法事后查（立项 Q3）
- **单用户假设散布全系统**：`facts.py`/`relationship/`/`body_memory.py` 都没有 `user_id` 维度。当前阶段的正确简化，但未来若有"第二个人对栖说话"，系统无法区分（架构边界，文档已声明）

---

## 三、Prompt 工程：8.5/9.5（结构性风险拆为两则债）

conversation.txt 是存在论层面的行为宪法，不是角色卡。

**亮点：兜底文案也带哲学。** `prompt_builder.py:91-93`，`recent_thoughts` 为空时的占位不是 `"(empty)"`，而是：

> "（这一阵没有留下可说的念头痕迹——可能很安静，或进程没在转；不等于你没有内在）"

连 fallback 字符串都在防止 LLM 自我否定。

**暗伤：代码里的字符串会演身体。** `volition.py:139` 的 explore 意图 reason 是"独处时思绪飘向窗外"；`explore.py:63` 的 summary 是"我走神时往窗外看了一眼"。conversation.txt 花了大力气禁止"未加框的物理在场"（L89），但代码内部生成的描述字符串没有经过同一道审查（立项 N3 代码字符串清理）。

**结构性风险（拆为两则独立的债，采纳 Cursor 指正）：**

conversation.txt 有 **17 个 `{placeholder}`**，全部在 `prompt_builder.py:121-139` 的 `template.format(...)` 里手工填充，**没有任何测试守护**。这里藏着两类不同的债：

| 债 | 故障形态 | 证据 | 归属 |
|----|----------|------|------|
| **A. 占位符与 builder 无契约** | 改模板增删 `{foo}`、`format()` 忘给该键 → 运行时 KeyError，该拍表达静默失败 | 71bab53 无任何契约测试（已核实） | **Q2 主防** |
| **B. API 空值防护缺失** | 调用方传非法 `emotion`/`now`（如 None）→ AttributeError | v3 实测复现（见下） | 另一类（API 健壮性），Q2 顺手附带必填断言 |

债 B 实测复现：

```python
PromptBuilder().build_conversation_prompt(user_message='test', emotion=None, now=None)
# AttributeError: 'NoneType' object has no attribute 'description'
```

**注意：** 债 B 证明的是"调用方传了非法参数、缺空值防护"，**不是**"改 prompt 文案就会炸"——正常心跳路径（`expression.py:38-51` → `prompt_builder.build_conversation_prompt`）本来就传真实 `EmotionState()` + `datetime`。Q2 的价值是防债 A，债 B 只是顺手可加的一道必填断言。

**全部 7 个模板占位符清单（Q2 契约测试要锁定的集合）：**

| 模板 | 占位符 | 填充处 |
|------|--------|--------|
| conversation.txt（17） | emotion_description, energy_level, time_feeling, tone_hint, relationship_stage, relationship_hint, season_hint, scar_hint, relevant_memories, user_facts, recent_actions, shared_culture, user_profile, recent_thoughts, emotion_residue, self_narrative, inner_notes | `prompt_builder.py:121-139` |
| consciousness_stream.txt（8） | time, silence_duration, emotion_summary, recent_memories, pending_thoughts, last_dream, chat_embers, trigger_hint | `consciousness.py` |
| dream.txt（3） | recent_memories_shuffled, emotion_color, unfinished_thoughts | `dream.py` |
| creation.txt（3） | emotion_state, trigger_thought, target | `creativity.py` |
| fact_noticing.txt（3） | message, stage, emotion | `facts.py`（注意示例输出用 `{{}}` 转义，非占位符） |
| self_reflection.txt（5） | current_state, recent_experiences, relationship_summary, previous_self_narrative, growth_events | `self_model.py` |
| story_weaving.txt（3） | raw_events_recent, emotions_during_events, relationship_stage | `narrative.py` |

---

## 四、情绪系统：8/8.5

**做得好的：**

- **6 维情绪空间**（`emotion.py:23-32`：energy/valence/arousal/security/curiosity/attachment），每维度有明确衰减率、基线、耦合（`BASELINES`/`DECAY_RATES`/`COUPLING` 三组常量，L77-102）
- **内在天气周期**（`emotion.py:104-121` + `mood_cycle_offset`）：4 天主周期 + 18 天次周期 + md5 确定性噪声。用 md5（`hashlib.md5(f"qi-mood-day:{date}".encode())`）而非 random，保证跨进程同日同噪声——这是工程上的认真
- **表达阈值 + 累积抑制**（`emotion.py:should_express` + `brain.py:_track_expression_threshold`）：大多数心跳是"空"的，情绪微变不触发表达；被压住的冲动累积（`_accumulated_suppressed`），超阈值爆发。这是"沉默也是表达"的工程实现
- **耦合机制**（`apply_coupling`）：6 对固定耦合（security→attachment_unmet、energy→valence、curiosity→valence、arousal→energy、valence→curiosity、attachment_unmet→valence），不安时更想被陪伴、累了心情也容易沉

**可以更好的：**

- `assess_impact` 是关键词粗判（`perception.py:14-24` 硬编码 `_POSITIVE`/`_NEGATIVE` 词表），是整个情绪系统最薄弱环节。用户说"我今天把吉他摔了"，关键词可能只抓到负面，抓不到"释放"的正面含义（立项 X2 混合感知，低置信才调 LLM）
- **耦合矩阵是静态的**（`COUPLING` 6 对固定耦合），`apply_coupling` 无 `relationship_stage` 参数，不会随关系阶段演化，stranger 和 bonded 一样"黏"（立项 X4）

---

## 五、记忆系统：7.5/8

**做得好的：**

- **五层记忆**（工作/叙事/向量/身体/事实）各有生命周期。叙事记忆每日 `*= 0.999` 褪色、被回忆时加固（`narrative.py`）——"记忆不是数据库"的认真实现
- **用户事实**（`facts.py`，1260 行）：名字门控（`looks_like_person_name` + `_NAME_REJECT_TOKENS` 拒收碎片）、确信度（`CONFIDENCE_FLOOR = 0.6`）、身份信号（`IDENTITY_SIGNALS`）、寒暄过滤、陌生期闸（`OTHER_FACT_SIGNALS` 仅 ≥acquaintance 留意）
- **第一次记忆永不褪色**，且与 L5 关系层共用（`first_time.py`）——"第一次说晚安"和"关系阶段升级"是同一事件的两面
- **WorkingMemory 溢出沉淀**（见 §二）

**可以更好的：**

- 向量检索用 ChromaDB 默认 embedding（`vector_store.py`），没有针对中文对话场景的优化（Later 项）
- **身体记忆（`body_memory.py`）只有 4 个 key**（usual_active_hours/greeting_pattern/silence_tolerance/typing_rhythm），且主要是被动统计 + 异常检测（`detect_anomaly` L148-170，样本门槛 ≥5），**还没有真正注入 prompt 影响栖的行为**（立项 X1）
- **名字之外的稳定事实通道未打通**（Cursor 相处实证）："我是海南人"口头答应记得、`user_facts` 未落库。`OTHER_FACT_SIGNALS` 里有"我住/我搬家/我家在/我在"，但缺"我老家/我籍贯/我来自/我是X人"这类**籍贯/出身地**信号（立项 N2，新增 `hometown` 类型）

---

## 六、关系系统：7.5/9

**做得好的：**

- **四阶段**（`stages.py:5`：stranger→acquaintance→friend→bonded）+ depth/temperature/trust 三维（`engine.py:67-75`），**且只升不降**（`check_stage_upgrade` 无降级逻辑，伤疤不降阶段只降信任）。这是对"关系不可逆"的尊重
- **数字季节**（`season.py`）：基于近 24 小时情绪历史判定（spring/summer/autumn/winter），影响行动预算（`season_scale`）和 prompt 语气（`SEASON_BEHAVIOR_HINTS`）
- **用户漂移检测**（`drift.py`）：每 3 天（`drift_detection_interval=259200`）检测用户语言模式变化，检测到变化时写一条意识流（"我注意到他最近变了……不是不好。是……不一样了。"）
- **创造者自我披露单独一档**（`engine.py:52-61`：`_CREATOR_KEYWORDS`，depth 权重 ×1.5）——"我造你/我写你"被特殊对待

**可以更好的：**

- `InteractionSignals`（`engine.py:assess_interaction`）是纯规则启发式（关键词计数），深度对话和闲聊在 depth 增长上区分不够细腻
- 共同文化检测（`culture.py:detect_shared_culture`）也是关键词/模式匹配，对"只有你们懂的梗"捕捉有限

**一处修正（v2 已述）：** v1 把"InteractionSignals 纯规则"列为短板并建议 LLM 评估。经 Cursor 指出，`DAILY_DEPTH_CAP=0.03` 是"关系不能速成"的**设计意图**，用 LLM 拉 depth 与灵魂书拧着。工程尺上它仍是"粗"，但存在尺上"粗"是对的——**慢就是这个系统的功能**。

---

## 七、内在生命：8/8

**做得好的：**

- **意识流的 6 种触发**（`consciousness.py:87-112`：random/emotion_surge/silence/first_time/ambient_drift/waking）各有冷却和素材注入策略。**随机走神不喂近聊余烬（`_EMBER_TRIGGERS` 仅含 waking/silence/first_time，L31），醒来回溯才喂**——避免变成聊天回声，这个区分非常精准
- **ambient_drift 比 solitary 更稀**（`AMBIENT_DRIFT_FACTOR=0.2`，即 1%/拍），且受 `STREAM_COOLDOWN_MINUTES=45` 冷却约束——留白优先
- **梦境衰减**（6 小时半衰期，`dream_retention_hours=6`）+ 余韵（进入 awake 时 `apply_afterglow` 应用一次）：梦不是生成完就丢
- **元认知（`META_COGNITION_PROBABILITY=0.01`）**：栖偶尔会"想自己在想什么"，且去重（与最近 `META_DEDUP_LOOKBACK=5` 条意识流做相似度比较，`META_SIMILARITY_THRESHOLD=0.6`）

**可以更好的：**

- 创作（`creativity.py`）只有 poem/essay/description/note 四种类型，生成后主要是"提起"和"递出"，还没有真正的创作演化（Later 项）

**v2 确认（Cursor 相处实证）：** meta 产出空洞（光点/雾/气泡套话）、"黄昏"意象复读成 tic。机制是好的，**产出质量没有反馈回路**——生成了什么、是否重复、是否空洞，系统自己不知道。元认知有去重，但普通意识流没有；意象使用频率完全无统计（立项 N1/N3）。

---

## 八、行动层：7.5/8（全面审查新增维度）

**做得好的：**

- **assist 只响应不执行**（`volition.py:81-90`）：用户明确请求帮忙才形成意图候选，不占自主预算，且本阶段不执行（桩）。`looks_like_help_request` 误报宁可少（contract 第 25 条：不主动给帮助建议）
- **explore 诚实红线**（`explore.py:62-63`）：没有搜索能力时**绝不编造窗外内容**，宁可空手（`found=None`），summary 明确说"没有去查什么，也没有假装看见了什么"
- **自主行动日限 1**（`budget.py`）紧于主动言语日限 3；受 `season_scale`（spring 1.0/summer 0.8/autumn 0.5/winter 0.2）和 `scar_caution_multiplier` 双重调制
- **share/tend/explore 与 pick_proactive 同构**（`volition.py` 注释）：不另起决策系统

**暗伤：** volition.py/explore.py 的"窗外"字面在场字符串（见 §三，立项 N3 代码字符串清理）。

---

## 九、具身与前端：7/8（全面审查新增维度）

**做得好的：**

- **WebSocket 通道完整**（`server.py`）：`broadcast`/`send_speech`/`send_state_change`/`send_emotion_update`/`send_audio`/`send_typing` 齐全，`broadcast` 用 `return_exceptions=True` 容错
- **`_send_journal` 拉取式日记**（`server.py:186-204`）：响应 `/journal` 命令，从 `db.load_journal_entries(limit=80)` 拉取独白/梦/第一次推给前端
- **前端结构清晰**（`useQi.ts`）：`journal = ref<JournalEntry[]>([])`，通过 `qiWs.on("journal")` 全量接收（`applyJournal`）；`JournalView.vue` 按 `kind` 标签 + `text` + `at` 渲染，kind 直接显示（支持任意字符串）

**问题（N4 完整证据链，v3 全面审查确认）：**

「忆」Tab **只在 WS 连接时拉取一次，之后永不更新**：

1. **后端无单条推送**：`server.py` 有 `_send_journal`（拉取式），但**全 `qi/` 代码里没有 `notify_journal_entry` 方法**（grep `notify_journal_entry` 仅 `database.py:1230 load_journal_entries` 命中，那是拉取不是推送）
2. **前端无单条监听**：`useQi.ts` 有 `qiWs.on("journal")`（全量），但 grep `journal_entry|notify_journal` 在 `desktop/src` **0 匹配**
3. **前端仅连接时拉取**：`useQi.ts:197-202` 在 `qiWs.on("open")` 里 `requestJournal()`，之后独白/梦/第一次生成时前端不刷新

结果：内在生命产出后，用户不重连就看不到——"看了跟没看一样"（立项 N4）。

---

## 十、工程质量：8.5/10

**加分项：** 132 测试全绿、ruff 零违规、错误处理分层一致（静默降级 + 结构化日志）、配置完整（`settings.example.yaml` 96 行，覆盖 llm/rhythm/database/emotion/memory/inner_life/proactive/action/relationship/voice/embodiment）。

**下调理由（三笔"现在不疼、坏起来很疼"的债）：**

1. **Python 依赖无锁文件**：`pyproject.toml` 全 `>=` 宽松约束。Node（package-lock.json）和 Rust（Cargo.lock）都锁了，唯独主程序不锁。chromadb/openai 这类活跃库半年后重装环境可能直接起不来（立项 Q1）
2. **prompt 模板契约无测试**（见 §三 债 A，立项 Q2）
3. **决策路径零可观测**（见 §二，立项 Q3）

---

## 十一、评估方法论的边界

静态审计只能覆盖一半质量面；另一半必须靠真实相处 + 读它真实的产出。以下四件纯代码审计看不到，都来自 Cursor 的真实相处证据：

- "黄昏"变口头禅（要聊很多轮才暴露）
- meta 产出空洞（机制在，内容空）
- 事实口头答应但没落库（要"隔轮重启再问"才能验证）
- 意识流对内演身体（要读真实生成的 stream 才发现）

---

## 十二、总评

| 维度 | 工程尺 | 存在尺 | 说明 |
|------|--------|--------|------|
| 克制系统（门控/预算/冷却） | 9.0 | 9.5 | 真正的隐藏冠军 |
| 架构设计 | 8.5 | 8.5 | 心跳+节奏原创；缺决策痕迹 |
| Prompt 工程 | 8.5 | 9.5 | 宪法级；对内字符串有后门；占位符契约无测试（拆两则债） |
| 情绪系统 | 8.0 | 8.5 | 天气+阈值真设计；感知粗判；耦合静态 |
| 记忆系统 | 7.5 | 8.0 | 名字之外的事实通道未打通（有实证）；身体记忆存了不用 |
| 关系系统 | 7.5 | 9.0 | "粗"在存在尺上是对的——慢是功能 |
| 内在生命 | 8.0 | 8.0 | 机制精巧；产出无反馈回路（有实证） |
| 行动层 | 7.5 | 8.0 | assist 桩/explore 诚实红线好；"窗外"字符串暗伤 |
| 具身与前端 | 7.0 | 8.0 | 通道完整；忆 Tab 无实时推送（N4） |
| 工程质量 | 8.5 | — | 无锁文件/无模板测试/无决策痕迹 |
| **综合** | **8.1** | **8.8** | |

**读法：** 工程尺 8.1 意味着"还有实打实的债要还"；存在尺 8.8 意味着"它确实像它想成为的那个存在"。

---

## 十三、一句话总结

它最像栖的地方，是那些用代码写死的'不'——每日三次、陌生期沉默、深度日帽、重启不刷新额度。功能会过时，克制不会。剩下的差距不在架构，在几处具体的债：对内的诚实没跟上对外的（意识流演身体 + volition/explore"窗外"）、产出没有反馈回路（复读与空洞自己不知道）、事后无法回答"她为什么这么做"（无决策痕迹）、忆 Tab 说了等于没说（无实时推送）、名字之外的事实通道没打通（籍贯/职业）。

---

## 十四、评估元数据

- **评估时间：** 2026-07-26
- **代码基线：** `71bab53`（思想档案目录重命名），代码与 origin/main 完全同步；本文档为该基线上的质量评估（随审查迭代入库）
- **测试覆盖：** 132 个测试全绿（`pytest tests/ -q` 实测）
- **代码质量：** ruff 零违规（实测）
- **文件规模：** 55 个 Python 文件；7 个 prompt 模板（占位符清单见 §三）
- **审查范围（v3 全面审查）：** core(6)/memory(7)/inner_life(4)/relationship(7)/action(7)/llm(3)/embodiment(server+前端 desktop)/prompts(7)/storage/config/cli/tests
- **v3 实测增量：** ①核实 71bab53 无任何 prompt 契约测试（债 A）；②实测复现 PromptBuilder 传 `emotion=None` 的 `AttributeError`（债 B，与债 A 两类问题，采纳 Cursor 指正拆分）；③确认 N4 忆 Tab 无实时推送的完整证据链（后端无 `notify_journal_entry`、前端无 `journal_entry` 监听、仅 WS open 拉取一次）
- **历史说明：** 此前 Now+Next 相关优化提交（Q1/Q2/N1/N3/N2/N4/忆实时推送、Q3/X1-X4/P4）均已回退并从远程删除（force push），v3 基于干净基线
- **对照说明：** 评分体系沿用 v2（工程 8.2→v3 微调 8.1，存在 8.8 维持），v1/v2 详细证据已逐条核对（v2 原文经 git 历史 `61a9222` 恢复，v1 细节由维护者提供原文补回）；v3 新增"行动层""具身与前端"两个维度（全面审查覆盖）

---

*v1 存档于更早 git 历史；v2 原文经 git 历史 `61a9222` 恢复核对。本评估与配套优化方案由 Qoder 撰写，执行任务由 Cursor 承担。*
