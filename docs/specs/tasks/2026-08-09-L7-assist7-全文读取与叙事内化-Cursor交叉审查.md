# L7 assist-7（全文读取与叙事内化）——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：`2026-08-09-L7-assist7-全文读取与叙事内化-任务包.md`、`…-PR方案.md`  
> **对照代码**：`qi/action/assist.py`（`_MAX_READ_BYTES` / `_digest_file` / `insert_action`）、`qi/action/layer.py` L79（`AssistAction(db, llm=llm)`，尚未传 narrative）、`qi/memory/narrative.py`（`save` 签名含 `importance`/`tags`）、`qi/action/share.py`（`narrative.save` 先例）、`qi/core/brain.py`（`ActionLayer(..., narrative=self.memory.narrative)`）、`tests/test_action_assist.py`（`test_assist_digest_uses_llm`）  
> **审查时刻**：2026-08-09  

---

## 总判

**路 B——1 处阻塞（短文件「合并」次数自相矛盾）。**

方向正确：去掉 32KB 截断、1MB 诚实失败、分块 digest + 每块 narrative 内化、超块诚实声明、保留 assist-6 `content_preview`、`layer` 注入 narrative——与维护者「数字生命 / narrative 内化 + 分块读」拍板一致；`NarrativeMemory.save` / share 路径可接线；不动 brain 控制流合理。

但 PR 骨架里 `_merge_digests` 在 `len(digests)==1` 时**不调**合并 LLM，与任务包验收、测试计划写的「短文件 = 块 1 次 + 合并 1 次（共 2 次 consciousness）」冲突。不定稿则编码/验收会各写各的。

---

## 理解确认（≠放行）

| # | 改动点 | 理解 |
|---|--------|------|
| 1 | 常量 | 删 `_MAX_READ_BYTES`；加 `_MAX_FILE_BYTES=1MB` / `_DIGEST_CHUNK_LEN=8000` / `_DIGEST_MAX_CHUNKS=6`；保留 `_CONTENT_PREVIEW_LEN` |
| 2 | 构造 / layer | `AssistAction(..., narrative=)`；`layer` L79 改为传入已有 `narrative` |
| 3 | 读取 | `st_size > 1MB` → failed_capability「太大了」；否则 `read_text` **整文件**进内存再按字符分块 |
| 4 | 消化 | `_digest_chunk` ×≤6 → 每成功块 `narrative.save(..., tags=["assist","file_read"])` → `_merge_digests` 开口；截断则附加「只读完了前面一部分」 |
| 5 | 留痕 | `content_preview` / `insert_action` 行为保持 assist-6 |
| 6 | 测试 | 短/多块/超块/1MB/不含全文 + R5 迁移旧 digest 断言 |

---

## 认可

1. **根因对**：读过即忘（无 narrative）+ 32KB/2000 截断，用内化 + 分块对症。  
2. **隐私**：narrative 只存块 digest 文案、不落全文；与 `_PRIVACY_LINE` / HITL4=a 一致。  
3. **诚实边界**：>6 块声明、>1MB `_fail` + 留痕，不假装读完。  
4. **接线面小**：`ActionLayer` 已持有 `narrative`（brain 已注入），只需传给 `AssistAction`；`save(importance=0.65, tags=...)` 签名匹配。  
5. **assist-6 不破坏**：preview 仍取 `content` 前 80 字；`prompt_extras` 不动。  
6. **降级**：块失败跳过、全败「我看了看 {name}。」、合并失败取首块——合理。  
7. **R5 点名** `test_action_assist.py` 等旧断言——必要。

---

## 必须整改（阻塞编码）

### B1. 短文件合并次数：骨架 vs 验收/测试不一致

| 来源 | 短文件（≤1 块）行为 |
|------|---------------------|
| PR `_merge_digests` 骨架 | `len(digests)==1` → **不调**合并 LLM，开口=块 digest |
| 任务包验收 | 「1 次块 digest + **1 次合并**」 |
| PR 测试计划 / R5 | 「短文件 = **2 次**：块+合并」；用例名 `test_assist_short_file_single_merge` |

不定案则：按骨架编码 → 验收勾「1 次合并」失败；按验收编码 → 与已写骨架冲突。

**整改（二选一，须写进修订 PR / 任务包，全文对齐）**：

| 选项 | 做法 | 倾向 |
|------|------|------|
| **(a) 推荐** | **保留骨架短路**：短文件仅 1 次 consciousness；开口=块 digest；无诚实声明。修订验收与测试为「短文件：1 次块 digest；`_merge_digests` 被调用但不发起合并 LLM（或直接断言 `len(calls)==1`）」；改用例名去掉强制 `single_merge` 语义 |
| (b) | **短文件也走合并 LLM**（始终 块+合并，短文件 2 次）。改骨架：去掉 `len(digests)==1` 早退；验收/测试维持 2 次 |

> 推荐 (a)：单块再「合并」无信息增益，白白 +1 次 consciousness；HITL 成本上限是为多块设计的。

---

## 编码时注意（不阻塞；B1 关闭后执行）

### N1. R5 迁移清单（至少）

- `tests/test_action_assist.py`::`test_assist_digest_uses_llm`：短文件在 (a) 下仍可 `calls[0].purpose==consciousness` 且 `qi_line` 为块 digest；若选 (b) 则断言末次为合并、`len(calls)==2`  
- `tests/test_assist_action_rewrite.py` 既有成功/preview 用例：构造时传入 `narrative=`（可用轻量 Fake / 真实 `NarrativeMemory`+vector，对齐 share/explore 测法）  
- 全库搜 `_digest_file` /「两次 consciousness」类锁死旧单次 digest 的断言

### N2. `layer.py` 必改一行

现状 `self.assist = AssistAction(db, llm=llm)`——漏传则生产路径**永不内化**。PR 已写，编码勿漏。

### N3. 1MB 测法

`monkeypatch` `Path.stat` 时保住 `is_file()` / `read_text` 不误伤；或临时文件 + mock 仅 `st_size`。

### N4. 字符块 vs 字节上限

块按 **字符** 切，1MB 按 **字节** `st_size`——与任务包一致；勿混用。

### N5. `_read_and_digest(..., season, now)` 

骨架未使用 `season`/`now`——可留参对齐调用方，或删参；勿误以为要写入 narrative period。

---

## 观察项（不进本包）

- 单次最多 6 条 narrative（importance=0.65）进 weave/梦的相处体感  
- 整文件 `read_text` 进内存（≤1MB）后只消化前 4.8 万字——声明已覆盖  
- 「我读了**他**给我的」称呼与 share 先例一致；非本包议题  
- 块全失败时无截断声明（降级「我看了看」）——极端边角  
- Spec「之后可回忆」依赖检索命中 digest 文案，相处复验（已与 assist-6 并入统一复验）

---

## 结论与分轨

| 项 | 结论 |
|----|------|
| 阻塞项 | **B1**（短文件合并次数） |
| 分轨 | **路 B** |
| 下一拍 | 方案 Agent 修订任务包/PR（选 a 或 b 并对齐验收与测试描述）→ Cursor `-整改复审.md` → `-编码请求.md` → 明示可编码后再动 `qi/` |

---

*Cursor · 交叉审查 · 2026-08-09 · 禁码*
