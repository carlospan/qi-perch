# doc-links file:// 协议跳过——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：`2026-08-08-doc-links-file协议跳过.md`、`...-PR方案.md`  
> **对照代码**：`tools/check_doc_links.py` L8 / L85–97、`tests/test_doc_links.py` L91–103  
> **时刻**：2026-08-08  

---

## 总判

**无阻塞。方向正确、改动面最小，路 A。**

根因成立：L85 协议跳过未含 `file://` → `file:///d:/qi-perch/...` 落到 L97 文件相对解析 → 判死链。加 `"file://"` 后 `startswith` 对 `file:///` 亦命中，返回 `None`，与 http/mailto 同口径；符合模块目标「只查本地相对链」。

---

## 认可

1. **1 行 + 1 测**对症，不改文档约定、不另开解析器——符合本次卫生目标。  
2. **测试落点**：扩 `test_skip_external_and_anchor` parametrize，不另起函数——正确。  
3. **风险 1 已诚实标明**（跳过=不验证存在性）；与 http 对称，可接受；验证型增强另包——同意。  
4. **纪律 / HITL**：纯 tooling，无红线触碰。

---

## 必须整改（阻塞）

无。

---

## 非阻塞（编码时注意）

| # | 意见 | 建议 |
|---|------|------|
| N1 | PR §四写「现有 19 +1 = 20 测」 | 现仓 `pytest --collect-only` 已是 **20**；加一条后应收 **21**。验收以「`test_doc_links` 全绿 + 全量 473」为准，勿卡错数字 |
| N2 | 模块 docstring L8 仍写「跳过 … http(s)/mailto」，未列 `file://` | 同文件顺手补 `file://` 一句即可（仍属 tools 改动，非 `docs/**`）；不加不阻塞 |
| N3 | 节标题 L88「跳过项：http(s)/mailto/纯 #fragment」 | 可选同步加 `file://`；不加不阻塞 |

---

## 开工前理解确认（禁码）

若放行后编码将：

1. `check_doc_links.py` L85 元组加 `"file://"`。  
2. `test_skip_external_and_anchor` parametrize 加 `"[file](file:///d:/qi-perch/docs/x.md)"`（或等价 `file://` 链）。  
3. 不改任何 `docs/**`；不实现 file://→repo 存在性校验。  
4. 自测：`python tools/check_doc_links.py` → OK；`pytest tests/test_doc_links.py -q` 全绿；`pytest -q` → **473 passed**。

**需澄清**：无。

**状态**：交叉审查已落盘；**无阻塞 → 路 A**。请方案 Agent 落 `-方案审查回复.md`「无需整改，可编码」；**获明示可编码前不写码**。
