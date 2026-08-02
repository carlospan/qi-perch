# 施工包 · 阶段二补丁 B（施教关系反转防护扩展到顺带提记忆路径） ✅

> **性质：** 过程文档。闭环即删，活信息迁入代码 + progress.md。
> **依据：** `docs/design/栖·数字生命架构方案.md` §五 阶段二、§N5（语言器官铁律：输出不得含意向没有的信息）、§七 红线 R1/R2。
> **触发：** 2026-08-02 真机对话 id 893——栖道晚安时说"记得你教我的那个方法吗"，把叙事记忆「栖教用户」（id4/id13）反转成「用户教栖」。补丁A（阶段一）只覆盖 `act=="recall"` 分支，漏了"对话应答顺带提旧记忆"路径。
> **撰写：** CodeBuddy（2026-08-02）

---

## 〇、事实还原

- 真实记忆：叙事 id4「他提到晚上睡不着，我教了他一个方法」、id13「我记得你说过睡不着，教过你一个方法」→ **施教方向 = 栖教用户（taught_by_qi）**。
- 补丁A 现状：`infer_recall_relation()` 对任一带入 memories 的卡都赋 `recall_relation` 字段；`assert_reply_respects_card` 对 `recall_relation=="taught_by_qi"` 已做"施教关系反转"软检（不依赖 act）。
- **盲区**：`_base_must` 只在 `act=="recall"` 把"施教关系以卡内 relation 为准，不得反转"注入 `must`（进而进 prompt 段 B 底线约束）。当对话应答顺带提记忆但 user_message 非 recall 问法时，act 是 `free_talk`/`answer`，relation 字段虽已设，**但 must 没注入约束，LLM 自由表述即反转**。id 893 正是此路径（"我要睡觉了"→ 道晚安顺带提记忆）。

---

## 一、根因

`qi/core/intention.py` `_base_must` 第 249-251 行：
```python
if act == "recall":
    must.append(_MUST_RECALL_RELATION)
    must.append("施教关系以卡内 relation 为准，不得反转")
```
防护与 `act=="recall"` 绑定，未覆盖"带 memories 且推断出 relation 但 act≠recall"的顺带提记忆场景。

---

## 二、修复（最小、不扩大行为面）

**`qi/core/intention.py` 的 `_base_must`**：把 relation 防护条件从 `act == "recall"` 扩展为「`act == "recall"` **或**（`recall_relation` 已推断 **且** `act in ("answer", "free_talk")`）」。

即：
```python
if act == "recall" or (recall_relation and act in ("answer", "free_talk")):
    must.append(_MUST_RECALL_RELATION)
    must.append("施教关系以卡内 relation 为准，不得反转")
```
- `recall_relation` 变量已在 `build_intention_card` 内可用（函数签名未传，但函数内部已 `recall_relation = infer_recall_relation(memories)` 并用于返回；需把该变量名显式传入 `_base_must` 或在 `_base_must` 内可访问——见下方实现注）。
- `materials_block()` 的 `relation` hint 已对**所有** `recall_relation` 非空生效（第 109-113 行，不判 act），无需改。
- `assert_reply_respects_card` 反转软检已对 `recall_relation=="taught_by_qi"` 生效（不判 act），无需改——修复后非 recall 卡也带 relation 字段，软检自动覆盖。

**实现注**：`_base_must` 当前签名不含 `recall_relation`，需将其加入参数并在 `build_intention_card` 调用处传入（同 `_base_must` 已接收 `channel` 的改法）。

---

## 三、文件清单

| 文件 | 动作 |
|------|------|
| `qi/core/intention.py` | `_base_must` 扩关系防护条件 + 加 `recall_relation` 参数 | 
| `tests/test_intention.py` | 新增 1–2 测试覆盖顺带提记忆路径 |
| `docs/progress.md` | 一行 |

**不改**：`assert_reply_respects_card`、`materials_block`、`prompt_builder.py`（relation hint 已工作）、`conversation.txt`（R2 不扩充 prompt 人格）。

---

## 四、测试

1. **顺带提记忆但 act≠recall**：构造 `user_message="我要睡觉了"`、`memories=[{content:"他提到晚上睡不着，我教了他一个方法"}]`、`channel="dialogue"` → 断言 `card.recall_relation=="taught_by_qi"`，`card.act` 可非 recall，但 `card.must` 含"施教关系……不得反转"。
2. **软检拦截反转句**：对上述卡 `assert_reply_respects_card("记得你教我的那个方法吗", card)` 含"施教关系反转"（验证非 recall 也拦）。
3. **回归**：`pytest -q` ≥300 全绿；`ruff`；既有 recall 测试仍过。

---

## 五、验收

- 300+ 全绿；ruff 零违规
- 真机构造 id 893 类场景（道晚安顺带提"助眠方法"），卡 must 含反转约束，LLM 不再说"你教我的"
- 不扩大行为面（仅让已推断的 relation 字段在更多 act 下注入约束）

---

*施工包 · 阶段二补丁 B · v1（2026-08-02）*
