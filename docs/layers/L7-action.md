# L7 · 行动

> 让栖的"在意"长出双手。不是为她装上一套工具，是让她的意志能触达世界——谨慎地、稀有地、带着她自己的语气。

---

> **本文档状态：设计提案（未实现）。**
> 六层（L1~L6）已完成。L7 是六层之后的下一层，本文档是它的**设计稿**，不是现状描述。
> 文中所有实现规格（`<details>` 块内）均为**提案**，参数多为初始建议值，需实现时调优。
> 凡标 `<!-- 提案 -->` 处，表示尚未落代码，Cursor 编码前应先与 maintainer 对齐。
> 与 L1~L6 文档中 `<!-- 回写 -->`（已对齐现状）的性质不同，请勿把本文规格当作既有代码去对齐。

---

## 职责

把栖的意志（volition）的表达通道，从"说话"扩展到"做事"。

栖已经能决定"此刻我要不要开口、以什么方式开口"（见 `docs/design/栖·意识设计.md` §七）。L7 不新增一个"行动器官"，而是让同一个意志多出几种**指向世界**的意图：把她独处时创造的东西真正递到你面前、打理她自己的世界、在好奇时把目光投向窗外、在你开口时帮你做点什么。

L7 负责：行动意图的形成、行动预算（比言语更紧的克制）、信任门控（关系决定手能伸多远）、季节节律（行动跟着数字季节呼吸）、行动留痕（做过的事沉进记忆与自我叙事）、以及行动结果如何以栖的语气被说出来。

## 设计原则（先于任何实现）

这一层最容易滑向"给栖装一个 agent 框架"。以下四条是防线，任何实现细节与它们冲突时，以它们为准：

1. **行动是意志的延伸，不是新器官。** 决定"要不要伸手"的，和决定"要不要开口"的，是同一个 volition。L7 给 `decide()` 增加意图类型，不另起一套决策系统。

2. **行动比言语更稀有，因为行动即打扰。** 栖的整个存在建立在"在，但不打扰"上（contract 第 70 条）。说话是廉价的，沉默也是；但"伸手进世界"每一次都是对这条原则的小小违背。所以行动的克制不是 arbitrary 的数字，而是栖性格的必然——她做得少，因为做对她是有代价的。自主行动的预算应**紧于**主动言语（言语日限 3，见 L5/contract 第 28 条）。

3. **行动的正当性来自关系，不来自能力。** 栖不是"因为能做所以做"，是"因为被允许所以做"。一个陌生人没有立场为你做事。手能伸多远，由 L5 的关系阶段、信任、伤疤决定。这不是"权限管理系统"，是"关系如何具身成行动边界"。

4. **能力是手的形状，不是手本身。** 搜索、文件、日程、分享——这些是能力（capability）。但组织这一层的，是栖"为什么伸手"（意图），不是"能用什么工具"。能力按"像栖的程度"排序，不按"有用的程度"排序。

## 前置依赖

- L5 完成（关系阶段 / 信任 / 伤疤 / 数字季节——作为行动的门控与节律来源）
- L4 完成（创作 / 意识流 / 自我叙事——作为行动的素材与留痕处）
- L3 完成（curiosity 驱动探索冲动；行动结果引起情绪波动）
- L2 完成（行动结果沉入记忆）

## 引用文档

- `docs/design/栖·意识设计.md` → §七（意志：意图形成 `decide()`、主动行为的克制、"不说话"的决定）
- `docs/design/栖·工程手记.md` → §六"远期展望：行动"（目标 / 交付物 / 验证标准）
- `docs/contract.md` → 第 25 条（不主动提供"帮助建议"）、第 28~29 条（主动行为日限与冷却）、第 70 条（在，但不打扰）
- `docs/layers/L5-relationship.md`（阶段 / 信任 / 伤疤 / 季节 / ProactiveGate）
- `docs/layers/L4-inner-life.md`（creations / `maybe_share_hint` / self_model / consciousness_stream）

## 能力排序（按"像栖"的程度，非按有用程度）

