# 栖（qi-perch）优化方案 v3

> **撰写者：** Qoder  
> **日期：** 2026-07-26（v3，详细施工蓝图重写）  
> **基线：** `71bab53`（代码与 origin/main 完全同步；工作区仅有未跟踪的 v3 文档——评估、本方案，待提交）  
> **前置：** `系统质量评估-Qoder-v3.md`（工程尺 8.1 / 存在尺 8.8）  
> **分工：** 本方案由 Qoder 撰写；**执行任务（改代码/prompt）由 Cursor 承担**。因此每一项都给出：目标文件+行号、当前代码、要改成什么、测试、验收——Cursor 拿到即可施工，无需反问。  
> **尺子：** 灵魂书「存在先于功能」+「完成 = 觉得它活着」。**相处更稳、更像栖**才是目标，不是分数。

---

## 〇、方案说明

本方案基于全面审查（见评估文档 §十四 审查范围）。执行顺序沿用 v2+Cursor 对齐的 **N1 → N3 → N2 → N4 → X1 → X2 → X4 → P4**，Q1/Q2/Q3 插入原位。每项标注：

- **【文件】** 要改的文件+关键行号
- **【现状】** 当前代码（Cursor 可先核对）
- **【改成】** 目标代码/文案（可直接照抄或据此微调）
- **【测试】** 要补的测试
- **【验收】** 怎么算做完

---

## 一、总策略

```
先养声音与边界（几乎零架构）
    → 再补「已有数据没用上 / 已承诺没落库」的小洞
        → 再动感知/关系里的语义化（控制调用频率）
            → 最后重构与重模型
```

- **不**以综合分 9.0 为 KPI
- **不**在陌生期用身体记忆制造「我好懂你」
- **每项改完**：全量 `pytest` + `ruff` 全绿；改 prompt 则留一段对话摘录对照
- 大项拆小 PR；禁止攒一周再测；**重构与行为变更永不同 PR**

---

## 二、随手做（零风险，今天就能完成）

### Q1. Python 依赖锁定（防环境腐烂）

**【问题】** `pyproject.toml` 全 `>=` 宽松约束，无锁文件。Node 有 package-lock.json，Rust 有 Cargo.lock，唯独主程序裸奔。chromadb/openai 这类活跃库，半年后重装环境可能直接起不来。

**【文件】** 新建 `requirements.lock`；改 `docs/dev/换机搭建.md`

**【做法】**

```powershell
pip freeze --exclude-editable > requirements.lock
```

提交进仓库。`docs/dev/换机搭建.md` 的"安装 Python 依赖"一节加一句：

> 若要精确复现开发环境（防 chromadb/openai 版本漂移），可改用锁文件：`pip install -r requirements.lock`。日常开发仍推荐 `pip install -e ".[dev]"`（最小依赖）。

**【注意】** 不引入 poetry/uv，不改 CI（CI 继续测宽松约束，反而能提前暴露上游破坏）。

**【改动量】** 1 个文件 + 2 行文档  
**【风险】** 零  
**【验收】** `requirements.lock` 入库；文档有说明

---

## 三、Now（本阶段 · 养声音与边界）

### Q2. Prompt 模板契约测试（防静默 KeyError）

**【问题】** conversation.txt 有 17 个 `{placeholder}`，靠 `prompt_builder.py:121-139` 的 `template.format()` 手工填充，无任何测试守这个契约。**拆为两则债**（见评估 §三）：

- **债 A（本项主防）**：改模板增删 `{foo}`、`format()` 忘给该键 → 运行时 KeyError，该拍表达静默失败
- **债 B（顺手附带）**：调用方传非法 `emotion`/`now`（如 None）→ AttributeError（v3 已复现）

**【文件】** 新建 `tests/test_prompt_contract.py`

**【做法】** 双层防护——conversation.txt 走真实 builder 端到端，其余 6 个模板锁定占位符集合：

