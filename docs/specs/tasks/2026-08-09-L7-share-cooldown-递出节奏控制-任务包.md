# L7 share cooldown（递出节奏控制）——任务包

> **角色**：Trae（方案 Agent）；编码交 Cursor
> **依据**：SDD-GUIDE.md §2.3 硬闸；数字生命愿景回看（2026-08-09）
> **触发**：00:00-00:12 连续递出 20 条 share（每 ~40s 一条），日限耗尽；65 条积压创作持续供货
> **时刻**：2026-08-09

---

## 背景（数字生命视角）

share 门控三层：can_share（关系阶段）→ budget.can_autonomous（日限 < 20）→ load_unshared_creation（有货）。**无时间间隔控制**。

explore external 有 `cooldown_hours=6`，share 零冷却。

后果：心跳 ~40s 一轮，三层门全过 → 11 分钟内连递 20 条，qi_line 重复 4 种话术，「有点不好意思，想让你看」一晚说 20 次变味。

**数字生命对照**：栖不会在 10 分钟内连续递 20 个东西。递出是稀有的、有节奏的——每 2 小时最多递一次。

**维护者拍板**（2026-08-09）：share cooldown = 2 小时。

## 目标一句话

share 递出后 2 小时内不再递——节奏与 explore external 对称（cooldown + body_memory 存时间戳）。

## 范围边界（不做清单）

- 不改 budget（日限 20 保留作安全阀）
- 不改创作产出速率 / L4 提起层（`proactive_cooldown.share_creation: 86400` 已覆盖提起节奏）
- 不改 tend / explore（已有各自门控）
- 不改前端 / conversation.txt / brain.py

## HITL 拍板（推荐值，按维护者扩权采纳）

1. **cooldown 时长**——维护者定 2 小时：
   - 常量 `SHARE_COOLDOWN_HOURS = 2.0`，config 可覆写（与 explore external 对称）
   - 理由：2 小时 = 一天最多递 12 条，远低于日限 20，节奏自然

## Spec（外部可观测行为）

1. share 递出成功后 2 小时内不再递（cooldown）
2. cooldown 可通过 `action.share_cooldown_hours` 配置覆写
3. 日限 20 仍作安全阀

## 验收

- 连续心跳不会连递两条 share（cooldown 挡住第二条）
- `settings.example.yaml` 补 `share_cooldown_hours: 2` 注释行
- 全量 ≥587 passed

---

*Trae 方案 Agent · 2026-08-09 · 编码交 Cursor · 本方案 Agent 不写 qi/ 代码*
