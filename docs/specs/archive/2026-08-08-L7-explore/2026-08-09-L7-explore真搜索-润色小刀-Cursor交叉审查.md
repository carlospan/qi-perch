# L7 explore 真搜索 · 润色小刀——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：[任务包](./2026-08-09-L7-explore真搜索-润色小刀-任务包.md)、[PR 方案](./2026-08-09-L7-explore真搜索-润色小刀-PR方案.md)  
> **对照代码**：`qi/action/explore.py`（`_make_query`）、`qi/action/explore_web.py`（`WebSearchClient`）、`qi/action/layer.py`（`_build_explore_web`）、`qi/embodiment/desktop/src/components/ExploreCard.vue`、`qi/config/settings.example.yaml`  
> **时刻**：2026-08-09  

---

## 总判

**路 B——1 处阻塞（B1）。**  

HITL（模块级 `_SEASON_ZH` / 可选 `exclude_domains` 默认空 / 不升 `search_depth`）与「只润色、不扩能力」方向正确；N6/N7 根因（prompt 注入英文 season）成立；「纯中文」软提示可接受；测试骨架可用。  

但 PR 里 `_exclude_domains` **读配置路径与现码构造不一致**（任务包步骤 3 写对了，PR §2 写错了）。按 PR 伪代码落地则配置永不生效。禁码；待 PR 改读法 + 测例 config 形后放行。

另：**N6 现象写了「见闻卡脚」**，实现只改 `_make_query`，卡脚仍会显示英文 `autumn`——见 B2（可收窄 Spec 或补一行展示映射，请 Trae 裁定）。

---

## 核对清单

### 1. N6/N7 · `_make_query` 季节中文

| 项 | 结论 |
|----|------|
| 根因 | ✓ 现码 `explore.py` L142–146：`f"季节={season}；..."`，season 为英文码 |
| `_SEASON_ZH` 模块级常量 | ✓ 与 HITL1 一致；不碰 `season.py` |
| 未知码兜底 `.get(season, season)` | ✓ |
| user 末尾「纯中文」软提示 | ✓ 非硬约束，符合 R2 |
| 不改 digest / 门控 / drift | ✓ |

✓ 可编码（query 路径）。

### 2. N8 · `exclude_domains`（R1 已核实）

**现码构造**（`layer.py` L79–90）：

```python
ext = (self.config.get("action") or {}).get("explore_external") or {}
return WebSearchClient(provider=..., api_key=..., config=ext)
```

→ `WebSearchClient.config` **就是** `explore_external` 子段，不是完整 settings。

| 项 | 结论 |
|----|------|
| 任务包步骤 3：`self.config.get("exclude_domains")` | ✓ **正确** |
| PR §2 `_exclude_domains`：`(self.config.get("explore_external") or {}).get(...)` | ✗ **错误**（多嵌一层，永远读不到） |
| PR 测例 `config={"action":{"explore_external":{...}}}` | ✗ 与生产构造不一致；应传扁平 `{"exclude_domains":[...]}`（或与 `cooldown_hours` 同级字段） |
| 默认空 → payload 不带字段 | ✓ 不改变现状 |
| 非空才写入 payload | ✓ |
| 小写 strip | ✓ |
| 不升 `search_depth` | ✓ HITL3 |

### 3. `settings.example.yaml`

现段有 `cooldown_hours` / `probability`，无 `exclude_domains`。加 `exclude_domains: []` + 注释 ✓。

### 4. 纪律

| 红线 | 结论 |
|------|------|
| 一次一包（N6/N7/N8 同质润色） | ✓ |
| 不碰 season 全局表示 | ✓ |
| LLM 仍 `purpose=consciousness` | ✓ |
| 不引入 agent framework | ✓ |

---

## 必须整改（阻塞编码）

### B1. `WebSearchClient.config` 读法：PR 与任务包/现码矛盾

**事实**：`config=ext`（已是 `explore_external` 字典）。

**整改（须写进 PR §2 + 测试）**：

```python
def _exclude_domains(self) -> list[str]:
    raw = self.config.get("exclude_domains") or []
    if not isinstance(raw, list):
        return []
    return [str(d).strip().lower() for d in raw if str(d).strip()]
```

测例构造对齐生产：

```python
client = WebSearchClient(
    provider="tavily",
    api_key="k",
    config={"exclude_domains": ["music.apple.com", "mojim.com"]},
)
```

空配置：`config={}` 或 `config={"exclude_domains": []}` → payload **不含** `exclude_domains` 键。

> 任务包 §实现步骤 3 已正确；以任务包为准修订 PR，删除「含 `action.explore_external` 路径」的错误伪代码。R1 可标为**已核实**。

### B2. N6「见闻卡脚」与实现范围不一致（请 Trae 二选一）

- **现象表 N6**：见闻卡脚 / query 出现 `autumn`  
- **实现**：只改 `_make_query` prompt  
- **现 UI**：`ExploreCard.vue` `seasonLabel = card.season`（仍是英文码，验证截图卡脚 `autumn`）

**请裁定其一并写回 Spec/步骤**：

| 选项 | 内容 |
|------|------|
| **a（推荐，最小）** | Spec 收窄：本包只保证 **query/开口** 不再带英文季节码；卡脚英文另开或本包注明「已知残留」 |
| **b** | 本包补展示映射：前端 ExploreCard（及若需 ActionCard）用与 `_SEASON_ZH` 同义的春夏秋冬；或后端写卡时附 `season_label`（仍不改全局 season 码） |

未裁定前：若按字面验收「开口不再出现 autumn」而卡脚仍显示，验收会扯皮——故标阻塞澄清。

---

## 建议（不阻塞，编码时注意）

### C1. 测例笔误

PR 样例 `assert purpose == "consciousness"` → 应为 `assert captured["purpose"] == "consciousness"`。

### C2. `test_make_query_unknown_season_fallback`

验收清单有、样例代码无——编码时补上（season=`"unknown"` → prompt 含 `unknown`、不崩）。

### C3. 相处复验

`exclude_domains` 默认空=行为不变；若维护者本机要压 Apple Music，须在 **gitignore 的** `settings.yaml` 自行填域名，勿把黑名单写进 example 默认非空。

---

## 放行条件

1. PR 修订 B1（读法 + 测例 config 形）；R1 改为已核实。  
2. Trae/维护者裁定 B2（a 或 b）并回写 Spec。  
3. 方案审查回复放行后，Cursor 再编码。

---

*交叉审查 · Cursor · 2026-08-09 · 润色小刀 · 禁码*
