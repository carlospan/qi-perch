# 包 9b 实施 PR 方案 · Cursor 编码请求

> **用途**：供 Cursor 自行读取并落地编码（**Cursor 直接读 `docs/specs/` 下对应文件即可，无需人工转发**；方案 Agent 只出方案，不写 `qi/` 实现）。  
> **分工纪律（不可混淆）**：本文件是「执行侧」请求——**只由 Cursor 写实现代码，方案 Agent 不在此文件范围内敲 `qi/` 代码**。若方案 Agent 误把"起草 PR"写成直接出实现，属于越界，应退回只出方案（此失误已发生过，故特此强调）。  
> **依据**：`specs/tasks/2026-08-02-阶段三-包9b-PR方案.md`（PR 方案，含精确改动点）、`specs/tasks/2026-08-02-阶段三-主线.md`（v2 包 9b 段）、现有代码（`qi/world/model.py` / `qi/core/emotion.py` / `qi/core/brain.py` / `qi/core/trace.py` / `qi/storage/database.py`）。  
> **撰写**：CodeBuddy（2026-08-02）  
> **协作分工**：方案 Agent 出方案/验收，Cursor 固定执行编码（详见 `specs/SDD-GUIDE.md` 第二节）。

---

## 请求

包 9b 的实施 PR 方案已写好：`specs/tasks/2026-08-02-阶段三-包9b-PR方案.md`（同目录本文件即编码请求，你直接读取即可，无需人工转发）。

请你**据此落地编码**，并遵守方案里的纪律红线，核心交付：

1. **新增 `qi/world/emotion_trajectory.py`**（`EmotionTrajectory`：以 `brain.emotion` 六维为预测域，维护近期 delta 分布，预测下一拍走向，实际 delta 与预测不符 → surprise；复用 `body_memory` key=`world.emotion_trajectory`）。
2. **改 `qi/world/model.py`**：`WorldModel.__init__` 挂 `emotion_trajectory` 入 `domains`；`update` 调其 `record`；`snapshot` 并入 `emotion_trajectory` 子域。
3. **`qi/core/trace.py`**：`motive_snapshot` 增 `emotion_trajectory_surprise`（独立字段，不污染 world_surprise）。
4. **新增 `tests/test_world_emotion_trajectory.py`**，参照 `tests/test_trace.py` 的 Brain/StubLLM 用法；跑 `pytest` + `ruff check qi tests` 全绿再落盘回执。

### 纪律红线（务必守住）

1. **不**改 `emotion.py` 演化逻辑（step_emotion / mood_cycle / circadian）；只读取 `brain.emotion` 观测。
2. **不**接 GWS 竞争者；情绪轨迹 surprise 仅作旁路信号。
3. **零新依赖**：后验手算（math）；不引 torch/transformers。
4. **不**新建表；复用 `body_memory`（key=`world.emotion_trajectory`）。
5. **拔管安全**：`record` 不依赖 LLM（fake-provider 全失败仍推进）。

方案已给出每处精确改动点与代码片段骨架，直接照做即可。若发现方案与实际代码有出入（如 `Brain` 构造、`emotion` 字段读取方式），以**不破坏现有行为**为前提自行适配，并在回执里说明偏离点。

---

## 回复交付要求

请**将编码结果写成独立文档**，存为：

```
docs/specs/archive/2026-08-02-stage3-task/包9b-PR方案-Cursor编码回执.md
```

文档结构建议（**一次落盘，两段式**）：
- **【开工前理解确认段】**（动手改代码前写）：确认已读取 PR 方案；逐条列出对关键改动点（`emotion_trajectory.py` / `model.py` 挂域 / `trace` 注入）的理解；标注任何拿不准或需澄清处。写完即继续写码，**不阻塞等待方案 Agent 回复**。
- **【完工结果段】**（写码完成后写）：落地摘要（新增/改了哪些文件）；是否 100% 照方案、偏离点；测试结果（`pytest` / `ruff` 实际输出摘要）；自查纪律红线 1–5；交回方案 Agent 做实施验收的建议。

**不要只在对话里贴结论文字**——过程稿须落盘为文件（本项目固定纪律）。写完后告知文档路径。

**验收归属**：Cursor 落盘回执后，由**方案 Agent（CodeBuddy 等）读取回执并执行实施验收**（核对纪律红线与验收清单），**维护者不直接检查代码**；维护者仅在 HITL 批点时才介入（本包为观察项，无硬拍板项）。

---

*CodeBuddy 编码请求 · 包 9b · 2026-08-02*
