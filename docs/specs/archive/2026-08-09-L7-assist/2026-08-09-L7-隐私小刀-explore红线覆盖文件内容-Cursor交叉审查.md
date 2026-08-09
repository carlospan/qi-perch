# L7 隐私小刀（explore 红线覆盖文件内容）——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：`2026-08-09-L7-隐私小刀-explore红线覆盖文件内容-任务包.md`、`…-PR方案.md`  
> **对照代码**：`qi/action/explore.py`（`_QUERY_PRIVACY_LINE` L31；`_make_query` L151；`_digest_hits` L208；`_digest_internal` L235——三处均 f-string 引用该常量）  
> **测试现状**：`tests/test_explore_digest.py` L61、`test_explore_external_branch.py` L130 **写死**旧句「不引用 user_facts / 对话内容」；`test_explore_internal_digest.py` 用 `_QUERY_PRIVACY_LINE in joined`（常量一改即跟随）  
> **审查时刻**：2026-08-09  

---

## 总判

**方向正确，无必须整改项 → 路 A（轻量放行）。**

assist-7/8 后文件概要进 narrative，explore 红线仅挡 user_facts/对话——边界洞判断正确。一处改常量、三处调用已共用同一符号，生效面与 PR 描述一致；范围不碰 narrative 存储 / 对话硬规则，干净。

---

## 理解确认（≠放行）

| # | 改动点 | 理解 |
|---|--------|------|
| 1 | 常量 | `_QUERY_PRIVACY_LINE = "不引用 user_facts、对话内容或用户文件内容原文"` |
| 2 | 生效 | `_make_query` / `_digest_hits` / `_digest_internal` 经 f-string 自动吃到新措辞 |
| 3 | 测试 | 写死旧句的断言改新句或改引用常量；可加「含用户文件内容原文」断言 |

---

## 认可

1. 单源常量，避免内外两套红线漂移。  
2. 「记得」留在 narrative（assist-8），「探索不背诵」用 prompt 红线——与数字生命对照一致。  
3. 对照 L151 / L208 / L235，确认无第四处漏网的旧硬编码红线串。  
4. 改动面极小，适合小刀包。

---

## 必须整改（阻塞编码）

**无。**

---

## 编码时注意（不阻塞）

### N1. 措辞断言迁移（必做，否则全量红）

至少两处写死旧句：

- `tests/test_explore_digest.py`：`assert "不引用 user_facts / 对话内容" in joined`  
- `tests/test_explore_external_branch.py`：同上  

建议改为 `assert _QUERY_PRIVACY_LINE in …` 或断言含「用户文件内容原文」，与 `test_explore_internal_digest.py` 对齐，避免下次再锁死字面。

### N2. 任务包笔误

任务包写「share/tend/explore 均只用该常量」——现码 **仅 explore.py** 使用 `_QUERY_PRIVACY_LINE`。不影响改动正确性。

### N3. 与 assist-8 联验

assist-8 把「（里面写着：preview）」写入 narrative 后，本红线主要约束 `_digest_internal` 开口；相处复验可听 explore 是否仍念文件字（prompt 软约束，非硬闸）。

---

## 观察项

- LLM 可能改写/意译文件内容而非「原文」——红线措辞挡「原文」，非万能  
- Spec「可提起读过某文件」靠模型自律，无结构化 allowlist  

---

## 结论与分轨

| 项 | 结论 |
|----|------|
| 阻塞项 | **无** |
| 分轨 | **路 A** |
| 下一拍 | 方案审查回复放行后编码 |

---

*Cursor · 交叉审查 · 2026-08-09 · 禁码*
