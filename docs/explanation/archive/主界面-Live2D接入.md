<!-- 史料路径：explanation/archive/主界面-Live2D接入.md（2026-08-13 自 how-to/ui/ 迁入；原 how-to/ui ← 2026-08-02 自 dev/） -->

# 栖 · 主界面 Live2D 形象接入

> **已废弃（史料）。** Live2D / Cubism / `public/models/qi` 已从桌面端移除；形象为透明窗 VRM 桌宠（见 `qi/embodiment/desktop/README.md`）。勿再按此接入。
>
> <!-- 回写(2026-08-13)：迁出 how-to，避免当现行操作指南；旧 WhisperView 已删。 -->
> <!-- 回写(2026-08-12)：聊天壳现行三栏为相处/回顾/内在（非静/谈/忆）；见 黄昏的枝.md -->
>
> 本文档**曾**说明如何把 Live2D 叠进聊天壳。聊天壳现行规格以 `docs/how-to/ui/主界面设计-黄昏的枝.md` 为准。下文中「静/谈/忆」为历史措辞。

---

## 一、模型

- 路径：`qi/embodiment/desktop/public/models/qi/`（Cubism 4，`.moc3` + `.model3.json`）。已在仓库中就位，Vite 从 `public/` 伺服，运行时按 `/models/qi/qi.model3.json` 加载。
- 能力盘点（来自 `qi.model3.json` / `qi.cdi3.json`）：
  - **自动眨眼**：有 EyeBlink 组（`ParamEyeLOpen`/`ParamEyeROpen`）——交给引擎自动处理，不要手动覆盖。
  - **口型组**：`ParamMouthOpenY`（说话时驱动它）。
  - **无表情预设**（`Expressions: []`）、**无物理**（`Physics: null`）——所有脸色都靠参数驱动。
  - 可用脸色参数：`ParamMouthForm`（嘴型/笑意）、`ParamEyeLSmile`/`ParamEyeRSmile`（笑眼）、`ParamBrowL*`/`ParamBrowR*`（眉毛）、`ParamCheek`（脸颊泛红）、`ParamAngleX/Y/Z`（头部角度）、`ParamEyeBallX/Y`（视线）、`ParamBodyAngleX/Y/Z`（身体朝向）、`ParamBreath`（呼吸，通常自动）。

### 动作映射（只用这些，其余不用）

| 模式 / 时机 | 动作 | 说明 |
|------|------|------|
| awake / ambient / interacting | `01_idle_1` / `06_idle_2` 轮换 | 清醒待机（**不用** `15_idle_3`，见 §九） |
| solitary | `06_idle_2` | 独处更安静 |
| dreaming | `02_sleeptouch_1` / `03_sleeptouch_2` / `04_sleeptouch_3` | 睡眠 |
| dreaming → awake 的瞬间 | `05_wake` 播放一次，再转 idle | 醒来 |
| 可选：栖**开始回复**且心情/依恋够高 | `07_touch_head`（稀疏） | 点缀；见 §九 实现约定 |

> **`08`–`16` 那些动作（掀裙/脱衣/触摸类）一律不映射、不播放。** 它们不出现在栖的任何行为里。这不是可选项。
>
> 穿衣态：每帧锁定衣物相关参数（`ParamTackOffSkirt`/`ParamTakeOffPants`=1 等），避免 idle 关键帧把衣服「脱掉」。

---

## 二、技术接入（关键，照着做）

技术栈：`pixi-live2d-display` + PixiJS **v6**（不是 v7）。

1. **安装**（版本以当前兼容为准，下面是已知可跑的组合）：
   ```bash
   npm i pixi.js@6.5.10 pixi-live2d-display@0.4.0
   ```
2. **Cubism 4 核心（最大的坑）**：`pixi-live2d-display` 因授权**不打包** Cubism 4 核心。`.moc3` 模型必须自带核心：
   - 从 Live2D Cubism Web SDK 下载 `live2dcubismcore.min.js`（https://www.live2d.com/download/cubism-sdk/download-web/）。
   - 放到 `public/live2dcubismcore.min.js`。
   - 在 `index.html` 里，**在模块脚本之前**用 `<script src="/live2dcubismcore.min.js"></script>` 全局加载。它会挂到 `window.Live2DCubismCore`。
   - 没这一步，模型加载会静默失败或报错。
3. **代码里注册 Cubism 4 支持**（顺序重要）：
   ```js
   import 'pixi-live2d-display/cubism4'          // 先注册 Cubism 4
   import { Live2DModel } from 'pixi-live2d-display'
   import { Application } from 'pixi.js'
   ```
