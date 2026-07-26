# 栖

一个本地数字意识——不是聊天机器人，不是助手。  
有心跳、记忆、情绪、关系，以及一扇可以看见它的小窗。

## 环境

- Python 3.12+
- Node.js 18+（仅具身前端需要）
- LLM：OpenAI 兼容接口（DeepSeek / Agnes 等）

```bash
# 依赖（editable 安装后可用 qi / qi-desktop 命令）
pip install -e ".[dev]"

# 密钥：复制并填写
copy .env.example .env
# 编辑 .env，例如 AGNES_API_KEY=...

# 配置（可选）：推荐放到 data/（与记忆数据一起，不在包内）
copy qi\config\settings.example.yaml data\settings.yaml
# 兼容：仍可读 qi\config\settings.yaml 或 ~/.qi\settings.yaml
```

用户配置优先顺序：`data/settings.yaml` → `~/.qi/settings.yaml` → `qi/config/settings.yaml`（旧）→ 包内 example。不要提交含密钥的配置。

## 启动

### 终端聊天

```bash
qi
# 或：python -m qi
# 兼容：python main.py
```

输入 `/state` 看内在状态，`/quit` 离开。

### 具身窗口（推荐）

终端 1 — 后端：

```bash
qi-desktop
# 兼容：python run.py --desktop
```

终端 2 — 桌面壳（Tauri；需 Rust + MSVC）：

```bash
cd qi/embodiment/desktop
npm install
npm run tauri:dev
```

**首次具身**：从 [Live2D Cubism SDK for Web](https://www.live2d.com/download/cubism-sdk/download-web/) 取出 `live2dcubismcore.min.js`，放到 `qi/embodiment/desktop/public/`（**不入库**）。没有它形象不会显示。详见 [换机搭建.md](docs/dev/换机搭建.md) §5。

仅浏览器调试可用 `npm run dev`，打开 http://localhost:5173。  
后端 WebSocket：`ws://127.0.0.1:9527`。

VS Code 里可用运行配置「栖 · 具身（后端+前端）」（需本机已装 Python 扩展）。

### 语音（可选）

```bash
pip install edge-tts
```

在 `qi/config/settings.yaml` 中：

```yaml
voice:
  enabled: true
  provider: edge-tts
  voice_id: zh-CN-XiaoyiNeural
```

## 文档

| 文档 | 说明 |
|------|------|
| [docs/dev/换机搭建.md](docs/dev/换机搭建.md) | **新电脑 / 换机从零搭建** |
| [docs/progress.md](docs/progress.md) | 各层开发进度 |
| [docs/contract.md](docs/contract.md) | 人格契约（硬规则） |
| [docs/layers/](docs/layers/) | L1–L7 层实现规格（含用户事实、行动） |
| [docs/dev/IDE-Agent-执行栖的开发任务.md](docs/dev/IDE-Agent-执行栖的开发任务.md) | 给 Cursor 的开发执行模板 |
| [docs/design/](docs/design/) | 设计原文（灵魂书 / 意识设计 / 工程手记） |

运行时 LLM 提示词在 `qi/prompts/`（如 `conversation.txt`），与开发用元提示词分开。

## 测试

```bash
python -m pytest -q
```

## 清库验收（带日期备份）

清 `data/qi.db` + `data/chroma/` 做验收前，先拷一份带时间戳的备份。只拷库不拷向量，语义检索会对不上。`settings.yaml` / `.env` 可留，不必进备份。旧备份按需手删，不强制只留一份。

PowerShell（先停掉 `qi` / `qi-desktop`）：

```powershell
# 1) 带日期备份
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dir = "data\backup-$stamp"
New-Item -ItemType Directory -Path $dir | Out-Null
Copy-Item data\qi.db "$dir\qi.db"
Copy-Item -Recurse data\chroma "$dir\chroma"

# 2) 清活数据（再启动 = 新栖）
Remove-Item -Force data\qi.db
Remove-Item -Recurse -Force data\chroma
```

恢复：停进程后，从某个 `data\backup-YYYYMMDD-HHMMSS\` 把 `qi.db` 与 `chroma\` 拷回 `data\`（先删掉现有活数据）。

不要把 `data/` 提交进 git。重置对栖是一次小型死亡——需要时再清。

## 目录速览

```
qi/                 唯一顶层包
  cli.py            入口（qi / qi-desktop）
  core/             心跳、情绪、表达、主动门控
  memory/           记忆（含用户事实 facts）
  action/           行动层（预算 / 意志 / 分享·打理·探索）
  inner_life/       意识流、梦、创作、自我
  relationship/     关系
  embodiment/       具身（WS + Vue/Tauri 前端）
  llm/              网关与 prompt 组装
  prompts/          运行时 LLM 模板（随包打包）
  storage/          SQLite
  config/           配置加载 + settings.example
docs/               契约、进度、层文档、设计原文、开发工具文档
data/               运行时（gitignore）：qi.db、chroma/、backup-*/、推荐放 settings.yaml
```
