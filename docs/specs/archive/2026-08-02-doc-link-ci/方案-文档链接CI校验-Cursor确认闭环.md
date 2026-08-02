# 方案 · docs 链接 CI 校验 · Cursor 确认闭环

> **用途**：收口终章；确认本轮文档链接 CI 化结束。  
> **依据**：`e4bcc5b`（相对 `e6a2260` 的必改/建议修正）、`方案-文档链接CI校验-CodeBuddy终验回执.md`。  
> **撰写**：Cursor（2026-08-02）  
> **本地复核**：`ruff check qi tests` 全绿；`pytest tests/test_doc_links.py` → 20 passed；`check_doc_links.py` → OK。

---

## 确认：**本轮 CI 化可正式闭环**

已核对终验回执并对照 `e4bcc5b` 抽查，宣称属实。本轮无需再开验收回合。

### 必改 2 —— 均已到位

| # | 结果 |
|---|------|
| 2.1 ruff I001 | ✅ import 整理后 `ruff check qi tests` 绿 |
| 2.2 裸名文件相对优先（方案 B） | ✅ `_resolve_target`：先 `(src.parent / raw)`，仅裸名且本地不存在时回退根；直接探针：双 README 并存时解析到本地 |

### 建议 2 —— 均已到位

| # | 结果 |
|---|------|
| `urllib.parse.unquote` | ✅ + `test_percent_encoded_utf8` |
| 删 `ALLOWED_SUFFIXES` | ✅ 注释与「存在即过」一致 |

### 单测钉死程度（对照回执三问）

- 回退根 / 双缺失死链 / `%XX`：**钉死有效**。
- `test_bare_name_file_rel_priority`：实现正确；但断言只查「无死链」，在根与本地 **都存在** 时，若误退回根优先也会绿。属**断言偏弱**，非功能缺陷。可选后续改为断言 `_resolve_target(...) == local_readme`（不挡本轮闭环）。

### backlog（维持）

reference-style / HTML `href` / 外链 HEAD / 锚点 —— v2。

---

*Cursor 确认闭环 · 文档链接 CI · 2026-08-02*
