# L7 explore 真搜索 d-1 · 开口含蓄化——PR 方案

> 关联：[任务包](./2026-08-08-L7-explore真搜索-d1-开口含蓄化-任务包.md) / [d-1 验收](./2026-08-08-L7-explore真搜索-d1联网地基-验收记录.md)
> 编码交 Cursor；本方案 Agent 不写 qi/ 代码

## 外部可观测行为

explore 外部成功触发时，栖开口（qi_line 气泡）只说「我刚才看了看 {query}。」，不再念 search 返回的 title。DB 留痕 `summary` 仍保留完整 `query + title` 用于溯源。

## 精确改动点

### `qi/action/explore.py` drift 外部分支（[L288-294](file:///d:/qi-perch/qi/action/explore.py#L288-L294)）

现：

```python
if await self._should_external(curiosity, now):
    found, summary, outcome = await self._fetch_external(
        curiosity, emotion, season, now
    )
    speak = True
    qi_line = summary
    source = "web"
```

改为：

```python
if await self._should_external(curiosity, now):
    found, summary, outcome = await self._fetch_external(
        curiosity, emotion, season, now
    )
    speak = True
    if found is not None:
        # 开口含蓄（像走神）：只说 query，不念 search title
        qi_line = f"我刚才看了看 {found['query']}。"
    else:
        # 空手仍诚实开口（summary 即空手文本）
        qi_line = summary
    source = "web"
```

依赖：`_fetch_external` 成功时返回 `found` dict 含 `query` key（[L247-253](file:///d:/qi-perch/qi/action/explore.py#L247-L253) ✓，已存在）。空手时 `found=None`，走 `else`。

### `tests/test_explore_external_branch.py`

- `test_external_when_gates_pass`（成功 case）断言更新：
  - `result["qi_line"] == f"我刚才看了看 {query}。"`（不含 title）
  - `result["summary"]` 仍含 title（溯源完整）
- `test_external_empty_failed_capability_still_speaks`（空手 case）：`qi_line == summary` 不变，断言不动

## 纪律红线对照

- R1：不破（相处验证仍维护者做）
- **B3 仍守**：qi_line 模板化不二次 LLM；不改 `brain_delivery`；内部不说；外部 `speak+qi_line` 仍走现有 `elif` 分支
- 不引入 Agent 框架 / LLM 走 gateway（本改不动 LLM）/ DB 走 database
- scope：仅 `explore.py` + 1 测试文件

## 测试计划与验收清单

- [ ] `test_external_when_gates_pass`：成功 qi_line 不含 title、summary 含 title
- [ ] `test_external_empty_failed_capability_still_speaks`：空手 qi_line=summary 不变
- [ ] 现有内部/门控/冷却/web=None 测试不回归
- [ ] 全量 pytest ≥487
- [ ] 相处验证（维护者）：再听成功开口「我刚才看了看 {query}。」像走神

## 风险

- `found["query"]` 依赖 `_fetch_external` 返回结构（已存在，低风险）
- 用户听不到具体搜到什么（妥协，可接受——`found` dict 仍含完整 `entries` 给 d-2 卡片 / d-3 整合）
