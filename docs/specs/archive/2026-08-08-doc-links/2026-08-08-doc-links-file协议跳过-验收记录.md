# doc-links file:// 跳过——实施验收记录

> 验收方：方案 Agent（Trae）
> 编码方：Cursor（[回执](./2026-08-08-doc-links-file协议跳过-Cursor编码回执.md)）
> 时刻：2026-08-08

---

## 一、改动点核对（git diff，逐点比对 PR）

| PR 改动点 | git diff | 偏离 |
|-----------|-----------|------|
| **A** [check_doc_links.py:85](file:///d:/qi-perch/tools/check_doc_links.py#L85) 跳过元组加 `"file://"` | `("http://", "https://", "mailto:", "ftp://", "file://")` | 无 |
| **A2** [check_doc_links.py:8](file:///d:/qi-perch/tools/check_doc_links.py#L8) docstring skip 说明补 `file://` | `跳过 fenced/inline code、http(s)/mailto、file://、纯 #fragment。` | 无 |
| **B** [test_doc_links.py:97](file:///d:/qi-perch/tests/test_doc_links.py#L97) parametrize 加 `file://` 用例 | `"[file](file:///d:/qi-perch/docs/x.md)",` | 无 |

**偏离方案处**：无。

**git diff --stat**：`tools/check_doc_links.py`（4 行 ±）+ `tests/test_doc_links.py`（1 行 +）+ `docs/specs/tasks/README.md`（3 行 ±，索引行——方案 Agent 落盘时加的 doc-links 行，process 稿，非代码）。

## 二、纪律红线

R1–R5 / contract / Agent 框架 / LLM gateway / DB database：**全不涉**（纯工具 + 测试）。不开新阶段、不触路线。文档约定 `file:///` **保留不改**。

## 三、独立复跑（非依赖 Cursor 自报）

| 验证 | 结果 |
|------|------|
| `python tools/check_doc_links.py` | `[doc-link-check] OK — no dead links under D:\qi-perch` ✓（51 条 file:// 死链全放行） |
| `pytest tests/test_doc_links.py -q` | **21 passed** in 5.16s ✓ |
| `pytest -q` 全量 | **474 passed** in 52.70s ✓（零红） |

**baseline 恢复全绿**：修前 472 passed / 1 failed（test_doc_links 预存在红）；修后 474 passed（原 473 collected + 本包新增 1 parametrize 用例，原失败测转绿）。**红 baseline 消除**——未来回归可见。

## 四、验收清单（照任务包）

- [x] [check_doc_links.py:85](file:///d:/qi-perch/tools/check_doc_links.py#L85) 含 `"file://"`
- [x] 模块 docstring [L8](file:///d:/qi-perch/tools/check_doc_links.py#L8) skip 说明含 `file://`（A2）
- [x] `test_skip_external_and_anchor` 含 `file://` 用例
- [x] `python tools/check_doc_links.py` → OK
- [x] `pytest tests/test_doc_links.py -q` 全绿（21 测）
- [x] `pytest -q` 全量 **474 passed**（baseline 全绿）
- [x] git diff 代码仅 2 文件（tools/check_doc_links.py + tests/test_doc_links.py；README.md 为索引 process 稿）

## 五、结论

**工程验收通过。** 3 改动点全落地、无偏离；纪律全过；独立复跑 474 passed 零红；**test_doc_links 红 baseline 消除，仓库测试 baseline 恢复全绿**。

## 六、待办

- 提交/推送：未执行。本包工程面全绿，可提交（含 2 代码文件 + tasks/README 索引 + 本包过程稿）。
- 口径「跳过 file://、不验证目标存在性」落实；若日后要验证 file:// 目标 → 另开增强包。
