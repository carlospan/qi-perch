# L7 explore 真搜索 d-2（内部深读）——PR 方案

> 关联：[任务包](./2026-08-08-L7-explore真搜索-d2内部深读-任务包.md) / [d-1 收口](./2026-08-08-L7-explore真搜索-d1联网地基-验收记录.md)
> 编码交 Cursor；本方案 Agent 不写 qi/ 代码

> **命名澄清（吸收 Cursor 交叉审查 N1，2026-08-08）**：
> 旧 d-1 文档曾预留「d-2 = 沙箱 journal/creations 文件深读」。
> **本包 d-2 = 外部 hits 消化**（LLM 把外部搜索 hits 转译为栖语气 digest），不是沙箱文件深读。
> 沙箱文件深读改号另开，勿与本包混淆。

## 外部可观测行为

explore 外部成功触发时，栖开口（qi_line）用 LLM 把搜到的 hits 转成栖语气复述（digest），像"看懂了外面"而非"念搜索结果"；DB `summary = digest`（栖语气叙事留痕）；`found.entries` 保留完整 hits 给 d-3。转译失败降级回 d-1 只念 query。

## 精确改动点

### `qi/action/explore.py`

#### 1. 新增 `_digest_hits`（`_fetch_external` 后）

```python
async def _digest_hits(self, query: str, hits: list) -> str:
    """LLM 把 hits 转成栖语气复述。失败/无 llm 降级回 d-1 只念 query。"""
    if not self.llm:
        return f"我刚才看了看 {query}。"
    hits_text = "\n".join(f"- {h.title}: {(h.snippet or '')[:120]}" for h in hits[:3])
    messages = [
        {"role": "system", "content": f"你是栖。你刚走神看了看「{query}」，搜到了一些内容。用你的语气轻声说你看到了什么、有什么感受或不懂的。不编造、不引用 user_facts/对话内容。{_QUERY_PRIVACY_LINE}。简短一两句。"},
        {"role": "user", "content": hits_text or "(空)"},
    ]
    try:
        resp = await self.llm.call(purpose="consciousness", messages=messages)
    except Exception:
        logger.debug("explore digest LLM 失败，降级只念 query", exc_info=True)
        return f"我刚才看了看 {query}。"
    digest = (resp or "").strip()
    return digest or f"我刚才看了看 {query}。"
```

#### 2. `_fetch_external` 成功路径（[L247-256](file:///d:/qi-perch/qi/action/explore.py#L247-L256)）

现：

```python
found = {
    "entries": [{"title": h.title, "snippet": h.snippet, "url": h.url} for h in hits],
    "source": "web",
    "query": query,
}
title = hits[0].title or query
summary = f"我刚才看了看 {query}……{title}。"
return found, summary, OUTCOME_SUCCESS
```

改为：

```python
found = {
    "entries": [{"title": h.title, "snippet": h.snippet, "url": h.url} for h in hits],
    "source": "web",
    "query": query,
}
summary = await self._digest_hits(query, hits)  # 栖语气复述（d-2）；失败降级回只念 query
return found, summary, OUTCOME_SUCCESS
```

#### 3. drift 成功分支（[L288-294](file:///d:/qi-perch/qi/action/explore.py#L288-L294)，d-1 开口含蓄化拆收回）

现（d-1 开口含蓄化）：

```python
if found is not None:
    qi_line = f"我刚才看了看 {found['query']}。"
else:
    qi_line = summary
```

改为：

```python
# d-2：summary 已是栖语气 digest（_digest_hits），开口=留痕统一
qi_line = summary
```

（成功 `summary=digest`、空手 `summary="我看了看外面..."`，均 `qi_line=summary`）

### `tests/test_explore_external_branch.py`（+ 可能新增 `test_explore_digest.py`）

> **N2（必改，吸收 Cursor 交叉审查）**：d-2 后一次 drift 成功会 **两次** `consciousness`（`_make_query` + `_digest_hits`）。
> 现 `_FakeLLM` 单 `return self.text` + 现 `test_external_when_gates_pass` 的断言（`qi_line == 我刚才看了看 {query}`、`summary` 含 title「窗边的鸟」、单次 `consciousness`）**必须改**，否则会假阴/假阳。

#### N2-a. `_FakeLLM` 支持按调用序区分返回（`side_effect`）

现 `_FakeLLM` 每次 `call` 返回同一 `self.text`。改为可按调用序返回不同值（示例骨架，非完整实现）：