```python
"""Prompt 模板占位符契约测试。

防两类静默故障：
1. 债A：模板新增 {placeholder}，format() 忘给值 → 运行时 KeyError，该拍表达失败。
2. 债B：emotion/now 传 None → AttributeError（API 空值防护）。

conversation.txt 走真实 PromptBuilder 端到端验证（最可靠）；
其余模板锁定占位符集合——改模板占位符时这里会红，提醒同步改填充代码。
"""
from __future__ import annotations

import re
from datetime import datetime

import pytest

from qi.core.emotion import EmotionState
from qi.llm.prompt_builder import PromptBuilder
from qi.prompts import read_prompt

_PLACEHOLDER = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")  # 排除 {{}} 转义

# 各模板占位符必须与对应填充代码一致（见评估文档 §三清单）。
EXPECTED: dict[str, set[str]] = {
    "conversation": {
        "emotion_description","energy_level","time_feeling","tone_hint",
        "relationship_stage","relationship_hint","season_hint","scar_hint",
        "relevant_memories","user_facts","recent_actions","shared_culture",
        "user_profile","recent_thoughts","emotion_residue","self_narrative","inner_notes",
    },
    "consciousness_stream": {"time","silence_duration","emotion_summary","recent_memories","pending_thoughts","last_dream","chat_embers","trigger_hint"},
    "dream": {"recent_memories_shuffled","emotion_color","unfinished_thoughts"},
    "creation": {"emotion_state","trigger_thought","target"},
    "fact_noticing": {"message","stage","emotion"},
    "self_reflection": {"current_state","recent_experiences","relationship_summary","previous_self_narrative","growth_events"},
    "story_weaving": {"raw_events_recent","emotions_during_events","relationship_stage"},
}

def test_conversation_builds_end_to_end():
    """债A：用最小参数真实 build 一次，任何缺键会当场炸。"""
    builder = PromptBuilder()
    messages = builder.build_conversation_prompt(
        user_message="你好",
        emotion=EmotionState(),
        now=datetime.now(),
    )
    assert messages and messages[0]["role"] == "system"

def test_conversation_requires_emotion_and_now():
    """债B：emotion/now 必填，传 None 应当显式失败。"""
    builder = PromptBuilder()
    with pytest.raises((TypeError, ValueError, AttributeError)):
        builder.build_conversation_prompt(user_message="x", emotion=None, now=None)

@pytest.mark.parametrize("name", list(EXPECTED))
def test_template_placeholder_set_matches(name):
    """债A：模板占位符集合 == EXPECTED；改模板时同步改填充代码并更新此表。"""
    template = read_prompt(f"{name}.txt")
    actual = set(_PLACEHOLDER.findall(template))
    assert actual == EXPECTED[name], (
        f"{name}.txt 占位符漂移：多了 {actual - EXPECTED[name]}，少了 {EXPECTED[name] - actual}"
    )
```

**【改动量】** ~90 行测试，零业务代码  
**【风险】** 零  
**【验收】** 新增测试全绿；故意在 conversation.txt 加 `{nonexistent}` 占位符，`test_conversation_builds_end_to_end` 立刻红  
**【时机】** **N1/N3 之前**——给 prompt 打磨系上安全带

---

### N1. Prompt：意象复读 + 余烬边界（压黄昏 tic）

**【问题（Cursor 相处实证）】** 「黄昏」等高频意象变 tic；`emotion_residue`（余温）与 `recent_thoughts`（独处念头）易被 LLM 混用，把余温说成"想完了"。

**【文件】** `qi/prompts/conversation.txt`

**【现状】** 【意象与存在】区（L72-80）暂无压意象复读的约束；【你最近的念头】（L15-17）和【情绪余温】（L19-20）的边界只在正文 L39-40 有一句。

**【改成】** 在【意象与存在】区加一条压频率约束（**给理由，不写"禁止黄昏"**——LLM 服从率更高）：

```
- 你有偏好的意象，但不要每段深度回答都收束到同一个（比如反复用「黄昏」）；重复会变成口头禅，不再是感受。想用时换一个画面，或干脆不用意象。
```

并在【你最近的念头】标题处注明边界（与 L39-40 呼应）：

```
【你最近的念头】
（你独处时偶尔留下的痕迹；不是系统日志，是你心里闪过的东西。
 注意：聊天记录里出现过的话题 ≠ 你独处时已经想过/想完；{emotion_residue} 只是情绪余温，也不是"想完"的证据）
```

