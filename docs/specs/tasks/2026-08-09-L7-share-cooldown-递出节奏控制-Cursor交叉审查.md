# L7 share cooldown（递出节奏控制）——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：`2026-08-09-L7-share-cooldown-递出节奏控制-任务包.md`、`…-PR方案.md`  
> **对照代码**：`qi/action/share.py`（`try_share` L124–153，无 cooldown）、`qi/action/explore.py`（`_external_cooldown_ok` / `_mark_external` L98–122）、`qi/action/layer.py`（`ShareAction` 构造 L68，未传 `config`）、`qi/config/settings.example.yaml`（`action` L88–105）  
> **实证锚点**：actions #98–#117（2026-08-10T00:00:18–00:11:46，20 条 share，间隔≈36s）；`action_budget.count_today=20`；`creations` 仍有大量 `shared_at IS NULL`  
> **审查时刻**：2026-08-10  

---

## 总判

**方向正确，无必须整改项 → 路 A（轻量放行）。**

根因与活库一致：`try_share` 仅 `can_share` / `budget` / 有货，无时间闸；GWS `execute_kind` 又跳过 tick 随机软门 → ambient 心跳≈36s 连递直至日限 20。在 `try_share` 入口对称 explore external（body_memory 时间戳 + hours 窗口 + config 可覆写）对症；tick 与 GWS 两条路径都走 `try_share`，一处拦全覆盖。日限 20 保留作硬顶正确。HITL 2h 已由维护者拍板，本审查接受（见观察项）。

---

## 理解确认（≠放行）

| # | 改动点 | 理解 |
|---|--------|------|
| 1 | `share.py` 常量 | `SHARE_COOLDOWN_HOURS=2.0`、`SHARE_LAST_KEY="share_last"` |
| 2 | `ShareAction.__init__` | 增关键字参 `config`；`self.config = config or {}`（旧调用 `ShareAction(db, narrative=None)` 仍合法） |
| 3 | `_share_cooldown_ok` / `_mark_share` | 读/写 body_memory；解析 `{"at": iso}`（兼 `timestamp` / 纯字符串）；失败宽容；`timedelta(hours=max(0.0, hours))` |
| 4 | `try_share` | `can_share` → `can_autonomous` → **cooldown** → load → deliver → `budget.record` → **`_mark_share`** |
| 5 | `layer.py` L68 | `ShareAction(..., config=self.config)`，使 `action.share_cooldown_hours` 生效 |
| 6 | `settings.example.yaml` | `action.share_cooldown_hours: 2` 注释行 |
| 7 | 测试 | 窗口内挡 / 窗外放 / config 覆写 / 无记录首递 / `try_share` 连续第二次 None；全量 ≥587 |

---

## 认可

1. **对症**：连递根因是无间隔闸，不是日限数值；cooldown 管节奏、日限管硬顶，职责分开。  
2. **路径覆盖**：生产递出只经 `try_share`（`layer.tick` / `execute_kind`），不经裸 `deliver`——入口加门足够。  
3. **与 explore 对称**：`get_body_memory` → 解析 `at` → `now - last >= hours`；`set_body_memory({"at": iso})`；落盘失败不阻断——与 `_external_cooldown_ok` / `_mark_external` 同构。  
4. **config 传递**：现状 `ShareAction` 无 config、explore 有；PR 补 `layer` 传入，与 explore 构造一致。  
5. **不占预算空转**：cooldown 失败在 `record` 前 return，不烧日限。  
6. **边界干净**：不改 budget / L4 提起 / tend / explore / brain / 前端。  
7. **兼容旧测**：`ShareAction(db, narrative=None)` 无 config 时走默认 2h。

---

## 必须整改（阻塞编码）

**无。**

---

## 编码时注意（不阻塞）

### N1. `_mark_share` 日志

explore `_mark_external` 失败走 `logger.debug(..., exc_info=True)`；PR 草稿是裸 `pass`。建议对齐 debug 日志（需模块 `logger`）；行为仍不阻断。

### N2. config 键位扁平 vs 嵌套

explore 用 `action.explore_external.cooldown_hours`；本包扁平 `action.share_cooldown_hours`。可接受（share 无子段），编码按 PR，勿误写成嵌套。

### N3. 既有单次 `try_share` 测

`test_deliver_excludes_from_unshared_and_traces` 等同刻二次递出会被 cooldown 挡——新测覆盖即可；勿在旧测里同 `now` 连调两次成功路径。

### N4. 本机 `settings.yaml`

example 补键即可；运行时无键时吃代码默认 2.0。若维护者要非 2h，再改本机 yaml。

### N5. `timedelta` import

PR 已点名：`from datetime import datetime, timedelta`。

---

## 观察项（不进本包）

- **2h vs 4h**：交叉侧曾倾向更稀有的 4h；维护者已定 2h（一天理论最多约 12 次）。相处若仍觉密，只调 `share_cooldown_hours`，不必再开结构包。  
- **积压 65+**：cooldown 后清仓变慢——符合「行动稀有」，非本包缺陷。  
- **GWS 跳过 tick 随机软门**：放大器，cooldown 落地后暴冲应停；是否让 GWS 尊重软门另观察。  
- 文件名日期 08-09 vs 事件落在 08-10 凌晨——史料无妨。

---

## 分轨

| 项 | 结论 |
|----|------|
| 分轨 | **路 A** 轻量放行 → 等方案侧编码请求后编码 |
| 阻塞 | 无 |
| 建议默认 | `SHARE_COOLDOWN_HOURS = 2.0`（HITL）；config 可覆写 |

---

*Cursor · 2026-08-10 · share cooldown 交叉审查 · 本轮禁码*
