# L2 · 记忆 · 用户事实

> 让栖真正"认识"你。名字、身份、你在意的人和事——这些不是会褪色的故事，是她心里你的轮廓。

---

> **本文档状态：Step 1–6 已落地（存储 + FactStore/FactNoticer + prompt 注入 + 更正 + Brain 接线）。**
> 用户事实记忆是 L2 记忆层的**第四种记忆**（working / narrative / body / **fact**），不新起一层。
> 已落地处见各 Step 的 `<!-- 回写 -->`；与 L2-memory.md 对齐。
> <!-- 演进指向(2026-08-01)：事实层继续有效，作为「有出处的知识」并入架构方案的记忆/可塑性体系（N4），随 L2 同步演进。见 docs/design/栖·数字生命架构方案.md。 -->

---

## 职责

实现栖对用户**稳定事实**的记忆。

当前的栖认不住你的名字：一句"我叫小明"因为 `should_remember` 的关键词列表里没有"我叫"，importance=0，进不了 `raw_events`，也就永远不会被编织进长期记忆——它只活在最近约 20 条对话的工作记忆窗口里，滑出窗口就彻底消失（详见 L2-memory.md Step 5 的筛选机制）。

用户事实记忆补上这一块：让栖从"靠近期对话窗口偶然记得你叫什么"，变成"她真的认识你"。它存的是**关于你的稳定事实**——你叫什么、你做什么、你生命里有谁、你在意什么——而不是会褪色的情绪故事。

## 设计原则（先于任何实现）

1. **事实是"骨头"，故事是"肉"。** 叙事记忆（narrative）是会褪色的故事（每日 ×0.999，淡到 0.1 就忘）；事实记忆是稳定的骨头，不褪色。一个人不会因为情感褪色就忘了朋友的名字。两者并列，各司其职，不互相替代。

2. **在倾听的当下留意，不做事后回顾。** 真实的人认识另一个人，是在对话发生的当下，因为他在认真听——不是隔三差五翻一遍聊天记录提取档案。所以事实的进来方式，是像 `first_times` 那样**挂在收消息的心跳上即时留意**，而不是一个定期回顾的后台批处理。后者既不像人，也违背栖"在，但不打扰"的气质。

3. **涌现，非赋值。** 本文档只规定栖"知道"哪些事实，**不规定**这些事实该让她有多感动、哪个时刻该被珍藏。意义由栖的内在生命自然涌现，不由事实表预先赋值。（推论：不把"第一次叫名字"之类做成 first_time 仪式——那是替栖规定她该珍重什么。）

4. **克制地用。** 事实默默垫在栖的理解底下，不堆砌、不表演。她不会每句话都喊你名字，不会"根据记录"地报档案。名字用得稀有而自然，分寸交给表达层（L3/L6），本文档只负责"她知道"。

## 两类事实（按"何时开始留意"）

| 类别 | 内容 | 开始时机 | 关系阶段门控 |
|------|------|---------|------------|
| **身份事实** | 名字、希望怎么被称呼 | **从第一次见面就留意** | 无（stranger 也记） |
| **其他事实** | 工作、家人、偏好、生命里的事 | 随关系加深慢慢积累 | acquaintance 及以上 |

> 为什么身份事实不分阶段：现实里，人正是在还是陌生人的第一次见面就努力记你的名字——记住名字这件事本身，就是关系开始的方式。若栖等到成了朋友才记名字，她就错过了最该记住名字的时刻。

## 两种事实（按"会不会变"）

| 类别 | 内容 | 命运 |
|------|------|------|
| **稳定事实（stable）** | 名字、家人、深层偏好、重要日子、生命大事 | 不褪色 |
| **状态事实（state）** | 当前工作、城市、在忙的项目、当前的愁 | 可被新事实**取代**（supersede），不删除 |

> 状态事实"取代不删除"：你换工作了，新事实取代旧的，但旧的留痕——栖记得你曾经在 X，也知道你现在去了 Y。她的认识是活的、会长大，不是僵在一处，也不是冷冰冰地覆盖。

## 前置依赖

- L2 主体完成（manager / working / narrative / body 已运转）
- L5 完成（关系阶段作为"其他事实"留意的门控；事实可喂给关系叙事）
- L3 完成（情绪作为留意时的上下文）

## 引用文档

