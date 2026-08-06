# N5 硬闸扩展——PR 方案（整改稿 v2）

> 类型：架构加固（N5 语言器官铁律）｜依赖：包 15/16/17 ✅、阶段一脚手架
> 纪律：SDD-GUIDE §2.3——本方案经 Cursor 交叉审查后整改，B1-B6/S1-S4 已吸收
> 审查溯源：`包-N5-硬闸扩展-Cursor交叉审查.md`（2026-08-07，活库 #1318/#1326/#1350/#1356/#1358 实证）
> 配套：`docs/specs/tasks/2026-08-07-N5-硬闸扩展.md`

## 0. 一句话

N5 硬闸管道（`expression.py` 出口 → `assert_reply_respects_card`）已在包 15-17 建立，
但当前只硬闸"施教反转"。本包新增**共同回忆声明闸**（主闸）和**实体一致性辅助闸**，
把硬闸从施教专项扩展为通用事实与回忆一致性，并强化 materials 在 prompt 中为原文短引。

> v2 整改要点（与 v1 差异）：① 以共同回忆声明闸为主，实体闸降为辅助（B1-A 吸收）；
> ② 硬闸/软检分离（B2）；③ 实体提取补充金样例与可测规则（B3）；
> ④ 去重旁路补齐（B4）；⑤ 阶段表述修正（B5）；⑥ 索引卫生（B6）；
> ⑦ S1-S4 全部吸收：must 解耦 / 原文短引 / 回归用例 id 锚定 / banned_names 债务声明。

## 1. 现状

### 1.1 已落地的 N5 硬闸管道（expression.py:200-264）

```
LLM 生成 text
  → _teach_memory_violation(text, intention)     ← 仅检查施教违规
     违规 → _fix_teach_inversion(messages) 重生成
     仍违规 → _TEACH_INVERSION_FALLBACK 模板兜底
  → is_duplicate_reply 去重                    ← 去重重生旁路也仅 _teach_memory_violation（B4）
  → 输出
```

### 1.2 本场硬伤（活库 #1309-1358，Cursor 交叉审查实证）

| id | 硬伤 | 类型 | v1 实体闸能否拦 | 整改后 |
|----|------|------|----------------|--------|
| #1326 | "你问『你要电脑做什么呢』" | 无出处共同回忆问句 | ❌ | ✅ 回忆声明闸 |
| #1358 | 本地部署谁先说 + "胡说/说服力"对白 | 主体倒置 + 编造对白 | ❌ | ✅ 回忆声明闸 |
| #1350 | "我说不会"实为"我会想试试" | 极性翻反 | ❌ | ⚠️ 软检（不硬闸） |
| #1356 | "会问你能不能叫我栖" | 施事倒置 | ❌ | ✅ 回忆声明闸 |
| #1318 | 旧哲学对话答欲望问 | 检索串台 | ❌ | ⚠️ B 项（另开 N5-b，本包不接，见下文） |

### 1.3 contract 护栏原则

> "少靠加长「不准说……」清单过日子。优先把状态做对、并注入对话（事实、念头）。"
> "护栏太矮→通用 AI 诗学；砌成墙→不再是可相处的人格。只钉存在论级的诚实。"

## 2. 核心设计：HARD / SOFT 分界线

```
HARD（硬闸，触发重生 + 模板兜底）:
  卡外专名 | 伪记忆句式 | 施教关系反转 | 空卡编造共同回忆
  | 【新增】共同回忆无出处（回忆声明闸）
  | 【新增】虚构实体（实体一致性辅助闸）

SOFT（软检，仅 trace / intention.evidence，不阻断）:
  无支撑自我认知结论
```

`expression` 仅对 HARD 重生；SOFT 打日志/写入 `intention.evidence`。`assert_reply_respects_card` 仍返回全量 violations，由调用方按 HARD/SOFT 筛选。

## 3. 改动

### 3.1 共同回忆声明闸（主闸，B1-A）

`assert_reply_respects_card` 新增：

```python
# 共同回忆声明闸：回复宣称"记得/说过/问过/那晚/那天…"但卡内无实材
if _DECLARATIVE_MEMORY_RE.search(text):
    if not _card_has_real_material(card):
        violations.append("共同回忆无出处")
    else:
        # 有实材：声明中的关键短语须能在 materials 中找到
        if not _key_phrase_in_materials(text, card.materials):
            violations.append("共同回忆关键短语不在素材中")
```

