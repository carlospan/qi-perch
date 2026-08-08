# L7 explore 真搜索 d-3-2（沙箱深读）——Cursor 编码回执

> **角色**：Cursor（编码）  
> **依据**：[方案审查回复](./2026-08-08-L7-explore真搜索-d3-2沙箱深读-方案审查回复.md)（B1 已关，明示可编码）+ 修订后 [PR 方案](./2026-08-08-L7-explore真搜索-d3-2沙箱深读-PR方案.md)  
> **时刻**：2026-08-08  

---

## 落地

| 项 | 状态 |
|----|------|
| `explore.py`：`INTERNAL_SOURCE_LIMIT` / `_clip_entry` / `_digest_internal`（`_QUERY_PRIVACY_LINE`）/ `_read_internal` | ✓ |
| drift 内部分支：`speak=True`、`qi_line=summary`、`source="journal"` | ✓ |
| 删死码：`_scan_finding` / `_scan_sandbox` / `_config_key_names` + 扫描常量 | ✓ |
| 保留 `resolve_sandbox_root` + `result["sandbox"]` | ✓ |
| `useQi.ts`：入卡 `web \|\| journal` 且 `entries.length > 0` | ✓ |
| B1 八处测试迁移（external_branch×5 + action_l7×1 + self_ops×2） | ✓ |
| 新增 `tests/test_explore_internal_digest.py` | ✓ |
| 未碰 brain_delivery / layer / brain / settings / ExploreCard.vue / types.ts | ✓ |

---

## 构建与测试

| 命令 | 结果 |
|------|------|
| `pytest -q` 全量 | **500 passed**（≥492） |
| `npx vue-tsc --noEmit`（desktop） | **通过** |
| `npm run build`（desktop） | **通过**（✓ built） |

---

## 偏离

1. `test_self_ops.py`：`test_explore_reads_sandbox_entries` **改写并重命名**为 `test_explore_reads_journal_narratives`（seed narrative）；`test_explore_empty_sandbox_found_none` → `test_explore_no_narratives_found_none`（fresh db）。与 PR「改写或并入」择一一致。  
2. 内部门径默认 `source` 初值改为 `"journal"`（外部分支仍覆盖为 `"web"`），避免短暂误标 sandbox。

---

## 下一拍

- Trae：实施验收 + C 方案整体收口  
- 维护者：相处复验——走神翻记忆时像「看懂了内在」；观察内部开口是否过频  

---

*Cursor 编码回执 · 2026-08-08 · 500 passed · vue-tsc + build 通过*
