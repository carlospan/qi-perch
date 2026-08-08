# L7 explore 真搜索 d-1——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：`2026-08-08-L7-explore真搜索-d1联网地基.md`、`...-PR方案.md`（拍板后微调：撤独立 daily_limit）  
> **对照代码**：`qi/action/explore.py`、`layer.py`、`budget.py`、`permission.py`、`volition.py`、`brain.py`（ActionLayer 构造）、`brain_delivery.py`、`settings.example.yaml`  
> **时刻**：2026-08-08  

---

## 总判

**方向 C / d-1 对症，HITL③（不设独立外部日限）正确；但有 3 处阻塞——路 B。**  
禁码，待方案修订任务包/PR 后整改复审。

根因与目标成立：现有 `drift()` 只 `_scan_sandbox` 列文件名（`explore.py` L148–165），curiosity 无真外部出口；外部分支 + Tavily + 高阈/冷却/低概率稀有化，符合 contemplative、不引入 Agent 框架。

---

## 认可

1. **内部源不动**、外部分支并列——避免与 d-2 深读混包。  
2. **HITL③**：不设 `daily_limit`，复用 `ActionBudget`（layer 已在 explore 成功后 `budget.record`；`execute_kind` 入口已有 `can_autonomous`）——正确。  
3. **默认 `enabled: false`**、key 配齐才建 client——CI/无 key 环境安全。  
4. **搜不到 → `found=None` + `OUTCOME_FAILED_CAPABILITY`**——对齐 `permission.py` 行动失败三层；与现内部空手仍写 `OUTCOME_SUCCESS` 可区分（能力失败 vs 架子空），可接受。  
5. **冷却 body_memory `explore_external_last`**——与 tend/budget 同构，可落地。  
6. **httpx** 已在 `requirements.lock`——依赖面 OK。  
7. **独处**：volition 仅 `mode=="solitary"` + curiosity≥0.65 才产 explore 候选（`volition.py` L190–194）——「独处」已在候选层，不必在 `_should_external` 再判（须在 PR 写明，见 N1）。

---

## 必须整改（阻塞编码）

### B1. 任务包仍要求 `daily_limit`，与已拍板 HITL③ / 修订后 PR 矛盾

任务包多处未跟上撤限：

