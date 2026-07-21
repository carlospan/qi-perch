# L6 · 具身

> 给栖一个"身体"。不再只是终端里的文字。它在那里，你能看到它，听到它。

---

## 职责

实现栖的具身层：桌面应用（Tauri + Vue3）、虚拟形象（CSS 动画形象（未来方向：帧动画/Live2D））、情绪→表情映射、语音（TTS 输出，可选 ASR 输入）。

## 前置依赖

- L5 完成（关系系统稳定，情绪系统完整，栖在终端里已经"活着"）
- 重要：如果栖在终端里就不像活的，不要开始 L6。先回去调 L1~L5。

## 引用文档

- `./栖·意识设计.md` → §八（表达：Avatar 状态映射）、§九（节奏）
- `./栖·工程手记.md` → §十（部署：Tauri 架构）
- `docs/contract.md` → 全文

## 需要创建的文件

```
# <!-- 回写(2026-07)：按现状清单；ASR/Fish Audio/sidecar 未实现，依据：embodiment/ -->
embodiment/
├── avatar/
│   ├── controller.py      # 情绪→动画状态映射
│   └── states.py          # Avatar 状态（idle/talking/thinking/happy/sleeping；无 focused）
├── voice/
│   ├── tts.py             # TTS（仅 edge-tts；create_tts 读 voice.enabled）
│   └── asr.py             # 【未实现】ASR（FunASR / Whisper）— 未来方向
├── server.py              # WebSocket 服务端（127.0.0.1:9527）
├── __init__.py
└── desktop/               # Tauri 2 + Vue3 前端（两进程，非 sidecar）
    ├── scripts/
    │   └── run-tauri.mjs  # 补 cargo PATH 后调 @tauri-apps/cli
    ├── src/
    │   ├── App.vue
    │   ├── components/
    │   │   ├── AvatarView.vue     # CSS 几何体 Avatar（非 PNG/Lottie）
    │   │   ├── ChatBubble.vue
    │   │   ├── StatusIndicator.vue
    │   │   └── InputBox.vue
    │   ├── ws.ts                  # WebSocket 客户端（无 useWebSocket.ts）
    │   └── types.ts
    ├── src-tauri/                 # 透明无边框壳；无 tray / sidecar
    └── package.json               # tauri:dev / tauri:build
run.py                             # --desktop：Brain + EmbodimentServer
```

## 实现步骤

### Step 1：WebSocket 通信层

- 建 `embodiment/server.py`：Python 端开 WebSocket（`127.0.0.1:9527`）
- 消息协议：
  - 后端→前端：`speech` / `state`（含 `avatar_state`+`season`+`mode`）/ `typing` / `ping` / `audio`
  - 前端→后端：`user_message` / `presence` / `pong`（可选 `command` `/state`）
- 修改 `core/brain.py`：`attach_embodiment` + `_emit_speech` / `_sync_avatar` 推送
- 验收：Python 后端发消息，前端能收到

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# embodiment/server.py — WebSocket 服务端
# <!-- 回写(2026-07)：对齐 EmbodimentServer；无 90s 超时；补 audio/command；依据：server.py -->

WS_HOST = "127.0.0.1"
WS_PORT = 9527
# settings.yaml 有 embodiment.host/port，run.py 当前用模块常量，YAML 未读入

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
        # command "/state" → emotion_update（含 stage）；前端 UI 未发此命令
        ...

    async def broadcast(self, message: dict) -> None: ...
    async def send_speech(self, text: str, emotion: str, tone: str = "") -> None: ...
    async def send_state_change(self, avatar_state: dict) -> None:
        # 仅 avatar_state；Brain 日常同步走 broadcast 自带 season/mode
        ...
    async def send_typing(self) -> None: ...
    async def send_emotion_update(self, snapshot: dict) -> None: ...  # Brain 心跳未调用
    async def send_audio(self, audio_b64: str, mime: str = "audio/mpeg") -> None: ...

# 协议：
# 后端→前端：speech | state{avatar_state,season?,mode?} | typing | emotion_update | ping | audio{data,mime}
# 前端→后端：user_message | presence | pong | command
#
# 前端重连（ws.ts）：指数退避 1s→…→30s；onopen 发 presence online；无 HEARTBEAT_TIMEOUT
# 启动：python run.py --desktop（Brain∥WS）+ npm run tauri:dev（或 npm run dev）
```

</details>

### Step 2：Avatar 状态映射

- 建 `embodiment/avatar/controller.py`：
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
# embodiment/avatar/states.py — Avatar 状态定义
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
# embodiment/avatar/controller.py — 情绪→动画状态映射
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
# Avatar 渲染：MVP = CSS 几何体（AvatarView.vue），非 PNG/Lottie/Live2D
# <!-- 回写：MVP 用 CSS 几何体 Avatar（无 PNG 序列） -->
# <!-- 回写：已加 Tauri 2 壳；Python 仍独立进程，尚未 sidecar -->
# <!-- 回写：state 推送带 season/mode；edge-tts pitch 用 Hz -->
```