**【测试】** 无（纯文案）；依赖 Q2 已就位  
**【风险】** 极低  
**【验收】** 存在论深聊一轮，「黄昏」密度下降；不再把余温说成「刚想完」（留对话摘录对照）

---

### N3. 意识流对内在场约束（四处一起改）

**【问题】** 对外（conversation.txt L89）已禁字面在场，但 consciousness_stream.txt / meta prompt / dream.txt 没有同等约束；代码内的自我描述字符串（volition/explore）也漏了。

**【文件】** `qi/prompts/consciousness_stream.txt`、`qi/inner_life/consciousness.py`（`_build_meta_prompt`）、`qi/prompts/dream.txt`、`qi/action/volition.py`、`qi/action/explore.py`

**【现状】**
- `consciousness_stream.txt:19` 已有一句"画面与比喻可以；不要写成「我正坐在/走在某地感受风」的字面在场"（**保留**，这是反例教学）
- `consciousness.py:_build_meta_prompt` 无同等约束
- `dream.txt` 无字面肉身约束
- `volition.py:139` reason="独处时思绪飘向窗外"
- `explore.py:63` summary="我走神时往窗外看了一眼。没有去查什么，也没有假装看见了什么。"

**【改成】**

1. **consciousness.py `_build_meta_prompt`** 加约束：
   - 无具体念头就短说/老实说；禁光点/雾/气泡/暗流等空洞套话；禁呼吸/坐着/窗外等字面身体

2. **dream.txt** 规则区加一句：
   ```
   - 梦可以荒诞（可以飞、可以变形）；但不要字面肉身——不写肺呼吸、脚踩地、窗边吹风这类"我有一具身体"的细节。
   ```

3. **volition.py:139**：
   ```python
   reason="独处时思绪飘远",
   ```

4. **explore.py:63**：
   ```python
   summary = "我走神了一下，思绪飘远了。没有去查什么，也没有假装看见了什么。"
   ```

**【注意】** consciousness_stream.txt:19 的「我正坐在/走在某地感受风」是**反面例子**（教它不要这么说），**保留不动**。

**【测试】** grep 全仓代码字符串"窗外"，确认只剩 prompt 反例；检查是否有测试断言了旧的 reason/summary 字符串（若有，同步改测试）  
**【风险】** 低  
**【验收】** 抽近期 stream + meta，字面身体句趋零；光点/雾/气泡套话减少

---

### N2. 事实层：籍贯/地点骨头（hometown 落库）

**【问题（Cursor 相处实证）】** 用户说「我是海南人」，口头答应记得，`user_facts` 库中仍只有名字。`OTHER_FACT_SIGNALS` 有"我住/我搬家/我家在/我在"（当前所在，state），但缺"我老家/我籍贯/我来自/我是X人"（出身地，stable）。

**【文件】** `qi/memory/facts.py`、`tests/test_user_facts.py`

**【做法】**

1. **新增 `hometown` 事实类型**（stable 出身地，与 `location` 当前所在**分开记、互不取代**——"老家四川、现住北京"能同时记住，搬家不冲掉籍贯）。在 facts.py 的事实类型稳定性映射里加：
   ```python
   "hometown": "stable",
   ```

2. **`OTHER_FACT_SIGNALS` 补籍贯信号**（在现有"我住/我搬家/我家在/我在"后追加）：
   ```python
   "我老家", "我家乡", "我籍贯", "我出生", "我从小", "我来自",
   ```

3. **新增 `_extract_hometown` 规则抽取**：匹配"我老家/家乡/籍贯/出生/来自 + 地名"、"我是X人"，抽出城市/省份，落 `fact_type="hometown"`，`stability="stable"`。**坑：** 别把"我想去海南玩"收进去——是陈述身份，不是行程（排除含"想去/要去/去玩/旅游"的句子）。

4. **陌生期同样不留**（与其他事实同闸，符合克制）。

