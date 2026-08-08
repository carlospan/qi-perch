# L7 curiosity 候选解堵——PR 方案

> 配套：[2026-08-08-L7-curiosity候选解堵.md](file:///d:/qi-perch/docs/specs/tasks/2026-08-08-L7-curiosity候选解堵.md)（任务包）
> 根因：[2026-08-08-L7-share停滞排查.md](file:///d:/qi-perch/docs/specs/tasks/2026-08-08-L7-share停滞排查.md)
> **编码交 Cursor；本方案 Agent 不写 `qi/` 代码。**
>
> <!-- 审查后修订(2026-08-08)：吸收 Cursor 交叉审查 B1/B2（路 B），见 §七。方向 A 维持（审查侧同意；B/C 不 pivot）。 -->

---

## 一、外部可观测行为（Spec）

移除包 10 注入的 `kind="curiosity"` GWS 候选。恢复后：
- `action:share` / `archive` / `tend` / `explore` 能在 GWS 仲裁中胜出（不再被非可执行的 curiosity 候选每拍压住）。
- broadcast_traces：`winner_arb=curiosity, outcome=idle` 不再出现；`outcome=idle` 比例从 ~82% 降回正常分布，`action` 重新出现。
- 独处 / ambient + 有未递出创作 → share 触发 → 谈区「qi_line + ActionCard」。

curiosity motive **不丢**：仍由 `motivation/curiosity.py` 计算 + 写回 `emotion.curiosity`，并驱动 `volition.py` 的 `action:explore` 候选生成（solitary + curiosity≥0.65）。

## 二、精确改动点

### A. `qi/core/trace.py` — 删除 curiosity 候选注入

**位置**：`collect_contenders(...)` 内，约 [L517-L525](file:///d:/qi-perch/qi/core/trace.py#L517-L525)

**现状**：
```python
    # 包 10：curiosity 竞争者仅在无用户消息时入场（respond 恒胜）
    if pending is None and curiosity > 0.0:
        candidates.append(
            Contender(
                kind="curiosity",
                salience=salience(kind="curiosity", curiosity=curiosity),
                reason="learning-progress 好奇驱动",
            )
        )

    return candidates
```

**拟改**：整块删除，`return candidates` 上提。`collect_contenders` 的 `curiosity` 形参保留（`motivation/curiosity.py` 写回 + `volition.py` explore 候选仍用，调用方仍传）。

**意图**：curiosity 不再以独立 contender 入场抢仲裁；只作 motive。

### B. `salience(kind="curiosity", ...)` 函数（[trace.py:152-153](file:///d:/qi-perch/qi/core/trace.py#L152-L153)）

**拟改**：**不动**（保留）。删除后无调用点，但保留以最小化改动面、防误伤其他引用。Cursor 可在审查时确认无其他调用点后选择清理——若清理须确保 `grep` 全仓零引用。**默认保留**（自治倾向：最小改动）。

### C. 文档回写（防 drift · SDD §四）

- [docs/reference/layers/L7-action.md](file:///d:/qi-perch/docs/reference/layers/L7-action.md) 文首演进指向：补「2026-08-08：包 10 curiosity 候选注入回退（空赢仲裁堵死自主行动，已解；见排查包）」。
- [docs/progress.md](file:///d:/qi-perch/docs/progress.md)：补「Gap 2 修复：curiosity 候选回退，L7 自主行动恢复触发」。
- [docs/specs/tasks/2026-08-08-L7-share停滞排查.md](file:///d:/qi-perch/docs/specs/tasks/2026-08-08-L7-share停滞排查.md) 文首：状态补「已修，见解堵包」。

### D. 测试翻改（吸收审查 B1）

**文件**：[tests/test_motivation_curiosity.py:108-150](file:///d:/qi-perch/tests/test_motivation_curiosity.py#L108-L150) `test_collect_contenders_curiosity_gate`

**拟改**：L127 `assert any(c.kind == "curiosity" for c in with_c)` → `assert not any(c.kind == "curiosity" for c in with_c)`（curiosity=0.8 时不再注入）。`without`（curiosity=0.0）与 `pending` 两分支原已断言不注入，保留不变。

**意图**：既有测试断言「应注入」与方向 A 冲突，必红 → 必翻。防回归即靠此断言（吸收 B2：不再新增「arbitrate 选 share」测）。

### E. docstring 微调（采纳审查 N1，可选）

**文件**：[qi/motivation/curiosity.py](file:///d:/qi-perch/qi/motivation/curiosity.py) 模块 docstring「并可作为 GWS 竞争者入场」

**拟改**：补「（contender 入场已回退，2026-08-08，见解堵包）」。方法 `contender()` 不删（最小改动），仅改文案避免后人再接回注入。

### F. 不改的（明确）

- `qi/core/gws.py`（arbitrate / _FAMILY_RANK / _EXECUTABLE_FAMILIES 不变）
- `qi/core/brain.py`（dispatch 不变；curiosity 不再胜出，无需加分支）
- `qi/action/volition.py`（action:explore 候选生成不变）
- `qi/motivation/curiosity.py`（curiosity motive 计算 + 写回不变；**仅 docstring 微调见 E**）
- `qi/config/settings.yaml`（gws.enabled 保持 true，autonomous_daily_limit 保持 20）

## 三、纪律红线对照

| 红线 | 对照 |
|------|------|
| R1 双轨 | 不涉（纯工程，无相处记录口径） |
| R2 不用 prompt 写人格 | 不涉（不改 prompt / 人设） |
| R3/R4/R5 | 不涉 |
| 不引入 Agent 框架 | ✓ 只删候选注入，不加决策系统；符 L7 原则 #1 |
| LLM 走 gateway | 不涉（不改 LLM 路径） |
| DB 走 database | 不涉（不改 DB 路径） |
| 不开新阶段 / 不触路线 | ✓ bug fix；explore 真搜索 = C，另开包 |

## 四、测试计划与验收清单

**测试**（吸收审查 B1/B2）：
- 现有 gws / broadcast / trace / motivation_curiosity 测试跑通（基线 473 passed）。
- **B1 翻改**（既有测试，必红 → 必改）：[tests/test_motivation_curiosity.py:108-150](file:///d:/qi-perch/tests/test_motivation_curiosity.py#L108-L150) `test_collect_contenders_curiosity_gate`
  - L127 `assert any(c.kind == "curiosity" for c in with_c)` → 翻为 `assert not any(c.kind == "curiosity" for c in with_c)`（curiosity=0.8 时**不**再注入）。
  - L128-137 `without`（curiosity=0.0）分支：原已断言 `not any`，保留（语义仍成立，可合并或保留）。
  - L139-149 `pending` 分支：原已断言不注入 curiosity，保留不变。
- **B2 删除拟新增的「arbitrate 选 share」测**：与「不改 gws」矛盾（curiosity 0.9 > share 0.30 且族秩更高，arbitrate 会选 curiosity）。**防回归只靠 B1 翻改后的 `collect_contenders` 不含 curiosity 断言**。
- **可选说明性测**（不强制）：手造 `[Contender(kind="curiosity", salience=0.9), Contender(kind="action:share", salience=0.30)]` 喂 `arbitrate`，断言选 curiosity——**说明**「若误注入则 curiosity 仍会赢、故须在 collect 层拦」，**不**要求选 share。
- **N1 采纳（可选微调）**：`qi/motivation/curiosity.py` docstring「可作为 GWS 竞争者入场」一句改为「（ contender 入场已回退，2026-08-08）」——避免后人再接回注入。方法 `contender()` 本身不删（最小改动）。

**验收勾选**（验收面放宽为 trace + 测试 + 文档，吸收审查 N2）：
- [ ] [trace.py:517-525](file:///d:/qi-perch/qi/core/trace.py#L517-L525) 注入块已删
- [ ] `test_collect_contenders_curiosity_gate` 已翻改（断言不含 curiosity）
- [ ] **不**新增「arbitrate 选 share」测；`gws.py / brain.py / volition.py / motivation/curiosity.py` 逻辑未改（docstring 微调除外）
- [ ] `pytest -q` 全量 ≥ 473 passed（零回归）
- [ ] 数据核对：修复后跑一段，broadcast_traces `outcome=idle` 比例下降、`action` 重新出现、`winner_arb=curiosity` 不再出现
- [ ] 文档回写（L7-action.md / progress.md / 排查包文首）
- [ ] 相处层（维护者）：触发 share 验「那句 + 卡片」+ 递出手感（[相处验证收口](file:///d:/qi-perch/docs/specs/tasks/2026-08-08-相处验证收口.md) 批次 0 闭环）

## 五、风险 / 不确定点 / 拍板项

- **风险 1（curiosity 是否有出口）**：删注入后 curiosity motive 仍有出口——`volition.py` `action:explore` 候选（curiosity 驱动）+ `emotion.curiosity` 写回。**无功能丢失**。
- **风险 2（explore 压 share）**：solitary + curiosity≥0.65 时 `action:explore` 候选 salience 可达 ~0.55，胜出会执行沙箱 explore（08-02 曾执行 1 次），可能仍压住 solitary 时的 share。但**非 idle**（有执行）；ambient 时 share 可胜出。可接受。若维护者要 share 更频 → 另开调参包（不并本包）。
- **不确定**：`salience(kind="curiosity")` 函数留否——**默认保留**（最小改动）；Cursor 审查确认零引用后可清理。
- **拍板项**：方向 A 已选（自治采纳推荐）；若维护者要 B / C，**编码前 pivot**（方向变则 PR 重写）。
- **待追认（自治）**：`salience` 函数保留不动；测试文件位置由 Cursor 定。

## 六、明确：编码交 Cursor

本方案 Agent 不写 `qi/` 代码。按 SDD-GUIDE §2.3：

1. **Cursor 读完本 PR 方案 → 落盘交叉审查（`-Cursor交叉审查.md` 或回执首段，禁码）+ 理解确认**。
2. 无阻塞 → 路 A：方案 Agent 落 `-方案审查回复.md`，结论「无需整改，可编码」。
3. 维护者 / 方案 Agent 明示可编码 → Cursor 编码 → 回执补完工段。
4. 方案 Agent 实施验收（`-验收记录.md`）。

若有阻塞 → 路 B（独立审查 → PR 修订 → 整改复审 → 编码请求 → 编码）。

---

## 七、审查后修订（2026-08-08 · 路 B · 吸收阻塞项）

**审查来源**：[2026-08-08-L7-curiosity候选解堵-Cursor交叉审查.md](file:///d:/qi-perch/docs/specs/tasks/2026-08-08-L7-curiosity候选解堵-Cursor交叉审查.md)

**方向**：维持 A（审查侧同意；B/C 不 pivot）。维护者可同时追认 A。

**已吸收阻塞项**：

| 项 | 整改 |
|----|------|
| **B1**（既有测试断言「应注入 curiosity」，PR 未点名） | §二加改动点 D：点名 [test_collect_contenders_curiosity_gate](file:///d:/qi-perch/tests/test_motivation_curiosity.py#L108-L150)，L127 翻为 `assert not any(...)`；§四验收面放宽为 trace + 测试 + 文档（吸收 N2） |
| **B2**（拟新增「arbitrate 选 share」测与「不改 gws」矛盾） | §四删除该拟新增测；防回归只靠 B1 翻改后的 `collect_contenders` 不含 curiosity 断言；可选说明性测（手造 contenders 证 curiosity 仍会赢，不要求选 share） |

**采纳非阻塞**：N1（curiosity.py docstring 微调 → §二 E）、N2（验收面放宽）、N3（测试落点 test_motivation_curiosity.py）、N4（维持 A）。

**未采纳/保留**：`salience(kind="curiosity")` 默认保留（审查认可）；`contender()` 方法不删（最小改动）。

**下一拍（路 B 步骤 3-5）**：
1. Cursor 落盘 `-整改复审.md`，逐条核对 B1/B2 已关闭（未关闭则退回此处，仍禁码）。
2. 方案 Agent 落 `-编码请求.md`（以本修订后 PR 为准的精确改动点）。
3. 维护者 / 方案 Agent 明示可编码 → Cursor 按**编码请求 + 本修订后 PR** 编码 → `-Cursor编码回执.md` 写完工。

**方案 Agent 结论**：B1/B2 已吸收，方向 A 维持。待 Cursor 整改复审确认 B 项关闭后出编码请求。
