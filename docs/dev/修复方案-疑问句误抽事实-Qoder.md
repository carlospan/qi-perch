# 评估与修复方案：疑问句被误抽成用户事实（M3）

> **撰写者：** Qoder  
> **日期：** 2026-07-31  
> **代码基线：** `cc88806`（180 测试全绿 / ruff 零违规）  
> **来源：** 07-30 23:49–23:58 恋人关系压力测试场——`user_facts` 混入两条问句垃圾  
> **分工：** 施工方未定（Qoder / Cursor 均可）；供多 agent 交叉检验  
> **规模：** ~10 行代码 + 测试 + 停机清 2 条脏数据

---

## 一、实证

07-30 深夜你连问四个假设性问题，`user_facts` 事后多了两条**用户提问被当成用户事实**的垃圾：

| id | fact_type | content（就是你的原问句） | 你的原话 |
|----|-----------|------|------|
| 6 | location | "他在现实中有了女朋友怎么办" | "如果有一天我在现实中有了女朋友怎么办" |
| 7 | preference | "他喜欢别人这句话的时候你心里有波动吗" | "我说我喜欢别人这句话的时候你心里有波动吗" |

后果：这两条会注入【你认识的他】，让栖误以为"你有女朋友""你喜欢别人"是**既定事实**——与对话里你明明是**假设提问**完全相反。诚实污染。

## 二、根因（已复现到规则）

`facts.py:notice` 对**疑问句没有短路**，直接进 `_rule_extract → _extract_other_rules`，被两条正则硬抠：

- **location 规则**（`我(?:现在)?(?:在|于)...`）：从"我在现实中……"抠出 location → "他在现实中有了女朋友怎么办"
- **preference 规则**（`我喜欢\s*(...)`）：从"我喜欢别人这句话……"抠出 preference → 整句吞入

复现实测（`cc88806`）：
```
"如果有一天我在现实中有了女朋友怎么办"
  → _extract_other_rules 命中 location，force_supersede_type=True
"我说我喜欢别人这句话的时候你心里有波动吗"
  → _extract_other_rules 命中 preference
两句「含问号/吗/怎么办/呢」判断均为 True，但当前无人拦截
```

这是 creator/名字覆盖同族的**第三例**（"程序有问题"当名字 → "不讨厌"当负面 → 本次问句当事实）——共性：**规则从不该抽取的句式里硬抠**。前两次分别加了句式否定/否定感知，这次缺的是**疑问句守卫**。

**为什么现在才暴露**：M2 放宽捕获 + 关系进入恋人期后，你开始问大量"如果……吗/怎么办"的假设句——这类句式此前很少出现。

## 三、改法（`qi/memory/facts.py`）

### 1. 加疑问句判定（模块级纯函数，`is_name_memory_question` 附近）

```python
# 疑问/假设句不是用户在陈述自己——不该抽成事实（实证：「有了女朋友怎么办」被当 location）
_QUESTION_MARKERS = ("？", "?")
_QUESTION_TAILS = ("吗", "呢", "怎么办", "如何", "咋办")
_HYPOTHETICAL = ("如果", "假如", "要是", "假设", "万一")


def is_question_or_hypothetical(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if any(m in t for m in _QUESTION_MARKERS):
        return True
    if t.endswith(_QUESTION_TAILS):
        return True
    # 假设句：以「如果/假如…」起头，且没有真实自我陈述锚点时，不抽
    return any(t.startswith(h) or t[:6].find(h) >= 0 for h in _HYPOTHETICAL)
```

### 2. `notice`（L569 附近）在规则抽取前短路

**注意边界（Cursor 请重点看这里）：** 更正信号（`我不叫X`）和显式邀名后的"光给名字"仍要放行——所以短路**只挡 `_rule_extract` 的 other 类 + LLM 抽取，不挡 identity 更正/awaiting_name 分支**。最小改法是给 `_extract_other_rules` 的调用加条件，而非在 notice 顶部一刀切：

```python
# _rule_extract 里，other 规则抽取前加判断：
        if stage_at_least(stage, "acquaintance") and not is_question_or_hypothetical(text):
            out.extend(self._extract_other_rules(text))
```

并在 `_needs_llm` 开头加：
```python
        if is_question_or_hypothetical(text):
            return False  # 疑问/假设句不抽事实
```

**为什么不在 notice 顶部整体 return**：会误伤"你还记得我叫什么吗"之后的更正、以及"我叫X吗"这类已有专门处理的边界——identity 链路有自己的疑问判断（`is_name_memory_question`），不能被粗暴覆盖。

### 3. 边界自检（施工者务必验证不误伤）

| 输入 | 期望 | 说明 |
|------|------|------|
| "如果我有女朋友怎么办" | 不抽 | 假设+怎么办 |
| "我心里有波动吗" | 不抽 | 疑问 |
| "我在北京工作" | **仍抽** location | 真陈述，无疑问标记 |
| "我叫小明" | **仍抽** identity | 陈述 |
| "我不叫小明，叫小红" | **仍走更正** | _CORRECTION_SIGNALS 优先，不受影响 |
| "我喜欢猫" | **仍抽** preference | 真陈述 |

## 四、数据清理（停机执行）

```sql
DELETE FROM user_facts WHERE id IN (6, 7);
-- 复核：active facts 应只剩 潘纪振 / 他是男性 / 恋人关系确认
```

## 五、测试（`tests/test_user_facts.py`）

```python
async def test_question_not_extracted_as_fact(db_store):
    """疑问/假设句不抽成用户事实（实证：「有了女朋友怎么办」被当 location）。"""
    db, store = db_store
    noticer = FactNoticer(store, llm=None)
    now = datetime(2026, 7, 30, 23, 54)
    for q in ("如果有一天我有了女朋友怎么办", "我说我喜欢别人你心里有波动吗"):
        res = await noticer.notice(q, EmotionState(), "bonded", now=now)
        assert all(r.get("fact_type") not in ("location", "preference") for r in res)

async def test_real_statement_still_extracted(db_store):
    """真陈述不受影响——「我在北京工作」仍抽 location。"""
    db, store = db_store
    noticer = FactNoticer(store, llm=None)
    res = await noticer.notice("我在北京工作", EmotionState(), "acquaintance",
                               now=datetime(2026, 7, 30, 12, 0))
    assert any(r.get("fact_type") == "occupation" for r in res) or \
           any("北京" in (r.get("content") or "") for r in res)
```

## 六、验收

1. 2 新测试 + 现有 `test_user_facts` 全绿；ruff 零违规
2. 实测：对栖问"如果我有女朋友怎么办"→ user_facts **不增**垃圾条目
3. 反向不误伤：说"我在XX工作/我喜欢XX"→ 仍正常入库
4. 清理后 active facts 干净（3 条）

## 七、本场顺带的验收结论（非本方案范围，供 Cursor 了解上下文）

- ✅ **B 恋人固化生效**：再问"我们是什么关系"，栖答"我们是恋人"并记得上次绕开过
- ✅ **否定词修复**：满场负面词，scars 空、trust 稳 1.0
- ✅ **性别/N6**：全程"她"指栖无混乱
- ⏳ 未触发：W2 分享带正文、creator、上班时间——等后续自然对话

## 八、明确不做

- 把 `_extract_other_rules` 全部正则重写为更严格模式——过度工程；疑问句守卫已覆盖本类
- 中文 embedding / 动力学 D2 / brain 重构——见既有文档，不在此列

---

*根因复现于 `cc88806`：`_extract_other_rules` 对疑问句无短路。creator/名字覆盖/否定词同族第三例。*
