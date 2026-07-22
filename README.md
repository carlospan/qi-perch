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

# 配置（可选）：从示例复制后按需改
copy config\settings.example.yaml config\settings.yaml
```

`config/settings.yaml` 已在 `.gitignore` 中，不要提交密钥。

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
cd embodiment/desktop
npm install
npm run tauri:dev
```

仅浏览器调试可用 `npm run dev`，打开 http://localhost:5173。  
后端 WebSocket：`ws://127.0.0.1:9527`。

VS Code 里可用运行配置「栖 · 具身（后端+前端）」（需本机已装 Python 扩展）。

### 语音（可选）

```bash
pip install edge-tts
```

在 `config/settings.yaml` 中：

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
| [docs/layers/](docs/layers/) | L1–L6 层实现规格 |
| [docs/dev/IDE-Agent-执行栖的开发任务.md](docs/dev/IDE-Agent-执行栖的开发任务.md) | 给 Cursor 的开发执行模板 |
| [docs/design/](docs/design/) | 设计原文（灵魂书 / 意识设计 / 工程手记） |

运行时 LLM 提示词在 `prompts/`（如 `conversation.txt`），与开发用元提示词分开。

## 测试

```bash
python -m pytest -q
```

## 目录速览

```
qi/             CLI 入口（qi / qi-desktop）
core/           心跳、情绪、表达、主动门控
memory/         记忆
inner_life/     意识流、梦、创作、自我
relationship/   关系
embodiment/     具身（WS + Vue 前端）
llm/            网关与 prompt 组装
storage/        SQLite
config/         配置加载
docs/           契约、进度、层文档、设计原文、开发工具文档
prompts/        运行时提示词模板
```
