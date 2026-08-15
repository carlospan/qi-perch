# L7 curiosity 候选解堵——实施验收记录

> 验收方：方案 Agent（Trae）
> 验收对象：[Cursor 编码回执](./2026-08-08-L7-curiosity候选解堵-Cursor编码回执.md)
> 依据：[编码请求](./2026-08-08-L7-curiosity候选解堵-编码请求.md) + 修订后 [PR 方案](./2026-08-08-L7-curiosity候选解堵-PR方案.md)
> 日期：2026-08-08

---

## 一、逐点核对（git diff + 文件实读）

| 改动点 | 请求 | 落地 | 判定 |
|--------|------|------|------|
| **A** trace.py 删包 10 注入；形参保留 | [L517-525](file:///d:/qi-perch/qi/core/trace.py#L517-L525) 块删 | ✓ 块已删；`curiosity` 形参保留 + `del curiosity`（见 §二偏离） | ✓ |
| **B** test L127 翻 `not any`；不新增「arbitrate 选 share」 | [test:127](file:///d:/qi-perch/tests/test_motivation_curiosity.py#L127) | ✓ `assert not any(c.kind == "curiosity" ...)`；未新增该测 | ✓ |
| **C** curiosity.py docstring 回退说明；逻辑/`contender()` 不动 | 模块 docstring | ✓ 补「（contender 入场已回退，2026-08-08，见解堵包）」；逻辑未改 | ✓ |
| **D** 文档回写（L7-action / progress / 排查包文首） | 3 处 | ✓ L7-action 演进指向(+1) / progress Gap2 叙事(+2) / 排查包文首「已修，见解堵包」 | ✓ |

**禁改清单核对**（git diff --stat 仅 6 文件：trace.py / test / curiosity.py / L7-action / progress / tasks/README）：
- `gws.py` / `brain.py` / `volition.py` 未触 ✓
- `motivation/curiosity.py` 逻辑未改（仅 docstring）✓
- `settings.yaml`（gws.enabled / 日限 20）未触 ✓
- `salience(kind="curiosity")` 分支保留 ✓（`test_salience_curiosity_branch` 仍绿）

## 二、偏离记录

**`del curiosity`（[trace.py:339](file:///d:/qi-perch/qi/core/trace.py#L339)）**——Cursor 在 `collect_contenders` 函数首行加 `del curiosity`，标注形参保留但函数体不再消费。

- 动机：对齐仓库「接口预留」写法（同 `curiosity.py` 的 `del now`），避免未使用形参告警。
- 行为影响：**无**（删除注入块后 `curiosity` 在函数内已无消费点，`del` 仅释放局部名）。
- 判定：**接受**。行为中性、标注清晰；非实质偏离。

## 三、测试复跑

| 命令 | 结果 |
|------|------|
| `pytest tests/test_motivation_curiosity.py tests/test_gws.py -q` | 22 passed（Cursor） |
| `pytest -q` 全量 | **472 passed / 1 failed**（76.5s，方案侧独立复跑） |

**失败项**：`tests/test_doc_links.py::test_integration_repo_clean`

**判定：预存在失败，非本包代码回归。** 证据：
- `git grep -l "file:///" HEAD -- docs/` → **2 个已提交文档**含 `file://` 链 → HEAD 上 `test_doc_links` 本就红（L6 commit/push 后即如此）。
- 本包**代码改动文件**（trace.py / test / curiosity.py / L7-action / progress）**无**该测死链。
- 失败列表含本会话新建的任务文档（相处验证收口等，未提交），与 L6 已提交文档同属 `file:///` 绝对链模式——同一预存在失败模式的新实例，非本包引入。

**根因（交维护者，不并本包）**：`tools/check_doc_links.py` 不跳过 `file://`，一律当相对路径判死链；而仓库 Code Reference 约定用 `file:///` 绝对链（IDE 可点）。两者冲突。修法二选一（另开小包）：checker 跳过/正确校验 `file://`；或任务文档改相对路径 `./xxx.md`（但失 IDE 点击）。

## 四、数据核对口径（broadcast_traces）

**本包代码层证明（已足）**：`collect_contenders` 不再返回 `kind="curiosity"`（B 翻改测绿为证）→ `arbitrate` 不再有 curiosity 候选 → winner 不可能是 curiosity → `action:share`（0.30）在可执行候选中可胜出。机制闭合。

**broadcast_traces outcome 分布恢复** = 需运行时心跳跑一段。**归入相处层验收**（维护者触发 share 时，`outcome=action` + `winner_arb=action:share` 重新出现即证；卡片真机出现即闭环 Gap 1）。方案 Agent 不跑全栈运行时。

## 五、纪律红线对照

| 红线 | 对照 |
|------|------|
| R1–R5 / contract | 不涉（纯行动层 bug 修复） |
| 不引入 Agent 框架 | ✓ 只删候选注入，符 L7 原则 #1 |
| LLM 走 gateway / DB 走 database | 不涉 |
| 不开新阶段 / 不触路线 | ✓ bug fix；explore 真搜索 = C 另开包 |
| 常量默认值同步 | 不涉（settings 未改） |

## 六、结论

**工程验收通过**（含 `del curiosity` 偏离，已接受）。

- 4 改动点全落地、禁改清单未触、纪律红线全过。
- 全量 472 passed / 1 failed，失败为预存在 `test_doc_links`（HEAD 本就红，非本包回归）。
- 机制层证明已足（collect 不含 curiosity → action 可胜出）。

## 七、待办（非本包）

1. **相处层（维护者，必须）**：触发 share → 验「那句 + ActionCard」+ 递出脆弱/纸感手感（[相处验证收口](./2026-08-08-相处验证收口.md) 批次 0 闭环 Gap 1）；同时 broadcast_traces `outcome=action` 重新出现证 Gap 2 闭合。
2. **test_doc_links cleanup（维护者拍板，另开小包）**：checker 跳过 `file://` 或任务文档改相对路径——与 Code Reference `file:///` 约定冲突的解法选择。
3. **顶层 README.md 有 95 行未提交改动**（git diff --stat 显示，非本包、非 Cursor 触碰）——预存在 WIP，与维护者确认是否纳入后续提交。
4. **方向 C（explore 真搜索）**：Gap 2 深层根因（curiosity 无真出口）；本包 A 已解堵，C 治本另开包拍板。

## 八、可追认

- 方向 A 维持（审查 + 复审 + 本验收一致）。
- `del curiosity` 偏离接受（行为中性）。
- test_doc_links 不并本包（预存在失败）。
