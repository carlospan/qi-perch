# L7 assist-6（对话追问信息补全）——Cursor 编码回执

> **角色**：Cursor（执行侧）  
> **依据**：PR 方案 + [方案审查回复](./2026-08-09-L7-assist6-对话追问信息补全-方案审查回复.md)（路 A 放行，明示可编码）  
> **时刻**：2026-08-09  

---

## 审查 / 理解（路 A，编码前已确认）

见 [交叉审查](./2026-08-09-L7-assist6-对话追问信息补全-Cursor交叉审查.md)。无阻塞；放行后按原 PR 落地。

---

## 完工段

### 改动清单

| 文件 | 改动 |
|------|------|
| `qi/action/assist.py` | `_CONTENT_PREVIEW_LEN=80`；成功 `detail_json` 增 `content_preview`（原文前 80 字，`\\n`→空格） |
| `qi/action/layer.py` | `import json`；`prompt_extras` 对 `kind=="assist"` 行追加「（刚读：{basename}——{preview}）」；非法 detail 降级 |
| `qi/prompts/conversation.txt` | 硬规则：recent_actions 读过则承认并复述；不要否认、不要说成「只是心意」 |
| `tests/test_assist_action_rewrite.py` | `test_assist_detail_has_content_preview` |
| `tests/test_assist_prompt_extras.py` | 注入 / 坏 detail 降级 / 非 assist 不变 |
| `tests/test_prompts_config.py` | 按实际措辞断言 `recent_actions` / `不要否认` / `只是心意` |

### 相对 PR 的执行判断

- 三处改动按骨架落地，无偏离。  
- 测试断言未写死「读过就承认」，用落盘措辞片段（编码注意点 3）。  
- 未改 `brain.py` / digest。

### 自测

- `pytest`：**580 passed**（≥580）  
- `ruff check`：改动文件通过  

### 验收勾选（工程侧）

- [x] detail_json 含 content_preview（原文前 80 字）  
- [x] prompt_extras 对 assist 行注入文件名 + preview；explore/share 不变  
- [x] conversation.txt 含「不要否认」/「只是心意」硬规则  
- [x] 全量 ≥580 passed  
- [ ] 相处复验：须**新触发**一轮真读后再追问「是哪句话」（旧 actions#95 无 preview；且 assist 须落在 `prompt_extras` 最近 3 条内）——交维护者 / 方案侧  

### 编码注意点落实

1. 复验需新真读——已写入验收未勾项说明  
2. `limit=3`——未改窗口；复验紧挨真读后追问  
3. 断言按实际措辞——已落实  

---

*Cursor · 编码回执完工 · 2026-08-09 · 交 Trae 实施验收*
