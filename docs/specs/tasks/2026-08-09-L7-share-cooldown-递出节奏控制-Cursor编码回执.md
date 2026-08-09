# L7 share cooldown（递出节奏控制）——Cursor 编码回执

> **角色**：Cursor（执行侧）  
> **依据**：[方案审查回复](./2026-08-09-L7-share-cooldown-递出节奏控制-方案审查回复.md)（路 A 放行，明示可编码）+ [PR 方案](./2026-08-09-L7-share-cooldown-递出节奏控制-PR方案.md)  
> **时刻**：2026-08-10  

---

## 完工段

### 改动文件

| 文件 | 改动 |
|------|------|
| `qi/action/share.py` | `SHARE_COOLDOWN_HOURS` / `SHARE_LAST_KEY`；`config`；`_share_cooldown_ok` / `_mark_share`（`logger.debug`+`exc_info`）；`try_share` 插 cooldown + 成功后 mark；`timedelta` import |
| `qi/action/layer.py` | `ShareAction(..., config=self.config)` |
| `qi/config/settings.example.yaml` | `action.share_cooldown_hours: 2` 注释行 |
| `tests/test_share_cooldown.py` | **新增** 五测（窗口内挡 / 窗外放 / config 覆写 / 无记录首递 / try_share 连续尊重 cooldown） |

### 编码注意点落实

1. `_mark_share` 对齐 explore：`logger.debug("share_last 落盘失败", exc_info=True)` + 模块 logger ✓  
2. 扁平键 `action.share_cooldown_hours` ✓  
3. 旧测：既有 `try_share` 同刻第二次为 acquaintance 门控失败，不依赖连递成功——无需改时间戳 ✓  
4. `from datetime import datetime, timedelta` ✓  

### 相对请求的执行判断

- 按 PR 原样 + 审查回复 4 条注意点；无偏离。  
- 集成测不依赖 `load_unshared` 在同秒 created_at 下的稳定排序，只断言 cooldown 挡第二次、窗外递出另一条。

### 自测

- 全量：**592 passed**（≥587）  
- `ruff check`（改动文件）：通过  

### 验收勾选（工程侧）

- [x] 连续 try_share 窗口内第二次 None  
- [x] `settings.example.yaml` 有 `share_cooldown_hours`  
- [x] 全量 ≥587 + ruff  
- [ ] 相处复验（ambient 下不再 ~36s 连递）——交维护者 / 方案侧  

---

*Cursor · 编码回执完工 · 2026-08-10 · 交 Trae 实施验收*
