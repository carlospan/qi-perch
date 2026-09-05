# 栖 · 桌面端（Vue3 + Tauri 2）

透明无边框窗（**1280×800** 横屏）；**方案 C 单窗融合**——相处页左侧 **3D VRM**，右侧对话；**不再默认弹出桌宠窗**。前端连本机 WebSocket `ws://127.0.0.1:9527`。

**聊天壳四栏**

| Tab | 内容 |
|-----|------|
| 相处（默认） | 左：VRM 半身 idle + 表情；右：对话时间线 + 输入条 |
| 回顾 | 创作 / 见闻卡片归档可筛 |
| 内在 | 梦 / 独白等日记（`/journal`） |
| 状态 | 六维心境（自然语言 + 数值） |

开发期：`npm run tauri:dev` 会按优先级拉起大脑——① 9527 已在听则沿用；② **优先**仓库 `python -m qi`（数据根为仓库 `data/`）；③ 失败再起 bundled `qi-brain`；④ 都没有则报错可见。设 `QI_SKIP_BRAIN=1` 可关掉自动拉起；要强制测安装布局大脑时设 `QI_PREFER_BUNDLED=1`。

**正式 sidecar（Windows）**：仓库根 `python tools/build_qi_brain.py` → onedir（dev/smoke）+ `qi-brain.zip`（安装包）。`tauri:build` 只打 zip；壳首次解压到 `%LOCALAPPDATA%\Qi\runtime\qi-brain\`。安装布局下用户不必自装 Python。

**BGE 离线**：`python tools/fetch_bge_resource.py` → `src-tauri/resources/bge-small-zh-v1.5/`（权重不入库）。运行时数据根有模优先，否则读该资源，皆无则 n-gram。

## VRM 形象（相处页）

**开箱自带**：默认形象在 `qi/embodiment/assets/qi-avatar.vrm`（已入库；许可见同目录 `NOTICE.md`）。`npm run dev` / `build` 会同步到 `public/avatars/`（该副本不入库）。

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

打包：见 [Windows安装包-本机证伪.md](../../../docs/how-to/Windows安装包-本机证伪.md)。仓库根也可：`python tools/pack_windows.py`（需先有 `qi-brain`）。

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
