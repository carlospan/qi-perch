# L7 隐私小刀（explore 红线覆盖文件内容）——Cursor 编码回执

> **角色**：Cursor（执行侧）  
> **依据**：[方案审查回复](./2026-08-09-L7-隐私小刀-explore红线覆盖文件内容-方案审查回复.md)（路 A 放行）+ PR  
> **批次**：与 assist-8 同批编码 / 同批验收  
> **时刻**：2026-08-09  

---

## 完工段

### 改动文件

| 文件 | 改动 |
|------|------|
| `qi/action/explore.py` | `_QUERY_PRIVACY_LINE` → `不引用 user_facts、对话内容或用户文件内容原文`（`_make_query` / `_digest_hits` / `_digest_internal` 三处自动生效） |
| `tests/test_explore_digest.py` | 旧措辞断言迁移 |
| `tests/test_explore_external_branch.py` | 旧措辞断言迁移 |
| `tests/test_explore_internal_digest.py` | 新增 `test_query_privacy_line_covers_user_files` |

### 相对请求的执行判断

- 一处常量、三处生效，按 PR 原样。  
- 写死旧句两测已迁；internal 测本就引用常量。  
- 无偏离。

### 自测

- 与 assist-8 同批全量：**587 passed**（≥585）  
- `ruff check`：通过  

### 验收勾选（工程侧）

- [x] `_QUERY_PRIVACY_LINE` 含「用户文件内容原文」  
- [x] 措辞断言迁移无遗漏  
- [x] 全量 ≥585  
- [ ] 相处复验（explore 不背诵文件字）——交维护者 / 方案侧  

---

*Cursor · 编码回执完工 · 2026-08-09 · 交 Trae 同批验收*
