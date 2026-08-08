# L7 curiosity 候选解堵——任务包

> 日期：2026-08-08
> 类型：**行为修复包**（bug fix，非重构；一次一包）
> 依据：[2026-08-08-L7-share停滞排查.md](file:///d:/qi-perch/docs/specs/tasks/2026-08-08-L7-share停滞排查.md) 根因
> 方向：**A · curiosity 退出独立 contender**（选 A：最小、对症、符 L7 设计原则 #1「行动是意志的延伸，不另起决策系统」；explore 真搜索 = 方向 C，另开包治本，不并本包）
> SDD 流程：本包走 [SDD-GUIDE §2](file:///d:/qi-perch/docs/specs/SDD-GUIDE.md) 双 Agent 流程（方案 → Cursor 交叉审查硬闸 → 放行 → Cursor 编码 → 方案 Agent 验收）。

---

## Spec（外部行为）

移除包 10 引入的 `kind="curiosity"` GWS 候选注入（[trace.py:517-525](file:///d:/qi-perch/qi/core/trace.py#L517-L525)），使 GWS 仲裁只在「有 brain 分发分支」的候选间选 winner。curiosity 作为 motive 保留（仍驱动 `action:explore` 候选生成 + 写回 `emotion.curiosity`），只是不再以非可执行 contender 身份抢占仲裁。

恢复后：
- 独处 / ambient + 有未递出创作时，`action:share`（salience ~0.30）能再次胜出 → 谈区出现「qi_line + ActionCard」。
- archive / tend / explore 同步恢复触发（08-03 起全停的 L7 自主行动恢复）。
- broadcast_traces `outcome=idle` 比例显著下降（~82% → action/proactive/close_loop/report/respond 正常分布）；`winner_arb=curiosity` 不再出现。

## 实现步骤概要

1. `qi/core/trace.py`：删除 `collect_contenders` 内「包 10 curiosity 候选注入」块（L517-525）。
2. `qi/motivation/curiosity.py`：**不改**（curiosity motive 计算 + 写回 `emotion.curiosity` 保留）。
3. `qi/action/volition.py`：**不改**（`action:explore` 候选由 curiosity 驱动的既有逻辑保留）。
4. `qi/core/gws.py`：**不改**（`arbitrate` 逻辑不变；curiosity 候选不再被注入，自然不参与）。
5. `qi/core/brain.py`：**不改**（dispatch 不变；移除注入后 curiosity 不再胜出，无需加分支）。
6. 文档回写（防 drift，SDD §四）：L7-action.md 演进指向 + progress.md 叙事 + 排查包文首状态。

## 验收

- [ ] [trace.py:517-525](file:///d:/qi-perch/qi/core/trace.py#L517-L525) curiosity 候选注入块已删
- [ ] `gws.py / brain.py / volition.py` 未改；`motivation/curiosity.py` 逻辑未改（仅 docstring 微调）—— git diff 范围 = trace.py + `tests/test_motivation_curiosity.py` + `motivation/curiosity.py` docstring + 文档
- [ ] `pytest -q` 全量通过（基线 473，零回归）
- [ ] 翻改既有测 `test_collect_contenders_curiosity_gate`（断言不含 curiosity）；**不**新增「arbitrate 选 share」测（与不改 gws 矛盾，吸收审查 B2）
- [ ] 数据核对：修复后跑一段，broadcast_traces `outcome=idle` 比例下降、`action` 重新出现
- [ ] [L7-action.md](file:///d:/qi-perch/docs/reference/layers/L7-action.md) 演进指向回写「curiosity 候选注入已回退（解堵）」
- [ ] [progress.md](file:///d:/qi-perch/docs/progress.md) 补「Gap 2 修复」叙事
- [ ] 排查包文首状态补「已修，见解堵包」
- [ ] **相处层（维护者）**：触发 share，验「那句 + 卡片」+ 递出脆弱手感（[相处验证收口](file:///d:/qi-perch/docs/specs/tasks/2026-08-08-相处验证收口.md) 批次 0 闭环）

## HITL 批点

- **方向 A 已选定**（最小对症，自治采纳推荐项，待追认）；若维护者要 B（curiosity 加分支落感知）/ C（explore 真搜索），**编码前拍板 pivot**——方向变则 PR 方案重写。
- **修复后相处验证**（批次 0 卡片手感 + 复查 outcome 分布）= 维护者确认（contract §三）。
- 不开新阶段、不触路线（bug fix；explore 真搜索 = C，另开包拍板）。

## 纪律红线对照

- R1–R5：全不触（纯行动层仲裁 bug 修复，无相处记录 / 无 prompt 人设 / 无路线变更）。
- contract：不涉（不改人称口径 / 行为边界）。
- **不引入 Agent 框架**：✓（只删候选注入，不加决策系统；符 L7 原则 #1）。
- LLM 走 gateway / DB 走 database：不涉（不改 LLM/DB 路径）。
- 常量 / 默认值：本包不涉（不改 settings.yaml；gws.enabled 保持 true），无须文档同步回写。