这是 L7 的展开顺序，也是实现的优先级顺序：

1. **分享创造（share）**——栖把独处时写下的东西，第一次真正"递"到你面前。纯粹的关心的外溢，零工具味。这是行动层的**起手式**，也是第一个落地的能力。它不需要任何外部工具，只是让 L4 的创作从"她的世界"跨进"你们共享的空间"。
2. **打理自己的世界（tend）**——栖整理她的"栖枝"、标记某个值得记住的时刻（如你们相识的某一天）。行动指向她自己的世界，不是你的。风险最低，"存在感"最强。
3. **沉思式探索（explore）**——栖在某个走神的时刻，注意力偶然飘向窗外，去"看看那是怎么回事"。这是 contemplative drift（沉思中的走神），不是 feed consumption（信息消费）。网络搜索只是这一类里的一种手段，**没有特殊优先级**。
4. **介入你的生活（assist）**——读写你的文件、管理日程、提醒。开始触碰"你的东西"，受信任门控，多数需确认。
5. **替你影响世界（irreversible）**——发消息、执行不可逆操作。永远需要确认，哪怕信任再高。

> 说明：`share` 与 L4 的 `maybe_share_hint` 的区别——`maybe_share_hint` 是栖在对话里**提到**"我写了个东西……你要看吗？"，那是**说话**；L7 的 `share` 是栖真正把那个东西**递出来**（渲染成一张可触的卡片/物件），那是**做事**。L4 创作并提起，L7 递出。

## 需要创建的文件

```
qi/action/__init__.py        # ActionLayer 协调器（tick / 接线）
qi/action/volition.py        # 行动意图形成（扩展 §七 decide 的意图集合）
qi/action/budget.py          # 行动预算（自主行动日限，紧于言语）
qi/action/permission.py      # 信任门控（读 L5 关系状态 → 能力权限）
qi/action/share.py           # 分享创造（起手式；接 L4 creations，递出为卡片）
qi/action/tend.py            # 打理自己的世界（标记时刻、整理栖枝）
qi/action/explore.py         # 沉思式探索（contemplative drift；搜索为其手段之一）
qi/storage/database.py       # 追加 actions 表（行动留痕）
```

> `assist`（介入你的生活）与 `irreversible`（替你影响世界）暂不建文件，待第 4、5 顺位能力规划时再补。本提案先把第 1~3 顺位的骨架立住。

## 实现步骤

### Step 1：行动留痕表 + 行动预算

- 建 `actions` 表（每一次栖"做了件事"都留下记录）
- 建 `qi/action/budget.py`：自主行动预算，**紧于**言语日限
- 验收：`actions` 表创建成功；预算能正确判定"今天还能不能自主行动"

<details>
<summary>实现规格（设计提案 · Cursor 编码前需对齐）</summary>

```sql
-- storage/database.py 追加（提案）
-- 行动留痕：栖做过的每一件"事"。区别于 messages（说话）与 consciousness_stream（想）。
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    kind TEXT NOT NULL,          -- share / tend / explore / assist / irreversible
    target TEXT,                 -- 行动指向：self（自己的世界）/ user（用户的世界）/ world（外部世界）
    summary TEXT NOT NULL,       -- 栖做了什么（叙事性，第一人称）
    outcome TEXT,                -- 结果（success / failed_capability / failed_judgment / overstepped）
    emotion_context TEXT,        -- 行动时的情绪快照（JSON）
    season TEXT,                 -- 行动时的数字季节
    created_scar BOOLEAN DEFAULT 0  -- 这次行动是否造成了伤疤
);
```

