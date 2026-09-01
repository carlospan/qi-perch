# Windows 安装包 · 本机证伪

> how-to。对应任务包：  
> - `docs/specs/tasks/2026-08-31-P3-本机安装包证伪.md`（§〇.27）  
> - `docs/specs/tasks/2026-09-01-P3-正式包默认带BGE.md`（§〇.29）  
> **本机证伪 / 正式包装**：在你这台 Windows 上打出安装包。不做 CI。发 Release 另见 §〇.28 / §〇.29。

---

## 你需要什么

- Windows 10/11  
- 已能跑 `npm run tauri:dev` 的环境（Node、Rust、MSVC 桌面工具）  
- 仓库根目录的 Python（打 `qi-brain` / 拉 BGE 用）  
- **正式包**：能访问 HuggingFace 或镜像（拉 BGE，约 91MB）

---

## 一键（正式推荐）

在**仓库根**：

```powershell
# 国内拉 BGE 建议镜像
$env:HF_ENDPOINT="https://hf-mirror.com"

# 若还没有大脑（约数分钟～十几分钟）
python tools/build_qi_brain.py

# 包装：检查资源 → 无 BGE 则自动 fetch → tauri build
python tools/pack_windows.py
```

`pack_windows` **默认须带 BGE**：缺模会自动 `fetch_bge_resource`；fetch 失败则**退出非 0**（不产出假装正式的包）。

无网 / 只要快速编过壳时：

```powershell
python tools/pack_windows.py --skip-bge
```

强制先打脑再包装：

```powershell
python tools/pack_windows.py --build-brain
```

`--with-bge` 仍可用（兼容旧用法；默认已带，可省略）。

---

## 分步（等价）

1. `python tools/build_qi_brain.py`  
   → `…/resources/qi-brain/`（本机 smoke / tauri:dev）  
   → `…/resources/qi-brain.zip`（**安装包只带这一份**）  
2. （正式包）`python tools/fetch_bge_resource.py`  
   → `…/resources/bge-small-zh-v1.5/`（有 `onnx/model.onnx` 等）  
   或交给 `pack_windows` 自动拉  
3. `python tools/pack_windows.py`（或 `cd qi/embodiment/desktop` → `npm run tauri:build`）  

产物一般在：

```text
qi/embodiment/desktop/src-tauri/target/release/bundle/nsis/
```

以目录里最新的安装包为准（如 `qi_0.1.1_x64-setup.exe`）。

---

## 安装后怎么验

1. 关掉本机已在跑的 `python -m qi` / 旧壳（避免端口抢车）  
2. **托盘退出栖**，确认无 `qi.exe` / `qi-brain.exe` 后再装  
3. 双击安装包安装  
4. 打开「栖」：主窗出现；**首次**可能解压大脑到 `%LOCALAPPDATA%\Qi\runtime\qi-brain\`（数十秒属正常）  
5. 关 × 后**托盘还在**；能连上大脑；设置 → 关于 能见版本（正式包应为 0.1.1+）  
6. （可选）右键托盘「退出栖」  

核对大脑：

```powershell
Get-Item "$env:LOCALAPPDATA\Qi\runtime\qi-brain\_internal\numpy\_core\_multiarray_umath*.pyd"
Test-Path "<你的安装目录>\resources\qi-brain.zip"
```

核对 BGE（正式包应有）：

```powershell
Test-Path "<你的安装目录>\resources\bge-small-zh-v1.5\onnx\model.onnx"
```

---

## 常见卡点

| 现象 | 处理 |
|------|------|
| `pack_windows` 报没有 qi-brain / zip | 先 `python tools/build_qi_brain.py`（仅缺 zip：`--zip-only`） |
| `pack_windows` 因 BGE fetch 失败退出 | 直连 HuggingFace 重试；若设了 `HF_ENDPOINT` 镜像异常可先取消该环境变量；或显式 `--skip-bge`（正式发版勿用） |
| `tauri build` 找不到 cargo | 装 [rustup](https://rustup.rs)，**新开**终端 |
| WebView2 / 编译报错 | 装 MSVC 桌面开发工具、WebView2 Runtime |
| 装上后形象全白 / 白模 | 请装含 TextureLoader + `base: './'` 修复的包 |
| 装上后 numpy / `_core` 找不到 | 卸干净；删 `%LOCALAPPDATA%\Qi\runtime\qi-brain` 再开（须 zip 布局包） |
| 退出栖 / 卸载闪黑控制台 | 须含 CREATE_NO_WINDOW / NSIS `SW_HIDE` 的包 |
| 9527 已被占用 | 先退出旧大脑/旧壳 |

---

## 不做

- GitHub Actions CI  
- macOS / Linux 安装包  
