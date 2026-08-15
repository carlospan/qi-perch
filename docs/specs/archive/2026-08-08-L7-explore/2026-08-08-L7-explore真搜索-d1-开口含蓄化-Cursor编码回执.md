# L7 explore 真搜索 d-1 · 开口含蓄化——Cursor 编码回执

> **角色**：Cursor（编码）  
> **依据**：[方案审查回复](./2026-08-08-L7-explore真搜索-d1-开口含蓄化-方案审查回复.md)（路 A，明示可编码）+ [PR 方案](./2026-08-08-L7-explore真搜索-d1-开口含蓄化-PR方案.md)  
> **时刻**：2026-08-08  

---

## 落地

### 审查回复范围内

| 项 | 状态 |
|----|------|
| `qi/action/explore.py` L26 `EXTERNAL_CURIOSITY_MIN = 0.8`（TEMP 收尾） | ✓ |
| `qi/action/explore.py` drift 外部分支拆 `qi_line`：成功 `f"我刚才看了看 {found['query']}。"`；空手 `qi_line = summary` | ✓ |
| `tests/test_explore_external_branch.py` `test_external_when_gates_pass`：`qi_line == f"我刚才看了看 {query}。"` + N3 显式 title 不进 qi_line / 进 summary | ✓ |
| 空手测 `test_external_empty_failed_capability_still_speaks` | 未改 ✓ |
| 未碰 `_fetch_external` / `_make_query` / `brain_delivery` / `settings.yaml` | ✓ |

### 额外 TEMP 收尾（偏离说明见下）

验证期遗留、会导致 L7/stasis 测红，已一并收回（非行为新需求，恢复 d-1 前/设计原值）：

| 文件 | 收回 |
|------|------|
| `qi/action/volition.py` | 取消压 share；explore 阈/pri 恢复 `≥0.65` 与原公式 |
| `qi/action/layer.py` | 去掉 `explore.drift(..., force=True)` |
| `qi/core/rhythm.py` | `AMBIENT_TO_SOLITARY_MINUTES` `1` → `30` |

---

## pytest

| 命令 | 结果 |
|------|------|
| `pytest tests/test_explore_web.py tests/test_explore_external_branch.py tests/test_action_l7.py tests/test_self_ops.py tests/test_stasis_checkpoint.py -q` | **48 passed** |
| `pytest -q` 全量 | **487 passed** |

---

## 偏离

1. **审查回复只点名清理 `EXTERNAL_CURIOSITY_MIN`**；本机验证期另有 volition/layer/rhythm TEMP，全量会红（share 被压、explore pri=1、solitary 1 分钟）。为避免脏 commit / 验收不过，**同次回执内收回上述三处**，恢复设计原值。未改产品 Spec。  
2. **`settings.yaml` 未动**（`.gitignore`，按审查回复交维护者）：相处复验后请改回 `cooldown_hours: 6`、`probability: 0.05`；若仍留有 `solitary_interval: 30` TEMP 亦请改回 `300`。

---

## 下一拍

- Trae：实施验收  
- 维护者：相处复验——成功开口应像「我刚才看了看 {query}。」（不念 title）；并改回本机 `settings.yaml` TEMP  

---

*Cursor 编码回执 · 2026-08-08 · 487 passed*