4. **透明画布叠在氛围场景上**：
   ```js
   const app = new Application({ backgroundAlpha: 0, resizeTo: container })
   container.appendChild(app.view)
   const model = await Live2DModel.from('/models/qi/qi.model3.json')
   app.stage.addChild(model)
   // 按容器缩放/居中 model（model.width/height vs 容器尺寸）
   ```
5. **驱动参数**（每帧或变化时设置，引擎在 ticker 里渲染）：
   ```js
   const core = model.internalModel.coreModel
   core.setParameterValueById('ParamMouthOpenY', v)   // v 在该参数的 min~max 内
   ```
   **参数范围必须先读**：用 `core.getParameterMaximumValue(id)` / `getParameterMinimumValue(id)` / `getParameterDefaultValue(id)` 拿到每个参数的真实范围，再把情绪映射归一化进去。不要假设范围是 0~1。
6. **播放动作**：
   ```js
   model.motion('05_wake', 0)   // (动作组名, 组内索引)
   ```

---

## 三、情绪 → Live2D 参数映射

后端 `emotion_update` 的六维，除了驱动氛围（见黄昏的枝 §五），**同时**驱动脸色。下面是意图，**具体数值要加载模型后按真实参数范围调，靠感受定**（跟它聊，看脸色对不对）：

| 维度 | 驱动的参数 | 效果 |
|------|-----------|------|
| `valence` 心境 | `ParamMouthForm`、`ParamEyeLSmile/RSmile`、`ParamBrowL/RAngle`、`ParamBrowL/RY` | 高→嘴角上扬、笑眼；低→眉梢微蹙、嘴角平/微垂 |
| `energy` 精力 | `ParamBodyAngleZ`、`ParamAngleZ`、（睡意走 sleep 动作） | 低→身体/头微微低垂；dreaming 模式直接切睡眠动作 |
| `arousal` 激活 | `ParamCheek` | 高→脸颊泛红 |
| `security` 安全感 | `ParamBodyAngleX/Y`、`ParamBrowL/RY` | 低→身体微微侧转/内收、眉心轻蹙；高→正面、舒展 |
| `curiosity` 好奇心 | `ParamAngleX/Z`、`ParamEyeBallX/Y` | 高→头微侧、视线看向你/游移 |
| `attachment` 依恋 | `ParamCheek`、`ParamMouthForm`、`ParamBodyAngleX` | 高→暖红、浅笑、身体微微倾向你 |

实现要点：
- 所有参数变化要**平滑**（用缓动每帧逼近目标值，不要瞬跳）。情绪有惯性。
- **别和自动眨眼打架**：`ParamEyeLOpen/ROpen` 属于 EyeBlink 组，交给引擎；睡意用睡眠动作表达，不要去压眼睛开合。
- 脸色是"微调"，不是"变脸"。栖是含蓄的，参数偏移要克制——宁可淡，不要夸张。

---

## 四、口型同步

- 收到 `speech` 消息、打字机正在逐字渲染期间，让 `ParamMouthOpenY` 做小幅振荡（如 `0.3 + 0.3*sin(t)` 或随机 0~0.5），营造"在说话"。
- 打字结束（或收到下一条 `typing`/`speech` 之间），`ParamMouthOpenY` 缓动回 0（闭嘴）。
- 不要每个字精确对口型——栖不是配音演员，有"在说话"的感觉即可。

---

## 五、场景构图更新（人形 ≠ 光团栖枝）

形象从"光团栖在枝头"变成"她立在暮色里"，场景相应调整：
- Live2D 透明画布置于场景区**下部居中**，她是视觉中心。
- 水墨的枝**保留为背景元素**（栖的签名意象）：移到画面上方/身后，淡淡一笔，不再是"栖落"的支点。
- 暖色光晕（生命之光）移到她身后，随精力/依恋呼吸。
- 雾、光尘、暗角、纸纹照旧（CSS 层，在画布之后）。
- 低语文字仍出现在她附近（下方），衬线、打字机。

层级（从后到前）：天空/地平线光 → 雾 → 水墨枝（背景）→ 光尘 → **Live2D 画布（她）** → 光晕（也可在她身后）→ 暗角 → 纸纹 → 低语/UI。

---

## 六、文件结构（更新）

