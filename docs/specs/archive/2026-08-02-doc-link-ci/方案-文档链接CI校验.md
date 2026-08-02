# 方案 · docs 链接自动校验（CI 化）

> 背景：体系重构已闭环（`6a8a933` + `51cb114`）。重构前靠人工全库扫死链；大厂工程实践把"死链/失效引用"交给 CI 自动门禁。本方案将其自动化，纳入现有 GitHub Actions。
> 状态：**定稿 v2（已吸收 Cursor 交叉检验结论）**
> 撰写：CodeBuddy（2026-08-02）；交叉检验：Cursor（同目录 `方案-文档链接CI校验-Cursor回复.md`）

---

## 一、目标

1. 提交/PR 时自动检测 `docs/`（及仓库根 `README.md`、各 `qi/**/README.md`）的 Markdown 死链、失效相对路径。
2. **不引入 Node 工具链**——仓库为纯 Python 栈（见 `ci.yml`：`ruff` + `pytest`，无 `setup-node`），应保持单一技术栈。
3. 支持中文文件名、相对链接（`./`、`../`、`docs/`）、跨 `docs/` 子目录解析。
4. 与现有 `ci.yml` 融合，不破坏既有 lint/test。

## 二、现状盘点

- 现有 CI：`.github/workflows/ci.yml` 仅 `lint-test`（Python 3.12 + ruff + pytest）。
- `docs/` 使用相对链接的文件：`explanation/栖·数字生命架构方案.md`（6 处 `../specs/...`）、`tutorials/README.md`（1）、`how-to/换机搭建.md`（2）。
- 史上已无 `docs/dev/`、`docs/design/` 等死前缀（重构已清），但**未来新增文档仍可能引入死链**，故 CI 有价值。

## 三、方案选型（C1–C3 候选）—— **已拍板 C1**

| 方案 | 工具 | 栈 | 中文路径 | 相对链解析 | 评价 |
|------|------|----|---------|-----------|------|
| **C1（采用）** | `markdown-link-check` 的 **Python 等价**：自写轻量检查器 `tools/check_doc_links.py` + `tests/test_doc_links.py` 单测 | Python | ✅ | ✅ 自实现 | 零新依赖、零 Node、可控、可单测 |
| C2 | `tcort/markdown-link-check`（Node） | Node | ✅ | ✅ | 业界标准，但**引入 Node 工具链**，与纯 Python 栈冲突 → 否决 |
| C3 | `lychee` (Rust 二进制) | 二进制 | ✅ | ✅ | 快、强，但需下载二进制、对纯本地相对链过重 → 外链在线校验留作 v2 backlog |

**Cursor 交叉检验结论**：C1 成立。代价——解析边界须自测满（见第六节坑清单），不能假装等价于成熟工具。逻辑放可 import 的检查器；CI 调 CLI；用少量单测钉死解析规则。不必上 lychee，除非以后要查外链。

**放置分工（两者都要，非二选一）：**
- `tools/check_doc_links.py`：CLI 主入口；含可 `import` 的 `check()`；打印 `文件:行号:链接`；非零退出。
- `tests/test_doc_links.py`：单测解析规则（`../`、中文名、目录链、跳过 http/archive、仓库根相对 `docs/`…）；可选集成测复用同一 `check()`，**禁止两套逻辑**。
- 现有仓库无 `tools/`，新建合理（仓库卫生脚本，非产品包）。

## 四、落地设计（C1）

### 4.1 检查器 `tools/check_doc_links.py`

职责：
- 递归扫描白名单目录：`docs/`、`README.md`、`qi/**/README.md`。
- 解析每个 `.md` 的 `[text](target)` 与 `[text](target "title")`。
- 判定：
  - `http(s)://` 外部链 → **跳过**（不联网，避免 CI 抖动；如需可后加 lychee）。
  - 锚点 `#sec` → 校验同文件是否有对应标题（可选，v1 可只校验文件存在）。
  - 相对路径 → 以**当前 .md 所在目录**为基准 `os.path.normpath` 解析；支持 `./`、`../`、`docs/`（仓库根相对）。
  - 目录链接（如 `docs/reference/layers/`）→ 解析到目录存在即可。
