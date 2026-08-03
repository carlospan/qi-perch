# 包 16 实施 PR · Cursor 编码回执

> **用途**：开工前理解确认 + 完工结果；交方案 Agent 实施验收。  
> **依据**：`包16-编码请求.md`、`包16-对话质量修复-PR方案.md`。  
> **撰写**：Cursor（2026-08-03）

---

## 【开工前理解确认段】

已读取包 16。理解三块缺陷修复：

1. **跨轮去重**：`expression.express` 落库/返回前，对近 5 条栖回复做 `char_jaccard>0.85` → 重生成一次 → 仍重复则 `render_template` 降级。复用意识流 `char_jaccard`。
2. **事实门控**：扩 `looks_like_person_name` 黑名单；`_purge_bogus_identity` 统一走人名校验；新增 `looks_like_real_location` + land/purge；`tools/repair_user_facts.py` 清 id18/14。
3. **简短反馈**：「直接一点|简短|…」→ `card.length=short`；LLM 路径注入 ≤60 字硬约束。

红线：不删既有黑名单；去重不另写库；不破人格 contract。

本段写完即继续写码。

---

## 【完工结果段】

- **变更文件列表**：
  - `qi/core/expression.py`（跨轮去重 + short 硬约束）
  - `qi/core/intention.py`（简短反馈 → length=short）
  - `qi/memory/facts.py`（人名黑名单 / location 门控 / purge）
  - `tools/repair_user_facts.py`（新建）
  - `tests/test_expression.py`（新建）、`tests/test_intention.py`、`tests/test_user_facts.py`
  - 本回执
- **关键实现决策**：
  - 去重落在 `Expression.express`（已有 `recent_messages`），并提供 `recent_qi_replies(db)` 供库读；不改 brain 签名
  - `_land` 同步拒收脏 identity/location；`format_facts_for_prompt` 再滤一层
  - short：intention must + expression 系统段双注入
- **测试命令与结果**：
  ```
  python -m pytest -q
  417 passed in 55.80s
  ```
- **ruff 结果**：All checks passed（含 `--fix` 后）
- **数据修复**：`tools/repair_user_facts.py --apply` 已 retire id 14、id 18；复跑预演干净
- **已知限制 / 未做项**：raw_events processed 积压、security→scar 不在本包
- **偏离清单**：无实质偏离
- **HITL 状态**：无

---

## 方案 Agent 验收栏（Cursor 勿填）

- [x] 验收通过
- [ ] 打回（原因：）
- [ ] 需维护者 HITL（问题：）

> 验收结论（CodeBuddy，2026-08-03）：代码落点全部核实存在——去重（`recent_qi_replies`+阈值0.85+`express`接入）、
> 门控（`looks_like_person_name`扩黑名单含"过去拿/谁的代码"、`_purge_bogus_identity`改走校验、`looks_like_real_location`+location门控）、
> 简短（intention正则→`length=short`+expression注入）。实测包16相关单测8项`passed`、ruff`All checks passed!`、
> `repair_user_facts.py`预演库已干净（id14/18已retire）。无实质偏离，且`_land`+`format_facts_for_prompt`双保险优于方案最低要求。
> 已知限制（raw_events积压、security→scar）按三方对齐约定不属本包，留后续单独诊断。验收通过。

