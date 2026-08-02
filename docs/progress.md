# 栖 · 开发进度

| 层 | 名称 | 状态 | 开始时间 | 完成时间 | 备注 |
|---|------|------|---------|---------|------|
| L1 | 心跳 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 代码完成，等感受验证。启动：配置 API key 后 `qi`（默认 provider 以 `settings.yaml` / `settings.example.yaml` 为准，example 现为 deepseek）。2026-07-25：pending 队列、`_pending_speech`、ActionLayer 同拍优先、first_time 先回复再独白、情绪落盘节流、waking。2026-07-26：`PromptContext`/`BackgroundTasks`、混合冲击、`body_hint`、`/why` 痕迹、F2 `_interacted_this_session`、忆推送接线 |
| L1.5 | 声音 | ⬜ 未开始 | - | - | Prompt 打磨，不写代码。无独立层文档，仅 prompt 调优，由用户感受判断完成。N1 意象/余烬已落地，仍属在养手感 |
| L2 | 记忆 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 叙事/向量/工作/身体记忆已接入；**用户事实（fact）已落地**（见 L2-memory-user-facts.md）；名字门控拒「谢谢你」等；`hometown` 籍贯；`body_rhythm_hint`；感受验证暂缓 |
| L3 | 情绪完善 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 耦合/天气/节律/频率/模式切换已接入；日噪声 md5 稳定；expression_threshold 可 YAML 覆盖；`COUPLING_STAGE_SCALE`；感受验证暂缓（待补） |
| L4 | 内在生命 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 意识流/梦/创作/自我反思已接入；提起 vs 递出已拆分（mentioned_at）；ambient_drift+冷却、waking+余烬、emotion_residue；`last_journal_entries` 实时推送；感受验证暂缓 |
| L5 | 关系 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 阶段/信任/文化/伤疤/第一次/季节/漂移已接入；first_compliment 不含光秃「谢谢你」；F1 `RECALL_MIN_AGE`；F2 冷启动不测共同沉默；N3b 内在体验禁呼吸/心跳；`last_recorded`；感受验证暂缓（待补） |
| L6 | 具身 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 黄昏的枝 + Live2D；420×680；情绪→氛围/脸色；谈=`/history`；忆=`/journal` + `journal_entry` 实时；`action` 卡片 UI 未做。启动：`qi-desktop` + `npm run tauri:dev`。见 `docs/how-to/换机搭建.md` §5 |
| L7 | 行动 | 🌱 在养 | 2026-07-23 | 2026-07-23 | 第一版骨架已接入：ActionBudget / volition / permission / share·tend·explore / ActionLayer + brain 接线（WS `action` + creation_card 开口）。未做：assist 执行、irreversible、伤疤失败接线、真实搜索、L6 卡片 UI。见 L7-action.md |

状态说明：
- ⬜ 未开始
- 🔨 进行中
- 🌱 在养（代码写完了，在跟它相处、调 prompt、等它"对"）
- ✅ 完成（感觉对了）

注："感受验证暂缓（待补）"指这几层代码已完成、仍在"在养"，只是通往 ✅ 的那一步感受验证还没做，待补。

