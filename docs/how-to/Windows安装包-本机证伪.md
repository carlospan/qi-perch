# Windows 安装包 · 本机证伪

> how-to。对应任务包 `docs/specs/tasks/2026-08-31-P3-本机安装包证伪.md`（§〇.27）。  
> **本机证伪**：在你这台 Windows 上打出安装包并装一趟。不做 CI、不强制发 GitHub Release。

---

## 你需要什么

- Windows 10/11  
- 已能跑 `npm run tauri:dev` 的环境（Node、Rust、MSVC 桌面工具）  
- 仓库根目录的 Python（打 `qi-brain` 用）

---

## 一键（推荐）

在**仓库根**：

```powershell
# 若还没有 bundled 大脑（约数分钟～十几分钟）
python tools/build_qi_brain.py

# 正式领养包建议带 BGE（约 91MB，需网络；国内可设镜像）
$env:HF_ENDPOINT="https://hf-mirror.com"
python tools/fetch_bge_resource.py

# 包装：检查资源 → tauri build
python tools/pack_windows.py
```

只要打包装、脑已有、BGE 可跳过：

```powershell
python tools/pack_windows.py
```

强制先打脑再包装：

```powershell
python tools/pack_windows.py --build-brain
```

包装前拉 BGE：

```powershell
python tools/pack_windows.py --with-bge
```

---

## 分步（等价）

1. `python tools/build_qi_brain.py`  
   → `…/resources/qi-brain/`（本机 smoke / tauri:dev）  
   → `…/resources/qi-brain.zip`（**安装包只带这一份**，避免 NSIS 逐文件拷半套）  
2. （建议）`python tools/fetch_bge_resource.py`  
   → `…/resources/bge-small-zh-v1.5/`（有 `onnx/model.onnx` 等）  
3. `cd qi/embodiment/desktop` → `npm install`（若未装）→ `npm run tauri:build`  

产物一般在：

```text
qi/embodiment/desktop/src-tauri/target/release/bundle/nsis/
```

或 `bundle/msi/`（视 Tauri 目标而定）。以目录里最新的安装包为准。

---

## 安装后怎么验（关门勾选）

1. 关掉本机已在跑的 `python -m qi` / 旧壳（避免端口抢车）  
2. **托盘退出栖**，任务管理器确认无 `qi.exe` / `qi-brain.exe` 后再装（安装程序也会 taskkill）  
3. 双击安装包安装  
4. 打开「栖」：主窗出现；**首次**可能解压大脑到 `%LOCALAPPDATA%\Qi\runtime\qi-brain\`（数十秒属正常）  
5. 关 × 后**托盘还在**；能连上大脑；设置 → 关于 能见版本  
6. （可选）右键托盘「退出栖」后退壳；若壳自拉起的脑应被收掉  

核对大脑是否落全（装完后）：

```powershell
Get-Item "$env:LOCALAPPDATA\Qi\runtime\qi-brain\_internal\numpy\_core\_multiarray_umath*.pyd"
# 安装目录应有单文件 zip，而不是整棵 _internal：
Test-Path "<你的安装目录>\resources\qi-brain.zip"
```

BGE：有则语义检索更像样；没有也能起，记忆检索偏 n-gram——**本刀不因此判失败**。

---

## 常见卡点

| 现象 | 处理 |
|------|------|
| `pack_windows` 报没有 qi-brain / zip | 先 `python tools/build_qi_brain.py`（仅缺 zip：`--zip-only`） |
| `tauri build` 找不到 cargo | 装 [rustup](https://rustup.rs)，**新开**终端 |
| WebView2 / 编译报错 | 装 MSVC 桌面开发工具、WebView2 Runtime |
| 装上后形象全白 / 白模 | 旧包绝对路径 + WebView2 ImageBitmap 贴图问题；请装含本修复的包（`base: './'` + TextureLoader） |
| 装上后 numpy / `_core` 找不到 | 旧包曾逐文件落半套；请卸干净后装**本版**（zip）；并删 `%LOCALAPPDATA%\Qi\runtime\qi-brain` 再开 |
| 装上后无脑 | 看壳日志是否「发现大脑 zip / 解压」；或 `QI_BRAIN_EXE` |
| 9527 已被占用 | 先退出旧大脑/旧壳再开安装版 |
| 重装仍半套 | 先杀进程再装；本版 hooks 会 taskkill |
| 退出栖闪黑控制台 / 等一会才退 | 退出路径曾**同步**跑裸 `taskkill`（又慢又闪窗）；现改为先 `kill` 主进程、taskkill 后台清树 + CREATE_NO_WINDOW（需重装含此修复的包才验） |
| 卸载/安装闪黑控制台 | NSIS hooks 曾 `ExecWait taskkill`；已改 `ExecShellWait … SW_HIDE`（需重打包安装器才验） |

---

## 不做（本刀）

- GitHub Actions CI  
- 自动上传 Releases（关于页链接可先指着空页或日后有产物再传）  
- macOS / Linux 安装包  
