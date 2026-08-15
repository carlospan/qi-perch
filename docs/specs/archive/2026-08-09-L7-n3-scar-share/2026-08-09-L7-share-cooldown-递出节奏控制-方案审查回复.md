# L7 share cooldown（递出节奏控制）——方案审查回复

> **角色**：Trae（方案 Agent）
> **依据**：[Cursor 交叉审查](./2026-08-09-L7-share-cooldown-递出节奏控制-Cursor交叉审查.md)（**路 A，无阻塞**）→ [PR 方案](./2026-08-09-L7-share-cooldown-递出节奏控制-PR方案.md)
> **时刻**：2026-08-09

---

## 总判

**路 A 放行——无需整改，可编码。** 根因判断对（try_share 加 cooldown 同时挡 tick/GWS）；与 explore body_memory 模式对称；layer 补传 config 必要。

## 编码注意点（Cursor 交叉审查提出，必执行）

1. **对齐 explore 的 `logger.debug`**：`_mark_share` 落盘失败用 `logger.debug(..., exc_info=True)`（explore L122 先例），并在 share.py 顶部补 `logger = logging.getLogger("qi.action.share")`
2. **扁平键 `action.share_cooldown_hours`**：`_share_cooldown_ok` 读 `(config or {}).get("action")` 的扁平键（与 explore `_external_cfg` 同构，不嵌套）
3. **旧测勿同刻连递两次**：现有 share 测试若在同一 now 连续 try_share 两次断言第二次成功——会因 cooldown 失败；Cursor grep 核对并隔离时间戳
4. `timedelta` 补 import（PR R1 已标）

## HITL 采纳

- cooldown 2 小时——维护者已定，写入 `SHARE_COOLDOWN_HOURS=2.0` + config 可覆写

---

## 明示可编码

PR 方案按原样落地 + 上述注意点。Cursor 编码后写 `-Cursor编码回执.md` 完工段，交 Trae 实施验收。

---

*Trae 方案 Agent · 2026-08-09 · 路 A 放行 · 本方案 Agent 不写 qi/ 代码*
