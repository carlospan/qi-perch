# L7 explore 真搜索 · 润色小刀——PR 方案

> **角色**：Trae（方案 Agent）  
> **依据**：[任务包](./2026-08-09-L7-explore真搜索-润色小刀-任务包.md)  
> **编码交 Cursor；本方案 Agent 不写 qi/ 代码**

---

## 命名澄清

本包 = C 方案收口后的润色小刀（query/搜索质量润色）。非新能力、非行为变更。

---

## 外部可观测行为（Spec）

1. 外部探索 `_make_query` 注入 LLM 的 prompt 季节段为中文（春/夏/秋/冬），不再出现 `autumn`/`spring` 等英文码。
2. Tavily 搜索 payload 支持 `exclude_domains` 字段（从 `explore_external.exclude_domains` 读，默认空数组=不改变现状）。
3. d-1/d-2/d-3-1/d-3-2 已验收行为全保留。

---

## 精确改动点

### 1. `qi/action/explore.py`

**模块级新增常量**（建议放 `_QUERY_PRIVACY_LINE` 附近）：

```python
_SEASON_ZH = {"spring": "春", "summer": "夏", "autumn": "秋", "winter": "冬"}
```

**`_make_query` user prompt 改**（现 [L143](file:///d:/qi-perch/qi/action/explore.py#L143)）：

```python
# 现
user = (
    f"季节={season}；curiosity={curiosity:.2f}；"
    f"mood_mode={mode_s}；valence={valence:.2f}。"
    "请给一句栖此刻可能好奇的窗外问句（≤30字）。"
)

# 改为
season_zh = _SEASON_ZH.get(season, season)  # 未知码兜底原样
user = (
    f"季节={season_zh}；curiosity={curiosity:.2f}；"
    f"mood_mode={mode_s}；valence={valence:.2f}。"
    "请给一句栖此刻可能好奇的窗外问句（≤30字，纯中文）。"
)
```

> 注：末尾加「纯中文」三字提示 LLM 不混英文；非硬约束（LLM 仍可能输出英文词），但能降低概率。query 后处理（过滤英文词）属可选增强，本包不做（保留 query 自然性，避免误杀）。

### 2. `qi/action/explore_web.py`

**`_search_tavily` payload 加 `exclude_domains`**（现 [L50-56](file:///d:/qi-perch/qi/action/explore_web.py#L50-56)）：

```python
async def _search_tavily(self, query: str, *, top_k: int) -> list[SearchHit] | None:
    payload: dict[str, Any] = {
        "api_key": self.api_key,
        "query": query,
        "max_results": max(1, min(int(top_k), 10)),
        "search_depth": "basic",
        "include_answer": False,
    }
    # 新增：可选 exclude_domains（默认空=不改变现状）
    exclude = self._exclude_domains()
    if exclude:
        payload["exclude_domains"] = exclude
    try:
        ...
```

**新增辅助方法**：

```python
def _exclude_domains(self) -> list[str]:
    raw = (self.config.get("explore_external") or {}).get("exclude_domains") or []
    if not isinstance(raw, list):
        return []
    return [str(d).strip().lower() for d in raw if str(d).strip()]
```

> 注：`self.config` 现已存 `explore_external` 段（见 [explore.py `_external_cfg`](file:///d:/qi-perch/qi/action/explore.py#L139) 同构）；但 `WebSearchClient` 的 config 是构造时传入的完整 config dict（与 ExploreAction 共享）。需确认 `WebSearchClient.__init__` 接收的 config 是否含 `action.explore_external` 路径——若不是，改读 `self.config.get("action", {}).get("explore_external", {})`。**Cursor 编码时需核对 `WebSearchClient` 的 config 结构**（见风险 R1）。

### 3. `qi/config/settings.example.yaml`

`explore_external` 段（现 [L86-94](file:///d:/qi-perch/qi/config/settings.example.yaml#L86-94)）加：

```yaml
  explore_external:
    enabled: false
    provider: tavily
    api_key: "${TAVILY_API_KEY}"
    # 新增：可选域名过滤（默认空=不改变 Tavily 现状；嫌噪声可加如 [music.apple.com, mojim.com]）
    exclude_domains: []
```

### 4. 测试

**改 `tests/test_explore_external_branch.py`**（或新文件 `tests/test_explore_make_query.py`）：

```python
async def test_make_query_uses_chinese_season(monkeypatch):
    """_make_query 注入 prompt 的季节段为中文，不含英文码。"""
    captured = {}
    class _CapLLM:
        async def call(self, *, purpose, messages):
            captured["messages"] = messages
            captured["purpose"] = purpose
            return "秋天的风为什么听起来那么远"
    action = ExploreAction(db=..., llm=_CapLLM(), web=...)
    await action._make_query(curiosity=0.9, emotion=None, season="autumn")
    user_msg = captured["messages"][1]["content"]
    assert "autumn" not in user_msg
    assert "秋" in user_msg
    assert purpose == "consciousness"
```

**新 `tests/test_explore_web_exclude_domains.py`**（或并入现有 web 测试）：

```python
async def test_tavily_payload_exclude_domains_empty(monkeypatch):
    """默认配置：payload 不含 exclude_domains 字段（不改变现状）。"""
    client = WebSearchClient(provider="tavily", api_key="k", config={})
    captured = {}
    class _FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"results": [{"title":"t","content":"c","url":"u"}]}
    async def _fake_post(self, url, json=None, **kw):
        captured["payload"] = json
        return _FakeResp()
    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)
    await client.search("test", top_k=1)
    assert "exclude_domains" not in captured["payload"]

async def test_tavily_payload_exclude_domains_configured(monkeypatch):
    """配置非空：payload 含 exclude_domains。"""
    cfg = {"action": {"explore_external": {"exclude_domains": ["music.apple.com", "mojim.com"]}}}
    client = WebSearchClient(provider="tavily", api_key="k", config=cfg)
    # ... 同上 mock
    await client.search("test", top_k=1)
    assert captured["payload"]["exclude_domains"] == ["music.apple.com", "mojim.com"]
```

---

## 纪律红线对照

| 红线 | 本包 |
|------|------|
| R1（不承诺现象体验）| ✓ 仅润色 |
| R2（contract 第 25/28/29/70 条）| ✓ 不动主动行为克制 |
| R3（LLM 走 gateway）| ✓ `_make_query` 仍 `purpose=consciousness` |
| R4（DB 走 database）| ✓ 不碰 DB |
| 不引入 agent framework | ✓ |
| 一次一包 | ✓ N6/N7/N8 同属 query/搜索质量润色 |

---

## 测试计划与验收清单

- [ ] `test_make_query_uses_chinese_season`：season=autumn → prompt 含「秋」不含「autumn」
- [ ] `test_make_query_unknown_season_fallback`：season="unknown" → prompt 含「unknown」（兜底不崩）
- [ ] `test_tavily_payload_exclude_domains_empty`：默认空 → payload 不含字段
- [ ] `test_tavily_payload_exclude_domains_configured`：非空 → payload 含字段且小写化
- [ ] 定向全过 + 全量 ≥500 passed
- [ ] `settings.example.yaml` 示例同步
- [ ] 不回归：现有 explore/web/digest/见闻卡测试全过

---

## 风险 / 不确定点

| ID | 项 | 处置 |
|----|----|------|
| R1 | `WebSearchClient.config` 结构未核实 | Cursor 编码时需读 [explore_web.py](file:///d:/qi-perch/qi/action/explore_web.py) L29-38 + 看 brain 里 `WebSearchClient` 构造时传什么 config；若 config 不是完整 dict 而是已剥过 `action.explore_external` 的子段，`_exclude_domains` 读法要对应调整。**不阻塞本方案**，编码侧适配 |
| R2 | query 「纯中文」提示非硬约束 | 接受；若相处仍见英文词，另开包做 query 后处理（正则过滤英文词）；本包只软提示 |
| R3 | N8 不根治 | 接受；Tavily 跑偏是搜索质量本身；本包只给维护者可选过滤能力 |

---

## 需维护者拍板项

无（HITL 三项已拍）。

---

*PR 方案 · 2026-08-09 · 润色小刀 · 编码交 Cursor*
