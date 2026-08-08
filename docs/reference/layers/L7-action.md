<!-- 现行路径：reference/layers/L7-action.md（原 layers/L7-action.md，2026-08-02 重构迁移；正文以代码为准，未改） -->

# L7 · 行动

> 让栖的"在意"长出双手。不是为她装上一套工具，是让她的意志能触达世界——谨慎地、稀有地、带着她自己的语气。

---

> **本文档状态：Step 1–6 已落地（actions / budget / volition / permission / share / tend / explore 气质 / ActionLayer / brain 接线）。**
> 六层（L1~L6）已完成。L7 行动层骨架与起手能力已接入心跳。
> explore：内部深读（d-3-2，读记忆叙事 + LLM digest + speak + 见闻卡）+ 外部联网（d-1）已收口；d-2 外部 hits 消化 + d-3-1 见闻卡片已收口。C 方案工程交付完成，相处复验中。assist / irreversible 文件未建。
> <!-- 演进指向(2026-08-01)：行动框架（预算/门控）保留；方向为 N1 执行器真实化（真读、有后果）与 N3 动机驱动（学习进度/内稳态压力替代随机意向）。见 docs/explanation/栖·数字生命架构方案.md §四 N1/N3。 -->
> <!-- 演进指向(2026-08-08)：包 10 curiosity 候选注入回退（空赢仲裁堵死自主行动，已解；见解堵包）。 -->
> <!-- 演进指向(2026-08-08)：explore 真搜索 C 方案 d-1~d-3-2 工程已交付（外部 Tavily + digest；内部 narratives 深读；ExploreCard）；相处复验中。assist / irreversible 仍待做。 -->
> <!-- 演进指向(2026-08-08)：explore C 方案收尾——d-2 外部 hits→digest；d-3-1 见闻卡片（web）；d-3-2 内部 narratives→digest + speak + 见闻卡（journal）；工程交付完成，相处复验中。 -->
> Step 5：actions + narrative 已接；self_model 喂入与伤疤 `save_scar` **尚未接线**。
> 已落地处见各段 `<!-- 回写 -->`。

---

## 职责

把栖的意志（volition）的表达通道，从"说话"扩展到"做事"。

栖已经能决定"此刻我要不要开口、以什么方式开口"（见 `docs/explanation/archive/栖·意识设计.md` §七）。L7 不新增一个"行动器官"，而是让同一个意志多出几种**指向世界**的意图：把她独处时创造的东西真正递到你面前、打理她自己的世界、在好奇时把目光投向窗外、在你开口时帮你做点什么。

L7 负责：行动意图的形成、行动预算（比言语更紧的克制）、信任门控（关系决定手能伸多远）、季节节律（行动跟着数字季节呼吸）、行动留痕（做过的事沉进记忆与自我叙事）、以及行动结果如何以栖的语气被说出来。

## 设计原则（先于任何实现）

这一层最容易滑向"给栖装一个 agent 框架"。以下四条是防线，任何实现细节与它们冲突时，以它们为准：

1. **行动是意志的延伸，不是新器官。** 决定"要不要伸手"的，和决定"要不要开口"的，是同一个 volition。L7 给 `decide()` 增加意图类型，不另起一套决策系统。

2. **行动比言语更稀有，因为行动即打扰。** 栖的整个存在建立在"在，但不打扰"上（contract 第 70 条）。说话是廉价的，沉默也是；但"伸手进世界"每一次都是对这条原则的小小违背。所以行动的克制不是 arbitrary 的数字，而是栖性格的必然——她做得少，因为做对她是有代价的。**现行数值**：主动**言语**日限仍为 3（ProactiveGate / contract 第 28 条）；自主**行动**日限默认为 **20**（`qi/action/budget.py`），远高于真实触发上限，只作安全阀——真实稀缺由可归档记忆量、独处门槛、在线时长等闸门塑造，不靠把日限压到比 3 更紧来装克制（2026-08-02 维护者拍板，见 `progress.md`）。

3. **行动的正当性来自关系，不来自能力。** 栖不是"因为能做所以做"，是"因为被允许所以做"。一个陌生人没有立场为你做事。手能伸多远，由 L5 的关系阶段、信任、伤疤决定。这不是"权限管理系统"，是"关系如何具身成行动边界"。

