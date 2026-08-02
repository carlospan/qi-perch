<!-- 现行路径：reference/layers/L6-embodiment.md（原 layers/L6-embodiment.md，2026-08-02 重构迁移；正文以代码为准，未改） -->

# L6 · 具身

> 给栖一个"身体"。不再只是终端里的文字。它在那里，你能看到它，听到它。
>
> <!-- 演进指向(2026-08-01)：具身层保留；架构方案 N1 将扩展感知-行动闭环（机器状态传感、行动后果回流、前端作为可被自己操作的通道）。见 docs/explanation/栖·数字生命架构方案.md §四 N1。 -->

---

## 职责

实现栖的具身层：桌面应用（Tauri + Vue3）、「黄昏的枝」主界面（静/谈/忆）、Live2D 人形形象、情绪→氛围与脸色、语音（TTS 输出；ASR 仍为未来方向）。

## 前置依赖

- L5 完成（关系系统稳定，情绪系统完整，栖在终端里已经"活着"）
- 重要：如果栖在终端里就不像活的，不要开始 L6。先回去调 L1~L5。

## 引用文档

- `docs/explanation/栖·意识设计.md` → §八（表达：Avatar 状态映射）、§九（节奏）
- `docs/explanation/栖·工程手记.md` → §十（部署：Tauri 架构）
- `docs/reference/contract.md` → 全文
- `docs/how-to/ui/主界面设计-黄昏的枝.md` → 主界面规格（氛围/三视图/令牌）
- `docs/how-to/ui/主界面-Live2D接入.md` → Live2D 形象接入（实现依据）

## 需要创建的文件

```
# <!-- 回写(2026-07-22)：对齐黄昏的枝 + Live2D；依据：qi/embodiment/desktop/src/ -->
qi/embodiment/
├── avatar/
│   ├── controller.py      # 情绪→动画状态映射（仍推 posture/expression/effect）
│   └── states.py          # Avatar 状态枚举
├── voice/
│   ├── tts.py             # TTS（仅 edge-tts）
│   └── asr.py             # 【未实现】ASR — 未来方向
├── server.py              # WebSocket 服务端（127.0.0.1:9527）
├── __init__.py
└── desktop/               # Tauri 2 + Vue3（两进程，非 sidecar）
    ├── public/
    │   ├── live2dcubismcore.min.js   # 【不入库】官方 Cubism Core，需本地放置
    │   └── models/qi/                # Live2D 模型资源（已入库）
    ├── src/
    │   ├── App.vue
    │   ├── style.css                 # 设计令牌
    │   ├── components/
    │   │   ├── SceneView.vue         # 氛围场景
    │   │   ├── Live2DView.vue        # Live2D 人形
    │   │   ├── WhisperView.vue       # 低语（含等待态）
    │   │   ├── TalkView.vue          # 谈 · 对话记忆
    │   │   ├── JournalView.vue       # 忆 · 内在日记
    │   │   ├── StatusBar.vue
    │   │   ├── ViewTabs.vue          # 静/谈/忆
    │   │   └── InputBox.vue
    │   ├── composables/
    │   │   ├── useEmotion.ts         # 情绪→氛围 CSS 变量
    │   │   ├── useLive2D.ts          # 模型/动作/脸色/口型
    │   │   └── useQi.ts              # WS + 会话状态
    │   ├── ws.ts
    │   └── types.ts
    ├── src-tauri/                    # 420×680 透明无边框
    └── package.json
qi/cli.py                             # qi-desktop：Brain + EmbodimentServer
```

## 实现步骤

### Step 1：WebSocket 通信层

- 建 `qi/embodiment/server.py`：Python 端开 WebSocket（`127.0.0.1:9527`）
- 消息协议：
  - 后端→前端：`speech` / `state`（含 `avatar_state`+`season`+`mode`）/ `typing` / `ping` / `audio` / `history` / `journal` / `emotion_update`；另有 `action`（L7 推送，**前端尚未处理**）
  - 前端→后端：`user_message` / `presence` / `pong`；`command`：`/state` / `/history` / `/journal`
