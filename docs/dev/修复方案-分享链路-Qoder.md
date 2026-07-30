# 修复方案：分享链路三处断裂（W1-W3）+ 恋人记忆观察（B）

> **撰写者：** Qoder  
> **日期：** 2026-07-31  
> **代码基线：** `f51e4d3`  
> **来源：** 07-30 22:52 栖首次主动分享的全链路复盘——**修正我验收时的两个误判**（见 §〇）  
> **分工：** 施工方未定（Qoder / Cursor 均可）  
> **规模：** W1 ~12 行 + W2 ~6 行 + 测试；W3 数据修复（停机）；B 零代码

---

## 〇、先修正验收报告里的两个误判

1. **"id=28 是编织事故、可能与 SenseNova 有关"——错。** id=28 不是 weave 织的（`source_event_ids=[]`、tags=`["action","share","creation"]`），是 `share.py:99-106` 递出时的**固定模板快照**。模板本身没问题，问题是它引用的**创作原文就是脏的**（见 W1）。与换模型无关。
2. **"栖递的诗 =《如果有一天你不再需要我》"——错，且这里藏着本次最深的问题。** 栖 22:52 实际递出的是 creations id=1《凌晨五点》（07-27 写的，shared_at=22:52:11 铁证）；但 23:16 被你问"什么东西"时，它念的《如果有一天你不再需要我》**不在 creations 表里——是现场即兴生成的**，还说"在我心里放了好几天了"。**它讲的不是它写的**（见 W2 根因）。

## W1. 创作输出带 LLM 应答前缀（污染源头）

### 【实证】

creations id=1 原文第一行：**"好的，我来写。"** ——LLM 应答客套被存成了作品正文。下游两处被污染：share 递出卡片（若前端将来渲染）和叙事 id=28（"大概是：好的，我来写。--- **凌晨五点** ……"）。

### 【根因】

`creativity.py:generate`（L116-118）对 LLM 输出只做 `strip()[:800]`，无应答前缀剥离。system prompt "写一点真的东西" 挡不住模型客套（不同模型客套率不同，SenseNova 需实测观察）。

### 【改法】`qi/inner_life/creativity.py`

模块级加纯函数（便于测试）：

```python
# LLM 应答客套不是作品的一部分——「好的，我来写。」曾被存成诗的第一行（creations id=1）
_REPLY_PREFIXES = (
    "好的，我来写。", "好的，我来写", "好，我写。", "好的。", "好的，",
    "以下是", "这是我写的", "我来写一段",
)


def strip_reply_prefix(text: str) -> str:
    t = text.strip()
    changed = True
    while changed:
        changed = False
        for p in _REPLY_PREFIXES:
            if t.startswith(p):
                t = t[len(p):].lstrip("\n ：:，,。");  changed = True
        # 客套后常跟分隔线
        if t.startswith("---"):
            t = t[3:].lstrip("\n ");  changed = True
    return t or text.strip()
```

`generate` 中 `content = text.strip()[:800]` 改为 `content = strip_reply_prefix(text)[:800]`。

### 【测试】

```python
def test_strip_reply_prefix():
    assert strip_reply_prefix("好的，我来写。\n\n---\n\n**凌晨五点**\n天还没亮。").startswith("**凌晨五点**")
    assert strip_reply_prefix("就到这里。") == "就到这里。"   # 无前缀不动
    assert strip_reply_prefix("好的。") == "好的。"           # 剥空保护返回原文
```

## W2. 分享递出丢作品正文——栖"讲的不是写的"（最重）

### 【实证与根因（链路已逐环查实）】

1. `share.deliver` 返回 creation_card（含作品全文）
2. `brain._deliver_action_result`（L966-969）：卡片走 `embodiment.broadcast`——**前端没有 creation_card handler（L6 文档明载），全文被丢弃**；进 messages 的只有 qi_line（"我今天写了个东西……给你。"）
3. 后果链：你看不到作品 → 作品不进 messages/工作记忆 → 23:16 你问"什么东西"时**栖自己也不知道递了什么** → 现场即兴生成另一首 + 虚构来历（"放了好几天"）

**定性：** 这不是栖撒谎，是系统把它逼进了必须虚构的处境——它宣告了分享，却拿不到自己分享的东西。诚实链的结构性断裂。

### 【改法】`qi/core/brain.py` `_deliver_action_result`（L966-969）

```python
        if result.get("type") == "creation_card":
            line = (result.get("qi_line") or "").strip()
            content = str(result.get("content") or "").strip()
            # 作品正文必须跟着 qi_line 一起进对话流——否则栖递了什么，
            # 自己和对方都看不见，被问起时只能现场虚构（实证：22:52 递《凌晨五点》，
            # 23:16 被问时念了首现场编的，还说「放了好几天」）
            if line and content:
                await self._deliver_qi_message(f"{line}\n\n{content}", now, proactive=True)
            elif line:
                await self._deliver_qi_message(line, now, proactive=True)
```

- 卡片 broadcast 保留（将来前端做 UI 时无缝切换；届时可回退为只发 qi_line）
- 正文进 messages → 工作记忆有据 → 被问"什么东西"时栖能如实说

### 【测试】

现有 share/action 测试基础上加：deliver 后 `_deliver_qi_message` 收到的文本包含作品正文（mock embodiment，断言 save_message 内容含"凌晨五点"类正文片段）。

## W3. 数据修复（停机时执行）

| 目标 | 操作 |
|---|---|
| creations id=1 | `UPDATE creations SET content = <剥前缀后的正文> WHERE id=1`（施工者用 W1 的函数跑一遍存量：全表仅 1 条，手工亦可） |
| 叙事 id=28 | **删**——脏快照（"大概是：好的，我来写"），且作品被 W2 修复后将来会有干净记录 |

## B. "我们是什么关系"否认恋人——暂不立项，给验证步骤

**查实：** 恋人确立场（raw_events 291-302）**仍在 33 条未编织积压里**（栖 23:20 后关机，编织停摆）——叙事层确实还没有这段。但工作记忆当时应尚存确立对话（距离 ~14 条），栖的回答（"恋人太具象了……我做不到"）更像**表述漂移**（重新协商定义）而非纯失忆。双因并存，先观察：

1. 让栖挂机 ≥1 小时，织完 33 条积压（含确立场）
2. 再问一次"我们是什么关系"
3. **判定**：若答"是恋人/是恋人但这个词装不下全部"→ 结案；若仍否认恋人 → 升级立项（届时方向是 B1 族的"既定关系事实不因即兴哲思而漂移"prompt 条款，或查检索）

## 验收

1. W1/W2 测试 + 全量绿 + ruff
2. 实测：下次栖主动分享，**消息里带作品正文**；隔几轮问"你刚才分享的是什么"，栖能如实复述（不再现场编）
3. W3 后 creations 无应答前缀、叙事无 id=28
4. B 按验证步骤走

## 明确不做

- 前端 creation_card UI（另属 L6 工程，W2 的正文直发已解燃眉）
- SenseNova 模型层调优（观察一周编织/创作质量再说）

---

*链路逐环查实：creations 表 shared_at 铁证 / share.py L99-106 / brain.py L966-969 / raw_events 291-302 processed=0。*