- 输出：发现死链则 `print` 具体 `文件:行号: 链接` 并以非零退出。

### 4.2 本地入口 & CI

- `pyproject.toml` 的 `[project.optional-dependencies].dev` 不动（纯标准库 `pathlib`/`re`/`urllib.parse`，**零新依赖**）。
- `ci.yml` 增加 step（在 ruff/pytest 之后或并行）：

```yaml
      - name: Doc link check
        run: python tools/check_doc_links.py
```

- 同时保留为可本地运行：`python tools/check_doc_links.py`，开发者手改文档后自检。

### 4.3 校验范围（v1）

- 仅本地相对/绝对仓库内链接；外部 URL 默认跳过（避免 CI 网络依赖与误报）。
- 白名单：`docs/`、`README.md`、`qi/**/README.md`。
- 排除：`docs/specs/archive/**`（见 §5.1）。

## 五、排除口径与坑清单（已定稿，吸收 Cursor ②/④）

### 5.1 强校验排除范围

- **`docs/specs/archive/**`**：全排除。史料故意保留旧路径，进 CI 红无工程价值。
- **`SKIP_FILES`（机制预留）**：当前实际**无需排除任何现行文件**——已核查 `docs/体系重构方案.md` 与全 `docs/` 无残留旧路径引用（重构已清）。机制保留以应对未来「含迁移映射的定稿」。
- `archive/**/INDEX.md`：随 archive 一并排除；若日后要验 INDEX，可单独白名单（v1 不做）。

### 5.2 解析规则（检查器须实现）

1. **仓库根相对 vs 文件相对**
   - 裸前缀 `docs/`、`qi/`、`仓库根文件名`（如 `README.md`、`LICENSE`）→ 相对 **repo root**。
   - `./`、`../` → 相对**当前 .md 所在目录**。
2. **中文路径**：一律 `pathlib.Path`；支持 `%XX` 解码；路径做 **NFC 归一**（mac 偶发 NFD）。以 CI Linux 大小写敏感为准。
3. **链接形态（v1）**：行内 `[text](url)`、可选 title、`![alt](path)`。
   - Backlog：reference-style、`<> ` autolink、HTML `href`、`.html` 设计稿内链。
4. **目标类型**：`.md` / `.yaml` / `.py` / **目录**（如 `layers/`）「存在即过」，不只认 `.md`。
5. **跳过项**：`http(s):`、`mailto:`、纯 `#fragment`。**不在 CI 里 HEAD 外网**。
6. **假阳性防护**：**跳过 fenced code（` ``` `）与行内 code（`` ` ``）**，否则代码块 `(docs/design/...)` 误报。
7. **路径分隔**：只用 `pathlib`，不写死 `\`；ubuntu CI 与 Windows 本地同脚本可跑。

### 5.3 开放问题（留作 backlog，不挡 v1）

- **Q2**：外链在线校验（lychee）— v2 候选。
- **Q3**：`#锚点` 同文件标题校验 — v2 候选（注意 GitHub 中文标题 slug 与本地不一致）。

## 六、与大厂规范对齐点

- Google/Anthropic 内部：文档即代码 + 链接检查 CI 是标准动作。
- 本方案将"人工死链扫描"升级为"CI 门禁"，是距离大厂工程实践最近的一步，且不增技术债（纯 Python、零依赖）。

## 七、施工顺序（已拍板）

1. 定稿本方案（吸收 Cursor 意见，本节）。 ✅
2. 实现 `tools/check_doc_links.py`（CLI + importable `check()`），覆盖 §5.2 全部规则。
3. 实现 `tests/test_doc_links.py`（单测解析规则 + 可选集成测复用 `check()`）。
4. 改 `ci.yml` 增加独立 step：`python tools/check_doc_links.py`；`on` 沿用 push + pull_request。
5. 本地 Windows 与 CI Linux 各跑一遍验证全绿。

---

*定稿 v2（已吸收 Cursor 交叉检验）· 2026-08-02*
