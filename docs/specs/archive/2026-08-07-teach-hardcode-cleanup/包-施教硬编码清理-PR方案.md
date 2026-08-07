# 施教硬编码清理——PR 方案

> 类型：去技术债（contract 护栏对齐）｜依赖：N5-a ✅、N5-b ✅、包 15/16/17 ✅
> 纪律：SDD-GUIDE §2.3——方案→Cursor 交叉审查→整改→编码→验收
> 配套：`docs/specs/tasks/2026-08-07-施教硬编码清理.md`

## 0. 一句话

包 15/17 为修施教反转累积了睡眠专项硬编码。N5-a/N5-b 落地后这些硬编码变冗余，
违反 contract "少靠不准说清单 / 只钉存在论级诚实"。本任务清理睡眠专项，泛化为通用施教防护。

## 1. 违规清单（对照 contract.md §二·护栏与人格）

| 位置 | 硬编码内容 | 违反原则 |
|------|-----------|---------|
| `consciousness_stream.txt:30` | "不得添加锚定里没有的细节（如**'数到七'**）" | "少靠不准说清单" |
| `culture.py:61` | "原话『**躺着/不强迫/看天花板**』" | "只钉存在论级诚实"（钉了具体内容） |
| `expression.py:_TEACH_INVERSION_FALLBACK` | "入睡那件事，是我教你的——允许自己躺着，不强迫" | 砌墙（只对睡眠有效） |
| `expression.py:_TEACH_INVERSION_CONSTRAINT` | "入睡方法是栖教给用户的" | 砌墙 |
| `intention.py:detect_sleep_teach_inversion()` | 函数名 + 只查 `_SLEEP_TOPIC_RE` | 过拟合一个 incident |
| `intention.py:_SLEEP_ADVICE_RE` | `r"躺着\|不强迫\|看天花板\|允许自己"` | S1 整改：**保留作 `anchor_teaching_relation` 内部启发式**（识别助眠建议证据），不是 prompt 硬编码——本包不删。违规的是把它写进 prompt/fallback，而代码中未写进 prompt |
| `intention.py:_SLEEP_TOPIC_RE` / `_INVERT_TOPIC_RE` | 只认睡眠话题 | 过拟合 |

## 2. 保留不动的（通用框架，不违规）

| 代码 | 理由 |
|------|------|
| `infer_recall_relation()` | 通用——任何"谁教谁"都能用 |
| `anchor_teaching_relation()` | 通用——从 messages 扫任意施教方向 |
| `_RELATION_HINT` dict | 通用方向提示 |
| `_TAUGHT_BY_QI_RE` / `_LEARNED_FROM_USER_RE` | 通用正则 |
| `recall_relation` 字段 | IntentionCard 上的通用方向标记 |
| `_USER_ACK_QI_TAUGHT_RE` / `_USER_TEACHES_QI_RE` | 通用——用户承认/声明施教 |
| `anchor_teaching_relation` 中的 `_SLEEP_ADVICE_RE` | 保留在函数内用于判断"栖是否给了助眠建议"——这是 anchor 函数的逻辑分支，不是 prompt 硬编码 |

## 3. 改动

### 3.1 `qi/prompts/consciousness_stream.txt` — 删具体细节

当前 line 30：
```
引用「方法/教过的事/入睡」时，严格以施教关系锚定为准；不得把"你教我的"说成反方向，不得添加锚定里没有的细节（如"数到七"）。若锚定与你的印象冲突，以锚定为准。
```

改为：
```
引用「方法/教过的事/入睡」时，严格以施教关系锚定为准；不得把"你教我的"说成反方向，不得添加锚定里没有的细节。若锚定与你的印象冲突，以锚定为准。
```

删掉"（如'数到七'）"——这是把一个历史 bug 的具体虚构细节写进 prompt，正是 contract 说的"不准说清单"。

### 3.2 `qi/relationship/culture.py` — 删原话硬编码

当前 line 59-61：
```python
if direction == "qi_teaches_user":
    line += "（施教方向：栖教用户，原话『躺着/不强迫/看天花板』，勿反转）"
```

改为：
```python
if direction == "qi_teaches_user":
    line += "（施教方向：栖教用户，勿反转）"
elif direction == "user_teaches_qi":
    line += "（施教方向：用户教栖，勿反转）"
```

删掉"原话『躺着/不强迫/看天花板』"——方向事实已在 `teach_direction` 字段中，不需要在 prompt 里写死原话。LLM 看到方向标记就够了。

### 3.3 `qi/core/intention.py` — 仅 rename + 别名（B1 选项 A：不碰检测逻辑）

> **B1 整改**：本包只做内容去硬编码（§3.1/3.2/3.4），`detect_*` 仅 rename + 别名，**不宣称话题泛化**。
> 检测逻辑（`_INVERT_TAUGHT_BY_QI_RE` + `_INVERT_TOPIC_RE` 联判）保持不变。
> 既有负例"你教我写代码的样子很认真"不拦——这是设计意图（避免误伤真实请教），不改动。