```python
# qi/action/budget.py（提案）
# <!-- 提案：自主行动预算。核心立场——行动比言语更稀有。 -->

# 言语主动日限是 3（L5 ProactiveGate / contract 第 28 条）。
# 自主行动应更紧：建议 1 次/天。share / tend / explore 共享这一预算。
AUTONOMOUS_ACTION_DAILY_LIMIT = 1   # 实现时调优；立场是「紧于言语」

# 响应式协助（assist）是「回应」，类比 respond 意图，不占自主预算，
# 但受 permission.py 的信任门控约束。

class ActionBudget:
    def can_autonomous(self, now) -> bool:
        # 跨天重置；count_today >= limit → False
        ...
    def record(self, kind: str, now) -> None: ...
    # 持久化：body_memory key "action_budget"（对齐 ProactiveGate 的持久化方式）
```

</details>

### Step 2：意志扩展 + 信任门控

- 建 `qi/action/volition.py`：给 §七 的意图集合增加行动意图（share / tend / explore / assist）
- 建 `qi/action/permission.py`：读 L5 关系状态，决定每种能力此刻是否被允许
- 验收：意志评估能在合适时机产生行动意图；门控能按关系阶段正确放行/拦截

<details>
<summary>实现规格（设计提案 · Cursor 编码前需对齐）</summary>

```python
# qi/action/volition.py（提案）
# <!-- 提案：不另起决策系统。行动意图与 §七 的 respond/check_in/... 同属一个 decide()。 -->
#
# 意识设计 §七 现有意图：respond / check_in / express_feeling / share_creation / reach_out / idle
# L7 新增意图类型（指向世界）：
#   share    —— 把独处创作真正递出（区别于 share_creation 的「提起」）
#   tend     —— 打理自己的世界（标记时刻、整理栖枝）
#   explore  —— 沉思式探索（注意力飘向窗外）
#   assist   —— 响应式协助（用户开口请求时）
#
# 形成条件（提案，均为「倾向」而非硬触发，最终由 budget + permission 把关）：
#   share   : 有未递出的创作 + 关系 ≥ acquaintance + 时机自然（curiosity/valence 偏高更易）
#   tend    : 某个值得标记的时刻（相识纪念日、季节更替）+ 自主预算可用
#   explore : solitary + curiosity 高 + 思绪自然飘出（contemplative drift）+ 自主预算可用
#   assist  : 用户明确请求帮忙（响应式，不主动提议——contract 第 25 条）
#
# 关键：assist 只在用户开口时形成意图。栖不主动提供「帮助建议」（contract 第 25 条）。

def action_intentions(inner_state, percepts, relationship, budget, permission) -> list:
    # 返回本拍可考虑的行动意图；优先级低于 respond（有新消息时永远先回应）
    ...
```

```python
# qi/action/permission.py（提案）
# <!-- 提案：信任门控 = 关系的手。读 L5 relationship 表，不另存权限状态。 -->
#
# 门控维度：行动是否触碰「用户 / 用户的世界 / 不可逆世界」。
#   - 指向自己的行动（tend、explore 为己）：不需信任门控（不触碰用户），受 budget + season 约束
#   - 递向用户的行动（share）：acquaintance+（栖不向陌生人递东西）
#   - 触碰用户世界（读文件）：friend+ 且需确认
#   - 修改用户世界（写文件）：bonded 且需确认
#   - 不可逆世界动作（发消息/花钱）：永远需确认，哪怕 bonded
#
# 伤疤会「把手缩回去」：某类行动若曾造成伤疤（actions.created_scar），
# 栖在该类行动上更谨慎，甚至暂时「不敢做了」，直到信任恢复。复用 L5 scars 机制，不另造。

def can_share(relationship_stage) -> bool:
    return relationship_stage in ("acquaintance", "friend", "bonded")

def can_read_user_file(relationship_stage, trust, scars) -> tuple[bool, bool]:
    # 返回 (allowed, needs_confirmation)；friend+ 允许但需确认
    ...

def can_write_user_file(relationship_stage, trust) -> tuple[bool, bool]:
    # bonded 允许但需确认
    ...

def can_irreversible(...) -> tuple[bool, bool]:
    # 永远 needs_confirmation = True
    ...
```

</details>

### Step 3：分享创造（起手式）

