# L7 · assist-5 对话集成修复——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：[任务包](./2026-08-09-L7-assist5-对话集成修复-任务包.md)、[PR 方案](./2026-08-09-L7-assist5-对话集成修复-PR方案.md)  
> **对照代码**：`qi/action/assist.py`、`qi/action/layer.py`（`prompt_extras`）、`qi/action/explore.py`（`insert_action` 先例）、`qi/prompts/conversation.txt`、`qi/core/brain.py`（`receive_user_message`）、`qi/embodiment/server.py`（`_handle_client_message`）、相处实证 msg #1518–#1525  
> **时刻**：2026-08-09  
> **HITL**：三项仍为「待拍 / 倾向 a」——**编码前须维护者追认 a/a/a**（或改口）

---

## 总判

**路 B——3 处阻塞（B1/B2/B3）。**

根因三层判断正确：actions 无 assist（#1519 真读后表仍空）、conversation 无能力语义、pending 消费后口头确认落入 LLM（#1522→#1523/#1525）。留痕 + prompt 硬规则方向对，且与 explore/`{recent_actions}` 既有管线对齐。  
但「口头确认兜底」按 PR 精确改动点**修不了真实 1522 场景**，还会在 `pending is None` 时用过宽 confirm cue **劫持正常对话**；引导句只 `return` 不投递则桌面端可能无开口。禁码；待 PR 修订 + HITL 追认后再放行。

---

## 核对清单

| # | 项 | 结论 |
|---|-----|------|
| 1 | `assist.execute` 成功/`_fail` insert_action；confirm_gate 不写 | ✓ 方向对；须明示 `_fail`→**async** + 调用处 `await`（见 N1）|
| 2 | `conversation.txt` 硬规则防「文件系统/隔着玻璃」 | ✓；位置在「不主动提供帮助建议」后合理 |
| 3 | 留痕 → `prompt_extras`/`recent_actions` 注入 | ✓；`layer.prompt_extras` 不按 kind 过滤，insert 后即可进 prompt |
| 4 | pending 已消费 + 口头确认补执行 | ✗ **B1/B2**；见下 |
| 5 | HITL 倾向 a/a/a | 同意倾向；**仍待追认** |

---

## 必须整改（阻塞编码）

### B1. 用 `last_user_message` 补路径——对不上真实 1522

**实证链**：

1. 用户「读一下 D:\ai\栖.txt」→ assist-4 设 `last_user_message` + confirm_gate（#1518）  
2. 「看吧」真读（#1519）→ pending 清；**不改** `last_user_message`  
3. 用户「啊？你看到了什么」（#1520）→ 正常对话：`last_user_message` **被覆盖**为这句（`brain.py` L1247）  
4. 用户「好你读吧」（#1522）→ PR 兜底：`parse_assist_request(last_user_message)` → **无路径** → 只回引导句  

→ Spec §3「仍补执行真读」在**有夹杂追问**的真实相处中**不会发生**；只能落到 HITL3 的「否则引导」支路，与任务包举的 1522 主目标不符。

**须写进 PR（选一或组合）**：

| 选项 | 做法 |
|------|------|
| **(a) 推荐** | 增加粘性 `last_assist_target: AssistRequest \| None`（或 path）：在存 pending / 成功 digest 时写入；超时或明确换话题时清。兜底 `parse` 失败时用该粘性目标 `execute_kind(..., confirmed=True)` |
| (b) | 兜底同时 `parse(text)` + `parse(last_user_message)` + 粘性目标，按优先级 |
| (c) | 仅引导、不补执行——须改 HITL3/Spec（降级），不推荐 |

测试须覆盖：**pending 已清 → 中间一句非确认追问 → 再「好你读吧」→ 仍真读**（对齐 #1520→#1522）。

### B2. `pending is None` 时对全量 `_is_confirm_cue` 兜底会劫持闲聊

