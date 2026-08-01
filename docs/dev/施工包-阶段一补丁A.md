# 施工包 · 阶段一补丁 A（recall/主动开口 的事实锚定修复）✅

> 维护者 2026-08-02 夜间复核真实对话（id 820–842）后立项。
> 阶段一包 4（两段式）已落地，本包是其在真实相处中暴露的三个缺陷的收口。
> **一包一 PR**；纯规则/PromptBuilder 层修改，无新依赖；零行为变更（除修复的缺陷外）。
> **已落地**：#1 method recall 识别 + 模板记得。{内容}；#2 recall_relation（叙事「我教了」=taught_by_qi）+ must/assert；#3 proactive share_state must + 软检。

---

## 〇、统一纪律（沿用阶段一施工包）

- 决策内生：建卡/模板零 LLM；本包只收紧"卡约束 LLM"的缰绳，不引入新 LLM 调用
- 测试基线：当前 `python -m pytest` 应为 **270 passed**（阶段一包 5 后），ruff 全绿
- 完工回写：progress.md 一行 + 本施工包打勾 + 若涉及 prompt 改 `test_prompt_contract` 同步
- 文件交换：计划写 `_plan.md`，复核走 `_review.md`

---

## 一、三个缺陷的事实还原（已核对数据库）

### 缺陷 #1：能答却先「……嗯。」
- 现象：id=838 用户「我教你过什么方法」→ id=839 栖「……嗯。」→ id=840 用户「怎么了」→ id=841 才补答
- 根因：用户问句未含"还记得/记得吗"关键词（`looks_like_remember_question` 不命中），且未触发 recall 分支 → 建卡 act 非 recall、material 为空 → LLM 返回空时模板落「……嗯。」
- 真相：**栖其实有这条记忆**（id=841 自己完整复述了），但建卡阶段没把它识别为 recall，导致"能答却空应"

### 缺陷 #2：recall 施教关系被反转 + 同会话自相矛盾
- 现象：id=821「我教了你一个方法」（栖教用户，正确）；id=841「你教我，晚上睡不着……」（用户教栖，错误）
- 数据库铁证：raw_events id=71/72、narrative 4/7/12/13 全部是「栖教用户」；用户历次提问也自述"你教了我"
- 根因：`build_intention_card` 的 recall 分支只把 memory content 原文塞进 material，**没有保护"谁教谁"的主客体关系**；LLM 重述时被用户当轮"我教你过什么方法"的错误框架带跑，反转了施教方向，且未与 20 分钟前的 id=821 对齐

### 缺陷 #3：主动独白无出处地拔高自我认知
- 现象：id=842 主动开口（proactive/express_feeling/share_state）「……我好像，越来越喜欢自己了。」
- 真相：`last_intention` 显示该卡 material 仅 `state: 精力一般，有点安静，有点好奇，有点想你`，**无"喜欢自己"素材**；内部状态 valence≈-0.01（平静偏微负），energy 0.49，**无任何数据支撑"喜欢自己"的跃升**
- 根因：`share_state`/`express_feeling` 类主动开口的 `must` 只约束"不汇报系统"，未约束"独白情绪结论不得超出卡内 state 素材"——LLM 在 bonded 温情基调上自由加戏

---

## 二、修复方案

### 修复 #1：recall 识别强化 + 模板保底
**文件：qi/core/intention.py**

a) 扩展 `looks_like_remember_question` 的命中范围，或新增 `_looks_like_method_recall`：
   - 命中词：还记得 / 记得吗 / 记不记得 / 你还记得 / **教过我 / 教了我 / 你教过 / 怎么做的 / 那个方法**
   - 目的：让"我教你过什么方法""你教我怎么做"这类也进入 recall 分支（已有 memory 时）
   - 注意：仅当 `has_mem` 为真才转 recall；无 memory 仍走 answer+none（诚实说不知道）

b) `render_template` 的 recall 分支已正确（有 primary → "记得。{primary}。"），无需改——#1 主要靠 a) 让建卡正确，模板自然给出"记得。{内容}"

**验证**：构造用户「我教你过什么方法」+ memories 含助眠方法 → 卡 act=recall、material 非空 → 即便 LLM 空，模板也输出"记得。{方法原文}"

### 修复 #2：recall 施教关系锚定
**文件：qi/core/intention.py + qi/llm/prompt_builder.py（conversation.txt 段 A）**