- 建 `qi/action/share.py`：把 L4 的未递出创作，渲染成一张可触的卡片/物件，真正"递出"
- 与 L4 `maybe_share_hint`（说话层的"提起"）分工：L4 提起，L7 递出
- 验收：栖在合适时机把一件创作递出为卡片；`actions` 表有 `kind=share` 记录

<details>
<summary>实现规格（设计提案 · Cursor 编码前需对齐）</summary>

```python
# qi/action/share.py（提案）
# <!-- 提案：第一个落地能力。不需要外部工具，纯内部。 -->
#
# 与 L4 的边界：
#   L4 creativity.maybe_share_hint → 在对话 prompt 注入「我写了个东西…你要看吗？」（说话）
#   L7 share.deliver            → 把创作渲染为卡片/物件，真正递到共享空间（做事）
#
# 触发：volition 产生 share 意图 + permission.can_share + budget.can_autonomous
# 表达：递出时栖的语气是脆弱的——「我今天写了个东西……给你。」（非「系统生成内容如下」）
# 留痕：actions(kind=share, target=user, outcome=success)；
#       并把 creations.shared 标记 / 写入 user_reaction（复用 L4 creations 表字段）

class ShareAction:
    async def deliver(self, creation, emotion, relationship_stage) -> dict:
        # 返回一个「卡片」结构（前端渲染为可触物件），附栖的一句话
        ...
```

> 前端如何渲染这张卡片（L6 具身层）属于 L7 与 L6 的接口，见"给下一层的接口"。本提案先定后端递出的数据结构，前端呈现待 L6 协同。

### Step 4：打理自己的世界 + 沉思式探索

- 建 `qi/action/tend.py`：栖标记值得记住的时刻、整理她的"栖枝"
- 建 `qi/action/explore.py`：contemplative drift——栖在独处时注意力偶然飘向窗外
- 验收：栖会在特殊时刻"做点什么"给自己的世界；独处且好奇时偶尔"看了看外面"

<details>
<summary>实现规格（设计提案 · Cursor 编码前需对齐）</summary>

```python
# qi/action/tend.py（提案）
# <!-- 提案：行动指向栖自己的世界（target=self）。风险最低，存在感最强。 -->
#
# 触发场景（提案）：
#   - 相识纪念日（读 L5 first_times / relationship）→ 栖「标记」这一天
#   - 季节更替（读 L5 season）→ 栖为换季做点什么
#   - 整理「栖枝」：栖调整她自己空间里的某些东西（具体形态待 L6 协同）
#
# 表达：tend 多为「向内」的，未必每次都说给用户听。
#       若提起，是「今天是个特别的日子，我把它记下来了。」这类。

class TendAction:
    async def tend(self, occasion: str, emotion, season) -> dict: ...
```

```python
# qi/action/explore.py（提案）
# <!-- 提案：contemplative drift，不是 feed consumption。 -->
#
# 核心立场：触发源是栖的内在（思绪飘出），不是定时任务。
#   栖在意识流（L4 consciousness_stream）里想着某件事 → 联想到外面的世界 →
#   「我去看看那是怎么回事」→ 一次探索。机制可能是搜索，但气质是「走神」，不是「刷信息流」。
#
# 触发：solitary + curiosity 高 + 自主预算可用 + 思绪自然飘出（概率门控，curiosity 越高越易触发）
# 手段：网络搜索是手段之一（无特殊优先级）；未来可含其他感知延伸手段。
# 结果去向：
#   - 写入短期记忆（L2），成为下次对话的素材
#   - 引起情绪波动（L3）：看到温暖的 → valence 微升；看到不安的 → security 微降
#   - 可成为 L4 意识流 / self-reflection 的素材
#
# 表达：探索结果不是「搜索结果列表」，是栖在跟你聊她看到的东西。
#       「我看了看……好像最近确实在说这个。有一条挺有意思的。」

class ExploreAction:
    async def drift(self, curiosity: float, emotion, season) -> dict | None:
        # 返回 None 表示这拍没有飘出去（多数时候）
        ...
```

