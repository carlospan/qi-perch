# 包 10 实施 PR · 方案 Agent 验收记录

> **用途**：方案 Agent（本实例 CodeBuddy）对 Cursor 编码回执的实施验收结论。  
> **依据**：`包10-PR方案-Cursor编码回执.md`、`specs/tasks/2026-08-02-阶段三-包10-PR方案.md`、实际代码 `qi/motivation/curiosity.py`、`qi/core/trace.py`、`qi/core/brain.py`、`qi/core/gws.py`、`qi/inner_life/{dream,creativity,consciousness}.py`、`qi/action/{layer,explore,share}.py`、测试结果。  
> **撰写**：CodeBuddy（2026-08-02）  
> **验收归属**：方案 Agent 读取回执并执行验收，维护者不直接检查编码（详见 `specs/SDD-GUIDE.md` 2.3）。

---

## 验收方式

未只信回执文字，实测核对：读实际代码 + 跑专项测试 + 跑全量 pytest + ruff + `grep random.` 残留审计 + 读 gws/brain/trace 关键段。

## 实测结果

| 项 | 命令 | 结果 |
|----|------|------|
| 包 10 专项测试 | `pytest -q tests/test_motivation_curiosity.py` | **12 passed** |
| 全量回归 | `pytest -q` | **355 passed**（基线 343 → 355，未回退） |
| ruff | `ruff check qi tests` | **All checks passed!** |
| `grep -rn "random\." qi/` | 残留 12 处 | 全部属时机阀 / 表达层，无"随机做动机来源"残留 ✅ |

## 随机审计三栏表落地核对（grep 结果逐条）

| 位置 | 角色 | 判定 |
|------|------|------|
| `share.py:85` choice | 表达层话术 | 保留 ✅ |
| `layer.py:207` `random>priority` | tick 软门控时机阀 | 保留 ✅ |
| `explore.py:145` `random>p` | WHETHER 时机阀（已 curiosity 化） | 保留 ✅ |
| `dream.py:72/90/93` choices/shuffle/choice | 加权抽 + 表达层 | 保留 ✅ |
| `dream.py:328` `>=DREAM_SHARE_PROB` | 提梦时机阀 | 保留 ✅ |
| `creativity.py:183` `>0.25` | 提起时机阀 | 保留 ✅ |
| `consciousness.py:130/132` `random<prob` | loop_backlog 时机阀（有积压） | 保留 ✅ |
| `consciousness.py:273` choice | 表达层尾句 | 保留 ✅ |
| `brain.py:769` `uniform(0.5,1.5)` | 投递 sleep 抖动时机阀 | 保留 ✅ |

> 原纯随机动机源 WHETHER（`dream.maybe_dream` 30%、`creativity.maybe_create` 纯随机、`consciousness.should_trigger_meta` 纯随机）**均已移除**，改 curiosity 驱动。三栏表落地正确。

## 代码核对（对照方案）

- `qi/motivation/curiosity.py`：`CuriositySignal.update` 合成 surprise+loop+intrinsic（剥 `_curiosity_motive_boost` 防顶满），写回 `emotion.curiosity`；不依赖 LLM ✅
- `qi/core/trace.py`：`salience()` 增 curiosity 分支；`collect_contenders(curiosity=)`；**curiosity 竞争者仅 `pending is None` 入场**（L510-518）；legacy/persist 回退路径也传 curiosity（L554-565）；`motive_snapshot` 已有 `curiosity` 字段 ✅
- `qi/core/brain.py`：`_heartbeat` 的 `step_emotion` 后调 `CuriositySignal.update`（L383-390）；GWS idle 路径传 curiosity（L627-635）✅
- `qi/core/gws.py`：`kind_family` 认 `curiosity`；`_FAMILY_RANK["curiosity"]=15`（action 与 idle 之间）✅
- `dream/creativity/consciousness`：WHETHER → curiosity 驱动；时机阀保留+注释 ✅

## 纪律红线

1. **respond 恒胜** ✅ curiosity 仅 `pending is None` 入场；arbitrate 测覆盖
2. **零新依赖** ✅ 仅 `math`/标准库，无 torch/transformers
3. **时机阀/表达层随机保留+注释** ✅ grep 审计确认
4. **拔管安全** ✅ `test_fake_provider_curiosity_update` 通过（不依赖 LLM）

## 偏离点评估（Cursor 自决项）

| 偏离 | 评估 | 结论 |
|------|------|------|
| update 位置：方案写 `_gws_broadcast` 内，实际在 `_heartbeat`（step_emotion 后） | 覆盖 legacy/GWS/persist 更全，更稳 | **接受**（优于方案字面） |
| 防顶满：剥 `_curiosity_motive_boost` 再叠本拍 | 避免跨拍累加顶满，设计严谨 | **接受** |
| curiosity 入场仅 `pending is None` | 红线要求 respond 恒胜，自决正确 | **接受** |
| persist 回退路径补传 curiosity | 完整性增强 | **接受** |
| motive_snapshot 未重复加 curiosity | 字段已存在 | **接受** |
| curiosity 胜出无专属 execute | 「动机只是大声」落空闲，explore 仍走 action | **接受**（符合阶段二纪律） |

> 所有偏离均为合理适配，无越界、无破坏现有行为，无需维护者 HITL 拍板。

## 验收结论

**包 10 实施验收通过 ✅**。learning-progress 好奇已接 GWS 竞争者，随机动机源全部退位为时机阀/表达层，测试/ruff 实测全绿，基线未回退。可推进包 9b（观察项）/ 包 11。

---

*CodeBuddy 验收记录 · 包 10 · 2026-08-02*
