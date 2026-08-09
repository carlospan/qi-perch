# L7 · assist-3 跨轮确认——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：[任务包](./2026-08-09-L7-assist3-跨轮确认-任务包.md)、[PR 方案](./2026-08-09-L7-assist3-跨轮确认-PR方案.md)  
> **对照代码**：`qi/core/brain.py`（GWS assist / B3 消费 / `receive_user_message` / `_heartbeat`）、`qi/action/assist.py`（`assist_confirm_request`）、`qi/embodiment/desktop/src/{types.ts,composables/useQi.ts,components/TalkView.vue}`  
> **时刻**：2026-08-09  
> **HITL**：按倾向假定 **a/c/a/a**；**仍待维护者追认**后方可编码  

---

## 总判

**路 B——3 处阻塞（B1/B2/B3）。**

方向对：assist-2 链通但 `confirmed` 恒 False；本包补 pending 状态机 + 确认卡片，才能真读闭环；前端按钮走 `sendMessage('看吧'|'不用')` 复用通道——克制面 OK。  
但三处真问题会让闭环空转或误判：**(1)** 存 pending 时 `last_assist_request` 已被 assist-2 B3 清空；**(2)** 用户确认后**没有强制再跑** `execute_kind(assist)`（「看吧」进 respond、且无 assist 候选）；**(3)** 确认词含裸「看」，会把新的「帮我看 Y」当成对旧 pending 的确认。禁码；待 PR 修订状态机次序与触发后再放行。

---

## 核对清单

### 1. 背景属实

| 项 | 结论 |
|----|------|
| assist-2：`confirmed=False` + B3 清 `last_assist_request`（`brain.py` ~L976–980）| ✓ |
| `assist_confirm_request` 无 `action_id`（`assist.py` `_confirm_gate`）| ✓ |
| `_deliver_action_result` 广播 `speak`+`qi_line` + action payload | ✓ |
| 前端只认 `creation_card` / `explore_drift` | ✓ |
| `TalkCardItem.card` 现为 `CreationCard \| ExploreCard` 包装结构 | ✓（PR 伪代码「TalkCardItem 并集」须改成扩 `card` 联合类型 + `ActionPayload`）|

### 2. HITL 假定

| # | 假定 | 备注 |
|---|------|------|
| 1 确认词宽列表 | **a** | 同意方向；须配 B3（新路径优先）|
| 2 超时取先到 | **c** | PR 只写了 5 分钟；**3 轮心跳须写进 PR**（见 N1，非本轮 Bx）|
| 3 digest 纯文本 | **a** | ✓；`ActionPayload` 可收 `assist_result` 但不渲染卡 |
| 4 按钮「看吧」/「不用」| **a** | ✓ |

### 3. 纪律

一次一包 / 不改 assist·layer·volition·trace / 不占预算——✓（状态机触发次序须修）。

---

## 必须整改（阻塞编码）

### B1. 存 pending 时 `last_assist_request` 已被清空

**现状（assist-2）**：

```python
action_result = await self.action.execute_kind(..., confirmed=False)
if action_type == "assist":
    self.last_assist_request = None  # B3 消费
if action_result is not None:
    await self._deliver_action_result(...)
```

**PR**：

```python
if action_result.get("type") == "assist_confirm_request":
    self.pending_assist_confirmation = self.last_assist_request  # 此时已是 None
```

→ pending **永远存不上**，口头/按钮确认无对象。

**须写进 PR（选一）**：

| 选项 | 做法 |
|------|------|
| **(a)** | 在 B3 清空**之前**：若 result 为 `assist_confirm_request`，用**当前** `last_assist_request`（或 `AssistRequest(op, result["target_path"])`）写入 `pending_assist_confirmation`，再清 `last_assist_request` |
| (b) | 仅从 `action_result["target_path"]` + `op` 重建 `AssistRequest`，不依赖 `last_assist_request` |

推荐 **(a)** 或 **(b)**，并加测：confirm_gate 后 `pending_assist_confirmation.target_path` 非空。

### B2. 确认后无人再调度 `execute_kind(assist)`

**链路断点**：

1. 用户发「看吧」→ `receive` 设 `_confirmed_assist` → 入队 → `_heartbeat`  
2. `pending is not None` → **走对话 respond**（「看吧」当普通消息）  
3. 「看吧」不含「帮我」→ `looks_like_help_request` False → **无 `action:assist` 候选**  
4. `_confirmed_assist` 空挂，直到某次偶然 GWS 胜出 assist——几乎不会

Spec「确认 → 真读 → digest」**不会发生**。

