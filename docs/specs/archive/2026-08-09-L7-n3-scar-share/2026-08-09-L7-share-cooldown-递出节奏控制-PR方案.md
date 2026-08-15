# L7 share cooldown（递出节奏控制）——PR 方案

> **角色**：Trae（方案 Agent）；编码交 Cursor
> **依据**：[任务包](./2026-08-09-L7-share-cooldown-递出节奏控制-任务包.md)
> **对照代码**：`qi/action/share.py`（`try_share` L137-152）、`qi/action/explore.py`（cooldown 先例 L98-122）、`qi/config/settings.example.yaml`（L88-105）
> **时刻**：2026-08-09

---

## 外部可观测行为

1. share 递出成功后 2 小时内不再递（cooldown）
2. cooldown 可通过 config `action.share_cooldown_hours` 覆写
3. 日限 20 仍作安全阀

## 精确改动点

### 1. `qi/action/share.py` 加 cooldown 门控（对称 explore external）

**常量区**（L21 后加）：
```python
SHARE_COOLDOWN_HOURS = 2.0
SHARE_LAST_KEY = "share_last"
```

**`__init__`**（L56-62）加 config：
```python
def __init__(
    self,
    db: Database,
    narrative: NarrativeMemory | None = None,
    *,
    config: dict | None = None,
):
    self.db = db
    self.narrative = narrative
    self.config = config or {}
```

**新增方法**（对称 explore `_external_cooldown_ok` / `_mark_external`）：
```python
async def _share_cooldown_ok(self, now: datetime) -> bool:
    hours = float(
        (self.config.get("action") or {}).get("share_cooldown_hours", SHARE_COOLDOWN_HOURS)
    )
    raw = await self.db.get_body_memory(SHARE_LAST_KEY)
    if not raw:
        return True
    try:
        if isinstance(raw, dict):
            ts = str(raw.get("at") or raw.get("timestamp") or "")
        else:
            ts = str(raw)
        last = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return True
    return now - last >= timedelta(hours=max(0.0, hours))

async def _mark_share(self, now: datetime) -> None:
    try:
        await self.db.set_body_memory(
            SHARE_LAST_KEY,
            {"at": now.isoformat(timespec="seconds")},
        )
    except Exception:
        pass  # 落盘失败不阻断递出
```

**`try_share`** L137-152 改：cooldown 检查插在 `can_share` 后、`load_unshared_creation` 前；`_mark_share` 在 `deliver` 后：
```python
async def try_share(
    self,
    emotion: EmotionState,
    relationship_stage: str,
    budget: ActionBudget,
    *,
    season: str = "spring",
    now: datetime | None = None,
) -> dict | None:
    now = now or datetime.now()
    if not can_share(relationship_stage):
        return None
    if not budget.can_autonomous(now):
        return None
    if not await self._share_cooldown_ok(now):   # 新增
        return None
    creation = await self.db.load_unshared_creation()
    if not creation:
        return None
    card = await self.deliver(
        creation,
        emotion,
        relationship_stage,
        season=season,
        now=now,
    )
    budget.record("share", now)
    await self._mark_share(now)                   # 新增
    return card
```

> `timedelta` 需补 import（现有 share.py 只 import `datetime`，需加 `from datetime import datetime, timedelta`）。

### 2. `qi/action/layer.py` 构造 ShareAction 处（L68）补 config

**现状**：`self.share = ShareAction(db, narrative=narrative)`

**改为**：`self.share = ShareAction(db, narrative=narrative, config=self.config)`

### 3. `qi/config/settings.example.yaml` L89 下补注释行

```yaml
action:
  autonomous_daily_limit: 20
  share_cooldown_hours: 2       # 递出后冷却（默认 2h，与 explore_external 对称）
  season_scale:
    ...
```

## 纪律红线对照

- **R1**：不改内容真实性 ✓
- **Step 5**：share 仍 insert_action ✓
- **生命节奏**：2h cooldown 限制频率，保留日限 20 安全阀 ✓

## 测试计划与验收清单

### 新增测试（`tests/test_share_cooldown.py` 或合入现有 share 测试）

1. `test_share_cooldown_blocks_within_window`：刚递出后 cooldown_ok → False
2. `test_share_cooldown_allows_after_window`：2h 后 cooldown_ok → True
3. `test_share_cooldown_config_override`：config `share_cooldown_hours: 0.5` → 30 分钟后 ok
4. `test_share_cooldown_no_record_first_time`：无 body_memory → ok（首次递出）
5. `test_try_share_respects_cooldown`：集成测试——连续两次 try_share，第二次 None

### 验收清单

- [ ] 连续心跳不连递两条 share
- [ ] `settings.example.yaml` 有 `share_cooldown_hours` 注释行
- [ ] 全量 ≥587 passed

## 风险 / 不确定点

- **R1**：`timedelta` import——现有 share.py 只 `from datetime import datetime`，需补 `timedelta`
- **R2**：`_mark_share` 失败不阻断递出——与 explore `_mark_external` 对称

## 需维护者拍板项

- HITL cooldown 2 小时——维护者已定

---

*Trae 方案 Agent · 2026-08-09 · 编码交 Cursor · 本方案 Agent 不写 qi/ 代码*