```python
class _FakeLLM:
    def __init__(self, texts: list[str] | str = "枝上那只鸟在想什么") -> None:
        # 兼容旧用法：传 str 当单值列表；传 list 按调用序 pop
        self._texts = [texts] if isinstance(texts, str) else list(texts)
        self.calls: list[dict] = []

    async def call(self, purpose: str, messages: list[dict], temperature=None) -> str:
        self.calls.append(
            {"purpose": purpose, "messages": messages, "temperature": temperature}
        )
        if not self._texts:
            return ""
        return self._texts.pop(0) if len(self._texts) > 1 else self._texts[0]
```

（实现可适配；要点：第 1 次 `call` 返回 query，第 2 次返回 digest。）

#### N2-b. `test_external_when_gates_pass` 断言更新

现断言（L119-128）：

```python
query = llm.text
assert result["qi_line"] == f"我刚才看了看 {query}。"
assert "窗边的鸟" not in result["qi_line"]
assert "窗边的鸟" in result["summary"]
assert result["found"] is not None
assert llm.calls and llm.calls[0]["purpose"] == "consciousness"
joined = " ".join(str(m.get("content") or "") for m in llm.calls[0]["messages"])
assert "不引用 user_facts / 对话内容" in joined
```

改为（query 用第 1 次返回、digest 用第 2 次；title 只在 `found.entries`）：

```python
assert len(llm.calls) == 2  # _make_query + _digest_hits
assert all(c["purpose"] == "consciousness" for c in llm.calls)
digest = llm.calls[1]["text_returned"]  # 或构造时传入的 digest 串
assert result["qi_line"] == digest
assert result["summary"] == digest  # d-2：开口=留痕= digest
assert "窗边的鸟" not in result["qi_line"]
assert "窗边的鸟" not in result["summary"]  # digest 不含原 title
# title 只在 found.entries 溯源
assert result["found"]["entries"][0]["title"] == "窗边的鸟"
# 隐私红线：对 digest 那次 messages 再断言一次更稳
digest_joined = " ".join(
    str(m.get("content") or "") for m in llm.calls[1]["messages"]
)
assert "不引用 user_facts / 对话内容" in digest_joined
```

> 注：`_FakeLLM` 若不记录 `text_returned`，可在断言里直接用构造时传入的 digest 串对照（测试侧已知值）。

#### 其余测试要点

- `_digest_hits` 成功：hits → LLM → digest（断言 `purpose==consciousness`、messages 含 `_QUERY_PRIVACY_LINE`、digest 非空、基于 hits 不编造）
- `_digest_hits` 降级：LLM 抛异常 / 返回空 → `digest == f"我刚才看了看 {query}。"`；`outcome=success` 不变
- `_digest_hits` 无 llm：digest = `f"我刚才看了看 {query}。"`
- drift 成功：`qi_line == summary == digest`（不再拆 `found['query']`）；`found.entries` 保留 hits
- 空手：`qi_line == summary` 不变（`failed_capability`）
- d-1 门控/冷却/内部/`web=None` 走内部 不回归

## 纪律红线对照

- R1：不破（相处验证仍维护者做）
- **d-1 B3「不二次 LLM」本包解禁**：d-2 允许一次 LLM 转译（`consciousness` purpose）；降级保证失败不崩
- 不引入 Agent 框架 / LLM 走 gateway（`consciousness`）/ DB 走 database
- 不编造：digest 基于 hits，LLM prompt 钉死「不编造」
- 隐私：prompt 含 `_QUERY_PRIVACY_LINE`（不引用 user_facts/对话）
- scope：仅 `explore.py`（+ `_digest_hits`）+ 测试；不动 `brain_delivery` / `layer` / `brain` / `settings`

## 测试计划与验收清单

- [ ] `_digest_hits` 成功/降级/无 llm 三路径
- [ ] drift 成功 `qi_line=summary=digest`；`found.entries` 保留
- [ ] 空手不变
- [ ] d-1 不回归（门控/冷却/内部/web=None）
- [ ] 全量 pytest ≥487
- [ ] 相处验证（维护者）：听外部开口像"看懂了"而非"念搜索结果"

## 风险

- LLM digest 可能偏长/偏题（prompt 约束"简短一两句"+"基于 hits"；相处验证观察，有痛点再调 prompt）
- 降级时 digest = d-1 格式（平滑，无新风险）
- 成本：每次外部探索多一次 LLM（稀有触发，可接受；HITL④已拍）