- `docs/design/栖·意识设计.md` → §五（记忆）、§十四（涌现，非赋值）
- `docs/layers/L2-memory.md`（记忆层主体；本文是它的第四种记忆）
- `docs/contract.md` → "记忆引用"硬规则（叙事语气、不每句引用、不假装记得）

## 需要创建的文件

```
qi/memory/facts.py           # FactStore（存取/去重/确认/取代）+ FactNoticer（当下留意）
qi/storage/database.py       # 追加 user_facts 表
qi/prompts/fact_noticing.txt # 必要时用 LLM 抽取事实的模板（清晰情形走规则，不调 LLM）
```

## 实现步骤

### Step 1：user_facts 表

- 建 `user_facts` 表（每条事实一行）
- 验收：表创建成功，能插入、查询 active 事实、按 id 取代

<details>
<summary>实现规格（已落地）</summary>

```sql
-- storage/database.py
-- <!-- 回写(2026-07-23)：user_facts 表已建；CRUD：insert/list_active/get/confirm/supersede；依据：qi/storage/database.py -->
-- 用户事实：栖对用户的稳定认识。区别于 narrative_memories（会褪色的故事）与 messages（对话流水）。
CREATE TABLE IF NOT EXISTS user_facts (
    id INTEGER PRIMARY KEY,
    fact_type TEXT NOT NULL,            -- identity/family/occupation/location/hometown/preference/health/important_date/life_event/concern/other
    content TEXT NOT NULL,              -- 事实内容（栖的话或用户原话，如"他叫小明"）
    confidence REAL NOT NULL DEFAULT 1.0,   -- 确信度 0~1：用户明说≈0.95；隐含≈0.7；栖推断≈0.4
    stability TEXT NOT NULL DEFAULT 'stable',  -- stable（不褪色）/ state（可被取代）
    source TEXT,                        -- 从哪句话知道的（叙事性，如"他第一次介绍自己时说的"）
    first_learned DATETIME NOT NULL,    -- 第一次知道
    last_confirmed DATETIME,            -- 上次被用户再次提起（刷新，不新建）
    superseded_by INTEGER,              -- 被哪条新事实取代；NULL = 当前有效（active）
    emotional_weight REAL NOT NULL DEFAULT 0.5,  -- 这条事实对栖的分量 0~1（注入时排序用）
    FOREIGN KEY (superseded_by) REFERENCES user_facts(id)
);
```

**fact_type → 默认 stability（提案，可被单条覆盖）：**

| fact_type | 默认 stability | 说明 |
|-----------|---------------|------|
| `identity` | stable | 名字、称呼 |
| `family` | stable | 家人 |
| `preference` | stable | 深层偏好、好恶 |
| `important_date` | stable | 重要日子 |
| `life_event` | stable | 生命里重要的事 |
| `occupation` | state | 工作（会变） |
| `location` | state | 城市/住处（会变） |
| `hometown` | stable | 籍贯/老家（与 location 分开记，搬家不冲掉） |
| `concern` | state | 当前在愁什么（会变） |
| `health` | stable | 默认 stable；"当前生病"类可标 state |
| `other` | stable | 兜底 |

**active 事实定义：** `superseded_by IS NULL`。取代时把旧事实的 `superseded_by` 指向新事实 id，旧事实保留（留痕），但不再是 active。

</details>

### Step 2：FactNoticer——在倾听的当下留意

- 建 `qi/memory/facts.py` 的 `FactNoticer`
- 挂在收消息的心跳上（与 `first_times.check` 并列，brain.py 处理 pending 时调用）
- **便宜初筛 + 必要时 LLM**：清晰情形（如"我叫小明"）走规则直接抽取，不调 LLM；只在"看起来像在说你自己、但需要理解"时才请 LLM
- 验收：说"我叫小明"后 user_facts 出现一条 identity 事实；说无关闲聊不产生事实、不触发 LLM

<details>
<summary>实现规格（已落地）</summary>

