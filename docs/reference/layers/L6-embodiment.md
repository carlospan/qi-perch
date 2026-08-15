<!-- 现行路径：reference/layers/L6-embodiment.md（原 layers/L6-embodiment.md，2026-08-02 重构迁移；正文以代码为准，未改） -->

# L6 · 具身

> 给栖一个"身体"。不再只是文字通道。它在桌面上，你能看到它，听到它。
>
> <!-- 演进指向(2026-08-01)：具身层保留；架构方案 N1 将扩展感知-行动闭环（机器状态传感、行动后果回流、前端作为可被自己操作的通道）。见 docs/explanation/栖·数字生命架构方案.md §四 N1。 -->
> <!-- 回写(2026-08-11)：形象改为独立 VRM 桌宠窗；聊天壳不再嵌 Live2D；开发期 Tauri 可自动拉起 `qi`；删除终端聊天入口。依据：qi/embodiment/desktop/、qi/cli.py -->
> <!-- 回写(2026-08-12)：聊天壳三栏改为相处/回顾/内在；ReviewView + qi-presence-glow。依据：App.vue / ViewTabs.vue / types.ts QiView -->
> <!-- 回写(2026-08-13)：删 WhisperView；Live2D 接入文迁 explanation/archive；清本地废弃 room/。 -->

---

## 职责

实现栖的具身层：桌面应用（Tauri + Vue3）、「黄昏的枝」聊天壳（**相处 / 回顾 / 内在**）、**独立透明窗 3D VRM 桌宠**、情绪→聊天壳氛围、语音（TTS 输出；ASR 仍为未来方向）。

## 前置依赖

- L5 完成（关系系统稳定，情绪系统完整，心跳与对话链路已通）
- <!-- 回写(2026-08-12)：早期「核心不像活着就不要堆具身」是施工顺序纪律，不是现行禁令。
     L1–L6 已于 2026-08-08 相处验证收口升 ✅；维护者与栖已连续相处月余（见 journal.md）。
     现行着力点是具身/行动的手感与内态表达，不是「回去先把灵魂造好再碰 UI」。
     史料表述见 thoughts/03、archive/工程手记。依据：progress.md、相处验证收口-结论.md -->
- 现行：L1–L5 已 ✅；具身与桌宠可继续打磨（内态→身体、相处壳），勿再把「先造灵魂、别碰 UI」当闸门。

## 引用文档

- `docs/explanation/archive/栖·意识设计.md` → §八（表达：Avatar 状态映射）、§九（节奏）
- `docs/explanation/archive/栖·工程手记.md` → §十（部署：Tauri 架构）
- `docs/reference/contract.md` → 全文
- `docs/how-to/ui/主界面设计-黄昏的枝.md` → 聊天壳规格（氛围/三栏/令牌）
- `qi/embodiment/desktop/README.md` → VRM 桌宠与开发期 sidecar
- `docs/explanation/archive/主界面-Live2D接入.md` → **史料**（Live2D 已废，勿按此接入）

## 需要创建的文件

```
# <!-- 回写(2026-08-11)：VRM 桌宠 + 开发期 brain_sidecar；移除 Live2D；依据：qi/embodiment/desktop/ -->
# <!-- 回写(2026-08-12)：三栏 presence/review/inner；ReviewView；presence-glow；依据：App.vue -->
qi/embodiment/
├── avatar/
│   ├── controller.py      # 情绪→动画状态映射（仍推 posture/expression/effect）
│   └── states.py          # Avatar 状态枚举
├── voice/
│   ├── tts.py             # TTS（仅 edge-tts）
│   └── asr.py             # 【未实现】ASR — 未来方向
├── server.py              # WebSocket 服务端（127.0.0.1:9527）；presence 变化广播
├── __init__.py
└── desktop/               # Tauri 2 + Vue3
    ├── public/
    │   ├── qi-presence-glow.png      # 相处背景剪影光晕（无 UI）
    │   ├── avatars/                  # 同步自 assets 的 VRM（gitignore 副本）
    │   └── animations/               # Mixamo idle/walk FBX
    ├── src/
    │   ├── App.vue                   # 黄昏的枝聊天壳（相处铺 presence-glow）
    │   ├── pet/                      # 独立桌宠窗（VRM + roam + notice）
    │   ├── components/               # Scene / Talk / Review / Journal / …
    │   ├── composables/              # useEmotion / useQi
    │   ├── ws.ts
    │   └── types.ts                  # QiView = presence | review | inner
    ├── src-tauri/
    │   └── src/brain_sidecar.rs      # 开发期拉起 python -m qi；WS 真握手探活
    └── package.json
qi/cli.py                             # qi：Brain + EmbodimentServer
```