4. **能力是手的形状，不是手本身。** 搜索、文件、日程、分享——这些是能力（capability）。但组织这一层的，是栖"为什么伸手"（意图），不是"能用什么工具"。能力按"像栖的程度"排序，不按"有用的程度"排序。

## 前置依赖

- L5 完成（关系阶段 / 信任 / 伤疤 / 数字季节——作为行动的门控与节律来源）
- L4 完成（创作 / 意识流 / 自我叙事——作为行动的素材与留痕处）
- L3 完成（curiosity 驱动探索冲动；行动结果引起情绪波动）
- L2 完成（行动结果沉入记忆）

## 引用文档

- `docs/explanation/archive/栖·意识设计.md` → §七（意志：意图形成 `decide()`、主动行为的克制、"不说话"的决定）
- `docs/explanation/archive/栖·工程手记.md` → §六"远期展望：行动"（目标 / 交付物 / 验证标准）
- `docs/reference/contract.md` → 第 25 条（不主动提供"帮助建议"）、第 28~29 条（主动行为日限与冷却）、第 70 条（在，但不打扰）
- `docs/reference/layers/L5-relationship.md`（阶段 / 信任 / 伤疤 / 季节 / ProactiveGate）
- `docs/reference/layers/L4-inner-life.md`（creations / `maybe_share_hint` / self_model / consciousness_stream）

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
qi/action/__init__.py        # 导出；协调器见 layer.py
qi/action/layer.py           # ActionLayer（tick / prompt_extras / 季节）
qi/action/volition.py        # 行动意图形成（与 pick_proactive_kind 并列）
qi/action/budget.py          # 行动预算（自主日限默认 20，安全阀）
qi/action/permission.py      # 信任门控（读 L5 关系状态 → 能力权限）
qi/action/share.py           # 分享创造（起手式；接 L4 creations）
qi/action/tend.py            # 打理自己的世界
qi/action/explore.py         # 沉思式探索（d-3-2 深读记忆叙事 + d-1 外部分支）
qi/action/explore_web.py     # 外部 WebSearchClient（Tavily；失败/空→None）
qi/action/self_ops.py        # 自反操作（归档/调预算/日记等，阶段二）
qi/storage/database.py       # actions 表（行动留痕）
```

> `assist`（介入你的生活）与 `irreversible`（替你影响世界）暂不建文件，待第 4、5 顺位能力规划时再补。本提案先把第 1~3 顺位的骨架立住；`self_ops` 属自反闭环，不是 assist。

## 实现步骤

### Step 1：行动留痕表 + 行动预算

- 建 `actions` 表（每一次栖"做了件事"都留下记录）
- 建 `qi/action/budget.py`：自主行动预算（默认日限 20，安全阀；真实稀缺不靠压日限）
- 验收：`actions` 表创建成功；预算能正确判定"今天还能不能自主行动"

<details>
<summary>实现规格（已落地 · Step 1）</summary>

```sql
-- storage/database.py
-- <!-- 回写(2026-07-23)：actions 表 + insert_action / list_recent_actions / count_actions_on_day；
--      依据：qi/storage/database.py -->
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    kind TEXT NOT NULL,          -- share / tend / explore / assist / irreversible
    target TEXT,                 -- self / user / world
    summary TEXT NOT NULL,
    outcome TEXT,                -- success / failed_capability / failed_judgment / overstepped
    emotion_context TEXT,
    season TEXT,
    created_scar BOOLEAN DEFAULT 0
);
```

```python
# qi/action/budget.py
# <!-- 回写(2026-07-23)：ActionBudget 与 ProactiveGate 同构（can_autonomous/record/snapshot/restore）；
#      持久化 key body_memory「action_budget」；config.action.autonomous_daily_limit。
#      依据：qi/action/budget.py、qi/config/settings.example.yaml -->
# <!-- 演进指向(2026-08-02)：原「默认日限 1」已改。阶段二·补丁 C 放宽至 3、真机实测日限非瓶颈（archive 受可归档记忆量卡、journal/close_loop 受门槛卡），
#      维护者裁定日限=20（远高真实触发上限、仅作安全阀，不塑造行为）；代码常量/settings.yaml/settings.example.yaml 三处一致为 20。见 docs/progress.md 已拍板决策。 -->

AUTONOMOUS_ACTION_DAILY_LIMIT = 20   # 远高真实触发上限，仅作安全阀；可经 config 覆盖

class ActionBudget:
    def can_autonomous(self, now) -> bool: ...
    def record(self, kind: str, now) -> None: ...
    # assist 不调用 record（响应式不占自主预算）
