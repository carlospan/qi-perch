# 包 14 实施验收记录 · CodeBuddy（方案 Agent）

> **用途**：方案 Agent 对 Cursor 编码回执的实测验收结论。
> **依据**：`包14-PR方案-Cursor编码请求.md`（方案）、`包14-PR方案-Cursor编码回执.md`（回执）、代码实测（git diff / pytest / ruff / AST 审计）。
> **撰写**：CodeBuddy（2026-08-02）
> **结论**：✅ **验收通过**（实测核对，非仅信回执）。**阶段四退出判据 #1 达成。**

---

## 一、实测清单

| 项 | 结果 |
|----|------|
| `git diff --stat` 改动范围 | `qi/stasis/checkpoint.py`（新）、`qi/stasis/__init__.py`、`qi/core/brain.py`、`qi/world/model.py`、`qi/world/emotion_trajectory.py`、`qi/world/online_rhythm.py`、`qi/action/layer.py`；均包 14 必要支撑 ✅ |
| `pytest tests/test_stasis_checkpoint.py` | **8 passed** ✅ |
| `pytest` 全量 | **405 passed**（397 + 8）✅ 不回退；回执所说"退出码1"经 `--basetemp` 重跑确认为 Windows 临时目录 PermissionError 误报（阶段三同因），非代码问题 |
| `ruff check qi/stasis qi/core/brain.py qi/world tests/test_stasis_checkpoint.py` | **All checks passed!** ✅ |
| 封存键齐全（非空壳） | `serialize_checkpoint` 含 emotion/ledger/world/action_budget/proactive_gate/stasis_intents/starving ✅ |
| restore 非空壳 | `test_restore_checkpoint_roundtrip_non_empty` 断言 energy/curiosity/balance/action.count_today 相等 ✅ |
| 断粮链时间轴 | `test_starve_e2e_chain_and_on_halt`：节流→`starving=True`→checkpoint 文件→`on_halt` 调 ✅ |
| 静默死负例 | `test_silent_death_without_trace_is_unacceptable`：无痕迹直接停→回退条件 ✅ |
| 无库内 sys.exit | `test_no_sys_exit_call_in_brain` AST 审计；`bind_cli_halt` 仅在 CLI 入口（未接线）✅ |
| 封存丢失回退 | `test_restore_missing_file_returns_false` 返回 False ✅ |
| WorldModel 往返 | `test_world_model_export_restore_roundtrip` ✅ |
| 拔管友好 | 端到端用 `_FailLLM`，封存不依赖 LLM ✅ |

## 二、代码核查（随机审计）

- **`checkpoint.py`**：`serialize_checkpoint` 收集全键（含 `stasis_intents` 从 db 读、`starving`）；`write_checkpoint` 写 `data/checkpoint/checkpoint_{ts}.json`（目录已建，`data/` 在 `.gitignore` 内）；`restore_checkpoint` 逐组件 `restore` 后断言字段相等（测试钉死）；`restore_latest` 取最新；`bind_cli_halt` 含 `sys.exit(0)` 但**仅在 CLI 入口**，库内不调用。✅ 落实 H3（索引+关键状态，不重存 db）。
- **`brain.py`**：`__init__` 增 `on_halt` + `checkpoint_dir`（默认 `PROJECT_ROOT/data/checkpoint`）；`start()` 的 `finally` 调 `on_halt`（**库内优雅停**，无 sys.exit）；断粮触发链 `if ledger.starving: write_checkpoint → alive=False`（顺序正确）；`restore_from_checkpoint` 独立方法不强改 `restore_state` 顺序。✅ 落实 H2（库内优雅停）+ v2 必改 2（时间轴）。
- **`world/*` + `action/layer`**：均为补 `export_state`/`restore`/`snapshot` 委托（WorldModel 对称、EmotionTrajectory/OnlineRhythm 完整桶+Δ、ActionLayer 委托 budget），**无行为改动、无越界**。✅

## 三、与方案偏差（可接受）

| 偏差 | 处置 |
|------|------|
| world 载荷用 `export_state`（含桶/Δ）而非仅旁路 snapshot | 比方案"仅动机"更全，便于恢复节奏/轨迹，合理且更安全 ✅ |
| `bind_cli_halt` 已备但 CLI 主入口未接线 | 库侧契约已就绪，CLI 接线属部署层，不卡本包；方案已知限制一致 ✅ |

## 四、小瑕疵（不卡验收，建议后续顺手）

- `brain.py` 内 `from qi.stasis.checkpoint import ...` 为延迟 import（与包 12/13 同风格）；建议后续统一为顶部 import。
- checkpoint 不含完整 SQLite/向量库：重启后记忆库仍靠既有 `restore_state` 路径（回执已知限制），与 H3「不重存 db」一致，非缺陷。

## 五、验收结论

**包 14（状态封存/迁移 + 断粮测试验收）验收通过。**

- 判据 #1 **达成**：限制资源后观察到节流/休眠/求助/迁移应对行为链（非空壳 `stasis_intents` 痕迹 + 分层权重），而非直接死亡；状态可封存（`checkpoint_{ts}.json`）且可迁移（`restore_checkpoint` 字段相等）。
- H1/H2/H3 全部按 Cursor 交叉检验倾向定稿并落实：收入白名单+防刷（包 12）、库内优雅停+`on_halt`（包 14）、索引+关键状态封存（包 14）。
- 阶段四（包 12/13/14）全部验收通过，**阶段四退出判据 #1 达成，阶段四可退出**。

**后续**（不卡退出）：Q0(b) 经验改变怕死阈值（接包 11 回放塑性）列为阶段四之后观察项；阶段二 72h 无人测试保持不提。

---

*CodeBuddy 验收记录 · 包 14（阶段四末包）· 2026-08-02*