**须写进 PR（倾向 a）**：

| 选项 | 做法 |
|------|------|
| **(a)** | 确认/拒绝视为**控制消息**：`receive` 检出确认后，**本拍心跳内直接** `execute_kind("assist", confirmed=True, op/path from _confirmed_assist)` 并 deliver；可选跳过或弱化对「看吧」的 LLM respond |
| (b) | 确认后注入高 salience `action:assist` 且保证本拍/下一 idle 必胜——仍与 respond 抢拍，易抖 |

推荐 **(a)**：控制面与对话面分离。拒绝同理：清 pending + 开口「好。」（Spec §3），勿只静默 clear。

测试须覆盖：**说「看吧」后同拍或明确下一调度出现 `outcome=success` digest**（tmp 文件）。

### B3. 确认词裸「看」吞掉新的协助请求

`_CONFIRM_CUES` 含 `"看"` → `"帮我看一下 D:/y.txt".find("看")` 为真。

若仍有 pending(X)，用户改口要看 Y：

- PR：先 `_is_confirm_cue` → 当成确认 X，**不**开 Y  
- 与 Spec「换话题 / 新请求」冲突

**须写进 PR（倾向 a）**：

```text
if pending is not None:
  if parse_assist_request(text) is not None:
      # 新协助请求：清旧 pending，走新解析（勿当确认）
      clear pending; 不设 _confirmed_assist
  elif reject_cue: clear
  elif confirm_cue: set _confirmed_assist
  else: clear  # 换话题
```

并建议确认词匹配改为**整句短确认**（如 strip 后 ∈ 列表，或仅允许「看吧/好/行/确认/可以/嗯/yes/ok」，**去掉单独「看」**）——HITL1=a 的「宽」保留多词，但避免单字「看」；或整句匹配优先。

---

## 非阻塞备注

- **N1** HITL2=c：PR 伪代码仅 5 分钟；须加 `pending_assist_confirmation_beats`（或等价），每心跳 +1，≥3 清；与 300s **取先到**。编码门槛。  
- **N2** 前端类型：扩 `TalkCardItem.card` 与 `ActionPayload` / history `cards`；`cardKey` 入参是 **card** 不是 TalkCardItem；`appendCard` 须带 `id`/`at`（对照现 `CreationCard` 路径）。  
- **N3** `assist_confirm_request` 无 `action_id`：去重用 `target_path`；**/history 服务端回灌无此卡**（未 insert_action）——会话内 WS 即可，勿假称 DB 回灌；或本包声明「确认卡不入 history」。  
- **N4** 任务包链 `[assist-2 验收记录]` 文件不存在（会挂 `test_doc_links`）→ 改链编码回执/验收实文件。  
- **N5** 测文件名任务包写 `test_assort_confirmation.py` → 应为 `test_assist_confirmation.py`。  
- **N6** 拒绝开口「好。」须有 deliver 路径（B2 同批写清）。  
- **N7** 「不用看」含「看」：若 confirm 先于 reject 会误确认——**reject 优先于 confirm**。  
- **N8** 全量 ≥546 + `vue-tsc` + `npm run build`。

---

## HITL 对照（审查假定 → 请追认）

| # | 项 | 审查假定 | 备注 |
|---|----|----------|------|
| 1 | 确认词 | **a**（宽）| 须配 B3；建议去掉单字「看」或整句匹配 |
| 2 | 超时 | **c**（先到）| PR 补 3 轮计数（N1）|
| 3 | digest 纯文本 | **a** | 同意 |
| 4 | 按钮文案 | **a** | 同意 |

另需关闭 **B1/B2/B3** 后才明示可编码。

---

## 阻塞项

| ID | 摘要 | 关闭条件 |
|----|------|----------|
| B1 | pending 存自已清空的 `last_assist_request` | 清空前写入或从 result 重建 |
| B2 | 确认后无 assist 再执行 | 控制消息本拍直调 `execute_kind(confirmed=True)` |
| B3 | 「看」误判新请求为确认 | 新 `parse_assist_request` 优先；reject 优先 confirm |

**Bx = 3。** 禁码。

---

## 下一拍

1. 维护者追认 HITL：**a / c / a / a**（或明示改口）  
2. Trae：方案审查回复——关闭 B1/B2/B3，回写状态机次序 + 3 轮超时  
3. 明示可编码后再交 Cursor 落地  

---

*Cursor 交叉审查 · 2026-08-09 · 路 B · B1/B2/B3 · 禁码 · HITL 待追认 a/c/a/a*
