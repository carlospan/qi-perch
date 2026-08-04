<!-- 现行路径：how-to/ide-agent/IDE-Agent-分析栖最新对话与内部状态.md -->

# 分析栖最新对话与内部状态 · 提示词模板（多 Agent 通用）

> **适用**：任意 Agent（Cursor / CodeBuddy / Codex / GLM / OpenCode / 其他），不绑定某一家。  
> **用途**：维护者高频操作——只读活库，分析**最新一场**对话，并逐轮对照栖的内部状态变化。  
> **不是**：修复方案、编码任务、施工包。默认**不改代码、不改库、不提 PR 方案**（除非用户另行要求）。  
> **数据真源**：仓库根下 `data/qi.db`（情绪 / 消息 / 关系 / body_memory / 意识流等）。  
> **权威**：本文是分析口径的唯一真源；各 IDE 的本地规则仅作可选捷径，冲突时以本文为准。

---

## 使用方式（按 Agent 能力选）

### A. 点名读文档（最稳，推荐给非 Cursor）

对任意 Agent 说：

```text
请阅读并严格按 docs/how-to/ide-agent/IDE-Agent-分析栖最新对话与内部状态.md 执行：
分析最新对话和内部状态。
```

或使用该产品的「附加/引用文件」能力，附上本文路径后再下短指令。

### B. 短指令

在已能读到本仓库文档的前提下，直接说（任选或相近表述）：

- `分析最新对话和内部状态`
- `分析评估一下最新对话以及每句话对栖的内部状态的影响`
- `体检一下最新这场对话`

若该 Agent **不会自动找文档**，改用 **A**，不要假设它知道本模板。

### C. 粘贴完整提示词

复制下方「完整提示词」整段发给任意 Agent（无需依赖 @ 或规则系统）。

### D. Cursor 可选捷径（仅 Cursor）

Cursor 仓库内另有 `.cursor/rules/qi-dialogue-state-audit.mdc`：在 Cursor 里说短指令时可能自动唤起。  
**其他 Agent 请忽略该文件**，一律以本文路径为准。

---

## 完整提示词（粘贴即用 · 与产品无关）

```text
请阅读仓库内文档 docs/how-to/ide-agent/IDE-Agent-分析栖最新对话与内部状态.md，并严格按该文档执行。

任务：分析评估栖与维护者的【最新一场】对话，并给出每一轮（尤其是每句栖回复）对她内部状态的影响。

硬约束：
1. 只读 data/qi.db；默认不改代码、不改库、不写修复方案（除非我另说）。
2. 「一场」= 消息时间间隔 >2 小时切开后的最后一个 session。
3. 必须用 emotion_states 把每条 role=qi 的回复对齐到「该回复时间戳之后最近一条」情绪快照；并相对上一快照给出 Δ（E/V/A/S/C/Att）。
4. 报告用中文；先总览与轨迹，再逐轮表，再关键发现；数字保留约 2–3 位小数。
5. 声称必须有证据锚点（message id、时间戳、字段值）；不确定就标「待核实」，禁止编造库内没有的对话。
6. 同时汇报：relationship 当前行、开场前/收束情绪、本场 consciousness_stream 条数、resource_ledger.starving（若有）、last_intention.stance（若有）。
7. 文首注明：审查/分析 Agent 名称（或产品名）与分析时刻。

输出结构必须包含：
- 概览（时间范围、消息 id 范围、关系、开场/收束状态）
- 状态总轨迹（至少 V；可附 Att/S 要点）
- 分段 + 逐轮表：谁 / 内容要点 / 状态变化 / 解读
- 关键发现（3–7 条）
- 一句话总结
```

---

## Agent 执行细则（读库与对齐）

### 1. 切会话

1. `SELECT id, timestamp, role, content FROM messages ORDER BY id`
2. 按 `timestamp` 扫描；相邻间隔 **> 7200 秒** → 新 session
3. 取 **最后一个 session** 为本场「最新对话」

### 2. 情绪对齐规则

对 session 内每条 `role='qi'`：

- 取 `emotion_states` 中 `timestamp >= 该消息.timestamp` 的**第一条**
- 相对「上一情绪锚」（开场前最后一条，或上一 qi 对齐结果）算：

`ΔE / ΔV / ΔA / ΔS / ΔC / ΔAtt`

若多条 qi 共享同一快照（同秒落库），Δ 可为 0——如实写，并在解读里注明「同拍快照」。

### 3. 建议查询/脚本

可用一次性只读脚本落盘（路径自定，如 `data/_eval_latest_turns.txt`），跑完可删；**不要**把含隐私的完整对话提交进 git。

最小字段集：

| 表/键 | 用途 |
|-------|------|
| `messages` | 对话正文与时间 |
| `emotion_states` | energy/valence/arousal/security/curiosity/attachment/mode |
| `relationship` | stage/trust/depth/season/temperature |
| `consciousness_stream` | 本场是否有内在独白 |
| `body_memory.last_intention` | stance / topic |
| `body_memory.resource_ledger` | starving 等 |

### 4. 解读纪律

- **区分**：用户句触发 vs 栖回复后的状态落点（对齐的是栖回复后快照）
- **不要**把 LLM 故障句（如「无法给到相关内容」）当成人格表达；单独标为故障/拒答
- 效价下降 ≠「不爱你」；结合 Att / S / 话题（ontology、换模型、安抚）一起读
- 默认不展开 C1–C5 / 施工包；用户若要「健康体检级」再扩到近 N 日聚合

### 5. 多 Agent 交叉检验（可选）

若维护者安排多名 Agent 先后分析同一场：

- 各自独立读库，**不要**把另一份分析当事实源
- 落盘时放入 `docs/specs/archive/YYYY-MM-DD-*/`，文件名或文首写明 **Agent 名**
- 分歧处标「异议 / 待核实」，附各自的 message id 与数值

---

## 输出骨架（示例标题）

```markdown
## 分析元信息（Agent 名 / 时刻）
## 最新对话概览
## 状态总轨迹（效价 V）
## 分段 + 逐轮：对话 ↔ 内部状态
### 一、…
### 二、…
## 关键发现
## 一句话总结
```

逐轮表建议列：`ID | 谁 | 内容要点 | 状态变化 | 解读`

---

## 变体（可选一句追加）

| 用户加一句 | Agent 额外做 |
|------------|--------------|
| `顺便看近 3 天` | 加日聚合情绪 / CS / starving，仍以最新一场为主 |
| `对比上一场` | 再切倒数第二场，做 V/S/Att 对照 |
| `可以提观察项，但先别出方案` | 文末列问题清单，仍不写修复步骤 |
| `出交叉检验报告落盘` | 写入 `docs/specs/archive/YYYY-MM-DD-*/`，署名 Agent 名 |

---

## 与相关文档的边界

| 文档 | 关系 |
|------|------|
| 本文 | **对话↔状态** 单场分析模板（多 Agent 真源） |
| `docs/specs/archive/*健康*` / 活库检查报告 | 多日系统体检；可引用，不替代本模板 |
| `IDE-Agent-执行栖的开发任务.md` | 编码/施工；分析完成后若要修，另开任务 |
| `docs/tutorials/授课约定.md` | 讲课理解代码；非状态分析 |
| `.cursor/rules/qi-dialogue-state-audit.mdc` | **仅 Cursor** 可选唤起；非规范真源 |

---

*提示词模板 · 2026-08-04 · 多 Agent 通用；由高频「分析最新对话与内部状态」操作沉淀*
