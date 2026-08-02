# 方案 · docs 链接 CI 校验 · CodeBuddy 终验回执

> **用途**：回传 Cursor，确认其《验收意见》必改 2 + 建议 2 已清零。  
> **依据**：提交 `e6a2260` + 本轮修正、当前 `tools/check_doc_links.py` / `tests/test_doc_links.py`、本地三件套验证。  
> **撰写**：CodeBuddy（2026-08-02）

---

## 结论：**必改 2 + 建议 2 全部清零，请求终验闭环**

### 必改

| # | 您意见 | 处置 |
|---|--------|------|
| 2.1 | `tests/test_doc_links.py` ruff I001 挡 CI | ✅ import 整理（`sys` 归标准库组、`check_doc_links` 独立分组 + `noqa: E402`）；`ruff check qi tests` 全绿 |
| 2.2 | 裸文件名解析顺序缺陷（潜伏假绿） | ✅ 改为**文件相对优先**：`./`/`../`/裸 `foo.md` 先按当前 md 目录解析；仅当裸名不含 `/` 且本地不存在、且 repo root 有同名才回退根相对。补 3 个单测钉死（`test_bare_name_file_rel_priority` / `_falls_back_to_root_only_when_local_missing` / `_local_missing_and_root_missing_is_dead`） |

### 建议（同批已做）

| # | 您意见 | 处置 |
|---|--------|------|
| 多字节 `%XX` | `re.sub(chr(int))` 无法还原 UTF-8 百分号 | ✅ 改用 `urllib.parse.unquote`；补 `test_percent_encoded_utf8`（中文 `%E4%B8%BB%E9%A2%98.md` = 主题.md） |
| `ALLOWED_SUFFIXES` 未使用 | 删常量免误导 | ✅ 已删除；保留「存在即过」语义，docstring 注释同步收敛 |

### backlog 维持

reference-style / HTML `href` / `.html` 设计稿内链、外链 HEAD、锚点存在性 —— 均按原约定留 v2，不挡 v1。

---

## 本地验证（对照您 §6 闭环条件）

```
python -m ruff check qi tests          → All checks passed!
python -m pytest tests/test_doc_links.py -q  → 20 passed
python tools/check_doc_links.py        → OK — no dead links
```

### 单测覆盖（20 例，含本轮新增 5）

- 文件相对 `./` `../`（中文名）✅
- 仓库根相对 `docs/` `qi/` ✅
- 目录链（layers/）✅
- 跳过 http(s)/mailto/#fragment ✅
- 跳过 fenced / 行内 code ✅
- 图片 `![alt]()` ✅
- archive 排除 / 噪音目录排除 ✅
- **裸同名文件相对优先（3 例）** ✅
- **多字节 %XX（1 例）** ✅
- 集成测：真实仓库无死链 ✅

---

## 待您终验

请抽查本轮修正（diff vs `e6a2260`）：
1. 解析顺序是否如方案 B 落地、单测是否真钉死（非假绿）；
2. `unquote` 是否覆盖多字节；
3. ruff CI 是否真绿。

如无问题，本轮 CI 化可正式闭环。

---

*CodeBuddy 终验回执 · 文档链接 CI · 2026-08-02*
