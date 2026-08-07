# N5-b 检索相关门——Cursor 编码回执

> **角色**：Cursor（执行编码）  
> **依据**：`包-N5-b-检索相关门-编码请求.md`、整改复审 T1（双字滑动）  
> **时刻**：2026-08-07  

---

## 已做

1. **`qi/core/brain_context.py`**
   - `_STOP_WORDS` + `_cjk_bigrams`（汉字双字滑动，无新依赖）
   - `_filter_by_topic_relevance`：话题 = query + 近 2 条；停用双字自话题侧剔除；全滤空返回 `[]`（B1）
   - `gather_prompt_context`：`retrieve_for_prompt` 之后调用过滤

2. **`tests/test_brain_context.py`**
   - `test_filter_irrelevant_topic_memory`（#1367 菜名 vs 重置/珍惜 → `[]`）
   - `test_keep_relevant_topic_memory`（两侧含「助眠」→ 保留）
   - `test_return_empty_when_all_irrelevant`
   - `test_stop_words_do_not_false_pass`（「不要放在心上」vs「珍惜」）

3. **未改**：`intention.py` / `retrieve_for_prompt` 签名 / expression（B2、红线）

## 相对编码请求的执行判断（T1）

编码请求伪码用连续汉字段；复审要求双字交。落地为双字；「保留」单测改为共有「助眠」，避免假重叠。

另：`_STOP_WORDS` 增「放在」「心上」，减轻「放在心上」类虚词串台。

## 验证

| 项 | 结果 |
|----|------|
| `pytest tests/test_brain_context.py` | 4 passed |
| 全量 `pytest` | **457 passed** |
| `ruff check`（改动文件） | 通过 |
| `ruff format` | 已格式化 |

## 请方案 Agent

填编码请求验收栏；出 `包-N5-b-检索相关门-验收记录.md`。

---

## 方案 Agent 验收栏（Cursor 勿填）

- [x] 验收通过
- [ ] 打回（原因：）
- [ ] 需维护者 HITL（问题：）

> 验收结论（CodeBuddy，2026-08-07）：代码落点全部核实——`_STOP_WORDS`（含"放在/心上"扩展）、
> `_cjk_bigrams`（双字滑动，T1 偏离采纳——比连续段更稳）、`_filter_by_topic_relevance`（B1 全滤空返回 `[]`）、
> `gather_prompt_context` 检索后调用过滤。B2 红线遵守（intention.py/expression 未改）。
> 实测 `test_brain_context.py` 4 项 passed（含 #1367 菜名→重置/珍惜过滤、睡眠→助眠保留、全滤空返回 []、
> 停用词不假通过）、ruff `All checks passed!`、全量 457 passed。
> T1 偏离（双字滑动 + 停用词扩展）是合理工程判断，与"宁漏勿杀"一致。验收通过。
