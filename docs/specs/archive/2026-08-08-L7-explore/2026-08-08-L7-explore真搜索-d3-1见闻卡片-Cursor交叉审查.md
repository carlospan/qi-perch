# L7 explore 真搜索 d-3-1（见闻卡片）——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：[任务包](./2026-08-08-L7-explore真搜索-d3-1见闻卡片-任务包.md)、[PR 方案](./2026-08-08-L7-explore真搜索-d3-1见闻卡片-PR方案.md)  
> **对照代码**：  
> - 后端（只读确认零改可行）：`qi/action/explore.py` drift 返回、`qi/core/brain_delivery.py` L127–146  
> - 前端：`qi/embodiment/desktop/src/types.ts`、`composables/useQi.ts`、`components/TalkView.vue`、`components/ActionCard.vue`  
> **时刻**：2026-08-08  

---

## 总判

**路 B——1 处阻塞（B1）。**  
方向与 HITL（1a / 内部不渲染 / 纸感+「看」）正确；纯前端 scope、后端字段与 delivery 顺序均已核对可支撑。  
但 PR 未钉死**外部空手**（`found=None` / `entries` 空）是否出卡——按现写法会在诚实空手开口后再贴一张空「看」纸，破坏走神手感。禁码；待 PR/任务包补一句门控后整改复审。

---

## 核对清单

### 1. 后端是否真可零改

| 项 | 结论 |
|----|------|
| drift 返回 | ✓ `type/found/summary/action_id/season/curiosity/source/sandbox`；外部另加 `speak`/`qi_line`（`explore.py` L343–355） |
| delivery | ✓ 先 `speak+qi_line` 开口，再 `broadcast action`（`brain_delivery.py` L134–144）→ 谈区「先声后卡」成立 |
| 内部沙箱 | ✓ `source="sandbox"` 且不设 `speak`/`qi_line` → 前端滤 `source==="web"` 即可不回归沉默 |

✓ 「纯前端包」前提成立。

### 2. 类型补齐（types.ts）

现 `explore_drift` 缺 `source` / `qi_line` / `speak`，`found` 为 `unknown`——与任务包现状段一致。  
PR 的 `ExploreHit` / `ExploreFound` / 收窄后的 `explore_drift` / `ExploreCard` / `TalkCardItem` 并集——✓ 必要且对齐后端。

### 3. useQi 入队

- 仅 `explore_drift && source==="web"` → append：✓ HITL2  
- `appendCard` 泛化为并集：✓ 需要  

### 4. ExploreCard + TalkView

- 角标「看」、hits≤3、faint、纸感对齐 ActionCard、digest 不重复：✓ HITL1a + HITL3  
- TalkView 按 `card.type` 分支：✓；vue-tsc 收窄风险 PR 已记，实现侧可 `as`  

### 5. scope / 纪律

- 仅 `desktop/src/`：✓  
- 不改 d-2 `qi_line=summary`：✓  
- 创作卡路径保留：✓（须注意去重键，见 N1）  

---

## 必须整改（阻塞编码）

### B1. 外部空手是否出卡——未钉死

外部搜空时后端仍：

- `source="web"`
- `found=None`
- `speak=True`，`qi_line`＝「我看了看外面，没查到什么。不假装看见了。」
- 仍 `broadcast` 整包 `explore_drift`

按 PR 现逻辑 `source==="web"` 即 `appendCard` → 用户先听到诚实空手，再看到一张**无 hits / 无 query 的空「看」卡**。与 Spec「看到她瞥见了什么」、HITL1a「正文=hits 溯源」不符。

**整改（须写进 PR `useQi` 段，择一钉死）**：

- **推荐**：仅当 `source==="web" && Array.isArray(found?.entries) && found.entries.length > 0` 时入卡；空手只开口、不出卡。  
- 或备选：空手出卡但正文固定「没瞥见什么」（一般不推荐，易像报错条）。

验收清单同步加：「外部空手：有开口、无见闻卡片」。

---

## 认可

1. **对症**：`found.entries` 白留 → 见闻卡补可见性，与 d-2 开口分工清楚。  
2. **HITL 三选与纯前端 scope 一致**（选 a 避免动后端）。  
3. **内部不渲染**守住 d-1 沉默。  
4. **命名澄清**（d-3-1 卡片 / d-3-2 沙箱深读）避免再与旧「内部深读」抢号。  

---

## 非阻塞备注（N）

| ID | 说明 |
|----|------|
| **N1 · 去重键** | 现 `appendCard` 按 `creation_id` 去重；PR 改为一律 `action_id`。当前 share 不重复递同一 creation，实险低；更稳是按 `card.type` 分支（creation→`creation_id`，explore→`action_id`）。 |
| **N2 · 任务包 HITL 文案** | 任务包仍写「HITL（待拍）」，PR/维护者消息已「已拍」。请 Trae 改任务包为「已拍：1=a / 2=内部不渲染 / 3=纸感+看」，免后人误停 HITL。 |
| **N3 · sandbox `found` 形** | 内部 `found.entries` 是文件名字符串列表，不是 `ExploreHit`；靠顶栏 `source==="web"` 门控即可，勿用 `found.source` 误判。 |
| **N4 · 样式** | PR 骨架 `.paper.explore { /* 同 .paper 基底 */ }` 须实拷 ActionCard 变量，避免空规则导致无纸感。 |
| **N5 · d-2 push** | 本地 `838b047` ahead 1；网络恢复后 `git push` 不挡本包审查，但编码前建议 main 已含 d-2，以免相处复验缺 digest。 |

---

## 阻塞项摘要

| ID | 摘要 |
|----|------|
| **B1** | 钉死外部空手（`found` 空 / `entries` 空）不入见闻卡（推荐） |

---

## 下一拍

1. **Trae**：PR（+ 任务包验收）吸收 B1；顺手 N2 HITL 文案；可选吸收 N1 去重分支 → 整改复审或直接审查回复。  
2. **Cursor**：B1 关闭且明示可编码后再动 `desktop/src/`。  
3. **维护者**：d-2 `git push`（网络恢复后）；d-3-1 验收时看「先 digest 开口 → 再瞥见卡片」。  

---

*Cursor 交叉审查 · 2026-08-08 · 禁码 · 路 B（B1）*
