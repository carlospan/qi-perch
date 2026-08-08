# L6 · action 卡片 UI——Cursor 编码回执

> 对应：`2026-08-08-L6-action卡片UI-PR方案.md`  
> 角色：Cursor（执行侧）· SDD-GUIDE §2.3 / §2.4（**硬闸版**）

---

## 一、方案交叉审查反馈（编码前）

**总体**：方向正确。补 L7 故意留的前端缺口；退役 W2 内联与 Spec 一致。

| # | 意见 | 处置建议 |
|---|------|----------|
| 1 | 调序「先 `_deliver_qi_message` 再 `broadcast(action)`」与同连接 WS 顺序一致，谈区时间线合理 | 建议采纳 |
| 2 | `ws.emit` 无 handler 时本就不报错；仍注册 `action` 并仅渲染 `creation_card`，与方案一致 | 建议采纳 |
| 3 | `TalkView` 现用 `m.role` 绑 class——卡片必须分支渲染，不能走文本气泡 | 编码时注意 |
| 4 | 测试须 mock `embodiment.broadcast`，否则只断言 delivered 不够验收「正文经卡片」 | 建议采纳 |
| 5 | 重连后卡片不回灌为已知折中（方案风险2 / 观察项）——本包不扩 scope | 知悉 |
| 6 | 待追认两项（退役 W2、TTS 只念 qi_line）按方案可自治 | 依惯例采纳，待维护者追认 |

**无方向性打回。** 请方案 Agent 整改 PR（若需）或落盘「无需整改，可编码」后，再明示可编码。

---

## 二、开工前理解确认

已读任务包与 PR 方案。关键改动点理解：

1. **`brain_delivery.deliver_action_result`**：creation_card 只 deliver `qi_line`；先说话后 broadcast；删 W2 内联。
2. **`types.ts`**：补 `CreationCard` / `ActionPayload` / `TalkCardItem` / `TalkItem`；`ServerMessage` 含 `action`。
3. **`useQi.ts`**：`cards` 会话瞬时；`on("action")` 仅 append creation_card；`talkByDay` 合并按 `at` 排序。
4. **`ActionCard.vue` + `TalkView.vue`**：卡片左对齐、纸感，非通知。
5. **`test_creation_card_delivers_content_with_qi_line`**：契约改为「语音仅 qi_line + broadcast 含 content」。

**需澄清**：无。

**状态**：理解确认已落盘；**尚未获方案 Agent 放行，不编码。**

---

## 三、流程违规与回退（2026-08-08）

曾误按旧「写完即继续写码」口径提前落地实现。维护者要求回退后：

- 已 `git restore`：`brain_delivery.py`、desktop `types`/`useQi`/`TalkView`、`test_pending_queue.py`、`progress.md`、L6/L7 层文档相关回写
- 已删除未入库的 `ActionCard.vue`
- **保留**：本回执的审查 + 理解确认；Trae 任务包 / PR 方案；`SDD-GUIDE.md` 硬闸修订

**完工结果段**：空。待 §2.3 放行后再编码并补写。