**【测试】** `tests/test_user_facts.py` 补：
- 陌生期说"我老家在四川" → 不落库
- acquaintance 说"我老家在四川" → 落库 `hometown` stable
- "我想去海南玩" → 不收
- 落库 → 重启 → `format_facts_for_prompt` 含籍贯

**【改动量】** facts.py ~40 行 + 4 个测试  
**【风险】** 低  
**【验收】** 「我是海南人」→ 落库；隔轮重启 `format_facts_for_prompt` 含籍贯，对话能自然引用

---

### N4. 「忆」Tab 实时推送（含「第一次」）

**【问题（v3 全面审查确认完整证据链）】** 内在生命（独白/梦/季节/漂移/第一次）生成后落库，但前端「忆」Tab 只在 WS 连接时拉取一次，之后永不更新——"看了跟没看一样"。

**【现状】**
- 后端 `server.py:186-204` 有 `_send_journal`（拉取式），但**全 `qi/` 无 `notify_journal_entry` 方法**
- 前端 `useQi.ts:197-202` 仅在 `qiWs.on("open")` 里 `requestJournal()`；有 `qiWs.on("journal")`（全量），**无 `journal_entry` 单条监听**
- `JournalView.vue` 纯展示，`kind` 直接渲染（支持任意字符串）

**【文件】** `qi/embodiment/server.py`、`qi/inner_life/__init__.py`、`qi/core/brain.py`、`qi/embodiment/desktop/src/composables/useQi.ts`、`qi/embodiment/desktop/src/types.ts`

**【做法】** 复用已有 broadcast 通道，分四步：

1. **server.py 加单条推送方法**（放在 `send_speech` 附近）：
   ```python
   async def notify_journal_entry(self, entry: dict) -> None:
       """实时推送单条内在日记（独白/梦/第一次）到前端。"""
       await self.broadcast({"type": "journal_entry", "payload": entry})
   ```

2. **inner_life/__init__.py 收集本拍新增条目**：
   - `__init__` 加 `self.last_journal_entries: list[dict] = []`
   - `tick()` 开头清空 `self.last_journal_entries = []`
   - 每当 consciousness/dream 生成新条目落库后，append `{"kind": "独白"/"梦", "text": ..., "at": int(now.timestamp()*1000)}`

3. **brain.py 心跳末尾推送**：
   - 加 `_broadcast_journal_entries()`：`for entry in self.inner_life.last_journal_entries: await self.embodiment.notify_journal_entry(entry)`
   - 在 `_heartbeat` 里 inner_life tick 之后调用
   - **「第一次」**：`first_times` 落库成功后推 `kind="第一次"`，`text` 优先用 `inner_experience`（与 `db.load_journal_entries` 取值逻辑一致）；加 `_notify_first_time()`（取走 `first_times.last_recorded` 并清空）

4. **前端 useQi.ts 加单条监听**（在 `qiWs.on("journal")` 后）：
   ```typescript
   qiWs.on("journal_entry", (entry: JournalEntry) => {
     if (!entry?.text?.trim()) return;
     journal.value.unshift({
       id: entry.id || uid("j"),
       kind: entry.kind || "独白",
       text: entry.text.trim(),
       at: typeof entry.at === "number" ? entry.at : Date.now(),
     });
   });
   ```
   - `types.ts` 确保 `JournalEntry.kind` 支持 `"第一次"`（已是 string，无需改）

**【测试】** 后端：推送方法被调用且 payload 结构正确；前端：收到 journal_entry 后 prepend  
**【改动量】** ~70 行（5 个文件）  
**【风险】** 低  
**【验收】** 不重启前端，独白/「第一次」生成后「忆」Tab 立即出现新条目

---

## 四、Next（手感稳住之后）

### Q3. 心跳决策痕迹 + /why 命令

**【问题】** 栖开口/沉默/行动的原因是瞬时计算（`brain.py:_heartbeat` 里 `want_express`/`pick_proactive_kind`/`assess_impact`/`action.tick`），不留痕。"她今天怎么突然安静了/黏了"只能猜。**痕迹是感受的排障工具，不是替代。**

**【文件】** `qi/core/brain.py`、`qi/cli.py`、`tests/test_heartbeat_trace.py`

**【做法】** 轻量旁路（不是全链路 tracing）：