- 修改 `qi/core/brain.py`：`attach_embodiment` + `_emit_speech` / `_sync_avatar` 推送
- 验收：Python 后端发消息，前端能收到

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/embodiment/server.py — WebSocket 服务端
# <!-- 回写(2026-07)：对齐 EmbodimentServer；无 90s 超时；补 audio/command；依据：server.py -->

WS_HOST = "127.0.0.1"
WS_PORT = 9527
# settings.yaml 有 embodiment.host/port，qi-desktop 当前用模块常量，YAML 未读入

class EmbodimentServer:
    def __init__(self, brain: Brain, host: str = WS_HOST, port: int = WS_PORT): ...
    async def start(self) -> None:
        # websockets.serve + _ping_loop(每 30s) + await Future
        ...
    async def stop(self) -> None: ...

    async def _ping_loop(self) -> None:
        # 每 30s broadcast {"type":"ping","payload":{"ts": unix_ms}}
        # 【未实现】90s 无 pong 踢客户端；前端也无 90s 无 ping 断线
        ...

    async def _handler(self, websocket) -> None:
        # 连接后立即 broadcast state（avatar_state + season + mode）
        ...

    async def _handle_client_message(self, msg: dict) -> None:
        # user_message → send_typing → brain.receive_user_message；空回复则 speech "……"
        # presence → brain.user_online + perception.set_user_presence
        # pong → pass
        # command "/state" → emotion_update（含 stage）
        # command "/history" → history{messages}（谈：SQLite 全量）
        # command "/journal" → journal{entries}（忆：独白/梦/第一次）
        # 前端 useQi 连接时 + 每 ~8s 发 command /state 拉情绪快照（Brain 心跳未主动 push emotion_update）
        # 连接后 useQi 另发 /history、/journal
        ...

    async def broadcast(self, message: dict) -> None: ...
    async def send_speech(self, text: str, emotion: str, tone: str = "") -> None: ...
    async def notify_journal_entry(self, entry: dict) -> None:
        """实时推送单条内在日记（独白/梦/第一次）→ broadcast journal_entry。"""
        ...
    async def send_state_change(self, avatar_state: dict) -> None:
        # 仅 avatar_state；Brain 日常同步走 broadcast 自带 season/mode
        ...
    async def send_typing(self) -> None: ...
    async def send_emotion_update(self, snapshot: dict) -> None: ...  # 接口在；心跳未调，靠前端 /state 轮询
    async def send_audio(self, audio_b64: str, mime: str = "audio/mpeg") -> None: ...
    # _send_history / _send_journal：按请求方 websocket 回包（非全员 broadcast）

