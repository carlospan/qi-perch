# L7 · explore 真搜索 d-1（联网地基）——PR 方案

> 配套：[2026-08-08-L7-explore真搜索-d1联网地基.md](./2026-08-08-L7-explore真搜索-d1联网地基.md)（任务包）
> **编码交 Cursor；本方案 Agent 不写 `qi/` 代码。**
> <!-- 拍板后微调(2026-08-08)：HITL 1-5 全按推荐落定；撤原草案 `daily_limit: 3`，改复用 ActionBudget 日限 20（不设独立外部日限）——见 §二D / §三 / §四 / §五。非路 B 阻塞整改。 -->
> <!-- 审查后修订(2026-08-08，路 B 第2步)：吸收 Cursor 交叉审查 B1/B2/B3。
>    B1=任务包清 daily_limit 残留（见任务包）；PR 本身上一轮已撤 daily_limit，本轮再核对无残留。
>    B2=补 gateway/llm 接线：§二B ExploreAction 加 llm + _make_query 走 consciousness purpose；§二C ActionLayer 接收 llm 下传 + 建 WebSearchClient；新增 §二C2 brain.restore_state 传 self.llm；§七 scope 加 qi/core/brain.py。
>    B3=钉说出口：§一 Spec + §二B drift 返回带 speak+qi_line；沿用 deliver_action_result 现有 elif 分支，不改 brain_delivery.py；「注入下轮对话」降级延后。
>    下一拍：Cursor 整改复审（逐条核 B1/B2/B3 关闭）→ 编码请求 → 明示可编码前禁码。 -->

---

## 一、外部可观测行为（Spec）

explore 飘出去时新增「向外面看一眼」：curiosity≥0.8 + 独处（由 volition `solitary` 候选保证，不重复判）+ 冷却 6h 过 + 概率0.05 门控 → 发起 web search（query 走 gateway `purpose="consciousness"`）→ 带回真实见闻 → **栖开口说**（`speak=True + qi_line=<栖语气 summary>`，模板化 summary **不二次 LLM**，走 `deliver_action_result` 现有 `elif speak and qi_line` 分支开口，**不改 brain_delivery.py**）+ actions 留痕。搜不到/失败 → found=None、outcome=failed_capability、`qi_line="我看了看外面，没查到什么。不假装看见了。"` 仍开口（诚实空手），不编造。**内部源（`_scan_sandbox`）行为不变、仍不说**（仅 actions 留痕）。

## 二、精确改动点

### A. 新建 `qi/action/explore_web.py` — WebSearchClient

```python
class WebSearchClient:
    """explore 外部源：contemplative drift 时向外面看一眼。
    红线：只返回真搜到的；失败/空 → None。不编造。"""
    def __init__(self, *, provider: str, api_key: str | None, config: dict): ...
    async def search(self, query: str, *, top_k: int = 3) -> list[SearchHit] | None:
        # provider 抽象（首接 Tavily）；HTTP 走 httpx（项目已有依赖）
        # 失败/空 → None（让 drift 落 found=None）
        ...
```
- 数据类 `SearchHit`：`{title, snippet, url}`（只取摘要+源，不取全文——d-1 轻量不当内容处理）
- provider 抽象：d-1 **只实现 `_search_tavily`**（拍板已定）；`_search_ddg` 留 `NotImplementedError`/不写（审查 N5）；用 httpx async
- 不入库（不入 L2/Chroma）；只回 drift 处理

### B. `qi/action/explore.py` — drift() 加外部源分支 + 说出口

