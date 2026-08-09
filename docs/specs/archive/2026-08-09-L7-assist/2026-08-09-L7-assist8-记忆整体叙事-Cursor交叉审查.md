# L7 assist-8（记忆整体叙事）——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：`2026-08-09-L7-assist8-记忆整体叙事-任务包.md`、`…-PR方案.md`  
> **对照代码**：`qi/action/assist.py`（`_read_and_digest` L226–252 循环内逐块 `narrative.save`；execute L125 传 `season, now`；`_CONTENT_PREVIEW_LEN=80`）、`tests/test_assist_fulltext.py`（`len(narr.saved)==3` / `==6` 等碎片断言）  
> **审查时刻**：2026-08-09  

---

## 总判

**方向正确，无必须整改项 → 路 A（轻量放行）。**

「读一个文件 = 一个记忆事件」对症 assist-7 最多 6 条碎片；收尾 save 一条「整体感受 + （里面写着：preview）」复用 assist-6 常量作事实锚点；签名去掉未用 `season/now` 干净。不碰 explore / brain / conversation，与隐私小刀包边界清晰。

---

## 理解确认（≠放行）

| # | 改动点 | 理解 |
|---|--------|------|
| 1 | `_read_and_digest` | 循环只收集块 digest → `_merge_digests` → **至多 1 次** `narrative.save`（含 preview）；无 digest 则「我看了看」且不写 narrative |
| 2 | 文案 | `我读了他给我的 {name}。{summary}（里面写着：{preview}）`；`qi_line`/`summary` 返回值仍为 merge 结果（**不含** preview 后缀） |
| 3 | 签名 | 去掉 `season/now`；execute 改为 `_read_and_digest(target_path, content)` |
| 4 | 测试 | long/short/新增 single_event 迁到 1 条 + preview；`not_fulltext` 保留；grep 清碎片断言 |

---

## 认可

1. 根因与 `list_recent_narratives(limit=3)` 碎片问题对齐。  
2. preview 锚点让「写了什么」可回忆，且不新增长度常量。  
3. 开口与记忆分离：speak 仍是诗意/合并 digest，记忆多 80 字事实——合理。  
4. 截断声明若在 `summary` 内，会进入叙事正文再拼 preview——可接受。  
5. 与隐私小刀分工正确：本包管「记得」，小刀管 explore「不背诵」。

---

## 必须整改（阻塞编码）

**无。**

---

## 编码时注意（不阻塞）

### N1. 碎片断言迁移面（须 grep，勿只改 PR 点名用例）

`tests/test_assist_fulltext.py` 至少：

| 用例 | 现状 | 迁后 |
|------|------|------|
| `test_assist_short_file_single_digest` | `len==1` | 补「里面写着」/ preview |
| `test_assist_long_file_chunked` | `len==3` | **`len==1`** + merged + preview |
| `test_assist_oversize_chunks_truncated` | **`len==6`**（PR 用例表未点名） | **`len==1`** |
| `test_assist_huge_file_fails_honest` | `saved==[]` | 不变 |
| `test_assist_narrative_not_fulltext` | 不含全文 | 保留；preview≤80 字仍不算全文 |

全库再搜 `narr.saved` / `file_read` /「我读了他给我的」。

### N2. 与隐私小刀的落地顺序

assist-8 把 preview 写入 narrative 后，explore 内部 digest 更容易「念」文件字——**建议与隐私小刀同批或小刀先于/紧接本包验收**（不阻塞本包放行）。

### N3. `_PRIVACY_LINE` 话术

assist 模块仍写「不外传原文」；本包在 narrative 落 80 字 preview（与 actions `content_preview` 同级「记得」）。编码勿把全文塞进 save。

---

## 观察项

- 截断声明 + preview 双括号体感  
- C 项（digest 转译保真）仍暂缓  

---

## 结论与分轨

| 项 | 结论 |
|----|------|
| 阻塞项 | **无** |
| 分轨 | **路 A** |
| 下一拍 | 方案审查回复放行后编码 |

---

*Cursor · 交叉审查 · 2026-08-09 · 禁码*
