# L7 assist-7（全文读取与叙事内化）——Cursor 编码回执

> **角色**：Cursor（执行侧）  
> **依据**：[编码请求](./2026-08-09-L7-assist7-全文读取与叙事内化-编码请求.md)（B1 关闭，明示可编码）+ 修订后 PR  
> **时刻**：2026-08-09  

---

## 完工段

### 改动文件

| 文件 | 改动 |
|------|------|
| `qi/action/assist.py` | 删 `_MAX_READ_BYTES`；加 `_MAX_FILE_BYTES` / `_DIGEST_CHUNK_LEN` / `_DIGEST_MAX_CHUNKS`；构造器 `narrative=`；1MB 保护 + 全读；`_digest_chunk` / `_merge_digests`（单块短路）/ `_read_and_digest` + 每块 `narrative.save`；删 `_digest_file` |
| `qi/action/layer.py` | `AssistAction(..., narrative=narrative)` |
| `tests/test_assist_fulltext.py` | **新增** assist-7 五测 |
| `tests/test_action_assist.py` | R5：`test_assist_digest_uses_llm` 断言短文件 `len(calls)==1` |

### 新增测试

1. `test_assist_short_file_single_digest` — 1 次 digest、无合并、narrative 1 条、无诚实声明  
2. `test_assist_long_file_chunked` — 20_000 字 → 3 块 + 1 合并、narrative 3  
3. `test_assist_oversize_chunks_truncated` — 7 块 → 只 6 + 声明  
4. `test_assist_huge_file_fails_honest` — `_MAX_FILE_BYTES=0` 触发诚实失败 + 留痕  
5. `test_assist_narrative_not_fulltext` — 叙事含概要不含全文  

（`test_assist_detail_has_content_preview` 仍在 `test_assist_action_rewrite.py`，未改坏。）

### 相对编码请求的执行判断

- 四处改动按请求落地；B1 定案 a：单块不调合并 LLM。  
- 1MB 测用 `monkeypatch` 将 `_MAX_FILE_BYTES` 置 0（等价触发，避免真建大文件 / 易碎 Path.stat mock）。  
- narrative 测用 `_FakeNarrative` 记录 `save`，不拉起 Chroma。  
- 无偏离。

### 自测

- `pytest`：**585 passed**（≥585）  
- `ruff check`：改动文件通过  

### 验收勾选（工程侧）

- [x] 短文件：1 次块 digest（无合并）；narrative 1 条；无诚实声明  
- [x] 多块：块数 = digest 次数；合并 1 次；narrative = 块数  
- [x] 超块上限：只读前 6 + 诚实声明  
- [x] 超 1MB：诚实失败 + failed_capability  
- [x] narrative 含概要不含全文  
- [x] 全量 ≥585  
- [ ] 相处复验（与 assist-6 统一）——交维护者 / 方案侧  

---

*Cursor · 编码回执完工 · 2026-08-09 · 交 Trae 实施验收*