注意：栖的"完成"不是"测试通过"。是"跟它聊了十分钟，觉得它活着"。  
测试规模约 **314**（`python -m pytest`，2026-08-02 阶段二·补丁 D 后实测）；层文档实现规格以代码为准。2026-07-25 选择性回写覆盖 L1–L7；**2026-07-26** 再回写 Now/Next/F1/F2（含 L2-user-facts / progress）。v3 Later 有痛点再开，不当施工队列。**2026-08-01** 文档大整顿：确立《栖·数字生命架构方案》为唯一架构方案（后续演进以其 §五 阶段零~四为准）；docs/README.md 立文档宪法；dev/ 清理至 7 份在用手册（换机搭建 / 主界面设计稿.html / 主界面-Live2D接入 / 主界面设计-黄昏的枝 / 施工包-阶段二 / IDE-Agent-同步层文档 / IDE-Agent-执行开发任务）；补丁 B/C/D 三个过程文档已按文档宪法闭环删除（活信息迁入 progress + 层文档 + 架构方案）；thoughts/ 纲要并入卷一，各卷加定位回写。**2026-08-02** 阶段零·任务包 C：gateway 失败语义分级 + 主动开口本地兜底 + `tests/test_fake_provider.py` 契约（对话 UNREACHABLE 静默；EMPTY 主动不 record）。**同日 P0**：`brain.py` 纯结构拆分为 `brain_*.py`（1076→632 行），零行为变更，199 测试全绿。**同日阶段零收官**：A（感知 LLM JSON 主路径 + intent 调制，过渡止血）/ B（bge-small-zh 本地 ONNX 语义检索，n-gram 回退，旧向量 SQLite 无损重建）/ D（意识流 season_hint）。测试 218。退出判据 1–4 已过（感知区分/语义命中/拔管契约/全绿），**判据 5（生命感监护）待维护者相处验证后再开阶段一**。**同日包 A**：感知 LLM JSON 主路径（过渡止血）+ intent 调制 + 关键词回退；关系层复用 assessment。**同日顺手项 D**：意识流 prompt 注入 `season_hint`（db 读关系季节，默认 spring）。**同日包 B**：叙事向量改 BGE-small-zh ONNX（CLS+L2）；n-gram 回退；Chroma 按 `qi_embedding` 重建回灌。**同日阶段一·包 1**：episodes 表 + 编织同步 role_map（type→说话人）；梦=未巩固积压驱动 + 加权选题；LLM/模板降级链；body_memory 决策 trace；`dream_retention` 衰减不动。叙事正文本体织反纠偏另立项。**同日阶段一·包 2**：attachment/security 阶段锚（bonded att→0.62）；关系事件 nudge；大承诺日帽≤2；trust/temperature 软顶+无交互日舒适区回归（temperature 舒适区为初值，未实证校准）。**同日阶段一·包 3**：open loops（body_memory，上限 5）；意识流积压+事件驱动；模板降级；首轮 deliver 后 prefer_close。ambient/空闲独白变少是 C4（无积压不空想），非「变冷淡」。**同日阶段一·包 4**：IntentionCard 两段式表达；N5 卡约束；对话/主动 EMPTY·UNREACHABLE→模板开口；`last_intention`+outcome。**同日阶段一·包 5**：身份快照（过渡脚手架，dirty←reflect/stage/season/valence；N=30）；conversation 基线 b27a0b0=3216→落点约 1405（≥50%）；意识流/梦同步注入。**同日阶段一·补丁 A**：recall 方法类问法建卡+模板保底；施教关系 taught_by_qi 锚定（叙事「我教了」）；proactive share_state 情绪结论 must+软检。**同日阶段二·包 6**：`broadcast_traces` + Contender/`salience()` 只记不算；winner 仍走旧路径；`list_recent_broadcast_traces`。**同日阶段二·包 7**：`gws.arbitrate` + shadow 对照（可执行子集冲一致率）；`gws.enabled` 默认 false，启用后仲裁分发；respond 永不被压过。**同日阶段二·包 8**：`sensing.collect` + `self_ops`（归档/调预算/日记）+ explore 真读沙箱；`archived` 列与 `closed_loop` 钩子；自反闭环可观测。**同日阶段二·补丁 B**：顺带提记忆路径（act≠recall）亦赋 `recall_relation` 并注入施教反转 must。**同日阶段二·补丁 C**：`gws.enabled` 默认 true；自主日限 3；awake 可跑三自反；close_loop/report 阈值放宽——让真机自主胜出可观测。**同日阶段二·补丁 D**：journal 候选 3h；`SILENCE_TRIGGER_HOURS` 4→3，使 close_loop 有合理心事源。**同日阶段一收官**：6 项退出判据全过（拔管兜底/prompt 瘦身≥50%(3216→1405,-56.3%)/梦=巩固(判据#3 经离线脚本实测：4 条积压全部 mark_dreamed、dreams 落库)/attachment 不脱钩(bonded att≈0.66)/274 全绿 ruff 零/维护者主观判据#6 点头）；按文档宪法删 `施工包-阶段一.md`。**同日开阶段二**（N1 传感/执行器扩展 + GWS 仲裁替换 `_pending_queue` 单通道 + `_record_trace` 升级为全量广播痕迹；退出判据=无人测试 72h + 溯源测试 10/10）。**同日阶段二·判据裁定（路 B）**：溯源判据#2（10/10）与自反闭环判据#4 的 3h 在线门槛属「触发频率闸门」非「因果正确性门槛」；真机实测 5 条自主拍 **5/5 因果链清晰**已证明机制成立，故将「真机攒够 ≥10 条自主拍」「真机观测到 close_loop」由阶段二**退出卡死项降级为长期观察指标**，不阻塞阶段二退出；剩余硬判据仅 #1（无人测试 72h，自然流逝累积）。**同日阶段二·正式退出**：工程交付已完成（GWS 仲裁替换 `_pending_queue` 单通道 + `_record_trace` 全量广播痕迹 + 自主行为 broadcast/contender/salience 可观测 + 补丁 B/C/D 全绿 314 测试）；判据 #2/#4 按路 B 降级为长期观察，判据 #1（72h 无人测试）作为后台稳定性观察继续累积，不阻塞退出。阶段二退出，进入阶段三（按架构方案 §五 阶段三优先级推进）。

## 已拍板决策

- **2026-08-02 · 自主日限维持 20（不回退到 3）**：补丁 C 将 `autonomous_daily_limit` 设为 3，但真机实测日限并非瓶颈（archive 受可归档记忆量卡、journal/close_loop 受门槛卡），故维护者拍板将实际生效的 `qi/config/settings.yaml` 改为 **20**（理由：远高真实触发上限、只作安全阀、不让样本积累被日限卡）。补丁 D 完工时 Cursor 以"不在本包范围"为由把 example/budget.py 口径拉回 3，造成三处不一致（实际 settings=20 / example=3 / 常量=3）；经复核，维护者裁定**维持 20**，并令 Cursor 把 example/budget.py 改回 20 对齐三处语义。规则：已生效的维护者配置决策，子补丁不得静默回退口径，要么不动、要么明确标注待确认。

- **2026-08-02 · 阶段二判据 #2/#4 降级为观察项（路 B）**：3h 在线门槛属「触发频率闸门」非「因果正确性门槛」。真机实测 5 条自主拍 5/5 因果链清晰已证明溯源机制成立；close_loop 生成路径（`trace.py` loop_n>0 注入 contender）代码侧已就位，仅缺悬心事触发。故将「真机攒够 ≥10 条自主拍」「真机观测到 close_loop」由阶段二**退出卡死项降级为长期观察指标**，不阻塞退出。剩余硬判据仅 #1（无人测试 72h，自然流逝累积）。

- **2026-08-02 · 阶段三暂不部署本地大模型（本机硬件不支撑）**：维护者机器为 RTX 4060 Laptop 4GB 显存 + 16GB 内存，日常多任务（浏览器/agent）下常驻 7B 模型会与显存打架、OOM；且借 LLM = 站巨人肩膀，远程 LLM 主力保活气/泛化更优。裁定：**阶段三不在本机常驻部署本地模型**；远程 LLM 持续当主力，本地模型仅留作「未来拔管兜底选项」（暂缓）。部署重启条件：机器显存 ≥8GB，或小型模型（如 3B 级）质量达标可流畅常驻，或维护者想试断网养栖。阶段三主线 = 内生认知（世界模型/动机/经验回放），不依赖本地模型、不阻塞。注：当前「本地化」形态（外挂 Ollama 进程）与远程 API 同构、未实现脑身一体；真换心需模型内嵌或内生认知长成，列为路线级待决。