```

</details>

### Step 2：意志扩展 + 信任门控

- 建 `qi/action/volition.py`：给 §七 的意图集合增加行动意图（share / tend / explore / assist）
- 建 `qi/action/permission.py`：读 L5 关系状态，决定每种能力此刻是否被允许
- 验收：意志评估能在合适时机产生行动意图；门控能按关系阶段正确放行/拦截

<details>
<summary>实现规格（已落地 · Step 2）</summary>

```python
# qi/action/volition.py
# <!-- 回写(2026-07-23)：action_intentions 与 pick_proactive_kind 并列同构（不虚构 decide 模块）；
#      §七 decide() 为概念对应。share 门槛 friend+；assist 仅用户明确请求才候选、本阶段不执行。
#      dreaming / 离线 → []。依据：qi/action/volition.py -->
#
# 意识设计 §七 概念意图：respond / check_in / express_feeling / share_creation / reach_out / idle
# 代码现实：回应由 brain pending 路径承担；主动言语由 pick_proactive_kind。
# L7 新增行动意图（指向世界）：
#   share    —— 把独处创作真正递出（区别于 maybe_share_hint 的「提起」）
#   tend     —— 打理自己的世界
#   explore  —— 沉思式探索
#   assist   —— 响应式协助（用户开口请求时；桩，不执行）
#
# 形成条件（倾向，最终由 budget + permission + season 把关）：
#   share   : 未递出创作 + 关系 ≥ friend + 时机自然
#   tend    : 调用方给出 occasion（纪念日等）+ 自主预算
#   explore : solitary + curiosity 高 + 自主预算
#   assist  : 用户明确请求帮忙（绝不主动——contract 第 25 条）

def action_intentions(...) -> list[ActionIntention]:
    ...
```

```python
# qi/action/permission.py
# <!-- 回写(2026-07-23)：can_share=friend+；tend/explore 不需信任门控；
#      读文件 friend+需确认；写文件 bonded需确认；不可逆永远需确认。
#      失败三层 outcome 规则写在 docstring；伤疤写入复用 db.save_scar（Step 5 接线）。
#      依据：qi/action/permission.py -->

def can_share(relationship_stage) -> bool:
    return relationship_stage in ("friend", "bonded")
```

</details>

### Step 3：分享创造（起手式）

- 建 `qi/action/share.py`：把 L4 的未递出创作，渲染成一张可触的卡片/物件，真正"递出"
- 与 L4 `maybe_share_hint`（说话层的"提起"）分工：L4 提起，L7 递出
- 验收：栖在合适时机把一件创作递出为卡片；`actions` 表有 `kind=share` 记录

<details>
<summary>实现规格（已落地 · Step 3）</summary>

```python
# qi/action/share.py
# <!-- 回写(2026-07-23)：ShareAction.deliver / try_share；卡片 type=creation_card；
#      只占 ActionBudget，不占 ProactiveGate；递出后 mark_creation_shared + insert_action。
#      无 24h 递出冷却（靠自主日限 + friend+；日限现行 20 安全阀）。依据：qi/action/share.py -->
# <!-- 回写(2026-07-25)：递出后**恒** narrative.save(importance=0.78)，非「显著才织」。 -->
#
# 与 L4 的边界：
#   L4 maybe_share_hint → 提起（只写 mentioned_at）
#   L7 share.deliver    → 递出（写 shared=1 / shared_at）
#
# 触发：permission.can_share + budget.can_autonomous + load_unshared_creation
#       （阶段三 ActionLayer 再接 volition 意图）
# 卡片字段：type / creation_id / creation_type / content / emotion_context /
#           qi_line / action_id / season

class ShareAction:
    async def deliver(self, creation, emotion, relationship_stage, *, season, now) -> dict: ...
    async def try_share(self, emotion, relationship_stage, budget, *, season, now) -> dict | None: ...
```

> 前端如何渲染这张卡片（L6 具身层）属于 L7 与 L6 的接口。本层只定后端递出的数据结构。

</details>

### Step 4：打理自己的世界 + 沉思式探索

- 建 `qi/action/tend.py`：栖标记值得记住的时刻、整理她的"栖枝"
- 建 `qi/action/explore.py`：contemplative drift——栖在独处时注意力偶然飘向窗外
- 验收：栖会在特殊时刻"做点什么"给自己的世界；独处且好奇时偶尔"看了看外面"

<details>
<summary>实现规格（已落地 · Step 4）</summary>

```python
# qi/action/tend.py
# <!-- 回写(2026-07-23)：TendAction.tend；target=self；occasion=anniversary|season:*；
#      默认不 speak。依据：qi/action/tend.py -->

