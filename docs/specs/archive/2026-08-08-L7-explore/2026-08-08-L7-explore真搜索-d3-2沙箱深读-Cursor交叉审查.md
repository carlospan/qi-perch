# L7 explore 真搜索 d-3-2（沙箱深读）——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：[任务包](./2026-08-08-L7-explore真搜索-d3-2沙箱深读-任务包.md)、[PR 方案](./2026-08-08-L7-explore真搜索-d3-2沙箱深读-PR方案.md)  
> **对照代码**：`qi/action/explore.py`（`_scan_*` / drift 内部分支）、`qi/storage/database.py`（`list_recent_narratives`）、`qi/embodiment/desktop/src/composables/useQi.ts`（d-3-1 入卡门控）、`tests/test_explore_external_branch.py`、`tests/test_action_l7.py`、`tests/test_self_ops.py`  
> **时刻**：2026-08-08  

---

## 总判

**路 B——1 处阻塞（B1）。**  
HITL（narratives / speak+出卡 / 复用 drift 门控）与 PR 骨架自洽；`list_recent_narratives` 现成可用；删死码范围正确；前端仅扩 `web||journal` 合理。  
但 PR「不回归 `test_explore_external_branch.py` 全过」与**现测断言**矛盾：多处仍假定内部门径 `source=="sandbox"` 且 **无 `speak`**。HITL2=a 落地后这些测必红，而测试计划未列出迁移。禁码；待 PR 补测试迁移清单后放行。

---

## 核对清单

### 1. `_digest_internal` / `_read_internal` 骨架

| 项 | 结论 |
|----|------|
| `list_recent_narratives(limit=INTERNAL_SOURCE_LIMIT)` | ✓ API 存在（`database.py` L679–693；`strength≥0.2` 未归档） |
| consciousness + 失败/无 llm 降级 | ✓ 与 d-2 `_digest_hits` 同构 |
| 无记忆：`found=None`、summary 含「没有」、`OUTCOME_SUCCESS` | ✓ |
| entries 形 `{title, snippet, url}` | ✓ 对齐 ExploreCard；`_clip_entry`≤40 合理 |
| `found.source="journal"` + 顶栏 `source="journal"` | ✓ 前后端一致 |

✓ 可编码（骨架层面）。

### 2. drift 内部分支

```text
else → _read_internal；speak=True；qi_line=summary；source="journal"
```

✓ HITL2=a。外部分支不动。保留 `resolve_sandbox_root` + `result["sandbox"]` 最小化 shape 变更——✓。

### 3. 删死码

`_scan_finding` / `_scan_sandbox` / `_config_key_names` + 相关常量：仅 explore 内部门径使用，无他处引用。✓  
保留 `resolve_sandbox_root` / `Path`：✓。

### 4. 前端门控

d-3-1 现：`source==="web" && entries.length>0`。  
扩 `web \|\| journal` + 保留 entries 非空：✓ 与外部空手 B1 同构（无记忆只开口无卡）。  
ExploreCard.vue / types 实质可不改（无 query/url 时模板已 `v-if`）——✓。

### 5. 纪律

- 不碰 brain_delivery / 外部门控 / `_digest_hits`：✓  
- 内部 speak 为 HITL 授权行为变更：✓ 非偷偷破线  

---

## 必须整改（阻塞编码）

### B1. 现有测试仍锁「内部 silent + source=sandbox」——PR 测试计划漏迁

HITL2=a 后，凡走内部门径的 drift 将变为：`source=="journal"` + `speak=True` + `qi_line`。

现码断言仍要求旧行为（抽样）：

