# 包 10 实施 PR · Cursor 编码回执

> **用途**：开工前理解确认 + 完工结果；交方案 Agent（CodeBuddy）实施验收。  
> **依据**：`包10-PR方案-Cursor编码请求.md`、`specs/tasks/2026-08-02-阶段三-包10-PR方案.md`、主线 v2 包 10。  
> **撰写**：Cursor（2026-08-02）

---

## 【开工前理解确认段】

已读取包 10 PR 方案与编码请求。关键改动点理解：

### `qi/motivation/curiosity.py`（CuriositySignal）
- `update(brain, now)`：读 `last_world.online_rhythm.surprise`、open_loop 长度、当前 `emotion.curiosity`（保留 anomaly）；合成 `clamp01(base + w_world*surprise + w_loop*loop_norm)`，写回 `emotion.curiosity`；不依赖 LLM。
- `contender()` / 经 `collect_contenders` 入场 `kind="curiosity"`。

### `trace.collect_contenders` / `salience`
- `salience` 增 curiosity 分支；`collect_contenders(..., curiosity=)` 在 curiosity>0 时追加竞争者。
- **自决**：仅当 `pending is None` 时追加（对齐红线「respond 恒胜 / 无 pending 才参与」）。
- `motive_snapshot` 已有 `curiosity` 字段 → **保留不重复加**，视为已满足溯源。

### `brain` 接入
- 方案写在 `_gws_broadcast` 内 `update`；**自决**：与包 9 同，在 `_heartbeat`（world 更新后）调用 `CuriositySignal.update`，保证 legacy / persist / GWS 路径都能写 `emotion.curiosity`；`_heartbeat_gws_idle` 把该值传入 `collect_contenders`。

### 三个随机动机源改造
| 点 | 改法 |
|----|------|
| `dream.maybe_dream` | `curiosity < 0.55` → skip（reason=`curiosity_low`）；加权抽保留+注释 |
| `creativity.maybe_create` | 好奇≥阈值 **或** 情绪强度≥阈值才创作；去纯随机 |
| `consciousness.should_trigger_meta` | `curiosity >= 0.5` 且非 awake |

### 保留并加注释
layer L207 / explore drift 时机阀 / dream shuffle·choice·mention / share choice / brain sleep / creativity share 0.25 / loop_backlog 随机。

### 拿不准
- curiosity 胜出 GWS 时无专属分发（方案未写）→ 按「动机只是大声」落空闲，不另开 explore 分发。
- 将同步改 `tests/test_inner_life.py` 中依赖 meta 概率 / dream probability_miss 的旧测。

本段写完即继续写码，不阻塞等待方案 Agent。

---

## 【完工结果段】

### 落地摘要

| 路径 | 动作 |
|------|------|
| `qi/motivation/__init__.py` | 新增 |
| `qi/motivation/curiosity.py` | 新增 `CuriositySignal`（surprise+loop 代理，剥旧加成防顶满） |
| `qi/core/trace.py` | `salience` curiosity 分支；`collect_contenders(curiosity=)`；persist 回退路径传 curiosity |
| `qi/core/brain.py` | `step_emotion` 后 `CuriositySignal.update`；GWS idle 传入 curiosity；投递 sleep 注释 |
| `qi/core/gws.py` | `kind_family`/`_FAMILY_RANK` 认 curiosity |
| `qi/inner_life/dream.py` | WHETHER→`DREAM_CURIOSITY_MIN`；表达层/加权/提梦注释 |
| `qi/inner_life/creativity.py` | WHETHER→好奇或高情绪；提起 0.25 注释保留 |
| `qi/inner_life/consciousness.py` | meta→`META_CURIOSITY_MIN`；loop_backlog 时机阀注释 |
| `qi/action/layer.py` / `explore.py` / `share.py` | 时机阀/表达层注释 |
| `tests/test_motivation_curiosity.py` | 新增 |
| `tests/test_inner_life.py` | meta/dream 旧测对齐包 10 |

### 是否 100% 照方案 / 偏离点

| 项 | 说明 |
|----|------|
| update 位置 | 方案写 `_gws_broadcast` 内；实际在 `_heartbeat`（`step_emotion` 后）以覆盖 legacy/GWS/persist |
| 防顶满 | 方案 `base+boost` 会跨拍累加；实现剥 `_curiosity_motive_boost` 再叠本拍信号 |
| curiosity 入场 | 仅 `pending is None`（方案片段未写，红线要求） |
| motive_snapshot | 已有 `curiosity` 字段，未重复添加 |
| GWS 胜出分发 | curiosity 胜出无专属 execute（动机只是大声）；explore 仍走 action |
| 类名 | 创作为 `Creativity`（非方案口误 `CreativityEngine`） |

### 测试结果

```
python -m pytest -q tests/test_motivation_curiosity.py tests/test_inner_life.py  → 42 passed
python -m pytest -q  → 355 passed in 66.44s
python -m ruff check qi tests  → All checks passed!
```

### 纪律红线自查

1. **respond 恒胜** ✅ pending 时不注入 curiosity；arbitrate 测覆盖  
2. **零新依赖** ✅  
3. **时机阀/表达层随机保留+注释** ✅  
4. **拔管** ✅ `test_fake_provider_curiosity_update`

### 交回方案 Agent 验收建议

对照 PR 验收清单勾选；重点看偏离点「防顶满」与「update 位置」是否接受。建议 `grep -rn "random\." qi/` 复核 WHETHER 仅剩时机阀/表达层。

---

*Cursor 编码回执 · 包 10 · 2026-08-02*