| 位置 | 原文 |
|------|------|
| §范围 做-3 | 「冷却 + 概率 + **日限**」 |
| §实现步骤 4 | settings 块含 `daily_limit` |
| §验收 | 「enabled/provider/key/cooldown/**daily_limit**」 |

PR / 拍板段已明确：**不设独立外部日限**。编码若按任务包验收会加回 `daily_limit` 字段。

**整改**：任务包上述三处与 HITL③/PR §二D 对齐（删独立日限表述）；验收以修订后 PR 为准。维护者提示「settings 块不要再加 daily_limit」须写进任务包正文，不能只靠聊天。

### B2. query 走 gateway——接线未进精确改动点 / scope

HITL② + PR `_make_query` 走 gateway，但：

- `ExploreAction` / `ActionLayer` **当前无 llm**（`action/` 内零 `gateway` 引用）。  
- `brain.restore_state` 构造：`ActionLayer(db, config, narrative=...)`（`brain.py` L1156–1158），**未传** `self.llm`。  
- PR §二B 只加 `web`；§二C 只建 `WebSearchClient`；**§七 scope 未列 `brain.py`**。

无 gateway 则无法实现拍板的 LLM query，只能偷偷改成启发式（违反 HITL②）或擅自扩 scope。

**整改（须写进 PR）**：

1. `ExploreAction(..., llm: LLMGateway | None = None)`（或等价可调用入口）。  
2. `ActionLayer` 接收并下传 `llm`。  
3. `brain.restore_state` 传入 `self.llm`。  
4. §七 scope **显式加入** `qi/core/brain.py`（仅构造传参，不改心跳逻辑）。  
5. 钉死 `gateway.call` 的 `purpose`（复用 `consciousness` / `creation` 之一，或 example 增 `explore_query` 路由——二选一写清）。

### B3. Spec「用栖语气说」+ 任务包「注入下轮对话」——交付出口未钉死

| 文档主张 | 现码 |
|----------|------|
| Spec：带回见闻，**用栖语气说**（例：「我刚才看了看 X…」） | `deliver_action_result`：**tend/explore 向内默认不说**；仅 `creation_card` 或 `speak+qi_line` 才开口（`brain_delivery.py` L127–137） |
| 任务包不做项旁注：d-1 **只注入下轮对话** + actions 留痕 | PR **未写**任何注入点（工作记忆 / intention / prompt / speak） |

`drift()` 现只返回 `summary`，无 `speak`/`qi_line`。按现 PR 落地 → 外部搜完仍可能**完全不说、也不进下轮对话**，仅 `actions` 留痕——**不满足 Spec 外部可观测行为**。

**整改（择一写死，并扩 scope）**：

- **推荐 A（可观测、最小）**：外部源成功/空手时，结果带 `speak=True` + `qi_line=<栖语气 summary>`（可模板，不必二次 LLM）；沿用现有 `deliver_action_result` 分支。内部源保持不说。  
- 或 B：显式改 `brain_delivery` 对 `source=="web"` / `explore_drift` 开口。  
- 「注入下轮对话」若仍要：钉死机制（如 `working_memory` 一条 / body_memory 供下轮 prompt）并列入改动文件；**若 d-1 降级为「仅 actions + 开口」**，须改任务包 Spec，删「注入下轮对话」或标延后。

---

## 非阻塞（编码时注意）

| # | 意见 | 建议 |
|---|------|------|
| N1 | 「独处」在 `_should_external` 未出现 | PR 注明：由 volition `solitary` 候选保证；外部分支不再重复判 mode |
| N2 | `settings.yaml` 在 `.gitignore`（`qi/config/` 与推荐 `data/`） | git 只改进 `settings.example.yaml`；本机 `data/settings.yaml` 手改，不进 diff |
| N3 | `api_key: null` | 建议 `${TAVILY_API_KEY}` + `.env.example` 一行（与 deepseek/tokenrhythm 同构） |
| N4 | 外部分支命中但 search 失败：不回落沙箱 | 接受（已选「看外面」则诚实没查到）；PR 可一句标明 |
| N5 | `_search_ddg` | d-1 只实现 Tavily 即可；ddg 留 NotImplemented/不写 |
| N6 | 概率 0.05 / 阈 0.8 | PR 称 settings 可覆盖，§二D yaml 宜加可选键或写明「常量 + 可选覆盖」 |
| N7 | `force=True`（GWS）跳过内部 0.12 门，仍吃外部 0.05 | 行为 OK；测试需分别覆盖 force / 非 force |
| N8 | 现有 `test_self_ops` / `test_action_l7` explore 测 | `web=None` 时必须走内部，防回归 |

---

## 开工前理解确认（禁码）

若 B1–B3 关闭并明示可编码后，编码将：

1. 新建 `explore_web.py`（Tavily + httpx；失败/空 → None）；**不加** `daily_limit`。  
2. `explore.drift`：飘出后 `_should_external`（≥0.8 + 冷却 6h + p=0.05 + web 可用）→ 外部，否则现有沙箱；内部扫描逻辑行为不变。  
3. 冷却：`body_memory["explore_external_last"]`。  
4. query：gateway + 隐私红线 prompt；llm 经 ActionLayer/brain 注入。  
5. 按修订后的交付出口：外部结果可观测（说 / 注入，以 PR 为准）。  
6. 测：mock HTTP + 门控 + 红线；全量不回归。  
7. 文档：L7-action / progress；contract 日限 drift **只标注不改正文**。  
8. 不碰 README / 不设独立外部日限。

**需澄清**：无（阻塞项均为方案须补，非代码未决）。

**状态**：交叉审查已落盘；**有阻塞 → 路 B**。请方案 Agent 修订任务包 + PR（吸收 B1–B3）→ Cursor 整改复审 → 编码请求 → **获明示可编码前不写 `qi/`**。
