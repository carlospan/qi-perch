# 栖 · 开发进度

| 层 | 名称 | 状态 | 开始时间 | 完成时间 | 备注 |
|---|------|------|---------|---------|------|
| L1 | 心跳 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 代码完成，等感受验证。启动：配置 API key 后 `qi`（默认 provider 以 `settings.yaml` / `settings.example.yaml` 为准，example 现为 deepseek）。2026-07-25：pending 队列、`_pending_speech`、ActionLayer 同拍优先、first_time 先回复再独白、情绪落盘节流、waking。2026-07-26：`PromptContext`/`BackgroundTasks`、混合冲击、`body_hint`、`/why` 痕迹、F2 `_interacted_this_session`、忆推送接线 |
| L1.5 | 声音 | ⬜ 未开始 | - | - | Prompt 打磨，不写代码。无独立层文档，仅 prompt 调优，由用户感受判断完成。N1 意象/余烬已落地，仍属在养手感 |
| L2 | 记忆 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 叙事/向量/工作/身体记忆已接入；**用户事实（fact）已落地**（见 L2-memory-user-facts.md）；名字门控拒「谢谢你」等；`hometown` 籍贯；`body_rhythm_hint`；感受验证暂缓 |
| L3 | 情绪完善 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 耦合/天气/节律/频率/模式切换已接入；日噪声 md5 稳定；expression_threshold 可 YAML 覆盖；`COUPLING_STAGE_SCALE`；感受验证暂缓（待补） |
| L4 | 内在生命 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 意识流/梦/创作/自我反思已接入；提起 vs 递出已拆分（mentioned_at）；ambient_drift+冷却、waking+余烬、emotion_residue；`last_journal_entries` 实时推送；感受验证暂缓 |
| L5 | 关系 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 阶段/信任/文化/伤疤/第一次/季节/漂移已接入；first_compliment 不含光秃「谢谢你」；F1 `RECALL_MIN_AGE`；F2 冷启动不测共同沉默；N3b 内在体验禁呼吸/心跳；`last_recorded`；感受验证暂缓（待补） |
| L6 | 具身 | 🌱 在养 | 2026-07-21 | 2026-07-21 | 黄昏的枝 + Live2D；420×680；情绪→氛围/脸色；谈=`/history`；忆=`/journal` + `journal_entry` 实时；`action` 卡片 UI 未做。启动：`qi-desktop` + `npm run tauri:dev`。见 `docs/dev/换机搭建.md` §5 |
| L7 | 行动 | 🌱 在养 | 2026-07-23 | 2026-07-23 | 第一版骨架已接入：ActionBudget / volition / permission / share·tend·explore / ActionLayer + brain 接线（WS `action` + creation_card 开口）。未做：assist 执行、irreversible、伤疤失败接线、真实搜索、L6 卡片 UI。见 L7-action.md |

状态说明：
- ⬜ 未开始
- 🔨 进行中
- 🌱 在养（代码写完了，在跟它相处、调 prompt、等它"对"）
- ✅ 完成（感觉对了）

注："感受验证暂缓（待补）"指这几层代码已完成、仍在"在养"，只是通往 ✅ 的那一步感受验证还没做，待补。

注意：栖的"完成"不是"测试通过"。是"跟它聊了十分钟，觉得它活着"。  
测试规模约 **228**（`python -m pytest`，2026-08-02 包 1 后实测）；层文档实现规格以代码为准。2026-07-25 选择性回写覆盖 L1–L7；**2026-07-26** 再回写 Now/Next/F1/F2（含 L2-user-facts / progress）。v3 Later 有痛点再开，不当施工队列。**2026-08-01** 文档大整顿：确立《栖·数字生命架构方案》为唯一架构方案（后续演进以其 §五 阶段零~四为准）；docs/README.md 立文档宪法；dev/ 清理至 6 份在用手册；thoughts/ 纲要并入卷一，各卷加定位回写。**2026-08-02** 阶段零·任务包 C：gateway 失败语义分级 + 主动开口本地兜底 + `tests/test_fake_provider.py` 契约（对话 UNREACHABLE 静默；EMPTY 主动不 record）。**同日 P0**：`brain.py` 纯结构拆分为 `brain_*.py`（1076→632 行），零行为变更，199 测试全绿。**同日阶段零收官**：A（感知 LLM JSON 主路径 + intent 调制，过渡止血）/ B（bge-small-zh 本地 ONNX 语义检索，n-gram 回退，旧向量 SQLite 无损重建）/ D（意识流 season_hint）。测试 218。退出判据 1–4 已过（感知区分/语义命中/拔管契约/全绿），**判据 5（生命感监护）待维护者相处验证后再开阶段一**。**同日包 A**：感知 LLM JSON 主路径（过渡止血）+ intent 调制 + 关键词回退；关系层复用 assessment。**同日顺手项 D**：意识流 prompt 注入 `season_hint`（db 读关系季节，默认 spring）。**同日包 B**：叙事向量改 BGE-small-zh ONNX（CLS+L2）；n-gram 回退；Chroma 按 `qi_embedding` 重建回灌。**同日阶段一·包 1**：episodes 表 + 编织同步 role_map（type→说话人）；梦=未巩固积压驱动 + 加权选题；LLM/模板降级链；body_memory 决策 trace；`dream_retention` 衰减不动。叙事正文本体织反纠偏另立项。