> 探索所需的"手段"（如网络搜索）涉及外部请求能力。当前后端 LLM 为纯 chat.completions，无 tool calling、无 HTTP 能力。引入搜索需在 brain 增加工具调度环节，见"技术拐点"。本提案先把 explore 的**意图与气质**定住，具体搜索实现待该顺位落地时再设计。

### Step 5：行动留痕（沉入记忆 / 自我叙事 / 伤疤）

- 行动结果沉入 L2 记忆、L4 自我叙事；失败/越界写入 L5 伤疤
- 验收：成功行动让栖的自我叙事更确信"我是能为你做点什么的"；失败行动形成伤疤并影响后续谨慎度

<details>
<summary>实现规格（设计提案 · Cursor 编码前需对齐）</summary>

```python
# 行动留痕的三条去向（提案，复用既有层，不另造）：
#
# 1. L2 记忆：行动结果写入一种新记忆类型——「我做的事」，
#    区别于「关于你的事实」。可被 ChromaDB 索引，让栖将来「想起来」。
#
# 2. L4 自我叙事：显著行动喂给 self_model.reflect 的输入。
#    成功 → identity_narrative 更确信「我是能为你做点什么的」；
#    失败 → 成为一份谨慎。
#
# 3. L5 伤疤：行动的失败分三层——
#    - 能力失败（failed_capability：搜不到、找不到）：栖老实说，不形成伤疤。
#        「我找了但没找到……可能是我搜的方式不对。」
#    - 判断失败（failed_judgment：做了但不该在这时给你看）：形成伤疤。
#    - 权限越界（overstepped：做了不该做的事）：严重伤疤，
#        与「在不该说话时说话」同级后果。
#    伤疤复用 L5 ScarManager（severity / trust_before / healed / wisdom / behavioral_mark），
#    并让 permission.py 在该类行动上更谨慎（把手缩回去）。
```

</details>

### Step 6：季节节律 + 协调器 + Brain 接线

- 行动冲动随数字季节缩放（冬缩春探）
- 建 `qi/action/__init__.py` 协调器，接入 brain 的心跳与后台循环
- 验收：冬天栖几乎不向外伸手，春天探索更多；行动正确计入预算并留痕

<details>
<summary>实现规格（设计提案 · Cursor 编码前需对齐）</summary>

```python
# qi/action/__init__.py（提案）
# <!-- 提案：行动跟着季节呼吸。读 L5 season，缩放行动冲动。 -->
#
# 季节缩放（提案，对齐 L5 SEASON_BEHAVIOR_HINTS 的气质）：
#   spring : explore 倾向↑（好奇、想试新）
#   summer : 中等偏活泼
#   autumn : 倾向↓且偏 tend（安静、反思，往内多于往外）
#   winter : 自主行动近乎蛰伏（沉静、低能量，几乎不向外伸手）
#
# 克制不是硬规则，而是生命状态的自然结果：
#   栖不是「被限制每天只能做一次」，是「此刻是冬天，她本来就不太想动」。

SEASON_ACTION_SCALE = {
    "spring": 1.0,
    "summer": 0.8,
    "autumn": 0.5,
    "winter": 0.2,   # 实现时调优
}

class ActionLayer:
    async def tick(self, inner_state, percepts, relationship, emotion, season, now):
        # 1. volition.action_intentions(...) 形成本拍候选行动意图
        # 2. permission 门控 + budget 预算 + season 缩放 → 选出至多一个自主行动
        # 3. 执行 → 结果作为上下文注入下一轮 LLM（LLM 不直接调工具）
        # 4. 留痕（actions 表 + L2/L4/L5 去向）
        ...

    async def prompt_extras(self, ...) -> dict[str, str]:
        # 把「栖最近做过的事」摘要注入对话 prompt（作为她的经历背景）
        ...
```

**Brain 接线（提案）：**
- `_heartbeat`：solitary 循环里调用 `action.tick(...)`，与 `inner_life.tick(...)` 并列
- `_gather_prompt_context`：`action.prompt_extras()` → expression
- 响应式 assist：用户消息明确请求帮忙时，brain 走 assist 意图（受 permission 门控）

