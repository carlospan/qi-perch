# 体系重构 · 最终验收 · Cursor 请求

> **用途**：转交 Cursor 对 `docs/` 体系重构做收口验收，**不要直接修改文件**。
> **撰写**：CodeBuddy（2026-08-02）

---

## 背景

`qi-perch`（栖）的 `docs/` 体系重构已全部完成（步骤 A + B），分四次提交：
- `838e140` 方案定稿 v3（吸收两轮 Cursor 评审）
- `3261417` 步骤 A 搭骨架 + 探针迁移
- `5cd310d` 步骤 A 修正（吸收步骤 A 评审，必改 4 项已清零）
- `ce2b139` 步骤 B 全量迁移 + 收口（42 文件，git 识别为 rename+新增+修改）

定稿方案：`docs/体系重构方案.md`（v3）。

---

## 请验收（仅评审，不动文件）

1. **结构正确性**：最终目录是否严格符合定稿 v3？有无文件放错类、空目录、或应迁未迁？
   - `explanation/ reference/ how-to/ tutorials/ specs/` 五类齐备
   - `specs/stages/stage-0~4.md` + `_invariants.md`；`specs/acceptance.md`；`specs/open-questions.md`；`specs/archive/`、`how-to/ui/assets/` 有 `.gitkeep`
2. **无断链**：全库是否还有指向已删旧路径（`docs/design/`、`docs/dev/`、`docs/layers/`、`docs/learn/`、`docs/thoughts/`、`docs/contract.md`、`docs/栖·意识养成路线图.md`）的死链？含 `.cursor/rules/qi-learn-course.mdc`、`progress.md`、各文件内部“相关文档”节。
3. **无双源**：架构方案 §五 是否已退为摘要+链接（非全文并存）？stage-0~4 是否为阶段判据唯一权威？R1–R5 是否在架构方案 §七 全文、仅在 `_invariants.md` 索引（未复制进 contract）？C1–C5 定义是否只在架构 §一（acceptance 只操作化）？
4. **config 单源**：`reference/config.md` 是否声明以 `qi/config/settings.example.yaml` 为真源、无手抄默认值？日限是否 = 20（非 1/3）？
5. **宪法 v3**：分场景裁决表是否覆盖全部场景且无错指？`open-questions.md` 死链是否已消除？
6. **可接受的小瑕疵**：过程稿（整改 v3 + 两轮评审往来）作为史料保留在 `docs/`，是否同意？还是应归档/删除？

---

## 请不要

- 不要直接 rename / 移动 / 编辑任何文件，也不要 git 提交。
- 输出“验收结论（通过 / 有条件通过 / 不通过）+ 遗留项清单”，由我方决定是否处理。

---

*体系重构 · 最终验收 · Cursor 请求（2026-08-02）*
