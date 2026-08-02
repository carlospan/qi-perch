# 包 11 实施 PR · Cursor 编码回执

> **用途**：开工前理解确认 + 完工结果；交方案 Agent（CodeBuddy）实施验收。  
> **依据**：`包11-PR方案-Cursor编码请求.md`、`specs/tasks/2026-08-02-阶段三-包11-PR方案.md`、主线 v2 包 11。  
> **撰写**：Cursor（2026-08-02）

---

## 【开工前理解确认段】

已读取包 11 PR 方案与编码请求。关键改动点理解：

### `qi/learning/replay.py`（ReplayBuffer）
- 只读 `list_recent_broadcast_traces(limit)`；按 `winner_salience >= floor` 过滤，并偏好 curiosity / close_loop / proactive 胜出拍；**按 salience 降序取头部**，非随机。
- `to_samples`：纯字段搬运 → `{beat, timestamp, winner_kind, winner_salience, motive, candidates, prompt_hint}`。
- `run_training(dry_run=True)`：默认只打印资源预估；`dry_run=False` 占位不 import 重依赖；**心跳/CI 不调用**。

### `qi/learning/corpus.py`（CorpusStore）
- 根目录默认 `data/corpus/`；`save_version` → `corpus_{tag}_{YYYYMMDD-HHMMSS}.jsonl`；`load_version` / `list_versions`。

### 异时骨架
- 选 `tools/replay_drift_check.py`（与 check_doc_links 同层 CLI）；读两版 jsonl，对比 winner_kind / motive 关键字段差异摘要；不训。

### `.gitignore`
- 显式补 `data/corpus/` + 注释（虽已有 `data/`）。

### 纪律
- 不改 broadcast 写入；零新依赖；训练隔离；不改心跳路径；无 LLM。

### 拿不准 / 自决
- 「motive.curiosity 高 / world_surprise 高」与 floor 的 OR 关系：拟 **salience≥floor OR curiosity≥0.7 OR world_surprise≥1.0 OR 优先 kind**，再按 salience 排序。
- 语料路径相对仓库根：用 `qi.PROJECT_ROOT / "data/corpus"` 作默认绝对根，测试传 tmp。

本段写完即继续写码，不阻塞等待方案 Agent。

---

## 【完工结果段】

### 落地摘要

| 路径 | 动作 |
|------|------|
| `qi/learning/__init__.py` | 新增 |
| `qi/learning/replay.py` | 新增 `ReplayBuffer` + `run_training(dry_run=True)` + 可选 `__main__` CLI |
| `qi/learning/corpus.py` | 新增 `CorpusStore`（jsonl 版本化） |
| `qi/learning/drift_check.py` | 新增异时差异摘要（#1-地基） |
| `tools/replay_drift_check.py` | 新增 CLI 入口 |
| `.gitignore` | 显式 `data/corpus/` |
| `tests/test_replay.py` | 新增 10 用例 |
| `broadcast_traces` 写入 / `brain` 心跳 | **未改** |

### 是否 100% 照方案 / 偏离点

| 项 | 说明 |
|----|------|
| 过滤 OR | salience≥floor **或** curiosity≥0.7 **或** world_surprise≥1.0；优先 kind 只影响排序（不自动入选） |
| 默认 corpus 根 | `PROJECT_ROOT / data/corpus`（绝对路径），测试传 tmp |
| drift | 同时有 `qi/learning/drift_check.py` + `tools/replay_drift_check.py` CLI |
| 真训 | `dry_run=False` 仅占位返回 `training=not_implemented`，不 import 重依赖 |

### 测试结果

```
python -m pytest -q tests/test_replay.py  → 10 passed
python -m pytest -q                       → 365 passed in 79.67s
python -m ruff check qi tests             → All checks passed!
```

### 纪律红线自查

1. **不改 broadcast 写入** ✅  
2. **零新依赖** ✅  
3. **训练默认隔离** ✅；`brain` 无 `run_training`/`ReplayBuffer`  
4. **不破坏现有行为** ✅ 纯新增  
5. **拔管** ✅ collect/to_samples 只读 db  

### 交回方案 Agent + HITL 提示

请对照 PR 验收清单勾选。  
**#1-真通过**不在本 PR：地基（语料版本化 + drift 骨架 + dry_run）已交；真异时漂移或降级观察项仍待维护者 HITL。

---

*Cursor 编码回执 · 包 11 · 2026-08-02*
