# L6 · action 卡片 UI——PR 方案

> **协作分工（固定流程，详见 `specs/SDD-GUIDE.md` §2）：本方案由方案 Agent（Trae）出；编码交 Cursor 落地。本方案 Agent 不写 `qi/` 实现代码。** 下文骨架片段为方向性示意（非完整可合并实现），Cursor 按既有代码风格适配，偏离处说明。
> 任务包：[2026-08-08-L6-action卡片UI.md](./2026-08-08-L6-action卡片UI.md)。

---

## 一、外部可观测行为（Spec）

栖 share 递出创作时，桌面端「谈」区可见：栖的说话气泡（qi_line，仅引入句）+ 紧接其下的创作卡片（正文 + 类型标 + 季节）。作品正文不再内联进 qi 语音；TTS 只朗读 qi_line。卡片为会话瞬时可见（不弹窗、不闪烁），重连后 qi_line 仍由 `/history` 回灌，卡片不回灌（创作本体在 L4 creations / actions 未丢）。tend / explore 的 `action` 推送到达不报错、不在谈区渲染。

## 二、精确改动点

### A. 后端：退役 W2 内联 + 调序（栖先说话 → 再广播卡片）

**文件**：[qi/core/brain_delivery.py](../../../qi/core/brain_delivery.py) :: `deliver_action_result`（现 L127–L153）

**拟改意图**：creation_card 时只 deliver `qi_line`（删去 `f"{line}\n\n{content}"` 内联）；改为「先说话、后广播卡片」的顺序，使前端时间线为 [栖那句] → [卡片]。删除原 L140–L143 的 workaround 注释。

**骨架（方向示意，非可合并实现）**：

```python
async def deliver_action_result(brain: Brain, result: dict, now: datetime) -> None:
    """行动结果：creation_card 的 qi_line 先开口（typing→speech），再广播卡片；
    卡片在对话流中紧随栖那句之后出现。tend/explore 向内、默认不说话。"""
    # 1) 栖先开口：creation_card 的 qi_line / tend·explore 的 speak 旗
    if result.get("type") == "creation_card":
        line = (result.get("qi_line") or "").strip()
        if line:
            await brain._deliver_qi_message(line, now, proactive=True)
    elif result.get("speak") and result.get("qi_line"):
        await brain._deliver_qi_message(str(result["qi_line"]), now, proactive=True)

    # 2) 再广播卡片 / 行动结果——前端在栖那句之后渲染
    if brain.embodiment is not None:
        try:
            await brain.embodiment.broadcast({"type": "action", "payload": result})
        except Exception:
            logger.exception("行动结果推送失败")
```

> 注意：`_deliver_qi_message(proactive=True)` 路径不变（现行即如此），本包不改 `proactive` 语义、不碰 ProactiveGate 口径（share 仍只占 ActionBudget，见 L7 原则 §2）。

### B. 前端类型

**文件**：[qi/embodiment/desktop/src/types.ts](../../../qi/embodiment/desktop/src/types.ts)

**拟改意图**：
- 新增 `CreationCard` 类型（字段对齐 [share.py](../../../qi/action/share.py) 返回的卡片 dict）。
- `ServerMessage` 联合新增 `{ type: "action"; payload: ActionPayload }`（当前缺失，故 `action` 无类型）。
- `ActionPayload` 为联合：`CreationCard` 精确；`tend_mark` / `explore_drift` 仅给最小形状（本包不渲染，但类型要诚实反映后端实际下发的三种，避免误标）。
- 新增卡片时间线条目类型 `TalkCardItem`，与 `TalkMessage` 投影合并为 `TalkItem`（见 C）。

**骨架**：