## 实现步骤

### Step 1：WebSocket 通信层

- 建 `qi/embodiment/server.py`：Python 端开 WebSocket（`127.0.0.1:9527`）
- 消息协议：
  - 后端→前端：`speech` / `state`（含 `avatar_state`+`season`+`mode`）/ `typing` / `ping` / `audio` / `history` / `journal` / `emotion_update`；另有 `action`（L7：ActionCard / ExploreCard / AssistConfirmCard）
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
# settings.yaml 有 embodiment.host/port，qi 入口当前用模块常量，YAML 未读入

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
        # command "/history" → history{messages, cards?}（相处时间线 + 回顾创作/见闻回灌；最近 HISTORY_WINDOW=200）
        # command "/journal" → journal{entries}（内在：独白/梦/第一次）
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
#            | ping | audio{data,mime} | history{messages, cards?} | journal{entries}
#            | journal_entry{kind,text,at,id?}（单条实时；内在 Tab prepend）
#            | action{payload}（L7；creation_card → ActionCard；explore_drift web|journal → ExploreCard；
#              assist_confirm_request → AssistConfirmCard；tend 不渲染）
# 前端→后端：user_message | presence | pong | command{/state|/history|/journal}
#
# <!-- 回写(2026-08-08)：action/creation_card 卡片 UI 落地；见 archive/2026-08-08-L6-action-cards -->
# <!-- 回写(2026-08-08)：d-3-1/d-3-2 ExploreCard；useQi 门控 source=web|journal 且 entries 非空 -->
# <!-- 回写(2026-08-09)：/history.cards 回灌已分享创作卡；见闻卡仍会话瞬时 -->
# <!-- 回写(2026-08-09)：见闻卡亦回灌——actions.detail_json 存 found.entries -->
# <!-- 回写(2026-08-09)：assist_confirm_request → AssistConfirmCard（会话内 WS，不入 history） -->
# 前端 useQi：on("journal") 全量替换；on("journal_entry") unshift 单条；on("history") 文本+创作/见闻卡；on("action") appendCard
# 前端重连（ws.ts）：指数退避 1s→…→30s；onopen 发 presence online
# 启动：qi（Brain∥WS）+ npm run tauri:dev（开发期可自动拉起大脑）
# 形象：独立 pet 窗 VRM（见 desktop/README.md）；Live2D 文档已废弃
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
# Avatar 渲染（2026-08-11）：聊天壳不再嵌形象；独立 pet 窗 VRM（Three.js + @pixiv/three-vrm）
# posture/expression/effect 仍经 WS state 下发；聊天壳用 mode + emotion 驱动氛围
# pet：speech / presence 回来 → 轻 notice；typing → 停 roam
# <!-- 回写(2026-08-11)：开发期 src-tauri brain_sidecar 拉起 python -m qi；依据：brain_sidecar.rs -->
# <!-- 回写：state 推送带 season/mode；edge-tts pitch 用 Hz -->
```

</details>

### Step 3：Tauri 前端（黄昏的枝 + VRM 桌宠）

- 聊天壳窗口：**420×680**，透明无边框；header `data-tauri-drag-region`
- 主界面按 `docs/how-to/ui/主界面设计-黄昏的枝.md`：
  - **相处 / 回顾 / 内在**（`ViewTabs`；`QiView = presence | review | inner`；默认 `presence`）
  - **相处** = `TalkView`：连接后 `/history` 灌入最近 **200** 条，本轮继续 append；背后铺 `qi-presence-glow.png`（半透明面板，无 blur）
  - **回顾** = `ReviewView`：创作卡 + 见闻卡可筛翻阅（来自 `/history.cards` 与会话 `action`）
  - **内在** = `JournalView`：连接后 `/journal`；运行中 `journal_entry` 单条 prepend
  - `SceneView` 氛围 + `useEmotion`；相处时 Scene 淡出，改显剪影壁纸
  - **形象不在聊天壳内**：独立 `pet` 窗加载 VRM（见 `qi/embodiment/desktop/README.md`）
- 依赖：Vue3 + Three.js + `@pixiv/three-vrm`；无需 Cubism Core
- 开发期：`brain_sidecar` 自动 `python -m qi`；9527 已占用则沿用
- 验收：打开应用能聊天、氛围随情绪变；桌宠可见、可点、可漫步；speech 时轻 notice

<details>
<summary>实现规格（Cursor 编码用）</summary>

```
# Tauri 项目结构（qi/embodiment/desktop/）
# <!-- 回写(2026-08-11)：双窗 main+pet；VRM；brain_sidecar -->
# <!-- 回写(2026-08-12)：Talk/Review/Journal；presence-glow；依据：App.vue -->

