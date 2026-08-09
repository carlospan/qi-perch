# L7 · assist-4 对话拍触发——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：[任务包](./2026-08-09-L7-assist4-对话拍触发-任务包.md)、[PR 方案](./2026-08-09-L7-assist4-对话拍触发-PR方案.md)  
> **对照代码**：`qi/core/brain.py`（`receive_user_message` L1174–1238 / `_execute_confirmed_assist` L1141–1172 / GWS assist 存 pending L997–1012）、`qi/action/layer.py`（`execute_kind`）、`qi/action/assist.py`（`execute` / `_confirm_gate` / `_fail`）、`qi/action/permission.py`（`can_read_user_file`）、`qi/core/brain_delivery.py`（`deliver_action_result`）  
> **时刻**：2026-08-09  
> **HITL**：维护者已追认 **a/a/a**（assist 开口=respond / 不进 pending_queue / 信任门控复用现有逻辑）

---

## 总判

**路 B——1 处阻塞（B1）。**

方向正确，根因属实：对话拍 `pending is not None` → 永不进 GWS idle → `execute_kind("assist")` 不跑；把 parse 提前并在对话拍直调 `confirmed=False`，与 assist 响应式定位一致，且不碰 GWS/assist.py。  
`_execute_assist_on_request` 与 `_execute_confirmed_assist` **签名同构**（仅 `confirmed=False`）——R2 过关。  
但 PR **精确改动点**在 `execute` + `_deliver_action_result` 后**未写入** `pending_assist_confirmation`（GWS 路径 L997–1011 已有），与同 PR 测试 #4、验收「pending 存」、任务包 Spec「看吧→真读」矛盾——修了触发仍接不上 assist-3。禁码；待 PR 补存 pending 后再放行。

---

## 核对清单（用户指定四点）

| # | 项 | 结论 |
|---|-----|------|
| 1 | `receive_user_message`：parse 提前 + `assist_req` 非 None 时直调 execute、不 append pending_queue | ✓ 方向对；须插在 assist-3 控制消息块**之后**（PR 骨架替换 L1210 起，保留 L1185–1208）|
| 2 | `execute_kind` 与 `_execute_confirmed_assist` L1141–1172 同构 | ✓ 位置参 + kwargs 齐全；仅 `confirmed=False` |
| 3 | stranger 时是否已拦 | ✓ **行为**已拦：`can_read_user_file` → `allowed=False` → `assist._fail`「熟一点」（**不是**走 `_confirm_gate`；见 N1）|
| 4 | 不跑 `_heartbeat` | ✓ 情绪/内在生命本拍不更新（PR R1）；另见 N2：用户句落库/`last_interaction` 亦跳过 |

---

## HITL

| # | 追认 | 审查意见 |
|---|------|----------|
| 1 assist 开口=respond | **a** | ✓；`deliver_action_result` 对 `speak`+`qi_line` 会 `_deliver_qi_message`，卡片靠 action broadcast |
| 2 不进 pending_queue | **a** | ✓；避免双开口 |
| 3 信任门控复用 | **a** | ✓ 复用 `assist.execute` 内门控；措辞见 N1 |

---

## 必须整改（阻塞编码）

### B1. 对话拍短路未写入 `pending_assist_confirmation`

**现状（assist-3 已落地，仅 GWS idle）**——`brain.py` L997–1011：

```python
if action_result and action_result.get("type") == "assist_confirm_request" and op and target_path:
    self.pending_assist_confirmation = AssistRequest(op=op, target_path=target_path)
    self.pending_assist_confirmation_at = now
    self.pending_assist_heartbeats = 0
self.last_assist_request = None
```

**PR 精确改动点**（§1–2）：`_execute_assist_on_request` → `_deliver_action_result` → `return qi_line`，**无**上述存 pending。

**后果**：friend+ confirm_gate 开口与 AssistConfirmCard 可出，但 `pending_assist_confirmation` 仍为 None → 用户「看吧」走不上 `_execute_confirmed_assist` → Spec §2 / 任务包验收闭环断。  
PR 自带测试 #4 与验收勾选「pending 存」也会红——方案内部已不一致。

**须写进 PR（推荐，对齐 GWS）**：在 `result` 非空且 `type == "assist_confirm_request"` 时，用 `assist_req.op` / `assist_req.target_path`（或 result 内 path）写入 pending + `at` + `heartbeats=0`；再按需清 `last_assist_request`。stranger / `_fail` 路径**不**存 pending。

加测保持：`test_assist_request_stores_pending_for_confirmation` 必须对 **`receive_user_message` 对话拍路径**断言（勿只测 GWS）。

---

## 知悉 / 编码注意（不阻塞）

### N1. stranger 拦点不是 `_confirm_gate`

任务包 / PR 写「stranger → `_confirm_gate` 拦 → failed_capability」。  
现码：`can_read_user_file` 对非 friend+ 返回 `(False, …)` → `AssistAction.execute` 走 `_fail("这个我得先跟你熟一点再说。")`，**不会**进 `_confirm_gate`。  
HITL3 行为意图正确；建议 PR 改措辞为「复用 `assist.execute` 信任门控（stranger→`_fail`；friend+→`_confirm_gate`）」。

### N2. 不跑 `_heartbeat` 不止情绪

跳过整拍对话处理时，除 PR R1（情绪/内在生命）外，本拍还不：`save_message(user)`、`last_interaction`、关系/感知/记忆、交互入账。与 assist-3「看吧」控制消息一致；若谈区依赖服务端历史，确认前端是否已本地插入用户句。建议 PR 风险段补一句，仍可维持「可接受」。

### N3. 小笔误

PR §1 正文「`_execute_confirmed_assisted`」→ 应为 `_execute_confirmed_assist`。

### N4. `result is None` 静默

`action is None` / `mode==dreaming` / 缺 op·path 时直 `return None`，用户无开口。边缘；编码可打日志，非本包必改。

---

## 纪律

- 范围：仅 `brain.py` + 新测——✓（B1 仍只动 brain，不改 assist.py）  
- 不改 GWS / volition / 前端——✓  
- 不与 share/tend/explore 仲裁——✓  
- R3（本拍无主动候选）——可接受  

---

## 理解确认（≠放行）

编码时将：

1. 在 assist-3 块之后：parse → 若有请求则 `_execute_assist_on_request(confirmed=False)`，**不** append `pending_queue`、**不** `_heartbeat`  
2. **（待 PR 补 B1）** confirm_request 时同构 GWS 存 `pending_assist_confirmation`  
3. 新增 `tests/test_assist_dialog_trigger.py` 四测（含 pending 存于 receive 路径）  
4. 不动 `qi/action/*` / 前端  

---

## 下一拍

Trae：修订 `-PR方案.md` 关闭 **B1**（文首标注审查后修订）→ 落盘 `-方案审查回复.md` 或等价放行件 → 维护者/方案侧明示可编码后，Cursor 再动码。

**本文件不含完工段；禁码。**