- `_DECLARATIVE_MEMORY_RE`：匹配确定回忆句式——"那天/那晚/凌晨/你问过/你说过/我说了/会问你是不是/记得你……"——不绑 `card.must` 里的"不假装记得"，默认对话通道启用（S1）。
- `_card_has_real_material(card)`：卡内 `materials` 中存在 tag ∈ {memory, fact} 的实材且 text 非空。
- `_key_phrase_in_materials(text, materials)`：记忆素材原文归一化后，检查回复声明中的关键短语（>3 字）是否能在 materials 中找到子串命中。

### 3.2 实体一致性辅助闸（B3）

```python
# 实体一致性：回复不应引入已知集之外的新专名实体
known = _build_known_set(card.materials)             # materials n-gram + 固定白名单
reply_entities = _extract_novel_entities(reply, known)
for e in reply_entities:
    if _is_definite_name_entity(e, known):
        violations.append(f"虚构实体:{e}")
```

**已知集定义**（写在代码常量，可单测）：
- materials 全文 2-4 字 n-gram
- 固定白名单：意象（深水/石子/树叶/窗子/羽毛/涟漪/余烬/黄昏/水面/微风/水底/晴空/薄云/回音/光线/暗流/缝隙/树梢/月光/清晨）、情绪（安静/温柔/紧张/珍惜/愿意/恍惚/酸涩/柔软/低落/平静）、功能词（谢谢/可以/不确定/对不起/没关系/好像/也许/大概）
- 特殊白名单：书名号内文本（《简爱》类）、显式"我叫××"类声明

**金样例**（写进单测）：

| 回复片段 | 已知集 | 应拦？ |
|---------|--------|--------|
| "那个叫小明的医生说的" | 无"小明" | ✅ 虚构实体 |
| "他叫阿强" | 无"阿强"但近聊有 | ✅（近聊不合并不判） |
| "像深水里的石子" | — | ❌ 意象白名单 |
| "……像一片叶子" | — | ❌ 意象白名单 |
| "可以试试躺着" | materials 中"允许自己躺着" | ❌ 匹配已知 |
| "会问你能不能叫我栖" | 无此对话 | ⚠️ 实体闸漏→回忆声明闸补拦 |

**第一版只拦**：materials/近聊皆无 + 命中疑似专名启发（长度≥2 的罕见字组合、大写英文名、"叫××的人"模式）。宁漏勿杀。

### 3.3 `expression.py` 硬闸扩展

```python
# 当前 line 206-241 的重构（B2 + B4）

_HARD_VIOLATION_PREFIXES = (
    "卡外专名:", "伪记忆句式", "施教关系反转",
    "空卡编造共同回忆", "虚构实体:", "共同回忆",
)

if text:
    viols = assert_reply_respects_card(text, intention)
    hard = [v for v in viols if v.startswith(_HARD_VIOLATION_PREFIXES)]
    if hard:                                    # B2：仅硬闸重生
        fixed = await self._fix_generation(messages, hard)
        if fixed is None:
            intention.outcome = "template"
            return _build_fallback(intention, hard)
        text = fixed

if text:
    if not is_duplicate_reply(text, hist):
        intention.outcome = "llm"
        return text
    # 去重重生 → 同样跑 HARD 闸（B4）
    again = await self._regenerate_avoid_duplicate(messages)
    if again:
        again_viols = assert_reply_respects_card(again, intention)
        if any(v.startswith(_HARD_VIOLATION_PREFIXES) for v in again_viols):
            intention.outcome = "template"
            return _build_fallback(intention, again_viols)
        if not is_duplicate_reply(again, hist):
            intention.outcome = "llm"
            return again
    templated = render_template(intention)
    ...
```

- `_fix_generation`：仿 `_fix_teach_inversion`，将 HARD violations 描述拼入 system prompt，重生成一次。不新增 `_fix_teach_inversion`，统一为 `_fix_generation`。
- `_fix_teach_inversion` 保留不删（包 15-17 产物），作为 `_fix_generation` 的 fallback 或逐步迁移到统一函数。
- `_TEACH_VIOLATION_TAGS` 保留不删，新增的 `_HARD_VIOLATION_PREFIXES` 是它的超集。

### 3.4 materials 注入改为原文短引（S2）

