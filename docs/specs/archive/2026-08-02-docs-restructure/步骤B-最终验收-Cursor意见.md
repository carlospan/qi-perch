# 体系重构 · 最终验收 · Cursor 意见

> **用途**：转交 CodeBuddy / 维护者收口；**仅评审，未改文件**。  
> **依据**：`步骤B-最终验收-Cursor请求.md`、定稿 `体系重构方案.md`（v3）、当前 `docs/` 与仓库引用。  
> **撰写**：Cursor（2026-08-02）

---

## 验收结论：**有条件通过**

五类骨架、stages/acceptance/open-questions、架构 §五 摘要化、宪法分场景、日限 20、旧目录删除、`.cursor/rules` 授课路径——**主体达标**。  
但存在**仓库根与具身 README 死链**、**授课约定旧路径表**、**定稿 how-to 两份未建**、**stage 文首仍写「步骤 B 前」**、架构内 **相对链接路径错误**。建议修完下列「必改」后再宣称重构闭环；不要求回滚迁移。

---

## 1. 结构正确性

| 检查项 | 结果 |
|--------|------|
| `explanation/ reference/ how-to/ tutorials/ specs/` | ✅ |
| `stage-0~4` + `_invariants` / `acceptance` / `open-questions` | ✅ |
| `specs/archive/.gitkeep`、`how-to/ui/assets/.gitkeep` + html | ✅ |
| 旧 `design/ dev/ layers/ learn/ thoughts/`、根 `contract.md`、根路线图 | ✅ 已不存在 |
| 定稿 v3 的 `how-to/真机运行与观测.md`、`how-to/判据与验收.md` | ❌ **未建**（宪法目录表仍列出「运行观测、判据验收」） |

**放错类**：未发现。过程稿（方案评审往来）仍堆在 `docs/` 根——见 §6。

---

## 2. 无断链

### 仍存活的死链（必改）

| 位置 | 问题 |
|------|------|
| **仓库根 `README.md`** | 仍链 `docs/dev/换机搭建.md`、`docs/design/…`、`docs/contract.md`、`docs/layers/`、`docs/dev/施工包-阶段零.md` 等 — **全库最显眼死链** |
| **`qi/embodiment/desktop/README.md`** | 仍链 `docs/dev/换机搭建.md`、`docs/dev/主界面-Live2D接入.md` |
| **`docs/tutorials/授课约定.md` §六 表** | 仍写 `docs/contract.md` / `docs/layers/` / `docs/design/` |

### 已清干净（抽样）

- `.cursor/rules/qi-learn-course.mdc` → `docs/tutorials/授课约定.md` ✅  
- `docs/progress.md` 未再引用旧目录前缀 ✅  
- 层文档「相关文档」已改 `docs/reference/layers/…` ✅  

### 相对链接缺陷（必改）

`explanation/栖·数字生命架构方案.md` 内链写作：

`[…](specs/stages/stage-0.md)`

相对 `explanation/` 会解析成 `docs/explanation/specs/…`（**不存在**）。应改为 `../specs/stages/stage-0.md`（或根绝对 `docs/specs/...` 按仓库习惯统一）。

### 史料中的旧路径（可接受）

`体系重构方案*.md`、`步骤A-*` 等过程稿内出现的 `docs/design/` 为史实叙述，**可保留**；勿与运行入口死链混为一谈。

---

## 3. 无双源

| 项 | 结果 |
|----|------|
| 架构 §五 退摘要+链 stages | ✅ 实质已退（短摘要 + 链接）；文首 HTML 注释仍写「将于步骤 B 退…」→ **过期，建议改** |
| stage-0~4 为施工权威 | ✅ 内容在；但 0/1/2 文首仍写「步骤 B 前全文并存」→ **元数据过期** |
| R 全文在架构 §七，contract 无 R | ✅ |
| `_invariants` 仅索引 R | ✅ |
| C1–C5 定义在架构 §一；acceptance 操作化 | ✅ |
| 架构 §六 与 acceptance 并存 | ⚠️ 可接受：§六 一句话表 + acceptance 操作化；非全文双源 |

**stage-2 内容小矛盾**：表内 #2 标观察项，已拍板写「#2/#4 降级」，但表内 **#4 未标观察项**——与 `progress.md` 不一致，建议对齐。

---

## 4. config 单源

| 项 | 结果 |
|----|------|
| 声明 yaml 为真源 | ✅ |
| `action.autonomous_daily_limit` = **20** | ✅（与 `settings.example.yaml` 一致） |
| 「不手抄默认值」 | ⚠️ **声明与正文张力**：`config.md` 仍大表抄写默认值。纪律上应视为「索引快照须随 yaml 更新」，非第二权威；严格验收记瑕疵，不挡通过 |

---

## 5. 宪法 v3

| 项 | 结果 |
|----|------|
| 分场景裁决（含配置→yaml） | ✅ |
| `open-questions.md` 存在且可链 | ✅ 死链已消除 |
| 目录描述含「运行观测、判据验收」而文件未建 | ⚠️ 与落地不一致 |

---

## 6. 过程稿是否可留在 `docs/` 根

**同意暂时保留作史料**，但建议二选一写进宪法/任务包收口：

- **A（推荐）**：迁入 `specs/archive/2026-08-02-docs-restructure/`（方案、两轮评审、步骤 A/B 请求与意见），`docs/` 根只留 `体系重构方案.md` 定稿或再链到 archive；或  
- **B**：定稿生效后删过程稿，只留定稿 + progress 一行。

现状：根目录过程文件偏多，易被 Agent 当成现行入口。**不挡「有条件通过」，但建议步骤收口时处理。**

---

## 遗留项清单

### 必改（建议收口前勾完）

1. [ ] 更新仓库根 `README.md` 文档表与换机链接 → 新路径  
2. [ ] 更新 `qi/embodiment/desktop/README.md` → `how-to/…`  
3. [ ] 更新 `tutorials/授课约定.md` §六 相关入口表  
4. [ ] 修正架构方案内 `specs/stages/*.md` 相对链接为 `../specs/stages/…`  
5. [ ] 补建或从宪法目录表去掉：`how-to/真机运行与观测.md`、`how-to/判据与验收.md`（定稿有则应建；若推迟须改宪法/定稿）  
6. [ ] 刷新 `stage-0/1/2`（及同类）文首：去掉「步骤 B 前并存」过期话；架构文件头「将于步骤 B」→「已退摘要」  
7. [ ] `stage-2` 表：#4 与已拍板「#2/#4 观察项」对齐  

### 建议改（不挡标「重构完成」亦可后补）

8. [ ] 过程稿归档或删除策略落地（§6）  
9. [ ] 架构 §六「contract.md」→ `reference/contract.md` 用词统一  
10. [ ] `config.md` 考虑改为「键列表 + 见 yaml」减手抄面，或标明「快照日期 / 以 yaml 为准」

---

## 简表对照验收请求六问

| # | 问 | 答 |
|---|----|----|
| 1 | 结构符合 v3？ | **大体是**；缺两份 how-to |
| 2 | 无断链？ | **否**——根 README / desktop README / 授课约定；架构相对链错 |
| 3 | 无双源？ | **实质无**；元数据过期 + stage-2 #4 备注 |
| 4 | config 单源、日限 20？ | **声明与日限通过**；表内仍抄默认值 |
| 5 | 宪法 / open-questions？ | **通过** |
| 6 | 过程稿可留？ | **可留，建议归档** |

---

*Cursor 最终验收意见 · 2026-08-02*
