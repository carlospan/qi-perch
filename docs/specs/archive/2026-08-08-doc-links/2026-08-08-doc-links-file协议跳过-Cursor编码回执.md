# doc-links file:// 协议跳过——Cursor 编码回执

> **角色**：Cursor（执行侧）  
> **依据**：[方案审查回复](./2026-08-08-doc-links-file协议跳过-方案审查回复.md)（明示可编码）+ 修订后 PR  
> **时刻**：2026-08-08  

---

## 完工段

### 执行判断

相对放行件 **3 处均已落地**，仅改 2 文件，无文档改动、无偏离。

| # | 请求 | 落地 |
|---|------|------|
| 1 | `check_doc_links.py` L85 元组加 `"file://"` | ✓ |
| 2 | 模块 docstring L8 skip 说明补 `file://`（A2） | ✓ |
| 3 | `test_skip_external_and_anchor` parametrize 加 `file://` 用例 | ✓ |

### 偏离说明

无。

### 自测

| 命令 | 结果 |
|------|------|
| `python tools/check_doc_links.py` | **OK — no dead links** |
| `pytest tests/test_doc_links.py -q` | **21 passed** |
| `pytest -q` 全量 | **474 passed**（零红） |

说明：
- 编码中途曾因方案审查回复指向本回执（尚未落盘）出现 1 条相对链死链；本回执落盘后复跑全绿。
- `file://` 已跳过，不再报死链。
- 验收口径「473」= 修前 collected（472 绿 + 1 红）；本包 **+1** parametrize 用例 → 全量 **474 passed**，符合「baseline 全绿 + 新测」。

### git diff 预期范围

- `tools/check_doc_links.py`
- `tests/test_doc_links.py`
- 本回执 + 流程 md（若一并纳入）

### 验收交接

请方案 Agent 做实施验收（`-验收记录.md`）：

- [x] Cursor 侧：3 处改动 + 自测全绿  
- [ ] 方案侧：核 git diff（仅 2 代码文件）+ check_doc_links OK + 全量 473

**状态：编码完工，交实施验收。**