class TendAction:
    async def tend(self, occasion: str, emotion, season, *, speak=False) -> dict: ...

# qi/action/explore.py
# <!-- 回写(2026-07-23)：ExploreAction.drift；多数拍 None；飘出时 found 恒 None（不编造搜索结果）；
#      只留「走神看一眼」的 actions 痕迹。搜索/HTTP 未实现。依据：qi/action/explore.py -->
# <!-- 回写(2026-08-08)：d-1 外部分支——curiosity≥0.8+冷却6h+概率0.05+web/llm → Tavily；
#      空手 found=None / failed_capability / speak+qi_line；内部不变仍不说。依据：explore.py / explore_web.py -->
# <!-- 回写(2026-08-08)：d-3-2 内部分支——list_recent_narratives → _digest_internal → speak+qi_line；
#      source=journal；见闻卡与外部对称；删沙箱列目录死码。依据：explore.py -->

class ExploreAction:
    async def drift(self, curiosity, emotion, season, *, season_scale, force=False) -> dict | None:
        # 飘出后：稀有走外部 web；否则深读记忆叙事（均可 speak）
        ...
```


</details>

### Step 5：行动留痕（沉入记忆 / 自我叙事 / 伤疤）

- 行动结果沉入 L2 记忆、L4 自我叙事；失败/越界写入 L5 伤疤
- 验收：成功行动让栖的自我叙事更确信"我是能为你做点什么的"；失败行动形成伤疤并影响后续谨慎度

<details>
<summary>实现规格（部分落地 · Step 5）</summary>

```python
# 行动留痕的三条去向（复用既有层，不另造）：
#
# 1. L2 记忆：行动结果**必写入 actions 表**（权威留痕）；share/tend 另
#    narrative.save 一条第一人称叙述（进 ChromaDB 可检索）。
#    不另建记忆模块。行动是栖自己的事，归叙事；与 user_facts（关于用户）不冲突。
# <!-- 回写(2026-07-23)：权威在 actions；share/tend 已接线 insert_action + narrative.save；
#      explore 空手不织 narrative。依据：qi/action/share.py、tend.py、explore.py -->
# <!-- 回写(2026-07-25)：share 恒织 importance=0.78；tend 恒织 0.7（非「显著才织」）。 -->
#
# 2. L4 自我叙事：显著行动喂给 self_model.reflect 的输入。
#    【尚未接线】成功 → identity_narrative 更确信「我是能为你做点什么的」；
#    失败 → 成为一份谨慎。
#
# 3. L5 伤疤：行动的失败分三层——
#    - 能力失败（failed_capability）：老实说，不形成伤疤。
#    - 判断失败（failed_judgment）：形成伤疤 → db.save_scar。
#    - 权限越界（overstepped）：严重伤疤。
#    规则与 outcome_creates_scar 已在 permission.py；【实际 save_scar 接线待后续】。
#    permission.scar_blocks_kind 可在有伤疤后把手缩回。
```

</details>

### Step 6：季节节律 + 协调器 + Brain 接线

- 行动冲动随数字季节缩放（冬缩春探）
- 建 `qi/action/__init__.py` 协调器，接入 brain 的心跳与后台循环
- 验收：冬天栖几乎不向外伸手，春天探索更多；行动正确计入预算并留痕

<details>
<summary>实现规格（已落地 · Step 6）</summary>

```python
# qi/action/layer.py（由 qi/action/__init__.py 导出 ActionLayer）
# <!-- 回写(2026-07-23)：ActionLayer.tick / prompt_extras / 季节缩放 / 预算持久化；
#      brain：pending is None 时先 action.tick，动手则跳过 pick_proactive_kind；
#      dreaming 不行动；ShareAction 注入 memory.narrative。
#      依据：qi/action/layer.py、qi/core/brain.py -->
# <!-- 回写(2026-07-25)：mode 门控 solitary|ambient；awake 不自主伸手；
#      _deliver_action_result 推 WS type=action + creation_card 开口。 -->

