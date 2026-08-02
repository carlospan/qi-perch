# 包 11 实施 PR · 方案 Agent 验收记录

> **用途**：方案 Agent（本实例 CodeBuddy）对 Cursor 编码回执的实施验收结论。  
> **依据**：`包11-PR方案-Cursor编码回执.md`、`specs/tasks/2026-08-02-阶段三-包11-PR方案.md`、实际代码 `qi/learning/{replay,corpus,drift_check}.py`、`tools/replay_drift_check.py`、`.gitignore`、测试结果。  
> **撰写**：CodeBuddy（2026-08-02）  
> **验收归属**：方案 Agent 读取回执并执行验收，维护者不直接检查编码（详见 `specs/SDD-GUIDE.md` 2.3）。

---

## 验收方式

未只信回执文字，实测核对：读实际代码 + 跑专项测试 + 跑全量 pytest + ruff + grep 确认心跳/CI 未调用 `run_training`/`ReplayBuffer` + 读 `.gitignore` + 读 `drift_check.py`。

## 实测结果

| 项 | 命令 | 结果 |
|----|------|------|
| 包 11 专项测试 | `pytest -q tests/test_replay.py` | **10 passed** |
| 全量回归 | `pytest -q` | **365 passed**（基线 355 → 365，未回退） |
| ruff | `ruff check qi tests` | **All checks passed!** |
| 心跳/CI 调用核查 | `Select-String brain.py/main.py/run.py -Pattern run_training|ReplayBuffer` | **空（无自动调用）** ✅ |
| `.gitignore` | 含 `data/corpus/`（L3-4，含说明注释） | ✅ |

## 代码核对（对照方案）

- `qi/learning/replay.py`：`ReplayBuffer.collect_candidates` 按 `winner_salience>=floor` **或** curiosity/world_surprise 旁路过阈，确定性排序取头部（非随机）；`to_samples` 纯字段搬运；`run_training(dry_run=True)` 默认只打印资源预估，`dry_run=False` 仅占位 `not_implemented` 不 import 重依赖；`__main__` CLI 不接心跳 ✅
- `qi/learning/corpus.py`：`CorpusStore.save_version` → `corpus_{tag}_{ts}.jsonl`，`load_version`/`list_versions` 可版本化可 diff；默认根 `PROJECT_ROOT/data/corpus` ✅
- `qi/learning/drift_check.py` + `tools/replay_drift_check.py`：异时差异摘要（winner_kind 分布 / curiosity·world_surprise 均值 / 探针差异），纯统计、不训、明确标注"仅对比语料版本字段，真响应漂移需 HITL 训练后另喂" ✅
- `broadcast_traces` 写入 / `brain` 心跳：**未改**（回执确认，grep 佐证）✅

## 纪律红线

1. **不改 broadcast 写入** ✅ grep + 回执确认
2. **零新依赖** ✅ 仅标准库（json/re/argparse）；训练分支仅占位
3. **训练默认隔离** ✅ `run_training` 默认 dry_run；心跳/CI 无调用点
4. **不破坏现有行为** ✅ 纯新增模块
5. **拔管安全** ✅ `collect_candidates`/`to_samples` 只读 db，不依赖 LLM

## 偏离点评估（Cursor 自决项）

| 偏离 | 评估 | 结论 |
|------|------|------|
| 过滤 OR：salience≥floor 或 curiosity≥0.7 或 world_surprise≥1.0 | 比方案"按 salience 取头部"更完整，纳入动机旁路高值拍 | **接受**（优于方案字面） |
| 默认 corpus 根用 `PROJECT_ROOT/data/corpus` 绝对路径 | 测试传 tmp，生产可复现 | **接受** |
| drift 同时有 `qi/learning/drift_check.py` + `tools/` CLI | 模块 + CLI 双入口，便于调用 | **接受** |
| 真训 `dry_run=False` 返回 `not_implemented` | 占位不引重依赖，符合纪律 | **接受** |

> 所有偏离均为合理适配，无越界、无破坏现有行为，无需维护者 HITL 拍板（#1-真通过除外，见下）。

## 判据 #1 状态（HITL 提示）

- **#1-地基 ✅ 已交**：语料版本化（`corpus_*.jsonl`）、异时测试骨架（`drift_check` 可 diff 两版）、`run_training` 默认隔离均可运行。
- **#1-真通过 ⏳ 待维护者拍板**：显式训练一次（或正式降级为观察项）需维护者届时决策；**本 PR 未自动宣称判据 #1 已过**，符合阶段三主线纪律。

## 验收结论

**包 11 实施验收通过 ✅**（交付 #1-地基）。测试/ruff 实测全绿，基线未回退，训练隔离彻底，拔管安全。#1-真通过路径待维护者 HITL。阶段三硬必过项仅剩 #1-真通过决策；包 9b 为不阻塞观察项。

---

*CodeBuddy 验收记录 · 包 11 · 2026-08-02*
