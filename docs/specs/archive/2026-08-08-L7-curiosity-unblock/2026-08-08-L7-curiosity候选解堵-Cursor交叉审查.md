# L7 curiosity 候选解堵——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：`2026-08-08-L7-curiosity候选解堵.md`、`...-PR方案.md`、`...-L7-share停滞排查.md`  
> **对照代码**：`qi/core/trace.py` L517–525、`qi/core/gws.py`、`qi/motivation/curiosity.py`、`tests/test_motivation_curiosity.py`  
> **时刻**：2026-08-08  

---

## 总判

**方向 A 正确、根因证据充分，可修；但有 2 处测试口径必须先改 PR，再编码（阻塞）。**

删掉 `collect_contenders` 里包 10 的 `kind="curiosity"` 注入，对症：该候选 salience≈curiosity（常 >0.3），族秩高于 action，胜出后不在 `_EXECUTABLE_FAMILIES`、brain 无分支 → idle，堵死 share/archive/tend/explore。与排查包数据（08-03 起 action=0、winner_arb=curiosity）一致。

---

## 认可

1. **最小对症**：只删注入块，不动 gws / brain / volition / motivation 计算——符合 bug fix、一次一包。  
2. **motive 保留路径清晰**：`CuriositySignal.update` → `emotion.curiosity`；`volition` 仍可用 curiosity 驱动 `action:explore`。  
3. **`salience(kind="curiosity")` 默认保留**：正确——`tests/test_motivation_curiosity.py::test_salience_curiosity_branch` 仍调用；**勿因「注入删除」顺手删 salience 分支**。  
4. **纪律 / 不扩 C**：explore 真搜索另开包——同意。  
5. **风险 2（explore 压 share）** 已诚实标明，可接受为后续调参，不并本包。

---

## 必须整改（阻塞编码）

### B1. 既有测试仍断言「应注入 curiosity」——PR 未点名

`tests/test_motivation_curiosity.py::test_collect_contenders_curiosity_gate`（约 L108–147）当前：

```python
assert any(c.kind == "curiosity" for c in with_c)  # curiosity=0.8
```

按方向 A 落地后此测必红。PR §四只写「新增 2 条」，**未写翻改本测**。

**整改**：PR 明确——将该测改为「`pending=None + curiosity=0.8` 时**不含** `kind="curiosity"`」；`curiosity=0.0` / `pending` 分支可合并或删冗余。验收栏 git diff 允许含该测试文件（任务包写「仅 trace.py + 文档」过窄，须放宽为 trace + 测试 + 文档）。

### B2. 拟新增测试 2 与「不改 gws」矛盾

PR §四：

> `arbitrate` 在含 `action:share`(0.30) + 旧 curiosity 候选场景下选 `action:share`

现行 `gws.arbitrate` **按 salience 取高**：curiosity(0.9) **会赢过** share(0.30)；且 curiosity 族秩 15 > action 10。在**不改 gws.py** 的前提下，此断言为假，无法作为「防回归」。

**整改（择一写进 PR）**：
- **推荐**：删掉该条；防回归只靠 B1 翻改后的 `collect_contenders` 断言（+ 可选：手造 contenders 列表证明「若误注入则 curiosity 仍会赢」作说明性测试，**不**要求选 share）。  
- 或：若坚持「有 curiosity 候选时仍选 share」→ 必须改 `gws`/`_FAMILY_RANK`/`executable` 过滤——那是另一方向，超出本包 A，需 pivot。

---

## 非阻塞（编码时注意）

| # | 意见 | 建议 |
|---|------|------|
| N1 | `CuriositySignal.contender()` 与模块文案「可作为 GWS 竞争者入场」将成为死路径 | 本包可不删方法（最小改动）；建议顺手改 `curiosity.py` 模块 docstring 一句，避免后人再接回注入 |
| N2 | 任务包验收「git diff 仅 trace.py + 文档」 | 与必改测试冲突；以「trace + 相关测试 + 文档」为准 |
| N3 | 测试落点 | 优先改 `tests/test_motivation_curiosity.py`；不必新建文件 |
| N4 | 方向 B/C | **本包维持 A**；B/C 编码前若维护者 pivot 再重写 PR。审查侧倾向 A（立即解堵），C 另包治本 |

---

## 开工前理解确认（禁码）

若 PR 按 B1/B2 整改后放行，编码将：

1. 删除 `trace.py` `collect_contenders` 内 L517–525 包 10 curiosity 注入块。  
2. 保留 `curiosity` 形参与 `salience(kind="curiosity")`。  
3. 翻改 `test_collect_contenders_curiosity_gate` → 断言不含 curiosity；不按错误的「arbitrate 选 share」写测。  
4. 回写 L7-action.md / progress.md / 排查包文首。  
5. 不改 gws / brain / volition / curiosity 计算逻辑（docstring 微调除外，若方案采纳 N1）。

**需澄清**：无（B1/B2 为方案须改，非代码未决）。

**状态**：交叉审查已落盘；**有阻塞项 → 路 B**。请方案 Agent 修订 PR 后出整改说明；Cursor 再出整改复审，**获明示可编码前不写 `qi/`**。

---

## 给维护者（方向 A/B/C）

审查侧同意方案倾向：**先 A 解堵，C 另开**。  
不必为了「审完才发现要换方向」而卡住——除非你明确要本包改 gws（偏 B）或并进真搜索（C）。  
请对 **A** 追认（或 pivot）；B1/B2 交给 Trae 改 PR 即可。
