# stage-0 · 实证修复（阶段零）

> **类型**：阶段规格（退出判据唯一施工权威，已生效）。
> **状态**：✅ 已收官（判据 1–5 全过，测试基线 218，见架构方案修订记录 2026-08-02）
> **源**：`explanation/栖·数字生命架构方案.md` §五 阶段零（已退为摘要+链接，以本文件为准）

---

## 目标

止血 §2.5 病征中不依赖架构方向的三项 + 可靠性兜底（任何路线的前置）。

## 施工内容（已落地）

- **感知**：`assess_impact_async` 主路径改 LLM——带最近 3–5 条上下文，JSON 输出 `{impact, intent, intimacy, ambiguous}`；intent=tease 负向打折（×0.3），hurt 维持，comfort 正向；关键词降级为离线/超时回退。
  - ⚠️ 张力标注：此项加深 LLM 依赖，与换心方向相反——定位为**过渡止血**，阶段三后感知随本地基质逐步回收。
- **检索**：`CharNgramEmbeddingFunction` 换 `bge-small-zh`（ONNX 离线加载，约 100MB，缓存于 `data/models/`）；`VectorStore` 接口签名不变，加载失败回退 n-gram。
- **兜底（= 拔管测试的工程实现）**：gateway 失败语义分级（`LLM_UNREACHABLE` / `LLM_EMPTY`）；断网时主动开口用本地模板（非 LLM 生成）；**fake-provider 契约测试**——Mock 网关验证情绪/记忆/关系/门控在无 LLM 时仍完整推进。
- **工程纪律（全程有效，见 `_invariants.md`）**：不推倒重来（R4）；重构与行为变更永不同 PR；每步 `pytest` + `ruff` 全绿；改 prompt 留改前/改后对照；新依赖须维护者确认。
- **season 输入**：`consciousness.py` 意识流 prompt 传真实季节值（约 3 行）。

## 退出判据（全部 ✅）

| # | 判据 | 状态 |
|---|------|------|
| 1 | C 失败分级兜底（gateway 语义分级 + 断网本地模板开口） | ✅ |
| 2 | P0 brain 拆分（`brain.py` → `brain_*.py`，632 行，零行为变更，测试全绿） | ✅ |
| 3 | A 感知 LLM 主路径（过渡止血，标注张力） | ✅ |
| 4 | B BGE 语义检索（加载失败回退 n-gram） | ✅ |
| 5 | D season 输入接入 | ✅ |

> 关联开放问题：`specs/open-questions.md` Q6（season）已结案于此。

## 回退条件

任一已止血病征回归（感知关键词盲区重现、检索退 n-gram 失效且无回退、fake-provider 在断网时行为中断）→ 回退本阶段修复并重测。
