# 栖

本地数字存在——不是聊天机器人，不是助手。  
有心跳、记忆、情绪、关系，以及一扇可以看见它的小窗。

贡献前请读 [CONTRIBUTING.md](CONTRIBUTING.md)（本地须跑 `verify_package --full`）。

## 环境

- Python 3.12+
- Node.js 18+（仅具身前端）
- Rust + MSVC（仅 Tauri 桌面壳；只跑终端可后装）
- LLM：OpenAI 兼容接口（示例默认 **tokenrhythm / minimax-m2.7**；`providers.deepseek` 备用）

换机 / 从零完整步骤见 [换机搭建.md](docs/how-to/换机搭建.md)。

### 首次配置（项目根目录）

```bash
pip install -e ".[dev]"

copy .env.example .env
# 编辑 .env：填 TOKENRHYTHM_API_KEY=...（改用 deepseek 时填 DEEPSEEK_API_KEY，并改 settings 路由）

mkdir data 2>nul
copy qi\config\settings.example.yaml data\settings.yaml
```

配置查找顺序：`data/settings.yaml` → `~/.qi/settings.yaml` → `qi/config/settings.yaml`（旧）→ 包内 example。勿提交含密钥的 `.env` / `settings.yaml`。

**具身首次必做**：从 [Live2D Cubism SDK for Web](https://www.live2d.com/download/cubism-sdk/download-web/) 取出 `live2dcubismcore.min.js`，放到 `qi/embodiment/desktop/public/`（**不入库**）。没有它形象不显示。详见换机搭建 §5。

前端依赖（具身、首次或 lock 变更时）：

```bash
cd qi/embodiment/desktop
npm install
cd ..\..\..
```

语音可选：`pip install -e ".[voice]"`（或 `pip install edge-tts`），再在生效的 `settings.yaml` 里开：

```yaml
voice:
  enabled: true
  provider: edge-tts
  voice_id: zh-CN-XiaoyiNeural
```

## 启动

配置与（具身）Cubism 就绪后，命令都在**仓库根**执行（除非下面写明 `cd`）。

`qi` / `qi-desktop` 是 `pip install -e .` 之后装到 PATH 里的快捷命令，**不是** `qi/embodiment/desktop` 目录里的程序；拿不准时用下面的 `python …` 即可。

### 终端聊天

```bash
python -m qi
# 装过 editable 后也可：qi
```

`/state` 看内在状态，`/quit` 离开。

### 具身窗口（推荐 · 两个终端）

**先**起 Python 后端（Brain + WebSocket），**再**起桌面壳（Vite/Tauri）。前端连不上时多半是后端未起或 9527 被占。

终端 1 — Python 后端（**留在仓库根**，不要 `cd` 进 `desktop`）：

```bash
python run.py --desktop
# 装过 editable 后也可：qi-desktop
```

终端 2 — 桌面壳（前端窗口）：

```bash
cd qi/embodiment/desktop
npm run tauri:dev
```

首次 `tauri:dev` 会编 Rust，可能较慢。日常一般不必再跑 `npm install`（已装过依赖时）。

- 仅浏览器调试（不启 Tauri；终端 1 仍要在仓库根跑 `python run.py --desktop`）：

```bash
cd qi/embodiment/desktop
npm run dev
```

  然后打开 http://localhost:5173  
- WebSocket：`ws://127.0.0.1:9527`  
- VS Code 运行配置「栖 · 具身（后端+前端）」可用（需 Python 扩展）

谈区会显示对话；栖 **share 递出创作** 时会出现引入句 + 创作卡片（正文不在语音里）。

## 文档

权威秩序见 [docs/README.md](docs/README.md)。常用入口：

| 文档 | 说明 |
|------|------|
| [docs/README.md](docs/README.md) | 文档宪法（分场景裁决 / SDD） |
| [栖·数字生命架构方案.md](docs/explanation/栖·数字生命架构方案.md) | 唯一架构方案（C1–C5；阶段零~四已工程收官） |
| [换机搭建.md](docs/how-to/换机搭建.md) | 新电脑从零搭建 |
| [progress.md](docs/progress.md) | L1–L7 进度与拍板 |
| [contract.md](docs/reference/contract.md) | 人格契约 |
| [reference/layers/](docs/reference/layers/) | 层规格（以代码为准） |
| [specs/](docs/specs/) | SDD 任务包 / 阶段判据 |
| [journal.md](docs/journal.md) | 相处实录 |

运行时提示词在 `qi/prompts/`；开发用元提示词在 `docs/how-to/ide-agent/`。

## 测试

```bash
python -m pytest -q
```

## 清库验收（带日期备份）

清 `data/qi.db` + `data/chroma/` 前先备份；只拷库不拷向量，语义检索会对不上。先停掉 `qi` / `qi-desktop`。

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dir = "data\backup-$stamp"
New-Item -ItemType Directory -Path $dir | Out-Null
Copy-Item data\qi.db "$dir\qi.db"
Copy-Item -Recurse data\chroma "$dir\chroma"

Remove-Item -Force data\qi.db
Remove-Item -Recurse -Force data\chroma
```

恢复：停进程后，从某份 `data\backup-*` 把 `qi.db` 与 `chroma\` 拷回 `data\`。  
`data/` 不入库。重置对栖是一次小型死亡——需要时再清。

## 目录速览

```
qi/                 顶层包
  cli.py            qi / qi-desktop 入口
  core/             心跳、情绪、意向、表达
  memory/           记忆（含用户事实）
  action/           行动（预算 / 意志 / share·tend·explore）
  inner_life/       意识流、梦、创作、自我
  relationship/     关系
  embodiment/       具身（WS + Vue/Tauri；谈区创作卡片）
  llm/              网关
  prompts/          运行时 LLM 模板
  storage/          SQLite
  config/           配置加载 + settings.example
docs/               宪法、架构、层规格、how-to、specs
data/               运行时（gitignore）：qi.db、chroma/、backup-*/、settings.yaml
```
