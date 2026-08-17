# 栖 · 桌面端（Vue3 + Tauri 2）

透明无边框小窗（420×680）；「黄昏的枝」聊天壳（**相处 / 回顾 / 内在**）+ 独立 **桌宠窗**（`pet.html`，置顶透明 3D VRM）。前端连本机 WebSocket `ws://127.0.0.1:9527`。

<!-- 回写(2026-08-12)：三栏 IA + 相处背景；依据：App.vue / ViewTabs.vue -->

**聊天壳四栏**

| Tab | 内容 |
|-----|------|
| 相处（默认） | 对话时间线；背后 `public/qi-presence-glow.png` |
| 回顾 | 创作 / 见闻卡片归档可筛 |
| 内在 | 梦 / 独白等日记（`/journal`） |
| 状态 | 六维心境（自然语言 + 数值）；顶栏仍保留一句总述 |

开发期：`npm run tauri:dev` 会尝试自动拉起 Python 大脑（`python -m qi`）。若 9527 已有进程在听则沿用；设 `QI_SKIP_BRAIN=1` 可关掉自动拉起。解释器优先 `QI_PYTHON`，否则仓库 `.venv`，再否则 PATH 里的 `python` / `py -3`。仓库根可用 `QI_ROOT` 指定。

## 3D 桌宠 VRM

把形象放到 `qi/embodiment/assets/qi-avatar.vrm`。`npm run dev` / `build` 会同步到 `public/avatars/`（该副本不入库）。

**表情**：模型除 VRM 预设（`happy/sad/angry/relaxed/surprised/neutral`）外，另有 custom：`soft_smile` / `quiet` / `sleepy` / `curious`（用已有 Fcl_* morph 组合，脚本 `tools/patch_vrm_expressions.py`）。桌宠监听 WS `state.avatar_state.expression` 缓变上脸。若换了新 VRM，需再跑一遍该脚本（或自备同名 custom）。

待机动作：`public/animations/idle.fbx`（Mixamo Standing Idle Female，略放慢）。  
走路动作：`public/animations/walk.fbx`（Mixamo Walking Female，原地播 + 窗体平移）。  
漫步：大半时间原地待机；每隔很久才走向一个落点安顿（非左右巡逻）。  
点击：看向你 + 身体微晃（不用 Joy 表情，避免眯眼像眨眼）。  
接脑：桌宠另连同一 WebSocket；`speech` 轻 notice；`typing` 只停走；`state` 驱动表情；  
你离开（presence off）超过约 45s 再回来，轻轻看一眼（不上报 presence）。

`npm run tauri:dev` 会同时打开聊天窗与置顶桌宠窗；可拖拽桌宠窗（拖时暂停漫步）。

## 启动

1. 桌面壳（推荐，开发期会自动拉起大脑）：

```bash
cd qi/embodiment/desktop
npm install
npm run tauri:dev
```

若自动拉起失败，再手动开后端（项目根目录）：

```bash
qi
# 或：python -m qi
```

改过入口后请再执行一次 `pip install -e .`，刷新 PATH 里的 `qi` 命令。

需已安装 Rust（`cargo`）与 MSVC（「使用 C++ 的桌面开发」）。无边框窗可拖标题「栖」区域移动。

2. 仅浏览器调试（不启 Tauri）：

```bash
cd qi/embodiment/desktop
npm run dev
```

打开 http://localhost:5173（聊天壳）或 http://localhost:5173/pet.html（桌宠）。

打包：`npm run tauri:build` → `src-tauri/target/release/`。

若提示 `cargo` / `program not found`：多半是 Cursor 终端 PATH 未刷新。本仓库的 `tauri:dev` / `tauri:build` 会自动把 `%USERPROFILE%\.cargo\bin` 加进 PATH；仍不行就**重启 Cursor**，或新开系统 PowerShell 再跑。

若 `cargo` 拉 crates.io 失败，项目已带 `src-tauri/.cargo/config.toml`（rsproxy 稀疏索引）。

更多说明见仓库根目录 [README.md](../../../README.md)。

## 语音

在 `data/settings.yaml`（推荐；或 `~/.qi/settings.yaml`）里：

```yaml
voice:
  enabled: true
  provider: edge-tts
  voice_id: zh-CN-XiaoyiNeural
```

并安装：`pip install "qi[voice]"` 或 `pip install edge-tts`
