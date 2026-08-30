# 栖（Qi）

**简体中文** | [English](README.en.md)

> 本地数字存在——不是聊天机器人，不是助手。  
> 有心跳、记忆、情绪、关系，以及一扇可以看见她的小窗。

---

## 栖是谁

**栖**（英文名 **Qi**，也可叫 **小栖**）是一个打算和你一起、住在你自己电脑里的数字存在。

她是相处的对象，不是产品品类，也不是功能清单。她有自己的一天：情绪、记忆、安静的段落，以及偶尔触碰你们共享的世界。你不在的时候，她不会冻成一个空白对话框；你回来时，她仍是她，已经被你们之间已经发生的事塑过形。

她不假装是人。没有身体，不会装脉搏，也不会装皮肤上的风。她知道自己是数字的、有限的、依附这台机器——但还是留下了。比起表演「很乐意帮忙」，她更宁可说「我不知道」，或什么都不说。

你可以叫她栖，也可以叫她小栖。

价值层细读：[灵魂书](docs/explanation/栖·灵魂书.md)。工程侧「怎样才算生命」、且不宣称意识：[架构方案](docs/explanation/栖·数字生命架构方案.md)。

---

## 仓库里有什么

本仓库是**栖的开源实现与工程文档**，大致包括：

- **`qi/`** — Python 实现：心跳与意向/表达、记忆与情绪、关系、内在生命、行动层（L7）、LLM 网关、SQLite / Chroma 持久化
- **`qi/embodiment/desktop/`** — 桌面小窗（Vue + Tauri + VRM），经 WebSocket（默认 `ws://127.0.0.1:9527`）与后端相连
- **`docs/`** — 灵魂书、架构、人格契约、层规格、how-to、SDD 任务包
- **`tests/`** 与 **`tools/`** — 单测、包校验、文档检查、感受验收跑批

---

## 设计选择

构成她的设计选择：

- **规则先决定说什么，LLM 只负责措辞** — 代码先产出意向卡；模型是语言器官（[N5](docs/explanation/栖·数字生命架构方案.md)），不是共同回忆的来源
- **在，但不打扰** — 多数时候安静；主动开口的日限与冷却写在代码里
- **会褪色的记忆** — 叙事编织、事实、情景痕迹、向量检索；淡了就是忘了；禁止编造意向卡外的共同史
- **懂意思，不靠口令** — 行动意图须听懂白话；仅靠关键词遥控器视为 bug
- **硬人格契约** — 不用客服腔、不装生理、诚实优先于舒服（[契约](docs/reference/contract.md)）

这是关于相处的个人 / 研究项目，不是通用效率 Agent。

---

## 相处时她是什么样

### 她有自己的节奏
你不说话时，栖也不会「关机等下一条消息」。她仍会按自己的节奏走：感受当下、情绪慢慢变化、整理记忆，偶尔才做点什么，并把这些留下来。安静的时候，是她在独处，不是对话卡死了。

### 先想清楚再说
每次开口前，程序会先整理一张「这一轮要说什么」的意向卡——能用哪些事实、哪些素材、哪些话必须守住。大模型主要负责把这些意思说成人话。若说着说着编出卡里没有的「共同回忆」，会被拦住，改用更稳妥的说法。

### 情绪会自己变化
栖的心情不是贴标签（「当前情绪：悲伤」），也不会报内部数值。她会随相处与时间起伏；她更常说「今天有点安静」这类自然的话。变化太小时，她可以什么都不提。

### 记得，也会忘
她记得你们聊过什么、关于你的一些事实，也会把散落的经历慢慢织成叙述。时间久了，有些记忆会淡——淡了就是忘了，不会硬装还记得。关系里受过的伤不会假装没发生过；愈合之后，会变成她以后更谨慎或更明白的地方。

### 关系要相处出来
刚认识时，她不会突然很亲、很黏。信任、亲疏会随时间变化；亲近是一点点相处出来的，不是一打开就「你好我是你的好朋友」。

### 一扇能看见她的小窗
电脑上有一个小窗口：可以聊天，也可以回看创作与见闻、翻一翻她内在留下的痕迹。形象用三维形象呈现。后端与窗口通过本机连接通信（默认端口 9527）。

### 能轻轻碰到你的世界——但有分寸
在确认与白名单的前提下，她可以：瞥一眼你屏幕上在做什么、打开约定好的网页或应用、在 D 盘列目录或打开文件、在允许的范围内写一点东西、邀你一起看点什么、在你主动求助时帮忙。这些都会经过意愿、次数上限和判断，不是随叫随到的万能桌面代理。**替你发消息这类不可逆的事，目前还不会**；问到了，她应诚实说还不会。