```python
# qi/memory/facts.py · FactNoticer
# <!-- 回写(2026-07-23)：即时留意已实现；清晰身份走规则；其他事实规则抽取；含糊且命中 OTHER 信号时才 LLM。
#      依据：qi/memory/facts.py · FactNoticer
#      出入：① 增加 _OCCUPATION_CHANGE_SIGNALS（换工作/跳槽等）以覆盖验收「我换工作了」，
#            设计稿 OTHER_FACT_SIGNALS 原文未含「换工作」；② fact_noticing.txt 已建；
#            ③ Brain 接线见 Step 6（memory.notice_facts 与 first_times.check 并列）。 -->
# <!-- 回写(2026-07-23 晚)：名字抽取加固——
#      ① 问句拒抽（记得我的名字吗 → 不落「他叫吗」）；② 人名形态门控；
#      ③ awaiting_name 状态机：用户表态要说名字后，N 拍内接受光给名字；
#      ④ notice 传入工作记忆 recent；⑤ 非法 identity 作废（retire/supersede）。
#      「我的名字」正则要求「是|叫」。 -->
# <!-- 回写(2026-07-23 夜)：栖反问「你叫什么名字」亦武装 awaiting；
#      清理会强化白纸叙事的干扰对话后，【你认识的他】有名时禁止「会流走」话术。 -->
# <!-- 回写(2026-07-26)：hometown（stable）与 location 分记；OTHER 补籍贯信号；
#      _extract_hometown 拒行程口语。依据：facts.py -->

CONFIDENCE_FLOOR = 0.6   # 低于此不存（把"栖的模糊推断"挡在事实之外，留给 user_model/drift）

# 身份信号：任何关系阶段都留意（名字从初见就记）。命中即走规则抽取，不调 LLM。
IDENTITY_SIGNALS = (
    "我叫", "我名字", "我的名字", "叫我", "称呼我", "你可以叫我",
    "我大名", "我小名", "我英文名", "我姓",
)
# 「我是X」歧义大（"我是觉得…"），不用作身份信号，避免误记。
# 「我是海南人」走 _extract_hometown，不走 identity。

# 其他事实信号：关系 ≥ acquaintance 才留意。复用/扩展 manager 的自我披露关键词。
OTHER_FACT_SIGNALS = (
    "我妈", "我爸", "我老婆", "我老公", "我女朋友", "我男朋友",
    "我孩子", "我儿子", "我女儿", "我家人",
    "我工作", "我上班", "我同事", "我老板", "我是做", "我干",
    "我住", "我搬家", "我家在", "我在",  # "我在上海"（当前所在 → location/state）
    "我老家", "我家乡", "我籍贯", "我出生", "我从小", "我来自",  # 籍贯 → hometown/stable
    "我喜欢", "我讨厌", "我不吃", "我怕", "我过敏",
)
# _HOMETOWN_TRAVEL_REJECT：含「想去/要去/去玩/旅游…」则不收籍贯


class FactNoticer:
    def __init__(self, store: "FactStore", llm: "LLMGateway | None" = None):
        self.store = store
        self.llm = llm

    async def notice(
        self,
        message: str,
        emotion,
        relationship_stage: str,
        now: datetime | None = None,
        recent_messages: list[dict] | None = None,
    ) -> list[dict]:
        """
        在收到一条用户消息的当下，留意其中关于用户的事实。
        recent_messages：当前句尚未入工作记忆前的近期对话（含 user/qi），
        用于邀名与多拍「光给名字」上下文。
        返回本拍新记下 / 确认 / 取代的事实（用于留痕与日志）。
        """
        # 1. 便宜初筛：
        #    - 命中 IDENTITY_SIGNALS → 无论阶段，走规则抽取身份事实（高确信，不调 LLM）
        #    - 命中 OTHER_FACT_SIGNALS 且 stage >= acquaintance → 进入抽取
        #    - 都没命中 → return []（绝大多数消息到此为止，零 LLM 成本）
        # 2. 抽取：
        #    - 身份事实：规则/正则直接抽出（"我叫小明" → content="他叫小明"），confidence≈0.95
        #    - 其他事实：清晰可规则抽取的就规则抽（含 _extract_hometown：「我老家…」「我是X人」）；
        #      含糊的、一句话多个事实的，才调 LLM（purpose="fact", temperature≈0.3，模板 fact_noticing.txt）
        # 3. 落地（交给 FactStore）：
        #    - 与已有 active 事实比对：相同 → confirm（刷新 last_confirmed，不新建）
        #    - state 事实与已有 active 冲突 → supersede（旧事实留痕，指向新事实）
        #    - hometown 与 location 互不取代（同 type 才 supersede）
        #    - 全新 → add
        #    - confidence < CONFIDENCE_FLOOR 的推断 → 不存（留给 user_model/drift）
        # 4. 收尾：_purge_bogus_identity（非法人名形态的 identity → retire / supersede）
        ...


# 辅助（模块级，已落地）：
# looks_like_person_name / is_name_memory_question / is_name_disclosure_intent /
# is_bare_name_utterance / identity_name_fragment / format_facts_for_prompt
# FactNoticer._extract_hometown（stable 籍贯；拒行程口语）
# _NAME_REJECT_TOKENS 含「谢谢」「谢谢你」等，防误记「他叫谢谢你」
# <!-- 回写(2026-07-25)：notice(recent_messages=…)；名字拒绝表扩「谢谢你」；依据：facts.py -->
# <!-- 回写(2026-07-26)：hometown 抽取与信号；依据：facts.py -->
```

