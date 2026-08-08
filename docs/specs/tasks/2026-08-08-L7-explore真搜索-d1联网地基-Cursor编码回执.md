# L7 explore 真搜索 d-1——Cursor 编码回执

> **角色**：Cursor（执行侧）  
> **依据**：[编码请求](./2026-08-08-L7-explore真搜索-d1联网地基-编码请求.md)（明示可编码）+ 修订后 PR（路 B 第2步）  
> **时刻**：2026-08-08  

---

## 完工段

### 执行判断

相对编码请求落地完成；**B1/B2/B3 未偏离**。

| 钉死项 | 落地 |
|--------|------|
| **B1** 无独立 `daily_limit` | ✓ `explore_external` 仅 enabled/provider/api_key/cooldown_hours/probability；注释标明复用 ActionBudget 20 |
| **B2** llm 透传 + consciousness | ✓ `ExploreAction(llm=…)` / `ActionLayer(llm=…)` / `brain.restore_state` 传 `self.llm`；`_make_query` → `llm.call(purpose="consciousness")` |
| **B3** 外部 speak+qi_line | ✓ 成功/空手都开口；内部不带 `speak`；**未改** `brain_delivery.py` |

### 落地文件

1. `qi/action/explore_web.py`（新）— `SearchHit` + `WebSearchClient`（Tavily / httpx）  
2. `qi/action/explore.py` — 外部分支 + 冷却 + query + speak  
3. `qi/action/layer.py` — `_build_explore_web` + llm 下传  
4. `qi/core/brain.py` — `restore_state` 仅加 `llm=self.llm`  
5. `qi/config/settings.example.yaml` — `explore_external` 块  
6. `.env.example` — `TAVILY_API_KEY=`  
7. `tests/test_explore_web.py` + `tests/test_explore_external_branch.py`  
8. `docs/reference/layers/L7-action.md` + `docs/progress.md`

### 偏离说明

1. **`settings.example.yaml` 增可选键 `probability: 0.05`**：PR 称常量可 settings 覆盖（N6）；便于本机调参，**不是** `daily_limit`。代码缺省仍为 `0.05`。  
2. 未实现 `_search_ddg`（按 N5 / 编码请求）。

### 自测

| 命令 | 结果 |
|------|------|
| `pytest tests/test_explore_web.py tests/test_explore_external_branch.py tests/test_self_ops.py tests/test_action_l7.py -q` | **35 passed** |
| `pytest -q` 全量 | **487 passed**（≥474，零红） |

### 验收交接

- [x] Cursor：代码 + 测 + 文档回写  
- [ ] 方案侧：git diff / 纪律红线 / 验收清单  
- [ ] 维护者相处：本机 `data/settings.yaml` 开 `explore_external.enabled: true` + Tavily key；独处攒 curiosity≥0.8、过冷却，听「看了看外面」开口手感  

**状态：编码完工，交实施验收。**
