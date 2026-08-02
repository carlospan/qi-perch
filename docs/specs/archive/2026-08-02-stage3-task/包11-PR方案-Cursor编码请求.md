# 包 11 实施 PR 方案 · Cursor 编码请求

> **用途**：供 Cursor 自行读取并落地编码（**Cursor 直接读 `docs/specs/` 下对应文件即可，无需人工转发**；方案 Agent 只出方案，不写 `qi/` 实现）。  
> **分工纪律（不可混淆）**：本文件是「执行侧」请求——**只由 Cursor 写实现代码，方案 Agent 不在此文件范围内敲 `qi/` 代码**。若方案 Agent 误把"起草 PR"写成直接出实现，属于越界，应退回只出方案（此失误已发生过，故特此强调）。  
> **依据**：`specs/tasks/2026-08-02-阶段三-包11-PR方案.md`（PR 方案，含精确改动点）、`specs/tasks/2026-08-02-阶段三-主线.md`（v2 包 11 段）、现有代码（`qi/core/trace.py` / `qi/storage/database.py` 的 `broadcast_traces` / `qi/core/brain.py` / `.gitignore`）。  
> **撰写**：CodeBuddy（2026-08-02）  
> **协作分工**：方案 Agent 出方案/验收，Cursor 固定执行编码（详见 `specs/SDD-GUIDE.md` 第二节）。

---

## 请求

包 11 的实施 PR 方案已写好：`specs/tasks/2026-08-02-阶段三-包11-PR方案.md`（同目录本文件即编码请求，你直接读取即可，无需人工转发）。

请你**据此落地编码**，并遵守方案里的纪律红线，核心交付：

1. **新增 `qi/learning/replay.py`**（`ReplayBuffer`：从 `broadcast_traces` 按 salience 筛选高价值拍 → `to_samples` 结构化样本；`run_training(dry_run=True)` 默认隔离）。
2. **新增 `qi/learning/corpus.py`**（`CorpusStore`：样本落盘 `data/corpus/corpus_{tag}_{ts}.jsonl`，可版本化、可 diff）。
3. **异时测试骨架**：新增 `tools/replay_drift_check.py`（或 `qi/learning/drift_check.py`），读两版语料跑差异摘要，不训也能跑。
4. **`.gitignore`** 显式补 `data/corpus/`。
5. **新增 `tests/test_replay.py`**，参照 `tests/test_trace.py` 的 db 用法（内存 `Database`）；跑 `pytest` + `ruff check qi tests` 全绿再落盘回执。

### 纪律红线（务必守住）

1. **不**改 `broadcast_traces` 写入逻辑（包 6 地基）；本包只读它。
2. **零新依赖**：语料生成纯 Python（json / 文件 IO）；训练分支仅占位不 import 重依赖。
3. **训练默认隔离**：`run_training()` 默认 `dry_run=True`；心跳/CI **不调用**它。
4. **不破坏现有行为**：新增模块，现有心跳/记忆/动机路径不变。
5. **拔管安全**：`collect_candidates` / `to_samples` 不依赖 LLM（fake-provider 下可用）。

方案已给出每处精确改动点与代码片段骨架，直接照做即可。若发现方案与实际代码有出入（如 `Database` 临时目录用法、`broadcast_traces` 字段名），以**不破坏现有行为**为前提自行适配，并在回执里说明偏离点。

---

## 回复交付要求

请**将编码结果写成独立文档**，存为：

```
docs/specs/archive/2026-08-02-stage3-task/包11-PR方案-Cursor编码回执.md
```

文档结构建议（**一次落盘，两段式**）：
- **【开工前理解确认段】**（动手改代码前写）：确认已读取 PR 方案；逐条列出对关键改动点（`replay.py` / `corpus.py` / 异时骨架 / `.gitignore`）的理解；标注任何拿不准或需澄清处。写完即继续写码，**不阻塞等待方案 Agent 回复**。
- **【完工结果段】**（写码完成后写）：落地摘要（新增/改了哪些文件）；是否 100% 照方案、偏离点；测试结果（`pytest` / `ruff` 实际输出摘要）；自查纪律红线 1–5；交回方案 Agent 做实施验收的建议（含 #1-真通过 HITL 提示）。

**不要只在对话里贴结论文字**——过程稿须落盘为文件（本项目固定纪律）。写完后告知文档路径。

**验收归属**：Cursor 落盘回执后，由**方案 Agent（CodeBuddy 等）读取回执并执行实施验收**（核对纪律红线与验收清单），**维护者不直接检查代码**；维护者仅在 HITL 批点（含判据 #1-真通过路径）时才介入。

---

*CodeBuddy 编码请求 · 包 11 · 2026-08-02*