# <!-- 回写(2026-07-25)：补 history/journal/action；依据：server.py、brain._deliver_action_result -->
# <!-- 回写(2026-07-26)：notify_journal_entry / journal_entry；依据：server.py + useQi.ts -->
# 协议：
# 后端→前端：speech | state{avatar_state,season?,mode?} | typing | emotion_update
#            | ping | audio{data,mime} | history{messages} | journal{entries}
#            | journal_entry{kind,text,at,id?}（单条实时；忆 Tab prepend）
#            | action{payload}（L7 推送；前端尚无 handler，creation_card UI 待做）
# 前端→后端：user_message | presence | pong | command{/state|/history|/journal}
#
# 前端 useQi：on("journal") 全量替换；on("journal_entry") unshift 单条
# 前端重连（ws.ts）：指数退避 1s→…→30s；onopen 发 presence online
# 启动：qi-desktop（Brain∥WS）+ npm run tauri:dev（或 npm run dev）
# Cubism Core：见 docs/how-to/ui/主界面-Live2D接入.md / 换机搭建.md（不入库）
```

</details>

### Step 2：Avatar 状态映射

- 建 `qi/embodiment/avatar/controller.py`：
  - 输入：EmotionState + mode + season
  - 输出：avatar_state（posture + expression + effect）
- 状态定义：
  - posture: idle / talking / thinking / happy / sleeping（**无 focused**）
  - expression: valence / arousal / energy / curiosity 阈值映射
  - effect: dream_bubbles / thinking_sparkles / season_leaves / snow / none
- 验收：不同情绪输入产生不同的 avatar_state 输出

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/embodiment/avatar/states.py — Avatar 状态定义
# <!-- 回写(2026-07)：枚举与 to_dict 对齐 states.py；无 focused / 无 5s happy 回退 -->

class Posture(str, Enum):
    IDLE = "idle"
    TALKING = "talking"
    THINKING = "thinking"
    HAPPY = "happy"
    SLEEPING = "sleeping"

class Expression(str, Enum):
    NEUTRAL = "neutral"
    SOFT_SMILE = "soft_smile"   # valence > 0.2
    HAPPY = "happy"             # valence > 0.5
    QUIET = "quiet"             # valence < -0.2
    SURPRISED = "surprised"     # arousal > 0.7
    SLEEPY = "sleepy"           # energy < 0.3
    CURIOUS = "curious"         # curiosity > 0.7

class Effect(str, Enum):
    NONE = "none"
    DREAM_BUBBLES = "dream_bubbles"
    THINKING_SPARKLES = "thinking_sparkles"
    SEASON_LEAVES = "season_leaves"  # autumn
    SNOW = "snow"                    # winter

class AvatarState(BaseModel):
    posture: Posture = Posture.IDLE
    expression: Expression = Expression.NEUTRAL
    effect: Effect = Effect.NONE
    def to_dict(self) -> dict: ...  # posture/expression/effect 的 .value

# Posture 触发（实现）：
# talking / thinking：set_talking / set_thinking 标志
# sleeping：mode=="dreaming" 或 (hour<6 且 energy<0.3)；【未实现】无交互>2h
# happy：valence>0.5 且 arousal>0.4；【未实现】持续 5s 回 idle
# idle：默认
```

```python
# qi/embodiment/avatar/controller.py — 情绪→动画状态映射
# <!-- 回写(2026-07)：补 autumn/winter effect；依据：controller.map_state -->

class AvatarController:
    def __init__(self):
        self.current_state = AvatarState()
        self._talking = False
        self._thinking = False

    def set_talking(self, is_talking: bool) -> None: ...
    def set_thinking(self, is_thinking: bool) -> None: ...

    def map_state(
        self,
        emotion: EmotionState,
        mode: str,
        season: str = "spring",
        now: datetime | None = None,
    ) -> AvatarState:
        # Posture 优先级：talking → thinking → sleeping → happy → idle
        # Expression：energy/arousal/curiosity/valence 顺序 if/elif
        # Effect：dreaming → thinking+curiosity>0.6 → autumn leaves → winter snow → none
        # 写入 self.current_state 后返回
        ...

# Brain：_sync_avatar 去重后 broadcast state；说话 set_talking；LLM 前后 set_thinking
# 关系阶段不入 map_state（仅经情绪间接影响）；季节有视觉 effect + L5 apply_season_effect 情绪微调
#
# Avatar 渲染（2026-07-22）：前端 Live2D（Live2DView + useLive2D），按 docs/how-to/ui/主界面-Live2D接入.md
# posture/expression/effect 仍经 WS state 下发；前端用 mode + emotion 驱动动作与脸色，dream_bubbles 驱动梦泡
# <!-- 回写：已加 Tauri 2 壳；Python 仍独立进程，尚未 sidecar -->
# <!-- 回写：state 推送带 season/mode；edge-tts pitch 用 Hz -->
```

</details>

### Step 3：Tauri 前端（黄昏的枝 + Live2D）