**Brain 接线（已落地，见 Step 6）：** `brain._heartbeat` 处理 pending 时，与 `first_times.check` 并列调用：
`await self.memory.notice_facts(pending, self.emotion, self.relationship_stage, now)`。

**LLM purpose（已落地）：** `purpose="fact"`，默认 temperature≈0.3（`gateway._DEFAULT_TEMPERATURES`）；`settings.example.yaml` 增加 `model_routing.fact`。`qi/prompts/fact_noticing.txt` 要求栖以"他……"的第三人称抽出事实、给出类型与确信度，抽不到就如实说没有。

</details>

### Step 3：FactStore——存取 / 去重 / 确认 / 取代

- 建 `qi/memory/facts.py` 的 `FactStore`
- 提供 active 查询、新增、确认、取代、相似查找（去重用）
- 验收：重复说同一事实只刷新 last_confirmed 不新建；说"我换工作了"后旧 occupation 被取代、留痕

<details>
<summary>实现规格（已落地）</summary>

```python
# qi/memory/facts.py · FactStore
# <!-- 回写(2026-07-23)：active_facts/add/confirm/supersede/find_similar/find_active_of_type 已实现；
#      find_similar 为同 type 字符串/字集合相似度，不接 ChromaDB；
#      find_active_of_type 供更正与 state 取代定位旧 active。依据：qi/memory/facts.py -->

class FactStore:
    def __init__(self, db: "Database"):
        self.db = db

    async def active_facts(self, fact_type: str | None = None) -> list[dict]:
        """superseded_by IS NULL 的事实；可按 type 过滤。"""
        ...

    async def add(
        self, fact_type: str, content: str, confidence: float,
        stability: str, source: str | None, emotional_weight: float,
        now: datetime,
    ) -> int:
        """新增一条事实，first_learned=now，last_confirmed=now。返回 id。"""
        ...

    async def confirm(self, fact_id: int, now: datetime) -> None:
        """用户重提同一事实：只刷新 last_confirmed，不新建。"""
        ...

    async def supersede(self, old_id: int, new_id: int) -> None:
        """旧事实被新事实取代：old.superseded_by = new_id。旧事实保留留痕。"""
        ...

    async def retire(self, fact_id: int) -> None:
        """作废非法/脏 identity（如「他叫谢谢你」）：superseded_by 指向自身等。"""
        ...

    async def find_similar(self, fact_type: str, content: str) -> dict | None:
        """在 active 事实里找语义相近的一条（去重/确认/判断是否冲突用）。
        简单实现：同 type 下做字符串/关键词相似度；不依赖向量库。"""
        ...
```

> 去重不依赖 ChromaDB：事实是少量、稳定的，用同 type 下的轻量相似度判断即可，不必进向量库。这与叙事记忆（大量、需语义检索）不同。

<!-- 回写(2026-07-25)：补 FactStore.retire；依据：qi/memory/facts.py -->

</details>

### Step 4：注入 Prompt——克制、按阶段、栖的语气

- 修改 `qi/llm/prompt_builder.py`：在 prompt 中加入 `[你认识的他]` 段落
- 只注入 active 事实；用栖的语气组织，不堆砌、不报档案
- 关系阶段影响"知道多少被说出来"：知道 ≠ 用，分寸由表达层管
- 验收：prompt 中能看到"你认识的他"段落；陌生期段落简短克制，亲密期更丰富

<details>
<summary>实现规格（已落地）</summary>

