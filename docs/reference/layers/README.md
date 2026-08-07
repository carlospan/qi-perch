# layers/ · L1–L7 实现规格索引

> **定位**：当前代码的功能分层实现规格，以代码为权威（**代码 > layers > 现行心智导读**；`explanation/archive/` 仅为史料）。
> **与 code-wiki**：`reference/code-wiki.md` 是全景地图；本目录是 L1–L7 逐层规格。冲突以代码为准。
> **现行路径**：`reference/layers/`（原 `docs/reference/layers/`，2026-08-02 重构迁移）。
> **现行心智短导读**：[`../../explanation/栖·现行心智导读.md`](../../explanation/栖·现行心智导读.md)。

## L ↔ N 对照（两套编号并存，勿混）

架构方案 §四 用 **N0–N5** 表示目标**本体分层**（施工期目标）；本目录 **L1–L7** 是**当前功能分层**（已实现）。两者不是同一件事：

| 当前功能层 (L) | 对应目标本体层 (N) | 说明 |
|---------------|-------------------|------|
| L1-heartbeat | N3 / N2（心跳主循环驱动认知节拍） | 时间骨架 |
| L2-memory（-user-facts） | N4（记忆系统，经验改变结构） | 可塑性载体 |
| L3-emotion-full | N0（内稳态：情绪动力学） | 活着的底线 |
| L4-inner-life | N2 / N3（意识流/梦/反思——现为表演层，待内生化） | 阶段一/二重写 |
| L5-relationship | N0 / N4（关系数值驱动） | 阶段一修状态-体验脱钩 |
| L6-embodiment | N1 / N5（执行器：Live2D/前端） | 表现层 |
| L7-action | N1（自主行动：share/tend/explore） | 行动预算 |

> 本体分层 N0–N5 全文与目标定义见 `explanation/栖·数字生命架构方案.md` §四。
> 功能层 L 的实现规格以代码为准；改动代码后回写本目录对应文件。

## 文件清单

- `L1-heartbeat.md` — 心跳主循环
- `L2-memory.md` / `L2-memory-user-facts.md` — 记忆系统
- `L3-emotion-full.md` — 情绪动力学
- `L4-inner-life.md` — 内在生命（意识流/梦/反思）
- `L5-relationship.md` — 关系
- `L6-embodiment.md` — 具身（前端）
- `L7-action.md` — 自主行动