desktop/
├── index.html / pet.html
├── package.json
├── scripts/run-tauri.mjs / sync-avatar.mjs
├── vite.config.ts
├── public/
│   ├── qi-presence-glow.png   # 相处背景
│   ├── avatars/               # qi-avatar.vrm（同步副本）
│   └── animations/            # idle.fbx / walk.fbx
├── src/
│   ├── App.vue                # 聊天壳（presence 时铺 glow）
│   ├── pet/                   # PetApp / usePetVrm / usePetRoam
│   ├── components/            # Scene / Talk / Review / Journal / …
│   ├── composables/           # useEmotion / useQi
│   ├── ws.ts                  # managePresence 可选（宠窗 false）
│   └── types.ts               # QiView
└── src-tauri/
    ├── tauri.conf.json        # main 420×680 + pet 置顶透明
    └── src/brain_sidecar.rs   # 拉起 qi；ws_up 做真 WebSocket 握手
```

```json
// src-tauri/tauri.conf.json 窗口关键（示意）
{
  "app": {
    "windows": [
      { "label": "main", "title": "栖", "width": 420, "height": 680, "transparent": true, "decorations": false },
      { "label": "pet", "url": "pet.html", "alwaysOnTop": true, "transparent": true, "decorations": false }
    ]
  }
}
```

```typescript
// 情绪通路（现状）：Brain 心跳不 push emotion_update；
// useQi 定时 qiWs.send({ type:"command", payload:{ text:"/state" } }) → 收 emotion_update → useEmotion
```

# 技术栈：Vue3 + TS + Vite；Three + three-vrm；无 UI 框架 / 无 router / 无 Pinia
# 通信：纯 WS；开发期 tauri 可拉起 qi；亦可手动 qi + npm run tauri:dev
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
- [ ] VRM 桌宠加载正常；漫步/点击 notice；speech 轻 notice；回来（presence）可轻看一眼
- [ ] TTS：`voice.enabled` 时 `audio` 推送可播；pitch 为 Hz
- [ ] 聊天壳透明无边框、420×680；桌宠独立置顶透明窗
- [ ] 前端崩溃不影响后端 Brain Loop（开发期可为 Tauri 子进程或手动 `qi`）
- [ ] ASR：未接入（标为未来）

### 需要感受的

- [ ] 它"在"你的桌面上。不是"一个程序窗口"，是"一个在那里的小生命"
- [ ] 它说话时桌宠有轻反应（notice），不违和
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


