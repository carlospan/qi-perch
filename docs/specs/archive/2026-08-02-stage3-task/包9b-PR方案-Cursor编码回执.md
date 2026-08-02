# 包 9b 实施 PR · Cursor 编码回执

> **用途**：开工前理解确认 + 完工结果；交方案 Agent（CodeBuddy）实施验收。  
> **依据**：`包9b-PR方案-Cursor编码请求.md`、`specs/tasks/2026-08-02-阶段三-包9b-PR方案.md`、主线 v2 包 9b。  
> **撰写**：Cursor（2026-08-02）

---

## 【开工前理解确认段】

已读取包 9b PR 方案与编码请求。关键改动点理解：

### `qi/world/emotion_trajectory.py`
- 追踪默认 `valence/arousal/energy`；每拍 delta = 当前 − 上一拍；首拍只建基线、surprise=0。
- 窗口 N=20：`predict_next` = 近期 delta 均值；`surprise = |actual−mean|/(std+ε)`，夹顶。
- body_memory key=`world.emotion_trajectory`；lazy load（同包 9，非构造时读库）。
- 不依赖 LLM；不改 `emotion.py`。

### `qi/world/model.py`
- 挂 `self.emotion_trajectory` 入 `domains`；`update` 在 online 之后 `record`；`snapshot` 并入子域。
- brain 端已有 `world.update`，**不改 brain**。

### `qi/core/trace.py`
- `motive_snapshot` 增独立字段 `emotion_trajectory_surprise`（dict per dim）；不改 `world_surprise`。

### 纪律
- 不接 GWS；零新依赖；不新建表；拔管安全。

### 拿不准 / 自决
- `record` 在心跳早期 `world.update` 时读 emotion（步进前）→ 拍间轨迹含上拍步进结果，可接受。
- 样本 <2 时 surprise=0（无可比预测）。

本段写完即继续写码，不阻塞等待方案 Agent。

---

## 【完工结果段】

### 落地摘要

| 路径 | 动作 |
|------|------|
| `qi/world/emotion_trajectory.py` | 新增 `EmotionTrajectory`（滑动窗口 delta 均值/方差 → surprise） |
| `qi/world/model.py` | 挂域 + `update`/`snapshot` 并入 |
| `qi/world/__init__.py` | 导出 `EmotionTrajectory` |
| `qi/core/trace.py` | `motive_snapshot` 增 `emotion_trajectory_surprise` |
| `tests/test_world_emotion_trajectory.py` | 新增 6 用例 |
| `qi/core/emotion.py` / GWS / brain 心跳结构 | **未改**（brain 仍只调既有 `world.update`） |

### 是否 100% 照方案 / 偏离点

| 项 | 说明 |
|----|------|
| lazy load | 同包 9：首次 `record` 读 body_memory（非构造时） |
| 短窗口 surprise | 样本&lt;2 时用 `|actual−pred|`，≥2 用 z-score |
| 观测时机 | 仍在心跳早期 `world.update`（步进前），拍间轨迹含上拍演化 |

### 测试结果

```
python -m pytest -q tests/test_world_emotion_trajectory.py  → 6 passed（与 online 合计 15）
python -m pytest -q  → 371 passed in 51.52s
python -m ruff check qi tests  → All checks passed!
```

### 纪律红线自查

1. **不改 emotion 演化** ✅  
2. **不接 GWS** ✅  
3. **零新依赖** ✅  
4. **复用 body_memory** ✅ key=`world.emotion_trajectory`  
5. **拔管** ✅ FailLLM 下仍落库  

### 交回方案 Agent

观察项交付完成；请对照验收清单勾选。不宣称阶段三退出相关硬判据。

---

*Cursor 编码回执 · 包 9b · 2026-08-02*
