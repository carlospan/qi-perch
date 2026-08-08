# L7 explore 真搜索 d-1 · 开口含蓄化——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：[任务包](./2026-08-08-L7-explore真搜索-d1-开口含蓄化-任务包.md)、[PR 方案](./2026-08-08-L7-explore真搜索-d1-开口含蓄化-PR方案.md)  
> **对照代码**：`qi/action/explore.py`（`_fetch_external` L229–256、`drift` 外部分支 L288–294、结果组装 L303–328）、`qi/core/brain_delivery.py`（`deliver_action_result` L127–136）、`tests/test_explore_external_branch.py`  
> **时刻**：2026-08-08  

---

## 总判

**路 A——无阻塞。**  
小改对准相处验证暴露的出戏点；改动点、依赖、B3、测试更新均核对通过。禁码；待 Trae 落审查回复明示可编码后，再改 `explore.py` 外部分支 + 成功 case 断言。

---

## 核对清单（逐项）

### 1. 改动点是否仅 drift 外部分支拆 `qi_line`

| 项 | 结论 |
|----|------|
| 现码痛点 | L293 `qi_line = summary` → 成功时开口 = `我刚才看了看 {query}……{title}。`（`_fetch_external` L254–255）——与任务包背景一致 |
| PR 拟改 | 仅替换 L288–294 块内 `qi_line` 赋值：`found is not None` → `f"我刚才看了看 {found['query']}。"`；`else` → `qi_line = summary` |
| `_fetch_external` / `_make_query` / settings / `brain_delivery` | **不动**——与任务包「不做」一致 |
| `insert_action(..., summary)` / `result["summary"]` | 仍写完整 summary——DB 溯源不丢 |

✓ 范围准确，无 scope 蔓延。

### 2. `found['query']` 依赖

`_fetch_external` 成功路径（L247–253）已写：

```python
found = {
    "entries": [...],
    "source": "web",
    "query": query,
}
```

空手 / 空 query → `found=None`，走 PR 的 `else: qi_line = summary`。  
无第二处构造外部 `found` dict。✓ 低风险依赖成立。

### 3. B3 仍守

| 约束 | 核对 |
|------|------|
| 模板化，不二次 LLM | ✓ qi_line 字面模板；不调 gateway |
| 不改 `brain_delivery` | ✓ 仍靠现有 `elif speak and qi_line`（L134–136） |
| 内部不说 | ✓ `else` 沙箱分支不设 `speak`/`qi_line`（现 L295–297 不变） |
| 外部仍 `speak=True` + `qi_line` | ✓ 成功/空手均 `speak = True` |

✓ B3 不破。

### 4. 测试更新是否合理、不回归

| 用例 | 结论 |
|------|------|
| `test_external_when_gates_pass` | 现断言 `"窗边的鸟" in qi_line or "鸟" in summary` **过松**（新语义下 title 不应进 qi_line）。PR 改为：`qi_line == f"我刚才看了看 {query}。"`（FakeLLM 默认 query=`枝上那只鸟在想什么`）且 **summary 仍含 title「窗边的鸟」**——合理、更贴 Spec |
| `test_external_empty_failed_capability_still_speaks` | 空手 `qi_line=summary`，「不假装」断言可不动 ✓ |
| `test_non_force_internal_gate_then_external` | 只断言 `speak`/`source`，不锁 title 文案——无需改 |
| 门控 / 冷却 / web=None / 内部 outcome | 不触及 qi_line 拆分——不回归预期成立 |
| 全量 ≥487 | 编码后验收项，本轮不跑码 |

✓ 测试计划合理。

---

## 认可

1. **对症**：相处里滑雪教程 / emoji 花草医生 / 维基用户页直接念出口——拆 `qi_line ≠ summary` 是最小止血，符合已拍 A。  
2. **溯源不丢**：`actions.summary` + `found.entries` 仍完整，给 d-2 卡片 / 日后整合留后路。  
3. **空手诚实不变**：与 d-1 红线一致。  
4. **精简流程匹配**：一行半逻辑 + 一测，无强制 HITL。

---

## 非阻塞备注（N，不挡编码）

| ID | 说明 |
|----|------|
| N1 | 成功开口仍可能较长（诗意 query 整句念出）——相对「不念 title」已含蓄；若相处仍嫌长，属后续 `_make_query`/长度帽，**不本包**。 |
| N2 | 维护者本机 TEMP（`cooldown_hours:0` / `probability:1` / 代码侧 force·压 share 等）验收本微调前或后须改回稀有门控，否则仍会高频刷「看了看」——Trae 已提醒；编码包可不改 `settings.yaml`（gitignore）。 |
| N3 | 编码时建议成功断言写成显式：`assert "窗边的鸟" not in result["qi_line"]` 且 `assert "窗边的鸟" in result["summary"]`，与 PR 文字等价、防回归更硬。 |

---

## 阻塞项

**无（Bx = 0）。**

---

## 下一拍

1. **Trae**：落审查回复，明示可编码（路 A）。  
2. **Cursor**：按 PR 改 `explore.py` L288–294 + 更新 `test_external_when_gates_pass`；跑相关测 + 全量。  
3. **维护者**：相处复验成功开口「我刚才看了看 {query}。」；TEMP 调试参数改回（`cooldown_hours: 6`、`probability: 0.05`，及代码侧 TEMP）。

---

*Cursor 交叉审查 · 2026-08-08 · 禁码 · 路 A*