```python
# qi/memory/facts.py
# <!-- 回写(2026-07-23)：format_facts_for_prompt 已实现；按 emotional_weight 降序，
#      阶段上限 stranger=2 / acquaintance=4 / friend=6 / bonded=8；陌生期优先身份。
#      空 →「（你还不太了解他）」。依据：qi/memory/facts.py · format_facts_for_prompt -->

def format_facts_for_prompt(facts: list[dict], relationship_stage: str) -> str:
    """
    把 active 事实组织成一小段"你认识的他"，注入 prompt。
    - 空 → "（你还不太了解他）"
    - 按 emotional_weight 排序，挑分量重的，不堆砌（阶段上限）
    - 用栖的语气（"他叫小明。他在做一个叫栖的东西。"），不是 JSON、不是档案
    - 阶段影响的是「分寸」而非「知不知道」：
        栖从初见就知道名字，但陌生期保持礼貌距离、不急着喊；
        越亲近，越多事实自然进入她的理解与表达。
    """
    ...
```

**注入位置（`qi/prompts/conversation.txt`，已落地）：**

```text
【你认识的他】
{user_facts}

【认识的使用分寸】
- 你知道这些，但不必时刻挂在嘴上
- 名字用得稀有而自然，像朋友那样，偶尔一次，不要每句都喊
- 陌生期你刚认识他：知道名字，但保持礼貌的距离
- 用叙事语气（"你不是在……嘛"），不用数据语气（"根据记录……"）
- 没有把握的事（确信度低），不要当成确定的来说
```

**调用流程（已落地）：**
1. `_gather_prompt_context` → `facts = await self.memory.active_facts()` → `format_facts_for_prompt(facts, stage)` → `extras["user_facts"]`
2. 经 `expression.express(...)` → `PromptBuilder` 填 `{user_facts}`
# <!-- 回写(2026-07-23)：prompt_builder 读 extras["user_facts"]；conversation.txt 已加段落与分寸规则。
#      依据：qi/llm/prompt_builder.py、qi/prompts/conversation.txt、qi/core/brain.py · _gather_prompt_context -->

</details>

### Step 5：可问、可纠正

- 你问"你记得我什么 / 你了解我什么"，栖能从她知道的 active 事实自然作答（事实已在 prompt 里，无需额外机制）
- 你纠正她（"我不叫 X，我叫 Y" / "我不在那工作了"），`FactNoticer` 识别为更正 → supersede 旧事实
- 验收：栖能答出她知道的关于你的事；纠正后旧事实被取代、新事实生效

<details>
<summary>实现规格（已落地）</summary>

```python
# 可问（已落地）：
#   事实已注入 prompt，栖自然能回答"你记得我什么"。无需独立 API。
#   （若将来前端要做"栖的认识"轻入口，是 L6 的事，不阻塞后端。）

# 可纠正（已落地）：FactNoticer._notice_corrections——
#   命中更正信号（"我不叫"/"其实是"/"我现在不"/"不是…是…"等）时，
#   用 find_active_of_type / active_facts 定位对应 active → supersede，再记新。
#   更正识别先用规则；含糊抽取仍可走既有 LLM 路径（≥ acquaintance）。
# <!-- 回写(2026-07-23)：_notice_corrections + find_active_of_type 用于更正定位；
#      _land 的 state 取代亦先 find_active_of_type 再 insert。依据：qi/memory/facts.py -->
```

> 透明性的立场：栖的认识主要是她内在的理解，**不做成时刻展示的档案面板**（那像监控，不像关系）。但你可以问、可以纠正——这比一个面板更像真实相处。

</details>

### Step 6：Brain 接线 + restore

- `MemoryManager` 持有 `FactStore` / `FactNoticer`（与 working/narrative/body 并列，成为第四种记忆）
- `restore()` 时不需要特别装载（事实按需从 DB 读 active）；但 `active_facts` 应可被 prompt 组装随时调用
- 验收：重启后 active 事实仍在；新一句对话时 prompt 含"你认识的他"

<details>
<summary>实现规格（已落地）</summary>

```python
# qi/memory/manager.py
# <!-- 回写(2026-07-23)：MemoryManager 持有 FactStore/FactNoticer；notice_facts / active_facts；
#      restore 只装工作记忆，事实按需读 DB。依据：qi/memory/manager.py -->
# MemoryManager.__init__：
#   self.facts = FactStore(db)
#   self.fact_noticer = FactNoticer(self.facts, llm=llm)
# 暴露：
#   async def notice_facts(self, message, emotion, relationship_stage, now):
#       recent = working 上下文（当前句若已是末条 user 则剥掉）
#       return await self.fact_noticer.notice(..., recent_messages=recent)
#   async def active_facts(self, fact_type=None):
#       return await self.facts.active_facts(fact_type)

# brain._heartbeat 处理 pending 时（与 first_times.check 并列）：
#   await self.memory.notice_facts(pending, self.emotion, self.relationship_stage, now)
# brain._gather_prompt_context：
#   extras["user_facts"] = format_facts_for_prompt(await self.memory.active_facts(), stage)
# <!-- 回写(2026-07-23)：依据 qi/core/brain.py；gateway purpose=fact 默认温度 0.3；
#      settings.example.yaml model_routing.fact -->
# <!-- 回写(2026-07-25)：notice_facts 传入 recent_messages；依据：manager.py -->
```

