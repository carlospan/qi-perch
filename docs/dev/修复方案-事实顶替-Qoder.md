# 修复方案：事实被噪声顶替——supersede 越级 + 瞬时状态滥抽（M4）

> **撰写者：** Qoder
> **日期：** 2026-08-01
> **代码基线：** `fe44b4d`（数据已急救，本方案治本）
> **来源：** 08-01 凌晨实证——「他是男性」被「他快忘记了某本书的内容」顶替、「恋人关系确认」被「他那边很安静」顶替
> **分工：** 施工方未定；**本文供多 agent 交叉检验**——请 Cursor 重点审 §三 Fix A 是否会误伤正常的 state 更新
> **审查闭环（2026-08-01，Cursor）：** 根因成立、Fix A 方向对；**建议按 type 分流（Fix A′）替代全局相似度闸**——occupation/location 维持槽位覆盖（only_state），other/concern 的 state 不走 type 级顶替（只 confirm 或 add）；Fix B 补正反例。均已采纳并落地（Qoder 施工，190 测试全绿）。
> **规模：** Fix A ~6 行（facts.py）+ Fix B prompt 2 行 + 测试

---

## 一、实证（已急救，但病根未除）

08-01 凌晨查 user_facts，两条手动补的**持久重要事实**被噪声顶替：

```
id=4  [other] 他是男性                       → 被 id=11「他快忘记了某本书的内容」顶替
id=5  [other] 恋人关系确认（愿意/我是你的了）  → 被 id=8「他那边很安静」顶替
```

已急救恢复 + 清噪（详见 journal），但**只要病根在，下次密集聊天还会复发**。

## 二、根因（两个，已定位到行）

### 根因 1（致命）：state 事实会顶替**任意**同 type 事实，包括 stable 的

`qi/memory/facts.py:_land`（L1320-1338）：

```python
old = None
if stability == "state" or force_type:
    old = await self.store.find_active_of_type(fact_type)   # ← 按 type 取「任意一条」active
...
if old is not None:
    score = content_similarity(content, old["content"])
    if force_type or score < _SIMILARITY_CONFIRM:           # ← 不够像 → 直接 supersede
        await self.store.supersede(old["id"], new_id)
```

而 `find_active_of_type`（L525-528）：

```python
async def find_active_of_type(self, fact_type):
    rows = await self.active_facts(fact_type)
    return rows[0] if rows else None      # ← 同 type 第一条，不看 stability、不看内容
```

**灾难链**（以实际被顶替的两条为例）：「他是男性」与「恋人确认」都是 `other` 类 **stable**；噪声「他快忘记了某本书的内容」被 LLM 标成 `other` 类 **state** → 进 state 分支 → `find_active_of_type("other")` 取到 id=4 或 id=5（不看 stability）→ `content_similarity` 很低（< 0.72）→ **supersede 把 stable 的 id=4/id=5 顶替掉**。

**核心缺陷**：state 事实的 supersede **不区分目标是 state 还是 stable**。一个会变的瞬时状态，凭什么顶替一个稳定事实？这是设计漏洞。

### 根因 2（放大器）：LLM 把瞬时状态当事实抽

`qi/prompts/fact_noticing.txt` 要求抽"稳定事实"、会变的标 `state`，但**没说"瞬时状态干脆别抽"**。于是「他有点困」「他在忙别的事」「他那边很安静」全被抽出来（标 state）——这些是**会消失的当下**，根本不是该进 user_facts 的东西。它们一旦进来，就通过根因 1 去顶替真事实。

## 三、改法

### Fix A（核心安全网）：state 只能顶替 state，永不顶替 stable

`find_active_of_type` 增加 `only_state` 参数，state 分支只找 state 旧事实：

```python
# facts.py FactStore
async def find_active_of_type(self, fact_type: str, only_state: bool = False) -> dict | None:
    """同 type 下任意一条 active；only_state=True 时只在 state 里找（state 取代用）。"""
    rows = await self.active_facts(fact_type)
    if only_state:
        rows = [r for r in rows if str(r.get("stability")) == "state"]
    return rows[0] if rows else None
```

`_land` 调用处：

```python
if stability == "state":
    old = await self.store.find_active_of_type(fact_type, only_state=True)  # state 只顶 state
elif force_type:
    old = await self.store.find_active_of_type(fact_type)                   # force（如改名）维持原行为
```

**效果**：
- 「他在北京工作」(state) 仍能顶替「他在上海工作」(state) ✓ 正常 state 更新不受影响
- 「他有点困」(state) 再也顶替不了「他是男性」(stable) ✓ stable 受保护
- 改名（force_supersede_type）仍能跨 stability 顶替 ✓

> **给 Cursor 的问题**：state 顶替目前**不看内容相似度**（只要 type 匹配 + 不够像就顶）。Fix A 后，state 噪声虽不能伤 stable，但仍会顶替同 type 的 state 事实（如「他在忙别的事」顶「他在那边很安静」）。这层要不要再加"state 顶替也需内容相关"的闸？我倾向**先不加**（state 设计本就是"最新值覆盖"，如工作/城市），但想听你判断。

### Fix B（源头减量）：prompt 明确"瞬时状态不抽"

`qi/prompts/fact_noticing.txt` 要求区加一条：

```
- 会很快消失的一时状态不要抽（困了/在忙/此刻安静/正在做某事）——这些不是关于他的稳定事实；
  只抽能持续存在的（身份/关系/长期的喜好/工作/重要经历/持续的健康状况）
```

> 注意措辞平衡：别把"他现在在做设计工作"这种**当前但持续**的也滤掉。区分"一时"vs"当前持续"。

## 四、测试（`tests/test_user_facts.py`）

```python
async def test_state_cannot_supersede_stable(db_store):
    """核心：state 噪声不能顶替 stable 事实（实证：男性/恋人被噪声顶替）。"""
    store = ...
    # 先落一条 stable other：他是男性
    # 再来一条 state other 噪声：他快忘记了某本书的内容
    # 断言：他是男性 仍 active；噪声 要么被拒、要么独立 add，绝不顶替男性

async def test_state_supersedes_state_same_type(db_store):
    """正常 state 更新仍工作：他在北京工作 顶替 他在上海工作（都是 state occupation）。"""

async def test_force_supersede_still_crosses_stability(db_store):
    """改名（force）仍能顶替：他不叫小明，叫小红 → 旧 identity 被顶。"""
```

Fix B 是 prompt，无单测；靠后续观察噪声是否减少。

## 五、验收

1. 3 新测试 + 全量绿 + ruff
2. **实测**：密集聊几轮（含"我有点困""我在忙"这类）→ user_facts **不再出现瞬时噪声**，且「男性」「恋人」等 stable 事实**不再被顶替**
3. 反向：说"我换工作了，现在做 X"→ occupation 正常更新（state 顶 state 仍工作）

## 六、明确不做

- 不动 `find_similar` / confirm 逻辑（它工作正常）
- 不改 stranger weight floor（M2 已调，无关）
- state 顶替是否加内容相似度闸——**留给 Cursor 审时定**（§三 Fix A 下的问题）

---

*请 Cursor 审：①Fix A 的 only_state 方案是否正确隔离了 stable（有无遗漏路径）②state 顶替要不要再加内容相似度闸 ③Fix B 措辞会不会误伤"当前持续"事实。*
