# L7 · assist-2 感知层提取——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：[任务包](./2026-08-09-L7-assist2-感知层提取-任务包.md)、[PR 方案](./2026-08-09-L7-assist2-感知层提取-PR方案.md)  
> **对照代码**：`qi/core/trace.py`（`collect_contenders`）、`qi/core/brain.py`（`receive_user_message` / `_heartbeat_gws_idle`）、`qi/action/volition.py`（assist 桩）、`qi/action/layer.py`（assist 分支）、`qi/action/assist.py`  
> **时刻**：2026-08-09  
> **HITL**：按倾向假定 **a/a/a/a**；**仍待维护者追认**后方可编码  

---

## 总判

**路 B——3 处阻塞（B1/B2/B3）。**

方向对：assist-1 骨架已通，缺的是「消息 → 路径/op → 候选 → execute_kind 传参」链；`trace` 现传 `user_message=None`、`brain` 不传 `op/target_path`——任务包诊断属实。  
但现码 **`collect_contenders` 对 assist 显式 `continue` 丢弃**（`trace.py` L446–447）——只改 L433 传消息仍**进不了 GWS**。相对路径正则写法也会把 `note.md` 收成 `.md`。且 `last_user_message` 不清、confirmed 恒 False 时，idle 拍可能**反复 confirm_gate 开口**。禁码；待 PR 补候选放行 + 正则修正 + 一次消费语义后再放行。

---

## 核对清单

### 1. 缺口核实

| 项 | 事实 |
|----|------|
| `trace.py` L433 `user_message=None` | ✓ |
| `collect_contenders` 仅一处调 `action_intentions` | ✓ **R5 关闭**：无第二处（L494 起是 report/uptime，不是 intentions）|
| `for it in intents: if it.kind == "assist": continue`（L446–447）| ✓ **PR 未写**——见 B1 |
| brain `execute_kind` 无 `op`/`target_path`/`confirmed` | ✓ |
| `receive_user_message` 只入队 + heartbeat，不存 last_* | ✓ |
| assist-1：`target_path`/`op` 缺 → layer `result=None`；有路径 + `confirmed=False` → confirm_gate | ✓ |

### 2. 方案面（假定 HITL a/a/a/a）

| 项 | 结论 |
|----|------|
| `parse_assist_request` + op cue 双重门 | ✓ 方向对；正则见 B2 |
| brain 存 `last_user_message` / `last_assist_request` | ✓ |
| execute_kind 传参 + `confirmed=False` | ✓ HITL2 |
| 只 `read_file` / priority 0.85 不改 | ✓ HITL1/4 |
| 任务包 Spec §2「胜出→读文件→digest」 | ✗ 与 HITL2/PR Spec「永走 confirm_gate」矛盾——**须回写 Spec**（以 PR/HITL2 为准）|
| Spec §4「assist.execute 返回 None」 | 不准：`AssistAction.execute` 恒返 dict；缺参时是 **layer** 返 `None` |

### 3. 纪律

一次一包 / 不改 assist·layer·permission / 正则保守 / confirmed 留 assist-3——✓（消费语义须补进本包，否则 confirm 骚扰属行为回归）。

---

## 必须整改（阻塞编码）

### B1. `collect_contenders` 仍丢弃 assist——只改 L433 不够

**现状**：

```python
for it in intents:
    if it.kind == "assist":
        continue  # 桩时代：不进 GWS
    candidates.append(Contender(kind=f"action:{it.kind}", ...))
```

PR 只改 `user_message=...` → intentions 里会出现 assist，但 **仍被 continue 扔掉** → GWS 永远看不到 `action:assist` → execute_kind 传参链空转。

**须写进 PR**：删除（或收窄）该 `continue`，让 `action:assist` 进入候选。  
建议收窄（与 B3 一起）：**仅当** `getattr(brain, "last_assist_request", None) is not None` 时放入 assist（有路径才进 GWS）；无路径的「帮我看看这段」不必空跑 execute_kind。若坚持 Spec「无路径也生成候选」，则至少去掉裸 `continue`，并接受 idle 空跑——仍须配 B3。