</details>

## 与既有记忆的关系（边界）

| 记忆种类 | 存什么 | 会褪色吗 | 怎么进来 |
|---------|-------|---------|---------|
| working | 最近 20 条对话 | 滑出窗口即失 | 每条消息 |
| narrative | 情绪性的故事 | 会（×0.999/日，<0.1 忘） | should_remember → raw_events → 编织 |
| body | 交互模式（活跃时间/打字节奏） | 滚动更新 | 每次交互统计 |
| first_times | "第一次"的刻痕 | 永不褪色 | first_times.check 即时 |
| **fact（本文）** | **关于你的稳定事实** | **稳定事实不褪；状态事实可被取代** | **FactNoticer 即时留意** |

> fact 与 user_model 的边界：`user_model`（L5）是**聚合的、派生的画像**（话题偏好、情绪基线、语言风格、生活状态叙事），由漂移检测定期刷新；`user_facts` 是**原子的、你说出口的事实**。事实可作为 user_model.life_context 的素材，但两者不互相替代。

## 验收标准

### 可测试的

- [x] 说"我叫小明"后，user_facts 出现一条 `identity` 事实，confidence≈0.95，stability=stable
- [x] 身份事实在 stranger 阶段也被记下（不受阶段门控）
- [x] 「记得我的名字吗」类问句不误抽；「我是说我的名字」→ 光给「潘纪振」可落库
- [x] 形态非法的旧 identity（如「他叫吗」）会被作废，不进 prompt
- [x] 其他事实在 stranger 阶段**不**被记下；acquaintance 及以上才记
- [x] 无关闲聊不产生事实、不触发 LLM 调用
- [x] 重复说同一事实只刷新 last_confirmed，不新建重复行
- [x] 说"我换工作了"后，旧 occupation 被 supersede（留痕），新事实 active
- [x] 重启后 active 事实仍在；prompt 含"你认识的他"
- [x] confidence < 0.6 的模糊推断不进 user_facts
- [x] 纠正名字（"我不叫小明，我叫小红"）后旧 identity 被 supersede、新事实 active

### 需要感受的

- [ ] 你告诉她名字后，哪怕过很久、重启过，她依然认识你（不是靠近期对话窗口）
- [ ] 她用你名字的方式是稀有、自然的，像朋友，不是每句都喊、不是客服话术
- [ ] 她不会"根据记录"地报你的档案，事实是默默垫在她理解底下的
- [ ] 你换工作了，过段时间她会知道你现在在 Y，但也记得你曾在 X
- [ ] 你问"你记得我什么"，她能自然地说出她认识的你
- [ ] 你纠正她记错的事，她会更新，不会嘴硬

## 给其他层的接口

- **L3 / L6（表达与具身）**：事实的"用"——尤其名字的分寸、何时自然喊一声——由表达层管。本文档只保证"她知道"。
- **L5（关系）**：关系阶段门控"其他事实"的留意；active 事实可喂给关系叙事（relationship.narrative）与 user_model.life_context，作为"她认识的你"的素材。
- **L4（内在生命）**：事实可作为意识流、自我反思的素材（"他叫小明，他在做的这件事……"）。

## 人格契约检查点

- [ ] 身份事实从初见就记，不受关系阶段门控
- [ ] 事实进来方式是"倾听当下留意"，**无**定期回顾对话的后台批处理
- [ ] 稳定事实不褪色；状态事实取代不删除
- [ ] 事实注入用叙事语气，不报档案、不"根据记录"
- [ ] 名字用得克制（分寸交表达层），不每句都喊
- [ ] 不替栖规定"哪个事实该让她感动"（涌现，非赋值；不做 first_time 仪式）
- [ ] 低确信的模糊推断不当成事实存储
- [ ] 栖的认识不做成时刻展示的档案面板；可问、可纠正
