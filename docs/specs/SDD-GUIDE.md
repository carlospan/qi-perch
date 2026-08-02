# SDD-GUIDE：本仓库怎么写规格 / 防 spec drift

> **定位**：Spec-driven Development 落地的流程约定。承接文档宪法 v2 的同步纪律，升级为 SDD 流程。
> **参考**：ThoughtWorks SDD（2025-12）、GitHub Spec Kit、OpenSpec（归档不删）。

---

## 一、什么时候写 spec

任何**代码变更 / 架构演进 / 阶段施工**前，先在 `specs/tasks/` 落任务包（用 `_template.md`）：
- 外部行为写 Spec，不写实现细节
- 步骤写实现，可勾选
- 验收写可外部验证的勾选清单
- HITL 批点标注哪些需维护者拍板

## 二、spec 与实现分离

- 先 spec → 再实现 → 最后对照验收勾选。
- 任务闭环后**归档 `specs/archive/` 不删**（OpenSpec 规范：规范是长期资产）。
- 不要用改名假装“阶段退出规格”：`specs/tasks/` = 进行中；`specs/stages/` = 退出判据权威（常青）。

## 三、阶段判据单一权威

- 退出判据以 `specs/stages/stage-*.md` 为唯一施工源。
- `explanation/栖·数字生命架构方案.md` §五 退为**摘要 + 链接**，不双源。
- C1–C5 定义全文留架构方案 §一；本仓库 `specs/acceptance.md` 只做**操作化 + 映射表**，链回 §一，不重写定义。

## 四、防 spec drift（核心纪律）

1. **常量/文件名/默认状态同步**（宪法第四节）：改代码常量、默认值、模块名、启用状态，必须排查 `docs/` 下所有写死同值处回写。
2. **机制文档以代码为准**：`reference/layers/` 与代码出入时回写 layers。
3. **定期审计**：每阶段退出复核，跑“文档 vs 代码”一致性扫描（断链/旧值/双源）。
4. **config 单源**：`reference/config.md` 以 `settings.example.yaml` 为真源，禁手抄默认值当第二权威（日限 1/3/20 教训）。

## 五、红线不双源

- R1–R5 全文留 `explanation/架构方案` §七；`specs/stages/_invariants.md` 只索引，不复制进 `reference/contract.md`，反之亦不可。
- 行为越界问 contract；工程纪律问 R 索引。

## 六、HITL 节点

规格评审、阶段退出、路线决策须维护者拍板；过程可自动。
