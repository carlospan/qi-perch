# L7 curiosity 候选解堵——编码请求

> 角色：方案 Agent（Trae）→ Cursor
> 依据：修订后 [PR 方案](./2026-08-08-L7-curiosity候选解堵-PR方案.md)（§二 A–F、§四、§七）+ [任务包](./2026-08-08-L7-curiosity候选解堵.md) 验收栏 + [整改复审](./2026-08-08-L7-curiosity候选解堵-整改复审.md)（B 项已关闭）
> 方向：**A**（复审维持；维护者异步追认不卡本线）
> **本文件 = 明示可编码**。Cursor 按本请求 + 修订后 PR 编码。

---

## 编码范围（精确改动点）

### 1. `qi/core/trace.py` — 删除包 10 curiosity 候选注入

**位置**：`collect_contenders(...)` 内 [L517-L525](file:///d:/qi-perch/qi/core/trace.py#L517-L525)

**删整块**：
```python
    # 包 10：curiosity 竞争者仅在无用户消息时入场（respond 恒胜）
    if pending is None and curiosity > 0.0:
        candidates.append(
            Contender(
                kind="curiosity",
                salience=salience(kind="curiosity", curiosity=curiosity),
                reason="learning-progress 好奇驱动",
            )
        )
```
删除后 `return candidates` 紧接上一行。**`collect_contenders` 的 `curiosity` 形参保留**（调用方仍传；`volition` explore 候选 + `motivation/curiosity` 写回仍用）。

### 2. `tests/test_motivation_curiosity.py` — 翻改既有测（吸收 B1）

**位置**：[L108-L150](file:///d:/qi-perch/tests/test_motivation_curiosity.py#L108-L150) `test_collect_contenders_curiosity_gate`

**改 L127**：
```python
# 旧：assert any(c.kind == "curiosity" for c in with_c)
assert not any(c.kind == "curiosity" for c in with_c)   # curiosity=0.8 时不再注入
```
- `without`（curiosity=0.0，L128-137）原已 `assert not any`，保留不变。
- `pending`（L139-149）原已断言不注入 curiosity，保留不变。
- **不新增**「arbitrate 选 share」测（吸收 B2）。
- **可选说明性测**（编码时按价值决定，不加不阻塞验收）：手造 `[Contender(kind="curiosity", salience=0.9), Contender(kind="action:share", salience=0.30)]` 喂 `arbitrate`，断言选 curiosity——说明「若误注入则 curiosity 仍会赢，故须在 collect 层拦」，**不**要求选 share。

### 3. `qi/motivation/curiosity.py` — docstring 微调（采纳 N1）

模块 docstring 原句「并可作为 GWS 竞争者入场」补后缀：「（contender 入场已回退，2026-08-08，见解堵包）」。**方法 `contender()` 不删**；逻辑不改。

### 4. 文档回写（防 drift · SDD §四）

- [docs/reference/layers/L7-action.md](file:///d:/qi-perch/docs/reference/layers/L7-action.md) 文首演进指向：补「2026-08-08：包 10 curiosity 候选注入回退（空赢仲裁堵死自主行动，已解；见解堵包）」。
- [docs/progress.md](file:///d:/qi-perch/docs/progress.md)：补「Gap 2 修复：curiosity 候选回退，L7 自主行动恢复触发」。
- [docs/specs/tasks/2026-08-08-L7-share停滞排查.md](file:///d:/qi-perch/docs/specs/tasks/2026-08-08-L7-share停滞排查.md) 文首：状态补「已修，见解堵包」。

## 禁止改的

- `qi/core/gws.py`（arbitrate / `_FAMILY_RANK` / `_EXECUTABLE_FAMILIES`）
- `qi/core/brain.py`（dispatch）
- `qi/action/volition.py`（action:explore 候选生成）
- `qi/motivation/curiosity.py` **逻辑**（仅 docstring，见 3）
- `qi/config/settings.yaml`（gws.enabled=true / autonomous_daily_limit=20 不变）
- `salience(kind="curiosity")` 分支（[trace.py:152-153](file:///d:/qi-perch/qi/core/trace.py#L152-L153)）—— `test_salience_curiosity_branch` 仍用，**勿清理**。

## 自测 + 回执要求

1. `pytest -q` 全量 ≥ 473 passed（零回归）。
2. 定向跑：`pytest tests/test_motivation_curiosity.py tests/test_gws.py -v`（翻改测 + 仲裁测通过）。
3. 回执 [`-Cursor编码回执.md`](./2026-08-08-L7-curiosity候选解堵-Cursor编码回执.md) 写**完工段**（相对本请求的执行判断 + 偏离说明；可选说明性测加否 + 理由）。

## 验收（方案 Agent 实施验收将照此）

- [ ] trace.py 注入块已删；curiosity 形参保留
- [ ] test_collect_contenders_curiosity_gate L127 翻为 `not any`；未新增「arbitrate 选 share」测
- [ ] gws/brain/volition/curiosity 逻辑未改（仅 docstring）
- [ ] 全量 pytest ≥ 473 passed
- [ ] 文档回写（L7-action.md / progress.md / 排查包）
- [ ] 数据核对（编码后可由方案 Agent 跑）：broadcast_traces outcome=idle 比例下降、action 重新出现、winner_arb=curiosity 不再出现
- [ ] 相处层（维护者，编码后）：触发 share 验「那句+卡片」+ 递出手感

---

## 明示可编码

**B1/B2 已关闭、复审通过、方向 A 维持。本文件即放行件。**

Cursor 可按本编码请求 + 修订后 PR 编码 → 完工回执 → 方案 Agent 实施验收。

> 维护者方向 A 追认 = 异步，不卡本编码线；若维护者编码前 pivot 到 B/C，停手重写（目前无 pivot 信号）。