```typescript
export type CreationCard = {
  type: "creation_card";
  creation_id: number;
  creation_type: string;
  content: string;
  emotion_context?: unknown;
  qi_line?: string;
  action_id: number;
  season?: string;
};

// 后端 action 下发三种（见 share.py / tend.py / explore.py）；本包只渲染 creation_card
export type ActionPayload =
  | CreationCard
  | { type: "tend_mark"; occasion: string; summary: string; action_id: number;
      season?: string; speak: boolean; qi_line?: string | null }
  | { type: "explore_drift"; found?: unknown; summary: string; action_id: number;
      season?: string; curiosity: number; sandbox: string };

// ServerMessage 联合追加：
//   | { type: "action"; payload: ActionPayload }

/** 谈区时间线条目（文本投影带 kind:"text"；卡片带 kind:"card"） */
export type TalkCardItem = { id: string; kind: "card"; card: CreationCard; at: number };
export type TalkItem = (TalkMessage & { kind: "text" }) | TalkCardItem;
```

### C. 前端状态 / 接线

**文件**：[qi/embodiment/desktop/src/composables/useQi.ts](../../../qi/embodiment/desktop/src/composables/useQi.ts)

**拟改意图**：
- 新增 `cards = ref<TalkCardItem[]>([])`（会话瞬时，不随 `/history` 回灌）。
- 新增 `appendCard(card: CreationCard)`：按 `creation_id` 去重后 push（`at = Date.now()`）。
- 在 `connect()` 的 handler 注册块新增 `qiWs.on("action", ...)`，仅处理 `creation_card`。
- `talkByDay` computed：把 `talk`（文本，投影 `kind:"text"`）与 `cards`（`kind:"card"`）合并后按 `at` 升序、再按日分组；返回 `TalkDayGroup` 其 `messages: TalkItem[]`。
- 现有 `appendTalk` 去重逻辑不变（cards 不进 `talk`）；`applyHistory` 不变（仅文本）。

**骨架**：

```typescript
const cards = ref<TalkCardItem[]>([]);

function appendCard(card: CreationCard) {
  if (cards.value.some((c) => c.card.creation_id === card.creation_id)) return;
  cards.value.push({ id: uid("card"), kind: "card", card, at: Date.now() });
}

// 在 connect() 的 handler 块追加：
qiWs.on("action", (payload: ActionPayload) => {
  if (payload.type === "creation_card") appendCard(payload);
  // tend_mark / explore_drift：到达不报错、不渲染（向内动作保持安静）
});

const talkByDay = computed<TalkDayGroup[]>(() => {
  const items: TalkItem[] = [
    ...talk.value.map((m) => ({ ...m, kind: "text" as const })),
    ...cards.value,
  ].sort((a, b) => a.at - b.at); // 稳定排序：同 at 时 talk 先（已先于 cards 入列）
  // 既有按日分组逻辑复用（dayKey / dayLabel）
  // ...
});
```

> `TalkDayGroup.messages` 类型由 `TalkMessage[]` 收紧为 `TalkItem[]`；`TalkView` 据此分支渲染。

### D. 前端组件

**新增文件**：`qi/embodiment/desktop/src/components/ActionCard.vue`

**拟改意图**：渲染「栖递来的一张纸」。Props: `card: CreationCard`。结构：类型标（`creation_type` 有意义才显示，如「写」「笔记」）+ 正文（`white-space: pre-wrap`，serif）+ 季节 / 时间淡灰脚注。视觉走左对齐（`margin-right:auto`，与 qi 气泡同侧但形态区分），底色 / 边框用 `--talk-qi-bg` / `--talk-qi-bd`，正文 `--ink`，脚注 `--ink-faint` / `var(--mono)`；可加 `--ember` 角标暗示「她递出的」。人称口径：卡片是栖作品本体（栖写作第一人称），不加「AI 生成 / 系统」字样、不加客服语气。

**修改文件**：[qi/embodiment/desktop/src/components/TalkView.vue](../../../qi/embodiment/desktop/src/components/TalkView.vue)