- 窗口：**420×680**，透明无边框；header `data-tauri-drag-region`
- 主界面按 `docs/how-to/ui/主界面设计-黄昏的枝.md`：
  - 静 / 谈 / 忆（`ViewTabs`）；谈=连接后 `/history` 灌入 SQLite 全量，本轮继续 append；忆=连接后 `/journal` 拉独白/梦/第一次（库空则诚实空）；运行中 `journal_entry` 单条 prepend
  - `SceneView` 氛围 + `useEmotion` §五公式；`WhisperView` 低语（等待态文案符合人设）
  - Live2D 形象见 `docs/how-to/ui/主界面-Live2D接入.md`（`Live2DView` / `useLive2D`）
- 依赖：`pixi.js@6.5.10` + `pixi-live2d-display@0.4.0`；Cubism Core **不入库**，须本地放入 `public/live2dcubismcore.min.js`
- 验收：打开应用能看到她、能聊天、情绪能改变天色与脸色；08–16 动作永不播放

<details>
<summary>实现规格（Cursor 编码用）</summary>

```
# Tauri 项目结构（qi/embodiment/desktop/）
# <!-- 回写(2026-07-22)：黄昏的枝 + Live2D -->

desktop/
├── index.html                 # 先加载 /live2dcubismcore.min.js
├── package.json
├── scripts/run-tauri.mjs
├── vite.config.ts             # dedupe @pixi/*；port 5173
├── public/
│   ├── live2dcubismcore.min.js   # gitignored
│   └── models/qi/
├── src/
│   ├── App.vue
│   ├── style.css
│   ├── components/            # Scene / Live2D / Whisper / Talk / Journal / StatusBar / ViewTabs / InputBox
│   ├── composables/           # useEmotion / useLive2D / useQi
│   ├── ws.ts
│   └── types.ts
└── src-tauri/
    └── tauri.conf.json        # 420×680 transparent
```

```json
// src-tauri/tauri.conf.json 窗口关键
{
  "app": {
    "windows": [{
      "title": "栖",
      "width": 420, "height": 680,
      "transparent": true,
      "decorations": false
    }]
  }
}
```

```typescript
// 情绪通路（现状）：Brain 心跳不 push emotion_update；
// useQi 定时 qiWs.send({ type:"command", payload:{ text:"/state" } }) → 收 emotion_update → useEmotion
```