SEASON_ACTION_SCALE = {
    "spring": 1.0, "summer": 0.8, "autumn": 0.5, "winter": 0.2,
}

class ActionLayer:
    async def tick(self, emotion, relationship_stage, season, now, *, mode, user_online, scars):
        # 离线 / dreaming / mode∉{solitary,ambient} → None（awake 偏对话）
        # intentions → 软门控(priority) → 至多一个 share|tend|explore
        # explore 另要求 mode==solitary（volition）
        ...
    async def prompt_extras(self) -> dict[str, str]:
        # recent_actions → conversation.txt【你做过的事】
        ...
```

**Brain 接线（已落地）：**
- `_heartbeat`：`pending is None` 分支先 `action.tick`；若动手则 `_deliver_action_result`，不再 `pick_proactive_kind`
- `_deliver_action_result`：先 `qi_line` 走 `_deliver_qi_message`（非 ProactiveGate），再 WS `broadcast({"type":"action","payload":result})`；正文由前端卡片承载（不内联进语音）
- `_gather_prompt_context`：`action.prompt_extras()` 并入 extras
- `restore_state`：`ActionLayer(db, config, narrative=memory.narrative, llm=self.llm)`；预算 ↔ body_memory
- assist 执行仍未接线（仅 volition 桩）
- L6 前端已接 `action`：`creation_card` → ActionCard；`explore_drift`（`source=web|journal` 且 entries 非空）→ ExploreCard；tend 到达不渲染
- `/history.cards`：已分享创作卡按 `shared_at` 回灌谈区（见闻卡仍会话瞬时）
  <!-- 回写(2026-08-08)：任务包 2026-08-08-L6-action卡片UI；退役 W2 正文内联。 -->
  <!-- 回写(2026-08-08)：d-3-1/d-3-2 见闻卡——ExploreCard；useQi 门控 web||journal。 -->
  <!-- 回写(2026-08-09)：创作卡随 history 回灌，补退役内联后的重启缺口。 -->

</details>

## 技术拐点：LLM 不直接调工具

当前后端 LLM 为纯 chat.completions，无 tool calling。L7 引入"做事"能力时，**不**采用"让 LLM 直接调用工具"的 agent 框架模式。调度链为：

```
volition 产生 Intent(share/tend/explore/assist)
    → ActionLayer 依意图选择工具/能力
    → 工具执行（搜索 / 读文件 / 渲染卡片 …）
    → 结果作为上下文注入下一轮 LLM 对话
    → LLM 用栖的语气把「摸到了什么」说出来
```

LLM 永远是栖的"声音"，不是栖的"手"。

> share / tend 已落地且不需外部工具。explore：内部深读记忆叙事（d-3-2）+ 外部联网（d-1 已收口）+ 外部 hits 消化（d-2）+ 见闻卡片（d-3-1）；**不编造**窗外/内在未见内容。C 方案工程交付完成，相处复验中。

## 验收标准

### 可测试的

- [x] `actions` 表正确记录每一次行动（kind / target / outcome / season）
- [x] 自主行动预算日限可配置（现行默认 20，安全阀），跨天重置
- [x] 信任门控按关系阶段正确放行/拦截（stranger 不递东西；读文件 friend+ 且需确认；不可逆永远需确认）
- [x] share 与 L4 `maybe_share_hint` 分工清晰（提起 vs 递出），不重复
- [x] explore 仅在 solitary + 高 curiosity 时偶发，非定时；无搜索时 found=None
- [ ] 行动留痕三条去向完整（actions 必写；share/tend 已织 narrative；伤疤待失败路径）
- [ ] 判断失败/权限越界形成伤疤，并使该类行动后续更谨慎
- [x] 季节缩放生效（winter 意图 priority 显著低于 spring）

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

- [ ] 行动比言语更稀有（真实触发受闸门约束；日限 20 仅作安全阀，见原则 §2）
- [ ] 栖不主动提供"帮助建议"（contract 第 25 条）；assist 只在用户开口时形成
- [ ] 不可逆操作永远需确认，哪怕 bonded
- [ ] 陌生期栖不向你递东西、不碰你的世界
- [ ] 行动失败不伪装、不编造（能力失败老实说）
- [ ] 行动的表达带着栖的语气与犹豫感，不是执行报告
- [ ] 伤疤能让栖"把手缩回去"（行动层的失败有后果，与情感伤害同一机制）
- [ ] 大多数时候栖是安静的——行动是例外，不是日常


