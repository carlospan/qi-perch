# L7 curiosity 候选解堵——Cursor 编码回执

> **角色**：Cursor（执行侧）  
> **依据**：[编码请求](./2026-08-08-L7-curiosity候选解堵-编码请求.md)（明示可编码）+ 修订后 PR  
> **方向**：A  
> **时刻**：2026-08-08  

---

## 完工段

### 执行判断

相对编码请求 **4 处均已落地**，禁改清单未触。可选说明性测 **未加**（防回归已由 B1 翻改覆盖；说明性测不阻塞验收）。

| # | 请求 | 落地 |
|---|------|------|
| 1 | 删 `trace.py` 包 10 curiosity 注入；形参保留 | ✓；另加 `del curiosity`（见偏离） |
| 2 | `test_collect_contenders_curiosity_gate` L127 → `assert not any(...)`；不新增「arbitrate 选 share」 | ✓ |
| 3 | `curiosity.py` 模块 docstring 补回退说明；逻辑/`contender()` 不动 | ✓ |
| 4 | L7-action.md / progress.md / 排查包文首回写 | ✓ |

### 偏离说明

1. **`collect_contenders` 内 `del curiosity`**：形参按请求保留后函数体不再消费，对齐仓库「接口预留」写法（同 `curiosity.py` 的 `del now`），避免未使用形参告警。行为无影响。  
2. **未加可选说明性测**：价值低、不阻塞；防回归靠翻改后的 collect 断言。

### 自测

| 命令 | 结果 |
|------|------|
| `pytest tests/test_motivation_curiosity.py tests/test_gws.py -q` | **22 passed** |
| `pytest -q` 全量 | **472 passed，1 failed** |

**失败项**：`tests/test_doc_links.py::test_integration_repo_clean`  
**原因（非本包代码回归）**：`docs/specs/tasks/` 下多份任务/方案文档使用 `file:///d:/qi-perch/...` 绝对链接；`tools/check_doc_links.py` 不跳过 `file://`，一律当相对路径 → 死链。涉及 L6 卡片包与本 L7 包的方案/任务/排查/编码请求等（编码前即存在；删注入后 `#L517-L525` 锚点亦会失效，但即便无锚点 `file://` 本身仍死）。  
**本包交付文件**（`qi/core/trace.py`、`qi/motivation/curiosity.py`、`tests/test_motivation_curiosity.py`、L7-action / progress）**无**该测死链。  
**建议（交方案 Agent，不并本包改 tools）**：任务文档改相对路径 `./xxx.md` / `qi/...`，或 checker 跳过 `file://`。

功能面：curiosity 注入已删、翻改测绿、gws/brain/volition/settings/`salience(kind="curiosity")` 未动。

### git diff 预期范围

- `qi/core/trace.py`（删注入 + `del curiosity`）
- `qi/motivation/curiosity.py`（docstring）
- `tests/test_motivation_curiosity.py`（断言翻改）
- `docs/reference/layers/L7-action.md`
- `docs/progress.md`
- `docs/specs/tasks/2026-08-08-L7-share停滞排查.md`
- 本回执 + 流程中的审查/请求 md（若一并纳入）

### 验收交接

请方案 Agent 做实施验收（`-验收记录.md`）：

- [x] Cursor 侧：注入已删、测已翻、docstring/文档已回写  
- [ ] 方案侧：核 git diff + 全量 pytest 口径（含 doc_links 是否另开修链）  
- [ ] 方案侧：broadcast_traces 数据核对（outcome / action / winner_arb≠curiosity）  
- [ ] 维护者：相处层触发 share「那句+卡片」

**状态：编码完工，交实施验收。**
