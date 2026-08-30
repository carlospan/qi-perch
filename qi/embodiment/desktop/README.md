# 栖 · 桌面端（Vue3 + Tauri 2）

透明无边框窗（**1280×800** 横屏）；**方案 C 单窗融合**——相处页左侧 **3D VRM**，右侧对话；**不再默认弹出桌宠窗**。前端连本机 WebSocket `ws://127.0.0.1:9527`。

**聊天壳四栏**

| Tab | 内容 |
|-----|------|
| 相处（默认） | 左：VRM 半身 idle + 表情；右：对话时间线 + 输入条 |
| 回顾 | 创作 / 见闻卡片归档可筛 |
| 内在 | 梦 / 独白等日记（`/journal`） |
| 状态 | 六维心境（自然语言 + 数值） |

开发期：`npm run tauri:dev` 会按优先级拉起大脑——① 9527 已在听则沿用；② 若已打过 bundled `qi-brain`（见下）则起它；③ 否则 `python -m qi`。设 `QI_SKIP_BRAIN=1` 可关掉自动拉起。

**正式 sidecar（Windows）**：仓库根执行 `python tools/build_qi_brain.py`，产物进 `src-tauri/resources/qi-brain/`；再 `npm run tauri:dev` / `tauri:build`。安装布局下用户不必自装 Python。

## VRM 形象（相处页）

把形象放到 `qi/embodiment/assets/qi-avatar.vrm`。`npm run dev` / `build` 会同步到 `public/avatars/`（该副本不入库）。

**表情**：接 `state.avatar_state.expression`（含 custom：`soft_smile` / `quiet` / `sleepy` / `curious` 等）。  
**互动**：点击看向你 + 微晃；`speech` / `typing` 轻 notice。  
**待机**：场景内 idle（无屏幕漫游、无双窗桌宠）。

`pet.html` 仍可通过 `http://localhost:5173/pet.html` 单独调试桌宠，**非产品入口**。

## 启动

```bash
cd qi/embodiment/desktop
npm install
npm run tauri:dev
```

仅浏览器调试：

```bash
npm run dev
```

打开 http://localhost:5173

打包：`npm run tauri:build` → `src-tauri/target/release/`。

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