| 文件 | 断言（现状） |
|------|----------------|
| `test_explore_external_branch.py` | 多处 `source == "sandbox"` 且 `"speak" not in result`（curiosity 阈下 / 冷却挡外部 / web=None / 外部概率未过 / `test_internal_success_outcome_unchanged`） |
| `test_action_l7.py::test_explore_never_fabricates_found` | PR 已点名改（删 `qi.db`）✓ |
| **`test_self_ops.py::test_explore_reads_sandbox_entries`** | **整测绑死沙箱列目录**（写 `sandbox_marker.txt` 并断言 entries 含该文件名 + 「架子」文案）——d-3-2 删扫描后**必须改写或删除**，PR 未点名 |
| `test_self_ops.py::test_explore_empty_sandbox_found_none` | 空 sandbox 目录 → found None；d-3-2 后应改为「无 narratives」语义（空库 / 不插记忆），勿再依赖 `action.sandbox` 空目录 |
| PR「不回归」段 | 写 `test_explore_external_branch.py` **全过**——按现测字面**不可能**不改断言 |

**整改（须写进 PR 测试计划）**：

1. 列出须改的 internal 路径用例（上表），统一迁到：  
   - `source == "journal"`  
   - `speak is True` 且 `qi_line == summary`（有/无记忆均可；无记忆 summary 含「没有」）  
2. 外部门控用例断言「未走 web」时用 `source == "journal"`（或 `!= "web"`），**不要**再写 `"sandbox"`。  
3. **点名处理 `test_explore_reads_sandbox_entries`**：改为「插入 narrative → entries 为截断 content / source=journal」，或删除并并入 `test_explore_internal_digest.py`。  
4. `test_explore_empty_sandbox_found_none` → 无记忆库路径（与 `_read_internal` 无源对齐）。

未补此项则编码后全量必红，或编码方擅自改测却无 PR 真源——故阻塞。

---

## 认可

1. **对症**：列文件名 silent → 读 narratives + digest + 可见，接回 d-1 预留的「内部源深读」，与 d-2/d-3-1 对称收口 C 方案。  
2. **源选择 narratives**：DB 现成、最「她自己」；不扩 creations API。  
3. **稀有度复用 drift 门控**：不另造冷却，合理。  
4. **删扫描死码**：避免双内部源并存，干净。  

---

## 非阻塞备注（N）

| ID | 说明 |
|----|------|
| **N1 · 任务包 HITL 文案** | 任务包仍写「HITL（待拍）」，PR 已「已拍」。请改任务包为已拍三项 + 与 PR 对齐，免后人误停。 |
| **N2 · 包名「沙箱深读」** | 实现读的是 narratives，不再扫 sandbox 目录。文首已有命名澄清；可选副题「内部记忆深读」以免与文件沙箱混淆。 |
| **N3 · 隐私常量** | `_digest_internal` 手写「不引用 user_facts…」，未拼 `_QUERY_PRIVACY_LINE`。建议与 d-2 一样引用常量，便于单测断言同串。 |
| **N4 · types 注释** | `ActionPayload.explore_drift.source` 注释仍写 `web\|sandbox`；可改 `web\|journal\|sandbox`（注释级，非必须）。 |
| **N5 · 开口频率** | 内部路径触发远多于外部（无 0.8/冷却/0.05）。PR 风险段已记；相处若嫌吵再加内部冷却——不本包。 |
| **N6 · d-3-1 是否已合入** | 前端门控扩依赖 d-3-1 `useQi`；编码前确认 main/工作树含见闻卡落地。 |

---

## 阻塞项摘要

| ID | 摘要 |
|----|------|
| **B1** | PR 测试计划须明示迁移：internal 路径断言 `sandbox`/无 speak → `journal` + speak；否则与「external_branch 不回归全过」矛盾 |

---

## 下一拍

1. **Trae**：PR 测试计划吸收 B1（+ 建议 N1/N3）→ 审查回复明示可编码。  
2. **Cursor**：B1 关闭后再改 `explore.py` + `useQi.ts` + 测。  
3. **维护者**：相处验「翻自己记得的事」手感；观察内部开口是否过频（N5）。  

---

*Cursor 交叉审查 · 2026-08-08 · 禁码 · 路 B（B1）*