```python
# 仅 rename，逻辑不变
def detect_teach_inversion(text: str) -> bool:
    """回复里把施教方向说反了吗？（原 detect_sleep_teach_inversion）
    栖视角说「你教我的方法/你教过我」+ 话题含入睡/方法/法子 → 反转。
    注意：非睡眠/方法话题的「你教我…」不拦（设计意图，避免误伤真实请教）。"""
    t = (text or "").strip()
    return bool(_INVERT_TAUGHT_BY_QI_RE.search(t) and _INVERT_TOPIC_RE.search(t))

# 向后兼容别名（包 15-17 测试引用旧名）
detect_sleep_teach_inversion = detect_teach_inversion
```

`_INVERT_TOPIC_RE` / `_SLEEP_TOPIC_RE` / `_SLEEP_ADVICE_RE` 全部保留不变。
`_SLEEP_ADVICE_RE` 保留作 `anchor_teaching_relation` 内部启发式（识别助眠建议证据），不是 prompt 硬编码——本包不删（S1 整改）。

**删掉原 §3.5 验收栏的"新增弹吉他检测"条目**——本包不做话题泛化。

### 3.4 `qi/core/expression.py` — fallback/constraint 改为通用

当前：
```python
_TEACH_INVERSION_CONSTRAINT = (
    "施教方向必须正确：入睡方法是栖教给用户的。严禁说「你教我的方法/你教过我」"
    "这类反转表述；若提起，说「我教你的那个方法」。"
)
_TEACH_INVERSION_FALLBACK = (
    "……我记得的。入睡那件事，是我教你的——允许自己躺着，不强迫。这个方向我不会记反。"
)
```

改为（S2/S3 整改：中性化 + 不露枚举名）：
```python
_TEACH_INVERSION_CONSTRAINT = (
    "施教方向必须正确：若卡标明栖教用户，"
    "严禁说「你教我的方法/你教过我」这类反转表述；"
    "若提起，说「我教你的那个方法」。"
)
_TEACH_INVERSION_FALLBACK = (
    "……我记得的。那件事，是我教你的。这个方向我不会记反。"
)
```

删掉"入睡方法是栖教给用户的"（具体内容）和"允许自己躺着，不强迫"（7-26 原话）。
FALLBACK 仍默认"是我教你的"——过渡期可接受（S2）；真正的方向判断由 `card.recall_relation` 在 `assert_reply_respects_card` 中做，fallback 只是最后兜底。

### 3.5 防回归测试（B2 整改：逐条点名必改单测）

> **B2 整改**：既有测试"行为不变"但**字符串断言会变**——以下单测必须改：

| 文件 | 现状断言 | 清理后 |
|------|---------|--------|
| `tests/test_relationship.py` | `assert "躺着/不强迫/看天花板" in block` | 改为 `assert "躺着" not in block` + `assert "栖教用户" in block` + `assert "勿反转" in block` |
| `tests/test_inner_life.py` | `assert "数到七" in prompt`（stream 硬约束句曾点名） | 改为 `assert "数到七" not in prompt` + `assert "不得添加锚定里没有的细节" in prompt` |
| `tests/test_expression.py` | 若断言旧 `_TEACH_INVERSION_FALLBACK` 全文含"入睡/躺着" | 跟新模板改断言（`assert "是我教你的" in result`，不断言"入睡"）；行为"违规→模板"不变 |

新增：
- `tests/test_intention.py`：`detect_teach_inversion` 别名可调用 + 既有负例"你教我写代码"仍不拦（`assert not detect_teach_inversion("你教我写代码的样子很认真")`）

**既有施教方向检测测试不变**（`detect_sleep_teach_inversion` → `detect_teach_inversion` 别名兼容，行为不变）。

### 3.6 红线

- 不删通用框架（`infer_recall_relation` / `anchor_teaching_relation` / `_RELATION_HINT` / `recall_relation`）
- 不删 `_TAUGHT_BY_QI_RE` / `_LEARNED_FROM_USER_RE` / `_USER_ACK_QI_TAUGHT_RE` / `_USER_TEACHES_QI_RE`
- 不删 `_SLEEP_ADVICE_RE`（`anchor_teaching_relation` 内部逻辑用，不是 prompt 硬编码）
- 包 15-17 既有施教回归测试全绿
- 清理后 N5-a 共同回忆声明闸仍能拦住"你教我的方法"类假回忆

## 4. 验收标准

1. `consciousness_stream.txt` 无"数到七"
2. `culture.py` 方向锤无"躺着/不强迫/看天花板"
3. `_TEACH_INVERSION_FALLBACK` / `_TEACH_INVERSION_CONSTRAINT` 不含"入睡"具体内容
4. `detect_sleep_teach_inversion` rename 为 `detect_teach_inversion`（别名兼容，检测逻辑不变——B1 选项 A）
5. 包 15-17 既有施教回归测试全绿
6. 全量 `pytest` 通过，`ruff` 零问题

## 5. 进度

| 步骤 | 状态 |
|------|------|
| 任务包 | ✅ `specs/tasks/2026-08-07-施教硬编码清理.md` |
| PR 方案 v1 | ✅（已整改） |
| Cursor 交叉审查 | ✅ `包-施教硬编码清理-Cursor交叉审查.md`（**已吸收 B1/B2/B3/S1-S3**） |
| PR 方案 v2 + 编码请求 | ✅ 本文件（B1 选 A：只清文案不碰检测逻辑；B2 逐条点名必改单测） |
| Cursor 编码 | ✅ `包-施教硬编码清理-Cursor编码回执.md`（全量 457 passed） |
| 04 验收 | 待做 |
