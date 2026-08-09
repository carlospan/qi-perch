# L7 assist-6（对话追问信息补全）——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：`2026-08-09-L7-assist6-对话追问信息补全-任务包.md`、`…-PR方案.md`  
> **对照代码**：`qi/action/assist.py`（成功路径 `insert_action` / `detail_json` ≈L111–124）、`qi/action/layer.py`（`prompt_extras` L436–455，顶部尚无 `import json`）、`qi/storage/database.py`（`list_recent_actions` SELECT *，含 `kind`/`detail_json`）、`qi/core/brain_context.py`（`action.prompt_extras` 并入对话 extras）、`qi/prompts/conversation.txt` L66（assist-5 硬规则）  
> **实证锚点**：msg #1526–#1531；actions id=95（真读成功、summary=诗意 digest、detail 无原文）  
> **审查时刻**：2026-08-09  

---

## 总判

**方向正确，无必须整改项 → 路 A（轻量放行）。**

根因判断与活库一致：真读已留痕，但 `prompt_extras` 只灌 `summary`（诗意 digest），追问「是哪句话」时 respond 侧无事实 → 否认 + 幻觉。用 `content_preview`（原文截断）补事实 + 硬规则校正否认姿态，能闭环 1528–1531 类断链；explore/share 行不进 `kind=="assist"` 分支，范围干净。不动 `brain.py` / 不改 digest（N4）与任务边界一致。

---

## 理解确认（≠放行）

| # | 改动点 | 理解 |
|---|--------|------|
| 1 | `assist.py` | 成功读文件后，`detail_json` 在现有 `op`/`target_path`/`digest` 上增加 `content_preview`：同一 `content` 变量前 80 字，`\\n`→空格 |
| 2 | `layer.prompt_extras` | 仅 `kind=="assist"` 解析 `detail_json`，行尾追加「（刚读：{basename}——{preview}）」；非法/空 detail 降级为仅 summary |
| 3 | `conversation.txt` | 在 assist-5 读文件能力句后加「recent_actions 里读过则承认并复述，不否认、不说成只是心意」 |
| 4 | 测试 | preview 断言 + prompt_extras 注入/降级/非 assist 不变 + 硬规则措辞断言；全量 ≥580 |

澄清（无阻塞）：PR 文内行号略旧（insert 实际约 L111+）；测试断言勿写死「读过就承认」四字，按落盘措辞（如「recent_actions」+「不要否认」/「大方承认」）即可——PR 已写「或按实际措辞」。

---

## 认可

1. **对症**：#1527 digest「那句话」+ actions#95 无原文 → #1528–#1531 断链；补 `content_preview` 进 `recent_actions`，下一拍对话路径（`brain_context`→`prompt_extras`）能看见事实。  
2. **R1**：preview 来自真读缓冲而非二次编造；比「只加文件名」更能答「是哪句话」。  
3. **与既有管道一致**：digest 已把 `content[:2000]` 送 consciousness；80 字 preview 进 conversation 不扩大读盘面，且低于 digest 已暴露的原文量。  
4. **explore/share 隔离**：`if kind == "assist"` 分支正确；`list_recent_actions` 的 `SELECT *` 已含所需字段。  
5. **降级**：非法 JSON / 无 path 与 preview → 只 summary，不炸。  
6. **边界**：不改 assist-5 控制流；1531 幻觉作观察项——合理。  
7. **「不必挂在嘴上」前缀**已约束无关话题背书风险（观察即可）。

---

## 必须整改（阻塞编码）

**无。**

---

## 编码时注意（不阻塞）

### N1. 相处复验须「再读一轮」

库内旧 assist 行（如 id=95）无 `content_preview`，升级后只会降级显示 summary。复验请重新：读路径 → 确认 → 再问「是哪句话」。

### N2. `recent_actions` 窗口 limit=3

其后若连续写入 ≥3 条非 assist 行动，assist 行会挤出窗口，追问又可能断链。本包可不改 limit；复验紧挨真读后问即可。若相处仍复现，再开观察/小包。

### N3. basename 空、preview 有

成功路径必有 `target_path`；防御分支若仅有 preview，文案会成「（刚读：——…）」——可接受，不必为本包加逻辑。

### N4. preview 与「不外传原文」话术

模块红线/digest 有「不外传原文」；本包是**对同一用户复述其授权文件**，与 HITL1=a 一致。编码勿把 preview 写进对外分享/share 卡。

### N5. 测试落点

`tests/test_action_l7.py` 已有 `test_prompt_extras_recent_actions`；注入/降级/非 assist 用例优先挂同文件或新 `test_assist_prompt_extras.py` 均可，与 PR 一致。

### N6. 硬规则与历史否认并存

对话史上已有 #1529/#1531 否认句，LLM 仍可能偏历史。A（事实）+ B（姿态）是对症双保险；若复验仍否认，再考虑控制流（本包明确不动 brain，正确）。

---

## 观察项（不进本包）

- 无关话题是否偶发复述 preview（前缀约束）  
- 1531 型自由幻觉是否在信息补全后消失  
- digest 仍虚（N4）是否导致「开口诗意、追问靠 preview」的体感分裂——可接受  

---

## 结论与分轨

| 项 | 结论 |
|----|------|
| 阻塞项 | **无** |
| 分轨 | **路 A** |
| 下一拍 | 待方案 Agent 落盘 `-方案审查回复.md`（「无需整改，可编码」）+ 维护者/方案侧明示可编码后，Cursor 按本 PR 编码并写回执完工段 |

---

*Cursor · 交叉审查 · 2026-08-09 · 禁码*