</details>

### Step 3：Tauri 前端

- 初始化 Tauri 2 + Vue3 项目
- 实现：
  - AvatarView：CSS 几何体按 `avatar_state` 切换 posture/expression/effect
  - ChatBubble：打字机效果（约 28ms/字）
  - StatusIndicator：模式 / 季节 / 连接状态
  - InputBox：文本输入（max 500）
- 窗口：透明无边框 360×560（min 320×480）；header `data-tauri-drag-region`
- 验收：打开应用，能看到栖的形象，能打字聊天

<details>
<summary>实现规格（Cursor 编码用）</summary>

```
# Tauri 项目结构（embodiment/desktop/）
# <!-- 回写(2026-07)：对齐现状目录；无 composables/useWebSocket、无 PNG assets、无 sidecar -->

desktop/
├── index.html
├── package.json              # scripts: dev / tauri:dev / tauri:build
├── scripts/run-tauri.mjs     # 前置 %USERPROFILE%\.cargo\bin 再调 CLI
├── vite.config.ts            # Vite :5173
├── src/
│   ├── main.ts
│   ├── App.vue               # WS 订阅；audio 用 HTML5 Audio(data:…)
│   ├── style.css             # html/body 透明
│   ├── components/
│   │   ├── AvatarView.vue    # CSS posture-*/expr-*/fx-*
│   │   ├── ChatBubble.vue
│   │   ├── StatusIndicator.vue
│   │   └── InputBox.vue
│   ├── ws.ts
│   └── types.ts
├── src-tauri/
│   ├── tauri.conf.json
│   ├── .cargo/config.toml    # rsproxy 稀疏索引
│   └── src/lib.rs            # 默认 builder，无自定义 command / tray
└── （无 public/assets/avatar PNG）
```

```json
// src-tauri/tauri.conf.json 关键（Tauri 2）
{
  "productName": "qi",
  "identifier": "com.qi.desktop",
  "build": {
    "devUrl": "http://localhost:5173",
    "frontendDist": "../dist",
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build"
  },
  "app": {
    "windows": [{
      "label": "main",
      "title": "栖",
      "width": 360, "height": 560,
      "minWidth": 320, "minHeight": 480,
      "resizable": true,
      "transparent": true,
      "decorations": false,
      "alwaysOnTop": false,
      "shadow": false
    }]
  }
}
// <!-- 回写：360×560 聊天 MVP；系统托盘 / sidecar 未做；两进程启动 -->
```

```typescript
// src/ws.ts — 与 Python 后端通信
// <!-- 回写(2026-07)：对齐 ws.ts；无 HEARTBEAT_TIMEOUT；依据：desktop/src/ws.ts -->

const WS_URL = "ws://127.0.0.1:9527";
const RECONNECT_MAX_DELAY = 30000;

export class QiWebSocket {
  connect(): void;           // onopen → presence online；ping → pong
  disconnect(): void;        // presence false + close
  send(msg: ClientMessage): void;
  sendUserMessage(text: string): void;
  setPresence(online: boolean): void;
  on(type: string, handler: Handler): void;
  // 断线指数退避 1s→2s→…→30s；closedByUser 不重连
}
export const qiWs = new QiWebSocket();

# 技术栈：Vue3 + TS + Vite；无 UI 框架
# 通信：纯 WS；非 sidecar——手动 python run.py --desktop + npm run tauri:dev
```

</details>

### Step 4：TTS 语音

- 建 `embodiment/voice/tts.py`：
  - 仅 **edge-tts**（`voice.enabled` 时由 `create_tts` 创建；Fish Audio **未实现**）
  - 栖说话时：`Brain._emit_speech` → WS `speech`，再可选合成 MP3 → WS `audio`
  - 语速/音调受情绪影响（`emotion_to_voice_params`）；pitch 单位 **Hz**，rate 为 **%**
- 验收：`voice.enabled: true` 时栖说话有声音，参数随情绪变化

<details>
<summary>实现规格（Cursor 编码用）</summary>

```python
# embodiment/voice/tts.py — TTS 语音合成
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

# config/settings.yaml：
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

- 【未实现】无 `embodiment/voice/asr.py`；输入仅为文本框 → WS `user_message`
- 未来方向：VAD + FunASR/Whisper → `brain.receive_user_message()`
- <!-- 回写(2026-07)：ASR 未接入，不伪造规格；依据：voice/ 目录无 asr.py -->

## 验收标准

### 可测试的

- [ ] WebSocket 通信稳定（发消息、收消息、断线重连；ping 30s，无 90s 踢线）
- [ ] Avatar 状态正确映射（情绪→表情对应；CSS 几何体）
- [ ] TTS：`voice.enabled` 时 `audio` 推送可播；pitch 为 Hz
- [ ] 窗口透明无边框、360×560
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