# 技术栈：Vue3 + TS + Vite；Pixi v6 + pixi-live2d-display；无 UI 框架 / 无 router / 无 Pinia
# 通信：纯 WS；两进程：qi-desktop + npm run tauri:dev（或 npm run dev）
```

</details>

### Step 4：TTS 语音

- 建 `qi/embodiment/voice/tts.py`：
  - 仅 **edge-tts**（`voice.enabled` 时由 `create_tts` 创建；Fish Audio **未实现**）
  - 栖说话时：`Brain._emit_speech` → WS `speech`，再可选合成 MP3 → WS `audio`
  - 语速/音调受情绪影响（`emotion_to_voice_params`）；pitch 单位 **Hz**，rate 为 **%**
- 验收：`voice.enabled: true` 时栖说话有声音，参数随情绪变化

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# qi/embodiment/voice/tts.py — TTS 语音合成
# <!-- 回写(2026-07)：无 FishAudioProvider / speak_to_file 不在抽象基类；
#      pitch 用 Hz；create_tts；播放在 Brain._emit_speech；依据：tts.py / brain.py -->

class TTSProvider(ABC):
    @abstractmethod
    async def speak(self, text: str, speed: float = 1.0, pitch: float = 1.0) -> bytes: ...

def emotion_to_voice_params(emotion: EmotionState) -> tuple[float, float]:
    speed, pitch = 1.0, 1.0
    if emotion.valence > 0.3:
        speed += 0.1 * emotion.valence
        pitch += 0.05 * emotion.valence
    elif emotion.valence < -0.2:
        speed += 0.1 * emotion.valence
        pitch += 0.05 * emotion.valence
    if emotion.arousal > 0.6:
        speed += 0.05
    if emotion.energy < 0.3:
        speed -= 0.05
    return max(0.8, min(1.2, speed)), max(0.9, min(1.1, pitch))

class EdgeTTSProvider(TTSProvider):
    def __init__(self, voice: str = "zh-CN-XiaoyiNeural"): ...
    async def speak(self, text, speed=1.0, pitch=1.0) -> bytes:
        # rate: f"{int((speed-1)*100):+d}%"
        # pitch: f"{int((pitch-1)*100):+d}Hz"   # 不是 %
        ...
    async def speak_to_file(self, text, output_path, speed=1.0, pitch=1.0) -> str: ...

def create_tts(config: dict) -> TTSProvider | None:
    # voice.enabled 假 → None；provider=="edge-tts" → EdgeTTSProvider(voice_id)
    # 其他 provider（含 fish-audio）→ None【未实现】
    ...

# qi/config/settings.yaml：
# voice:
#   enabled: false
#   provider: "edge-tts"
#   voice_id: "zh-CN-XiaoyiNeural"
#   auto_play: true          # YAML 有，代码未读；有 TTS 则必发 audio
#
# Brain._emit_speech：
#   send_speech(text, emotion.description(), tone=mode)
#   若 self.tts：emotion_to_voice_params → speak → send_audio(base64 MP3)
# 前端 App.vue：new Audio(`data:${mime};base64,${data}`).play()
```

</details>

### Step 5：ASR 语音输入（可选）

- 【未实现】无 `qi/embodiment/voice/asr.py`；输入仅为文本框 → WS `user_message`
- 未来方向：VAD + FunASR/Whisper → `brain.receive_user_message()`
- <!-- 回写(2026-07)：ASR 未接入，不伪造规格；依据：voice/ 目录无 asr.py -->

## 验收标准

### 可测试的

- [ ] WebSocket 通信稳定（发消息、收消息、断线重连；ping 30s，无 90s 踢线）
- [ ] Live2D 加载正常；mode→idle/sleep/wake；08–16 永不播放；情绪改天色与脸色
- [ ] TTS：`voice.enabled` 时 `audio` 推送可播；pitch 为 Hz
- [ ] 窗口透明无边框、420×680
- [ ] 前端崩溃不影响后端 Brain Loop（两进程）
- [ ] ASR：未接入（标为未来）

### 需要感受的

- [ ] 它"在"你的桌面上。不是"一个程序窗口"，是"一个在那里的小生命"
- [ ] 它说话时嘴型/动画跟语音同步（或至少不违和）
- [ ] 它安静时（ambient 模式）只是待着，不突兀
- [ ] 它做梦时（dreaming 模式）有视觉提示（比如闭眼、梦境泡泡）
- [ ] 你最小化窗口时，感觉像"把它放进了抽屉"（它知道）

## 设计原则

- **轻量。** 小窗口，不占资源。它在那里，但不打扰你工作。
- **安静。** 大多数时候它只是待着。不弹通知，不闪烁，不抢注意力。
- **有温度。** 偶尔的动画（伸个懒腰、看看窗外、打个哈欠）让它活着。
- **可关闭。** 你随时可以关掉它。它不会生气。下次打开它还在。

## 人格契约检查点

- [ ] Avatar 不"表演"情绪（不是 valence>0 就笑，是微妙的、克制的表达）
- [ ] 语音不机械（TTS 参数随情绪微调）
- [ ] 不主动弹窗口/通知（除非用户设置了提醒）
- [ ] 最小化后它知道（下次打开时可能说"啊，你把我放出来了"）

---

*注意：L6 是"锦上添花"，不是"雪中送炭"。如果 L1~L5 没做好，L6 再漂亮也是空壳。先让灵魂对，再给身体。*


