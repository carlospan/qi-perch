# L7 explore 真搜索 d-2（内部深读）——Cursor 编码回执

> **角色**：Cursor（编码）  
> **依据**：[方案审查回复](./2026-08-08-L7-explore真搜索-d2内部深读-方案审查回复.md)（路 A，明示可编码）+ 修订后 [PR 方案](./2026-08-08-L7-explore真搜索-d2内部深读-PR方案.md)  
> **时刻**：2026-08-08  

---

## 落地

| 项 | 状态 |
|----|------|
| `qi/action/explore.py` 新增 `_digest_hits`（`consciousness` / 隐私红线 / 失败·空·无 llm 降级只念 query） | ✓ |
| `_fetch_external` 成功：`summary = await self._digest_hits(query, hits)`；`found.entries` 仍留 hits | ✓ |
| drift 外部分支：`qi_line = summary`（收回 d-1 开口含蓄化拆） | ✓ |
| N2-a：`tests/test_explore_external_branch.py` `_FakeLLM` 支持按调用序返回 | ✓ |
| N2-b：`test_external_when_gates_pass` 断言改为两次 consciousness、`qi_line==summary==digest`、title 只在 entries | ✓ |
| 新增 `tests/test_explore_digest.py`：成功 / 空串降级 / 异常降级 / 无 llm / 降级仍 `outcome=success` | ✓ |
| 未碰 `brain_delivery` / `layer` / `brain` / `settings` / 外部门控 | ✓ |

---

## pytest

| 命令 | 结果 |
|------|------|
| `pytest tests/test_explore_digest.py tests/test_explore_external_branch.py tests/test_explore_web.py -q` | **18 passed** |
| `pytest -q` 全量 | **492 passed**（≥487；本包新增 digest 用例） |

---

## 偏离

1. **N3（prompt 冗余）**：实现侧择一——system 用「不编造。红线：`{_QUERY_PRIVACY_LINE}`」，未再叠写第二句「不引用 user_facts/对话内容」字面（常量本身已是该句）。  
2. **N5 文档回写**：按审查回复不进本包 scope；`L7-action.md` / `progress` 留给验收或另拍。  
3. 方法放置：`_digest_hits` 紧挨在 `_fetch_external` 之后、`drift` 之前（与 PR「`_fetch_external` 后」一致）。

---

## 下一拍

- Trae：实施验收  
- 维护者：相处复验——外部开口像「看懂了外面」，而非念 title / 只念 query  

---

*Cursor 编码回执 · 2026-08-08 · 492 passed*
