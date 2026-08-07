# N5-b 检索相关门——编码请求（交 Cursor 执行）

> 配套：`包-N5-b-检索相关门-PR方案.md`（v2 整改后，B1/B2 已吸收）
> 审查溯源：`包-N5-b-检索相关门-Cursor交叉审查.md`
> 状态：交叉审查已完成，方案已整改，可编码
> 纪律：SDD-GUIDE §2.1——Cursor 编码，不重新设计架构方向

## 目标

向量语义检索召回的"语义相近但话题无关"的记忆会污染 prompt（#1367：菜名→重置/珍惜串台）。
本任务在 `brain_context.py` 的检索结果注入前加一道**话题相关性闸**——过滤不相关记忆。

## 改动一：`qi/core/brain_context.py` — 检索后加话题过滤

### 1.1 新增 `_filter_by_topic_relevance` 函数

```python
import re

_STOP_WORDS = frozenset({
    "知道", "可以", "不要", "没有", "什么", "这个", "那个", "自己",
    "不是", "已经", "怎么", "因为", "如果", "所以", "然后", "就是",
    "觉得", "应该", "真的", "还是", "但是", "不过", "可能", "其实",
    "有点", "一下", "一次", "一直", "一定", "一样", "只是", "不会",
    "一个", "今天", "现在", "已经", "刚才", "上次", "为什么",
})

def _filter_by_topic_relevance(
    memories: list[dict],
    query: str,
    recent_messages: list[dict],
    *,
    min_overlap: int = 1,
) -> list[dict]:
    """过滤话题无关记忆。至少一个关键词与当前话题重叠才保留。
    全部不重叠时返回空列表（B1：不塞回错记忆）。"""
    if not memories:
        return []

    # 当前话题关键词：用户消息 + 最近 2 条对话（如有）
    topic_text = query
    for m in recent_messages[-2:]:
        topic_text += " " + (m.get("content") or "")
    topic_words = {
        w for w in re.findall(r"[\u4e00-\u9fff]{2,}", topic_text)
        if w not in _STOP_WORDS
    }

    kept = []
    for mem in memories:
        content = str(mem.get("content") or "")
        mem_words = set(re.findall(r"[\u4e00-\u9fff]{2,}", content))
        if topic_words & mem_words:
            kept.append(mem)
    return kept
```

### 1.2 在 `gather_prompt_context` 中调用

在 `retrieve_for_prompt` 之后、`memories` 注入 `PromptContext` 之前插入一行：

```python
memories = await brain.memory.retrieve_for_prompt(query, top_k=3)
memories = _filter_by_topic_relevance(memories, query, recent)  # 新增
```

`recent` 已在函数上文（line 25/30）定义，无需新增变量。

## 改动二：防回归测试

### `tests/test_brain_context.py` 或 `tests/test_memory.py`

- `test_filter_irrelevant_topic_memory`：
  构造 query="其实只是一个菜名，你不要放在心上" + recent 对应上下文
  + 一条记忆 content="那天下午你问我记不记得重置的原因……现在的你我很珍惜"
  → 过滤后返回空列表（"菜名"与"重置/珍惜"无重叠关键词）

- `test_keep_relevant_topic_memory`：
  构造 query="晚上又睡不着" + 一条记忆 content="可以试试躺着，不强迫自己睡"
  → 过滤后保留该记忆（"睡不着"+"躺着"+"强迫"有多词重叠）

- `test_return_empty_when_all_irrelevant`：
  构造菜名对话 + 全部记忆都是深度对话话题 → 返回 []

## 红线（库内禁止）

- 不删既有向量检索逻辑（`retrieve_for_prompt` 不改签名）
- `_STOP_WORDS` 只挡高频虚词，不挡话题关键词
- 不引入新依赖（纯 `re` + `set` 交集）
- 全量过滤返回 []（B1 整改；下游 `build_intention_card` 的 `has_mem=False` 路径已处理空记忆）
- 不碰 `intention.py`（B2 整改：低置信标记不做）

## 验收（编码完成后）

- [ ] #1367 场景：菜名 + "重置/珍惜"记忆 → 空列表（单测）
- [ ] 睡眠话题 + "助眠"记忆 → 保留（单测）
- [ ] 全量过滤 → 返回空列表
- [ ] 既有检索/注入/表达测试不变
- [ ] 全量 `pytest` 通过，`ruff` 零问题

## 方案 Agent 验收栏（Cursor 勿填）

- [ ] 验收通过
- [ ] 打回（原因：）
- [ ] 需维护者 HITL（问题：）