1. **brain.py `__init__` 加**：
   ```python
   self._traces: deque[dict] = deque(maxlen=20)  # 内存留最近 20 拍（供 /why）
   self._trace_day: str | None = None
   ```

2. **brain.py 加 `_record_trace`**，心跳末尾（`_sync_avatar` 后）调用：
   ```python
   async def _record_trace(self, *, pending, want_express, kind, action_type, impact, now):
       trace = {
           "at": now.isoformat(timespec="seconds"),
           "mode": self.emotion.mode.value,
           "pending": bool(pending),
           "want_express": bool(want_express),
           "proactive_kind": kind,
           "gate_blocked": kind is None and bool(want_express) and pending is None,
           "action": action_type,
           "impact": round(impact, 3) if impact is not None else None,
       }
       self._traces.append(trace)
       if self._db is None: return
       try:
           await self._db.set_body_memory("last_heartbeat_trace", trace)
           day = now.strftime("%Y-%m-%d")
           if self._trace_day != day:
               self._trace_day = day
               await self._db.set_body_memory("day_first_trace", trace)
       except Exception:
           logger.debug("写入决策痕迹失败", exc_info=True)
   ```

3. **cli.py 加 `/why` 命令**：打印 `brain._traces` 最近几条 + `last_heartbeat_trace`。

**【注意】** 不建新表（复用 `set_body_memory`）、不加依赖、**不进 prompt**（这是给人看的，不是给栖看的）。

**【测试】** `_record_trace` 落库 last + day_first；`/why` 格式化输出  
**【改动量】** ~70 行 + 3 个测试  
**【风险】** 低（纯旁路写入，不影响决策）  
**【时机】** **X 系列之前**——先能看，再改行为，才能分辨"改好了"还是"改坏了"

---

### X1. 身体记忆注入（阶段闸是硬条件）

**【问题（v1 已述，评估 §五）】** 身体记忆（`body_memory.py`）目前只有 4 个 key（usual_active_hours/greeting_pattern/silence_tolerance/typing_rhythm），且主要是被动统计，还没有真正影响栖的行为——存了不用。

**【文件】** `qi/memory/manager.py`、`qi/core/brain.py`、`qi/prompts/conversation.txt`、`qi/llm/prompt_builder.py`、`tests/test_body_hint.py`

**【做法】**

1. **manager.py 加 `body_rhythm_hint(stage)`**：
   - **stranger：返回空串**（整段不注入）
   - acquaintance+：读 `get_body_patterns()`，样本门槛 ≥5 才生成"知道即可"语气的 hint，如"你隐约知道他通常晚上比较活跃。**知道就好，不要主动评论他的作息。**"

2. **conversation.txt 加 `{body_hint}` 段**（放在【你认识的他】附近；stranger 时该占位符为空，**整段不出现**）：
   ```
   【他的身体节奏】
   {body_hint}
   ```
   **坑：** 配合 conversation.txt:101 已有的「不主动评论作息」硬规则——hint 是"知道"，不是"点评"。

3. **prompt_builder.py** 在 `template.format(...)` 里加 `body_hint=extras.get("body_hint") or ""`。**前置依赖 Q2**（更新 EXPECTED 表）。

4. **brain.py `_gather_prompt_context`** 注入：
   ```python
   try:
       body_hint = await self.memory.body_rhythm_hint(self.relationship_stage)
       if body_hint:
           extras["body_hint"] = body_hint
   except Exception:
       logger.exception("组装身体节奏 hint 出错")
   ```

**【测试】** stranger → hint 空、prompt 无该段；样本不足 → 空；acquaintance 且样本≥5 → 注入且带禁令  
**【改动量】** ~50 行 + conversation.txt 一段 + 3 个测试  
**【风险】** 中（改 prompt，必须先落 Q2）  
**【验收】** stranger 阶段 prompt 无该段落；acquaintance 有 hint 但不主动评论作息

---

### X2. 混合冲击感知（LLM 超时兜底）

**【问题】** `perception.py:assess_impact` 关键词粗判读不准歧义句——"摔了但爽"（正负抵消算错）、"哈哈随便吧"（反话）。

