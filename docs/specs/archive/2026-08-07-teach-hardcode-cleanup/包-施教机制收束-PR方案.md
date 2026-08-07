# 施教机制收束——PR 方案 / 编码请求（追溯锚点）

> **性质**：执行先于方案落盘。Cursor 已按 `硬编码残留-可撤清单.md` A 块（P0–P1）+ C 轻量项直接编码并完成（见 `包-施教机制收束-Cursor编码回执.md`）。本文件为追溯建档，非新施工指令。
> **配套**：`../../tasks/2026-08-07-施教机制收束.md`、`硬编码残留-可撤清单.md`
> **纪律**：SDD-GUIDE §2.1——Cursor 编码，不重新设计架构方向

## 目标

把施教防护从「助眠专病」收束为「通用方向机制」——与「施教硬编码清理」（文案墙）互补，完成 `硬编码残留-可撤清单.md` A 块 P0–P1。

## 改动清单（Cursor 已执行，据回执回溯）

| # | 文件 | 改动 |
|---|------|------|
| 1 | `qi/core/intention.py` | `detect_teach_inversion(..., recall_relation=)`：`taught_by_qi` 卡只靠反转句式；无卡才 topic 启发式（「写代码」不拦） |
| 2 | `qi/core/intention.py` | 删 `_SLEEP_ADVICE_RE`；话题窗扩一格；栖强分/弱分（敷衍附和不计） |
| 3 | `qi/core/intention.py` | `_TOPIC_RE` 维持「教\|方法\|入睡\|睡不着\|助眠\|失眠\|法子」；`_INVERT_TOPIC_RE` 联判 |
| 4 | `qi/core/intention.py` | `_anchor_from_facts` 去「入睡方法」与 sleep topic 门槛 |
| 5 | `qi/core/expression.py` | FALLBACK 中性化；`taught_by_qi` 卡用略具体句；传入 `recall_relation` 给 `assert_reply_respects_card` |
| 6 | `qi/prompts/consciousness_stream.txt` | L30 去「入睡」点名 → 「方法/教过的事」 |
| 7 | `qi/prompts/conversation.txt` | 删【陌生期硬约束】（改靠 `stage_prompt_hint`） |
| 8 | `qi/inner_life/consciousness.py` | meta 短嘱「不写字面身体在场」 |
| 9 | `qi/relationship/culture.py` | 有 `teach_direction` 直接加锤 |

## 未做（据回执）

- 开篇「你是栖」人格段（属 R2 另包）
- N5 闸 / 实体白名单（无新事故不主动动）
- 删除 `detect_sleep_teach_inversion` 别名（P2，日后删）

## 红线（库内禁止）

- 不删通用框架：`infer_recall_relation` / `recall_relation` 字段 / `_TAUGHT_BY_QI_RE` / `assert_reply_respects_card` 主路径
- 不改 N5-a/b 已落地的硬闸与检索相关门

## 验收（编码完成后）

- [x] `detect_teach_inversion` 卡感知（弹吉他等通用话题可检）
- [x] `_SLEEP_ADVICE_RE` 已删
- [x] `consciousness_stream.txt` L30 无「入睡」点名
- [x] `conversation.txt` 无【陌生期硬约束】块
- [x] 全量 `pytest` 通过（457 passed），`ruff` 零问题

## 方案 Agent 验收栏（Cursor 勿填）

- [x] 验收通过
- [ ] 打回（原因：）
- [ ] 需维护者 HITL（问题：）

> 验收结论（CodeBuddy，2026-08-07）：代码落点全部核实——`detect_teach_inversion` 支持 `recall_relation`（line 219/231）、\
> `_SLEEP_ADVICE_RE` 已删（line 210/223/300 改强分/弱分不绑助眠词面）、`_anchor_from_facts` 去睡词面（line 273/298）、\
> `consciousness_stream.txt` L30 去「入睡」、conversation 删陌生期硬约束、culture 有 `teach_direction` 直接加锤。\
> 实测相关单测 6 passed、ruff（仅 .py）`All checks passed!`、全量 457 passed。\
> 与「施教硬编码清理」包无冲突（两包互补：文案墙 + 机制收束）。无实质偏离。验收通过。