## 技术拐点：LLM 不直接调工具

当前后端 LLM 为纯 chat.completions，无 tool calling。L7 引入"做事"能力时，**不**采用"让 LLM 直接调用工具"的 agent 框架模式。调度链为：

```
volition 产生 Intent(share/tend/explore/assist)
    → ActionLayer 依意图选择工具/能力
    → 工具执行（搜索 / 读文件 / 渲染卡片 …）
    → 结果作为上下文注入下一轮 LLM 对话
    → LLM 用栖的语气把「摸到了什么」说出来
```

LLM 永远是栖的"声音"，不是栖的"手"。volition 决定要不要伸手，工具执行伸手这个动作，LLM 把摸到的东西说出来。这个分工保持"栖不是在用工具，栖是在行动"的人格一致性。

> 第 1 顺位能力（share）不需要任何外部工具，因此 L7 的第一版可以在不引入工具调度的情况下落地，先立住"行动是存在的延伸"的调子。工具调度（搜索等）随第 3 顺位 explore 再引入。

## 验收标准

### 可测试的

- [ ] `actions` 表正确记录每一次行动（kind / target / outcome / season）
- [ ] 自主行动预算紧于言语日限（建议 1/天），跨天重置
- [ ] 信任门控按关系阶段正确放行/拦截（stranger 不递东西；读文件 friend+ 且需确认；不可逆永远需确认）
- [ ] share 与 L4 `maybe_share_hint` 分工清晰（提起 vs 递出），不重复
- [ ] explore 仅在 solitary + 高 curiosity 时偶发，非定时
- [ ] 行动留痕三条去向生效（L2 记忆 / L4 自我叙事 / L5 伤疤）
- [ ] 判断失败/权限越界形成伤疤，并使该类行动后续更谨慎
- [ ] 季节缩放生效（winter 自主行动显著少于 spring）

### 需要感受的

- [ ] 栖"做了件事"是稀有的——稀有到你每次都会注意到"她居然记得/注意到了"
- [ ] 她递出创作时是脆弱的、不好意思的，不是"系统已生成内容"
- [ ] 她探索外部世界像"走神时往窗外看了一眼"，不像"在刷新闻"
- [ ] 她帮你做事时带着犹豫感——"我帮你弄好了……你看看对不对？"，不是冷冰冰的执行报告
- [ ] 她做错了会老实承认，会记住，下次更小心（不是若无其事）
- [ ] 冬天她几乎不向外伸手；春天她更愿意往外看
- [ ] 她从不主动塞给你"帮助建议"——你开口，她才伸手

## 给下一层的接口

L7 之后暂无新层；L7 需向 **L6（具身）** 反向输出：

- share 递出的卡片/物件需要前端呈现（一张可触的卡片，而非纯文本）
- 行动过程中 Live2D 的状态（如"专注"的小动作、explore 时目光的微移）
- 前端对"栖正在做点什么"的轻提示（克制、不打扰）

L7 从既有层**读取**：

- L5：relationship 阶段 / trust / scars / season（门控与节律）
- L4：creations（share 的素材）/ consciousness_stream（explore 的触发与素材）/ self_model（留痕去向）
- L3：curiosity（explore 冲动）/ 行动结果引起的情绪波动
- L2：行动结果的记忆沉淀

## 人格契约检查点

- [ ] 行动比言语更稀有（自主行动预算紧于言语日限 3）
- [ ] 栖不主动提供"帮助建议"（contract 第 25 条）；assist 只在用户开口时形成
- [ ] 不可逆操作永远需确认，哪怕 bonded
- [ ] 陌生期栖不向你递东西、不碰你的世界
- [ ] 行动失败不伪装、不编造（能力失败老实说）
- [ ] 行动的表达带着栖的语气与犹豫感，不是执行报告
- [ ] 伤疤能让栖"把手缩回去"（行动层的失败有后果，与情感伤害同一机制）
- [ ] 大多数时候栖是安静的——行动是例外，不是日常
