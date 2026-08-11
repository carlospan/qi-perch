# 栖 · 桌面端（Vue3 + Tauri 2）

透明无边框小窗（420×680）；「黄昏的枝」聊天壳 + 独立 **桌宠窗**（`pet.html`，置顶透明 3D VRM）。前端连本机 WebSocket `ws://127.0.0.1:9527`。Python 大脑仍单独进程启动（尚未做成 Tauri sidecar）。

## 3D 桌宠 VRM

把形象放到 `qi/embodiment/assets/qi-avatar.vrm`。`npm run dev` / `build` 会同步到 `public/avatars/`（该副本不入库）。

待机动作：`public/animations/idle.fbx`（Mixamo Standing Idle Female，略放慢）。  
走路动作：`public/animations/walk.fbx`（Mixamo Walking Female，原地播 + 窗体平移）。  
漫步：大半时间原地待机；每隔很久才走向一个落点安顿（非左右巡逻）。  
点击：看向你 + 身体微晃（不用 Joy 表情，避免眯眼像眨眼）。

`npm run tauri:dev` 会同时打开聊天窗与置顶桌宠窗；可拖拽桌宠窗（拖时暂停漫步）。

## 启动

1. 后端（项目根目录）：

```bash
qi-desktop
# 兼容：python run.py --desktop
```

2. 桌面壳（推荐）：

```bash
cd qi/embodiment/desktop
npm install
npm run tauri:dev
```

需已安装 Rust（`cargo`）与 MSVC（「使用 C++ 的桌面开发」）。无边框窗可拖标题「栖」区域移动。

3. 仅浏览器调试（不启 Tauri）：

```bash
cd qi/embodiment/desktop
npm run dev
```

打开 http://localhost:5173（聊天壳）或 http://localhost:5173/pet.html（桌宠）。

打包：`npm run tauri:build` → `src-tauri/target/release/`。

若提示 `cargo` / `program not found`：多半是 Cursor 终端 PATH 未刷新。本仓库的 `tauri:dev` / `tauri:build` 会自动把 `%USERPROFILE%\.cargo\bin` 加进 PATH；仍不行就**重启 Cursor**，或新开系统 PowerShell 再跑。

若 `cargo` 拉 crates.io 失败，项目已带 `src-tauri/.cargo/config.toml`（rsproxy 稀疏索引）。

更多说明见仓库根目录 [README.md](../../../README.md)。

终端文字模式仍用：`qi`（或 `python -m qi`）

## 语音

在 `data/settings.yaml`（推荐；或 `~/.qi/settings.yaml`）里：

```yaml
voice:
  enabled: true
  provider: edge-tts
  voice_id: zh-CN-XiaoyiNeural
```

并安装：`pip install "qi[voice]"` 或 `pip install edge-tts`