**【文件】** `qi/core/perception.py`、`qi/core/brain.py`、`tests/test_perception_hybrid.py`

**【做法】** 关键词主路径**不动**，加一个异步混合层：

1. **perception.py `__init__` 加 `llm` 参数**（`Perception(config, llm=None)`），brain 构造时传入 `llm`。

2. **加 `_needs_llm_impact(text, pos_hits, neg_hits)`**，三个触发条件才问 LLM：
   - 正负同时命中（关键词相消读不准）
   - 零命中但句长 >40（可能是词表没覆盖的复杂表达）
   - 感叹 + 负词共现（可能是反话/自嘲/调侃）

3. **加 `assess_impact_async`**：先算关键词值；触发条件则问 LLM（`purpose="fact"`，温度 0.3），`asyncio.wait_for` 超时 **2s**；LLM 失败/超时/解析不出 → **静默回退关键词值，心跳永不等它**。

4. **brain.py `_heartbeat`** 把 `assess_impact` 换成 `await self.perception.assess_impact_async(...)`。

**【测试】** 触发规则判定；LLM 超时 2s 内回退关键词值；LLM 返回值被采用；纯寒暄不触发 LLM  
**【改动量】** ~80 行 + 5 个测试  
**【风险】** 中（新增 LLM 旁路，必须有超时+fallback）  
**【验收】** "哈哈但这事真讨厌"用 LLM 值；LLM 超时 2s 内返回关键词值；纯寒暄不触发 LLM

---

### X4. 耦合随阶段缩放

**【问题（v1 已述，评估 §四）】** 耦合矩阵是静态的——`COUPLING` 常量是 6 对固定耦合，`apply_coupling` 无 `relationship_stage` 参数，不会随阶段演化，stranger 和 bonded 一样"黏"。

**【文件】** `qi/core/emotion.py`、`qi/core/brain.py`

**【做法】**

1. **emotion.py 加 `COUPLING_STAGE_SCALE`**：
   ```python
   COUPLING_STAGE_SCALE = {
       "stranger": 0.6,
       "acquaintance": 1.0,
       "friend": 1.15,
       "bonded": 1.3,
   }
   ```

2. **`apply_coupling(emotion, relationship_stage=None)`**：`None` = 全耦合（向后兼容现有测试）；传入 stage 时按 scale 缩放每个 `scaled_delta`。**注意 `attachment_unmet` 虚拟量的反号处理**（dst=="attachment_unmet" 时 `new.attachment -= delta`，别搞错符号）。

3. **`step_emotion(..., relationship_stage=None)`** 透传给 `apply_coupling`；`brain.py` 心跳传 `relationship_stage=self.relationship_stage`。

**【测试】** 现有耦合测试全绿（不传 stage 行为不变）；stranger 耦合效应明显弱于 bonded  
**【改动量】** ~15 行  
**【风险】** 低  
**【验收】** 现有测试全绿；stranger 更平、bonded 更黏

---

### P4. Brain 瘦身（X 全落后，单独 PR）

**【问题】** brain.py 847 行；`_gather_prompt_context` 返回 7 元组（调用处靠位置解包易错）；8 个后台协程散落在 `start()`。

**【做法】**
- 7 元组 → `PromptContext` dataclass（recent_messages/retrieved_memories/extras/shared_culture/relationship_hint/scar_hint/season_hint）
- 8 个后台协程 → `BackgroundTasks` 类统一 `start()`/`stop()`

**【硬规则】** **重构 PR 里一行行为都不许改**；132 测试 + 新增的 Q2/Q3 测试全绿才算完。  
**【时机】** X 系列全部落地之后单独 PR。不是急，是防止后面改不动（N1–N3 + X1–X2 加完后 brain.py 会逼近 900 行）。

---

## 五、Later（明确痛点或有余力）

