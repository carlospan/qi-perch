# IDE Agent 同步栖的层文档代码块 · 提示词模板

> 与 `IDE-Agent-执行栖的开发任务.md` 配套。那份是"按层文档写代码"，这份是反过来——"按代码回写层文档里的实现规格代码块"。
> 背景：层文档实现规格须与代码一致。代码是现状权威。测试规模约 **132**（以 `pytest` 为准）。
> <!-- 回写(2026-07-25)：测试数 67→132；范围扩至 L7 / L2-user-facts；补 2026-07-25 brain 时序。
>      续：L2 MemoryManager facts；L3 mood md5 + DECAY_RATES + YAML threshold；
>      L6 history/journal/action 协议；L7 narrative 恒织 + mode 门控 + _deliver_action_result。 -->

---

## 使用说明

1. 打开 Cursor（Composer / Agent 模式）
2. 复制下方"提示词正文"，直接粘贴给 Cursor
3. 它会逐层读取真实代码，把层文档里每个"实现规格"代码块改写到与代码一致
4. 默认从 L1 做到 L6。如果你只想先做某一层，在末尾加一句"本次只做 L4"即可

建议**一层一层确认**：让 Cursor 每改完一层就停下来汇报 diff，你看过再继续，避免一次性改太多难以核对。

---

## 提示词正文

