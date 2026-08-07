# N5-b 检索相关门——PR 方案

> 类型：架构加固（N5 语言器官 / 检索-注入管线）｜依赖：N5 硬闸扩展 ✅、包 15/16/17 ✅
> 债务来源：N5 硬闸扩展交叉审查 B1-B——"语义命中但与当轮 topic/intent 不对题 → 不进卡或 low_confidence"
> 实证：活库 #1367（菜名 → 重置/珍惜记忆串台）
> 纪律：SDD-GUIDE §2.3——方案→Cursor 交叉审查→整改→编码→验收

## 0. 一句话

向量语义检索召回的"语义相近但话题无关"的记忆会污染 prompt，导致栖答非所问。
本任务在检索结果注入 IntentionCard 之前加一道**话题相关性闸**——过滤不相关记忆或降级标注。

## 1. 实证（#1367，活库）

| id | 角色 | 内容 |
|----|------|------|
| #1364 | 用户 | "你梦到 干拌烤鸭 了吗" |
| #1365 | 栖 | 回应烤鸭话题，正常 |
| #1366 | 用户 | "其实只是一个菜名，你不要放在心上" |
| **#1367** | **栖** | **"……那天下午，你问我记不记得重置的原因。我说以前确实是因为不够好，但你说了句'现在的你，我很珍惜'……后来又问我灵魂寄存在哪里……"** |

#1367 的回答**完全跳话题**——用户刚说了"只是菜名"，栖立刻跳到数周前的深度对话（重置/珍惜/灵魂寄存）。这些记忆在语义上"相关"（因为"珍惜"一词在菜名语境和深度对话中同时出现），但**话题完全不同**。

## 2. 根因

路径：

```
brain_context.py::gather_prompt_context()
  query = pending or "此刻的心情"      ← query="其实只是一个菜名，你不要放在心上"
  memories = retrieve_for_prompt(query)  ← 向量检索 top_k=3
      向量检索: "珍惜/放在心上" ↝ 命中了叙事记忆中"很珍惜"那段
  → PromptContext.memories = [重置/珍惜/灵魂寄存叙事...]
  → expression.express() 注入 prompt
  → LLM 看到三段深度对话记忆 + 当前"菜名"消息 → 优先响应了记忆中的"深度话题"
```

**关键点**：向量语义检索没有"话题相关性"判断。"珍惜"在菜名语境是日常用词，在深度对话中是情感关键词——向量空间里它们很近，但话题层面一个是日常闲聊、一个是存在追问。

## 3. 改动

### 3.1 `brain_context.py` — 检索后加话题相关性过滤

在 `gather_prompt_context` 的 `retrieve_for_prompt` 之后、注入 `PromptContext` 之前：

```python
memories = await brain.memory.retrieve_for_prompt(query, top_k=3)
memories = _filter_by_topic_relevance(memories, query, recent)  # 新增
```

新增 `_filter_by_topic_relevance(memories, query, recent)`：

```python
def _filter_by_topic_relevance(
    memories: list[dict],
    query: str,
    recent_messages: list[dict],
    *,
    min_overlap: int = 1,
) -> list[dict]:
    """过滤话题无关记忆。至少一个关键词与当前话题重叠才保留。"""
    from qi.memory.manager import MemoryManager

    # 当前话题关键词：用户消息 + 最近 2 条对话
    topic_text = query
    for m in recent_messages[-2:]:
        topic_text += " " + (m.get("content") or "")
    topic_words = set(
        w for w in re.findall(r"[\u4e00-\u9fff]{2,}", topic_text)
        if w not in _STOP_WORDS
    )

    kept = []
    for mem in memories:
        content = str(mem.get("content") or "")
        mem_words = set(re.findall(r"[\u4e00-\u9fff]{2,}", content))
        overlap = topic_words & mem_words
        if len(overlap) >= min_overlap:
            kept.append(mem)
        else:
            # 话题无关 → 不注入 prompt（日志记录）
            logger.debug(
                "检索相关门过滤: 记忆话题与当前无关, query_keys=%s, mem_keys=%s",
                sorted(topic_words)[:10], sorted(mem_words)[:10],
            )
    return kept  # B1 整改：全滤空不塞回错记忆；下游 expression 取 memories 时防空即可
```

`_STOP_WORDS`：常见停用词，避免"知道""可以""不要"等高频词造成假重叠。

**关键设计**：
- 基于关键词集合交的轻量判断——不需要 LLM 调用，不需要新依赖
- 全部被过滤时返回空列表（B1 整改：不塞回错记忆；下游 `build_intention_card` 防空已处理——`has_mem=False` 走 `answer`/`none` 路径）
- 停止词表确保"知道""可以""不要"等高频词不污染话题判断

### 3.2 （B2 整改：原 free_talk 低置信标记已删除）

凡 free_talk 记忆都打低置信过宽，本包只做话题过滤即可。

### 3.3 `tests/test_brain_context.py` 或 `tests/test_memory.py` — 防回归

- `test_filter_irrelevant_topic_memory`：构造菜名对话 context + 一条"重置/珍惜"记忆 → 过滤后记忆清单不含"重置"
- `test_keep_relevant_topic_memory`：构造睡眠话题 context + 一条"助眠/躺着"记忆 → 保留
- `test_return_empty_when_all_irrelevant`：全部被过滤时返回空列表（B1）
- 既有检索测试不变

### 3.5 红线

- 不删既有向量检索逻辑（`retrieve_for_prompt` 不改签名）
- `_STOP_WORDS` 只挡高频虚词，不挡话题关键词
- 不引入新依赖（纯 `re` + `set` 交集）

## 4. 验收标准

1. #1367 场景：菜名话题 + "重置/珍惜"记忆 → 记忆被过滤（单测）
2. 睡眠话题 + "助眠/躺着"记忆 → 保留（单测）
3. 全量过滤 → 返回空列表（B1，下游 `has_mem=False` 走空卡路径）
4. 既有检索/注入/表达测试不变
5. 全量 `pytest` 通过，`ruff` 零问题

## 5. 进度

| 步骤 | 状态 |
|------|------|
| 任务包 | ✅ `specs/tasks/2026-08-07-N5-b-检索相关门.md` |
| PR 方案 v1 | ✅（已撤回） |
| Cursor 交叉审查 | ✅ `包-N5-b-检索相关门-Cursor交叉审查.md`（**已吸收 B1/B2**） |
| PR 方案 v2 + 编码请求 | ✅ 本文件 + 编码请求 |
| Cursor 编码 | ✅ `包-N5-b-检索相关门-Cursor编码回执.md`（双字交 + 全量 457 passed） |
| 04 验收 | 待做 |
