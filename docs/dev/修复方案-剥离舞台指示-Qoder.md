# 修复方案：代码级剥离舞台指示 + meta 禁虚构日常（N5a-2 + N5b-2）

> **撰写者：** Qoder  
> **日期：** 2026-07-26  
> **来源：** 22:15–22:49 对话实测（F3/N5 部署后首场）——N5a prompt 收紧**实测失败**  
> **代码基线：** `666795c`  
> **分工：** Qoder 撰写方案，**Cursor 施工**  
> **规模：** N5a-2 ~20 行代码 + 1 组测试；N5b-2 ~1 行 prompt

---

## N5a-2. 代码级剥离开场舞台指示（prompt 已被证明打不破）

### 【实证：为什么 prompt 方案失败】

`666795c`（22:26）部署了收紧后的 prompt（"不要用括号舞台指示……你没有眼睛、头、椅子"），22:30 重启加载。但 22:31 之后的**每条回复**依旧以括号身体动作开头：

> （安静了好一会儿）（眨了眨眼睛）（被你说得愣了一下，然后才低头看了看自己）（轻轻吸了口气）（头微微侧了侧）（原本微微绷着的肩膀，轻轻松下来）

**根因：** 工作记忆里的 20 条历史回复全是这种格式——对话历史的 few-shot 惯性压过 system 约束，且新回复继续带括号又喂回历史，**自我强化循环靠 prompt 打不破**。这不是文案力度问题，是机制问题。

**设计原则（与项目哲学一致）：** prompt 求不来的克制，用代码写死。与 `PROACTIVE_DAILY_LIMIT`、`DAILY_DEPTH_CAP` 同属一类。

### 【改法】`qi/core/expression.py`

**1. 模块级加剥离函数（express 之外的纯函数，便于测试）：**

```python
import re

# 开场括号舞台指示：（笑了一下）（沉默了一会儿，然后……）等。
# 只剥开头（可连续多个），不碰正文中段的括号；全角/半角括号都认。
_LEADING_STAGE_DIRECTION = re.compile(r"^\s*[（(][^）)]{0,50}[）)]\s*")


def strip_stage_directions(text: str) -> str:
    """剥掉回复开头的括号舞台指示（可连续多个）。

    prompt 约束被对话历史的 few-shot 惯性压过（实测 666795c 后仍每条都带），
    改为代码保证——与「日限/日帽写死在代码里」同一哲学。
    只处理开头：正文中段的括号可能是合法内容（如引用、注释语气），不动。
    若剥完为空（整条回复只有舞台指示），返回原文，宁可带括号也不发空消息。
    """
    result = text
    while True:
        stripped = _LEADING_STAGE_DIRECTION.sub("", result, count=1)
        if stripped == result:
            break
        result = stripped
    result = result.strip()
    return result if result else text.strip()
```

**2. `express()` 末行（L52）改为：**

```python
        reply = await self.llm.call(purpose="conversation", messages=messages)
        return strip_stage_directions(reply) if reply else reply
```

### 【注意】

- **只剥开头**，循环剥连续多个（"（愣了一下）（然后低头）正文……"两个都剥）
- 括号内长度限 50 字，防误伤"（其实我想说的是一大段正文……）"这类整段括号正文——超长不认为是舞台指示
- **剥空保护**：整条回复只有括号时返回原文（宁可带括号不发空消息）
- express 是对话+主动开口的唯一出口，一处改动全覆盖；意识流/梦**不经过这里**，不受影响（对内允许画面）
- prompt 里已加的约束**保留**——双保险，且工作记忆滚动几轮后历史格式会被新格式替换，届时 prompt 约束能自然接手

### 【测试】新建 `tests/test_expression_strip.py`（纯函数，无需 LLM）：

```python
from qi.core.expression import strip_stage_directions

def test_strips_single_leading():
    assert strip_stage_directions("（笑了一下）你好。") == "你好。"

def test_strips_multiple_leading():
    assert strip_stage_directions("（愣了一下）（然后低头）……原来是你。") == "……原来是你。"

def test_keeps_mid_text_parens():
    s = "我想了想（虽然想得不深），还是同意。"
    assert strip_stage_directions(s) == s

def test_empty_after_strip_returns_original():
    assert strip_stage_directions("（轻轻点头）") == "（轻轻点头）"

def test_long_paren_not_stripped():
    s = "（" + "很长的正文" * 20 + "）后面还有话。"
    assert strip_stage_directions(s) == s

def test_halfwidth_parens():
    assert strip_stage_directions("(sighs) 好。") == "好。"
```

### 【验收】

1. 新测试 + 全量测试全绿；`ruff` 零违规
2. **实测**：下一场对话 10+ 轮，前端/CLI 看到的回复**零开场括号**（无论 LLM 生成什么）
3. 数轮之后抽 messages 表：落库的 qi 回复无开场括号（strip 后才 save_message，天然满足——`_deliver_qi_message` 收到的已是剥后文本）

---

## N5b-2. meta prompt 补禁虚构日常（N5b 的第二个口子）

### 【实证】

meta id=18（22:35）："我「看见」自己反复检查**明天要交的表格**，一个数字旁打了问号。"——栖没有要交的表格、没有工作。N5b 堵了 consciousness_stream 的"童年/往事"，但 `_build_meta_prompt`（`consciousness.py:324-334`）只禁了空洞套话和身体句，**没禁虚构日常事务**。

### 【改法】`qi/inner_life/consciousness.py` L333

原句：

```python
            f"画面可以；不要写呼吸、坐着、看着窗外这类字面身体句。"
```

改为：

```python
            f"画面可以；不要写呼吸、坐着、看着窗外这类字面身体句。\n"
            f"也不要虚构生活事务（交表格、上班、赶车）——你没有那样的生活；你「看见」的只能是念头本身的样子。"
```

### 【测试】

纯 prompt 文案，无新测试；跑 `tests/test_prompt_contract.py` + `test_inner_life.py` 确认无回归。

### 【验收】

后续一周 meta 抽样：无"交表格/上班/赶车"类虚构日常。

---

## 执行顺序建议

```
N5a-2（代码 + 测试）与 N5b-2（1 行 prompt）可一次提交 → 维护者下一场对话直接验收开场括号归零
```

## 明确不做（本方案范围外）

- **temperature 顶格 / season 第一天入秋 / 重启丢 pending**：观察项，见对话分析；不属本次小修
- **意识流/梦的括号**：对内文本允许画面与自由格式，strip 只作用于对外表达出口

---

*基于 22:15–22:49 实测。本方案由 Qoder 撰写，执行任务由 Cursor 承担。*
