# L7 · assist-1 执行骨架——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：[任务包](./2026-08-09-L7-assist1-执行骨架-任务包.md)、[PR 方案](./2026-08-09-L7-assist1-执行骨架-PR方案.md)  
> **对照代码**：`qi/action/layer.py`（`execute_kind` / `_AWAKE_SELF_OPS` / budget）、`qi/action/permission.py`（`can_read_user_file`）、`qi/action/volition.py`（assist 桩）、`qi/core/trace.py`（collect_contenders 跳过 assist）、`qi/core/brain_delivery.py`、`qi/action/explore.py`（consciousness digest 先例）、`qi/action/budget.py`  
> **时刻**：2026-08-09  
> **HITL**：按倾向假定 **a/a/a/a**；**仍待维护者追认**后方可编码  

---

## 总判

**路 B——2 处阻塞（B1/B2）。**

方向对：permission / volition 桩 / 伤疤接线已就绪；本包建 `AssistAction` + `execute_kind` 分支 + `confirmed` 参 + consciousness 复述，符合第 4 顺位起手与一次一包（触发源 / 前端 UI 另开）。  
但现网 `execute_kind` 入口有两道**对全体 kind 生效**的闸——**awake 只放 self_ops**、**自主预算耗尽则整段 return None**。assist 是对话期响应式帮助，真实调用几乎必在 `mode=awake`，且「不占预算」不等于「不被预算日限挡住」。PR 只加分支、不改这两闸 → **骨架接上后直调/assist-2 接线仍可能静默失败**。禁码；待 PR 为 assist 开旁路后再放行。

---

## 核对清单

### 1. 背景与不动范围

| 项 | 结论 |
|----|------|
| `can_read_user_file`：friend+ → `(True, True)`；伤疤 → `(False, True)`；否则不允许 | ✓ |
| volition assist 桩仅 `looks_like_help_request`；本包不改 | ✓ |
| `collect_contenders` 显式 `if it.kind == "assist": continue` | ✓ 本包不走 GWS 仲裁；直调 `execute_kind`（触发源 assist-2）|
| permission / 前端 / 感知层不动 | ✓ |

### 2. AssistAction 骨架（任务包伪代码）

| 项 | 结论 |
|----|------|
| 确认门：`needs_confirm and not confirmed` → `confirm_required` + speak | ✓ HITL1=a |
| consciousness digest + 无 llm / 失败降级文件名 | ✓ 对齐 explore digest 先例；HITL2=a |
| 32KB 截断 | ✓ HITL3=a |
| 本包不产 `overstepped`（confirm_gate 拦） | ✓ HITL4=a；与 Spec §4「未确认就执行→overstepped」字面冲突——**须回写 Spec 以 HITL4 为准** |
| 伪代码 `if not needs_confirm and not confirmed: pass` | 死分支；删除，免误导 |
| return 带 `outcome` | ✓ 接得上 `_maybe_save_scar`（本包不产伤疤 outcome，骨架仍通）|
| `deliver_action_result`：`speak`+`qi_line` 已开口 | ✓ 无需改 delivery |

### 3. layer 签名与注入

| 项 | 结论 |
|----|------|
| `__init__` 注入 `AssistAction(db, llm=llm)` | ✓ |
| `execute_kind` 加 `op` / `target_path` / `confirmed` | ✓ 最小；默认不影响既有调用 |
| assist 不调 `budget.record` | ✓ |
| 仍走 `_maybe_save_scar`（未来 overstepped 时生效）| ✓ |

### 4. 纪律

响应式 / 不主动 / 不改 volition 桩 / LLM 走 gateway / 一次一包 / 不外传原文（prompt 红线）——✓。

---

## 必须整改（阻塞编码）

### B1. `execute_kind` 的 awake 门把 assist 挡死

**现状**（`layer.py`）：

```python
_AWAKE_SELF_OPS = frozenset({"archive", "journal", "budget_tune"})
...
if mode == "awake":
    if kind not in _AWAKE_SELF_OPS:
        return None
```

用户开口请求帮忙时 brain 多为 **awake**。assist 不在 `_AWAKE_SELF_OPS` → `execute_kind("assist", ..., mode="awake")` **恒 None**。  
PR 测试用 `mode="solitary"`，掩盖此闸。

**须写进 PR（选一，倾向 a）**：

| 选项 | 做法 |
|------|------|
| **(a)** | awake 门例外：`kind == "assist"` 放行（或 `_AWAKE_ALLOWED = _AWAKE_SELF_OPS \| {"assist"}`）|
| (b) | assist 专用入口（另方法）——扩面，不取 |

### B2. `can_autonomous` 总闸把「不占预算」的 assist 一并掐掉

**现状**（`execute_kind` 分支前）：

```python
if not self.budget.can_autonomous(now):
    return None
```

assist **不** `record`，但日限满时仍进不了分支 → 与 Spec「响应式不占 ActionBudget」语义冲突（不占 ≠ 不被日限拦截）。

**须写进 PR（倾向 a）**：`kind == "assist"` 时**跳过** `can_autonomous` 检查（仍受 permission / 确认门）。

---

## 非阻塞备注

- **N1** 伪代码未 `insert_action`：现网 share/tend/explore 均留痕。建议 success / failed_capability（及可选 confirm_required）写 `insert_action("assist", ...)`，便于 `prompt_extras` / 历史；非阻断，建议本包顺手补。  
- **N2** Spec §4「未确认→overstepped」与 HITL4=a 矛盾：审查回复回写 Spec——本包只产 `confirm_required`；overstepped 留调用方误用 / 后续包。  
- **N3** 路径：`resolve()` 无根目录牢笼——接受 R4（friend+ + 只读 + assist-2 再收紧亦可）。建议编码时拒绝非文件（`path.is_file()`），目录/非常规 → `failed_capability`。  
- **N4** GWS / brain 本包不传 `op`/`target_path`——接受 R2；验收靠单测直调。  
- **N5** `outcome="confirm_required"` 不进 `outcome_creates_scar`——✓ 不误建疤。  
- **N6** FakeLLM 签名须兼容 `llm.call(purpose=..., messages=...)`（与 explore 测一致）。  
- **N7** 全量门槛 ≥522 与当前 main 对齐即可。

---

## HITL 对照（审查假定 → 请追认）

| # | 项 | 审查假定 | 备注 |
|---|----|----------|------|
| 1 | 确认门 `confirmed` 参 | **a** | 同意 |
| 2 | consciousness 复述 | **a** | 同意 |
| 3 | 32KB | **a** | 同意 |
| 4 | 本包不产 overstepped | **a** | 同意；须改 Spec §4 字面 |

另需关闭 **B1/B2**（awake 放行 + 跳过 can_autonomous）后才明示可编码。

---

## 阻塞项

| ID | 摘要 | 关闭条件 |
|----|------|----------|
| B1 | awake 门挡 assist | PR 明示 assist 在 awake 可执行 |
| B2 | 自主日限总闸挡 assist | PR 明示 assist 跳过 `can_autonomous` |

**Bx = 2。** 禁码。

---

## 下一拍

1. 维护者追认 HITL：**a / a / a / a**（或明示改口）  
2. Trae：方案审查回复——关闭 B1/B2，回写 Spec §4 + 删死分支；建议采纳 N1/N3  
3. 明示可编码后再交 Cursor 落地  

---

*Cursor 交叉审查 · 2026-08-09 · 路 B · B1/B2 · 禁码 · HITL 待追认 a/a/a/a*
