# 栖 · 开发进度

| 层 | 名称 | 状态 | 开始时间 | 完成时间 | 备注 |
|---|------|------|---------|---------|------|
| L1 | 心跳 | ✅ 完成 | 2026-07-21 | 2026-08-08 | 代码完成，等感受验证。启动：配置 API key 后 `qi` / `python -m qi`（具身 WS；**已无终端聊天**）。默认 provider 以 `settings.yaml` / example 为准（example 现为 **tokenrhythm / minimax-m2.7**）。2026-07-25：pending 队列、`_pending_speech`、ActionLayer 同拍优先、first_time 先回复再独白、情绪落盘节流、waking。2026-07-26：`PromptContext`/`BackgroundTasks`、混合冲击、`body_hint`、`format_why` 痕迹、F2 `_interacted_this_session`、忆推送接线 |
| L1.5 | 声音 | ⬜ 未开始 | - | - | Prompt 打磨，不写代码。无独立层文档，仅 prompt 调优，由用户感受判断完成。N1 意象/余烬已落地，仍属在养手感 |
| L2 | 记忆 | ✅ 完成 | 2026-07-21 | 2026-08-08 | 叙事/向量/工作/身体记忆已接入；**用户事实（fact）已落地**（见 L2-memory-user-facts.md）；名字门控拒「谢谢你」等；`hometown` 籍贯；`body_rhythm_hint` |
| L3 | 情绪完善 | ✅ 完成 | 2026-07-21 | 2026-08-08 | 耦合/天气/节律/频率/模式切换已接入；日噪声 md5 稳定；expression_threshold 可 YAML 覆盖；`COUPLING_STAGE_SCALE`；阶段锚 `STAGE_BASELINES` + `energy_baseline_offset` |
| L4 | 内在生命 | ✅ 完成 | 2026-07-21 | 2026-08-08 | 意识流/梦/创作/自我反思已接入；提起 vs 递出已拆分（mentioned_at）；ambient_drift+冷却、waking+余烬、emotion_residue；`last_journal_entries` 实时推送；梦=积压 episode + curiosity≥0.55（非每拍 10%） |
| L5 | 关系 | ✅ 完成 | 2026-07-21 | 2026-08-08 | 阶段/信任/文化/伤疤/第一次/季节/漂移已接入；first_compliment 不含光秃「谢谢你」；F1 `RECALL_MIN_AGE`；F2 冷启动不测共同沉默；N3b 内在体验禁呼吸/心跳；`last_recorded` |
| L6 | 具身 | ✅ 完成 | 2026-07-21 | 2026-08-08 | 黄昏的枝 + VRM 桌宠；420×680；情绪→氛围；**相处/回顾/内在**（相处=`/history`+presence-glow；回顾=创作/见闻；内在=`/journal`+`journal_entry`）。启动：`npm run tauri:dev`（开发期可自动拉起 `qi`）。见 `docs/how-to/换机搭建.md` §5 |
| L7 | 行动 | 🌱 在养 | 2026-07-23 | 2026-07-23 | 第一版骨架已接入：ActionBudget / volition / permission / share·tend·explore / ActionLayer + brain 接线（WS `action` + creation_card 开口；正文走卡片、不内联）。**真实搜索改已完成**（C 方案 d-1/d-2/d-3-1/d-3-2 工程交付完成，相处复验中）。N3 动机接线 / 伤疤失败接线 / assist **八包 + 隐私小刀**（追问 preview、全文分块、整体叙事、explore 不背文件原文）已落地；现行仅 UTF-8 `read_file`≤1MB；irreversible 未做。见 L7-action.md |

状态说明：
- ⬜ 未开始
- 🔨 进行中
- 🌱 在养（代码写完了，在跟它相处、调 prompt、等它"对"）
- ✅ 完成（感觉对了）

