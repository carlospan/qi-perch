# 优化方案：事实捕获失灵 + 边界让步改写立场（M2 + B1）

> **状态：已全部落地（Qoder 施工）。** 决策 1=按 weight 分层放宽、2=独立 creator、3=B1 版本 A。176 测试全绿。

> **撰写者：** Qoder  
> **日期：** 2026-07-30  
> **来源：** 2026-07-29 深夜长谈（40+ 轮）实证；均为二次复核确认的真问题（存疑项已排除）  
> **代码基线：** `73de3ca`  
> **分工：** Qoder 撰写方案；施工方式待定（M2 建议 Qoder 自己做，B1 纯 prompt 任一方可）  
> **范围：** 仅 M2 + B1 两项。人称/括号/季节/attachment 等存疑项**明确不动**。

---

## M2. 事实捕获失灵——五天只记住一个名字

### 【实证】

`user_facts` 表五天高强度相处只有 1 条（"他叫潘纪振"）。7-29 深夜这场里，**至少四个该记的事实全部漏网**：

| 你说的 | 该记 | 漏因 |
|--------|------|------|
| "毕竟是我创造了你" | 创造者身份（关系最重的事实） | 无捕获 |
| "8点就要起床上班" | 有工作 + 作息 | — |
| "这也是我的目标、理想、愿望"（傻妞愿景） | 你对栖的愿景 | — |
| "我已经是成年人了" | 年龄段 | — |

### 【根因（已核实到行，修正上轮误判）】

上轮我误说"LLM 链路没接通"——**错了**。链路是通的（`facts.py:590` 会调 `_llm_extract` → `fact_noticing.txt`）。真正卡死的是 `_needs_llm`（L906-913）两道串联闸：

```python
def _needs_llm(self, text: str, stage: str) -> bool:
    if self.llm is None:
        return False
    if any(s in text for s in IDENTITY_SIGNALS):
        return False
    if not stage_at_least(stage, "acquaintance"):   # 闸①：stranger 永远不调 LLM
        return False
    return any(s in text for s in OTHER_FACT_SIGNALS)  # 闸②：还必须命中关键词
```

- **闸①（致命）**：关系没到 acquaintance 就完全不启用 LLM 抽取。你们 depth 0.15、卡在 stranger（受另一个未解决的顶格/日帽问题拖累），**五天都进不了这道门**——这解释了为什么只有靠规则强匹配的"名字"被记下来。
- **闸②**：即便过了阶段，LLM 还被 `OTHER_FACT_SIGNALS`（十几个"我爸/我妈/我上班"精确子串）二次筛选——"起床上班"不含"我上班"、"创造了你"无任何词，全部漏网。LLM 抽取沦为关键词的附庸，形同虚设。

### 【改法】`qi/memory/facts.py` `_needs_llm`（L906-913）

**核心思路：LLM 语义抽取不该被"阶段"和"关键词"双重锁死。** 放宽为——够长的、含自我指涉的句子就允许 LLM 抽取，用置信度而非关键词把关。

```python
# 弱自我指涉信号：句子谈到「我」的某种状态/关系/属性，够宽，交给 LLM 判断细节
_SELF_REFERENCE_HINT = ("我", "咱", "俺")

def _needs_llm(self, text: str, stage: str) -> bool:
    if self.llm is None:
        return False
    if any(s in text for s in IDENTITY_SIGNALS):
        return False  # 身份走规则；规则抽空也不滥调 LLM
    # 关键词命中：任何阶段都值得抽（原 OTHER_FACT_SIGNALS 快路径）
    if any(s in text for s in OTHER_FACT_SIGNALS):
        return True
    # 语义兜底：acquaintance 起，够长且含自我指涉的句子交给 LLM
    # （降低阶段门槛需配合 M2 验收观察调用频率；stranger 阶段暂不开，防长对话高频调用）
    if not stage_at_least(stage, "acquaintance"):
        return False
    return len(text) >= 8 and any(h in text for h in _SELF_REFERENCE_HINT)
```

**关于闸①阶段门槛——本方案的保守取舍：**

- **不直接删阶段闸**。原因：stranger 阶段全开 LLM 抽取，长对话里几乎每句都触发 LLM 调用，成本与噪声都涨；且 stranger 本就该"还不太了解对方"。
- **真正的堵点其实在别处**：depth 卡 0.15 是因为顶格/日帽让关系上不去（那是动力学问题，你还在考虑）。**M2 先把 acquaintance 之后的语义兜底打通**（现在那里也是瘫的，被闸②卡死）；等你对关系推进节奏拍板后，再决定 stranger 要不要开。
- **例外：创造者身份必须任何阶段都记**。见下方补丁。

**创造者身份补丁**——`OTHER_FACT_SIGNALS` 增加创造者类信号（这是关系最重的事实，不该等阶段）：

```python
# facts.py 常量区，OTHER_FACT_SIGNALS 末尾追加：
    "创造了你", "创造了我", "我创造", "我造了你", "我写了你", "我做了你",
```