`_CONFIRM_CUES` 含裸「好」「行」「可以」「嗯」，且为**子串**匹配（`brain.py` L1118–1128）。  
PR：

```python
if self._is_confirm_cue(text) and self.pending_assist_confirmation is None:
    ...
    return "嗯？你想让我看什么？"
```

→ 任意时刻用户说「好的，今天天气不错」「可以啊」都会进兜底，**不再走 respond**。与 assist-3「宽确认词仅在 pending 有效时」的设计相反。

**须写进 PR**：

- 兜底**仅当**存在近期 assist 上下文（粘性目标未过期 / 或刚成功 digest 后 N 分钟 / 或 `last_assist_target` 非空）；**无上下文时不得**因 confirm cue 短路；  
- 且/或本兜底改用**窄确认词**（如「看吧」「确认」，不含裸「好」「嗯」）。

### B3. 引导句只 `return`、未 `_deliver_qi_message`——桌面可能无开口

`embodiment/server.py` L316–328：WS 路径**不**把 `receive_user_message` 的返回值当 speech 再推；依赖 brain 内投递。  
拒绝路径有 `await self._deliver_qi_message("好。", ...)`；PR 引导句仅 `return "嗯？…"` → 前端可能只看到 typing 结束、**无栖开口**（或落到空响「……」的旁路，取决于是否把非空 return 当已投递）。

**须写进 PR**：引导句与拒绝同构——先 `_deliver_qi_message`，再 `return`。

---

## 知悉 / 编码注意（不阻塞，PR 宜补一句）

### N1. `_fail` 必须改 async

`insert_action` 为 async；现 `_fail` 为同步。PR 写 `await self.db.insert_action` 却未写明签名改为 `async def _fail` + `return await self._fail(...)`（L58/69/80/88/95）。编码时必改，建议 PR 正文补全以免漏 await。

### N2. Spec §1 措辞

任务包 Spec §1 写 confirm_gate 开口后「actions 表出现 assist 记录」，与 HITL1=a「confirm_gate 不 insert」易读成矛盾。建议改为：confirm 开口后**尚无**行；**真读成功/失败**后才出现记录。

### N3. 成功 summary=digest 进 recent_actions

digest 诗意转译（「我爱栖」→「温柔的心」）仍可能让 LLM/用户困惑——任务包已标 N4 观察项，本包可不修；硬规则 + 留痕是必要但不充分，相处仍可能抖。

### N4. 重复真读

兜底补执行会对同一文件再读一遍——可接受；注意日限/伤疤逻辑 assist 本就不占预算。

---

## HITL（倾向认同，待追认）

| # | 倾向 | 审查 |
|---|------|------|
| 1 留痕范围 | **a** | ✓；confirm 不写、成败都写，对齐 explore |
| 2 prompt 静态硬规则 | **a** | ✓ |
| 3 口头确认补执行 | **a** | ✓ 方向；实现须用粘性目标（B1），不能只靠 `last_user_message` |

---

## 理解确认（≠放行）

修订并放行后，编码理解将是：

1. `assist.execute`：成功与 `_fail(failed_capability)` `insert_action`；`_confirm_gate` 不写；`_fail` async  
2. `conversation.txt` 加一行 assist 语义硬规则  
3. `receive`：在近期 assist 上下文下，confirm cue + pending 空 → 用**粘性路径** `confirmed=True` 补执行并 deliver；否则引导句 **deliver**；无上下文不劫持  
4. 测试：insert 成败/confirm 不写；夹杂追问后口头确认仍真读；无路径引导；prompt 含硬规则  

---

## 下一拍

1. 维护者：**HITL 追认 a/a/a**（或改口）  
2. Trae：修订 `-PR方案.md` 关闭 **B1/B2/B3**（文首审查后修订）→ `-方案审查回复.md`  
3. 明示可编码后，Cursor 再动码  

**本文件不含完工段；禁码。**