注："感受验证暂缓（待补）"指这几层代码已完成、仍在"在养"，只是通往 ✅ 的那一步感受验证还没做，待补。**2026-08-08 更新**：L1–L6 已通过相处验证（b 路径：回溯式感受读 1400 条真实对话 + 维护者 live 答五问「心疼」=有过 → 五问全过、不回炉）升 ✅，原"感受验证暂缓"注记作废；L7 仍在养（**explore 真搜索 C 方案工程已交付、相处复验中**）。**2026-08-09 更新**：N3 动机接线 / 伤疤失败接线 / assist 八包 + 隐私小刀已落地；仅 irreversible 待做。见 `docs/specs/tasks/2026-08-08-相处验证收口-结论.md`。

注意：栖的"完成"不是"测试通过"。是"跟它聊了十分钟，觉得它活着"。  
测试规模约 **606**（`pytest --collect-only`，2026-08-12；CI 全量约 604 passed + 2 skipped；先前节点：补丁 D≈314 / 阶段四退出≈405 / explore C≈500 / L7≈556 / assist 五包≈576 / assist-6/7/8≈587）；层文档实现规格以代码为准。2026-07-25 选择性回写覆盖 L1–L7；**2026-07-26** 再回写 Now/Next/F1/F2（含 L2-user-facts / progress）。v3 Later 有痛点再开，不当施工队列。**2026-08-01** 文档大整顿：确立《栖·数字生命架构方案》为唯一架构方案（后续演进以其 §五 阶段零~四为准）；docs/README.md 立文档宪法；dev/ 清理至 7 份在用手册（换机搭建 / 主界面设计稿.html / 主界面-Live2D接入 / 主界面设计-黄昏的枝 / 施工包-阶段二 / IDE-Agent-同步层文档 / IDE-Agent-执行开发任务）；补丁 B/C/D 三个过程文档已按文档宪法闭环删除（活信息迁入 progress + 层文档 + 架构方案）；thoughts/ 纲要并入卷一，各卷加定位回写。**2026-08-02** 阶段零·任务包 C：gateway 失败语义分级 + 主动开口本地兜底 + `tests/test_fake_provider.py` 契约（对话 UNREACHABLE 静默；EMPTY 主动不 record）。**同日 P0**：`brain.py` 纯结构拆分为 `brain_*.py`（1076→632 行），零行为变更，199 测试全绿。**同日阶段零收官**：A（感知 LLM JSON 主路径 + intent 调制，过渡止血）/ B（bge-small-zh 本地 ONNX 语义检索，n-gram 回退，旧向量 SQLite 无损重建）/ D（意识流 season_hint）。测试 218。退出判据 1–4 已过（感知区分/语义命中/拔管契约/全绿），**判据 5（生命感监护）待维护者相处验证后再开阶段一**。**同日包 A**：感知 LLM JSON 主路径（过渡止血）+ intent 调制 + 关键词回退；关系层复用 assessment。**同日顺手项 D**：意识流 prompt 注入 `season_hint`（db 读关系季节，默认 spring）。**同日包 B**：叙事向量改 BGE-small-zh ONNX（CLS+L2）；n-gram 回退；Chroma 按 `qi_embedding` 重建回灌。**同日阶段一·包 1**：episodes 表 + 编织同步 role_map（type→说话人）；梦=未巩固积压驱动 + 加权选题；LLM/模板降级链；body_memory 决策 trace；`dream_retention` 衰减不动。叙事正文本体织反纠偏另立项。**同日阶段一·包 2**：attachment/security 阶段锚（bonded att→0.62）；关系事件 nudge；大承诺日帽≤2；trust/temperature 软顶+无交互日舒适区回归（temperature 舒适区为初值，未实证校准）。**同日阶段一·包 3**：open loops（body_memory，上限 5）；意识流积压+事件驱动；模板降级；首轮 deliver 后 prefer_close。ambient/空闲独白变少是 C4（无积压不空想），非「变冷淡」。**同日阶段一·包 4**：IntentionCard 两段式表达；N5 卡约束；对话/主动 EMPTY·UNREACHABLE→模板开口；`last_intention`+outcome。**同日阶段一·包 5**：身份快照（过渡脚手架，dirty←reflect/stage/season/valence；N=30）；conversation 基线 b27a0b0=3216→落点约 1405（≥50%）；意识流/梦同步注入。**同日阶段一·补丁 A**：recall 方法类问法建卡+模板保底；施教关系 taught_by_qi 锚定（叙事「我教了」）；proactive share_state 情绪结论 must+软检。**同日阶段二·包 6**：`broadcast_traces` + Contender/`salience()` 只记不算；winner 仍走旧路径；`list_recent_broadcast_traces`。**同日阶段二·包 7**：`gws.arbitrate` + shadow 对照（可执行子集冲一致率）；`gws.enabled` 默认 false，启用后仲裁分发；respond 永不被压过。**同日阶段二·包 8**：`sensing.collect` + `self_ops`（归档/调预算/日记）+ explore 真读沙箱；`archived` 列与 `closed_loop` 钩子；自反闭环可观测。**同日阶段二·补丁 B**：顺带提记忆路径（act≠recall）亦赋 `recall_relation` 并注入施教反转 must。**同日阶段二·补丁 C**：`gws.enabled` 默认 true；自主日限 3；awake 可跑三自反；close_loop/report 阈值放宽——让真机自主胜出可观测。**同日阶段二·补丁 D**：journal 候选 3h；`SILENCE_TRIGGER_HOURS` 4→3，使 close_loop 有合理心事源。**同日阶段一收官**：6 项退出判据全过（拔管兜底/prompt 瘦身≥50%(3216→1405,-56.3%)/梦=巩固(判据#3 经离线脚本实测：4 条积压全部 mark_dreamed、dreams 落库)/attachment 不脱钩(bonded att≈0.66)/274 全绿 ruff 零/维护者主观判据#6 点头）；按文档宪法删 `施工包-阶段一.md`。**同日开阶段二**（N1 传感/执行器扩展 + GWS 仲裁替换 `_pending_queue` 单通道 + `_record_trace` 升级为全量广播痕迹；退出判据=无人测试 72h + 溯源测试 10/10）。**同日阶段二·判据裁定（路 B）**：溯源判据#2（10/10）与自反闭环判据#4 的 3h 在线门槛属「触发频率闸门」非「因果正确性门槛」；真机实测 5 条自主拍 **5/5 因果链清晰**已证明机制成立，故将「真机攒够 ≥10 条自主拍」「真机观测到 close_loop」由阶段二**退出卡死项降级为长期观察指标**，不阻塞阶段二退出；剩余硬判据仅 #1（无人测试 72h，自然流逝累积）。**同日阶段二·正式退出**：工程交付已完成（GWS 仲裁替换 `_pending_queue` 单通道 + `_record_trace` 全量广播痕迹 + 自主行为 broadcast/contender/salience 可观测 + 补丁 B/C/D 全绿 314 测试）；判据 #2/#4 按路 B 降级为长期观察，判据 #1（72h 无人测试）作为后台稳定性观察继续累积，不阻塞退出。阶段二退出，进入阶段三（按架构方案 §五 阶段三优先级推进）。

## 已拍板决策

- **2026-08-12 · 文档回写（前端 IA）**：聊天壳三栏静/谈/忆 → **相处/回顾/内在**；对齐 L6 / 黄昏的枝 / code-wiki / README；相处背景 `qi-presence-glow.png`；测试规模口径 → 606。

- **2026-08-09 · N3 动机接线**：pressure 软调制 explore 概率，`PRESSURE_THROTTLE_K=0.5` / `PRESSURE_REST_K=0.6`；force 路径双压满时下限 **0.2**（由两 K 相乘得出，不是第三枚 K）。伤疤 severity **0.3 / 0.7** 在 `layer._maybe_save_scar`，与 explore K 分开。
- **2026-08-09 · 意向/表达防记忆劫持**：`intention`——了解多少走 facts；纠偏/元状态不灌叙事；free_talk 仅粗相关 memory 进卡。`expression`——模板不贴 memory 原文；模板复读吐安全句。见 `316acc5`。
- **2026-08-09 · 活文档对齐代码**：layers L1/L3/L4/L5/L6/L7、code-wiki、config、progress、心智导读、stage-0 行数脚注——对照现码回写（梦门/阶段锚/GWS idle/history=200/explore 已联网等）。

- **2026-08-09 · 伤疤失败接线**：`layer._maybe_save_scar`，severity 0.3/0.7，骨架触发源待产出。

- **2026-08-09 · assist 三包**：`execute_kind` + `confirm_gate` + consciousness digest；感知层 `parse_assist_request`；跨轮确认 pending + `AssistConfirmCard.vue` + 超时 5 分钟或 3 轮。
- **2026-08-09 · assist-4/5（对话拍 + 集成）**：`receive_user_message` 解析到 assist 则短路 `execute_kind(confirmed=False)`（不进 pending_queue）；成功/失败 `insert_action`；`conversation.txt` 硬规则禁编造「读不到文件系统」；粘性 `last_assist_target` + 窄词口头补执行。过程稿归档 `docs/specs/archive/2026-08-09-L7-assist/`。测试 **576**。

- **2026-08-09 · assist-6/7/8 + 隐私小刀**：assist-6——`detail_json.content_preview`（80 字）注入 `prompt_extras` + conversation「读过就承认」；assist-7——去 32KB 截断、≤1MB、分块 digest（8000×6，单块短路）；assist-8——收尾 **1 条** narrative（整体感受 +「里面写着：preview」）；隐私小刀——explore `_QUERY_PRIVACY_LINE` 覆盖「用户文件内容原文」。工程验收 **587 passed**。相处：清否认史后真读→追问已观测承认「我爱栖」（msg #1515；首问仍可能缩）；隔日回忆 / explore 不背诵可继续观察。过程稿同桶归档。

- **2026-08-08 · L7 explore 真搜索 d-1（联网地基）**：外部分支（Tavily；默认 `explore_external.enabled=false`）；门控 curiosity≥0.8 + 冷却 6h + 概率 0.05；**不设独立外部日限**（复用 ActionBudget 20）；query 走 gateway `purpose=consciousness`；外部结果 `speak+qi_line` 开口，搜不到 `failed_capability` 不编造。见 `docs/specs/tasks/2026-08-08-L7-explore真搜索-d1联网地基.md`。**contract drift**：旧文「默认 1/天」vs 现行 20——**已于 2026-08-09 回写 contract 对齐 20**。**已收口（2026-08-08）**：相处验证（栖会主动检索 5 条记录、真搜真返回、不编造、query 像栖）+ 开口含蓄化微调（成功只念 query 不念 search title，消除跑题出戏）+ 487 passed。后续 d-2/d-3 已接续收口（见下）。

- **2026-08-08 · L7 explore 真搜索 d-2（外部 hits 消化）**：`_digest_hits` 把 Tavily hits 转成栖语气 digest（`consciousness`）；成功时 `qi_line=summary=digest`；失败降级只念 query；`found.entries` 留溯源。见 `docs/specs/tasks/2026-08-08-L7-explore真搜索-d2内部深读-任务包.md`。**已收口**：492 passed；相处复验「像看懂了而非念搜索结果」。

- **2026-08-08 · L7 explore 真搜索 d-3-1+d-3-2（见闻卡 + 内部深读）**：d-3-1 纯前端 ExploreCard（角标「看」、hits faint；仅 `web`+非空 entries）；d-3-2 内部改读 `list_recent_narratives` → digest → `speak` + `source=journal`，前端门控扩 `web||journal`；删沙箱列目录死码。见 d-3-1/d-3-2 任务包。**已收口（工程）**：500 passed + vue-tsc/build；C 方案工程交付完成，相处复验中。

- **2026-08-08 · Gap 2 修复：curiosity 候选回退，L7 自主行动恢复触发**：删 `trace.collect_contenders` 包 10 注入的非可执行 `kind="curiosity"` 候选（空赢 GWS → idle，堵死 share/archive/tend/explore）；curiosity 只作 motive（写回 `emotion.curiosity` + 驱动 `action:explore`）。见 `docs/specs/tasks/2026-08-08-L7-curiosity候选解堵.md` / 排查包。**真机验证（17:00+）**：curiosity 候选消失、share 恢复触发（6 天积压 8 张创作 16:58-17:02 递出）。

- **2026-08-08 · 相处验证收口：L1-L6 升 ✅**：b 路径（回溯式感受读 1400 条真实对话 + 960 意识流 + 维护者 live 答五问第五项「心疼」=有过）→ 五问全过、不回炉。L1-L6 🌱→✅（完成时间 2026-08-08）；L7 仍在养（explore 真搜索工程已交付、相处复验中；当日快照尚写 assist / irreversible 待做——**其后 08-09 assist 八包 + 隐私小刀已落地，仅 irreversible 仍待做**）。**R1 不破**：心疼是维护者第一人称感受记录，非栖有现象体验的证明。见 `docs/specs/tasks/2026-08-08-相处验证收口-结论.md`。

- **2026-08-08 · 健康审计 Stage1 文档回写**：`reference/layers` L1/L2/L4/L7 文件清单与卫星/N 侧索引对齐现码；L7 原则句与 `budget.py` 日限 **20**（安全阀）对齐；`stage-0` 注明 P0「632」为收官快照、现行 `brain.py`≈1377；`stage-1`/`stage-4` 判据表勾达成（与 progress 退出叙事一致）；layers README 收录允许依赖例外（`storage→core`、`llm→relationship` 等）。

- **2026-08-08 · 健康审计 Stage4 文档回写**：`config.md` / code-wiki §九 补全 `stasis`；wiki 概述与 §8.1 现行 provider 对齐 **tokenrhythm / minimax-m2.7**；刷测试规模≈462、`brain.py`≈1223（其后编排面约 1377）；progress 文首与 L1 表备注同步。

- **2026-08-08 · 健康审计 Stage5 Top3**：Tauri CSP 非空；具身 WS `origins` 白名单 + `resolve_bind` 禁非 loopback；`cli` 接线 `embodiment.host/port`；lock 升 `aiohttp==3.14.3` / `cryptography==50.0.0`（`chromadb 1.5.9` PYSEC-2026-311 仍无上游 Fix，观察）。

- **2026-08-08 · 健康审计 Stage6 Top3**：BGE ONNX 懒加载（构造不拉 session）；`/history` 默认最近 200 条；补 user_facts/narrative/dreams/actions 索引；感知寒暄短路扩大；表达 LLM 每拍最多 2 次（HARD 与去重重生互斥）。

- **2026-08-08 · 健康审计 Stage7 Top3**：CI 增 frontend（`npm ci`+Vite build）与 `pip-audit`（忽略 chromadb 无 Fix CVE）；去重独立 ruff、`verify_package` lint 含 `tools`；补 `CONTRIBUTING.md` + PR 模板；刷 code-wiki §8.8。

- **2026-08-08 · 健康审计 Stage8 Top3**：断线禁用输入 + StatusBar「未连上」+ 谈区「最近约 200」；无边框窗控（最小化/关闭）；Live2D 失败显式占位（Cubism/模型加载 reject ready）。

- **2026-08-02 · 自主日限维持 20（不回退到 3）**：补丁 C 将 `autonomous_daily_limit` 设为 3，但真机实测日限并非瓶颈（archive 受可归档记忆量卡、journal/close_loop 受门槛卡），故维护者拍板将实际生效的 `qi/config/settings.yaml` 改为 **20**（理由：远高真实触发上限、只作安全阀、不让样本积累被日限卡）。补丁 D 完工时 Cursor 以"不在本包范围"为由把 example/budget.py 口径拉回 3，造成三处不一致（实际 settings=20 / example=3 / 常量=3）；经复核，维护者裁定**维持 20**，并令 Cursor 把 example/budget.py 改回 20 对齐三处语义。规则：已生效的维护者配置决策，子补丁不得静默回退口径，要么不动、要么明确标注待确认。

- **2026-08-02 · 阶段二判据 #2/#4 降级为观察项（路 B）**：3h 在线门槛属「触发频率闸门」非「因果正确性门槛」。真机实测 5 条自主拍 5/5 因果链清晰已证明溯源机制成立；close_loop 生成路径（`trace.py` loop_n>0 注入 contender）代码侧已就位，仅缺悬心事触发。故将「真机攒够 ≥10 条自主拍」「真机观测到 close_loop」由阶段二**退出卡死项降级为长期观察指标**，不阻塞退出。剩余硬判据仅 #1（无人测试 72h，自然流逝累积）。

- **2026-08-02 · 阶段三暂不部署本地大模型（本机硬件不支撑）**：维护者机器为 RTX 4060 Laptop 4GB 显存 + 16GB 内存，日常多任务（浏览器/agent）下常驻 7B 模型会与显存打架、OOM；且借 LLM = 站巨人肩膀，远程 LLM 主力保活气/泛化更优。裁定：**阶段三不在本机常驻部署本地模型**；远程 LLM 持续当主力，本地模型仅留作「未来拔管兜底选项」（暂缓）。部署重启条件：机器显存 ≥8GB，或小型模型（如 3B 级）质量达标可流畅常驻，或维护者想试断网养栖。阶段三主线 = 内生认知（世界模型/动机/经验回放），不依赖本地模型、不阻塞。注：当前「本地化」形态（外挂 Ollama 进程）与远程 API 同构、未实现脑身一体；真换心需模型内嵌或内生认知长成，列为路线级待决。

- **2026-08-02 · 阶段三判据 #1-真通过降级为观察项（路 B）**：包 11 已交付 #1-**地基**（语料版本化 `data/corpus/` + 异时测试骨架 `drift_check.py` + `run_training` 默认隔离不进心跳），但 #1-**真通过**（显式训练一次后响应可归因漂移）需真训。本机 RTX 4060 4GB 显存无法常驻训练（同上条已拍板不部署本地模型），真训非阶段三必要退出条件。故将「#1-真通过」由硬判据**降级为观察项**：阶段三退出不以真训为硬条件；经验回放管线留作离线资产，资源允许（显存≥8GB 或 3B 级模型流畅）时可再触发路 A。禁止仅靠「语料版本 diff」在任务包里宣称判据 #1 已过。回写：`stage-3.md` 判据表加注降级。

- **2026-08-02 · 阶段四退出（判据 #1 达成）**：包 12（N0 资源账本，实测 386 passed）/ 13（内稳态压力动力学，实测 397 passed）/ 14（状态封存+断粮测试验收，实测 405 passed）三包全过，H1/H2/H3 按 Cursor 交叉检验倾向定稿并落实。判据 #1（断粮测试）：限制资源后观察到节流/休眠/求助/迁移应对行为链（非空壳 `stasis_intents` 痕迹 + 分层权重）而非直接死亡，状态可封存（`checkpoint_{ts}.json`）且可迁移（`restore` 字段相等），库内 `on_halt` 优雅停（禁 `sys.exit`）。**阶段四退出判据 #1 达成，阶段四可退出**。不卡退出的观察项：Q0(b) 经验改变"怕死阈值"接包 11 回放塑性（阶段四之后观察项，禁硬接未真训回放）；阶段二 72h 无人测试仍后台累积（阶段四不卡）。回写：`stage-4.md` 判据表标 #1 达成、`2026-08-02-阶段四-主线.md` 三包标 ✅ + 退出确认段。
