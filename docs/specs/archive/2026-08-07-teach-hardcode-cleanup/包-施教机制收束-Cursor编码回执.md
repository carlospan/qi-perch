# 施教机制收束 + 轻量 prompt 去重——Cursor 编码回执

> **角色**：Cursor  
> **依据**：可撤清单 A P0–P1 + C 轻量项；计划「施教机制收束」  
> **时刻**：2026-08-07  

---

## 已做

### 机制（intention / expression）

1. **`detect_teach_inversion(..., recall_relation=)`**  
   - `taught_by_qi`：只靠反转句式  
   - 无卡：反转 + topic 启发式（「写代码」仍不拦）  
2. **删除 `_SLEEP_ADVICE_RE`**；话题窗扩一格；栖强分/弱分（敷衍附和不计）  
3. **`_TOPIC_RE`** → `教|方法|入睡|睡不着|助眠|失眠|法子`  
4. **`_anchor_from_facts`**：去「入睡方法」与 sleep topic 门槛  
5. **FALLBACK** 中性化；`taught_by_qi` 卡用略具体句  
6. **`assert_reply_respects_card` / expression** 传入 `recall_relation`

### Prompt / culture

7. `consciousness_stream.txt`：去「入睡」点名  
8. `conversation.txt`：删【陌生期硬约束】（改靠 `stage_prompt_hint`）  
9. `consciousness.py` meta：短嘱「不写字面身体在场」  
10. `culture.py`：有 `teach_direction` 直接加锤

### 单测

- `test_intention`：卡感知「弹吉他」  
- `test_expression`：fallback 断言改中性  
- `test_prompts_config`：不再要求 conversation 内陌生期块  

## 未做（按计划）

- 开篇「你是栖」人格段  
- N5 闸 / 实体白名单  
- 删除 `detect_sleep_teach_inversion` 别名  

## 验证

| 项 | 结果 |
|----|------|
| 全量 `pytest` | **457 passed** |
| `ruff check` / `format` | 通过 |