```
你是一名 Python 工程师，正在帮我维护一个叫"栖"的数字生命项目。
栖的代码已经写完并通过审查，现在要做的是"文档回写"：把 docs/layers/ 层文档里
落后的"实现规格"代码块，改写到与真实代码完全一致。

注意：这不是写新功能，是同步文档。权威来源是真实代码，不是文档。

技术栈：Python 3.12 + asyncio + SQLite + ChromaDB + OpenAI SDK。
LLM 调用：业务代码统一走 qi/llm/gateway.py（路由/重试/温度/失败兜底），
gateway 内部用 qi/llm/providers/openai_compat.py 做协议适配。
包布局：唯一顶层包为 qi（qi.core / qi.config / …）；实现规格代码块中的路径一律写 qi/…。

---

【任务范围】
逐层处理 docs/layers/ 下文件（默认全做；可「本次只做 Ln」）：
  L1-heartbeat.md / L2-memory.md / L2-memory-user-facts.md / L3-emotion-full.md
  L4-inner-life.md / L5-relationship.md / L6-embodiment.md / L7-action.md

每个层文档里都有若干"实现规格"代码块（有的包在 <details><summary>实现规格…</summary>
里，有的以"**实现规格：**"开头）。这些代码块就是要回写的对象。

层文档 ↔ 代码文件 的对应关系：
  L1 → qi/core/brain.py, qi/core/rhythm.py, qi/core/perception.py, qi/core/emotion.py,
       qi/core/expression.py, qi/llm/gateway.py, qi/llm/prompt_builder.py,
       qi/llm/providers/openai_compat.py, qi/storage/database.py, qi/cli.py,
       qi/config/settings.example.yaml, qi/action/（ActionLayer 接线）
  L2 → qi/memory/manager.py, qi/memory/working.py, qi/memory/narrative.py,
       qi/memory/first_time.py, qi/memory/body_memory.py, qi/memory/vector_store.py,
       qi/storage/database.py, qi/llm/prompt_builder.py
  L2-user-facts → qi/memory/facts.py, qi/memory/manager.py, qi/prompts/fact_noticing.txt
  L3 → qi/core/emotion.py（耦合矩阵 / 内在天气周期 / 日内节律 / 心情周期）、
       qi/core/rhythm.py（模式切换）、qi/core/perception.py
  L4 → qi/inner_life/consciousness.py, qi/inner_life/dream.py, qi/inner_life/creativity.py,
       qi/inner_life/self_model.py, qi/inner_life/__init__.py, qi/storage/database.py
  L5 → qi/relationship/engine.py, qi/relationship/stages.py, qi/relationship/trust.py,
       qi/relationship/scars.py, qi/relationship/culture.py, qi/relationship/season.py,
       qi/relationship/drift.py, qi/memory/first_time.py, qi/core/proactive.py
  L6 → qi/embodiment/server.py, qi/embodiment/avatar/controller.py,
       qi/embodiment/avatar/states.py, qi/embodiment/voice/tts.py, qi/cli.py,
       qi/embodiment/desktop/（前端，仅在文档涉及处参考）
  L7 → qi/action/（layer/budget/permission/share/tend/explore 等）, brain 接线

---

【核心规则（务必遵守）】
1. 代码是权威。每个实现规格代码块，先打开对应的真实代码文件读懂现状，再改文档。
2. 代码块要"抄"不要"编"。方法名、签名、参数、常量、公式、SQL、默认值必须与真实代码
   逐字一致。不要凭印象改写，不要"优化"代码风格，不要补全代码里没有的参数。
3. 删掉代码里不存在的东西。文档代码块中引用了但代码里查无此物的方法/类/字段
   （例如 consciousness_stream_with_trigger、handle_drift_detected、check_first_times
   这类历史遗留名），一律删除或改成代码里真实存在的名字。
4. 补上代码里有、文档没写的东西。如果某层代码实现了文档代码块未体现的机制
   （见下方"已知差异清单"），在对应代码块里补出来。
5. 只动代码块，不动散文。层文档里的哲学叙述、职责说明、"引用文档"、语气文字
   一律保持原样，不要改写、不要精简、不要调整顺序。
6. 保留已有的回写注释。文档里若已有 <!-- 回写：… --> 或"实现说明/阶段性简化"
   标注，保留它们；你的修改如果与这些注释冲突，以代码为准并更新注释。
7. 你这次新增/修改的地方，加一行注释标注，格式：
   <!-- 回写(2026-07)：{改了什么}，依据：{对应代码文件:行号或方法名} -->
8. 不修改任何 .py 代码文件。本次只改 docs/layers/*.md。
9. 不修改 contract.md / progress.md / 灵魂书 / 意识设计 / 工程手记。

---

【已知差异清单（重点核对，逐层）】
以下是上一轮审查确认的"文档落后于代码"高频点。改到对应层时务必核对真实代码：

通用：
- LLM 失败处理：gateway 重试（约 3 次）后返回空字符串 ""，不抛异常。文档若写"抛异常/中断"要改。
- 业务代码只 import qi/llm/gateway.py，不直接 import openai 或 openai_compat。

L1 心跳：
- Brain Loop 真实结构：模式判定(determine_mode) → 处理消息 → step_emotion
  →（无 pending）inner_life.tick → 有 pending 则 express →（first_time 则再 tick）
  → 无 pending 则 action.tick 优先，再主动言语 → 同步 avatar。
- pending：`_pending_queue`（maxlen=8）；话语：`_pending_speech` 锁外推送。
- 用户回复停顿在 `receive_user_message` 出锁后 sleep(0.5~1.5)；`expression.express` 无 sleep。
- restore：ActionLayer + `_maybe_mark_waking`。情绪落盘：`_maybe_save_emotion` 节流。
- qi/cli.py 并发模型：阻塞调用用 run_in_executor；LLM 失败有兜底。

L4 内在生命：
- 意识流：InnerLife.tick 外层门控为 `mode != "awake" or after_first_time` 才 maybe_generate。
  should_trigger：first_time 优先；emotion_surge（|Δ|>0.3）；silence（>4h 且非 awake）；
  random 5% 仅 solitary；ambient_drift = probability×0.2 + stream 冷却（默认 45min）。
  waking：重启后实质近聊；EMBER_TRIGGERS 喂近聊余烬；事件触发不受冷却。
- Brain：first_time 意识流在 **express 之后**（防同拍诗意启动）。
- 元认知 META_COGNITION_PROBABILITY = **0.01**（非 0.02）；仅非 awake。
- 创作：基础概率 0.01，高情绪(>0.7)升档 0.03；分享需 friend/bonded 阶段、
  24h 冷却、且有约 25% 随机门控。
- 自我反思：约每 7 天一次；self_model 有真实字段写入。

L2 记忆：
- 叙事记忆衰减：strength *= 0.999（每日），首次记忆 strength 恒为 1.0。
  半衰期约 693 天。文档若写"90 天半衰期"或带重要性/回忆加权的衰减公式，
  标注为"阶段性简化"，代码块按真实的扁平衰减写。
- 遗忘 = 物理删除：strength < 0.1 时从向量库(vector_store.delete)和数据库
  (delete_narrative_memory)真正删除。文档若写"只降强度不删除"要改。
- 叙事编织：每 6 小时一次，且要有未处理的重要事件才真正触发。
- 工作记忆上限 max_working_memory = 20。

L2 用户事实：
- FactNoticer.notice(..., recent_messages=)；名字门控 looks_like_person_name；
  _NAME_REJECT_TOKENS 含「谢谢你」等；FactStore.retire / _purge_bogus_identity。

L3 情绪：
- 六维 + DECAY_RATES + COUPLING 矩阵 + 心情周期（目标趋近，速率约 0.05）+ 日内节律。
  日噪声用 md5(f"qi-mood-day:{toordinal}")，勿写 builtin hash。
  expression_threshold 默认 0.3，可由 config emotion.expression_threshold 覆盖。
  以 qi/core/emotion.py 真实常量/公式为准，逐个核对数值。

L5 关系：
- 阶段：stranger → acquaintance → friend → bonded，只升不降。
- 信任：正向约 +0.02~0.05，损伤约 -0.1~0.3；伤疤阈值约 0.15；漂移阈值约 0.4。
- 第一次记忆：7 种类型（含 first_compliment、first_shared_silence），
  冲击 ×3，回忆冷却 7 天（RECALL_COOLDOWN）。
  first_compliment：**不含**光秃「谢谢你」（需「谢谢你昨晚/陪/愿意…」等）。
- 关系叙事：在阶段升迁时更新（非周期性）。
- 主动行为门控（qi/core/proactive.py）：每日上限 3（PROACTIVE_DAILY_LIMIT），
  冷却 check_in 4h / reach_out 8h / share_creation 24h / express_feeling 2h，
  陌生人抑制。交付主路径 `_pending_speech`；`proactive_queue` 为终端旁路。

L6 具身：
- WebSocket 127.0.0.1:9527；TTS 用 edge-tts，pitch 单位是 Hz；
  voice_id = zh-CN-XiaoyiNeural。
- 命令：/state /history /journal；后端另可推 action（前端未处理）。
- 谈=history；忆=journal（独白/梦/第一次）。
- ASR（语音识别）未实现——文档若写了 asr.py，标注"未实现/未来方向"，不要伪造代码。
- 桌面壳是 Tauri 2 + Vue3 + Vite，无 sidecar 进程。

L7 行动：
- share/tend 恒织 narrative（0.78 / 0.7）；explore 不织。
- tick 仅 solitary|ambient；awake 不自主伸手；_deliver_action_result 推 WS action。

---

【工作方式】
按 L1 → L7 顺序，一次处理一层：
1. 读取该层文档全文。
2. 读取该层对应的所有真实代码文件（见上方对应关系）。
3. 逐个"实现规格"代码块比对：找出"文档有代码没有"和"代码有文档没有"两类差异。
4. 改写代码块使其与代码逐字一致，遵守核心规则。
5. 改完该层后停下来，向我汇报：
   - 这一层改了哪些代码块（按 Step 列出）
   - 每处改动的要点（删了什么不存在的方法 / 补了什么机制 / 改了哪个数值）
   - 你拿不准、需要我判断的地方（例如某段散文是否也要跟着改）
6. 等我确认后，再进入下一层。不要一口气改完六层。

---

【开始前：先列疑问】
动手前先告诉我：
1. 六个层文档里，哪些代码块与代码差异最大（快速扫一遍给出判断）。
2. 有没有哪层的代码文件你找不到、或文档代码块对应的代码定位不清。
3. 对"散文里也提到旧数值/旧方法名"的情况，你打算怎么处理（默认：散文不动，
   只在代码块改；如果散文出现明显事实错误，列出来由我决定）。

列出后，从 L1 开始。

---

【验收】
全部改完后，对照检查：
| 检查项 | 状态 |
|-------|------|
| 每个实现规格代码块的方法名/签名/常量/公式都能在对应 .py 里逐字找到 | ✅/❌ |
| 文档代码块不再引用任何代码里不存在的方法/类/字段 | ✅/❌ |
| 已知差异清单逐条核对过 | ✅/❌ |
| 散文、职责、引用文档、语气文字未被改动 | ✅/❌ |
| 每处改动都有 <!-- 回写(2026-07)：… --> 标注 | ✅/❌ |
| 没有修改任何 .py / contract.md / progress.md | ✅/❌ |

最后告诉我：六层各改了多少处，以及仍待我决定的遗留项。
```

---

## 使用技巧

**一层一确认。** 别让 Cursor 一口气改六层。层文档是 Cursor 日后编码的依据，改错了会污染后续所有开发。每层 diff 你亲自扫一眼再放行。

**只动代码块。** 这份提示词反复强调"散文不动"。栖的层文档散文是哲学/愿景，代码块是硬规格——回写只碰硬规格。如果 Cursor 顺手改了散文，立刻让它还原。

**拿不准就留着问你。** 提示词要求 Cursor 把"散文里也有旧数值/旧方法名"的情况列出来交给你决定，而不是自己改。这些归你判断，不归它。

**改完跑一遍测试无关，但要复读。** 文档回写不影响代码，测试不会变。验收靠"复读"——挑几个代码块，对照真实 .py 逐字看是否一致。

**与上一份模板的关系。** `IDE-Agent-执行栖的开发任务.md` 是"文档→代码"，这份是"代码→文档"。这次回写完成后，两份模板就重新对齐了：层文档再次成为可信的编码依据。