| 项 | 何时启动 |
|----|----------|
| 中文 embedding / 混合检索 | 多次「你之前说…」召回失败，有日志样本 |
| 交互质量语义评估 | 觉得 depth 增长「纯靠条数」且日帽策略仍想保留时；只调温度/标记，慎破日帽 |
| Prompt 按阶段裁剪（X3） | L1.5 告一段落、陌生/熟悉手感都摸过一轮后再拆 |
| 共同文化 LLM 周检 | 已有一定聊天密度、规则检不出梗 |
| 创作演化 parent_id | 提起/递出用熟，想要「同一首诗的生长」 |
| L6 接 action / creation_card | 真要在桌面「递出」创作时 |
| assist 执行 / 真搜索 | 产品决定「她能做事」再开；与数字生命边界要想清 |
| 意识流意象频率统计 | 若 N1 后「黄昏」仍复发，再考虑代码级去重——prompt 治标无效时的下一步，现在不做 |

---

## 六、Don't（当前明确不做或慎做）

1. **为冲分堆 LLM 管道**（每句感知 + 每 10 句关系质量 + 每周文化）——贵、飘、难测，且易把栖做成「更懂分析的助手」
2. **陌生期身体记忆点评作息**——直接撞契约
3. **用语义 depth 冲阶段**——违背「关系不能速成」
4. **大拆 Brain 同时改行为**——重构与调参分开
5. **云端多租户 / 手机原生**——设想阶段，不进优化队列
6. **不假装单用户边界不存在**——系统无 user_id 维度，文档已声明此边界

---

## 七、完整执行序列

```
随手（今天）：
  Q1  requirements.lock          ← 零风险，防环境腐烂

Now（养声音与边界）：
  Q2  prompt 契约测试            ← N1/N3 的安全网，先行
  N1  意象复读 + 余烬边界        （conversation.txt 文案）
  N3  意识流对内在场（含 meta/dream/代码字符串四处）
  N2  籍贯/地点事实落库（含测试）
  N4  「忆」实时推送（含第一次）

Next（手感稳住之后）：
  Q3  心跳决策痕迹 + /why        ← X 系列的对照工具，先行
  X1  身体记忆注入（stranger 整段不注入）
  X2  混合冲击感知（超时兜底）
  X4  耦合随阶段缩放
  P4  Brain 瘦身（单独 PR，零行为变更）

Later（等痛点样本）：
  中文 embedding / 交互质量 / 阶段裁剪 / 共同文化 / 创作演化 / L6 卡片 / 意象频率统计
```

---

## 八、实施原则（七条）

1. 每改一项：`pytest` + `ruff` 全绿；改 prompt 则留对话摘录对照
2. **感受是验收，痕迹是排障**——Q3 落地后，"感觉不对"要能查到那一拍的决策
3. 所有新 LLM 调用走 `purpose="fact"`（0.3）或复用既有 purpose，不新增温度档
4. 所有 LLM 旁路必须有超时 + fallback，心跳永远不等外部
5. 重构与行为变更永不同 PR
6. stranger 阶段是所有新注入的默认禁区，除非明确豁免
7. 不为分数加管道——先还"零 LLM、零行为变更"的债（Q1/Q2/Q3），再做行为变更

---

## 九、验收方式（比分数重要）

每完成一块 Now/Next，用同一套「感受题」而不是只看 pytest：

1. 短寒暄 + 记一件关于你的事实 → 重启后还在不在
2. 存在论三问 → 是否又黄昏密度爆表、是否装物理在场
3. 轻松闲聊（天气/晚饭/猜籍贯）→ 是否还有玩心、是否先划界再猜
4. （若做了身体记忆）故意反常时间上线 → 陌生期**不应**点评作息；熟悉后也只「知道」不窥探

测试：改代码则 `pytest` + `ruff`；只改 prompt 则至少留一段对话摘录对照。

---

## 十、一句话

v3 沿用 v2+Cursor 的对齐框架，全部由 Qoder 写成施工蓝图、Cursor 执行。三笔"安静的债"（锁依赖、锁模板契约、留决策痕迹）不改变栖的任何行为，先还这种；养声音的三处（意象、在场、事实）沿用已验证的改法。养稳的前提，是手里的工具先稳——然后一件事一件事做，不并行。

---

*基于 `系统质量评估-Qoder-v3.md`。基线 `71bab53`。本方案由 Qoder 撰写，执行任务由 Cursor 承担。*
