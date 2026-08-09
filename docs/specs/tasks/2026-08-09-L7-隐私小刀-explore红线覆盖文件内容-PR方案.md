# L7 隐私小刀（explore 红线覆盖文件内容）——PR 方案

> **角色**：Trae（方案 Agent）；编码交 Cursor
> **依据**：[任务包](./2026-08-09-L7-隐私小刀-explore红线覆盖文件内容-任务包.md)
> **对照代码**：`qi/action/explore.py`（`_QUERY_PRIVACY_LINE` L31 / `_make_query` L148-152 / `_digest_hits` L206-210 / `_digest_internal` L232-236）
> **时刻**：2026-08-09

---

## 外部可观测行为

1. explore 的 query 生成 / 外部 hits digest / 内部记忆 digest 均不引用用户文件内容原文
2. 栖探索时可提起「读过某文件」这件事，但不背诵内容

## 精确改动点

### 1. `qi/action/explore.py` `_QUERY_PRIVACY_LINE`（L31）

**现状**：
```python
_QUERY_PRIVACY_LINE = "不引用 user_facts / 对话内容"
```

**改为**：
```python
_QUERY_PRIVACY_LINE = "不引用 user_facts、对话内容或用户文件内容原文"
```

> 一处常量，三处生效：`_make_query`（外部 query）/ `_digest_hits`（外部 hits）/ `_digest_internal`（内部记忆）。内部 digest 会读到 assist-7/8 写入的「我读了他给我的 X…」narrative——红线覆盖后，栖探索「记得但不引用内容原文」。

## 纪律红线对照

- **R1**：不引用 = 不编造来源 ✓
- **隐私**：覆盖用户文件内容，堵 assist-7 引入的边界洞 ✓

## 测试计划与验收清单

### 新增/修改测试

1. 既有 digest/query 测试若有措辞断言（写死「不引用 user_facts / 对话内容」）→ 迁移为新措辞（Cursor 先 grep `_QUERY_PRIVACY_LINE` 与测试断言）
2. 新增断言（若有现有 explore 测试文件合适位置）：`_QUERY_PRIVACY_LINE` 含「用户文件内容原文」

### 验收清单

- [ ] `_QUERY_PRIVACY_LINE` 措辞含「用户文件内容原文」
- [ ] 措辞断言迁移无遗漏
- [ ] 全量 ≥585 passed

## 风险 / 不确定点

- **R1**：测试中写死旧措辞的断言遗漏——Cursor grep `_QUERY_PRIVACY_LINE` 及测试文件核对

## 需维护者拍板项

- HITL 措辞方案 a——按维护者扩权采纳

---

*Trae 方案 Agent · 2026-08-09 · 编码交 Cursor · 本方案 Agent 不写 qi/ 代码*
