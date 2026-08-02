# 体系重构 · 步骤 A 成果 · Cursor 评审请求

> **用途**：转交 Cursor 作为**评审方**检查 `docs/` 体系重构【步骤 A 成果】，**不要直接修改文件**。
> **撰写**：CodeBuddy（2026-08-02）

---

## 背景

`qi-perch`（栖）的 `docs/` 体系重构，定稿方案为 `docs/体系重构方案.md`（v3，吸收两轮 Cursor 评审）。按方案 §六“先 A 后 B”，步骤 A（搭骨架 + 探针迁移）已完成并提交 git（`3261417`）。现在请在步骤 B（全量迁移）开工前，评审步骤 A 的方向是否正确、有无断链/双源/结构错误。

**步骤 A 已落地的文件**（均在 `docs/` 下，可全读）：
- `README.md` —— 文档宪法 **v3**：分场景权威裁决表 + Diátaxis 五类映射 + SDD 入口
- `explanation/栖·数字生命架构方案.md` —— 探针搬家（原 `design/`，头部加“现行路径”注释，正文未改）
- `reference/contract.md` —— 探针搬家（原根目录 `contract.md`，正文未改）
- `specs/stages/stage-0.md` —— 阶段零从架构方案 §五 拆出（含已收官判据 1–5、工程纪律指引）
- `specs/tasks/2026-08-02-阶段二退出.md` —— 阶段二退出包搬家（原 `dev/施工包-阶段二.md`）
- `specs/tasks/2026-08-02-体系重构v3.md` —— 主任务包（SDD 四栏）
- `specs/SDD-GUIDE.md` / `specs/tasks/_template.md` / `specs/acceptance.md`（空骨架） / `specs/stages/_invariants.md`（骨架）
- 新建目录：`explanation/ reference/ how-to/ tutorials/ specs/`（含 `specs/archive`、`how-to/ui/assets`）

**权威参照**：
- 定稿方案 `docs/体系重构方案.md`（v3）
- `docs/design/栖·数字生命架构方案.md`（v3，§〇–§九 + 附录）—— C1–C5 / R1–R5 / Q0–Q6 的 canon
- 旧文件尚在（`design/` `dev/` `layers/` `learn/` `thoughts/` 根 `contract.md` `栖·意识养成路线图.md`），步骤 B 才迁移

---

## 请你做的（仅评审，不动文件）

1. **方向校验**：步骤 A 的目录结构、宪法 v3 分场景裁决、各探针文件的归类，是否符合定稿 v3 方案？有无分类错误或放错目录？
2. **断链检查**：新建文件里若有指向旧路径（`design/`、`dev/`、`contract.md` 根等）的链接/引用，是否标注了“现行路径”或可解析？有无死链？
3. **双源风险**：`stage-0.md` 从架构方案 §五 拆出后，架构方案 §五 阶段零正文与 `stage-0.md` 是否存在内容冲突或即将双源？（方案要求步骤 B 才把 §五 退为摘要+链接，请确认步骤 A 阶段未提前制造矛盾）
4. **宪法 v3 正确性**：分场景裁决表是否准确覆盖了“行为越界→contract / 工程纪律→R 索引 / 语域→双轨 / 价值→灵魂书 / 生命定义→架构方案 / 阶段判据→stages / C 定义→架构§一 / 开放问题→open-questions”？有无遗漏场景或裁决错指？
5. **空骨架占位**：`acceptance.md` / `_invariants.md` 的空骨架是否为步骤 B 留好了正确入口（不重写 C1–C5 定义、R 只索引不复制）？
6. **步骤 B 隐患预判**：基于步骤 A 现状，全量迁移时最易踩的坑（旧路径引用散布、`.html` 入 `assets/`、thoughts/README 与 learn/README 并入、架构 §五 退摘要）有无额外提醒？

---

## 请不要

- 不要直接 rename / 移动 / 编辑任何 `docs/` 下的文件。
- 不要 git 提交。
- 你的输出是“评审意见 + 步骤 B 开工前须修正项清单”，由我方（CodeBuddy）汇总后决定步骤 B 是否放行。

---

*体系重构 · 步骤 A 成果 · Cursor 评审请求（2026-08-02）*