**位置**：[`drift()` L123-192](file:///d:/qi-perch/qi/action/explore.py#L123-L192)、[`__init__` L110-121](file:///d:/qi-perch/qi/action/explore.py#L110-L121)

**现状**：飘出（curiosity≥0.65 + 概率）→ `_scan_sandbox(root)` → finding；返回 dict 无 `speak`（不说）

**拟改**：飘出后判 `_should_external` → 外部（带 `speak=True + qi_line` 开口）/ 内部（行为不变、仍不说）。骨架（非完整可合并实现，Cursor 适配）：

```python
# drift() 飘出后（curiosity≥0.65 内部门已过）：
if await self._should_external(curiosity, now):              # 外部分支
    query = await self._make_query(curiosity, emotion, season)
    hits = await self.web.search(query)
    finding = {"entries": [...hits], "source": "web", "query": query} if hits else None
    summary = (f"我刚才看了看 {query}……{hits[0].title}。" if hits
               else "我看了看外面，没查到什么。不假装看见了。")
    speak, qi_line, source = True, summary, "web"
    outcome = OUTCOME_SUCCESS if hits else OUTCOME_FAILED_CAPABILITY   # 空手=能力失败，不形成伤疤
else:                                                          # 内部分支（行为不变）
    finding, summary = self._scan_finding(root)               # 现有 _scan_sandbox 包一层
    speak, qi_line, source, outcome = None, None, "sandbox", OUTCOME_SUCCESS   # 内部仍不说

# drift 返回（外部带 speak+qi_line 开口；内部不带——审查 B3）
return {"type": "explore_drift", "found": finding, "summary": summary,
        "speak": speak, "qi_line": qi_line, "source": source,
        "action_id": ..., "season": season, "curiosity": curiosity}
# insert_action outcome = 上面的 outcome

# _should_external（独处由 volition solitary 候选保证，不重复判 mode——审查 N1）
async def _should_external(self, curiosity, now) -> bool:
    if self.web is None or self.llm is None: return False    # 无 client/llm → 走内部（向后兼容，审查 B2/N8）
    if curiosity < 0.8: return False                         # 比内部(0.65)更严
    if not self._external_cooldown_ok(now): return False     # 冷却 6h
    if random.random() > 0.05: return False                  # 外部概率更低（不像刷新闻）
    return True

# _make_query：走 gateway purpose="consciousness"（复用，温度0.85 发散适合好奇 query；
#              不污染 last_outcome——仅 conversation purpose 刷新；审查 B2）
async def _make_query(self, curiosity, emotion, season) -> str:
    messages = [...]   # 注入「不引用 user_facts / 对话内容」红线 prompt
    return (await self.llm.call(purpose="consciousness", messages=messages)).strip()
```
- `ExploreAction.__init__` 加 `llm: LLMGateway | None = None` + `web: WebSearchClient | None = None`（[L110-121](file:///d:/qi-perch/qi/action/explore.py#L110-L121)）；`web`/`llm` 任一 None → 外部分支禁用（向后兼容现测，审查 B2/N8）
- 冷却：last external time 存 body_memory key `explore_external_last`（复用预算持久化同构，[budget.py](file:///d:/qi-perch/qi/action/budget.py)）；`_external_cooldown_ok` 读之
- `insert_action` outcome：外部空手 → `OUTCOME_FAILED_CAPABILITY`（[permission.py:148](file:///d:/qi-perch/qi/action/permission.py#L148)），不形成伤疤；内部维持 `OUTCOME_SUCCESS`
- **说出口（审查 B3）**：外部成功/空手都带 `speak=True + qi_line`；内部不带 → `deliver_action_result`（[brain_delivery.py:134-137](file:///d:/qi-perch/qi/core/brain_delivery.py#L134-L137)）现有 `elif speak and qi_line` 分支开口，**不改 brain_delivery.py**

### C. `qi/action/layer.py` — 构造传 web client + llm

**位置**：[`__init__` L52-65](file:///d:/qi-perch/qi/action/layer.py#L52-L65) `self.explore = ExploreAction(...)`

**拟改（审查 B2）**：`ActionLayer.__init__` 加 `llm: LLMGateway | None = None` 参数；按 config 建 `WebSearchClient`（`enabled`+`api_key` 配齐才建，否则 `None`）；`ExploreAction(..., web=web, llm=llm)`。tick / execute_kind 调 drift 不变（[L226-235](file:///d:/qi-perch/qi/action/layer.py#L226-L235)、[L289-318](file:///d:/qi-perch/qi/action/layer.py#L289-L318) 不改）。

### C2. `qi/core/brain.py` — restore_state 传 self.llm（审查 B2）

**位置**：[L1156-1158](file:///d:/qi-perch/qi/core/brain.py#L1156-L1158) `self.action = ActionLayer(db, self.config, narrative=self.memory.narrative)`

**拟改（仅构造传参，不改心跳逻辑）**：加 `llm=self.llm`。`Brain.__init__` 已有 `self.llm`（gateway），无需新增字段。

### D. `qi/config/settings.example.yaml` + `.env.example` — 配置块

**位置**：[action: L81-84](file:///d:/qi-perch/qi/config/settings.example.yaml#L81-L84) 下

```yaml
action:
  autonomous_daily_limit: 20
  explore_external:
    enabled: false                  # 默认关，配齐 key 才开
    provider: tavily                # tavily | ddg | ...
    api_key: "${TAVILY_API_KEY}"    # 走 .env（与 deepseek/tokenrhythm 同构，审查 N3）
    cooldown_hours: 6
    # 不设独立 external daily_limit——复用 ActionBudget 日限 20（安全阀）；
    # 外部稀有靠 curiosity≥0.8 高阈 + 冷却6h + 概率0.05（拍板 HITL③）
```

- `.env.example` 加一行 `TAVILY_API_KEY=`（占位，审查 N3）
- `settings.yaml` 在 `.gitignore`，**本机手改不进 diff**（审查 N2）；git 只改 `settings.example.yaml` + `.env.example`

### E. `tests/` — 新增

- `test_explore_web.py`：mock httpx，验 Tavily 成功/失败/空 → hits/None/None
- `test_explore_external_branch.py`：
  - 门控：curiosity<0.8 不外部；≥0.8 + 冷却过 + 概率命中 → 外部；冷却未过 → 走内部
  - **`web=None` / `llm=None` → 走内部防回归**（审查 N8）
  - **`force=True` 与非 force 分别覆盖**（force 跳 0.12 内部门仍吃 0.05 外部门，审查 N7）
  - 红线：外部搜不到 → finding None、drift found=None、outcome=failed_capability、不编造
  - query 隐私红线：断言 gateway 调用 messages 含「不引用 user_facts / 对话内容」红线句
  - **说出口（审查 B3）**：外部结果（成功/空手）带 `speak=True + qi_line`；内部结果不带 `speak`
  - **gateway 接线（审查 B2）**：`_make_query` 调 `llm.call(purpose="consciousness")`（断言 purpose）；`ActionLayer`/`ExploreAction` 注入 `llm` 透传
- 现有 explore 测试不回归（内部源行为不变；`web`/`llm` 缺省走内部）

### F. 文档回写

- `docs/reference/layers/L7-action.md`：explore 段加「外部联网（d-1）」+ 演进指向更新
- `docs/progress.md`：加 d-1 决策记录
- `docs/reference/contract.md`：**不改文字**，但在 d-1 验收清单标「contract drift：自主行动日限 1/天 vs 20，待同步」（防 drift）

## 三、纪律红线对照

| 红线 | 对照 |
|------|------|
| R1–R5 / contract | explore 为己、可逆（读 GET）、不触碰用户；外部稀有（冷却+概率+高阈）；不破 |
| 不引入 Agent 框架 | ✓ 工具由 drift()/ActionLayer 调，LLM 不直接调 |
| LLM 走 gateway | ✓ query 生成走 gateway `purpose="consciousness"`（复用，不污染 `last_outcome`——仅 conversation 刷新）；web search 独立（审查 B2） |
| DB 走 database | ✓ actions 留痕 `db.insert_action` |
| 不开新阶段 / 不触路线 | ✓ L7 未做项补全 |
| 常量默认值 | cooldown 6h / curiosity 阈 0.8 / 概率 0.05——settings 可覆盖；**不设独立 external daily_limit**（复用自主日限 20，拍板 HITL③）；触及须同步回写 L7-action.md + settings.example |
| 行动开口不新增通道 | ✓ 外部结果 `speak+qi_line` 走 `deliver_action_result` 现有 `elif` 分支；不改 `brain_delivery.py`（审查 B3）；内部保持不说 |
| contract drift | 自主行动日限 1/天 vs 20——标注待同步，不本包改 |

## 四、测试计划与验收清单

**测试**：
- 新增 ~8-12 测（web client mock + 外部分支 + 冷却 + 红线）
- 全量 pytest ≥474（不回归；现有 explore 测试内部源行为不变）

**验收勾选**（照任务包）：
- [ ] `WebSearchClient` 落地（首接 Tavily，mock 测试绿）
- [ ] drift() 外部源分支 + 触发门控（curiosity≥0.8 + 冷却6h + 概率0.05）
- [ ] **gateway/llm 接线（审查 B2）**：`ExploreAction` 接收 `llm` → `ActionLayer` 接收并下传 → `brain.restore_state` 传 `self.llm`；query 走 `purpose="consciousness"`
- [ ] 红线：搜不到/失败 → found=None、outcome=failed_capability、不编造
- [ ] query 不引用用户隐私（prompt 红线 + 测试断言）
- [ ] **说出口（审查 B3）**：外部结果带 `speak=True + qi_line`（成功/空手都开口）；内部不带；走 `deliver_action_result` 现有分支，**不改 `brain_delivery.py`**
- [ ] settings 配置块（enabled 默认 false / provider / api_key `${TAVILY_API_KEY}` / cooldown 6h）——**不加 `daily_limit`**（HITL③）；`.env.example` 加 `TAVILY_API_KEY=`（N3）
- [ ] 冷却持久化（body_memory key `explore_external_last`）
- [ ] mock 测试全绿（`force`/非 force 分覆盖 N7；`web=None`→走内部 N8）；全量 pytest ≥474
- [ ] L7-action.md 回写 + progress 决策 + contract drift 标注（contract 正文不改，只列待同步清单）
- [ ] git diff 不含无关文件（README / chore 不碰——按 PR 改动点清单）

## 五、风险 / 不确定点 / 拍板项

- **风险 1（API 成本）**：外部探索触发 LLM query + search API call。缓解：curiosity≥0.8 高阈 + 冷却 6h + 概率 0.05（真机日均远低于上限；复用 ActionBudget 日限 20 安全阀，不设独立外部日限——拍板 HITL③）。HITL 已确认全按推荐。
- **风险 2（不当内容）**：d-1 轻量（摘要+source，栖转述规避）。深度过滤另开包。
- **风险 3（query 隐私）**：query 走 gateway，注入「不引用 user_facts / 对话内容」红线 prompt + 测试断言。仍存 LLM 不守红线的残余风险——首次相处验证时观察 query 内容。
- **不确定**：provider 抽象首接 Tavily（拍板已定）；若后续切 DuckDuckGo 则 `search` 实现换（结构同）。
- **拍板项**：HITL 1-5 **已拍板全按推荐**（2026-08-08 维护者）：Tavily / LLM gateway / 冷却6h+复用日限20（不设独立外部日限）/ 轻量 / contract drift 标注待同步。见任务包「拍板落定」段。
- **待追认（自治）**：冷却存 body_memory key `explore_external_last`；外部空手 summary 与内部同构。

## 六、明确：编码交 Cursor

本方案 Agent 不写代码。按 SDD-GUIDE §2.3：

**路 B 第 1 步已完成**：Cursor 落盘 `-Cursor交叉审查.md`，标 B1/B2/B3 阻塞。
**路 B 第 2 步已完成**（本 PR 文首「审查后修订」吸收 B1/B2/B3）：
- **B1**：任务包范围/步骤/验收清 `daily_limit` 残留（与 HITL③「不设独立外部日限」对齐）。
- **B2**：补 gateway/llm 接线——`ExploreAction.__init__` 加 `llm` + `web`；`_make_query` 走 `purpose="consciousness"`（复用，不污染 `last_outcome`）；`ActionLayer.__init__` 加 `llm` 下传 + 建 `WebSearchClient`；新增 §二C2 `brain.restore_state` 传 `self.llm`；§七 scope 加 `qi/core/brain.py`。
- **B3**：钉说出口——外部结果带 `speak=True + qi_line`（成功/空手都开口，模板化不二次 LLM）走 `deliver_action_result` 现有 `elif` 分支，**不改 `brain_delivery.py`**；内部保持不说；「注入下轮对话」降级延后（不在 d-1）。

**下一拍（路 B 第 3 步）**：Cursor 读修订后 PR → 落盘 `-整改复审.md`，逐条核对 B1/B2/B3 关闭；未关闭则退回第 2 步（仍禁码）。
**之后**：路 B 第 4 步 方案落 `-编码请求.md`（以整改后 PR 为准）→ 维护者/方案明示可编码 → Cursor 编码 → `-Cursor编码回执.md` 完工段 → 方案 Agent 实施验收。

**获明示可编码前，Cursor 不写 `qi/` 代码。**

## 七、给 Cursor 的 scope 纪律（上一包越界教训）

- **只动本 PR 改动点清单内文件**：`explore_web.py`（新）/ `explore.py` / `layer.py` / **`qi/core/brain.py`（仅 `restore_state` 构造传 `llm=self.llm` 一行，不改心跳——审查 B2）** / `settings.example.yaml` / **`.env.example`（加 `TAVILY_API_KEY=`，审查 N3）** / `tests/` / L7-action.md / progress.md。
- `settings.yaml` 在 `.gitignore`，**本机手改不进 diff**（审查 N2）；git 只改 `settings.example.yaml` + `.env.example`。
- **不碰**：README / 不自加 chore commit / 不扩 scope（尤其 `brain.py` 只动构造传参那一行，别顺手重构心跳）。有「顺手改善」冲动先报、不擅自做。
- 过程稿（任务包/PR/交叉审查/整改复审/编码请求/回执/验收）按 SDD 落盘。