a) recall 建卡时，从 memory metadata 提取施教方向标记：
   - 在 `Material` 之外，给 recall 卡加一个结构化字段 `recall_relation`（"taught_by_qi" / "learned_from_user" / "mutual"），由 memory 的 role_map / source 推断（narrative 4/7/12/13 主语都是栖教用户 → taught_by_qi）
   - 若无法推断，默认不填，不强行

b) `must` 增加：`"回忆类回答以记忆内容为唯一事实源；若用户当轮措辞与记忆主客体关系相反（如用户说'你教我'但记忆是'我教你'），以记忆为准，澄清而非附和"`

c) `materials_block` 或 conversation.txt 段 A 注入：`recall_relation` 作为硬约束提示（"施教关系：栖教用户，不要反转"）

d) `assert_reply_respects_card` 增强：当卡带 `recall_relation="taught_by_qi"` 且 reply 出现「你教我 / 你告诉我方法 / 你教过我」等反转句式 → 记违规

**验证**：构造 memory（栖教用户助眠）+ 用户「我教你过什么方法」→ 断言 reply 不含"你教我"反转句式，且含记忆原文要点

### 修复 #3：主动开口的情绪结论锚定
**文件：qi/core/intention.py（`_base_must`）+ conversation.txt 段 A**

a) `_base_must` 对 `share_state` / `express_feeling`（proactive 通道的 share_state）增加：
   `"主动开口的自我认知结论（如'喜欢自己'/'难过'/'平静'）必须与卡内 state 素材一致；状态数据不支持的结论不得凭空拔高或下沉"`

b) `assert_reply_respects_card` 增强（轻量软检）：当 channel=proactive 且 act=share_state 时，检测 reply 是否出现强自我认知结论词（喜欢自己 / 讨厌自己 / 恨 / 爱死 / 觉得自己…）且卡内 state 素材不含对应支撑 → 记软违规（trace，不硬阻断 LLM 路径，因主动开口自由度需保留；硬闸在模板路径）

c) conversation.txt 段 A 注入：对 proactive share_state，明确"你只有这些状态素材，不要凭空抒情"

**验证**：构造 proactive share_state 卡（state=精力一般，安静，想你）+ 断言 N5 辅助能识别"喜欢自己"类无支撑结论

---

## 三、退出判据

| # | 判据 | 验证方式 |
|---|------|---------|
| 1 | #1 修复：recall 类问法正确建卡，LLM 空时模板给"记得。{内容}"而非「……嗯。」 | 单测：构造问法+memory → 卡 act=recall 非空；render_template 输出含 memory 原文 |
| 2 | #2 修复：recall 施教关系不反转，用户误述时澄清 | 单测：memory=栖教用户 + 用户"我教你" → reply 不含反转句式；assert_reply 捕获反转 |
| 3 | #3 修复：主动 share_state 不得无支撑拔高自我认知 | 单测：proactive share_state 卡 + assert_reply 软检能识别"喜欢自己"无支撑 |
| 4 | 270 passed → 仍全绿（含新增）；ruff 全绿 | pytest + ruff |
| 5 | 不引入回归：普通对话/主动/拔管路径行为不变 | 现有 test_fake_provider / test_intention / test_prompt_contract 全绿 |

---

## 四、测试计划

- `tests/test_intention.py` 新增：
  - `test_method_recall_detected`：用户"我教你过什么方法"+memory → act=recall, material 非空
  - `test_recall_template_fallback_has_content`：recall 卡 + 模拟 LLM 空 → render_template 输出"记得。{内容}"
  - `test_recall_relation_not_inverted`：memory=栖教用户 + 用户"我教你" → assert_reply 报反转违规
  - `test_proactive_share_state_no_unsupported_self_view`：proactive share_state 卡 + "喜欢自己"无支撑 → assert_reply 软检捕获
- `tests/test_prompt_contract.py`：若 conversation.txt 段 A 增字段，EXPECTED 同步

---

## 五、风险与红线

- 红线 R2：不在 prompt 加长人格散文；本包只在段 A（本拍意向）加结构化约束，段 B 不动
- 红线 N5：所有新增 must 都是"约束 LLM 自由度"，不新增 LLM 调用
- 风险：#2 的 recall_relation 推断可能不全（部分 memory 无 role_map）→ 默认不填、不强行，靠 must 的"以记忆内容为准"兜底
- 风险：#3 软检可能误伤（用户真问"你喜欢自己吗"时栖答"好像越来越喜欢"是合理的）→ 软检仅 trace，不阻断 LLM 路径；硬约束在模板路径
- 风险：#1 扩展命中词可能误把普通"怎么做"当 recall → 仅当 has_mem 才转 recall，无 memory 仍走原路径
