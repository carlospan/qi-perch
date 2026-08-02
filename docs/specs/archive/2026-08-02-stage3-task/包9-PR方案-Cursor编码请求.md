# 包 9 实施 PR 方案 · Cursor 编码请求

> **用途**：供 Cursor 自行读取并落地编码（**Cursor 直接读 `docs/specs/` 下对应文件即可，无需人工转发**；方案 Agent 只出方案，不写 `qi/` 实现）。  
> **分工纪律（不可混淆）**：本文件是「执行侧」请求——**只由 Cursor 写实现代码，方案 Agent 不在此文件范围内敲 `qi/` 代码**。若方案 Agent 误把"起草 PR"写成直接出实现，属于越界，应退回只出方案（此失误已发生过一次，故特此强调）。  
> **依据**：`specs/tasks/2026-08-02-阶段三-包9-PR方案.md`（PR 方案，含精确改动点）、`specs/tasks/2026-08-02-阶段三-主线.md`（v2 包 9 段）、现有代码结构（`qi/core/trace.py` / `qi/core/brain.py` / `qi/storage/database.py`）。  
> **撰写**：CodeBuddy（2026-08-02）  
> **纪律**：本文件仅为编码请求，CodeBuddy 未写实现代码。

---

## 请求

包 9 的实施 PR 方案已写好：`specs/tasks/2026-08-02-阶段三-包9-PR方案.md`（同目录下的本文件即编码请求，你直接读取即可，无需人工转发）。

请你**据此落地编码**（新增 `qi/world/online_rhythm.py` + `qi/world/model.py`，改 `qi/core/brain.py` 接入 + `qi/core/trace.py` 注入 `world_surprise`，新增 `tests/test_world_online_rhythm.py`），并遵守方案里的纪律红线：

1. **只增信号**：不接 GWS 竞争者、不改 `proactive`/`explore` 权重（归包 10）。
2. **零新依赖**：贝塔后验手算，复用 `body_memory` 表（key=`world.online_rhythm`），不新建表。
3. **拔管安全**：`world.update` 不依赖 LLM（fake-provider 全失败时仍推进）。
4. **测试**：新增 `tests/test_world_online_rhythm.py`，参照 `tests/test_trace.py` 的 Brain/StubLLM 用法；落库后查 `broadcast_traces.motive_json.world_surprise` 可见。
5. 跑 `pytest` + `ruff check qi tests` 全绿再交回。

方案里已给出每处的精确改动点与代码片段，直接照做即可。若发现方案与实际代码有出入（如 `Brain` 构造、`_heartbeat` 细节），以不破坏现有行为为前提自行适配，并在回复里说明偏离点。

---

## 回复交付要求

请**将编码结果写成独立文档**，存为：

```
docs/specs/archive/2026-08-02-stage3-task/包9-PR方案-Cursor编码回执.md
```

文档结构建议：
- 落地摘要（新增/改了哪些文件）
- 是否 100% 照方案；若有偏离，列偏离点及原因
- 测试结果（`pytest` / `ruff` 实际输出摘要）
- 自查：纪律红线 1–4 是否都守住
- 交回方案 Agent（CodeBuddy / Codex 等）做实施验收的下一步建议

**不要只在对话里贴结论文字**——过程稿须落盘为文件（本项目固定纪律）。写完后告知文档路径。
**验收归属**：Cursor 落盘回执后，由**方案 Agent（CodeBuddy 等）读取回执并执行实施验收**（核对纪律红线与验收清单），**维护者不直接检查代码**；维护者仅在 HITL 批点（如阶段退出、路线决策）时才介入。

---

*CodeBuddy 编码请求 · 包 9 · 2026-08-02*
