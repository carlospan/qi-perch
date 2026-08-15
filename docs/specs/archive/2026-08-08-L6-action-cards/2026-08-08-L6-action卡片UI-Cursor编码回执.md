# L6 · action 卡片 UI——Cursor 编码回执

> 对应：`2026-08-08-L6-action卡片UI-PR方案.md`  
> 角色：Cursor（执行侧）· SDD-GUIDE §2.3 / §2.4（**硬闸版**）  
> 放行：`2026-08-08-L6-action卡片UI-方案审查回复.md`（无需整改，可编码）+ 维护者明示「可以编码」

---

## 一、方案交叉审查反馈（编码前）

**总体**：方向正确。补 L7 故意留的前端缺口；退役 W2 内联与 Spec 一致。

| # | 意见 | 处置建议 |
|---|------|----------|
| 1 | 调序「先 `_deliver_qi_message` 再 `broadcast(action)`」时间线合理 | 建议采纳 |
| 2 | 注册 `action` 仅渲染 `creation_card` | 建议采纳 |
| 3 | `TalkView` 卡片须按 `kind` 分支，不走文本气泡 | 编码时注意 |
| 4 | 测试须 mock `embodiment.broadcast` | 建议采纳 |
| 5 | 重连卡片不回灌为观察项 | 知悉 |
| 6 | 待追认两项可自治 | 依惯例采纳，待维护者追认 |

**无方向性打回。** 方案 Agent 已裁定「无需整改，可编码」。

---

## 二、开工前理解确认

已读任务包、PR 方案与方案审查回复。关键改动点：

1. `brain_delivery.deliver_action_result`：只 deliver qi_line；先说话后 broadcast  
2. `types.ts`：CreationCard / ActionPayload / TalkItem；ServerMessage 含 action  
3. `useQi.ts`：cards 瞬时；on("action") 仅 creation_card；talkByDay 合并排序  
4. ActionCard + TalkView：kind 分支；纸感左对齐  
5. 测试：语音仅 qi_line + broadcast 含 content  

**需澄清**：无。放行后编码。

---

## 三、完工结果

**已落地：**
- `qi/core/brain_delivery.py`：先 qi_line 再 broadcast；退役 W2 内联  
- `types.ts` / `useQi.ts` / `ActionCard.vue` / `TalkView.vue`  
- `tests/test_pending_queue.py` 契约更新  
- `progress.md`、L6/L7 层文档回写  

**偏离方案处（初版）：** 曾写「无实质偏离」——**角标映射一点收回**（见下节）。其余 Spec 行为无偏离。

**自测：**
- [x] `pytest tests/test_pending_queue.py tests/test_action_l7.py -q` → 21 passed
- [x] `npm run build` + `npx vue-tsc --noEmit` → 通过（角标修正后已重跑）

**待方案 Agent 复核角标 + 更新验收记录；** 手动 share 感受项待维护者相处。

---

## 四、角标映射修正（验收后）

1. 初依 Trae `...-角标映射裁定.md`：粗粒度「写」/「笔记」。
2. **维护者拍板（2026-08-08）**：接受 `_infer_type` 偶发不准，改细标——`poem→诗`，`essay→随笔`，`description→画面`，`note→笔记`；未知仍省略。覆盖粗粒度裁定。

**现行 `ActionCard.vue`：**
```ts
note: "笔记", poem: "诗", essay: "随笔", description: "画面"
// 未知 → ""
```

请方案 Agent 知悉并更新验收记录 / 裁定附注。