**拟改意图**：`groups.messages` 现为 `TalkItem[]`；模板 `v-for m in g.messages` 分支：`m.kind === "card"` → `<ActionCard :card="m.card" />`（外裹 `.msg.qi.card` 容器，复用左对齐与 `rise` 进场动画）；否则原文本气泡（`who` / `txt` / `when`）。`ActionCard` 由 TalkView 引入。

### E. 测试更新

**文件**：[tests/test_pending_queue.py](../../../tests/test_pending_queue.py) :: `test_creation_card_delivers_content_with_qi_line`（L168–L197）

**拟改意图**：契约由「正文内联进 qi 语音」改为「qi_line 进语音、正文经 broadcast 推卡片」。
- 有正文分支：`delivered == ["我今天写了个东西……给你。"]`（仅 qi_line，正文不在语音）；补一断言：`embodiment.broadcast` 被调用且 payload 含 `content`（mock `brain.embodiment`）。
- 无正文分支：`delivered == ["写了一点。"]`（不变）。
- docstring 改：W2 现由卡片满足，不再靠内联。

## 三、纪律红线对照

- **R1–R5**：不触；纯前端 UI + 后端语音文本裁剪与调序。
- **contract 人称**：qi_line 为既有文案（[share.py](../../../qi/action/share.py)），栖开口第一人称，符合「引号内例句 = 栖第一人称」；不新增「作为 AI / 帮助建议 / 客服语气」；卡片不打扰（谈区内可见，非弹窗 / 通知）。
- **不引入 Agent 框架**：是。LLM 仍 `chat.completions` 经 gateway；行动经 volition → ActionLayer，非 LLM 调工具（L7 技术拐点不变）。
- **LLM 走 gateway / DB 走 database**：是，本包不涉 LLM / DB 新路径（仅读既有 action payload 与既有 creations 数据）。
- **不触路线 / 阶段**：是（L7 既有接口补全，不开阶段五）。
- **常量 / �值**：本包不涉常量 / 默认值改动，无须文档同步回写（防 drift 不适用）。

## 四、测试计划与验收勾选清单

- 后端：`pytest tests/test_pending_queue.py tests/test_action_l7.py -q` → 全绿；全量 `pytest` 无回归（重点排查依赖 `_deliver_qi_message` 语音文本的断言）。
- 前端：`cd qi/embodiment/desktop && npm run build`；`npx vue-tsc --noEmit`（类型零错）。
- 手动：`qi` + `npm run tauri:dev`（或仅 `tauri:dev`，开发期可自动拉起大脑），触发 share（关系 friend+、有未递出创作、独处拍 solitary/ambient）→ 见 qi_line 气泡 + 卡片。
- 验收勾选清单 = 任务包「验收」栏（7 项）。

## 五、风险、不确定点、拍板项

- **风险1（中）**：`talkByDay` 合并改动的静默回归（去重 / 排序）。缓解：`appendTalk` 去重逻辑不变；`cards` 单独按 `creation_id` 去重；合并仅影响投影，不改 `talk` / `applyHistory`。
- **风险2（低）**：退役 W2 内联后，重连历史只见 qi_line 不见正文 → 用户可能「找不到刚才那张卡片」。缓解：创作本体在 L4 creations / actions 未丢；可后续在忆区或卡片持久化补（**观察项，另立包**）。
- **不确定点**：`creation_type` 字段语义（note / poem / …）未必都有意义 → 卡片类型标兜底省略。
- **待追认（自治）**：① 退役 W2 内联；② TTS 不朗读全文只念 qi_line。
- **需维护者拍板**：无（可自治，SDD-GUIDE §6.1）。若维护者要「栖把作品念出来」，另开包加可选拨放开关（不入本包）。

## 六、分工声明

**编码交 Cursor；本方案 Agent（Trae）不写 `qi/` 代码。** Cursor 落地后自查并回执（含「开工前理解确认 + 完工结果」，见 SDD-GUIDE §2.3/§2.4），方案 Agent 读回执做实施验收。
