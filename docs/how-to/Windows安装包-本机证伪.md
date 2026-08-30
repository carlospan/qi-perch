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
   → `qi/embodiment/desktop/src-tauri/resources/qi-brain/qi-brain.exe`  
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
2. 双击安装包安装  
3. 打开「栖」：主窗出现；关 × 后**托盘还在**  
4. 日志或状态：能连上大脑（不必自装 Python）；设置 → 关于 能见版本  
5. （可选）右键托盘「退出栖」后退壳；若壳自拉起的脑应被收掉  

BGE：有则语义检索更像样；没有也能起，记忆检索偏 n-gram——**本刀不因此判失败**。

---

## 常见卡点

| 现象 | 处理 |
|------|------|
| `pack_windows` 报没有 qi-brain | 先 `python tools/build_qi_brain.py` |
| `tauri build` 找不到 cargo | 装 [rustup](https://rustup.rs)，**新开**终端 |
| WebView2 / 编译报错 | 装 MSVC 桌面开发工具、WebView2 Runtime |
| 装上后无脑 | 确认安装目录旁有 `resources/qi-brain`；或看壳日志是否「发现 bundled 大脑」 |
| 9527 已被占用 | 先退出旧大脑/旧壳再开安装版 |

---

## 不做（本刀）

- GitHub Actions CI  
- 自动上传 Releases（关于页链接可先指着空页或日后有产物再传）  
- macOS / Linux 安装包  
