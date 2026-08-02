# 包 10 实施 PR 方案 · Cursor 编码请求

> **用途**：供 Cursor 自行读取并落地编码（**Cursor 直接读 `docs/specs/` 下对应文件即可，无需人工转发**；方案 Agent 只出方案，不写 `qi/` 实现）。  
> **分工纪律（不可混淆）**：本文件是「执行侧」请求——**只由 Cursor 写实现代码，方案 Agent 不在此文件范围内敲 `qi/` 代码**。若方案 Agent 误把"起草 PR"写成直接出实现，属于越界，应退回只出方案（此失误已发生过，故特此强调）。  
> **依据**：`specs/tasks/2026-08-02-阶段三-包10-PR方案.md`（PR 方案，含精确改动点与审计三栏表）、`specs/tasks/2026-08-02-阶段三-主线.md`（v2 包 10 段）、现有代码（`qi/core/gws.py` / `qi/core/trace.py` / `qi/core/brain.py` / `qi/action/explore.py`（已 curiosity 化）/ `qi/inner_life/dream.py` / `qi/inner_life/creativity.py` / `qi/inner_life/consciousness.py` / `qi/action/layer.py` / `qi/core/emotion.py`）。  
> **撰写**：CodeBuddy（2026-08-02）  
> **协作分工**：方案 Agent 出方案/验收，Cursor 固定执行编码（详见 `specs/SDD-GUIDE.md` 第二节）。

---

## 请求

包 10 的实施 PR 方案已写好：`specs/tasks/2026-08-02-阶段三-包10-PR方案.md`（同目录本文件即编码请求，你直接读取即可，无需人工转发）。

请你**据此落地编码**，并遵守方案里的纪律红线，核心交付：

1. **新增 `qi/motivation/curiosity.py`**（`CuriositySignal`：从 world surprise + open_loop + emotion.curiosity 合成 learning-progress 代理，产出 `Contender(kind="curiosity")`）。
2. **`qi/core/trace.py`**：`salience()` 增 `curiosity` 分支；`collect_contenders` 增 `curiosity` 参数并追加 curiosity 竞争者；`motive_snapshot` 增 `curiosity` 溯源字段。
3. **`qi/core/brain.py`**：`_gws_broadcast` 调用 `CuriositySignal.update` 并把 `curiosity` 传入 `collect_contenders`。
4. **随机动机源 → curiosity 驱动**（按方案审计三栏表）：`dream.maybe_dream` / `consciousness.should_trigger_meta` 的纯随机 WHETHER 改 curiosity；`creativity.maybe_create` 改"好奇或情绪高触发"；**保留**所有时机阀随机（layer L207 / dream shuffle / share choice / brain sleep 抖动 / creativity 提起 0.25）并加注释。
5. **新增 `tests/test_motivation_curiosity.py`**，参照 `tests/test_trace.py` 的 Brain 用法；跑 `pytest` + `ruff check qi tests` 全绿再落盘回执。

### 纪律红线（务必守住）

1. **不**改 `respond` 恒胜（用户消息在队时 curiosity 不压过）。
2. **零新依赖**：learning-progress 用轻量代理，不引 torch/transformers。
3. **保留**所有"时机阀/表达层"随机（仅移除"随机做动机来源"的 WHETHER），改动处加注释。
4. **拔管安全**：`CuriositySignal.update` 不依赖 LLM（fake-provider 全失败仍推进）。

方案已给出每处精确改动点与代码片段骨架，直接照做即可。若发现方案与实际代码有出入（如 `collect_contenders` 其他调用点、`emotion.curiosity` 读取方式），以**不破坏现有行为**为前提自行适配，并在回执里说明偏离点。

---

## 回复交付要求

请**将编码结果写成独立文档**，存为：

```
docs/specs/archive/2026-08-02-stage3-task/包10-PR方案-Cursor编码回执.md
```

文档结构建议（**一次落盘，两段式**）：
- **【开工前理解确认段】**（动手改代码前写）：确认已读取 PR 方案；逐条列出对关键改动点（`curiosity.py` / `trace.collect_contenders` / `brain._gws_broadcast` / 三个随机动机源改造）的理解；标注任何拿不准或需澄清处。写完即继续写码，**不阻塞等待方案 Agent 回复**。
- **【完工结果段】**（写码完成后写）：落地摘要（新增/改了哪些文件）；是否 100% 照方案、偏离点；测试结果（`pytest` / `ruff` 实际输出摘要）；自查纪律红线 1–4；交回方案 Agent 做实施验收的建议。

**不要只在对话里贴结论文字**——过程稿须落盘为文件（本项目固定纪律）。写完后告知文档路径。

**验收归属**：Cursor 落盘回执后，由**方案 Agent（CodeBuddy 等）读取回执并执行实施验收**（核对纪律红线与验收清单），**维护者不直接检查代码**；维护者仅在 HITL 批点时才介入。

---

*CodeBuddy 编码请求 · 包 10 · 2026-08-02*
