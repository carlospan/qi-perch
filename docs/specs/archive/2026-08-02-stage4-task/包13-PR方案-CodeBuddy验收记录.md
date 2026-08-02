# 包 13 实施验收记录 · CodeBuddy（方案 Agent）

> **用途**：方案 Agent 对 Cursor 编码回执的实测验收结论。
> **依据**：`包13-PR方案-Cursor编码请求.md`（方案）、`包13-PR方案-Cursor编码回执.md`（回执）、代码实测（git diff / pytest / ruff / grep 审计）。
> **撰写**：CodeBuddy（2026-08-02）
> **结论**：✅ **验收通过**（实测核对，非仅信回执）。

---

## 一、实测清单

| 项 | 结果 |
|----|------|
| `git diff --stat` 改动范围 | `qi/stasis/pressure.py`（新）、`qi/stasis/__init__.py`、`qi/core/emotion.py`、`qi/core/brain.py`；`budget.py` **未改** ✅ |
| `pytest tests/test_stasis_pressure.py` | **11 passed** ✅ |
| `pytest` 全量 | **397 passed**（基线 386 + 新增 11）✅ 不回退 |
| `ruff check qi/stasis qi/core/emotion.py qi/core/brain.py tests/test_stasis_pressure.py` | **All checks passed!** ✅ |
| energy 无盖写审计 | grep `emotion.energy =` 仅 `clamp_emotion`（line 307，既有夹紧）；新增处全为 `+=` 趋近 ✅ |
| `sys.exit` 审计 | `pressure.py` AST 审计无 `sys.exit`；brain 新增处无 exit ✅ |
| 静默死防护 | `maybe_mark_starving` 先 `leave_intent_trace` 再置 `starving`；负例测试断言"无痕迹" ✅ |
| 多样应对 | `compute_pressure` 用 attachment/security 调制 seek_help/migrate；单测 `test_diverse_response_weights_by_attachment_security` 钉死 ✅ |
| 拔管友好 | `test_pressure_no_llm_dependency` 仅 ledger+emotion 无 LLM ✅ |

## 二、代码核查（随机审计）

- **`emotion.py`（最小侵入）**：`step_emotion` 增 `energy_baseline_offset` 关键参 + `STASIS_APPROACH_RATE=0.05`（文档化常量，非平行闸门）；末尾 `e.energy += STASIS_APPROACH_RATE * (target - e.energy)`，**朝 `(circadian 目标 + offset)` 趋近**，与现有目标趋近式完全同构。decay/coupling/mood_cycle/circadian 公式一字未改。✅ 落实 v2 必改 1。
- **`brain.py`**：每拍 `balance_to_energy_offset(ledger.balance)` 注入 `step_emotion`；`compute_pressure` 产应对权重（仅 debug 日志，节流/休眠靠既有 `energy<0.3` 闸门与 `next_interval` 自然生效）；`maybe_mark_starving` 调 `db.set_body_memory("stasis_intents", ...)` 写意向痕迹。全部 `try/except` 不阻断。无 `sys.exit`、无 checkpoint 写盘。✅ 落实红线 2/3/4/5。
- **`pressure.py`**：`balance_to_energy_offset` clamp(-0.5, 0.3) 防顶满；模块级 `_low_balance_streak` + reset/get 测试钩子；`PressureResponse` frozen dataclass；`leave_intent_trace` 非空壳（含 `note` "会维持：意向痕迹（非声称想活）"——措辞守 R3/Q0，不称"想活"）。✅
- **`stasis_intents` 落点**：包 14 checkpoint 应收集此键（已与回执"验收关注点"对齐）。

## 三、与方案偏差（可接受）

| 偏差 | 处置 |
|------|------|
| 无重大偏差；`sys.exit` 审计由注释字面量升级为 AST 调用检查（更严） | 优于方案，✅ |
| `_low_balance_streak` 模块级（非 ledger 持久化） | 回执已说明"snapshot 可选持久化归包 14"；本包仅运行时计数，合理 ✅ |

## 四、小瑕疵（不卡验收，建议后续顺手）

- `brain.py` 两处 `from qi.stasis.pressure import ...` 为函数内延迟 import（与包 12 同风格），功能无碍；建议包 14 或独立清理时统一为顶部 import（与阶段三包 10 清理同节奏）。
- 节流/休眠目前仅 `logger.debug` 记录，未显式断言"被既有闸门消费"。但这由阶段三/既有测试（`energy<0.3` 闸门）覆盖，本包 `test_low_energy_lengthens_interval` 已断言 `next_interval` 随 energy 拉长，链路可测。

## 五、验收结论

**包 13（内稳态压力动力学）验收通过。** 余额→energy 稳态目标偏移（趋近式，禁盖写）落地；分层应对链（节流→休眠→断粮标记）产出多样且情境敏感权重；`starving` 置位前必写求助/迁移意向痕迹（防静默死、防单一反射）；无 `sys.exit`、无 checkpoint 写盘（归包 14）；Q0(b) 仅留 `pressure_sensitivity` 接口未接未真训回放。

**下一包**：出包 14 PR 方案（状态封存/迁移 + 断粮测试验收，阶段四退出判据）——收集 `stasis_intents` + `ledger.snapshot` + `emotion` + world/budget body_memory 键，序列化 `checkpoint_{ts}.json`，注入 `on_halt` 优雅停，端到端断言时间轴应对链。

---

*CodeBuddy 验收记录 · 包 13 · 2026-08-02*