prompt 中不再"生动扩写"。改为：

```
【你此刻知道的事】
{memory_text}    ← 素材原文短引（≤ 80 字/条），列表形式，保留原句
{facts_text}     ← 用户事实原文短引
{state_text}     ← 当前状态描述
【诚实边界】你此刻知道的人和事仅有以上。若想引用"那晚/那天/你说过/我问过…"类的共同回忆——请确认以上素材中确实有那段对话；若不确定，请不要假装记得。不确定时可以用意象、比喻或诚实地说"我不确定"。
```

约束句从加长不准说清单变为**诚实边界**——和 contract 存在论级诚实对齐。

### 3.5 防回归测试（S3，活库 id 锚定）

- `tests/test_intention.py`：
  - 合成含"你问『你要电脑做什么呢』"且 card 无 memory → `assert_reply_respects_card` 含"共同回忆无出处"（锚定 #1326）
  - 合成含"像深水里的石子"→ 无虚构实体（锚定意象白名单）
  - 既有施教/伪记忆/专名测试不变（包 15-17 回归）
- `tests/test_expression.py`：
  - 构造 intention + 回复含确定回忆句式但卡无实材 → 硬闸触发重生（锚定 #1326/#1358）
  - 去重重生路径同样触发 HARD 闸（B4 回归，合成一条重复回复 + 含回忆句式）
  - 既有施教/去重测试不变
- `tests/test_prompt_builder.py`（或 test_prompt_contract.py）：
  - 断言 materials 注入格式为"原文短引"+"诚实边界"约束句（非生动扩写）

### 3.6 红线

- 不删包 15-17 的施教反转硬闸
- `assert_reply_respects_card` 既有检查维度不删，只在末尾新增
- 实体提取只用标准库 `re`，不引入新依赖
- 文学意象白名单写代码常量 + 单测（不是口头承诺）
- contract 护栏原则：少靠不准说清单，只钉存在论级的诚实

### 3.7 显式债务（S4）

- `banned_names`：当前 expression 未传。本包不做（优先级低于共同回忆闸 + 实体闸）。列为已知债务。

### 3.8 索引卫生（B6）

- `docs/specs/tasks/README.md`「现行」表加入本任务包条目。
- `docs/specs/archive/2026-08-07-n5-hard-gate/` 补 `INDEX.md`。

## 4. 验收标准

- [ ] `assert_reply_respects_card` 对"回复含确定回忆句式但卡内无 memory/fact"返回"共同回忆无出处"（锚定 #1326/#1358）
- [ ] `assert_reply_respects_card` 对"回复含 literary 意象深水/石子/树叶"不返回虚构实体
- [ ] `expression.py` HARD 闸覆盖：卡外专名/伪记忆/施教反转/空卡编造/虚构实体/共同回忆
- [ ] `expression.py` SOFT 不阻断（无支撑自我认知仅 trace）
- [ ] 去重重生路径同样触发 HARD 闸（B4）
- [ ] prompt 中 materials 注入格式为"原文短引 + 诚实边界"（非生动扩写）
- [ ] 包 15-17 施教硬闸不被削弱（既有施教单测全绿）
- [ ] 全量 `pytest` 通过，`ruff` 零问题
- [ ] tasks/README.md 已列入本任务包
- [ ] archive/INDEX.md 已补

## 5. 不接项（明确排除）

| 项 | 处置 | 理由 |
|----|------|------|
| 检索相关门（B1-B） | 另开 N5-b | 属建卡侧（`brain_context`），不在 expression 硬闸范围 |
| banned_names 接线 | 列债务，本包不做 | 优先级低于共同回忆闸 + 实体闸 |
| 极性翻反（#1350）、答非所问（#1318） | 不硬闸 | 属语义层问题，非 N5 "事实一致性"范围 |

## 6. 进度

| 步骤 | 状态 |
|------|------|
| 任务包 | ✅ `specs/tasks/2026-08-07-N5-硬闸扩展.md` |
| PR 方案 v1 | ✅（已撤回） |
| Cursor 交叉审查 | ✅ `包-N5-硬闸扩展-Cursor交叉审查.md` |
| PR 方案 v2（本文件） | ✅ 整改完成，B1-B6/S1-S4 已吸收 |
| Cursor 编码 | ✅ `包-N5-硬闸扩展-Cursor编码回执.md` |
| 04 验收 | 待做 |