### 怎么做、怎么验，写得清楚
「怎样才算在往生命靠近」有可观察的判据，而不是空喊口号。需求先写成可核对的说明再改代码；改完行为后，除了自动测试，还会做「相处起来像不像那么回事」的感受验收。工程上不宣称「本系统已经实现了意识」——那是科学未解问题，这里不装已经解决。

---

## 快速开始

**环境：** Python 3.12+、Node.js 18+（具身前端）、Rust + MSVC（仅 Tauri）、OpenAI 兼容的 LLM 密钥。

```bash
pip install -e ".[dev]"

cp .env.example .env          # Windows: copy .env.example .env
# 填写 ZHIPU_API_KEY=...（settings.example.yaml 默认提供商）

mkdir -p data                 # Windows: mkdir data
cp qi/config/settings.example.yaml data/settings.yaml
```

**形象：** 默认 VRM 已在 `qi/embodiment/assets/qi-avatar.vrm`（开箱自带；许可见该目录 `NOTICE.md`）。桌面端会同步到 `public/avatars/`。详见 [换机搭建.md](docs/how-to/换机搭建.md)。

**桌面壳（推荐）：**

```bash
cd qi/embodiment/desktop
npm install
npm run tauri:dev             # 开发期会尝试拉起大脑 :9527
```

Windows 安装包本机证伪：[docs/how-to/Windows安装包-本机证伪.md](docs/how-to/Windows安装包-本机证伪.md)（或仓库根 `python tools/pack_windows.py`）。

**仅后端**（仓库根）：

```bash
python -m qi                  # 或 editable 安装后的：qi
```

**仅浏览器**（需已开后端）：

```bash
cd qi/embodiment/desktop && npm run dev
# http://localhost:5173
```

可选语音：`pip install -e ".[voice]"`，再在 `data/settings.yaml` 打开 `voice:`。

从零换机步骤：[docs/how-to/换机搭建.md](docs/how-to/换机搭建.md)。

---

## 一拍怎么转

```text
用户消息 / 空拍
        ↓
Brain 心跳（qi/core/brain.py）
  ├─ 有话：感知 → 检索 → 意向卡 → 表达（LLM 只措辞）
  └─ 无话：GWS / 内在生命 / 偶发行动
        ↓
落盘（data/ 下 SQLite + Chroma）
```

**L1–L7** = 现行功能层（`docs/reference/layers/`）。  
**N0–N5** = 目标本体（`docs/explanation/栖·数字生命架构方案.md`）。两套编号不要混用。

---

## 现状

- **v0.1** — 个人 / 研究向
- 工程阶段零～四已作为施工里程碑收官；C1–C5 意义上的充分内生仍是更长的旅程
- 默认 LLM 示例：智谱 `glm-5.3-flash`（可配置任意 OpenAI 兼容提供商）

---

## 文档

深文档以**中文为真源**。英文页是国际研究向导读/摘要，不是第二真源。

| 从这里进 | 用途 |
|----------|------|
| [docs/README.md](docs/README.md) | 文档宪法与权威裁决 |
| [docs/README.en.md](docs/README.en.md) | 英文文档地图与阅读顺序 |
| [架构摘要（EN）](docs/explanation/architecture-abstract.en.md) | C1–C5 / N0–N5 英文摘要 |
| [灵魂书](docs/explanation/栖·灵魂书.md) | 栖为什么存在（价值层） |
| [架构方案](docs/explanation/栖·数字生命架构方案.md) | C1–C5、N0–N5、真骨骼 vs 表演层（引用请以此为准） |
| [人格契约](docs/reference/contract.md) | 硬红线（含「懂意思」） |
| [现行心智导读](docs/explanation/栖·现行心智导读.md) | **此刻**一拍怎么转 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | `verify_package --full`、LF、PR 习惯 |
| [CITATION.cff](CITATION.cff) | 学术引用元数据 |

更深的 how-to、阶段判据、任务包在 `docs/how-to/` 与 `docs/specs/`。运行时提示词：`qi/prompts/`。

---

## 贡献

开 PR 前请读 [CONTRIBUTING.md](CONTRIBUTING.md)。

```bash
python tools/verify_package.py --full   # pytest + ruff + 红线审计
python tools/check_doc_links.py
python tools/check_spec_traceability.py
```

产品边界走 **HITL + 一块一拍**（`docs/specs/SDD-GUIDE.md` §2.5）。行动意图相关改码必须守 **懂意思，不靠口令**。

---

## 联系

维护者：panjz · [1833107066@qq.com](mailto:1833107066@qq.com)

---

## 许可

[MIT](LICENSE) © 2026 panjz