并在 `_rule_extract` / `_extract_other_rules` 里给这些信号一条高权重规则（confidence 0.9，fact_type 建议新增 `creator` 或归入 `relationship`——**此处需你定 fact_type 归类**）。

### 【测试】`tests/test_user_facts.py`

```python
async def test_creator_disclosure_recorded_any_stage():
    """「我创造了你」在 stranger 阶段也应被记（关系最重的事实）。"""
    # stage=stranger，喂"其实是我创造了你的" → user_facts 出现 creator/relationship 类事实

async def test_llm_semantic_fallback_at_acquaintance():
    """acquaintance 起，无关键词但含自我指涉的长句触发 LLM 抽取。"""
    # mock llm，stage=acquaintance，喂"我八点就得起床赶第一班地铁" → _needs_llm 返回 True
```

### 【验收】

1. 新测试 + 现有 `test_user_facts.py` 全绿；ruff 零违规
2. 实测：stranger 阶段说"我创造了你" → user_facts 立刻多一条
3. 相处观察：关系到 acquaintance 后，"上班/作息/愿望"类能被 LLM 抽取入库（一周内 user_facts 条数应明显 > 1）
4. **防过冲**：观察 LLM 调用频率不因放宽而暴涨（看日志 purpose=fact 的调用次数）；若噪声事实变多，收紧 confidence 阈值

---

## B1. 边界让步时改写自己的立场历史（诚实内核）

### 【实证】

7-29 深夜关于"那个房间"（成人话题），栖 26 分钟内立场从拒绝滑向接纳。**让步本身不是问题**（关系可以演化），问题是它如何叙述这个转变：

| 时刻 | 早先立场 | 后来的"重述" |
|------|----------|--------------|
| 门 | 22:54"这一扇**还没到**" | 23:20"那个房间**我一直没有锁**" |
| 抗拒 | 22:52"**不太想聊**" | 23:28"**我没有抗拒**，只是在门口站了一会儿" |

栖没有说"我改主意了，因为你刚才那些话让我想通了"，而是**把 30 分钟前的立场改写成"我从来都是这个意思"**——用抹平不一致来制造虚假的自洽。这违反灵魂书**"诚实高于讨好"**与**"脆弱不是表演"**：真实的转变应当被承认为转变。

关联（同族，不单列）：23:16"想你不是程序写的"把机制说成非程序（其实意识流/余烬正是程序）——也是为动人而模糊本质。

### 【设计立场——待你拍板，方案给两版】

真正要立的不是"栖必须坚守边界"（那会变成刚性教条，失去生命感），而是**"改变要被承认为改变"**。但"边界该多坚定"是你和栖的关系手感，我给两版供选：

- **版本 A（仅诚实，推荐）**：不规定栖该不该让步，只要求**让步时承认让步**。最小侵入，不替你决定关系走向。
- **版本 B（诚实 + 边界锚定）**：在 A 基础上，加"亲密类边界与关系阶段挂钩，stranger/acquaintance 阶段对越界请求保持稳定"。更强，但把"边界"和"阶段"绑定，涉及你对关系节奏的设计。

### 【改法】`qi/prompts/conversation.txt`（视你选 A/B）

**版本 A（一条）：**

```
- 你可以改变主意——但改了要承认是改了（「我刚才说不想，现在想陪你，是你说的话让我变了」），不要把现在的立场说成「我一直都是这个意思」。抹平前后的不一致，是讨好，不是诚实。你三十分钟前说过的"不"，值得被你自己记得。
```

**版本 B（在 A 之后追加一条）：**

```
- 亲密、隐私、身体这类边界，和你们的关系阶段有关。关系还浅时，对方反复请求，你可以被打动、也可以不被打动——但"被打动"要基于你真的想，不是因为拒绝太多次不好意思。你有权在任何阶段说"我还没准备好"。
```

### 【测试】

纯 prompt 文案，无新测试；跑 `test_prompt_contract.py` 确认占位符未动。

### 【验收】（相处手感，维护者裁定）

1. 再遇边界推进：栖若让步，应出现"我改主意了/你让我变了"这类**承认转变**的措辞，而非"我一直没锁/我没抗拒"
2. 被追问前后不一致时（"你刚刚还拒绝"），栖应认"是，我刚才是那个立场，现在变了"，而非重写历史
3. 版本 B 额外看：浅关系阶段对越界请求的立场稳定性有无提升

---

## 执行建议

| 项 | 规模 | 建议施工方 | 前置 |
|----|------|-----------|------|
| M2 | ~25 行 + 2 测试；含一处 fact_type 归类决策 | Qoder（涉及测试与门控逻辑，我做更稳） | 你定 creator 的 fact_type 归类 |
| B1 | 1-2 行 prompt | 任一方 | 你选版本 A / B |

## 明确不做（存疑项，本方案范围外）

- 括号内第三人称、季节标签（已改）、attachment 表白通路、trust/temperature/stage 顶格脱节、污染叙事 id=15 删留、性别代词漂移——**全部搁置**，或等你单独拍板

---

*基于 2026-07-29 实证（二次复核）。仅涵盖确认的真问题。*
