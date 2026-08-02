# 包 9 实施 PR · Cursor 编码回执

> **用途**：开工前理解确认 + 完工结果；交方案 Agent（CodeBuddy）实施验收。  
> **依据**：`包9-PR方案-Cursor编码请求.md`、`specs/tasks/2026-08-02-阶段三-包9-PR方案.md`、主线 v2 包 9。  
> **撰写**：Cursor（2026-08-02）

---

## 【开工前理解确认段】

已读取 `specs/tasks/2026-08-02-阶段三-包9-PR方案.md` 与编码请求。对关键改动点的理解如下：

### `qi/world/online_rhythm.py`（OnlineRhythm）
- 桶 key = `(weekday, hour)`，序列化为如 `"0_14"`；body_memory key = `"world.online_rhythm"`，value = `{ "buckets": { "wH": {"s","f"} } }`。
- `record(db, online, now)`：当前桶 s/f +1，经 `set_body_memory` 持久化。
- `predict(now)`：`P = (α+s)/(α+β+n)`，α=β=1；无计数 → 0.5。
- `surprise(online, now)`：`-log(P)` 若 online 否则 `-log(1-P)`，P 夹到 ε…1−ε。
- `snapshot(now)` → `{predicted_online, surprise, bucket}`。
- **适配点（预判）**：Brain 构造时 `_db` 尚未挂上，无法在 `__init__` 真读库；拟 **首次 `record`/`update` 时 lazy `get_body_memory`**，等价「重启不丢」，偏离方案字面「构造时加载」。

### `qi/world/model.py`（WorldModel）
- `self.online = OnlineRhythm()`；`self.domains` 预留多域。
- `update(brain, now)`：`record(..., online=brain.user_online)`（心跳空窗 = 缺席失败，对齐主线 v2 可测规则）。
- `snapshot` → `{"online_rhythm": ...}`。
- **不**接 GWS / 不改 proactive/explore。

### `qi/core/brain.py`
- `__init__`：`self.world = WorldModel()`；`self.last_world = None`。
- `_heartbeat`：传感采集之后、`determine_mode` 前后均可；try/except 更新 world → `last_world`，失败则 `last_world = None`。

### `qi/core/trace.py`
- `motive_snapshot` 增 `world_surprise`（来自 `last_world.online_rhythm.surprise`）；不改 `persist_broadcast` 签名。

### 纪律红线自检意图
1. 只增信号  
2. 零新依赖、复用 body_memory、不新建表（主线【文件】里「或新增 online_events」以本 PR 方案为准：**不建表**）  
3. update 不依赖 LLM  
4. 新增 `tests/test_world_online_rhythm.py`（含 Brain 一拍落库查 motive）

### 拿不准 / 已自决
- 方案写「构造时从 set_body_memory 读」→ 应为 `get_body_memory`；加载时机见上 lazy。  
- 无 `_db` 时：仍更新内存桶，跳过持久化，保证单测/冷启动不抛。

本段写完即继续写码，不阻塞等待方案 Agent。

---

## 【完工结果段】

### 落地摘要

| 路径 | 动作 |
|------|------|
| `qi/world/__init__.py` | 新增 |
| `qi/world/online_rhythm.py` | 新增 `OnlineRhythm`（桶计数 + 贝塔后验 + surprise + body_memory） |
| `qi/world/model.py` | 新增 `WorldModel`（`domains` 预留多域） |
| `qi/core/brain.py` | `__init__` 挂 `world`/`last_world`；`_heartbeat` 传感后 `update`+`snapshot` |
| `qi/core/trace.py` | `motive_snapshot` 注入 `world_surprise` |
| `tests/test_world_online_rhythm.py` | 新增 9 用例 |
| `qi/storage/database.py` | **未改**（复用 `get/set_body_memory`，无新表） |
| `proactive.py` / `gws.py` / `explore.py` | **未改** |

### 是否 100% 照方案 / 偏离点

| 项 | 说明 |
|----|------|
| lazy load | 方案写「构造时读 body_memory」；实际 **首次 `record` 时 `get_body_memory`**（Brain 构造时尚无 `_db`） |
| surprise 时序 | 先按更新前 `predict` 算 surprise，再 s/f+1（贝叶斯预测误差惯例；方案未写死顺序） |
| `record` 返回值 | 额外返回本拍 surprise（内部用）；对外 API 仍以 `snapshot` 为主 |
| 无 db | 仍更新内存桶，跳过持久化，不抛 |
| online_events 表 | 主线【文件】曾写「或新增」；**按 PR 方案不建表** |
| 方法名 | 用方案的 `predict` / `surprise`（非主线草稿的 `predict_now`） |

### 测试结果

```
python -m pytest -q tests/test_world_online_rhythm.py  → 9 passed
python -m pytest -q                                   → 343 passed in 54.10s
python -m ruff check qi tests                         → All checks passed!
```

### 纪律红线自查

1. **只增信号** ✅ 未改 proactive/gws/explore 触发或权重  
2. **零新依赖 / body_memory** ✅ 标准库 `math`；key=`world.online_rhythm`  
3. **拔管安全** ✅ `test_fake_provider_world_update_still_runs`：FailLLM 下仍写桶  
4. **痕迹可见** ✅ `motive_json.world_surprise` 在 heartbeat 后可查  

### 交回方案 Agent 验收建议

请对照 PR 方案验收清单勾选：桶计数、predict 收敛、surprise 排序、缺席降预测、`world_surprise` 落库、domains 预留、拔管、pytest/ruff。  
偏离点仅 lazy load / surprise 先算后更——若方案 Agent 要求改成「构造时加载」需另挂 `Brain` 接 db 钩子，当前无必要。

---

*Cursor 编码回执 · 包 9 · 2026-08-02*