测试断言应为 `"action:assist" in kinds`（不是 `"assist"`）。

### B2. 相对路径正则交替优先级错误

PR：

```python
re.compile(r"([\w./-]+\.txt|\.md|\.json|\.csv|\.log|\.py|\.js|\.ts)", re.I)
```

在 Python 中这是 `([\w./-]+\.txt)` **或** `\.md` **或** `\.json`…  
对「看下 note.md」：`search` 常命中末尾的 **`.md`**，`target_path==".md"`，任务包测 `== "note.txt"` 类 case 在 `.md` 上会失败。

**须改为**（例）：

```python
re.compile(r"([\w./-]+\.(?:txt|md|json|csv|log|py|js|ts))", re.I)
```

并用测锁定 `note.md` → `note.md`。

### B3. 缺「一次消费」→ idle 可能反复 confirm_gate

链路（修订后）：`receive` 存 `last_user_message`（长期）→ 每拍 idle `pending is None` 时 `collect_contenders` 再读该消息 → assist priority 0.85 → 易胜出 → `confirmed=False` → **再次开口「说一声我就看」**。

本包虽不真读文件，但会**言语骚扰**，与行动克制冲突。

**须写进 PR（选一，倾向 a）**：

| 选项 | 做法 |
|------|------|
| **(a)** | 本拍 `execute_kind("assist")` 返回后（含 confirm_gate / None），`brain.last_assist_request = None`，且 **清或 consumemark `last_user_message` 对 assist 的效应**（例如 `self._assist_consumed = True`，下条 `receive` 时复位；`collect` 在 consumed 时不放 assist）|
| (b) | `collect` 仅当 `last_assist_request is not None` 放 assist，且执行后清 `last_assist_request`（无路径不进 GWS；回写 Spec §4）|

推荐 **(a) 或 (b)** 写死进 PR；测试补「连续两拍 idle 不二次 confirm」。

---

## 非阻塞备注

- **N1** R5：已核实无第二处 `action_intentions`——PR 风险表可关。  
- **N2** 无 `brain_with_llm` fixture——按 `test_trace` / `test_resource_ledger` 自建 Brain + FailLLM/FakeLLM。  
- **N3** `collect_contenders(..., pending is None)`：有 pending 的对话拍不跑 action 观测——assist 落在后续 idle；接受并写进方案备注。  
- **N4** 验收补一条：`execute_kind` 在 `action_type=="assist"` 时传入的 `op`/`target_path` 与 `last_assist_request` 一致（可 mock layer 断言）。  
- **N5** POSIX 正则可能误咬 URL path——op cue 双重门可接受；相处再收。  
- **N6** 全量门槛 ≥532 对齐当前 main。

---

## HITL 对照（审查假定 → 请追认）

| # | 项 | 审查假定 | 备注 |
|---|----|----------|------|
| 1 | 只 read_file | **a** | 同意 |
| 2 | confirmed 恒 False | **a** | 同意；Spec §2 须改为 confirm_gate |
| 3 | 正则保守 | **a** | 同意；先修 B2 再谈保守 |
| 4 | priority 0.85 | **a** | 同意 |

另需关闭 **B1/B2/B3** 后才明示可编码。

---

## 阻塞项

| ID | 摘要 | 关闭条件 |
|----|------|----------|
| B1 | assist 被 `continue` 丢弃 | PR 放行 `action:assist`（建议有路径才放）|
| B2 | 相对扩展名正则错 | 改为非捕获组扩展名列表 |
| B3 | 无一次消费 → confirm 可能连问 | PR 写消费/consumed 语义 + 测 |

**Bx = 3。** 禁码。

---

## 下一拍

1. 维护者追认 HITL：**a / a / a / a**  
2. Trae：方案审查回复——关闭 B1/B2/B3，回写 Spec §2/§4  
3. 明示可编码后再交 Cursor 落地  

---

*Cursor 交叉审查 · 2026-08-09 · 路 B · B1/B2/B3 · 禁码 · HITL 待追认 a/a/a/a*
