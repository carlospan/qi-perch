# doc-links file:// 协议跳过——PR 方案

> 配套：[2026-08-08-doc-links-file协议跳过.md](./2026-08-08-doc-links-file协议跳过.md)（任务包）
> **编码交 Cursor；本方案 Agent 不写 `qi/` 或 `tools/` 代码。**

---

## 一、外部可观测行为（Spec）

`file://`（含 `file:///`）协议链接不再被判死链——`check_doc_links` 跳过之，与 `http/https/mailto/ftp` 同。`test_integration_repo_clean` 恢复全绿。

## 二、精确改动点

### A. `tools/check_doc_links.py` — 跳过列表加 `file://`

**位置**：[`_resolve_target` L85](file:///d:/qi-perch/tools/check_doc_links.py#L85)

**现状**：
```python
    # 跳过外部 / 协议链接 / 纯锚点
    if raw.startswith(("http://", "https://", "mailto:", "ftp://")):
        return None
```

**拟改**：元组加 `"file://"`：
```python
    if raw.startswith(("http://", "https://", "mailto:", "ftp://", "file://")):
        return None
```

**意图**：`file:///d:/qi-perch/...` 在协议跳过处返回 `None`（外部/不可判定），不再落到 L97 文件相对解析。符合 checker 自身设计（[L8](file:///d:/qi-perch/tools/check_doc_links.py#L8)「检查本地相对链接」——`file://` 是绝对 file URL，非本地相对）。

**A2（采纳审查非阻塞 · 同文件）**：模块 docstring [L8](file:///d:/qi-perch/tools/check_doc_links.py#L8) skip 说明补 `file://`——「跳过 fenced/inline code、http(s)/mailto、**file://**、纯 #fragment」。防后人困惑为何 file:// 不验。

### B. `tests/test_doc_links.py` — 锁 `file://` 跳过行为

**位置**：[`test_skip_external_and_anchor` L91-103](file:///d:/qi-perch/tests/test_doc_links.py#L91-L103) parametrize 列表

**现状**：
```python
@pytest.mark.parametrize(
    "link",
    [
        "[ext](https://openai.com/docs)",
        "[mail](mailto:a@b.com)",
        "[anchor](#section-1)",
    ],
)
```

**拟改**：加一条 `file://` 用例：
```python
        "[anchor](#section-1)",
        "[file](file:///d:/qi-perch/docs/x.md)",
    ],
```

**意图**：钉死「`file://` 跳过、不判死链」，防回归（若有人移除 L85 的 `file://`，此测即红）。

### C. 不改的

- 任何 `docs/**/*.md`（`file:///` 写法保留——Code Reference 约定）。
- checker 其他逻辑（`_resolve_target` 其余分支 / `collect_md_files` / `check` 不变）。

## 三、纪律红线对照

| 红线 | 对照 |
|------|------|
| R1–R5 / contract | 不涉 |
| 不引入 Agent 框架 | ✓ |
| LLM gateway / DB database | 不涉 |
| 不开新阶段 / 不触路线 | ✓ 工具卫生 |
| 常量默认值 | 不涉 |
| 文档约定 | ✓ `file:///` 保留不改 |

## 四、测试计划与验收清单

**测试**：
- 现有 `tests/test_doc_links.py` 20 测全绿 + 新增 `file://` parametrize 用例（共 21 测，审查侧核实）。
- `python tools/check_doc_links.py` → `OK — no dead links`（0 死链）。

**验收勾选**（照任务包）：
- [ ] [check_doc_links.py:85](file:///d:/qi-perch/tools/check_doc_links.py#L85) 含 `"file://"`
- [ ] 模块 docstring [L8](file:///d:/qi-perch/tools/check_doc_links.py#L8) skip 说明含 `file://`
- [ ] `test_skip_external_and_anchor` 含 `file://` 用例
- [ ] `python tools/check_doc_links.py` → OK
- [ ] `pytest tests/test_doc_links.py -q` 全绿（21 测）
- [ ] `pytest -q` 全量 **473 passed**（baseline 全绿）
- [ ] git diff 仅 2 文件（tools/check_doc_links.py + tests/test_doc_links.py）

## 五、风险 / 不确定点 / 拍板项

- **风险 1（跳过=不验证 file:// 目标）**：跳过后 broken `file://` 链不被 checker 抓。**可接受**——`file://` 是 IDE 点击用，broken 时 IDE 自见；且 http/mailto 同此处理。若日后要验证，另开增强包（需 file://→repo 相对解析）。
- **不确定**：无。
- **拍板项**：口径「跳过、不验证、不改文档约定」已定（任务包 HITL）；无未决。
- **待追认（自治）**：`file://` 用例落在 `test_skip_external_and_anchor` parametrize（复用现有测，不另起函数）。

## 六、明确：编码交 Cursor

本方案 Agent 不写代码。按 SDD-GUIDE §2.3：

1. Cursor 读完本 PR → 落盘交叉审查（禁码）+ 理解确认。
2. 无阻塞 → 路 A：方案 Agent 落 `-方案审查回复.md`「无需整改，可编码」。
3. 明示可编码 → Cursor 编码 → `-Cursor编码回执.md` 完工段 → 方案 Agent 实施验收。

若有阻塞 → 路 B（PR 修订 → 整改复审 → 编码请求 → 编码）。