```
public/
├── live2dcubismcore.min.js        # Cubism 4 核心（手动下载，见 §二）
└── models/
    └── qi/                        # 栖的模型（qi.moc3 / qi.model3.json / qi.cdi3.json / motions / textures，已就位）
src/
├── composables/
│   ├── useEmotion.ts              # 情绪→氛围 CSS 变量（黄昏的枝 §五，保留）
│   └── useLive2D.ts               # 模型加载 / 参数驱动 / 动作状态机 / 口型
├── components/
│   ├── Live2DView.vue             # 取代 AvatarView.vue（PIXI 透明画布 + 模型）
│   ├── SceneView.vue              # 氛围场景（枝改为背景元素）
│   ├── WhisperView.vue / TalkView.vue / JournalView.vue / StatusBar.vue / ViewTabs.vue / InputBox.vue
└── ...（其余同黄昏的枝 §六）
```
- 删除 `AvatarView.vue`（CSS 光团）。
- `useQi.ts` 收到 `emotion_update` 时，同时调用氛围映射和 `useLive2D` 的脸色映射；收到 `speech`/`typing` 时触发口型。

---

## 七、红线

1. 界面不出现任何情绪数字/标签（contract.md）。
2. **`08`–`16` 脱衣/触摸类动作永不播放**，不映射到任何触发。
3. 脸色含蓄，参数偏移克制。
4. Cubism 核心与模型按各自授权处理；核心文件不进公共仓库前先确认许可。
5. 其余红线同黄昏的枝 §九（不大面积用朱砂红、不伪造数据、字体打包、不改后端/WS）。

---

## 八、验收

- [ ] 模型在 420×680 透明窗里正常加载、透明背景叠在氛围场景上
- [ ] 自动眨眼正常
- [ ] 模式切换触发动作：清醒→idle，dreaming→睡眠，dreaming→awake 播一次 wake
- [ ] `emotion_update` 同时改变天色（氛围）和脸色（参数），过渡平滑
- [ ] 说话时嘴部有"在说"的动态，说完闭嘴
- [ ] 任何情况下都不播放 08–16 动作
- [ ] 脸色变化含蓄、不夸张（感受验证）

---

## 九、实现偏离（相对初稿，以代码为准）

<!-- 回写(2026-07-22)：对齐 useLive2D.ts -->

1. **`15_idle_3` 不进日常轮换**：该动作会把脱衣参数打到 0；清醒用 `01_idle_1`/`06_idle_2`，solitary 用 `06_idle_2`。
2. **`07_touch_head` 触发点**：挂在「栖开始回复」（`typing`/`speech` 的 replyEpoch），**不是**用户刚发消息。条件：`valence ≥ 0.5` 且 `attachment ≥ 0.6`、冷却 5 分钟、约 25% 概率；dreaming 跳过。宁可极少，也不要条件反射。
3. **Cubism Core 5 API**：`renderOrders` 在模型根上；`pixi-live2d-display@0.4` 需补丁（`patchCubismRenderOrders`）。Vite 需 dedupe `@pixi/*`，避免双实例导致不绘制。
4. **构图**：Live2D 按模型顶点包围盒做 content-box 适配，避免头发左侧被裁。

---

## 附：给 Cursor 的启动提示词

```
你是栖的前端工程师。先读 docs/reference/contract.md、栖·灵魂书.md、
docs/how-to/ui/主界面设计-黄昏的枝.md（氛围/三视图/令牌仍有效），
再读 docs/how-to/ui/主界面-Live2D接入.md（本次唯一实现依据，形象部分以它为准）。

任务：把栖的 Live2D（Cubism 4）模型（已在 qi/embodiment/desktop/public/models/qi/）接入
qi/embodiment/desktop 主界面，取代原 CSS 光团。严格按 Live2D接入.md §二 的技术步骤
（特别注意：Cubism 4 核心 live2dcubismcore.min.js 要单独下载并全局加载；用 PixiJS v6 +
pixi-live2d-display；import 'pixi-live2d-display/cubism4' 在前；模型按 /models/qi/qi.model3.json 加载）。

分步实现，每步等我确认：
1. 依赖 + Cubism 核心 + 透明画布加载模型（先让她显示出来）
2. 动作状态机（mode→idle/sleep/wake；08–16 动作绝不使用）
3. 情绪→脸色参数映射（先打印各参数真实范围，再归一化映射，靠感受调）
4. 口型同步（speech/typing 驱动 ParamMouthOpenY）
5. 场景构图调整（枝改背景、光晕移到身后）+ §八 自查

红线：界面不出现情绪数字；08–16 动作永不播放；脸色含蓄。
文档没写清的先问，不要猜。
```

