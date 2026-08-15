# L7 explore 真搜索 d-2（内部深读）——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：[任务包](./2026-08-08-L7-explore真搜索-d2内部深读-任务包.md)、[PR 方案](./2026-08-08-L7-explore真搜索-d2内部深读-PR方案.md)  
> **对照代码**：`qi/action/explore.py`（`_make_query` / `_fetch_external` L229–256 / drift 外部分支 L288–299）、`qi/llm/gateway.py`（`call` 失败返空串、不抛）、`qi/core/brain_delivery.py`（`speak+qi_line`）、`tests/test_explore_external_branch.py`  
> **关联**：d-1 联网地基 + 开口含蓄化收口；d-1 任务包曾预留「d-2 = 沙箱 journal/creations 深读」  
> **时刻**：2026-08-08  

---

## 总判

**路 A——无阻塞。**  
HITL 四项与 PR 骨架自洽；对照现码可落在 `explore.py` + 测试内，不碰 delivery/layer/brain/settings；降级路径能兜住 gateway「失败返空不抛」。禁码；待 Trae 审查回复明示可编码。

---

## 核对清单（逐项）

### 1. `_digest_hits` 骨架

| 项 | 结论 |
|----|------|
| `purpose="consciousness"` | ✓ 与 HITL② / `_make_query` 同构；gateway 仅 `conversation` 写 `last_outcome`（`gateway.py` L106–108） |
| 隐私红线 | ✓ prompt 含 `_QUERY_PRIVACY_LINE`；另有「不编造」字面 |
| 失败降级 | ✓ `except` → `f"我刚才看了看 {query}。"`；空串 → 同降级 |
| 无 llm | ✓ 首行 `if not self.llm` 降级（单测直调；生产路径 `_should_external` 已要求 llm） |
| hits 截断 | ✓ `hits[:3]` + snippet `[:120]`，成本可控 |

✓ 可编码。

**实现注（非阻塞）**：`LLMGateway.call` **正常失败不抛、返 `""`**（`gateway.py` L175–186）。降级主路径是「空串 or」，`except` 兜意外。单测须同时覆盖 `return_value=""` 与 `side_effect=Exception`。

### 2. `_fetch_external` 成功路径

| 项 | 结论 |
|----|------|
| `summary = await self._digest_hits(query, hits)` | ✓ 替换现 L254–255 的 `query……title` 模板 |
| `found.entries` 仍由 hits 结构化 | ✓ 与现 L247–253 同形，给 d-3 |
| 先 digest 再 return；`hits` 仍为 `SearchHit` 列表 | ✓ 顺序正确 |
| 降级时 `outcome` 仍 `OUTCOME_SUCCESS` | ✓ 对齐 HITL③（搜到了，没消化≠能力失败） |
| 空手 / 空 query | ✓ 不进 `_digest_hits`，现有 `failed_capability` 不变 |

✓

### 3. drift 成功 `qi_line = summary`（收回含蓄化拆）

现 L293–298：成功只念 `found['query']`，空手 `qi_line=summary`。  
PR 改为统一 `qi_line = summary`——因成功时 `summary` 已是 digest（或降级后的只念 query）。  
空手仍 `summary` 诚实句。✓ 与 Spec「开口=留痕」一致；B3 模板开口在本包被有意取代。

### 4. d-1 B3「不二次 LLM」解禁

| 项 | 结论 |
|----|------|
| 本包允许一次转译 LLM | ✓ 任务包/HITL/PR 明文解禁 |
| 仍不二次润色开口 | ✓ digest 一次即 `qi_line`；不另调 |
| 失败不崩 | ✓ 降级回 d-1 只念 query |
| 不改 `brain_delivery` | ✓ 仍走 `speak+qi_line` |

✓ 解禁范围清楚，非偷偷破红线。

### 5. scope

仅 `explore.py`（+ `_digest_hits`）+ 测试；不动 `brain_delivery` / `layer` / `brain` / `settings` / 外部门控。✓

### 6. d-1 不回归预期

门控 / 冷却 / 内部沙箱 / `web=None`→内部——PR 未改 `_should_external` / `_scan_finding`。  
须更新的是成功路径断言（见 N2），不是行为回退。✓

---

## 认可

1. **对症**：相处验证「搜到了但听不到理解」——digest 比继续只念 query 更贴 contemplative。  
2. **降级平滑**：失败=含蓄化 d-1 句式，用户无新失败态。  
3. **溯源留 d-3**：`found.entries` 不动，卡片可后做。  
4. **成本**：每外部探索 +1 次 consciousness；稀有门控下与 HITL④ 一致。

---

## 非阻塞备注（N）

| ID | 说明 |
|----|------|
| **N1 · 命名/路线图** | d-1 任务包曾写死「d-2：内部源深读（读 journal/creations 文件内容）」。**本包正文实为「外部 hits → 栖语气 digest」**，与旧预留不是同一件事。不挡本包编码（HITL 已按推荐拍本 Spec），但建议 Trae 在任务包/PR 文首加一句：**本包 = 外部见闻消化；原沙箱文件深读改号另开（勿再称本包为沙箱深读）**，避免 d-3/后人误读。 |
| **N2 · 测试必改 FakeLLM** | 现 `test_external_when_gates_pass` 假定 `qi_line == 我刚才看了看 {query}` 且 `summary` 含 title「窗边的鸟」。d-2 后：`qi_line == summary == digest`，title 只在 `found.entries`；且一次 drift 会 **两次** `consciousness`（`_make_query` + `_digest_hits`）。编码须用 `side_effect` 区分两句返回，并改断言；隐私红线应对 **digest 那次** messages 再断言一次更稳。 |
| **N3 · prompt 冗余** | system 已写「不引用 user_facts/对话」又拼 `_QUERY_PRIVACY_LINE`——可接受；可择一，非必须。 |
| **N4 · digest 幻觉** | 「不编造」只靠 prompt；相处观察偏长/编造再收紧。PR 风险段已写。 |
| **N5 · 文档回写** | scope 不含 `L7-action.md` / `progress`；验收或另拍回写「成功开口=digest」。 |

---

## 阻塞项

**无（Bx = 0）。**

---

## 下一拍

1. **Trae**：落审查回复；建议吸收 N1 文首澄清 + N2 测试要点后明示可编码。  
2. **Cursor**：按 PR 加 `_digest_hits`、改 `_fetch_external` 成功 summary、drift `qi_line=summary`；更新/新增测试；全量 ≥487。  
3. **维护者**：相处复验——外部开口像「看懂了」而非念 title/只念 query。

---

*Cursor 交叉审查 · 2026-08-08 · 禁码 · 路 A*
