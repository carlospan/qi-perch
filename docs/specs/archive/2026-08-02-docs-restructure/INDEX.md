# archive/2026-08-02-docs-restructure · 体系重构史料

> 本目录归档 `docs/` 体系重构（Diátaxis 四分类 + SDD）的过程稿，供回溯决策脉络。
> **现行有效文档**：`docs/体系重构方案.md`（定稿 v3）、`docs/README.md`（宪法 v3）、`docs/specs/` 下各规格。
> 归档不删（对齐 OpenSpec / GitHub Spec Kit）。

## 包含

- `体系重构方案-整改v3.md` + 其 Cursor 评审请求/意见 —— 对照架构方案全文审查出的盲区与整改
- `体系重构方案-Cursor评审请求.md` / `体系重构方案-Cursor评审意见.md` —— 主方案 v1/v2 轮次评审
- `步骤A-Cursor评审请求.md` / `步骤A-Cursor评审意见.md` —— 步骤 A 成果评审
- `步骤B-最终验收-Cursor请求.md` / `步骤B-最终验收-Cursor意见.md` —— 最终验收（有条件通过，遗留项已收口）
- `步骤B-最终验收-CodeBuddy回复.md` —— CodeBuddy 收口回执（逐项回应 7 必改 + 3 建议，全清零）
- `步骤B-最终验收-Cursor确认闭环.md` —— Cursor 抽查确认闭环，本轮无需再开验收回合
- `方案-文档链接CI校验.md` —— docs 链接死链 CI 化方案（定稿 v2，吸收 Cursor 交叉检验）
- `方案-文档链接CI校验-Cursor回复.md` —— Cursor 交叉检验回复（拍板 C1 + tools/tests 分工等）
- `方案-文档链接CI校验-CodeBuddy验收请求.md` —— 落地后验收请求（`e6a2260`）
- `方案-文档链接CI校验-Cursor验收意见.md` —— 有条件通过（必改 2 + 建议 2）
- `方案-文档链接CI校验-CodeBuddy终验回执.md` —— 必改/建议清零，请求终验
- `方案-文档链接CI校验-Cursor确认闭环.md` —— Cursor 确认本轮 CI 化正式闭环

## 史料链（时间序）

1. 体系重构方案 v1/v2 → Cursor 评审请求/意见
2. 整改 v3（对照架构全文审查）→ Cursor 评审请求/意见
3. 方案定稿 v3（`docs/体系重构方案.md`，提交 `838e140`）
4. 步骤 A 搭骨架 + 探针迁移（`3261417`）→ Cursor 评审（有条件放行，`5cd310d` 修正）
5. 步骤 B 全量迁移 + 收口（`ce2b139`）
6. 最终验收（`6a8a933` 收口，遗留项清零）→ CodeBuddy 回执 → Cursor 确认闭环
7. 文档链接 CI 化：方案 v2（`方案-文档链接CI校验.md`）→ Cursor 交叉检验 → 落地 `e6a2260` → 验收请求 → Cursor 有条件通过（必改 2+建议 2）→ 修正 `e4bcc5b` → 终验回执 → Cursor 确认闭环

> 体系重构全过程共 5 次提交，于 `6a8a933` 闭环；文档链接 CI 化为独立增量，于 `e4bcc5b` 闭环。
