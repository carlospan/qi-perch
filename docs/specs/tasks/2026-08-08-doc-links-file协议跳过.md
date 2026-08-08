# doc-links file:// 协议跳过——任务包

> 日期：2026-08-08
> 类型：**工具修复包**（tooling bug fix，1 行 + 1 测试用例）
> 依据：[curiosity 解堵验收记录 §三](./2026-08-08-L7-curiosity候选解堵-验收记录.md)（test_doc_links 预存在失败）
> SDD 流程：走 [SDD-GUIDE §2](file:///d:/qi-perch/docs/specs/SDD-GUIDE.md) 双 Agent 流程。

---

## Spec（外部行为）

`tools/check_doc_links.py` 跳过 `file://` 协议链接（与 `http/https/mailto/ftp` 同处理），不再当相对路径判死链。恢复 `test_integration_repo_clean` 全绿 → pytest 全量 baseline 回到 473 passed（无红）。

**口径**：跳过 = 不验证 `file://` 目标存在性（与 http 同；IDE 点击时自见是否 broken）。**不改文档约定**——仓库 Code Reference 继续用 `file:///` 绝对链（IDE 可点）。

## 背景（为何现在做）

[check_doc_links.py:85](file:///d:/qi-perch/tools/check_doc_links.py#L85) 跳过列表 `("http://", "https://", "mailto:", "ftp://")` **没含 `file://`** → `file:///d:/qi-perch/...` 落到文件相对解析（[L97](file:///d:/qi-perch/tools/check_doc_links.py#L97)）→ 路径不存在 → 判死链。现仓 51 条死链**全为 file://**（L6/L7 任务文档用 `file:///` 写法），HEAD 上测试本就红——红 baseline 会掩盖未来回归。

## 实现步骤概要

1. `tools/check_doc_links.py` [L85](file:///d:/qi-perch/tools/check_doc_links.py#L85)：`startswith` 元组加 `"file://"`。
2. `tests/test_doc_links.py` [test_skip_external_and_anchor L91-103](file:///d:/qi-perch/tests/test_doc_links.py#L91-L103)：parametrize 加 `"[f](file:///d:/x.md)"` 用例（锁跳过行为，防回归）。
3. **不改任何文档**（`file:///` 约定保留）。

## 验收

- [ ] [check_doc_links.py:85](file:///d:/qi-perch/tools/check_doc_links.py#L85) 含 `"file://"`
- [ ] `test_skip_external_and_anchor` 含 `file://` 用例
- [ ] `python tools/check_doc_links.py` → `OK — no dead links`
- [ ] `pytest tests/test_doc_links.py -q` 全绿
- [ ] `pytest -q` 全量 **473 passed**（baseline 恢复全绿，零红）
- [ ] git diff 仅 `tools/check_doc_links.py` + `tests/test_doc_links.py`（无文档改动）

## HITL 批点

- **口径已定**（跳过 `file://`、不验证、不改文档约定）——自治采纳推荐。
- 若维护者要 checker **验证** `file://` 目标存在性（而非跳过）→ 本包不做，另开增强包（需 file://→repo 相对解析，更复杂）。

## 纪律红线对照

- R1–R5 / contract：不涉（纯工具，无相处/prompt/人格）。
- 不引入 Agent 框架 / LLM gateway / DB database：不涉。
- 不开新阶段 / 不触路线：✓ 工具卫生。
- 常量默认值：不涉。
